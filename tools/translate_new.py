#!/usr/bin/env python3
# 给 examples_new.json 里缺中文的句子补翻译（Google gtx 接口，失败退回 MyMemory），断点续跑
import json, os, re, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
EXF = os.path.join(BASE, 'examples_new.json')
TODOF = os.path.join(BASE, 'todo_new.json')
OUTF = os.path.join(BASE, 'translations_new.json')
UA = {'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0'}


def get(url, timeout=12):
    r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)
    return r.read().decode('utf-8', 'replace')


def gtrans(text):
    q = urllib.parse.quote(text)
    url = ('https://translate.googleapis.com/translate_a/single?client=gtx&sl=en'
           f'&tl=zh-CN&dt=t&q={q}')
    raw = get(url)
    data = json.loads(raw)
    return ''.join(seg[0] for seg in data[0] if seg and seg[0]).strip()


def mm(text):
    q = urllib.parse.quote(text)
    url = f'https://api.mymemory.translated.net/get?q={q}&langpair=en|zh-CN&de=wordbook@example.com'
    data = json.loads(get(url))
    if data.get('quotaFinished'):
        raise RuntimeError('quota')
    return (data['responseData']['translatedText'] or '').strip()


def translate(text):
    for fn in (gtrans, mm):
        for attempt in range(3):
            try:
                out = fn(text)
                if out and re.search(r'[\u4e00-\u9fff]', out):
                    return out
            except Exception:
                time.sleep(1.2 * (attempt + 1))
    return ''


def main():
    ex = json.load(open(EXF, encoding='utf-8'))
    todo = json.load(open(TODOF, encoding='utf-8'))
    done = json.load(open(OUTF, encoding='utf-8')) if os.path.exists(OUTF) else {}
    need = [(w, todo[w]['e']) for w in todo
            if todo[w].get('e') and w in ex and not ex[w].get('c') and w not in done]
    print('待翻译', len(need), file=sys.stderr)
    lock = __import__('threading').Lock()
    cnt = [0]

    def work(item):
        w, e = item
        zh = translate(e)
        with lock:
            cnt[0] += 1
            if zh:
                done[w] = zh
                ex[w]['c'] = zh
            if cnt[0] % 50 == 0:
                json.dump(done, open(OUTF, 'w'), ensure_ascii=False, indent=0)
                json.dump(ex, open(EXF, 'w'), ensure_ascii=False, indent=0)
                print('进度', cnt[0], '/', len(need), file=sys.stderr)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, need))
    json.dump(done, open(OUTF, 'w'), ensure_ascii=False, indent=0)
    json.dump(ex, open(EXF, 'w'), ensure_ascii=False, indent=0)
    print('完成翻译', len(done), '缺例句', sum(1 for w in todo if not todo[w].get('e')), file=sys.stderr)


if __name__ == '__main__':
    main()
