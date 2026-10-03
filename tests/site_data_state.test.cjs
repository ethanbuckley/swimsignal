// Each upstream overflow's data state (ingest.live.data_states) in the page's words: a stale or offline
// reading never says "not discharging", and the Right now sentence counts it as not reporting.
// The page's own functions (index.html: statusText, drawnStatus, liveSay) run on small fixtures, and
// click anywhere (anypoint.js) counts as forecast.live_counts does (tests/test_data_state.py).
// On its own: node --test tests/site_data_state.test.cjs
process.env.TZ = 'Europe/London';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const A = require('../src/dipcast/site/anypoint.js');

const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const between = (from, to) => { const a = page.indexOf(from), b = page.indexOf(to, a); assert.ok(a >= 0 && b > a, from); return page.slice(a, b); };
const ctx = vm.createContext({ esc: s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;') });
vm.runInContext(between("// An overflow's live status in words.", '\nconst initial = ')
  + between('// A company feed that did not answer the last poll', '\n// Every overflow upstream as a dot')
  + '\nthis.statusText = statusText; this.drawnStatus = drawnStatus; this.liveSay = liveSay;', ctx);
const { statusText, drawnStatus, liveSay } = ctx;

test('a reading that is not current says when its feed last updated, never "not discharging"', () => {
  const since = '2026-10-02T13:00:00+00:00';
  assert.equal(statusText(0, { data_state: 'live' }), 'not discharging');
  assert.equal(statusText(1, { data_state: 'live' }), 'discharging');
  assert.equal(statusText(0, { data_state: 'stale', feed_updated_at: since }), 'no update since 2 Oct, 14:00');
  assert.equal(statusText(0, { data_state: 'stale', feed_updated_at: null }), 'no update time from the company');
  assert.equal(statusText(1, { data_state: 'stale', feed_updated_at: since }), 'discharging at its last update, 2 Oct, 14:00');
  assert.equal(statusText(-1, { data_state: 'offline' }), 'monitor offline');
  assert.equal(statusText(-3, { data_state: 'offline' }), 'company feed down');
  assert.equal(statusText(-2, { data_state: 'offline' }), 'not in the company’s live feed');
  assert.equal(statusText(-2, { data_state: 'no_feed' }), 'no live feed');
  // Data from before data_state, and the map's call with a status alone, read as they did.
  assert.equal(statusText(0), 'not discharging');
  assert.equal(statusText(-2, {}), 'no live feed');
});

test('a quiet overflow that is not current is drawn in the grey of unknown; a discharge stays a discharge', () => {
  assert.equal(drawnStatus({ status: 0, data_state: 'live' }), 0);
  assert.equal(drawnStatus({ status: 0, data_state: 'stale' }), -1);
  assert.equal(drawnStatus({ status: 1, data_state: 'stale' }), 1);
  assert.equal(drawnStatus({ status: -2, data_state: 'no_feed' }), -2);
  assert.equal(drawnStatus({ status: 0 }), 0);   // data from before data_state
});

test('Right now names a stale feed beside a feed that is down, and counts neither as reporting', () => {
  assert.equal(liveSay({}, 22, 22), '22 of 22 report live.');
  assert.equal(liveSay({}, 22, 20), '20 of 22 report live; the 2 that do not could be spilling unseen.');
  const stale = { stale_upstream: 14, feed_stale: [{ company: 'Northumbrian Water', overflows: 14, since: '2026-10-02T13:00:00+00:00' }] };
  assert.equal(liveSay(stale, 20, 5), '5 of 20 report live. One more gives no live reading and could be spilling unseen.'
    + " Northumbrian Water's live feed has not updated since 2 Oct, 14:00: its 14 overflows here could be spilling unseen.");
  assert.equal(liveSay({ stale_upstream: 3, feed_stale: [{ company: 'South West Water', overflows: 3, since: null }] }, 3, 0),
    "0 of 3 report live. South West Water's live feed has given no time for its last update: its 3 overflows here could be spilling unseen.");
  const both = { ...stale, feed_down_upstream: 2, feed_down: [{ company: 'Yorkshire Water', overflows: 2, since: null }] };
  assert.equal(liveSay(both, 20, 4), '4 of 20 report live.'
    + " Yorkshire Water's live feed is down: its 2 overflows here could be spilling unseen."
    + " Northumbrian Water's live feed has not updated since 2 Oct, 14:00: its 14 overflows here could be spilling unseen.");
});

const spot = () => JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'anypoint_spot.json'), 'utf8'));

test('click anywhere counts an offline monitor and a stale feed as forecast.live_counts does', () => {
  const fx = spot(), od = fx.od, idx = fx.rows.map(r => r.i);
  const base = A.forecast(fx.rows, od, fx.cal);
  assert.equal(base.now.monitored_upstream, 15);                      // all fifteen quiet and current
  assert.ok(base.contributors.every(c => c.data_state === 'live'));
  const quiet = k => od.live[idx[k]] === 0;                           // nothing finished lately there
  const k0 = [...idx.keys()].find(quiet);
  od.status[idx[k0]] = -1;                                            // one monitor goes offline
  let got = A.forecast(fx.rows, od, fx.cal);
  assert.equal(got.now.monitored_upstream, 14);                       // before 4 Oct: still 15
  assert.equal(got.contributors.find(c => c.status === -1).data_state, 'offline');
  od.feed_stale_since = { 'Yorkshire Water': '2026-10-02T13:00:00+00:00' };   // and the company's feed is stale
  got = A.forecast(fx.rows, od, fx.cal);
  const rec = got.now.recent_upstream;
  assert.equal(got.now.monitored_upstream, rec);                      // only what finished lately still reports
  assert.equal(got.now.stale_upstream, 14 - rec);
  assert.deepEqual(got.now.feed_stale, [{ company: 'Yorkshire Water', overflows: 14 - rec, since: '2026-10-02T13:00:00+00:00' }]);
  const c = got.contributors.find(x => x.status === 0);
  assert.equal(c.data_state, 'stale');
  assert.equal(c.feed_updated_at, '2026-10-02T13:00:00+00:00');
  od.status[idx[k0]] = -2; od.no_feed = ['Yorkshire Water'];
  assert.equal(A.forecast(fx.rows, od, fx.cal).contributors.find(x => x.status === -2).data_state, 'no_feed');
});
