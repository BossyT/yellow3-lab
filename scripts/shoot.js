#!/usr/bin/env node
//
// Screenshot a list of pages at a list of widths, with a real layout viewport.
//
// Same reason as scripts/responsive-qa.js: `chrome --headless --screenshot
// --window-size` does not give you the width you asked for. This drives CDP,
// sets device metrics, forces lazy images to load, and writes one PNG per
// page per width - which is what a before/after comparison needs.
//
//   SHOOT_OUT=/tmp/before node --experimental-websocket scripts/shoot.js \
//     https://www.yellow3.io/ https://www.yellow3.io/platforms
//
//   SHOOT_WIDTHS=390,768,1024,1440 ... to override the default widths.

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const OUT = process.env.SHOOT_OUT || path.join(os.tmpdir(), 'shoot');
const WIDTHS = (process.env.SHOOT_WIDTHS || '1440').split(',').map(Number);
const FULL = process.env.SHOOT_FULL !== '0';
const urls = process.argv.slice(2);

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

const slug = (u, w) => u.replace(/^https?:\/\//, '').replace(/[^\w.-]+/g, '_')
  .replace(/_+$/, '') + '@' + w + '.png';

async function main() {
  if (!urls.length) { console.error('give me some urls'); process.exit(1); }
  fs.mkdirSync(OUT, { recursive: true });
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'shoot-profile-'));
  const port = 9600 + (process.pid % 300);
  const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--hide-scrollbars',
    '--no-first-run', '--remote-debugging-port=' + port, '--user-data-dir=' + profile,
    'about:blank'], { stdio: 'ignore' });

  let wsUrl = null;
  for (let i = 0; i < 50 && !wsUrl; i++) {
    await sleep(200);
    try { wsUrl = (await (await fetch(`http://127.0.0.1:${port}/json/version`)).json())
      .webSocketDebuggerUrl; } catch { /* starting */ }
  }
  if (!wsUrl) { chrome.kill(); throw new Error('no debugger'); }

  const ws = new WebSocket(wsUrl);
  await new Promise(r => ws.addEventListener('open', r, { once: true }));
  const { targetId } = await rpc(ws, 'Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await rpc(ws, 'Target.attachToTarget', { targetId, flatten: true });
  await rpc(ws, 'Page.enable', {}, sessionId);
  await rpc(ws, 'Runtime.enable', {}, sessionId);

  for (const url of urls) {
    for (const w of WIDTHS) {
      await rpc(ws, 'Emulation.setDeviceMetricsOverride',
        { width: w, height: 900, deviceScaleFactor: 1, mobile: w < 900 }, sessionId);
      await rpc(ws, 'Page.navigate',
        { url: url + (url.includes('?') ? '&' : '?') + 'shot=' + Date.now() }, sessionId);
      await sleep(2600);
      // Lazy images never load for a screenshot - force and wait, or the shot
      // shows grey holes that look like layout faults.
      await rpc(ws, 'Runtime.evaluate', { expression: `(async () => {
        const imgs = [...document.images];
        imgs.forEach(i => { i.loading = 'eager'; if (!i.complete) i.src = i.src; });
        await Promise.all(imgs.map(i => i.complete ? null
          : new Promise(r => { i.onload = i.onerror = r; })));
      })()`, awaitPromise: true }, sessionId).catch(() => {});
      await sleep(500);
      const shot = await rpc(ws, 'Page.captureScreenshot',
        { format: 'png', captureBeyondViewport: FULL }, sessionId);
      const file = path.join(OUT, slug(url, w));
      fs.writeFileSync(file, Buffer.from(shot.data, 'base64'));
      console.log('  ' + path.basename(file));
    }
  }

  ws.close(); chrome.kill(); await sleep(600);
  try { fs.rmSync(profile, { recursive: true, force: true, maxRetries: 3 }); } catch {}
  console.log('\nwritten to ' + OUT);
}

main().catch(e => { console.error(e.message); process.exit(1); });
