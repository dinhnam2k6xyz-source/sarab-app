import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from app.core.security import safe_fetch_url
from app.scrapers.base import BaseScraper, NovelMeta, ChapterMeta, ChapterContentResult


class ReadNovelFullAdapter(BaseScraper):
    """Adapter for ReadNovelFull / NovelFull style platforms."""

    def can_handle(self, url: str) -> bool:
        hostname = urlparse(url).hostname or ""
        return any(x in hostname.lower() for x in ["readnovelfull", "novelfull", "boxnovel", "wuxiaworld"])

    async def get_novel_info(self, url: str) -> NovelMeta:
        response = await safe_fetch_url(url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Title
        title_tag = (
            soup.select_one("div.book-info h3.title")
            or soup.select_one("div.desc h3.title")
            or soup.select_one("h1.novel-title")
            or soup.find("h1")
        )
        title = title_tag.get_text(strip=True) if title_tag else "Novel"

        # Author
        author_tag = (
            soup.select_one("div.info a[href*='author']")
            or soup.select_one(".novel-info a[href*='author']")
            or soup.select_one("span.author a")
        )
        author = author_tag.get_text(strip=True) if author_tag else "Chưa rõ tác giả"

        # Cover
        cover_tag = (
            soup.select_one(".book-info img")
            or soup.select_one(".book-img img")
            or soup.select_one("div.cover img")
        )
        cover_url = ""
        if cover_tag:
            src = cover_tag.get("data-src") or cover_tag.get("src") or ""
            if src:
                cover_url = urljoin(url, src)

        # Description
        desc_tag = (
            soup.select_one(".desc-text")
            or soup.select_one(".panel-body")
            or soup.select_one("div.description")
        )
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
        links = soup.select("#list-chapter .list-chapter li a") or soup.select(".list-chapter a") or soup.select("ul.chapter-list li a")

        for idx, a_tag in enumerate(links, start=1):
            href = a_tag.get("href", "")
            ch_url = urljoin(url, href)
            ch_title = a_tag.get_text(strip=True) or f"Chapter {idx}"
            chapters.append(ChapterMeta(chapter_number=idx, title=ch_title, url=ch_url))

        return chapters

    async def get_chapter_content(self, url: str) -> ChapterContentResult:
        response = await safe_fetch_url(url)
        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.select_one("a.chapter-title") or soup.select_one("h2") or soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else "Chapter"

        content_elem = (
            soup.select_one("div#chr-content")
            or soup.select_one("div#chapter-content")
            or soup.select_one("div.chapter-content")
            or soup.select_one("div.cha-content")
        )
        raw_html = str(content_elem) if content_elem else ""

        return ChapterContentResult(
            title=title,
            raw_html=raw_html,
        )
