#!/usr/bin/env bash
# 部署/更新后端 — 构建 Docker 镜像并重建容器（数据在 volume 中，不丢失）
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

cd "$PROJECT_DIR"

check_prereqs
ensure_data_dirs

# ── 兼容性补丁：MySQL 8 下 DISTINCT+ORDER BY 报错 3065 ──
# 若上游代码回退为 DISTINCT 写法，这里自动重新打补丁（幂等）
if grep -q "SELECT DISTINCT p.department" backend/main.py; then
    log "检测到 MySQL 8 不兼容的 DISTINCT 查询，自动应用 GROUP BY 补丁 ..."
    python3 - <<'PYEOF'
import re
p = "backend/main.py"
src = open(p, encoding="utf-8").read()
old = """SELECT DISTINCT p.department
                FROM persons p
                LEFT JOIN departments d ON p.department = d.name
                LEFT JOIN dept_categories c ON d.category_id = c.id
                ORDER BY COALESCE(c.sort_order, 999), COALESCE(d.sort_order, 999), p.department"""
new = """SELECT p.department
                FROM persons p
                LEFT JOIN departments d ON p.department = d.name
                LEFT JOIN dept_categories c ON d.category_id = c.id
                GROUP BY p.department
                ORDER BY MIN(COALESCE(c.sort_order, 999)), MIN(COALESCE(d.sort_order, 999)), p.department"""
assert old in src, "补丁文本不匹配，请手动检查 backend/main.py"
open(p, "w", encoding="utf-8").write(src.replace(old, new))
print("[Patch] DISTINCT → GROUP BY 补丁已应用")
PYEOF
else
    ok "无需打补丁（GROUP BY 写法已就位）"
fi

# ── 构建镜像 ────────────────────────────────────────
log "构建后端镜像 $IMAGE_NAME ..."
docker build -t "$IMAGE_NAME" .

# ── 重建容器（保留数据卷）──────────────────────────
log "重建容器 $CONTAINER_NAME ..."
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
docker run -d --name "$CONTAINER_NAME" --restart=always --network host \
    -v "$PROJECT_DIR/photos:/app/photos" \
    -v "$PROJECT_DIR/people:/app/people" \
    -v "$PROJECT_DIR/config:/app/config" \
    "$IMAGE_NAME"

# ── 健康检查 ────────────────────────────────────────
log "等待后端启动（最多 60 秒）..."
for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:$BACKEND_PORT/api/departments/names" >/dev/null 2>&1; then
        ok "后端已就绪: http://127.0.0.1:$BACKEND_PORT/api/departments/names"
        exit 0
    fi
    sleep 2
done
fail "后端健康检查超时，查看日志: docker logs $CONTAINER_NAME"
