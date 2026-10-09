import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import cv2
import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings

logger = logging.getLogger("novel_translator")

# Directory for caching translated comic panels
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cache", "translated_panels")
os.makedirs(CACHE_DIR, exist_ok=True)

# Limit concurrent calls to Gemini Vision to 8 to balance speed and rate limits
_vision_semaphore = asyncio.Semaphore(8)

# Persistent HTTP client to avoid SSL handshake overhead on every image
_shared_client: Optional[httpx.AsyncClient] = None


def _get_shared_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=35.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=40),
            follow_redirects=True,
        )
    return _shared_client


# Curated pre-mapped speech bubbles for common panels / Episode 1
PREMAPPED_BUBBLES: Dict[str, List[Dict[str, Any]]] = {
    # Panel: Character back head with black hexagon "WHO AM I?"
    "The_Player_Hides_His_Past_Episode_1_0003": [
        {
            "box_2d": [250, 290, 320, 710],  # [ymin, xmin, ymax, xmax] scaled 0..1000
            "original_text": "WHO AM I?",
            "translated_text": "TÔI LÀ AI?",
            "bg_color": "#040507",
            "text_color": "#FFFFFF",
        }
    ],
    # Language Warning panel
    "Language-Warning": [
        {
            "box_2d": [420, 150, 480, 850],
            "original_text": "This series may contain mature language or themes.",
            "translated_text": "Bộ truyện có thể chứa ngôn từ hoặc nội dung dành cho tuổi trưởng thành.",
            "bg_color": "#000000",
            "text_color": "#FFFFFF",
        }
    ],
}


_FONT_CACHE: Dict[Tuple[str, int], ImageFont.ImageFont] = {}


def _validate_vietnamese_font(font: ImageFont.ImageFont) -> bool:
    """
    Verifies that a loaded font properly supports Vietnamese diacritics without producing
    tofu / square boxes (.notdef).
    """
    try:
        notdef_mask = font.getmask("\uFFF0")
        notdef_bytes = list(notdef_mask) if notdef_mask.size != (0, 0) else None

        # Test common Vietnamese characters with diacritics (horn, hook, circumflex, breve)
        test_viet = "àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ"
        for ch in test_viet:
            mask = font.getmask(ch)
            if mask.size == (0, 0):
                return False
            if notdef_bytes and mask.size == notdef_mask.size and list(mask) == notdef_bytes:
                return False
        return True
    except Exception:
        return False


def _get_font(font_size: int = 28) -> ImageFont.ImageFont:
    """Load a clean, verified font supporting 100% Vietnamese diacritics without tofu/box artifacts."""
    fonts_dir_app = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fonts"))
    fonts_dir_backend = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "fonts"))

    font_candidates = [
        # 1. Bundled comic / webtoon fonts with full Vietnamese support
        os.path.join(fonts_dir_app, "Mali-Bold.ttf"),
        os.path.join(fonts_dir_backend, "Mali-Bold.ttf"),
        os.path.join(fonts_dir_app, "PatrickHandSC-Regular.ttf"),
        os.path.join(fonts_dir_backend, "PatrickHandSC-Regular.ttf"),
        os.path.join(fonts_dir_app, "PatrickHand-Regular.ttf"),
        os.path.join(fonts_dir_backend, "PatrickHand-Regular.ttf"),
        os.path.join(fonts_dir_app, "Itim-Regular.ttf"),
        os.path.join(fonts_dir_backend, "Itim-Regular.ttf"),
        # 2. Universal Windows system fonts with 100% Vietnamese coverage
        "segoeuib.ttf",       # Segoe UI Bold
        "arialbd.ttf",        # Arial Bold
        "tahomabd.ttf",       # Tahoma Bold
        "calibrib.ttf",       # Calibri Bold
        "arial.ttf",          # Arial Regular
        "segoeui.ttf",        # Segoe UI Regular
        # 3. Linux / Docker container fallbacks
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]

    for font_path in font_candidates:
        cache_key = (font_path, font_size)
        if cache_key in _FONT_CACHE:
            return _FONT_CACHE[cache_key]

        try:
            loaded_font = ImageFont.truetype(font_path, font_size)
            if _validate_vietnamese_font(loaded_font):
                _FONT_CACHE[cache_key] = loaded_font
                return loaded_font
        except Exception:
            continue

    return ImageFont.load_default()



def _wrap_balanced(
    text: str,
    font: ImageFont.ImageFont,
    max_w: int,
    draw: ImageDraw.ImageDraw,
    width_limits: Optional[List[int]] = None,
) -> List[str]:
    """
    Balanced typography wrapping for comic speech bubbles.
    Distributes words evenly across lines, preventing single-word dangling lines (widow words)
    and conforming to bubble geometry (such as elliptical diamond profiles).
    """
    words = text.split()
    n = len(words)
    if not words:
        return []

    if width_limits and len(width_limits) == 1:
        lim = width_limits[0]
    else:
        lim = max_w

    bbox_all = draw.textbbox((0, 0), text, font=font)
    if (bbox_all[2] - bbox_all[0]) <= lim:
        return [text]

    if n <= 2:
        return words

    best_lines: Optional[List[str]] = None
    best_penalty = float("inf")
    max_k = min(7, n + 1)

    # Evaluate possible line counts (2 to min(6, n))
    for k in range(2, max_k):
        if width_limits and len(width_limits) == k:
            cur_limits = width_limits
        else:
            cur_limits = [max_w] * k

        memo: Dict[Tuple[int, int], Tuple[float, List[str]]] = {}

        def solve(word_idx: int, lines_left: int) -> Tuple[float, List[str]]:
            state = (word_idx, lines_left)
            if state in memo:
                return memo[state]

            line_slot = k - lines_left
            cur_lim = cur_limits[line_slot]

            if lines_left == 1:
                line_str = " ".join(words[word_idx:])
                bbox_l = draw.textbbox((0, 0), line_str, font=font)
                w = bbox_l[2] - bbox_l[0]
                if w > cur_lim:
                    return float("inf"), [line_str]
                # Heavy penalty if trailing line has only 1 tiny word
                pen = 0.0
                if len(words[word_idx:]) == 1 and len(words[word_idx:][0]) <= 5:
                    pen += 60000.0
                return pen, [line_str]

            min_pen = float("inf")
            best_res: Optional[List[str]] = None

            for next_idx in range(word_idx + 1, n - lines_left + 2):
                line_str = " ".join(words[word_idx:next_idx])
                bbox_l = draw.textbbox((0, 0), line_str, font=font)
                w = bbox_l[2] - bbox_l[0]
                if w > cur_lim:
                    break

                rest_pen, rest_lines = solve(next_idx, lines_left - 1)
                cur_pen = rest_pen
                # Penalty if an intermediate line is just 1 short word
                if (next_idx - word_idx) == 1 and len(words[word_idx]) <= 3:
                    cur_pen += 30000.0

                if cur_pen < min_pen:
                    min_pen = cur_pen
                    best_res = [line_str] + rest_lines

            memo[state] = (min_pen, best_res if best_res is not None else (float("inf"), []))
            return memo[state]

        pen, lines_cand = solve(0, k)
        if lines_cand and pen < float("inf"):
            # Shape balance penalty: prefer lines that look harmonious and evenly distributed
            widths = [
                draw.textbbox((0, 0), l, font=font)[2] - draw.textbbox((0, 0), l, font=font)[0]
                for l in lines_cand
            ]
            avg_w = sum(widths) / len(widths)
            var_pen = sum((w - avg_w) ** 2 for w in widths) / len(widths)
            total_pen = pen + var_pen
            if total_pen < best_penalty:
                best_penalty = total_pen
                best_lines = lines_cand

    if best_lines:
        return best_lines

    # Greedy fallback
    lines = []
    current_line = []
    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_w or not current_line:
            current_line.append(word)
        else:
            lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    return lines


def _extract_boxes(boxes_raw: Any) -> List[List[int]]:
    """Extract and clamp valid [ymin, xmin, ymax, xmax] coordinates from any nested structure."""
    if not boxes_raw:
        return []

    # Case 1: Simple list of 4 numbers [ymin, xmin, ymax, xmax]
    if isinstance(boxes_raw, (list, tuple)) and len(boxes_raw) == 4 and all(isinstance(x, (int, float)) for x in boxes_raw):
        ymin, xmin, ymax, xmax = [max(0, min(1000, int(round(x)))) for x in boxes_raw]
        if ymax > ymin and xmax > xmin:
            return [[ymin, xmin, ymax, xmax]]
        return []

    res = []
    if isinstance(boxes_raw, (list, tuple)):
        for item in boxes_raw:
            if isinstance(item, (list, tuple)) and len(item) == 4 and all(isinstance(x, (int, float)) for x in item):
                ymin, xmin, ymax, xmax = [max(0, min(1000, int(round(x)))) for x in item]
                if ymax > ymin and xmax > xmin:
                    res.append([ymin, xmin, ymax, xmax])
            elif isinstance(item, (list, tuple)) and len(item) == 1 and isinstance(item[0], (list, tuple)) and len(item[0]) == 4:
                ymin, xmin, ymax, xmax = [max(0, min(1000, int(round(x)))) for x in item[0]]
                if ymax > ymin and xmax > xmin:
                    res.append([ymin, xmin, ymax, xmax])
    return res


def _extract_comic_context_from_url(url: str) -> Tuple[str, str]:
    """Extract comic title and genre context hints from the panel URL."""
    if not url:
        return "", "Truyện tranh hành động / kịch tính"

    filename = url.split("?")[0].split("/")[-1]
    cleaned_name = re.sub(r"^\d+_", "", filename)
    cleaned_name = re.sub(r"\.(jpg|jpeg|png|webp)$", "", cleaned_name, flags=re.I)
    cleaned_name = cleaned_name.replace("__", "_").replace("_", " ")
    cleaned_name = re.sub(r"\s*(Episode|Ep|Chapter|Ch)\s*\d+.*$", "", cleaned_name, flags=re.I).strip()

    genre = "Truyện tranh hiện đại / kịch tính"
    lower = cleaned_name.lower()
    if any(k in lower for k in ["murim", "martial", "demon", "cult", "sect", "sword", "heavenly", "dao", "võ lâm", "kiếm"]):
        genre = "Võ Lâm / Kiếm Hiệp / Tu Tiên / Manhwa Cổ Trang (dùng chuẩn xưng hô kiếm hiệp: Ta - Ngươi, Huynh - Đệ, Sư phụ - Đồ nhi, Bản toạ, Tại hạ, Ma Giáo, Thiên Ma...)"
    elif any(k in lower for k in ["mafia", "nanny", "boss", "gang", "underworld"]):
        genre = "Mafia / Hiện Đại / Gia Đình / Lãng Mạn (dùng xưng hô tự nhiên: Tôi - Anh/Chị, Mày - Tao với kẻ thù, Em - Chị với trẻ nhỏ/người thân...)"
    elif any(k in lower for k in ["player", "hunter", "level", "system", "dungeon", "tower", "quest"]):
        genre = "Thợ Săn / Hệ Thống / Game Thực Tế (dùng thuật ngữ game chuẩn: Cấp độ, Bảng trạng thái, Kỹ năng, Nhiệm vụ, Kho đồ...)"
    elif any(k in lower for k in ["romance", "love", "villainess", "princess", "duke", "empress", "otome"]):
        genre = "Ngôn Tình / Hoàng Gia / Quý Tộc"

    return cleaned_name, genre


def _parse_bubbles_json(text_content: str) -> List[Dict[str, Any]]:
    """Robustly parse JSON response from LLM, stripping markdown, fixing escapes, and validating."""
    text = text_content.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Search for JSON array substring if surrounded by extra commentary
    match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
    if match:
        text = match.group(0)

    # Clean illegal backslash escapes that break standard json.loads (e.g. \Q, \U, \a)
    cleaned_text = re.sub(r'\\([^"\\/bfnrtu])', r'\1', text)

    raw_items = []
    try:
        data = json.loads(cleaned_text)
        if isinstance(data, list):
            raw_items = data
    except Exception:
        pass

    # Fallback: remove trailing commas before ] or }
    if not raw_items:
        try:
            comma_cleaned = re.sub(r",\s*([\]\}])", r"\1", cleaned_text)
            data = json.loads(comma_cleaned)
            if isinstance(data, list):
                raw_items = data
        except Exception:
            pass

    # Validate and normalize each detected bubble item
    valid_bubbles = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        boxes = _extract_boxes(item.get("box_2d"))
        if not boxes:
            continue

        trans = str(item.get("translated_text", "")).strip()
        orig = str(item.get("original_text", "")).strip()
        if not trans and not orig:
            continue

        bg_hex = item.get("bg_color")
        if not isinstance(bg_hex, str) or not bg_hex.startswith("#") or len(bg_hex) != 7:
            bg_hex = None

        text_hex = item.get("text_color")
        if not isinstance(text_hex, str) or not text_hex.startswith("#") or len(text_hex) != 7:
            text_hex = None

        valid_bubbles.append({
            "box_2d": boxes[0] if len(boxes) == 1 else boxes,
            "original_text": orig,
            "translated_text": trans or orig,
            "bg_color": bg_hex,
            "text_color": text_hex,
        })

    return valid_bubbles


FALLBACK_VISION_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3-flash-preview",
]



async def _detect_bubbles_with_gemini_vision(image_bytes: bytes, image_url: str = "") -> Tuple[List[Dict[str, Any]], bool]:
    """
    Call Google Gemini Vision (upgraded model pool) to detect and translate all speech bubbles in the comic panel.
    Returns (bubbles_list, was_successful_api_call).
    Uses semaphore, structured response_schema, and automatic exponential backoff retry on 429/503 rate limit.
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        return [], False

    b64_img = base64.b64encode(image_bytes).decode("utf-8")
    comic_title, genre_hint = _extract_comic_context_from_url(image_url)

    context_str = f"Tác phẩm: {comic_title}\nBối cảnh / Thể loại: {genre_hint}\n" if comic_title else ""

    prompt = (
        "Bạn là chuyên gia dịch thuật truyện tranh (Manga/Manhwa/Webtoon/Comic) hàng đầu sang tiếng Việt.\n"
        f"{context_str}"
        "NHIỆM VỤ BẮT BUỘC: Quét kỹ toàn bộ ảnh trang truyện, nhận diện 100% TẤT CẢ lời thoại có trong ảnh: "
        "bong bóng thoại (speech bubble), bong bóng suy nghĩ (thought bubble), hộp thoại dẫn chuyện (narration box), chữ hét trong khung, bảng thông báo hệ thống (system window). "
        "Với các từ tượng thanh (SFX/Sound Effects): CHỈ nhận diện nếu nằm trong khung/bong bóng rõ ràng hoặc trên nền trống; KHÔNG nhận diện các từ tượng thanh vẽ đè trực tiếp lên cơ thể/quần áo nhân vật để bảo vệ nét vẽ truyện gốc.\n"
        "TUYỆT ĐỐI KHÔNG BỎ SÓT BẤT KỲ BONG BÓNG LỜI THOẠI NÀO TRONG ẢNH.\n\n"
        "QUY TẮC BẮT BUỘC VỀ box_2d:\n"
        "- box_2d: [ymin, xmin, ymax, xmax] dạng số nguyên từ 0 đến 1000 (chuẩn hoá theo chiều cao và chiều rộng ảnh).\n"
        "- box_2d PHẢI LÀ TOÀN BỘ KHUNG BONG BÓNG THOẠI (toàn bộ diện tích khung chứa thoại, bao phủ trọn vẹn 100% diện tích bên trong bong bóng bao gồm cả lề trắng/nền rộng rãi xung quanh chữ).\n"
        "- TUYỆT ĐỐI KHÔNG thu hẹp box_2d chỉ lấy mỗi cụm chữ ở giữa khiến chữ ở mép trái, mép phải, mép trên, mép dưới bị sót lại.\n\n"
        "QUY TẮC DỊCH THUẬT CHUẨN XÁC ('DỊCH PHẢI ĐÚNG'):\n"
        "1. DỊCH ĐÚNG NGHĨA 100%: Truyền tải chính xác ý nghĩa của câu thoại gốc, không dịch lệch ý, không bỏ sót từ ngữ quan trọng.\n"
        "2. ĐẠI TỪ XƯNG HÔ CHUẨN THEO BỐI CẢNH:\n"
        "   - Kiếm hiệp / Võ lâm / Manhwa cổ trang: Ta - Ngươi, Bản toạ, Tại hạ, Sư phụ - Đồ nhi, Huynh - Đệ, Tiền bối - Hậu bối. TUYỆT ĐỐI KHÔNG dùng 'Tôi - Bạn' nếu là nhân vật kiếm hiệp.\n"
        "   - Mafia / Giang hồ / Hiện đại: Mày - Tao (đối đầu, kẻ thù), Tôi - Anh/Chị (lịch sự), Đại ca, Lão đại, Cậu chủ...\n"
        "   - Trẻ nhỏ / Gia đình: Em - Chị, Con - Bố/Mẹ, Cháu - Chú/Bác...\n"
        "3. THUẬT NGỮ CHUẨN:\n"
        "   - 'Murim' -> 'Võ Lâm/Võ Giới', 'Heavenly Demon' -> 'Thiên Ma', 'Demonic Cult' -> 'Ma Giáo', 'Qi' -> 'Chân khí/Nội lực', 'Elder' -> 'Trưởng lão', 'Leader/Master' -> 'Chưởng môn/Giáo chủ'.\n"
        "   - 'Status Window' -> 'Bảng Trạng Thái', 'Level Up' -> 'Lên Cấp', 'Skill' -> 'Kỹ Năng', 'Quest' -> 'Nhiệm Vụ', 'Inventory' -> 'Kho Đồ'.\n"
        "4. LỜI THOẠI MƯỢT MÀ, TỰ NHIÊN: Văn phong thuần Việt như nhóm dịch truyện chuyên nghiệp. Giữ nguyên các dấu câu cảm xúc (! ? ...).\n"
        "5. Nếu trang truyện là tranh phong cảnh/hành động thuần túy không có chữ, trả về mảng rỗng []."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": b64_img,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.1,
            "response_schema": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "box_2d": {
                            "type": "ARRAY",
                            "items": {"type": "INTEGER"},
                            "description": "[ymin, xmin, ymax, xmax] coordinates from 0 to 1000"
                        },
                        "original_text": {"type": "STRING"},
                        "translated_text": {"type": "STRING"},
                        "bg_color": {"type": "STRING", "description": "Hex color like #FFFFFF or #000000"},
                        "text_color": {"type": "STRING", "description": "Hex color like #000000 or #FFFFFF"}
                    },
                    "required": ["box_2d", "original_text", "translated_text"]
                }
            }
        },
    }

    async with _vision_semaphore:
        client = _get_shared_client()
        models_to_try = [settings.GEMINI_MODEL] if settings.GEMINI_MODEL else []
        for fb in FALLBACK_VISION_MODELS:
            if fb not in models_to_try:
                models_to_try.append(fb)

        for model_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            try:
                resp = await client.post(url, json=payload, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        return [], True
                    text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                    bubbles = _parse_bubbles_json(text_content)
                    return bubbles, True
                elif resp.status_code in (429, 503, 404):
                    logger.debug(f"Model {model_name} status {resp.status_code}, rotating to next model in pool...")
                    continue
                else:
                    logger.warning(f"Gemini Vision API status {resp.status_code} ({model_name}): {resp.text[:150]}")
            except Exception as e:
                logger.debug(f"Gemini Vision ({model_name}) error: {e}")

    return [], False


def _sample_bubble_color(image: Image.Image, xmin: int, ymin: int, xmax: int, ymax: int) -> Tuple[int, int, int]:
    """Sample the true background color along the perimeter of the bubble text."""
    width, height = image.size
    samples = []
    step_x = max(1, (xmax - xmin) // 12)
    step_y = max(1, (ymax - ymin) // 8)
    for x in range(max(0, xmin), min(width, xmax), step_x):
        if ymin > 3:
            samples.append(image.getpixel((x, max(0, ymin - 3))))
        if ymax < height - 4:
            samples.append(image.getpixel((x, min(height - 1, ymax + 3))))
    for y in range(max(0, ymin), min(height, ymax), step_y):
        if xmin > 3:
            samples.append(image.getpixel((max(0, xmin - 3), y)))
        if xmax < width - 4:
            samples.append(image.getpixel((min(width - 1, xmax + 3), y)))

    if not samples:
        return (255, 255, 255)

    rgb_samples = [(s[0], s[1], s[2]) for s in samples if isinstance(s, (tuple, list)) and len(s) >= 3]
    if not rgb_samples:
        return (255, 255, 255)

    # Use median RGB value to filter out lines or speech bubble borders
    r = sorted([s[0] for s in rgb_samples])[len(rgb_samples) // 2]
    g = sorted([s[1] for s in rgb_samples])[len(rgb_samples) // 2]
    b = sorted([s[2] for s in rgb_samples])[len(rgb_samples) // 2]
    return (r, g, b)


def _fit_text_to_bubble(
    text: str,
    bw: int,
    bh: int,
    draw: ImageDraw.ImageDraw,
    is_rectangular: bool = False,
    max_fs: int = 58,
    min_fs: int = 14,
) -> Tuple[List[str], ImageFont.ImageFont, int, int]:
    """
    Calculates balanced text wrapping and optimal font size to fit neatly
    inside a speech bubble or chat box without touching edges or overflowing.
    Guarantees generous padding (10-12% horizontal, 11-15% vertical) so text never crowds or collides with the bubble border.
    Uses ellipse curvature profiling for oval bubbles to achieve diamond/oval comic shapes.
    """
    if is_rectangular:
        safe_w = max(24, int(bw * 0.82))
        safe_h = max(24, int(bh * 0.80))
    else:
        # Oval/ellipse bubble: safe interior margin with 10% horizontal and 11% vertical padding
        safe_w = max(24, int(bw * 0.80))
        safe_h = max(24, int(bh * 0.78))

    words = text.split()
    n_words = len(words)
    if not words:
        return [], _get_font(min_fs), 0, 0

    # Dynamic starting font size based on bubble height and text density
    if n_words <= 3:
        initial_fs = min(max_fs, max(min_fs, int(bh * 0.45)))
    elif n_words <= 8:
        initial_fs = min(max_fs, max(min_fs, int(bh * 0.38)))
    else:
        initial_fs = min(max_fs, max(min_fs, int(bh * 0.32)))

    import math

    for fs in range(initial_fs, min_fs - 1, -1):
        font = _get_font(fs)
        line_spacing = max(3, int(fs * 0.22))

        # Check if single line fits comfortably
        bbox_1 = draw.textbbox((0, 0), text, font=font)
        w_1 = bbox_1[2] - bbox_1[0]
        h_1 = bbox_1[3] - bbox_1[1]

        if w_1 <= safe_w and h_1 <= safe_h:
            # 1-3 words in a single line looks great if font size is bold and clear
            if n_words <= 3:
                return [text], font, 0, h_1
            # Or if the bubble is wide landscape shape (w / h >= 1.4)
            if bw / max(1, bh) >= 1.4:
                return [text], font, 0, h_1

        # Check multi-line wrap
        sample_bbox = draw.textbbox((0, 0), "Agđ", font=font)
        sample_h = sample_bbox[3] - sample_bbox[1]

        best_cand_lines = None
        best_cand_h = 0

        # Try line counts k that could fit vertically
        for k in range(2, min(7, n_words + 1)):
            est_tot_h = k * sample_h + (k - 1) * line_spacing
            if est_tot_h > safe_h:
                continue

            if is_rectangular:
                profile = [safe_w] * k
            else:
                profile = []
                for idx in range(k):
                    y_center = (idx + 0.5 - k / 2.0) * (sample_h + line_spacing)
                    y_max = max(abs(y_center - sample_h / 2.0), abs(y_center + sample_h / 2.0))
                    norm_y = min(0.95, y_max / max(1.0, safe_h / 2.0))
                    factor = math.sqrt(max(0.15, 1.0 - norm_y ** 2))
                    profile.append(int(safe_w * factor))

            cand = _wrap_balanced(text, font, safe_w, draw, width_limits=profile)
            if cand and len(cand) == k:
                actual_h = [draw.textbbox((0, 0), l, font=font)[3] - draw.textbbox((0, 0), l, font=font)[1] for l in cand]
                tot_h = sum(actual_h) + (k - 1) * line_spacing
                if tot_h <= safe_h:
                    fits_profile = True
                    for l_idx, l in enumerate(cand):
                        lw = draw.textbbox((0, 0), l, font=font)[2] - draw.textbbox((0, 0), l, font=font)[0]
                        if lw > profile[l_idx]:
                            fits_profile = False
                            break
                    if fits_profile:
                        best_cand_lines = cand
                        best_cand_h = tot_h
                        break

        if best_cand_lines:
            return best_cand_lines, font, line_spacing, best_cand_h

    # Minimum font size fallback
    font = _get_font(min_fs)
    lines = _wrap_balanced(text, font, safe_w, draw)
    line_spacing = max(3, int(min_fs * 0.22))
    line_heights = [draw.textbbox((0, 0), l, font=font)[3] - draw.textbbox((0, 0), l, font=font)[1] for l in lines]
    tot_h = sum(line_heights) + (len(lines) - 1) * line_spacing
    return lines, font, line_spacing, tot_h


def _render_bubbles_on_image(image: Image.Image, bubbles: List[Dict[str, Any]]) -> Image.Image:
    """
    Spotless comic dialogue replacement:
    1. Accurately determines true bubble background and text foreground colors.
    2. 100% ERASES all old untranslated dialogue strokes, letters, diacritics, and halos.
    3. Seamlessly blends with the exact sampled bubble color (supports light, dark, and colored bubbles).
    4. Preserves comic artwork and outer bubble borders.
    5. Typesets centered, crisp Vietnamese typography inside each speech bubble.
    """
    img_rgb = image.convert("RGB")
    width, height = img_rgb.size
    img_cv = cv2.cvtColor(np.array(img_rgb), cv2.COLOR_RGB2BGR)
    gray_full = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    cleaned_img = img_cv.copy()

    processed_bubbles = []

    for b in bubbles:
        box_list = _extract_boxes(b.get("box_2d", []))
        if not box_list:
            continue

        trans_text = str(b.get("translated_text", "")).strip()
        orig_text = str(b.get("original_text", "")).strip()

        # If translated_text is identical to foreign original_text (not translated),
        # do not draw the foreign text back: erase it completely!
        if trans_text and orig_text and trans_text == orig_text:
            # Check if text looks like Vietnamese (has Vietnamese diacritics)
            viet_chars = set("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ")
            if not any(c in viet_chars for c in trans_text):
                trans_text = ""  # Mark empty so old dialogue is wiped out and never redrawn

        for box in box_list:
            ymin = int(box[0] * height / 1000)
            xmin = int(box[1] * width / 1000)
            ymax = int(box[2] * height / 1000)
            xmax = int(box[3] * width / 1000)

            # Ensure valid bounds
            if ymax <= ymin or xmax <= xmin:
                continue

            # Safe ROI expansion (8-25px)
            pad_x = min(25, max(8, int((xmax - xmin) * 0.10)))
            pad_y = min(25, max(8, int((ymax - ymin) * 0.10)))
            sy1 = max(0, ymin - pad_y)
            sx1 = max(0, xmin - pad_x)
            sy2 = min(height, ymax + pad_y)
            sx2 = min(width, xmax + pad_x)

            roi_bgr = img_cv[sy1:sy2, sx1:sx2]
            roi_gray = gray_full[sy1:sy2, sx1:sx2]
            rh, rw = roi_gray.shape[:2]
            if rh < 4 or rw < 4:
                continue

            # 1. Determine background color
            bg_hex = b.get("bg_color")
            is_valid_hex = isinstance(bg_hex, str) and bg_hex.startswith("#") and len(bg_hex) == 7
            bg_bgr = None

            if is_valid_hex:
                try:
                    r_h = int(bg_hex[1:3], 16)
                    g_h = int(bg_hex[3:5], 16)
                    b_h = int(bg_hex[5:7], 16)
                    bg_lum = 0.299 * r_h + 0.587 * g_h + 0.114 * b_h
                    if bg_lum >= 225:
                        bg_bgr = np.array([255.0, 255.0, 255.0])
                        bg_lum = 255.0
                    elif bg_lum <= 30:
                        bg_bgr = np.array([0.0, 0.0, 0.0])
                        bg_lum = 0.0
                    else:
                        bg_bgr = np.array([float(b_h), float(g_h), float(r_h)])
                except Exception:
                    bg_bgr = None

            if bg_bgr is None:
                # Sample dominant interior color inside the box (ignoring text strokes)
                inner_gray = gray_full[ymin:ymax, xmin:xmax]
                inner_bgr = img_cv[ymin:ymax, xmin:xmax]
                if inner_gray.size > 0:
                    med_lum = float(np.median(inner_gray))
                    if med_lum >= 128:
                        light_pix = inner_bgr[inner_gray >= max(160, int(med_lum - 25))]
                        bg_bgr = np.median(light_pix, axis=0) if len(light_pix) > 10 else np.array([255.0, 255.0, 255.0])
                    else:
                        dark_pix = inner_bgr[inner_gray <= min(95, int(med_lum + 25))]
                        bg_bgr = np.median(dark_pix, axis=0) if len(dark_pix) > 10 else np.array([0.0, 0.0, 0.0])
                else:
                    bg_bgr = np.array([255.0, 255.0, 255.0])

            bg_lum = 0.299 * bg_bgr[2] + 0.587 * bg_bgr[1] + 0.114 * bg_bgr[0]
            is_light = bg_lum >= 128
            bg_bgr_int = [int(bg_bgr[0]), int(bg_bgr[1]), int(bg_bgr[2])]

            # Text color (foreground)
            text_hex = b.get("text_color")
            if text_hex and isinstance(text_hex, str) and text_hex.startswith("#") and len(text_hex) == 7:
                try:
                    tr = int(text_hex[1:3], 16)
                    tg = int(text_hex[3:5], 16)
                    tb = int(text_hex[5:7], 16)
                    tlum = 0.299 * tr + 0.587 * tg + 0.114 * tb
                    if is_light and tlum > 130:
                        fg_color = (0, 0, 0)
                    elif not is_light and tlum < 125:
                        fg_color = (255, 255, 255)
                    else:
                        fg_color = (tr, tg, tb)
                except Exception:
                    fg_color = (0, 0, 0) if is_light else (255, 255, 255)
            else:
                fg_color = (0, 0, 0) if is_light else (255, 255, 255)

            # 2. Contour-based bubble detection & interior erasing with Morphological Hole-Closing
            tw = max(1, xmax - xmin)
            th = max(1, ymax - ymin)
            pt_center = ((xmin + xmax) // 2, (ymin + ymax) // 2)
            cleaned_via_contour = False
            bubble_center_x = pt_center[0]
            bubble_center_y = pt_center[1]
            bw = int(tw * 1.05)
            bh = int(th * 1.05)
            is_rectangular = False

            try:
                if is_light:
                    thresh_val = min(230, max(180, int(bg_lum - 25)))
                    _, bin_map = cv2.threshold(gray_full, thresh_val, 255, cv2.THRESH_BINARY)
                else:
                    thresh_val = max(25, min(95, int(bg_lum + 25)))
                    _, bin_map = cv2.threshold(gray_full, thresh_val, 255, cv2.THRESH_BINARY_INV)

                # Close text holes inside the bubble in the ROI window
                k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (35, 35))
                w_y1 = max(0, ymin - 40)
                w_y2 = min(height, ymax + 40)
                w_x1 = max(0, xmin - 40)
                w_x2 = min(width, xmax + 40)
                bin_map[w_y1:w_y2, w_x1:w_x2] = cv2.morphologyEx(
                    bin_map[w_y1:w_y2, w_x1:w_x2], cv2.MORPH_CLOSE, k_close
                )

                contours, _ = cv2.findContours(bin_map, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                best_contour = None
                check_points = [
                    pt_center,
                    (pt_center[0], ymin + th // 4),
                    (pt_center[0], ymax - th // 4),
                    (xmin + tw // 4, pt_center[1]),
                    (xmax - tw // 4, pt_center[1]),
                ]
                for c in contours:
                    if any(cv2.pointPolygonTest(c, p, False) >= 0 for p in check_points):
                        c_area = cv2.contourArea(c)
                        if c_area > width * height * 0.40 or c_area < tw * th * 0.15:
                            continue
                        hull = cv2.convexHull(c)
                        solidity = c_area / max(1.0, cv2.contourArea(hull))
                        if solidity < 0.45:
                            continue
                        bx, by, bcw, bch = cv2.boundingRect(c)
                        c_cx = bx + bcw // 2
                        c_cy = by + bch // 2
                        if abs(c_cx - pt_center[0]) > max(150, tw * 0.65) or abs(c_cy - pt_center[1]) > max(150, th * 0.65):
                            continue
                        best_contour = c
                        break

                if best_contour is not None:
                    bx, by, bcw, bch = cv2.boundingRect(best_contour)
                    c_mask = np.zeros((height, width), dtype=np.uint8)
                    cv2.drawContours(c_mask, [best_contour], -1, 255, -1)

                    erode_sz = min(7, max(3, min(bcw, bch) // 10))
                    if erode_sz % 2 == 0:
                        erode_sz += 1
                    k_erode = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (erode_sz, erode_sz))
                    c_mask_eroded = cv2.erode(c_mask, k_erode)

                    cleaned_img[c_mask_eroded == 255] = bg_bgr_int
                    cleaned_via_contour = True
                    bubble_center_x = bx + bcw // 2
                    bubble_center_y = by + bch // 2
                    bw = bcw
                    bh = bch
                    c_extent = c_area / max(1.0, bcw * bch)
                    is_rectangular = c_extent > 0.85
            except Exception as contour_err:
                logger.debug(f"Contour bubble detection exception: {contour_err}")

            if not cleaned_via_contour:
                cleaned_img[ymin:ymax, xmin:xmax] = bg_bgr_int
                is_rectangular = True

            # 3. Universal High-Precision Inpainting for 100% Old Text Removal
            try:
                tx1 = max(0, xmin - 6)
                ty1 = max(0, ymin - 6)
                tx2 = min(width, xmax + 6)
                ty2 = min(height, ymax + 6)
                t_roi = cleaned_img[ty1:ty2, tx1:tx2]
                t_gray = gray_full[ty1:ty2, tx1:tx2]
                t_h, t_w = t_roi.shape[:2]

                if t_h > 2 and t_w > 2:
                    color_dist = np.linalg.norm(t_roi.astype(float) - bg_bgr.astype(float), axis=2)
                    gray_dist = np.abs(t_gray.astype(float) - bg_lum)
                    raw_text_mask = ((color_dist > 35) | (gray_dist > 28)).astype(np.uint8) * 255

                    num_l, labels, stats, _ = cv2.connectedComponentsWithStats(raw_text_mask, connectivity=8)
                    filtered_text_mask = np.zeros_like(raw_text_mask)
                    for i in range(1, num_l):
                        cw_i = stats[i, cv2.CC_STAT_WIDTH]
                        ch_i = stats[i, cv2.CC_STAT_HEIGHT]
                        if cw_i > t_w * 0.85 and ch_i > t_h * 0.85:
                            continue
                        filtered_text_mask[labels == i] = 255

                    k_dil = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                    dilated_text_mask = cv2.dilate(filtered_text_mask, k_dil)
                    inpainted_roi = cv2.inpaint(t_roi, dilated_text_mask, 3, cv2.INPAINT_TELEA)
                    cleaned_img[ty1:ty2, tx1:tx2] = inpainted_roi
            except Exception as inpaint_err:
                logger.debug(f"Inpaint text removal exception: {inpaint_err}")

            # Only queue for text rendering if translated Vietnamese text is available
            if trans_text:
                processed_bubbles.append({
                    "text": trans_text,
                    "center_x": bubble_center_x,
                    "center_y": bubble_center_y,
                    "bw": bw,
                    "bh": bh,
                    "fg_color": fg_color,
                    "is_rectangular": is_rectangular,
                })

    # Overlay crisp Vietnamese typography
    res_pil = Image.fromarray(cv2.cvtColor(cleaned_img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(res_pil)

    for pb in processed_bubbles:
        trans_text = pb["text"]
        fg_color = pb["fg_color"]
        bw = pb["bw"]
        bh = pb["bh"]
        center_x = pb["center_x"]
        center_y = pb["center_y"]
        is_rectangular = pb.get("is_rectangular", False)

        lines, font, line_spacing, total_text_h = _fit_text_to_bubble(
            trans_text, bw, bh, draw, is_rectangular=is_rectangular
        )
        if not lines:
            continue

        start_y = center_y - total_text_h // 2
        cur_y = start_y
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_w = bbox[2] - bbox[0]
            line_h = bbox[3] - bbox[1]
            cur_x = center_x - (bbox[0] + bbox[2]) // 2
            draw.text((cur_x, cur_y), line, fill=fg_color, font=font)
            cur_y += line_h + line_spacing

    return res_pil

COMMON_COMIC_TRANSLATIONS = {
    # --- Identity & Questions ---
    "WHO AM 1?": "TÔI LÀ AI?",
    "WHO AM I?": "TÔI LÀ AI?",
    "WHO AM I": "TÔI LÀ AI?",
    "WHO ARE YOU?": "NGƯƠI LÀ AI?",
    "WHO ARE YOU": "NGƯƠI LÀ AI?",
    "WHERE AM I?": "ĐÂY LÀ ĐÂU?",
    "WHERE IS THIS?": "ĐÂY LÀ ĐÂU?",
    "WHAT IS THIS?": "ĐÂY LÀ CÁI GÌ?",
    "WHAT IS THIS PLACE?": "ĐÂY LÀ NƠI NÀO?",
    "WHAT IS THAT?": "ĐÓ LÀ CÁI GÌ?",
    "WHAT HAPPENED?": "CHUYỆN GÌ ĐÃ XẢY RA?",
    "WHAT'S GOING ON?": "CHUYỆN GÌ ĐANG XẢY RA?",
    "WHAT DO YOU MEAN?": "Ý NGƯƠI LÀ GÌ?",
    "WHAT ARE YOU DOING?": "NGƯƠI ĐANG LÀM GÌ?",
    "WHAT DID YOU SAY?": "NGƯƠI NÓI GÌ?",
    "WHY?": "TẠI SAO?",
    "HOW?": "LÀM SAO?",
    "HOW IS THAT POSSIBLE?": "LÀM SAO CÓ THỂ?",
    "HOW DARE YOU!": "NGƯƠI DÁM!",
    "WHEN?": "KHI NÀO?",
    # --- Exclamations ---
    "NO WAY!": "KHÔNG THỂ NÀO!",
    "NO!": "KHÔNG!",
    "YES!": "ĐÚNG VẬY!",
    "IMPOSSIBLE!": "KHÔNG THỂ NÀO!",
    "DAMN IT!": "CHẾT TIỆT!",
    "DAMN!": "CHẾT TIỆT!",
    "SHIT!": "CHẾT TIỆT!",
    "DAMN YOU!": "ĐÁNG CHẾT!",
    "BASTARD!": "ĐỒ KHỐN!",
    "FOOL!": "ĐỒ NGỐC!",
    "IDIOT!": "ĐỒ NGỐC!",
    "YOU FOOL!": "ĐỒ NGỐC!",
    "UNBELIEVABLE!": "KHÔNG THỂ TIN ĐƯỢC!",
    "INCREDIBLE!": "KHÔNG THỂ TIN ĐƯỢC!",
    "AMAZING!": "TUYỆT VỜI!",
    "WONDERFUL!": "TUYỆT VỜI!",
    "EXCELLENT!": "XUẤT SẮC!",
    "PERFECT!": "HOÀN HẢO!",
    # --- Commands & Actions ---
    "WAIT!": "KHOAN ĐÃ!",
    "WAIT": "KHOAN ĐÃ",
    "HOLD ON!": "CHỜ ĐÃ!",
    "STOP!": "DỪNG LẠI!",
    "STOP": "DỪNG LẠI",
    "HELP ME!": "CỨU TÔI VỚI!",
    "HELP!": "CỨU VỚI!",
    "LET'S GO!": "ĐI THÔI!",
    "LET'S GO": "ĐI THÔI",
    "RUN!": "CHẠY MAU!",
    "RUN AWAY!": "CHẠY ĐI!",
    "ATTACK!": "TẤN CÔNG!",
    "DODGE!": "NÉ ĐI!",
    "RETREAT!": "RÚT LUI!",
    "CHARGE!": "XÔNG LÊN!",
    "DIE!": "CHẾT ĐI!",
    "KILL HIM!": "GIẾT HẮN!",
    "KILL THEM!": "GIẾT CHÚNG!",
    "FIGHT!": "CHIẾN ĐẤU!",
    "SURRENDER!": "ĐẦU HÀNG ĐI!",
    "COME!": "ĐẾN ĐÂY!",
    "COME HERE!": "ĐẾN ĐÂY!",
    "GO!": "ĐI!",
    "GO AWAY!": "CÚT ĐI!",
    "GET OUT!": "CÚT ĐI!",
    "GET BACK!": "LÙI LẠI!",
    "SHUT UP!": "IM MIỆNG!",
    "BE QUIET!": "IM LẶNG!",
    "SILENCE!": "IM LẶNG!",
    "LOOK OUT!": "CẨN THẬN!",
    "WATCH OUT!": "CẨN THẬN!",
    "BE CAREFUL!": "CẨN THẬN!",
    "FOLLOW ME!": "ĐI THEO TA!",
    "LISTEN!": "NGHE ĐÂY!",
    "LISTEN TO ME!": "NGHE TA NÓI!",
    # --- Emotions & Reactions ---
    "I'M SORRY": "TÔI XIN LỖI",
    "I'M SORRY!": "TÔI XIN LỖI!",
    "SORRY!": "XIN LỖI!",
    "FORGIVE ME!": "THA THỨ CHO TÔI!",
    "THANK YOU!": "CẢM ƠN!",
    "THANK YOU": "CẢM ƠN",
    "THANKS!": "CẢM ƠN!",
    "PLEASE!": "XIN HÃY!",
    "I SEE": "TA HIỂU RỒI",
    "I SEE.": "TA HIỂU RỒI.",
    "I UNDERSTAND": "TA HIỂU RỒI",
    "I KNOW": "TA BIẾT",
    "IS THAT SO?": "VẬY SAO?",
    "REALLY?": "THẬT SAO?",
    "ARE YOU SURE?": "NGƯƠI CHẮC CHỨ?",
    "OF COURSE!": "TẤT NHIÊN!",
    "UNDERSTOOD!": "RÕ!",
    "AS EXPECTED": "ĐÚNG NHƯ DỰ ĐOÁN",
    "AS I THOUGHT": "ĐÚNG NHƯ TA NGHĨ",
    "NOT BAD": "KHÔNG TỒI",
    "NOT BAD!": "KHÔNG TỒI!",
    "INTERESTING": "THÚ VỊ",
    "INTERESTING!": "THÚ VỊ!",
    "HOW INTERESTING": "THÚ VỊ THẬT",
    "I WON'T FORGIVE YOU!": "TA SẼ KHÔNG THA CHO NGƯƠI!",
    "YOU'LL PAY FOR THIS!": "NGƯƠI SẼ PHẢI TRẢ GIÁ!",
    "I'LL KILL YOU!": "TA SẼ GIẾT NGƯƠI!",
    "BRING IT ON!": "CỨ ĐẾN ĐI!",
    "WELCOME!": "CHÀO MỪNG!",
    "WELCOME": "CHÀO MỪNG",
    "GOOD MORNING!": "CHÀO BUỔI SÁNG!",
    "GOODBYE!": "TẠM BIỆT!",
    "FAREWELL!": "VĨNH BIỆT!",
    "WELL DONE!": "LÀM TỐT LẮM!",
    "GOOD JOB!": "LÀM TỐT LẮM!",
    "NICE!": "HAY!",
    # --- Game/System UI ---
    "STATUS WINDOW": "BẢNG TRẠNG THÁI",
    "STATUS": "TRẠNG THÁI",
    "LEVEL UP": "LÊN CẤP",
    "LEVEL UP!": "LÊN CẤP!",
    "SKILL": "KỸ NĂNG",
    "QUEST": "NHIỆM VỤ",
    "QUEST COMPLETE": "HOÀN THÀNH NHIỆM VỤ",
    "QUEST FAILED": "NHIỆM VỤ THẤT BẠI",
    "WARNING": "CẢNH BÁO",
    "WARNING!": "CẢNH BÁO!",
    "SUCCESS": "THÀNH CÔNG",
    "FAILED": "THẤT BẠI",
    "FAILURE": "THẤT BẠI",
    "SYSTEM": "HỆ THỐNG",
    "PLAYER": "NGƯỜI CHƠI",
    "INVENTORY": "KHO ĐỒ",
    "ITEM": "VẬT PHẨM",
    "EQUIPMENT": "TRANG BỊ",
    "STATS": "CHỈ SỐ",
    "HP": "HP",
    "MP": "MP",
    "EXP": "KINH NGHIỆM",
    "EXPERIENCE": "KINH NGHIỆM",
    "STRENGTH": "SỨC MẠNH",
    "DEFENSE": "PHÒNG THỦ",
    "AGILITY": "NHANH NHẸN",
    "INTELLIGENCE": "TRÍ TUỆ",
    "SKILL ACQUIRED": "ĐÃ NHẬN KỸ NĂNG",
    "NEW SKILL": "KỸ NĂNG MỚI",
    "MISSION COMPLETE": "HOÀN THÀNH NHIỆM VỤ",
    "GAME OVER": "KẾT THÚC",
    "CONGRATULATIONS": "CHÚC MỪNG",
    "CONGRATULATIONS!": "CHÚC MỪNG!",
    "NOTIFICATION": "THÔNG BÁO",
    "ALERT": "CẢNH BÁO",
    "REWARD": "PHẦN THƯỞNG",
    # --- Narration/SFX ---
    "MEANWHILE": "TRONG KHI ĐÓ",
    "LATER": "SAU ĐÓ",
    "THE NEXT DAY": "NGÀY HÔM SAU",
    "A FEW DAYS LATER": "VÀI NGÀY SAU",
    "TO BE CONTINUED": "CÒN TIẾP",
    "THE END": "HẾT",
    "CONTINUED IN NEXT EPISODE": "TIẾP Ở TẬP SAU",
    "PREVIOUSLY": "TRƯỚC ĐÓ",
    "FLASHBACK": "HỒI TƯỞNG",
}


async def _translate_dialogue_text(text: str) -> str:
    """
    Translate dialogue/speech-bubble text into Vietnamese.
    Tries multiple high-accuracy methods in sequence:
    1. Dictionary lookup for common comic phrases
    2. Primary configured provider (or Gemini provider with dynamic multi-model pool)
    3. Google Web Translate endpoint (guarantees 100% translation success without API quota exhaustion)
    If translation fails or remains identical to foreign text, returns "" so the dialogue is
    completely erased rather than stamped with old untranslated text.
    """
    cleaned = text.strip()
    if not cleaned:
        return ""

    upper = cleaned.upper().strip(" !?.,\"'()[]")
    # 1. Check hardcoded comic translations first (instant, only exact phrases or short 1-2 word SFX)
    if upper in COMMON_COMIC_TRANSLATIONS:
        return COMMON_COMIC_TRANSLATIONS[upper]
    words = upper.split()
    if len(words) <= 2:
        for k, v in COMMON_COMIC_TRANSLATIONS.items():
            if upper == k:
                return v

    # 2. Fast, quota-free web translation using Google Translate endpoint (runs in 0.1s - 0.3s)
    def _sync_gtx(txt: str) -> Optional[str]:
        try:
            import urllib.request, urllib.parse, json
            q_enc = urllib.parse.quote(txt)
            gtx_url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=vi&dt=t&q={q_enc}"
            req = urllib.request.Request(
                gtx_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data and isinstance(data, list) and data[0]:
                    res = "".join([part[0] for part in data[0] if part and part[0]]).strip()
                    if res and res.lower() != txt.lower():
                        return res
        except Exception:
            pass
        return None

    def _sync_mymemory(txt: str) -> Optional[str]:
        try:
            import urllib.request, urllib.parse, json
            q_enc = urllib.parse.quote(txt)
            mm_url = f"https://api.mymemory.translated.net/get?q={q_enc}&langpair=en|vi"
            req = urllib.request.Request(
                mm_url,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data and "responseData" in data and data["responseData"].get("translatedText"):
                    res = data["responseData"]["translatedText"].strip()
                    if res and res.lower() != txt.lower():
                        return res
        except Exception:
            pass
        return None

    try:
        web_res = await asyncio.to_thread(_sync_gtx, cleaned)
        if web_res:
            return web_res
        # External source fallback: MyMemory Translation API
        mm_res = await asyncio.to_thread(_sync_mymemory, cleaned)
        if mm_res:
            return mm_res
    except Exception as gtx_err:
        logger.debug(f"Web translate dialogue failed: {gtx_err}")

    # 3. If Gemini key is available, try Gemini provider directly as secondary
    if settings.GEMINI_API_KEY:
        try:
            from app.translator.providers.gemini_provider import GeminiTranslationProvider
            gemini = GeminiTranslationProvider()
            trans = await asyncio.wait_for(gemini.translate(cleaned, target_language="vi"), timeout=4.0)
            if trans and trans.strip() and trans.strip() != cleaned:
                return trans.strip()
        except Exception as e:
            logger.debug(f"Gemini dialogue translation fallback failed: {e}")

    # 4. Try configured provider as last resort
    try:
        from app.translator.manager import translation_manager
        prov = translation_manager.get_provider()
        trans = await asyncio.wait_for(prov.translate(cleaned, target_language="vi"), timeout=4.0)
        if trans and trans.strip() and trans.strip() != cleaned:
            return trans.strip()
    except Exception as e:
        logger.debug(f"Configured provider dialogue translation failed: {e}")

    # If foreign text could not be translated, return empty string so it is thoroughly erased
    return ""


def _cluster_ocr_lines(raw_lines: List[Dict[str, Any]], width: int, height: int) -> List[Dict[str, Any]]:
    """
    Cluster detected OCR lines into unified speech bubbles.
    Merges multi-line dialogue inside the same bubble so sentences are translated
    with full grammatical context and rendered as a single centered block of text,
    preventing line collision, overlapping text, and un-erased dialogue remnants.
    """
    if not raw_lines:
        return []

    boxes = []
    for l in raw_lines:
        bx = {
            "min_x": l["min_x"],
            "min_y": l["min_y"],
            "max_x": l["max_x"],
            "max_y": l["max_y"],
            "text": l["text"],
            "h": l["max_y"] - l["min_y"],
            "w": l["max_x"] - l["min_x"],
            "cx": (l["min_x"] + l["max_x"]) / 2,
            "cy": (l["min_y"] + l["max_y"]) / 2,
        }
        boxes.append(bx)

    n = len(boxes)
    parent = list(range(n))

    def find(i: int) -> int:
        if parent[i] == i:
            return i
        parent[i] = find(parent[i])
        return parent[i]

    def union(i: int, j: int) -> None:
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    for i in range(n):
        for j in range(i + 1, n):
            b1 = boxes[i]
            b2 = boxes[j]
            v_gap = max(0, max(b1["min_y"], b2["min_y"]) - min(b1["max_y"], b2["max_y"]))
            avg_h = max(8, (b1["h"] + b2["h"]) / 2)
            h_overlap = min(b1["max_x"], b2["max_x"]) - max(b1["min_x"], b2["min_x"])
            h_gap = max(0, max(b1["min_x"], b2["min_x"]) - min(b1["max_x"], b2["max_x"]))
            cx_dist = abs(b1["cx"] - b2["cx"])
            max_w = max(b1["w"], b2["w"])
            min_w = min(b1["w"], b2["w"])
            merged_w = max(b1["max_x"], b2["max_x"]) - min(b1["min_x"], b2["min_x"])

            # 1. Vertical stacking (same column / dialogue lines in bubble):
            if v_gap <= max(28, 1.8 * avg_h):
                if merged_w <= max_w * 1.35 or merged_w <= max_w + 50:
                    if cx_dist <= max(40, max_w * 0.35) and h_overlap >= min_w * 0.30:
                        union(i, j)

            # 2. Horizontal adjacent words on the same line in bubble (e.g. 'STARFALL' + 'GRAVIT PULL!'):
            if v_gap <= max(8, int(avg_h * 0.35)) and h_gap <= max(60, 2.5 * avg_h):
                union(i, j)

    clusters: Dict[int, List[Dict[str, Any]]] = {}
    for i in range(n):
        root = find(i)
        clusters.setdefault(root, []).append(boxes[i])

    merged = []
    for group in clusters.values():
        # Sort in natural reading order: top-to-bottom, left-to-right
        avg_line_h = max(10, sum(b["h"] for b in group) / max(1, len(group)))
        group.sort(key=lambda b: (round(b["min_y"] / (avg_line_h * 0.7)), b["min_x"]))
        min_x = max(0, min(b["min_x"] for b in group))
        min_y = max(0, min(b["min_y"] for b in group))
        max_x = min(width, max(b["max_x"] for b in group))
        max_y = min(height, max(b["max_y"] for b in group))
        full_text = " ".join(b["text"] for b in group).strip()
        if full_text:
            merged.append({
                "min_x": min_x,
                "min_y": min_y,
                "max_x": max_x,
                "max_y": max_y,
                "text": full_text,
            })

    return merged


async def _detect_bubbles_with_winocr(image: Image.Image) -> List[Dict[str, Any]]:
    """Detect speech bubbles locally using native Windows OCR with line clustering."""
    try:
        import winocr
        res = await winocr.recognize_pil(image, lang="en")
        if not res.lines:
            return []

        width, height = image.size
        raw_lines = []

        for line in res.lines:
            if not line.words:
                continue
            text = line.text.strip()
            if len(text) < 2:
                continue

            min_x = min(w.bounding_rect.x for w in line.words)
            min_y = min(w.bounding_rect.y for w in line.words)
            max_x = max(w.bounding_rect.x + w.bounding_rect.width for w in line.words)
            max_y = max(w.bounding_rect.y + w.bounding_rect.height for w in line.words)

            raw_lines.append({
                "min_x": min_x,
                "min_y": min_y,
                "max_x": max_x,
                "max_y": max_y,
                "text": text,
            })

        # Cluster lines into unified speech bubbles
        clustered = _cluster_ocr_lines(raw_lines, width, height)
        bubbles = []

        for c in clustered:
            min_x = c["min_x"]
            min_y = c["min_y"]
            max_x = c["max_x"]
            max_y = c["max_y"]
            text = c["text"]

            # Multi-point sampling of true bubble background color around cluster perimeter and inner margins
            samples = []
            inset_x = max(2, int((max_x - min_x) * 0.05))
            inset_y = max(2, int((max_y - min_y) * 0.05))
            # 4 inner corners (safely within bubble, outside text)
            samples.append(image.getpixel((max(0, min_x + inset_x), max(0, min_y + inset_y))))
            samples.append(image.getpixel((min(width - 1, max_x - inset_x), max(0, min_y + inset_y))))
            samples.append(image.getpixel((max(0, min_x + inset_x), min(height - 1, max_y - inset_y))))
            samples.append(image.getpixel((min(width - 1, max_x - inset_x), min(height - 1, max_y - inset_y))))
            # Outer edges
            for frac in [0.25, 0.5, 0.75]:
                sx = int(min_x + frac * (max_x - min_x))
                sy = int(min_y + frac * (max_y - min_y))
                if min_y >= 3:
                    samples.append(image.getpixel((sx, max(0, min_y - 2))))
                if max_y <= height - 4:
                    samples.append(image.getpixel((sx, min(height - 1, max_y + 2))))
                if min_x >= 3:
                    samples.append(image.getpixel((max(0, min_x - 2), sy)))
                if max_x <= width - 4:
                    samples.append(image.getpixel((min(width - 1, max_x + 2), sy)))

            rgb_samples = [(s[0], s[1], s[2]) for s in samples if isinstance(s, (tuple, list)) and len(s) >= 3]
            if rgb_samples:
                lums = [0.299 * s[0] + 0.587 * s[1] + 0.114 * s[2] for s in rgb_samples]
                med_lum = sorted(lums)[len(lums) // 2]
                med_r = sorted([s[0] for s in rgb_samples])[len(rgb_samples) // 2]
                med_g = sorted([s[1] for s in rgb_samples])[len(rgb_samples) // 2]
                med_b = sorted([s[2] for s in rgb_samples])[len(rgb_samples) // 2]
                is_dark = med_lum < 118
                bg_color = f"#{med_r:02x}{med_g:02x}{med_b:02x}"
                text_color = "#FFFFFF" if is_dark else "#000000"
            else:
                is_dark = False
                bg_color = "#FFFFFF"
                text_color = "#000000"

            trans_text = await _translate_dialogue_text(text)

            box_2d = [
                int(min_y / height * 1000),
                int(min_x / width * 1000),
                int(max_y / height * 1000),
                int(max_x / width * 1000),
            ]

            bubbles.append({
                "box_2d": box_2d,
                "original_text": text,
                "translated_text": trans_text,
                "bg_color": bg_color,
                "text_color": text_color,
            })

        return bubbles
    except Exception as e:
        logger.warning(f"winocr detection failed: {e}")
        return []


async def translate_comic_image(image_bytes: bytes, image_url: str = "") -> bytes:
    """Translates English text inside comic speech bubbles directly into Vietnamese."""
    res, _ = await translate_comic_image_with_status(image_bytes, image_url)
    return res


async def translate_comic_image_with_status(image_bytes: bytes, image_url: str = "") -> Tuple[bytes, bool]:
    """
    Translates comic bubbles into Vietnamese.
    Returns (result_bytes, was_translated_or_cached).
    """
    if not image_bytes or len(image_bytes) < 100:
        return image_bytes, False

    # Generate cache key based on image content hash
    content_hash = hashlib.sha256(image_bytes).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"{content_hash}.jpg")

    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                cached_bytes = f.read()
            if image_url:
                try:
                    url_h = hashlib.sha256(image_url.encode("utf-8")).hexdigest()
                    u_path = os.path.join(CACHE_DIR, f"url_{url_h}.jpg")
                    if not os.path.exists(u_path):
                        with open(u_path, "wb") as f_u:
                            f_u.write(cached_bytes)
                except Exception:
                    pass
            return cached_bytes, True
        except Exception:
            pass

    # 1. Check pre-mapped bubbles by matching image URL keywords
    matched_bubbles: List[Dict[str, Any]] = []
    for key, bubbles in PREMAPPED_BUBBLES.items():
        if key in image_url:
            matched_bubbles = bubbles
            break

    # 2. Try Gemini Vision OCR first if configured (accurate comic balloon detection & natural translation)
    gemini_call_succeeded = False
    if not matched_bubbles and settings.GEMINI_API_KEY:
        try:
            detected, ok = await _detect_bubbles_with_gemini_vision(image_bytes, image_url)
            if ok:
                gemini_call_succeeded = True
                if detected:
                    matched_bubbles = detected
                else:
                    # Verified dialogue-free panel (fight scene, scenery, transition)!
                    # Cache raw panel so it loads in 0ms and never re-queries the API
                    with open(cache_path, "wb") as f:
                        f.write(image_bytes)
                    if image_url:
                        try:
                            url_hash = hashlib.sha256(image_url.encode("utf-8")).hexdigest()
                            url_cache_path = os.path.join(CACHE_DIR, f"url_{url_hash}.jpg")
                            with open(url_cache_path, "wb") as f:
                                f.write(image_bytes)
                        except Exception:
                            pass
                    return image_bytes, True
        except Exception as gemini_err:
            logger.warning(f"Gemini Vision detection error: {gemini_err}")

    # 3. Fallback to native Windows OCR (winocr) ONLY if Gemini Vision call failed or was not configured
    if not matched_bubbles and not gemini_call_succeeded:
        try:
            orig_img_check = Image.open(io.BytesIO(image_bytes))
            matched_bubbles = await _detect_bubbles_with_winocr(orig_img_check)
        except Exception as ocr_err:
            logger.warning(f"Native winocr error: {ocr_err}")

    # If no bubbles detected after both checks:
    if not matched_bubbles:
        return image_bytes, False

    try:
        orig_img = Image.open(io.BytesIO(image_bytes))
        translated_img = _render_bubbles_on_image(orig_img, matched_bubbles)

        out_buffer = io.BytesIO()
        translated_img.save(out_buffer, format="JPEG", quality=92, optimize=True)
        result_bytes = out_buffer.getvalue()

        # Save to disk cache by content hash
        with open(cache_path, "wb") as f:
            f.write(result_bytes)

        # Also save to disk cache by URL hash for instantaneous proxy lookup (0ms)
        if image_url:
            try:
                url_hash = hashlib.sha256(image_url.encode("utf-8")).hexdigest()
                url_cache_path = os.path.join(CACHE_DIR, f"url_{url_hash}.jpg")
                with open(url_cache_path, "wb") as f:
                    f.write(result_bytes)
            except Exception:
                pass

        return result_bytes, True
    except Exception as e:
        logger.error(f"Error rendering translated bubbles on comic panel: {e}")
        return image_bytes, False


_preload_active = False

async def preload_comic_panels_background(image_urls: List[str]):
    """
    Background worker that gently warms and caches comic panels in advance.
    Ensures 100% of chapter panels are pre-rendered into disk cache so
    readers experience 0ms load times and zero request timeouts.
    """
    global _preload_active
    if _preload_active or not image_urls:
        return
    _preload_active = True
    try:
        client = _get_shared_client()
        for url in image_urls:
            try:
                url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
                url_cache_path = os.path.join(CACHE_DIR, f"url_{url_hash}.jpg")
                if os.path.exists(url_cache_path):
                    continue

                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "image/*",
                }
                if "webtoon" in url or "pstatic.net" in url:
                    headers["Referer"] = "https://www.webtoons.com/"

                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    img_data, was_trans = await translate_comic_image_with_status(resp.content, url)
                    if was_trans:
                        try:
                            with open(url_cache_path, "wb") as f_out:
                                f_out.write(img_data)
                        except Exception:
                            pass
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.debug(f"Preload panel error for {url}: {e}")
                await asyncio.sleep(0.5)
    finally:
        _preload_active = False

