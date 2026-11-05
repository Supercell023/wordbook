#!/bin/bash
# 本地打包 Android 客户端（无需 Gradle；用 arm64 版 aapt + JDK 的 d8/apksigner）
#
# 默认用仓库里的 debug.keystore 签 debug 包；四个环境变量齐全时改签 release：
#   WORDBOOK_KEYSTORE   .jks / .keystore 路径
#   WORDBOOK_KEY_ALIAS  密钥别名
#   WORDBOOK_STOREPASS  仓库密码
#   WORDBOOK_KEYPASS    密钥密码
#
# 产物：android/wordbook-<versionName>-release.apk（或 -debug.apk），
#       同时复制一份 android/wordbook.apk 作为固定下载路径。
set -e
BT=/root/android-sdk/android-14        # 提供 aapt / d8.jar / apksigner.jar
export PATH=$BT:/usr/lib/jvm/java-17-openjdk-arm64/bin:$PATH
AJ=/root/android-sdk/android-34/android.jar
SRC="$(cd "$(dirname "$0")" && pwd)"
OUT=/tmp/apkbuild

VER=$(sed -n 's/.*android:versionName="\([^"]*\)".*/\1/p' "$SRC/AndroidManifest.xml" | head -n 1)
VER=$(printf '%s' "${VER:-0.0.0}" | sed 's/[^0-9A-Za-z._-]/_/g')
[ -n "$VER" ] || VER=0.0.0

rm -rf "$OUT"; mkdir -p "$OUT/gen" "$OUT/classes" "$OUT/dex" "$SRC/assets"
[ -f "$SRC/assets/vocab.html" ] || { echo "缺少 assets/vocab.html，请先在仓库根目录运行 ./build.sh sync"; exit 1; }

# 1. 资源 + 清单 → 未签名 APK
AAPT="${AAPT:-/usr/bin/aapt}"
[ -x "$AAPT" ] || AAPT="$BT/aapt"
"$AAPT" package -f -M "$SRC/AndroidManifest.xml" -S "$SRC/res" -A "$SRC/assets" \
  -I "$AJ" -F "$OUT/base.apk" --min-sdk-version 24 --target-sdk-version 34

# 2. 编译 Java → class → dex
javac -source 8 -target 8 -nowarn -bootclasspath "$AJ" -classpath "$AJ" \
  -d "$OUT/classes" "$SRC/src/com/dsh/wordbook/MainActivity.java" 2>/dev/null
java -cp "$BT/lib/d8.jar" com.android.tools.r8.D8 --lib "$AJ" --min-api 24 \
  --output "$OUT/dex" $(find "$OUT/classes" -name '*.class')

# 3. 把 classes.dex 塞进 APK
cd "$OUT" && zip -q "$OUT/base.apk" -j "$OUT/dex/classes.dex"

# 4. 对齐
ZIPALIGN="${ZIPALIGN:-/usr/bin/zipalign}"
[ -x "$ZIPALIGN" ] || ZIPALIGN="$BT/zipalign"
"$ZIPALIGN" -f 4 "$OUT/base.apk" "$OUT/aligned.apk"

# 5. 签名：环境变量齐全走 release，否则维持原来的 debug 签名
KS="${WORDBOOK_KEYSTORE:-}"
ALIAS="${WORDBOOK_KEY_ALIAS:-}"
STOREPASS="${WORDBOOK_STOREPASS:-}"
KEYPASS="${WORDBOOK_KEYPASS:-}"
APK=""

if [ -n "$KS" ] && [ -n "$ALIAS" ] && [ -n "$STOREPASS" ] && [ -n "$KEYPASS" ]; then
  [ -f "$KS" ] || { echo "找不到 WORDBOOK_KEYSTORE 指向的密钥库：$KS" >&2; exit 1; }
  echo "==> 使用 release 签名（版本 $VER）"
  APK="$OUT/wordbook-$VER-release.apk"
  java -jar "$BT/lib/apksigner.jar" sign \
    --ks "$KS" --ks-key-alias "$ALIAS" \
    --ks-pass "pass:$STOREPASS" --key-pass "pass:$KEYPASS" \
    --out "$APK" "$OUT/aligned.apk"
  SUFFIX=release
else
  missing=""
  [ -n "$KS" ] || missing="$missing WORDBOOK_KEYSTORE"
  [ -n "$ALIAS" ] || missing="$missing WORDBOOK_KEY_ALIAS"
  [ -n "$STOREPASS" ] || missing="$missing WORDBOOK_STOREPASS"
  [ -n "$KEYPASS" ] || missing="$missing WORDBOOK_KEYPASS"
  if [ -n "$KS$ALIAS$STOREPASS$KEYPASS" ]; then
    echo "提示：release 签名变量不完整（缺$missing），改用 debug 签名。" >&2
  fi
  if [ ! -f "$SRC/debug.keystore" ]; then
    keytool -genkeypair -keystore "$SRC/debug.keystore" -storepass android -keypass android \
      -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 \
      -dname "CN=WordBook Demo, O=DSH, C=CN" >/dev/null 2>&1
  fi
  echo "==> 使用 debug 签名（版本 $VER）"
  APK="$OUT/wordbook-$VER-debug.apk"
  java -jar "$BT/lib/apksigner.jar" sign --ks "$SRC/debug.keystore" --ks-pass pass:android \
    --key-pass pass:android --out "$APK" "$OUT/aligned.apk"
  SUFFIX=debug
fi

java -jar "$BT/lib/apksigner.jar" verify "$APK"

# 6. 输出：带版本号的正式文件 + 固定别名（README / CI 用）
cp "$APK" "$SRC/wordbook-$VER-$SUFFIX.apk"
cp "$APK" "$SRC/wordbook.apk"
ls -l "$SRC/wordbook-$VER-$SUFFIX.apk" "$SRC/wordbook.apk"
