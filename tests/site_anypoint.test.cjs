// Click anywhere (src/dipcast/site/anypoint.js) against the Python it follows. Two fixtures:
//  - anypoint_spot.json: a listed spot's forecast from forecast_point and its inputs
//    (tests/fixtures/make_anypoint_spot.py); the page's arithmetic must give the same days to
//    three decimals;
//  - anypoint_synthetic.json: a small network's published files and what the API traced for
//    clicks on it (tests/test_anypoint.py, which also checks the fixture against the API).
// On its own: node --test tests/site_anypoint.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const A = require('../src/dipcast/site/anypoint.js');

const fixture = name => JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', name), 'utf8'));
const near = (a, b, tol, what) => assert.ok(Math.abs(a - b) <= tol, `${what}: ${a} against ${b}`);

test('the page\'s transport arithmetic gives a listed spot\'s forecast to three decimals', () => {
  const fx = fixture('anypoint_spot.json');
  const got = A.forecast(fx.rows, fx.od, fx.cal);
  assert.equal(got.days.length, fx.expect.days.length);
  got.days.forEach((d, k) => {
    const want = fx.expect.days[k];
    assert.equal(d.date, want.date);
    assert.equal(d.risk === null, want.risk === null, `${d.date}: a figure on one side only`);
    if (want.risk !== null) near(d.risk, want.risk, 0.0005 + 1e-9, `${d.date} risk`);
    assert.equal(d.label, want.label, d.date);
    assert.equal(d.data_status, want.data_status, d.date);
    if (want.expected_spilling_overflows !== null) near(d.expected_spilling_overflows, want.expected_spilling_overflows, 0.05 + 1e-9, `${d.date} spilling`);
  });
  near(got.now.risk, fx.expect.now.risk, 0.0005 + 1e-9, 'right now');
  for (const k of ['discharging_upstream', 'recent_upstream', 'monitored_upstream', 'feed_down_upstream']) assert.equal(got.now[k], fx.expect.now[k], k);
  assert.equal(got.upstream_summary.overflows, fx.expect.upstream_summary.overflows);
  assert.equal(got.upstream_summary.history_days, fx.expect.upstream_summary.history_days);
  near(got.upstream_summary.sum_weight, fx.expect.upstream_summary.sum_weight, 0.0005 + 1e-9, 'sum of weights');
});

test('the calibration follows numpy.interp, flat beyond the knots, and keeps an unknown unknown', () => {
  const c = { iso_x: [0, 0.1, 1], iso_y: [0.01, 0.2, 0.9] };
  near(A.calibrate(0.05, c), 0.105, 1e-12, 'between knots');
  assert.equal(A.calibrate(-1, c), 0.01);
  assert.equal(A.calibrate(2, c), 0.9);
  assert.ok(Number.isNaN(A.calibrate(NaN, c)));
  // A spill a day and a half upstream lands half on each of the next two days (transport.shift_by_travel).
  assert.deepEqual(A.shiftByTravel([[1, 0, 0, 0]], [36]), [[0, 0.5, 0.5, 0]]);
  assert.equal(A.historyDays([]), 1);
  assert.equal(A.historyDays([33.3]), 3);
});

// The synthetic network's files, as the page would fetch them.
const syn = fixture('anypoint_synthetic.json');
const files = (() => {
  const tiles = {};
  for (const [k, t] of Object.entries(syn.files.tiles)) {
    const b = Buffer.from(t.index, 'base64');
    tiles[k] = { index: A.decodeIndex(b.buffer.slice(b.byteOffset, b.byteOffset + b.length)), links: t.links };
  }
  return { cfg: syn.files.cfg, lakes: syn.files.lakes, od: syn.files.od, tiles };
})();
const placeAt = c => {
  const keys = A.lakePolygon(c.lat, c.lon, files.lakes, files.cfg.lake_shore_m) ? [] : A.squares(c.lat, c.lon, files.cfg);
  return A.place(c.lat, c.lon, { ...files, tiles: Object.fromEntries(keys.map(k => [k, files.tiles[k]])) });
};

test('a click goes where the API puts it, and gets the API\'s overflows, distances and dilutions', () => {
  let rows = 0;
  for (const c of syn.clicks.filter(x => x.what !== 'the lonely pool')) {
    const got = placeAt(c);
    assert.equal(got.mode, c.mode, c.what);
    if (c.mode === 'none') { assert.match(got.error, /No river or lake within 1\.5 km/, c.what); continue; }
    assert.equal(got.location.watercourse, c.watercourse, c.what);
    assert.equal(!!got.location.adopted_main_channel, c.adopted, `${c.what}: moved to the main channel`);
    const mine = got.rows.map(r => ({ ...r, site_id: syn.files.ids[r.i] })).sort((a, b) => a.site_id.localeCompare(b.site_id));
    const want = [...c.rows].sort((a, b) => a.site_id.localeCompare(b.site_id));
    assert.deepEqual(mine.map(r => r.site_id), want.map(r => r.site_id), c.what);
    mine.forEach((r, k) => {
      // Distances in tens of metres, the click's place along a line simplified to 30 m.
      near(r.dist, want[k].distance_m, 6, `${c.what} ${r.site_id} distance`);
      near(r.dlake, want[k].lake_distance_m, 3, `${c.what} ${r.site_id} across the lake`);
      near(r.dil, want[k].dilution, 1e-3, `${c.what} ${r.site_id} dilution`);
      rows++;
    });
  }
  assert.ok(rows > 50, `${rows} rows compared`);
});

test('a click in a lake with no river connection says so', () => {
  const got = placeAt(syn.clicks.find(x => x.what === 'the lonely pool'));
  assert.equal(got.mode, 'isolated');
  assert.equal(got.name, 'Lonely Pool');
  assert.match(got.error, /^An isolated lake with no river connection/);
});

test('a click outside every square with data says there is no data there', () => {
  const got = A.place(52.0, -4.0, { ...files, tiles: {} });
  assert.equal(got.mode, 'none');
  assert.match(got.error, /England only/);
});

// Wales and Scotland as the build publishes them (data/raw/outside_england.json). The squares near
// the border have files, so before this a click on the Taff in Cardiff found no overflow upstream and
// said "No sewage risk from monitored overflows" (live site, 3 Oct 2026).
const outside = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'raw', 'outside_england.json'), 'utf8'));
test('a click in Wales or Scotland says England only, even where the squares have files', () => {
  const away = { 'Taff in Cardiff': [51.48, -3.18], 'Usk at Abergavenny': [51.82, -3.02], 'Dee at Llangollen': [52.97, -3.17],
    'Wye at Hay': [52.075, -3.125], 'Monnow at Monmouth': [51.81, -2.715], 'Tweed at Kelso': [55.60, -2.43], 'Esk at Langholm': [55.15, -2.99] };
  const home = { 'Wharfe at Burnsall': [54.047, -1.953], 'Dee at Chester': [53.19, -2.89], 'Wye at Hereford': [52.05, -2.715],
    'Tweed at Berwick': [55.77, -2.005], 'Eden at Carlisle': [54.90, -2.93], 'Severn off Lydney': [51.70, -2.50], 'Thames at Richmond': [51.46, -0.31] };
  for (const [what, [lat, lon]] of Object.entries(away)) assert.equal(A.outsideEngland(lat, lon, outside), true, what);
  for (const [what, [lat, lon]] of Object.entries(home)) assert.equal(A.outsideEngland(lat, lon, outside), false, what);
  const c = syn.clicks.find(x => x.mode === 'river');
  const shape = { geometry: { coordinates: [[[[c.lon - 0.1, c.lat - 0.1], [c.lon + 0.1, c.lat - 0.1], [c.lon + 0.1, c.lat + 0.1], [c.lon - 0.1, c.lat + 0.1]]]] } };
  const got = A.place(c.lat, c.lon, { ...files, outside: shape });
  assert.equal(got.mode, 'none');
  assert.match(got.error, /England only/);
  assert.equal(A.place(c.lat, c.lon, { ...files, outside }).mode, 'river');   // the synthetic river is not in Wales
});

// The island of Ireland, in the same file. SwimSignal's river network has no link there and it reads
// no Irish overflow data, so before this a click in Belfast or Dublin found no square and said "No river
// or lake near this point has a monitored storm overflow within 60 km upstream" (live site, 4 Oct 2026).
// Each place below was checked against the source boundaries themselves (ONS for Northern Ireland,
// Tailte Éireann for the Republic), with how far it is from the border where that is close.
const NI = { 'Lagan in Belfast': [54.5866, -5.9295], 'Erne at Enniskillen': [54.3448, -7.6385], 'Foyle at Derry': [54.9966, -7.3190],
  'Strabane, east of the Foyle (1.1 km from the border)': [54.8265, -7.4610], 'Belleek, on the Erne (400 m from the border)': [54.4770, -8.0850],
  'Belfast Lough': [54.69, -5.78], 'the middle of Lough Foyle (4.9 km from Northern Ireland, 6.3 km from the Republic)': [55.10, -7.10] };
const ROI = { 'Liffey in Dublin': [53.3461, -6.2733], 'Shannon at Athlone': [53.4239, -7.9407], 'Lough Derg at Mountshannon': [52.9293, -8.42816],
  'Lifford, west of the Foyle (450 m from the border)': [54.8340, -7.4870], 'Ballyshannon, on the Erne': [54.5025, -8.1880],
  'Galway': [53.274, -9.049], 'Dingle': [52.1408, -10.2686], 'Dublin Bay': [53.33, -6.13] };
test('a click in Northern Ireland or the Republic says England only and names the official source there', () => {
  for (const [what, [lat, lon]] of Object.entries(NI)) assert.equal(A.outsideWhere(lat, lon, outside), 'northern_ireland', what);
  for (const [what, [lat, lon]] of Object.entries(ROI)) assert.equal(A.outsideWhere(lat, lon, outside), 'republic_of_ireland', what);
  const ni = A.place(54.5866, -5.9295, { ...files, tiles: {}, outside });
  assert.equal(ni.mode, 'none');
  assert.equal(ni.outside, 'northern_ireland');
  assert.equal(ni.error, 'SwimSignal has overflow data for England only, so it has no forecast in Northern Ireland.');
  const roi = A.place(53.3461, -6.2733, { ...files, tiles: {}, outside });
  assert.equal(roi.error, 'SwimSignal has overflow data for England only, so it has no forecast in the Republic of Ireland.');
  assert.match(A.OUTSIDE.northern_ireland.see, /href="https:\/\/www\.daera-ni\.gov\.uk\/articles\/bathing-water-quality-dashboard"/);
  assert.match(A.OUTSIDE.republic_of_ireland.see, /href="https:\/\/www\.beaches\.ie\/"/);
  // Nothing about the water itself: no level, no "no overflow", no "clean".
  for (const w of Object.values(A.OUTSIDE)) assert.doesNotMatch(w.error + w.see, /no sewage|no overflow|clean|safe|low risk/i);
});

test('Wales, Scotland and England keep their answers beside the Irish part', () => {
  const gb = { 'Taff in Cardiff': [51.48, -3.18], 'Tweed at Kelso': [55.60, -2.43], 'Kintyre, 23 km from the island of Ireland': [55.30, -5.75],
    'Portpatrick': [54.84, -5.12] };
  for (const [what, [lat, lon]] of Object.entries(gb)) assert.equal(A.outsideWhere(lat, lon, outside), 'wales_scotland', what);
  assert.equal(A.place(51.48, -3.18, { ...files, tiles: {}, outside }).error, 'SwimSignal has overflow data for England only, so it has no forecast here.');
  // Not the Environment Agency's sentence, which is about England: the coverage page's links to NRW and SEPA.
  assert.match(A.OUTSIDE.wales_scotland.see, /Natural Resources Wales and the Scottish Environment Protection Agency .*href="coverage\.html"/);
  for (const [lat, lon] of [[54.047, -1.953], [55.77, -2.005], [51.70, -2.50], [51.46, -0.31], [54.0, -2.0]]) assert.equal(A.outsideWhere(lat, lon, outside), '');
  // A file from before Ireland was added has no parts: all of it is Wales and Scotland.
  const old = { geometry: { coordinates: [[[[-4, 52], [-3, 52], [-3, 53], [-4, 53]]]] } };
  assert.equal(A.outsideWhere(52.5, -3.5, old), 'wales_scotland');
  assert.equal(A.outsideWhere(52.5, -2.5, old), '');
  assert.equal(A.outsideWhere(52.5, -3.5, null), '');
});

test('a click in England with no square near says no overflow is upstream, not England only', () => {
  const got = A.place(54.0, -2.0, { ...files, tiles: {}, outside });
  assert.equal(got.mode, 'none');
  assert.equal(got.error, 'No river or lake near this point has a monitored storm overflow within 60 km upstream, so SwimSignal has no sewage spills to forecast here.');
});

test('a point with no overflow upstream gets the API\'s answer: every day zero, nothing upstream', () => {
  const od = { today: 1, days: ['2026-10-02', '2026-10-03', '2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07'], scale: 1000,
    p: [], live: [], status: [], company: [], companies: [], low: [],
    assumptions: { river_velocity_ms: 0.5, lake_velocity_ms: 0.05, t90_hours: 30, low_confidence_factor: 0.7, max_missing_share: 0.1 } };
  const got = A.forecast([], od, {});
  assert.deepEqual(got.days.map(d => [d.date, d.risk, d.label]), od.days.slice(1).map(d => [d, 0, 'low']));
  assert.equal(got.upstream_summary.overflows, 0);
});
