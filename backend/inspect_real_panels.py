import asyncio
import os
import sys
from PIL import Image

sys.path.insert(0, os.path.abspath("backend"))
from app.image_translator.bubble_translator import _detect_bubbles_with_winocr

async def inspect():
    for p in ["backend/real_panel_2.jpg", "backend/real_panel_3.jpg", "backend/real_panel_4.jpg", "backend/real_panel_5.jpg"]:
        img = Image.open(p)
        bubbles = await _detect_bubbles_with_winocr(img)
        print(f"{p} ({img.size}): {len(bubbles)} bubbles found")
        for b in bubbles:
            print(f"  Box: {b['box_2d']}, Orig: '{b['original_text']}' -> Trans: '{b['translated_text'].encode('ascii', 'replace').decode()}'")

if __name__ == "__main__":
    asyncio.run(inspect())
