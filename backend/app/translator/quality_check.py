import re
from typing import List, Tuple
from pydantic import BaseModel
from app.core.config import settings


class QualityCheckResult(BaseModel):
    is_valid: bool
    score: float = 1.0  # 0.0 to 1.0
    issues: List[str] = []


AI_HALLUCINATION_PATTERNS = [
    re.compile(r"as\s+an\s+ai\s+(?:language\s+)?model", re.IGNORECASE),
    re.compile(r"tôi\s+là\s+một\s+mô\s+hình\s+ngôn\s+ngữ\s+ai", re.IGNORECASE),
    re.compile(r"i\s+cannot\s+fulfill\s+this\s+request", re.IGNORECASE),
    re.compile(r"tôi\s+không\s+thể\s+thực\s+hiện\s+yêu\s+cầu", re.IGNORECASE),
    re.compile(r"dưới\s+đây\s+là\s+bản\s+dịch\s+của\s+bạn\s*:", re.IGNORECASE),
    re.compile(r"here\s+is\s+the\s+translation\s*:", re.IGNORECASE),
]


class QualityChecker:
    """Verifies chunk translation completeness, ratio, and absence of hallucinations."""

    @staticmethod
    def check_chunk(source_text: str, translated_text: str) -> QualityCheckResult:
        issues: List[str] = []
        score = 1.0

        if not translated_text or not translated_text.strip():
            return QualityCheckResult(
                is_valid=False,
                score=0.0,
                issues=["Bản dịch trả về rỗng."],
            )

        src_len = len(source_text.strip())
        trans_len = len(translated_text.strip())

        # 1. Ratio check (skip if chunk contains images)
        has_images = "[IMG:" in source_text
        if not has_images:
            ratio = trans_len / max(src_len, 1)
            if ratio < settings.QUALITY_MIN_RATIO:
                issues.append(f"Bản dịch quá ngắn bất thường so với bản gốc ({ratio:.2f} < {settings.QUALITY_MIN_RATIO}).")
                score -= 0.4
            elif ratio > settings.QUALITY_MAX_RATIO:
                issues.append(f"Bản dịch dài bất thường so với bản gốc ({ratio:.2f} > {settings.QUALITY_MAX_RATIO}).")
                score -= 0.4

        # 2. Hallucination / AI refusal check
        for pat in AI_HALLUCINATION_PATTERNS:
            if pat.search(translated_text):
                issues.append("Bản dịch chứa câu thoại từ chối hoặc lời chào của AI.")
                score -= 0.6
                break

        # 3. Repetition loop check (repeating same sentence 3+ times)
        # Strip out image tokens so URL dots/domains are not treated as sentence delimiters
        text_without_images = re.sub(r"\[IMG:[^\]]+\]", "", translated_text)
        trans_sentences = [s.strip() for s in re.split(r"[.!?。！？\n]+", text_without_images) if len(s.strip()) > 15]
        sentence_counts = {}
        for s in trans_sentences:
            sentence_counts[s] = sentence_counts.get(s, 0) + 1
            if sentence_counts[s] >= 3:
                issues.append(f"Phát hiện lặp nội dung câu dịch: '{s[:40]}...'")
                score -= 0.5
                break

        # 4. Paragraph retention check
        src_paras = [p.strip() for p in source_text.split("\n\n") if p.strip()]
        trans_paras = [p.strip() for p in translated_text.split("\n\n") if p.strip()]

        if len(src_paras) >= 3 and len(trans_paras) < len(src_paras) // 2:
            issues.append(f"Mất nhiều đoạn văn trong bản dịch: gốc {len(src_paras)} đoạn, dịch chỉ có {len(trans_paras)} đoạn.")
            score -= 0.3

        is_valid = score >= 0.5 and len(issues) == 0 or (len(issues) == 1 and "đoạn văn" in issues[0])
        score = max(0.0, min(1.0, score))

        return QualityCheckResult(
            is_valid=is_valid,
            score=score,
            issues=issues,
        )
