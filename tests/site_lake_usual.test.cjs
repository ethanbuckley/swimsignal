// The lake tile's "higher or lower than usual" line (docs/LAKE-RANGE-DIRECTION-PROPOSAL-2026-11.md): the build puts
// `usual` and `direction` on an in-season day's ecoli_range at a lake bathing water with its own samples
// (lake_range.compared); the page says one of three forms after the range sentence, and nothing without them.
// node --test tests/site_lake_usual.test.cjs
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
const PAGE = ['esc', 'glyph', 'ICON', 'tone', 'scaleBar', 'untested', 'explain', 'factorRow', 'ecoliName', 'ecoliFold', 'ecoliCheck', 'ecoliSaid', 'ecoliMore', 'lakeRanged', 'rangeOf', 'ecoliReading', 'likely', 'rangeLine', 'monthPart', 'usualLine', 'RANGE_BASIS', 'rangeBasis', 'RANGE_MORE', 'RANGE_OFF_SAID', 'rangeFold', 'typicalLine', 'TYPICAL_SAID', 'TYPICAL_MORE',
  'noFeedSaid', 'nowTile', 'feedDown', 'feedStale', 'liveSay', 'recentSay', 'overflowDots', 'runningAtLastAnswer', 'statusText', 'feedTime', 'fmt', 'riverTile', 'rangeBar',
  'WT_ROUTES', 'waterEstOk', 'waterEstHow', 'waterEstSay', 'WT_AIR', 'WT_TAIL', 'waterEstMore', 'waterTile', 'weatherOn', 'spilling', 'bandWords', 'initial', 'rainCols', 'sunPath', 'facts', 'UNLISTED_ECOLI', 'water'];
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
const day = (date, range, season = true) => ({ date, label: 'low', risk: 0.01, p_ecoli_gt900: 0.02, in_validated_season: season, rain_48h_mm: 2,
  ecoli_range: range });
const lake = (ranges, { basis = 'tested', dates = DATES, season = true } = {}) => ({ id: 'bw-ukd1203-45650', name: 'Windermere, Millerground Landing',
  kind: 'lake', source: 'designated', location: { mode: 'lake' }, upstream_summary: { overflows: 4 },
  now: { label: 'low', risk: 0, discharging_upstream: 0, monitored_upstream: 4 }, contributors: [], assumptions: { max_upstream_km: 60, recent_spill_hours: 48 },
  ecoli_range_scope: { rule: 'lake-range-v1', basis, bw_id: basis === 'average lake' ? null : 'ukd1203-45650' },
  days: dates.map((d, i) => day(d, ranges[i] || ranges[0], season)) });
const R = (median, extra = {}) => ({ low: 4.2, median, high: 150, ...extra });
const tileSay = (ctx, d) => text((vm.runInContext('facts', ctx)(d).find(t => /E.&nbsp;coli estimate/.test(t.label)) || {}).say);

test('the three forms, with the period of the month and the page\'s own reading words', () => {
  const ctx = page(), line = vm.runInContext('usualLine', ctx);
  assert.equal(line(day('2026-07-04', R(16, { usual: 6.2, direction: 'higher' }))), 'That is higher than usual for this lake in early July (usually under 10).');
  assert.equal(line(day('2026-07-15', R(16, { usual: 30, direction: 'lower' }))), 'That is lower than usual for this lake in mid July (usually about 30).');
  assert.equal(line(day('2026-07-28', R(16, { usual: 22, direction: 'about' }))), 'That is about usual for this lake in late July.');
  assert.equal(line(day('2026-08-10', R(2400, { usual: 1100, direction: 'higher' }))), 'That is higher than usual for this lake in early August (usually about 1,100).');
  assert.equal(line(day('2026-05-11', R(16, { usual: 30, direction: 'lower' }))), 'That is lower than usual for this lake in mid May (usually about 30).');
  assert.equal(line(day('2026-09-30', R(16, { usual: 30, direction: 'lower' }))), 'That is lower than usual for this lake in late September (usually about 30).');
});

test('no line without a usual reading and a direction', () => {
  const line = vm.runInContext('usualLine', page());
  assert.equal(line(day('2026-07-04', R(16))), '');                                        // average lake, out of season, or the file off
  assert.equal(line(day('2026-07-04', R(16, { usual: null, direction: 'about' }))), '');
  assert.equal(line(day('2026-07-04', R(16, { usual: 9, direction: 'sideways' }))), '');
  assert.equal(line(day('2026-07-04', null)), '');
  assert.equal(line(null), '');
});

test('on the lake tile the line follows the range sentence, in its text; nothing at an average lake or out of season', () => {
  const ctx = page();
  const higher = tileSay(ctx, lake([R(16, { usual: 6.2, direction: 'higher' })]));
  assert.match(higher, /^A sample today would most likely read about 16 E\. coli per 100 ml; 8 in 10 would read between under 10 and 150\. That is higher than usual for this lake in early July \(usually under 10\)\. Tomorrow about 16/);
  assert.match(tileSay(ctx, lake([R(16, { usual: 30, direction: 'lower' })])), /150\. That is lower than usual for this lake in early July \(usually about 30\)\. Tomorrow/);
  assert.match(tileSay(ctx, lake([R(16, { usual: 22, direction: 'about' })])), /150\. That is about usual for this lake in early July\. Tomorrow/);
  // Tomorrow keeps its own short sentence: the line is today's only.
  assert.equal((higher.match(/usual/g) || []).length, 2);
  // An average lake: the build gives no usual, and the tile says what it said before.
  const avg = tileSay(ctx, lake([R(16)], { basis: 'average lake' }));
  assert.doesNotMatch(avg, /usual/);
  assert.match(avg, /^A sample today would most likely read about 16 E\. coli per 100 ml; 8 in 10 would read between under 10 and 150\. Tomorrow/);
  // Out of season the tile has no figure and no line, even if a day carried one.
  const oct = ['2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08'];
  const off = vm.runInContext('facts', page(oct))(lake([R(16, { usual: 6.2, direction: 'higher' })], { dates: oct, season: false }));
  for (const t of off) assert.doesNotMatch(text(t.say) + text(t.fold), /than usual|about usual/);
});

test('no safety, risk, exceedance or colour words in the line', () => {
  const line = vm.runInContext('usualLine', page());
  for (const [u, dir] of [[6.2, 'higher'], [30, 'lower'], [22, 'about']])
    assert.doesNotMatch(line(day('2026-07-04', R(16, { usual: u, direction: dir }))), /risk|exceed|breach|safe|clean|alert|warn|green|amber|red\b|<b>|class=/i);
});
