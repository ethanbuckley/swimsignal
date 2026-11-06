// The app's pages in a real browser, with a small fixed forecast (tests/fixtures/smoke/data): any uncaught script
// error fails. The Node tests load each script on its own and never ran a page as a browser does, so on 5 Nov 2026
// the organisers' page drew nothing for any spot with overflows (levels.js's WEIGHT_SAID missing from its browser
// list of names) while every test passed. This would have failed then.
//
//   node tests/browser_smoke.mjs            (Chrome from CHROME_PATH, or the usual install paths)
//
// The pages are the source ones in src/dipcast/site, not a build: they run as they are. The clock is fixed two hours
// after the fixture's forecast, so its five days are current whatever day this runs. Nothing leaves the machine:
// every request to another host is refused, so a map tile or the analytics beacon is a refused request, not a failure.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SITE = path.join(ROOT, 'src/dipcast/site'), DATA = path.join(ROOT, 'tests/fixtures/smoke/data');
const lite = JSON.parse(fs.readFileSync(path.join(DATA, 'spots-lite.json'), 'utf8'));
const NOW = Date.parse(lite.generated_at) + 2 * 3600e3, DAY = new Date(NOW).toISOString().slice(0, 10);
const IDS = lite.spots.map(s => s.id);

// The pages, with what each must show once drawn (a selector), so a page that drew nothing fails too.
const PAGES = [
  ['index.html', '#spots li, #spots .area'],
  ...IDS.map(id => [`index.html?spot=${id}`, '#result h1']),
  [`organisers.html#spot=${IDS[0]}&date=${DAY}`, '#event h2, #event h3'],
  [`embed.html?spot=${IDS[0]}`, 'h1.name'],
  [`record.html#spot=${IDS[0]}&day=${DAY}`, '#record h2, #record table, #record p'],
  // Plan a swim from a town, given by its place, so no place list is needed.
  [`plan/#day=${DAY}&from=Reading&at=51.45%2C-0.97&within=50`, '#dp, #plan-sum b'],
  ['saved/', '.view-saved .empty-saved', 'empty'],
  ['saved/', '#scards .places li', 'saved'],
  // A town typed in the search: the spots near it, under the spots named for it (fixture places.json; no rivers file).
  ['index.html', '#q', 'search'],
];

const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp', '.woff2': 'font/woff2', '.webmanifest': 'application/manifest+json' };
const server = http.createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/^\/+/, '') || 'index.html';
  // The app's own views, which a build writes as copies of the page with a <base> at the site's root: here the view is
  // the page itself, and what it asks for below the view's folder is the site's.
  if (/^(plan|saved)\/?$/.test(p)) p = 'index.html'; else p = p.replace(/^(plan|saved)\//, '');
  const file = p.startsWith('data/') ? path.join(DATA, p.slice(5)) : path.join(SITE, p);
  if (!file.startsWith(SITE) && !file.startsWith(DATA)) { res.writeHead(403).end(); return; }
  fs.readFile(file, (err, body) => {
    if (err) { res.writeHead(404).end(); return; }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' }).end(body);
  });
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${server.address().port}/`;

const CHROMES = [process.env.CHROME_PATH, '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'].filter(Boolean);
const exe = CHROMES.find(p => fs.existsSync(p));
if (!exe) { console.error('No Chrome found: set CHROME_PATH.'); process.exit(2); }
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'smoke-'));
const chrome = spawn(exe, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check',
  '--disable-gpu', '--no-sandbox'], { stdio: ['ignore', 'ignore', 'pipe'] });
const wsUrl = await new Promise((ok, no) => { let buf = '';
  chrome.stderr.on('data', d => { buf += d; const m = buf.match(/DevTools listening on (ws:\/\/\S+)/); if (m) ok(m[1]); });
  setTimeout(() => no(new Error('Chrome did not start')), 20000); });
const browser = new WebSocket(wsUrl);
await new Promise(r => browser.onopen = r);
let id = 0; const pending = new Map(), handlers = new Set();
browser.onmessage = ev => { const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } else handlers.forEach(f => f(m)); };
const send = (method, params = {}, sessionId) => new Promise(r => { const i = ++id; pending.set(i, r);
  browser.send(JSON.stringify({ id: i, method, params, ...(sessionId ? { sessionId } : {}) })); });
const sleep = ms => new Promise(r => setTimeout(r, ms));

const failures = [];
for (const [w, h, mobile] of [[375, 812, true], [1440, 900, false]]) {
  for (const [page, drawn, saved] of PAGES) {
    const { result: { targetId } } = await send('Target.createTarget', { url: 'about:blank' });
    const { result: { sessionId: s } } = await send('Target.attachToTarget', { targetId, flatten: true });
    const errors = [];
    const on = m => {
      if (m.sessionId !== s) return;
      if (m.method === 'Runtime.exceptionThrown') { const d = m.params.exceptionDetails;
        errors.push(((d.exception && d.exception.description) || d.text || '').split('\n').slice(0, 3).join(' | ')); }
      if (m.method === 'Fetch.requestPaused') { const u = new URL(m.params.request.url);
        send(u.origin + '/' === BASE ? 'Fetch.continueRequest' : 'Fetch.failRequest',
          u.origin + '/' === BASE ? { requestId: m.params.requestId } : { requestId: m.params.requestId, errorReason: 'BlockedByClient' }, s); }
    };
    handlers.add(on);
    await send('Runtime.enable', {}, s); await send('Page.enable', {}, s);
    await send('Fetch.enable', { patterns: [{ urlPattern: '*' }] }, s);
    await send('Network.enable', {}, s); await send('Network.setBypassServiceWorker', { bypass: true }, s);
    await send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile }, s);
    await send('Page.addScriptToEvaluateOnNewDocument', { source: `(() => { const T = ${NOW}, D = Date;
      class F extends D { constructor(...a) { super(...(a.length ? a : [T + (performance.now() | 0)])); } static now() { return T + (performance.now() | 0); } }
      globalThis.Date = F; })();` }, s);
    // The Saved route needs a fresh browser state, then two saved spots for the comparison to exist.
    if (saved) await send('Page.addScriptToEvaluateOnNewDocument', { source: `localStorage.clear(); ${saved === 'saved' ? `localStorage.setItem('dipcast.saved', ${JSON.stringify(JSON.stringify(IDS.slice(0, 2)))});` : ''}` }, s);
    await send('Page.navigate', { url: BASE + page }, s);
    let shown = false;
    for (let t = 0; t < 40 && !shown; t++) { await sleep(250);
      const r = await send('Runtime.evaluate', { expression: `!!document.querySelector(${JSON.stringify(drawn)})`, returnByValue: true }, s);
      shown = !!(r.result && r.result.result && r.result.result.value); }
    // A spot: open each day and close it again, as a reader would, and every fold.
    if (shown && page.includes('?spot=')) {
      await send('Runtime.evaluate', { awaitPromise: true, expression: `(async () => {
        for (const b of [...document.querySelectorAll('button.drow')]) { b.click(); await new Promise(r => setTimeout(r, 120)); }
        const c = document.getElementById('day-close'); if (c) c.click();
        for (const d of document.querySelectorAll('main details')) { d.open = true; d.dispatchEvent(new Event('toggle')); }
        await new Promise(r => setTimeout(r, 600)); })()` }, s);
    }
    if (shown && saved === 'saved') {
      const r = await send('Runtime.evaluate', { expression: `(() => { const d = document.querySelector('#compare'); if (!d) return false; d.open = true; d.dispatchEvent(new Event('toggle')); return !!document.querySelector('#compare-result table'); })()`, returnByValue: true }, s);
      if (!r.result?.result?.value) errors.push('Saved comparison did not draw a table');
    }
    // "Marlow" names no spot; Henley-on-Thames is 5.6 miles away, so it is listed under "Near Marlow" with its own level.
    if (shown && saved === 'search') {
      const r = await send('Runtime.evaluate', { awaitPromise: true, returnByValue: true, expression: `(async () => {
        const q = document.getElementById('q'); q.value = 'Marlow'; q.dispatchEvent(new Event('input', { bubbles: true }));
        for (let t = 0; t < 20 && !document.querySelector('#on-map a[data-id]'); t++) await new Promise(r => setTimeout(r, 150));
        const a = document.querySelector('#on-map a[data-id="thames-henley"]'), h = document.querySelector('#on-map .area-head h3');
        return !!a && /5\\.6 miles from Marlow/.test(a.textContent) && !!a.querySelector('.hl') && !!h && /^Near Marlow/.test(h.textContent); })()` }, s);
      if (!r.result?.result?.value) errors.push('Searching a town did not list the spot near it');
    }
    await sleep(400);
    handlers.delete(on);
    await send('Target.closeTarget', { targetId });
    const where = `${page}${saved ? ` (${saved})` : ''} at ${w} px`;
    if (!shown) failures.push(`${where}: never drew ${drawn}`);
    for (const e of errors) failures.push(`${where}: ${e}`);
    console.log(`${!shown || errors.length ? 'FAIL' : 'ok  '} ${where}`);
  }
}
browser.close(); server.close();
await new Promise(r => { chrome.once('exit', r); chrome.kill(); });
try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* the OS clears its temp folder */ }
if (failures.length) { console.error('\n' + failures.join('\n')); process.exit(1); }
console.log(`\n${PAGES.length * 2} page loads, no script error.`);
