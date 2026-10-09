import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.novel import TranslationJob
from app.schemas.novel import TranslationJobResponse
from app.queue.job_runner import progress_hub

router = APIRouter()


@router.get("/jobs/{job_id}", response_model=TranslationJobResponse)
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get current status and progress of a translation job."""
    stmt = select(TranslationJob).where(TranslationJob.id == job_id)
    res = await db.execute(stmt)
    job = res.scalars().first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Không tìm thấy tiến trình dịch {job_id}."},
        )

    return TranslationJobResponse(
        job_id=job.id,
        chapter_id=job.chapter_id,
        status=job.status,
        current_chunk=job.current_chunk,
        total_chunks=job.total_chunks,
        progress_percent=job.progress_percent,
        message=job.message,
        error_message=job.error_message,
    )


@router.get("/jobs/{job_id}/events")
async def stream_job_events(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Server-Sent Events (SSE) stream for realtime translation progress.
    Streams event updates directly to frontend without polling delay.
    """
    stmt = select(TranslationJob).where(TranslationJob.id == job_id)
    res = await db.execute(stmt)
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy công việc.")

    queue = progress_hub.subscribe(job_id)

    async def event_generator():
        # First send initial state
        initial_data = {
            "job_id": job.id,
            "chapter_id": job.chapter_id,
            "status": job.status,
            "current_chunk": job.current_chunk,
            "total_chunks": job.total_chunks,
            "progress_percent": job.progress_percent,
            "message": job.message,
            "error": job.error_message,
        }
        yield f"data: {json.dumps(initial_data)}\n\n"

        if job.status in ("completed", "failed"):
            progress_hub.unsubscribe(job_id, queue)
            return

        try:
            while True:
                # Wait for next event or send keep-alive every 15s
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("status") in ("completed", "failed"):
                        break
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            progress_hub.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.websocket("/ws/jobs/{job_id}")
async def websocket_job_progress(websocket: WebSocket, job_id: str):
    """WebSocket alternative for live progress."""
    await websocket.accept()
    queue = progress_hub.subscribe(job_id)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event.get("status") in ("completed", "failed"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        progress_hub.unsubscribe(job_id, queue)
