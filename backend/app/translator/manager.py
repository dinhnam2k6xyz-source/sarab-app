import asyncio
import time
from typing import Callable, Dict, Optional, Tuple
from app.core.config import settings
from app.core.logging import log_event
from app.cleaner.cleaner import ContentCleaner
from app.translator.chunker import ContentChunker, ChunkItem
from app.translator.quality_check import QualityChecker
from app.translator.providers.base import BaseTranslationProvider
from app.translator.providers.gemini_provider import GeminiTranslationProvider
from app.translator.providers.openai_provider import OpenAITranslationProvider
from app.translator.providers.deepl_provider import DeepLTranslationProvider
from app.translator.providers.offline_provider import OfflineTranslationProvider


class TranslationManager:
    """Orchestrates chunking, translation retry, fallback provider, quality verification, and merging."""

    def __init__(self):
        self.providers: Dict[str, BaseTranslationProvider] = {
            "gemini": GeminiTranslationProvider(),
            "openai": OpenAITranslationProvider(),
            "deepl": DeepLTranslationProvider(),
            "offline": OfflineTranslationProvider(),
        }

    def get_provider(self, name: Optional[str] = None) -> BaseTranslationProvider:
        prov_name = (name or settings.TRANSLATION_PROVIDER).lower()
        # If requested provider requires key but none configured, fall back to offline
        if prov_name == "gemini" and not settings.GEMINI_API_KEY:
            return self.providers["offline"]
        if prov_name == "openai" and not settings.OPENAI_API_KEY:
            return self.providers["offline"]
        if prov_name == "deepl" and not settings.DEEPL_API_KEY:
            return self.providers["offline"]

        return self.providers.get(prov_name, self.providers["offline"])

    def get_fallback_provider(self) -> BaseTranslationProvider:
        prov_name = settings.FALLBACK_PROVIDER.lower()
        return self.providers.get(prov_name, self.providers["offline"])

    async def _translate_chunk_with_retry(
        self,
        chunk: ChunkItem,
        glossary: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
    ) -> Tuple[str, str, float]:
        """
        Translates a single chunk with retry and fallback.
        Preserves image tokens [IMG:url] without wasting AI tokens.
        Returns (translated_chunk_text, provider_used, quality_score).
        """
        # If chunk contains ONLY image tokens (e.g. comic panels)
        non_img_paras = [p for p in chunk.paragraphs if not p.strip().startswith("[IMG:")]
        if not non_img_paras:
            return chunk.text, "images", 1.0
        primary_provider = self.get_provider()
        fallback_provider = self.get_fallback_provider()

        # For mixed chunks: protect [IMG:...] tags with placeholders so AI does not mutate them
        import re
        img_placeholders = {}
        chunk_text_to_translate = chunk.text
        if any(p.strip().startswith("[IMG:") for p in chunk.paragraphs):
            lines = chunk.text.split("\n\n")
            processed = []
            img_idx = 0
            for line in lines:
                if line.strip().startswith("[IMG:"):
                    ph = f"<<<IMG_TOKEN_{img_idx}>>>"
                    img_placeholders[ph] = line.strip()
                    processed.append(ph)
                    img_idx += 1
                else:
                    processed.append(line)
            chunk_text_to_translate = "\n\n".join(processed)

        def _restore_image_tokens(text_in: str) -> str:
            text_out = text_in
            for ph, orig_img in img_placeholders.items():
                text_out = text_out.replace(ph, orig_img)
            # Extra safety: restore any slight variations by AI (e.g., spaces or legacy format)
            for i, orig_img in enumerate(img_placeholders.values()):
                text_out = re.sub(rf"<<<\s*IMG_TOKEN_{i}\s*>>>", orig_img, text_out)
                text_out = re.sub(rf"\[(?:Illustration|Minh họa)\s*{i}\]", orig_img, text_out, flags=re.IGNORECASE)
            return text_out

        current_provider = primary_provider
        last_error = ""

        for attempt in range(1, max_retries + 1):
            try:
                start_t = time.time()
                trans_text = await current_provider.translate(
                    text=chunk_text_to_translate,
                    target_language="vi",
                    glossary=glossary,
                    context_hint=chunk.context_hint,
                )
                latency = (time.time() - start_t) * 1000

                # Restore original image tokens
                trans_text = _restore_image_tokens(trans_text)

                # Quality check
                qc_res = QualityChecker.check_chunk(chunk.text, trans_text)
                if qc_res.is_valid:
                    log_event(
                        event_type="translate_chunk_success",
                        translation_provider=current_provider.name,
                        latency_ms=latency,
                        status="ok",
                    )
                    return trans_text, current_provider.name, qc_res.score
                else:
                    last_error = f"Chất lượng dịch chưa đạt: {', '.join(qc_res.issues)}"
                    log_event(
                        event_type="translate_chunk_qc_failed",
                        translation_provider=current_provider.name,
                        latency_ms=latency,
                        status="error",
                        error=last_error,
                    )
            except Exception as e:
                last_error = str(e)
                log_event(
                    event_type="translate_chunk_error",
                    translation_provider=current_provider.name,
                    status="error",
                    error=last_error,
                )
                # If error is quota exceeded (429), switch immediately to fallback provider without waiting
                err_lower = last_error.lower()
                if ("429" in err_lower or "quota" in err_lower or "resource_exhausted" in err_lower) and current_provider != fallback_provider:
                    current_provider = fallback_provider
                    try:
                        trans_text = await current_provider.translate(
                            text=chunk_text_to_translate,
                            target_language="vi",
                            glossary=glossary,
                            context_hint=chunk.context_hint,
                        )
                        trans_text = _restore_image_tokens(trans_text)
                        qc_res = QualityChecker.check_chunk(chunk.text, trans_text)
                        return trans_text, current_provider.name, qc_res.score
                    except Exception as fb_err:
                        last_error = str(fb_err)
                        break

            # Exponential backoff
            if attempt < max_retries:
                await asyncio.sleep(min(2 ** attempt, 8))
            elif current_provider != fallback_provider:
                current_provider = fallback_provider
                try:
                    trans_text = await current_provider.translate(
                        text=chunk_text_to_translate,
                        target_language="vi",
                        glossary=glossary,
                        context_hint=chunk.context_hint,
                    )
                    trans_text = _restore_image_tokens(trans_text)
                    qc_res = QualityChecker.check_chunk(chunk.text, trans_text)
                    return trans_text, current_provider.name, qc_res.score
                except Exception as fb_err:
                    last_error = str(fb_err)

        raise RuntimeError(f"Không thể dịch đoạn {chunk.chunk_index}: {last_error}")

    async def _emit_progress(self, cb, cur: int, tot: int, pct: int, msg: str):
        if not cb:
            return
        if asyncio.iscoroutinefunction(cb):
            await cb(cur, tot, pct, msg)
        else:
            cb(cur, tot, pct, msg)

    async def translate_chapter(
        self,
        cleaned_text: str,
        chapter_title: str = "",
        glossary: Optional[Dict[str, str]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Tuple[str, str, str, float]:
        """
        Translates a complete chapter.
        Calls progress_callback(current_chunk, total_chunks, percent, message).
        Returns (translated_title, translated_text, provider_name, average_quality_score).
        """
        if not cleaned_text or not cleaned_text.strip():
            return chapter_title, "", "offline", 1.0

        # Step 1: Chunking
        await self._emit_progress(progress_callback, 0, 0, 5, "Đang chia đoạn...")

        chunks = ContentChunker.chunk(cleaned_text)
        total_chunks = len(chunks)

        if total_chunks == 0:
            return chapter_title, "", "offline", 1.0

        # Translate chapter title if needed
        trans_title = chapter_title
        if chapter_title:
            try:
                provider = self.get_provider()
                trans_title = await provider.translate(chapter_title, target_language="vi", glossary=glossary)
                trans_title = trans_title.strip()
            except Exception:
                trans_title = chapter_title

        translated_chunks = []
        providers_used = set()
        quality_scores = []

        # Step 2: Translate each chunk
        for chunk in chunks:
            pct = 10 + int((chunk.chunk_index - 1) / total_chunks * 80)
            msg = f"Đang dịch đoạn {chunk.chunk_index}/{total_chunks}..."
            await self._emit_progress(progress_callback, chunk.chunk_index, total_chunks, pct, msg)

            trans_chunk, prov, q_score = await self._translate_chunk_with_retry(chunk, glossary=glossary)
            translated_chunks.append(trans_chunk)
            providers_used.add(prov)
            quality_scores.append(q_score)

        # Step 3: Quality check on full text
        await self._emit_progress(progress_callback, total_chunks, total_chunks, 95, "Đang kiểm tra chất lượng hoàn tất...")

        merged_translation = "\n\n".join(translated_chunks)
        avg_score = sum(quality_scores) / len(quality_scores) if quality_scores else 1.0
        provider_name = ", ".join(providers_used) if providers_used else "gemini"

        await self._emit_progress(progress_callback, total_chunks, total_chunks, 100, "Hoàn thành!")

        return trans_title, merged_translation, provider_name, avg_score


translation_manager = TranslationManager()
