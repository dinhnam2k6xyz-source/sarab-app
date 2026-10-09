from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc
from app.core.database import get_db
from app.models.novel import Novel, Chapter, Translation
from app.schemas.novel import NovelSummary, ChapterItemSchema

router = APIRouter()


@router.get("", response_model=List[NovelSummary])
async def list_novels(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all analyzed novels with translation counts."""
    query = select(Novel).order_by(desc(Novel.updated_at))
    if search:
        query = query.where(Novel.title.ilike(f"%{search.strip()}%"))
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    novels = result.scalars().all()

    response_list = []
    for n in novels:
        # Count translated chapters
        count_stmt = select(func.count(Chapter.id)).where(
            Chapter.novel_id == n.id,
            Chapter.status == "completed",
        )
        c_res = await db.execute(count_stmt)
        trans_count = c_res.scalar() or 0

        response_list.append(
            NovelSummary(
                id=n.id,
                title=n.title,
                author=n.author,
                cover_url=n.cover_url,
                description=n.description,
                url=n.url,
                source_domain=n.source_domain,
                total_chapters=n.total_chapters,
                translated_count=trans_count,
                created_at=n.created_at,
            )
        )
    return response_list


@router.get("/{novel_id}")
async def get_novel_detail(
    novel_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get novel metadata and statistics."""
    stmt = select(Novel).where(Novel.id == novel_id)
    res = await db.execute(stmt)
    novel = res.scalars().first()
    if not novel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Không tìm thấy truyện với ID {novel_id}"},
        )

    # Count translated
    count_stmt = select(func.count(Chapter.id)).where(
        Chapter.novel_id == novel.id,
        Chapter.status == "completed",
    )
    c_res = await db.execute(count_stmt)
    trans_count = c_res.scalar() or 0

    return {
        "id": novel.id,
        "title": novel.title,
        "author": novel.author,
        "cover_url": novel.cover_url,
        "description": novel.description,
        "url": novel.url,
        "source_domain": novel.source_domain,
        "total_chapters": novel.total_chapters,
        "translated_count": trans_count,
        "created_at": novel.created_at,
        "updated_at": novel.updated_at,
    }


@router.get("/{novel_id}/chapters", response_model=List[ChapterItemSchema])
async def get_novel_chapters(
    novel_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort: str = Query("asc", pattern="^(asc|desc)$"),
    search: Optional[str] = None,
    filter_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get chapter list of a novel with search, sort, and pagination."""
    query = select(Chapter).where(Chapter.novel_id == novel_id)

    if search:
        query = query.where(Chapter.title.ilike(f"%{search.strip()}%"))
    if filter_status:
        query = query.where(Chapter.status == filter_status)

    if sort == "desc":
        query = query.order_by(desc(Chapter.chapter_number))
    else:
        query = query.order_by(asc(Chapter.chapter_number))

    query = query.offset(offset).limit(limit)

    res = await db.execute(query)
    chapters = res.scalars().all()

    return [
        ChapterItemSchema(
            id=c.id,
            chapter_number=c.chapter_number,
            title=c.title,
            url=c.url,
            status=c.status,
            has_translation=(c.status == "completed"),
        )
        for c in chapters
    ]


@router.delete("/{novel_id}")
async def delete_novel(
    novel_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a novel and all associated chapters and translations."""
    stmt = select(Novel).where(Novel.id == novel_id)
    res = await db.execute(stmt)
    novel = res.scalars().first()
    if not novel:
        raise HTTPException(status_code=404, detail="Không tìm thấy truyện để xóa.")

    await db.delete(novel)
    await db.commit()
    return {"success": True, "message": "Đã xóa truyện thành công."}
