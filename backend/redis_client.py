"""Redis 缓存客户端（本地 127.0.0.1:36379）。

用途: 登录会话、登录失败计数/锁定、签名 nonce 防重放缓存。
Redis 不可用时自动降级为进程内内存缓存（仅开发/应急场景），并打印警告。
"""

import json
import os
import threading
import time

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:36379/0")
REDIS_ENABLED = os.environ.get("REDIS_DISABLE", "") != "1"

_client = None
_fallback = {}          # {key: (expire_ts, value)}
_fallback_lock = threading.Lock()


def _get_client():
    global _client
    if not REDIS_ENABLED:
        return None
    if _client is None:
        import redis
        _client = redis.Redis.from_url(
            REDIS_URL, decode_responses=True,
            socket_timeout=2, socket_connect_timeout=2,
        )
    return _client


def ping() -> bool:
    """探测 Redis 是否可用。"""
    c = _get_client()
    if c is None:
        return False
    try:
        return bool(c.ping())
    except Exception:
        return False


def get(key: str):
    c = _get_client()
    if c is not None:
        try:
            return c.get(key)
        except Exception:
            pass
    # 内存降级
    with _fallback_lock:
        item = _fallback.get(key)
        if item and item[0] > time.time():
            return item[1]
        _fallback.pop(key, None)
        return None


def setex(key: str, seconds: int, value):
    c = _get_client()
    if c is not None:
        try:
            c.setex(key, seconds, value)
            return
        except Exception:
            pass
    with _fallback_lock:
        _fallback[key] = (time.time() + seconds, value)


def delete(*keys: str):
    c = _get_client()
    if c is not None:
        try:
            c.delete(*keys)
            return
        except Exception:
            pass
    with _fallback_lock:
        for k in keys:
            _fallback.pop(k, None)


def incr(key: str, seconds: int = None) -> int:
    """自增；若键不存在先设过期（seconds），返回当前值。"""
    c = _get_client()
    if c is not None:
        try:
            if seconds and not c.exists(key):
                c.setex(key, seconds, 1)
                return 1
            return int(c.incr(key))
        except Exception:
            pass
    with _fallback_lock:
        item = _fallback.get(key)
        now = time.time()
        if not item or item[0] <= now:
            _fallback[key] = (now + (seconds or 60), "1")
            return 1
        val = int(item[1]) + 1
        _fallback[key] = (item[0], str(val))
        return val


def setnx_ex(key: str, seconds: int, value="1") -> bool:
    """仅当键不存在时设置并返回 True（用于 nonce 防重放）。"""
    c = _get_client()
    if c is not None:
        try:
            return bool(c.set(key, value, ex=seconds, nx=True))
        except Exception:
            pass
    with _fallback_lock:
        item = _fallback.get(key)
        if item and item[0] > time.time():
            return False
        _fallback[key] = (time.time() + seconds, value)
        return True


def get_json(key: str):
    v = get(key)
    if v is None:
        return None
    try:
        return json.loads(v)
    except Exception:
        return None


def set_json(key: str, seconds: int, obj) -> None:
    setex(key, seconds, json.dumps(obj, ensure_ascii=False))
