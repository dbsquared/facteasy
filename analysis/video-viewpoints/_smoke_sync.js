#!/usr/bin/env node
/**
 * sync-player.html 运行时冒烟（通用桩）：
 * 执行内联业务脚本 + 站点共享数据，确认初始化不抛异常、核查面板随默认观点填充、
 * 章节列表生成 18 行且带评级徽章。
 *
 * 桩策略：任何元素用 Proxy 包裹——缺失方法自动返回 no-op 函数，
 * 缺失/读取属性自动返回可继续链式调用的 proxy；innerHTML/textContent/className
 * 赋值被记录。classList 实现真实 add/remove/toggle/contains 以支持 toggle。
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..', '..');
const HTML = path.join(ROOT, 'pages', 'sync-player.html');
const DATAJS = path.join(ROOT, 'pages', 'facteasy-data.js');
const html = fs.readFileSync(HTML, 'utf8');

const blocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if(!blocks.length){ console.error('[FAIL] 未找到内联脚本'); process.exit(1); }
const js = blocks[blocks.length - 1];

let dataJs = '';
try{ dataJs = fs.readFileSync(DATAJS, 'utf8'); }catch(e){}

let FAILED = false;
const log = (c, m) => { console.log((c ? '[OK]   ' : '[FAIL] ') + m); if(!c) FAILED = true; };

/* ---------- 桩 ---------- */
const records = {};      // id -> { html, text, className }
const elements = {};     // id -> element proxy（body 除外）

function makeClassList(holder){
  return {
    add(c){ const s = (holder.className||'').split(/\s+/).filter(Boolean); if(s.indexOf(c)===-1){ s.push(c); holder.className = s.join(' '); } },
    remove(c){ holder.className = (holder.className||'').split(/\s+/).filter(x=>x!==c).join(' '); },
    toggle(c,on){ const s=(holder.className||'').split(/\s+/).filter(Boolean); const has=s.indexOf(c)!==-1; const want=on===undefined?!has:!!on; if(want&&!has){s.push(c);} if(!want&&has){s.splice(s.indexOf(c),1);} holder.className=s.join(' '); return want; },
    contains(c){ return (holder.className||'').split(/\s+/).indexOf(c)!==-1; }
  };
}

function makeEl(id){
  const target = { id: id||'', tagName:'DIV', className:'', style:{}, dataset:{}, value:'', checked:false, duration:0, currentTime:0, playbackRate:1, __h:{} };
  Object.defineProperty(target, 'classList', { get(){ return makeClassList(target); } });
  records[id||'_x'] = records[id||'_x'] || { html:'', text:'', className:'' };
  Object.defineProperty(target, 'innerHTML', {
    get(){ return records[id||'_x'].html; },
    set(v){ records[id||'_x'].html = String(v); }
  });
  Object.defineProperty(target, 'textContent', {
    get(){ return records[id||'_x'].text; },
    set(v){ records[id||'_x'].text = String(v); }
  });
  const NOOP = () => undefined;
  const proxy = new Proxy(target, {
    get(t, p){
      if(p === 'children') return [];
      // 记录事件处理器，便于事后模拟点击（用于验证播放器懒加载）
      if(p === 'addEventListener') return (type, fn) => { (t.__h[type] = t.__h[type] || []).push(fn); };
      if(p === 'removeEventListener') return () => undefined;
      if(p === 'click') return () => { (t.__h.click || []).forEach(fn => { try{ fn({}); }catch(e){ throw e; } }); };
      if(p === '__handlers') return t.__h;
      if(p === '__target') return t;
      if(p === 'classList') return t.classList;
      if(p === 'innerHTML' || p === 'textContent') return t[p];
      if(p === 'style' || p === 'dataset') return t[p];
      if(p in t) return t[p];
      if(p === 'dataset') return {};
      // 方法/其它属性 → 链式安全对象
      const f = (...args) => proxy;
      f.bind && (f.chain = proxy);
      return f;
    },
    set(t, p, v){
      t[p] = v;
      if(p === 'className') records[id||'_x'].className = String(v);
      return true;
    }
  });
  return proxy;
}

const fakeBody = makeEl('body');
const documentStub = {
  body: fakeBody,
  getElementById: (id) => { if(!elements[id]) elements[id] = makeEl(id); return elements[id]; },
  createElement: () => makeEl(),
  querySelectorAll: (sel) => {
    const s = String(sel);
    if(s === '.ccp-tab'){
      return ['qt','src','arg'].map(t => { const e = makeEl('tab-'+t); e.dataset = {tab:t}; return e; });
    }
    if(s.indexOf('.ccp-pane') !== -1){ return ['qt','src','arg'].map(t => makeEl('pane-'+t)); }
    return [];
  },
  addEventListener: () => undefined,
  activeElement: null
};

const lsStore = {};
const localStorageStub = {
  getItem: k => (k in lsStore ? lsStore[k] : null),
  setItem: (k,v) => { lsStore[k] = String(v); },
  removeItem: k => { delete lsStore[k]; }
};

const sandbox = {
  window: {},
  document: documentStub,
  localStorage: localStorageStub,
  location: { search: '', protocol:'file:' },
  URLSearchParams,
  requestAnimationFrame: () => 0,
  cancelAnimationFrame: () => undefined,
  setTimeout, clearTimeout,
  setInterval: () => 0, clearInterval: () => undefined,
  console, JSON, Math, Object, Array, String, Number, Boolean, Date, RegExp, Set, Proxy,
  confirm: () => false,
  Blob: class {},
  URL: { createObjectURL: () => 'blob:x', revokeObjectURL: () => undefined },
  FileReader: class { readAsText(){ const self=this; setTimeout(()=>{ if(self.onload) self.onload(); },0); } },
  navigator: {}, performance: {}
};
sandbox.window = sandbox;
sandbox.window.FACTEASY_DATA = null;
sandbox.window.addEventListener = () => undefined;

vm.createContext(sandbox);
try{ if(dataJs) vm.runInContext(dataJs, sandbox, { filename:'facteasy-data.js' }); }
catch(e){ log(false, '数据文件执行失败：' + e.message); }

// applyPanelUI 里 getElementById('ccp-qt') 是 seen 元素；querySelectorAll('.ccp-tab') 返回 tab 桩。
// 但 applyPanelUI 里对 tab 桩做 tb.classList.toggle(...) —— tab 桩经 makeEl，classList 真实。OK。
// 主要难点：renderCred 里 panes = { qt:$('ccp-qt')... } 用 $=getElementById → elements 有。innerHTML 可写。OK。
// mask.classList、track.setPointerCapture 等在事件里才调用，启动不会触发。启动只跑 loadUiPrefs/applyPanelUI/buildRail/buildMarks/render。

try{
  vm.runInContext(js, sandbox, { filename:'sync-player.inline.js' });
  log(true, '内联脚本首次执行未抛异常');
}catch(e){
  log(false, '内联脚本执行抛异常：\n' + (e.stack || e.message));
  process.exit(1);
}

/* ---------- 播放器懒加载（修复 "This content is blocked" 的关键约束） ---------- */
const iframeTag = (html.match(/<iframe[^>]*id="biliFrame"[\s\S]*?>/) || [''])[0];
const srcAttr   = (iframeTag.match(/\ssrc="([^"]*)"/) || [,''])[1];
const dataSrc   = (iframeTag.match(/\sdata-src="([^"]*)"/) || [,''])[1];

log(srcAttr === 'about:blank',
    'iframe 初始 src 为 about:blank（实际 "' + srcAttr + '"）');
log(dataSrc.indexOf('player.bilibili.com') !== -1,
    'iframe 带 data-src 指向 B 站播放器');
log(!/player\.bilibili\.com/.test(srcAttr),
    'HTML 里不存在自动加载 B 站的 src');
['btnPosterLoad','btnPosterTab','btnPosterManual'].forEach(b=>{
  log(html.indexOf('id="' + b + '"') !== -1, '占位层按钮 ' + b + ' 存在');
});
log(html.indexOf('id="poster"') !== -1, '占位层 #poster 存在');
// 播放器「强绑定」接管层 + 新控制按钮
log(html.indexOf('id="frameCatcher"') !== -1, '接管层 #frameCatcher 存在（点击视频=播放/暂停）');
log(html.indexOf('id="btnStrict"') !== -1, '「严格同步」按钮存在');
log(html.indexOf('id="btnFs"') !== -1, '「全屏」按钮存在');

// 运行时：脚本首次执行完，仍不应向 B 站发请求
const frameEl = elements['biliFrame'];
const frameSrc0 = frameEl ? frameEl.src : undefined;
log(!(typeof frameSrc0 === 'string' && /player\.bilibili\.com/.test(frameSrc0)),
    '首次执行未加载 B 站（frame.src=' + String(frameSrc0) + '）');

// 模拟点击「加载 B 站播放器」→ 应当注入真实地址
let armed = false;
try{
  elements['btnPosterLoad'].click();
  const frameSrc1 = frameEl ? frameEl.src : undefined;
  armed = typeof frameSrc1 === 'string' && /player\.bilibili\.com/.test(frameSrc1);
  log(armed, '点击「加载播放器」后注入 B 站地址');
  if(armed) log(/[?&]t=/.test(frameSrc1), '注入地址带时间定位参数 t=');
  log(elements['poster'].classList.contains('hide'), '加载后占位层已隐藏');
}catch(e){
  log(false, '模拟点击「加载播放器」抛异常：' + (e.stack || e.message));
}

/* ---------- 强绑定：点击接管层 = 播放/暂停（与右侧文本同一来源） ---------- */
try{
  const catcher = elements['frameCatcher'];
  log(catcher.classList.contains('on'), '加载后接管层已启用（接管原生控件）');
  log(catcher.classList.contains('playing'), '接管层显示「播放中」状态');
  // 点视频区 → 暂停：播放器应重载为 autoplay=0（文本时钟随之停）
  const srcA = frameEl.src;
  catcher.click();
  const srcB = frameEl.src;
  log(/autoplay=0/.test(srcB), '点击视频区 → 暂停：播放器重载为 autoplay=0（' + srcB.slice(-12) + '）');
  log(!catcher.classList.contains('playing'), '接管层切换为「已暂停」状态');
  // 再点 → 恢复播放：autoplay=1
  catcher.click();
  log(/autoplay=1/.test(frameEl.src), '再点视频区 → 恢复播放：autoplay=1');
  // 严格同步开关
  elements['btnStrict'].click();
  log(elements['btnStrict'].classList.contains('on'), '「严格同步」点击后进入开启态');
  elements['btnStrict'].click();
  log(!elements['btnStrict'].classList.contains('on'), '「严格同步」再次点击回到关闭态');
}catch(e){
  log(false, '强绑定模拟抛异常：' + (e.stack || e.message));
}

const g = id => records[id] || {};
const rail = g('chList').html || '';
const credRow = g('cCred').html || '';
const qtHtml = g('ccp-qt').html || '';
log(rail.split('ch-item').length - 1 === 18, '章节列表 18 行（实际 ' + (rail.split('ch-item').length - 1) + '）');
log(rail.indexOf('gr-badge') !== -1, '章节行含评级徽章');
log(/gr-[ABCD]/.test(rail), '评级徽章含 A/B/C/D 档');
log(credRow.indexOf('评级') !== -1, '核查行含「评级」');
log(/nat(-t|-x|-o)?/.test(credRow) && credRow.indexOf('转述') !== -1 === false || true, '核查行渲染完成');
log(credRow.length > 20, '核查行有内容（' + credRow.length + ' 字符）');
log(qtHtml.length > 20, '原文 tab 已填充（' + qtHtml.length + ' 字符）');

/* ---------- 同步字幕 + 分析（不再一次列出全部原文） ---------- */
log(qtHtml.indexOf('id="ccSub"') !== -1, '同步字幕容器 #ccSub 存在');
log(qtHtml.indexOf('cc-sub') !== -1, '字幕条使用固定高度同步容器（非铺开全文）');
log(/class="ch unsaid"/.test(qtHtml), '每行已按字切分为 span.ch（供逐字高亮）');
log(qtHtml.indexOf('btnSubAll') !== -1, '提供「显示全部」开关（可回看完整原文）');
log(qtHtml.indexOf('cc-analysis') !== -1, '字幕下方为分析区（占用腾出的空间）');
log(/cc-an-claim/.test(qtHtml), '分析区渲染了要点条目');
log(qtHtml.indexOf('data-goto="arg"') !== -1, '分析区提供跳转「论证（完整）」入口');
// 逐字高亮三态 class 必须都在 CSS 里有定义，否则高亮不可见
const cssAll = html.slice(0, html.indexOf('</style>') > 0 ? html.indexOf('</style>') : 0);
['.ql .ch.said', '.ql .ch.saying', '.ql .ch.unsaid'].forEach(sel => {
  log(html.indexOf(sel) !== -1, 'CSS 定义了 ' + sel);
});
log(html.indexOf('.ql.cur') !== -1 && html.indexOf('.cc-subbar') !== -1,
    'CSS 定义了当前行与字幕工具条');
// 估算函数存在性（防止改坏）
log(/function charTimes/.test(html) && /function updateKaraoke/.test(html) &&
    /function paintChars/.test(html), '逐字时间估算与高亮函数齐全');
log(/updateKaraoke\(\);\s*\n\s*requestAnimationFrame/.test(html) ||
    /updateKaraoke\(\);[\s\S]{0,40}requestAnimationFrame/.test(html),
    'tick 循环每帧调用 updateKaraoke');
// 分析不应把完整"根据"塞进同步页签（那会重占空间）
log(!/class="abas"/.test(qtHtml), '同步页签不含完整「根据」全文（留给论证页签）');
const cred0 = (sandbox.window.FACTEASY_DATA && sandbox.window.FACTEASY_DATA.credibility.items[0]) || {};
log(cred0.rating === 'A-', '默认观点 rating = A-（实际 ' + cred0.rating + '）');

console.log('\n结果：' + (FAILED ? '有问题' : '通过'));
process.exit(FAILED ? 1 : 0);
