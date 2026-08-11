#!/usr/bin/env python3
"""外部接口签名调用示例（Python）。

用法:
    export BASE_URL=http://127.0.0.1            # nginx 入口
    export APP_ID=ea_xxxxxxxxxxxxxxxx
    export APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxx
    python examples/api_client.py

依赖: pip install requests cryptography
"""

import hashlib
import hmac
import json
import os
import secrets
import sys
import time

import requests

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1").rstrip("/")
APP_ID = os.environ["APP_ID"]
APP_SECRET = os.environ["APP_SECRET"]


def sign(method: str, path: str, timestamp: int, nonce: str, body: bytes, secret: str) -> str:
    """按规范计算 HMAC-SHA256 签名。"""
    body_sha = hashlib.sha256(body).hexdigest()
    string_to_sign = "\n".join([method.upper(), path, str(timestamp), nonce, body_sha])
    return hmac.new(secret.encode(), string_to_sign.encode(), hashlib.sha256).hexdigest()


def encrypt_body(plaintext: bytes, secret: str) -> str:
    """AES-256-GCM 加密（与后端 security.encrypt_body 一致）。"""
    import base64
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    key = hashlib.sha256(secret.encode()).digest()
    nonce = os.urandom(12)
    enc = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    ct = enc.update(plaintext) + enc.finalize()
    return base64.b64encode(nonce + enc.tag + ct).decode()


def signed_request(method: str, path: str, query: dict | None = None,
                   body: dict | None = None, encrypt: bool = False) -> requests.Response:
    """发送签名请求。"""
    ts = int(time.time())
    nonce = secrets.token_hex(8)

    if body is not None:
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
        if encrypt:
            payload = encrypt_body(raw, APP_SECRET).encode()
            headers = {"X-Encrypt": "1", "Content-Type": "text/plain"}
        else:
            payload = raw
            headers = {"Content-Type": "application/json"}
    else:
        payload = b""
        headers = {}

    sig = sign(method, path, ts, nonce, payload, APP_SECRET)
    headers.update({
        "X-App-Id": APP_ID,
        "X-Timestamp": str(ts),
        "X-Nonce": nonce,
        "X-Signature": sig,
    })
    return requests.request(method, BASE_URL + path, params=query, data=payload, headers=headers, timeout=10)


def main():
    print(f"BASE_URL = {BASE_URL}\nAPP_ID   = {APP_ID}\n")

    # 1. GET 签名请求（无请求体）
    r = signed_request("GET", "/ext/persons", query={"limit": 3})
    print(f"[GET  /ext/persons] {r.status_code}")
    print("   ", json.dumps(r.json(), ensure_ascii=False)[:200])

    # 2. POST 签名请求（JSON 请求体）
    r = signed_request("POST", "/ext/echo", body={"hello": "world", "n": 42})
    print(f"[POST /ext/echo]     {r.status_code}")
    print("   ", json.dumps(r.json(), ensure_ascii=False)[:200])

    # 3. POST + AES-256-GCM 加密请求体
    r = signed_request("POST", "/ext/echo", body={"secret": "加密内容🔒"}, encrypt=True)
    print(f"[POST /ext/echo]     {r.status_code} (X-Encrypt=1)")
    print("   ", json.dumps(r.json(), ensure_ascii=False)[:200])


if __name__ == "__main__":
    sys.exit(main())
