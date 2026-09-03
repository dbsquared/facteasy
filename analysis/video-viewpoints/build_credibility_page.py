#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 credibility.json 生成可交互的可信度评估页面 pages/credibility.html。

用法：
    python build_credibility_page.py

说明：
    credibility.json 是唯一数据源，改完 json 重跑本脚本即可刷新页面，
    不需要手改 HTML。数据以 JS 对象内联进页面，因此 file:// 直接打开也能用。

页面呈现三块核心内容（对应数据里的新结构）：
    1. 原文逐字稿   —— item.quote.segments（含关键句高亮与 ASR 勘误）
    2. 出处与根据   —— item.sources[]（编号 / 类型 / 权威层级 / 核验状态 / 链接）
                      + holds[]、doubts[] 每条的 basis 与 ref 引用
    3. 来源性质标签 —— item.natures[]（转述 / 专属 / 原创，可多标签并存）
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SRC_JSON = os.path.join(HERE, 'credibility.json')
OUT_HTML = os.path.join(ROOT, 'pages', 'credibility.html')


def worst_grade(rating):
    """复合评级（如 '事实 A / 动机解读 C'）取最弱环节。"""
    order = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
    letters = re.findall(r'[ABCD]', re.sub(r'N/A', '', str(rating or '')))
    if not letters:
        return 'N/A'
    return sorted(letters, key=lambda c: order[c])[-1]


def compute_counts(items):
    counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'N/A': 0}
    for it in items:
        counts[worst_grade(it.get('rating'))] += 1
    counts['total'] = len(items)
    return counts


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>观点可信度评估 · FactEasy</title>
<style>
  :root{
    --bg:#0b0e13;
    --bg-soft:#11161f;
    --panel:#151b25;
    --panel-2:#1a222e;
    --line:#252d3a;
    --line-soft:#1e2632;
    --txt:#e7edf5;
    --txt-dim:#9aa7b8;
    --txt-faint:#66748a;
    --accent:#e0a45a;
    --accent-soft:rgba(224,164,90,.14);
    --accent-2:#7fb2ff;
    --ok:#4ec9a0;
    --radius:14px;
    --ga:#4ec9a0;
    --gb:#7fb2ff;
    --gc:#e0a45a;
    --gd:#e8695a;
    --gn:#8b94a3;
    --gp:#b48ef0;
  }
  *{box-sizing:border-box;}
  body{
    margin:0;min-height:100vh;
    background:
      radial-gradient(1200px 600px at 15% -10%, rgba(224,164,90,.07), transparent 60%),
      radial-gradient(900px 500px at 100% 0%, rgba(127,178,255,.06), transparent 55%),
      var(--bg);
    color:var(--txt);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
    font-size:15px;line-height:1.65;-webkit-font-smoothing:antialiased;
  }
  a{color:var(--accent-2);text-decoration:none;}
  ::selection{background:rgba(224,164,90,.28);}

  .topbar{
    display:flex;align-items:center;gap:18px;flex-wrap:wrap;
    padding:14px 26px;border-bottom:1px solid var(--line-soft);
    background:rgba(11,14,19,.85);backdrop-filter:blur(10px);
    position:sticky;top:0;z-index:50;
  }
  .brand{display:flex;align-items:center;gap:10px;}
  .brand .logo{
    width:26px;height:26px;border-radius:8px;
    background:linear-gradient(135deg,var(--accent),#c9833c);
    display:grid;place-items:center;font-size:14px;font-weight:800;color:#241703;
  }
  .brand .name{font-size:16px;font-weight:700;}
  .brand .sub{font-size:11.5px;color:var(--txt-faint);}
  .tb-spacer{flex:1;}
  nav.mainnav{display:flex;align-items:center;gap:4px;flex-wrap:wrap;}
  nav.mainnav a{
    color:var(--txt-dim);font-size:13.5px;padding:7px 13px;
    border-radius:9px;transition:background .15s,color .15s;white-space:nowrap;
  }
  nav.mainnav a:hover{background:var(--panel-2);color:var(--txt);}
  nav.mainnav a.here{color:var(--accent);background:var(--accent-soft);}

  .wrap{max-width:1180px;margin:0 auto;padding:0 26px 72px;}

  .hero{padding:44px 0 10px;}
  .eyebrow{
    display:inline-flex;align-items:center;gap:8px;
    font-size:12px;color:var(--accent);
    border:1px solid rgba(224,164,90,.3);background:var(--accent-soft);
    padding:5px 12px;border-radius:999px;margin-bottom:16px;
  }
  h1{margin:0 0 10px;font-size:clamp(24px,3.2vw,32px);font-weight:720;letter-spacing:-.3px;}
  .lede{margin:0 0 18px;color:var(--txt-dim);font-size:14.5px;max-width:820px;}
  .hero-meta{display:flex;gap:8px;flex-wrap:wrap;font-size:12px;color:var(--txt-faint);}
  .hero-meta span{
    border:1px solid var(--line);background:var(--panel);
    padding:3px 10px;border-radius:999px;
  }

  section{padding:26px 0;}
  .sec-head{display:flex;align-items:baseline;gap:12px;margin-bottom:16px;}
  h2{margin:0;font-size:19px;font-weight:680;letter-spacing:.2px;}
  .sec-head .note{font-size:12.5px;color:var(--txt-faint);}

  .verdict{
    background:linear-gradient(180deg,var(--panel) 0%,var(--bg-soft) 100%);
    border:1px solid var(--line-soft);border-left:3px solid var(--accent);
    border-radius:var(--radius);padding:20px 22px;
  }
  .verdict .big{font-size:16px;color:var(--accent);font-weight:600;margin-bottom:12px;}
  .verdict p{margin:0 0 10px;color:var(--txt-dim);font-size:13.5px;}
  .two{display:grid;grid-template-columns:1fr 1fr;gap:18px;}
  @media (max-width:820px){.two{grid-template-columns:1fr;}}
  .verdict h4{margin:0 0 8px;font-size:13px;font-weight:600;color:var(--txt);}
  .verdict ul{margin:0;padding-left:18px;color:var(--txt-dim);font-size:13px;}
  .verdict li{margin-bottom:5px;}

  .defgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;}
  @media (max-width:820px){.defgrid{grid-template-columns:1fr;}}
  .defcard{
    background:var(--panel);border:1px solid var(--line-soft);
    border-radius:11px;padding:13px 15px;
  }
  .defcard h4{margin:0 0 6px;font-size:13.5px;display:flex;align-items:center;gap:8px;}
  .defcard p{margin:0;font-size:12.5px;color:var(--txt-dim);}
  .legendnote{
    margin-top:12px;font-size:12.5px;color:var(--txt-faint);
    background:var(--panel);border:1px solid var(--line-soft);
    border-left:3px solid var(--gp);border-radius:9px;padding:10px 13px;
  }

  .distwrap{
    background:linear-gradient(180deg,var(--panel) 0%,var(--bg-soft) 100%);
    border:1px solid var(--line-soft);border-radius:var(--radius);padding:18px 20px;
  }
  .distbar{display:flex;height:26px;border-radius:8px;overflow:hidden;gap:2px;}
  .distbar div{
    display:grid;place-items:center;font-size:12px;font-weight:600;color:#0b0e13;
    min-width:0;overflow:hidden;
  }
  .distlegend{display:flex;gap:14px;flex-wrap:wrap;margin-top:12px;font-size:12.5px;color:var(--txt-dim);}
  .distlegend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;}

  .toolbar{
    margin-bottom:16px;padding:14px 16px;
    background:linear-gradient(180deg,var(--panel) 0%,var(--bg-soft) 100%);
    border:1px solid var(--line-soft);border-radius:var(--radius);
    display:flex;flex-direction:column;gap:11px;
  }
  .tb-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap;}
  .search{
    flex:1;min-width:220px;display:flex;align-items:center;gap:8px;
    background:var(--bg-soft);border:1px solid var(--line);
    border-radius:10px;padding:8px 12px;
  }
  .search input{flex:1;background:transparent;border:0;outline:0;color:var(--txt);font-size:13.5px;font-family:inherit;}
  .search input::placeholder{color:var(--txt-faint);}
  .count{font-size:12.5px;color:var(--txt-faint);white-space:nowrap;}
  .count b{color:var(--accent);}
  .btn-mini{
    font-size:12px;padding:5px 11px;border-radius:8px;cursor:pointer;
    background:var(--panel-2);border:1px solid var(--line);color:var(--txt-dim);
    transition:color .14s,border-color .14s;
  }
  .btn-mini:hover{color:var(--accent);border-color:rgba(224,164,90,.4);}
  .btn-mini.on{color:var(--accent);background:var(--accent-soft);border-color:rgba(224,164,90,.45);}
  .tagbar{display:flex;align-items:center;gap:7px;flex-wrap:wrap;}
  .tagbar .lbl{font-size:12px;color:var(--txt-faint);margin-right:2px;}
  .chip{
    font-size:12px;padding:4px 11px;border-radius:999px;cursor:pointer;
    border:1px solid var(--line);background:var(--panel-2);color:var(--txt-dim);
    transition:background .15s,color .15s,border-color .15s;user-select:none;
  }
  .chip:hover{border-color:#3a465a;color:var(--txt);}
  .chip.on{color:var(--accent);background:var(--accent-soft);border-color:rgba(224,164,90,.45);}
  .chip.on.ga{color:var(--ga);background:rgba(78,201,160,.14);border-color:rgba(78,201,160,.45);}
  .chip.on.gb{color:var(--gb);background:rgba(127,178,255,.14);border-color:rgba(127,178,255,.45);}
  .chip.on.gc{color:var(--gc);background:var(--accent-soft);border-color:rgba(224,164,90,.45);}
  .chip.on.gd{color:var(--gd);background:rgba(232,105,90,.14);border-color:rgba(232,105,90,.45);}
  .chip.on.gn{color:var(--gn);background:rgba(139,148,163,.14);border-color:rgba(139,148,163,.45);}
  .chip.on.gp{color:var(--gp);background:rgba(180,142,240,.14);border-color:rgba(180,142,240,.45);}
  .chip .n{opacity:.65;margin-left:4px;font-size:11px;}

  .list{display:flex;flex-direction:column;gap:10px;}
  .claim{
    background:linear-gradient(180deg,var(--panel) 0%,var(--bg-soft) 100%);
    border:1px solid var(--line-soft);border-left:3px solid var(--line);
    border-radius:var(--radius);overflow:hidden;transition:border-color .15s;
  }
  .claim:hover{border-color:#334052;}
  .claim.ga{border-left-color:var(--ga);}
  .claim.gb{border-left-color:var(--gb);}
  .claim.gc{border-left-color:var(--gc);}
  .claim.gd{border-left-color:var(--gd);}
  .claim.gn{border-left-color:var(--gn);}
  .claim-head{
    display:flex;align-items:center;gap:12px;width:100%;
    padding:14px 16px;background:transparent;border:0;cursor:pointer;
    color:inherit;font:inherit;text-align:left;
  }
  .claim-head:focus-visible{outline:2px solid var(--accent-2);outline-offset:-2px;}
  .num{
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    font-size:12px;color:var(--txt-faint);flex:0 0 auto;
  }
  .tc{
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    font-size:11.5px;color:var(--accent-2);flex:0 0 auto;
    border:1px solid var(--line);border-radius:6px;padding:1px 6px;
  }
  .tc:hover{background:rgba(127,178,255,.12);}
  .ttl{flex:1;font-size:14px;font-weight:600;line-height:1.5;min-width:0;}
  .natwrap{display:flex;gap:5px;flex:0 0 auto;}
  .nat{
    font-size:11.5px;padding:3px 9px;border-radius:6px;white-space:nowrap;
    border:1px solid var(--line);background:var(--panel-2);color:var(--txt-dim);
  }
  .nat.t-zhuan{color:var(--gb);border-color:rgba(127,178,255,.35);background:rgba(127,178,255,.10);}
  .nat.t-excl{color:var(--gc);border-color:rgba(224,164,90,.35);background:var(--accent-soft);}
  .nat.t-orig{color:var(--gp);border-color:rgba(180,142,240,.35);background:rgba(180,142,240,.10);}
  .grade{
    font-size:12.5px;font-weight:600;flex:0 0 auto;min-width:44px;text-align:center;
    padding:3px 8px;border-radius:7px;
  }
  .grade.ga{color:var(--ga);background:rgba(78,201,160,.14);}
  .grade.gb{color:var(--gb);background:rgba(127,178,255,.14);}
  .grade.gc{color:var(--gc);background:var(--accent-soft);}
  .grade.gd{color:var(--gd);background:rgba(232,105,90,.14);}
  .grade.gn{color:var(--gn);background:rgba(139,148,163,.14);}
  .caret{flex:0 0 auto;color:var(--txt-faint);font-size:12px;transition:transform .18s;}
  .claim.open .caret{transform:rotate(180deg);}
  .claim-body{display:none;padding:0 16px 16px;border-top:1px solid var(--line-soft);}
  .claim.open .claim-body{display:block;}

  .metarow{
    display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 14px;
    padding-bottom:14px;border-bottom:1px dashed var(--line-soft);
    font-size:12px;color:var(--txt-dim);align-items:center;
  }
  .metarow span{
    background:var(--panel-2);border:1px solid var(--line);
    padding:3px 9px;border-radius:6px;
  }
  .metarow b{color:var(--txt-faint);font-weight:400;margin-right:4px;}
  .blk{margin-bottom:16px;}
  .blk h4{
    margin:0 0 8px;font-size:12.5px;font-weight:600;color:var(--txt);
    display:flex;align-items:center;gap:6px;
  }
  .blk h4::before{content:"";width:3px;height:12px;border-radius:2px;background:var(--txt-faint);}
  .blk.ok h4::before{background:var(--ok);}
  .blk.warn h4::before{background:var(--gc);}
  .blk p{margin:0;color:var(--txt-dim);font-size:13px;}
  .blk ul{margin:0;padding-left:18px;color:var(--txt-dim);font-size:13px;}
  .blk li{margin-bottom:5px;}
  .blk li::marker{color:var(--txt-faint);}

  /* ---- 原文逐字稿 ---- */
  .qt{border:1px solid var(--line-soft);border-radius:11px;overflow:hidden;}
  .qt-head{
    display:flex;align-items:center;gap:10px;flex-wrap:wrap;
    padding:8px 12px;background:var(--panel-2);border-bottom:1px solid var(--line-soft);
    font-size:11.5px;color:var(--txt-faint);
  }
  .qt-head .rng{font-family:ui-monospace,Menlo,Consolas,monospace;color:var(--accent-2);}
  .qt-head .sp{flex:1;}
  .qt-toggle{
    font-size:11px;padding:2px 9px;border-radius:6px;cursor:pointer;
    border:1px solid var(--line);background:var(--panel);color:var(--txt-dim);
  }
  .qt-toggle:hover{color:var(--accent);border-color:rgba(224,164,90,.4);}
  .qt-toggle.on{color:var(--accent);background:var(--accent-soft);border-color:rgba(224,164,90,.45);}
  .qt-lines{padding:8px 12px;display:flex;flex-direction:column;gap:3px;}
  .ql{display:flex;gap:10px;align-items:baseline;}
  .ql .t{
    flex:0 0 auto;font-family:ui-monospace,Menlo,Consolas,monospace;
    font-size:11px;color:var(--txt-faint);width:42px;text-align:right;
  }
  .ql .x{flex:1;font-size:13px;color:var(--txt-dim);padding-left:8px;border-left:2px solid transparent;}
  .ql.key .x{
    color:var(--txt);border-left-color:var(--accent);
    background:linear-gradient(90deg,rgba(224,164,90,.11),transparent 70%);
  }
  .ql .qfix{
    display:block;font-size:11.5px;color:var(--gc);opacity:.9;margin-top:1px;
  }
  .ql .qfix::before{content:"勘误：";opacity:.7;}
  .qt-note{
    padding:7px 12px;border-top:1px dashed var(--line-soft);
    font-size:11.5px;color:var(--txt-faint);background:rgba(26,34,46,.4);
  }

  /* ---- 出处与根据 ---- */
  .srclist{display:flex;flex-direction:column;gap:8px;}
  .src{
    padding:10px 12px;background:var(--panel-2);
    border:1px solid var(--line-soft);border-radius:9px;
  }
  .src .top{display:flex;gap:9px;align-items:baseline;}
  .src .sid{
    flex:0 0 auto;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11px;
    color:var(--accent);border:1px solid rgba(224,164,90,.3);
    background:var(--accent-soft);padding:1px 7px;border-radius:5px;
  }
  .src .slab{flex:1;font-size:13px;color:var(--txt);}
  .src .smeta{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px;}
  .src .smeta span{
    font-size:11px;padding:1px 7px;border-radius:5px;
    background:var(--panel);border:1px solid var(--line);color:var(--txt-dim);
  }
  .src .smeta .tier{color:var(--gb);border-color:rgba(127,178,255,.3);}
  .src .smeta .ver{color:var(--ga);border-color:rgba(78,201,160,.3);}
  .src .smeta .ver.no{color:var(--gc);border-color:rgba(224,164,90,.3);}
  .src .snote{margin-top:5px;font-size:12px;color:var(--txt-faint);}
  .src .slink{margin-top:5px;font-size:12px;word-break:break-all;}

  /* ---- 论证条目 ---- */
  .arglist{display:flex;flex-direction:column;gap:9px;}
  .arg{
    padding:10px 12px;background:var(--panel-2);
    border:1px solid var(--line-soft);border-radius:9px;
  }
  .arg .aclaim{font-size:13.5px;color:var(--txt);font-weight:600;}
  .arg .abas{margin-top:4px;font-size:12.5px;color:var(--txt-dim);}
  .arg .abas b{color:var(--txt-faint);font-weight:400;}
  .arg .ameta{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:6px;}
  .ref{
    font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11px;
    color:var(--accent-2);border:1px solid var(--line);
    background:var(--panel);padding:0 6px;border-radius:4px;cursor:help;
  }
  .tag-mini{font-size:11px;padding:1px 7px;border-radius:5px;background:var(--panel);border:1px solid var(--line);color:var(--txt-dim);}
  .tag-mini.t-zhuan{color:var(--gb);border-color:rgba(127,178,255,.3);}
  .tag-mini.t-excl{color:var(--gc);border-color:rgba(224,164,90,.3);}
  .tag-mini.t-orig{color:var(--gp);border-color:rgba(180,142,240,.3);}
  .blk.ok .arg{border-left:2px solid rgba(78,201,160,.45);}
  .blk.warn .arg{border-left:2px solid rgba(224,164,90,.45);}

  .subs{display:flex;gap:7px;flex-wrap:wrap;margin-top:4px;}
  .subs span{
    font-size:12px;padding:3px 10px;border-radius:6px;
    background:var(--panel-2);border:1px solid var(--line);color:var(--txt-dim);
  }
  .subs b{color:var(--txt);font-weight:600;}
  .noteit{
    margin-top:12px;padding:10px 12px;border-radius:9px;
    background:var(--panel-2);border:1px solid var(--line-soft);
    font-size:12.5px;color:var(--txt-faint);
  }

  .fixlist{display:flex;flex-direction:column;gap:10px;}
  .fix{
    display:flex;gap:12px;padding:13px 16px;background:var(--panel);
    border:1px solid var(--line-soft);border-left:3px solid var(--gd);
    border-radius:11px;font-size:13.5px;color:var(--txt-dim);
  }
  .fix .k{
    flex:0 0 auto;font-family:ui-monospace,Menlo,Consolas,monospace;
    font-size:11.5px;color:var(--accent);border:1px solid rgba(224,164,90,.3);
    background:var(--accent-soft);padding:2px 8px;border-radius:6px;height:fit-content;
  }
  .fix .t{flex:1;}
  .fix .t b{color:var(--txt);font-weight:600;display:block;margin-bottom:3px;}
  .fix.wd{border-left-color:var(--gn);}
  .fix.wd .k{color:var(--gn);border-color:rgba(139,148,163,.35);background:rgba(139,148,163,.12);}
  .fix.wd .t{color:var(--txt-faint);}
  .fix.wd .t b{text-decoration:line-through;opacity:.75;}

  .ctr{
    padding:15px 17px;background:var(--panel);border:1px solid var(--line-soft);
    border-left:3px solid var(--gc);border-radius:11px;margin-bottom:10px;
  }
  .ctr .items{font-size:11.5px;color:var(--txt-faint);margin-bottom:6px;}
  .ctr .d{font-size:13.5px;color:var(--txt-dim);margin-bottom:8px;}
  .ctr .r{font-size:13px;color:var(--ok);}
  .ctr .r b{color:var(--ok);font-weight:600;}

  .limits{margin:0;padding-left:18px;color:var(--txt-faint);font-size:12.5px;}
  .limits li{margin-bottom:5px;}

  .empty{padding:44px 16px;text-align:center;color:var(--txt-faint);font-size:13.5px;}

  footer{
    margin-top:26px;padding-top:18px;border-top:1px solid var(--line-soft);
    color:var(--txt-faint);font-size:12.5px;
    display:flex;gap:14px;flex-wrap:wrap;align-items:center;
  }
  footer .spacer{flex:1;}

  @media (max-width:640px){
    .topbar{padding:12px 16px;}
    .wrap{padding:0 16px 56px;}
    .hero{padding:32px 0 8px;}
    .claim-head{flex-wrap:wrap;gap:8px;}
    .ttl{flex:1 0 100%;order:3;}
  }
</style>
</head>
<body>

  <header class="topbar">
    <div class="brand">
      <div class="logo">F</div>
      <div>
        <div class="name">FactEasy</div>
        <div class="sub">事实核查工作台</div>
      </div>
    </div>
    <div class="tb-spacer"></div>
    <nav class="mainnav" aria-label="主导航">
      <a href="../index.html">首页</a>
      <a href="../videos.html">视频列表</a>
      <a href="sync-player.html">同步阅读器</a>
      <a href="../analysis/video-viewpoints/viewpoints.md">观点数据</a>
      <a href="credibility.html" class="here">可信度报告</a>
      <a href="../index.html#docs">研究文档</a>
    </nav>
  </header>

  <div class="wrap">

    <section class="hero">
      <div class="eyebrow">● 观点可信度 · 逐条评估</div>
      <h1 id="h1">观点可信度评估</h1>
      <p class="lede">
        对切分出的每条观点给出<b>原文逐字稿</b>（关键句高亮、ASR 同音讹误逐条勘误），
        判定来源性质（<b style="color:var(--gb)">转述</b> / <b style="color:var(--gc)">专属</b> / <b style="color:var(--gp)">原创</b>，可并存），
        <b>逐条列出出处与根据</b>（类型、权威层级 T0–T4、核验状态与链接），
        再据此给出综合评级。
      </p>
      <div class="hero-meta" id="heroMeta"></div>
    </section>

    <section id="tags">
      <div class="sec-head">
        <h2>来源性质标签</h2>
        <span class="note">一条观点可同时带多个标签</span>
      </div>
      <div class="defgrid" id="defGrid"></div>
      <div class="legendnote" id="legendNote"></div>
    </section>

    <section id="summary">
      <div class="sec-head">
        <h2>总体结论</h2>
        <span class="note">主干 · 例证 · 归因</span>
      </div>
      <div class="verdict" id="verdictBox"></div>
    </section>

    <section id="dist">
      <div class="sec-head">
        <h2>评级分布</h2>
        <span class="note">含子观点时按最弱环节计</span>
      </div>
      <div class="distwrap">
        <div class="distbar" id="distBar"></div>
        <div class="distlegend" id="distLegend"></div>
      </div>
    </section>

    <section id="claims">
      <div class="sec-head">
        <h2>逐条评估</h2>
        <span class="note">点击卡片展开原文、出处与论证</span>
      </div>

      <div class="toolbar">
        <div class="tb-row">
          <label class="search">
            <span style="color:var(--txt-faint);font-size:13px;">&#128269;</span>
            <input id="q" type="search" placeholder="搜索观点、原文、出处、根据…" autocomplete="off">
          </label>
          <span class="count" id="count">共 <b>0</b> 条</span>
          <button class="btn-mini" id="btnKeyOnly">原文：全部</button>
          <button class="btn-mini" id="btnExpand">展开全部</button>
          <button class="btn-mini" id="btnCollapse">收起全部</button>
        </div>
        <div class="tagbar" id="gradeBar"><span class="lbl">评级：</span></div>
        <div class="tagbar" id="natureBar"><span class="lbl">性质（可多选）：</span></div>
      </div>

      <div class="list" id="list"></div>
      <div class="empty" id="empty" style="display:none;">没有匹配的观点</div>
    </section>

    <section id="fixes">
      <div class="sec-head">
        <h2>需要修正的具体问题</h2>
        <span class="note" id="fixNote"></span>
      </div>
      <div class="fixlist" id="fixList"></div>
      <div class="fixlist" id="wdList" style="margin-top:10px;"></div>
    </section>

    <section id="ctr">
      <div class="sec-head">
        <h2>论证结构上的内部矛盾</h2>
        <span class="note">同一内容中互斥的多个解释</span>
      </div>
      <div id="ctrList"></div>
    </section>

    <section id="limits">
      <div class="sec-head">
        <h2>方法与限制</h2>
        <span class="note">核查边界</span>
      </div>
      <ul class="limits" id="limitList"></ul>
    </section>

    <footer>
      <span>FactEasy · 观点可信度评估</span>
      <span class="spacer"></span>
      <a href="credibility.html">回到顶部</a>
      <a href="../analysis/video-viewpoints/credibility.md">Markdown 原文</a>
      <a href="../analysis/video-viewpoints/credibility.json">JSON 数据</a>
    </footer>

  </div>

<script>
const DATA = __DATA__;

const NATURE = {
  '转述': { cls: 't-zhuan', chip: 'gb', short: '转述' },
  '专属': { cls: 't-excl', chip: 'gc', short: '专属' },
  '原创': { cls: 't-orig', chip: 'gp', short: '原创' }
};
const NATURE_ORDER = ['转述', '专属', '原创'];

const GRADE_META = {
  'A':    { name: '成立',         color: 'var(--ga)', cls: 'ga' },
  'B':    { name: '基本成立',      color: 'var(--gb)', cls: 'gb' },
  'C':    { name: '部分成立',      color: 'var(--gc)', cls: 'gc' },
  'D':    { name: '不足 / 不成立', color: 'var(--gd)', cls: 'gd' },
  'N/A':  { name: '不可证伪',      color: 'var(--gn)', cls: 'gn' }
};
const ORDER = { 'A': 0, 'B': 1, 'C': 2, 'D': 3, 'N/A': 9 };

const REF_LABEL = { 'Q': '本视频逐字稿', 'L': '逻辑推演' };

const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

function fmt(sec){
  const s = Math.max(0, Math.floor(Number(sec) || 0));
  return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
}

/* 含子观点时按最弱环节取色 */
function worstGrade(it){
  const m = String(it.rating || '').replace(/N\/A/g, '').match(/[ABCD]/g);
  if(!m) return 'N/A';
  return m.slice().sort((a, b) => ORDER[a] - ORDER[b]).pop();
}

const ITEMS = DATA.items.map((it) => Object.assign({}, it, { _g: worstGrade(it) }));

/* ---------- Hero ---------- */
(function(){
  const v = DATA.video, a = DATA.assessment;
  document.getElementById('h1').textContent = '观点可信度评估';
  document.getElementById('heroMeta').innerHTML = [
    '<span>' + esc(v.platform === 'bilibili' ? 'B 站' : v.platform) + ' ' + esc(v.bvid) + '</span>',
    '<span>' + esc(v.title) + '</span>',
    '<span>时长 ' + fmt(v.duration) + '</span>',
    '<span>观点 ' + a.counts.total + ' 条</span>',
    '<span>出处 ' + ITEMS.reduce((n, it) => n + (it.sources || []).length, 0) + ' 条</span>',
    '<span>评估日期 ' + esc(a.date) + '</span>'
  ].join('');
})();

/* ---------- 标签定义 ---------- */
(function(){
  const defs = DATA.nature_definitions || {};
  document.getElementById('defGrid').innerHTML = NATURE_ORDER.map((k) => {
    const n = NATURE[k];
    return '<div class="defcard"><h4><span class="nat ' + n.cls + '">' + k + '</span></h4>' +
           '<p>' + esc(defs[k] || '') + '</p></div>';
  }).join('');
  document.getElementById('legendNote').innerHTML = esc(DATA.nature_legend_note || '');
})();

/* ---------- 总体结论 ---------- */
(function(){
  const o = DATA.overall || {};
  const li = (arr) => (arr || []).map((x) => '<li>' + esc(x) + '</li>').join('');
  document.getElementById('verdictBox').innerHTML = '' +
    '<div class="big">' + esc(o.verdict || '') + '</div>' +
    '<div class="two">' +
      '<div><h4>站得住的部分</h4><ul>' + li(o.strengths) + '</ul></div>' +
      '<div><h4>站不住的部分</h4><ul>' + li(o.weaknesses) + '</ul></div>' +
    '</div>';
})();

/* ---------- 分布条 ---------- */
(function(){
  const cnt = {};
  ITEMS.forEach((it) => { cnt[it._g] = (cnt[it._g] || 0) + 1; });
  const keys = ['A', 'B', 'C', 'D', 'N/A'].filter((k) => cnt[k]);
  const total = ITEMS.length;
  document.getElementById('distBar').innerHTML = keys.map((k) => {
    const w = (cnt[k] / total * 100).toFixed(2);
    return '<div style="flex:0 0 ' + w + '%;background:' + GRADE_META[k].color + '">' +
           (cnt[k] / total > 0.06 ? cnt[k] + ' 条' : '') + '</div>';
  }).join('');
  document.getElementById('distLegend').innerHTML = keys.map((k) =>
    '<span><i style="background:' + GRADE_META[k].color + '"></i>' +
    k + ' ' + GRADE_META[k].name + ' · ' + cnt[k] + ' 条</span>'
  ).join('') + '<span style="color:var(--txt-faint)">共 ' + total + ' 条</span>';
})();

/* ---------- 筛选 ---------- */
let activeGrade = 'all';
let activeNatures = new Set();
let keyOnly = false;

function natureSet(it){
  return new Set((it.natures || []).length ? it.natures : ['未标注']);
}

function buildChips(){
  const gb = document.getElementById('gradeBar');
  [...gb.children].forEach((n) => { if(!n.classList.contains('lbl')) n.remove(); });
  const cnt = {};
  ITEMS.forEach((it) => { cnt[it._g] = (cnt[it._g] || 0) + 1; });
  [['all', '全部', '']].concat(
    ['A', 'B', 'C', 'D', 'N/A'].filter((k) => cnt[k])
      .map((k) => [k, k + ' · ' + GRADE_META[k].name, GRADE_META[k].cls])
  ).forEach(([val, label, cls]) => {
    const b = document.createElement('span');
    b.className = 'chip ' + cls + (activeGrade === val ? ' on' : '');
    b.textContent = label + (cnt[val] ? '（' + cnt[val] + '）' : '');
    b.addEventListener('click', () => { activeGrade = val; buildChips(); render(); });
    gb.appendChild(b);
  });

  const nb = document.getElementById('natureBar');
  [...nb.children].forEach((n) => { if(!n.classList.contains('lbl')) n.remove(); });
  const ncnt = {};
  ITEMS.forEach((it) => natureSet(it).forEach((k) => { ncnt[k] = (ncnt[k] || 0) + 1; }));
  const keys = NATURE_ORDER.filter((k) => ncnt[k])
    .concat(Object.keys(ncnt).filter((k) => NATURE_ORDER.indexOf(k) === -1));

  const mk = (val, label, cls) => {
    const b = document.createElement('span');
    const on = val === 'all' ? activeNatures.size === 0 : activeNatures.has(val);
    b.className = 'chip ' + cls + (on ? ' on' : '');
    b.innerHTML = label + (ncnt[val] ? '<span class="n">' + ncnt[val] + '</span>' : '');
    b.addEventListener('click', () => {
      if(val === 'all') activeNatures.clear();
      else if(activeNatures.has(val)) activeNatures.delete(val);
      else activeNatures.add(val);
      buildChips(); render();
    });
    nb.appendChild(b);
  };
  mk('all', '全部', '');
  keys.forEach((k) => mk(k, k, (NATURE[k] || {}).chip || ''));
}

function currentList(){
  const q = (document.getElementById('q').value || '').trim().toLowerCase();
  return ITEMS.filter((it) => {
    if(activeGrade !== 'all' && it._g !== activeGrade) return false;
    if(activeNatures.size){
      const ns = natureSet(it);
      let hit = false;
      activeNatures.forEach((k) => { if(ns.has(k)) hit = true; });
      if(!hit) return false;
    }
    if(!q) return true;
    const hay = [
      it.title, it.rating, it.nature_basis, it.tier, it.reliability,
      it.timeliness, it.scope, it.evidence_strength, it.note,
      (it.natures || []).join(' '),
      (it.sources || []).map((s) => [s.id, s.label, s.kind, s.tier, s.note, s.url].join(' ')).join(' '),
      (it.holds || []).map((h) => [h.claim, h.basis, (h.tags || []).join(' ')].join(' ')).join(' '),
      (it.doubts || []).map((d) => [d.claim, d.basis, (d.tags || []).join(' ')].join(' ')).join(' '),
      ((it.quote || {}).segments || []).map((s) => s.text + ' ' + (s.fix || '')).join(' '),
      Object.keys(it.sub_ratings || {}).join(' ')
    ].join(' ').toLowerCase();
    return hay.indexOf(q) !== -1;
  });
}

/* ---------- 卡片：原文 ---------- */
function quoteHTML(it){
  const q = it.quote;
  if(!q || !q.segments || !q.segments.length) return '';
  const st = q.stats || {};
  const rows = q.segments.filter((s) => !keyOnly || s.key).map((s) => {
    const fix = s.fix
      ? '<span class="qfix">' + esc(s.fix) + '</span>'
      : '';
    return '<div class="ql' + (s.key ? ' key' : '') + '">' +
             '<span class="t">' + fmt(s.t) + '</span>' +
             '<span class="x">' + esc(s.text) + fix + '</span>' +
           '</div>';
  }).join('');
  return '' +
    '<div class="blk"><h4>原文逐字稿</h4><div class="qt">' +
      '<div class="qt-head">' +
        '<span class="rng">' + esc(q.range || (fmt(it.start) + '–' + fmt(it.end))) + '</span>' +
        '<span>' + (st.lines || q.segments.length) + ' 行 / ' + (st.chars || 0) + ' 字</span>' +
        '<span>关键句 ' + (st.key_lines || 0) + '</span>' +
        (st.fix_lines ? '<span>勘误 ' + st.fix_lines + '</span>' : '') +
        '<span class="sp"></span>' +
        '<span class="qt-toggle' + (keyOnly ? ' on' : '') + '" data-keyonly="1">' +
          (keyOnly ? '仅关键句' : '全部') + '</span>' +
      '</div>' +
      '<div class="qt-lines">' + (rows || '<div class="ql"><span class="t">—</span><span class="x">（无关键句）</span></div>') + '</div>' +
      (q.note ? '<div class="qt-note">' + esc(q.note) + '</div>' : '') +
    '</div></div>';
}

/* ---------- 卡片：出处 ---------- */
function sourcesHTML(it){
  const arr = it.sources || [];
  if(!arr.length) return '';
  const rows = arr.map((s) => {
    const meta = [];
    if(s.kind) meta.push('<span>' + esc(s.kind) + '</span>');
    if(s.tier) meta.push('<span class="tier">' + esc(s.tier) + '</span>');
    if(s.verified){
      const no = /未|需/.test(s.verified);
      meta.push('<span class="ver' + (no ? ' no' : '') + '">' + esc(s.verified) + '</span>');
    }
    const link = s.url
      ? '<div class="slink"><a href="' + esc(s.url) + '" target="_blank" rel="noopener">' + esc(s.url) + '</a></div>'
      : '';
    return '<div class="src" id="src-' + it.id + '-' + esc(s.id) + '">' +
      '<div class="top"><span class="sid">' + esc(s.id) + '</span>' +
        '<span class="slab">' + esc(s.label) + '</span></div>' +
      (meta.length ? '<div class="smeta">' + meta.join('') + '</div>' : '') +
      (s.note ? '<div class="snote">' + esc(s.note) + '</div>' : '') +
      link +
    '</div>';
  }).join('');
  return '<div class="blk"><h4>出处与根据（' + arr.length + ' 条）</h4><div class="srclist">' + rows + '</div></div>';
}

/* ---------- 卡片：论证条目 ---------- */
function argHTML(a, srcMap){
  const metas = [];
  (a.ref || []).forEach((r) => {
    const title = REF_LABEL[r] || (srcMap[r] ? srcMap[r].label : '');
    metas.push('<span class="ref" title="' + esc(title) + '">' + esc(r) + '</span>');
  });
  (a.tags || []).forEach((t) => {
    metas.push('<span class="tag-mini ' + ((NATURE[t] || {}).cls || '') + '">' + esc(t) + '</span>');
  });
  return '<div class="arg">' +
    '<div class="aclaim">' + esc(a.claim) + '</div>' +
    (a.basis ? '<div class="abas"><b>根据：</b>' + esc(a.basis) + '</div>' : '') +
    (metas.length ? '<div class="ameta">' + metas.join('') + '</div>' : '') +
  '</div>';
}

function argBlock(title, arr, cls, srcMap){
  if(!arr || !arr.length) return '';
  return '<div class="blk ' + cls + '"><h4>' + esc(title) + '（' + arr.length + '）</h4>' +
         '<div class="arglist">' + arr.map((a) => argHTML(a, srcMap)).join('') + '</div></div>';
}

/* ---------- 卡片 ---------- */
function metaRow(it){
  const cells = [];
  cells.push('<span><b>时间</b>' + fmt(it.start) + '–' + fmt(it.end) + '</span>');
  if(it.tier) cells.push('<span><b>权威层级</b>' + esc(it.tier) + '</span>');
  if(it.reliability) cells.push('<span><b>可靠程度</b>' + esc(it.reliability) + '</span>');
  if(it.evidence_strength) cells.push('<span><b>关联强度</b>' + esc(it.evidence_strength) + '</span>');
  (it.natures || []).forEach((k) => {
    cells.push('<span class="nat ' + ((NATURE[k] || {}).cls || '') + '">' + esc(k) + '</span>');
  });
  return '<div class="metarow">' + cells.join('') + '</div>';
}

function cardHTML(it){
  const g = GRADE_META[it._g];
  const srcMap = {};
  (it.sources || []).forEach((s) => { srcMap[s.id] = s; });

  const subs = it.sub_ratings && Object.keys(it.sub_ratings).length
    ? '<div class="blk"><h4>子评级</h4><div class="subs">' +
      Object.keys(it.sub_ratings).map((k) =>
        '<span><b>' + esc(k) + '</b> ' + esc(it.sub_ratings[k]) + '</span>').join('') +
      '</div></div>'
    : '';
  const extra = [];
  if(it.timeliness) extra.push('<div class="blk"><h4>时效性</h4><p>' + esc(it.timeliness) + '</p></div>');
  if(it.scope) extra.push('<div class="blk"><h4>适用范围</h4><p>' + esc(it.scope) + '</p></div>');

  const nats = (it.natures || []).map((k) =>
    '<span class="nat ' + ((NATURE[k] || {}).cls || '') + '">' + esc(k) + '</span>').join('');

  return '' +
  '<article class="claim ' + g.cls + '" data-id="' + it.id + '">' +
    '<button class="claim-head" type="button" aria-expanded="false">' +
      '<span class="num">#' + it.id + '</span>' +
      '<a class="tc" href="sync-player.html?t=' + Math.floor(it.start) + '" ' +
        'title="跳到视频该位置" onclick="event.stopPropagation()">' + fmt(it.start) + '</a>' +
      '<span class="ttl">' + esc(it.title) + '</span>' +
      '<span class="natwrap">' + nats + '</span>' +
      '<span class="grade ' + g.cls + '">' + esc(it.rating) + '</span>' +
      '<span class="caret">▼</span>' +
    '</button>' +
    '<div class="claim-body">' +
      metaRow(it) +
      quoteHTML(it) +
      (it.nature_basis ? '<div class="blk"><h4>来源性质判断依据</h4><p>' + esc(it.nature_basis) + '</p></div>' : '') +
      sourcesHTML(it) +
      argBlock('成立环节', it.holds, 'ok', srcMap) +
      argBlock('疑点与证据不足', it.doubts, 'warn', srcMap) +
      extra.join('') +
      subs +
      (it.note ? '<div class="noteit">' + esc(it.note) + '</div>' : '') +
    '</div>' +
  '</article>';
}

let openIds = new Set();

function render(){
  const list = currentList();
  document.getElementById('list').innerHTML = list.map(cardHTML).join('');
  document.getElementById('count').innerHTML = '共 <b>' + list.length + '</b> 条' +
    (list.length !== ITEMS.length ? '（总 ' + ITEMS.length + ' 条）' : '');
  document.getElementById('empty').style.display = list.length ? 'none' : 'block';

  document.querySelectorAll('.claim').forEach((el) => {
    const id = Number(el.dataset.id);
    if(openIds.has(id)) el.classList.add('open');
    const head = el.querySelector('.claim-head');
    head.setAttribute('aria-expanded', el.classList.contains('open') ? 'true' : 'false');
    head.addEventListener('click', () => {
      el.classList.toggle('open');
      const on = el.classList.contains('open');
      head.setAttribute('aria-expanded', on ? 'true' : 'false');
      if(on) openIds.add(id); else openIds.delete(id);
    });
  });

  document.querySelectorAll('[data-keyonly]').forEach((el) => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      keyOnly = !keyOnly;
      document.getElementById('btnKeyOnly').textContent = keyOnly ? '原文：仅关键句' : '原文：全部';
      document.getElementById('btnKeyOnly').classList.toggle('on', keyOnly);
      render();
    });
  });
}

document.getElementById('q').addEventListener('input', render);
document.getElementById('btnExpand').addEventListener('click', () => {
  openIds = new Set(currentList().map((it) => it.id)); render();
});
document.getElementById('btnCollapse').addEventListener('click', () => {
  openIds = new Set(); render();
});
document.getElementById('btnKeyOnly').addEventListener('click', () => {
  keyOnly = !keyOnly;
  const b = document.getElementById('btnKeyOnly');
  b.textContent = keyOnly ? '原文：仅关键句' : '原文：全部';
  b.classList.toggle('on', keyOnly);
  render();
});

/* ---------- 修正清单 / 矛盾 / 限制 ---------- */
(function(){
  const fixes = DATA.corrections_needed || [];
  document.getElementById('fixNote').textContent = fixes.length + ' 处';
  document.getElementById('fixList').innerHTML = fixes.map((f) =>
    '<div class="fix"><span class="k">#' + f.id + '</span>' +
    '<span class="t"><b>' + esc(f.issue) + '</b>' + esc(f.impact) + '</span></div>'
  ).join('') || '<div class="empty">暂无</div>';

  const wd = DATA.corrections_withdrawn || [];
  document.getElementById('wdList').innerHTML = wd.map((f) =>
    '<div class="fix wd"><span class="k">#' + f.id + ' 已撤销</span>' +
    '<span class="t"><b>' + esc(f.issue) + '</b>' + esc(f.reason) +
    (f.withdrawn_at ? '（' + esc(f.withdrawn_at) + '）' : '') + '</span></div>'
  ).join('');

  document.getElementById('ctrList').innerHTML = (DATA.internal_contradictions || []).map((c) =>
    '<div class="ctr">' +
      '<div class="items">涉及观点 ' + (c.items || []).map((i) => '#' + i).join('、') + '</div>' +
      '<div class="d">' + esc(c.description) + '</div>' +
      '<div class="r"><b>调和口径：</b>' + esc(c.suggested_resolution) + '</div>' +
    '</div>'
  ).join('') || '<div class="empty">暂无</div>';

  document.getElementById('limitList').innerHTML =
    (DATA.limitations || []).map((x) => '<li>' + esc(x) + '</li>').join('');
})();

buildChips();
render();
</script>
</body>
</html>
"""


def main():
    with open(SRC_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 评级分布由 rating 派生，避免 JSON 里的手工计数与数据脱节
    data.setdefault('assessment', {})['counts'] = compute_counts(data.get('items', []))

    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    html = TEMPLATE.replace('__DATA__', payload)

    out_dir = os.path.dirname(OUT_HTML)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    with open(OUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)

    items = data.get('items', [])
    n_src = sum(len(it.get('sources', [])) for it in items)
    n_line = sum(it.get('quote', {}).get('stats', {}).get('lines', 0) for it in items)
    n_key = sum(it.get('quote', {}).get('stats', {}).get('key_lines', 0) for it in items)
    n_fix = sum(it.get('quote', {}).get('stats', {}).get('fix_lines', 0) for it in items)

    print('生成完成: %s' % OUT_HTML)
    print('  观点条目: %d 条' % len(items))
    print('  原文行: %d 行（关键句 %d 行，勘误 %d 行）' % (n_line, n_key, n_fix))
    print('  出处条目: %d 条' % n_src)
    print('  文件大小: %.1f KB' % (os.path.getsize(OUT_HTML) / 1024.0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
