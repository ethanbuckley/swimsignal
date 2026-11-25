// What to do, under the level, in a card (option A of the 18 Nov 2026 mock-ups, Ethan's choice; index.html actCard,
// actWhy, actGo, actPlan, eaAdviceLine; docs/DESIGN.md "What to do under the level"). An outside audit measured Ilkley
// at 390 px: the level at about 427 px and "Avoid swimming here right now" at about 1,159 px, under the five days.
// Each state the mock-up did not draw, from the rules already on the page. The page's own functions, run as
// scripts/prerender_spots.js runs them.   node --test tests/site_act_card.test.cjs
process.env.TZ = 'Europe/London';   // as the build runs them
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const spots = require('../scripts/prerender_spots.js');

const PAGE = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const GEN = '2026-11-17T19:40:00+00:00', ROOT = 'https://example.org/swim/';
const DAYS = ['2026-11-17', '2026-11-18', '2026-11-19', '2026-11-20', '2026-11-21'];
const RISK = {low: 0.05, moderate: 0.2, high: 0.5, 'very high': 0.8};
const PROFILE = 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=uke4100-08901';
const spot = (labels, extra = {}) => ({id: 'a', name: 'A river', kind: 'river', source: 'curated', upstream_summary: {overflows: 45},
  location: {mode: 'river', watercourse: 'River Wharfe'}, contributors: [], assumptions: {max_upstream_km: 60, recent_spill_hours: 48},
  lat: 53.93, lon: -1.82, now: {label: 'low', risk: 0.03, discharging_upstream: 0, monitored_upstream: 45},
  days: labels.map((l, i) => ({date: DAYS[i], label: l, risk: l ? RISK[l] : null, rain_48h_mm: 4})), ...extra});
const ilkley = extra => spot(['very high', 'very high', 'high', 'high', 'high'], {id: 'bw-uke4100-08901', name: 'Wharfe at Cromwheel, Ilkley',
  source: 'designated', classification: {class: 'poor', year: 2025, url: PROFILE},
  now: {label: 'very high', risk: 0.8, discharging_upstream: 0, recent_upstream: 3, monitored_upstream: 45}, ...extra});
const built = s => spots.prerender({generated_at: GEN, spots: [s]}, ROOT)[s.id];
const answer = h => h.slice(h.indexOf('<section class="answer"'), h.indexOf('</section>', h.indexOf('<section class="answer"')));
const card = h => { const m = h.match(/<div class="act-card" id="act-card">.*?<\/div><\/div>|<div class="act-card" id="act-card">(?:(?!<div class="ci">).)*/); return m ? m[0] : ''; };
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').replace(/ \./g, '.').trim();

// The page's own definitions, with levels.js, plan.js and the rest, for a picked day and the Plan link's test.
function page(list) {
  const store = {getItem: () => null, setItem() {}, removeItem() {}};
  const ctx = vm.createContext({console, URL, URLSearchParams, Intl, history: {state: null}, location: new URL(ROOT),
    navigator: {onLine: true}, localStorage: store, sessionStorage: store, addEventListener() {}, setTimeout, clearTimeout,
    ROOT: new URL(ROOT), map: null, TOUCH: false, STILL: false});
  ctx.window = ctx;
  vm.runInContext(`Date.now = () => ${Date.parse(GEN) + 600e3};`, ctx);
  for (const f of ['eatoday.js', 'experience.js', 'levels.js', 'lists.js', 'plan.js', 'outing.js'])
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site', f), 'utf8'), ctx);
  vm.runInContext(spots.reached(PAGE, ['answerWords', 'answerAfter', 'lowerReach'], ['ROOT', 'map', 'TOUCH', 'STILL']), ctx);
  ctx.LIST = list;
  vm.runInContext(`setToday("${DAYS[0]}"); DATA = {generated_at: "${GEN}", spots: LIST};`, ctx);
  return expr => vm.runInContext(expr, ctx);
}

test('very high at a water rated poor: the line in bold, why in one sentence, today\'s advice, under the level and the day', () => {
  const h = built(ilkley()), a = answer(h), c = card(a);
  // Name, one kind line, the level, one grey line with the day and the issue time (no age in the built copy), then the card.
  assert.match(a, /<p class="kind">River Wharfe · Designated bathing water<\/p>/);
  assert.match(a, /<h2 class="big veryhigh" id="risk-headline">Very high risk from sewage spills<\/h2><p class="issued when">Today, Tuesday 17 November · Issued 19:40<\/p><div class="act-card"/);
  assert.match(c, /^<div class="act-card" id="act-card"><p class="act-do"><strong>Avoid swimming here right now: choose a lower day or spot\.<\/strong><\/p>/);
  assert.equal(text(c.match(/<p class="act-why">.*?<\/p>/)[0]), 'Recent sewage spills. Rated poor, so every day here is at least high risk.');
  // Every day high or very high: no day to offer; the built copy has no planner, so no "Find another spot" (actPlan adds it).
  assert.match(c, /<div class="act-go"><\/div>/);
  assert.match(c, /<p class="act-ea">Today's official advice was not checked\. <a href="#ea-today">Check Environment Agency advice<\/a>\.<\/p>/);   // the page's own fold, which links the EA
  // Said once: not in the line by the issue time, and what to do not again under the five days.
  assert.doesNotMatch(a.replace(c, ''), /official advice was not checked/);
  assert.doesNotMatch(h.slice(h.indexOf('id="answer-after"')), /class="act"/);
  // The card is in ink: no level's colour on it or in it.
  assert.doesNotMatch(c, /class="[^"]*\b(?:low|moderate|high|veryhigh)\b/);
});

test('moderate and high: the what-to-do lines word for word, the first sentence bold, and a lower day where one is low', () => {
  const mod = card(answer(built(spot(['moderate', 'moderate', 'low', 'low', 'low'], {now: {label: 'moderate', risk: 0.2, discharging_upstream: 2, monitored_upstream: 45}}))));
  assert.equal(text(mod.match(/<p class="act-do">.*?<\/p>/)[0]), 'Take more care: young children, older people and anyone with a weakened immune system may want a lower day or spot.');
  assert.match(mod, /<a class="btn primary" href="#day=2026-11-19" data-act-day="2026-11-19">Low risk on Thursday<\/a>/);
  const high = card(answer(built(spot(['high', 'high', 'moderate', 'low', 'low']))));
  assert.match(high, /<p class="act-do"><strong>Better to choose a lower day or spot\.<\/strong> If you do swim, try not to swallow any water\.<\/p>/);
  // The first low day, not the first lower one, so it is the day "Low risk by Friday" names.
  assert.match(high, /data-act-day="2026-11-20">Low risk on Friday<\/a>/);
  // No low day: the first moderate one; nothing lower: no button at all.
  assert.match(card(answer(built(spot(['high', 'high', 'moderate', 'high', 'high'])))), /data-act-day="2026-11-19">Moderate risk on Thursday<\/a>/);
  assert.match(card(answer(built(spot(['high', 'high', 'high', 'high', 'very high'])))), /<div class="act-go"><\/div>/);
});

test('a low level and a plain level have no card: their line stays under the five days', () => {
  for (const s of [spot(['low', 'low', 'low', 'low', 'low']), spot(['low', 'low', 'low', 'low', 'low'], {upstream_summary: {overflows: 0}})]) {
    const h = built(s);
    assert.doesNotMatch(h, /act-card/);
    assert.match(h.slice(h.indexOf('id="answer-after"')), /<p class="act">/);
    assert.match(answer(h), /<div class="ci">.*<p class="issued">Issued Tue 19:40<\/p><\/div>/);   // the issue time where it was
  }
  // A low lake at a bathing water (Windermere at Millerground): today's advice in the line by the issue time, in the new words.
  const lake = built(spot(['low', 'low', 'low', 'low', 'low'], {kind: 'lake', source: 'designated', location: {mode: 'lake', watercourse: 'Windermere', lake_area_km2: 14.7},
    classification: {class: 'excellent', year: 2025, url: PROFILE}}));
  assert.match(answer(lake), /<p class="kind">Lake · Windermere · 14\.7 km² · Designated bathing water<\/p>/);
  assert.match(answer(lake), /<p class="cover">Today's official advice was not checked\. <a href="[^"]+">Check Environment Agency advice<\/a>\.<\/p>/);
});

test('an official notice stays above the level, apart from it, and the card points to it', () => {
  const official = [{line: 'Environment Agency: advice against bathing (harmful algae)', publisher: 'Environment Agency', link: PROFILE,
    since: '2026-06-19', checked: '2026-11-16', state: 'checked', restricts: true}];
  const h = built(spot(['moderate', 'moderate', 'low', 'low', 'low'], {kind: 'lake', source: 'designated', classification: {class: 'good', year: 2025, url: PROFILE}, official}));
  assert.ok(h.indexOf('class="notice official"') < h.indexOf('id="risk-headline"') && h.indexOf('id="risk-headline"') < h.indexOf('id="act-card"'));
  assert.match(card(h), /<p class="act-do"><strong>Follow the official advice above first\.<\/strong><\/p>/);
  assert.doesNotMatch(card(h), /act-ea/);   // a reviewed notice has its own check date and link
});

test('a picked day: that day\'s line, why and date; right now not known: the line over the level, and the card under it', () => {
  const s = spot(['low', 'low', 'low', 'high', 'low']), run = page([s]);
  run('var S = DATA.spots[0];');
  const sat = run(`answerWords(S, "${DAYS[3]}")`);
  assert.match(sat, /<p class="issued when">Friday 20 November · Issued 19:40, /);
  assert.match(sat, /<p class="act-do"><strong>Better to choose a lower day or spot\.<\/strong>/);
  assert.match(sat, /data-act-day="2026-11-21">Low risk on Saturday<\/a>/);
  assert.doesNotMatch(run(`answerWords(S, "${DAYS[1]}")`), /act-card/);   // a low picked day: none
  assert.match(run(`answerAfter(S, "${DAYS[1]}")`), /<p class="act">Usual care: /);
  // Nothing upstream reports live: that comes first, the level is the modelled forecast, then the card.
  const blind = spot(['high', 'high', 'high', 'low', 'low'], {now: {label: 'unknown', risk: null, discharging_upstream: 0, monitored_upstream: 0}});
  const b = page([blind])('answerWords(DATA.spots[0])');
  assert.ok(b.indexOf('class="live live-off"') < b.indexOf('<p class="modelled">') && b.indexOf('id="risk-headline"') < b.indexOf('id="act-card"'));
});

test('a stale forecast\'s notice, a point on the map and no forecast', () => {
  // The notice for an old forecast sits above the answer, as before; the card is still under the level.
  const h = built(ilkley());
  assert.ok(h.indexOf('data-notices') < h.indexOf('id="act-card"'));
  // A point clicked on the map that is not a listed spot gets the same card: the same forecast and the same line.
  assert.match(page([])(`answerWords(${JSON.stringify(spot(['high', 'high', 'high', 'high', 'high'], {unlisted: true}))})`), /id="act-card"/);
  // The forecast did not load: no level, so no card; the line it had stays in the answer.
  assert.doesNotMatch(page([])(`answerWords(${JSON.stringify({...spot(['high']), error: 'Could not load', days: []})})`), /act-card/);
});

test('"Find another spot" only where Plan a swim would offer a lower spot, never one at high or very high', () => {
  const here = spot(['very high', 'very high', 'very high', 'very high', 'very high'], {id: 'here'});
  const near = (id, labels, extra = {}) => spot(labels, {id, lat: 53.95, lon: -1.85, ...extra});   // about 2 miles away
  assert.equal(page([here, near('b', ['high', 'high', 'high', 'high', 'high'])])('lowerReach(DATA.spots[0], null)'), false);
  assert.equal(page([here, near('b', ['moderate', 'moderate', 'high', 'high', 'high'])])('lowerReach(DATA.spots[0], null)'), true);   // the level counts tomorrow too
  // Under advice against bathing, or with no monitored overflow (no level): not offered, as "Lower risk nearby".
  assert.equal(page([here, near('b', ['low', 'low', 'low', 'low', 'low'], {source: 'designated', classification: {class: 'poor', year: 2025}})])('lowerReach(DATA.spots[0], null)'), false);
  assert.equal(page([here, near('b', ['low', 'low', 'low', 'low', 'low'], {upstream_summary: {overflows: 0}})])('lowerReach(DATA.spots[0], null)'), false);
  // Beyond the plan's 20 miles: not offered. On a picked day, that day's levels.
  assert.equal(page([here, spot(['low', 'low', 'low', 'low', 'low'], {id: 'far', lat: 54.4, lon: -1.85})])('lowerReach(DATA.spots[0], null)'), false);
  assert.equal(page([here, near('b', ['high', 'high', 'high', 'high', 'low'])])(`lowerReach(DATA.spots[0], "${DAYS[4]}")`), true);
  // Added after the page is drawn, first, with the day second and plain; planHere and showDay call it.
  assert.match(PAGE, /go\.insertAdjacentHTML\('afterbegin', `<a class="btn primary" href="\$\{esc\(planPath\(\) \+ planHereHash\(d\)\)\}" data-plan-here>Find another spot<\/a>`\)/);
  assert.match(PAGE, /planHereLine\(d\)\);\n  actPlan\(d\);/);
  assert.match(PAGE, /innerHTML = answerWords\(d, DAY\); actPlan\(d\);/);
});
