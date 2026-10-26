// Catchment replay (src/dipcast/site/replay.js, prototype): reported spills in words as observed, arrivals
// always labelled as estimates, gaps never drawn over, no causal words, and the page unchanged without
// ?replay=1. The data step is tests/test_replay.py.
// node --test tests/site_replay.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
global.overflowNames = L.overflowNames;
global.companyName = L.companyName;
const R = require('../src/dipcast/site/replay.js');

// 25 Oct 2026, after the clocks went back: UK time is UTC.
const replay = (extra = {}) => ({
  id: 'x', window: { from: '2026-10-23T22:00Z', to: '2026-10-25T22:00Z', hours: 48, ahead_to: '2026-10-26T04:00Z' }, counted: 4,
  overflows: [
    { site_id: 'YWS00199', name: 'POOL/STW/3XDWF OVERFLOW', company: 'Yorkshire Water', km: 20.5, travel_h: 28.5, weight: 0.36, state: 'live', status: 0,
      spills: [{ start: '2026-10-24T17:04Z', end: '2026-10-24T20:51Z', running: false, end_known: true,
        arrival: { from: '2026-10-25T21:34Z', to: '2026-10-26T01:21Z', state: 'at_spot' } }], earlier_spills: 0, offline: [] },
    { site_id: 'A2', name: 'BRIDGE LANE/CSO', company: 'Yorkshire Water', km: 3.1, travel_h: 0.4, weight: 0.8, state: 'live', status: 1,
      spills: [{ start: '2026-10-25T21:00Z', end: null, running: true, end_known: false,
        arrival: { from: '2026-10-25T21:24Z', to: null, state: 'at_spot' } }], earlier_spills: 0, offline: [] },
    { site_id: 'A3', name: 'MILL ROAD/CSO', company: 'Dwr Cymru Welsh Water', km: 8, travel_h: 9, weight: 0.3, state: 'offline', status: -1,
      spills: [{ start: '2026-10-25T06:00Z', end: null, running: false, end_known: false,
        arrival: { from: '2026-10-25T15:00Z', to: null, state: 'unknown_end' } }], earlier_spills: 2,
      offline: [{ from: '2026-10-25T08:00Z', to: null }] },
  ],
  more_with_events: 0, quiet: { live: { n: 2, weight: 0.4 }, offline: { n: 1, weight: 0.1 } },
  rain: { start: '2026-10-23T22:00Z', step_h: 1, mm: Array.from({ length: 48 }, (_, i) => (i === 5 ? null : i >= 46 ? 2 : i % 7 === 0 ? 1.2 : 0)),
    cells: 3, issued_at: '2026-10-25T20:10Z', forecast_from: '2026-10-25T21:00Z' },
  gauge: { station: 'Flint Mill', level_m: 1.522, observed_at: '2026-10-25T21:15:00Z', stale: false, rise_6h_m: 0.154, rise_from: '2026-10-25T17:00:00Z' },
  ...extra,
});

test('a reported spill is said as reported, and its arrival as a modelled estimate', () => {
  const t = R.replaySpillSaid(replay().overflows[0].spills[0]);
  assert.equal(t, 'Reported spilling Sat 18:04 to Sat 21:51. Modelled to reach the spot around Sun 21:34 to Mon 01:21 (estimate; arriving now).');
  const run = R.replaySpillSaid(replay().overflows[1].spills[0]);
  assert.match(run, /^Reported spilling since Sun 21:00, still discharging at the last reading\. Modelled to reach the spot from around Sun 21:24 \(estimate; still arriving\)\.$/);
});

test('an end the feed never gave is said to be unknown, and nothing is drawn after the start', () => {
  const r = replay(), s = r.overflows[2].spills[0];
  assert.match(R.replaySpillSaid(s), /Its end was not reported\..*\(estimate; when it passed is not known\)/);
  const svg = R.replaySvg({ ...r, overflows: [r.overflows[2]] });
  const spill = svg.match(/<rect [^>]*class="rp-spill"\/>/g);
  assert.equal(spill.length, 1);
  assert.match(spill[0], /width="2\.0"/, "a start mark, not a bar to now");
  assert.match(svg, /end not reported/);
  const arr = svg.match(/<rect [^>]*class="rp-arr"\/>/g);
  assert.match(arr[0], /width="2\.0"|width="1\.5"/, 'an arrival with no end is a start mark too');
  assert.match(R.replayTable(r), /2 earlier spills in these hours not listed\./);
  assert.match(R.replayOfflineSaid(r.overflows[2].offline[0]), /^No reading \(monitor offline\) from Sun 08:00; when it came back is not recorded\.$/);
});

test('water already passed and water still due are told apart', () => {
  const s = { start: '2026-10-24T09:00Z', end: '2026-10-24T10:00Z', running: false, end_known: true };
  assert.match(R.replaySpillSaid({ ...s, arrival: { from: '2026-10-24T12:00Z', to: '2026-10-24T13:00Z', state: 'passed' } }), /\(estimate; passed\)\.$/);
  assert.match(R.replaySpillSaid({ ...s, arrival: { from: '2026-10-26T02:00Z', to: '2026-10-26T03:00Z', state: 'due' } }), /\(estimate; not there yet\)\.$/);
  assert.match(R.replaySpillSaid({ ...s, arrival: null }), /No travel time to the spot is modelled\.$/);
});

test('rain: blank hours are a gap mark, never a bar; forecast hours are marked as forecast', () => {
  const r = replay(), svg = R.replaySvg(r);
  assert.equal((svg.match(/class="rp-gap"/g) || []).length, 1);
  assert.equal((svg.match(/class="rp-rain rp-fc"/g) || []).length, 1, 'the one rain hour after the issue time inside the window');
  const said = R.replayRainSaid(r.rain);
  assert.match(said, /^Model rain averaged over the cells of the overflows upstream \(3 cells of Open-Meteo's grid\): 10\.4 mm in the hours shown\./);
  assert.match(said, /not rain gauges, and not the rainfall over the whole area draining here/);
  assert.match(svg, />Model rain, mean of the overflows' cells, mm\/h</);
  assert.match(said, /1 hour not held, left blank\.$/);
  assert.match(R.replayRainSaid({ unavailable: 'no counted overflow upstream' }), /^Rain: not available here \(no counted overflow upstream\)\.$/);
});

test('the gauge is its current reading and its time, with no rise and no line drawn', () => {
  assert.equal(R.replayGaugeSaid(replay().gauge), 'River level at Flint Mill: 1.52 m at Sun 21:15, the current reading. Earlier readings are not shown.');
  assert.equal(R.replayGaugeSaid({ unavailable: 'no level gauge matched to this spot' }), 'River level: no level gauge matched to this spot.');
  assert.doesNotMatch(R.replaySvg(replay()), /gauge|polyline|<path /);
});

test('overflows with no reading are counted, so silence is not read as no spill', () => {
  assert.equal(R.replayQuietSaid(replay()), '2 other counted overflows with a live reading reported no spill in the polls these hours have. '
    + '1 counted overflow has no current reading, so a spill there would not show here.');
  const q = R.replayQuietSaid(replay({ quiet: { no_history: { n: 2 }, late_history: { n: 1 } }, more_with_events: 3, truncated: true }));
  assert.equal(q, '2 counted overflows have no poll history, so whether they spilled in these hours is not known. '
    + '1 counted overflow first appears in the poll history part way through these hours, so earlier spills there are not known. '
    + '3 more with reported spills or gaps, smaller reach, are left out to keep this small.');
});

test('the tile: names, data states, an accessible drawing and table, and no causal words', () => {
  const html = R.replayTile(replay());
  assert.match(html, /^<details class="tile fold" id="replay" open><summary>/);
  assert.match(html, /<svg class="rp-svg"[^>]*role="img" aria-labelledby="rp-title" aria-describedby="rp-desc"/);
  assert.match(html, /<table class="rp-table"><caption>Reported spills upstream and their modelled arrival here, Fri 23:00 to Sun 22:00<\/caption>/);
  assert.match(html, /<th scope="row">Pool sewage works storm tank overflow<span class="rp-meta">Yorkshire Water · 20\.5 km upstream · about 29 h away \(modelled\) · live reading/);
  assert.match(html, /Bridge Lane storm overflow<span class="rp-meta">Yorkshire Water · 3\.1 km upstream · under an hour away \(modelled\)/);
  assert.match(html, /Dŵr Cymru Welsh Water .* no current reading: the monitor or its feed is not reporting/);
  // The per-overflow details fold under the drawing; the table stays in the page, reached by its summary.
  assert.match(html, /<details class="rp-more"><summary>Details for each overflow \(3\)<\/summary><div class="rp-scroll" tabindex="0" role="region" aria-label="Table of reported spills"><table class="rp-table">/);
  assert.ok(html.indexOf('rp-more') > html.indexOf('</svg>'), 'the details come after the timeline');
  assert.match(html, /<desc id="rp-desc">3 overflows upstream reported spills or gaps in these hours, 1 still discharging at the last reading\. Each is listed under &quot;Details for each overflow&quot;\.<\/desc>/);
  assert.match(html, /<p class="t-say">3 overflows upstream reported spills or gaps in these hours, 1 still discharging/);
  assert.match(html, /reported spilling \(observed\).*modelled to reach the spot \(estimate\).*no reading.*rain not held/);
  assert.doesNotMatch(html, /\bcaus|\bbecause\b|\bresult(ed)? in\b|\bdue to\b|\bpollut/i);
  assert.doesNotMatch(html, /catchment/i, 'the rain is the overflows\' cells, never called catchment rainfall');
  assert.equal(R.replayTile(null), '');
});

test('the drawing marks now, and draws hours ahead only for water still due', () => {
  const svg = R.replaySvg(replay());
  assert.match(svg, /class="rp-now"/);
  assert.match(svg, />Now</);
  const flat = R.replaySvg(replay({ window: { ...replay().window, ahead_to: '2026-10-25T22:00Z' } }));
  const nowX = +flat.match(/<line x1="([\d.]+)"[^>]*class="rp-now"/)[1];
  // With nothing due, the axis still runs 4 h past now (52 h in all), so now sits 4/52 of the width from the edge.
  assert.equal(nowX, +(4 + 48 / 52 * 332).toFixed(1));
  assert.ok(nowX < 320, 'now is clear of the right edge and the rain scale');
  const due = R.replaySvg(replay());   // water due until Mon 04:00, 6 h past now
  assert.equal(+due.match(/<line x1="([\d.]+)"[^>]*class="rp-now"/)[1], +(4 + 48 / 54 * 332).toFixed(1));
});

test('styles use the page tokens only: no new colour, no gradient', () => {
  assert.doesNotMatch(R.REPLAY_CSS, /#[0-9a-f]{3,6}\b|rgb|gradient/i);
  assert.doesNotMatch(R.replayKey(), /gradient/);
});

test('the page is unchanged without ?replay=1: no script tag, a host only behind the flag', () => {
  const page = fs.readFileSync(path.join(__dirname, '..', 'src', 'dipcast', 'site', 'index.html'), 'utf8');
  assert.doesNotMatch(page, /<script src="replay\.js/);
  assert.match(page, /const REPLAY = new URLSearchParams\(location\.search\)\.get\('replay'\) === '1';/);
  assert.match(page, /if \(REPLAY && d\.detail_file\) h \+= '<div id="replay-host"><\/div>';/);
  assert.match(page, /if \(REPLAY\) mountReplay\(d\);/);
  assert.match(page, /document\.querySelector\('script\[src\*="levels\.js\?v="\]'\)/, 'at the build stamp, read off levels.js');
  assert.match(page, /s\.src = `replay\.js\$\{v \? `\?v=\$\{new URL\(v\)\.searchParams\.get\('v'\)\}` : ''\}`;/);
});

test('a real replay from saved state renders (tests/fixtures/replay_ilkley.json, 25 Oct 2026)', () => {
  const r = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'replay_ilkley.json'), 'utf8'));
  const html = R.replayTile(r);
  assert.ok(html.length > 2000);
  assert.match(html, /Pool sewage works storm tank overflow/);
  // Pool, YWS00199: the polls missed its stop (gap from Sat 20:37), so its end is a span, not the feed tail's time.
  assert.match(html, /Reported spilling from Sat 18:04\. It stopped between Sat 20:37, the last poll that saw it discharging, and Sat 21:51/);
  assert.match(html, /Yorkshire Water's feed answered 23 polls/);
});

test('a lake route: reported spills shown, no arrival drawn or timed, and said so', () => {
  const r = replay(), lake = { ...r.overflows[0], lake_route: true, travel_h: null,
    spills: r.overflows[0].spills.map(s => ({ ...s, arrival: null })) };
  assert.equal(R.replaySpillSaid(lake.spills[0], true), 'Reported spilling Sat 18:04 to Sat 21:51. Arrival through the lake not estimated here.');
  const svg = R.replaySvg({ ...r, overflows: [lake] });
  assert.equal((svg.match(/class="rp-spill"/g) || []).length, 1, 'the reported event stays');
  assert.equal((svg.match(/class="rp-arr"/g) || []).length, 0, 'no modelled bar');
  assert.match(svg, />arrival through the lake not estimated here</);
  const table = R.replayTable({ ...r, overflows: [lake] });
  assert.match(table, /20\.5 km upstream · its water passes through a lake on the way · live reading/);
  assert.doesNotMatch(table, /Modelled to reach|h away/);
  // Even if an arrival were in the data, a lake row never draws one.
  assert.equal((R.replaySvg({ ...r, overflows: [{ ...lake, spills: r.overflows[0].spills }] }).match(/class="rp-arr"/g) || []).length, 0);
});

test('the real lake fixture (Windermere, Waterhead, 25 Oct 2026) renders with no arrivals', () => {
  const r = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'replay_waterhead.json'), 'utf8'));
  const html = R.replayTile(r);
  assert.doesNotMatch(html, /class="rp-arr"(?! rp-arr-key)/);
  assert.match(html, /Ambleside sewage works overflow/);
  assert.match(html, /Arrival through the lake not estimated here\./);
  assert.match(html, /For all of them, the water passes through a lake, so its arrival here is not estimated\./);
});

test('an unknown end keeps an open-ended arrival on a river route', () => {
  const s = { start: '2026-10-25T06:00Z', end: null, running: false, end_known: false, arrival: { from: '2026-10-25T15:00Z', to: null, state: 'unknown_end' } };
  assert.match(R.replaySpillSaid(s), /Modelled to reach the spot from around Sun 15:00 \(estimate; when it passed is not known\)\.$/);
});

test('polling is said as it happened: answered polls, the longest gaps, never "every 30 minutes"', () => {
  const cov = { 'Yorkshire Water': { polls: 81, from: '2026-10-24T01:00Z', to: '2026-10-25T21:50Z', starts_late: true,
    gaps: [['2026-10-24T10:00Z', '2026-10-24T14:00Z']], more_gaps: 0 }, 'Dwr Cymru Welsh Water': { polls: 0, gaps: [] } };
  const said = R.replayCoverageSaid(replay({ coverage: cov }));
  assert.match(said, /^Yorkshire Water's feed answered 81 polls, from Sat 02:00 to Sun 21:50\. Nothing was polled before then in these hours\. Its longest gap with no poll: Sat 11:00 to Sat 15:00 \(4 h\)\./);
  assert.match(said, /Dŵr Cymru Welsh Water's feed did not answer a poll in these hours, so its spills then are not known\./);
  assert.match(said, /Events between polls can be missed\.$/);
  assert.match(R.replayCoverageSaid(replay({ coverage: { unavailable: 'no poll log' } })), /^When the feeds were polled is not recorded here, so how complete these hours are is not known\./);
  const html = R.replayTile(replay({ coverage: cov }));
  assert.doesNotMatch(html, /every 30 minutes|continuous|complete record/i);
  assert.match(html, /when SwimSignal polled them; events between polls can be missed/);
  const svg = R.replaySvg(replay({ coverage: cov }));
  assert.ok((svg.match(/class="rp-nopoll"/g) || []).length >= 1, 'the gap is drawn on its company\'s rows');
});

test('an end known only between two polls is said and drawn as a span, not a time', () => {
  const s = { start: '2026-10-25T10:00Z', end: null, running: false, end_known: false, end_after: '2026-10-25T10:20Z', end_by: '2026-10-25T12:00Z',
    arrival: { from: '2026-10-25T12:00Z', to: null, to_after: '2026-10-25T12:20Z', to_by: '2026-10-25T14:00Z', state: 'passed' } };
  assert.equal(R.replaySpillSaid(s), 'Reported spilling from Sun 10:00. It stopped between Sun 10:20, the last poll that saw it discharging, '
    + 'and Sun 12:00, when the feed said it had stopped; the feed was not polled, or the monitor was offline, in between. '
    + 'Modelled to reach the spot from around Sun 12:00, its last water between Sun 12:20 and Sun 14:00 (estimate; passed).');
  const r = replay(), row = { ...r.overflows[0], spills: [s] };
  const svg = R.replaySvg({ ...r, overflows: [row] });
  assert.equal((svg.match(/class="rp-unsure"/g) || []).length, 2, 'the end span and the arrival span, outlined');
  assert.doesNotMatch(svg, /end not reported/);
  const open = { ...s, end_by: undefined, arrival: { from: '2026-10-25T12:00Z', to: null, to_after: '2026-10-25T12:20Z', state: 'unknown_end' } };
  assert.match(R.replaySpillSaid(open), /^Reported spilling from Sun 10:00, still discharging at the poll at Sun 10:20\. Its end was not reported\./);
});

test('an overflow with no poll history, or one that starts late, says so and is drawn as not polled', () => {
  const r = replay(), none = { ...r.overflows[1], history: 'none' }, late = { ...r.overflows[0], history_from: '2026-10-24T20:00Z' };
  const table = R.replayTable({ ...r, overflows: [none, late] });
  assert.match(table, /No poll history for it: only this update's reading is known\./);
  assert.match(table, /Its poll history starts at Sat 21:00; before then nothing is known\./);
  const svg = R.replaySvg({ ...r, overflows: [none, late] });
  assert.equal((svg.match(/class="rp-nopoll"/g) || []).length, 2);
});
