// The rain forecasts' band on days 3 to 5 (review task D4, docs/ENSEMBLE-RAIN-TEST-2026-11.md): a thin line
// across the day's bar, from the lowest to the highest spill risk of three Met Office ensemble rain forecasts,
// on the bar's own scale. Only on days 3 to 5, only where the spill risk places the bar, and not where the
// three agree. A screen reader hears it in words.
// On its own: node --test tests/site_ensemble_band.test.cjs
process.env.TZ = 'Europe/London';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const BUILT = '2026-10-18T07:10:00+01:00';
const DAYS = ['2026-10-18', '2026-10-19', '2026-10-20', '2026-10-21', '2026-10-22'];
const day = (i, risk, band, extra = {}) => ({date: DAYS[i], risk, label: risk < 0.15 ? 'low' : risk < 0.4 ? 'moderate' : 'high',
  in_validated_season: false, ...(band ? {band} : {}), ...extra});
const spot = (days, extra = {}) => ({id: 'a', name: 'A', upstream_summary: {overflows: 3}, location: {mode: 'river'},
  now: {risk: 0.01, label: 'low', monitored_upstream: 3}, days, ...extra});

const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const pageSrc = html.slice(html.indexOf('<script>\nconst BRAND') + 9, html.lastIndexOf('</script>')).split('\n');
const pageDefs = names => names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`) || l.startsWith(`let ${n} =`));
  assert.ok(i >= 0, `no ${n} in index.html`);
  let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
  return pageSrc.slice(i, j).join('\n'); }).join('\n');
const page = spots => {
  const nowMs = Date.parse(BUILT) + 600e3;
  class FixedDate extends Date { constructor(...a) { super(...(a.length ? a : [nowMs])); } static now() { return nowMs; } }
  const ctx = vm.createContext({Date: FixedDate, navigator: {onLine: true}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/levels.js'), 'utf8'), ctx);
  vm.runInContext(`let DATA = ${JSON.stringify({generated_at: BUILT, spots})}, VIEW = {day: null};\nsetToday('${DAYS[0]}');\n`
    + pageDefs(['esc', 'tone', 'inBand', 'levelPlace', 'BAND_FROM', 'SPILL_EDGES', 'bandPlace', 'spillWord', 'bandSaid', 'dayWx', 'dayRows']), ctx);
  return expr => vm.runInContext(expr, ctx);
};
const bands = h => [...h.matchAll(/<b class="band" style="left:([\d.]+)%;width:([\d.]+)%"><\/b>/g)].map(m => [Number(m[1]), Number(m[2])]);

test('a band on days 3 to 5 only, on the bar\'s own scale', () => {
  const b = {low: 0.05, high: 0.55};
  const run = page([spot([0, 1, 2, 3, 4].map(i => day(i, 0.2, b)))]);
  const rows = run('dayRows(DATA.spots[0])');
  // Five rows, three bands: 0.05 is a third of the way through low (0 to 0.15), 0.55 half way through high (0.40 to 0.70).
  assert.deepEqual(bands(rows), [[8.3, 54.2], [8.3, 54.2], [8.3, 54.2]]);
  assert.equal(rows.split('<button').length - 1, 5);
  assert.equal(rows.split('<button')[1].includes('class="band"'), false);   // today
  assert.equal(rows.split('<button')[2].includes('class="band"'), false);   // tomorrow
  assert.match(rows, /<span class="sr">Three Met Office rain forecasts give low to high risk\.<\/span>/);
  assert.equal(run('bandSaid({low: 0.2, high: 0.3})'), 'Three Met Office rain forecasts give moderate risk.');
});

test('no band where the three agree, where the members did not reach the day, or where the bar is not the spills\'', () => {
  const run = page([
    spot([day(0, 0.2), day(1, 0.2), day(2, 0.2, {low: 0.2, high: 0.203}), day(3, 0.2), day(4, null, {low: 0.1, high: 0.5}, {label: 'unknown'})]),
    // The E. coli estimate sets the level in season: the bar is placed by it, so the spills' band would mislead.
    spot([0, 1, 2, 3, 4].map(i => day(i, 0.05, {low: 0.01, high: 0.3}, {in_validated_season: true, p_ecoli_gt900: 0.6}))),
    // A water rated poor: at least high every day, whatever the spills say.
    spot([0, 1, 2, 3, 4].map(i => day(i, 0.05, {low: 0.01, high: 0.3})), {classification: {class: 'Poor'}}),
  ]);
  assert.deepEqual(bands(run('dayRows(DATA.spots[0])')), []);
  assert.deepEqual(bands(run('dayRows(DATA.spots[1])')), []);
  assert.deepEqual(bands(run('dayRows(DATA.spots[2])')), []);
  assert.doesNotMatch(run('dayRows(DATA.spots[2])'), /Three Met Office rain forecasts/);
});

test('the band is drawn in ink, two pixels inside the bar, and named in the page\'s CSS once', () => {
  assert.match(html, /\.dbar \.band \{ position:absolute; top:2px; height:2px; background:var\(--ink\); \}/);
});
