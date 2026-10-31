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
vm.runInContext(pageDefs(['esc', 'fmt', 'glyph', 'ago', 'agoSpan', 'WT_ROUTES', 'waterEstOk', 'waterEstHow', 'waterEstSay', 'WT_AIR', 'WT_TAIL', 'waterEstMore', 'waterTile']), ctx);
const waterTile = vm.runInContext('waterTile', ctx);

const hoursAgo = h => new Date(Date.now() - h * 3600e3).toISOString();
// As build_site.attach_water_temperature writes it for Friars Meadow on 3 Oct 2026.
const bures = { temp_c: 16.3, observed_at: hoursAgo(2), age_hours: 1.0, quality: 'Unchecked', station: 'Bures Mill',
  where: 'at Bures Mill', river: 'Stour', station_id: 'E02254A', url: 'https://environment.data.gov.uk/hydrology/station/E02254A',
  distance_km: 8.1, direction: 'downstream', river_km: 10.9 };

test('a reading is shown with where the sensor is, how far along the river and how old it is', () => {
  const t = waterTile(bures), plain = x => x.replace(/<span data-ago="\d+">([^<]*)<\/span>/g, '$1');
  assert.equal(t.label, 'Water temperature');
  assert.equal(t.fig, '16°');
  assert.equal(t.unit, 'C');
  assert.equal(plain(t.say), 'Measured at Bures Mill on the Stour, 10.9&nbsp;km downstream, 2 h ago.');
  assert.match(t.say, /<span data-ago="\d+">2 h<\/span> ago\./);   // moved on while the page is open (stillCurrent)
  assert.match(t.more, /not yet checked/);
  assert.match(t.more, /href="https:\/\/environment\.data\.gov\.uk\/hydrology\/station\/E02254A"/);
  assert.match(t.more, /Not part of the pollution level\./);
  assert.match(waterTile({ ...bures, direction: 'upstream', river_km: 3, where: 'below Wharncliffe WwTW', river: 'Don' }).say,
    /^Measured below Wharncliffe WwTW on the Don, 3\.0&nbsp;km upstream, /);
});

test('the age is counted when the page is read, not when it was built', () => {
  assert.match(waterTile({ ...bures, observed_at: hoursAgo(26) }).say, /, <span data-ago="\d+">26 h<\/span> ago\.$/);
  assert.match(waterTile({ ...bures, observed_at: hoursAgo(0.5) }).say, /, <span data-ago="\d+">30 min<\/span> ago\.$/);
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
  assert.match(t.say, /^Measured at Bures Mill on the Stour, 10\.9&nbsp;km downstream, <span data-ago="\d+">2 h<\/span> ago\. At the spot: about 17&nbsp;°C \(estimated, typically within 2&nbsp;°C\)\.$/);
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

test('the visible conditions summary retains measurement context and states missing readings', () => {
  const c = vm.createContext({waterTile: () => ({fig: '16°', unit: 'C', live: true, say: 'Measured at Bures Mill, 10.9 km downstream, 2 h ago.'}), riverTile: () => null});
  vm.runInContext(pageDefs(['conditionsSummary']), c);
  const summary = vm.runInContext('conditionsSummary', c);
  const h = summary({kind: 'river'});
  assert.match(h, /Measured at Bures Mill, 10.9 km downstream, 2 h ago/);
  assert.match(h, /warmer or colder than at the sensor/);
  assert.match(h, /River level:<\/b> No gauge reading available/);
  assert.match(summary({kind: 'lake'}), /Lake level:<\/b> No gauge reading available/);
});

test('the conditions summary does not show an old gauge as current', () => {
  let seen;
  const c = vm.createContext({waterTile: () => null, riverTile: rs => { seen = rs; return null; }});
  vm.runInContext(pageDefs(['conditionsSummary']), c);
  vm.runInContext('conditionsSummary', c)({kind: 'river', river_state: {observed_at: hoursAgo(48), stale: false, level_m: 1}});
  assert.equal(seen.stale, true);
  assert.ok(seen.age_hours >= 48);
});

test('the conditions summary writes a temperature as 10°C, a level as 0.35 m', () => {
  const c = vm.createContext({waterTile: () => ({fig: '10°', unit: 'C', say: ''}), riverTile: () => ({fig: '0.35', unit: 'm', say: ''})});
  vm.runInContext(pageDefs(['conditionsSummary']), c);
  const h = vm.runInContext('conditionsSummary', c)({kind: 'river'});
  assert.match(h, /Water temperature:<\/b> 10°C\./);
  assert.match(h, /River level:<\/b> 0\.35 m\./);
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

