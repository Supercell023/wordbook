#!/usr/bin/env python3
# 把缺口例句里带人名的句子换成不带专有名词的版本，并让这些词重新翻译。
import json, bz2, re, os, sys
from collections import defaultdict

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
sys.path.insert(0, BASE)
import examples as ex

TODO = os.path.join(BASE, 'todo_translate.json')
TRANS = os.path.join(BASE, 'translations.json')

def main():
    todo = json.load(open(TODO, encoding='utf-8'))
    trans = json.load(open(TRANS, encoding='utf-8'))
    print('读取英文语料 …', flush=True)
    eidx = defaultdict(list)
    for line in bz2.open('/tmp/tatoeba/eng_sentences.tsv.bz2', 'rt', encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('\t')
        if len(p) < 3: continue
        e = p[2]
        if not (4 <= len(e.split()) <= 16): continue
        if re.search(r'[0-9]', e): continue
        if e.strip()[-1] not in '.!?': continue
        if ex.propn(e) > 0: continue
        for t in set(re.findall(r"[a-z][a-z'-]*", e.lower())):
            eidx[t].append(e)
    changed = 0
    for w, v in list(todo.items()):
        e = v.get('e') or ''
        if not e or ex.propn(e) == 0: continue
        cands = []
        for f in ex.forms(w):
            cands.extend(eidx.get(f, []))
        if not cands: continue
        cands.sort(key=lambda s: (abs(len(s.split()) - 8), len(s)))
        new = cands[0]
        if new == e: continue
        todo[w]['e'] = new
        trans.pop(w, None)
        changed += 1
    json.dump(todo, open(TODO, 'w'), ensure_ascii=False, indent=0)
    json.dump(trans, open(TRANS, 'w'), ensure_ascii=False, indent=0)
    print('替换', changed, '条，待重译', len(trans), '/', len(todo), flush=True)

if __name__ == '__main__':
    main()
