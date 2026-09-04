# FactEasy

面向病毒式传播视频 / Vlog / 播客的**事实核查工作台**：把长视频切成可核验的观点单元，标注时间区间、识别插入广告，并让补充说明跟着播放进度同步呈现。

**在线站点**：<https://dbsquared.github.io/facteasy/>

## 目录结构

本仓库按 **GitHub Pages 从根目录发布** 组织：

| 路径 | 用途 |
|------|------|
| `index.html` | 站点首页（Pages 入口） |
| `videos.html` | 视频列表（数据驱动表格，支持标签筛选 / 检索 / 排序） |
| `404.html` | 自定义 404 页 |
| `.nojekyll` | 跳过 Jekyll 构建，纯静态直出 |
| `pages/` | 站点子页面 |
| `pages/sync-player.html` | 视频同步阅读器：左侧 B 站播放器，右侧内容随进度联动，**内嵌事实核查面板** |
| `pages/credibility.html` | 观点可信度逐条评估（独立完整版） |
| `pages/facteasy-data.js` | 共享数据层：观点 + 核查结果，由脚本生成，供上述两页共用 |
| `research/` | 研究与产品文档（Markdown） |
| `analysis/video-viewpoints/` | 视频观点切分与广告识别的分析数据与方法脚本 |

## 在本地预览

站点全部使用**相对路径**，直接双击 `index.html` 即可用浏览器打开，无需构建。

如需通过 HTTP 访问（更接近线上环境）：

```bash
python -m http.server 8000
# 然后打开 http://127.0.0.1:8000/
```

## 启用 / 更新 GitHub Pages

1. 打开仓库 **Settings → Pages**
2. **Source** 选择 `Deploy from a branch`
3. **Branch** 选择 `main`，目录选择 **`/ (root)`**
4. 保存后等待约 1 分钟，访问 `https://dbsquared.github.io/facteasy/`

仓库根目录已有 `index.html`，且 `.nojekyll` 会跳过 Jekyll，推送后站点会直接更新。

## 新增视频

编辑 `videos.html` 顶部的数据数组，追加一条记录即可，渲染 / 筛选 / 排序逻辑无需改动：

```js
const VIDEOS = [
  {
    source: '哔哩哔哩',   // 来源平台
    author: 'UP 主',      // 发布者
    title:  '视频标题',
    views:  0,            // 播放数
    tags:   ['标签A', '标签B'],
    url:    'pages/xxx.html'   // 本站页面入口
  }
];
```

## 重新生成共享数据

`pages/facteasy-data.js` 是**生成物**，不要手改。改完 `analysis/video-viewpoints/` 下的
`viewpoints.json` 或 `credibility.json` 后执行：

```bash
cd analysis/video-viewpoints
python build_site_data.py        # → ../../pages/facteasy-data.js
python build_credibility_page.py # → ../../pages/credibility.html
python build_credibility_md.py   # → ./credibility.md
```

同步阅读器与可信度报告两页共用这一份数据，因此改一次两边同时生效。

## 已知限制

- **B 站播放器依赖 iframe 嵌入**：`pages/sync-player.html` 通过 iframe 加载 B 站官方播放器。部分内嵌预览环境（如某些 IDE 的静态预览面板）会拦截外部 iframe，此时页面会给出「在新标签页打开」与「无视频计时」两种兜底方式。
- **页面内的观点时间戳**：当前视频的 18 个观点时间戳由音频转写 + 语义切分得到，存放于 `analysis/video-viewpoints/viewpoints.json`，经 `build_site_data.py` 生成进 `pages/facteasy-data.js` 供页面读取。
- **核查面板的进度驱动**：同步阅读器的核查面板跟随页面内的本地时钟切换观点。B 站 iframe 为跨域，无法直接读取播放器进度，因此若用户手动拖动视频进度条，页面会尝试重新定位，但极端网络下可能有 1–2 秒误差。
- **B 站播放器为懒加载**：`pages/sync-player.html` 打开时**不加载**播放器，需点击「加载 B 站播放器」。这样在会拦截外部 iframe 的环境（部分 IDE 预览面板 / 沙箱）里不会一进来就显示 `This content is blocked`。右侧的观点切分与事实核查不依赖播放器，不加载也能用。已实测 `player.bilibili.com` 响应头**不含** `X-Frame-Options` 与 CSP `frame-ancestors`——B 站官方外链播放器本身不限制嵌入，报错均来自宿主环境。
