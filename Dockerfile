# 会务助手后端 — FastAPI 生产镜像
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    APP_ENV=prod \
    TZ=Asia/Shanghai \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app

# 先拷贝依赖清单，利用缓存层
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 拷贝后端代码（config/、photos/、people/ 通过 volume 挂载，不入镜像）
COPY backend/ /app/backend/

WORKDIR /app/backend
EXPOSE 10023

# 健康检查：应用无 /health 接口，用 /api/departments/names 兜底
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:10023/api/departments/names', timeout=4)" || exit 1

CMD ["python", "main.py"]
