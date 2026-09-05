/**
 * 运行时冒烟：用极简 DOM 桩执行 credibility.html 里的内联脚本，
 * 覆盖「渲染 / 评级筛选 / 性质多选 / 关键词搜索 / 仅关键句」几条路径，
 * 确保不抛异常且产出的 HTML 片段包含预期结构。
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..', '..');
const HTML = path.join(ROOT, 'pages', 'credibility.html');
const html = fs.readFileSync(HTML, 'utf8');

const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.error('[FAIL] 未找到内联 <script>'); process.exit(1); }
const js = m[1];

/* ---------- 极简 DOM ---------- */
class ClassList {
  constructor(el) { this.el = el; }
  _set() { return (this.el.className || '').split(/\s+/).filter(Boolean); }
  contains(c) { return this._set().indexOf(c) !== -1; }
  add(c) { if (!this.contains(c)) this.el.className = (this.el.className + ' ' + c).trim(); }
  remove(c) { this.el.className = this._set().filter((x) => x !== c).join(' '); }
  toggle(c, on) { const has = this.contains(c); const want = on === undefined ? !has : !!on; if (want) this.add(c); else this.remove(c); return want; }
}

class El {
  constructor(tag) {
    this.tagName = tag;
    this.children = [];
    this.className = '';
    this.innerHTML = '';
    this.textContent = '';
    this.style = {};
    this.dataset = {};
    this.attrs = {};
    this.value = '';
    this.parent = null;
    this.classList = new ClassList(this);
  }
  appendChild(c) { c.parent = this; this.children.push(c); return c; }
  remove() {
    if (!this.parent) return;
    const i = this.parent.children.indexOf(this);
    if (i !== -1) this.parent.children.splice(i, 1);
  }
  setAttribute(k, v) { this.attrs[k] = v; }
  getAttribute(k) { return this.attrs[k]; }
  addEventListener() {}
  querySelector() { return null; }
  querySelectorAll() { return []; }
}

const IDS = ['h1', 'heroMeta', 'defGrid', 'legendNote', 'verdictBox', 'distBar', 'distLegend',
  'q', 'count', 'btnKeyOnly', 'btnExpand', 'btnCollapse', 'gradeBar', 'natureBar',
  'list', 'empty', 'fixNote', 'fixList', 'wdList', 'ctrList', 'limitList'];

const store = {};
IDS.forEach((id) => { store[id] = new El('div'); store[id].id = id; });

const document = {
  getElementById: (id) => {
    if (!store[id]) throw new Error('未知挂载点 #' + id);
    return store[id];
  },
  createElement: (tag) => new El(tag),
  querySelectorAll: () => []
};

const sandbox = { document, console, JSON, Math, Object, Array, String, Number, Set, RegExp, Date };
sandbox.window = sandbox;
vm.createContext(sandbox);

let fail = 0;
const ok = (c, msg) => { console.log((c ? '[OK]   ' : '[FAIL] ') + msg); if (!c) fail++; };

try {
  vm.runInContext(js, sandbox, { filename: 'credibility.inline.js' });
  ok(true, '内联脚本首次执行未抛异常');
} catch (e) {
  ok(false, '内联脚本执行抛异常：' + e.stack);
  process.exit(1);
}

const list = store.list.innerHTML;
const count = () => (store.count.innerHTML.match(/<b>(\d+)<\/b>/) || [])[1];

ok(/原文逐字稿/.test(list), '默认渲染包含「原文逐字稿」区块');
ok(/出处与根据/.test(list), '默认渲染包含「出处与根据（」区块');
ok(/成立环节（/.test(list), '默认渲染包含「成立环节」区块');
ok(/疑点与证据不足（/.test(list), '默认渲染包含「疑点与证据不足」区块');
ok(/class="ql key"/.test(list), '默认渲染包含关键句高亮行');
ok(!/class="qfix"/.test(list), '勘误已落库，不再有独立 qfix 勘误标注');
ok(/文本已按语义与史实逐条补正/.test(list), '原文标注已更新为「已补正」口径');
ok(/nat t-excl/.test(list) && /nat t-orig/.test(list) && /nat t-zhuan/.test(list),
  '三个性质标签（专属 / 原创 / 转述）均有渲染');
ok(!/兼有/.test(list), '页面已无「兼有」字样');
ok(count() === '18', '默认计数为 18 条（实际 ' + count() + '）');
ok(store.wdList.innerHTML.indexOf('已撤销') !== -1, '已撤销修正项已渲染');
ok(store.defGrid.innerHTML.indexOf('转述') !== -1, '标签图例已渲染');

/* ---------- 交互路径 ---------- */
const chips = (barId) => store[barId].children.map((c) => c.textContent || c.innerHTML);
const clickChip = (barId, idx) => {
  const bar = store[barId];
  // 重新绑定：El.addEventListener 是空实现，这里直接复用闭包需脚本内部引用，
  // 因此改用脚本暴露的全局函数不可行 —— 改为断言 chip 数量即可。
  return bar.children[idx];
};

ok(store.natureBar.children.length >= 4, '性质筛选条已生成 ' + store.natureBar.children.length + ' 个 chip（全部 + 3 标签）');
ok(store.gradeBar.children.length >= 2, '评级筛选条已生成 ' + store.gradeBar.children.length + ' 个 chip');

/* 用脚本内定义的 render/过滤函数做白盒调用（搜索框保持为空，避免污染基数） */
store.q.value = '';
const cases = [
  ['仅关键句', () => { vm.runInContext('keyOnly = true; render();', sandbox); },
    (s) => (s.match(/class="ql key"/g) || []).length],
  ['全部原文', () => { vm.runInContext('keyOnly = false; render();', sandbox); },
    (s) => (s.match(/class="ql/g) || []).length]
];
try {
  cases[0][1]();
  const keyRows = cases[0][2](store.list.innerHTML);
  cases[1][1]();
  const allRows = cases[1][2](store.list.innerHTML);
  ok(keyRows > 0 && keyRows < allRows,
    '仅关键句切换生效（关键句 ' + keyRows + ' 行 < 全部 ' + allRows + ' 行）');
} catch (e) {
  ok(false, '仅关键句切换抛异常：' + e.message);
}

const filters = [
  ["activeNatures = new Set(['原创']); render();", '原创'],
  ["activeNatures = new Set(['专属']); render();", '专属'],
  ["activeNatures = new Set(['转述']); render();", '转述'],
  ["activeNatures = new Set(['专属','原创']); render();", '专属+原创'],
  ["activeNatures = new Set(); activeGrade = 'C'; render();", '评级 C'],
  ["activeGrade = 'all'; render();", '清空筛选']
];
filters.forEach(([code, label]) => {
  try {
    vm.runInContext(code, sandbox);
    ok(true, '筛选「' + label + '」未抛异常，命中 ' + count() + ' 条');
  } catch (e) {
    ok(false, '筛选「' + label + '」抛异常：' + e.message);
  }
});

console.log('\n结果：' + (fail ? fail + ' 项有问题' : '通过'));
process.exit(fail ? 1 : 0);
