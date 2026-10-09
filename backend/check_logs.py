import sqlite3

con = sqlite3.connect("backend/novel_translator.db")
cur = con.cursor()
logs = cur.execute("SELECT * FROM crawl_logs ORDER BY id DESC LIMIT 20").fetchall()
print("Crawl logs:")
for l in logs:
    print(" ", l)

# Check if there are other tables or logs
import glob
print("All translated panels:", len(glob.glob("backend/cache/translated_panels/*.jpg")))
