# data/ 数据说明

仓库里只放**体积小、可再生成**的数据；66MB 的 `ecdict.csv` 不入库，按下面说明自行下载。

## 词库来源

| 文件 | 内容 | 来源 | 许可 |
| --- | --- | --- | --- |
| `ecdict.csv`（不提交） | 77 万词条，含音标、释义、BNC/COCA 词频、考试标签 | [skywind3000/ECDICT](https://github.com/skywind3000/ECDICT) | MIT |
| `sh_zk.json` | 上海中考词汇 1610 条（词 + 词性 + 释义） | 《上海市初中英语词汇表（2020 年版）》，PDF 取自 [mahavivo/english-wordlists](https://github.com/mahavivo/english-wordlists) | 原表版权归上海市教委/上海教育出版社，仅作个人学习用途 |
| `sh_gk.json` | 上海高考开放词库 8561 条（scope=0 为核心 6465 条） | [gk.openerp.cn/atlas](https://gk.openerp.cn/atlas/index.json) | CC BY 4.0 |
| `tem4.tsv` | 专四 4,025 词（词 + 中文释义） | [Qwerty Learner](https://github.com/RealKai42/qwerty-learner) `Level4luan_2_T.json` | GPL-3.0 |
| `tem8.tsv` | 专八 12,197 词（与专四重叠 3,942） | 同上 `Level8luan_2_T.json` | GPL-3.0 |
| `catti.tsv` | CATTI 三级口译常用词汇，过滤后 3,111 条术语/短语 | [sherylling1986-beep/catti-vocabulary](https://github.com/sherylling1986-beep/catti-vocabulary) | 上游未声明，商用前请核对 |

`tools/build.py` 用 ECDICT 的 tag 字段（`zk/gk/cet4/cet6/ky/ielts/toefl`）切出中考、高考、四级、六级、考研、雅思、托福七个词库，合并上海两个词库，再用 `tem4/tem8/catti` 外挂词表补词库位；去重去停用词后共 **18,337** 词。

由于 ETS / British Council 从未发布官方 IELTS/TOEFL 词表，这里的雅思、托福词库来自 ECDICT 的 `ielts`、`toefl` 标签，属于社区整理版本。

## 例句数据

| 文件 | 内容 |
| --- | --- |
| `examples.json` | 每个词的例句 `{word: {e: 英文句, c: 中文}}`，Tatoeba 优先、News-Commentary 兜底 |
| `examples_new.json` | 第二批补的例句（`expand_examples.py` 产出） |
| `translations.json` / `translations_new.json` | 机器翻译补充的中文译文 |
| `todo_translate.json` / `todo_new.json` | 待翻译清单 |
| `nosent_out_*.json` | 没有语料可用的 470 个生僻词，人工/模型补写的例句 `{word: [英文, 中文]}` |
| `hand_examples.json` | 手工校对过的例句，优先级最高 |

合并顺序（`tools/build.py`）：
`hand_examples.json` > `nosent_out_*.json` > `examples_new.json` > `examples.json` + `translations*.json`

例句语料许可：

- [Tatoeba](https://tatoeba.org) — CC BY 2.0 FR（英文句、中文句、句对链接）
- [OPUS News-Commentary](https://opus.nlpl.eu/News-Commentary.php) — 仅用于非商业学习用途
- 其余机器翻译与人工补写部分随本项目一起以 MIT 发布

## 重新生成

```bash
# 1. 下载 ECDICT
curl -L -o data/ecdict.csv \
  https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv

# 2. 安装依赖
pip install -r tools/requirements.txt

# 3. 构建（生成 dist/vocab.html）
./build.sh build
```

音标、音节（pyphen）、同族词（WordNet）都在构建时算好写进 HTML，运行时不依赖任何网络或第三方库。
