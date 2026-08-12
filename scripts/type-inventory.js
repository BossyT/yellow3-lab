#!/usr/bin/env node
//
// What typography does a live page ACTUALLY use, by semantic role?
//
// Written because /research and /platforms look like different design systems
// while sharing a font family. The difference had to be measured rather than
// guessed - the same argument as every other guard in this repo.
//
//   node --experimental-websocket scripts/type-inventory.js <url> [<url> ...]
//
// Reads computed styles from the rendered page, groups them by role, and
// prints the distinct treatments per role with how many elements carry each.
// It changes nothing.

const { spawn } = require('node:child_process');
const fs = require('node:fs'); const os = require('node:os'); const path = require('node:path');
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const WIDTH = Number(process.env.TYPE_WIDTH || 1440);
const urls = process.argv.slice(2);
const sleep = ms => new Promise(r => setTimeout(r, ms));
let nextId = 1;

function rpc(ws, method, params = {}, sessionId) {
  const id = nextId++;
  return new Promise((res, rej) => {
    const on = (e) => { let m; try { m = JSON.parse(e.data); } catch { return; }
      if (m.id !== id) return; ws.removeEventListener('message', on);
      m.error ? rej(new Error(m.error.message)) : res(m.result); };
    ws.addEventListener('message', on);
    ws.send(JSON.stringify(sessionId ? { id, method, params, sessionId } : { id, method, params }));
  });
}

// Roles are decided by what an element IS on the page, not by its class name -
// a hero title is a hero title whether it is called .hero h1 or
// .y3-platforms__headline.
const PROBE = `(() => {
  const seen = [];
  const px = v => v === 'normal' ? 'normal' : v;
  const inNav = el => !!el.closest('nav, .site-nav');
  const inFoot = el => !!el.closest('footer, .site-footer');

  const role = (el) => {
    const t = el.tagName.toLowerCase();
    const cs = getComputedStyle(el);
    const size = parseFloat(cs.fontSize);
    if (inNav(el)) return 'nav';
    if (inFoot(el)) return 'footer';
    if (t === 'h1') return 'display / h1';
    if (t === 'h2') return 'h2';
    if (t === 'h3' || t === 'h4') return t;
    // A div acting as a heading: large, short, and not a paragraph.
    if (size >= 24 && (el.children.length === 0) && el.textContent.trim().length < 120)
      return 'display-like (non-heading)';
    if (cs.textTransform === 'uppercase' && size <= 13) return 'eyebrow / micro label';
    if (t === 'a' || t === 'button') return 'action / cta';
    if (t === 'p' && size >= 15) return 'body';
    if (t === 'p' || t === 'small' || t === 'span') return 'secondary body';
    return null;
  };

  for (const el of document.querySelectorAll('body *')) {
    if (!el.textContent || !el.textContent.trim()) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const rl = role(el);
    if (!rl) continue;
    const cs = getComputedStyle(el);
    seen.push({
      role: rl,
      tag: el.tagName.toLowerCase(),
      cls: (el.className || '').toString().split(' ').filter(Boolean).slice(0,2).join('.'),
      family: cs.fontFamily.split(',')[0].replace(/["']/g,''),
      size: Math.round(parseFloat(cs.fontSize) * 10) / 10,
      weight: cs.fontWeight,
      line: cs.lineHeight === 'normal' ? 'normal'
            : Math.round((parseFloat(cs.lineHeight) / parseFloat(cs.fontSize)) * 100) / 100,
      spacing: cs.letterSpacing === 'normal' ? 'normal'
            : Math.round(parseFloat(cs.letterSpacing) * 100) / 100 + 'px',
      transform: cs.textTransform,
      sample: el.textContent.trim().replace(/\\s+/g,' ').slice(0, 40),
    });
  }
  return seen;
})()`;

(async () => {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'ti-'));
  const port = 9700 + (process.pid % 90);
  const chrome = spawn(CHROME, ['--headless=new','--disable-gpu','--hide-scrollbars','--no-first-run',
    '--remote-debugging-port='+port,'--user-data-dir='+profile,'about:blank'], { stdio:'ignore' });
  let wsUrl = null;
  for (let i=0;i<50&&!wsUrl;i++){ await sleep(200);
    try { wsUrl=(await (await fetch(`http://127.0.0.1:${port}/json/version`)).json()).webSocketDebuggerUrl; } catch {} }
  const ws = new WebSocket(wsUrl);
  await new Promise(r => ws.addEventListener('open', r, { once: true }));
  const { targetId } = await rpc(ws,'Target.createTarget',{url:'about:blank'});
  const { sessionId } = await rpc(ws,'Target.attachToTarget',{targetId,flatten:true});
  await rpc(ws,'Page.enable',{},sessionId); await rpc(ws,'Runtime.enable',{},sessionId);
  await rpc(ws,'Emulation.setDeviceMetricsOverride',
    {width:WIDTH,height:1000,deviceScaleFactor:1,mobile:false},sessionId);

  const ORDER = ['display / h1','display-like (non-heading)','h2','h3','h4','body',
                 'secondary body','eyebrow / micro label','action / cta','nav','footer'];

  for (const url of urls) {
    await rpc(ws,'Page.navigate',{url:url+(url.includes('?')?'&':'?')+'ti='+Date.now()},sessionId);
    await sleep(2500);
    const { result } = await rpc(ws,'Runtime.evaluate',{expression:PROBE,returnByValue:true},sessionId);
    const rows = result.value;
    console.log('\n' + '='.repeat(78) + '\n' + url + '  @' + WIDTH + 'px\n');
    for (const role of ORDER) {
      const mine = rows.filter(r => r.role === role);
      if (!mine.length) continue;
      const groups = new Map();
      for (const r of mine) {
        const key = `${r.size}px / ${r.weight} / lh ${r.line} / ls ${r.spacing} / ${r.transform}`;
        if (!groups.has(key)) groups.set(key, { n: 0, eg: r });
        groups.get(key).n++;
      }
      console.log(`  ${role}`);
      for (const [key, g] of [...groups].sort((a,b) => b[1].n - a[1].n).slice(0, 4)) {
        console.log(`    ${String(g.n).padStart(3)}x  ${key}`);
        console.log(`         ${g.eg.tag}${g.eg.cls ? '.' + g.eg.cls : ''}  "${g.eg.sample}"`);
      }
    }
  }
  ws.close(); chrome.kill(); await sleep(500);
  try { fs.rmSync(profile,{recursive:true,force:true,maxRetries:3}); } catch {}
})();
