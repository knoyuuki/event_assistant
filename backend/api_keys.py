"""外部应用密钥管理模块。

- 表: api_apps（应用密钥）、api_call_logs（调用日志）
- CRUD: 创建/查询/更新/删除/轮换密钥
- 日志: 记录调用方 IP、接口路径、状态码、请求参数、返回结果
- 清理: 调用日志仅保留 7 天，超期由定时任务自动删除（也可手动触发）
"""

import json
import secrets
import time
from datetime import datetime, timedelta

import pymysql
from pymysql.cursors import DictCursor

from database import get_connection
from security import encrypt, decrypt

# ── 常量 ─────────────────────────────────────────────
LOG_RETENTION_DAYS = 7          # 调用日志保留天数
LOG_MAX_TEXT = 2000             # 日志中请求参数/返回结果的最大长度
SECRET_BYTES = 32               # 生成的密钥长度（urlsafe base64）

# ── 工具 ─────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now()


def _truncate(value, limit=LOG_MAX_TEXT) -> str:
    """截断超长内容，避免日志表膨胀。"""
    s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    if len(s) > limit:
        return s[:limit] + f"...(truncated {len(s) - limit} chars)"
    return s


def _generate_app_id() -> str:
    return "ea_" + secrets.token_hex(8)


def _generate_secret() -> str:
    return secrets.token_urlsafe(SECRET_BYTES)


# ── 建表 ─────────────────────────────────────────────
def init_api_tables():
    """创建密钥与调用日志表（幂等）。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS api_apps (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    app_id VARCHAR(64) NOT NULL UNIQUE COMMENT '外部应用标识',
                    app_name VARCHAR(100) NOT NULL COMMENT '应用名称',
                    secret_encrypted TEXT NOT NULL COMMENT 'Fernet 加密后的密钥',
                    status TINYINT NOT NULL DEFAULT 1 COMMENT '1=启用 0=禁用',
                    description VARCHAR(255) DEFAULT NULL COMMENT '备注',
                    expires_at DATETIME DEFAULT NULL COMMENT '过期时间，NULL=永不过期',
                    last_called_at DATETIME DEFAULT NULL COMMENT '最近调用时间',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS api_call_logs (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    app_id VARCHAR(64) NOT NULL COMMENT '应用标识',
                    caller_ip VARCHAR(45) NOT NULL COMMENT '调用方IP',
                    method VARCHAR(10) NOT NULL COMMENT 'HTTP方法',
                    path VARCHAR(255) NOT NULL COMMENT '接口路径',
                    status_code INT NOT NULL COMMENT '状态码',
                    request_params TEXT COMMENT '请求参数(JSON)',
                    response_result MEDIUMTEXT COMMENT '返回结果(JSON)',
                    duration_ms INT DEFAULT NULL COMMENT '耗时(毫秒)',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_log_app_created (app_id, created_at),
                    INDEX idx_log_created (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        conn.commit()
    finally:
        conn.close()


# ── 密钥 CRUD ────────────────────────────────────────
def create_app(app_name: str, description: str = None, expires_at: str = None) -> dict:
    """创建外部应用，返回 app_id 与明文密钥（仅此一次展示）。"""
    app_id = _generate_app_id()
    secret = _generate_secret()
    expires = None
    if expires_at:
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if expires.tzinfo:
            expires = expires.astimezone().replace(tzinfo=None)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO api_apps (app_id, app_name, secret_encrypted, description, expires_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                (app_id, app_name, encrypt(secret), description, expires),
            )
        conn.commit()
        return {
            "id": cur.lastrowid,
            "app_id": app_id,
            "app_secret": secret,
            "app_name": app_name,
            "description": description,
            "expires_at": expires.isoformat() if expires else None,
            "status": 1,
            "created_at": _now().isoformat(sep=" "),
        }
    finally:
        conn.close()


def list_apps() -> list[dict]:
    """列出全部应用（不含明文密钥）。"""
    conn = get_connection()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute(
                "SELECT id, app_id, app_name, status, description, expires_at, "
                "last_called_at, created_at, updated_at FROM api_apps ORDER BY id DESC"
            )
            rows = cur.fetchall()
            for r in rows:
                for k in ("expires_at", "last_called_at", "created_at", "updated_at"):
                    if r.get(k):
                        r[k] = r[k].strftime("%Y-%m-%d %H:%M:%S")
            return rows
    finally:
        conn.close()


def get_app_by_id(app_id: int) -> dict | None:
    return _get_app("id", app_id)


def get_app_by_app_id(app_key: str) -> dict | None:
    return _get_app("app_id", app_key)


def _get_app(field: str, value) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute(
                f"SELECT * FROM api_apps WHERE {field} = %s", (value,)
            )
            row = cur.fetchone()
            if row:
                row["secret_plain"] = decrypt(row["secret_encrypted"])
            return row
    finally:
        conn.close()


def update_app(app_id: int, app_name: str = None, status: int = None,
               description: str = None) -> bool:
    """更新应用信息（名称/状态/备注）。status: 1启用 0禁用。"""
    sets, params = [], []
    if app_name is not None:
        sets.append("app_name = %s"); params.append(app_name)
    if status is not None:
        sets.append("status = %s"); params.append(int(status))
    if description is not None:
        sets.append("description = %s"); params.append(description)
    if not sets:
        return False
    params.append(app_id)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE api_apps SET {', '.join(sets)} WHERE id = %s", params)
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def rotate_secret(app_id: int) -> str | None:
    """轮换密钥，返回新明文密钥。"""
    secret = _generate_secret()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE api_apps SET secret_encrypted = %s WHERE id = %s",
                (encrypt(secret), app_id),
            )
        conn.commit()
        return secret if cur.rowcount > 0 else None
    finally:
        conn.close()


def delete_app(app_id: int) -> bool:
    """删除应用（同时删除其调用日志）。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            app = get_app_by_id(app_id)
            if not app:
                return False
            cur.execute("DELETE FROM api_call_logs WHERE app_id = %s", (app["app_id"],))
            cur.execute("DELETE FROM api_apps WHERE id = %s", (app_id,))
        conn.commit()
        return True
    finally:
        conn.close()


# ── 调用日志 ─────────────────────────────────────────
def log_call(app_id: str, caller_ip: str, method: str, path: str, status_code: int,
             request_params: dict, response_result, duration_ms: int):
    """记录一次外部接口调用。"""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO api_call_logs (app_id, caller_ip, method, path, status_code, "
                    "request_params, response_result, duration_ms) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (app_id, caller_ip[:45], method[:10], path[:255], int(status_code),
                     _truncate(request_params), _truncate(response_result), int(duration_ms)),
                )
                cur.execute(
                    "UPDATE api_apps SET last_called_at = %s WHERE app_id = %s",
                    (_now(), app_id),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:  # 日志失败不影响业务
        print(f"[ApiLog] 写入调用日志失败: {e}")


def get_logs(app_id: int, days: int = LOG_RETENTION_DAYS, limit: int = 50, offset: int = 0) -> dict:
    """查询某应用最近 N 天（默认 7 天）的调用日志。"""
    app = get_app_by_id(app_id)
    if not app:
        return None
    since = _now() - timedelta(days=days)
    conn = get_connection()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute(
                "SELECT id, caller_ip, method, path, status_code, request_params, "
                "response_result, duration_ms, created_at FROM api_call_logs "
                "WHERE app_id = %s AND created_at >= %s "
                "ORDER BY id DESC LIMIT %s OFFSET %s",
                (app["app_id"], since, int(limit), int(offset)),
            )
            rows = cur.fetchall()
            for r in rows:
                r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM api_call_logs WHERE app_id = %s AND created_at >= %s",
                (app["app_id"], since),
            )
            total = cur.fetchone()["cnt"]
        return {"app_id": app["app_id"], "days": days, "total": total,
                "limit": limit, "offset": offset, "logs": rows}
    finally:
        conn.close()


def cleanup_expired_logs(days: int = LOG_RETENTION_DAYS) -> int:
    """删除超过保留期的调用日志，返回删除条数。"""
    cutoff = _now() - timedelta(days=days)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM api_call_logs WHERE created_at < %s", (cutoff,)
            )
            deleted = cur.rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()
