#!/usr/bin/env node
//
// Monday Briefing acceptance test, run against a real browser and real media.
//
// WHY IT EXISTS. Every Monday a new edition ships with a new recording and four
// new timing markers. Nothing else in this repo can tell you whether the player
// actually starts with sound, whether the active row follows THIS edition's
// markers, or whether a seek moves both - a screenshot shows none of it, and
// the markers are the one part of the contract that changes every week and is
// measured by hand.
//
// IT READS THE MARKERS OFF THE PAGE, never from a constant here. A test with
// its own copy of the timings would pass while the page carried last week's.
//
//   node --experimental-websocket scripts/briefing-qa.js <url>
//
// THE SERVER MUST HONOUR RANGE REQUESTS. `python3 -m http.server` does not, and
// without them Chrome refuses to seek past what it has buffered - which looks
// exactly like broken story synchronisation and is not. That cost a diagnosis
// once already: five acceptance checks failed against a correct player. Vercel
// Blob serves ranges, so production is fine; for a local run use a server that
// sends `Accept-Ranges: bytes` and check with:
//
//   curl -sI -H 'Range: bytes=0-99' <media-url> | head -1     -> 206
//
// --autoplay-policy is set so a headless run can start media without a gesture.
// The SITE's own requirement is checked separately: the first assertion is that
// nothing is playing on load.

const { spawn } = require('node:child_process');

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const URL_ARG = process.argv[2];
if (!URL_ARG) {
  console.error('usage: node --experimental-websocket scripts/briefing-qa.js <url>');
  process.exit(2);
}

let nextId = 1;
const sleep = ms => new Promise(r => setTimeout(r, ms));

function rpc(ws, method, params = {}) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    const onMessage = (event) => {
      let msg; try { msg = JSON.parse(event.data); } catch { return; }
      if (msg.id !== id) return;
      ws.removeEventListener('message', onMessage);
      msg.error ? reject(new Error(method + ': ' + msg.error.message)) : resolve(msg.result);
    };
    ws.addEventListener('message', onMessage);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

let pass = 0;
const failures = [];
function check(name, ok, detail) {
  if (ok) { pass++; console.log(`  ok    ${name}${detail ? '   ' + detail : ''}`); }
  else { failures.push(name); console.log(`  FAIL  ${name}${detail ? '   ' + detail : ''}`); }
}

(async () => {
  const port = 9337;
  const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${port}`,
    '--no-first-run', '--autoplay-policy=no-user-gesture-required',
    '--user-data-dir=/tmp/briefing-qa-profile'], { stdio: 'ignore' });
  await sleep(1500);

  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const ws = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
  await new Promise(r => ws.addEventListener('open', r));
  await rpc(ws, 'Page.enable');
  await rpc(ws, 'Emulation.setDeviceMetricsOverride',
    { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
  await rpc(ws, 'Page.navigate', { url: URL_ARG });
  await sleep(2500);

  const ev = async expr => (await rpc(ws, 'Runtime.evaluate',
    { returnByValue: true, awaitPromise: true, expression: expr })).result.value;

  // ---- the edition's own markers -----------------------------------------
  const marks = await ev(`[...document.querySelectorAll('.story-row')]
    .map(r => parseFloat(r.getAttribute('data-at')))`);
  console.log('\nEDITION');
  check('four story rows', marks.length === 4, JSON.stringify(marks));
  check('every marker is numeric', marks.every(m => Number.isFinite(m)), JSON.stringify(marks));
  check('story 01 starts at zero', marks[0] === 0);
  check('markers ascend', marks.every((m, i) => i === 0 || m > marks[i - 1]));
  check('markers are not the handover sample',
    JSON.stringify(marks) !== JSON.stringify([0, 14, 27, 41]));

  // ---- idle ---------------------------------------------------------------
  const idle = await ev(`(() => { const v = document.querySelector('.astrid-video');
    const t = s => (document.querySelector(s) || {}).textContent;
    return { paused: v.paused, muted: v.muted, dur: v.duration,
      total: t('.timecode-total'), topline: t('.topline-total'), elapsed: t('.timecode-elapsed'),
      transport: t('.transport-text'), sound: t('.sound-button'),
      overlay: !!document.querySelector('.stage-play'),
      active: [...document.querySelectorAll('.story-row')].findIndex(r => r.classList.contains('active')) }; })()`);
  console.log('\nIDLE');
  check('nothing autoplays', idle.paused === true);
  check('media is not muted', idle.muted === false);
  check('PLAY WITH SOUND is offered', idle.overlay === true);
  check('transport reads PLAY', idle.transport === 'PLAY');
  check('sound reads SOUND ON', idle.sound === 'SOUND ON');
  check('elapsed starts at 00:00', idle.elapsed === '00:00');
  check('duration comes from the media', Number.isFinite(idle.dur) && idle.dur > 0 && idle.total !== '--:--',
    `${idle.total} (${idle.dur}s)`);
  check('no sample duration is displayed', idle.total !== '00:54' && Math.abs(idle.dur - 53.527) > 0.01);
  check('topline duration matches the transport', idle.topline === idle.total);
  check('story 01 is active at rest', idle.active === 0);

  // ---- playing ------------------------------------------------------------
  await ev(`document.querySelector('.stage-play').click()`);
  await sleep(2200);
  const playing = await ev(`(() => { const v = document.querySelector('.astrid-video');
    return { paused: v.paused, muted: v.muted, t: v.currentTime,
      overlay: !!document.querySelector('.stage-play') && !document.querySelector('.stage-play').hidden,
      transport: (document.querySelector('.transport-text')||{}).textContent }; })()`);
  console.log('\nPLAYING');
  check('one deliberate click starts playback', playing.paused === false);
  check('sound is on while playing', playing.muted === false);
  check('position advances', playing.t > 0.4, `t=${playing.t.toFixed(2)}s`);
  check('overlay control is removed', playing.overlay === false);
  check('transport reads PAUSE', playing.transport === 'PAUSE');

  // ---- synchronisation, against this edition's markers ---------------------
  console.log('\nSTORY SYNCHRONISATION');
  for (let i = 0; i < marks.length; i++) {
    const at = marks[i] + Math.min(2, (i + 1 < marks.length ? marks[i + 1] - marks[i] : 3) / 2);
    const got = await ev(`(async () => { const v = document.querySelector('.astrid-video');
      await new Promise(res => { const done = () => { v.removeEventListener('seeked', done); res(); };
        v.addEventListener('seeked', done); v.currentTime = ${at}; setTimeout(res, 6000); });
      await new Promise(r => setTimeout(r, 300));
      return { t: v.currentTime, i: [...document.querySelectorAll('.story-row')]
        .findIndex(x => x.classList.contains('active')) }; })()`);
    check(`t=${at.toFixed(1)}s activates row 0${i + 1}`, got.i === i,
      `landed ${got.t.toFixed(2)}s, row 0${got.i + 1}`);
  }
  check('exactly one row is current',
    (await ev(`document.querySelectorAll('.story-row[aria-current="true"]').length`)) === 1);

  // ---- row click ----------------------------------------------------------
  const target = marks[marks.length - 1];
  const seeked = await ev(`(async () => { const v = document.querySelector('.astrid-video');
    await new Promise(res => { const done = () => { v.removeEventListener('seeked', done); res(); };
      v.addEventListener('seeked', done);
      document.querySelectorAll('.story-row')[${marks.length - 1}].click();
      setTimeout(res, 6000); });
    return v.currentTime; })()`);
  console.log('\nROW INTERACTION');
  check(`clicking row 0${marks.length} seeks to ${target}s`, Math.abs(seeked - target) < 1.5,
    `t=${seeked.toFixed(2)}s`);

  // ---- sound and pause ----------------------------------------------------
  console.log('\nSOUND AND PAUSE');
  await ev(`document.querySelector('.sound-button').click()`);
  const muted = await ev(`(() => ({ muted: document.querySelector('.astrid-video').muted,
    label: document.querySelector('.sound-button').textContent }))()`);
  check('sound control changes the real media state', muted.muted === true);
  check('sound label follows state', muted.label === 'SOUND OFF');
  await ev(`document.querySelector('.transport-button').click()`);
  await sleep(500);
  const paused = await ev(`(() => { const v = document.querySelector('.astrid-video');
    return { paused: v.paused, muted: v.muted,
      transport: document.querySelector('.transport-text').textContent }; })()`);
  check('pause stops playback', paused.paused === true);
  check('pause preserves the sound choice', paused.muted === true);
  check('transport returns to PLAY', paused.transport === 'PLAY');

  // ---- ended --------------------------------------------------------------
  console.log('\nENDED');
  const ended = await ev(`(async () => { const v = document.querySelector('.astrid-video');
    v.muted = false; v.currentTime = v.duration - 0.3; await v.play();
    await new Promise(r => setTimeout(r, 1800));
    return { ended: v.ended, label: document.querySelector('.transport-text').textContent }; })()`);
  check('reaches the real end of the media', ended.ended === true);
  check('offers a replay', ended.label === 'REPLAY', ended.label);
  const replay = await ev(`(async () => { const v = document.querySelector('.astrid-video');
    document.querySelector('.transport-button').click();
    await new Promise(r => setTimeout(r, 900));
    return { t: v.currentTime, paused: v.paused }; })()`);
  check('replay restarts from zero', replay.t < 3 && replay.paused === false,
    `t=${replay.t.toFixed(2)}s`);

  // ---- the written briefing stands alone ----------------------------------
  console.log('\nWRITTEN BRIEFING');
  const written = await ev(`(() => ({
    headlines: [...document.querySelectorAll('.story-headline')].every(h => h.textContent.trim().length > 10),
    consequences: [...document.querySelectorAll('.story-detail')].every(d => d.textContent.trim().length > 10),
    footer: !!document.querySelector('.evidence-footer'),
    transcript: document.querySelectorAll('.transcript p').length,
    sources: document.querySelectorAll('.sources li').length,
    sourceLinks: [...document.querySelectorAll('.sources a')].every(a => a.href.startsWith('https://')),
    dpp: /\\bDPP\\b/.test(document.querySelector('.briefing').textContent) }))()`);
  check('every headline is readable without the video', written.headlines === true);
  check('every consequence is readable', written.consequences === true);
  check('evidence footer present', written.footer === true);
  check('transcript is rendered', written.transcript > 0, `${written.transcript} paragraphs`);
  check('sources are rendered', written.sources > 0, `${written.sources}`);
  check('every source is a direct https link', written.sourceLinks === true);
  check('no standalone DPP in the frame copy', written.dpp === false);

  console.log(`\n${pass} passed, ${failures.length} failed`);
  if (failures.length) failures.forEach(f => console.log(`  - ${f}`));
  ws.close(); chrome.kill();
  process.exit(failures.length ? 1 : 0);
})();
