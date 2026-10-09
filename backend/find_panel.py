import os
import glob
from PIL import Image
import asyncio
import winocr

async def find_image():
    cache_files = glob.glob('backend/cache/translated_panels/*.jpg')
    print(f"Checking {len(cache_files)} cached images...")
    for f in cache_files:
        try:
            img = Image.open(f)
            res = await winocr.recognize_pil(img, lang="en")
            full_txt = " ".join(l.text for l in res.lines).lower()
            keywords = ["abigail", "blanche", "cung", "xinh", "hnh ha", "hành", "dù sao", "chết", "chóc"]
            if any(k in full_txt for k in keywords):
                print(f"MATCH: {f}")
                print(f"  Text: {full_txt[:120]}")
        except Exception as e:
            pass

if __name__ == "__main__":
    asyncio.run(find_image())
