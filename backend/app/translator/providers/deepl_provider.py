from typing import Dict, Optional
import httpx
from app.core.config import settings
from app.translator.providers.base import BaseTranslationProvider


class DeepLTranslationProvider(BaseTranslationProvider):
    name = "deepl"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.DEEPL_API_KEY
        # Free API keys usually end with :fx
        is_free = self.api_key.endswith(":fx") if self.api_key else True
        self.base_url = "https://api-free.deepl.com/v2/translate" if is_free else "https://api.deepl.com/v2/translate"

    async def translate(
        self,
        text: str,
        source_language: str = "auto",
        target_language: str = "VI",
        glossary: Optional[Dict[str, str]] = None,
        context_hint: Optional[str] = "",
    ) -> str:
        if not self.api_key:
            raise ValueError("DEEPL_API_KEY chưa được cấu hình.")

        # DeepL translates paragraph array or text
        paragraphs = text.split("\n\n")

        headers = {
            "Authorization": f"DeepL-Auth-Key {self.api_key}",
            "Content-Type": "application/json",
        }

        # Apply glossary pre-replacements if glossary is present
        processed_paras = []
        for p in paragraphs:
            cur_p = p
            if glossary:
                for k, v in glossary.items():
                    cur_p = cur_p.replace(k, v)
            processed_paras.append(cur_p)

        payload = {
            "text": processed_paras,
            "target_lang": target_language.upper(),
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(self.base_url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"DeepL API lỗi ({resp.status_code}): {resp.text}")

            data = resp.json()
            translations = data.get("translations", [])
            translated_paras = [t.get("text", "") for t in translations]

            return "\n\n".join(translated_paras)
