import sqlite3

from models.db import DB_PATH

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger'")
for r in cur.fetchall():
    print(r)
conn.close()
