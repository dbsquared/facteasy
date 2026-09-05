#!/usr/bin/env node
/**
 * 逐字高亮的时间估算单元测试。
 *
 * 为什么单独测：_smoke_sync.js 的 DOM 桩里 querySelectorAll('.ql') 返回空数组，
 * updateKaraoke() 会因 rows 为空直接 return，高亮逻辑根本执行不到。
 * 而"每个字在什么时候被说"是本次改动的核心数学，必须单独验证。
 *
 * 做法：从 sync-player.html 里抽出 PUNCT_RE / PAUSE_W / charTimes 源码，
 * 用真实数据跑，断言时间轴的单调性、覆盖率与标点停顿权重。
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..', '..');
const HTML = path.join(ROOT, 'pages', 'sync-player.html');
const DATAJS = path.join(ROOT, 'pages', 'facteasy-data.js');
const html = fs.readFileSync(HTML, 'utf8');

let FAILED = false;
const log = (c, m) => { console.log((c ? '[OK]   ' : '[FAIL] ') + m); if (!c) FAILED = true; };

/* ---------- 从页面里抽出待测函数（brace 匹配） ---------- */
function extractBlock(src, startIdx) {
  let i = src.indexOf('{', startIdx);
  let depth = 0;
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(startIdx, i + 1); }
  }
  throw new Error('brace 未闭合');
}

// 注意：PUNCT_RE 的字符类里本身就含 ';'，不能用 [^;]+ 截，
// 必须按"行"提取，否则会在字符类内部把正则切断。
const pauseW = (html.match(/const PAUSE_W\s*=\s*.*/) || [''])[0];
const punctRe = (html.match(/const PUNCT_RE\s*=\s*.*/) || [''])[0];
const fnIdx = html.indexOf('function charTimes');
log(pauseW !== '' && punctRe !== '' && fnIdx !== -1, '成功定位 PAUSE_W / PUNCT_RE / charTimes');
if (!pauseW || !punctRe || fnIdx === -1) { console.log('\n结果：有问题'); process.exit(1); }
const fnSrc = extractBlock(html, fnIdx);

const ctx = { console };
vm.createContext(ctx);
vm.runInContext(pauseW + '\n' + punctRe + '\n' + fnSrc + '\n', ctx);
const charTimes = ctx.charTimes;
log(typeof charTimes === 'function', 'charTimes 可用');

/* ---------- 用真实数据跑 ---------- */
global.window = {};
require(DATAJS);
const DATA = global.window.FACTEASY_DATA;
const items = DATA.credibility.items;

let nSeg = 0, badMono = 0, badCover = 0, badPunct = 0, badLen = 0;
let worstStart = 0, worstEnd = 0;
const samples = [];

items.forEach(it => {
  const segs = (it.quote && it.quote.segments) || [];
  const vEnd = Number(it.end);
  segs.forEach((s, k) => {
    nSeg++;
    const nextT = (k + 1 < segs.length) ? Number(segs[k + 1].t) : vEnd;
    const ct = charTimes(s, nextT);
    const chars = Array.from(String(s.text || ''));

    // 1) 字数必须对上
    if (ct.length !== chars.length) badLen++;

    // 2) 时间轴单调不倒退
    for (let i = 0; i < ct.length; i++) {
      if (ct[i].e < ct[i].s - 1e-9) badMono++;
      if (i > 0 && ct[i].s < ct[i - 1].e - 1e-9) badMono++;
    }

    // 3) 首字起点必须等于段起点；末字终点不得越过下段起点（可因静默限幅而早于它）
    if (ct.length) {
      worstStart = Math.max(worstStart, Math.abs(ct[0].s - Number(s.t)));
      const overshoot = ct[ct.length - 1].e - nextT;
      if (Math.abs(ct[0].s - Number(s.t)) > 0.01) badCover++;   // 起点必须对齐
      if (overshoot > 0.01) badCover++;                          // 不得越界
      // 正常语速（≤2 字/秒的限幅未触发）时应完整覆盖到下段起点
      const isP = (c) => /[，。！？、；：,.!?;:…—]/.test(c);
      const totalW = chars.reduce((a, c) => a + (isP(c) ? 1.8 : 1), 0) || 1;
      const notClamped = (nextT - Number(s.t)) <= totalW * 0.5 + 1e-9;
      if (notClamped) {
        const gap = Math.abs(ct[ct.length - 1].e - nextT);
        worstEnd = Math.max(worstEnd, gap);
        if (gap > 0.01) badCover++;
      }
    }

    // 4) 标点字的时长应大于普通字
    const isP = (c) => /[，。！？、；：,.!?;:…—]/.test(c);
    const pDur = ct.filter(c => isP(c.ch)).map(c => c.e - c.s);
    const nDur = ct.filter(c => !isP(c.ch)).map(c => c.e - c.s);
    if (pDur.length && nDur.length) {
      const avg = (a) => a.reduce((x, y) => x + y, 0) / a.length;
      if (!(avg(pDur) > avg(nDur))) badPunct++;
    }
    if (samples.length < 3 && ct.length > 8) {
      samples.push({ id: it.id, t: s.t, text: chars.join(''), ct: ct.slice(0, 6) });
    }
  });
});

log(nSeg === 462, '覆盖全部 462 段（实际 ' + nSeg + '）');
log(badLen === 0, '每段字数与原文一致（异常 ' + badLen + '）');
log(badMono === 0, '字级时间单调不倒退（异常 ' + badMono + '）');
log(badCover === 0, '段内时间完整覆盖（异常 ' + badCover + '）');
log(worstStart < 0.01 && worstEnd < 0.01,
    '首/末字与段边界对齐（最大偏差 ' + worstStart.toFixed(4) + 's / ' + worstEnd.toFixed(4) + 's）');
log(badPunct === 0, '标点字时长大于普通字（异常段 ' + badPunct + '）');

/* ---------- 抽一段看实际效果 ---------- */
console.log('\n样例（前 6 字的估算时间）：');
samples.forEach(s => {
  console.log('  #' + s.id + ' @' + s.t + 's «' + s.text.slice(0, 18) + '…»');
  console.log('    ' + s.ct.map(c =>
    c.ch + '[' + c.s.toFixed(2) + '-' + c.e.toFixed(2) + ']').join(' '));
});

/* ---------- 边界：空文本 / 异常时段 ---------- */
const edge1 = charTimes({ t: 10, text: '' }, 12);
log(Array.isArray(edge1) && edge1.length === 0, '空文本不报错');
const edge2 = charTimes({ t: 10, text: '测试' }, 10);      // 下一段起点==本段（dur<=0）
log(edge2.length === 2 && edge2[0].s === 10, '零/负时长段有兜底（不产生 NaN）');
const edge3 = charTimes({ t: 5, text: '很长的一句' }, 999); // 异常长段
log(edge3.length === 5 && (edge3[4].e - edge3[0].s) <= 8.001, '异常长段被限幅至 8s 内');
const nanChk = edge2.concat(edge3).every(c => isFinite(c.s) && isFinite(c.e));
log(nanChk, '所有边界输入均产出有限数（无 NaN/Infinity）');

console.log('\n结果：' + (FAILED ? '有问题' : '通过'));
process.exit(FAILED ? 1 : 0);
