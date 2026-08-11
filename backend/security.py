"""Fernet symmetric encryption for sensitive values (e.g. database password).

Key resolution priority:
1. Env var `APP_ENC_KEY`  → Fernet key string (base64)
2. Local file `config/secret.key`
3. Neither exists → auto-generate `config/secret.key` on first use
   (so the app works out of the box; the key file is gitignored).

The key file and the encryption key itself are secrets — never commit them.
"""

import os
from pathlib import Path

from cryptography.fernet import Fernet

# Key file lives in the project-root config/ directory
KEY_FILE = Path(__file__).resolve().parent.parent / "config" / "secret.key"

KEY_ENV_VAR = "APP_ENC_KEY"


def get_or_create_key() -> bytes:
    """Return the Fernet key (bytes), creating config/secret.key if needed."""
    key = os.environ.get(KEY_ENV_VAR)
    if key:
        return key.strip().encode()

    if KEY_FILE.is_file():
        return KEY_FILE.read_bytes().strip()

    # First run: generate and persist a key for future sessions
    key_bytes = Fernet.generate_key()
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_bytes(key_bytes)
    print(
        f"[Security] 已自动生成加密密钥: {KEY_FILE}\n"
        f"           请妥善保管该文件，切勿提交到版本库。"
    )
    return key_bytes


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext value, returning a Fernet token string."""
    f = Fernet(get_or_create_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a Fernet token string back to plaintext."""
    if not token:
        return ""
    f = Fernet(get_or_create_key())
    return f.decrypt(token.encode()).decode()


# ── AES-256-GCM 请求体加密（可选）──────────────────
# 用于外部接口的请求体加密：密钥由 app_secret 派生（SHA-256），
# 输出格式: base64( nonce(12B) + tag(16B) + ciphertext )

def _aes_key_from(secret: str) -> bytes:
    import hashlib
    return hashlib.sha256(secret.encode()).digest()


def encrypt_body(plaintext: bytes, secret: str) -> str:
    """AES-256-GCM 加密请求体，返回 base64 字符串。"""
    import base64
    import os
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    nonce = os.urandom(12)
    encryptor = Cipher(algorithms.AES(_aes_key_from(secret)), modes.GCM(nonce)).encryptor()
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    return base64.b64encode(nonce + encryptor.tag + ciphertext).decode()


def decrypt_body(payload_b64: str, secret: str) -> bytes:
    """解密 AES-256-GCM 请求体（encrypt_body 的逆操作）。"""
    import base64
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    raw = base64.b64decode(payload_b64)
    nonce, tag, ciphertext = raw[:12], raw[12:28], raw[28:]
    try:
        decryptor = Cipher(algorithms.AES(_aes_key_from(secret)), modes.GCM(nonce, tag)).decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    except InvalidTag:
        raise ValueError("AES-GCM 解密失败：密钥或密文不正确")
