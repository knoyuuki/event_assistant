"""MySQL database connection and table initialization."""

import pymysql
import pymysql.err
from pymysql.cursors import DictCursor

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "root",
    "database": "face_support",
    "charset": "utf8mb4",
}

# ─── Department category tree (predefined) ──────────────────────────
# Each entry: {name, departments}
# sort_order is derived from the list index (0-based)

DEPT_CATEGORY_TREE = [
    {"name": "公司领导", "departments": ["公司领导", "资深总裁", "资深副总裁", "资深经理"]},
    {"name": "综合管理类", "departments": ["办公室", "党群部", "企发部/数智办", "人力部", "审计部", "法律部/运营NOC", "纪委办", "巡察办", "安管部", "工会", "采购中心", "P1", "P2", "云办"]},
    {"name": "运营统筹类", "departments": ["总师室", "市场部", "财务部", "云网运", "政企事业群", "资本中心", "云网发", "客服部"]},
    {"name": "区局分公司", "departments": ["中区局", "南区局", "西区局", "北区局", "东区局", "莘闵局", "宝山局", "嘉定局", "浦东局", "金山局", "松江局", "青浦局", "奉贤局", "崇明局"]},
    {"name": "行业大客户部", "departments": ["政务BD", "公共服务BD", "金融BD", "工商BD", "战略BD", "科创BD"]},
    {"name": "经营责任类", "departments": ["信网部", "数生部", "商客部/上海号百", "公客部", "渠道中心", "客经中心", "理想公司", "云中台/数集部", "云能力中心"]},
    {"name": "运营支撑类", "departments": ["移互部", "应急局", "业管中心", "上海ICNOC", "客服中心", "业财中心", "政支中心", "网信安部", "共服中心", "AIBOC", "市民热线"]},
    {"name": "云舟", "departments": ["信天公司", "信网公司", "宽频公司", "凯讯公司", "海缆公司", "百事应", "临港算力", "上海热线", "新华电信"]},
]

# Alias map: photo filename short name → canonical department name
DEPT_NAME_ALIASES = {
    "数智办": "企发部/数智办",
    "企发部": "企发部/数智办",
    "数字生活部": "数生部",
    "采供中心": "采购中心",
    "采供": "采购中心",
    "运营NOC": "法律部/运营NOC",
    "法律部": "法律部/运营NOC",
    "ICNOC": "上海ICNOC",
    "信产公司": "云能力中心",
    "天翼云": "云能力中心",
    "天翼云上海分公司": "云能力中心",
    "商客部": "商客部/上海号百",
    "上海号百": "商客部/上海号百",
    "数集部": "云中台/数集部",
    "云中台": "云中台/数集部",
    # Excel→Markdown 部门名映射（一级分类中可能出现的合并名）
    "云网运/应急办/重大办": "云网运",
    "云网运营/重大办": "云网运",
    "移互部/网优中心/5G共建共享工作组": "移互部",
    "信网部/互联网BD": "信网部",
    "政支中心/量子中心": "政支中心",
    "数生部/互联网部": "数生部",
    "数生部/智慧家庭中心": "数生部",
    "党群部/企业文化部/党委办/": "党群部",
    "党群部/企业文化部/党委办": "党群部",
    "公客部/终端公司": "公客部",
    "集团客服中心": "客服中心",
    # Additional Excel→DB department mappings
    "政务BD/重大办": "政务BD",
    "上海理想本部": "理想公司",
    "云能力中心/数字政务中心": "云能力中心",
    "云中台专班": "云中台/数集部",
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
