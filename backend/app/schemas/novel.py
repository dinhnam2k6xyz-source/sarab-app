from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict


# Standard Error schema
class ErrorDetail(BaseModel):
    code: str
    message: str


class StandardErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail


# Analyze schemas
class AnalyzeRequest(BaseModel):
    url: str = Field(..., description="URL của trang truyện cần phân tích")


class ChapterItemSchema(BaseModel):
    id: Optional[int] = None
    chapter_number: int
    title: str
    url: str
    status: str = "pending"
    has_translation: bool = False


class NovelAnalyzeData(BaseModel):
    id: Optional[int] = None
    title: str
    author: str = "Chưa rõ tác giả"
    cover: str = ""
    description: str = ""
    url: str
    source_domain: str = ""
    total_chapters: int = 0
    chapters: List[ChapterItemSchema] = []


class AnalyzeResponse(BaseModel):
    success: bool = True
    novel: NovelAnalyzeData


# Novel list and detail
class NovelSummary(BaseModel):
    id: int
    title: str
    author: str
    cover_url: str
    description: str
    url: str
    source_domain: str
    total_chapters: int
    translated_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Translation jobs
class TranslateChapterRequest(BaseModel):
    force: bool = False  # If True, re-translate even if cached


class BulkTranslateRequest(BaseModel):
    chapter_ids: List[int]
    force: bool = False


class TranslationJobResponse(BaseModel):
    job_id: str
    chapter_id: int
    status: str
    current_chunk: int = 0
    total_chunks: int = 0
    progress_percent: int = 0
    message: str = "Đang chuẩn bị..."
    error_message: Optional[str] = None


class BulkTranslateResponse(BaseModel):
    success: bool = True
    queued_count: int
    jobs: List[TranslationJobResponse]


# Reader schema
class ReaderResponse(BaseModel):
    chapter_id: int
    novel_id: int
    novel_title: str
    chapter_number: int
    chapter_title: str
    translated_title: str
    translated_text: str
    original_text: str
    prev_chapter_id: Optional[int] = None
    next_chapter_id: Optional[int] = None
    status: str


# Glossary schemas
class GlossaryCreateRequest(BaseModel):
    source_term: str
    translated_term: str
    note: Optional[str] = ""


class GlossaryItemResponse(BaseModel):
    id: int
    novel_id: int
    source_term: str
    translated_term: str
    note: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
