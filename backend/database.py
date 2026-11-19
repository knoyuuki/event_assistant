"""MySQL database connection and table initialization."""

import pymysql
import pymysql.err
from pymysql.cursors import DictCursor

from config_loader import load_config
from security import decrypt

# ─── Database config from active config file ───────────────────
# Loaded via config_loader (APP_ENV / APP_CONFIG); password is stored
# encrypted in the config file and decrypted here at startup.
_CONFIG = load_config()
DB_CONFIG = {
    "host": _CONFIG["database"].get("host", "127.0.0.1"),
    "port": _CONFIG["database"].get("port", 3306),
    "user": _CONFIG["database"].get("user", "root"),
    "password": decrypt(_CONFIG["database"].get("password_encrypted", "")),
    "database": _CONFIG["database"].get("database", "event_assistant"),
    "charset": _CONFIG["database"].get("charset", "utf8mb4"),
}

# ─── Department category tree (predefined) ──────────────────────────
# Each entry: {name, departments}
# sort_order is derived from the list index (0-based)

DEPT_CATEGORY_TREE = [
    {"name": "****分类1", "departments": ["****01", "****02", "****03", "****04"]},
    {"name": "****分类2", "departments": ["****05", "****06", "****07", "****08", "****09", "****10", "****11", "****12", "****13", "****14", "****15", "****16", "****17", "****18"]},
    {"name": "****分类3", "departments": ["****19", "****20", "****21", "****22", "****23", "****24", "****25", "****26"]},
    {"name": "****分类4", "departments": ["****27", "****28", "****29", "****30", "****31", "****32", "****33", "****34", "****35", "****36", "****37", "****38", "****39", "****40"]},
    {"name": "****分类5", "departments": ["****41", "****42", "****43", "****44", "****45", "****46"]},
    {"name": "****分类6", "departments": ["****47", "****48", "****49", "****50", "****51", "****52", "****53", "****54", "****55"]},
    {"name": "****分类7", "departments": ["****56", "****57", "****58", "****59", "****60", "****61", "****62", "****63", "****64", "****65", "****66"]},
    {"name": "****分类8", "departments": ["****67", "****68", "****69", "****70", "****71", "****72", "****73", "****74", "****75"]},
]

# Alias map: photo filename short name → canonical department name
DEPT_NAME_ALIASES = {
    # 部门别名映射（已脱敏；按实际部门名补充 short_name -> canonical_name）
}


def normalize_dept_name(raw_name: str) -> str:
    """Normalize a department name from photo filename to canonical name."""
    return DEPT_NAME_ALIASES.get(raw_name, raw_name)


def get_connection():
    """Get a new MySQL connection."""
    return pymysql.connect(**DB_CONFIG, cursorclass=DictCursor)


def init_database():
    """Create database and tables if they don't exist, and seed department tree."""
    # Connect without database to create it
    conn = pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        charset=DB_CONFIG["charset"],
    )
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    conn.close()

    # Connect to the database and create tables
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS persons (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(50) NOT NULL,
                department VARCHAR(100) NOT NULL,
                position VARCHAR(100) NOT NULL,
                filename VARCHAR(255) NOT NULL UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # Add new columns to persons table (if they don't exist)
        new_columns = [
            ("position_title", "VARCHAR(100) DEFAULT NULL COMMENT '人员职位'"),
            ("position_level", "DECIMAL(2,1) DEFAULT NULL COMMENT '职位等级'"),
            ("managed_departments", "TEXT DEFAULT NULL COMMENT '分管部门(JSON数组)'"),
            ("managed_businesses", "TEXT DEFAULT NULL COMMENT '分管业务(JSON数组)'"),
            ("notes", "TEXT DEFAULT NULL COMMENT '备注'"),
            ("person_type", "VARCHAR(20) DEFAULT NULL COMMENT '人员类型：部门领导/员工/P1/P2'"),
            ("sort_order", "INT DEFAULT NULL COMMENT '同部门同类型内排序'"),
            ("phone", "VARCHAR(60) DEFAULT NULL COMMENT '手机号'"),
            ("email", "VARCHAR(100) DEFAULT NULL COMMENT '邮箱'"),
        ]
        for col_name, col_def in new_columns:
            try:
                cur.execute(
                    f"ALTER TABLE persons ADD COLUMN {col_name} {col_def}"
                )
            except pymysql.err.OperationalError:
                pass  # Column already exists

        cur.execute("""
            CREATE TABLE IF NOT EXISTS test_results (
                id INT AUTO_INCREMENT PRIMARY KEY,
                total INT NOT NULL,
                correct INT NOT NULL,
                score DECIMAL(5,2) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                input_persons TEXT COMMENT '原始人员名单输入',
                input_departments TEXT NOT NULL COMMENT '原始部门名单输入',
                sorted_persons TEXT COMMENT '排序后人员名单JSON',
                sorted_departments TEXT COMMENT '排序后部门名单JSON',
                sort_snapshot_id INT DEFAULT NULL COMMENT '使用的部门排序存档ID',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # Add new columns to meetings table (if they don't exist)
        meeting_new_columns = [
            ("sort_snapshot_id", "INT DEFAULT NULL COMMENT '使用的部门排序存档ID'"),
        ]
        for col_name, col_def in meeting_new_columns:
            try:
                cur.execute(
                    f"ALTER TABLE meetings ADD COLUMN {col_name} {col_def}"
                )
            except pymysql.err.OperationalError:
                pass  # Column already exists

        cur.execute("""
            CREATE TABLE IF NOT EXISTS dept_sort_snapshots (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(200) NOT NULL COMMENT '存档名称',
                note TEXT DEFAULT NULL COMMENT '备注',
                data TEXT NOT NULL COMMENT '排序数据JSON',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS dept_categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                sort_order INT NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                description VARCHAR(255) DEFAULT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # Add new columns to departments table (if they don't exist)
        dept_new_columns = [
            ("category_id", "INT DEFAULT NULL COMMENT '所属分类ID'"),
            ("sort_order", "INT NOT NULL DEFAULT 0 COMMENT '排序'"),
        ]
        for col_name, col_def in dept_new_columns:
            try:
                cur.execute(
                    f"ALTER TABLE departments ADD COLUMN {col_name} {col_def}"
                )
            except pymysql.err.OperationalError:
                pass  # Column already exists

    conn.commit()

    # ─── Seed department categories and assign departments ──────────
    with conn.cursor() as cur:
        # Check if categories already exist
        cur.execute("SELECT COUNT(*) AS cnt FROM dept_categories")
        cat_count = cur.fetchone()["cnt"]

        if cat_count == 0:
            # Seed categories
            for idx, cat_data in enumerate(DEPT_CATEGORY_TREE):
                cur.execute(
                    "INSERT INTO dept_categories (name, sort_order) VALUES (%s, %s)",
                    (cat_data["name"], idx),
                )
            conn.commit()
            print(f"[DB] Seeded {len(DEPT_CATEGORY_TREE)} department categories.")

            # Seed departments from the tree and assign category_id + sort_order
            for cat_data in DEPT_CATEGORY_TREE:
                cur.execute(
                    "SELECT id FROM dept_categories WHERE name = %s",
                    (cat_data["name"],),
                )
                cat_row = cur.fetchone()
                if not cat_row:
                    continue
                cat_id = cat_row["id"]

                for dept_idx, dept_name in enumerate(cat_data["departments"]):
                    cur.execute(
                        "SELECT id FROM departments WHERE name = %s",
                        (dept_name,),
                    )
                    dept_row = cur.fetchone()
                    if dept_row:
                        # Update existing department with category_id and sort_order
                        cur.execute(
                            "UPDATE departments SET category_id = %s, sort_order = %s WHERE id = %s",
                            (cat_id, dept_idx, dept_row["id"]),
                        )
                    else:
                        # Insert new department
                        cur.execute(
                            "INSERT INTO departments (name, category_id, sort_order) VALUES (%s, %s, %s)",
                            (dept_name, cat_id, dept_idx),
                        )
            conn.commit()
            print("[DB] Seeded departments from category tree.")
        else:
            # Categories exist — check for departments with NULL category_id
            # and try to auto-assign them based on the tree mapping
            cur.execute(
                "SELECT id, name FROM departments WHERE category_id IS NULL"
            )
            unassigned = cur.fetchall()
            if unassigned:
                # Build a lookup: dept_name → (category_name, dept_sort_order)
                dept_to_cat = {}
                for cat_data in DEPT_CATEGORY_TREE:
                    for dept_idx, dept_name in enumerate(cat_data["departments"]):
                        dept_to_cat[dept_name] = (cat_data["name"], dept_idx)

                assigned = 0
                for dept in unassigned:
                    mapping = dept_to_cat.get(dept["name"])
                    if mapping:
                        cat_name, dept_sort = mapping
                        cur.execute(
                            "SELECT id FROM dept_categories WHERE name = %s",
                            (cat_name,),
                        )
                        cat_row = cur.fetchone()
                        if cat_row:
                            cur.execute(
                                "UPDATE departments SET category_id = %s, sort_order = %s WHERE id = %s",
                                (cat_row["id"], dept_sort, dept["id"]),
                            )
                            assigned += 1
                if assigned:
                    conn.commit()
                    print(f"[DB] Auto-assigned {assigned} departments to categories.")

    conn.close()
