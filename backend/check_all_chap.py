import sqlite3
import re

con = sqlite3.connect("backend/novel_translator.db")
cur = con.cursor()
rows = cur.execute("SELECT chapter_id, raw_html FROM chapter_contents").fetchall()
for cid, html in rows:
    imgs = re.findall(r'<img src="([^"]+)"', html)
    print(f"Chapter ID {cid}: {len(imgs)} images")

novels = cur.execute("SELECT id, title FROM novels").fetchall()
print("Novels:", [(n[0], n[1].encode('ascii', 'replace').decode()) for n in novels])

chapters = cur.execute("SELECT id, novel_id, title, chapter_number, url FROM chapters").fetchall()
print("Chapters:")
for c in chapters:
    print(c[0], c[1], c[2].encode('ascii', 'replace').decode(), c[4])
