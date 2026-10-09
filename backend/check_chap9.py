import sqlite3
import re

con = sqlite3.connect("backend/novel_translator.db")
row = con.cursor().execute("SELECT raw_html FROM chapter_contents WHERE chapter_id=9").fetchone()
if row:
    imgs = re.findall(r'<img src="([^"]+)"', row[0])
    for i, img in enumerate(imgs):
        print(f"[{i}]: {img}")
else:
    print("No raw_html for chapter 9")
