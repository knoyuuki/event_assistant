#!/usr/bin/env bash
# 一键完整部署 — 会务助手（nginx 前端 + Docker 后端）
# 用法:
#   ./scripts/deploy.sh                          # 已有 config/prod.json 时
#   DB_PASSWORD='MySQL密码' ./scripts/deploy.sh  # 首次部署（生成加密配置）
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

log "========== 会务助手 一键部署 =========="
check_prereqs
ensure_data_dirs
ensure_db_config

# 1. 后端：构建镜像 + 启动容器
log "[1/3] 部署后端（Docker）..."
"$SCRIPT_DIR/deploy-backend.sh"

# 2. nginx 站点配置
log "[2/3] 配置 nginx 站点 ..."
cp "$DEPLOY_DIR/nginx-event-assistant.conf" "$NGINX_AVAILABLE"
ln -sf "$NGINX_AVAILABLE" "$NGINX_ENABLED"
rm -f /etc/nginx/sites-enabled/default
"$NGINX_BIN" -t || fail "nginx 配置校验失败"
systemctl reload nginx
ok "nginx 站点已启用: $NGINX_SITE"

# 3. 前端：构建 + 同步
log "[3/3] 部署前端 ..."
"$SCRIPT_DIR/deploy-frontend.sh"

# ── 日志轮转（保留策略）────────────────────────────
log "配置日志轮转（nginx 30 天 / docker 7 天）..."
cp "$DEPLOY_DIR/logrotate-nginx" /etc/logrotate.d/nginx
cp "$DEPLOY_DIR/logrotate-docker-containers" /etc/logrotate.d/docker-containers
"$LOGROTATE_BIN" -d /etc/logrotate.d/nginx >/dev/null 2>&1 && ok "logrotate nginx: 每日轮转，保留 30 天"
"$LOGROTATE_BIN" -d /etc/logrotate.d/docker-containers >/dev/null 2>&1 && ok "logrotate docker: 每日轮转，保留 7 天"

echo ""
echo "==================== 部署完成 ===================="
echo "  前端:  http://<服务器IP>/        (nginx :80)"
echo "  后端:  http://127.0.0.1:$BACKEND_PORT  (Docker: $CONTAINER_NAME)"
echo "  数据库: 127.0.0.1:33306 (event_assistant)"
echo "  照片目录: $PROJECT_DIR/photos"
echo "  配置目录: $CONFIG_DIR（secret.key 请妥善备份！）"
echo "=================================================="
