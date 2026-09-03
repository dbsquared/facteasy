#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 credibility.json 生成 Markdown 版评估报告 analysis/video-viewpoints/credibility.md。

用法：
    python build_credibility_md.py

credibility.json 是唯一数据源，改完 json 重跑本脚本即可刷新 md，不要手改 md。
报告三要素与页面一致：原文逐字稿 / 出处与根据 / 来源性质标签（转述·专属·原创）。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_JSON = os.path.join(HERE, 'credibility.json')
OUT_MD = os.path.join(HERE, 'credibility.md')

TIER_TABLE = [
    ('T0', '一手史料 / 原始档案 / 典籍原文',
     '《礼记》《仪礼》、唐代避讳令原文、1972 年会谈记录、唐前译经'),
    ('T1', '官修正史 / 权威工具书 / 一手当事人记载',
     '两《唐书》、《毛选》原文、公安部户籍规范、当事人后人回忆'),
    ('T2', '权威学术专著 / 核心期刊论文 / 专业考据',
     '洪迈《容斋续笔》、现代史学辨伪论文、人物传记研究'),
    ('T3', '主流媒体 / 官方机构发布',
     '人民网、光明网、央视网、澎湃、入境事务处表格'),
    ('T4', '百科 / 聚合类自媒体', '百度百科、自媒体二次演绎'),
]

RATING_TABLE = [
    ('A', '成立。有 T0–T2 级证据直接支撑，无实质疑点'),
    ('B', '基本成立。主干可信，但需限定条件 / 表述绝对化 / 个别细节有版本差异'),
    ('C', '部分成立。方向不错但证据强度不足、举例失当或解释属推测'),
    ('D', '不成立 / 证据不足。与证据冲突，或缺乏可验证依据'),
    ('N/A', '纯价值判断或修辞，不具真伪属性，不可证伪'),
]

TIER_DEFS = dict((t[0], t[1]) for t in TIER_TABLE)
REF_LABEL = {'Q': '本视频逐字稿（见该条「原文逐字稿」）', 'L': '逻辑推演'}


def fmt(sec):
    s = max(0, int(float(sec or 0)))
    return '%02d:%02d' % (s // 60, s % 60)


def worst_grade(rating):
    order = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
    letters = re.findall(r'[ABCD]', re.sub(r'N/A', '', str(rating or '')))
    if not letters:
        return 'N/A'
    return sorted(letters, key=lambda c: order[c])[-1]


def cell(text):
    """Markdown 表格单元格：去掉换行、转义竖线。"""
    return str(text or '').replace('|', '\\|').replace('\n', ' ').strip()


def tag_of(kind, text):
    return '`%s`' % text if kind else ''


def quote_block(it):
    q = it.get('quote') or {}
    segs = q.get('segments') or []
    if not segs:
        return ''
    st = q.get('stats') or {}
    head = '**原文逐字稿**　`%s`　%d 行 / %d 字，关键句 %d 行' % (
        q.get('range') or (fmt(it['start']) + '–' + fmt(it['end'])),
        st.get('lines', len(segs)), st.get('chars', 0), st.get('key_lines', 0))
    if st.get('fix_lines'):
        head += '，勘误 %d 行' % st['fix_lines']

    lines = ['| 时间 | 原文 | 标注 |', '|---|---|---|']
    for s in segs:
        txt = cell(s.get('text', ''))
        if s.get('fix'):
            txt += '<br>↳ **勘误**：' + cell(s['fix'])
        mark = '⭐ 关键句' if s.get('key') else ''
        lines.append('| `%s` | %s | %s |' % (fmt(s.get('t')), txt, mark))
    note = '\n\n> %s' % q['note'] if q.get('note') else ''
    return '\n'.join([head, ''] + lines) + note


def sources_block(it):
    srcs = it.get('sources') or []
    if not srcs:
        return ''
    lines = ['**出处与根据**（%d 条）' % len(srcs), '',
             '| 编号 | 出处 | 类型 | 层级 | 核验 | 备注 |', '|---|---|---|---|---|---|']
    for s in srcs:
        note = s.get('note') or ''
        if s.get('url'):
            note = (note + ' ' if note else '') + '<%s>' % s['url']
        lines.append('| **`%s`** | %s | %s | %s | %s | %s |' % (
            cell(s.get('id')), cell(s.get('label')), cell(s.get('kind')),
            cell(s.get('tier')), cell(s.get('verified')), cell(note)))
    return '\n'.join(lines)


def short(text, n=22):
    text = str(text or '')
    return text if len(text) <= n else text[:n] + '…'


def arg_block(title, arr, src_map):
    if not arr:
        return ''
    out = ['**%s**（%d 条）' % (title, len(arr)), '']
    for i, a in enumerate(arr, 1):
        metas = []
        for r in (a.get('ref') or []):
            label = REF_LABEL.get(r) or short((src_map.get(r) or {}).get('label'))
            metas.append('`%s`%s' % (r, '（%s）' % cell(label) if label else ''))
        for t in (a.get('tags') or []):
            metas.append('`%s`' % t)
        out.append('%d. **%s**　%s' % (i, cell(a.get('claim')), ' '.join(metas)))
        if a.get('basis'):
            out.append('   - **根据**：' + cell(a['basis']))
    return '\n'.join(out)


def item_block(it):
    src_map = dict((s.get('id'), s) for s in (it.get('sources') or []))
    nats = ' / '.join('**%s**' % n for n in (it.get('natures') or []))

    out = ['### #%d　%s' % (it['id'], it['title']), '']

    meta = ['`%s–%s`' % (fmt(it['start']), fmt(it['end'])),
            '性质：%s' % (nats or '—')]
    if it.get('tier'):
        meta.append('权威层级：%s' % it['tier'])
    if it.get('reliability'):
        meta.append('可靠程度：%s' % it['reliability'])
    if it.get('evidence_strength'):
        meta.append('关联强度：%s' % it['evidence_strength'])
    meta.append('**评级：%s**' % it.get('rating'))
    out.append(' · '.join(meta))
    out.append('')

    if it.get('nature_basis'):
        out += ['**来源性质判断依据**：' + it['nature_basis'], '']

    qb = quote_block(it)
    if qb:
        out += [qb, '']

    sb = sources_block(it)
    if sb:
        out += [sb, '']

    hb = arg_block('成立环节', it.get('holds'), src_map)
    if hb:
        out += [hb, '']

    db = arg_block('疑点与证据不足', it.get('doubts'), src_map)
    if db:
        out += [db, '']

    for label, key in (('时效性', 'timeliness'), ('适用范围', 'scope')):
        if it.get(key):
            out += ['**%s**：%s' % (label, it[key]), '']

    if it.get('sub_ratings'):
        out += ['**子评级**：' + '；'.join('%s %s' % (k, v)
                for k, v in it['sub_ratings'].items()), '']

    if it.get('note'):
        out += ['> **按**：' + it['note'], '']

    return '\n'.join(out)


def build(data):
    v = data['video']
    a = data['assessment']
    items = data['items']
    counts = {}
    for it in items:
        counts[worst_grade(it.get('rating'))] = counts.get(worst_grade(it.get('rating')), 0) + 1

    nd = data.get('nature_definitions') or {}
    out = []
    A = out.append

    A('# 观点可信度逐条评估报告')
    A('')
    A('**评估对象**：B 站 `%s`《%s》（%s，UP 主「%s」）' % (
        v.get('bvid'), v.get('title'), fmt(v.get('duration')), v.get('uploader') or '—'))
    A('**评估范围**：`viewpoints.json` / `viewpoints.md` 中切分出的 **%d 条观点**，逐条独立评估' % len(items))
    A('**评估日期**：%s' % a.get('date'))
    A('**评估方法**：%s' % a.get('method'))
    A('**配套数据**：`viewpoints.json`（观点与时间段）、`credibility.json`（本报告的机器可读版本）')
    A('')
    A('> 本报告由 `build_credibility_md.py` 从 `credibility.json` 自动生成，请勿手改；')
    A('> 改数据后重跑 `python build_credibility_md.py` 与 `python build_credibility_page.py` 即可同步。')
    A('')
    A('---')
    A('')

    # 一、方法
    A('## 一、评估方法')
    A('')
    A('### 1.1 来源性质三标签法（可并存）')
    A('')
    A('每条观点按成分打标签，**可同时带多个**；每条论点（成立环节 / 疑点）也单独标注其所对应的成分。')
    A('')
    A('| 标签 | 定义 | 核查路径 |')
    A('|---|---|---|')
    paths = {
        '转述': '定位原始出处 → 评估该出处的权威层级 → 判断作者转述是否忠实',
        '专属': '检索是否有第二来源 → 无第二来源则按「孤证」降级，只评事实真伪不评解释',
        '原创': '自行检索证据 → 检验逻辑自洽性与可证伪性 → 判断证据与结论的关联强度',
    }
    for k in ('转述', '专属', '原创'):
        A('| **%s** | %s | %s |' % (k, nd.get(k, ''), paths[k]))
    A('')
    if data.get('nature_legend_note'):
        A('> ' + data['nature_legend_note'])
        A('')
    A('> **关键原则**：**事实为真 ≠ 解释成立**。凡带「原创」成分的观点，')
    A('> 事实骨架与解释框架分开评级（如 `事实 A / 归因 C`）。')
    A('')

    A('### 1.2 权威层级（Tier）')
    A('')
    A('| 层级 | 含义 | 本样本中的例子 |')
    A('|---|---|---|')
    for t, mean, eg in TIER_TABLE:
        A('| **%s** | %s | %s |' % (t, mean, eg))
    A('')
    A('**降级规则**：同一信息若只有 T4 来源而无上层支撑，一律不下 A 评级。')
    A('')

    A('### 1.3 综合评级')
    A('')
    A('| 评级 | 含义 |')
    A('|---|---|')
    for r, mean in RATING_TABLE:
        A('| **%s** | %s |' % (r, mean))
    A('')
    A('含子观点时按**最弱环节**计分布（如 `事实 A / 归因 C` 计入 C）。')
    A('')

    A('### 1.4 引用编号')
    A('')
    A('每条论点后的反引号编号为**根据**的来源：')
    A('')
    A('- `S1` `S2` …：该条「出处与根据」表中的编号，鼠标悬停（页面版）可见出处全称')
    A('- `Q`：本视频逐字稿，即该条「原文逐字稿」中对应时间的原话')
    A('- `L`：纯逻辑推演，无外部出处')
    A('')

    A('---')
    A('')

    # 二、总览
    A('## 二、总览表')
    A('')
    A('| # | 时间 | 观点（简称） | 来源性质 | 权威层级 | 关联强度 | 评级 |')
    A('|---|------|-------------|---------|---------|---------|------|')
    for it in items:
        A('| %d | %s–%s | %s | %s | %s | %s | **%s** |' % (
            it['id'], fmt(it['start']), fmt(it['end']), cell(it['title']),
            ' + '.join(it.get('natures') or ['—']), cell(it.get('tier') or '—'),
            cell(it.get('evidence_strength') or '—'), it.get('rating')))
    A('')
    dist = '　'.join('%s %d 条' % (k, counts[k])
                    for k in ('A', 'B', 'C', 'D', 'N/A') if counts.get(k))
    A('**评级分布**（按最弱环节）：%s，共 %d 条' % (dist, len(items)))
    A('')
    A('---')
    A('')

    # 三、逐条
    A('## 三、逐条评估')
    A('')
    for it in items:
        A(item_block(it))
        A('---')
        A('')

    # 四、修正
    A('## 四、需要修正的具体问题')
    A('')
    fixes = data.get('corrections_needed') or []
    if fixes:
        for f in fixes:
            A('- **#%d %s** —— %s' % (f['id'], f.get('issue'), f.get('impact')))
    else:
        A('暂无')
    A('')

    wd = data.get('corrections_withdrawn') or []
    if wd:
        A('### 已撤销的修正项（分析方自身的错误）')
        A('')
        for f in wd:
            A('- ~~**#%d %s**~~ —— %s%s' % (
                f['id'], f.get('issue'), f.get('reason'),
                '（撤销于 %s）' % f['withdrawn_at'] if f.get('withdrawn_at') else ''))
        A('')

    A('---')
    A('')

    # 五、内部矛盾
    A('## 五、论证结构上的内部矛盾')
    A('')
    ctrs = data.get('internal_contradictions') or []
    if ctrs:
        for c in ctrs:
            A('**涉及观点**：%s' % '、'.join('#%d' % i for i in (c.get('items') or [])))
            A('')
            A('- 矛盾：%s' % c.get('description'))
            A('- 调和口径：%s' % c.get('suggested_resolution'))
            A('')
    else:
        A('暂无')
        A('')

    A('---')
    A('')

    # 六、总体结论
    o = data.get('overall') or {}
    A('## 六、总体结论')
    A('')
    A('**%s**' % o.get('verdict', ''))
    A('')
    A('**站得住的部分**')
    A('')
    for x in (o.get('strengths') or []):
        A('- %s' % x)
    A('')
    A('**站不住的部分**')
    A('')
    for x in (o.get('weaknesses') or []):
        A('- %s' % x)
    A('')
    A('---')
    A('')

    # 七、限制
    A('## 七、方法与限制')
    A('')
    for x in (data.get('limitations') or []):
        A('- %s' % x)
    A('')

    return '\n'.join(out) + '\n'


def main():
    with open(SRC_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    md = build(data)
    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write(md)

    items = data['items']
    print('生成完成: %s' % OUT_MD)
    print('  观点条目: %d 条' % len(items))
    print('  原文行: %d 行' % sum(len((it.get('quote') or {}).get('segments') or []) for it in items))
    print('  出处条目: %d 条' % sum(len(it.get('sources') or []) for it in items))
    print('  文件大小: %.1f KB' % (os.path.getsize(OUT_MD) / 1024.0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
