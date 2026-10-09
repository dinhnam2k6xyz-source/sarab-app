from typing import Dict, Optional
import httpx
from app.core.config import settings
from app.translator.providers.base import BaseTranslationProvider


class OpenAITranslationProvider(BaseTranslationProvider):
    name = "openai"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL
        self.base_url = settings.OPENAI_BASE_URL.rstrip("/")

    async def translate(
        self,
        text: str,
        source_language: str = "auto",
        target_language: str = "vi",
        glossary: Optional[Dict[str, str]] = None,
        context_hint: Optional[str] = "",
    ) -> str:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY chưa được cấu hình.")

        url = f"{self.base_url}/chat/completions"

        glossary_instructions = ""
        if glossary:
            terms = "\n".join([f'- "{src}" => "{dst}"' for src, dst in glossary.items()])
            glossary_instructions = (
                f"\nBẢNG THUẬT NGỮ VÀ TÊN NHÂN VẬT (BẮT BUỘC TUÂN THỦ):\n{terms}\n"
            )

        context_instructions = ""
        if context_hint:
            context_instructions = f"\nBỐI CẢNH ĐOẠN TRƯỚC (DÙNG ĐỂ THAM KHẢO NGỮ CẢNH, KHÔNG DỊCH LẠI):\n{context_hint}\n"

        system_instruction = (
            "Bạn là dịch giả tiểu thuyết chuyên nghiệp hàng đầu sang tiếng Việt. "
            "Nhiệm vụ của bạn là dịch nguyên văn đoạn văn bản sau sang tiếng Việt chuẩn văn phong truyện chữ.\n"
            "QUY TẮC BẮT BUỘC:\n"
            "1. Tuyệt đối không tự ý thêm bớt nội dung, không bỏ sót đoạn văn.\n"
            "2. Giữ nguyên toàn bộ cấu trúc các đoạn văn (ngăn cách bởi \\n\\n).\n"
            "3. Dịch hội thoại tự nhiên, thuần Việt, đúng tính cách và cách xưng hô.\n"
            "4. Tuân thủ tuyệt đối bảng thuật ngữ tên riêng đã cung cấp.\n"
            "5. Không thêm bất kỳ lời chào, ghi chú hay markdown giải thích nào. CHỈ trả về văn bản đã dịch."
            f"{glossary_instructions}"
        )

        user_content = f"{context_instructions}\nVĂN BẢN GỐC CẦN DỊCH:\n{text}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.3,
        }

        async with httpx.AsyncClient(timeout=50.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI API lỗi ({resp.status_code}): {resp.text}")

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("OpenAI không trả về kết quả.")

            translated_text = choices[0].get("message", {}).get("content", "").strip()
            return translated_text
