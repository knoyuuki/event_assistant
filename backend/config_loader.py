"""Configuration loader — reads the active JSON config file.

Active config selection (in priority order):
1. Env var `APP_CONFIG`   → path to a specific JSON config file
2. Env var `APP_ENV`      → profile name, loads config/{APP_ENV}.json
3. Default                → dev (config/dev.json)

Example:
    APP_ENV=prod python backend/main.py
    APP_CONFIG=/path/to/custom.json python backend/main.py
"""

import json
import os
from pathlib import Path

# config/ directory is at the project root, one level above backend/
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

DEFAULT_PROFILE = "dev"


def resolve_config_path() -> Path:
    """Resolve the active config file path from environment variables."""
    explicit = os.environ.get("APP_CONFIG")
    if explicit:
        return Path(explicit)

    profile = os.environ.get("APP_ENV", DEFAULT_PROFILE)
    return CONFIG_DIR / f"{profile}.json"


def load_config() -> dict:
    """Load and return the active config as a dict."""
    path = resolve_config_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"配置文件不存在: {path}\n"
            f"请设置 APP_ENV 或 APP_CONFIG，或运行 "
            f"`python backend/encrypt_password.py --password '你的密码'` 生成 config/dev.json。"
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
