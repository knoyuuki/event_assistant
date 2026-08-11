#!/usr/bin/env bash
# 更新服务 — git pull 最新代码后重新部署前后端（数据与配置不动）
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

cd "$PROJECT_DIR"

log "========== 更新会务助手 =========="

# 检查本地是否有未提交改动（避免覆盖本地补丁/配置）
if [ -n "$(git status --porcelain | grep -v -E '^( M|\?\?)' )" ]; then
    warn "检测到本地已修改的文件，git pull 可能冲突："
    git status --porcelain | grep -v '^??' | head -10
fi

log "拉取最新代码 ..."
git pull --ff-only || {
    warn "fast-forward 拉取失败（本地可能有改动），尝试普通 pull ..."
    git pull || fail "git pull 失败，请手动处理冲突"
}

log "[1/2] 更新后端 ..."
"$SCRIPT_DIR/deploy-backend.sh"

log "[2/2] 更新前端 ..."
"$SCRIPT_DIR/deploy-frontend.sh"

ok "========== 更新完成 =========="
