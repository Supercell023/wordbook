#!/usr/bin/env bash
# 把最新的 dist/vocab.html 和应用图标同步进鸿蒙工程。
# 用法：在任意目录执行 bash harmony/sync.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RAW="$ROOT/harmony/entry/src/main/resources/rawfile"
BASE_MEDIA="$ROOT/harmony/entry/src/main/resources/base/media"
APP_MEDIA="$ROOT/harmony/AppScope/resources/base/media"

if [ ! -f "$ROOT/dist/vocab.html" ]; then
  echo "缺少 $ROOT/dist/vocab.html，请先运行 python3 tools/build.py" >&2
  exit 1
fi

mkdir -p "$RAW" "$BASE_MEDIA" "$APP_MEDIA"
cp "$ROOT/dist/vocab.html" "$RAW/vocab.html"
cp "$ROOT/web/icons/icon-192.png" "$BASE_MEDIA/icon.png"
cp "$ROOT/web/icons/icon-512.png" "$BASE_MEDIA/startIcon.png"
cp "$ROOT/web/icons/icon-512.png" "$APP_MEDIA/app_icon.png"

echo "已同步："
echo "  $RAW/vocab.html  ($(wc -c < "$RAW/vocab.html") bytes)"
echo "  $BASE_MEDIA/icon.png"
echo "  $BASE_MEDIA/startIcon.png"
echo "  $APP_MEDIA/app_icon.png"
