# 单词本 · 班级版（学生端 + 老师端 + 中继服务器）

一个老师、十来个学生的私有背单词系统。学生离线背词，手动把进度推到自己的服务器；老师在手机浏览器里看全班情况、发任务、让大模型写点评。

## 目录

| 文件 | 作用 |
|---|---|
| `server.js` | 中继服务器（零依赖，Node 18+） |
| `admin.html` | 老师端网页（手机适配） |
| `public/vocab.html` | 学生端网页（手机适配，可离线用） |
| `apk/wordbook.apk` | Android 客户端（内嵌同一份网页，离线可背） |
| `test.js` | 服务器接口自测（25 项） |
| `data/` | 运行后自动生成：数据库、签名密钥 |

## 一、部署（5 分钟）

1. 租一台最便宜的云服务器（1 核 1G 就够，Ubuntu 22.04/24.04）。
2. 把整个目录传上去，装 Node 18+：
   ```bash
   sudo apt update && sudo apt install -y nodejs
   ```
   或按 NodeSource 装新版。
3. 启动（首次会打印老师初始密码）：
   ```bash
   cd 单词本班级版
   ADMIN_USER=teacher ADMIN_PASS=你的密码 node server.js
   ```
   首次启动输出的那一行 `初始老师账号： teacher / xxxxxx` 记下来。
4. 放行端口（云厂商安全组 + 防火墙都要）：
   ```bash
   sudo ufw allow 8787/tcp
   ```
5. 浏览器打开：
   - 学生：`http://服务器IP:8787/student.html`
   - 老师：`http://服务器IP:8787/admin`

> 想长期跑：`nohup node server.js > server.log 2>&1 &` 或配 systemd。
> 有域名的话建议套一层 Caddy/Nginx 做 HTTPS（iOS 对 http 的支持越来越差）。

## 二、老师怎么用

1. 打开 `/admin`，用初始密码登录。
2. 「激活码」标签 → 生成，比如 5 个 → 每个学生分一个（一次性，绑定后作废）。
3. 把 **服务器地址 + 激活码** 发给学生。
4. 「学生」标签看全班：谁上传了、学了几组、首次正确率、错词排行。
5. 点「详情」→ 看正确率走势、每次上传记录、错词清单 →「AI 点评」生成一段建议。
6. 「布置」标签下发任务/消息，学生下次同步时能在首页看到。

## 三、学生怎么用

**网页版**：手机浏览器打开服务器地址，直接背；设置里填激活码绑定。

**App 版**：安装 `apk/wordbook.apk`（或从学生页的设置里点「下载 App」）。
- 背词完全离线，数据只存在手机里；
- 要上传时：首页点「有新的学习数据」→ 或设置 →「上传进度」；
- 上传成功会显示 `已上传 ✓`；**没有新数据时按钮会变灰**，不会重复推送。

## 四、大模型点评（可选）

默认用服务器本地规则生成点评，不花钱也能用。要换成真 AI：

```bash
LLM_KEY=sk-xxxx LLM_URL=https://api.deepseek.com/chat/completions LLM_MODEL=deepseek-chat node server.js
```

- DeepSeek：`https://api.deepseek.com/chat/completions`，模型 `deepseek-chat`
- 通义/智谱/MIMO 等：填对应 OpenAI 兼容地址和模型名即可
- 没配 key 或调用失败会**自动退回本地规则**，不影响使用
- 建议在老师端「手动点一次生成一次」，避免 token 浪费

## 五、接口一览（改客户端时用）

```
POST /api/s/bind        {code, name, device}        -> {token, studentId, name}
POST /api/s/push        {hash, data}   (Bearer)     -> {ok, at}；相同 hash 返回 409
GET  /api/s/inbox       (Bearer)                    -> 任务 + 消息
POST /api/s/ack         {id}            (Bearer)

POST /api/t/login       {user, pass}                -> {token}
GET  /api/t/overview    (Bearer)                    -> 学生列表 + 最新摘要
GET  /api/t/student/:id (Bearer)                    -> 上传历史
GET/POST /api/t/codes   (Bearer)                    -> 激活码列表 / 生成
POST /api/t/assign      {title, text, due, target}  (Bearer)
POST /api/t/message     {text, target}              (Bearer)
POST /api/t/analyze     {studentId}     (Bearer)    -> {text, source: llm|local}
GET  /api/t/log         (Bearer)                    -> 最近动态
```

## 六、数据与安全

- 令牌是 HMAC 签名的，密钥在 `data/secret`（别泄露、别提交到公开仓库）
- 激活码一次性，绑定设备后不能再用
- 上传按「数据指纹」去重：学习状态没变，服务器直接拒绝（409）
- 学生数据只存昵称、组次、错词、正确率，不存真实姓名（建议让学生填昵称）
- 备份：直接备份整个 `data/` 目录
- 建议每学期重置一次：删 `data/db.json` 重新生成（会清空所有学生）

## 七、自测

```bash
node test.js            # 服务器 25 项接口测试
```

## 八、已知限制

- APK 是 demo 包（debug 签名），正式分发要换正式签名并加固
- 网页版与 App 版的数据**不互通**：App 内嵌网页，浏览器里的是另一份 localStorage；换设备请用设置里的「导出备份」
- 目前没有 HTTPS，公网使用时注意别在公共 WiFi 下传数据

## 六、一键部署（可选，推荐）

不想手动装 Node / 配 systemd，用附带脚本：

```bash
sudo bash deploy.sh                                # HTTP，端口 8787
sudo bash deploy.sh --domain wb.example.com        # 自动装 Caddy 配 HTTPS（需域名已解析）
sudo bash deploy.sh --password '你的密码'          # 指定老师初始密码
```

脚本会：装 Node 22 → 拷到 `/opt/wordbook` → 生成 `/etc/wordbook.env`（端口、账号密码、数据目录、大模型配置）→ 注册 systemd 服务 `wordbook` →（可选）装 Caddy 自动申请证书 → 放行防火墙。重复执行只更新程序，`data/` 里的数据保留。

常用运维：

```bash
systemctl status wordbook     # 看状态
systemctl restart wordbook    # 改完 /etc/wordbook.env 后重启
journalctl -u wordbook -f     # 看日志
```

## 七、学生端功能（v3 新增）

- **今日复习（间隔重复）**：每个学过的词按 1/2/4/7/15/30 天安排下次复习，到期后首页出现「🔁 今日复习 N 个词到期」，答错回到 1 天。
- **生词本**：答错自动收录（可在设置关闭），也能手动点 ☆ 收藏；生词本可单独复习，不写进已背组。
- **每日目标与连续打卡**：首页显示「🔥 连续 N 天 · 今日 x/20 词」，目标可在设置里改 10/20/30/50。
- **拼写自测**：首页「⌨️ 拼写自测」，看中文写英文，20 词一局，不认识的会自动进生词本。
- **APK 发音修复**：安卓版改用系统 TextToSpeech（WebView 原生不支持网页语音），网页版仍用浏览器语音。
- **取消组不再跳号**：新开一组没背就退出，组号会回收，下一个还是第 1 组。

## 八、iOS 学生端

iOS 没有「发个安装包就能装」这回事，两条路：

1. **PWA（推荐，零成本）**：服务器配好 HTTPS（`deploy.sh --domain 你的域名`），学生在 iPhone Safari 打开
   `https://你的域名/student.html` → 分享 → **添加到主屏幕**。全屏、离线可背、升级即刷新。
2. **原生 App（要 Mac）**：`ios/` 目录是 XcodeGen 工程，`xcodegen generate` 后用 Xcode 签名安装；
   免费 Apple ID 7 天有效期，付费开发者账号可走 TestFlight 分发给全班。详见 `ios/README.md`。
