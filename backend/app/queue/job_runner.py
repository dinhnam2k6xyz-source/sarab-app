import asyncio
import json
import uuid
from typing import Dict, List, Optional
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.logging import log_event
from app.models.novel import (
    Novel,
    Chapter,
    ChapterContent,
    Translation,
    TranslationJob,
    TranslationGlossary,
    ChapterStatus,
    JobStatus,
)
from app.scrapers.registry import registry
from app.cleaner.cleaner import ContentCleaner
from app.translator.manager import translation_manager


class JobProgressHub:
    """In-memory event hub for Server-Sent Events (SSE) and WebSocket subscribers."""

    def __init__(self):
        # job_id -> list of asyncio.Queue
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue:
        queue = asyncio.Queue()
        if job_id not in self._subscribers:
            self._subscribers[job_id] = []
        self._subscribers[job_id].append(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue):
        if job_id in self._subscribers:
            if queue in self._subscribers[job_id]:
                self._subscribers[job_id].remove(queue)
            if not self._subscribers[job_id]:
                del self._subscribers[job_id]

    async def broadcast(self, job_id: str, event_data: dict):
        if job_id in self._subscribers:
            for queue in self._subscribers[job_id]:
                await queue.put(event_data)


progress_hub = JobProgressHub()


async def execute_translation_job(job_id: str, chapter_id: int, force: bool = False):
    """
    Core translation worker pipeline:
    queued -> processing (scraping/cleaning) -> translating (chunking & AI) -> quality_check -> completed
    """
    async with AsyncSessionLocal() as session:
        # Load job & chapter
        job_stmt = select(TranslationJob).where(TranslationJob.id == job_id)
        job_res = await session.execute(job_stmt)
        job = job_res.scalars().first()
        if not job:
            return

        chapter_stmt = select(Chapter).where(Chapter.id == chapter_id)
        chap_res = await session.execute(chapter_stmt)
        chapter = chap_res.scalars().first()
        if not chapter:
            job.status = JobStatus.FAILED.value
            job.error_message = "Không tìm thấy chương trong cơ sở dữ liệu."
            await session.commit()
            return

        novel_stmt = select(Novel).where(Novel.id == chapter.novel_id)
        novel_res = await session.execute(novel_stmt)
        novel = novel_res.scalars().first()

        async def update_progress(status: str, cur_chunk: int, tot_chunks: int, pct: int, msg: str, err: str = ""):
            job.status = status
            job.current_chunk = cur_chunk
            job.total_chunks = tot_chunks
            job.progress_percent = pct
            job.message = msg
            if err:
                job.error_message = err
            await session.commit()

            event = {
                "job_id": job_id,
                "chapter_id": chapter_id,
                "status": status,
                "current_chunk": cur_chunk,
                "total_chunks": tot_chunks,
                "progress_percent": pct,
                "message": msg,
                "error": err,
            }
            await progress_hub.broadcast(job_id, event)

        try:
            # 1. Processing: Loading content
            await update_progress(JobStatus.PROCESSING.value, 0, 0, 10, "Đang tải nội dung chương...")
            chapter.status = ChapterStatus.PROCESSING.value
            await session.commit()

            # Check if content exists
            content_stmt = select(ChapterContent).where(ChapterContent.chapter_id == chapter_id)
            c_res = await session.execute(content_stmt)
            content_obj = c_res.scalars().first()

            if not content_obj or not content_obj.cleaned_text:
                # Scrape chapter content
                scraper = registry.get_scraper(chapter.url)
                scraped_res = await scraper.get_chapter_content(chapter.url)
                if not scraped_res.raw_html:
                    raise RuntimeError("Không thể lấy nội dung từ URL của chương này.")

                cleaned_text, p_count, sha_hash = ContentCleaner.clean(
                    scraped_res.raw_html, chapter_title=chapter.title
                )

                if not content_obj:
                    content_obj = ChapterContent(
                        chapter_id=chapter_id,
                        raw_html=scraped_res.raw_html,
                        cleaned_text=cleaned_text,
                        paragraph_count=p_count,
                        char_count=len(cleaned_text),
                        source_hash=sha_hash,
                    )
                    session.add(content_obj)
                else:
                    content_obj.raw_html = scraped_res.raw_html
                    content_obj.cleaned_text = cleaned_text
                    content_obj.paragraph_count = p_count
                    content_obj.char_count = len(cleaned_text)
                    content_obj.source_hash = sha_hash

                await session.commit()
            else:
                cleaned_text = content_obj.cleaned_text
                sha_hash = content_obj.source_hash

            # 2. Check Cache
            if not force and sha_hash:
                trans_stmt = select(Translation).where(Translation.chapter_id == chapter_id)
                t_res = await session.execute(trans_stmt)
                existing_trans = t_res.scalars().first()
                if existing_trans and existing_trans.translated_text and existing_trans.source_hash == sha_hash:
                    chapter.status = ChapterStatus.COMPLETED.value
                    await update_progress(
                        JobStatus.COMPLETED.value,
                        1,
                        1,
                        100,
                        "Hoàn tất từ bản dịch đã lưu (Cache)!",
                    )
                    return

            # 3. Load Glossary
            glossary_dict: Dict[str, str] = {}
            if novel:
                gloss_stmt = select(TranslationGlossary).where(TranslationGlossary.novel_id == novel.id)
                g_res = await session.execute(gloss_stmt)
                for item in g_res.scalars().all():
                    glossary_dict[item.source_term] = item.translated_term

            # 4. Translating
            chapter.status = ChapterStatus.TRANSLATING.value
            await session.commit()

            async def direct_progress_callback(cur: int, tot: int, pct: int, msg: str):
                await update_progress(JobStatus.TRANSLATING.value, cur, tot, pct, msg)

            trans_title, trans_text, prov_name, quality_score = await translation_manager.translate_chapter(
                cleaned_text=cleaned_text,
                chapter_title=chapter.title,
                glossary=glossary_dict,
                progress_callback=direct_progress_callback,
            )

            # 5. Quality Check
            await update_progress(JobStatus.QUALITY_CHECK.value, 0, 0, 95, "Đang kiểm tra chất lượng hoàn tất...")

            # 6. Save Translation
            trans_stmt = select(Translation).where(Translation.chapter_id == chapter_id)
            t_res = await session.execute(trans_stmt)
            trans_obj = t_res.scalars().first()

            if not trans_obj:
                trans_obj = Translation(
                    chapter_id=chapter_id,
                    source_hash=sha_hash,
                    translated_title=trans_title,
                    translated_text=trans_text,
                    provider=prov_name,
                    model="",
                    char_count=len(trans_text),
                    quality_score=quality_score,
                )
                session.add(trans_obj)
            else:
                trans_obj.source_hash = sha_hash
                trans_obj.translated_title = trans_title
                trans_obj.translated_text = trans_text
                trans_obj.provider = prov_name
            # 7. If this is a comic chapter with images, pre-translate comic panels
            if "[IMG:" in trans_text:
                import re, hashlib, os, httpx
                from app.image_translator.bubble_translator import CACHE_DIR, translate_comic_image_with_status
                img_urls = re.findall(r"\[IMG:(.*?)\]", trans_text)
                if img_urls:
                    tot_imgs = len(img_urls)
                    async with httpx.AsyncClient(timeout=35.0, follow_redirects=True) as p_client:
                        for p_idx, p_url in enumerate(img_urls):
                            p_pct = int(90 + (p_idx / tot_imgs) * 9)
                            await update_progress(
                                JobStatus.TRANSLATING.value,
                                p_idx + 1,
                                tot_imgs,
                                p_pct,
                                f"Đang tiền xử lý dịch tranh ({p_idx + 1}/{tot_imgs})...",
                            )
                            try:
                                p_hash = hashlib.sha256(p_url.encode("utf-8")).hexdigest()
                                p_cache_file = os.path.join(CACHE_DIR, f"url_{p_hash}.jpg")
                                if not os.path.exists(p_cache_file):
                                    hdrs = {
                                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                        "Accept": "image/*",
                                    }
                                    if "webtoon" in p_url or "pstatic.net" in p_url:
                                        hdrs["Referer"] = "https://www.webtoons.com/"
                                    r_img = await p_client.get(p_url, headers=hdrs)
                                    if r_img.status_code == 200:
                                        out_bytes, was_tr = await translate_comic_image_with_status(r_img.content, p_url)
                                        if was_tr:
                                            with open(p_cache_file, "wb") as f_out:
                                                f_out.write(out_bytes)
                                await asyncio.sleep(0.2)
                            except Exception:
                                pass

            chapter.status = ChapterStatus.COMPLETED.value
            await session.commit()

            # 7. Completed
            await update_progress(
                JobStatus.COMPLETED.value,
                job.total_chunks,
                job.total_chunks,
                100,
                "Hoàn thành dịch chương thành công!",
            )

        except Exception as exc:
            err_msg = str(exc)
            chapter.status = ChapterStatus.FAILED.value
            await session.commit()
            await update_progress(JobStatus.FAILED.value, 0, 0, 0, "Lỗi trong quá trình dịch thuật.", err=err_msg)
            log_event(
                event_type="translation_job_failure",
                chapter=str(chapter_id),
                status="error",
                error=err_msg,
            )


async def enqueue_translation_job(chapter_id: int, novel_id: Optional[int] = None, force: bool = False) -> str:
    """Create and enqueue a background translation job."""
    job_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as session:
        job = TranslationJob(
            id=job_id,
            chapter_id=chapter_id,
            novel_id=novel_id,
            status=JobStatus.QUEUED.value,
            message="Đang chuẩn bị hàng đợi...",
        )
        session.add(job)
        await session.commit()

    asyncio.create_task(execute_translation_job(job_id, chapter_id, force))
    return job_id
