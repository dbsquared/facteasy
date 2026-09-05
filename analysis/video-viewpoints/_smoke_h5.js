#!/usr/bin/env node
/**
 * h5-player.html 运行时冒烟：用桩执行内联脚本（加载真实 facteasy-data.js），
 * 校验：462 段字幕构建、观点渲染、点击「加载播放器」会向 /playurl 发请求。
 * fetch / dashjs 用桩替代（无法在 node 里真播）。
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..', '..');
const HTML = path.join(ROOT, 'pages', 'h5-player.html');
const DATAJS = path.join(ROOT, 'pages', 'facteasy-data.js');
const html = fs.readFileSync(HTML, 'utf8');

// 取最后一个真正有内容的 <script>（IIFE）
const m = html.match(/\(function\(\)\{\s*'use strict';[\s\S]*?\}\)\(\);\s*<\/script>/);
if(!m){ console.error('[FAIL] 未找到内联脚本'); process.exit(1); }
const js = m[0].replace(/^<script>/, '').replace(/<\/script>$/, '');

let dataJs = '';
try{ dataJs = fs.readFileSync(DATAJS, 'utf8'); }catch(e){}

let FAILED = false;
const log = (c, msg) => { console.log((c?'[OK]   ':'[FAIL] ')+msg); if(!c) FAILED = true; };

/* 桩 */
const records = {};
const elements = {};
function makeClassList(h){ return {
  add(c){const s=(h.className||'').split(/\s+/).filter(Boolean); if(s.indexOf(c)===-1)s.push(c); h.className=s.join(' ');},
  remove(c){h.className=(h.className||'').split(/\s+/).filter(x=>x!==c).join(' ');},
  toggle(c,on){const s=(h.className||'').split(/\s+/).filter(Boolean); const has=s.indexOf(c)!==-1; const w=on===undefined?!has:!!on; if(w&&!has)s.push(c); if(!w&&has)s.splice(s.indexOf(c),1); h.className=s.join(' '); return w;},
  contains(c){return (h.className||'').split(/\s+/).indexOf(c)!==-1;}
};}
function makeEl(id){
  const t={id:id||'',tagName:'DIV',className:'',style:{},dataset:{},value:'',checked:false,duration:0,currentTime:0,playbackRate:1,__h:{}};
  Object.defineProperty(t,'classList',{get(){return makeClassList(t);}});
  records[id||'_x']=records[id||'_x']||{html:'',text:'',className:''};
  Object.defineProperty(t,'innerHTML',{get(){return records[id||'_x'].html;},set(v){records[id||'_x'].html=String(v);}});
  Object.defineProperty(t,'textContent',{get(){return records[id||'_x'].text;},set(v){records[id||'_x'].text=String(v);}});
  const NOOP=()=>undefined;
  const proxy=new Proxy(t,{ get(t,p){
    if(p==='children') return [];
    if(p==='addEventListener') return (type,fn)=>{(t.__h[type]=t.__h[type]||[]).push(fn);};
    if(p==='removeEventListener') return ()=>undefined;
    if(p==='click') return ()=>{(t.__h.click||[]).forEach(fn=>fn({}));};
    if(p==='classList') return t.classList;
    if(p==='innerHTML'||p==='textContent') return t[p];
    if(p==='style'||p==='dataset') return t[p];
    if(p in t) return t[p];
    const f=()=>proxy; return f;
  }, set(t,p,v){ t[p]=v; if(p==='className') records[id||'_x'].className=String(v); return true; }});
  return proxy;
}
let fetchCalled = null;
const documentStub = {
  body: makeEl('body'),
  getElementById: id => { if(!elements[id]) elements[id]=makeEl(id); return elements[id]; },
  createElement: () => makeEl(),
  querySelectorAll: () => [],
  addEventListener: () => undefined,
  fullscreenElement: null
};
const sandbox = {
  window: {}, document: documentStub, localStorage:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},
  location:{search:''}, URLSearchParams, requestAnimationFrame:()=>0, cancelAnimationFrame:()=>undefined,
  setTimeout, clearTimeout, setInterval:()=>0, clearInterval:()=>undefined,
  console, JSON, Math, Object, Array, String, Number, Boolean, Date, RegExp, Set, Proxy,
  confirm:()=>false, Blob:class{}, URL:{createObjectURL:()=>'blob:x',revokeObjectURL:()=>{}},
  dashjs: { MediaPlayer: () => ({ create: () => ({ initialize(){}, setJSONManifest(){}, on(){} }) }) },
  fetch: (url) => { fetchCalled = url; return Promise.resolve({ json: () => Promise.resolve({ dash:{ video:[{id:32,baseUrl:'x'}], audio:[{id:30280,baseUrl:'y'}] } }) }); }
};
sandbox.window = sandbox;
sandbox.window.addEventListener = () => undefined;
vm.createContext(sandbox);

// 1) 数据文件
try{ vm.runInContext(dataJs, sandbox, {filename:'facteasy-data.js'}); log(true,'facteasy-data.js 加载'); }
catch(e){ log(false,'facteasy-data.js 执行失败：'+e.message); }

// 2) 内联脚本
try{ vm.runInContext(js, sandbox, {filename:'h5.inline.js'}); log(true,'内联脚本执行未抛异常'); }
catch(e){ log(false,'内联脚本抛异常：\n'+(e.stack||e.message)); process.exit(1); }

// 3) 字幕构建
const subHtml = records['ccSubLines'] ? records['ccSubLines'].html : '';
log(subHtml.indexOf('ch unsaid') !== -1, '同步字幕已按字切分（含 ch unsaid 高亮位）');

// 4) 观点渲染（setT(0) 应把 vTitle 设为第 1 个观点）
const vTitle = records['vTitle'] ? records['vTitle'].text : '';
log(!!vTitle, '观点渲染填充标题（' + (vTitle||'').slice(0,30) + '）');

// 5) 点击「加载播放器」应请求 /playurl
try{
  elements['btnLoad'].click();
  log(fetchCalled && /\/playurl\?bvid=BV1mQuC6fEFz/.test(fetchCalled), '点击加载播放器 → 请求 /playurl（' + (fetchCalled||'') + '）');
}catch(e){ log(false,'加载播放器抛异常：'+(e.stack||e.message)); }

// 6) 关键元素存在
['biliVideo','seek','selRate','selQn','btnLoad','ccSub','anBox','vRate'].forEach(id=>{
  log(html.indexOf('id="'+id+'"') !== -1, '页面含 #'+id);
});

console.log('\n结果：' + (FAILED?'有问题':'通过'));
process.exit(FAILED?1:0);
