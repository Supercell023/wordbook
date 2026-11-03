#!/usr/bin/env bash
# 词书 · 构建脚本
#   ./build.sh build    重新生成 dist/vocab.html（需要 data/ecdict.csv）
#   ./build.sh icons    重新生成 web/icons/*.png（纯 python3，不需要 Pillow）
#   ./build.sh sync     同步 web/ 资源 + dist/vocab.html 到 dist / server / android / ios
#   ./build.sh verify   校验 manifest、图标真实尺寸、PWA 关键标签是否齐全
#   ./build.sh all      build + icons + sync + verify（默认）
#
# 同步目标（四份内容保持一致，缺一份就可能「装不上 PWA」）：
#   dist/                 直接托管这个目录也能安装
#   server/public/        server.js 的静态根
#   android/assets/       内嵌进 APK 的离线副本
#   ios/Resources/www/    内嵌进 iOS App 的离线副本
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
DIST="$ROOT/dist"
WEB="$ROOT/web"
PUBLIC="$ROOT/server/public"
ANDROID="$ROOT/android/assets"
IOSWWW="$ROOT/ios/Resources/www"
TARGETS=("$DIST" "$PUBLIC" "$ANDROID" "$IOSWWW")

build() {
  if [ ! -f "$ROOT/data/ecdict.csv" ]; then
    cat >&2 <<'EOF'
缺少 data/ecdict.csv（ECDICT 词库，约 66MB）。
下载：
  bash tools/fetch_data.sh
（或手动 curl -L -o data/ecdict.csv \
  https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv）
EOF
    exit 1
  fi
  echo "==> 构建词库"
  "$PY" "$ROOT/tools/build.py"
}

icons() {
  echo "==> 生成 PWA 图标"
  "$PY" "$WEB/icons/make_icons.py"
}

sync() {
  echo "==> 同步资源"

  # 1) 页面：优先 dist，缺失时用历史产物补齐，避免 cp 直接报错中断
  local html="$DIST/vocab.html"
  if [ ! -f "$html" ]; then
    for cand in "$PUBLIC/vocab.html" "$ANDROID/vocab.html" "$IOSWWW/vocab.html"; do
      if [ -f "$cand" ]; then
        mkdir -p "$DIST"; cp "$cand" "$html"
        echo "   dist/vocab.html 由 ${cand#$ROOT/} 补齐"
        break
      fi
    done
  fi
  [ -f "$html" ] || { echo "缺少 dist/vocab.html，请先运行 ./build.sh build" >&2; exit 1; }

  # 2) 图标：尺寸不对或缺失就重生成（生成器只依赖标准库）
  if ! "$PY" "$WEB/icons/make_icons.py" --check >/dev/null 2>&1; then
    icons
  fi

  # 3) 四份目录：vocab.html + manifest.json + sw.js + icons/
  #    SW 缓存名用构建哈希，页面一变就自动换缓存并提示刷新。
  local d ver
  ver="$(sha256sum "$html" | cut -c1-12)"
  mkdir -p "$DIST/icons" "$PUBLIC/icons" "$ANDROID/icons" "$IOSWWW/icons"
  for d in "${TARGETS[@]}"; do
    if [ "$d" != "$DIST" ]; then
      cp "$html" "$d/vocab.html"
    fi
    cp "$WEB/manifest.json"    "$d/manifest.json"
    sed "s/__SW_VERSION__/$ver/g" "$WEB/sw.js" > "$d/sw.js"
    cp "$WEB"/icons/*.png      "$d/icons/"
    cp "$WEB"/icons/*.svg      "$d/icons/"
  done

  echo "   dist/vocab.html          $(du -h "$html" | cut -f1)"
  echo "   manifest/sw/icons →      dist/ server/public/ android/assets/ ios/Resources/www/"
}

verify() {
  echo "==> 校验 PWA 资源"
  "$PY" - "$ROOT" <<'PY'
import json, os, struct, sys

root = sys.argv[1]
dirs = ["dist", "server/public", "android/assets", "ios/Resources/www"]
problems = []


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(33)
    if len(head) < 33 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


man_path = os.path.join(root, "dist", "manifest.json")
try:
    man = json.load(open(man_path, encoding="utf-8"))
except Exception as e:  # noqa: BLE001
    print("  ✗ manifest.json 解析失败: %s" % e)
    sys.exit(1)

need = ["name", "short_name", "start_url", "scope", "display",
        "theme_color", "background_color"]
for k in need:
    if not man.get(k):
        problems.append("manifest 缺少字段 %s" % k)
if man.get("display") not in ("standalone", "fullscreen", "minimal-ui"):
    problems.append("manifest display=%r 不能触发安装" % man.get("display"))

icons = man.get("icons") or []
maskable = [i for i in icons if "maskable" in (i.get("purpose") or "")]
if not maskable:
    problems.append("manifest 没有 purpose=maskable 的图标")

for d in dirs:
    base = os.path.join(root, d)
    for f in ("vocab.html", "manifest.json", "sw.js"):
        if not os.path.isfile(os.path.join(base, f)):
            problems.append("%s 缺少 %s" % (d, f))
    swp = os.path.join(base, "sw.js")
    if os.path.isfile(swp) and "__SW_VERSION__" in open(swp, encoding="utf-8").read():
        problems.append("%s sw.js 未写入构建版本（请跑 ./build.sh sync）" % d)
    for ic in icons:
        p = os.path.join(base, ic["src"])
        if not os.path.isfile(p):
            problems.append("%s 缺少 %s（manifest 引用）" % (d, ic["src"]))
            continue
        if ic.get("type") == "image/png" and ic.get("sizes") != "any":
            want = ic["sizes"].split("x")[0]
            got = png_size(p)
            if not got:
                problems.append("%s 不是合法 PNG" % os.path.join(d, ic["src"]))
            elif str(got[0]) != want:
                problems.append("%s 实际 %dx%d，manifest 声明 %s"
                                % (os.path.join(d, ic["src"]), got[0], got[1], ic["sizes"]))

html = open(os.path.join(root, "dist", "vocab.html"), encoding="utf-8", errors="replace").read()
for tag, hint in (
    ('rel="manifest"', "缺少 <link rel=\"manifest\" href=\"manifest.json\">"),
    ('serviceWorker', "缺少 Service Worker 注册代码"),
    ('apple-touch-icon', "缺少 <link rel=\"apple-touch-icon\">"),
):
    if tag not in html:
        problems.append("vocab.html " + hint)

sizes = []
for ic in icons:
    p = os.path.join(root, "dist", ic["src"])
    if ic.get("type") == "image/png" and os.path.isfile(p):
        g = png_size(p)
        sizes.append("%s=%s" % (ic["src"].split("/")[-1], "%dx%d" % g if g else "?"))
print("  图标实测: " + (", ".join(sizes) if sizes else "无"))
print("  manifest: display=%s start_url=%s scope=%s 图标 %d 个（maskable %d 个）"
      % (man.get("display"), man.get("start_url"), man.get("scope"), len(icons), len(maskable)))

if problems:
    for p in problems:
        print("  ✗ " + p)
    sys.exit(1)
print("  ✓ PWA 资源齐备")
PY
}

case "${1:-all}" in
  build)  build ;;
  icons)  icons ;;
  sync)   sync ;;
  verify) verify ;;
  all)
    if [ -f "$ROOT/data/ecdict.csv" ]; then
      build
    elif [ -f "$DIST/vocab.html" ]; then
      echo "==> 跳过 build（无 data/ecdict.csv，沿用现有 dist/vocab.html）"
    else
      build
    fi
    icons
    sync
    verify
    ;;
  *) echo "用法: $0 [build|icons|sync|verify|all]" >&2; exit 2 ;;
esac
