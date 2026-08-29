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
| `pages/sync-player.html` | 视频同步阅读器：左侧 B 站播放器，右侧内容随进度联动 |
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

## 已知限制

- **B 站播放器依赖 iframe 嵌入**：`pages/sync-player.html` 通过 iframe 加载 B 站官方播放器。部分内嵌预览环境（如某些 IDE 的静态预览面板）会拦截外部 iframe，此时页面会给出「在新标签页打开」与「无视频计时」两种兜底方式。
- **页面内的观点时间戳**：当前视频的 18 个观点时间戳由音频转写 + 语义切分得到，存放于 `analysis/video-viewpoints/viewpoints.json`，并已内联进 `pages/sync-player.html`。
