#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 viewpoints.json + credibility.json 打包成站点共享数据 pages/facteasy-data.js。

用法：
    python build_site_data.py

用途：
    sync-player.html（同步阅读器）用 <script src="facteasy-data.js"> 引入，
    把「观点时间轴」与「可信度核查结果」合到同一个页面里随播放进度联动。

    credibility.html 走的是内联路线（单文件、file:// 可直接打开），不依赖本文件；
    本文件只服务于同步阅读器，所以在保证字段完整的前提下做了精简，控制体积。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
VP_JSON = os.path.join(HERE, 'viewpoints.json')
CR_JSON = os.path.join(HERE, 'credibility.json')
OUT_JS = os.path.join(ROOT, 'pages', 'facteasy-data.js')

# credibility item 中同步阅读器需要展示的字段（其余不输出，控制体积）
KEEP = ['id', 'start', 'end', 'title', 'natures', 'nature_basis', 'tier',
        'reliability', 'evidence_strength', 'sources', 'holds', 'doubts',
        'quote', 'rating', 'note']


def main():
    with open(VP_JSON, 'r', encoding='utf-8') as f:
        viewpoints = json.load(f)
    with open(CR_JSON, 'r', encoding='utf-8') as f:
        cred = json.load(f)

    items = []
    for it in cred.get('items', []):
        slim = dict((k, it[k]) for k in KEEP if k in it)
        # 时间码以 viewpoints.json 为准（同源），避免两份数据漂移
        items.append(slim)

    payload = {
        'generated': cred.get('assessment', {}).get('date', ''),
        'viewpoints': viewpoints,
        'credibility': {
            'date': cred.get('assessment', {}).get('date', ''),
            'method': cred.get('assessment', {}).get('method', ''),
            'counts': cred.get('assessment', {}).get('counts', {}),
            'nature_definitions': cred.get('nature_definitions', {}),
            'items': items
        }
    }

    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    js = ('/* 自动生成，勿手改。改 viewpoints.json / credibility.json 后重跑：\n'
          '   python build_site_data.py\n'
          '   数据源：analysis/video-viewpoints/  →  消费方：pages/sync-player.html */\n'
          'window.FACTEASY_DATA = ' + body + ';\n')

    out_dir = os.path.dirname(OUT_JS)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(OUT_JS, 'w', encoding='utf-8') as f:
        f.write(js)

    n_src = sum(len(it.get('sources', [])) for it in items)
    n_line = sum(it.get('quote', {}).get('stats', {}).get('lines', 0) for it in items)
    print('生成完成: %s' % OUT_JS)
    print('  观点章节: %d 条（viewpoints.json）' % len(viewpoints))
    print('  核查条目: %d 条 / 出处 %d 条 / 原文 %d 行' % (len(items), n_src, n_line))
    print('  文件大小: %.1f KB' % (os.path.getsize(OUT_JS) / 1024.0))

    # 交叉校验：两份数据的 id / 时间码必须一致
    vp = dict((v['id'], v) for v in viewpoints)
    bad = []
    for it in items:
        v = vp.get(it['id'])
        if not v:
            bad.append('#%d 在 viewpoints.json 中缺失' % it['id'])
            continue
        if abs(v['start'] - it['start']) > 0.01 or abs(v['end'] - it['end']) > 0.01:
            bad.append('#%d 时间码不一致：viewpoints %s–%s vs credibility %s–%s'
                       % (it['id'], v['start'], v['end'], it['start'], it['end']))
    if bad:
        print('\n[WARN] 两份数据不一致 %d 处：' % len(bad))
        for b in bad[:10]:
            print('  - ' + b)
        return 1
    print('  交叉校验: id 与时间码一致')
    return 0


if __name__ == '__main__':
    sys.exit(main())
