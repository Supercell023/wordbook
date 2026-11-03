# iOS 版（词书 · 背单词）

iPhone 上有两条路，按你的条件选：

## 路线 A：不打包，用 Safari「添加到主屏幕」（推荐，现在就能用）

1. 电脑/服务器上运行班级版服务器，并配好 HTTPS（`deploy.sh --domain 你的域名`）。
   iOS 的离线缓存和主屏图标**需要 https**；纯 http 也能背词，但不会离线保存缓存。
2. 学生 iPhone 用 **Safari** 打开 `https://你的域名/student.html`。
3. 点底部「分享」→「添加到主屏幕」→ 命名「词书」。
4. 之后从主屏图标打开：全屏、无地址栏，和 App 一样；断网也能背（Service Worker 已缓存）。

这条路不需要 Mac、不需要开发者账号，升级只要刷新页面。

## 路线 B：真·原生 App（需要 Mac + Xcode）

本目录就是一个 XcodeGen 工程描述，源码都写好了：

```
ios/
  project.yml            # XcodeGen 工程描述
  Info.plist
  Sources/WordBookApp.swift
  Sources/ContentView.swift   # WKWebView + AVSpeechSynthesizer 发音桥
  Resources/www/vocab.html    # 打包进 App 的网页（当前版本）
```

### 打包步骤（在 Mac 上）

```bash
brew install xcodegen
cd ios
xcodegen generate          # 生成 WordBook.xcodeproj
open WordBook.xcodeproj
```

1. Xcode 里选中 WordBook target → Signing & Capabilities → 选你的 Team（免费 Apple ID 也行）。
2. 手机用数据线连 Mac，选中真机，点 Run。
3. 免费账号签的 App **7 天过期**，到期重新 Run 一次即可；付费开发者账号 99 美元/年，可 1 年有效，也能上 TestFlight 给全班装。

### 说明

- 网页资源是打包进 App 的，**完全离线**；发音用系统 `AVSpeechSynthesizer`（en-US）。
- 网页里的 `window.AndroidTTS` 桥在 iOS 上由注入脚本提供，所以发音代码不用改。
- 换新版本：`cp ../vocab.html Resources/www/vocab.html` 后重新 Run。
- iOS 不支持侧载 APK 那种“发个安装包就能装”，必须经过 Xcode 签名或 TestFlight。

## 对比

| | PWA（路线 A） | 原生（路线 B） |
|---|---|---|
| 要 Mac | 不用 | 要 |
| 要开发者账号 | 不用 | 免费 7 天 / 付费 1 年 |
| 离线 | 有（需 https） | 有 |
| 发音 | Safari 系统语音 | AVSpeechSynthesizer |
| 更新 | 刷新即生效 | 重新打包 |
