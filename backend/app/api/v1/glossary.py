from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.novel import Novel, TranslationGlossary
from app.schemas.novel import GlossaryCreateRequest, GlossaryItemResponse

router = APIRouter()


@router.get("/novels/{novel_id}/glossary", response_model=List[GlossaryItemResponse])
async def get_glossary_terms(
    novel_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all translation glossary terms for a specific novel."""
    stmt = select(TranslationGlossary).where(TranslationGlossary.novel_id == novel_id).order_by(TranslationGlossary.id)
    res = await db.execute(stmt)
    terms = res.scalars().all()
    return terms


@router.post("/novels/{novel_id}/glossary", response_model=GlossaryItemResponse)
async def add_glossary_term(
    novel_id: int,
    req: GlossaryCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Add or update a glossary term for a novel."""
    # Verify novel exists
    n_stmt = select(Novel).where(Novel.id == novel_id)
    n_res = await db.execute(n_stmt)
    novel = n_res.scalars().first()
    if not novel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Không tìm thấy bộ truyện này."},
        )

    # Check if term already exists
    stmt = select(TranslationGlossary).where(
        TranslationGlossary.novel_id == novel_id,
        TranslationGlossary.source_term == req.source_term.strip(),
    )
    res = await db.execute(stmt)
    existing = res.scalars().first()

    if existing:
        existing.translated_term = req.translated_term.strip()
        existing.note = req.note or ""
        await db.commit()
        await db.refresh(existing)
        return existing

    term = TranslationGlossary(
        novel_id=novel_id,
        source_term=req.source_term.strip(),
        translated_term=req.translated_term.strip(),
        note=req.note or "",
    )
    db.add(term)
    await db.commit()
    await db.refresh(term)
    return term


@router.delete("/novels/{novel_id}/glossary/{term_id}")
async def delete_glossary_term(
    novel_id: int,
    term_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a glossary term."""
    stmt = select(TranslationGlossary).where(
        TranslationGlossary.id == term_id,
        TranslationGlossary.novel_id == novel_id,
    )
    res = await db.execute(stmt)
    term = res.scalars().first()
    if not term:
        raise HTTPException(status_code=404, detail="Không tìm thấy thuật ngữ cần xóa.")

    await db.delete(term)
    await db.commit()
    return {"success": True, "message": "Đã xóa thuật ngữ thành công."}
