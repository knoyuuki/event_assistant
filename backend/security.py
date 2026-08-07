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
