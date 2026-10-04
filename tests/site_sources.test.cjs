// "Where the risk comes from" on a spot's page (index.html, whereFrom and the functions before it):
// one sentence naming the overflow a risk comes from, or how many it is spread over, and after a
// spill when right now's risk should be back to low. The fields come from forecast.py
// (tests/test_clears_and_sources.py checks those); here, the words the page makes of them.
// On its own: node --test tests/site_sources.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const NOW = Date.parse('2026-10-04T01:16:00Z');   // Sunday 02:16 in the UK, two hours after the build
class FixedDate extends Date { static now() { return NOW; } }

// Top-level definitions taken from index.html's script, as site_planner.test.cjs does: a definition
// runs from its first line to the next line at the margin that does not close it.
const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const pageSrc = html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n');
const pageDefs = names => names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
  assert.ok(i >= 0, `no ${n} in index.html`);
  let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
  return pageSrc.slice(i, j).join('\n'); }).join('\n');
const ctx = vm.createContext({Date: FixedDate});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/levels.js'), 'utf8') + '\nsetToday("2026-10-04"); let DAY = null;', ctx);
vm.runInContext(pageDefs(['esc', 'fmt', 'glyph', 'ICON', 'nameCase', 'onWater', 'sourcePlace', 'sourceSentence', 'DAY_PARTS',
  'partOfDay', 'clearSentence', 'whereFrom']), ctx);
const run = (expr, ...args) => vm.runInContext(expr, ctx)(...args);
const plain = h => h.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ');

const ILKLEY = {site_id: 'YW1', site_name: 'ILKLEY WwTW', receiving_watercourse: 'River Wharfe', status: 0,
  distance_km: 6.0, lake_distance_km: 0.0, travel_h: 5.2, share: 0.62, spread_over: 3};
const days = (extra = {}) => ['2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08'].map((date, k) =>
  ({date, risk: 0.05, label: 'low', risk_from_later_spills: k ? 0.02 : 0, ...(extra[date] || {})}));
const spot = (now, extra) => ({upstream_summary: {overflows: 12}, location: {mode: 'river'}, assumptions: {recent_spill_hours: 48},
  now: {risk: 0.05, label: 'low', discharging_upstream: 0, ...now}, days: days(extra), contributors: []});
const tile = (d, day = null) => { vm.runInContext(`DAY = ${JSON.stringify(day)}`, ctx); return plain(run('whereFrom', d)); };

test('one overflow is named alone only when it holds at least half the risk', () => {
  assert.equal(plain(run('sourceSentence', ILKLEY, '2026-10-04')),
    "Most of today's risk from sewage spills comes from Ilkley WwTW on the River Wharfe, 6.0 km upstream, about 5 hours away.");
  assert.match(plain(run('sourceSentence', {...ILKLEY, share: 0.5}, '2026-10-05')), /^Half of tomorrow's risk/);
  assert.match(plain(run('sourceSentence', {...ILKLEY, share: 0.93}, '2026-10-06')), /^Nearly all of Tuesday's risk/);
  // Under half: spread over the overflows that make up nine tenths, the largest named, its share rounded down.
  assert.equal(plain(run('sourceSentence', {...ILKLEY, share: 0.497, spread_over: 6}, '2026-10-06')),
    "Tuesday's risk from sewage spills is spread over 6 overflows. The largest part, 49%, comes from Ilkley WwTW on the River Wharfe, "
    + '6.0 km upstream, about 5 hours away.');
  // Right now, with a spill running, close by, across a lake, an hour away.
  const kirk = {...ILKLEY, site_name: 'KIRKOSWALD WwTW', receiving_watercourse: 'River Eden', status: 1, distance_km: 0.4, travel_h: 0.4, share: 0.74};
  assert.equal(plain(run('sourceSentence', kirk, 'now')),
    'Most of the risk from sewage spills right now comes from Kirkoswald WwTW on the River Eden, discharging now, 0.4 km upstream, under an hour away.');
  assert.match(plain(run('sourceSentence', {...ILKLEY, distance_km: 1.2, lake_distance_km: 0.8, travel_h: 1.4}, 'now')), /2\.0 km upstream, about 1 hour away\.$/);
  // A feed's id where it has no name; a name that could break the page is escaped.
  assert.match(plain(run('sourceSentence', {...ILKLEY, site_name: null}, 'now')), /comes from YW1 on the River Wharfe/);
  assert.match(run('sourceSentence', {...ILKLEY, site_name: '<img src=x>'}, 'now'), /&lt;img src=x&gt;/);
});

test("the feed's watercourse is given only where it reads as a name", () => {
  const on = w => run('onWater', w);
  assert.equal(on('River Wharfe'), 'on the River Wharfe');
  assert.equal(on('RIVER SEVERN'), 'on the River Severn');
  assert.equal(on('OUSE'), 'on the Ouse');
  assert.equal(on('The River Eden'), 'on the River Eden');
  assert.equal(on('Glenridding Beck'), 'on Glenridding Beck');
  assert.equal(on('Lake Windermere'), 'on Lake Windermere');
  for (const w of ['RIVER FROME(S)', 'TRIB OF THE RIVER TEIGN', 'Tributary of Torver Beck', 'Groundwater', 'UCK',
    'Starston Beck River Waveney  N', 'RUTLAND WATER/BARLEYTHORPE BRO', 'RIVER AVON (VIA SWS)', '', null]) assert.equal(on(w), '', String(w));
});

test('the clearing time is the part of the day it falls in, in UK time', () => {
  assert.equal(run('partOfDay', '2026-10-05T07:30:00+01:00'), 'by about Monday morning');
  assert.equal(run('partOfDay', '2026-10-04T12:00:00+01:00'), 'by about Sunday afternoon');
  assert.equal(run('partOfDay', '2026-10-04T23:26:00+01:00'), 'by about Sunday evening');
  assert.equal(run('partOfDay', '2026-10-04T23:30:00Z'), 'overnight into Monday');     // 00:30 on Monday in the UK
  assert.equal(run('partOfDay', '2026-12-01T17:59:00Z'), 'by about Tuesday afternoon');   // GMT in winter
});

test('after a spill the page says when the model expects low risk, and why then', () => {
  const run1 = spot({risk: 0.62, label: 'high', discharging_upstream: 1, clears_at: '2026-10-05T09:10:00+01:00', clears_by: 'die-off'});
  assert.equal(plain(run('clearSentence', run1)), 'If the overflow discharging upstream stops now, the model expects low risk from spills by about Monday morning.');
  assert.match(plain(run('clearSentence', {...run1, now: {...run1.now, discharging_upstream: 3}})), /^If the 3 overflows discharging upstream stop now, /);
  // All finished: the assumption is that no new one starts. The 48 h window, from when each spill's
  // water passed, brought it under low.
  const done = spot({risk: 0.2, label: 'moderate', clears_at: '2026-10-05T19:00:00+01:00', clears_by: 'window'});
  assert.equal(plain(run('clearSentence', done)), 'If no new spill starts, the model expects low risk from spills by about Monday evening, '
    + 'as it stops counting each spill 48 hours after its water has passed.');
  // Travel time held it up (a big spill far upstream, its water still on its way): the overflow and its travel time.
  const far = spot({risk: 0.49, label: 'high', discharging_upstream: 1, clears_at: '2026-10-05T17:00:00+01:00', clears_by: 'travel',
    clears_after: {site_id: 'UU9', site_name: 'APPLEBY WwTW', travel_h: 30.2}});
  assert.equal(plain(run('clearSentence', far)), 'If the overflow discharging upstream stops now, the model expects low risk from spills '
    + 'by about Monday afternoon, allowing for travel time: water from Appleby WwTW takes about 30 hours to get here.');
  assert.match(run('clearSentence', {...far, now: {...far.now, clears_after: {site_id: 'X<1>', site_name: null, travel_h: 12}}}),
    /water from X&lt;1&gt; takes about 12 hours to get here\.$/);
  assert.match(plain(run('clearSentence', {...far, now: {...far.now, clears_after: undefined}})), /by about Monday afternoon\.$/);   // no name: no clause
  // A later day raised by spills after today alone is named; one raised only by today's is not.
  const wet = spot({risk: 0.62, label: 'high', discharging_upstream: 1, clears_at: '2026-10-05T09:10:00+01:00', clears_by: 'die-off'},
    {'2026-10-05': {risk: 0.3, label: 'moderate', risk_from_later_spills: 0.05}, '2026-10-06': {risk: 0.45, label: 'high', risk_from_later_spills: 0.41}});
  assert.match(plain(run('clearSentence', wet)), /by about Monday morning\. Rain may bring new spills and high risk on Tuesday\.$/);
  // Nothing to say: right now low, no time (a forecast built before the field, a clicked point), a time already past.
  assert.equal(run('clearSentence', spot({clears_at: '2026-10-05T09:10:00+01:00'})), '');
  assert.equal(run('clearSentence', spot({risk: 0.62, label: 'high'})), '');
  assert.equal(run('clearSentence', spot({risk: 0.62, label: 'high', clears_at: '2026-10-04T01:00:00Z', clears_by: 'die-off'})), '');
});

test('the tile follows the day shown, and is left out where there is nothing to say', () => {
  const kirk = {...ILKLEY, site_name: 'KIRKOSWALD WwTW', receiving_watercourse: 'River Eden', status: 1, share: 0.74, spread_over: 4};
  const d = spot({risk: 0.79, label: 'very high', discharging_upstream: 1, source: kirk, clears_at: '2026-10-04T23:26:00+01:00', clears_by: 'die-off'},
    {'2026-10-04': {risk: 0.28, label: 'moderate', source: {...ILKLEY, share: 0.48, spread_over: 6}},
     '2026-10-06': {risk: 0.42, label: 'high', risk_from_later_spills: 0.4, source: {...ILKLEY, share: 0.27, spread_over: 6}}});
  // Today: right now is the higher risk, so its sources; then when it clears, and the later day.
  assert.equal(tile(d), 'Where the risk comes from'
    + 'Most of the risk from sewage spills right now comes from Kirkoswald WwTW on the River Eden, discharging now, 6.0 km upstream, about 5 hours away.'
    + 'If the overflow discharging upstream stops now, the model expects low risk from spills by about Sunday evening. Rain may bring new spills and high risk on Tuesday.');
  assert.equal(tile(d, '2026-10-04'), tile(d));   // today picked is today
  // A later day: its own sources, and no clearing time.
  assert.equal(tile(d, '2026-10-06'), "Where the risk comes fromTuesday's risk from sewage spills is spread over 6 overflows. "
    + 'The largest part, 27%, comes from Ilkley WwTW on the River Wharfe, 6.0 km upstream, about 5 hours away.');
  assert.equal(tile(d, '2026-10-05'), '');   // a low day
  // Today higher than right now: today's sources.
  const calm = spot({risk: 0.16, label: 'moderate', source: kirk}, {'2026-10-04': {risk: 0.28, label: 'moderate', source: ILKLEY}});
  assert.match(tile(calm), /^Where the risk comes fromMost of today's risk/);
  // A spill running far upstream, with today low: right now's sources still, as it is spilling.
  const far = spot({risk: 0.04, label: 'low', discharging_upstream: 1, source: {...kirk, distance_km: 40, travel_h: 22.2, share: 1}});
  assert.equal(tile(far), 'Where the risk comes fromNearly all of the risk from sewage spills right now comes from Kirkoswald WwTW on the River Eden, '
    + 'discharging now, 40.0 km upstream, about 22 hours away.');
  // No fields (a forecast built before them, or a clicked point), nothing upstream, or a failed forecast: no tile.
  assert.equal(tile(spot({risk: 0.62, label: 'high'}, {'2026-10-04': {risk: 0.5, label: 'high'}})), '');
  assert.equal(tile({...d, upstream_summary: {overflows: 0}}), '');
  assert.equal(tile({...d, error: 'forecast failed: x'}), '');
  vm.runInContext('DAY = null', ctx);
});

test('the page draws the tile before the overflows and fills it again for a picked day', () => {
  const at = s => { const i = html.indexOf(s); assert.ok(i >= 0, s); return i; };
  assert.ok(at('h += `<div id="sources-host">${whereFrom(d)}</div>`;') < at('if (d.contributors.length) h += overflowTile(d, total);'));
  assert.ok(at("if (src) src.innerHTML = whereFrom(d);") > at('function showDay(d, iso) {'));
  assert.ok(at('#sources-host:empty { display:none; }') > 0);
  assert.ok(at('function whereFrom(d) {') < at('function overflowTile(d, total) {'));
});
