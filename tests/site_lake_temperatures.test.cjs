// Measured lake temperatures (src/dipcast/site/lake-temperatures.js, the viewer on lake-temperatures.html, and the one
// link on a lake spot's page in index.html): what the Environment Agency's readings say, and only that
// (docs/LAKE-TEMPERATURE-OBS-CONTRACT-v1.md, "What it may and may not say"). Four lakes cut from the research export
// (tests/fixtures/lake_temperature_obs_v1_sample.json): Windermere (N Basin), 722 readings, linked to two spots; Brothers
// Water, with months of 3 readings; Crummock Water, 3 readings, all in July; Haweswater Reservoir, with no linked spot.
// node --test tests/site_lake_temperatures.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const T = require('../src/dipcast/site/lake-temperatures.js');

const DOC = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'lake_temperature_obs_v1_sample.json'), 'utf8'));
const lake = id => DOC.lakes.find(x => x.wb_id === id);
const WIN = lake('GB31247007'), BRO = lake('GB30229116'), CRU = lake('GB31229000'), HAW = lake('GB30229073');
const plain = h => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();
const rows = html => [...html.matchAll(/<tr><th scope="row">([^<]+)<\/th>(.*?)<\/tr>/g)].map(m => [m[1], plain(m[2])]);

test('by month: May to September only, each figure on the row of its count', () => {
  assert.deepEqual(T.ltMonthly(WIN).map(m => m.month), [5, 6, 7, 8, 9]);
  // A month outside the season, were one ever exported, is not shown.
  assert.deepEqual(T.ltMonthly({ monthly: [...WIN.monthly, { month: 10, n: 9, median: 11 }] }).map(m => m.month), [5, 6, 7, 8, 9]);
  const r = rows(T.ltTable(WIN));
  assert.deepEqual(r.map(x => x[0]), ['May', 'June', 'July', 'August', 'September']);
  assert.deepEqual(r[2], ['July', '155 18.6 °C 17.1 to 19.9 °C']);   // the contract's example: July median 18.6 °C from 155 readings
  assert.doesNotMatch(T.ltTable(WIN), /October|April|winter/i);
  // Every row with a temperature has a count of one or more beside it.
  for (const L of DOC.lakes) for (const [, cells] of rows(T.ltTable(L))) {
    if (/°C/.test(cells)) assert.match(cells, /^[1-9][\d,]* /, cells);
  }
});

test('a month with few readings shows its count and says it is few; an empty month says no readings', () => {
  const r = rows(T.ltTable(CRU));
  assert.deepEqual(r.map(x => x[1]), ['0 none none', '0 none none', '3 (few) 16.5 °C too few', '0 none none', '0 none none']);
  assert.match(plain(T.ltTable(CRU)), /Few readings: July has 3\. A median from fewer than 10 visits says little about a typical July\./);
  assert.match(plain(T.ltTable(BRO)), /Few readings: May has 3, June has 3, July has 7, August has 5 and September has 4\./);
  assert.doesNotMatch(T.ltTable(WIN), /\(few\)|Few readings/);
});

test('the years covered come first, in bold, and each year with readings is listed with its count', () => {
  assert.equal(plain(T.ltWhen(BRO)), 'Measured on visits from 11 Jul 2000 to 21 Sept 2026 in 7 different years: 22 readings, May to September only.');
  assert.match(T.ltWhen(BRO), /^<p class="lt-when"><b>/);
  assert.equal(plain(T.ltYears(CRU)), "Readings each year: 2000 (1), 2010 (1), 2021 (1).");   // three Julys, years apart
  assert.match(plain(T.ltYears(BRO)), /^Readings each year: 2000 \(1\), 2007 \(1\), 2009 \(5\), 2010 \(1\), 2019 \(5\), 2021 \(1\), 2026 \(8\)\.$/);
  assert.equal(T.ltSpanYears(WIN), `${WIN.summary.first.slice(0, 4)} to ${WIN.summary.last.slice(0, 4)}`);
  const sum = plain(T.ltSummary({ ...DOC, available: true }));
  assert.match(sum, /^Readings from 2000 to 2026, May to September only\. 11,502 readings in 210 lakes, at 368 sampling points\. 15 of the lakes have a SwimSignal spot on them\./);
  assert.equal(plain(T.ltSummary({ available: false, why: 'no export in this build' })), 'No measured lake temperatures are published in this update (no export in this build).');
});

test('the chart has a dot a reading, on an axis of May to September only, and its median lines carry their counts', () => {
  const svg = T.ltChart(WIN, 600);
  assert.equal((svg.match(/class="lt-dot"/g) || []).length, WIN.readings.date.length);
  assert.deepEqual([...svg.matchAll(/text-anchor="middle">(\w+)</g)].map(m => m[1]), ['May', 'Jun', 'Jul', 'Aug', 'Sep']);
  assert.match(svg, /<title>July: median 18\.6 °C from 155 readings<\/title>/);
  assert.match(plain(svg), /There are no readings from October to April in this record\./);
  assert.equal(T.ltDay('2020-05-01'), 0);
  assert.equal(T.ltDay('2020-09-30'), 152);
  assert.equal(T.ltDay('2020-10-01'), null);   // never placed on the axis
  assert.equal((T.ltChart(CRU, 320).match(/class="lt-med"/g) || []).length, 1);   // only July has a median
});

test('a linked spot says how far it is from the nearest sampling point, and that it is a different place', () => {
  assert.equal(T.ltDistance(0), 'under 10 m');
  assert.equal(T.ltDistance(184), '180 m');
  assert.equal(T.ltDistance(1240), '1.2 km');
  const t = plain(T.ltSpots(WIN));
  assert.match(t, /^The readings were taken at the sampling points below, which are different places from where you get in\./);
  assert.match(t, /Windermere, Millerground Landing is under 10 m from the nearest one; Windermere, Rayrigg Meadow is under 10 m from the nearest one\./);
  assert.match(T.ltSpots(BRO), /href="spot\/brothers-water\/"/);
  assert.match(plain(T.ltSpots(BRO)), /Brothers Water is 180 m from the nearest one\./);
  assert.equal(T.ltSpots(HAW), '');
  assert.equal(T.ltLabel('BROTHERSWATER - LAKES TOUR'), 'Brotherswater - Lakes Tour');
  assert.match(plain(T.ltPoints(BRO)), /^Brotherswater \(NW-88010024\): 17 readings, 2000 to 2026\. On a map Brotherswater - Lakes Tour \(NW-88022545\): 5 readings, 2010 to 2026\./);
});

test('nothing reads as now, at the swim entry, a forecast or safe; the approved sentence stands beside the figures', () => {
  for (const L of DOC.lakes) {
    const html = T.ltLake(L, DOC, 600), t = plain(html);
    assert.ok(t.includes(DOC.claim.public_wording), L.name);
    assert.ok(t.indexOf(DOC.claim.public_wording) < t.indexOf('By month'), 'beside the figures, before them');
    const own = t.replace(DOC.claim.public_wording, '');
    assert.doesNotMatch(own, /\btoday\b|\bnow\b|current|latest|forecast|\bsafe|warm enough|too cold|\bswim(mable)?\b at/i, L.name);
  }
});

test('the picker lists linked lakes first, each with its count of readings', () => {
  const html = T.ltPicker({ lakes: DOC.lakes }, 'GB30229116');
  assert.ok(html.indexOf('Lakes with a SwimSignal spot') < html.indexOf('Other lakes'));
  assert.ok(html.indexOf('Windermere (N Basin), 722 readings') < html.indexOf('Other lakes'));
  assert.ok(html.indexOf('Haweswater Reservoir, 23 readings') > html.indexOf('Other lakes'));
  assert.match(html, /value="GB30229116" selected/);
  assert.match(html, /<label class="lt-pick" for="lt-select">Lake<\/label><select id="lt-select">/);
});

// The spot page's line (index.html, lakeTempLine), run on its own.
const page = fs.readFileSync(path.join(__dirname, '..', 'src', 'dipcast', 'site', 'index.html'), 'utf8');
const between = (a, b) => { const i = page.indexOf(a), j = page.indexOf(b, i); assert.ok(i >= 0 && j > i, `${a} .. ${b}`); return page.slice(i, j); };
const ctx = vm.createContext({ esc: s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]) });
vm.runInContext(between('const ltFar', 'const lakeTempHost') + ';this.lakeTempLine = lakeTempLine;', ctx);

test("a lake spot's page has one link: past temperatures by month, the years, the distance, never a figure", () => {
  const link = (L, s) => ({ wb_id: L.wb_id, lake: L.name, nearest_point_m: s.nearest_point_m, first: L.summary.first, last: L.summary.last });
  const win = ctx.lakeTempLine(link(WIN, WIN.spots[0]));
  assert.match(win, /^<a href="lake-temperatures\.html#lake=GB31247007">Past water temperatures in Windermere \(N Basin\), by month<\/a>: /);
  assert.equal(win.replace(/^<a[^>]*>[^<]*<\/a>/, '').replace(/&nbsp;/g, ' '),
    `: measured by the Environment Agency between May and September, 2000 to 2026, at a sampling point under 10 m from this spot. A different place from where you get in, and not today's temperature.`);
  const bro = plain(ctx.lakeTempLine(link(BRO, BRO.spots[0])));
  assert.match(bro, /at a sampling point 180 m from this spot\./);
  for (const t of [plain(win), bro]) assert.doesNotMatch(t, /°|\d+(\.\d)? ?C\b|median/);
  assert.equal(ctx.lakeTempLine(null), '');
  assert.equal(ctx.lakeTempLine({ ...link(BRO, BRO.spots[0]), wb_id: 'x"><script>' }), '');
  // In the page: after the latest readings, and into "At the water" on a phone.
  assert.match(page, /const tiles = dayTiles\(d, DAY\) \+ nowTiles\(d\) \+ lakeTempHost\(d\);/);
  assert.match(page, /\['water', 'At the water', \['#now-tiles', '#lt-past',/);
});
