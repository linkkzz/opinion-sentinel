#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
NODE_DIR="/Users/mxx/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin"
TOOL_DIR="/Users/mxx/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin"

if [ ! -x "$ROOT_DIR/.venv/bin/uvicorn" ]; then
  echo "缺少 Python 依赖，请先运行："
  echo "python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt"
  exit 1
fi

if [ ! -d "$ROOT_DIR/frontend/node_modules" ]; then
  echo "缺少前端依赖，请先进入 frontend 目录运行 pnpm install。"
  exit 1
fi

export PATH="$NODE_DIR:$TOOL_DIR:$PATH"

for PORT in 8000 5173; do
  if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "端口 $PORT 已被占用，请先关闭旧服务后再启动。"
    echo "可执行：lsof -nP -iTCP:$PORT -sTCP:LISTEN"
    exit 1
  fi
done

cleanup() {
  echo
  echo "正在关闭舆情智析平台……"
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$ROOT_DIR"
echo "启动后端：http://127.0.0.1:8000"
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

cd "$ROOT_DIR/frontend"
echo "启动前端：http://127.0.0.1:5173"
pnpm dev --host 127.0.0.1 --strictPort &
FRONTEND_PID=$!

echo
echo "舆情智析平台启动中，按 Ctrl+C 可同时关闭前后端。"
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

echo "检测到服务异常退出。"
exit 1
