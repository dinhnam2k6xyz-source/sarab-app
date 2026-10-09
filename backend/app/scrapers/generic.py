import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from app.core.security import safe_fetch_url
from app.scrapers.base import BaseScraper, NovelMeta, ChapterMeta, ChapterContentResult


class GenericScraper(BaseScraper):
    """
    Intelligent Generic Scraper with meta-tag extraction,
    readability heuristics, and heuristic chapter list discovery.
    """

    def can_handle(self, url: str) -> bool:
        # Fallback scraper handles any valid URL
        return True

    def _clean_title(self, raw_title: str) -> str:
        if not raw_title:
            return "Truyện chưa đặt tên"
        cleaned = raw_title.strip()
        # Remove typical website branding suffixes like " - NovelBin", " | Read Light Novel Free"
        cleaned = re.sub(
            r"\s*[-|–—]\s*(read.*free|novel.*|lightnovel.*|truyen.*|wattpad.*|webnovel.*|syosetu.*)$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        return cleaned.strip() or raw_title.strip()

    async def get_novel_info(self, url: str) -> NovelMeta:
        response = await safe_fetch_url(url)
        # BeautifulSoup auto-detects encoding or uses response.encoding
        soup = BeautifulSoup(response.text, "html.parser")

        # 1. Detect Title
        title = ""
        og_title = soup.select_one("meta[property='og:title']") or soup.select_one("meta[name='twitter:title']")
        if og_title and og_title.get("content"):
            title = self._clean_title(og_title["content"])
        elif soup.find("h1"):
            title = self._clean_title(soup.find("h1").get_text(strip=True))
        elif soup.title:
            title = self._clean_title(soup.title.get_text(strip=True))

        if not title:
            title = "Truyện không có tiêu đề"

        # 2. Detect Author
        author = ""
        meta_author = (
            soup.select_one("meta[name='author']")
            or soup.select_one("meta[property='book:author']")
            or soup.select_one("meta[property='article:author']")
        )
        if meta_author and meta_author.get("content"):
            author = meta_author["content"].strip()
        else:
            # Look for author indicators in page text
            author_candidates = soup.find_all(
                lambda tag: tag.name in ["span", "p", "div", "a"]
                and any(k in tag.get_text(strip=True).lower() for k in ["author:", "tác giả:", "作者：", "written by"])
                and len(tag.get_text(strip=True)) < 80
            )
            if author_candidates:
                cand_text = author_candidates[0].get_text(strip=True)
                cand_clean = re.sub(r"^(author:|tác giả:|作者：|written by)\s*", "", cand_text, flags=re.IGNORECASE)
                if cand_clean:
                    author = cand_clean

        if not author:
            author = "Chưa rõ tác giả"

        # 3. Detect Cover Image
        cover_url = ""
        og_image = soup.select_one("meta[property='og:image']") or soup.select_one("meta[name='twitter:image']")
        if og_image and og_image.get("content"):
            cover_url = urljoin(url, og_image["content"])
        else:
            cover_img = (
                soup.select_one(".cover img")
                or soup.select_one(".book-cover img")
                or soup.select_one(".poster img")
                or soup.select_one("img[alt*='cover' i]")
            )
            if cover_img and cover_img.get("src"):
                cover_url = urljoin(url, cover_img.get("src"))

        # 4. Detect Description
        description = ""
        og_desc = soup.select_one("meta[property='og:description']") or soup.select_one("meta[name='description']")
        if og_desc and og_desc.get("content"):
            description = og_desc["content"].strip()
        else:
            desc_tag = (
                soup.select_one(".description")
                or soup.select_one(".synopsis")
                or soup.select_one(".summary")
                or soup.select_one("#synopsis")
            )
            if desc_tag:
                description = desc_tag.get_text(separator="\n", strip=True)

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
        seen_urls = set()

        # Heuristic 1: Look inside dedicated TOC / Chapter containers
        toc_selectors = [
            "#chapters", ".chapters", "#chapter-list", ".chapter-list",
            ".list-chapter", "#list-chapter", ".toc", "#toc", ".catalog",
            ".episodes", ".volume-list", "ul.list-chapters", ".table-of-contents"
        ]
        
        toc_container = None
        for sel in toc_selectors:
            found = soup.select_one(sel)
            if found and len(found.find_all("a")) >= 2:
                toc_container = found
                break

        anchor_pool = toc_container.find_all("a") if toc_container else soup.find_all("a")

        chapter_patterns = [
            re.compile(r"chapter[-_\s/]*\d+", re.IGNORECASE),
            re.compile(r"chương[-_\s/]*\d+", re.IGNORECASE),
            re.compile(r"第.+[章回]", re.IGNORECASE),
            re.compile(r"episode[-_\s/]*\d+", re.IGNORECASE),
            re.compile(r"part[-_\s/]*\d+", re.IGNORECASE),
            re.compile(r"vol(?:ume)?[-_\s/]*\d+", re.IGNORECASE),
            re.compile(r"ch[-_\s/]*\d+", re.IGNORECASE),
        ]

        ch_num = 1
        for a in anchor_pool:
            href = a.get("href", "")
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            full_link = urljoin(url, href)
            if full_link in seen_urls:
                continue

            text = a.get_text(strip=True)
            if not text:
                continue

            # Check if text or link matches chapter pattern
            matches_pattern = any(p.search(text) for p in chapter_patterns) or any(
                p.search(href) for p in chapter_patterns
            )

            if toc_container or matches_pattern:
                seen_urls.add(full_link)
                chapters.append(
                    ChapterMeta(
                        chapter_number=ch_num,
                        title=text if len(text) < 150 else f"Chương {ch_num}",
                        url=full_link,
                    )
                )
                ch_num += 1

        # Fallback: If no chapter links were found, check if this page is a single chapter page
        if not chapters:
            content_res = await self.get_chapter_content(url)
            if content_res.raw_html and len(content_res.raw_html) > 200:
                novel_info = await self.get_novel_info(url)
                chapters.append(
                    ChapterMeta(
                        chapter_number=1,
                        title=content_res.title or novel_info.title or "Chương 1",
                        url=url,
                    )
                )

        return chapters

    async def get_chapter_content(self, url: str) -> ChapterContentResult:
        response = await safe_fetch_url(url)
        soup = BeautifulSoup(response.text, "html.parser")

        # 1. Detect Chapter Title
        title = ""
        title_candidates = [
            soup.select_one(".chapter-title"),
            soup.select_one(".entry-title"),
            soup.select_one("h1"),
            soup.select_one("h2"),
        ]
        for cand in title_candidates:
            if cand and cand.get_text(strip=True):
                title = cand.get_text(strip=True)
                break

        # 2. Find content container
        content_selectors = [
            "#chapter-content", ".chapter-content", "#chr-content", ".chr-content",
            ".entry-content", ".reading-content", "#content", ".content",
            "article", ".chapter-inner", ".text-content", "#chapterText",
            "#chapter-c", ".epcontent", ".chapter_content", ".story-content"
        ]

        content_elem = None
        for sel in content_selectors:
            cand = soup.select_one(sel)
            if cand:
                # Must contain reasonable amount of text or paragraphs
                p_count = len(cand.find_all("p"))
                text_len = len(cand.get_text(strip=True))
                if p_count >= 2 or text_len > 300:
                    content_elem = cand
                    break

        # 3. Density heuristic fallback: find div with maximum <p> tags
        if not content_elem:
            divs = soup.find_all(["div", "article", "section"])
            best_score = 0
            for d in divs:
                p_count = len(d.find_all("p", recursive=False))
                text_len = len(d.get_text(strip=True))
                score = p_count * 100 + min(text_len, 5000)
                if score > best_score:
                    best_score = score
                    content_elem = d

        raw_html = str(content_elem) if content_elem else ""

        return ChapterContentResult(
            title=title or "Chương",
            raw_html=raw_html,
        )
