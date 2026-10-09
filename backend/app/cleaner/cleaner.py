import html
import re
import unicodedata
import hashlib
from typing import List, Tuple
from urllib.parse import urlparse
from bs4 import BeautifulSoup


# Common promotional and piracy disclaimer patterns to filter out
PROMO_PATTERNS = [
    re.compile(r"read\s+latest\s+chapters?\s+at\s+.*", re.IGNORECASE),
    re.compile(r"please\s+visit\s+.*?\s+to\s+read\s+.*", re.IGNORECASE),
    re.compile(r"visit\s+.*?\s+for\s+(?:more|the\s+best)\s+novels?", re.IGNORECASE),
    re.compile(r"this\s+chapter\s+is\s+updated\s+by\s+.*", re.IGNORECASE),
    re.compile(r"source\s*:\s*https?://\S+", re.IGNORECASE),
    re.compile(r"translated\s+by\s+.*", re.IGNORECASE),
    re.compile(r"edited\s+by\s+.*", re.IGNORECASE),
    re.compile(r"support\s+the\s+translator\s+on\s+.*", re.IGNORECASE),
    re.compile(r"novel\s+update\s+coming\s+soon.*", re.IGNORECASE),
    re.compile(r"join\s+our\s+discord.*", re.IGNORECASE),
    re.compile(r"support\s+me\s+on\s+patreon.*", re.IGNORECASE),
    re.compile(r"report\s+broken\s+chapters?.*", re.IGNORECASE),
    # Webtoons & Manga viewer UI boilerplate
    re.compile(r"^up\s*every\s+[a-z]+.*", re.IGNORECASE),
    re.compile(r"^share\s+this\s+series.*", re.IGNORECASE),
    re.compile(r"^and\s+show\s+support\s+for\s+the\s+creator.*", re.IGNORECASE),
    re.compile(r"^like$", re.IGNORECASE),
    re.compile(r"^(?:un)?subscribed\s+(?:to|for)\s+your\s+list.*", re.IGNORECASE),
    re.compile(r"^you\s+can\s+subscribe\s+up\s+to\s+.*", re.IGNORECASE),
    re.compile(r"^(facebook|twitter|reddit|tumblr|x)$", re.IGNORECASE),
    re.compile(r"^the\s+url\s+has\s+been\s+copied.*", re.IGNORECASE),
    re.compile(r"^paste\(ctrl\+v\)\s+it\s+in\s+the\s+desired\s+location.*", re.IGNORECASE),
]


class ContentCleaner:
    """Clean raw novel chapter HTML and produce normalized, reader-ready paragraphs and image blocks."""

    @staticmethod
    def clean(raw_html_or_text: str, chapter_title: str = "") -> Tuple[str, int, str]:
        """
        Cleans content, returns (cleaned_text, paragraph_count, sha256_hash).
        Paragraphs and images are delimited by double newline '\\n\\n'.
        Images are formatted as '[IMG:image_url]'.
        """
        if not raw_html_or_text:
            return "", 0, hashlib.sha256(b"").hexdigest()

        # 1. Parse HTML
        soup = BeautifulSoup(raw_html_or_text, "html.parser")

        # 2. Decompose unwanted tags
        unwanted_tags = [
            "script", "style", "noscript", "iframe", "svg", "canvas",
            "form", "button", "nav", "header", "footer", "aside",
            "object", "embed", "input", "select", "option", "textarea"
        ]
        for tag in soup.find_all(unwanted_tags):
            tag.decompose()

        # 3. Decompose ad, navigation, share, and comment containers
        bad_selectors = [
            "[class*='advert']", "[id*='advert']", "[class*='ad-']", "[class*='-ad']",
            "[class*='ads']", "[id*='ads']", "[class*='banner']", "[class*='share']",
            "[class*='social']", "[class*='comment']", "[class*='disqus']",
            "[class*='rating']", "[class*='sidebar']", "[class*='watermark']",
            "[class*='prev-next']", "[class*='navigation']", "[class*='chapter-nav']",
            "[class*='btn']", "[class*='report']", "[class*='sns']", ".like_area",
            ".share_area", ".post_social", ".manage_sub"
        ]
        for sel in bad_selectors:
            for elem in soup.select(sel):
                elem.decompose()

        # 4. Convert <img> tags to [IMG:src] tokens to preserve comic panels & novel illustrations
        for img in soup.find_all("img"):
            src = (
                img.get("data-url")
                or img.get("data-src")
                or img.get("src")
                or img.get("data-original")
                or ""
            )
            if src:
                src = src.strip()
                if src.startswith("//"):
                    src = f"https:{src}"
                if not ContentCleaner._is_unwanted_icon(src, img) and (src.startswith("http") or src.startswith("/")):
                    if img.parent and img.parent.name == "p" and len(img.parent.find_all()) == 1:
                        img.parent.string = f"[IMG:{src}]"
                    else:
                        p_elem = soup.new_tag("p")
                        p_elem.string = f"[IMG:{src}]"
                        img.replace_with(p_elem)
                else:
                    img.decompose()
            else:
                img.decompose()

        # 5. Convert <br> tags to standard newlines
        for br in soup.find_all("br"):
            br.replace_with("\n")

        # 6. Extract text and image blocks
        paragraphs: List[str] = []

        # Find block elements
        blocks = soup.find_all(["p", "div", "blockquote", "li", "h1", "h2", "h3", "h4"])
        if blocks:
            for b in blocks:
                # Avoid inner paragraphs being duplicated if parent div was already processed
                if b.find_all(["p", "div"]) and b.name != "p":
                    continue
                text = b.get_text()
                for line in text.splitlines():
                    cleaned_line = ContentCleaner._normalize_line(line)
                    if ContentCleaner._is_valid_paragraph(cleaned_line):
                        paragraphs.append(cleaned_line)
        else:
            # Fallback for plain text or minimal HTML
            raw_text = soup.get_text()
            for line in raw_text.splitlines():
                cleaned_line = ContentCleaner._normalize_line(line)
                if ContentCleaner._is_valid_paragraph(cleaned_line):
                    paragraphs.append(cleaned_line)

        # 7. Deduplicate repeated consecutive promotional lines
        filtered_paras: List[str] = []
        last_p = ""
        for p in paragraphs:
            # Skip if identical to previous (including duplicate consecutive panels from DOM lazy-loading)
            if p == last_p:
                continue

            # Preserve all images
            if p.startswith("[IMG:"):
                filtered_paras.append(p)
                last_p = p
                continue

            # Skip promo patterns
            if any(pat.fullmatch(p) or pat.search(p) for pat in PROMO_PATTERNS if len(p) < 120):
                continue

            filtered_paras.append(p)
            last_p = p

        # 8. Merge paragraphs with double newline
        cleaned_text = "\n\n".join(filtered_paras)
        para_count = len(filtered_paras)
        sha256_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()

        return cleaned_text, para_count, sha256_hash

    @staticmethod
    def _normalize_line(line: str) -> str:
        if not line:
            return ""

        # If it's an image token, preserve exact URL
        if line.startswith("[IMG:") and line.endswith("]"):
            return line.strip()

        # Decode HTML entities
        text = html.unescape(line)

        # Normalize Unicode NFKC
        text = unicodedata.normalize("NFKC", text)

        # Replace non-breaking and zero-width spaces
        text = text.replace("\u00a0", " ")
        text = text.replace("\u200b", "")
        text = text.replace("\ufeff", "")
        text = text.replace("\u3000", " ")

        # Collapse multiple spaces inside the line
        text = re.sub(r"[ \t]+", " ", text).strip()

        return text

    @staticmethod
    def _is_valid_paragraph(p: str) -> bool:
        if not p:
            return False
        if p.startswith("[IMG:") and p.endswith("]"):
            return True
        # Skip pure symbols, separators like "---", "***", "====="
        if re.fullmatch(r"[-*=_~·#^`]{2,}", p):
            return False
        return len(p.strip()) > 0

    @staticmethod
    def _is_unwanted_icon(src: str, img_tag=None) -> bool:
        """Determines if an image is a UI icon/avatar/spacer rather than a comic panel or novel illustration."""
        if not src:
            return True
        src_lower = src.lower()

        # 1. Comic panels and webtoon CDNs are always preserved, never treated as icons
        if any(k in src_lower for k in [
            "webtoon", "pstatic.net", "episode", "chapter", "viewer", "panel", "page",
            "manga", "manhwa", "comic"
        ]):
            return False

        # 2. Check explicit dimensions or CSS classes on img tag if present
        if img_tag:
            w = img_tag.get("width")
            h = img_tag.get("height")
            try:
                if w and h and int(w) <= 48 and int(h) <= 48:
                    return True
            except (ValueError, TypeError):
                pass
            classes = " ".join(img_tag.get("class", [])).lower()
            if any(c in classes for c in ["avatar", "user-icon", "author-thumb", "profile", "emoji"]):
                return True

        # 3. Check path and filename structure
        parsed = urlparse(src_lower)
        path = parsed.path
        filename = path.split("/")[-1]

        # Dummy / spacer / favicon files
        if any(filename.endswith(ext) for ext in [".ico", "blank.gif", "pixel.gif", "spacer.gif"]):
            return True

        # UI asset folders
        if any(f"/{folder}/" in path for folder in ["avatars", "emojis", "badges", "icons"]):
            return True

        # Explicit UI asset filename prefixes or exact asset names
        if any(filename.startswith(f"{prefix}_") or filename.startswith(f"{prefix}-") for prefix in ["icon", "avatar", "logo", "emoji", "badge"]):
            return True
        if filename in ["avatar.png", "avatar.jpg", "avatar.jpeg", "logo.png", "logo.svg", "icon.png", "icon.svg"]:
            return True

        return False
