#!/usr/bin/env bash
# 下载 ECDICT 词库到 data/ecdict.csv（构建 dist/vocab.html 的输入）
#
#   bash tools/fetch_data.sh            # 已有且 >50MB 就跳过
#   bash tools/fetch_data.sh --force    # 强制重新下载
#
# 下载先写到 data/ecdict.csv.tmp，校验大小（>50MB）和表头（word,phonetic）
# 通过后再原子 mv 到 data/ecdict.csv，失败不会留下半截文件。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/data/ecdict.csv"
TMP="$DEST.tmp"
URL="${ECDICT_URL:-https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv}"
MIN_BYTES=52428800   # 50MB，ECDICT 完整词库约 66MB
FORCE=0

usage() {
  cat <<'EOF'
用法: bash tools/fetch_data.sh [--force]
  --force   忽略已有的 data/ecdict.csv，重新下载
环境变量:
  ECDICT_URL  自定义下载地址（默认 skywind3000/ECDICT 的 master 分支）
EOF
}

for arg in "$@"; do
  case "$arg" in
    --force|-f) FORCE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

if ! command -v curl >/dev/null 2>&1; then
  echo "错误: 找不到 curl，请先安装（apt-get install -y curl / brew install curl）" >&2
  exit 1
fi

mkdir -p "$ROOT/data"

if [ -f "$DEST" ] && [ "$FORCE" -ne 1 ]; then
  size=$(wc -c < "$DEST" | tr -d ' ')
  if [ "$size" -gt "$MIN_BYTES" ]; then
    echo "已存在 data/ecdict.csv（$(awk "BEGIN{printf \"%.1f\", $size/1048576}") MB），跳过下载。"
    echo "需要重新下载请加 --force"
    exit 0
  fi
  echo "已有 data/ecdict.csv 只有 $size 字节（<= 50MB），视为不完整，重新下载。"
fi

cleanup() { rm -f "$TMP"; }
trap cleanup EXIT INT TERM

echo "==> 下载 ECDICT 词库（约 66MB）"
echo "    $URL"
echo "    → data/ecdict.csv"

if ! curl -fL --retry 3 --retry-delay 2 --connect-timeout 20 \
      -o "$TMP" "$URL"; then
  echo "" >&2
  echo "下载失败。" >&2
  echo "  - 检查网络或代理后重试；国内可换镜像：" >&2
  echo "      ECDICT_URL='https://ghproxy.net/https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv' \\" >&2
  echo "        bash tools/fetch_data.sh --force" >&2
  echo "  - 也可以手动下载后保存为 data/ecdict.csv" >&2
  exit 1
fi

size=$(wc -c < "$TMP" | tr -d ' ')
if [ "$size" -le "$MIN_BYTES" ]; then
  echo "错误: 下载文件只有 $size 字节（需要 > 50MB），可能是镜像返回了错误页。" >&2
  echo "      已删除临时文件，请换网络/镜像重试。" >&2
  exit 1
fi

IFS= read -r header < "$TMP" || true
header="${header#$'\xef\xbb\xbf'}"
header="${header%$'\r'}"
if [[ "$header" != word,phonetic* ]]; then
  echo "错误: 下载文件表头不是 word,phonetic，文件可能不是 ECDICT CSV。" >&2
  echo "      实际表头: ${header:0:120}" >&2
  exit 1
fi

mv -f "$TMP" "$DEST"
trap - EXIT INT TERM
echo "==> 完成: data/ecdict.csv（$(awk "BEGIN{printf \"%.1f\", $size/1048576}") MB）"
