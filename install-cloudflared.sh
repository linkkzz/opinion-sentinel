#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$ROOT_DIR/.tools"
ARCH="$(uname -m)"

case "$ARCH" in
  arm64) ASSET="cloudflared-darwin-arm64.tgz" ;;
  x86_64) ASSET="cloudflared-darwin-amd64.tgz" ;;
  *)
    echo "暂不支持当前处理器架构：$ARCH"
    exit 1
    ;;
esac

mkdir -p "$INSTALL_DIR"
TMP_FILE="$(mktemp -t cloudflared.XXXXXX.tgz)"
trap 'rm -f "$TMP_FILE"' EXIT

echo "正在下载适用于 $ARCH 的 cloudflared……"
curl -fL --progress-bar \
  "https://github.com/cloudflare/cloudflared/releases/latest/download/$ASSET" \
  -o "$TMP_FILE"

tar -xzf "$TMP_FILE" -C "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/cloudflared"

echo "安装完成：$INSTALL_DIR/cloudflared"
"$INSTALL_DIR/cloudflared" --version
echo "现在可以执行：./share.sh"
