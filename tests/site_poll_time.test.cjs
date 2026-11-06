// The live readings say when they were polled (6 Nov 2026). GitHub ran the scheduled build a median 4.6 h apart
// from 7 Oct to 6 Nov 2026, so "0 of 6 discharging" under "Right now", and "none spilling at the last poll", were
// often hours old with no time beside them. The Right now tile now gives the poll's time and age and says a spill
// since is not shown; the line under the five days, which is in the built page, gives the clock time only; the
// list gives the issue's age. Nothing here changes a level, a count or which overflows count as reporting.
// node --test tests/site_poll_time.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const spots = require('../scripts/prerender_spots.js');
const L = require('../src/dipcast/site/levels.js');

const PAGE = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
// The live site on 6 Nov 2026: issued 15:38, feeds read 15:34 (written as build_site.live_feed_health writes it),
// read at 19:20, 3 h 46 min after the poll. November, so London's clock is UTC's.
const GEN = '2026-11-06T15:38:11.038578+00:00', POLLED = '2026-11-06 15:34:35.903037+00:00';
const NOW = Date.parse('2026-11-06T19:20:35Z');
const DAYS = ['2026-11-06', '2026-11-07', '2026-11-08', '2026-11-09', '2026-11-10'];
const spot = (total, mon, now = {}) => ({id: 'a', name: 'A river', kind: 'river', source: 'curated',
  upstream_summary: {overflows: total}, location: {mode: 'river'}, contributors: [], assumptions: {max_upstream_km: 60, recent_spill_hours: 48},
  now: {label: 'low', risk: 0, discharging_upstream: 0, recent_upstream: 0, monitored_upstream: mon, monitored_weight: mon / total, upstream_weight: 1, ...now},
  days: DAYS.map(date => ({date, label: 'low', risk: 0.03, rain_48h_mm: 1}))});
const FULL = spot(6, 6), MOST = spot(16, 13), ONE = spot(1, 1), SPILLING = spot(6, 6, {discharging_upstream: 2, label: 'high', risk: 0.5});
const NONE = spot(14, 0, {no_feed_upstream: 14});
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();

function page(build = {live_feeds: {polled_at: POLLED}}) {
  const store = {getItem: () => null, setItem() {}, removeItem() {}}, root = 'https://example.org/swim/';
  const ctx = vm.createContext({console, URL, URLSearchParams, Intl, history: {state: null}, location: new URL(root),
    navigator: {onLine: true}, localStorage: store, sessionStorage: store, addEventListener() {}, setTimeout, clearTimeout,
    ROOT: new URL(root), map: null, TOUCH: false, STILL: false});
  ctx.window = ctx;
  vm.runInContext(`Date.now = () => ${NOW};`, ctx);
  for (const f of ['eatoday.js', 'experience.js', 'levels.js', 'lists.js'])
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site', f), 'utf8'), ctx);
  vm.runInContext(spots.reached(PAGE, ['liveRow', 'nowTile', 'tile', 'overviewTop', 'polledMs'], ['ROOT', 'map', 'TOUCH', 'STILL']), ctx);
  ctx.BUILD = build;
  vm.runInContext(`setToday("${DAYS[0]}"); DATA = {generated_at: "${GEN}", build: BUILD, spots: []};`, ctx);
  return ctx;
}

test("the poll time is read from the build's own form, which Safari's Date.parse refuses as written", () => {
  const ctx = page();
  assert.equal(vm.runInContext('polledMs()', ctx), Date.parse('2026-11-06T15:34:35.903Z'));
  assert.equal(vm.runInContext('pollAt()', ctx), 'Fri 15:34');
  assert.equal(vm.runInContext('pollAt()', page({live_feeds: {polled_at: '2026-11-06 15:34:35+00:00'}})), 'Fri 15:34');
  for (const b of [{}, {live_feeds: {}}, {live_feeds: {polled_at: 'not a time'}}, null]) {
    const c = page(b);
    assert.ok(Number.isNaN(vm.runInContext('polledMs()', c)), JSON.stringify(b));
    assert.equal(vm.runInContext('pollAt()', c), '', 'no time is made up');
    assert.equal(vm.runInContext('pollSay()', c), '');
  }
});

test('the line under the five days gives the clock time of the poll, never an age (it is in the built page)', () => {
  L.setToday(DAYS[0]);
  assert.equal(L.liveLine(FULL), 'Live status from all 6 overflows upstream: none spilling at the last poll', 'no time given: as before');
  assert.equal(L.liveLine(FULL, 'Fri 15:34'), 'Live status from all 6 overflows upstream: none spilling at the last poll (Fri 15:34)');
  assert.equal(L.liveLine(ONE, 'Fri 15:34'), 'Live status from the overflow upstream: not spilling at the last poll (Fri 15:34)');
  assert.equal(L.liveLine(SPILLING, 'Fri 15:34'), 'Live status from all 6 overflows upstream: 2 spilling at the last poll (Fri 15:34)');
  assert.equal(L.liveLine(MOST, 'Fri 15:34'),
    'Live status from 13 of 16 overflows upstream: none spilling at the last poll (Fri 15:34); 3 do not report, so could be spilling unseen');
  assert.equal(L.liveLine(NONE, 'Fri 15:34'), 'Live sewage spill status unavailable: none of the 14 overflows upstream reports live', 'no readings, so no poll to date');

  const row = s => vm.runInContext('liveRow', page())(s);
  assert.equal(row(FULL), '<p class="live-row">Live status from all 6 overflows upstream: none spilling at the last poll (Fri 15:34).</p>');
  assert.doesNotMatch(row(FULL), /ago|data-ago/);
  assert.equal(vm.runInContext('liveRow', page({}))(FULL), '<p class="live-row">Live status from all 6 overflows upstream: none spilling at the last poll.</p>');
  assert.equal(row(NONE), '', 'unavailable stays over the level, as before');
});

test('the Right now tile gives the poll time and age, and that a spill since is not shown; the count is unchanged', () => {
  const ctx = page(), tile = (s, n) => vm.runInContext('nowTile', ctx)(s, n);
  const t = tile(FULL, 6);
  assert.equal(t.fig, 0);
  assert.equal(t.unit, 'of 6 discharging');
  assert.match(t.say, /6 of 6 report live\.$/);
  assert.match(t.note, /^Last poll Fri 15:34, <span data-ago="\d+">3 h 46 min<\/span> ago: a spill that started after it is not shown\.$/);
  assert.equal(text(tile(SPILLING, 6).note), 'Last poll Fri 15:34, 3 h 46 min ago: a spill that started after it is not shown.');
  // The span moves on with the page's minute check (stillCurrent), from the poll, not the issue.
  assert.equal(Number(t.note.match(/data-ago="(\d+)"/)[1]), Date.parse('2026-11-06T15:34:35.903Z'));
  // Drawn as the tile's quiet line.
  assert.match(vm.runInContext('tile', ctx)(t), /<p class="t-note">Last poll Fri 15:34, /);
  // None reporting: Unknown, with no poll to date.
  const u = tile(NONE, 14);
  assert.equal(u.fig, 'Unknown');
  assert.doesNotMatch(u.say + (u.note || ''), /Last poll/);
  // A forecast with no poll time: the tile as before.
  assert.equal(vm.runInContext('nowTile', page({}))(FULL, 6).note, '');
});

test("the list's first line gives the forecast's age, which moves on in place", () => {
  const top = vm.runInContext('overviewTop', page())([]);
  assert.match(top, /^Updated Fri 15:38 \(<span data-ago="\d+">3 h 42 min<\/span> ago\)\.$/);
});

test("the built page's line has the poll's clock time and no age (scripts/prerender_spots.js, the smoke fixture)", () => {
  const data = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/smoke/data/spots.json'), 'utf8'));
  assert.equal(data.build.live_feeds.polled_at, '2026-11-05 20:46:09.722573+00:00');
  const out = spots.prerender(data, 'https://example.org/swim/');
  assert.match(out['bw-uke2204-08905'], /<p class="live-row">Live status from all 6 overflows upstream: none spilling at the last poll \(Thu 20:46\)\.<\/p>/);
  for (const h of Object.values(out)) assert.doesNotMatch(h, /data-ago/);
});
