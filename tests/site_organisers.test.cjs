// The organisers' page (organisers.html, src/dipcast/site/organisers.js) and the live sign (the
// embed's screen mode, embed.js). A day's level and its reason come from levels.js, so the page says
// what the spot's page, the embed and the alerts say; the overflows come from the spot's forecast.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const O = require('../src/dipcast/site/organisers.js');
const Embed = require('../src/dipcast/site/embed.js');
const L = require('../src/dipcast/site/levels.js');

const GEN = '2026-10-04T00:16:57+01:00', NOW = Date.parse(GEN) + 2 * 3600e3;
const BASE = 'https://swimsignal.co.uk/';
const CREDITS = {attribution: 'Storm overflow status from the water companies, CC BY 4.0', modified: 'Combined, filtered and modelled by SwimSignal.',
  spot_locations: 'Swim spot locations from OpenStreetMap, © OpenStreetMap contributors, ODbL 1.0',
  licences: {'CC BY 4.0': 'https://creativecommons.org/licenses/by/4.0/'}, full: 'https://swimsignal.co.uk/terms.html#data'};
const DATA = {generated_at: GEN, lead_skill: {spill: [1, 0.84, 0.79, 0.7, 0.59], water: [1, 0.75, 0.69, 0.55, 0.55]}, credits: CREDITS};
const day = (date, label, risk, e, extra = {}) => ({date, label, risk, expected_spilling_overflows: e, p_ecoli_gt900: 0.41, in_validated_season: false, rain_48h_mm: 6.2, ...extra});
const ov = (name, weight, km, extra = {}) => ({site_id: name.toUpperCase(), company: 'Thames Water', site_name: name, receiving_watercourse: 'River Thames',
  lat: 51.5, lon: -0.9, status: 0, has_live: true, lta_spills: 18.14, spill_hours: 120.75, distance_km: km, lake_distance_km: 0, travel_h: km / 1.8,
  weight, p_spill_days: [0.01, 0.02, 0.03, 0.06, null], ...extra});
const henley = {id: 'thames-henley', name: 'River Thames, Henley-on-Thames', kind: 'river', source: 'curated', location: {mode: 'river', watercourse: 'River Thames'},
  assumptions: {max_upstream_km: 60}, now: {label: 'low'},
  upstream_summary: {overflows: 51, with_live_feed: 51, without_live_feed: 0, max_travel_h: 32.6},
  days: [day('2026-10-04', 'low', 0.002, 0.1), day('2026-10-05', 'low', 0.002, 0.1), day('2026-10-06', 'moderate', 0.2, 2.2),
         day('2026-10-07', 'low', 0.034, 4.8), {date: '2026-10-08', label: 'unknown', risk: null, expected_spilling_overflows: null, p_ecoli_gt900: null}],
  contributors: [ov('WARGRAVE STW', 0.307, 7.3), ov('Friday Street (Henley) SPS', 0.998, 0), ov('Goring STW', 0.033, 34.6, {has_live: false})]};

test('a day is past, inside the five days, or later, when its forecast first appears four days before', () => {
  L.setToday('2026-10-04');
  assert.deepEqual(O.when(henley, '2026-10-03'), {state: 'past'});
  const w = O.when(henley, '2026-10-07');
  assert.equal(w.state, 'in'); assert.equal(w.j, 3); assert.equal(w.x.date, '2026-10-07');
  assert.equal(O.when(henley, '2026-10-08').j, 4);   // the fifth day
  assert.deepEqual(O.when(henley, '2026-10-09'), {state: 'later', from: '2026-10-05'});
  assert.deepEqual(O.when(henley, '2026-10-17'), {state: 'later', from: '2026-10-13'});
});

test('a day inside the forecast gives its level by the page rules, why, and how sure', () => {
  const h = O.view(henley, '2026-10-06', DATA, BASE, NOW);
  assert.ok(h.includes(`<p class="ev-level moderate">${L.dayHeadline(henley, '2026-10-06')}</p>`));
  assert.equal(L.dayHeadline(henley, '2026-10-06'), 'Moderate risk: sewage spills');
  assert.ok(h.includes('Moderate risk: about 2 of the 51 overflows upstream are expected to spill.'));
  assert.ok(h.includes('Exposure index <b>20</b> of 100'));
  // The three most likely to reach the spot that day, chance times reach, names in normal case.
  assert.match(h, /Most likely to reach the spot: Friday Street \(Henley\) SPS \(spill chance 3%, reach 100%\); Wargrave STW/);
  assert.ok(h.includes('<b>41%</b>. Untested from October to April'));   // out of season: shown, not counted
  assert.ok(h.includes('2 days. In tests on past years, spill forecasts this far ahead were about 80% as good as same-day ones, and water-quality ones about 70%.'));
  assert.ok(h.includes('6\u00a0mm in the 48 hours to midday.'));
  assert.ok(h.includes('A forecast, not a water test: check the signs at the water before you swim.'));
  assert.ok(h.includes('Not a designated bathing water'));
  assert.ok(!h.includes('Stale'));
  assert.ok(O.view(henley, '2026-10-04', DATA, BASE, NOW).includes('The day this forecast was issued for.'));
  const nodata = O.view(henley, '2026-10-08', DATA, BASE, NOW);
  assert.ok(nodata.includes('No forecast for this day') && nodata.includes('The rainfall forecast for this day has not arrived'));
  assert.ok(O.view(henley, '2026-10-06', DATA, BASE, Date.parse(GEN) + 9 * 3600e3).includes('<b>Stale.</b> This forecast is 9 h old'));
});

test('a later day says when its forecast appears and what is known now, with the rating as levels.js words it', () => {
  const bw = {...henley, id: 'bw-x', name: 'Wharfe at Cromwheel, Ilkley', source: 'designated',
    classification: {class: 'poor', year: 2025, url: 'https://environment.data.gov.uk/bwq/profiles/x'}};
  const h = O.view(bw, '2026-10-17', DATA, BASE, NOW);
  assert.ok(h.includes('The forecast for Saturday 17 October first appears on <b>Tuesday 13 October</b>, as the last of its five days'));
  assert.ok(h.includes(L.poorAdvice('2026-10-17')) && h.includes('Environment Agency rating, 2025'));
  assert.ok(h.includes('51 monitored upstream'));
  assert.ok(!h.includes('ev-level'));   // no level for a day the forecast does not reach
  assert.ok(O.view(bw, '2027-06-12', DATA, BASE, NOW).includes(L.poorAdvice('2027-06-12')));   // in season: advice against bathing applies
  assert.notEqual(L.poorAdvice('2027-06-12'), L.poorAdvice('2026-10-17'));
  assert.ok(O.view(henley, '2026-10-01', DATA, BASE, NOW).includes('That day has passed'));
});

test('spots with nothing to forecast get their plain words, here as everywhere', () => {
  const none = {...henley, id: 'semerwater', name: 'Semerwater', kind: 'lake', location: {mode: 'lake'}, upstream_summary: {overflows: 0}, contributors: [], days: henley.days.map(d => ({...d}))};
  const h = O.view(none, '2026-10-06', DATA, BASE, NOW);
  assert.ok(h.includes(`<p class="ev-level clear">${L.COVER[L.NO_OVERFLOWS]}</p>`) && h.includes(L.OTHER_RISKS));
  assert.ok(h.includes('No monitored storm overflow is within 60\u00a0km upstream') && !h.includes('id="csv"'));
  const tarn = {id: 'tarn', name: 'A Tarn', kind: 'lake', source: 'curated', days: [], contributors: [], error: 'An isolated lake with no river connection.'};
  const t = O.view(tarn, '2026-10-17', DATA, BASE, NOW);
  assert.ok(t.includes('No river flows into this lake') && !t.includes('<table'));
  assert.ok(O.view(tarn, '2026-10-05', DATA, BASE, NOW).includes(`<p class="ev-level na">${L.COVER[L.NO_RIVER]}</p>`));
});

test('the overflows are the forecast\'s, most reach first, and say when the list is not all of them', () => {
  const rows = O.overflowRows(henley);
  assert.deepEqual(rows.map(r => r.name), ['Friday Street (Henley) SPS', 'Wargrave STW', 'Goring STW']);
  const h = O.overflows(henley);
  assert.ok(h.includes('51 monitored storm overflows are within 60\u00a0km upstream along the river network, all with a live feed.'));
  assert.ok(h.includes('Sewage from the farthest takes about 33\u00a0h to arrive.'));
  // Without the full list (it could not be loaded, or the build wrote none): the three, and why.
  assert.ok(h.includes('The table lists the 3 that matter most in the current forecast: the full list of 51 could not be loaded. Try again later.'));
  assert.ok(O.overflows(henley, 'loading').includes('The table lists the 3 that matter most in the current forecast while the other 48 load.'));
  const cells = [...h.matchAll(/<tr><th scope="row" class="ov">([^<]+)<\/th>(.*?)<\/tr>/g)].map(m => [m[1], [...m[2].matchAll(/data-l="([^"]+)">([^<]*)</g)].map(c => c.slice(1))]);
  assert.deepEqual(cells[1], ['Wargrave STW', [['Company', 'Thames Water'], ['Into', 'River Thames'], ['Upstream', '7.3\u00a0km'], ['Travel', '4\u00a0h'],
    ['Reach', '31%'], ['Spills a year', '18'], ['Hours spilling', '121'], ['Live feed', 'Yes']]]);
  assert.equal(cells[2][1][7][1], 'No');
  const mixed = {...henley, upstream_summary: {overflows: 3, with_live_feed: 2, without_live_feed: 1, max_travel_h: 0.4}};
  assert.ok(O.overflows(mixed).includes(': 2 report their status live, and 1 has no live feed, so SwimSignal forecasts it from rain and their yearly record alone.'));
  assert.ok(O.overflows(mixed).includes('takes under an hour to arrive') && !O.overflows(mixed).includes('does not yet publish'));
});

test('with every overflow upstream loaded (data/upstream/<id>.json), the table and the CSV list them all, most reach first', () => {
  const all = Array.from({length: 51}, (_, k) => ov(`Overflow ${k}`, 0.01 * (k + 1), k + 1));
  const h = O.overflows(henley, all);
  const names = [...h.matchAll(/<th scope="row" class="ov">([^<]+)<\/th>/g)].map(m => m[1]);
  assert.equal(names.length, 51);
  assert.deepEqual(names.slice(0, 2), ['Overflow 50', 'Overflow 49']);
  assert.ok(!h.includes('The table lists'));
  const text = O.csv(henley, DATA, BASE, all), lines = text.trim().split('\n');
  assert.equal(lines.filter(l => !l.startsWith('#')).length, 52);   // the header and 51 rows
  assert.ok(lines.some(l => l === '# 51 monitored overflows within 60 km upstream along the river network.'));
  // An empty or failed list falls back to the forecast's own.
  assert.equal(O.overflowRows(henley, []).length, 3);
  assert.equal(O.overflowRows(henley, 'failed').length, 3);
  assert.ok(O.view(henley, '2026-10-06', DATA, BASE, NOW, all).includes('Overflow 0'));
  // A long run in a feed's watercourse may break after its & or /, so it does not widen the table; a tiny reach is "<1%".
  const odd = O.overflows(henley, [ov('North_CSO_Princetown', 0.004, 40, {receiving_watercourse: 'WEIR BROOK&TRIB OF WEIR BROOK/DITCH'})]);
  assert.ok(odd.includes('data-l="Into">WEIR BROOK&amp;<wbr>TRIB OF WEIR BROOK/<wbr>DITCH</td>'), odd);
  assert.ok(odd.includes('class="ov">North_<wbr>CSO_<wbr>Princetown</th>'), odd);
  assert.ok(odd.includes('data-l="Reach">&lt;1%</td>'));
});

test('the CSV carries what it is, its columns and the credits, and is safe to open in a spreadsheet', () => {
  const odd = {...henley, contributors: [ov('=HYPERLINK("x")', 0.5, 1), ov('Name, with comma "quoted"', 0.4, 2)]};
  const text = O.csv(odd, DATA, BASE), lines = text.trim().split('\n');
  const notes = lines.filter(l => l.startsWith('# ')), body = lines.filter(l => !l.startsWith('#'));
  assert.ok(notes[0].includes('River Thames, Henley-on-Thames (thames-henley), from the forecast issued 2026-10-04T00:16:57+01:00. https://swimsignal.co.uk/spot/thames-henley/'));
  assert.ok(notes.some(n => n.includes('these are the 2 that matter most')));
  assert.ok(notes.some(n => n === `# Credits: ${CREDITS.attribution}`) && notes.some(n => n.includes('Full credits: https://swimsignal.co.uk/terms.html#data')));
  assert.ok(!notes.some(n => n.includes('OpenStreetMap')));   // not an OpenStreetMap spot
  assert.equal(body[0], 'site_id,site_name,company,receiving_watercourse,km_upstream,travel_hours,reach,spills_a_year,spill_hours_latest_return,live_feed,lat,lon');
  assert.ok(body[1].startsWith(`"'=HYPERLINK(""X"")","'=HYPERLINK(""x"")",Thames Water,River Thames,1,`));   // a formula is defused
  assert.ok(body[2].includes('"Name, with comma ""quoted"""'));
  assert.equal(body.length, 3);
  assert.ok(O.csv({...henley, source: 'openstreetmap'}, DATA, BASE).includes(`# ${CREDITS.spot_locations}`));
});

test('the spot and the day live after the # in the address', () => {
  assert.equal(O.toHash('thames-henley', '2026-10-07'), '#spot=thames-henley&date=2026-10-07');
  assert.deepEqual(O.fromHash('#spot=thames-henley&date=2026-10-07'), {spot: 'thames-henley', date: '2026-10-07'});
  assert.deepEqual(O.fromHash('#spot=x&date=next-week'), {spot: 'x', date: null});
  assert.equal(O.toHash(null, null), '');
});

test('names are escaped, and every link stays on this site', () => {
  const bad = {...henley, name: '<img src=x onerror=alert(1)>', contributors: [ov('<b>x</b>', 0.5, 1)]};
  const h = O.view(bad, '2026-10-06', DATA, BASE, NOW);
  assert.ok(!h.includes('<img') && !h.includes('<b>x</b>') && h.includes('&lt;img src=x onerror=alert(1)&gt;'));
  assert.ok(h.includes('href="spot/thames-henley/sign/"') && h.includes('href="embed.html?spot=thames-henley&amp;screen"') && h.includes('href="spot/thames-henley/"'));
});

test('the day detail\'s words are index.html\'s, so a day reads the same on both pages', () => {
  const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  for (const words of ['are expected to spill', 'a spill from a nearby overflow upstream is possible', 'under one spill is expected from the',
    'In tests on past years, spill forecasts this far ahead were about', 'as good as same-day ones', 'The rainfall forecast for this day has not arrived, so there is no figure.',
    'after travel time, die-off and dilution', 'from die-off over the travel time and dilution by the size of the river network upstream']) {
    assert.ok(page.includes(words), words);
  }
  assert.equal(O.spilling({expected_spilling_overflows: 0.2, label: 'low'}, 5), 'under one spill is expected from the 5 overflows upstream');
  assert.equal(O.spilling({expected_spilling_overflows: 0.2, label: 'high'}, 5), 'a spill from a nearby overflow upstream is possible');
  assert.equal(O.spilling({expected_spilling_overflows: 7, label: 'high'}, 5), 'all 5 overflows upstream are expected to spill');
});

// ------------------------------------------------------------------ the live sign
test('the live sign is the embed\'s card, with the sign\'s QR code and when it last asked', () => {
  const s = {...henley, days: henley.days};
  const parts = Embed.screenParts(s, 'https://swimsignal.co.uk/embed.html?spot=thames-henley&screen', Date.parse(GEN) + 3600e3, null);
  assert.ok(parts.includes('<img class="qr" src="spot/thames-henley/qr.svg" alt=""'));
  assert.ok(parts.includes('Scan for the full forecast, or go to <b>swimsignal.co.uk/spot/thames-henley</b>'));
  assert.match(parts, /Checked at \d\d:\d\d\. Checks again every 20 minutes\./);
  assert.match(Embed.screenParts(s, BASE, null, NOW), /Could not reach SwimSignal at \d\d:\d\d\. Trying again every 20 minutes\./);
  assert.ok(!Embed.screenParts({...s, id: 'Bad Id'}, BASE, NOW, null).includes('<img'));   // no page, so no sign and no code
  assert.ok(Embed.REFRESH_MIN >= 15 && Embed.REFRESH_MIN <= 30);
});

test('a stale live sign says why: the build, or this screen\'s connection', () => {
  const late = Date.parse(GEN) + 10 * 3600e3;
  assert.ok(Embed.card(henley, DATA, late).includes('This forecast is 10 h old: the automatic update has not run since.'));
  assert.ok(Embed.card(henley, DATA, late, {offline: true}).includes('This forecast is 10 h old: this screen has not been able to fetch a newer one.'));
  assert.ok(!Embed.card(henley, DATA, Date.parse(GEN) + Embed.STALE_MIN * 60e3, {offline: true}).includes('Stale'));
});
