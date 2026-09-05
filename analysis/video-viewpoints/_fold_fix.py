#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一次性迁移：把 credibility.json 里每段的「勘误 fix」直接落进 text，并删除 fix 字段。

背景：之前 ASR 同音讹误用 text(原始) + fix(勘误) 两栏表示，渲染时在每行下方灰字显示
「勘误：…」。用户要求「勘误的地方直接把文本改了」→ text 落成修正后文字，不再保留
fix 字段，UI 也不再显示独立「勘误」行。

动作（只动 quote 内部，其余字段一律不动）：
  1. 每段：若 s.fix 存在 → s.text = s.fix，删除 s.fix。
  2. stats：重算 chars；删除 fix_lines。
  3. quote.note：去掉「标注「勘误」的行为按语义与史实补正后的文本」，改为说明文本
     已是按语义与史实补正后的转写。
用法：python _fold_fix.py            # 写回
      python _fold_fix.py --preview # 预览统计，不写回
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'credibility.json')

NEW_NOTE = ('逐字稿由 Whisper（faster-whisper-medium）自动转写，存在同音讹误；'
            '文本已按语义与史实逐条补正。⭐ 为该观点的关键句。')


def main():
    preview = '--preview' in sys.argv
    with open(SRC, 'r', encoding='utf-8') as f:
        data = json.load(f)

    n_fold = 0
    n_seg = 0
    items_touched = 0
    for it in data.get('items', []):
        q = it.get('quote') or {}
        segs = q.get('segments') or []
        touched = False
        for s in segs:
            if isinstance(s, dict):
                n_seg += 1
                if 'fix' in s:
                    s['text'] = s['fix']
                    del s['fix']
                    n_fold += 1
                    touched = True
        if touched:
            items_touched += 1
        # 重算 chars（若 stats 存在）
        st = q.get('stats')
        if isinstance(st, dict):
            st['chars'] = sum(len(x.get('text', '')) for x in segs if isinstance(x, dict))
            st.pop('fix_lines', None)
        # 更新 note
        if 'quote' in it and it['quote'].get('note') is not None:
            it['quote']['note'] = NEW_NOTE

    print('段总数 %d，其中含 fix 的 %d 段已落库；涉及 %d 个观点。' % (n_seg, n_fold, items_touched))
    # 校验：不应再有任何 fix 残留
    leftover = 0
    for it in data.get('items', []):
        for s in (it.get('quote') or {}).get('segments') or []:
            if 'fix' in s:
                leftover += 1
    print('残留 fix 字段：%d（应为 0）' % leftover)

    if preview:
        print('\n（预览模式，未写回）')
        return 0 if leftover == 0 else 1

    with open(SRC, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print('已写回 %s' % SRC)
    return 0 if leftover == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
