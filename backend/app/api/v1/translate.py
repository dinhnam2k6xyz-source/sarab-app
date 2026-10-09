from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.rate_limit import rate_limit_translate
from app.models.novel import Chapter, TranslationJob
from app.schemas.novel import (
    TranslateChapterRequest,
    BulkTranslateRequest,
    TranslationJobResponse,
    BulkTranslateResponse,
)
from app.queue.job_runner import enqueue_translation_job

router = APIRouter()


@router.post(
    "/chapter/{chapter_id}",
    response_model=TranslationJobResponse,
    dependencies=[Depends(rate_limit_translate)],
)
async def translate_single_chapter(
    chapter_id: int,
    req: TranslateChapterRequest = TranslateChapterRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Queue background translation for a single chapter.
    Returns job_id and status 'queued'.
    """
    stmt = select(Chapter).where(Chapter.id == chapter_id)
    res = await db.execute(stmt)
    chapter = res.scalars().first()
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Không tìm thấy chương {chapter_id}."},
        )

    job_id = await enqueue_translation_job(
        chapter_id=chapter.id,
        novel_id=chapter.novel_id,
        force=req.force,
    )

    return TranslationJobResponse(
        job_id=job_id,
        chapter_id=chapter.id,
        status="queued",
        current_chunk=0,
        total_chunks=0,
        progress_percent=0,
        message="Đã đưa vào hàng đợi dịch...",
    )


@router.post(
    "/bulk",
    response_model=BulkTranslateResponse,
    dependencies=[Depends(rate_limit_translate)],
)
async def translate_bulk_chapters(
    req: BulkTranslateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Queue background translation for multiple chapters.
    """
    if not req.chapter_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMPTY_SELECTION", "message": "Vui lòng chọn ít nhất một chương để dịch."},
        )

    # Limit maximum batch size to prevent abuse
    if len(req.chapter_ids) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BATCH_TOO_LARGE", "message": "Chỉ có thể chọn tối đa 50 chương trong một lần dịch hàng loạt."},
        )

    stmt = select(Chapter).where(Chapter.id.in_(req.chapter_ids))
    res = await db.execute(stmt)
    chapters = res.scalars().all()

    jobs_response: List[TranslationJobResponse] = []
    for chapter in chapters:
        job_id = await enqueue_translation_job(
            chapter_id=chapter.id,
            novel_id=chapter.novel_id,
            force=req.force,
        )
        jobs_response.append(
            TranslationJobResponse(
                job_id=job_id,
                chapter_id=chapter.id,
                status="queued",
                current_chunk=0,
                total_chunks=0,
                progress_percent=0,
                message="Đã đưa vào hàng đợi dịch...",
            )
        )

    return BulkTranslateResponse(
        success=True,
        queued_count=len(jobs_response),
        jobs=jobs_response,
    )
