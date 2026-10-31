// The five day rows' key and their words to a screen reader (outside review, 31 Oct 2026: the grey bar and the
// "0 mm" and "11°" figures were not self-explanatory). A key over the columns names the bar's scale and the
// two figures, hidden from a screen reader, which hears each row as one sentence instead.
// On its own: node --test tests/site_day_key.test.cjs
process.env.TZ = 'Europe/London';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const BUILT = '2026-10-31T07:10:00+00:00';
const DAYS = ['2026-10-31', '2026-11-01', '2026-11-02', '2026-11-03', '2026-11-04'];
const day = (i, risk, extra = {}) => ({date: DAYS[i], risk, label: risk < 0.15 ? 'low' : 'high', rain_48h_mm: i * 4, in_validated_season: false, ...extra});
const weather = {days: DAYS.map((date, i) => ({date, tmax: 10 + i}))};
const spot = (days, extra = {}) => ({id: 'a', name: 'A', upstream_summary: {overflows: 3}, location: {mode: 'river'},
  now: {risk: 0.01, label: 'low', monitored_upstream: 3}, days, weather, ...extra});

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
    + pageDefs(['esc', 'fmt', 'tone', 'inBand', 'levelPlace', 'BAND_FROM', 'SPILL_EDGES', 'bandPlace', 'spillWord', 'bandSaid', 'dayWx', 'dayRows']), ctx);
  return expr => vm.runInContext(expr, ctx);
};
const said = h => [...h.matchAll(/<(?:button|div) class="drow[^>]*>(.*?)<\/(?:button|div)>/g)]
  .map(m => [...m[1].matchAll(/<span class="sr">([^<]*)<\/span>/g)].map(s => s[1]).join(' '));

test('a key over the columns names the bar\'s scale and the two figures, out of a screen reader\'s way', () => {
  const rows = page([spot([0, 1, 2, 3, 4].map(i => day(i, i === 2 ? 0.5 : 0.05)))])('dayRows(DATA.spots[0])');
  assert.ok(rows.startsWith('<div class="dkey" aria-hidden="true"><span></span><span class="dk">Low to very high</span>'
    + '<span class="dx"><span>Rain</span><span>Air</span></span></div><div class="drows"'), rows.slice(0, 300));
  // The row's own words are hidden too, and said in full: no "Sat", no bare "Low", no figure twice.
  assert.doesNotMatch(rows, /<span class="(d|l)">/);
  assert.match(rows, /<span aria-hidden="true">4&nbsp;mm<\/span><span aria-hidden="true">11°<\/span>/);
  assert.deepEqual(said(rows), [
    'Today, Saturday 31 October: low risk. Rain 0 mm in the 48 hours to midday. Air high 10 °C.',
    'Sunday 1 November: low risk. Rain 4 mm in the 48 hours to midday. Air high 11 °C.',
    'Monday 2 November: high risk. Rain 8 mm in the 48 hours to midday. Air high 12 °C.',
    'Tuesday 3 November: low risk. Rain 12 mm in the 48 hours to midday. Air high 13 °C.',
    'Wednesday 4 November: low risk. Rain 16 mm in the 48 hours to midday. Air high 14 °C.']);
});

test('the key names only the columns some row fills', () => {
  const run = page([spot([0, 1, 2, 3, 4].map(i => day(i, 0.05, {rain_48h_mm: null}))), spot([0, 1, 2, 3, 4].map(i => day(i, 0.05)), {weather: null})]);
  assert.match(run('dayRows(DATA.spots[0])'), /^<div class="dkey" [^>]*>.*?<span class="dx"><span><\/span><span>Air<\/span><\/span><\/div>/);
  assert.match(run('dayRows(DATA.spots[1])'), /^<div class="dkey" [^>]*>.*?<span class="dx"><span>Rain<\/span><span><\/span><\/span><\/div>/);
});

test('where nothing upstream can spill, the rain is the level: the key says so, and the row says it in words', () => {
  const rows = page([spot([0, 1, 2, 3, 4].map(i => day(i, null)), {upstream_summary: {overflows: 0}})])('dayRows(DATA.spots[0])');
  assert.ok(rows.startsWith('<div class="dkey rain" aria-hidden="true"><span></span><span>Rain</span><span></span><span class="dx"><span>Air</span></span></div>'), rows.slice(0, 300));
  assert.equal(said(rows)[1], 'Sunday 1 November: 4 mm of rain in the 48 hours to midday. Air high 11 °C.');
});
