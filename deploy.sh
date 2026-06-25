#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$ROOT_DIR/.env.deploy"

info() { printf '\033[1;36m%s\033[0m\n' "$*"; }
fail() { printf '\033[1;31m%s\033[0m\n' "$*" >&2; exit 1; }

install_docker() {
  command -v apt-get >/dev/null 2>&1 || fail "自动安装仅支持 Ubuntu/Debian，请先按 Docker 官方文档安装 Docker Engine。"
  local sudo_cmd=""
  if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null 2>&1 || fail "请使用 root 用户运行，或先安装 sudo。"
    sudo_cmd="sudo"
  fi

  info "未检测到 Docker，正在安装 Docker Engine……"
  $sudo_cmd apt-get update
  $sudo_cmd apt-get install -y ca-certificates curl
  $sudo_cmd install -m 0755 -d /etc/apt/keyrings
  . /etc/os-release
  case "$ID" in
    ubuntu|debian) ;;
    *) fail "当前系统不是 Ubuntu/Debian，请先手动安装 Docker Engine。" ;;
  esac
  $sudo_cmd curl -fsSL "https://download.docker.com/linux/$ID/gpg" -o /etc/apt/keyrings/docker.asc
  $sudo_cmd chmod a+r /etc/apt/keyrings/docker.asc
  local arch codename
  arch="$(dpkg --print-architecture)"
  codename="${VERSION_CODENAME:-$(. /etc/os-release && echo "$VERSION_CODENAME")}"
  echo "deb [arch=$arch signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/$ID $codename stable" \
    | $sudo_cmd tee /etc/apt/sources.list.d/docker.list >/dev/null
  $sudo_cmd apt-get update
  $sudo_cmd apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  $sudo_cmd systemctl enable --now docker
}

if ! command -v docker >/dev/null 2>&1; then
  install_docker
fi

DOCKER=(docker)
if ! docker info >/dev/null 2>&1; then
  if command -v sudo >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
    DOCKER=(sudo docker)
  else
    fail "当前用户无权访问 Docker，请使用 root 运行或将用户加入 docker 组。"
  fi
fi

"${DOCKER[@]}" compose version >/dev/null 2>&1 || fail "缺少 Docker Compose 插件，请安装 docker-compose-plugin。"

if [ ! -f "$ENV_FILE" ]; then
  command -v openssl >/dev/null 2>&1 || fail "缺少 openssl，无法安全生成数据库密码。"
  umask 077
  cat >"$ENV_FILE" <<EOF
DB_PASSWORD=$(openssl rand -hex 24)
MYSQL_ROOT_PASSWORD=$(openssl rand -hex 24)
OLLAMA_MODEL=qwen2.5:3b
AI_REQUEST_TIMEOUT_SECONDS=600
PUBLIC_PORT=80
SITE_USERNAME=opinion
SITE_PASSWORD=$(openssl rand -hex 6)
EOF
  info "已生成部署配置：$ENV_FILE"
fi

site_username="$(grep '^SITE_USERNAME=' "$ENV_FILE" | cut -d= -f2-)"
site_password="$(grep '^SITE_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
[ -n "$site_username" ] && [ -n "$site_password" ] || fail ".env.deploy 缺少 SITE_USERNAME 或 SITE_PASSWORD。"
printf '%s:%s\n' "$site_username" "$(openssl passwd -apr1 "$site_password")" >"$ROOT_DIR/.htpasswd"
chmod 600 "$ROOT_DIR/.htpasswd"

cd "$ROOT_DIR"
info "正在构建并启动舆情智析平台……首次启动需要下载镜像和大模型，请耐心等待。"
"${DOCKER[@]}" compose --env-file "$ENV_FILE" up -d --build

info "正在等待服务就绪……"
for _ in $(seq 1 120); do
  if "${DOCKER[@]}" compose --env-file "$ENV_FILE" ps --status running backend web | grep -q "web"; then
    if curl -fsS -u "$site_username:$site_password" "http://127.0.0.1:$(grep '^PUBLIC_PORT=' "$ENV_FILE" | cut -d= -f2)/api/health" >/dev/null 2>&1; then
      host_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
      port="$(grep '^PUBLIC_PORT=' "$ENV_FILE" | cut -d= -f2)"
      info "部署完成：http://${host_ip:-服务器公网IP}${port:+:$port}"
      info "访问账号：$site_username"
      info "访问密码：$site_password"
      info "查看日志：docker compose --env-file .env.deploy logs -f"
      exit 0
    fi
  fi
  sleep 5
done

"${DOCKER[@]}" compose --env-file "$ENV_FILE" ps
"${DOCKER[@]}" compose --env-file "$ENV_FILE" logs --tail=80 backend web ollama-pull
fail "服务未在预期时间内就绪，请根据上方日志排查。"
