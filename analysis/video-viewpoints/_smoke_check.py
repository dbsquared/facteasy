#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""冒烟检查：抽出 credibility.html 的内联脚本做语法检查，并核对结构完整性。"""
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
HTML = os.path.join(ROOT, 'pages', 'credibility.html')
NODE = r'C:\Users\dbsqu\.workbuddy\binaries\node\versions\22.22.2-2\node.exe'

with open(HTML, 'r', encoding='utf-8') as f:
    html = f.read()

ok = True

# 1. 抽出 <script> 内容做语法检查
m = re.search(r'<script>(.*?)</script>', html, re.S)
if not m:
    print('[FAIL] 未找到内联 <script>')
    ok = False
else:
    js = m.group(1)
    tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_smoke.js')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(js)
    r = subprocess.run([NODE, '--check', tmp], capture_output=True, text=True)
    if r.returncode == 0:
        print('[OK]   内联 JS 语法检查通过（%d 字符）' % len(js))
    else:
        print('[FAIL] JS 语法错误：\n' + r.stderr)
        ok = False
    os.remove(tmp)

# 2. 数据占位符已替换
if '__DATA__' in html:
    print('[FAIL] 占位符 __DATA__ 未替换')
    ok = False
else:
    print('[OK]   数据占位符已替换')

# 3. 关键挂载点存在
ANCHORS = ['heroMeta', 'defGrid', 'legendNote', 'verdictBox', 'distBar', 'distLegend',
           'gradeBar', 'natureBar', 'list', 'fixList', 'wdList', 'ctrList',
           'limitList', 'empty', 'count', 'btnKeyOnly']
for anchor in ANCHORS:
    if 'id="%s"' % anchor not in html:
        print('[FAIL] 缺少挂载点 #%s' % anchor)
        ok = False
if ok:
    print('[OK]   %d 个挂载点齐全' % len(ANCHORS))

# 3b. 数据结构自检：每条观点必须有原文、出处、性质标签，且 ref 必须可解析
m2 = re.search(r'const DATA = (\{.*?\});\n', html, re.S)
if not m2:
    print('[FAIL] 未能从页面中提取 DATA')
    ok = False
else:
    import json as _json
    data = _json.loads(m2.group(1))
    items = data.get('items', [])
    problems = []
    for it in items:
        i = it.get('id')
        segs = (it.get('quote') or {}).get('segments') or []
        if not segs:
            problems.append('#%d 缺少原文 segments' % i)
        if not it.get('sources'):
            problems.append('#%d 缺少 sources' % i)
        if not it.get('natures'):
            problems.append('#%d 缺少 natures' % i)
        if not it.get('nature_basis'):
            problems.append('#%d 缺少 nature_basis' % i)
        ids = {s.get('id') for s in it.get('sources', [])}
        for key in ('holds', 'doubts'):
            for a in it.get(key, []):
                if not a.get('basis'):
                    problems.append('#%d %s 缺少 basis：%s' % (i, key, a.get('claim', '')[:20]))
                for r in a.get('ref', []):
                    if r not in ids and r not in ('Q', 'L'):
                        problems.append('#%d %s 引用了不存在的出处 %s' % (i, key, r))
                for t in a.get('tags', []):
                    if t not in data.get('nature_definitions', {}):
                        problems.append('#%d %s 未知性质标签 %s' % (i, key, t))
    if problems:
        print('[FAIL] 数据自检发现 %d 个问题：' % len(problems))
        for p in problems[:20]:
            print('       - ' + p)
        ok = False
    else:
        nseg = sum(len((it.get('quote') or {}).get('segments') or []) for it in items)
        nsrc = sum(len(it.get('sources') or []) for it in items)
        print('[OK]   数据自检通过（%d 条观点 / %d 行原文 / %d 条出处）'
              % (len(items), nseg, nsrc))

# 4. 标签配对粗查
for tag in ['section', 'article', 'script', 'style', 'div']:
    o = len(re.findall(r'<%s[ >]' % tag, html))
    c = len(re.findall(r'</%s>' % tag, html))
    if o != c:
        print('[FAIL] <%s> 配对不一致：开 %d / 闭 %d' % (tag, o, c))
        ok = False
if ok:
    print('[OK]   标签配对一致')

# 5. 导航相对路径（页面在 pages/ 下）
bad = [h for h in re.findall(r'href="([^"]+)"', html)
       if h.startswith('analysis/') and not h.startswith('../analysis/')]
if bad:
    print('[FAIL] pages/ 下相对路径错误：%s' % bad)
    ok = False
else:
    print('[OK]   相对路径正确')

print('\n结果：%s' % ('通过' if ok else '有问题'))
sys.exit(0 if ok else 1)
