"""Scan the photos directory and sync person records to the database."""

import os
import re
from pathlib import Path
from database import get_connection, normalize_dept_name

# Photos directory — resolved to absolute path relative to this file
PHOTOS_DIR = str(Path(__file__).resolve().parent.parent / "photos")

# Supported image extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


def parse_filename(filename: str) -> tuple[str, str, str] | None:
    """
    Parse a filename like '姓名-部门-职位.jpg' into (name, department, position).
    Returns None if the filename doesn't match the expected pattern.
    """
    # Remove extension
    name_without_ext = os.path.splitext(filename)[0]
    # Split by '-'
    parts = name_without_ext.split("-")
    if len(parts) >= 3:
        # Name is the first part, department is everything between first and last,
        # position is the last part
        name = parts[0]
        position = parts[-1]
        department = "-".join(parts[1:-1])
        return name, department, position
    return None


def init_departments_from_photos(conn) -> None:
    """
    Scan the photos directory and initialize department records
    for any department names found that don't yet exist in the departments table.
    Also assigns category_id and sort_order for departments in the predefined tree.
    """
    if not os.path.isdir(PHOTOS_DIR):
        return

    dept_names = set()
    for fname in os.listdir(PHOTOS_DIR):
        ext = os.path.splitext(fname)[1].lower()
        if ext not in IMAGE_EXTENSIONS:
            continue
        parsed = parse_filename(fname)
        if parsed:
            # Normalize the department name from filename
            raw_dept = parsed[1]
            canonical_dept = normalize_dept_name(raw_dept)
            dept_names.add(canonical_dept)

    with conn.cursor() as cur:
        for dept in dept_names:
            # Check if department already exists
            cur.execute("SELECT id, category_id FROM departments WHERE name = %s", (dept,))
            existing = cur.fetchone()
            if existing:
                # If no category assigned yet, try to auto-assign
                if existing["category_id"] is None:
                    _try_assign_category(cur, dept, existing["id"])
            else:
                # Insert new department, trying to auto-assign category
                cat_id, sort_order = _get_category_info(dept)
                cur.execute(
                    "INSERT INTO departments (name, category_id, sort_order) VALUES (%s, %s, %s)",
                    (dept, cat_id, sort_order),
                )
    conn.commit()
    print(f"[Scanner] Initialized {len(dept_names)} departments from photos.")


def _get_category_info(dept_name: str) -> tuple[int | None, int]:
    """
    Look up a department name in the predefined tree and return
    (category_id, sort_order). Returns (None, 0) if not found.
    """
    from database import DEPT_CATEGORY_TREE
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for cat_data in DEPT_CATEGORY_TREE:
                for dept_idx, name in enumerate(cat_data["departments"]):
                    if name == dept_name:
                        cur.execute(
                            "SELECT id FROM dept_categories WHERE name = %s",
                            (cat_data["name"],),
                        )
                        cat_row = cur.fetchone()
                        if cat_row:
                            return cat_row["id"], dept_idx
                        break
        return None, 0
    finally:
        conn.close()


def _try_assign_category(cur, dept_name: str, dept_id: int) -> None:
    """Try to auto-assign a category_id and sort_order to an existing department."""
    from database import DEPT_CATEGORY_TREE
    for cat_data in DEPT_CATEGORY_TREE:
        for dept_idx, name in enumerate(cat_data["departments"]):
            if name == dept_name:
                cur.execute(
                    "SELECT id FROM dept_categories WHERE name = %s",
                    (cat_data["name"],),
                )
                cat_row = cur.fetchone()
                if cat_row:
                    cur.execute(
                        "UPDATE departments SET category_id = %s, sort_order = %s WHERE id = %s",
                        (cat_row["id"], dept_idx, dept_id),
                    )
                return


def scan_photos() -> list[dict]:
    """
    Scan the photos directory, parse filenames, and upsert into the database.
    Also initializes department records from discovered department names.
    Department names are normalized via the alias map.
    Returns the list of all person records.
    """
    if not os.path.isdir(PHOTOS_DIR):
        print(f"[Scanner] Photos directory not found: {PHOTOS_DIR}")
        return []

    conn = get_connection()
    try:
        # Initialize departments from photo filenames
        init_departments_from_photos(conn)

        scanned_files = set()
        for fname in os.listdir(PHOTOS_DIR):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in IMAGE_EXTENSIONS:
                continue

            parsed = parse_filename(fname)
            if parsed is None:
                print(f"[Scanner] Skipping unparseable file: {fname}")
                continue

            name, raw_department, position = parsed
            # Normalize department name to canonical form
            department = normalize_dept_name(raw_department)
            scanned_files.add(fname)

            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM persons WHERE filename = %s", (fname,)
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        "UPDATE persons SET name=%s, department=%s, position=%s "
                        "WHERE filename=%s",
                        (name, department, position, fname),
                    )
                else:
                    cur.execute(
                        "INSERT INTO persons (name, department, position, filename) "
                        "VALUES (%s, %s, %s, %s)",
                        (name, department, position, fname),
                    )
            conn.commit()

        # Remove DB records for deleted files
        with conn.cursor() as cur:
            cur.execute("SELECT filename FROM persons")
            db_files = {row["filename"] for row in cur.fetchall()}
            deleted = db_files - scanned_files
            for fname in deleted:
                cur.execute("DELETE FROM persons WHERE filename = %s", (fname,))
            if deleted:
                conn.commit()

        # Return all current persons
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM persons ORDER BY id")
            return cur.fetchall()
    finally:
        conn.close()
