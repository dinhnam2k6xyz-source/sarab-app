import pytest
from app.scrapers.generic import GenericScraper
from app.scrapers.registry import registry
from app.scrapers.adapters.syosetu import SyosetuAdapter
from app.scrapers.adapters.royalroad import RoyalRoadAdapter
from app.scrapers.adapters.webtoons import WebtoonsAdapter


def test_registry_resolution():
    syosetu_scraper = registry.get_scraper("https://ncode.syosetu.com/n1234ab/")
    assert isinstance(syosetu_scraper, SyosetuAdapter)

    rr_scraper = registry.get_scraper("https://www.royalroad.com/fiction/12345/novel-title")
    assert isinstance(rr_scraper, RoyalRoadAdapter)

    webtoons_scraper = registry.get_scraper("https://www.webtoons.com/en/action/title/episode-1/viewer?title_no=123&episode_no=1")
    assert isinstance(webtoons_scraper, WebtoonsAdapter)

    generic = registry.get_scraper("https://somewebsite.com/novels/test")
    assert isinstance(generic, GenericScraper)


def test_webtoons_adapter_url_normalization():
    adapter = WebtoonsAdapter()
    viewer_url = "https://www.webtoons.com/en/action/the-player-hides-his-past/episode-1/viewer?title_no=5655&episode_no=1"
    list_url = adapter._get_list_url(viewer_url)
    assert "/list?title_no=5655" in list_url


def test_generic_scraper_clean_title():
    scraper = GenericScraper()
    assert scraper._clean_title("My Novel Title - Read Light Novel Free") == "My Novel Title"
    assert scraper._clean_title("Great Story | NovelUpdates") == "Great Story"
