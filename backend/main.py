"""FastAPI application - Face Recognition Assistant backend."""

import json
import os
import random
import re
import asyncio
import time
from contextlib import asynccontextmanager
from difflib import SequenceMatcher
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException, Request, Depends, Header, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from database import init_database, get_connection, normalize_dept_name, DEPT_CATEGORY_TREE
from config_loader import load_config
from api_keys import (
    init_api_tables, create_app, list_apps, get_app_by_id, update_app,
    rotate_secret, delete_app, log_call, get_logs, cleanup_expired_logs,
    get_app_by_app_id, LOG_RETENTION_DAYS, LOG_MAX_TEXT,
)
from api_auth import verify_ext_signature
from auth import (
    init_auth_tables, seed_admin_user, do_login, do_change_password,
    create_session, destroy_session, get_session_user,
    authz_allow, get_current_user, require_admin_or_token,
)
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
    init_api_tables()
    init_auth_tables()
    seed_admin_user()
    print(f"[Startup] Database initialized.")

    # 定时清理任务：调用日志仅保留 7 天，每小时自动清理一次
    cleanup_task = asyncio.create_task(_log_cleanup_loop())
    print(f"[Startup] API 调用日志清理任务已启动（保留 {LOG_RETENTION_DAYS} 天，每小时检查）")
    yield
    cleanup_task.cancel()


async def _log_cleanup_loop():
    """定时清理超期调用日志（默认每小时）。"""
    while True:
        try:
            deleted = await asyncio.to_thread(cleanup_expired_logs, LOG_RETENTION_DAYS)
            if deleted:
                print(f"[Cleanup] 已清理 {deleted} 条超过 {LOG_RETENTION_DAYS} 天的调用日志")
        except Exception as e:
            print(f"[Cleanup] 清理调用日志失败: {e}")
        await asyncio.sleep(3600)


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
                SELECT p.department
                FROM persons p
                LEFT JOIN departments d ON p.department = d.name
                LEFT JOIN dept_categories c ON d.category_id = c.id
                GROUP BY p.department
                ORDER BY MIN(COALESCE(c.sort_order, 999)), MIN(COALESCE(d.sort_order, 999)), p.department
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


FUZZY_DEPT_THRESHOLD = 0.5


def _fuzzy_match_department(name: str, candidates: list[str],
                            threshold: float = FUZZY_DEPT_THRESHOLD) -> str | None:
    """Return the candidate department most similar to `name`, or None.

    Rules (kept consistent with the import module's matching):
      - substring containment (name in candidate, or candidate in name)
        counts as a high-confidence match (base score 0.85);
      - otherwise use difflib sequence similarity (SequenceMatcher.ratio).
    Ties are broken by higher sequence ratio, then by shorter name.
    """
    if not name or not candidates:
        return None
    scored: list[tuple] = []
    for dept in candidates:
        ratio = SequenceMatcher(None, name, dept).ratio()
        if name in dept or dept in name:
            score = max(0.85, ratio)
        else:
            score = ratio
        if score >= threshold:
            scored.append((score, ratio, -len(dept), dept))
    if not scored:
        return None
    scored.sort(reverse=True)
    return scored[0][3]


def _sort_departments(conn, dept_names: list[str], snapshot_rank: dict | None = None) -> list[str]:
    """Sort department names by (category order, department order).
    Uses a saved snapshot's ranking when provided, otherwise the current tree order.

    Each input name is first fuzzy-matched against the known departments and
    resolved to the best match (e.g. 「企发部」→「企发部/数智办」); the resolved
    canonical names are used for ranking. Names that match nothing are kept as-is
    and appended at the end preserving their original relative order.
    """
    if not dept_names:
        return []
    rank = _dept_rank_map(conn, snapshot_rank)
    candidates = list(rank.keys())

    resolved: list[str] = []
    seen: set[str] = set()
    for raw in dept_names:
        name = raw.strip()
        if not name:
            continue
        if name in rank:
            canonical = name
        else:
            canonical = _fuzzy_match_department(name, candidates) or name
        # Deduplicate: several inputs may resolve to the same department.
        if canonical in seen:
            continue
        seen.add(canonical)
        resolved.append(canonical)

    def key(name: str):
        return rank.get(name, (999999, 999999))

    # Stable sort: unknown names keep input order and land at the end.
    return sorted(resolved, key=key)


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


# ─── 外部接口：签名验证 + 调用日志 ──────────────────

# 管理令牌：来自配置 app.admin_token 或环境变量 ADMIN_TOKEN；未配置时管理接口禁用
_admin_token = (
    os.environ.get("ADMIN_TOKEN")
    or load_config().get("app", {}).get("admin_token", "")
)

# 内部接口访问令牌：nginx :80 代理 /api/ 时携带，用于区分"经前端访问"；
# 服务器内部直连（127.0.0.1）不受限。
_internal_token = load_config().get("app", {}).get("internal_token", "")


def _check_admin(authorization: str = Header(default="", alias="X-Admin-Token")) -> None:
    """管理接口鉴权（系统令牌方式，兼容保留）。"""
    if not _admin_token:
        raise HTTPException(status_code=503, detail="管理令牌未配置（请设置 app.admin_token 或 ADMIN_TOKEN）")
    if authorization != _admin_token:
        raise HTTPException(status_code=401, detail="管理令牌无效")


ext_router = APIRouter(prefix="/api/ea", tags=["外部接口"])
admin_router = APIRouter(prefix="/api", tags=["密钥管理"])


class AppCreateRequest(BaseModel):
    app_name: str
    description: str | None = None
    expires_at: str | None = None  # ISO 格式，可选


class AppUpdateRequest(BaseModel):
    app_name: str | None = None
    status: int | None = None  # 1=启用 0=禁用
    description: str | None = None


# ── 外部示例接口（受签名保护）────────────────────
@ext_router.post("/echo")
async def ext_echo(request: Request, app_id: str = Depends(verify_ext_signature)):
    """签名保护示例：回显请求体。"""
    body = await request.json()
    return {"code": 0, "message": "ok", "data": {"app_id": app_id, "echo": body}}


@ext_router.get("/persons")
async def ext_persons(request: Request, app_id: str = Depends(verify_ext_signature),
                      limit: int = Query(5, ge=1, le=50)):
    """签名保护示例：查询人员列表（数据子集）。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, department, position, filename FROM persons ORDER BY id LIMIT %s",
                (int(limit),),
            )
            items = cur.fetchall()
            for r in items:
                r["photo_url"] = f"/api/photo/{r['filename']}"
            return {"code": 0, "message": "ok", "data": {"app_id": app_id, "items": items}}
    finally:
        conn.close()


# ── 智能体专用：部门排序存档查询（供"部门排序选择"）──
@ext_router.get("/dept-snapshots")
async def ext_dept_snapshots(request: Request, app_id: str = Depends(verify_ext_signature)):
    """查询可用部门排序存档列表（选择 sort_snapshot_id 用）。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, note, created_at FROM dept_sort_snapshots ORDER BY id DESC"
            )
            rows = cur.fetchall()
            for r in rows:
                r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            return {"code": 0, "message": "ok", "data": {"app_id": app_id, "items": rows}}
    finally:
        conn.close()


# ── 智能体专用：部门名列表（构造部门名单用）──────────
@ext_router.get("/departments")
async def ext_departments(request: Request, app_id: str = Depends(verify_ext_signature)):
    """查询全部部门名（树序）。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.department
                FROM persons p
                LEFT JOIN departments d ON p.department = d.name
                LEFT JOIN dept_categories c ON d.category_id = c.id
                GROUP BY p.department
                ORDER BY MIN(COALESCE(c.sort_order, 999)), MIN(COALESCE(d.sort_order, 999)), p.department
            """)
            names = [row["department"] for row in cur.fetchall()]
            return {"code": 0, "message": "ok", "data": {"app_id": app_id, "items": names}}
    finally:
        conn.close()


# ── 智能体专用：名单排序（人员名单 + 部门名单 + 排序选择）──
class ExtMeetingSortRequest(BaseModel):
    name: str | None = None                       # 会议名称（可选）
    input_persons: str | None = None              # 人员名单：姓名，支持换行/逗号/顿号分隔
    input_departments: str | None = None          # 部门名单：部门名，支持换行/逗号/顿号分隔
    sort_snapshot_id: int | None = None           # 部门排序存档ID（部门排序选择，来自 /dept-snapshots）


@ext_router.post("/meetings/sort")
async def ext_meeting_sort(request: Request, req: ExtMeetingSortRequest,
                           app_id: str = Depends(verify_ext_signature)):
    """智能体接口：输入人员名单/部门名单与排序选择，返回排序后名单。

    排序规则: 职位等级 → 部门树顺序（或所选存档） → 组内顺序。
    """
    conn = get_connection()
    try:
        dept_names = _parse_names(req.input_departments)
        person_names = _parse_names(req.input_persons)
        if not dept_names and not person_names:
            raise HTTPException(status_code=400, detail="input_departments 与 input_persons 不能同时为空")

        snapshot_rank = _load_snapshot_rank(conn, req.sort_snapshot_id)
        sorted_persons = _sort_persons(conn, person_names, snapshot_rank)
        if dept_names:
            sorted_depts = _sort_departments(conn, dept_names, snapshot_rank)
        else:
            sorted_depts = _derive_departments_from_persons(conn, sorted_persons, snapshot_rank)

        # 落库存档（与内部 /api/meetings 一致），便于追溯
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO meetings
                   (name, input_persons, input_departments, sorted_persons, sorted_departments, sort_snapshot_id)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (req.name or "外部调用", req.input_persons or "", req.input_departments or "",
                 json.dumps(sorted_persons, ensure_ascii=False),
                 json.dumps(sorted_depts, ensure_ascii=False), req.sort_snapshot_id),
            )
            new_id = cur.lastrowid
        conn.commit()

        return {
            "code": 0,
            "message": "ok",
            "data": {
                "app_id": app_id,
                "meeting_id": new_id,
                "sort_snapshot_id": req.sort_snapshot_id,
                "sorted_departments": sorted_depts,
                "sorted_persons": sorted_persons,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


# ── 密钥管理（管理员）─────────────────────────────
@admin_router.post("/app-keys", dependencies=[Depends(require_admin_or_token)])
def api_create_app(req: AppCreateRequest):
    """创建外部应用，返回 app_id + app_secret（仅此一次展示，请妥善保存）。"""
    if not req.app_name.strip():
        raise HTTPException(status_code=400, detail="app_name 不能为空")
    return create_app(req.app_name.strip(), req.description, req.expires_at)


@admin_router.get("/app-keys", dependencies=[Depends(require_admin_or_token)])
def api_list_apps():
    """列出全部外部应用。"""
    return {"code": 0, "data": list_apps()}


@admin_router.get("/app-keys/{app_id}", dependencies=[Depends(require_admin_or_token)])
def api_get_app(app_id: int):
    """查询单个外部应用。"""
    app = get_app_by_id(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")
    app.pop("secret_encrypted", None); app.pop("secret_plain", None)
    return {"code": 0, "data": app}


@admin_router.put("/app-keys/{app_id}", dependencies=[Depends(require_admin_or_token)])
def api_update_app(app_id: int, req: AppUpdateRequest):
    """更新应用（名称/状态/备注）。"""
    if not update_app(app_id, req.app_name, req.status, req.description):
        raise HTTPException(status_code=404, detail="应用不存在或无更新内容")
    return {"code": 0, "message": "更新成功"}


@admin_router.post("/app-keys/{app_id}/rotate", dependencies=[Depends(require_admin_or_token)])
def api_rotate_app(app_id: int):
    """轮换密钥：旧密钥立即失效，返回新密钥（仅此一次展示）。"""
    secret = rotate_secret(app_id)
    if not secret:
        raise HTTPException(status_code=404, detail="应用不存在")
    return {"code": 0, "message": "密钥已轮换，旧密钥已失效", "app_secret": secret}


@admin_router.delete("/app-keys/{app_id}", dependencies=[Depends(require_admin_or_token)])
def api_delete_app(app_id: int):
    """删除应用及其全部调用日志。"""
    if not delete_app(app_id):
        raise HTTPException(status_code=404, detail="应用不存在")
    return {"code": 0, "message": "已删除"}


@admin_router.get("/app-keys/{app_id}/logs", dependencies=[Depends(require_admin_or_token)])
def api_app_logs(app_id: int, days: int = Query(LOG_RETENTION_DAYS, ge=1, le=30),
                 limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    """查询某应用最近 N 天（默认 7 天）的调用日志。"""
    result = get_logs(app_id, days=days, limit=limit, offset=offset)
    if result is None:
        raise HTTPException(status_code=404, detail="应用不存在")
    return {"code": 0, "data": result}


@admin_router.post("/admin/logs/cleanup", dependencies=[Depends(require_admin_or_token)])
def api_cleanup_logs(days: int = Query(LOG_RETENTION_DAYS, ge=1, le=30)):
    """手动触发清理：删除超过保留期的调用日志。"""
    deleted = cleanup_expired_logs(days)
    return {"code": 0, "message": f"已清理 {deleted} 条超过 {days} 天的调用日志"}


app.include_router(ext_router)
# 注意: admin_router 的 include 在其全部路由定义完成后（见下方用户管理代码之后）


# ── 登录鉴权接口 ─────────────────────────────────────
auth_router = APIRouter(prefix="/api/auth", tags=["登录鉴权"])


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@auth_router.post("/login")
async def api_login(req: LoginRequest, request: Request):
    """登录：成功返回 token 与用户信息（含角色）。"""
    # 真实调用方 IP（nginx 已设置 X-Forwarded-For；直连时用 client.host）
    xff = request.headers.get("X-Forwarded-For")
    ip = (xff.split(",")[0].strip()[:45] if xff
          else (request.client.host if (request.client and request.client.host) else "-"))
    result = do_login(req.username, req.password, ip)
    return {"code": 0, "message": "ok", "data": result}


@auth_router.post("/logout")
def api_logout(request: Request):
    """登出：销毁当前会话。"""
    token = _bearer_token(request)
    destroy_session(token)
    return {"code": 0, "message": "已退出登录"}


@auth_router.get("/me")
def api_me(request: Request):
    """当前登录用户信息。"""
    user = get_current_user(request)
    return {"code": 0, "data": user}


@auth_router.post("/change-password")
def api_change_password(req: ChangePasswordRequest, request: Request):
    """修改当前登录账号密码。"""
    user = get_current_user(request)
    do_change_password(user["username"], req.old_password, req.new_password)
    destroy_session(_bearer_token(request))
    return {"code": 0, "message": "密码已修改，请重新登录"}


def _bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    return auth[7:].strip() if auth.startswith("Bearer ") else ""


# ── 用户管理（仅管理员）──────────────────────────────
class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "user"  # admin/user
    display_name: str | None = None


class UserUpdateRequest(BaseModel):
    role: str | None = None
    display_name: str | None = None
    status: int | None = None  # 1=启用 0=禁用
    password: str | None = None  # 重置密码


@admin_router.post("/auth/users", dependencies=[Depends(require_admin_or_token)])
def api_create_user(req: UserCreateRequest):
    """创建用户（管理员）。"""
    from auth import hash_password
    username = (req.username or "").strip()
    if not username or not req.password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="密码至少 8 位")
    if req.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="角色仅支持 admin/user")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE username = %s", (username,)
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="用户名已存在")
            cur.execute(
                "INSERT INTO users (username, password_hash, role, display_name) "
                "VALUES (%s, %s, %s, %s)",
                (username, hash_password(req.password), req.role, req.display_name),
            )
        conn.commit()
        return {"code": 0, "message": "用户已创建", "id": cur.lastrowid}
    finally:
        conn.close()


@admin_router.get("/auth/users", dependencies=[Depends(require_admin_or_token)])
def api_list_users():
    """用户列表（管理员）。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, role, display_name, status, last_login_at, created_at "
                "FROM users ORDER BY id"
            )
            rows = cur.fetchall()
            for r in rows:
                if r.get("last_login_at"):
                    r["last_login_at"] = r["last_login_at"].strftime("%Y-%m-%d %H:%M:%S")
                if r.get("created_at"):
                    r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            return {"code": 0, "data": rows}
    finally:
        conn.close()


@admin_router.put("/auth/users/{user_id}", dependencies=[Depends(require_admin_or_token)])
def api_update_user(user_id: int, req: UserUpdateRequest):
    """更新用户（角色/显示名/状态/重置密码，管理员）。"""
    from auth import hash_password
    sets, params = [], []
    if req.role is not None:
        if req.role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="角色仅支持 admin/user")
        sets.append("role = %s"); params.append(req.role)
    if req.display_name is not None:
        sets.append("display_name = %s"); params.append(req.display_name)
    if req.status is not None:
        sets.append("status = %s"); params.append(int(req.status))
    if req.password:
        if len(req.password) < 8:
            raise HTTPException(status_code=400, detail="密码至少 8 位")
        sets.append("password_hash = %s"); params.append(hash_password(req.password))
    if not sets:
        raise HTTPException(status_code=400, detail="无更新内容")
    params.append(user_id)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE users SET {', '.join(sets)} WHERE id = %s", params
            )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="用户不存在")
        return {"code": 0, "message": "用户已更新"}
    finally:
        conn.close()


@admin_router.delete("/auth/users/{user_id}", dependencies=[Depends(require_admin_or_token)])
def api_delete_user(user_id: int):
    """删除用户（管理员）。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="用户不存在")
            if row["role"] == "admin":
                raise HTTPException(status_code=400, detail="不能删除管理员账号")
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        return {"code": 0, "message": "用户已删除"}
    finally:
        conn.close()


app.include_router(admin_router)
app.include_router(auth_router)


# ── 中间件 0：外部接口请求体解密（AES-GCM）────────────
# 必须在路由前完成：FastAPI 在依赖运行前就解析请求体，
# 因此 X-Encrypt=1 的解密放在中间件层，并把原始密文暂存供签名校验。
@app.middleware("http")
async def ext_body_decrypt(request: Request, call_next):
    if request.url.path.startswith("/api/ea/") and request.headers.get("X-Encrypt") == "1":
        raw = await request.body()
        request.state.raw_body = raw
        try:
            app = get_app_by_app_id(request.headers.get("X-App-Id", ""))
            if app:
                from security import decrypt_body
                request._body = await asyncio.to_thread(decrypt_body, raw.decode(), app["secret_plain"])
        except Exception:
            request._body = raw  # 解密失败：保持原文，由签名依赖统一报 401
    return await call_next(request)


# ── 中间件 1：内部接口访问控制 ───────────────────────
# 规则: /api/*（除 /api/ea/ 与 /api/auth/ 外）仅允许:
#   ① 经 nginx :80 代理（携带 X-Internal-Access 内网标记头）——即前端应用访问
#   ② 服务器内部直连（127.0.0.1 / ::1，无标记头）
# 外部访问只能走 nginx :10025 的 /api/ea/**（签名保护）。
@app.middleware("http")
async def internal_access_control(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and not path.startswith("/api/ea/") \
            and not path.startswith("/api/auth/"):
        header_ok = _internal_token and request.headers.get("X-Internal-Access") == _internal_token
        client = request.client.host if request.client else ""
        local_ok = client in ("127.0.0.1", "::1")
        if not header_ok and not local_ok:
            return JSONResponse(status_code=403, content={"detail": "禁止外部直接访问内部接口"})
    return await call_next(request)


# ── 中间件 2：分权分域（RBAC）───────────────────────
# 规则: 内部 /api/* 下所有增删改操作仅限 admin（游客白名单除外）；
#       密钥管理接口允许 admin 会话或 X-Admin-Token。
@app.middleware("http")
async def rbac_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and not path.startswith("/api/ea/"):
        try:
            authz_allow(request.method, path, request)
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    return await call_next(request)


def _caller_ip(request: Request) -> str:
    """取真实调用方 IP：优先 X-Forwarded-For（nginx 已设置），其次直连地址。"""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()[:45]
    return request.client.host if (request.client and request.client.host) else "-"


# ── 外部接口调用日志中间件 ──────────────────────────
@app.middleware("http")
async def ext_call_logging(request: Request, call_next):
    """记录外部接口调用：IP / 路径 / 状态码 / 请求参数 / 返回结果。
    仅记录携带 X-App-Id 的请求（含签名失败的请求），不影响内部接口。
    """
    app_id_header = request.headers.get("X-App-Id")
    is_ext = request.url.path.startswith("/ext/")
    if not app_id_header and not is_ext:
        return await call_next(request)

    start = time.perf_counter()
    try:
        body_bytes = await request.body()
    except Exception:
        body_bytes = b""
    request_params = {
        "query": dict(request.query_params),
        "body": body_bytes.decode("utf-8", errors="replace")[:LOG_MAX_TEXT],
    }

    try:
        response = await call_next(request)
    except Exception:
        # 未捕获异常：记录 500 后继续抛出
        log_call(app_id_header or "-", _caller_ip(request),
                 request.method, request.url.path, 500, request_params, {"error": "internal_error"},
                 int((time.perf_counter() - start) * 1000))
        raise

    # 读取响应体（JSON 场景直接可用）
    resp_body = b""
    try:
        if hasattr(response, "body"):
            resp_body = response.body
        else:
            resp_body = b"".join([chunk async for chunk in response.body_iterator])
            response = JSONResponse(
                content=json.loads(resp_body.decode("utf-8", errors="replace") or "null")
                if resp_body else {},
                status_code=response.status_code,
                headers=dict(response.headers),
            )
    except Exception:
        pass

    duration_ms = int((time.perf_counter() - start) * 1000)
    log_call(
        app_id_header or "-",
        _caller_ip(request),
        request.method,
        request.url.path,
        response.status_code,
        request_params,
        resp_body.decode("utf-8", errors="replace")[:LOG_MAX_TEXT],
        duration_ms,
    )
    return response


# ─── Main ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    _cfg = load_config()
    _host = _cfg.get("server", {}).get("host", "0.0.0.0")
    _port = _cfg.get("server", {}).get("port", 10023)
    print(f"[Startup] Active config: {_cfg.get('app', {}).get('name', '会务助手')} "
          f"| server http://{_host}:{_port} | database={_cfg.get('database', {}).get('database')}")
    uvicorn.run(app, host=_host, port=_port)
