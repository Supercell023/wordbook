#!/usr/bin/env bash
# 单词本服务器一键部署（Ubuntu 22.04 / 24.04，x86_64 或 arm64）
#   用法：sudo bash deploy.sh                       # 只开 HTTP，端口 8787
#         sudo bash deploy.sh --port 9000           # 自定义端口
#         sudo bash deploy.sh --domain wb.example.com  # 自动装 Caddy 配 HTTPS
#         sudo bash deploy.sh --password 'MyPass123'   # 指定老师初始密码
#   重复执行是安全的：会保留 data/ 里的数据，只更新程序。
set -euo pipefail

APP_DIR=/opt/wordbook
SERVICE=wordbook
NODE_VER=v22.11.0
PORT=8787
DOMAIN=""
PASS=""
SRC="$(cd "$(dirname "$0")" && pwd)"

while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --domain) DOMAIN="$2"; shift 2 ;;
    --password) PASS="$2"; shift 2 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "未知参数：$1"; exit 1 ;;
  esac
done

[ "$(id -u)" = "0" ] || { echo "请用 root 运行：sudo bash deploy.sh"; exit 1; }

# 若仓库里有构建好的 dist/vocab.html，先同步进 public/
REPO_DIST="$(cd "$SRC/../dist" 2>/dev/null && pwd || true)"
if [ -n "$REPO_DIST" ] && [ -f "$REPO_DIST/vocab.html" ]; then
  mkdir -p "$SRC/public/icons"
  cp "$REPO_DIST/vocab.html" "$SRC/public/vocab.html"
  [ -f "$SRC/../web/manifest.json" ] && cp "$SRC/../web/manifest.json" "$SRC/public/"
  [ -f "$SRC/../web/sw.js" ] && cp "$SRC/../web/sw.js" "$SRC/public/"
  [ -d "$SRC/../web/icons" ] && cp "$SRC"/../web/icons/*.png "$SRC/public/icons/" 2>/dev/null || true
fi
if [ ! -f "$SRC/public/vocab.html" ]; then
  echo "缺少 server/public/vocab.html：请在仓库根目录先运行 ./build.sh" >&2
  exit 1
fi

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }

# ---------- 1. Node ----------
say "检查 Node.js"
need_node=1
if command -v node >/dev/null 2>&1; then
  major=$(node -p 'process.versions.node.split(".")[0]')
  [ "$major" -ge 18 ] && need_node=0
fi
if [ "$need_node" = 1 ]; then
  case "$(uname -m)" in
    x86_64|amd64) arch=x64 ;;
    aarch64|arm64) arch=arm64 ;;
    *) echo "不支持的架构：$(uname -m)"; exit 1 ;;
  esac
  tmp=$(mktemp -d)
  say "下载 Node $NODE_VER ($arch)"
  (curl -fsSL "https://nodejs.org/dist/$NODE_VER/node-$NODE_VER-linux-$arch.tar.xz" -o "$tmp/node.tar.xz" \
    || wget -qO "$tmp/node.tar.xz" "https://nodejs.org/dist/$NODE_VER/node-$NODE_VER-linux-$arch.tar.xz")
  tar -xJf "$tmp/node.tar.xz" -C /usr/local --strip-components=1 --exclude=CHANGELOG.md --exclude=LICENSE
  rm -rf "$tmp"
fi
node -v

# ---------- 2. 程序文件 ----------
say "安装到 $APP_DIR（保留已有数据）"
mkdir -p "$APP_DIR/data" "$APP_DIR/public" "$APP_DIR/apk"
cp -f "$SRC/server.js" "$SRC/admin.html" "$SRC/README.md" "$APP_DIR/"
cp -f "$SRC/public/vocab.html" "$APP_DIR/public/vocab.html"
[ -f "$SRC/apk/wordbook.apk" ] && cp -f "$SRC/apk/wordbook.apk" "$APP_DIR/apk/wordbook.apk"
if [ ! -f "$APP_DIR/data/db.json" ]; then
  : # 首次启动自动生成
fi

# ---------- 3. 环境变量 ----------
if [ ! -f /etc/wordbook.env ]; then
  say "生成 /etc/wordbook.env"
  INIT_PASS="${PASS:-$(head -c 9 /dev/urandom | base64 | tr -d '/+=' | head -c 10)}"
  cat > /etc/wordbook.env <<EOF
PORT=$PORT
ADMIN_USER=teacher
ADMIN_PASS=$INIT_PASS
DATA_DIR=$APP_DIR/data
LLM_URL=https://api.deepseek.com/chat/completions
LLM_KEY=
LLM_MODEL=deepseek-chat
EOF
  chmod 600 /etc/wordbook.env
  echo "  老师账号：teacher / $INIT_PASS  （改 /etc/wordbook.env 后重启服务生效）"
else
  say "沿用已有的 /etc/wordbook.env"
fi
. /etc/wordbook.env

# ---------- 4. systemd ----------
say "配置 systemd 服务"
cat > /etc/systemd/system/$SERVICE.service <<EOF
[Unit]
Description=WordBook server
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=/etc/wordbook.env
ExecStart=$(command -v node) $APP_DIR/server.js
Restart=always
RestartSec=3
NoNewPrivileges=true
ProtectSystem=full
ReadWritePaths=$APP_DIR/data

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now $SERVICE
sleep 1
systemctl --no-pager --lines=5 status $SERVICE || true

# ---------- 5. 防火墙 ----------
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  say "放行端口 $PORT"
  ufw allow "$PORT/tcp" >/dev/null || true
fi

# ---------- 6. HTTPS（可选） ----------
if [ -n "$DOMAIN" ]; then
  say "安装 Caddy 并配置 HTTPS：$DOMAIN"
  if ! command -v caddy >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl gnupg >/dev/null
    curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
      | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \
      > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq && apt-get install -y -qq caddy >/dev/null
  fi
  cat > /etc/caddy/Caddyfile <<EOF
$DOMAIN {
    encode zstd gzip
    reverse_proxy 127.0.0.1:$PORT
}
EOF
  systemctl restart caddy
  systemctl enable caddy >/dev/null 2>&1 || true
  URL="https://$DOMAIN"
else
  IP=$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')
  URL="http://$IP:$PORT"
fi

cat <<EOF

────────────────────────────────────────
 部署完成

 老师端：  $URL/admin
 学生端：  $URL/
 账号：    ${ADMIN_USER:-teacher} / ${ADMIN_PASS:-见 /etc/wordbook.env}

 常用命令：
   systemctl status $SERVICE      # 运行状态
   journalctl -u $SERVICE -f      # 实时日志
   nano /etc/wordbook.env         # 改密码 / LLM 配置
   systemctl restart $SERVICE     # 改完重启
   bash deploy.sh                 # 重复执行 = 升级程序（数据保留）
────────────────────────────────────────
EOF
