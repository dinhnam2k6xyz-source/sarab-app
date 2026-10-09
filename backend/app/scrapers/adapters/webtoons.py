import re
from urllib.parse import urlparse, parse_qs, urljoin
from bs4 import BeautifulSoup
from app.core.security import safe_fetch_url
from app.scrapers.base import BaseScraper, NovelMeta, ChapterMeta, ChapterContentResult


class WebtoonsAdapter(BaseScraper):
    """
    Dedicated adapter for WEBTOON (webtoons.com).
    Supports comic/manhwa series info, complete episode listing,
    and high-resolution panel image extraction with Referer bypass.
    """

    def can_handle(self, url: str) -> bool:
        hostname = urlparse(url).hostname or ""
        return "webtoons.com" in hostname.lower()

    def _get_list_url(self, url: str) -> str:
        """Convert an episode viewer URL into the main comic series list URL."""
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        title_no = qs.get("title_no", [""])[0]

        if "/viewer" in parsed.path:
            # Reconstruct list URL
            # Path looks like: /en/action/the-player-hides-his-past/episode-1/viewer
            path_parts = parsed.path.rstrip("/").split("/")
            # Remove episode-X and viewer
            if len(path_parts) >= 3 and path_parts[-1] == "viewer":
                series_path = "/".join(path_parts[:-2])  # e.g. /en/action/the-player-hides-his-past
                return f"{parsed.scheme}://{parsed.netloc}{series_path}/list?title_no={title_no}"
        return url

    async def get_novel_info(self, url: str) -> NovelMeta:
        list_url = self._get_list_url(url)
        headers = {"Referer": "https://www.webtoons.com/"}
        response = await safe_fetch_url(list_url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        # 1. Title
        title_tag = (
            soup.select_one(".subj_info .subj")
            or soup.select_one("h1.subj")
            or soup.select_one("meta[property='og:title']")
            or soup.find("h1")
        )
        title = ""
        if title_tag:
            title = title_tag.get("content") if title_tag.name == "meta" else title_tag.get_text(strip=True)

        # Remove " - WEBTOON" suffix if present
        title = re.sub(r"\s*\|\s*WEBTOON$", "", title, flags=re.IGNORECASE).strip()
        if not title:
            title = "Webtoon Comic"

        # 2. Author
        author_tag = (
            soup.select_one(".author_area .author")
            or soup.select_one(".author")
            or soup.select_one("meta[property='com-linewebtoon:webtoon:author']")
            or soup.select_one("meta[name='author']")
        )
        author = "Chưa rõ tác giả"
        if author_tag:
            author = author_tag.get("content") if author_tag.name == "meta" else author_tag.get_text(strip=True)
            author = re.sub(r"^author:\s*", "", author, flags=re.IGNORECASE).strip()

        # 3. Cover
        cover_tag = (
            soup.select_one(".detail_header .thmb img")
            or soup.select_one(".detail_body .thmb img")
            or soup.select_one("meta[property='og:image']")
        )
        cover_url = ""
        if cover_tag:
            cover_url = cover_tag.get("content") if cover_tag.name == "meta" else cover_tag.get("src") or ""
            if cover_url:
                cover_url = urljoin(url, cover_url)

        # 4. Description
        desc_tag = (
            soup.select_one("p.summary")
            or soup.select_one(".summary")
            or soup.select_one("meta[property='og:description']")
        )
        description = ""
        if desc_tag:
            description = desc_tag.get("content") if desc_tag.name == "meta" else desc_tag.get_text(separator="\n", strip=True)

        return NovelMeta(
            title=title,
            author=author,
            cover_url=cover_url,
            description=description,
            source_domain="webtoons.com",
        )

    async def get_chapters(self, url: str) -> list[ChapterMeta]:
        list_url = self._get_list_url(url)
        headers = {"Referer": "https://www.webtoons.com/"}
        response = await safe_fetch_url(list_url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        chapters: list[ChapterMeta] = []
        seen_urls = set()

        # Fetch episodes from list page
        ep_items = soup.select("#_listUl li a") or soup.select(".episode_cont ul li a") or soup.select("ul#_episodeList li a")

        for idx, a_tag in enumerate(ep_items, start=1):
            href = a_tag.get("href", "")
            if not href:
                continue

            full_link = urljoin(list_url, href)
            if full_link in seen_urls:
                continue
            seen_urls.add(full_link)

            # Extract title
            sub_title_tag = a_tag.select_one(".sub_title") or a_tag.select_one("span.subj")
            tx_tag = a_tag.select_one(".tx")

            ep_name = ""
            if tx_tag and sub_title_tag:
                ep_name = f"{tx_tag.get_text(strip=True)} - {sub_title_tag.get_text(strip=True)}"
            elif sub_title_tag:
                ep_name = sub_title_tag.get_text(strip=True)
            elif tx_tag:
                ep_name = tx_tag.get_text(strip=True)
            else:
                ep_name = a_tag.get_text(strip=True)

            # Try to get episode number from URL query
            qs = parse_qs(urlparse(full_link).query)
            ep_no_str = qs.get("episode_no", [""])[0]
            try:
                ep_number = int(ep_no_str)
            except ValueError:
                ep_number = idx

            chapters.append(
                ChapterMeta(
                    chapter_number=ep_number,
                    title=ep_name or f"Episode {ep_number}",
                    url=full_link,
                )
            )

        # Sort chronologically by chapter_number
        chapters.sort(key=lambda c: c.chapter_number)

        # Re-number from 1..N sequentially
        for i, ch in enumerate(chapters, start=1):
            ch.chapter_number = i

        # If given a single viewer page and no episodes list was found, use that viewer page as chapter 1
        if not chapters:
            content_res = await self.get_chapter_content(url)
            chapters.append(
                ChapterMeta(
                    chapter_number=1,
                    title=content_res.title or "Episode 1",
                    url=url,
                )
            )

        return chapters

    async def get_chapter_content(self, url: str) -> ChapterContentResult:
        headers = {"Referer": "https://www.webtoons.com/"}
        response = await safe_fetch_url(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        # 1. Episode Title
        title = ""
        title_tag = soup.select_one("h1.subj") or soup.select_one(".subj_info") or soup.select_one(".subj")
        if title_tag:
            title = title_tag.get_text(strip=True)

        if not title:
            title = "Episode"

        # 2. Extract comic panel images with comprehensive selectors
        img_elements = (
            soup.select("#_imageList img")
            or soup.select(".viewer_lst img")
            or soup.select(".viewer_img img")
            or soup.select("img._images")
            or soup.select(".viewer_body img")
            or soup.select(".viewer_inner img")
            or soup.select("div[class*='viewer'] img")
            or soup.find_all("img", src=re.compile(r"webtoon|pstatic", re.I))
            or soup.find_all("img", attrs={"data-url": re.compile(r"webtoon|pstatic", re.I)})
        )

        content_html_parts = []

        # Optional author/creator note
        creator_note = soup.select_one("#_authorArea") or soup.select_one(".creator_note")
        if creator_note:
            note_text = creator_note.get_text(strip=True)
            if note_text and len(note_text) > 5:
                content_html_parts.append(f"<p><strong>Lời tác giả:</strong> {note_text}</p>")

        panel_count = 0
        for img in img_elements:
            src = (
                img.get("data-url")
                or img.get("data-src")
                or img.get("src")
                or img.get("data-original")
                or ""
            )
            if not src:
                continue

            # Skip tiny icons or ad pixels
            if "icon" in src.lower() or "banner" in src.lower() or "logo" in src.lower() or "bg_" in src.lower():
                continue

            panel_count += 1
            content_html_parts.append(f'<p><img src="{src}" alt="Panel {panel_count}" /></p>')

        if panel_count == 0:
            raise RuntimeError(
                f"Không thể cào hình ảnh từ Webtoons ({url}). Vui lòng kiểm tra lại đường dẫn chương truyện hoặc website nguồn."
            )

        raw_html = f'<div class="webtoon-panels">{"".join(content_html_parts)}</div>'

        return ChapterContentResult(
            title=title,
            raw_html=raw_html,
        )

