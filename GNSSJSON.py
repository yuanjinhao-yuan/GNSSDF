import sqlite3
import json
import sys
import os

DB_FILE = "GNSSDF.db"
OUT_FILE = "GNSSDF.json"

def export_to_json(db_file=DB_FILE, out_file=OUT_FILE):
    if not os.path.exists(db_file):
        print(f"[!] 数据库不存在: {db_file}")
        return

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 先看看表结构，确认字段名
    c.execute("PRAGMA table_info(tracks)")
    cols = [row["name"] for row in c.fetchall()]
    print(f"[*] tracks 表字段: {cols}")

    c.execute("SELECT * FROM tracks ORDER BY time ASC")
    rows = c.fetchall()

    data = []
    for r in rows:
        item = {}
        for col in cols:
            item[col] = r[col]
        data.append(item)

    conn.close()

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[*] 已导出 {len(data)} 个点 → {out_file}")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_FILE
    out = sys.argv[2] if len(sys.argv) > 2 else OUT_FILE
    export_to_json(db, out)