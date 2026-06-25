#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

CLOUDFLARED_BIN="$(command -v cloudflared 2>/dev/null || true)"
if [ -z "$CLOUDFLARED_BIN" ] && [ -x "$ROOT_DIR/.tools/cloudflared" ]; then
  CLOUDFLARED_BIN="$ROOT_DIR/.tools/cloudflared"
fi

if [ -z "$CLOUDFLARED_BIN" ]; then
  echo "未安装 cloudflared。请先执行："
  echo "  ./install-cloudflared.sh"
  exit 1
fi

cleanup() {
  echo
  echo "正在关闭公网隧道和舆情智析平台……"
  kill "$APP_PID" 2>/dev/null || true
  wait "$APP_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "正在启动舆情智析平台……"
"$ROOT_DIR/start.sh" &
APP_PID=$!

echo "正在等待前端服务就绪……"
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:5173 >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$APP_PID" 2>/dev/null; then
    echo "平台启动失败，请查看上方日志。"
    exit 1
  fi
  sleep 1
done

if ! curl -fsS http://127.0.0.1:5173 >/dev/null 2>&1; then
  echo "等待前端启动超时。"
  exit 1
fi

echo
echo "正在创建 Cloudflare 临时公网地址……"
echo "看到 https://xxxxx.trycloudflare.com 后，把该地址发给同学即可。"
echo "按 Ctrl+C 会同时关闭公网访问和本地平台。"
echo

"$CLOUDFLARED_BIN" tunnel \
  --url http://127.0.0.1:5173 \
  --protocol http2 \
  --no-autoupdate
