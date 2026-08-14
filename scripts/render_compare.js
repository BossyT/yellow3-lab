#!/usr/bin/env node
//
// The render-comparison gate: approved prototype against production page,
// content root to content root, at real device widths.
//
// GPT made this mandatory on 2026-08-14, after three defects shipped that
// reading the code could never have caught. Homepage V3 was ported rule for
// rule and still rendered at 13,732px against an approved 8,999px, because the
// port flattened one @media block into unconditional rules - and the rule count
// matched at 143 either way. A stylesheet can be faithful and still be wrong.
//
// So this measures the rendered page. It reports per-section heights and the
// computed styles behind them, because a proportional shortfall is a typography
// fault and a constant offset is a padding fault, and the numbers say which.
//
// Nav and footer are excluded by construction: the comparison is rooted at the
// content root of each page, and the prototypes do not contain a shell.
//
//   node --experimental-websocket scripts/render_compare.js \
//     --approved file:///.../APPROVED_RESEARCH_CONTENT.html \
//     --production http://localhost:8000/research.html \
//     --approved-root main --production-root main.rs1 \
//     --probe h1 --probe h2 --probe .wrap
//
// SHOOT_WIDTHS=1440,390 overrides the widths.

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const WIDTHS = (process.env.SHOOT_WIDTHS || '1440,390').split(',').map(Number);

const argv = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = argv.indexOf('--' + name);
  return i === -1 ? fallback : argv[i + 1];
};
const args = (name) => argv.reduce((acc, v, i) =>
  (v === '--' + name ? acc.concat(argv[i + 1]) : acc), []);

const APPROVED = arg('approved');
const PRODUCTION = arg('production');
const APPROVED_ROOT = arg('approved-root', 'main');
const PRODUCTION_ROOT = arg('production-root', 'main');
const PROBES = args('probe');
const OUT = arg('out');

if (!APPROVED || !PRODUCTION) {
  console.error('need --approved <url> and --production <url>');
  process.exit(1);
}

const sleep = ms => new Promise(r => setTimeout(r, ms));
let nextId = 1;

function rpc(ws, method, params = {}, sessionId) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    const onMessage = (event) => {
      let msg; try { msg = JSON.parse(event.data); } catch { return; }
      if (msg.id !== id) return;
      ws.removeEventListener('message', onMessage);
      msg.error ? reject(new Error(method + ': ' + msg.error.message)) : resolve(msg.result);
    };
    ws.addEventListener('message', onMessage);
    ws.send(JSON.stringify(sessionId ? { id, method, params, sessionId } : { id, method, params }));
  });
}

// Runs in the page. Heights come from getBoundingClientRect so that margins,
// borders and grid gaps are all accounted for exactly as painted.
const PROBE_FN = (rootSel, probeSels) => {
  const round = n => Math.round(n * 10) / 10;
  const root = document.querySelector(rootSel);
  if (!root) return JSON.stringify({ error: 'no content root: ' + rootSel });

  const label = el => {
    const cls = [...el.classList].filter(c => c !== 'section');
    return cls.length ? cls.join('.') : (el.className || el.tagName.toLowerCase());
  };

  const sections = [...root.children]
    .filter(el => el.tagName === 'SECTION')
    .map(el => ({ name: label(el), height: round(el.getBoundingClientRect().height) }));

  const KEYS = ['font-size', 'line-height', 'letter-spacing', 'font-weight',
    'margin-top', 'margin-bottom', 'padding-top', 'padding-bottom',
    'max-width', 'display', 'grid-template-columns', 'gap', 'color'];

  const computed = {};
  for (const sel of probeSels) {
    const nodes = [...root.querySelectorAll(sel)];
    computed[sel] = nodes.slice(0, 8).map(el => {
      const cs = getComputedStyle(el);
      const out = { text: (el.textContent || '').trim().slice(0, 34) };
      for (const k of KEYS) out[k] = cs.getPropertyValue(k);
      out.height = round(el.getBoundingClientRect().height);
      out.width = round(el.getBoundingClientRect().width);
      return out;
    });
  }

  const de = document.documentElement;
  return JSON.stringify({
    rootHeight: round(root.getBoundingClientRect().height),
    sections,
    computed,
    overflow: de.scrollWidth > de.clientWidth
      ? { scrollWidth: de.scrollWidth, clientWidth: de.clientWidth } : null,
    brokenImages: [...root.querySelectorAll('img')]
      .filter(i => !i.complete || i.naturalWidth === 0)
      .map(i => i.getAttribute('src')),
  });
};

async function capture(ws, sessionId, url, rootSel, width) {
  await rpc(ws, 'Emulation.setDeviceMetricsOverride',
    { width, height: 900, deviceScaleFactor: 1, mobile: width < 900 }, sessionId);
  await rpc(ws, 'Page.navigate', { url }, sessionId);
  await sleep(1800);
  // Below-fold images stay lazy in a headless render and measure as zero, which
  // reads exactly like a collapsed section. Force them and wait.
  await rpc(ws, 'Runtime.evaluate', {
    expression: `(async () => {
      const imgs=[...document.images];
      imgs.forEach(i=>{i.loading='eager'; if(!i.complete) i.src=i.src;});
      await Promise.all(imgs.map(i=>i.complete?null:new Promise(r=>{i.onload=i.onerror=r;})));
      document.fonts && await document.fonts.ready;
    })()`, awaitPromise: true }, sessionId).catch(() => {});
  await sleep(500);
  const expr = `(${PROBE_FN.toString()})(${JSON.stringify(rootSel)},${JSON.stringify(PROBES)})`;
  const r = await rpc(ws, 'Runtime.evaluate',
    { expression: expr, returnByValue: true }, sessionId);
  return JSON.parse(r.result.value);
}

const pad = (s, n) => String(s).padEnd(n);
const lpad = (s, n) => String(s).padStart(n);

function report(width, approved, production) {
  console.log('\n' + '='.repeat(66));
  console.log(`  ${width}px - content root to content root`);
  console.log('='.repeat(66));

  if (approved.error || production.error) {
    console.log('  ' + (approved.error || production.error));
    return false;
  }

  console.log(`  ${pad('section', 16)}${lpad('approved', 10)}${lpad('production', 12)}${lpad('ratio', 9)}`);
  console.log('  ' + '-'.repeat(45));

  const n = Math.max(approved.sections.length, production.sections.length);
  let worst = 1;
  for (let i = 0; i < n; i++) {
    const a = approved.sections[i], p = production.sections[i];
    if (!a || !p) { console.log(`  ${pad((a || p).name, 16)}  section count differs`); worst = 0; continue; }
    const ratio = p.height / a.height;
    const flag = Math.abs(ratio - 1) > 0.02 ? '  <-- ' + (ratio < 1 ? 'short' : 'tall') : '';
    console.log(`  ${pad(a.name, 16)}${lpad(a.height, 10)}${lpad(p.height, 12)}${lpad(ratio.toFixed(3), 9)}${flag}`);
    if (Math.abs(ratio - 1) > Math.abs(worst - 1)) worst = ratio;
  }
  console.log('  ' + '-'.repeat(45));
  const total = production.rootHeight / approved.rootHeight;
  console.log(`  ${pad('TOTAL', 16)}${lpad(approved.rootHeight, 10)}${lpad(production.rootHeight, 12)}${lpad(total.toFixed(3), 9)}`);

  for (const [side, data] of [['approved', approved], ['production', production]]) {
    if (data.overflow) console.log(`\n  ! ${side} overflows: ${data.overflow.scrollWidth} > ${data.overflow.clientWidth}`);
    if (data.brokenImages.length) console.log(`  ! ${side} broken images: ${data.brokenImages.join(', ')}`);
  }

  // Computed-style differences are the evidence behind a ratio. A proportional
  // shortfall with no computed difference means look somewhere else.
  const diffs = [];
  for (const sel of PROBES) {
    const A = approved.computed[sel] || [], P = production.computed[sel] || [];
    if (A.length !== P.length) {
      diffs.push(`${sel}: ${A.length} node(s) approved, ${P.length} production`);
      continue;
    }
    for (let i = 0; i < A.length; i++) {
      for (const k of Object.keys(A[i])) {
        if (k === 'text') continue;
        if (A[i][k] !== P[i][k])
          diffs.push(`${sel}[${i}] ${k}: ${A[i][k]} -> ${P[i][k]}   "${A[i].text}"`);
      }
    }
  }
  if (diffs.length) {
    console.log('\n  computed-style differences');
    for (const d of diffs.slice(0, 60)) console.log('    ' + d);
    if (diffs.length > 60) console.log(`    ... and ${diffs.length - 60} more`);
  } else if (PROBES.length) {
    console.log('\n  computed styles identical across all probes');
  }

  return Math.abs(total - 1) <= 0.02 && diffs.length === 0;
}

async function main() {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'rcmp-profile-'));
  const port = 9300 + (process.pid % 200);
  const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--hide-scrollbars',
    '--no-first-run', '--allow-file-access-from-files',
    '--remote-debugging-port=' + port, '--user-data-dir=' + profile,
    'about:blank'], { stdio: 'ignore' });

  let wsUrl = null;
  for (let i = 0; i < 50 && !wsUrl; i++) {
    await sleep(200);
    try { wsUrl = (await (await fetch(`http://127.0.0.1:${port}/json/version`)).json())
      .webSocketDebuggerUrl; } catch { /* starting */ }
  }
  if (!wsUrl) { chrome.kill(); throw new Error('chrome did not come up'); }

  const ws = new WebSocket(wsUrl);
  await new Promise(r => ws.addEventListener('open', r, { once: true }));
  const { targetId } = await rpc(ws, 'Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await rpc(ws, 'Target.attachToTarget', { targetId, flatten: true });
  await rpc(ws, 'Page.enable', {}, sessionId);
  await rpc(ws, 'Runtime.enable', {}, sessionId);

  const all = {};
  let green = true;
  for (const w of WIDTHS) {
    const approved = await capture(ws, sessionId, APPROVED, APPROVED_ROOT, w);
    const production = await capture(ws, sessionId, PRODUCTION, PRODUCTION_ROOT, w);
    all[w] = { approved, production };
    if (!report(w, approved, production)) green = false;
  }

  if (OUT) fs.writeFileSync(OUT, JSON.stringify(all, null, 1));
  console.log('\n' + (green
    ? '  GREEN - every section within 2% and no computed-style difference'
    : '  NOT GREEN - see the rows flagged above') + '\n');

  ws.close(); chrome.kill(); await sleep(400);
  try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
  process.exit(green ? 0 : 1);
}

main().catch(e => { console.error(e.message); process.exit(2); });
