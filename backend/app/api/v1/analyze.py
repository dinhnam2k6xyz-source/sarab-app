import time
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.rate_limit import rate_limit_analyze
from app.core.security import validate_url_ssrf
from app.core.logging import log_event
from app.models.novel import Novel, Chapter, CrawlLog
from app.schemas.novel import AnalyzeRequest, AnalyzeResponse, NovelAnalyzeData, ChapterItemSchema
from app.scrapers.registry import registry

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(rate_limit_analyze)])
async def analyze_url(
    req: AnalyzeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Analyzes novel URL, detects title, author, cover, description, chapter list,
    and records novel into database.
    """
    url = req.url.strip()
    req_id = getattr(request.state, "request_id", "")
    start_time = time.time()

    # 1. SSRF Validation
    is_safe, error_msg = validate_url_ssrf(url)
    if not is_safe:
        log_event("analyze_ssrf_blocked", request_id=req_id, url=url, status="error", error=error_msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "SSRF_BLOCKED", "message": error_msg},
        )

    # 2. Get Scraper
    scraper = registry.get_scraper(url)
    scraper_name = scraper.__class__.__name__

    try:
        novel_meta, chapters_meta = await scraper.get_full_novel(url)
    except Exception as exc:
        latency = (time.time() - start_time) * 1000
        err_str = str(exc)
        log_event(
            "analyze_scrape_error",
            request_id=req_id,
            url=url,
            scraper=scraper_name,
            latency_ms=latency,
            status="error",
            error=err_str,
        )

        user_friendly_msg = "Không thể lấy nội dung từ URL này. Vui lòng kiểm tra lại liên kết hoặc thử website khác."
        if "403" in err_str or "Forbidden" in err_str:
            user_friendly_msg = "Website nguồn từ chối kết nối hoặc yêu cầu xác thực bảo mật."
        elif "timeout" in err_str.lower() or "timed out" in err_str.lower():
            user_friendly_msg = "Website nguồn đang phản hồi quá chậm, kết nối bị quá hạn (Timeout)."

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "SCRAPE_FAILED", "message": user_friendly_msg},
        )

    latency = (time.time() - start_time) * 1000

    # 3. Save or update Novel in Database
    novel_stmt = select(Novel).where(Novel.url == url)
    res = await db.execute(novel_stmt)
    novel = res.scalars().first()

    if not novel:
        novel = Novel(
            url=url,
            title=novel_meta.title,
            author=novel_meta.author,
            cover_url=novel_meta.cover_url,
            description=novel_meta.description,
            source_domain=novel_meta.source_domain,
            total_chapters=len(chapters_meta),
        )
        db.add(novel)
        await db.flush()  # get novel.id
    else:
        novel.title = novel_meta.title
        novel.author = novel_meta.author
        if novel_meta.cover_url:
            novel.cover_url = novel_meta.cover_url
        if novel_meta.description:
            novel.description = novel_meta.description
        novel.total_chapters = len(chapters_meta)
        await db.flush()

    # Log crawl success
    crawl_log = CrawlLog(
        novel_id=novel.id,
        url=url,
        status_code=200,
        scraper_used=scraper_name,
        latency_ms=latency,
    )
    db.add(crawl_log)

    # 4. Save chapters if novel has new or updated chapters
    existing_chaps_stmt = select(Chapter).where(Chapter.novel_id == novel.id)
    ch_res = await db.execute(existing_chaps_stmt)
    existing_chaps = {c.chapter_number: c for c in ch_res.scalars().all()}

    saved_chapters: list[ChapterItemSchema] = []
    for ch in chapters_meta:
        if ch.chapter_number in existing_chaps:
            c_db = existing_chaps[ch.chapter_number]
            c_db.title = ch.title
            c_db.url = ch.url
            saved_chapters.append(
                ChapterItemSchema(
                    id=c_db.id,
                    chapter_number=c_db.chapter_number,
                    title=c_db.title,
                    url=c_db.url,
                    status=c_db.status,
                    has_translation=(c_db.status == "completed"),
                )
            )
        else:
            c_db = Chapter(
                novel_id=novel.id,
                chapter_number=ch.chapter_number,
                title=ch.title,
                url=ch.url,
                status="pending",
            )
            db.add(c_db)
            await db.flush()
            saved_chapters.append(
                ChapterItemSchema(
                    id=c_db.id,
                    chapter_number=c_db.chapter_number,
                    title=c_db.title,
                    url=c_db.url,
                    status="pending",
                    has_translation=False,
                )
            )

    await db.commit()
    await db.refresh(novel)

    log_event(
        "analyze_success",
        request_id=req_id,
        url=url,
        scraper=scraper_name,
        latency_ms=latency,
        status="ok",
    )

    return AnalyzeResponse(
        success=True,
        novel=NovelAnalyzeData(
            id=novel.id,
            title=novel.title,
            author=novel.author,
            cover=novel.cover_url,
            description=novel.description,
            url=novel.url,
            source_domain=novel.source_domain,
            total_chapters=novel.total_chapters,
            chapters=saved_chapters,
        ),
    )
