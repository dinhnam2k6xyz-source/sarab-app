import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from app.core.security import safe_fetch_url
from app.scrapers.base import BaseScraper, NovelMeta, ChapterMeta, ChapterContentResult


class RoyalRoadAdapter(BaseScraper):
    """Adapter for Royal Road (royalroad.com)."""

    def can_handle(self, url: str) -> bool:
        hostname = urlparse(url).hostname or ""
        return "royalroad.com" in hostname.lower()

    async def get_novel_info(self, url: str) -> NovelMeta:
        response = await safe_fetch_url(url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Title
        title_tag = soup.select_one("div.fic-header h1") or soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else "Royal Road Novel"

        # Author
        author_tag = soup.select_one("div.fic-header h4 a") or soup.select_one(".fic-header a[href*='/profile/']")
        author = author_tag.get_text(strip=True) if author_tag else "Chưa rõ tác giả"

        # Cover
        cover_tag = soup.select_one(".cover-art-container img") or soup.select_one("img.thumbnail")
        cover_url = ""
        if cover_tag and cover_tag.get("src"):
            cover_url = urljoin(url, cover_tag.get("src"))

        # Description
        desc_tag = soup.select_one(".description .hidden-content") or soup.select_one(".description")
        description = desc_tag.get_text(separator="\n", strip=True) if desc_tag else ""

        domain = urlparse(url).netloc

        return NovelMeta(
            title=title,
            author=author,
            cover_url=cover_url,
            description=description,
            source_domain=domain,
        )

    async def get_chapters(self, url: str) -> list[ChapterMeta]:
        response = await safe_fetch_url(url)
        soup = BeautifulSoup(response.text, "html.parser")

        chapters: list[ChapterMeta] = []
        rows = soup.select("table#chapters tbody tr")

        for idx, row in enumerate(rows, start=1):
            a_tag = row.select_one("a[href*='/chapter/']")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            ch_url = urljoin(url, href)
            ch_title = a_tag.get_text(strip=True) or f"Chapter {idx}"
            chapters.append(ChapterMeta(chapter_number=idx, title=ch_title, url=ch_url))

        return chapters

    async def get_chapter_content(self, url: str) -> ChapterContentResult:
        response = await safe_fetch_url(url)
        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.select_one(".chapter-inner h1") or soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else "Chapter"

        content_elem = soup.select_one(".chapter-inner .chapter-content") or soup.select_one(".chapter-content")
        raw_html = str(content_elem) if content_elem else ""

        return ChapterContentResult(
            title=title,
            raw_html=raw_html,
        )
