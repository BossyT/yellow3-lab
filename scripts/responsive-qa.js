#!/usr/bin/env node
//
// Responsive QA against a real layout viewport.
//
// WHY THIS EXISTS. `chrome --headless --screenshot --window-size=390,844`
// does NOT give you a 390px page. The window has a platform minimum and no
// device emulation, so the page lays out wider and the screenshot simply crops
// it - which looks exactly like a horizontal-overflow bug and is not one. The
// known-good homepage clips the same way, which is how the artefact was caught.
//
// The only honest way is the DevTools protocol: Emulation.setDeviceMetricsOverride
// sets the layout viewport, so media queries fire at the width you asked for.
//
//   node --experimental-websocket scripts/responsive-qa.js <url> [--shots]
//
// Node 20 needs the flag; the WebSocket client is otherwise built in. No npm
// packages - this repo has no node_modules and is not getting one for QA.

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const URL_ARG = process.argv[2] || 'https://www.yellow3.io/platforms';
const WANT_SHOTS = process.argv.includes('--shots');
const OUT = process.env.QA_OUT || path.join(os.tmpdir(), 'responsive-qa');

// The two the design owner asked to see, plus a width either side of every
// breakpoint the page ships - a rule that fires one pixel late is a rule that
// is wrong, and only the pair catches it.
const VIEWPORTS = [
  { w: 390,  h: 844,  mobile: true,  shot: 'mobile-390x844' },
  { w: 768,  h: 1024, mobile: true,  shot: 'tablet-768x1024' },
  { w: 619,  h: 900,  mobile: true },
  { w: 621,  h: 900,  mobile: true },
  { w: 859,  h: 900,  mobile: true },
  { w: 861,  h: 900,  mobile: false },
  { w: 899,  h: 900,  mobile: false },
  { w: 901,  h: 900,  mobile: false },
];

// Runs inside the page. Returns facts, not opinions.
const PROBE = `(() => {
  const q = s => document.querySelector(s);
  const qa = s => [...document.querySelectorAll(s)];
  const vw = document.documentElement.clientWidth;
  const top = el => el ? Math.round(el.getBoundingClientRect().top + window.scrollY) : null;

  // Anything actually sticking out past the viewport, named.
  const offenders = [];
  for (const el of qa('.y3-platforms *')) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && (r.right > vw + 1 || r.left < -1)) {
      offenders.push((el.className || el.tagName) + ' w=' + Math.round(r.width)
                     + ' right=' + Math.round(r.right));
    }
  }

  const callout = q('.y3-platforms__callout');
  const actions = q('.y3-platforms__actions');
  const actionKids = actions ? [...actions.children] : [];
  const idxRow = q('.y3-platforms__product-index-row');
  const img = q('#model-intelligence img');

  // Evidence strip must sit BELOW its product story, in every area that has one.
  const orderOk = qa('.y3-platforms__product-section').every(sec => {
    const story = sec.querySelector('.y3-platforms__story');
    const ev = sec.querySelector('.y3-platforms__evidence');
    return !ev || !story || ev.getBoundingClientRect().top > story.getBoundingClientRect().top;
  });

  return {
    viewport: vw,
    docScrollWidth: document.documentElement.scrollWidth,
    horizontalOverflow: document.documentElement.scrollWidth > vw + 1,
    offenders: offenders.slice(0, 6),
    calloutPosition: callout ? getComputedStyle(callout).position : null,
    calloutBelowImage: (() => {
      const shot = q('.y3-platforms__screenshot');
      if (!callout || !shot) return null;
      return callout.getBoundingClientRect().top >= shot.getBoundingClientRect().bottom - 2;
    })(),
    ctaStacked: actionKids.length > 1
      ? Math.abs(actionKids[0].getBoundingClientRect().top
                 - actionKids[1].getBoundingClientRect().top) > 4
      : null,
    productIndexFont: idxRow
      ? getComputedStyle(idxRow.querySelector('strong')).fontSize : null,
    productIndexRows: qa('.y3-platforms__product-index-row').length,
    productOrder: qa('.y3-platforms__product-name').map(e => e.textContent.trim()),
    evidenceBelowProduct: orderOk,
    conversionRows: qa('.y3-platforms__conversion-row').length,
    conversionRowHeight: (() => {
      const r = q('.y3-platforms__conversion-row');
      return r ? Math.round(r.getBoundingClientRect().height) : null;
    })(),
    naffeCopyVisible: (() => {
      const s = q('#naffe-ai .y3-platforms__story-copy');
      if (!s) return null;
      const r = s.getBoundingClientRect();
      return r.width > 200 && r.height > 100;
    })(),
    miImageRendered: img
      ? { w: Math.round(img.getBoundingClientRect().width),
          h: Math.round(img.getBoundingClientRect().height),
          natural: img.naturalWidth + 'x' + img.naturalHeight,
          fit: getComputedStyle(img).objectFit }
      : null,
  };
})()`;

// --------------------------------------------------------------------- CDP

let nextId = 1;
function rpc(ws, method, params = {}, sessionId) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    const onMessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }
      if (msg.id !== id) return;
      ws.removeEventListener('message', onMessage);
      msg.error ? reject(new Error(method + ': ' + msg.error.message)) : resolve(msg.result);
    };
    ws.addEventListener('message', onMessage);
    ws.send(JSON.stringify(sessionId ? { id, method, params, sessionId }
                                     : { id, method, params }));
  });
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  if (typeof WebSocket === 'undefined') {
    console.error('No WebSocket. Run with: node --experimental-websocket ' + process.argv[1]);
    process.exit(1);
  }
  fs.mkdirSync(OUT, { recursive: true });
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-profile-'));
  const port = 9333 + (process.pid % 200);

  const chrome = spawn(CHROME, [
    '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
    '--remote-debugging-port=' + port, '--user-data-dir=' + profile,
    'about:blank',
  ], { stdio: 'ignore' });

  let wsUrl = null;
  for (let i = 0; i < 50 && !wsUrl; i++) {
    await sleep(200);
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/version`);
      wsUrl = (await res.json()).webSocketDebuggerUrl;
    } catch { /* not up yet */ }
  }
  if (!wsUrl) { chrome.kill(); throw new Error('Chrome did not expose a debugger'); }

  const ws = new WebSocket(wsUrl);
  await new Promise(r => ws.addEventListener('open', r, { once: true }));

  const { targetId } = await rpc(ws, 'Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await rpc(ws, 'Target.attachToTarget', { targetId, flatten: true });
  await rpc(ws, 'Page.enable', {}, sessionId);
  await rpc(ws, 'Runtime.enable', {}, sessionId);

  const results = [];
  for (const vp of VIEWPORTS) {
    await rpc(ws, 'Emulation.setDeviceMetricsOverride', {
      width: vp.w, height: vp.h, deviceScaleFactor: vp.mobile ? 2 : 1,
      mobile: vp.mobile,
    }, sessionId);

    const url = URL_ARG + (URL_ARG.includes('?') ? '&' : '?') + 'qa=' + Date.now();
    await rpc(ws, 'Page.navigate', { url }, sessionId);
    await sleep(2500);                       // let fonts, images and layout settle

    const { result } = await rpc(ws, 'Runtime.evaluate', {
      expression: PROBE, returnByValue: true, awaitPromise: false,
    }, sessionId);
    results.push({ width: vp.w, ...result.value });

    if (WANT_SHOTS && vp.shot) {
      // LAZY IMAGES DO NOT LOAD FOR A SCREENSHOT. captureBeyondViewport paints
      // the whole page, but an <img loading="lazy"> below the fold was never
      // scrolled into view, so it is still empty - which renders as a grey hole
      // where the product UI should be and reads exactly like a layout bug.
      // Force them eager and wait for the decode before capturing.
      await rpc(ws, 'Runtime.evaluate', { expression: `(async () => {
        const imgs = [...document.images];
        imgs.forEach(i => { i.loading = 'eager'; if (!i.complete) i.src = i.src; });
        await Promise.all(imgs.map(i => i.complete ? null
          : new Promise(r => { i.onload = i.onerror = r; })));
        return imgs.map(i => i.naturalWidth).join(',');
      })()`, awaitPromise: true, returnByValue: true }, sessionId);
      await sleep(800);
      const shot = await rpc(ws, 'Page.captureScreenshot', {
        format: 'png', captureBeyondViewport: true,
      }, sessionId);
      const file = path.join(OUT, vp.shot + '.png');
      fs.writeFileSync(file, Buffer.from(shot.data, 'base64'));
      console.log('  shot ' + file);
    }
  }

  ws.close();
  chrome.kill();
  // Chrome is still flushing its profile; a failed tidy-up must never lose the
  // report the run exists to produce.
  await sleep(600);
  try { fs.rmSync(profile, { recursive: true, force: true, maxRetries: 3 }); }
  catch { /* a temp dir left behind is not a QA result */ }

  console.log('\n' + URL_ARG + '\n');
  let bad = 0;
  for (const r of results) {
    const flags = [];
    if (r.horizontalOverflow) { flags.push('HORIZONTAL OVERFLOW'); bad++; }
    if (!r.evidenceBelowProduct) { flags.push('evidence strip above its product'); bad++; }
    if (r.width <= 900 && r.calloutPosition !== 'static') {
      flags.push('callout not static (' + r.calloutPosition + ')'); bad++;
    }
    if (r.width > 900 && r.calloutPosition !== 'absolute') {
      flags.push('callout not overlaying (' + r.calloutPosition + ')'); bad++;
    }
    if (r.width <= 620 && r.ctaStacked === false) { flags.push('CTA pair not stacked'); bad++; }
    console.log(`${String(r.width).padStart(4)}px  scrollW=${r.docScrollWidth}`
      + `  callout=${r.calloutPosition}`
      + `  index=${r.productIndexRows} rows @ ${r.productIndexFont}`
      + `  conv=${r.conversionRows}@${r.conversionRowHeight}px`
      + `  ${flags.length ? 'FAIL ' + flags.join('; ') : 'ok'}`);
    if (r.offenders.length) console.log('        wider than viewport: ' + r.offenders.join(' | '));
  }
  const order = results[0].productOrder;
  console.log('\nproduct order: ' + order.join(' -> '));
  console.log('MI image     : ' + JSON.stringify(results[0].miImageRendered));
  console.log(bad ? `\n${bad} problem(s)\n` : '\nno problems\n');
  process.exit(bad ? 1 : 0);
}

main().catch(e => { console.error(e.message); process.exit(1); });
