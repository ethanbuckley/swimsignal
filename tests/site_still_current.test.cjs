// A page left open and in view (index.html, stillCurrent; issue #495): a quiet feed passing six hours,
// midnight before the next build and a newer forecast on the server, with the page's own functions
// on a fixed clock.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const between = (a, b) => { const i = html.indexOf(a), j = html.indexOf(b, i); assert.ok(i >= 0 && j > i, a); return html.slice(i, j); };
const BUILT = '2026-10-30T20:00:00+00:00', T0 = Date.parse(BUILT);
const H = 3600e3;

function page({ nowMs, feedAt = BUILT, held = false, drafts = [], head = 'Fri, 30 Oct 2026 20:00:00 GMT' } = {}) {
  const clock = { now: nowMs };
  class FixedDate extends Date { constructor(...a) { super(...(a.length ? a : [clock.now])); } static now() { return clock.now; } }
  const spans = [{ dataset: { ago: String(T0) }, textContent: '0 min', closest: () => null },
    { dataset: { ago: String(T0) }, textContent: 'frozen', closest: sel => sel === '[role=alert]' ? {} : null }];
  const calls = { reload: 0, heads: 0, notices: 0 };
  const ctx = vm.createContext({ Date: FixedDate, navigator: { onLine: true }, setInterval() {}, confirm: () => true,
    fetch: (url, o) => { calls.heads++; assert.equal(o.method, 'HEAD'); return Promise.resolve({ ok: true, headers: { get: k => k === 'last-modified' ? head : null } }); },
    document: { visibilityState: 'visible', activeElement: null, addEventListener() {},
      querySelector: sel => sel === '[data-keep-page]' && held ? {} : null,
      querySelectorAll: sel => sel === '[data-ago]' ? spans : sel === '[data-notices]' ? [{ hasAttribute: () => false, set innerHTML(h) { calls.notices++; calls.last = h; } }] : [] } });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/levels.js'), 'utf8'), ctx);
  vm.runInContext(`
    let DATA = ${JSON.stringify({ generated_at: BUILT, spots: [{ id: 'a', now: { monitored_upstream: 4, quiet_by_feed: [{ company: 'Thames', overflows: 4, updated_at: feedAt }] }, contributors: [] }] })};
    const reload = () => { calls.reload++; };
    const DRAFTS = new Map(${JSON.stringify(drafts)});
    const STALE_MIN = 8 * 60;
    const ageMin = () => (Date.now() - new Date(DATA.generated_at).getTime()) / 60000;
    ${between('const ago = m =>', '\nconst issued')}
    const freshness = () => UPDATE ? UPDATE_SAY[UPDATE] : '';
    ${between('let NOTICE = ', '\nconst notices =')}
    ${between('function refreshNotices()', 'window.addEventListener')}
    ${between('const FEED_CURRENT_MS', '\n// The overflows that stopped lately')}
    ${between('const setDays =', '\nconst fiveDays')}
    ${between('let CHECKED = ', 'setInterval(stillCurrent')}
    NOTICE = noticeState(); setDays(); for (const s of DATA.spots) ageReadings(s, Date.now());`, Object.assign(ctx, { calls }));
  const run = async ms => { clock.now = ms; await vm.runInContext(`stillCurrent(${ms})`, ctx); };
  return { ctx, calls, spans, run, get: e => vm.runInContext(e, ctx) };
}

test('a quiet feed passing six hours while the page is open reloads it, at the threshold and not before', async () => {
  const p = page({ nowMs: T0 + 4 * H });   // a feed 4 h old when the page was opened
  assert.equal(p.get('DATA.spots[0].now.monitored_upstream'), 4);
  await p.run(T0 + 5.9 * H);
  assert.equal(p.calls.reload, 0);
  await p.run(T0 + 6 * H + 60e3);
  assert.equal(p.calls.reload, 1);
  assert.equal(p.get('DATA.spots[0].now.stale_upstream'), 4);
});

test('with words being written, the page offers the reload once and does not reload', async () => {
  const p = page({ nowMs: T0 + 4 * H, held: true });
  await p.run(T0 + 6.5 * H);
  assert.equal(p.calls.reload, 0);
  assert.equal(p.get('UPDATE'), 'aged');
  const drawn = p.calls.notices;
  assert.ok(drawn >= 1);
  await p.run(T0 + 6.6 * H); await p.run(T0 + 6.7 * H);
  assert.equal(p.calls.notices, drawn);   // a status, not redrawn (so not read out) every minute
});

test('a draft kept from a form that was left counts as being written; an empty one does not', async () => {
  const kept = page({ nowMs: T0 + 4 * H, drafts: [['a:rv-form', { photos: false, fields: [{ value: 'Lovely swim', checked: false }] }]] });
  await kept.run(T0 + 6.5 * H);
  assert.equal(kept.calls.reload, 0);
  const blank = page({ nowMs: T0 + 4 * H, drafts: [['a:rv-form', { photos: false, fields: [{ value: '', checked: false }] }]] });
  await blank.run(T0 + 6.5 * H);
  assert.equal(blank.calls.reload, 1);
});

test('midnight before the next build reloads the page, so Today moves on', async () => {
  // Built 20:00 UTC; feed fresh throughout (updated an hour ago at each check), so only the day changes.
  const p = page({ nowMs: Date.parse('2026-10-30T23:50:00+00:00'), feedAt: '2026-10-30T23:00:00+00:00' });
  assert.equal(p.get('today()'), '2026-10-30');
  await p.run(Date.parse('2026-10-30T23:59:00+00:00'));
  assert.equal(p.calls.reload, 0);
  await p.run(Date.parse('2026-10-31T00:01:00+00:00'));
  assert.equal(p.calls.reload, 1);
});

test('a newer forecast on the server is offered, not loaded, and asked for once in 10 minutes', async () => {
  const p = page({ nowMs: T0 + H, feedAt: new Date(T0 + H).toISOString(), head: 'Fri, 30 Oct 2026 23:00:00 GMT' });
  p.get("FORECAST_STAMP = 'Fri, 30 Oct 2026 20:00:00 GMT'; CHECKED = " + (T0 + H));
  await p.run(T0 + H + 5 * 60e3);
  assert.equal(p.calls.heads, 0);
  await p.run(T0 + H + 10 * 60e3);
  assert.equal(p.calls.heads, 1);
  assert.equal(p.calls.reload, 0);
  assert.equal(p.get('UPDATE'), 'newer');
  assert.match(p.calls.last, /A newer forecast is out\./);
  await p.run(T0 + H + 25 * 60e3);
  assert.equal(p.calls.heads, 1);   // offered already: no more asking
});

test('the same forecast on the server changes nothing', async () => {
  const p = page({ nowMs: T0 + H, feedAt: new Date(T0 + H).toISOString() });
  p.get("FORECAST_STAMP = 'Fri, 30 Oct 2026 20:00:00 GMT'; CHECKED = 0");
  await p.run(T0 + H + 60e3);
  assert.equal(p.calls.heads, 1);
  assert.equal(p.get('UPDATE'), '');
  assert.equal(p.calls.reload, 0);
});

test('each "... ago" moves on in place, except inside the Stale alert', async () => {
  const p = page({ nowMs: T0 + H, feedAt: new Date(T0 + 3 * H).toISOString() });
  p.get('CHECKED = Infinity');
  await p.run(T0 + 3 * H);
  assert.equal(p.spans[0].textContent, '3 h');
  assert.equal(p.spans[1].textContent, 'frozen');
});

test('the page wires the check to the minute and to coming back into view', () => {
  assert.match(html, /setInterval\(stillCurrent, 60 \* 1000\);/);
  assert.doesNotMatch(html, /setInterval\(refreshNotices/);
  assert.match(html, /if \(Date\.now\(\) - LOADED > 30 \* 60 \* 1000 && !held\(\)\) reload\(\); else stillCurrent\(\);/);
  assert.match(html, /DATA = await res\.json\(\); FORECAST_STAMP = stamp\(res\);/);
});
