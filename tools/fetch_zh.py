#!/usr/bin/env python3
# 用 MyMemory 批量翻译缺口例句（可断点续跑）。结果写入 translations.json
import urllib.request, urllib.parse, json, time, os, sys, re

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
TODO = os.path.join(BASE, 'todo_translate.json')
OUT = os.path.join(BASE, 'translations.json')
DE = 'vocab-demo@example.com'

def load():
    todo = json.load(open(TODO))
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    return todo, done

def save(d):
    tmp = OUT + '.tmp'
    json.dump(d, open(tmp, 'w'), ensure_ascii=False, indent=0)
    os.replace(tmp, OUT)

def main():
    todo, done = load()
    todo = {k: v for k, v in todo.items() if v['e'] and k not in done}
    print('待译', len(todo), '已完成', len(done), flush=True)
    for i, (k, v) in enumerate(todo.items(), 1):
        e = v['e']
        u = ('https://api.mymemory.translated.net/get?q=' + urllib.parse.quote(e[:480]) +
             '&langpair=en|zh-CN&de=' + urllib.parse.quote(DE))
        for attempt in range(3):
            try:
                d = json.loads(urllib.request.urlopen(
                    urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20
                ).read().decode())
                txt = (d['responseData']['translatedText'] or '').strip()
                if 'MYMEMORY WARNING' in txt.upper() or 'QUOTA' in txt.upper():
                    print('QUOTA', txt[:100], flush=True); return
                if not re.search(r'[\u4e00-\u9fff]', txt) or txt.lower() == e.lower():
                    txt = ''
                done[k] = txt
                break
            except Exception as ex:
                if attempt == 2:
                    print('ERR', k, type(ex).__name__, str(ex)[:60], flush=True)
                time.sleep(2 + attempt)
        if i % 25 == 0:
            save(done); print(i, flush=True)
        time.sleep(0.55)
    save(done)
    print('完成', len(done), flush=True)

if __name__ == '__main__':
    main()
