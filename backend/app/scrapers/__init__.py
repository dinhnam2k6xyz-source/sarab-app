from app.scrapers.base import BaseScraper, NovelMeta, ChapterMeta, ChapterContentResult
from app.scrapers.generic import GenericScraper
from app.scrapers.registry import registry, ScraperRegistry

__all__ = [
    "BaseScraper",
    "NovelMeta",
    "ChapterMeta",
    "ChapterContentResult",
    "GenericScraper",
    "registry",
    "ScraperRegistry",
]
