// Conditions for your outing (src/dipcast/site/outing.js, outingConditions): the water's temperature, the river's level
// and its trend, the day's air, wind and daylight and the rain, each at the resolution it really has, and each
// said as measured, an estimate, stale or not known (index.html, valueTag).
const {test} = require('node:test');
const assert = require('node:assert/strict');
const L = require('../src/dipcast/site/levels.js');
const O = require('../src/dipcast/site/outing.js');
L.setToday('2026-11-02');   // a Monday
const NOW = Date.parse('2026-11-02T02:00:00Z');

const RS = {station: 'Addingham', river: 'River Wharfe', level_m: 0.41, typical_low_m: 0.19, typical_high_m: 1.87, label: 'low',
  observed_at: '2026-11-01T23:45:00Z', stale: false, same_river: true, rise_6h_m: -0.012, rise_from: '2026-11-01T18:45:00Z', rise_to: '2026-11-01T23:45:00Z'};
const spot = (o = {}) => ({id: 'a', name: 'Bolton Abbey', kind: 'river', river_state: RS,
  weather: {days: [{date: '2026-11-02', tmax: 10, sunrise: '07:09', sunset: '16:31', wind_kmh: 17, gust_kmh: 35}, {date: '2026-11-03', tmax: 12, sunrise: '07:11', sunset: '16:29'}]},
  days: [{date: '2026-11-02', rain_48h_mm: 0.2}, {date: '2026-11-03', rain_48h_mm: 6.4}], ...o});
// index.html's waterTile and riverTile, as they answer for this spot.
const EST = {fig: '11°', unit: 'C, provisional estimate'};
const LEVEL = {label: 'River level', fig: '0.41', word: 'Low water', vis: ''};
const panel = (c = {}, o = {}) => O.outingConditions([{role: 'Your spot', s: spot(), water: EST, level: LEVEL, ...c}], {day: '2026-11-02', when: '', nowMs: NOW, ...o});
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ');

test('today: the estimate, the reading with its gauge and age, a real trend, the day\'s high, wind and daylight', () => {
  const h = panel(), t = text(h);
  assert.match(t, /Conditions for your outing/);
  assert.match(h, /<span class="vt vt-estimate">Provisional estimate for today<\/span>/);
  assert.match(t, /0\.41 m Low water at Addingham Measured 2 h ago/);
  assert.match(h, /<span class="vt vt-measured">Measured 2 h ago<\/span>/);
  assert.match(t, /Fell 0\.01 m, 18:45 to 23:45/);
  assert.match(t, /Air 10° Forecast high today/);
  assert.match(t, /Wind 11 mph Forecast strongest today Gusts to 22 mph/);
  assert.match(t, /strongest at 10 m above open ground/);
  assert.match(t, /Sunset 16:31 Sunrise 07:09 today/);
  assert.match(t, /Rain 0\.2 mm In the 48 hours to midday today/);
  assert.match(t, /for the whole day, not an hour/);
  assert.match(t, /Weather data by Open-Meteo\.com/);
  assert.doesNotMatch(t, /not forecasts for/);   // today's readings need no caveat about a later day
});

test('a later day: no estimate offered as that day\'s, readings said as the latest, that day\'s weather', () => {
  const t = text(panel({}, {day: '2026-11-03'}));
  assert.match(t, /Water temperature – Not known for tomorrow Today's provisional estimate is about 11°C/);
  assert.match(t, /The water and level readings are the latest measured, not forecasts for tomorrow\./);
  assert.match(t, /Air 12° Forecast high tomorrow/);
  assert.match(t, /Wind – Not known/);   // that day's answer had no wind
  assert.match(t, /Sunset 16:29 Sunrise 07:11 tomorrow/);
  assert.match(t, /6 mm Forecast, in the 48 hours to midday tomorrow/);
});

test('daily figures never carry an hour they do not have', () => {
  const h = panel({}, {when: '14'});
  for (const k of ['Air', 'Wind']) assert.doesNotMatch(text(h.match(new RegExp(`<h4 class="t-lab">${k}</h4>.*?</div>`))[0]), /\d\d:\d\d/);
  assert.doesNotMatch(text(h), /at 14:00|by 14:00/);
});

test('a reading over a day old is stale: no figure, no trend, and when it was read', () => {
  const old = {...RS, observed_at: '2026-10-31T10:00:00Z', rise_from: '2026-10-31T05:00:00Z', rise_to: '2026-10-31T10:00:00Z'};
  assert.equal(O.outingFresh(old, NOW).stale, true);
  assert.equal(O.outingFresh(RS, NOW), RS);
  const h = panel({s: spot({river_state: old}), level: {label: 'River level', fig: '–'}}), t = text(h);
  assert.match(t, /River level – No current reading Last reading at Addingham 40 h ago: too old to use/);
  assert.match(h, /vt-stale/);
  assert.doesNotMatch(t, /Fell|Rose|No change/);
  assert.equal(O.outingTrend({...RS, stale: true}), '');
});

test('a trend only from the gauge\'s own readings; without them it says so', () => {
  const none = {...RS}; delete none.rise_6h_m;
  assert.match(text(panel({s: spot({river_state: none})})), /No recent trend from this gauge/);
  assert.match(text(panel({s: spot({kind: 'lake', river_state: {...none, water: 'lake'}}), level: {...LEVEL, label: 'Lake level'}})), /No trend is read for a lake/);
  assert.equal(O.outingTrend({...RS, rise_6h_m: 0.004}), 'No change to the centimetre, 18:45 to 23:45');
  assert.equal(O.outingTrend({...RS, rise_6h_m: 0.25}), 'Rose 0.25&nbsp;m, 18:45 to 23:45');
});

test('missing data said as missing, never as a value', () => {
  const t = text(panel({s: spot({weather: undefined, days: []}), water: null, level: null}));
  assert.match(t, /Water temperature – No reading/);
  assert.match(t, /River level – No gauge/);
  assert.match(t, /Air – Not known/);
  assert.match(t, /Wind – Not known/);
  assert.match(t, /Sunset – Not known/);
  assert.doesNotMatch(t, /mph|°/);
  assert.doesNotMatch(t, /Rain/);
  assert.doesNotMatch(t, /Open-Meteo/);   // no weather shown, no credit
  assert.match(text(panel({water: {fig: '–', unit: 'not estimated today'}})), /Water temperature – Not known Not estimated today/);
});

test('a measured water temperature keeps the reading\'s own where and when', () => {
  const t = text(panel({water: {live: true, fig: '9°', say: 'Measured at Ilkley on the River Wharfe, 2.1&nbsp;km upstream, 3 h ago. At the spot: about 11.'}}));
  assert.match(t, /Water temperature 9° Measured at Ilkley on the River Wharfe, 2\.1 km upstream, 3 h ago/);
  assert.doesNotMatch(t, /At the spot/);
});

test('the picked time against daylight', () => {
  assert.equal(O.outingDark('evening', '07:09', '16:31'), 'All of the time you picked is after sunset');
  assert.equal(O.outingDark('afternoon', '07:09', '16:31'), 'Part of the time you picked is after sunset');
  assert.equal(O.outingDark('morning', '07:09', '16:31'), 'Part of the time you picked is before sunrise');
  assert.equal(O.outingDark('06', '07:09', '16:31'), 'All of the time you picked is before sunrise');
  assert.equal(O.outingDark('12', '07:09', '16:31'), '');
  assert.equal(O.outingDark('', '07:09', '16:31'), '');
  assert.equal(O.outingDark('evening', '', ''), '');
});

test('in the outing tile: one panel with a group for each chosen spot, none without a spot', () => {
  const base = {day: '2026-11-02', when: '', spot: 'a', groups: [], backupGroups: [], missing: [], issued: 'x', open: true, nowMs: NOW,
    main: {id: 'a', name: 'Bolton Abbey', href: '#', tone: 'low', headline: 'Low risk'}, alt: {id: 'b', name: 'Cromwheel', href: '#', tone: 'high', headline: 'High risk'}};
  assert.doesNotMatch(O.outingSection(base), /outing-cond/);
  const h = O.outingSection({...base, cond: [{role: 'Your spot', s: spot(), water: EST, level: LEVEL}, {role: 'Backup', s: spot({name: 'Cromwheel'}), water: null, level: null}]});
  assert.equal((h.match(/class="outing-cond"/g) || []).length, 1);
  assert.match(text(h), /Your spot: Bolton Abbey .*Backup: Cromwheel/);
  assert.ok(h.indexOf('outing-cond') < h.indexOf('A lower forecast level does not mean safe water'));
});
