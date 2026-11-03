#!/usr/bin/env python3
# 构建词库：ECDICT（中考/高考/四级/六级/雅思/托福）+ 上海中考/高考，生成 vocab.html
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


def clean_tr(t):
    t = t.replace("\\n", "\n").replace("\r", "\n")
    lines = [x.strip() for x in t.split("\n") if x.strip()]
    keep = [x for x in lines if not x.startswith("[")]
    if not keep:
        keep = lines
    # 最多两行，避免卡片过长
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
_POSCN = {"n": "名", "v": "动", "a": "形", "s": "形", "r": "副"}


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


_POSP = {"n.": "名", "a.": "形", "adj.": "形", "s.": "形", "v.": "动", "vt.": "动", "vi.": "动",
         "ad.": "副", "adv.": "副"}


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
        # 标注词性（取该词自身最常见的词性）
        cands = [c for c in cands if not _infl(c, common) and c not in NAMES]
        res = []
        for c in sorted(cands, key=lambda x: (freq.get(x) or 10 ** 7))[:3]:
            pos = posmap.get(c, "")
            if not pos:
                try:
                    ts = wn.synsets(c)
                    if ts:
                        pos = _POSCN.get(ts[0].pos(), "")
                except Exception:
                    pass
            res.append([c, pos])
        if res:
            out[w] = res
    return out


def difficulty(d):
    """0=最容易, 1=最难：层级 45% + 词频 35% + 词长 10% + 义项数 10%"""
    lv = min(1.0, d["lvl"] * 0.3)
    f = d["freq"]
    fq = 1.0 if f >= 10 ** 7 else min(1.0, max(0.0, math.log(f) / math.log(30000)))
    ln = min(1.0, max(0.0, (len(d["w"]) - 4) / 8))
    sn = min(1.0, d["tr"].count("/") / 4)
    return 0.45 * lv + 0.35 * fq + 0.10 * ln + 0.10 * sn


def main():
    rows = {}
    allfreq = {}
    with open(SRC, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            w = (r.get("word") or "").strip()
            if not w or len(w) > 30:
                continue
            bnc = int(r.get("bnc") or 0)
            frq = int(r.get("frq") or 0)
            cand = [x for x in (bnc, frq) if x > 0]
            allfreq[w.lower()] = min(cand) if cand else None
            tags = (r.get("tag") or "").split()
            bits = 0
            for t in tags:
                if t in BITS:
                    bits |= BITS[t]
            if not bits:
                continue
            tr = (r.get("translation") or "").strip()
            if not tr or len(w) > 30:
                continue
            if w.lower() in STOP:
                continue
            tr = clean_tr(tr)
            if not tr:
                continue
            freq = allfreq[w.lower()] or 10 ** 7
            lvl = max(LEVEL.index(t) for t in tags if t in BITS)
            ph = (r.get("phonetic") or "").strip().replace("ә", "ə").replace("ɡ", "g")
            key = w.lower()
            old = rows.get(key)
            if old and old["freq"] <= freq and old["lvl"] >= lvl:
                continue
            rows[key] = {"w": w, "ph": ph, "tr": tr, "mask": bits, "freq": freq, "lvl": lvl}

    # 上海中考词库（PDF 抽取）-- 不在 ECDICT 里的词用原表释义
    zkf = os.path.join(BASE, "sh_zk.json")
    if os.path.exists(zkf):
        for k, v in json.load(open(zkf, encoding="utf-8")).items():
            if k in rows:
                rows[k]["mask"] |= BITS["sh-zk"]
                rows[k]["lvl"] = max(rows[k]["lvl"], LEVEL.index("sh-zk"))
                continue
            rows[k] = {"w": k, "ph": "", "tr": v["def"], "mask": BITS["sh-zk"],
                       "freq": 10 ** 7, "lvl": LEVEL.index("sh-zk")}
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
            rows[k] = {"w": k, "ph": d["ipa"].strip("/") if d.get("ipa") else "",
                       "tr": re.sub(r"^[a-z]+\.\s*", "", d["zh"] or "").strip() or "—",
                       "mask": BITS["sh-gk"], "freq": 10 ** 7, "lvl": LEVEL.index("sh-gk")}

    data = sorted(rows.values(), key=lambda x: (x["lvl"], x["freq"], x["w"].lower()))
    for d in data:
        d["diff"] = difficulty(d)
    common = {w for w, f in allfreq.items() if f and f <= 20000}
    NAMES = {k for k, v in rows.items() if v["w"][:1].isupper()}
    posmap = {}
    for d in data:
        t = (d["tr"] or "").split()[0] if d["tr"] else ""
        posmap[d["w"].lower()] = _POSP.get(t, "")
    fam = build_families([d["w"].lower() for d in data], common, allfreq, posmap, NAMES)
    for d in data:
        d["syl"] = syl_split(d["w"])
        d["fam"] = fam.get(d["w"].lower())
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
    raw = [[d["w"], d["ph"], d["tr"], d["mask"], round(d["diff"], 3), d["freq"], ex.get(d["w"].lower()),
            d["syl"], d["fam"]] for d in data]
    print(f"带例句: {sum(1 for r in raw if r[6])}/{len(raw)}")
    print(f"带同族词: {sum(1 for r in raw if r[8])}/{len(raw)}")
    print(f"音节已切: {sum(1 for r in raw if r[7] != r[0])}/{len(raw)}")
    print(f"词条数: {len(raw)}")
    for name, bit in BITS.items():
        print(f"  {name:5s}: {sum(1 for d in data if d['mask'] & bit)}")
    for i, name in enumerate(LEVEL):
        print(f"\n{name} 前 6 条:")
        for d in [x for x in data if x["lvl"] == i][:6]:
            print("  ", d["w"], "/" + d["ph"] + "/", d["tr"][:50])
    import random
    random.seed(7)
    print("\n随机抽查:")
    for d in random.sample(data, 8):
        print("  ", d["w"], "/" + d["ph"] + "/", d["tr"][:60])

    payload = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    with open(TPL, encoding="utf-8") as f:
        tpl = f.read()
    html = tpl.replace("__WORDS__", payload)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"输出: {OUT}  {os.path.getsize(OUT)/1024:.0f} KB")


if __name__ == "__main__":
    main()
