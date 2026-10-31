// The Water temperature tile (index.html, waterTile), run in Node beside levels.js as in the browser:
// a reading is shown only with where the sensor is, how far along the river, and how old it is now.
// On its own: node --test tests/site_water_temp.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');

// Top-level definitions taken from index.html's script (as site_planner.test.cjs takes them): a
// definition runs from its first line to the next line at the margin that does not close it.
const pageSrc = (() => { const html = fs.readFileSync(join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  return html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n'); })();
function pageDefs(names) {
  return names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
    assert.ok(i >= 0, `no ${n} in index.html`);
    let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
    return pageSrc.slice(i, j).join('\n'); }).join('\n');
}
const ctx = vm.createContext({});
vm.runInContext(fs.readFileSync(join(__dirname, '../src/dipcast/site/levels.js'), 'utf8'), ctx);
vm.runInContext(pageDefs(['esc', 'fmt', 'glyph', 'ago', 'WT_ROUTES', 'waterEstOk', 'waterEstHow', 'waterEstSay', 'WT_AIR', 'WT_TAIL', 'waterEstMore', 'waterTile']), ctx);
const waterTile = vm.runInContext('waterTile', ctx);

const hoursAgo = h => new Date(Date.now() - h * 3600e3).toISOString();
// As build_site.attach_water_temperature writes it for Friars Meadow on 3 Oct 2026.
const bures = { temp_c: 16.3, observed_at: hoursAgo(2), age_hours: 1.0, quality: 'Unchecked', station: 'Bures Mill',
  where: 'at Bures Mill', river: 'Stour', station_id: 'E02254A', url: 'https://environment.data.gov.uk/hydrology/station/E02254A',
  distance_km: 8.1, direction: 'downstream', river_km: 10.9 };

test('a reading is shown with where the sensor is, how far along the river and how old it is', () => {
  const t = waterTile(bures);
  assert.equal(t.label, 'Water temperature');
  assert.equal(t.fig, '16°');
  assert.equal(t.unit, 'C');
  assert.equal(t.say, 'Measured at Bures Mill on the Stour, 10.9&nbsp;km downstream, 2 h ago.');
  assert.match(t.more, /not yet checked/);
  assert.match(t.more, /href="https:\/\/environment\.data\.gov\.uk\/hydrology\/station\/E02254A"/);
  assert.match(t.more, /Not part of the pollution level\./);
  assert.match(waterTile({ ...bures, direction: 'upstream', river_km: 3, where: 'below Wharncliffe WwTW', river: 'Don' }).say,
    /^Measured below Wharncliffe WwTW on the Don, 3\.0&nbsp;km upstream, /);
});

test('the age is counted when the page is read, not when it was built', () => {
  assert.match(waterTile({ ...bures, observed_at: hoursAgo(26) }).say, /, 26 h ago\.$/);
  assert.match(waterTile({ ...bures, observed_at: hoursAgo(0.5) }).say, /, 30 min ago\.$/);
});

test('without a distance along the river, a direction or a time, nothing is shown', () => {
  assert.equal(waterTile(null), null);
  assert.equal(waterTile(undefined), null);
  assert.equal(waterTile({ ...bures, river_km: null }), null);
  assert.equal(waterTile({ ...bures, direction: null }), null);
  assert.equal(waterTile({ ...bures, observed_at: null }), null);
  assert.equal(waterTile({ ...bures, temp_c: null }), null);
});

test('only the Environment Agency is linked, and the words are escaped', () => {
  assert.doesNotMatch(waterTile({ ...bures, url: 'https://example.org/x' }).more, /href=/);
  assert.match(waterTile({ ...bures, where: 'at <b>Mill</b>' }).say, /at &lt;b&gt;Mill&lt;\/b&gt;/);
  assert.doesNotMatch(waterTile({ ...bures, quality: 'Good' }).more, /not yet checked/);
});

// The estimate (build_site.attach_water_temperature_estimate): river spots, May to September, for one day.
const setToday = vm.runInContext('setToday', ctx);
const est = { temp_c: 17, within_c: 2.0, date: '2026-07-14' };

test('a river spot with no sensor shows the estimate, said as an estimate, with its typical error', () => {
  setToday('2026-07-14');
  const t = waterTile(null, est, 'river');
  assert.equal(t.label, 'Water temperature');
  assert.equal(t.fig, '17°');
  assert.equal(t.unit, 'C, estimated');
  assert.equal(t.say, 'About 17&nbsp;°C (estimated, typically within 2&nbsp;°C).');
  assert.ok(!t.live);
  assert.match(t.more, /not a measurement/);
  assert.match(t.more, /weather model's air temperature/);
  assert.match(t.more, /today's forecast itself was not checked/);
  assert.doesNotMatch(t.more, /air temperature here/);
  assert.match(t.more, /Not part of the pollution level\./);
  assert.doesNotMatch(t.more, /no estimate for lakes/);   // lakes have their own provisional route since 30 Oct 2026 (#492)
  setToday(null);
});

test('with a sensor, the reading comes first and the estimate after it, in the same tile', () => {
  setToday('2026-07-14');
  const t = waterTile(bures, est, 'river');
  assert.equal(t.fig, '16°');
  assert.ok(t.live);
  assert.match(t.say, /^Measured at Bures Mill on the Stour, 10\.9&nbsp;km downstream, 2 h ago\. At the spot: about 17&nbsp;°C \(estimated, typically within 2&nbsp;°C\)\.$/);
  assert.match(t.more, /not a measurement/);
  setToday(null);
});

test('never on the sea, never on another day, never without its figures', () => {
  setToday('2026-07-14');
  assert.equal(waterTile(null, est, 'sea'), null);
  assert.equal(waterTile(null, est), null);                                        // kind unknown
  assert.equal(waterTile(null, { ...est, date: '2026-07-13' }, 'river'), null);   // a page built yesterday
  assert.equal(waterTile(null, { ...est, temp_c: null }, 'river'), null);
  assert.equal(waterTile(null, { ...est, within_c: undefined }, 'river'), null);   // a route-less file needs its figure
  assert.equal(waterTile(null, { ...est, route: 'sea_model' }, 'river'), null);    // a route this page does not know
  assert.doesNotMatch(waterTile(bures, est, 'lake').say, /estimated/);             // the reading stays
  setToday(null);
});

// #492 (Ethan, 30 October 2026): every river and lake spot, all year, each route worded by what was measured for it.
test('a lake in summer: a provisional estimate with the error its summer test measured, and that the lake test failed', () => {
  setToday('2026-07-14');
  const t = waterTile(null, { temp_c: 18, date: '2026-07-14', route: 'lake_model', tested: false, typical_c: 1.70 }, 'lake');
  assert.equal(t.unit, 'C, provisional estimate');
  assert.equal(t.say, 'About 18&nbsp;°C (provisional estimate; typical error 1.7&nbsp;°C at lakes in a summer test).');
  assert.match(t.more, /did not pass its test/);
  assert.match(t.more, /lakes under 1&nbsp;km² the typical error was 1\.7&nbsp;°C/);
  const big = waterTile(null, { temp_c: 17, date: '2026-07-14', route: 'lake_curve', tested: false, typical_c: 1.98 }, 'lake');
  assert.match(big.more, /lakes of 1&nbsp;km² or more the typical error was 2\.0&nbsp;°C/);
  setToday(null);
});

test('October to April: a provisional estimate said to be not yet checked in these months, with no error claimed', () => {
  setToday('2026-10-31');
  for (const [kind, route] of [['river', 'river_off_season'], ['lake', 'lake_off_season']]) {
    const t = waterTile(null, { temp_c: 11, date: '2026-10-31', route, tested: false, typical_c: null }, kind);
    assert.equal(t.say, 'About 11&nbsp;°C (provisional estimate, not yet checked in these months).');
    assert.match(t.more, /has not been checked from October to April/);
    assert.match(t.more, /being compared with the Environment Agency's water sensors/);
    assert.doesNotMatch(t.say + t.more, /typically within|typical error was/);   // no error said where none was measured
  }
  // With a sensor, the measurement first; the estimate after it, in its own words.
  const s = waterTile(bures, { temp_c: 11, date: '2026-10-31', route: 'river_off_season' }, 'river');
  assert.match(s.say, /^Measured at Bures Mill .* At the spot: about 11&nbsp;°C \(provisional estimate, not yet checked in these months\)\.$/);
  setToday(null);
});

test('no estimate because its inputs did not arrive: said, not left blank, and never an old one', () => {
  setToday('2026-10-31');
  const t = waterTile(null, null, 'lake', { why: 'air', date: '2026-10-31' });
  assert.equal(t.fig, '–');
  assert.match(t.say, /^No estimate in this update/);
  assert.equal(waterTile(null, null, 'lake', { why: 'air', date: '2026-10-30' }), null);   // a gap from another day
  assert.equal(waterTile(null, null, 'sea', { why: 'air', date: '2026-10-31' }), null);
  setToday(null);
});


// #492 stage 2: a clicked river or lake point (anypoint.js, waterAt), from the nearest cached cell's 7-day air.
const A = require('../src/dipcast/site/anypoint.js');
const WA = { date: '2026-10-31', cells: { '54.4,-2.9': 9.31 }, months: [5, 6, 7, 8, 9], typical_c: { river: 1.85, lake: 1.93 },
  curves: { river: [-0.41166947693946565, 34.999999993691574, 18.3677886247391, 0.08066342666976217], lake: [-0.08307401472541856, 34.999999999992696, 14.660334045119965, 0.10187070075502881] } };

test('a clicked point: the curve on the nearest cell, its distance, and no error claimed outside May to September', () => {
  const own = A.waterAt({ water_air: WA }, 54.38, -2.92, 'lake').est;
  assert.deepEqual(own, { temp_c: 13, date: '2026-10-31', route: 'lake_air_curve', tested: false, typical_c: null, air_7d_c: 9.3, air_km: 0 });
  const next = A.waterAt({ water_air: WA }, 54.5, -2.8, 'river').est;   // the square next to the point's
  assert.equal(next.route, 'river_air_curve'); assert.equal(next.air_km, 13);
  assert.deepEqual(A.waterAt({ water_air: WA }, 52.0, -1.0, 'river'), { miss: { why: 'air', date: '2026-10-31' } });   // no cell near
  assert.deepEqual(A.waterAt({ water_air: WA }, 54.4, -2.9, 'coast'), {});   // not a river or lake: its own route (#479)
  assert.deepEqual(A.waterAt({}, 54.4, -2.9, 'river'), {});                 // a file from before stage 2
  // In the months it was tested in, the curve alone's measured error.
  assert.equal(A.waterAt({ water_air: { ...WA, date: '2026-07-14' } }, 54.4, -2.9, 'river').est.typical_c, 1.85);
});

test('a clicked point on the page: said as a provisional estimate for an unlisted point, with the area\'s distance', () => {
  setToday('2026-10-31');
  const t = waterTile(null, { temp_c: 11, date: '2026-10-31', route: 'river_air_curve', tested: false, typical_c: null, air_km: 13 }, 'river');
  assert.equal(t.say, 'About 11&nbsp;°C (provisional estimate, not yet checked in these months).');
  assert.match(t.more, /for a point that is not a listed spot/);
  assert.match(t.more, /nearest this point, about 13&nbsp;km away/);
  assert.doesNotMatch(t.more, /typically [0-9.]+&nbsp;°C out/);
  setToday('2026-07-14');
  const s = waterTile(null, { temp_c: 17, date: '2026-07-14', route: 'lake_air_curve', tested: false, typical_c: 1.93, air_km: 0 }, 'lake');
  assert.equal(s.say, 'About 17&nbsp;°C (provisional estimate; typical error 1.9&nbsp;°C at lakes in a summer test).');
  assert.match(s.more, /typically 1\.9&nbsp;°C out/);
  setToday(null);
});
