from typing import List, Optional
from pydantic import BaseModel
from app.core.config import settings


class ChunkItem(BaseModel):
    chunk_index: int
    total_chunks: int = 1
    paragraphs: List[str]
    text: str
    context_hint: str = ""


class ContentChunker:
    """Smart chunking preserving paragraph boundaries and dialogue context."""

    @staticmethod
    def chunk(
        cleaned_text: str,
        max_chunk_chars: Optional[int] = None,
        context_paragraphs_count: Optional[int] = None,
    ) -> List[ChunkItem]:
        max_chars = max_chunk_chars or settings.CHUNK_MAX_CHARS
        context_count = context_paragraphs_count or settings.CHUNK_OVERLAP_CONTEXT_PARAS

        if not cleaned_text or not cleaned_text.strip():
            return []

        all_paras = [p.strip() for p in cleaned_text.split("\n\n") if p.strip()]
        if not all_paras:
            return []

        chunks_paras: List[List[str]] = []
        current_chunk: List[str] = []
        current_len = 0

        for para in all_paras:
            para_len = len(para) + 2  # account for \n\n

            # If adding this paragraph exceeds limit and current chunk has paragraphs
            if current_len + para_len > max_chars and current_chunk:
                chunks_paras.append(current_chunk)
                current_chunk = [para]
                current_len = para_len
            else:
                current_chunk.append(para)
                current_len += para_len

        if current_chunk:
            chunks_paras.append(current_chunk)

        total_chunks = len(chunks_paras)
        result: List[ChunkItem] = []

        for idx, c_paras in enumerate(chunks_paras, start=1):
            chunk_text = "\n\n".join(c_paras)

            # Context hint from preceding chunk
            context_hint = ""
            if idx > 1:
                prev_paras = chunks_paras[idx - 2]
                overlap = prev_paras[-context_count:] if len(prev_paras) >= context_count else prev_paras
                context_hint = "\n\n".join(overlap)

            result.append(
                ChunkItem(
                    chunk_index=idx,
                    total_chunks=total_chunks,
                    paragraphs=c_paras,
                    text=chunk_text,
                    context_hint=context_hint,
                )
            )

        return result
