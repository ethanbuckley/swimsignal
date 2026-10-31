// The opening of a spot's page (20 Oct 2026, a second outside review): "Its long, centred introduction pushes
// the five-day forecast down", and "make the important missing input visible without searching through the
// page". The place, the level, why and when, what the forecast could read and the issue time read as one
// block (answerWords, coverLine), the five days straight under it, and what to do and what the level counts
// under the five days (answerAfter). The page's own functions, run as scripts/prerender_spots.js runs them.
process.env.TZ = 'Europe/London';   // as the build runs them
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const spots = require('../scripts/prerender_spots.js');

const PAGE = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const GEN = '2026-10-20T16:35:00+01:00', NOW = Date.parse('2026-10-20T17:30:00+01:00');
const DAYS = ['2026-10-20', '2026-10-21', '2026-10-22', '2026-10-23', '2026-10-24'];
const RISK = {low: 0.05, moderate: 0.2, high: 0.5};
const spot = (labels, extra = {}) => ({id: 'a', name: 'A river', kind: 'river', source: 'curated', upstream_summary: {overflows: 45},
  location: {mode: 'river'}, contributors: [], assumptions: {max_upstream_km: 60, recent_spill_hours: 48},
  now: {label: 'low', risk: 0.03, discharging_upstream: 0, monitored_upstream: 45},
  days: labels.map((l, i) => ({date: DAYS[i], label: l, risk: l ? RISK[l] : null, rain_48h_mm: 4})), ...extra});
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();

// The page's definitions that the opening reaches, with levels.js and the other scripts, as the prerender runs them.
function page(now = NOW) {
  const store = {getItem: () => null, setItem() {}, removeItem() {}}, root = 'https://example.org/swim/';
  const ctx = vm.createContext({console, URL, URLSearchParams, Intl, history: {state: null}, location: new URL(root),
    navigator: {onLine: true}, localStorage: store, sessionStorage: store, addEventListener() {}, setTimeout, clearTimeout,
    ROOT: new URL(root), map: null, TOUCH: false, STILL: false});
  ctx.window = ctx;
  vm.runInContext(`Date.now = () => ${now};`, ctx);
  for (const f of ['eatoday.js', 'experience.js', 'levels.js', 'lists.js'])
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site', f), 'utf8'), ctx);
  vm.runInContext(spots.reached(PAGE, ['answerWords', 'answerAfter', 'coverWords', 'daysTile'], ['ROOT', 'map', 'TOUCH', 'STILL']), ctx);
  vm.runInContext(`setToday("${DAYS[0]}"); DATA = {generated_at: "${GEN}", spots: []};`, ctx);
  return ctx;
}
const J = x => JSON.parse(JSON.stringify(x));   // out of the page's realm

test('the line on what the forecast could read: live readings, days with no forecast, Wales, the EA advice', () => {
  const ctx = page(), words = (s, iso = null) => J(vm.runInContext('coverWords', ctx)(s, iso)), live = s => vm.runInContext('liveLine', ctx)(s);
  // Since the review of PR #463 (30 Oct 2026) the live status is the answer's first line (levels.js, liveLine), in
  // counts, before the level; the line by the issue time keeps the rest, so the counts are not said twice.
  const lb = spot(['low', 'moderate', 'moderate', 'moderate', 'high'], {now: {label: 'low', risk: 0.03, discharging_upstream: 2, monitored_upstream: 44}});
  assert.equal(live(lb), 'Live status from 44 of 45 overflows upstream: 2 spilling at the last poll; 1 does not report, so could be spilling unseen');
  assert.deepEqual(words(lb), []);
  assert.equal(live(spot(['low', 'low', 'low', 'low', 'low'], {now: {label: 'low', monitored_upstream: 42}})),
    'Live status from 42 of 45 overflows upstream: none spilling at the last poll; 3 do not report, so could be spilling unseen');
  assert.equal(live(spot(['low', 'low', 'low', 'low', 'low'])), 'Live status from all 45 overflows upstream: none spilling at the last poll');   // said every time
  assert.equal(live(spot(['low', 'low', 'low', 'low', 'low'], {upstream_summary: {overflows: 1}, now: {label: 'low', monitored_upstream: 1}})),
    'Live status from the overflow upstream: not spilling at the last poll');
  // None reports: unavailable, at any level, and never as dry.
  const none = {label: null, discharging_upstream: 0, monitored_upstream: 0, no_feed_upstream: 45};
  for (const days of [['low', 'moderate', 'low', 'low', 'low'], ['low', 'low', 'low', 'low', 'low']]) {
    assert.equal(live(spot(days, {now: none})), 'Live sewage spill status unavailable: none of the 45 overflows upstream reports live, so whether any is spilling is not known');
    assert.deepEqual(words(spot(days, {now: none})), []);
  }
  // An update with no count keeps the old clause here (no live line to replace it).
  assert.deepEqual(words(spot(['low', 'low', 'low', 'low', 'low'], {now: {label: 'low'}})), ['All 45 overflows upstream report live, none spilling now']);
  // A picked later day rests on the rain: nothing about the live status.
  assert.deepEqual(words(lb, DAYS[2]), []);
  // Days with no forecast, by name; never said as low.
  assert.deepEqual(words(spot(['low', 'low', 'low', null, null])), ['No forecast for Friday or Saturday']);
  // Overflows in Wales, short; today's EA advice at a bathing water, with where to look.
  const ludlow = spot(['high', 'high', 'high', 'high', 'high'], {source: 'designated', upstream_summary: {overflows: 11, wales_share: 0.12},
    now: {label: 'low', discharging_upstream: 0, monitored_upstream: 10},
    classification: {class: 'poor', year: 2025, url: 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukg2200-36060'}});
  assert.equal(text(vm.runInContext('coverLine', ctx)(ludlow)), 'Overflows in Wales not counted '
    + "(12% of the river above). Today's EA advice not checked: open it before you swim.");
  assert.match(vm.runInContext('coverLine', ctx)(ludlow), /<a href="#ea-today">open it<\/a>/);
  // Nothing to say, no line: a plain level with nothing upstream, not a bathing water.
  assert.equal(vm.runInContext('coverLine', ctx)(spot(['low', 'low', 'low', 'low', 'low'], {upstream_summary: {overflows: 0}})), '');
  for (const s of [lb, ludlow]) assert.doesNotMatch(vm.runInContext('coverLine', ctx)(s), /\blow\b/i);
});

test('the answer is one block, the five days straight under it, and what to do and what it counts under them', () => {
  const s = spot(['low', 'moderate', 'moderate', 'moderate', 'high'], {now: {label: 'low', risk: 0.03, discharging_upstream: 2, monitored_upstream: 44}});
  const h = spots.prerender({generated_at: GEN, spots: [s]}, 'https://example.org/swim/').a;
  // The answer: name, level, why and when, where the week goes, what was read, the issue time, then the place
  // (kind, under the issue time since 29 Oct 2026); nothing else.
  const answer = h.slice(h.indexOf('<section class="answer"'), h.indexOf('</section>', h.indexOf('<section class="answer"')));
  assert.deepEqual([...answer.matchAll(/<(?:h1|h2|p) class="([\w-]+)/g)].map(m => m[1]),
    ['spot-name', 'big', 'why', 'next', 'issued', 'kind']);   // the live status's counts are under the five days (31 Oct 2026)
  assert.ok(h.indexOf('class="live-row"') > h.indexOf('id="day-strip"'));
  // Then the five days' tile, first in the stack: its sentence, the rows, what to do, what the level counts.
  assert.ok(h.indexOf('</section><div class="stack"><section class="tile" aria-labelledby="days-h">') > 0);
  const tile = h.slice(h.indexOf('aria-labelledby="days-h"'));
  const at = k => tile.indexOf(k);
  assert.ok(at('class="t-sent"') < at('id="day-strip"') && at('id="day-strip"') < at('id="answer-after"')
    && at('id="answer-after"') < at('id="day-view"') && at('id="day-view"') < at('class="check"'));
  assert.match(tile, /<div class="after" id="answer-after"><p class="act">Take more care: [^<]+<\/p><p class="scope">This forecast counts sewage from the monitored storm overflows upstream/);
  // A picked day fills both again.
  assert.match(PAGE, /getElementById\('answer-words'\)\.innerHTML = answerWords\(d, DAY\);\n\s+const after = document\.getElementById\('answer-after'\); if \(after\) after\.innerHTML = answerAfter\(d, DAY\);/);
});
