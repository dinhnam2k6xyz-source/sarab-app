from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc, desc
from app.core.database import get_db
from app.models.novel import Novel, Chapter, ChapterContent, Translation
from app.schemas.novel import ReaderResponse

router = APIRouter()


@router.get("/chapters/{chapter_id}")
async def get_chapter(
    chapter_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get single chapter overview."""
    stmt = select(Chapter).where(Chapter.id == chapter_id)
    res = await db.execute(stmt)
    chapter = res.scalars().first()
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Không tìm thấy chương này."},
        )

    return {
        "id": chapter.id,
        "novel_id": chapter.novel_id,
        "chapter_number": chapter.chapter_number,
        "title": chapter.title,
        "url": chapter.url,
        "status": chapter.status,
    }


@router.get("/reader/{chapter_id}", response_model=ReaderResponse)
async def get_reader_content(
    chapter_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get reader content for modern reader interface, including
    translated text, original text, and adjacent chapter navigation IDs.
    """
    stmt = select(Chapter).where(Chapter.id == chapter_id)
    res = await db.execute(stmt)
    chapter = res.scalars().first()
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Không tìm thấy chương {chapter_id}."},
        )

    # Novel details
    n_stmt = select(Novel).where(Novel.id == chapter.novel_id)
    n_res = await db.execute(n_stmt)
    novel = n_res.scalars().first()
    novel_title = novel.title if novel else "Truyện"

    # Chapter content (original)
    c_stmt = select(ChapterContent).where(ChapterContent.chapter_id == chapter_id)
    c_res = await db.execute(c_stmt)
    content_obj = c_res.scalars().first()
    original_text = content_obj.cleaned_text if content_obj else ""

    # Translation
    t_stmt = select(Translation).where(Translation.chapter_id == chapter_id)
    t_res = await db.execute(t_stmt)
    trans_obj = t_res.scalars().first()
    translated_title = trans_obj.translated_title if trans_obj else chapter.title
    translated_text = trans_obj.translated_text if trans_obj else ""

    # Find previous chapter
    prev_stmt = (
        select(Chapter.id)
        .where(
            Chapter.novel_id == chapter.novel_id,
            Chapter.chapter_number < chapter.chapter_number,
        )
        .order_by(desc(Chapter.chapter_number))
        .limit(1)
    )
    prev_res = await db.execute(prev_stmt)
    prev_id = prev_res.scalars().first()

    # Find next chapter
    next_stmt = (
        select(Chapter.id)
        .where(
            Chapter.novel_id == chapter.novel_id,
            Chapter.chapter_number > chapter.chapter_number,
        )
        .order_by(asc(Chapter.chapter_number))
        .limit(1)
    )
    next_res = await db.execute(next_stmt)
    next_id = next_res.scalars().first()

    # Pre-warm / preload comic panels in the background so reading experience is instantaneous
    full_body = translated_text or original_text or ""
    if "[IMG:" in full_body:
        import re, asyncio
        from app.image_translator.bubble_translator import preload_comic_panels_background
        img_urls = re.findall(r"\[IMG:(.*?)\]", full_body)
        if img_urls:
            asyncio.create_task(preload_comic_panels_background(img_urls))

    return ReaderResponse(
        chapter_id=chapter.id,
        novel_id=chapter.novel_id,
        novel_title=novel_title,
        chapter_number=chapter.chapter_number,
        chapter_title=chapter.title,
        translated_title=translated_title or chapter.title,
        translated_text=translated_text,
        original_text=original_text,
        prev_chapter_id=prev_id,
        next_chapter_id=next_id,
        status=chapter.status,
    )
