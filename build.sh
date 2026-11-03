#!/usr/bin/env bash
# 词书 · 构建脚本
#   ./build.sh build   重新生成 dist/vocab.html（需要 data/ecdict.csv）
#   ./build.sh sync    把 web/ 资源与 dist/vocab.html 同步到 server / android / ios
#   ./build.sh all     两者都做（默认）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"

sync() {
  echo "==> 同步资源"
  mkdir -p "$ROOT/server/public/icons" "$ROOT/android/assets" "$ROOT/ios/Resources/www" "$ROOT/dist"
  cp "$ROOT/web/manifest.json" "$ROOT/web/sw.js" "$ROOT/server/public/"
  cp "$ROOT"/web/icons/*.png "$ROOT/server/public/icons/"
  cp "$ROOT/dist/vocab.html" "$ROOT/server/public/vocab.html"
  cp "$ROOT/dist/vocab.html" "$ROOT/android/assets/vocab.html"
  cp "$ROOT/dist/vocab.html" "$ROOT/ios/Resources/www/vocab.html"
  cp "$ROOT/web/manifest.json" "$ROOT/web/sw.js" "$ROOT/ios/Resources/www/" 2>/dev/null || true
  echo "   server/public/vocab.html  $(du -h "$ROOT/server/public/vocab.html" | cut -f1)"
}

build() {
  if [ ! -f "$ROOT/data/ecdict.csv" ]; then
    cat >&2 <<'EOF'
缺少 data/ecdict.csv（ECDICT 词库，约 66MB）。
下载：
  curl -L -o data/ecdict.csv \
    https://github.com/skywind3000/ECDICT/raw/master/ecdict.csv
（国内可用 https://ghproxy.net/https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv）
EOF
    exit 1
  fi
  echo "==> 构建词库"
  "$PY" "$ROOT/tools/build.py"
}

case "${1:-all}" in
  build) build ;;
  sync)  sync ;;
  all)   build; sync ;;
  *)     echo "用法: $0 [build|sync|all]" >&2; exit 2 ;;
esac
