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
const { overflowNames } = require('../src/dipcast/site/levels.js');

const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const between = (from, to) => { const a = page.indexOf(from), b = page.indexOf(to, a); assert.ok(a >= 0 && b > a, from); return page.slice(a, b); };
const ctx = vm.createContext({ esc: s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;') });
vm.runInContext(between("// An overflow's live status in words.", '\nconst initial = ')
  + between('// A company feed that did not answer the last poll', '\n// Every overflow upstream as a dot')
  + '\nthis.statusText = statusText; this.drawnStatus = drawnStatus; this.liveSay = liveSay; this.ageReadings = ageReadings;', ctx);
const { statusText, drawnStatus, liveSay, ageReadings } = ctx;

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

test("a picked day's overflows are drawn and named as the overflows tile draws them", () => {
  const day = vm.createContext({ esc: ctx.esc, statusText, drawnStatus, overflowNames, nil: v => v === null || v === undefined });
  vm.runInContext(between('const ownName = ', '\n') + '\n' + between('const share = p =>', '\n// How good a forecast this far ahead')
    + '\nthis.dayOverflows = dayOverflows;', day);
  const since = '2026-10-02T13:00:00+00:00';
  const c = (id, status, state, extra = {}) => ({ site_id: id, site_name: id, status, data_state: state, weight: 0.5, p_spill_days: [0.4], ...extra });
  const h = day.dayOverflows({ contributors: [c('Quiet', 0, 'live'), c('Frozen', 0, 'stale', { feed_updated_at: since }), c('Running', 1, 'stale', { feed_updated_at: since })] }, 0);
  const rows = h.split('<li>').slice(1);
  assert.match(rows[0], /class="sdot s0".*<span class="sr">not discharging: <\/span><b>Quiet<\/b>/);
  assert.match(rows[1], /class="sdot s-1".*<span class="sr">no update since 2 Oct, 14:00: <\/span><b>Frozen<\/b>/);   // grey, not quiet
  assert.match(rows[2], /class="sdot s1".*discharging at its last update/);
  // The plain name first, the company's beside it, smaller and muted (levels.js, overflowNames).
  const named = day.dayOverflows({ contributors: [c('YW1', 0, 'live', { site_name: 'KIRKOSWALD WwTW' })] }, 0);
  assert.match(named, /<b>Kirkoswald sewage works overflow<\/b> <span class="own-name">\(Kirkoswald WwTW\)<\/span>: spill chance 40%/);
});

test('the map keys name the grey as no current reading: offline, no feed or a feed not updating', () => {
  assert.equal((page.match(/>no current reading</g) || []).length, 2);
  assert.ok(!page.includes('offline or no feed') && !page.includes('</span>offline</div>'));
});

// 11 Oct 2026 (feed freshness): a spill running when its company's feed failed, a record that stopped
// updating in a feed that has not, and a reading that has aged past six hours where the page is read.
test('a spill running when its feed last answered says so and is drawn as discharging', () => {
  const since = '2026-10-11T07:00:00+00:00';
  assert.equal(statusText(-3, { data_state: 'offline', last_status: 1, feed_down_since: since }), 'discharging when the feed last answered, 11 Oct, 08:00');
  assert.equal(statusText(-3, { data_state: 'offline', last_status: 1 }), 'discharging when the feed last answered');
  assert.equal(statusText(-3, { data_state: 'offline', last_status: 0, feed_down_since: since }), 'company feed down');
  assert.equal(statusText(-3, { data_state: 'offline' }), 'company feed down');   // carried before last_status
  assert.equal(drawnStatus({ status: -3, data_state: 'offline', last_status: 1 }), 1);
  assert.equal(drawnStatus({ status: -3, data_state: 'offline', last_status: 0 }), -3);
});

test('records that stopped updating are named apart from a stale feed', () => {
  const now = { stale_upstream: 2, feed_stale: [{ company: 'Wessex Water', overflows: 2, since: '2026-03-31T14:23:00+00:00', records: true }] };
  assert.equal(liveSay(now, 38, 35), '35 of 38 report live. One more gives no live reading and could be spilling unseen.'
    + ' Wessex Water has not updated 2 of its overflows here since 31 Mar, 15:23: they could be spilling unseen.');
  const one = { stale_upstream: 1, feed_stale: [{ company: 'Anglian Water', overflows: 1, since: null, records: true }] };
  assert.equal(liveSay(one, 16, 15), '15 of 16 report live. Anglian Water gives no update time for one of its overflows here: it could be spilling unseen.');
});

test('a quiet reading over six hours old where the page is read stops counting as reporting', () => {
  const built = Date.parse('2026-10-11T18:00:00Z');
  const spot = () => ({ now: { monitored_upstream: 20, stale_upstream: 0, feed_stale: [], discharging_upstream: 1, recent_upstream: 0,
    quiet_by_feed: [{ company: 'Southern Water', overflows: 12, updated_at: '2026-10-11T13:30:00+00:00' },
                    { company: 'Thames Water', overflows: 7, updated_at: '2026-10-11T17:50:00+00:00' }] },
    contributors: [{ company: 'Southern Water', status: 0, data_state: 'live' }, { company: 'Southern Water', status: 1, data_state: 'live' },
                   { company: 'Thames Water', status: 0, data_state: 'live' }] });
  const fresh = ageReadings(spot(), built);                      // read as built: nothing changes
  assert.equal(fresh.now.monitored_upstream, 20); assert.equal(fresh.now.stale_upstream, 0);
  const s = ageReadings(spot(), built + 2 * 3600e3);              // read at 20:00: Southern's 13:30 is 6.5 h old
  assert.equal(s.now.monitored_upstream, 8); assert.equal(s.now.stale_upstream, 12);
  assert.deepEqual(JSON.parse(JSON.stringify(s.now.feed_stale)), [{ company: 'Southern Water', overflows: 12, since: '2026-10-11T13:30:00+00:00' }]);   // across the vm's realm
  assert.deepEqual(s.contributors.map(c => c.data_state), ['stale', 'live', 'live']);   // a discharge stays a discharge
  assert.equal(statusText(0, { ...s.contributors[0], feed_updated_at: '2026-10-11T13:30:00+00:00' }), 'no update since 11 Oct, 14:30');
  ageReadings(s, built + 3 * 3600e3);                             // a second pass (the overflows' file arriving) adds nothing
  assert.equal(s.now.monitored_upstream, 8); assert.equal(s.now.stale_upstream, 12);
  const old = { now: { monitored_upstream: 5 } };                 // a forecast from before quiet_by_feed
  assert.equal(ageReadings(old, built + 9 * 3600e3).now.monitored_upstream, 5);
});

test('click anywhere counts a carried spill and a frozen record as forecast.live_counts does', () => {
  const fx = spot(), od = fx.od, idx = fx.rows.map(r => r.i);
  const quiet = k => od.live[idx[k]] === 0;
  const [k0, k1] = [...idx.keys()].filter(quiet);
  od.status[idx[k0]] = -3; od.feed_down_since = { 'Yorkshire Water': '2026-10-11T07:00:00+00:00' };
  let got = A.forecast(fx.rows, od, fx.cal);
  assert.equal(got.now.discharging_upstream, 0); assert.equal(got.now.feed_down_upstream, 1);
  const before = got.now.risk;
  od.last_running = [idx[k0]];                                    // it was discharging when the feed last answered
  got = A.forecast(fx.rows, od, fx.cal);
  assert.equal(got.now.discharging_upstream, 1); assert.equal(got.now.feed_down_upstream, 0);
  assert.equal(got.now.monitored_upstream, 15);
  assert.ok(got.now.risk > before);
  const c = got.contributors.find(x => x.status === -3);
  if (c) { assert.equal(c.last_status, 1); assert.equal(c.feed_down_since, '2026-10-11T07:00:00+00:00'); }
  od.stale_rows = { [String(idx[k1])]: '2026-03-31T14:23:00+00:00' };   // one record stopped updating
  got = A.forecast(fx.rows, od, fx.cal);
  assert.equal(got.now.monitored_upstream, 14); assert.equal(got.now.stale_upstream, 1);
  assert.deepEqual(got.now.feed_stale, [{ company: 'Yorkshire Water', overflows: 1, since: '2026-03-31T14:23:00+00:00', records: true }]);
});
