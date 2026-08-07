"""CLI tool: generate encryption key and encrypt the database password.

Usage:
    python backend/encrypt_password.py --password '你的数据库密码'
    python backend/encrypt_password.py --password 'root' --config prod

What it does:
    1. Ensures config/secret.key exists (auto-generates if missing).
    2. Encrypts the given password with Fernet.
    3. Writes the encrypted token into config/{profile}.json
       (creates from config/example.json template if needed).

The written config file contains ONLY the encrypted token — never plaintext.
Both config/{profile}.json and config/secret.key are gitignored.
"""

import argparse
import json
import io
import sys
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from security import encrypt  # noqa: E402

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
EXAMPLE_FILE = CONFIG_DIR / "example.json"

# Default config template, used only when example.json is missing
DEFAULT_TEMPLATE = {
    "app": {"name": "会务助手", "debug": True},
    "server": {"host": "0.0.0.0", "port": 10023},
    "database": {
        "host": "127.0.0.1",
        "port": 3306,
        "user": "root",
        "password_encrypted": "",
        "database": "event_assistant",
        "charset": "utf8mb4",
    },
}


def _load_template() -> dict:
    """Load config/example.json, falling back to the built-in default."""
    if EXAMPLE_FILE.is_file():
        with open(EXAMPLE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(json.dumps(DEFAULT_TEMPLATE))


def main() -> int:
    parser = argparse.ArgumentParser(description="加密数据库密码并写入配置")
    parser.add_argument("--password", required=True, help="数据库明文密码")
    parser.add_argument(
        "--config", default="dev",
        help="配置文件 profile 名（默认 dev → config/dev.json）",
    )
    args = parser.parse_args()

    # 1. Ensure key exists (auto-generate) and encrypt
    token = encrypt(args.password)
    print(f"[OK] 密码已加密（Fernet 令牌长度 {len(token)}）")

    # 2. Prepare config target
    target = CONFIG_DIR / f"{args.config}.json"

    if target.is_file():
        with open(target, "r", encoding="utf-8") as f:
            config = json.load(f)
        print(f"[OK] 已加载现有配置: {target}")
    else:
        config = _load_template()
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[OK] 已从模板创建新配置: {target}")

    # 3. Write encrypted password (never plaintext)
    config.setdefault("database", {})["password_encrypted"] = token
    config["database"]["database"] = "event_assistant"

    with open(target, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"[OK] 已写入 {target}")
    print(f"[OK] 配置中的 password_encrypted 为密文，无密钥无法解密。")
    print("     启动方式: python backend/main.py  （默认加载 dev 配置）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
