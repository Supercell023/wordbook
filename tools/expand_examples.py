#!/usr/bin/env python3
# 只给「还没有例句」的新词补例句，不动已有例句（避免和已翻译好的中文对不上）
import json, os, sys
from collections import defaultdict
import examples as E

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
existing = json.load(open(os.path.join(BASE, 'examples.json'), encoding='utf-8'))
have = set(existing.keys())

miss = [(r[0], r[2]) for r in E.RAW if r[0].lower() not in have]
print('缺例句的词', len(miss), file=sys.stderr)

idx, eidx = E.load()
out, todo = {}, {}
for w, tr in miss:
    wl = w.lower()
    cands = []
    for f in E.forms(wl):
        cands.extend(idx.get(f, []))
    best = E.pick(wl, tr, cands)
    if best:
        out[wl] = {'e': best[1], 'c': best[2]}
        continue
    cand = []
    for f in E.forms(wl):
        cand.extend(eidx.get(f, []))
    cand = [e for e in cand if E.name_count(e) == 0] or cand
    if cand:
        cand.sort(key=lambda e: (abs(len(e.split()) - 8), len(e)))
        out[wl] = {'e': cand[0], 'c': ''}
        todo[wl] = {'tr': tr, 'e': cand[0]}
    else:
        todo[wl] = {'tr': tr, 'e': ''}

json.dump(out, open(os.path.join(BASE, 'examples_new.json'), 'w'), ensure_ascii=False, indent=0)
json.dump(todo, open(os.path.join(BASE, 'todo_new.json'), 'w'), ensure_ascii=False, indent=0)
print('新补例句', sum(1 for v in out.values() if v['c']), '待翻译', sum(1 for v in out.values() if not v['c']),
      '完全没有句子', sum(1 for v in todo.values() if not v['e']), file=sys.stderr)
