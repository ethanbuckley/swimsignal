// What the iPhone journey on the live site found on 27 Oct 2026 (swimsignal-private/phone-journey-2026-10-27.md,
// findings 2 to 6): an advised spot was a plain green dot on the map, the plan's share was simply missing when
// its only low spot had advice, an outing to an advised spot with a Very high risk backup said nothing of it,
// the spot picker offered the backup, and "Saturday: 61 of 105" sat under the "Today and tomorrow" filter.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const P = require('../src/dipcast/site/plan.js');
const O = require('../src/dipcast/site/outing.js');
const PAGE = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');

const col = (id, name, extra = {}) => ({id, name, href: `spot/${id}/`, tone: 'low', headline: 'Low risk tomorrow', level: 'low', advised: false, ...extra});
const tile = o => O.outingSection({day: '2026-10-28', when: '', spot: 'a', groups: [], backupGroups: [], missing: [], issued: 'x', open: true, ...o});

test('an outing where neither choice looks good says so, with why, and only then', () => {
  L.setToday('2026-10-27');
  const pond = col('a', 'Frensham Great Pond', {advised: true}), wey = col('b', 'River Wey, Waverley', {tone: 'vhigh', level: 'very high'});
  const h = tile({main: pond, alt: wey});
  assert.match(h, /<p class="outing-poor"><b>Neither spot looks good tomorrow\.<\/b> Frensham Great Pond has an official notice, and River Wey, Waverley is at Very high risk\. Look at the other spots in this plan, or another day\.<\/p>/);
  assert.ok(h.indexOf('outing-poor') < h.indexOf('outing-pair'));   // above the two columns
  // One of the two is fine: nothing said.
  assert.ok(!tile({main: pond, alt: col('c', 'Shepperton Lake')}).includes('outing-poor'));
  assert.ok(!tile({main: col('c', 'Shepperton Lake'), alt: wey}).includes('outing-poor'));
  // Moderate is not High: nothing said.
  assert.ok(!tile({main: col('c', 'X', {level: 'moderate'}), alt: null}).includes('outing-poor'));
  // No backup: the spot alone, a day further on by name.
  assert.match(tile({day: '2026-10-31', main: col('d', 'Port Meadow', {level: 'high'}), alt: null}),
    /<b>Your spot does not look good on Saturday\.<\/b> Port Meadow is at High risk\./);
  assert.ok(!tile({main: null, alt: null}).includes('outing-poor'));
});

test('the spot picker leaves out the backup, as the backup picker leaves out the spot', () => {
  const BY = new Map(['a', 'b', 'c'].map(id => [id, {id, name: id.toUpperCase()}]));
  const ids = g => g.flatMap(([, s]) => s.map(x => x.id));
  assert.deepEqual(ids(O.outingOptions([...BY.values()], new Set(), BY, 'b')), ['a', 'c']);
  assert.match(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/outing.js'), 'utf8'),
    /groups: outingOptions\(list, SAVED, byId, PLAN\.backup\), backupGroups: outingOptions\(list, SAVED, byId, PLAN\.spot\)/);
});

test('a shared outing holds the day, time and spots, and starts its plan from the spot, never from you', () => {
  const dates = ['2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30', '2026-10-31'];
  const main = {id: 'frensham', name: 'Frensham Great Pond', lat: 51.157, lon: -0.785};
  for (const from of [{here: true}, {name: 'Farnham', lat: 51.214, lon: -0.799}]) {
    const plan = {day: '2026-10-31', from, within: 10, kind: 'all', compare: ['x'], when: 'morning', spot: 'frensham', backup: 'wey'};
    const hash = P.planHash(O.outingShared(plan, main));
    assert.ok(!hash.includes('here') && !hash.includes('Farnham') && !hash.includes('51.214') && !hash.includes('compare'), hash);
    const back = P.readPlan(hash, dates);
    assert.deepEqual([back.day, back.when, back.spot, back.backup, back.from], ['2026-10-31', 'morning', 'frensham', 'wey', {name: main.name, lat: main.lat, lon: main.lon}]);
  }
  const keep = O.outingSection({day: '2026-10-31', spot: 'frensham', groups: [], backupGroups: [], missing: [], issued: 'x', open: true, main: col('frensham', main.name), alt: null});
  assert.match(keep, /id="outing-share">Share this outing<\/button>/);
  assert.match(keep, /not where you start from/);
});

test("the plan's share says why there is nothing to share when every spot it would hold has advice", () => {
  const body = PAGE.slice(PAGE.indexOf('function planShare('), PAGE.indexOf('function bindPlan('));
  assert.match(body, /if \(!pick\.length\) \{ if \(out\.length\)/);
  assert.match(body, /Nothing to share \$\{on\}: \$\{out\.length === 1 \? `the only spot it would hold, \$\{esc\(out\[0\]\.s\.name\)\}, has`/);
});

test('a spot with official advice is ringed on the map, and the key says what the ring means while one is', () => {
  const body = PAGE.slice(PAGE.indexOf('function styleMarkers('), PAGE.indexOf('function setMapDay('));
  assert.match(body, /color: adv \? ADVICE_RING : PAPER, weight: adv \? 3\.5 : 2, fillColor: colour\(lv\)/);   // the level's colour kept
  assert.match(body, /\.advkey'\)\.forEach\(k => \{ k\.hidden = !DATA\.spots\.some\(mapAdvised\); \}\)/);
  assert.match(PAGE, /<span class="advkey" hidden><span class="dot adv"><\/span>Ringed: an official notice; open the spot to read it<\/span>/);
  assert.match(PAGE, /const ADVICE_RING = '#e5a53a';/);
  assert.match(PAGE, /--notice-line:#e5a53a;/);   // the same amber as the advice's own line
});

test("under \"Today and tomorrow\" a later weekend day is said to be the weekend's", () => {
  L.setToday('2026-10-27');   // a Tuesday: Saturday is the fifth day
  const dates = ['2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30', '2026-10-31'];
  const spots = [{upstream_summary: {overflows: 1}, location: {mode: 'lake'}, now: {label: 'high'},
    days: dates.map((date, i) => ({date, label: i === 4 ? 'low' : 'high', risk: i === 4 ? 0.01 : 0.5}))}];
  const a = L.lowAnswerDay(spots, dates);
  assert.equal(a.date, '2026-10-31');
  assert.equal(L.lowAnswerWords(a), 'This weekend, Saturday: 1 of 1 spot at low risk');
  assert.equal(L.lowAnswerWords(L.lowAnswerDay(spots, dates, '2026-10-31')), 'Saturday: 1 of 1 spot at low risk');   // picked
});
