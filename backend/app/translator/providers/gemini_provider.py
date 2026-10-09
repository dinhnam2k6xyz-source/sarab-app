from typing import Dict, Optional
import httpx
from app.core.config import settings
from app.translator.providers.base import BaseTranslationProvider


class GeminiTranslationProvider(BaseTranslationProvider):
    name = "gemini"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL

    async def translate(
        self,
        text: str,
        source_language: str = "auto",
        target_language: str = "vi",
        glossary: Optional[Dict[str, str]] = None,
        context_hint: Optional[str] = "",
    ) -> str:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY chưa được cấu hình.")

        # Build prompt instructions
        glossary_instructions = ""
        if glossary:
            terms = "\n".join([f'- "{src}" => "{dst}"' for src, dst in glossary.items()])
            glossary_instructions = (
                f"\nBẢNG THUẬT NGỮ VÀ TÊN NHÂN VẬT (BẮT BUỘC TUÂN THỦ):\n{terms}\n"
            )

        context_instructions = ""
        if context_hint:
            context_instructions = f"\nBỐI CẢNH ĐOẠN TRƯỚC (DÙNG THAM KHẢO NGỮ CẢNH, KHÔNG DỊCH LẠI):\n{context_hint}\n"

        system_instruction = (
            "Bạn là một dịch giả tiểu thuyết chuyên nghiệp hàng đầu sang tiếng Việt. "
            "Nhiệm vụ của bạn là dịch đoạn văn bản sau sang tiếng Việt chuẩn văn phong truyện chữ, mượt mà và tự nhiên.\n"
            "QUY TẮC BẮT BUỘC:\n"
            "1. Tuyệt đối không tự ý thêm bớt nội dung, không bỏ sót đoạn văn.\n"
            "2. Giữ nguyên cấu trúc các đoạn văn. Mỗi đoạn văn cách nhau bằng hai dấu xuống dòng (\\n\\n).\n"
            "3. Dịch các câu đối thoại tự nhiên, đúng ngữ khí và cách xưng hô của nhân vật.\n"
            "4. Tuân thủ triệt để bảng thuật ngữ và tên riêng nếu có.\n"
            "5. Không thêm bất kỳ lời chào, lời dẫn, ghi chú hay markdown giải thích nào. CHỈ trả về nội dung đã dịch."
            f"{glossary_instructions}"
        )

        user_content = f"{context_instructions}\nVĂN BẢN CẦN DỊCH:\n{text}"

        payload = {
            "system_instruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_content}]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "topP": 0.95,
            }
        }

        models_to_try = [self.model] if self.model else ["gemini-flash-lite-latest"]
        fallbacks = [
            "gemini-flash-lite-latest",
            "gemini-3.1-flash-lite-preview",
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.6-flash",
            "gemini-3.7-flash",
            "gemini-3-flash-preview",
        ]
        for fb in fallbacks:
            if fb not in models_to_try:
                models_to_try.append(fb)

        last_error = ""
        async with httpx.AsyncClient(timeout=20.0) as client:
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
                try:
                    resp = await client.post(url, json=payload, timeout=10.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if not candidates:
                            continue
                        content_parts = candidates[0].get("content", {}).get("parts", [])
                        if not content_parts:
                            continue
                        translated_text = content_parts[0].get("text", "").strip()
                        if translated_text:
                            return translated_text
                    elif resp.status_code in (429, 503, 404):
                        last_error = f"Model {model_name} status {resp.status_code}"
                        continue
                    else:
                        last_error = f"Gemini API lỗi ({resp.status_code}) từ model {model_name}: {resp.text[:150]}"
                except Exception as e:
                    last_error = f"Lỗi kết nối tới {model_name}: {e}"
                    continue

        raise RuntimeError(f"Tất cả model Gemini trong pool đều không thể hoàn thành dịch. Chi tiết: {last_error}")
