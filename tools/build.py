#!/usr/bin/env python3
# 构建词库：ECDICT（中考/高考/四级/六级/雅思/托福）+ 上海中考/高考，生成 vocab.html
# 数据列（15 列）：
#  0 单词 1 音标 2 词库位 3 难度 4 词频 5 例句 6 音节 7 同族词
#  8 义项 [[词性, [中文义...]], ...]  9 专业义 [[领域, [义...]], ...]
# 10 英英释义 [[词性, 英文释义], ...]  11 词形 [[中文标签, 词形], ...]
# 12 柯林斯星级  13 近义词  14 反义词
import csv, json, re, sys, os, math, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SRC = os.path.join(DATA, "ecdict.csv")
TPL = os.path.join(ROOT, "web", "app.template.html")
OUT = os.path.join(ROOT, "dist", "vocab.html")
BITS = {"zk": 1, "gk": 2, "cet4": 4, "cet6": 8, "ky": 256, "tem4": 512, "tem8": 1024,
        "catti": 2048, "ielts": 16, "toefl": 32, "sh-zk": 64, "sh-gk": 128}
LEVEL = ["zk", "sh-zk", "gk", "sh-gk", "cet4", "cet6", "ky", "tem4", "tem8", "ielts", "toefl", "catti"]
# 外挂词表：专四/专八/CATTI。词本身在 ECDICT 里时只加词库位，不改 ECDICT 释义；
# 不在 ECDICT 里的短语/术语，用词表自带中文释义补一条。
EXTRA_BITS = {"tem4": 512, "tem8": 1024, "catti": 2048}
BASE = DATA

# 功能词 / 极基础词：学习者都会，放进词库只会浪费前几组
STOP = set("""
the a an and or but if of to in on at by for with from into onto about as than then so
such not no nor be is am are was were been being do does did doing done have has had
having will would shall should can could may might must need ought i me my mine you your
yours he him his she her hers it its we us our ours they them their theirs this that these
those who whom whose which what when where why how there here all any some both each every
few many much more most other another same own very too also just only even still yet again
ever never always often sometimes up down out off over under above below between among
through during before after since until while because although though unless whether one two
three first second last next now well god sir madam etc ok okay yeah yes hi hello bye please
thanks thank

say said go went get got make made know knew see seen take took give gave come came think
thought tell told look want use find found work put let keep begin seem help show hear play
run move live believe bring happen write sit stand lose pay meet include continue learn
change lead understand watch follow stop create speak read allow add spend grow open walk
win offer remember love consider appear buy wait serve die send expect build stay fall cut
reach kill remain hold turn start try call

time year people good new like day days man men woman women life world hand part place
thing way school house home water food night morning family friend mother father book name
number money city country car road tree sun moon star sky sea river mountain animal dog cat
bird fish head eye ear nose mouth face hair arm leg foot body heart boy girl son daughter
brother sister doctor teacher student class room door window table chair bed paper pen
letter word line page story music game sport ball color red blue green black white big
small long short old young hot cold warm cool fast slow easy hard happy sad tired hungry
busy free right wrong true false same different important interesting beautiful nice fine
great little large high low near far early late quick ready sure able afraid angry glad
welcome holiday weekend birthday breakfast lunch dinner afternoon evening today tomorrow
yesterday week month hour minute
""".split())

# ECDICT 词性缩写 → 标准英文缩写
POS_MAP = {
    "n": "n.", "n.": "n.",
    "v": "v.", "v.": "v.",
    "vt": "vt.", "vt.": "vt.",
    "vi": "vi.", "vi.": "vi.",
    "a": "adj.", "a.": "adj.", "adj": "adj.", "adj.": "adj.", "s": "adj.", "s.": "adj.",
    "ad": "adv.", "ad.": "adv.", "adv": "adv.", "adv.": "adv.",
    "prep": "prep.", "prep.": "prep.",
    "conj": "conj.", "conj.": "conj.",
    "pron": "pron.", "pron.": "pron.",
    "num": "num.", "num.": "num.",
    "art": "art.", "art.": "art.",
    "int": "interj.", "int.": "interj.", "interj": "interj.", "interj.": "interj.",
    "phr": "phr.", "phr.": "phr.",
}

# 专业领域标签（[计] → 计算机）
DOMAIN_CN = {
    "计": "计算机", "法": "法律", "律": "法律", "医": "医学", "化": "化学", "经": "经济",
    "商": "商业", "电": "电子", "物": "物理", "数": "数学", "机": "机械", "军": "军事",
    "农": "农业", "心": "心理", "哲": "哲学", "逻": "逻辑", "语": "语言", "生": "生物",
    "地质": "地质", "治": "政治", "体育": "体育", "音": "音乐", "美": "美术",
    "印": "印刷", "纺": "纺织", "建": "建筑", "海": "航海", "空": "航空",
}

FORM_LB = {"p": "过去式", "d": "过去分词", "i": "现在分词", "3": "第三人称单数",
           "s": "复数", "r": "比较级", "t": "最高级"}


def _split_items(body):
    return [x.strip(" .;；") for x in re.split(r"[,，;；]", body) if x.strip(" .;；")]


# ---- 义项清洗 ----------------------------------------------------------
STATS = {"sense_drop": 0, "empty_pos": 0, "form_drop": 0, "fam_drop": 0,
         "ex_keep": 0, "ex_replaced": 0, "ex_bad": 0, "ex_added": 0}

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
# 纯标点/纯符号：既没有汉字也没有字母数字
_PUNCT_ONLY = re.compile(r"[^\w\u4e00-\u9fff]+")
# “见color / 同colour / 参见 go” 这类纯索引义项（要求索引目标是拉丁词，
# 避免误删“见闻/同感/参见”这类有实义的词）
_INDEX_RE = re.compile(r"^(见|同|另见|参见|见词|同上|see\s+also|same\s+as|variant\s+of)"
                       r"\s*[:：]?\s*[A-Za-z][A-Za-z' \-]{1,20}$", re.I)


def _norm_key(s):
    """大小写/标点/空白不敏感的归一化 key，用于去重与查重。"""
    return re.sub(r"[\W_]+", "", (s or "").lower(), flags=re.UNICODE)


def clean_item(it):
    it = re.sub(r"\s+", " ", (it or "")).strip()
    return it.strip(" .;；,，、:：·|")


def sense_noise(it):
    """True = 该义项是噪声，应丢弃。只拦明显坏的，误删风险高的规则一律收紧。"""
    if not it:
        return True
    if not _CJK_RE.search(it) and not re.search(r"[A-Za-z0-9]", it):
        return True                      # 纯标点 / 纯符号
    if _PUNCT_ONLY.fullmatch(it):
        return True
    if len(it) > 60 and not _CJK_RE.search(it):
        return True                      # 超长且无中文：多半是英文残句
    if _INDEX_RE.match(it):
        return True                      # “见xxx / 同xxx” 纯索引
    if it in ("—", "——", "-", "?"):
        return True
    return False


def clean_senses(senses, max_items=9):
    """义项清洗：去噪声、同词性内去重（大小写/标点不敏感）、合并重复词性组。
    保持 ECDICT 原行顺序，不重排、不臆造。返回 (清洗后 list, 丢弃条数)。"""
    out, idx, dropped = [], {}, 0
    for pos, items in (senses or []):
        p = re.sub(r"\s+", " ", (pos or "")).strip()
        pk = _norm_key(p)
        if pk and pk in idx:
            grp = out[idx[pk]]
        else:
            idx[pk] = len(out)
            grp = [p, []]
            out.append(grp)
        seen = {_norm_key(x) for x in grp[1]}
        seen.discard("")
        for it in items:
            c = clean_item(it)
            if sense_noise(c):
                dropped += 1
                continue
            k = _norm_key(c)
            if not k or k in seen or len(grp[1]) >= max_items:
                dropped += 1 if (not k or k in seen) else 0
                continue
            seen.add(k)
            grp[1].append(c)
    return [g for g in out if g[1]], dropped


def parse_senses(tr, max_sense=6, max_items=9):
    """把 ECDICT 的 translation 拆成 [[词性, [义项...]], ...] 与专业义。
    一个词可能有多行、多词性；义项内再用逗号/分号切开。"""
    t = (tr or "").replace("\\n", "\n").replace("\r", "\n")
    lines = [x.strip() for x in t.split("\n") if x.strip()]
    senses, spec = [], []
    for line in lines:
        # 跳过“run的过去式”这类词形注释，避免被当成一个义项
        if re.search(r"的(过去式|过去分词|现在分词|复数|比较级|最高级|第三人称单数)", line):
            continue
        m = re.match(r"^\[([^\]]+)\]\s*(.+)$", line)
        if m:
            if len(spec) < 3:
                items = _split_items(m.group(2))[:max_items]
                if items:
                    spec.append([DOMAIN_CN.get(m.group(1).strip(), m.group(1).strip()), items])
            continue
        m = re.match(r"^([A-Za-z]+\.?)\s*(.+)$", line)
        pos, body = "", line
        if m and m.group(1).lower() in POS_MAP:
            pos = POS_MAP[m.group(1).lower()]
            body = m.group(2)
        items = _split_items(body)[:max_items]
        if not items:
            continue
        # 合并同一词性的多行（常见于 n. 第一行 / n. 第二行）
        if senses and pos and senses[-1][0] == pos and len(senses[-1][1]) < max_items:
            for x in items:
                if x not in senses[-1][1] and len(senses[-1][1]) < max_items:
                    senses[-1][1].append(x)
        elif len(senses) < max_sense:
            senses.append([pos, items])
    senses, dropped = clean_senses(senses, max_items)
    STATS["sense_drop"] += dropped
    # 专业义也有同样的噪声问题，用同一套规则清洗（保留领域顺序）
    spec2 = []
    for dom, items in spec:
        keep, seen = [], set()
        for it in items:
            c = clean_item(it)
            if sense_noise(c):
                STATS["sense_drop"] += 1
                continue
            k = _norm_key(c)
            if not k or k in seen:
                STATS["sense_drop"] += 1
                continue
            seen.add(k)
            keep.append(c)
        if keep:
            spec2.append([dom, keep])
    return senses, spec2


_WN_POS_CACHE = {}


def wn_pos(w):
    """词性缺失时用 WordNet 首 synset 推断，统一英文缩写。"""
    k = w.lower()
    if k in _WN_POS_CACHE:
        return _WN_POS_CACHE[k]
    pos = ""
    try:
        from nltk.corpus import wordnet as wn
        ts = wn.synsets(k)
        if ts:
            pos = _POSEN.get(ts[0].pos(), "")
    except Exception:
        pass
    _WN_POS_CACHE[k] = pos
    return pos



def short_tr(senses, spec=None, limit=48):
    """给同族词/近反义词弹卡用的短释义。"""
    parts = []
    for pos, items in (senses or [])[:2]:
        s = "；".join(items[:3])
        parts.append((pos + " " if pos else "") + s)
    txt = "；".join(parts)
    if not txt and spec:
        txt = "；".join(spec[0][1][:3])
    txt = re.sub(r"\s+", " ", txt).strip()
    if len(txt) > limit:
        txt = txt[:limit].rstrip("；;，, ") + "…"
    return txt


def _norm_pos(p):
    """词性标注归一：只接受词表内的标准缩写，其它一律返回空，避免臆造。"""
    s = (p or "").strip()
    if not s:
        return ""
    if s.lower() in POS_MAP:
        return POS_MAP[s.lower()]
    if re.fullmatch(r"[A-Za-z]{1,6}\.?", s):
        return POS_MAP.get(s.lower().rstrip("."), "")
    return ""


def fill_pos(senses, defs, w, hint=""):
    """空词性回填：数据自带词性 → 英英释义词性 → WordNet；返回回填组数。
    只填空组，不改已有词性，保证不臆造。"""
    fp = _norm_pos(hint)
    if not fp:
        for p, _ in (defs or []):
            if p:
                fp = p
                break
    if not fp:
        fp = wn_pos(w)
    if not fp:
        return 0
    n = 0
    for s in senses:
        if not s[0]:
            s[0] = fp
            n += 1
    return n


def parse_defs(definition, max_defs=2, max_len=100):
    """英英释义：保留前 2 条，按词性带标签；避免单文件膨胀。"""
    d = (definition or "").replace("\\n", "\n").replace("\r", "\n")
    out = []
    for line in [x.strip() for x in d.split("\n") if x.strip()]:
        m = re.match(r"^([A-Za-z]+\.)\s*(.+)$", line)
        if m and m.group(1).lower() in POS_MAP:
            pos, body = POS_MAP[m.group(1).lower()], m.group(2)
        else:
            pos, body = "", line
        body = re.sub(r"\s+", " ", body).strip()
        if len(body) > max_len:
            body = body[:max_len].rstrip(" ,;") + "…"
        out.append([pos, body])
        if len(out) >= max_defs:
            break
    return out


def parse_forms(exchange, word):
    """exchange: d:abandoned/p:abandoned/i:abandoning/3:abandons → [[标签, 词形]]。
    过滤：空词形、与主词相同的词形、（标签,词形）重复项、非拉丁词形。"""
    out, seen = [], set()
    for part in (exchange or "").split("/"):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        v = (v or "").strip().strip(" .,;:·")
        if k not in FORM_LB or not v:
            continue
        if v.lower() == (word or "").lower():          # 与主词相同
            STATS["form_drop"] += 1
            continue
        if not re.fullmatch(r"[A-Za-z][A-Za-z'\-]*", v):  # 空/含中文/带标点的脏词形
            STATS["form_drop"] += 1
            continue
        pair = (FORM_LB[k], v.lower())
        if pair in seen:
            STATS["form_drop"] += 1
            continue
        if len(out) >= 6:
            break
        seen.add(pair)
        out.append([FORM_LB[k], v])
    return out


def clean_tr(t):
    """旧版清洗逻辑，仅用于解析失败时的兜底。"""
    t = t.replace("\\n", "\n").replace("\r", "\n")
    lines = [x.strip() for x in t.split("\n") if x.strip()]
    keep = [x for x in lines if not x.startswith("[")] or lines
    s = " / ".join(keep[:2])
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > 110:
        s = s[:110].rstrip("；;，, ") + "…"
    return s


try:
    import pyphen
    _HY = pyphen.Pyphen(lang="en_US")
except Exception:
    _HY = None


def syl_split(w):
    """音节切分：ap·pear / com·put·er；单音节原样返回"""
    if _HY is None:
        return w
    if " " in w:
        return " ".join(syl_split(x) for x in w.split(" "))
    if "-" in w:
        return "-".join(syl_split(x) for x in w.split("-"))
    try:
        return _HY.inserted(w, "·")
    except Exception:
        return w


_SUFFIX = ["ment", "ness", "ance", "ence", "tion", "sion", "ation", "ity", "er", "or", "ive",
           "al", "ial", "ous", "ious", "ful", "less", "ly", "ize", "ism", "ist", "ic", "able",
           "ible", "dom", "ship", "hood", "en"]
_POSEN = {"n": "n.", "v": "v.", "a": "adj.", "s": "adj.", "r": "adv."}

_IRREG = [(r"de$", "sion"), (r"mit$", "mission"), (r"cede$", "cession"), (r"ss$", "ssion"),
          (r"nd$", "nsion"), (r"y$", "ication")]


def _rule_cands(w, common):
    c = set()
    for pat, suf in _IRREG:
        m = re.search(pat, w)
        if m and len(w) > 5:
            stem = re.sub(pat, "", w)
            for t in (stem + suf, stem + "i" + suf, stem + "e" + suf):
                if t in common:
                    c.add(t)
    for s in _SUFFIX:
        stems = {w}
        if w.endswith("e"):
            stems.add(w[:-1])
        if w.endswith("y"):
            stems.add(w[:-1] + "i")
        for st in stems:
            x = st + s
            if x != w and x in common:
                c.add(x)
    for s in _SUFFIX:
        if w.endswith(s) and len(w) - len(s) >= 4:
            st = w[:-len(s)]
            for t in (st, st + "e", st + "y"):
                if len(t) >= 4 and t in common:
                    c.add(t)
            if st.endswith("i") and st[:-1] + "y" in common:
                c.add(st[:-1] + "y")
    return c


def _infl(c, common):
    """过滤 -ing/-ed/-s 之类的屈折形式（不是真正的派生词）"""
    for suf, base in (("ing", c[:-3]), ("ed", c[:-2]), ("s", c[:-1])):
        if c.endswith(suf) and len(base) >= 3 and (base in common or base + "e" in common):
            if suf != "s" or len(c) > 4:
                return True
    return False


def build_families(words, common, freq, posmap, NAMES):
    """同词族：后缀规则 + WordNet 派生链接（要求同前缀≥5），按词频排序取前 3"""
    from nltk.corpus import wordnet as wn
    vcache = {}

    def wn_valid(c):
        if c not in vcache:
            try:
                vcache[c] = bool(wn.synsets(c))
            except Exception:
                vcache[c] = False
        return vcache[c]

    out = {}
    for w in words:
        cands = {c for c in _rule_cands(w, common) if wn_valid(c)}
        try:
            for syn in wn.synsets(w):
                for l in syn.lemmas():
                    for d in l.derivationally_related_forms():
                        n = d.name().replace("_", " ").lower()
                        if " " in n or n == w or n not in common:
                            continue
                        k = 0
                        while k < min(len(n), len(w)) and n[k] == w[k]:
                            k += 1
                        if k >= 5:
                            cands.add(n)
        except Exception:
            pass
        # 标注词性（取该词自身最常见的词性，统一用英文缩写）
        cands = [c for c in cands if c != w and not _infl(c, common) and c not in NAMES]
        res, seen = [], set()
        for c in sorted(cands, key=lambda x: (freq.get(x) or 10 ** 7))[:3]:
            if c in seen:
                STATS["fam_drop"] += 1
                continue
            pos = posmap.get(c, "")
            if not pos:
                try:
                    ts = wn.synsets(c)
                    if ts:
                        pos = _POSEN.get(ts[0].pos(), "")
                except Exception:
                    pass
            seen.add(c)
            res.append([c, pos])
        if res:
            out[w] = res
    return out


def build_relations(words, common, freq, NAMES):
    """近义词 / 反义词：WordNet lemma，过滤屈折形式与超纲生僻词。"""
    from nltk.corpus import wordnet as wn
    out = {}

    def valid(n):
        return (bool(re.fullmatch(r"[a-z][a-z'\-]*", n)) and len(n) >= 3
                and n in common and (freq.get(n) or 10 ** 7) <= 30000
                and n not in NAMES and not _infl(n, common))

    for w in words:
        syns, ants = [], []
        try:
            for syn in wn.synsets(w)[:6]:
                for l in syn.lemmas():
                    n = l.name().replace("_", " ").lower()
                    if n != w and " " not in n and valid(n) and n not in syns:
                        syns.append(n)
                    for a in l.antonyms():
                        m = a.name().replace("_", " ").lower()
                        if m != w and " " not in m and valid(m) and m not in ants:
                            ants.append(m)
        except Exception:
            pass
        syns.sort(key=lambda x: (freq.get(x) or 10 ** 7, x))
        ants.sort(key=lambda x: (freq.get(x) or 10 ** 7, x))
        if syns or ants:
            out[w] = [syns[:3], ants[:2]]
    return out


def difficulty(d):
    """0=最容易, 1=最难：层级 45% + 词频 35% + 词长 10% + 义项数 10%"""
    lv = min(1.0, d["lvl"] * 0.3)
    f = d["freq"]
    fq = 1.0 if f >= 10 ** 7 else min(1.0, max(0.0, math.log(f) / math.log(30000)))
    ln = min(1.0, max(0.0, (len(d["w"]) - 4) / 8))
    sn = min(1.0, len(d["senses"]) / 4)
    return 0.45 * lv + 0.35 * fq + 0.10 * ln + 0.10 * sn


# ---- 例句筛选 ----------------------------------------------------------
def _hollow(t):
    """“暂无中文释义”“—”“n/a”这类空洞值。"""
    t = (t or "").strip()
    if not t:
        return True
    if t in ("—", "——", "-", "?", "暂无", "暂无中文释义", "无", "n/a", "N/A"):
        return True
    return not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", t)


def dedupe_zh(txt, sep="；"):
    """按分号合并重复片段（大小写/标点不敏感），保留首次出现的顺序。"""
    parts = [p.strip() for p in re.split(r"[；;]", txt or "") if p.strip()]
    out, seen = [], set()
    for p in parts:
        k = _norm_key(p)
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(p)
    return sep.join(out)


def infl_forms(word, forms=None):
    """“例句必须包含目标词”的匹配集合：主词 + 词形变化 + 常见屈折。"""
    base = (word or "").lower().strip()
    out = {base}
    for _lb, f in (forms or []):
        if f:
            out.add(f.lower())
    if re.fullmatch(r"[a-z][a-z'\-]*", base):
        out.update({base + "s", base + "'s", base + "ed", base + "ing",
                    base + "er", base + "est"})
        if base.endswith("e"):
            out.update({base + "d", base[:-1] + "ing",
                        base[:-1] + "er", base[:-1] + "est"})
        if base.endswith("y") and len(base) > 2:
            out.update({base[:-1] + "ies", base[:-1] + "ied",
                        base[:-1] + "ier", base[:-1] + "iest"})
        if re.search(r"(s|x|z|ch|sh)$", base):
            out.add(base + "es")
        if len(base) >= 3 and not re.search(r"[aeiou]$", base) and not base.endswith("y"):
            out.update({base + base[-1] + "ing", base + base[-1] + "ed",
                        base + base[-1] + "er"})
    return out


def check_example(e, forms):
    """硬规则：含目标词（含词形变化）、20–150 字符、≥4 词、不含中文。
    合格返回 token 列表，不合格返回 None。"""
    e = (e or "").strip()
    if not e or _CJK_RE.search(e):
        return None
    if not (20 <= len(e) <= 150):
        return None
    toks = re.findall(r"[a-z][a-z'\-]*", e.lower())
    if len(toks) < 4:
        return None
    if not any(t in forms for t in toks):
        return None
    return toks


def score_example(toks, e, common):
    """越小越好：生僻词更少 → 更短；完全同分时由调用方保持候选顺序。"""
    rare = sum(1 for t in toks if t not in common)
    return (rare, len(e))



def load_extras():
    """读取 data/{tem4,tem8,catti}.tsv。返回 {小写词: {w, mask, tr}}。
    同一词命中多个词表时合并 mask；释义优先取第一个非空。"""
    out = {}
    for name, bit in EXTRA_BITS.items():
        path = os.path.join(DATA, name + ".tsv")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                w = (parts[0] or "").strip()
                if not w or len(w) > 48:
                    continue
                k = w.lower()
                tr = (parts[1] if len(parts) > 1 else "").strip()
                cur = out.setdefault(k, {"w": w, "mask": 0, "tr": ""})
                cur["mask"] |= bit
                if not cur["tr"] and tr:
                    cur["tr"] = tr
    return out


def main():
    rows, allfreq = {}, {}
    extra = load_extras()
    # 先预载上海词库的键：这些词即使被 STOP 挡住，也要从 ECDICT 取丰富释义，
    # 但 mask 仍只保留上海词库位，避免改变原有词库数量。
    sh_need = set()
    _zkf = os.path.join(BASE, "sh_zk.json")
    if os.path.exists(_zkf):
        sh_need.update(str(k).lower() for k in json.load(open(_zkf, encoding="utf-8")).keys())
    _gkf = os.path.join(BASE, "sh_gk.json")
    if os.path.exists(_gkf):
        _gj = json.load(open(_gkf, encoding="utf-8"))
        _f = _gj["fields"]
        for _e in _gj["words"]:
            _d = dict(zip(_f, _e))
            if _d.get("scope") != 0:
                continue
            _k = (_d.get("id") or "").lower()
            if re.fullmatch(r"[a-z][a-z'\-]*", _k) and len(_k) >= 2 and _k not in STOP:
                sh_need.add(_k)

    with open(SRC, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            w = (r.get("word") or "").strip()
            if not w or len(w) > 30:
                continue
            key = w.lower()
            bnc = int(r.get("bnc") or 0)
            frq = int(r.get("frq") or 0)
            cand = [x for x in (bnc, frq) if x > 0]
            allfreq[key] = min(cand) if cand else None
            tags = (r.get("tag") or "").split()
            bits = 0
            for t in tags:
                if t in BITS:
                    bits |= BITS[t]
            if key in extra:
                bits |= extra[key]["mask"]
            if not bits and key not in sh_need:
                continue
            tr = (r.get("translation") or "").strip()
            if not tr or len(w) > 30:
                continue
            if key in STOP:
                if key not in sh_need:
                    continue
                bits = 0  # 只作为上海词库补充，不改变原有词库归属
            senses, spec = parse_senses(tr)
            defs = parse_defs(r.get("definition"))
            if not senses:
                # 清洗后义项被清空的兜底，避免出现“有词无义”
                fallback = clean_tr(tr)
                if not fallback and not spec:
                    continue
                if fallback:
                    senses = [["", [fallback]]]
            fill_pos(senses, defs, w)
            if any(not sn[0] for sn in senses):
                fill_pos(senses, defs, w, "phr." if " " in w else "n.")
            freq = allfreq.get(key) or 10 ** 7
            lv = [LEVEL.index(t) for t in tags if t in BITS and (BITS[t] & bits)]
            if key in extra:
                lv += [LEVEL.index(n) for n, b in EXTRA_BITS.items() if extra[key]["mask"] & b]
            lvl = max(lv, default=0)
            ph = (r.get("phonetic") or "").strip().replace("ә", "ə").replace("ɡ", "g")
            old = rows.get(key)
            if old and old["freq"] <= freq and old["lvl"] >= lvl:
                continue
            rows[key] = {
                "w": w, "ph": ph, "mask": bits, "freq": freq, "lvl": lvl,
                "senses": senses, "spec": spec,
                "defs": defs,
                "forms": parse_forms(r.get("exchange"), w),
                "stars": int(r.get("collins") or 0),
            }

    # 上海中考词库（PDF 抽取）-- 不在 ECDICT 里的词用原表释义
    zkf = os.path.join(BASE, "sh_zk.json")
    if os.path.exists(zkf):
        for k, v in json.load(open(zkf, encoding="utf-8")).items():
            if k in rows:
                rows[k]["mask"] |= BITS["sh-zk"]
                rows[k]["lvl"] = max(rows[k]["lvl"], LEVEL.index("sh-zk"))
                # 原表自带词性，只用于补「全空」的单义项组，避免改多词性词
                sn = rows[k]["senses"]
                if len(sn) == 1 and not sn[0][0]:
                    fill_pos(sn, rows[k]["defs"], k, v.get("pos"))
                continue
            senses, spec = parse_senses(v.get("def") or "")
            hint = _norm_pos(v.get("pos"))
            if not senses:
                senses = [[hint, [v.get("def") or "—"]]]
            fill_pos(senses, [], k, hint)
            rows[k] = {"w": k, "ph": "", "mask": BITS["sh-zk"],
                       "freq": 10 ** 7, "lvl": LEVEL.index("sh-zk"),
                       "senses": senses, "spec": spec, "defs": [], "forms": [], "stars": 0}
    # 上海高考词库（CC BY 4.0 开放词库，scope=0）
    gkf = os.path.join(BASE, "sh_gk.json")
    if os.path.exists(gkf):
        gj = json.load(open(gkf, encoding="utf-8"))
        f = gj["fields"]
        for e in gj["words"]:
            d = dict(zip(f, e))
            if d["scope"] != 0:
                continue
            k = (d["id"] or "").lower()
            if not re.fullmatch(r"[a-z][a-z'\-]*", k) or len(k) < 2 or k in STOP:
                continue
            if k in rows:
                rows[k]["mask"] |= BITS["sh-gk"]
                rows[k]["lvl"] = max(rows[k]["lvl"], LEVEL.index("sh-gk"))
                continue
            raw_zh = (d["zh"] or "").strip()
            mz = re.match(r"^([A-Za-z]+\.)\s*", raw_zh)
            # 认识的词性前缀保留给 parse_senses；不认识的照旧剥掉，避免把前缀当义项
            keep_prefix = bool(mz and mz.group(1).lower() in POS_MAP)
            src_zh = raw_zh if keep_prefix else re.sub(r"^[a-z]+\.\s*", "", raw_zh).strip()
            zh = re.sub(r"^[a-z]+\.\s*", "", src_zh).strip() or "—"
            senses, spec = parse_senses(src_zh)
            if not senses:
                senses = [[_norm_pos(mz.group(1)) if keep_prefix else "", [zh]]]
            fill_pos(senses, [], k)
            rows[k] = {"w": k, "ph": d["ipa"].strip("/") if d.get("ipa") else "",
                       "mask": BITS["sh-gk"], "freq": 10 ** 7, "lvl": LEVEL.index("sh-gk"),
                       "senses": senses, "spec": spec, "defs": [], "forms": [], "stars": 0}

    # 外挂词表里 ECDICT 没有的词（多为 CATTI 术语/短语）补一条基础记录
    for k, v in extra.items():
        if k in rows:
            continue
        w = v["w"]
        tr = re.sub(r"\s+", " ", v["tr"]).strip()
        if not tr:
            continue
        senses, spec = parse_senses(tr)
        if not senses:
            senses = [["", [tr[:80]]]]
        hint = "phr." if " " in w else "n."
        fill_pos(senses, [], w, hint)
        if not senses:
            continue
        rows[k] = {"w": w, "ph": "", "mask": v["mask"],
                   "freq": 10 ** 7,
                   "lvl": max((LEVEL.index(n) for n, b in EXTRA_BITS.items() if v["mask"] & b), default=0),
                   "senses": senses, "spec": spec, "defs": [], "forms": [], "stars": 0}

    data = sorted(rows.values(), key=lambda x: (x["lvl"], x["freq"], x["w"].lower()))
    for d in data:
        d["diff"] = difficulty(d)
    common = {w for w, f in allfreq.items() if f and f <= 20000}
    NAMES = {k for k, v in rows.items() if v["w"][:1].isupper()}
    posmap = {}
    for d in data:
        pos = ""
        for p, _ in d["senses"]:
            if p:
                pos = p
                break
        posmap[d["w"].lower()] = pos
    words = [d["w"].lower() for d in data]
    fam = build_families(words, common, allfreq, posmap, NAMES)
    rel = build_relations(words, common, allfreq, NAMES)
    for d in data:
        d["syl"] = syl_split(d["w"])
        key = d["w"].lower()
        # 同族词：过滤与主词相同的项 + 去重，保持词频排序
        fam_list, seen = [], set()
        for pair in (fam.get(key) or []):
            c = (pair[0] or "").strip().lower()
            if not c or c == key or c in seen:
                STATS["fam_drop"] += 1
                continue
            seen.add(c)
            fam_list.append([pair[0], pair[1]])
        d["fam"] = fam_list or None
        r = rel.get(key)
        syn = [x for x in dict.fromkeys(r[0]) if x != key] if r else []
        ant = [x for x in dict.fromkeys(r[1]) if x != key] if r else []
        d["syn"] = syn
        d["ant"] = ant
        d["tr_short"] = short_tr(d["senses"], d["spec"], 120) or "—"

    # 同族词 / 近反义词的简释义（这些词不一定在主词库里，弹卡时用）
    need = set()
    for d in data:
        for pair in (d.get("fam") or []):
            need.add(pair[0])
        need.update(d.get("syn") or [])
        need.update(d.get("ant") or [])
    famd, famd_en = {}, set()
    _sd = STATS["sense_drop"]
    with open(SRC, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            w = (r.get("word") or "").strip().lower()
            if w not in need or w in famd:
                continue
            tr = (r.get("translation") or "").strip()
            if not tr:
                continue
            senses, spec = parse_senses(tr, max_sense=3, max_items=4)
            txt = dedupe_zh(short_tr(senses, spec, 46))
            # 只收有中文的；纯英文的留给 WordNet 兜底（统一加“英：”前缀）
            if txt and _CJK_RE.search(txt) and not _hollow(txt):
                famd[w] = txt
    # 这一遍只是为弹卡二次解析，不重复计入义项清洗统计
    STATS["sense_drop"] = _sd
    # 主词库里的词也补上（近义词点击时释义更完整）；只收有中文的
    for d in data:
        key = d["w"].lower()
        if key in need and key not in famd:
            txt = dedupe_zh(d["tr_short"])
            if txt and _CJK_RE.search(txt) and not _hollow(txt):
                famd[key] = txt
    # 确实没有中文的（多为派生词/生僻词），才用 WordNet 英文兜底，前缀“英：”
    try:
        from nltk.corpus import wordnet as wn
    except Exception:
        wn = None
    if wn:
        for w in sorted(need):
            if w in famd:
                continue
            try:
                syns = wn.synsets(w)
                if syns:
                    en = re.sub(r"\s+", " ", (syns[0].definition() or "")).strip()
                    if en and not _hollow(en):
                        famd[w] = "英：" + en[:70]
            except Exception:
                pass
    # 英文兜底项统一口径：以“英：”开头的都算英文覆盖
    famd_en = {w for w in need if famd.get(w, "").startswith("英：")}

    # ---- 例句：先把所有候选源全量收集，再按规则打分重选 ----
    # rank: 0=手工例句(hand_examples) 1=examples.json 2=examples_new 3=nosent_out
    exf = os.path.join(BASE, "examples.json")
    tf = os.path.join(BASE, "translations.json")
    exnf = os.path.join(BASE, "examples_new.json")
    hf = os.path.join(BASE, "hand_examples.json")
    src = []  # (rank, key, en, zh)
    if os.path.exists(exf):
        ej = json.load(open(exf, encoding="utf-8"))
        tj = json.load(open(tf, encoding="utf-8")) if os.path.exists(tf) else {}
        for k, v in ej.items():
            c = (v.get("c") or "").strip() or (str(tj.get(k) or "")).strip()
            e = (v.get("e") or "").strip()
            if e and c:
                src.append((1, k, e, c))
    if os.path.exists(exnf):
        for k, v in json.load(open(exnf, encoding="utf-8")).items():
            e = (v.get("e") or "").strip()
            c = (v.get("c") or "").strip()
            if e and c:
                src.append((2, k, e, c))
    for nf in sorted(glob.glob(os.path.join(BASE, "nosent_out_*.json"))):
        for k, v in json.load(open(nf, encoding="utf-8")).items():
            if isinstance(v, list) and len(v) == 2 and v[0] and v[1]:
                src.append((3, k, v[0].strip(), v[1].strip()))
    if os.path.exists(hf):
        for k, v in json.load(open(hf, encoding="utf-8")).items():
            if v and v[0] and v[1]:
                src.append((0, k, (v[0] or "").strip(), (v[1] or "").strip()))

    # 基线：完全复刻原来的“后写覆盖”优先级，用于对比覆盖率
    base_ex = {}
    for rank in (1, 2, 3, 0):
        for rk, k, e, c in src:
            if rk != rank:
                continue
            if rank == 2 and k in base_ex:
                continue
            base_ex[k] = [e, c]

    cands = {}
    for rk, k, e, c in src:
        cands.setdefault(k.strip().lower(), []).append((rk, e, c))

    ex, replaced, kept_bad = {}, 0, []
    for d in data:
        wl = d["w"].lower()
        cl = cands.get(wl)
        base = base_ex.get(wl) or base_ex.get(d["w"])
        if not cl:
            if base:
                ex[wl] = base
            continue
        forms = infl_forms(wl, d["forms"])
        pick = None
        # 手工例句只要通过硬规则就保留（只修明显坏的句子）
        for rk, e, c in cl:
            if rk == 0 and check_example(e, forms) is not None:
                pick = (e, c)
                break
        if pick is None:
            best = None
            for rk, e, c in cl:
                toks = check_example(e, forms)
                if toks is None:
                    continue
                sc = score_example(toks, e, common)
                if best is None or sc < best:
                    best, pick = sc, (e, c)
        if pick is None:
            # 没有合格候选：保留原句（不牺牲覆盖率），仅记录“坏句”
            if base:
                ex[wl] = base
                kept_bad.append(wl)
            continue
        if base and base[0].strip() != pick[0].strip():
            replaced += 1
        ex[wl] = [pick[0], pick[1]]

    cov_base = sum(1 for d in data if base_ex.get(d["w"].lower()) or base_ex.get(d["w"]))
    cov_new = sum(1 for d in data if ex.get(d["w"].lower()))
    # 回退保护：重选若让覆盖率下降超过 1 个百分点，整批退回原选择
    if cov_base and (cov_base - cov_new) > 0.01 * len(data):
        print(f"例句重选回退：覆盖率 {cov_new} → {cov_base}（下降超过 1%），沿用原选择")
        ex = {k.lower(): v for k, v in base_ex.items()}
        cov_new = sum(1 for d in data if ex.get(d["w"].lower()))

    raw = [[d["w"], d["ph"], d["mask"], round(d["diff"], 3), d["freq"],
            ex.get(d["w"].lower()), d["syl"], d["fam"], d["senses"], d["spec"],
            d["defs"], d["forms"], d["stars"], d["syn"], d["ant"]] for d in data]

    # schema 自检：15 列结构不变，例句是 [英,中] 或 None，避免静默写坏前端
    bad = [r[0] for r in raw if len(r) != 15]
    if bad:
        raise SystemExit(f"schema 错误：{len(bad)} 条不是 15 列，例如 {bad[:5]}")
    bad_ex = [r[0] for r in raw if r[5] is not None and
              (not isinstance(r[5], list) or len(r[5]) != 2)]
    if bad_ex:
        raise SystemExit(f"例句结构错误：{len(bad_ex)} 条，例如 {bad_ex[:5]}")
    print(f"schema: 15 列 ✓  例句字段结构 ✓  (词条 {len(raw)})")

    sens_n = sum(len(r[8]) for r in raw)
    item_n = sum(len(s[1]) for r in raw for s in r[8])
    empty_grp = sum(1 for r in raw for s in r[8] if not s[0])
    empty_first = sum(1 for r in raw if r[8] and not r[8][0][0])
    famd_cn = sum(1 for v in famd.values() if _CJK_RE.search(v) and not v.startswith("英："))
    famd_nen = len(famd_en)
    famd_other = len(famd) - famd_cn - famd_nen
    forms_n = sum(len(r[11]) for r in raw)
    print(f"词条数: {len(raw)}")
    print(f"例句覆盖: {cov_new}/{len(raw)}  (优化前 {cov_base})  "
          f"重选 {replaced} 条  仍不合格但保留 {len(kept_bad)} 条")
    print(f"同族词覆盖: {sum(1 for r in raw if r[7])}/{len(raw)}")
    print(f"近义词覆盖: {sum(1 for r in raw if r[13])}  反义词覆盖: {sum(1 for r in raw if r[14])}")
    print(f"义项组: {sens_n}  义项条: {item_n}  多词性词: {sum(1 for r in raw if len(r[8]) >= 2)}")
    print(f"义项清洗丢弃: {STATS['sense_drop']} 条  空词性: {empty_grp} 组"
          f"（首组空词性 {empty_first} 词）")
    print(f"英英释义: {sum(1 for r in raw if r[10])}  词形变化: {sum(1 for r in raw if r[11])}"
          f" 词形条数: {forms_n}（过滤 {STATS['form_drop']}）"
          f"  专业义: {sum(1 for r in raw if r[9])}  柯林斯星级: {sum(1 for r in raw if r[12])}")
    print(f"音节已切: {sum(1 for r in raw if r[6] != r[0])}/{len(raw)}")
    print(f"同族/近反义词简释义: {len(famd)}  中文 {famd_cn}  英文兜底 {famd_nen}"
          f"  其它 {famd_other}  仍缺 {len(need) - len(famd)}  (需补词 {len(need)})")
    for name, bit in BITS.items():
        print(f"  {name:5s}: {sum(1 for d in data if d['mask'] & bit)}")
    for i, name in enumerate(LEVEL):
        print(f"\n{name} 前 6 条:")
        for d in [x for x in data if x["lvl"] == i][:6]:
            print("  ", d["w"], "/" + d["ph"] + "/", d["tr_short"][:50])
    import random
    random.seed(7)
    print("\n随机抽查:")
    for d in random.sample(data, 8):
        print("  ", d["w"], "/" + d["ph"] + "/", d["tr_short"][:60])

    payload = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    fam_payload = json.dumps(famd, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    with open(TPL, encoding="utf-8") as f:
        tpl = f.read()
    html = tpl.replace("__WORDS__", payload).replace("__FAMD__", fam_payload)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"输出: {OUT}  {os.path.getsize(OUT)/1024:.0f} KB")


if __name__ == "__main__":
    main()
