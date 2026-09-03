#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 whisper 生成的 SRT 逐字稿中，按 credibility.json 每条观点的时间区间
抽取"原文"（verbatim transcript segments），写入 credibility.json 的
item["quote"]["segments"]，并保留手工标注的 key 标记。

用法：
    python extract_quote.py            # 抽取并写回（保留已有 key 标记）
    python extract_quote.py --preview  # 只打印，不写回

特性：
  - 幂等：重复运行不会丢失已有 key 标记（按 text 精确匹配）。
  - 只覆盖 quote.segments / quote.range / quote.stats，不动其他字段。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_JSON = os.path.join(HERE, 'credibility.json')
SRT = r'E:\projects\video-fetcher\transcripts\蒋介石明明是名中正字介石，为何大陆会普遍称他蒋介石？.srt'

TIME_RE = re.compile(
    r'(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})'
)


def parse_srt(path):
    """返回 [(start_sec, end_sec, text), ...]"""
    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read()
    blocks = re.split(r'\n\s*\n', raw.replace('\r\n', '\n').replace('\r', '\n'))
    out = []
    for b in blocks:
        lines = [l for l in b.split('\n') if l.strip() != '']
        if len(lines) < 2:
            continue
        m = None
        ti = None
        for i, l in enumerate(lines[:3]):
            m = TIME_RE.search(l)
            if m:
                ti = i
                break
        if not m:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = (int(x) for x in m.groups())
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0
        end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0
        text = ' '.join(x.strip() for x in lines[ti + 1:]).strip()
        if text:
            out.append((round(start, 2), round(end, 2), text))
    out.sort(key=lambda x: x[0])
    return out


def fmt(sec):
    s = max(0, int(sec))
    return '%02d:%02d' % (s // 60, s % 60)


def main():
    preview = '--preview' in sys.argv
    segs = parse_srt(SRT)
    if not segs:
        print('[FAIL] 逐字稿解析为空：%s' % SRT)
        return 1

    with open(SRC_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for it in data.get('items', []):
        a, b = float(it['start']), float(it['end'])
        picked = [s for s in segs if s[0] >= a - 0.01 and s[0] < b - 0.01]
        if not picked:  # 兜底：按重叠区间取
            picked = [s for s in segs if s[0] < b and s[1] > a]

        old = (it.get('quote') or {}).get('segments') or []
        keymap = {}
        for o in old:
            if isinstance(o, dict) and o.get('key') and o.get('text'):
                keymap[o['text']] = True

        new_segs = []
        for st, en, tx in picked:
            new_segs.append({
                't': st,
                'text': tx,
                'key': bool(keymap.get(tx)),
            })

        it['quote'] = {
            'range': '%s–%s' % (fmt(a), fmt(b)),
            'segments': new_segs,
            'stats': {
                'lines': len(new_segs),
                'chars': sum(len(s['text']) for s in new_segs),
                'key_lines': sum(1 for s in new_segs if s['key']),
            },
        }
        if preview:
            print('--- #%d %s [%s] %d 行 / %d 字'
                  % (it['id'], it['title'], fmt(a) + '–' + fmt(b),
                     len(new_segs), it['quote']['stats']['chars']))

    if preview:
        print('\n（预览模式，未写回）')
        return 0

    with open(SRC_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

    total = sum(i['quote']['stats']['lines'] for i in data['items'])
    print('已写回 %s' % SRC_JSON)
    print('  观点 %d 条，共 %d 行逐字稿' % (len(data['items']), total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
