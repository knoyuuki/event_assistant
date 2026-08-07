"""
One-time data migration: copy all data from an existing database
(default: face_support) into the active config's database (event_assistant).

Primary keys are preserved so cross-table references stay consistent
(departments.category_id → dept_categories.id, meetings.sort_snapshot_id →
dept_sort_snapshots.id). Target tables are truncated before copying.

Usage:
    cd backend
    python migrate_db.py                 # face_support → event_assistant
    python migrate_db.py --src other_db  # custom source database
"""

import argparse
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import pymysql
from pymysql.cursors import DictCursor

from database import DB_CONFIG

# Copy order respects cross-table references (categories → departments → snapshots → meetings)
TABLES = [
    "dept_categories",
    "departments",
    "dept_sort_snapshots",
    "meetings",
    "persons",
    "test_results",
]


def migrate(src_db: str) -> None:
    src_cfg = {**DB_CONFIG, "database": src_db}
    dst_cfg = dict(DB_CONFIG)

    print(f"[Migrate] {src_db} → {dst_cfg['database']}")

    src = pymysql.connect(**src_cfg, cursorclass=DictCursor)
    dst = pymysql.connect(**dst_cfg, cursorclass=DictCursor)
    try:
        with dst.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")

        for table in TABLES:
            # Read source
            with src.cursor() as cur:
                cur.execute(f"SELECT * FROM `{table}`")
                rows = cur.fetchall()

            # Clear target
            with dst.cursor() as cur:
                cur.execute(f"TRUNCATE TABLE `{table}`")

            # Insert preserving ids
            if rows:
                cols = list(rows[0].keys())
                col_list = ", ".join(f"`{c}`" for c in cols)
                placeholders = ", ".join(["%s"] * len(cols))
                sql = f"INSERT INTO `{table}` ({col_list}) VALUES ({placeholders})"
                with dst.cursor() as cur:
                    for r in rows:
                        cur.execute(sql, [r[c] for c in cols])

            # Reset auto_increment to max(id)+1
            with dst.cursor() as cur:
                cur.execute(f"SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM `{table}`")
                next_id = cur.fetchone()["next_id"]
                cur.execute(f"ALTER TABLE `{table}` AUTO_INCREMENT = %s", (next_id,))

            print(f"  {table}: {len(rows)} 行")

        dst.commit()
        print("[Migrate] 完成。")
    except Exception as e:
        dst.rollback()
        print(f"[Migrate] 失败: {e}")
        raise
    finally:
        src.close()
        dst.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="从旧数据库迁移数据到当前配置的数据库")
    parser.add_argument("--src", default="face_support", help="源数据库名（默认 face_support）")
    args = parser.parse_args()
    migrate(args.src)
    return 0


if __name__ == "__main__":
    sys.exit(main())
