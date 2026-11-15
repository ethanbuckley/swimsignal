// Past samples after rain (docs/AFTER-RAIN-SAMPLES-2026-11.md): at a bathing water with no daily E. coli figure, the
// past-samples tile adds the day's 48-hour rain and the water's own samples split at 10 mm (build_site.attach_after_rain),
// in season only, and keeps its old words everywhere else.
// node --test tests/site_after_rain.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const DATES = ['2026-07-04', '2026-07-05', '2026-07-06', '2026-07-07', '2026-07-08'];
const NOW = Date.parse('2026-07-04T09:00:00+01:00');
const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const pageSrc = html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n');
const pageDefs = names => names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`) || l.startsWith(`let ${n} =`));
  assert.ok(i >= 0, `no ${n} in index.html`);
  let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
  return pageSrc.slice(i, j).join('\n'); }).join('\n');
class FixedDate extends Date { constructor(...a) { if (!a.length) super(NOW); else super(...a); } static now() { return NOW; } }
// As tests/site_honest_headlines.test.cjs runs the tiles (facts).
const PAGE = ['esc', 'glyph', 'ICON', 'tone', 'scaleBar', 'untested', 'explain', 'factorRow', 'ecoliName', 'ecoliFold', 'ecoliCheck', 'ecoliSaid', 'ecoliMore', 'lakeRanged', 'rangeOf', 'ecoliReading', 'likely', 'rangeLine', 'monthPart', 'usualLine', 'RANGE_BASIS', 'rangeBasis', 'RANGE_MORE', 'RANGE_OFF_SAID', 'rangeFold', 'typicalLine', 'TYPICAL_SAID', 'TYPICAL_MORE', 'afterRainDay', 'afterRainLine', 'AFTER_RAIN_SAID', 'AFTER_RAIN_MORE',
  'noFeedSaid', 'nowTile', 'feedDown', 'feedStale', 'liveSay', 'recentSay', 'overflowDots', 'runningAtLastAnswer', 'statusText', 'feedTime', 'fmt', 'riverTile', 'rangeBar',
  'WT_ROUTES', 'waterEstOk', 'waterEstHow', 'waterEstSay', 'WT_AIR', 'WT_TAIL', 'waterEstMore', 'waterTile', 'weatherOn', 'spilling', 'bandWords', 'initial', 'rainCols', 'sunPath', 'facts', 'UNLISTED_ECOLI', 'water', 'polledMs', 'pollAt', 'pollSay'];
function page(dates = DATES) {
  const ctx = vm.createContext({ Date: FixedDate, ROOT: { pathname: '/' }, DATA: { generated_at: `${dates[0]}T08:00:00+01:00`, ecoli_check: null },
    milesAway: m => `${m.toFixed(1)} miles away`, MILE_KM: 1.609 });
  const dir = path.join(__dirname, '../src/dipcast/site/');
  vm.runInContext(fs.readFileSync(dir + 'experience.js', 'utf8'), ctx);
  vm.runInContext(fs.readFileSync(dir + 'levels.js', 'utf8') + `\nsetToday("${dates[0]}");`, ctx);
  vm.runInContext(pageDefs(PAGE), ctx);
  return ctx;
}
const text = h => String(h || '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;| /g, ' ').replace(/\s+/g, ' ').trim();

const TYPICAL = { samples: 81, first_year: 2023, last_year: 2026, low: 45, median: 150, high: 350, line: 900, over_line: 3 };
const AFTER = { line_mm: 10, after_rain: { samples: 12, median: 190 }, after_less: { samples: 67, median: 130 }, first_year: 2023, last_year: 2026 };
const day = (date, rain, season = true) => ({ date, label: 'low', risk: 0, p_ecoli_gt900: 0.02, in_validated_season: season, rain_48h_mm: rain });
const pond = ({ after = AFTER, rains = [14.4, 3, 0, 0, 1], dates = DATES, season = true } = {}) => ({ id: 'bw-uki1106-11940',
  name: 'The Serpentine - Hyde Park', kind: 'lake', source: 'designated', location: { mode: 'lake' }, upstream_summary: { overflows: 0 },
  now: { label: 'low', risk: 0, discharging_upstream: 0, monitored_upstream: 0 }, contributors: [], assumptions: { max_upstream_km: 60, recent_spill_hours: 48 },
  ecoli_typical: TYPICAL, ...(after ? { ecoli_after_rain: after } : {}), days: dates.map((d, i) => day(d, rains[i], season)) });
const tile = (ctx, d, iso = null) => (vm.runInContext('facts', ctx)(d, iso).find(t => /past samples/.test(t.label)) || {});

test('in season: the day\'s rain, then the samples after more and after less rain, then "not a forecast"', () => {
  const ctx = page(), t = tile(ctx, pond());
  assert.equal(text(t.say),
    'The middle of 81 Environment Agency samples here, May to September 2023–2026, read 150 E. coli per 100 ml; the middle 8 in 10 read between 45 and 350. 3 were over 900. '
    + 'About 14 mm of rain here in the 48 hours to midday today. Past samples here taken after more than 10 mm in 48 hours: the middle of 12 read 190. '
    + 'After less rain, the middle of 67 read 130. Past samples, not a forecast.');
  assert.match(text(t.more), /rain rule on the Accuracy page/);
  assert.doesNotMatch(text(t.say), /nothing to forecast from/);
});

test('a lab limit reads as the page reads it', () => {
  const line = vm.runInContext('afterRainLine', page());
  assert.match(text(line({ ...AFTER, after_less: { samples: 54, median: '<10' } }, day('2026-07-04', 2))), /After less rain, the middle of 54 read under 10\./);
});

test('without the split, out of season, or with no rain figure: the old words, unchanged', () => {
  const ctx = page();
  const old = 'Past samples, not a forecast: with no monitored overflow upstream there is nothing to forecast from.';
  assert.match(text(tile(ctx, pond({ after: null })).say), new RegExp(old.replace(/[.:]/g, '\\$&') + '$'));
  assert.match(text(tile(ctx, pond({ rains: [null, null, null, null, null] })).say), /nothing to forecast from\.$/);
  const oct = ['2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08'];
  assert.match(text(tile(page(oct), pond({ dates: oct, season: false })).say), /nothing to forecast from\.$/);
});

test('a picked day uses that day\'s rain and names it', () => {
  const ctx = page(), d = pond();
  const t = tile(ctx, d, d.days[2].date);
  assert.match(text(t.say), /About 0 mm of rain here in the 48 hours to midday on Monday\./);
});

test('no estimate, safety, risk, exceedance or colour words', () => {
  const s = text(tile(page(), pond()).say);
  assert.doesNotMatch(s.replace(/Past samples, not a forecast\./, ''), /risk|exceed|breach|safe|clean|alert|warn|likely|expect|forecast|higher|lower|usual/i);
});

test('a picked day\'s rows (water) say the same, with the fold', () => {
  const ctx = page(), d = pond(), row = vm.runInContext('water', ctx)(d, [d.days[0]]);
  assert.match(text(row), /About 14 mm of rain here in the 48 hours to midday today\. Past samples here taken after more than 10 mm in 48 hours: the middle of 12 read 190\. After less rain, the middle of 67 read 130\. Past samples, not a forecast\./);
  assert.match(row, /<summary>About these samples<\/summary>/);
});
