# 词书 · HarmonyOS NEXT 版

这是一个 **HarmonyOS NEXT（纯血鸿蒙，API 12+）** 的 Stage 模型工程骨架。
它不重写词书逻辑，而是用 ArkTS 的 `Web` 组件加载打包在 `rawfile` 里的
`vocab.html`，因此背词、复习、词卡、暗夜模式、奖励动效等全部沿用现有实现。

> 注意：本工程是在 Linux/proot 环境里生成的，**当前机器没有 DevEco Studio、
> HarmonyOS SDK、hvigorw、hdc**，所以这里只做了工程文件和静态检查，
> **没有编译出 HAP**。请用 DevEco Studio 打开后编译、签名、安装。

## 适用版本

| 系统 | 安装方式 |
| --- | --- |
| HarmonyOS 4.x 及更早 | 继续用仓库里的 `android/wordbook.apk`，不需要本工程 |
| HarmonyOS NEXT / 5.x | 用本工程编译 HAP |

## 用 DevEco Studio 打开

1. 安装 **DevEco Studio 5.0.3 或更高版本**，并安装 HarmonyOS NEXT SDK（API 12 或更高）。
2. `File → Open`，选择本目录 `harmony/`（不是仓库根目录）。
3. 等待右上角 hvigor Sync 完成。如果提示 SDK 版本不匹配，把
   `build-profile.json5` 里的 `compatibleSdkVersion` 改成你已安装的版本，
   例如 `"5.0.1(13)"`。
4. 配置签名：`File → Project Structure → Signing Configs`，
   勾选 `Automatically generate signature` 并登录华为开发者账号；
   或使用你自己的 `.p12` / `.cer` / `.p7b` 手动配置。
5. 连接真机（Core Speech Kit 的 TTS **只在真机可用**，模拟器不支持），
   点击 Run。

如果只想先打出未签名 HAP：

```bash
# DevEco 自带的 hvigorw 在工程根目录；没有的话用 DevEco 菜单 Build Hap(s)
./hvigorw clean --no-daemon
./hvigorw assembleHap --mode module -p product=default -p buildMode=debug --no-daemon
```

签名后的产物通常在：

```text
entry/build/default/outputs/default/entry-default-signed.hap
```

## 目录说明

```text
harmony/
├── AppScope/
│   ├── app.json5                 # bundleName、版本号、应用图标
│   └── resources/base/...        # 应用级图标/名称
├── entry/
│   ├── build-profile.json5
│   ├── hvigorfile.ts
│   ├── oh-package.json5
│   └── src/main/
│       ├── module.json5          # Ability、INTERNET 权限、页面入口
│       ├── ets/
│       │   ├── entryability/EntryAbility.ets
│       │   ├── pages/Index.ets   # Web 组件 + JavaScriptProxy
│       │   └── common/SpeechService.ets
│       └── resources/
│           ├── base/...          # 图标、颜色、字符串、main_pages
│           └── rawfile/vocab.html
├── build-profile.json5
├── hvigorfile.ts
├── oh-package.json5
├── sync.sh                       # 把 dist/vocab.html 同步进来
└── README.md
```

## 更新网页内容

每次改完 `web/app.template.html` 并重新构建后，在仓库根目录执行：

```bash
python3 tools/build.py
bash build.sh sync
bash harmony/sync.sh
```

`harmony/sync.sh` 会把最新的 `dist/vocab.html` 和图标复制到鸿蒙工程。
然后重新 Run / Build 即可。

## 发音说明

网页里的 `window.AndroidTTS` 由 `Index.ets` 通过 `javaScriptProxy` 注入，
方法名与 Android 版保持一致：

```text
ready() / speak(text) / stop() / setAccent(accent) / setRate(rate)
```

ArkTS 侧用 `@kit.CoreSpeechKit` 的 `textToSpeech` 实现。Core Speech Kit
官方只标注中文，但英文文本可以直接朗读；它需要真机，且首次创建引擎是异步的。
网页仍会先尝试在线高清音频（有道单词、Google 整句），失败后再回退到
`AndroidTTS`；如果系统 TTS 也不可用，最后回退到 Web Speech API（如果
ArkWeb 支持）。

## 已知限制

- 本机没有 SDK，**未编译、未签名、未上架**；需要 DevEco Studio + 华为开发者账号。
- `rawfile/vocab.html` 是构建产物，约 7 MB；更新网页后要重新执行 `harmony/sync.sh`。
- 本地页面里的 PWA Service Worker 不会像浏览器一样工作，应用本身不依赖它。
- 在线高清发音需要网络和 `ohos.permission.INTERNET`；国内网络访问 Google 可能失败，
  此时会回退到系统语音。
- 目前是 WebView 壳，状态栏/导航栏使用系统默认样式；如需沉浸式，可在
  `EntryAbility.onWindowStageCreate` 里加窗口全屏配置。

## 版本

- 网页/Android 对应版本：`0.12.1`
- HarmonyOS 工程：`versionCode 19` / `versionName 0.12.1`
- bundleName：`com.supercell.wordbook`
