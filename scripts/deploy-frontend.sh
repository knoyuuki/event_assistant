#!/usr/bin/env bash
# 部署/更新前端 — 构建 dist 并同步到 nginx 站点目录
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

check_prereqs

log "安装前端依赖 ..."
(cd "$FRONTEND_DIR" && npm install --no-audit --no-fund)

log "构建前端 ..."
(cd "$FRONTEND_DIR" && npm run build)

log "同步到 $WEB_ROOT ..."
mkdir -p "$WEB_ROOT"
rsync -a --delete "$FRONTEND_DIR/dist/" "$WEB_ROOT/"

ok "前端已部署，刷新 nginx 配置（如有变更）..."
[ -f "$NGINX_AVAILABLE" ] && "$NGINX_BIN" -t && systemctl reload nginx
ok "前端部署完成: http://<服务器IP>/"
