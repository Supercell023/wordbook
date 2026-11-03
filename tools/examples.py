#!/usr/bin/env python3
# 为每个单词挑一条中英对照例句：Tatoeba 优先，News-Commentary 兜底，都没有的列出来待翻译。
import bz2, json, re, sys, os
from collections import defaultdict
from opencc import OpenCC
CC = OpenCC('t2s')

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
TAT = '/tmp/tatoeba'
NC = '/tmp/news'

ROOT = os.path.dirname(BASE)
h = open(os.path.join(ROOT, 'dist', 'vocab.html'), encoding='utf-8').read()
RAW = json.loads(re.search(r'const RAW = (\[.*?\]);\n', h, re.S).group(1))
WORDS = [(r[0], r[2]) for r in RAW]

TRAD = set('們個這說對時會來為國學開關麼樣發現經過給讓點還嗎裡與並將從當時個言語讀寫聽買賣錢書車馬鳥龍門長東見觀覽選擇運運動員藝術節電腦網絡訪問頁國際華爾樂歲權義務責任認識應該應該頭題願幫助辦辦法')
NAMES = set('tom mary john bob alice jack mike sarah david lisa jane peter susan bill kate '
            'jim joe sam anna paul linda james robert michael william richard charles joseph '
            'thomas christopher daniel matthew anthony mark donald steven andrew kenneth '
            'george joshua kevin brian edward ronald timothy jason jeffrey ryan jacob gary '
            'nicholas eric jonathan stephen larry justin scott brandon frank benjamin gregory '
            'samuel raymond patrick alexander dennis jerry tyler aaron jose adam henry '
            'nathan douglas zachary kyle walter ethan jeremy harold keith christian '
            'roger noah gerald carl terry sean austin arthur lawrence jesse dylan bryan '
            'jordan billy bruce albert willie gabriel logan alan juan wayne roy ralph randy '
            'eugene vincent russell elijah louis bobby philip johnny'.split())

def forms(w):
    f = {w, w + 's', w + 'es', w + 'ed', w + 'ing', w + 'd'}
    if w.endswith('e'): f |= {w[:-1] + 'ing', w[:-1] + 'ed'}
    if w.endswith('y'): f |= {w[:-1] + 'ies', w[:-1] + 'ied'}
    if w.endswith('f'): f |= {w[:-1] + 'ves'}
    if w.endswith('fe'): f |= {w[:-2] + 'ves'}
    if w.endswith('our'): f |= {w.replace('our', 'or')}
    return f

WHITE = set('ien iII I Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July August September October November December English Chinese American British French Japanese Chinese Asia Europe Africa America China Japan France Britain Germany India London New York Christmas'.lower().split())

def han(s): return re.findall(r'[\u4e00-\u9fff]', s)

def propn(e):
    toks = e.split()
    n = 0
    for i, t in enumerate(toks):
        core = re.sub(r"[^A-Za-z'-]", '', t)
        if i > 0 and core[:1].isupper() and core.lower() not in WHITE: n += 1
    return n

def trad_count(zh): return sum(1 for ch in zh if ch in TRAD)

def name_count(e):
    return sum(1 for t in re.findall(r"[a-z]+", e.lower()) if t in NAMES)

def overlap(zh, tr):
    a = set(re.findall(r'[\u4e00-\u9fff]{2}', tr or ''))
    b = set(re.findall(r'[\u4e00-\u9fff]{2}', zh))
    return len(a & b)

def base_ok(e, zh, lvl=0):
    n = len(e.split())
    if n < 2 or n > 16: return False
    if not e[:1].isupper(): return False
    if e.strip()[-1] not in '.!?': return False
    if re.search(r'[·•※]', e): return False
    if len(han(zh)) < 3: return False
    if lvl < 3 and lvl != 2 and re.search(r'[0-9]', e): return False
    if lvl < 2 and n < 4: return False
    if lvl == 3 and n > 20: return False
    return True

def pick(word, tr, cands):
    # 逐级放宽：干净长句 → 允许人名 → 允许数字 → 允许超短句
    for lvl in (0, 1, 2, 3):
        best = None
        for e, zh, src in cands:
            if not base_ok(e, zh, lvl): continue
            if lvl == 0 and name_count(e) > 0: continue
            if lvl == 0 and src == 'nc' and propn(e) > 0: continue
            if lvl == 0 and src == 'nc' and len(e.split()) < 8: continue
            sc = 6 * overlap(zh, tr) - 3 * name_count(e) - abs(len(e.split()) - 8) * 0.8
            if src == 'nc': sc -= 5
            if best is None or sc > best[0]: best = (sc, e, zh, src)
        if best: return best
    return None

def load():
    print('读取 Tatoeba …', file=sys.stderr)
    eng, cmn = {}, {}
    for line in bz2.open(f'{TAT}/eng_sentences.tsv.bz2', 'rt', encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('\t')
        if len(p) >= 3: eng[int(p[0])] = p[2]
    for line in bz2.open(f'{TAT}/cmn_sentences.tsv.bz2', 'rt', encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('\t')
        if len(p) >= 3: cmn[int(p[0])] = CC.convert(p[2]).strip()
    pairs = []
    for line in bz2.open(f'{TAT}/cmn-eng_links.tsv.bz2', 'rt', encoding='utf-8'):
        a = line.rstrip('\n').split('\t')
        if len(a) >= 2:
            try: x, y = int(a[0]), int(a[1])
            except ValueError: continue
            if x in cmn and y in eng: pairs.append((eng[y], cmn[x]))
    idx = defaultdict(list)
    for e, zh in pairs:
        for t in set(re.findall(r"[a-z][a-z'-]*", e.lower())):
            idx[t].append((e, zh, 'tat'))
    print('Tatoeba 句对', len(pairs), file=sys.stderr)
    eidx = defaultdict(list)
    for i, e in eng.items():
        if not (4 <= len(e.split()) <= 14): continue
        if re.search(r'[0-9]', e): continue
        if e.strip()[-1] not in '.!?': continue
        for t in set(re.findall(r"[a-z][a-z'-]*", e.lower())):
            eidx[t].append(e)

    en = open(f'{NC}/News-Commentary.en-zh.en', encoding='utf-8', errors='replace').read().split('\n')
    zhf = open(f'{NC}/News-Commentary.en-zh.zh', encoding='utf-8', errors='replace').read().split('\n')
    ncn = 0
    for i in range(min(len(en), len(zhf))):
        e, zh = en[i], zhf[i]
        if not e or not zh: continue
        ncn += 1
        for t in set(re.findall(r"[a-z][a-z'-]*", e.lower())):
            idx[t].append((e, zh, 'nc'))
    print('News-Commentary 句对', ncn, file=sys.stderr)
    return idx, eidx

def main():
    idx, eidx = load()
    out, todo = {}, {}
    for w, tr in WORDS:
        cands = []
        for f in forms(w.lower()):
            cands.extend(idx.get(f, []))
        best = pick(w.lower(), tr, cands)
        if best:
            out[w.lower()] = {'e': best[1], 'c': best[2], 's': best[3]}
        else:
            cand = []
            for f in forms(w.lower()): cand.extend(eidx.get(f, []))
            cand = [e for e in cand if name_count(e) == 0] or cand
            if cand:
                cand.sort(key=lambda e: (abs(len(e.split()) - 8), len(e)))
                out[w.lower()] = {'e': cand[0], 'c': '', 's': 'todo'}
                todo[w.lower()] = {'tr': tr, 'e': cand[0]}
            else:
                todo[w.lower()] = {'tr': tr, 'e': ''}
    src = defaultdict(int)
    for v in out.values():
        src[v['s']] += 1
        if v['s'] == 'todo': v.pop('s')
    print('有例句', len(out), dict(src), '待翻译', len(todo), file=sys.stderr)
    json.dump(out, open(os.path.join(BASE, 'examples.json'), 'w'), ensure_ascii=False, indent=0)
    json.dump(todo, open(os.path.join(BASE, 'todo_translate.json'), 'w'), ensure_ascii=False, indent=0)

if __name__ == '__main__':
    main()
