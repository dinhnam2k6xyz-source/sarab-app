from typing import List, Type
from app.scrapers.base import BaseScraper
from app.scrapers.generic import GenericScraper
from app.scrapers.adapters.syosetu import SyosetuAdapter
from app.scrapers.adapters.royalroad import RoyalRoadAdapter
from app.scrapers.adapters.readnovelfull import ReadNovelFullAdapter
from app.scrapers.adapters.webtoons import WebtoonsAdapter


class ScraperRegistry:
    def __init__(self):
        self._adapters: List[BaseScraper] = [
            WebtoonsAdapter(),
            SyosetuAdapter(),
            RoyalRoadAdapter(),
            ReadNovelFullAdapter(),
        ]
        self._fallback = GenericScraper()

    def register(self, adapter: BaseScraper):
        """Register a new adapter at high priority."""
        self._adapters.insert(0, adapter)

    def get_scraper(self, url: str) -> BaseScraper:
        """Find the most appropriate scraper for the given URL, or return the generic fallback."""
        for adapter in self._adapters:
            if adapter.can_handle(url):
                return adapter
        return self._fallback


registry = ScraperRegistry()
