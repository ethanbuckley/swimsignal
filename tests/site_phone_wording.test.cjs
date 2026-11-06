// The phone journey's wording, made consistent on 6 Nov 2026 (after PR #633's audit): compare names the days as
// the rest of the site does, says "no monitored overflow" the same way with its caveat for an isolated lake too,
// a plan row gives an isolated lake its reason, and "Notifications are blocked" is said once on Saved.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const DIR = path.join(__dirname, '../src/dipcast/site/');
const L = require('../src/dipcast/site/levels.js');
const {compareNow} = require('../src/dipcast/site/experience.js');
const Li = require('../src/dipcast/site/lists.js');
const page = fs.readFileSync(DIR + 'index.html', 'utf8');
const pageSrc = page.slice(page.indexOf('<script>\n') + 9, page.lastIndexOf('</script>')).split('\n');
// Top-level definitions from index.html's script, as site_planner.test.cjs takes them.
function pageDefs(names) {
  return names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
    assert.ok(i >= 0, `no ${n} in index.html`);
    let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
    return pageSrc.slice(i, j).join('\n'); }).join('\n');
}
function pageContext(names, extra = {}, today = '2026-11-06') {
  const ctx = vm.createContext({...extra});
  vm.runInContext(fs.readFileSync(DIR + 'experience.js', 'utf8'), ctx);
  vm.runInContext(fs.readFileSync(DIR + 'levels.js', 'utf8') + `\nsetToday("${today}");`, ctx);
  vm.runInContext(pageDefs(names), ctx);
  return ctx;
}
const DATES = ['2026-11-06', '2026-11-07', '2026-11-08', '2026-11-09', '2026-11-10'];
const NONE = 'No monitored overflow found upstream, so no spills to report. Other pollution sources may still affect this water.';
// Loughrigg Tarn: the river network draws nothing into it. Brothers Water: nothing monitored within 60 km.
const isolated = {id: 'loughrigg', name: 'Loughrigg Tarn', kind: 'lake', source: 'curated', days: [], contributors: [],
  error: 'An isolated lake with no river connection in the network: storm overflows cannot reach it by water, so the forecast has nothing to say about it.',
  assumptions: {max_upstream_km: 60}};
const clear = {id: 'brothers', name: 'Brothers Water', kind: 'lake', source: 'curated', upstream_summary: {overflows: 0}, contributors: [],
  location: {mode: 'lake'}, now: {label: 'unknown', discharging_upstream: 0}, assumptions: {max_upstream_km: 60},
  days: DATES.map(date => ({date, risk: 0, label: 'low', p_ecoli_gt900: 0.1, in_validated_season: false}))};

test('compare names each day as the day strip, Saved and the plan do: "Today", then the weekday', () => {
  const river = {id: 'r', name: 'River', kind: 'river', source: 'curated', upstream_summary: {overflows: 2}, location: {mode: 'river'},
    now: {label: 'low', discharging_upstream: 0, monitored_upstream: 2}, days: DATES.map(date => ({date, risk: 0.05, label: 'low'}))};
  const ctx = pageContext(['esc', 'tone', 'compareTable'], {DATA: {generated_at: '2026-11-06T08:00:00Z'},
    fiveDays: () => DATES, issued: () => 'Fri 08:00', agoSpan: () => '1 hour', spotPath: id => `spot/${id}.html`, compareWater: () => ['–', '–']});
  vm.runInContext('compareRows = () => [["Right now", "x", ""]];', ctx);
  const html = vm.runInContext('compareTable', ctx)([river, clear], DATES[1]);
  const days = [...html.matchAll(/<span class="day">([^<]+)<\/span>/g)].map(m => m[1]);
  assert.deepEqual(days, ['Today', 'Sat', 'Sun', 'Mon', 'Tue']);
  assert.deepEqual(days, DATES.map(vm.runInContext('shortDay', ctx)));   // levels.js, the others' words
  assert.doesNotMatch(html, /Tomorrow|8 Nov/);
});

test('compare\'s Right now gives an isolated lake the same words and caveat as a lake with nothing upstream, never a low risk', () => {
  assert.equal(compareNow(isolated), NONE);
  assert.equal(compareNow(clear), NONE);
  for (const s of [isolated, clear]) assert.doesNotMatch(compareNow(s), /low risk/i);
  // Other errors keep their own words.
  assert.equal(compareNow({days: [], error: 'forecast failed: timeout'}), 'No forecast in this update.');
  assert.equal(compareNow({days: [], error: 'No river or lake within 1.5 km of this point.'}), 'Not covered by the forecast.');
});

test('a plan row for an isolated lake says why it has no monitored overflow', () => {
  const ctx = pageContext(['esc', 'spilling', 'planWhy'], {DATA: {generated_at: '2026-11-06T08:00:00Z'}});
  const why = s => vm.runInContext('planWhy', ctx)(s, DATES[1]);
  assert.equal(why(isolated), L.ISOLATED_WHY);
  assert.match(why(isolated), /^The river network draws no river or beck into this lake, so no monitored overflow can be traced to it\./);
  assert.equal(why({...clear, days: []}), 'No monitored storm overflow within 60 km upstream.');
  // A failed forecast is not an isolated lake: no reason invented for it.
  assert.equal(why({days: [], error: 'forecast failed: timeout', upstream_summary: {overflows: 4}}), '');
  for (const s of [isolated, clear]) assert.doesNotMatch(why(s), /low risk/i);
});

test('notifications blocked is said once, in the Alerts tile, not under every saved card', () => {
  for (const email of [false, true]) {
    const st = Li.spotAlert({push: true, email, can: 'blocked'});
    assert.equal(st.text, ''); assert.equal(st.link, false); assert.equal(st.toggle, false);
  }
  // Since 7 Nov 2026 the tile draws it itself, with where to allow them (tests/site_alerts_blocked.test.cjs).
  const said = 'Notifications are blocked for this site in your browser settings, so alerts cannot be turned on.';
  assert.equal(page.split(said).length - 1, 1, 'once in index.html: the Alerts tile');
  assert.match(page, /Notification\.permission === 'denied' \? `<p class="small tight" id="alerts-blocked"/);
  assert.ok(!fs.readFileSync(DIR + 'lists.js', 'utf8').includes(said));
  // A card with nothing to say is not drawn (index.html's CSS).
  assert.match(page, /\.place-alert:empty \{ display:none; \}/);
});
