#!/usr/bin/env node
/**
 * bili_h5_proxy.js —— 本地 B 站取流 + 分片代理
 *
 * 为什么需要它：
 *  - 浏览器跨域拿不到 /x/player/wbi/playurl（无 CORS），且分片 CDN 校验 Referer/UA。
 *  - 本代理在服务端用 WBI 签名取 DASH 流，把音视频 baseUrl 改写成
 *    http://<本机>:<端口>/seg?u=<编码后的真实地址>，再逐段回源并转发（带 Range 透传，
 *    支持拖拽/缓冲）。前端 dash.js 全程访问同源 localhost，无 CORS、无 referer 问题。
 *
 * 运行：node bili_h5_proxy.js  （默认端口 8124，可用 PORT=xxxx 覆盖）
 * 然后浏览器打开 http://127.0.0.1:8124/  —— 这就是自建 H5 播放器。
 *
 * 清晰度：游客（不带 sessdata）最高 480P（qn=32）；720P+ 需在页面里填 SESSDATA
 * （从浏览器 Cookie 里复制，14 天有效期）。SESSDATA 只存在你本机内存/页面 localStorage，
 * 不会上传到任何第三方。
 */
'use strict';
const http = require('http');
const https = require('https');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');

const ROOT = path.resolve(__dirname, '..', '..');           // 仓库根
const PAGE = path.join(ROOT, 'pages', 'h5-player.html');
const DATA = path.join(ROOT, 'pages', 'facteasy-data.js');

const PORT = parseInt(process.env.PORT, 10) || 8124;
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
const REFERER = 'https://www.bilibili.com';

/* ---------------- WBI 签名 ---------------- */
const MIXIN_KEY_ENC_TAB = [
  46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,
  37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52
];

function getMixinKey(imgKey, subKey){
  const raw = imgKey + subKey;
  let s = '';
  for (const i of MIXIN_KEY_ENC_TAB) s += raw[i] || '';
  return s.slice(0, 32);
}
function signWbi(params, imgKey, subKey){
  const mixin = getMixinKey(imgKey, subKey);
  const p = Object.assign({}, params, { wts: Math.floor(Date.now() / 1000) });
  const keys = Object.keys(p).sort();
  const query = keys.map(k => {
    const v = String(p[k]).replace(/[!'()*]/g, '');
    return encodeURIComponent(k) + '=' + encodeURIComponent(v);
  }).join('&');
  const w_rid = crypto.createHash('md5').update(query + mixin).digest('hex');
  return Object.assign({}, p, { w_rid });
}

/* ---------------- 取流 ---------------- */
let keyCache = { at: 0, imgKey: '', subKey: '' };
function getWbiKeys(sessdata){
  if (keyCache.imgKey && Date.now() - keyCache.at < 12 * 3600 * 1000){
    return Promise.resolve({ imgKey: keyCache.imgKey, subKey: keyCache.subKey });
  }
  return biliJson('https://api.bilibili.com/x/web-interface/nav', {}, sessdata).then(d => {
    const img = d.data && d.data.wbi_img && d.data.wbi_img.img_url;
    const sub = d.data && d.data.wbi_img && d.data.wbi_img.sub_url;
    if (!img || !sub) throw new Error('拿不到 wbi_img（code=' + d.code + '）');
    keyCache = {
      at: Date.now(),
      imgKey: img.split('/').pop().split('.')[0],
      subKey: sub.split('/').pop().split('.')[0]
    };
    return { imgKey: keyCache.imgKey, subKey: keyCache.subKey };
  });
}

function biliJson(url, params, sessdata){
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    Object.keys(params).forEach(k => u.searchParams.set(k, params[k]));
    const headers = { 'User-Agent': UA, 'Referer': REFERER, 'Accept': 'application/json' };
    if (sessdata) headers['Cookie'] = 'SESSDATA=' + sessdata;
    const req = https.request(u, { method: 'GET', headers }, res => {
      let b = '';
      res.on('data', d => b += d);
      res.on('end', () => {
        try { resolve(JSON.parse(b)); }
        catch (e) { reject(new Error('JSON 解析失败: ' + b.slice(0, 200))); }
      });
    });
    req.on('error', reject);
    req.setTimeout(20000, () => req.destroy(new Error('nav 超时')));
    req.end();
  });
}

function rewriteDash(dash, host){
  const base = 'http://' + host;
  const rw = s => base + '/seg?u=' + encodeURIComponent(s);
  (dash.video || []).forEach(v => {
    v.baseUrl = rw(v.baseUrl);
    if (Array.isArray(v.backupUrl)) v.backupUrl = v.backupUrl.map(rw);
  });
  (dash.audio || []).forEach(a => {
    a.baseUrl = rw(a.baseUrl);
    if (Array.isArray(a.backupUrl)) a.backupUrl = a.backupUrl.map(rw);
  });
  return dash;
}

async function getPlayurl(bvid, cid, qn, sessdata, host){
  const { imgKey, subKey } = await getWbiKeys(sessdata);
  const signed = signWbi({ bvid, cid, qn, fnval: 16, fnver: 0, fourk: 1 }, imgKey, subKey);
  const data = await biliJson('https://api.bilibili.com/x/player/wbi/playurl', signed, sessdata);
  if (data.code !== 0) throw new Error('playurl 返回 code=' + data.code + ' msg=' + (data.message || ''));
  if (!data.data || !data.data.dash) throw new Error('无 dash 流（可能该清晰度需登录/VIP）');
  rewriteDash(data.data.dash, host);
  return data.data;
}

/* ---------------- 分片回源（带 Range 透传） ---------------- */
function streamProxy(req, res){
  const m = req.url.match(/\/seg\?u=(.+)$/);
  if (!m){ res.writeHead(400); res.end('missing u'); return; }
  let target;
  try { target = decodeURIComponent(m[1]); } catch (e){ res.writeHead(400); res.end('bad u'); return; }
  if (!/^https?:\/\//.test(target)){ res.writeHead(400); res.end('bad url'); return; }
  fetchUpstream(target, req.headers, res, 0);
}
function fetchUpstream(target, clientHeaders, res, depth){
  if (depth > 4){ res.writeHead(502); res.end('重定向过多'); return; }
  const tu = new URL(target);
  const headers = { 'User-Agent': UA, 'Referer': REFERER, 'Origin': REFERER };
  if (clientHeaders['range']) headers['Range'] = clientHeaders['range'];
  const lib = tu.protocol === 'http:' ? http : https;
  const r = lib.request(tu, { method: 'GET', headers }, up => {
    if ([301,302,303,307,308].includes(up.statusCode) && up.headers.location){
      fetchUpstream(new URL(up.headers.location, tu).href, clientHeaders, res, depth + 1);
      return;
    }
    const out = {
      'Content-Type': up.headers['content-type'] || 'application/octet-stream',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'no-store'
    };
    if (up.headers['content-length']) out['Content-Length'] = up.headers['content-length'];
    if (up.headers['content-range']) out['Content-Range'] = up.headers['content-range'];
    if (up.headers['accept-ranges']) out['Accept-Ranges'] = up.headers['accept-ranges'];
    res.writeHead(up.statusCode, out);
    up.pipe(res);
    up.on('error', () => { try { res.destroy(); } catch (e) {} });
  });
  r.on('error', e => { if (!res.headersSent) res.writeHead(502); res.end('回源失败: ' + e.message); });
  res.on('close', () => { try { r.destroy(); } catch (e) {} });
  r.end();
}

/* ---------------- 静态/页面 ---------------- */
function serveFile(res, file, type){
  fs.readFile(file, (err, buf) => {
    if (err){ res.writeHead(404); res.end('not found'); return; }
    res.writeHead(200, { 'Content-Type': type, 'Cache-Control': 'no-store' });
    res.end(buf);
  });
}

/* ---------------- HTTP 服务 ---------------- */
const server = http.createServer((req, res) => {
  const u = new URL(req.url, 'http://localhost');
  const q = u.searchParams;
  const host = req.headers.host || ('127.0.0.1:' + PORT);

  if (u.pathname === '/' || u.pathname === '/index.html'){
    return serveFile(res, PAGE, 'text/html; charset=utf-8');
  }
  if (u.pathname === '/facteasy-data.js'){
    return serveFile(res, DATA, 'application/javascript; charset=utf-8');
  }
  if (u.pathname === '/playurl'){
    const bvid = q.get('bvid') || 'BV1mQuC6fEFz';
    const cid = q.get('cid') || '40830764747';
    const qn = parseInt(q.get('qn') || '32', 10);
    const sessdata = q.get('sessdata') || '';
    getPlayurl(bvid, cid, qn, sessdata, host).then(dash => {
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(JSON.stringify(dash));
    }).catch(e => {
      res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ error: String(e.message) }));
    });
    return;
  }
  if (u.pathname === '/seg'){
    return streamProxy(req, res);
  }
  res.writeHead(404); res.end('not found');
});

server.listen(PORT, '127.0.0.1', () => {
  console.log('B 站 H5 代理已启动： http://127.0.0.1:' + PORT + '/');
  console.log('（游客 480P；填 SESSDATA 可解锁 720P+。Ctrl+C 退出）');
});
server.on('error', e => {
  if (e.code === 'EADDRINUSE'){
    console.error('端口 ' + PORT + ' 被占用，换 PORT=xxxx 再试');
  } else {
    console.error('server error', e.message);
  }
  process.exit(1);
});
