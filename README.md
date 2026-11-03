# 词书 · WordBook

一个给中学生用的背单词应用：**单文件网页**，可以离线用、可以装成 App、可以接一个班级服务器让老师看进度。

- 词库：中考、高考、四级、六级、雅思、托福 + 上海中考、上海高考，共约 **12,115** 词
- 每组 20 词，先中英对照熟悉，再只显示英文、点「掌握 / 不熟」
- 已背词本：按组复习、跨组随机重组复习
- 间隔重复（SRS）、生词本、每日目标与连续打卡、拼写自测
- 例句中英对照 + 系统语音朗读（音节划分、同族词、音标）
- 学生端把进度推给老师端，老师可以看班级概览、布置任务、AI 点评
- Android APK、iOS（PWA / Xcode 工程）双端

![答题页](docs/screenshots/shot-v2-quiz.png)

## 目录结构

```
web/            应用源码（单文件模板 + PWA 清单/Service Worker/图标）
dist/vocab.html 构建产物：把 12115 个词和例句全部塞进一个 HTML（约 2.5MB）
tools/          词库与例句的构建、翻译脚本（Python）
data/           小体积数据文件（词表、例句、译文），说明见 data/README.md
server/         班级服务器（零依赖 Node）+ 老师管理端 + 部署脚本
android/        Android APK 工程（aapt2/d8/apksigner 手工打包，无需 Gradle）
ios/            iOS 工程（XcodeGen 项目 + WKWebView + AVSpeechSynthesizer）
tests/          jsdom 功能测试（123 项）+ Playwright 布局/截图脚本
docs/           文档与截图
```

## 快速开始

### 只想用网页

直接打开 `dist/vocab.html` 就能背单词（双击即可，不需要联网、不需要服务器）。

### 重新构建词库

```bash
pip install -r tools/requirements.txt
curl -L -o data/ecdict.csv \
  https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv
./build.sh          # build + sync：生成 dist/vocab.html 并同步到 server/android/ios
```

### 起一个班级服务器

```bash
cd server
node server.js                      # 首次启动会打印初始老师密码
# 浏览器打开 http://localhost:8787       学生端
# 浏览器打开 http://localhost:8787/admin 老师端
```

环境变量：`PORT`、`ADMIN_USER`、`ADMIN_PASS`、`DATA_DIR`、`LLM_URL`、`LLM_KEY`、`LLM_MODEL`（后三个用于 AI 点评，不配则用本地规则生成）。

部署到云服务器（Node + systemd + 可选 Caddy HTTPS）：

```bash
sudo bash server/deploy.sh --domain example.com
```

### 打 Android APK

```bash
sudo apt-get install -y openjdk-17-jdk-headless aapt zipalign
bash android/build.sh           # 产物：android/wordbook.apk
```

### 打 iOS

iOS 不能侧载，仓库提供两条路：

1. **PWA**：把 `server/` 部署到 https 域名，Safari 打开后「分享 → 添加到主屏幕」，得到全屏 App（已做 Service Worker 离线缓存）
2. **Xcode 工程**：`ios/` 目录，Mac 上 `xcodegen generate && open WordBook.xcodeproj`，填好签名即可真机运行

## 测试

```bash
cd tests
npm install                     # jsdom + playwright-core
node test.js                    # 123 项功能断言
node layout.js                  # 用 Chromium 量各页面边界，检查横向溢出
```

## 文档

- [使用说明](docs/使用说明.md) — 学生怎么背、老师怎么看
- [部署指南](docs/部署指南.md) — 从零部署到一台云服务器
- [架构说明](docs/架构.md) — 数据流、状态结构、接口清单
- [data/README.md](data/README.md) — 词库与例句的来源、许可、格式

## 数据与许可

代码以 MIT 发布（见 [LICENSE](LICENSE)）。词库和例句来自第三方，各自的许可见 [data/README.md](data/README.md)：ECDICT（MIT）、上海高考开放词库（CC BY 4.0）、Tatoeba（CC BY 2.0 FR）、OPUS News-Commentary（非商业学习用途）。上海中考词汇表原表版权归上海市教委 / 上海教育出版社，本仓库仅随附抽取后的词表供个人学习。

## 已知限制

- 约 305 个生僻词只有英文例句、没有中文翻译（不影响背单词，卡片上会只显示英文句）
- 雅思/托福词库是社区整理版，不是官方词表
- iOS 版需要 Mac 签名才能在真机安装；没有 Mac 的学生用 PWA 即可
- 班级服务器默认用 HTTP，正式使用请配 HTTPS（`deploy.sh --domain` 会自动配 Caddy）
