"""Pydantic models for API request/response."""

from typing import Optional
from pydantic import BaseModel


class Person(BaseModel):
    id: int
    name: str
    department: str
    position: str
    filename: str
    person_type: Optional[str] = None
    sort_order: Optional[int] = None
    position_title: Optional[str] = None
    position_level: Optional[float] = None
    managed_departments: Optional[str] = None
    managed_businesses: Optional[str] = None
    notes: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    created_at: Optional[str] = None


class PersonCreate(BaseModel):
    name: str
    department: str
    position: str
    filename: str
    person_type: Optional[str] = None
    sort_order: Optional[int] = None
    position_title: Optional[str] = None
    position_level: Optional[float] = None
    managed_departments: Optional[str] = None
    managed_businesses: Optional[str] = None
    notes: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class PersonUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    filename: Optional[str] = None
    person_type: Optional[str] = None
    sort_order: Optional[int] = None
    position_title: Optional[str] = None
    position_level: Optional[float] = None
    managed_departments: Optional[str] = None
    managed_businesses: Optional[str] = None
    notes: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class AnswerItem(BaseModel):
    id: int
    name: str


class TestCheckRequest(BaseModel):
    answers: list[AnswerItem]


class TestCheckResponse(BaseModel):
    total: int
    correct: int
    score: float
    details: list[dict]  # [{id, correct_name, user_answer, is_correct}]


class TestResultSave(BaseModel):
    total: int
    correct: int
    score: float


# ─── Department Category ────────────────────────────────────────

class DeptCategory(BaseModel):
    id: int
    name: str
    sort_order: int = 0
    created_at: Optional[str] = None


class DeptCategoryCreate(BaseModel):
    name: str
    sort_order: Optional[int] = None


class DeptCategoryUpdate(BaseModel):
    name: Optional[str] = None
    sort_order: Optional[int] = None


class ReorderItem(BaseModel):
    id: int
    sort_order: int


# ─── Department ─────────────────────────────────────────────────

class Department(BaseModel):
    id: int
    name: str
    category_id: Optional[int] = None
    sort_order: int = 0
    description: Optional[str] = None
    created_at: Optional[str] = None


class DepartmentCreate(BaseModel):
    name: str
    category_id: Optional[int] = None
    sort_order: int = 0
    description: Optional[str] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    sort_order: Optional[int] = None
    description: Optional[str] = None


# ─── Position Level & Person Type ──────────────────────────────────

# Canonical position level names and their numeric values
POSITION_LEVEL_MAP = {
    "二级正": 2.0,
    "二级副": 2.5,
    "资深总裁": 2.7,
    "资深副总裁": 2.7,
    "资深经理": 2.7,
    "三级正": 3.0,
    "三级副": 3.5,
    "督导": 3.7,
    "转非": 3.7,
}

# Backward-compatible aliases: old name → canonical name
POSITION_LEVEL_ALIASES = {
    "总经理": "三级正",
    "副总经理": "三级副",
    "副总经理(主持工作)": "三级副",
    "上海公司的总经理": "二级正",
    "上海公司的副总经理": "二级副",
}

# Valid person types
PERSON_TYPES = ["部门领导", "员工", "P1", "P2"]


def get_position_level(title: str) -> float:
    """Get position level from title. Returns 4.0 for unknown titles."""
    if not title:
        return 4.0
    title = title.strip()
    if title in POSITION_LEVEL_MAP:
        return POSITION_LEVEL_MAP[title]
    canonical = POSITION_LEVEL_ALIASES.get(title)
    if canonical and canonical in POSITION_LEVEL_MAP:
        return POSITION_LEVEL_MAP[canonical]
    return 4.0


# ─── Meeting ──────────────────────────────────────────────────────

class MeetingCreate(BaseModel):
    name: str
    input_persons: Optional[str] = None
    input_departments: Optional[str] = None
    sort_snapshot_id: Optional[int] = None


class MeetingUpdate(BaseModel):
    name: Optional[str] = None
    input_persons: Optional[str] = None
    input_departments: Optional[str] = None
    sort_snapshot_id: Optional[int] = None


class MeetingResort(BaseModel):
    sort_snapshot_id: Optional[int] = None


class Meeting(BaseModel):
    id: int
    name: str
    input_persons: Optional[str] = None
    input_departments: Optional[str] = None
    sorted_persons: Optional[str] = None
    sorted_departments: Optional[str] = None
    sort_snapshot_id: Optional[int] = None
    created_at: Optional[str] = None


# ─── Department Sort Snapshot (存档) ─────────────────────────────

class DeptSnapshotCreate(BaseModel):
    name: str
    note: Optional[str] = None


class DeptSnapshotUpdate(BaseModel):
    name: Optional[str] = None
    note: Optional[str] = None
    # 为 true 时用当前部门树的排序覆盖该存档的数据
    recapture: Optional[bool] = None


class DeptSnapshot(BaseModel):
    id: int
    name: str
    note: Optional[str] = None
    data: Optional[str] = None
    created_at: Optional[str] = None
