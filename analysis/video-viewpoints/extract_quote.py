#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 whisper 生成的 SRT 逐字稿中，按 credibility.json 每条观点的时间区间
抽取"原文"（verbatim transcript segments），写入 credibility.json 的
item["quote"]["segments"]，并保留手工标注的 key 标记。

用法：
    python extract_quote.py            # 抽取并写回（保留已有 key 标记与修正后文本）
    python extract_quote.py --preview  # 只打印，不写回

幂等策略（勘误已落库后）：
  逐字稿里已标注关键句、且 ASR 讹误已按语义/史实补正（修正后文字直接存于
  segment.text，不再用独立的 fix 字段）。为免重跑时被 SRT 原始错词回灌，
  本脚本按时间戳匹配已有 segment：
    - 找到同时间段（±0.15s）的旧段 → 沿用旧 text（已补正）与 key；
    - 找不到（新增/时间变动）→ 才采用 SRT 原文。
  因此同一份 SRT 反复运行结果是稳定的，不会丢失补正与关键句标注。

特性：
  - 只覆盖 quote.segments / quote.range / quote.stats，不动其他字段；
    quote.note 若已存在则原样保留。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_JSON = os.path.join(HERE, 'credibility.json')
DEFAULT_SRT = r'E:\projects\video-fetcher\transcripts\蒋介石明明是名中正字介石，为何大陆会普遍称他蒋介石？.srt'
# 也可用环境变量或命令行指定逐字稿：python extract_quote.py path/to/xxx.srt
SRT = os.environ.get('FACTEASY_SRT') or (
    sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else DEFAULT_SRT
)

TIME_RE = re.compile(
    r'(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})'
)

T_MATCH = 0.15  # 时间戳匹配容差（秒）


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
        # 旧段按时间戳建索引，供匹配（保留已补正 text 与 key）
        old_by_t = {}
        for o in old:
            if isinstance(o, dict) and o.get('t') is not None:
                old_by_t[o['t']] = o
        old_ts = sorted(old_by_t.keys())
        old_note = (it.get('quote') or {}).get('note')

        def match_old(st):
            """在旧段时间戳里找离 st 最近且 |Δ|<=T_MATCH 的，返回旧段或 None"""
            if not old_ts:
                return None
            import bisect
            i = bisect.bisect_left(old_ts, st)
            cand = []
            if i > 0:
                cand.append(old_ts[i - 1])
            if i < len(old_ts):
                cand.append(old_ts[i])
            for t in cand:
                if abs(t - st) <= T_MATCH:
                    return old_by_t[t]
            return None

        new_segs = []
        n_kept = n_new = 0
        for st, en, tx in picked:
            old_seg = match_old(st)
            if old_seg is not None and old_seg.get('text'):
                # 命中旧段：沿用已补正文本与关键句标注
                new_segs.append({'t': st, 'text': old_seg['text'],
                                 'key': bool(old_seg.get('key'))})
                n_kept += 1
            else:
                # 新增段：采用 SRT 原文
                new_segs.append({'t': st, 'text': tx, 'key': False})
                n_new += 1

        q = {
            'range': '%s–%s' % (fmt(a), fmt(b)),
            'segments': new_segs,
            'stats': {
                'lines': len(new_segs),
                'chars': sum(len(s['text']) for s in new_segs),
                'key_lines': sum(1 for s in new_segs if s['key']),
            },
        }
        if old_note:
            q['note'] = old_note
        it['quote'] = q
        if preview:
            print('--- #%d %s [%s] %d 行 / %d 字（沿用 %d，新增 %d）'
                  % (it['id'], it['title'], fmt(a) + '–' + fmt(b),
                     len(new_segs), it['quote']['stats']['chars'],
                     n_kept, n_new))

    if preview:
        print('\n（预览模式，未写回）')
        return 0

    with open(SRC_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

    total = sum(i['quote']['stats']['lines'] for i in data['items'])
    keys = sum(i['quote']['stats']['key_lines'] for i in data['items'])
    print('已写回 %s' % SRC_JSON)
    print('  观点 %d 条，共 %d 行逐字稿（关键句 %d 行）'
          % (len(data['items']), total, keys))
    return 0


if __name__ == '__main__':
    sys.exit(main())
