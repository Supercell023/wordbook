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
BITS = {"zk": 1, "gk": 2, "cet4": 4, "cet6": 8, "ielts": 16, "toefl": 32, "sh-zk": 64, "sh-gk": 128}
LEVEL = ["zk", "sh-zk", "gk", "sh-gk", "cet4", "cet6", "ielts", "toefl"]
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
    return senses, spec


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
    """exchange: d:abandoned/p:abandoned/i:abandoning/3:abandons → [[标签, 词形]]。"""
    out = []
    for part in (exchange or "").split("/"):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        v = v.strip()
        if k in FORM_LB and v and v.lower() != word.lower() and len(out) < 6:
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
        cands = [c for c in cands if not _infl(c, common) and c not in NAMES]
        res = []
        for c in sorted(cands, key=lambda x: (freq.get(x) or 10 ** 7))[:3]:
            pos = posmap.get(c, "")
            if not pos:
                try:
                    ts = wn.synsets(c)
                    if ts:
                        pos = _POSEN.get(ts[0].pos(), "")
                except Exception:
                    pass
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


def main():
    rows, allfreq = {}, {}
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
            if senses:
                fallback_pos = (defs[0][0] if defs and defs[0][0] else "") or wn_pos(w)
                for s in senses:
                    if not s[0]:
                        s[0] = fallback_pos
            if not senses and not spec:
                fallback = clean_tr(tr)
                if not fallback:
                    continue
                senses = [["", [fallback]]]
            freq = allfreq.get(key) or 10 ** 7
            lvl = max((LEVEL.index(t) for t in tags if t in BITS and (BITS[t] & bits)), default=0)
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
                continue
            senses, spec = parse_senses(v.get("def") or "")
            if senses:
                fp = wn_pos(k)
                for s in senses:
                    if not s[0]:
                        s[0] = fp
            if not senses:
                senses = [["", [v.get("def") or "—"]]]
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
            zh = re.sub(r"^[a-z]+\.\s*", "", d["zh"] or "").strip() or "—"
            senses, spec = parse_senses(zh)
            if senses:
                fp = wn_pos(k)
                for s in senses:
                    if not s[0]:
                        s[0] = fp
            if not senses:
                senses = [["", [zh]]]
            rows[k] = {"w": k, "ph": d["ipa"].strip("/") if d.get("ipa") else "",
                       "mask": BITS["sh-gk"], "freq": 10 ** 7, "lvl": LEVEL.index("sh-gk"),
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
        d["fam"] = fam.get(key)
        r = rel.get(key)
        d["syn"] = r[0] if r else []
        d["ant"] = r[1] if r else []
        d["tr_short"] = short_tr(d["senses"], d["spec"], 120) or "—"

    # 同族词 / 近反义词的简释义（这些词不一定在主词库里，弹卡时用）
    need = set()
    for d in data:
        for pair in (d.get("fam") or []):
            need.add(pair[0])
        need.update(d.get("syn") or [])
        need.update(d.get("ant") or [])
    famd = {}
    with open(SRC, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            w = (r.get("word") or "").strip().lower()
            if w not in need or w in famd:
                continue
            tr = (r.get("translation") or "").strip()
            if not tr:
                continue
            senses, spec = parse_senses(tr, max_sense=3, max_items=4)
            txt = short_tr(senses, spec, 46)
            if txt:
                famd[w] = txt
    # 主词库里的词也补上（近义词点击时释义更完整）
    for d in data:
        key = d["w"].lower()
        if key in need and key not in famd:
            famd[key] = d["tr_short"]
    # 仍缺中文释义的（多为派生词），用 WordNet 英文释义兜底，保证点开有内容
    try:
        from nltk.corpus import wordnet as wn
    except Exception:
        wn = None
    if wn:
        for w in need:
            if w in famd:
                continue
            try:
                syns = wn.synsets(w)
                if syns:
                    en = (syns[0].definition() or "").strip()
                    if en:
                        famd[w] = "英：" + en[:70]
            except Exception:
                pass

    ex = {}
    exf = os.path.join(BASE, "examples.json")
    tf = os.path.join(BASE, "translations.json")
    if os.path.exists(exf):
        ej = json.load(open(exf, encoding="utf-8"))
        tj = json.load(open(tf, encoding="utf-8")) if os.path.exists(tf) else {}
        for k, v in ej.items():
            c = (v.get("c") or "").strip() or (tj.get(k) or "").strip()
            e = (v.get("e") or "").strip()
            if e and c:
                ex[k] = [e, c]
    exnf = os.path.join(BASE, "examples_new.json")
    if os.path.exists(exnf):
        for k, v in json.load(open(exnf, encoding="utf-8")).items():
            e = (v.get("e") or "").strip()
            c = (v.get("c") or "").strip()
            if e and c and k not in ex:
                ex[k] = [e, c]
    for nf in sorted(glob.glob(os.path.join(BASE, "nosent_out_*.json"))):
        for k, v in json.load(open(nf, encoding="utf-8")).items():
            if isinstance(v, list) and len(v) == 2 and v[0] and v[1]:
                ex[k] = [v[0].strip(), v[1].strip()]
    hf = os.path.join(BASE, "hand_examples.json")
    if os.path.exists(hf):
        for k, v in json.load(open(hf, encoding="utf-8")).items():
            if v and v[0] and v[1]:
                ex[k] = v

    raw = [[d["w"], d["ph"], d["mask"], round(d["diff"], 3), d["freq"],
            ex.get(d["w"].lower()), d["syl"], d["fam"], d["senses"], d["spec"],
            d["defs"], d["forms"], d["stars"], d["syn"], d["ant"]] for d in data]

    sens_n = sum(len(r[8]) for r in raw)
    item_n = sum(len(s[1]) for r in raw for s in r[8])
    print(f"词条数: {len(raw)}")
    print(f"例句覆盖: {sum(1 for r in raw if r[5])}/{len(raw)}")
    print(f"同族词覆盖: {sum(1 for r in raw if r[7])}/{len(raw)}")
    print(f"近义词覆盖: {sum(1 for r in raw if r[13])}  反义词覆盖: {sum(1 for r in raw if r[14])}")
    print(f"义项组: {sens_n}  义项条: {item_n}  多词性词: {sum(1 for r in raw if len(r[8]) >= 2)}")
    print(f"英英释义: {sum(1 for r in raw if r[10])}  词形变化: {sum(1 for r in raw if r[11])}"
          f"  专业义: {sum(1 for r in raw if r[9])}  柯林斯星级: {sum(1 for r in raw if r[12])}")
    print(f"音节已切: {sum(1 for r in raw if r[6] != r[0])}/{len(raw)}")
    print(f"同族/近反义词简释义: {len(famd)}")
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
