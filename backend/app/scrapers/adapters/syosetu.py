import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from app.core.security import safe_fetch_url
from app.scrapers.base import BaseScraper, NovelMeta, ChapterMeta, ChapterContentResult


class SyosetuAdapter(BaseScraper):
    """Adapter for Syosetu (Shousetsuka ni Narou - ncode.syosetu.com / novel18.syosetu.com)."""

    def can_handle(self, url: str) -> bool:
        hostname = urlparse(url).hostname or ""
        return "syosetu.com" in hostname.lower()

    async def get_novel_info(self, url: str) -> NovelMeta:
        response = await safe_fetch_url(url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Title
        title_tag = (
            soup.select_one(".p-novel__title")
            or soup.select_one("p.novel_title")
            or soup.select_one("h1.novel_title")
            or soup.find("h1")
        )
        title = title_tag.get_text(strip=True) if title_tag else "Syosetu Novel"

        # Author
        author_tag = (
            soup.select_one(".p-novel__author a")
            or soup.select_one(".p-novel__author")
            or soup.select_one("div.novel_writername a")
            or soup.select_one("div.novel_writername")
        )
        author = author_tag.get_text(strip=True).replace("作者：", "").strip() if author_tag else "Chưa rõ tác giả"

        # Description
        desc_tag = (
            soup.select_one(".p-novel__summary")
            or soup.select_one("div#novel_ex")
            or soup.select_one(".novel_ex")
        )
        description = desc_tag.get_text(separator="\n", strip=True) if desc_tag else ""

        # Syosetu usually does not have covers for amateur web novels, provide placeholder or default icon
        cover_url = ""

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
        chapter_links = (
            soup.select(".p-eplist__sublist a")
            or soup.select("dl.novel_sublist2 dd.subtitle a")
            or soup.select(".index_box a[href*='/']")
        )

        # If it's a short story (tanpen) without chapter list, the page itself is chapter 1
        if not chapter_links and (soup.select_one(".p-novel__body") or soup.select_one("#honbun")):
            return [ChapterMeta(chapter_number=1, title="Toàn văn (Đoản văn)", url=url)]

        for idx, a_tag in enumerate(chapter_links, start=1):
            href = a_tag.get("href", "")
            ch_url = urljoin(url, href)
            ch_title = a_tag.get_text(strip=True) or f"Chương {idx}"
            chapters.append(ChapterMeta(chapter_number=idx, title=ch_title, url=ch_url))

        return chapters

    async def get_chapter_content(self, url: str) -> ChapterContentResult:
        response = await safe_fetch_url(url)
        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = (
            soup.select_one(".p-novel__subtitle")
            or soup.select_one(".novel_subtitle")
            or soup.find("h1")
        )
        title = title_tag.get_text(strip=True) if title_tag else "Chương"

        content_elem = (
            soup.select_one(".p-novel__body")
            or soup.select_one(".p-novel__text")
            or soup.select_one("div#honbun")
            or soup.select_one(".novel_honbun")
            or soup.select_one("#novel_p")
        )
        raw_html = str(content_elem) if content_elem else ""

        return ChapterContentResult(
            title=title,
            raw_html=raw_html,
        )
