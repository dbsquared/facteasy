#!/usr/bin/env python3
"""生成可交互时间轴 HTML。
输入:
  - viewpoints.json : [{id,start,end,title,summary,ad}]  (秒)
  - video 本地 mp4 路径 (file:// 内嵌播放器)
输出: timeline.html (点击彩条/列表项 -> 播放器跳转到 start)
"""
import sys, json
from pathlib import Path

VIEWS = Path(sys.argv[1] if len(sys.argv) > 1 else "viewpoints.json").resolve()
VIDEO = sys.argv[2] if len(sys.argv) > 2 else ""
OUT = VIEWS.parent / "timeline.html"

views = json.loads(VIEWS.read_text(encoding="utf-8"))
dur = max(v["end"] for v in views) if views else 0


def pct(t):
    return (t / dur * 100) if dur else 0


# 给每个观点分配一个稳定颜色(跳过红/橙, 广告用警示色)
palette = ["#3b82f6", "#8b5cf6", "#10b981", "#14b8a6", "#6366f1",
           "#0ea5e9", "#7c3aed", "#059669", "#0891b2", "#4f46e5",
           "#22c55e", "#0d9488", "#9333ea", "#0284c7", "#65a30d"]
rows = []
for i, v in enumerate(views):
    color = "#ef4444" if v.get("ad") else palette[i % len(palette)]
    left = pct(v["start"]); width = max(pct(v["end"]) - left, 0.4)
    tag = '<span class="adt">广告</span>' if v.get("ad") else f'<span class="vp">观点 {v["id"]}</span>'
    rows.append(f"""
    <div class="seg" style="left:{left:.3f}%;width:{width:.3f}%;background:{color}" data-t="{v['start']}" title="{v['title']}"></div>""")

list_items = []
for v in views:
    color = "#ef4444" if v.get("ad") else palette[(v["id"] - 1) % len(palette)] if isinstance(v.get("id"), int) else "#3b82f6"
    mm = lambda t: f"{int(t//60):02d}:{int(t%60):02d}"
    tag = "广告" if v.get("ad") else f"观点{v['id']}"
    list_items.append(f"""
    <li class="row" data-t="{v['start']}">
      <span class="dot" style="background:{color}"></span>
      <span class="t">{mm(v['start'])}–{mm(v['end'])}</span>
      <span class="tag tag-{'ad' if v.get('ad') else 'vp'}">{tag}</span>
      <span class="title">{v['title']}</span>
      <div class="sum">{v['summary']}</div>
    </li>""")

video_src = VIDEO if VIDEO.startswith("file://") else ("file:///" + VIDEO.replace("\\", "/")) if VIDEO else ""

html = f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>视频观点/广告时间轴</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,"Microsoft YaHei",sans-serif;background:#0f172a;color:#e2e8f0}}
.wrap{{max-width:980px;margin:0 auto;padding:20px}}
h1{{font-size:18px;margin:0 0 4px}}
.sub{{color:#94a3b8;font-size:13px;margin-bottom:14px}}
video{{width:100%;border-radius:10px;background:#000;display:block}}
.timeline{{position:relative;height:34px;margin:16px 0 6px;background:#1e293b;border-radius:8px;overflow:hidden;cursor:pointer}}
.seg{{position:absolute;top:0;bottom:0;opacity:.85;border-right:1px solid #0f172a}}
.seg:hover{{opacity:1;outline:2px solid #fff}}
.legend{{font-size:12px;color:#94a3b8;margin-bottom:10px}}
ul{{list-style:none;padding:0;margin:0}}
.row{{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px;padding:10px 12px;border-bottom:1px solid #1e293b;cursor:pointer;border-radius:6px}}
.row:hover{{background:#1e293b}}
.dot{{width:10px;height:10px;border-radius:50%;flex:0 0 auto;transform:translateY(1px)}}
.t{{font-variant-numeric:tabular-nums;color:#cbd5e1;font-size:13px}}
.tag{{font-size:11px;padding:1px 7px;border-radius:10px;font-weight:600}}
.tag-vp{{background:#1e3a5f;color:#93c5fd}}
.tag-ad{{background:#7f1d1d;color:#fca5a5}}
.title{{font-weight:600;font-size:14px}}
.sum{{flex-basis:100%;color:#94a3b8;font-size:13px;margin-top:2px;padding-left:18px}}
.adt{{display:none}}
</style></head>
<body><div class="wrap">
<h1>视频观点 / 广告时间轴</h1>
<div class="sub">点击下方彩条或列表项，播放器将跳转到对应时间。红色=疑似广告段。</div>
{'<video id="v" controls preload="metadata" src="'+video_src+'"></video>' if video_src else '<div class="sub">（未提供视频路径，无法内嵌播放器）</div>'}
<div class="timeline" id="tl">{''.join(rows)}</div>
<div class="legend">时间轴总长 {int(dur//60)}分{int(dur%60)}秒 ｜ 共 {len(views)} 个标记（红=广告）</div>
<ul id="list">{''.join(list_items)}</ul>
</div>
<script>
const v=document.getElementById('v');
function seek(t){{ if(v){{ v.currentTime=t; v.scrollIntoView({{behavior:'smooth',block:'center'}}); v.play().catch(()=>{{}}); }} }}
document.querySelectorAll('.seg').forEach(e=>e.onclick=()=>seek(parseFloat(e.dataset.t)));
document.querySelectorAll('.row').forEach(e=>e.onclick=()=>seek(parseFloat(e.dataset.t)));
</script></body></html>"""

OUT.write_text(html, encoding="utf-8")
print("WROTE", OUT, "dur=", round(dur, 1), "marks=", len(views))
