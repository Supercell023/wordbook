#!/bin/bash
# 本地打包 Android 客户端（无需 Gradle；用 arm64 版 aapt + JDK 的 d8/apksigner）
set -e
export PATH=/usr/lib/jvm/java-17-openjdk-arm64/bin:$PATH
BT=/root/android-sdk/android-14        # 提供 d8.jar / apksigner.jar
AJ=/root/android-sdk/android-34/android.jar
SRC=/root/workspace/vocab/android
OUT=/tmp/apkbuild
rm -rf "$OUT"; mkdir -p "$OUT/gen" "$OUT/classes" "$OUT/dex" "$SRC/assets"
cp /root/workspace/vocab/vocab.html "$SRC/assets/vocab.html"

# 1. 资源 + 清单 → 未签名 APK
aapt package -f -M "$SRC/AndroidManifest.xml" -S "$SRC/res" -A "$SRC/assets" \
  -I "$AJ" -F "$OUT/base.apk" --min-sdk-version 24 --target-sdk-version 34

# 2. 编译 Java → class → dex
javac -source 8 -target 8 -nowarn -bootclasspath "$AJ" -classpath "$AJ" \
  -d "$OUT/classes" "$SRC/src/com/dsh/wordbook/MainActivity.java" 2>/dev/null
java -cp "$BT/lib/d8.jar" com.android.tools.r8.D8 --lib "$AJ" --min-api 24 \
  --output "$OUT/dex" $(find "$OUT/classes" -name '*.class')

# 3. 把 classes.dex 塞进 APK
cd "$OUT" && zip -q "$OUT/base.apk" -j "$OUT/dex/classes.dex"

# 4. 对齐 + 签名
zipalign -f 4 "$OUT/base.apk" "$OUT/aligned.apk"
if [ ! -f "$SRC/debug.keystore" ]; then
  keytool -genkeypair -keystore "$SRC/debug.keystore" -storepass android -keypass android \
    -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=WordBook Demo, O=DSH, C=CN" >/dev/null 2>&1
fi
java -jar "$BT/lib/apksigner.jar" sign --ks "$SRC/debug.keystore" --ks-pass pass:android \
  --key-pass pass:android --out "$OUT/wordbook.apk" "$OUT/aligned.apk"
java -jar "$BT/lib/apksigner.jar" verify "$OUT/wordbook.apk"
cp "$OUT/wordbook.apk" "$SRC/单词本.apk"
ls -l "$SRC/单词本.apk"
