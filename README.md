<div align="center">

# 📖 词书

**一个能自己留着、也能发给学生的背单词应用**

词库自己建 · 数据全在本地 · 服务器只帮你收作业

[![词库](https://img.shields.io/badge/%E8%AF%8D%E5%BA%93-12%2C115%20%E8%AF%8D-2ea44f?style=for-the-badge)](https://github.com/Supercell023/wordbook)
[![单文件](https://img.shields.io/badge/%E5%8D%95%E6%96%87%E4%BB%B6-5.6MB-1f6feb?style=for-the-badge)](https://github.com/Supercell023/wordbook/releases)
[![测试](https://img.shields.io/badge/%E6%B5%8B%E8%AF%95-186%20%E9%A1%B9%E9%80%9A%E8%BF%87-brightgreen?style=for-the-badge)](https://github.com/Supercell023/wordbook)
[![CI](https://github.com/Supercell023/wordbook/actions/workflows/ci.yml/badge.svg)](https://github.com/Supercell023/wordbook/actions/workflows/ci.yml)
[![平台](https://img.shields.io/badge/%E5%B9%B3%E5%8F%B0-Android%20%C2%B7%20iOS%20%C2%B7%20Web-8957e5?style=for-the-badge)](https://github.com/Supercell023/wordbook)
[![许可](https://img.shields.io/badge/%E8%AE%B8%E5%8F%AF-MIT-yellow?style=for-the-badge)](LICENSE)

</div>

<div align="center">

<img src="docs/screenshots/shot-home.png" width="22%" alt="首页">
<img src="docs/screenshots/shot-preview.png" width="22%" alt="熟悉单词">
<img src="docs/screenshots/shot-card.png" width="22%" alt="词卡">
<img src="docs/screenshots/shot-v2-quiz.png" width="22%" alt="答题">
<br>
<img src="docs/screenshots/shot-dark.png" width="44%" alt="暗夜模式">
<img src="docs/screenshots/shot-fx.png" width="44%" alt="完成奖励">
<br><sub>暗夜模式 · 完成奖励</sub>
<br>
<img src="docs/screenshots/shot-listen.png" width="30%" alt="听音选义">
<img src="docs/screenshots/shot-cloze.png" width="30%" alt="例句填空">
<img src="docs/screenshots/shot-wrong.png" width="30%" alt="错题本">
<br><sub>听音选义 · 例句填空 · 错题本</sub>

</div>

---

## ✨ 它有什么不一样

| | 市面上的背单词软件 | 词书 |
|---|---|---|
| 词库 | 平台定，改不了 | **自己建**：中考/高考/四级/六级/雅思/托福 + 上海中考/上海高考 |
| 学习数据 | 存在别人服务器上 | **全在本地**，断网也能背，导出就是一份 JSON |
| 分组 | 算法决定，你只能跟着走 | **一组 20 词，全部点「掌握」才算过**，不熟的本组重考 |
| 复习 | 只能按它安排的来 | **按原组复习**，或**跨组随机重组 20 词** |
| 词条 | 一两个中文意思，词性写「名/动」 | **多义项 + 英文词性 + 英英释义 + 词形变化 + 近反义词 + 柯林斯星级** |
| 查词 | 只能按词表一页页翻 | 首页 🔍 **英文 / 中文都能查**；同族词、近反义词在词卡里都能继续点 |
| 老师 | 买班级版才行 | **自带一个零依赖服务器**：激活码绑定、进度推送、AI 点评 |
| 隐私 | 学生数据进平台 | 只收昵称和进度，**不收集任何个人信息** |

## 🎯 怎么背的

```text
选词库 ─▶ 一组 20 词 ─▶ 中英文整体熟悉一遍
                          │
                          ▼
              随机抽一个英文，只有两个按钮
                  ┌───────────┐  ┌───────────┐
                  │  掌握 ✅  │  │  不熟 ✖   │
                  └─────┬─────┘  └─────┬─────┘
                        │              │
                  出队，不再考     放回本组队尾，再考
                        │              │
                        └──────┬───────┘
                               ▼
                  20 个全点过掌握 ─▶ 写入「已背词本」
                                          │
                       ┌──────────────────┴──────────────────┐
                       ▼                                     ▼
              按原组复习（可随机选组）              跨组随机重组 20 词
```

点开释义之后还有：**中英对照例句**、**音节划分**（ap·pear）、**同族词**（appear → appearance n.）、**词形变化**（book → booked / books）、**近反义词**；同族词和近反义词都可以继续点开看释义。单词旁边有 🔊 朗读。

界面用**宋体 + Times New Roman** 的书卷排版，支持**浅色 / 暗夜 / 跟随系统**、**字号（标准/大/特大）和高对比度**；复习完一天的任务会随机撒星星、花瓣或烟花。

发音也做了升级：默认走**高清联网音色**（单词用有道、整句用 Google 翻译语音，只发送当前内容，可在设置里关），可切**美音/英音**和**慢/标准/快**；关掉后完全用系统 TTS，离线可用。整句高清需要能访问 Google，失败会自动回退系统语音。

学完一组不是结束：**每个词有自己的复习间隔**（ease、连对次数、遗忘次数），答错的词会降间隔、优先回炉；首页能看到**未来 7 天到期预测**和**薄弱词**。练习除了认词，还有**听音选义**、**例句填空**、**拼写自测**；答错/拼错自动进**错题本**，按错误类型（认词/听音/填空/拼写）记录。词卡里可以看完全部义项、英英释义、词形、近反义和同族词，同族词之间能一层层点进去，再用「‹」返回上一个词；搜索会保留最近查过的词。

## 🚀 三种用法，挑一个

### ① 一个 HTML 文件（最省事）

下载 [Releases](https://github.com/Supercell023/wordbook/releases) 里的 `vocab.html`，双击就能背。不联网、不安装、数据存在浏览器里。

### ② 安卓安装包

下载 Releases 里的 `wordbook.apk`，或直接下载仓库中的 [android/wordbook.apk](android/wordbook.apk)（v0.10.0）安装。内置原生语音（Android TextToSpeech），比网页版发音更稳。

### ③ 安装成 PWA（iPhone / Android 推荐）

把 `server/` 部署到一台 **https** 服务器（或在本机用 `http://localhost` 调试）。Android Chrome 打开后会弹出「安装应用」，iPhone Safari 用「分享 → 添加到主屏幕」。安装后全屏、可离线、能发音。

- PWA 要求 **HTTPS 或 localhost**；局域网 `http://192.168.x.x` 浏览器不允许安装。
- 构建时跑 `./build.sh all`，会生成图标、同步 manifest / sw / icons 到四个端，并自校验。
- 详细排查见 [部署指南](docs/部署指南.md) 第八节。

## 🗂 词库

| 词库 | 词数 | 例句覆盖 |
|---|---:|---:|
| 中考 | 1,228 | 100% |
| 高考 | 3,296 | 100% |
| 四级 | 3,817 | 100% |
| 六级 | 5,391 | 100% |
| 考研 | 4,770 | 98.3% |
| 雅思 | 4,946 | 99.6% |
| 托福 | 6,949 | 95.1% |
| 上海中考 | 1,610 | 100% |
| 上海高考 | 6,135 | 100% |

（一个词可以属于多个词库，所以加起来不等于总数）

合计 **12,194** 词，例句覆盖 **96.5%**（11,773 条），同族词覆盖 **49.7%**（6,055 个），音节全部自动切分（8,891 个多音节词）。

> 雅思、托福没有官方词表（ETS 和英国文化协会都没发布过），这里用的是社区整理版，来自 ECDICT 的考试标签。

## 🏗 架构

```text
  ECDICT ─┐
  上海中考 ─┼─▶ tools/build.py ─▶ dist/vocab.html（5.6MB 单文件）
  上海高考 ─┤        │                  ├─▶ 浏览器直接打开
  Tatoeba ─┘        │                  ├─▶ server/public ─▶ 学生手机
  WordNet ──────────┘                  ├─▶ android/assets ─▶ APK
                                       └─▶ ios/Resources ─▶ WKWebView

  学生端（localStorage）──手动推送──▶ server.js ──▶ 老师端 admin.html
                                         │
                                         └──▶ 大模型 / 本地规则 ─▶ AI 点评
```

- **不需要数据库**：老师端数据就是一个 `db.json`
- **不需要后台常驻进程**：学习过程纯前端，服务器挂了也能背
- **不需要 Gradle**：APK 用 `aapt + javac + d8 + apksigner` 手工打

## 🛠 本地构建

```bash
# 词库（需要 Python 3.10+）
pip install -r tools/requirements.txt      # 或 pip install pyphen nltk
bash tools/fetch_data.sh                   # 下载 data/ecdict.csv（约 66MB，已有则跳过）
./build.sh                                 # 生成 dist/vocab.html 并同步到各端

# 安卓
sudo apt-get install -y openjdk-17-jdk-headless aapt zipalign
bash android/build.sh                      # 产物 android/wordbook-<版本>-debug.apk + wordbook.apk
# release 签名见 docs/部署指南.md 第十一节（WORDBOOK_KEYSTORE 等四个环境变量）

# 测试
cd tests && npm ci && node test.js
```

`tools/fetch_data.sh` 支持 `--force` 强制重下，也可用 `ECDICT_URL=...` 指定镜像；下载会先校验大小和表头再原子替换，不会留下半截 CSV。

CI 见 [`.github/workflows/ci.yml`](.github/workflows/ci.yml)：push 到 `main`/`master`、Pull Request 或手动触发时，自动准备 Node 20 / Python 3.12、下载词库、构建、`sync` + `verify` 并跑功能测试，产物（`dist/vocab.html`、已提交的 `android/wordbook.apk`）在 Actions 的 `wordbook-build` artifact 里。CI 不装 Android SDK，APK 仍需本地打包。

## 👩‍🏫 班级版：老师能看什么

```bash
cd server && node server.js
# 学生端  http://localhost:8787/
# 老师端  http://localhost:8787/admin
```

老师端是一个适配手机的网页：

- **学生总览**：班级人数、今日已学、平均正确率、需关注人数；近 7 天学习量柱状图与班级高频错词
- **学生卡**：今日/目标进度、连续天数、正确率、待复习、累计分钟、未读作业、高频错词、风险提示（未上传 / 掉队 / 今日未学 / 正确率低 / 复习积压）
- **详情**：7 天趋势、9 项指标、练习构成（认词 / 听音 / 填空 / 拼写）、最近练习、作业回执、老师备注
- **筛选与导出**：按今日未学、需关注、作业未读、低正确率、未上传筛选；一键导出 CSV（含备注与作业状态）
- **激活码**：一次生成一批，一人一码，绑定即作废
- **布置**：下发任务和留言，学生下次同步时收到；能看到已读/未读、逾期人数，可删除
- **点评**：接入 DeepSeek / MIMO 等任意 OpenAI 兼容接口，没配就用本地规则分析

学生端「上传」按钮在**没有新数据时是灰的**，前后端双重去重，防止乱推。

部署到云服务器：

```bash
sudo bash server/deploy.sh --domain wb.example.com
```

自动装 Node、注册 systemd、配 Caddy 和 HTTPS。详细步骤看 [部署指南](docs/部署指南.md)。

## ✅ 测试

- **188 项功能断言**：用 jsdom 真实加载 `dist/vocab.html`，模拟点击走完学习、复习、生词本、拼写、迁移、多义项、词卡、主题、搜索与奖励等全部流程
- **布局检查**：用 Chromium 量每个页面的元素边界，保证 390px 手机宽度下没有横向溢出
- **服务器测试**：34 项接口断言（激活码、去重、越权、伪造令牌、老师备注、作业回执、CSV 导出）

## 📚 文档

- [使用说明](docs/使用说明.md) —— 学生怎么背、老师怎么看
- [部署指南](docs/部署指南.md) —— 从零到一台能用的服务器
- [架构说明](docs/架构.md) —— 数据结构、分组算法、接口清单
- [竞品调研](docs/竞品调研.md) —— 同类 App 的特色、槽点与本项目的取舍
- [内容质量报告](docs/内容质量报告.md) —— 义项清洗、词性回填、例句筛选的数字与遗留风险
- [数据来源](data/README.md) —— 每个文件从哪来、什么许可

## 📜 许可

代码 [MIT](LICENSE)。词库和例句来自第三方，各自的许可见 [data/README.md](data/README.md)：ECDICT（MIT）、上海高考开放词库（CC BY 4.0）、Tatoeba（CC BY 2.0 FR）。

上海中考词汇表原表版权归上海市教委 / 上海教育出版社，仓库里只随附抽取后的词表，供个人学习使用。如果权利人认为不妥，提一个 issue，我会立即移除。
