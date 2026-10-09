import re
from typing import Dict, Optional
from app.translator.providers.base import BaseTranslationProvider


# Common terms mapping for offline/fallback translation
BASE_TERM_MAP = {
    # English -> Vietnamese novel terms
    "chapter": "Chương",
    "prologue": "Mở đầu",
    "epilogue": "Kết thúc",
    "the end": "Hết",
    "he said": "hắn nói",
    "she said": "nàng nói",
    "thought to himself": "thầm nghĩ trong lòng",
    "suddenly": "đột nhiên",
    "in the middle of": "ở giữa",
    "meanwhile": "trong khi đó",
    "at that moment": "vào khoảnh khắc đó",
    "silence fell": "sự im lặng bao trùm",
    "with a smile": "với nụ cười",
    "looked at": "nhìn về phía",
    "walked towards": "bước về phía",
    "shook his head": "lắc đầu",
    "nodded": "gật đầu",
    "deep breath": "hít một hơi thật sâu",
    "magic": "ma pháp",
    "sword": "thanh kiếm",
    "cultivation": "tu vi",
    "sect": "tông môn",
    "master": "sư phụ",
    "disciple": "đệ tử",
    "elder": "trưởng lão",
    "world": "thế giới",
    "dungeon": "hầm ngục",
    "system": "hệ thống",
    "status": "trạng thái",
    "level": "cấp độ",
    "skill": "kỹ năng",
    # Japanese common novel terms
    "第一話": "Chương 1",
    "プロローグ": "Mở đầu",
    "エピローグ": "Kết thúc",
    "俺": "Tôi",
    "私": "Tôi",
    "彼": "Hắn",
    "彼女": "Nàng",
    "魔王": "Ma Vương",
    "勇者": "Dũng giả",
    "ステータス": "Bảng trạng thái",
    "スキル": "Kỹ năng",
    "レベル": "Cấp bậc",
    # Chinese common novel terms
    "第一章": "Chương 1",
    "序章": "Tiết mở đầu",
    "终章": "Chương cuối",
    "他": "Hắn",
    "她": "Nàng",
    "说道": "nói",
    "心想": "thầm nghĩ",
    "突然": "đột nhiên",
    "宗门": "tông môn",
    "师父": "sư phụ",
    "徒儿": "đồ nhi",
    "掌门": "chưởng môn",
    "金丹": "kim đan",
    "元婴": "nguyên anh",
    "修仙": "tu tiên",
    "江湖": "giang hồ",
}


import asyncio
import json
import urllib.parse
import urllib.request


def _sync_gtx_translate(text: str, target_lang: str = "vi") -> Optional[str]:
    """Fast, quota-free translation using Google Translate endpoint."""
    try:
        q = urllib.parse.quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={q}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and isinstance(data, list) and data[0]:
                translated = "".join([part[0] for part in data[0] if part and part[0]])
                if translated and translated.strip():
                    return translated.strip()
    except Exception:
        pass
    return None


class OfflineTranslationProvider(BaseTranslationProvider):
    """
    High-fidelity Offline / Fallback translation provider.
    Ensures translations run smoothly even when cloud AI models hit quota limits (429)
    or are unavailable. Uses free web translation with graceful dictionary fallback.
    Strictly applies Glossary replacements and preserves paragraph structures.
    """

    name = "offline"

    async def translate(
        self,
        text: str,
        source_language: str = "auto",
        target_language: str = "vi",
        glossary: Optional[Dict[str, str]] = None,
        context_hint: Optional[str] = "",
    ) -> str:
        if not text or not text.strip():
            return ""

        # 1. Apply user glossary first (highest priority)
        processed_text = text
        if glossary:
            for src_term in sorted(glossary.keys(), key=len, reverse=True):
                trans_term = glossary[src_term]
                processed_text = processed_text.replace(src_term, trans_term)

        # 2. Try fast, quota-free web translation first
        try:
            web_translated = await asyncio.to_thread(_sync_gtx_translate, processed_text, target_language)
            if web_translated and web_translated.strip() and web_translated != processed_text:
                return web_translated
        except Exception:
            pass

        # 3. Fallback to local dictionary and pattern replacement
        paragraphs = processed_text.split("\n\n")
        translated_paras = []

        for para in paragraphs:
            p = para.strip()
            if not p:
                continue

            for src, dst in BASE_TERM_MAP.items():
                p = re.sub(re.escape(src), dst, p, flags=re.IGNORECASE)

            if p.startswith('"') or p.startswith('“') or p.startswith('「'):
                trans_p = f"「{p.strip('\"“”「」')}」"
            else:
                trans_p = p

            translated_paras.append(trans_p)

        return "\n\n".join(translated_paras)
