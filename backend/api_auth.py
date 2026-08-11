"""外部接口签名验证（HMAC-SHA256）与鉴权依赖。

签名规范（详见 docs/api-signature.md）:
    请求头: X-App-Id / X-Timestamp / X-Nonce / X-Signature（可选 X-Encrypt: 1）
    待签串 : METHOD\\nPATH\\nTIMESTAMP\\nNONCE\\nBODY_SHA256(hex)
    签名   : hex(HMAC-SHA256(app_secret, 待签串))
"""

import hashlib
import hmac
import time
from datetime import datetime

from fastapi import Request, HTTPException
from starlette.concurrency import run_in_threadpool

from api_keys import get_app_by_app_id

# ── 常量 ─────────────────────────────────────────────
SIGN_HEADERS = ("X-App-Id", "X-Timestamp", "X-Nonce", "X-Signature")
TIMESTAMP_WINDOW = 300          # 时间戳允许偏差 ±300 秒（防重放）
REPLAY_CACHE_TTL = TIMESTAMP_WINDOW * 2

# 防重放：内存缓存 {app_id: {nonce: timestamp}}，进程重启后清空（可接受）
_replay_cache: dict[str, dict[str, float]] = {}
_cache_last_prune = 0.0


def _prune_replay_cache():
    """清理过期的 nonce 缓存。"""
    global _cache_last_prune
    now = time.time()
    if now - _cache_last_prune < 60:
        return
    _cache_last_prune = now
    for app_id in list(_replay_cache.keys()):
        _replay_cache[app_id] = {
            n: ts for n, ts in _replay_cache[app_id].items() if now - ts < REPLAY_CACHE_TTL
        }
        if not _replay_cache[app_id]:
            _replay_cache.pop(app_id, None)


# ── 签名计算（供客户端示例与服务端验证共用）────────
def compute_signature(secret: str, method: str, path: str,
                      timestamp: str, nonce: str, body: bytes) -> str:
    """计算 HMAC-SHA256 签名（hex）。body 为实际发送的原始字节（可能已加密）。"""
    body_sha = hashlib.sha256(body).hexdigest()
    string_to_sign = "\n".join([method.upper(), path, str(timestamp), nonce, body_sha])
    return hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"),
                    hashlib.sha256).hexdigest()


# ── 服务端验证 ───────────────────────────────────────
def verify_signature_sync(app_id: str, timestamp: str, nonce: str, signature: str,
                          method: str, path: str, body: bytes) -> str:
    """校验签名，成功返回明文 secret，失败抛 HTTPException。"""
    # 1. 应用是否存在
    app = get_app_by_app_id(app_id)
    if not app:
        raise HTTPException(status_code=401, detail="无效的 app_id")

    # 2. 应用状态与有效期
    if app["status"] != 1:
        raise HTTPException(status_code=403, detail="应用已被禁用")
    if app["expires_at"] and app["expires_at"] < datetime.now():
        raise HTTPException(status_code=403, detail="应用密钥已过期")

    # 3. 时间戳防重放（±5 分钟）
    try:
        ts = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail="X-Timestamp 格式错误")
    if abs(time.time() - ts) > TIMESTAMP_WINDOW:
        raise HTTPException(status_code=401, detail="时间戳超出允许范围（±300秒）")

    # 4. nonce 防重放（同一窗口内不可重复使用）
    _prune_replay_cache()
    cached = _replay_cache.setdefault(app_id, {})
    if nonce in cached and time.time() - cached[nonce] < REPLAY_CACHE_TTL:
        raise HTTPException(status_code=401, detail="nonce 已被使用（重放攻击）")
    cached[nonce] = time.time()

    # 5. 签名校验
    expected = compute_signature(app["secret_plain"], method, path, timestamp, nonce, body)
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="签名校验失败")

    return app["secret_plain"]


async def verify_ext_signature(request: Request) -> str:
    """FastAPI 依赖：校验外部接口签名，返回 app_id。"""
    missing = [h for h in SIGN_HEADERS if not request.headers.get(h)]
    if missing:
        raise HTTPException(status_code=401, detail=f"缺少签名头: {', '.join(missing)}")

    app_id = request.headers["X-App-Id"]
    timestamp = request.headers["X-Timestamp"]
    nonce = request.headers["X-Nonce"]
    signature = request.headers["X-Signature"]

    # 读取原始 body（starlette 会缓存，后续可重复读）
    body = await request.body()
    secret = await run_in_threadpool(
        verify_signature_sync, app_id, timestamp, nonce, signature,
        request.method, request.url.path, body,
    )

    # 可选：AES-256-GCM 请求体解密
    if request.headers.get("X-Encrypt") == "1":
        if not body:
            raise HTTPException(status_code=401, detail="X-Encrypt=1 但请求体为空")
        try:
            from security import decrypt_body
            plain = await run_in_threadpool(decrypt_body, body.decode(), secret)
        except Exception:
            raise HTTPException(status_code=401, detail="请求体解密失败")
        request._body = plain  # 让下游 Pydantic 正常解析

    return app_id
