#!/usr/bin/env bash
# 共享函数库 — 会务助手部署脚本
set -euo pipefail

# ── 路径 ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
CONFIG_DIR="$PROJECT_DIR/config"
DEPLOY_DIR="$PROJECT_DIR/deploy"
VENV_DIR="$PROJECT_DIR/.venv"

WEB_ROOT="/var/www/event_assistant"
NGINX_SITE="event_assistant"
NGINX_AVAILABLE="/etc/nginx/sites-available/$NGINX_SITE"
NGINX_ENABLED="/etc/nginx/sites-enabled/$NGINX_SITE"
CONTAINER_NAME="event-assistant-backend"
IMAGE_NAME="event-assistant-backend:latest"
BACKEND_PORT=10023

# 找到系统命令（兼容受限 PATH）
find_cmd() {
    local cmd="$1" fallback="$2"
    if command -v "$cmd" >/dev/null 2>&1; then
        command -v "$cmd"
    else
        echo "$fallback"
    fi
}
NGINX_BIN="$(find_cmd nginx /usr/sbin/nginx)"
LOGROTATE_BIN="$(find_cmd logrotate /usr/sbin/logrotate)"

log()  { echo -e "\033[1;36m[$(date '+%H:%M:%S')]\033[0m $*"; }
ok()   { echo -e "\033[1;32m[OK]\033[0m $*"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $*"; }
fail() { echo -e "\033[1;31m[FAIL]\033[0m $*"; exit 1; }

# ── 前置检查 ─────────────────────────────────────────
check_prereqs() {
    command -v docker >/dev/null 2>&1 || fail "未安装 docker，请先安装"
    command -v npm >/dev/null 2>&1 || fail "未安装 node/npm，请先安装"
    [ -x "$NGINX_BIN" ] || fail "未安装 nginx，请先安装"
    [ -d "$PROJECT_DIR/.git" ] || fail "不是 git 仓库: $PROJECT_DIR"
}

# 确保数据目录存在（photos/people 不入库）
ensure_data_dirs() {
    mkdir -p "$PROJECT_DIR/photos" "$PROJECT_DIR/people"
}

# ── 数据库配置（仅首次需要）─────────────────────────
# 生成 config/prod.json（Fernet 加密密码）。若已存在则跳过。
ensure_db_config() {
    local target="$CONFIG_DIR/prod.json"
    [ -f "$target" ] && { ok "数据库配置已存在: $target（如需更换密码请手动更新）"; return 0; }

    local db_pass="${DB_PASSWORD:-}"
    if [ -z "$db_pass" ]; then
        warn "未检测到 config/prod.json，且未设置 DB_PASSWORD 环境变量"
        echo "   用法: DB_PASSWORD='你的MySQL密码' $0"
        echo "   （或先手动运行: python backend/encrypt_password.py --password '密码' --config prod）"
        exit 1
    fi

    if [ ! -x "$VENV_DIR/bin/python" ]; then
        log "创建 Python 虚拟环境并安装 cryptography ..."
        python3 -m venv "$VENV_DIR"
        "$VENV_DIR/bin/pip" install -q cryptography
    fi
    (cd "$PROJECT_DIR" && "$VENV_DIR/bin/python" backend/encrypt_password.py --password "$db_pass" --config prod)
    # 写入服务器/数据库连接（容器用 host 网络直连本机 33306）
    "$VENV_DIR/bin/python" - <<'PYEOF'
import json
p = "config/prod.json"
with open(p, encoding="utf-8") as f:
    cfg = json.load(f)
cfg.setdefault("app", {})["debug"] = False
db = cfg.setdefault("database", {})
db["host"] = db.get("host", "127.0.0.1")
db["port"] = int(db.get("port", 33306) or 33306)
db["user"] = db.get("user", "minami")
with open(p, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
    f.write("\n")
PYEOF
    ok "已生成数据库配置: $target（密码为密文存储）"
}
