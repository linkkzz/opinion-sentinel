FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Noto CJK 用于生成中文 PDF；curl 用于容器健康检查。
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# Playwright 浏览器（用于采集账号扫码登录 + Cookie 按需刷新）
RUN python -m playwright install chromium --with-deps

COPY backend/app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
