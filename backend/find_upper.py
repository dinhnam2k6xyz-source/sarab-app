import os
import glob
from PIL import Image
import asyncio
import winocr

async def find_image():
    cache_files = glob.glob('backend/cache/translated_panels/*.jpg')
    for f in cache_files:
        try:
            img = Image.open(f)
            res = await winocr.recognize_pil(img, lang="en")
            full_txt = " ".join(l.text for l in res.lines).lower()
            if "chet" in full_txt or "choc" in full_txt or "ky uc" in full_txt or "blanche so" in full_txt:
                print(f"FOUND UPPER PANEL: {f}")
                print(f"  Text: {full_txt}")
                return f
        except Exception as e:
            pass

if __name__ == "__main__":
    asyncio.run(find_image())
