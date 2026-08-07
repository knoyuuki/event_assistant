"""
Migration script: Clear all department data and rebuild from
people/企业通讯录部门层级.md.

Usage:
    cd backend
    python migrate_dept_tree.py
"""

import os
import re
import sys
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Ensure we can import database.py from this directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import get_connection

# Path to the markdown hierarchy file
MARKDOWN_FILE = str(
    Path(__file__).resolve().parent.parent / "people" / "企业通讯录部门层级.md"
)


def parse_markdown_tree(filepath: str) -> list[dict]:
    """
    Parse the markdown department hierarchy file.

    Structure:
        1.分类名称
        * 部门名称：...

    Returns:
        [{"name": "公司领导", "departments": ["公司领导", "资深总裁", ...]}, ...]
    """
    if not os.path.exists(filepath):
        print(f"[ERROR] Markdown file not found: {filepath}")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    tree = []
    current_category = None

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        # Match category line: "1.公司领导", "2.综合管理类", etc.
        cat_match = re.match(r"^\d+\.(.+)", line)
        if cat_match:
            current_category = {"name": cat_match.group(1).strip(), "departments": []}
            tree.append(current_category)
            continue

        # Match department line: "* 办公室：...", "* 资深总裁", etc.
        dept_match = re.match(r"^\*\s*(.+)$", line)
        if dept_match and current_category is not None:
            raw = dept_match.group(1).strip()
            # Split on full-width colon (U+FF1A) to strip personnel info
            colon_pos = raw.find("：")
            if colon_pos >= 0:
                dept_name = raw[:colon_pos].strip()
            else:
                dept_name = raw.strip()
            if dept_name and dept_name not in current_category["departments"]:
                current_category["departments"].append(dept_name)

    # Filter out any categories that have no departments parsed
    tree = [cat for cat in tree if cat["departments"]]
    return tree


def clear_and_rebuild(tree: list[dict]):
    """Delete all existing department data and rebuild from the parsed tree."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Clear departments first, then categories
            cur.execute("DELETE FROM departments")
            cur.execute("DELETE FROM dept_categories")
            # Reset auto-increment
            cur.execute("ALTER TABLE departments AUTO_INCREMENT = 1")
            cur.execute("ALTER TABLE dept_categories AUTO_INCREMENT = 1")
        conn.commit()
        print("[DB] Cleared all existing departments and categories.")

        with conn.cursor() as cur:
            for cat_idx, cat_data in enumerate(tree):
                # Insert category
                cur.execute(
                    "INSERT INTO dept_categories (name, sort_order) VALUES (%s, %s)",
                    (cat_data["name"], cat_idx),
                )
                cat_id = cur.lastrowid

                # Insert departments under this category
                for dept_idx, dept_name in enumerate(cat_data["departments"]):
                    cur.execute(
                        "INSERT INTO departments (name, category_id, sort_order) VALUES (%s, %s, %s)",
                        (dept_name, cat_id, dept_idx),
                    )

                print(
                    f"  [{cat_idx+1}] {cat_data['name']}: "
                    f"{len(cat_data['departments'])} departments"
                )

        conn.commit()
        print(f"\n[DONE] Rebuilt {len(tree)} categories with their departments.")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        conn.close()


def print_tree(tree: list[dict]):
    """Print the parsed tree for preview."""
    print("Parsed department tree from markdown:")
    print("=" * 50)
    for cat_data in tree:
        print(f"\n{cat_data['name']}:")
        for dept_name in cat_data["departments"]:
            print(f"  - {dept_name}")


def main():
    print("Parsing markdown hierarchy file...")
    tree = parse_markdown_tree(MARKDOWN_FILE)

    print_tree(tree)

    print("\n" + "=" * 50)
    print("Clearing and rebuilding database...")
    clear_and_rebuild(tree)


if __name__ == "__main__":
    main()
