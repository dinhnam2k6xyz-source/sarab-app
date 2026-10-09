import enum
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
    func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class ChapterStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    TRANSLATING = "translating"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    TRANSLATING = "translating"
    QUALITY_CHECK = "quality_check"
    COMPLETED = "completed"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    novels = relationship("Novel", back_populates="user", cascade="all, delete-orphan")


class Novel(Base):
    __tablename__ = "novels"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    url = Column(String(1024), unique=True, index=True, nullable=False)
    title = Column(String(500), index=True, nullable=False)
    author = Column(String(255), default="Chưa rõ tác giả")
    cover_url = Column(String(1024), default="")
    description = Column(Text, default="")
    source_domain = Column(String(255), default="")
    total_chapters = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="novels")
    chapters = relationship(
        "Chapter",
        back_populates="novel",
        cascade="all, delete-orphan",
        order_by="Chapter.chapter_number",
    )
    glossary_items = relationship(
        "TranslationGlossary",
        back_populates="novel",
        cascade="all, delete-orphan",
    )
    crawl_logs = relationship("CrawlLog", back_populates="novel", cascade="all, delete-orphan")


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    chapter_number = Column(Integer, default=1, index=True)
    title = Column(String(500), nullable=False)
    url = Column(String(1024), nullable=False)
    status = Column(String(50), default="pending", index=True)  # pending, processing, translating, completed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    novel = relationship("Novel", back_populates="chapters")
    content = relationship("ChapterContent", back_populates="chapter", uselist=False, cascade="all, delete-orphan")
    translation = relationship("Translation", back_populates="chapter", uselist=False, cascade="all, delete-orphan")
    jobs = relationship("TranslationJob", back_populates="chapter", cascade="all, delete-orphan")
    crawl_logs = relationship("CrawlLog", back_populates="chapter", cascade="all, delete-orphan")


class ChapterContent(Base):
    __tablename__ = "chapter_contents"

    id = Column(Integer, primary_key=True, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), unique=True, nullable=False, index=True)
    raw_html = Column(Text, default="")
    cleaned_text = Column(Text, default="")
    paragraph_count = Column(Integer, default=0)
    char_count = Column(Integer, default=0)
    source_hash = Column(String(64), index=True, default="")  # SHA-256
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chapter = relationship("Chapter", back_populates="content")


class Translation(Base):
    __tablename__ = "translations"

    id = Column(Integer, primary_key=True, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), unique=True, nullable=False, index=True)
    source_hash = Column(String(64), index=True, default="")  # For duplicate detection
    translated_title = Column(String(500), default="")
    translated_text = Column(Text, default="")
    provider = Column(String(50), default="gemini")
    model = Column(String(100), default="")
    char_count = Column(Integer, default=0)
    quality_score = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chapter = relationship("Chapter", back_populates="translation")


class TranslationJob(Base):
    __tablename__ = "translation_jobs"

    id = Column(String(36), primary_key=True, index=True)  # UUID
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=True, index=True)
    status = Column(String(50), default="queued", index=True)  # queued, processing, translating, quality_check, completed, failed
    current_chunk = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    progress_percent = Column(Integer, default=0)
    message = Column(String(255), default="Đang chuẩn bị...")
    error_message = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    chapter = relationship("Chapter", back_populates="jobs")


class TranslationGlossary(Base):
    __tablename__ = "translation_glossary"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    source_term = Column(String(255), nullable=False)
    translated_term = Column(String(255), nullable=False)
    note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    novel = relationship("Novel", back_populates="glossary_items")


class TranslationProvider(Base):
    __tablename__ = "translation_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)  # gemini, openai, deepl, offline
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)
    config_json = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CrawlLog(Base):
    __tablename__ = "crawl_logs"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=True, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=True, index=True)
    url = Column(String(1024), default="")
    status_code = Column(Integer, default=200)
    scraper_used = Column(String(100), default="")
    latency_ms = Column(Float, default=0.0)
    error = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    novel = relationship("Novel", back_populates="crawl_logs")
    chapter = relationship("Chapter", back_populates="crawl_logs")
