"""登录鉴权与分权分域（RBAC）。

安全设计:
- 密码: PBKDF2-HMAC-SHA256（60 万次迭代 + 16 字节随机盐），数据库仅存哈希
- 会话: 登录成功发放随机 token，存 Redis（默认 24h 过期）
- 防爆破: 同一账号失败 5 次锁定 15 分钟；同一 IP 失败 20 次限流 15 分钟
- 防遍历: 用户名不存在与密码错误返回同一提示，不暴露账号是否存在
- 防注入: 全部参数化查询
- 分权: role=admin 可管理（增删改），role=user 仅浏览/会议排序
"""

import hashlib
import os
import secrets
import uuid
from datetime import datetime

import pymysql
from pymysql.cursors import DictCursor
from fastapi import Request, HTTPException

from database import get_connection
from config_loader import load_config
import redis_client

# ── 常量 ─────────────────────────────────────────────
PBKDF2_ITERATIONS = 600_000
SESSION_TTL = 24 * 3600            # 会话有效期 24h
LOCKOUT_THRESHOLD = 5              # 失败次数阈值
LOCKOUT_SECONDS = 15 * 60          # 锁定时长 15 分钟
IP_THRESHOLD = 20                  # 单 IP 失败次数阈值
IP_WINDOW_SECONDS = 15 * 60
SESSION_PREFIX = "ea:sess:"
FAIL_PREFIX = "ea:login_fail:"
LOCK_PREFIX = "ea:login_lock:"
IP_FAIL_PREFIX = "ea:login_fail_ip:"

_admin_token = (
    os.environ.get("ADMIN_TOKEN")
    or load_config().get("app", {}).get("admin_token", "")
)


# ── 密码哈希 ─────────────────────────────────────────
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return secrets.compare_digest(digest.hex(), hash_hex)
    except Exception:
        return False


# ── 建表 ─────────────────────────────────────────────
def init_auth_tables():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE COMMENT '登录名',
                    password_hash VARCHAR(255) NOT NULL COMMENT 'PBKDF2哈希',
                    role VARCHAR(20) NOT NULL DEFAULT 'user' COMMENT 'admin/user',
                    display_name VARCHAR(100) DEFAULT NULL COMMENT '显示名',
                    status TINYINT NOT NULL DEFAULT 1 COMMENT '1=启用 0=禁用',
                    last_login_at DATETIME DEFAULT NULL COMMENT '最近登录时间',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        conn.commit()
    finally:
        conn.close()


def seed_admin_user():
    """首次启动时若无任何用户，创建 admin 账号。

    密码来源: 配置 app.admin_initial_password / 环境变量 ADMIN_INIT_PASSWORD；
    未设置则随机生成并写入 config/admin_initial_password.txt（gitignored 目录）。
    """
    conn = get_connection()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM users")
            if cur.fetchone()["cnt"] > 0:
                return
    finally:
        conn.close()

    password = (
        os.environ.get("ADMIN_INIT_PASSWORD")
        or load_config().get("app", {}).get("admin_initial_password", "")
    )
    if not password:
        password = secrets.token_urlsafe(12)
        config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
        try:
            with open(os.path.join(config_dir, "admin_initial_password.txt"), "w") as f:
                f.write(f"username: admin\npassword: {password}\n")
        except OSError as e:
            print(f"[Auth] 无法写入初始密码文件: {e}")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, role, display_name) "
                "VALUES (%s, %s, 'admin', '系统管理员')",
                ("admin", hash_password(password)),
            )
        conn.commit()
        print(f"[Auth] 已创建初始管理员账号 admin（初始密码见 config/admin_initial_password.txt）")
    finally:
        conn.close()


# ── 用户查询 ─────────────────────────────────────────
def get_user_by_username(username: str) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute(
                "SELECT id, username, password_hash, role, display_name, status "
                "FROM users WHERE username = %s", (username,),
            )
            row = cur.fetchone()
            if row:
                row.pop("password_hash", None)
            return row
    finally:
        conn.close()


def _get_user_with_hash(username: str) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute(
                "SELECT id, username, password_hash, role, display_name, status "
                "FROM users WHERE username = %s", (username,),
            )
            return cur.fetchone()
    finally:
        conn.close()


# ── 会话 ─────────────────────────────────────────────
def create_session(user: dict) -> str:
    token = secrets.token_urlsafe(32)
    redis_client.set_json(
        SESSION_PREFIX + token, SESSION_TTL,
        {"id": user["id"], "username": user["username"],
         "role": user["role"], "display_name": user.get("display_name")},
    )
    return token


def destroy_session(token: str):
    if token:
        redis_client.delete(SESSION_PREFIX + token)


def get_session_user(token: str) -> dict | None:
    if not token:
        return None
    return redis_client.get_json(SESSION_PREFIX + token)


# ── 登录 / 登出 / 改密 ──────────────────────────────
def do_login(username: str, password: str, ip: str) -> dict:
    """执行登录，返回 {token, user}；失败抛 HTTPException。"""
    username = (username or "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    # 账号锁定检查
    lock_key = LOCK_PREFIX + username
    if redis_client.get(lock_key):
        raise HTTPException(status_code=403, detail="账号已锁定，请 15 分钟后再试")

    # IP 限流检查
    ip_key = IP_FAIL_PREFIX + ip
    if int(redis_client.get(ip_key) or 0) >= IP_THRESHOLD:
        raise HTTPException(status_code=403, detail="尝试过于频繁，请 15 分钟后再试")

    user = _get_user_with_hash(username)
    # 统一错误提示（防遍历：不区分用户名不存在/密码错误）
    if not user or not verify_password(password, user["password_hash"]):
        fails = redis_client.incr(FAIL_PREFIX + username, IP_WINDOW_SECONDS)
        redis_client.incr(ip_key, IP_WINDOW_SECONDS)
        if fails >= LOCKOUT_THRESHOLD:
            redis_client.setex(lock_key, LOCKOUT_SECONDS, "1")
            redis_client.delete(FAIL_PREFIX + username)
            raise HTTPException(status_code=403, detail="失败次数过多，账号已锁定 15 分钟")
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if user["status"] != 1:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    # 登录成功：清除失败计数，更新最近登录时间
    redis_client.delete(FAIL_PREFIX + username, ip_key)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET last_login_at = NOW() WHERE id = %s", (user["id"],)
            )
        conn.commit()
    finally:
        conn.close()

    user.pop("password_hash", None)
    token = create_session(user)
    return {"token": token, "user": user}


def do_change_password(username: str, old_password: str, new_password: str):
    """修改密码（校验旧密码）。"""
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="新密码至少 8 位")
    user = _get_user_with_hash(username)
    if not user or not verify_password(old_password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="原密码错误")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (hash_password(new_password), user["id"]),
            )
        conn.commit()
    finally:
        conn.close()


# ── RBAC 依赖 ────────────────────────────────────────
def extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return ""


def get_current_user(request: Request) -> dict:
    """从请求头解析会话，返回用户信息；无效抛 401。"""
    token = extract_token(request)
    user = get_session_user(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")
    return user


def require_admin(request: Request) -> dict:
    """要求 admin 角色；否则 403。"""
    user = get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="无权限：该操作仅限管理员")
    return user


def require_admin_or_token(request: Request) -> dict:
    """密钥管理等运维接口：admin 会话 或 X-Admin-Token 均可。"""
    token = request.headers.get("X-Admin-Token", "")
    if token and _admin_token and secrets.compare_digest(token, _admin_token):
        return {"role": "admin", "username": "system", "via": "admin-token"}
    return require_admin(request)


def authz_allow(method: str, path: str, request: Request) -> bool:
    """中间件用的授权判定：True=放行，False/raise=拒绝。"""
    # 认证接口放行
    if path.startswith("/api/auth/"):
        return True
    # 密钥管理：admin 或系统令牌
    if path.startswith("/api/app-keys") or path.startswith("/api/admin/"):
        require_admin_or_token(request)
        return True
    # 游客可写的白名单（会议排序、认人测试）
    guest_writes = {
        ("POST", "/api/meetings"),
        ("POST", "/api/test/check"),
        ("POST", "/api/test/results"),
    }
    if method in ("POST", "PUT", "DELETE", "PATCH"):
        if (method, path) not in guest_writes:
            require_admin(request)
    return True
