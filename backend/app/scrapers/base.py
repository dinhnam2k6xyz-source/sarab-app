from pydantic import BaseModel
from typing import List, Optional
from abc import ABC, abstractmethod


class NovelMeta(BaseModel):
    title: str
    author: str = "Chưa rõ tác giả"
    cover_url: str = ""
    description: str = ""
    source_domain: str = ""
    total_chapters: int = 0


class ChapterMeta(BaseModel):
    chapter_number: int
    title: str
    url: str


class ChapterContentResult(BaseModel):
    title: str
    raw_html: str
    cleaned_text: str = ""
    paragraph_count: int = 0


class BaseScraper(ABC):
    """Abstract Base Class for novel web scrapers."""

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Check if this scraper supports the given URL."""
        pass

    @abstractmethod
    async def get_novel_info(self, url: str) -> NovelMeta:
        """Extract novel metadata (title, author, cover, description)."""
        pass

    @abstractmethod
    async def get_chapters(self, url: str) -> List[ChapterMeta]:
        """Extract chapter list from the novel overview page."""
        pass

    @abstractmethod
    async def get_chapter_content(self, url: str) -> ChapterContentResult:
        """Extract chapter title and content from a chapter page."""
        pass

    async def get_full_novel(self, url: str) -> tuple[NovelMeta, List[ChapterMeta]]:
        """Fetch both novel metadata and chapter list."""
        novel_info = await self.get_novel_info(url)
        chapters = await self.get_chapters(url)
        novel_info.total_chapters = len(chapters)
        return novel_info, chapters
