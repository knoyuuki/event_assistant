"""FastAPI application - Face Recognition Assistant backend."""

import json
import os
import random
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from database import init_database, get_connection, normalize_dept_name, DEPT_CATEGORY_TREE
from models import (
    TestCheckRequest, TestResultSave,
    PersonCreate, PersonUpdate,
    DepartmentCreate, DepartmentUpdate,
    DeptCategoryCreate, DeptCategoryUpdate, ReorderItem,
    MeetingCreate, MeetingUpdate, MeetingResort,
    DeptSnapshotCreate, DeptSnapshotUpdate,
    POSITION_LEVEL_MAP, POSITION_LEVEL_ALIASES, PERSON_TYPES,
    get_position_level,
)

# Photos directory — resolved to absolute path relative to this file
PHOTOS_DIR = str(Path(__file__).resolve().parent.parent / "photos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_database()
    print(f"[Startup] Database initialized.")
    yield


app = FastAPI(title="Face Recognition Assistant", lifespan=lifespan)

# CORS - allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Photo Serving ───────────────────────────────────────────

@app.get("/api/photo/{filename}")
def serve_photo(filename: str):
    """Serve a photo file from the photos directory."""
    filepath = os.path.join(PHOTOS_DIR, filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(filepath)


# ─── Person Endpoints ────────────────────────────────────────

@app.get("/api/persons")
def list_persons(
    department: str = Query(None),
    person_type: str = Query(None),
    position_level: float = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """List persons with optional department/type filter, fuzzy name search, and pagination."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Build WHERE clauses
            conditions = []
            params = []

            if department:
                conditions.append("department = %s")
                params.append(department)

            if person_type:
                conditions.append("person_type = %s")
                params.append(person_type)

            if position_level is not None:
                conditions.append("position_level = %s")
                params.append(position_level)

            if search:
                conditions.append("name LIKE %s")
                params.append(f"%{search}%")

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            # Count total
            cur.execute(f"SELECT COUNT(*) AS cnt FROM persons {where_clause}", params)
            total = cur.fetchone()["cnt"]

            # Fetch page — sort by department/type/sort_order when filtered
            order_clause = "ORDER BY department, person_type, sort_order, id"
            offset = (page - 1) * page_size
            cur.execute(
                f"SELECT * FROM persons {where_clause} {order_clause} "
                f"LIMIT %s OFFSET %s",
                params + [page_size, offset],
            )
            items = cur.fetchall()

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
    finally:
        conn.close()


@app.get("/api/persons/sequential")
def persons_sequential(department: str = Query(None)):
    """List persons in sequential (filename) order."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if department:
                cur.execute(
                    "SELECT * FROM persons WHERE department = %s ORDER BY filename",
                    (department,)
                )
            else:
                cur.execute("SELECT * FROM persons ORDER BY filename")
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/api/persons/random")
def persons_random(department: str = Query(None)):
    """List persons in random order."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if department:
                cur.execute(
                    "SELECT * FROM persons WHERE department = %s",
                    (department,)
                )
            else:
                cur.execute("SELECT * FROM persons")
            rows = cur.fetchall()
        random.shuffle(rows)
        return rows
    finally:
        conn.close()


@app.put("/api/persons/reorder")
def reorder_persons(items: list[ReorderItem]):
    """Batch reorder persons within their department+person_type group."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for item in items:
                cur.execute(
                    "UPDATE persons SET sort_order = %s WHERE id = %s",
                    (item.sort_order, item.id),
                )
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.get("/api/person-types")
def list_person_types():
    """Return all valid person type values."""
    return {"types": PERSON_TYPES}


@app.get("/api/persons/{person_id}")
def get_person(person_id: int):
    """Get a single person by ID."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM persons WHERE id = %s", (person_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Person not found")
            return row
    finally:
        conn.close()


@app.post("/api/persons")
def create_person(req: PersonCreate):
    """Create a new person record."""
    conn = get_connection()
    try:
        # Auto-calculate position_level if not provided
        level = req.position_level
        if level is None and req.position_title:
            level = get_position_level(req.position_title)

        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO persons
                   (name, department, position, filename,
                    person_type, sort_order,
                    position_title, position_level,
                    managed_departments, managed_businesses, notes,
                    phone, email)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (req.name, req.department, req.position, req.filename,
                 req.person_type, req.sort_order,
                 req.position_title, level,
                 req.managed_departments, req.managed_businesses, req.notes,
                 req.phone, req.email),
            )
            new_id = cur.lastrowid
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT * FROM persons WHERE id = %s", (new_id,))
            return cur.fetchone()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.put("/api/persons/{person_id}")
def update_person(person_id: int, req: PersonUpdate):
    """Update a person record."""
    conn = get_connection()
    try:
        # Check exists
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM persons WHERE id = %s", (person_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Person not found")

        # Build update fields
        fields = {}
        if req.name is not None:
            fields["name"] = req.name
        if req.department is not None:
            fields["department"] = req.department
        if req.position is not None:
            fields["position"] = req.position
        if req.filename is not None:
            fields["filename"] = req.filename
        if req.person_type is not None:
            fields["person_type"] = req.person_type
        if req.sort_order is not None:
            fields["sort_order"] = req.sort_order
        if req.position_title is not None:
            fields["position_title"] = req.position_title
        if req.position_level is not None:
            fields["position_level"] = req.position_level
        if req.managed_departments is not None:
            fields["managed_departments"] = req.managed_departments
        if req.managed_businesses is not None:
            fields["managed_businesses"] = req.managed_businesses
        if req.notes is not None:
            fields["notes"] = req.notes
        if req.phone is not None:
            fields["phone"] = req.phone
        if req.email is not None:
            fields["email"] = req.email

        # Auto-calculate position_level if title changed without explicit level
        if "position_title" in fields and "position_level" not in fields:
            fields["position_level"] = get_position_level(fields["position_title"])

        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        set_clause = ", ".join(f"{k}=%s" for k in fields)
        values = list(fields.values()) + [person_id]

        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE persons SET {set_clause} WHERE id = %s",
                values,
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT * FROM persons WHERE id = %s", (person_id,))
            return cur.fetchone()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.delete("/api/persons/{person_id}")
def delete_person(person_id: int):
    """Delete a person record."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM persons WHERE id = %s", (person_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Person not found")
            cur.execute("DELETE FROM persons WHERE id = %s", (person_id,))
        conn.commit()
        return {"status": "ok"}
    finally:
        conn.close()


# ─── Department Category Endpoints ───────────────────────────

@app.get("/api/dept-categories")
def list_categories():
    """List all department categories ordered by sort_order."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM dept_categories ORDER BY sort_order, id")
            return cur.fetchall()
    finally:
        conn.close()


@app.post("/api/dept-categories")
def create_category(req: DeptCategoryCreate):
    """Create a new department category."""
    conn = get_connection()
    try:
        sort_order = req.sort_order
        if sort_order is None:
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order FROM dept_categories")
                sort_order = cur.fetchone()["next_order"]

        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO dept_categories (name, sort_order) VALUES (%s, %s)",
                (req.name, sort_order),
            )
            new_id = cur.lastrowid
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT * FROM dept_categories WHERE id = %s", (new_id,))
            return cur.fetchone()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.put("/api/dept-categories/reorder")
def reorder_categories(items: list[ReorderItem]):
    """Batch reorder department categories."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for item in items:
                cur.execute(
                    "UPDATE dept_categories SET sort_order = %s WHERE id = %s",
                    (item.sort_order, item.id),
                )
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.put("/api/dept-categories/{cat_id}")
def update_category(cat_id: int, req: DeptCategoryUpdate):
    """Update a department category."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM dept_categories WHERE id = %s", (cat_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Category not found")

        fields = {}
        if req.name is not None:
            fields["name"] = req.name
        if req.sort_order is not None:
            fields["sort_order"] = req.sort_order

        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        set_clause = ", ".join(f"{k}=%s" for k in fields)
        values = list(fields.values()) + [cat_id]

        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE dept_categories SET {set_clause} WHERE id = %s",
                values,
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT * FROM dept_categories WHERE id = %s", (cat_id,))
            return cur.fetchone()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.delete("/api/dept-categories/{cat_id}")
def delete_category(cat_id: int):
    """Delete a department category (only if no departments reference it)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM dept_categories WHERE id = %s", (cat_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Category not found")

            # Check for departments referencing this category
            cur.execute("SELECT COUNT(*) AS cnt FROM departments WHERE category_id = %s", (cat_id,))
            dept_count = cur.fetchone()["cnt"]
            if dept_count > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot delete: {dept_count} departments still reference this category"
                )

            cur.execute("DELETE FROM dept_categories WHERE id = %s", (cat_id,))
        conn.commit()
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


# ─── Department Endpoints ────────────────────────────────────

@app.get("/api/departments")
def list_departments(tree: bool = Query(False)):
    """List all departments. If tree=true, return nested category→department structure."""
    conn = get_connection()
    try:
        if tree:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM dept_categories ORDER BY sort_order, id")
                categories = cur.fetchall()
                cur.execute("SELECT * FROM departments ORDER BY sort_order, id")
                departments = cur.fetchall()

            # Group departments by category_id
            dept_by_cat: dict[int | None, list] = {}
            for dept in departments:
                cat_id = dept.get("category_id")
                dept_by_cat.setdefault(cat_id, []).append(dept)

            result = []
            for cat in categories:
                result.append({
                    **cat,
                    "departments": dept_by_cat.get(cat["id"], []),
                })

            # Add uncategorized departments if any
            uncategorized = dept_by_cat.get(None, [])
            if uncategorized:
                result.append({
                    "id": None,
                    "name": "未分类",
                    "sort_order": 999,
                    "created_at": None,
                    "departments": uncategorized,
                })

            return result
        else:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM departments ORDER BY category_id, sort_order, id"
                )
                return cur.fetchall()
    finally:
        conn.close()


@app.get("/api/departments/names")
def list_department_names():
    """List all distinct department names in tree order (for filter dropdowns)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Join persons with departments and categories to sort in tree order
            cur.execute("""
                SELECT DISTINCT p.department
                FROM persons p
                LEFT JOIN departments d ON p.department = d.name
                LEFT JOIN dept_categories c ON d.category_id = c.id
                ORDER BY COALESCE(c.sort_order, 999), COALESCE(d.sort_order, 999), p.department
            """)
            return [row["department"] for row in cur.fetchall()]
    finally:
        conn.close()


@app.post("/api/departments")
def create_department(req: DepartmentCreate):
    """Create a new department."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Auto-assign sort_order if not provided
            sort_order = req.sort_order
            if sort_order == 0 and req.category_id:
                cur.execute(
                    "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order FROM departments WHERE category_id = %s",
                    (req.category_id,),
                )
                row = cur.fetchone()
                if row:
                    sort_order = row["next_order"]

            cur.execute(
                "INSERT INTO departments (name, category_id, sort_order, description) VALUES (%s, %s, %s, %s)",
                (req.name, req.category_id, sort_order, req.description),
            )
            new_id = cur.lastrowid
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT * FROM departments WHERE id = %s", (new_id,))
            return cur.fetchone()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.put("/api/departments/reorder")
def reorder_departments(items: list[ReorderItem]):
    """Batch reorder departments."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for item in items:
                cur.execute(
                    "UPDATE departments SET sort_order = %s WHERE id = %s",
                    (item.sort_order, item.id),
                )
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.put("/api/departments/{dept_id}")
def update_department(dept_id: int, req: DepartmentUpdate):
    """Update a department."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM departments WHERE id = %s", (dept_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Department not found")

        fields = {}
        if req.name is not None:
            fields["name"] = req.name
        if req.category_id is not None:
            fields["category_id"] = req.category_id
        if req.sort_order is not None:
            fields["sort_order"] = req.sort_order
        if req.description is not None:
            fields["description"] = req.description

        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        set_clause = ", ".join(f"{k}=%s" for k in fields)
        values = list(fields.values()) + [dept_id]

        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE departments SET {set_clause} WHERE id = %s",
                values,
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT * FROM departments WHERE id = %s", (dept_id,))
            return cur.fetchone()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.delete("/api/departments/{dept_id}")
def delete_department(dept_id: int):
    """Delete a department."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM departments WHERE id = %s", (dept_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Department not found")
            cur.execute("DELETE FROM departments WHERE id = %s", (dept_id,))
        conn.commit()
        return {"status": "ok"}
    finally:
        conn.close()


# ─── Department Sort Snapshot (部门排序存档) ──────────────────────

def _capture_dept_tree(conn) -> dict:
    """Capture the current department tree ordering as a serializable dict."""
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM dept_categories ORDER BY sort_order, id")
        categories = cur.fetchall()
        cur.execute("SELECT * FROM departments ORDER BY category_id, sort_order, id")
        departments = cur.fetchall()

    dept_by_cat: dict[int | None, list] = {}
    for dept in departments:
        dept_by_cat.setdefault(dept.get("category_id"), []).append(dept)

    result = [
        {
            "id": c["id"],
            "name": c["name"],
            "sort_order": c["sort_order"],
            "departments": [
                {
                    "id": d["id"],
                    "name": d["name"],
                    "category_id": d["category_id"],
                    "sort_order": d["sort_order"],
                }
                for d in dept_by_cat.get(c["id"], [])
            ],
        }
        for c in categories
    ]

    # Include uncategorized departments so no department is dropped,
    # and their 所属分类 (category membership = NULL) is preserved.
    uncategorized = dept_by_cat.get(None, [])
    if uncategorized:
        result.append({
            "id": None,
            "name": "未分类",
            "sort_order": 999,
            "departments": [
                {
                    "id": d["id"],
                    "name": d["name"],
                    "category_id": None,
                    "sort_order": d["sort_order"],
                }
                for d in uncategorized
            ],
        })

    return {"categories": result}


def _parse_snapshot_rank(data_json: str) -> dict:
    """Build a {dept_name: (cat_order, dept_order)} lookup from a snapshot's data."""
    try:
        data = json.loads(data_json)
    except Exception:
        return {"dept": {}}
    dept_rank: dict[str, tuple] = {}
    for cat in data.get("categories", []):
        # Uncategorized pseudo-group (id is None) sorts after all real categories
        cat_order = 999 if cat.get("id") is None else cat.get("sort_order", 0)
        for d in cat.get("departments", []):
            dept_rank[d["name"]] = (cat_order, d.get("sort_order", 0))
    return {"dept": dept_rank}


@app.get("/api/dept-snapshots")
def list_dept_snapshots():
    """List all saved department sort snapshots (newest first)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, note, data, created_at FROM dept_sort_snapshots ORDER BY id DESC"
            )
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/api/dept-snapshots/{snapshot_id}")
def get_dept_snapshot(snapshot_id: int):
    """Get a single saved department sort snapshot."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, note, data, created_at FROM dept_sort_snapshots WHERE id = %s",
                (snapshot_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="排序存档不存在")
            return row
    finally:
        conn.close()


@app.post("/api/dept-snapshots")
def create_dept_snapshot(req: DeptSnapshotCreate):
    """Save the current department tree ordering as a named snapshot."""
    conn = get_connection()
    try:
        if not req.name or not req.name.strip():
            raise HTTPException(status_code=400, detail="存档名称不能为空")
        data_json = json.dumps(_capture_dept_tree(conn), ensure_ascii=False)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO dept_sort_snapshots (name, note, data) VALUES (%s, %s, %s)",
                (req.name.strip(), req.note, data_json),
            )
            new_id = cur.lastrowid
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, note, data, created_at FROM dept_sort_snapshots WHERE id = %s",
                (new_id,),
            )
            return cur.fetchone()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.put("/api/dept-snapshots/{snapshot_id}")
def update_dept_snapshot(snapshot_id: int, req: DeptSnapshotUpdate):
    """Update a snapshot's name and/or note. When recapture is true,
    also overwrite the snapshot's stored data with the current tree order."""
    conn = get_connection()
    try:
        fields = {}
        if req.name is not None:
            if not req.name.strip():
                raise HTTPException(status_code=400, detail="存档名称不能为空")
            fields["name"] = req.name.strip()
        if req.note is not None:
            fields["note"] = req.note
        if req.recapture:
            fields["data"] = json.dumps(_capture_dept_tree(conn), ensure_ascii=False)

        if not fields:
            raise HTTPException(status_code=400, detail="没有需要更新的字段")

        set_clause = ", ".join(f"{k}=%s" for k in fields)
        values = list(fields.values()) + [snapshot_id]

        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE dept_sort_snapshots SET {set_clause} WHERE id = %s",
                values,
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="排序存档不存在")
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, note, data, created_at FROM dept_sort_snapshots WHERE id = %s",
                (snapshot_id,),
            )
            return cur.fetchone()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.delete("/api/dept-snapshots/{snapshot_id}")
def delete_dept_snapshot(snapshot_id: int):
    """Delete a saved department sort snapshot."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM dept_sort_snapshots WHERE id = %s", (snapshot_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="排序存档不存在")
        conn.commit()
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.post("/api/dept-snapshots/{snapshot_id}/apply")
def apply_dept_snapshot(snapshot_id: int):
    """Restore the current department tree to a snapshot's ordering."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM dept_sort_snapshots WHERE id = %s", (snapshot_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="排序存档不存在")
            data = json.loads(row["data"])

            for cat_idx, cat in enumerate(data.get("categories", [])):
                # "未分类" pseudo-group (id is None): restore departments to uncategorized
                if cat.get("id") is None:
                    target_cat_id = None
                else:
                    # Resolve category by id first, then by name (in case ids changed)
                    cat_db = None
                    cur.execute("SELECT id FROM dept_categories WHERE id = %s", (cat["id"],))
                    cat_db = cur.fetchone()
                    if not cat_db:
                        cur.execute("SELECT id FROM dept_categories WHERE name = %s", (cat["name"],))
                        cat_db = cur.fetchone()
                    if not cat_db:
                        continue
                    target_cat_id = cat_db["id"]
                    cur.execute(
                        "UPDATE dept_categories SET sort_order = %s WHERE id = %s",
                        (cat_idx, target_cat_id),
                    )

                for dept_idx, d in enumerate(cat.get("departments", [])):
                    dept_db = None
                    if d.get("id") is not None:
                        cur.execute("SELECT id FROM departments WHERE id = %s", (d["id"],))
                        dept_db = cur.fetchone()
                    if not dept_db:
                        cur.execute("SELECT id FROM departments WHERE name = %s", (d["name"],))
                        dept_db = cur.fetchone()
                    if not dept_db:
                        continue
                    cur.execute(
                        "UPDATE departments SET category_id = %s, sort_order = %s WHERE id = %s",
                        (target_cat_id, dept_idx, dept_db["id"]),
                    )
        conn.commit()
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


# ─── Position Level ──────────────────────────────────────────

@app.get("/api/position-levels")
def get_position_levels():
    """Get the position title to level mapping, aliases, and person types."""
    return {
        "mapping": POSITION_LEVEL_MAP,
        "aliases": POSITION_LEVEL_ALIASES,
        "default_level": 4.0,
    }


# ─── Test Endpoints ──────────────────────────────────────────

@app.post("/api/test/check")
def check_answers(req: TestCheckRequest):
    """Check test answers and return score."""
    if not req.answers:
        return {"total": 0, "correct": 0, "score": 0, "details": []}

    conn = get_connection()
    try:
        details = []
        correct_count = 0
        with conn.cursor() as cur:
            for ans in req.answers:
                cur.execute("SELECT name FROM persons WHERE id = %s", (ans.id,))
                row = cur.fetchone()
                correct_name = row["name"] if row else ""
                is_correct = (ans.name.strip() == correct_name)
                if is_correct:
                    correct_count += 1
                details.append({
                    "id": ans.id,
                    "correct_name": correct_name,
                    "user_answer": ans.name.strip(),
                    "is_correct": is_correct,
                })

        total = len(req.answers)
        score = round((correct_count / total) * 100, 2) if total > 0 else 0
        return {
            "total": total,
            "correct": correct_count,
            "score": score,
            "details": details,
        }
    finally:
        conn.close()


@app.post("/api/test/results")
def save_test_result(req: TestResultSave):
    """Save a test result to the database."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO test_results (total, correct, score) VALUES (%s, %s, %s)",
                (req.total, req.correct, req.score),
            )
        conn.commit()
        return {"status": "ok"}
    finally:
        conn.close()


# ─── Import ──────────────────────────────────────────────────

@app.post("/api/import-excel")
def import_excel(dry_run: bool = Query(False)):
    """Import personnel data from the Excel directory file."""
    from importer import import_persons_from_excel
    result = import_persons_from_excel(dry_run=dry_run)
    return result


@app.post("/api/import-markdown-leaders")
def import_leaders():
    """Import company leadership from the markdown hierarchy file."""
    from importer import import_company_leaders_from_markdown
    result = import_company_leaders_from_markdown()
    return result


# ─── Rescan ──────────────────────────────────────────────────

@app.post("/api/rescan")
def rescan():
    """Re-scan the photos directory and match photos to persons by name."""
    from importer import match_photos_to_persons
    result = match_photos_to_persons()
    return {"status": "ok", **result}


# ─── Seed tree ───────────────────────────────────────────────

@app.post("/api/departments/seed-tree")
def seed_tree():
    """Re-seed the department category tree from the predefined structure."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for idx, cat_data in enumerate(DEPT_CATEGORY_TREE):
                cur.execute(
                    "SELECT id FROM dept_categories WHERE name = %s",
                    (cat_data["name"],),
                )
                cat_row = cur.fetchone()
                if cat_row:
                    # Update sort_order
                    cur.execute(
                        "UPDATE dept_categories SET sort_order = %s WHERE id = %s",
                        (idx, cat_row["id"]),
                    )
                    cat_id = cat_row["id"]
                else:
                    cur.execute(
                        "INSERT INTO dept_categories (name, sort_order) VALUES (%s, %s)",
                        (cat_data["name"], idx),
                    )
                    cat_id = cur.lastrowid

                for dept_idx, dept_name in enumerate(cat_data["departments"]):
                    cur.execute(
                        "SELECT id FROM departments WHERE name = %s",
                        (dept_name,),
                    )
                    dept_row = cur.fetchone()
                    if dept_row:
                        cur.execute(
                            "UPDATE departments SET category_id = %s, sort_order = %s WHERE id = %s",
                            (cat_id, dept_idx, dept_row["id"]),
                        )
                    else:
                        cur.execute(
                            "INSERT INTO departments (name, category_id, sort_order) VALUES (%s, %s, %s)",
                            (dept_name, cat_id, dept_idx),
                        )
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


# ─── Meeting Endpoints ────────────────────────────────────────

def _parse_names(raw_text: str | None) -> list[str]:
    """Parse a delimited name list into cleaned individual items."""
    if not raw_text or not raw_text.strip():
        return []
    # Split by 顿号、中文逗号、英文逗号、换行
    parts = re.split(r'[、，,\n]+', raw_text.strip())
    return [p.strip() for p in parts if p.strip()]


def _dept_rank_map(conn, snapshot_rank: dict | None = None) -> dict[str, tuple]:
    """Return {dept_name: (cat_order, dept_order)} ranking.
    Uses a saved snapshot's ranking if provided, otherwise reads the current
    department tree ordering from the database."""
    if snapshot_rank is not None:
        return snapshot_rank["dept"]

    with conn.cursor() as cur:
        cur.execute("""
            SELECT d.name,
                   COALESCE(c.sort_order, 999) AS cat_order,
                   d.sort_order AS dept_order
            FROM departments d
            LEFT JOIN dept_categories c ON d.category_id = c.id
        """)
        rows = cur.fetchall()
    return {r["name"]: (r["cat_order"], r["dept_order"]) for r in rows}


def _load_snapshot_rank(conn, snapshot_id: int | None) -> dict | None:
    """Load a snapshot's ranking by id, or return None to use current tree order."""
    if not snapshot_id:
        return None
    with conn.cursor() as cur:
        cur.execute("SELECT data FROM dept_sort_snapshots WHERE id = %s", (snapshot_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="保存的部门排序记录不存在")
    return _parse_snapshot_rank(row["data"])


def _sort_departments(conn, dept_names: list[str], snapshot_rank: dict | None = None) -> list[str]:
    """Sort department names by (category order, department order).
    Uses a saved snapshot's ranking when provided, otherwise the current tree order.
    Unknown names are appended at the end preserving their original relative order.
    """
    if not dept_names:
        return []
    rank = _dept_rank_map(conn, snapshot_rank)

    def key(name: str):
        return rank.get(name, (999999, 999999))

    # Stable sort: unknown names keep input order and land at the end.
    return sorted(dept_names, key=key)


def _sort_persons(conn, person_names: list[str], snapshot_rank: dict | None = None) -> list[dict]:
    """Sort persons by position_level ASC (lower = higher rank),
    then by department order (snapshot or current tree),
    then by per-group sort_order (configured in 人员管理) as the final tie-break.
    Returns list of {name, department, position_title, position_level}.
    """
    if not person_names:
        return []

    rank = _dept_rank_map(conn, snapshot_rank)
    placeholders = ','.join(['%s'] * len(person_names))

    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT p.name, p.department, p.position_title, p.position_level, p.sort_order
            FROM persons p
            WHERE p.name IN ({placeholders})
        """, person_names)
        rows = cur.fetchall()

    # Deduplicate by name, keeping the highest-ranked (lowest position_level) occurrence.
    best: dict[str, dict] = {}
    for row in rows:
        name = row["name"]
        lvl = row["position_level"] if row["position_level"] is not None else 99
        if name not in best or lvl < best[name]["_lvl"]:
            best[name] = {**row, "_lvl": lvl}
    matched = list(best.values())
    matched_names = set(best.keys())

    unmatched = [n for n in person_names if n not in matched_names]

    def key(row: dict):
        lvl = row["position_level"] if row["position_level"] is not None else 99
        so = row.get("sort_order")
        sort_key = so if so is not None else 999999
        # name as final tie-break keeps the order fully deterministic
        # (sort_order can collide across person_type groups within a department)
        return (lvl, rank.get(row.get("department") or "", (999999, 999999)), sort_key, row.get("name") or "")

    matched.sort(key=key)

    result = []
    for row in matched:
        level = row["position_level"]
        result.append({
            "name": row["name"],
            "department": row["department"],
            "position_title": row["position_title"],
            "position_level": float(level) if level is not None else None,
        })
    for name in unmatched:
        result.append({
            "name": name,
            "department": "",
            "position_title": "",
            "position_level": None,
        })

    return result


def _derive_departments_from_persons(conn, sorted_persons: list[dict], snapshot_rank: dict | None = None) -> list[str]:
    """Extract unique, non-empty departments from sorted persons,
    then sort by department tree order (snapshot or current)."""
    dept_set = {p["department"] for p in sorted_persons if p["department"]}
    if not dept_set:
        return []
    dept_list = list(dept_set)
    return _sort_departments(conn, dept_list, snapshot_rank)


@app.post("/api/meetings")
def create_meeting(req: MeetingCreate):
    """Create a meeting with auto-sorted department and person rosters."""
    conn = get_connection()
    try:
        # Parse inputs
        dept_names = _parse_names(req.input_departments)
        person_names = _parse_names(req.input_persons)

        if not dept_names and not person_names:
            raise HTTPException(status_code=400, detail="参会部门名单和人员名单不能同时为空")

        # Optional: sort by a saved department-sort snapshot instead of current tree order
        snapshot_rank = _load_snapshot_rank(conn, req.sort_snapshot_id)

        # Sort persons first (may be needed to derive departments)
        sorted_persons = _sort_persons(conn, person_names, snapshot_rank)

        # Sort departments: use explicit input if provided, else derive from matched persons
        if dept_names:
            sorted_depts = _sort_departments(conn, dept_names, snapshot_rank)
        else:
            sorted_depts = _derive_departments_from_persons(conn, sorted_persons, snapshot_rank)

        sorted_depts_json = json.dumps(sorted_depts, ensure_ascii=False)
        sorted_persons_json = json.dumps(sorted_persons, ensure_ascii=False)

        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO meetings
                   (name, input_persons, input_departments, sorted_persons, sorted_departments, sort_snapshot_id)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (req.name, req.input_persons or "", req.input_departments or "",
                 sorted_persons_json, sorted_depts_json, req.sort_snapshot_id),
            )
            new_id = cur.lastrowid
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT * FROM meetings WHERE id = %s", (new_id,))
            return cur.fetchone()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.get("/api/meetings")
def list_meetings(
    search: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    department: str = Query(None),
    person: str = Query(None),
):
    """List meetings ordered by creation time descending, with optional filters."""
    conn = get_connection()
    try:
        conditions = []
        params = []

        if search:
            conditions.append("name LIKE %s")
            params.append(f"%{search}%")

        if date_from:
            conditions.append("DATE(created_at) >= %s")
            params.append(date_from)

        if date_to:
            conditions.append("DATE(created_at) <= %s")
            params.append(date_to)

        if department:
            conditions.append("(input_departments LIKE %s OR sorted_departments LIKE %s)")
            params.append(f"%{department}%")
            params.append(f"%{department}%")

        if person:
            conditions.append("(input_persons LIKE %s OR sorted_persons LIKE %s)")
            params.append(f"%{person}%")
            params.append(f"%{person}%")

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM meetings {where_clause} ORDER BY created_at DESC",
                params,
            )
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/api/meetings/{meeting_id}")
def get_meeting(meeting_id: int):
    """Get a single meeting by ID."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM meetings WHERE id = %s", (meeting_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Meeting not found")
            return row
    finally:
        conn.close()


@app.put("/api/meetings/{meeting_id}")
def update_meeting(meeting_id: int, req: MeetingUpdate):
    """Update a meeting's name and/or input lists. Re-sorts if inputs changed."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM meetings WHERE id = %s", (meeting_id,))
            meeting = cur.fetchone()
            if not meeting:
                raise HTTPException(status_code=404, detail="Meeting not found")

        # Determine new values
        new_name = req.name if req.name is not None else meeting['name']
        new_input_persons = req.input_persons if req.input_persons is not None else meeting.get('input_persons')
        new_input_departments = req.input_departments if req.input_departments is not None else meeting.get('input_departments')
        # sort_snapshot_id: use model_fields_set so an explicit null clears the snapshot
        if "sort_snapshot_id" in req.model_fields_set:
            new_sort_snapshot_id = req.sort_snapshot_id
        else:
            new_sort_snapshot_id = meeting.get('sort_snapshot_id')

        # Re-sort
        dept_names = _parse_names(new_input_departments)
        person_names = _parse_names(new_input_persons)

        if not dept_names and not person_names:
            raise HTTPException(status_code=400, detail="参会部门名单和人员名单不能同时为空")

        snapshot_rank = _load_snapshot_rank(conn, new_sort_snapshot_id)

        sorted_persons = _sort_persons(conn, person_names, snapshot_rank)
        if dept_names:
            sorted_depts = _sort_departments(conn, dept_names, snapshot_rank)
        else:
            sorted_depts = _derive_departments_from_persons(conn, sorted_persons, snapshot_rank)

        sorted_depts_json = json.dumps(sorted_depts, ensure_ascii=False)
        sorted_persons_json = json.dumps(sorted_persons, ensure_ascii=False)

        with conn.cursor() as cur:
            cur.execute(
                """UPDATE meetings SET name=%s, input_persons=%s, input_departments=%s,
                   sorted_persons=%s, sorted_departments=%s, sort_snapshot_id=%s WHERE id=%s""",
                (new_name, new_input_persons or "", new_input_departments or "",
                 sorted_persons_json, sorted_depts_json, new_sort_snapshot_id, meeting_id),
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT * FROM meetings WHERE id = %s", (meeting_id,))
            return cur.fetchone()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.delete("/api/meetings/{meeting_id}")
def delete_meeting(meeting_id: int):
    """Delete a meeting."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM meetings WHERE id = %s", (meeting_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Meeting not found")
            cur.execute("DELETE FROM meetings WHERE id = %s", (meeting_id,))
        conn.commit()
        return {"status": "ok"}
    finally:
        conn.close()


@app.post("/api/meetings/{meeting_id}/resort")
def resort_meeting(meeting_id: int, req: MeetingResort | None = None):
    """Re-run sorting for an existing meeting and update the record.
    If req.sort_snapshot_id is provided it is used as the sorting basis,
    otherwise the meeting's stored sort_snapshot_id is reused."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM meetings WHERE id = %s", (meeting_id,))
            meeting = cur.fetchone()
            if not meeting:
                raise HTTPException(status_code=404, detail="Meeting not found")

        # Determine the sorting basis
        if req is not None and req.sort_snapshot_id is not None:
            snapshot_id = req.sort_snapshot_id
        else:
            snapshot_id = meeting.get('sort_snapshot_id')

        snapshot_rank = _load_snapshot_rank(conn, snapshot_id)

        # Parse and re-sort
        dept_names = _parse_names(meeting.get('input_departments'))
        person_names = _parse_names(meeting.get('input_persons'))

        if not dept_names and not person_names:
            raise HTTPException(status_code=400, detail="参会部门名单和人员名单不能同时为空")

        sorted_persons = _sort_persons(conn, person_names, snapshot_rank)

        if dept_names:
            sorted_depts = _sort_departments(conn, dept_names, snapshot_rank)
        else:
            sorted_depts = _derive_departments_from_persons(conn, sorted_persons, snapshot_rank)

        sorted_depts_json = json.dumps(sorted_depts, ensure_ascii=False)
        sorted_persons_json = json.dumps(sorted_persons, ensure_ascii=False)

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE meetings SET sorted_persons = %s, sorted_departments = %s, sort_snapshot_id = %s WHERE id = %s",
                (sorted_persons_json, sorted_depts_json, snapshot_id, meeting_id),
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT * FROM meetings WHERE id = %s", (meeting_id,))
            return cur.fetchone()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


# ─── Main ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10023)
