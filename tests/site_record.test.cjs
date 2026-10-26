// The decision record (record.html, src/dipcast/site/record.js): one spot and one day on up to two A4 pages,
// opening with what it is not and the live accuracy figures, then the level and why by levels.js's rules,
// every input with its age and source, the About page's limits word for word, and blank decision lines.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Rec = require('../src/dipcast/site/record.js');
const L = require('../src/dipcast/site/levels.js');

const ROOT = path.join(__dirname, '..');
const GEN = '2026-10-04T00:16:57+01:00', NOW = Date.parse(GEN) + 2 * 3600e3;
const BASE = 'https://swimsignal.co.uk/';
const DATA = {generated_at: GEN, lead_skill: {spill: [1, 0.84, 0.79, 0.7, 0.59], water: [1, 0.75, 0.69, 0.55, 0.55]},
  build: {live_feeds: {polled_at: '2026-10-03 23:10:00.5+00:00'}}};
const VER = {live: {warning_table: {warn_at: 0.4, level: 'high', n: 28380, hits: 153, misses: 582, false_alarms: 221, hit_rate: 0.20816, warnings_true: 0.40909,
  n_days: 6, first_day: '2026-09-29', last_day: '2026-10-04'}}};
const day = (date, label, risk, e, extra = {}) => ({date, label, risk, expected_spilling_overflows: e, p_ecoli_gt900: 0.33, in_validated_season: false, rain_48h_mm: 6.2, ...extra});
const ov = (name, weight, km, extra = {}) => ({site_id: name.toUpperCase(), company: 'Yorkshire Water', site_name: name, receiving_watercourse: 'River Wharfe',
  lat: 53.9, lon: -1.8, status: 0, has_live: true, data_state: 'live', feed_updated_at: '2026-10-03T22:19:33+00:00', lta_spills: 48.5, spill_hours: 48.25,
  distance_km: km, lake_distance_km: 0, travel_h: km / 1.8, weight, p_spill_days: [0.002, 0.02, 0.05, 0.055, 0.086], ...extra});
const DAYS = ['2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08'];
const ilkley = {id: 'bw-uke4100-08901', name: 'Wharfe at Cromwheel, Ilkley', kind: 'river', source: 'designated', location: {mode: 'river', watercourse: 'River Wharfe'},
  assumptions: {max_upstream_km: 60, version: 'spill=808da63d;code=0.1.0+ed7c3ef'},
  now: {risk: 0, label: 'low', discharging_upstream: 0, recent_upstream: 0, monitored_upstream: 15, feed_down_upstream: 0, feed_down: [], stale_upstream: 0, feed_stale: [], no_feed_upstream: 0},
  upstream_summary: {overflows: 15, with_live_feed: 15, without_live_feed: 0, max_travel_h: 20.8},
  days: [day(DAYS[0], 'low', 0.01, 0.1), day(DAYS[1], 'low', 0.08, 1.0), day(DAYS[2], 'moderate', 0.2, 2), day(DAYS[3], 'low', 0.05, 0.5), day(DAYS[4], 'low', 0.05, 0.5)],
  contributors: [ov('RIVADALE VIEW/CSO', 0.978, 0.5), ov('Addingham/NO 1 SPS/Preliminary Treatment-STW/6Xdwf Overflow', 0.8, 4.1), ov('Burnsall CAR PK/CSO', 0.21, 21.8, {p_spill_days: [0.01, 0.07, 0.1, 0.1, 0.1]})],
  algae: {date: '2026-09-24', level: 0, phrase: 'none seen'}, lab_sample: {taken_at: '2026-09-24T13:02+01:00', ecoli: 380},
  classification: {class: 'poor', year: 2025, url: 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=uke4100-08901'},
  river_state: {station: 'Ilkley', level_m: 0.195, typical_low_m: 0.09, typical_high_m: 1.8, observed_at: '2026-10-03T21:15:00Z', distance_km: 1.0},
  water_temp: {temp_c: 15.6, observed_at: '2026-10-03T22:00:26Z', where: 'at Bures Mill', river: 'Stour', river_km: 10.9, direction: 'downstream'},
  flood_alerts: []};
const lake = {id: 'buttermere', name: 'Buttermere', kind: 'lake', source: 'curated', location: {mode: 'lake'}, now: {label: null}, upstream_summary: {overflows: 0},
  days: DAYS.map(d => ({date: d, risk: null, label: null, rain_48h_mm: 3})), flood_alerts: null};
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/\s+/g, ' ');
// "safe" only where a sentence says the forecast is not, or never says, that the water is safe.
const onlyDisclaimed = (h, word) => {
  for (const s of text(h).split(/(?<=[.!?])\s+/)) if (new RegExp(`\\b${word}\\b`, 'i').test(s)) assert.match(s, /\b(not|never|no)\b/i, `"${word}" outside a disclaimer: ${s}`);
};

test('the address holds the spot and the day', () => {
  assert.deepEqual(Rec.fromHash('#spot=bw-uke4100-08901&day=2026-10-05'), {spot: 'bw-uke4100-08901', day: '2026-10-05'});
  assert.deepEqual(Rec.fromHash('#spot=x&day=tomorrow'), {spot: 'x', day: null});   // not a date: today's record
  assert.deepEqual(Rec.fromHash(''), {spot: null, day: null});
  assert.equal(Rec.toHash('a b', '2026-10-05'), '#spot=a+b&day=2026-10-05');
  assert.deepEqual(Rec.fromHash(Rec.toHash('a b', '2026-10-05')), {spot: 'a b', day: '2026-10-05'});
});

test('the first paragraph says what it is not, and quotes the live accuracy figures in plain words', () => {
  const h = Rec.view(ilkley, DAYS[1], DATA, VER, BASE, NOW);
  const first = text(h.split('</p>')[0]).trim();
  assert.ok(first.startsWith('This page records SwimSignal\'s pollution risk forecast for one spot on one day, to attach to a written decision.'));
  assert.ok(first.includes('It is a forecast, not a water test: nothing was sampled at the water for it. It never says the water is safe or clean, and no level means that.'));
  assert.ok(first.includes('On 6 days of live scoring between 29 September and 4 October 2026, it warned of 21% of the spills at the storm overflows it scores, and 41% of its warnings were followed by a spill.'));
  assert.ok(first.includes('A warning is a spill chance of 40% or more, the High risk line. So it misses most spills, and most of its warnings are false alarms.'));
  assert.ok(first.includes('That is too few days to judge across different weather.'));
  assert.ok(h.indexOf('r-first') < h.indexOf('r-spot'));   // before anything about the spot
  // Without the scores, it says where they are rather than leaving them out silently.
  assert.ok(Rec.view(ilkley, DAYS[1], DATA, null, BASE, NOW).includes('The live accuracy figures could not be loaded. They are on https://swimsignal.co.uk/verification.html.'));
});

test('the level and why follow levels.js, with the overflows that matter most, how far and how long away', () => {
  L.setToday(DAYS[0]);
  const h = Rec.view(ilkley, DAYS[1], DATA, VER, BASE, NOW);
  assert.equal(L.dayHeadline(ilkley, DAYS[1]), 'High risk: rated poor');
  assert.ok(h.includes('<p class="r-level high">High risk</p><p class="r-why">Rated poor</p>'));
  assert.ok(h.includes('Low risk: about 1 of the 15 overflows upstream is expected to spill. Sewage spill risk <b>8</b> of 100'));
  assert.match(h, /<b>Rivadale View storm overflow<\/b> \(Rivadale View\/CSO\): 0\.5\skm upstream, sewage arrives in under an hour\. Spill chance 2%, reach 98%\./);
  assert.match(h, /<b>Burnsall CAR PK storm overflow<\/b> \(Burnsall CAR PK\/CSO\): 21\.8\skm upstream, sewage arrives in about 12 h\. Spill chance 7%, reach 21%\./);
  assert.ok(h.includes('<dt>Discharging when the forecast was issued</dt><dd>0 of 15 discharging. All 15 report live.</dd>'));
  assert.ok(h.includes('6 mm in the 48 hours to midday on Monday, 5 October 2026.'));
  assert.ok(h.includes('1 day. In tests on past years, spill forecasts this far ahead were about 85% as good as same-day ones'));
  // A plain level: the words of the spot's page, and the other risks.
  const b = Rec.view(lake, DAYS[0], DATA, VER, BASE, NOW);
  assert.ok(b.includes('<p class="r-level clear">No monitored overflow found upstream</p>') && b.includes(L.OTHER_RISKS));
});

test('every input has its time, its age when the page was opened, and its source', () => {
  const h = Rec.view(ilkley, DAYS[1], DATA, VER, BASE, NOW);
  const inputs = h.split('class="fields r-inputs"')[1].split('</dl>')[0];
  for (const [what, when] of [['Forecast issued', '4 Oct 2026, 00:16, 2 h ago'], ['Live overflow status', 'Feeds read 4 Oct 2026, 00:10, 2 h 7 min ago'],
    ['Algae at the last check', '24 September 2026, 10 days ago'], ['Latest lab sample', '24 Sept 2026, 13:02, 10 days ago'],
    ['River level', '3 Oct 2026, 22:15, 4 h 2 min ago'], ['Water temperature', '3 Oct 2026, 23:00, 3 h 17 min ago']]) {
    const row = inputs.split(`<dt>${what}</dt>`)[1];
    assert.ok(row, what); assert.ok(row.split('</dd>')[0].includes(when), `${what}: ${row.split('</dd>')[0]}`);
    assert.ok(row.split('</dd>')[0].includes('Source:'), what);
  }
  assert.ok(inputs.includes('<code>spill=808da63d;code=0.1.0+ed7c3ef</code>'));
  assert.ok(inputs.includes("the feeds' latest updates are from 3 Oct 2026, 23:19"));
  assert.ok(inputs.includes('<dt>Environment Agency rating</dt><dd>Poor, for 2025.'));
  assert.ok(inputs.includes('0.20 m at Ilkley, 1 km away; its usual range is 0.09 to 1.80 m. Not part of the pollution level.'));
  assert.ok(inputs.includes('16°C, measured at Bures Mill on the Stour, 10.9 km downstream. Not part of the pollution level.'));
  assert.ok(inputs.includes('The Environment Agency listed no flood alerts or warnings in force within 10 km when the forecast was made.'));   // a build before flood_alerts_search
  assert.ok(Rec.view(lake, DAYS[0], DATA, VER, BASE, NOW).includes('Not checked: the Environment Agency did not answer'));   // null is never "none"
});

// 26 Oct 2026: the Wharfe spots were given "Lower River Ure". An alert is now named only when the EA's
// outline of its area covers the spot, "in force here"; the others are counted, never named, and the
// record never turns them into "none".
test('alerts for other water or not matched to the spot are counted, never named, never "none" or "nearby"', () => {
  const row = s => {
    const h = text(Rec.view({...ilkley, ...s}, DAYS[1], DATA, VER, BASE, NOW).split('class="fields r-inputs"')[1].split('</dl>')[0]);
    return h.split('Flood alerts')[1];
  };
  const other = row({flood_alerts: [], flood_alerts_other: 1, flood_alerts_unmatched: 0});
  assert.ok(other.includes("1 other alert or warning is in force for other water or could not be matched to this spot: check the Environment Agency's flood map."), other);
  assert.ok(!/none|nearby|Ure/i.test(other.split('Checked with the forecast')[0]), other);
  const unmatched = row({flood_alerts: [], flood_alerts_other: 0, flood_alerts_unmatched: 2});
  assert.ok(unmatched.includes('2 other alerts or warnings are in force') && !/none|nearby/i.test(unmatched.split('Checked with the forecast')[0]), unmatched);
  const both = row({flood_alerts: [{severity: 'Flood alert', area: 'Upper River Wharfe'}], flood_alerts_other: 1, flood_alerts_unmatched: 1});
  assert.ok(both.includes('Flood alert in force here: Upper River Wharfe. 2 other alerts or warnings are in force for other water'), both);
  // None at all, in the words of the search that found none.
  assert.ok(row({flood_alerts: [], flood_alerts_other: 0, flood_alerts_unmatched: 0, flood_alerts_search: 'within_10km'})
    .includes("The Environment Agency's search within 10 km returned no flood alerts or warnings in force when the forecast was made."));
  assert.ok(row({flood_alerts: [], flood_alerts_other: 0, flood_alerts_unmatched: 0, flood_alerts_search: 'england'})
    .includes('The Environment Agency listed no flood alerts or warnings in force anywhere in England when the forecast was made.'));
  assert.ok(!/nearby/i.test(row({flood_alerts: [], flood_alerts_search: 'within_10km'})));
  assert.ok(row({flood_alerts: null, flood_alerts_other: null, flood_alerts_unmatched: null}).includes('Not checked'));   // unchecked stays its own
});

test('what the forecast cannot see is the About page\'s list, word for word', () => {
  const about = fs.readFileSync(path.join(ROOT, 'src', 'dipcast', 'pages', 'about.html'), 'utf8');
  const list = about.split('<h2>What it cannot see</h2>')[1].split('</ul>')[0];
  const items = [...list.matchAll(/<li>([\s\S]*?)<\/li>/g)].map(m => m[1].replace(/<[^>]+>/g, '').trim());
  // Every item, the overflows in Wales included: until 12 Oct 2026 the About page's said Dŵr Cymru's overflows
  // "which matter at the spots on the Dee and on the Wye in Herefordshire" are forecast from rain and their
  // yearly record, though those in Wales are not in the data, and the test let that item differ.
  const wales = Rec.CANNOT_SEE.findIndex(t => t.startsWith('Dŵr Cymru Welsh Water\'s overflows in Wales are not in SwimSignal\'s data'));
  assert.ok(wales >= 0);
  assert.deepEqual(Rec.CANNOT_SEE, items.map(t => t.replace(/&quot;/g, '"')));
  assert.ok(![...Rec.CANNOT_SEE, ...items].some(t => /which matter at the spots on the Dee/.test(t)));
  // Every line but Dŵr Cymru's, which only a spot with its overflows upstream, or a river from Wales, carries
  // (11 Oct 2026: Chee Dale had it).
  const h = Rec.view(ilkley, DAYS[1], DATA, VER, BASE, NOW);
  for (const t of Rec.CANNOT_SEE.filter(t => !t.startsWith('Dŵr Cymru'))) assert.ok(text(h).includes(t.replace(/\s+/g, ' ')), t);
  assert.ok(!text(h).includes('Dŵr Cymru Welsh Water\'s overflows in Wales'));
  const wye = {...ilkley, contributors: [...ilkley.contributors, ov('HAY ON WYE/STW', 0.5, 12, {company: 'Dwr Cymru Welsh Water'})]};
  assert.ok(text(Rec.view(wye, DAYS[1], DATA, VER, BASE, NOW)).includes(Rec.CANNOT_SEE[wales]));
  const ludlow = {...ilkley, upstream_summary: {...ilkley.upstream_summary, wales_share: 0.12}};
  assert.ok(text(Rec.view(ludlow, DAYS[1], DATA, VER, BASE, NOW)).includes(Rec.CANNOT_SEE[wales]));
  // The E. coli estimate's sentence only where the spot shows the estimate: not at a lake.
  assert.ok(text(h).includes('On rivers, the E. coli estimate allows for rain washing in pollution from other sources, but only on average.'));
  const tarn = Rec.cannotSee({...ilkley, kind: 'lake', location: {mode: 'lake'}});
  assert.equal(tarn[0], 'The sewage spill risk covers monitored storm overflows only. It knows nothing about a particular farm, road, boat, misconnected drain or incident.');
  assert.ok(!tarn.join(' ').includes('E. coli') && Rec.cannotSee(lake).every(t => !t.includes('E. coli')));
});

test('the accuracy line says how many days, and that most hits were at the one company the model learned from', () => {
  const by = [{company: 'United Utilities', hits: 208, misses: 489, false_alarms: 266}, {company: 'Anglian Water', hits: 0, misses: 127, false_alarms: 8},
    {company: 'Yorkshire Water', hits: 15, misses: 496, false_alarms: 63}];
  const W = {...VER.live.warning_table, hits: 223, n_days: 10, first_day: '2026-09-29', last_day: '2026-10-10', trained_on: 'United Utilities', by_company: by};
  const t = Rec.accuracy({live: {warning_table: W}}, BASE);
  assert.ok(t.startsWith('On 10 days of live scoring between 29 September and 10 October 2026, it warned of 21%'), t);
  assert.ok(t.includes('208 of the 223 warnings that came true were at United Utilities, the one company the spill model learned from. At the other companies it warned of 2% of the spills.'), t);
});

test('blank decision lines close a record within the five days', () => {
  const h = Rec.view(ilkley, DAYS[1], DATA, VER, BASE, NOW);
  for (const l of ['Decided by', 'Role', 'Decision (circle one): go / no-go / changed plan', 'Date and time', 'Notes', 'Signature']) assert.ok(h.includes(`<span>${l}</span>`), l);
  assert.ok(h.indexOf('What the forecast cannot see') < h.indexOf('id="r-decide"'));
  assert.ok(h.includes('Printed from https://swimsignal.co.uk/record.html#spot=bw-uke4100-08901&amp;day=2026-10-05, issue id '));
});

test('outside the five days it says when the forecast first appears, and gives no record', () => {
  const later = Rec.view(ilkley, '2026-10-17', DATA, VER, BASE, NOW);
  assert.ok(later.includes('The forecast for Saturday, 17 October 2026 first appears on <b>Tuesday, 13 October 2026</b>, as the last of its five days'));
  assert.ok(!later.includes('r-decide') && !later.includes('r-inputs') && !later.includes('r-level'));
  const past = Rec.view(ilkley, '2026-10-01', DATA, VER, BASE, NOW);
  assert.ok(past.includes('That day has passed.') && !past.includes('r-decide'));
  assert.ok(Rec.view(ilkley, DAYS[4], DATA, VER, BASE, NOW).includes('id="r-decide"'));   // the fifth day is inside
});

test('an unknown spot is said plainly; a stale forecast carries the app\'s notice', () => {
  const h = Rec.view(null, DAYS[0], DATA, VER, BASE, NOW, 'old-spot');
  assert.ok(h.includes('No spot with the id <b>old-spot</b> is in this forecast: it may have been renamed or removed.'));
  assert.ok(Rec.view(ilkley, DAYS[0], DATA, VER, BASE, Date.parse(GEN) + 9 * 3600e3).includes('<b>Stale.</b> This forecast is 9 h old'));
  assert.ok(!Rec.view(ilkley, DAYS[0], DATA, VER, BASE, NOW).includes('Stale'));
});

test('right now is named on the day itself when the live feeds put it higher', () => {
  const live = {...ilkley, classification: null, source: 'curated', now: {...ilkley.now, risk: 0.5, label: 'high', discharging_upstream: 2}};
  const h = Rec.view(live, DAYS[0], DATA, VER, BASE, NOW);
  assert.ok(h.includes('<dt>Right now</dt><dd>High risk: sewage spills, from the live feeds when the forecast was issued.</dd>'));
  assert.ok(!Rec.view(live, DAYS[1], DATA, VER, BASE, NOW).includes('<dt>Right now</dt>'));
});

test('never "safe" or "clean" except in a sentence that says it is not', () => {
  for (const [s, d] of [[ilkley, DAYS[0]], [ilkley, DAYS[1]], [ilkley, DAYS[4]], [ilkley, '2026-10-20'], [lake, DAYS[0]], [null, DAYS[0]]]) {
    for (const ver of [VER, null]) {
      const h = Rec.view(s, d, DATA, ver, BASE, NOW, 'x');
      onlyDisclaimed(h, 'safe'); onlyDisclaimed(h, 'clean');
    }
  }
  onlyDisclaimed(fs.readFileSync(path.join(ROOT, 'src', 'dipcast', 'site', 'record.html'), 'utf8'), 'safe');
});

test('links to the record: the organisers\' page for the picked day, the sites view, and a spot\'s day detail', () => {
  const site = path.join(ROOT, 'src', 'dipcast', 'site');
  assert.ok(fs.readFileSync(path.join(site, 'organisers.js'), 'utf8').includes('record.html#spot=${esc(encodeURIComponent(s.id))}&amp;day=${iso}">Print a decision record for this day</a>'));
  assert.ok(fs.readFileSync(path.join(site, 'sites.js'), 'utf8').includes('record.html#spot=${encodeURIComponent(id)}&day=${iso}'));
  const app = fs.readFileSync(path.join(site, 'index.html'), 'utf8');
  const detail = app.split('function dayDetail(')[1].split('\n}\n')[0];
  assert.ok(detail.includes('record.html#spot=${esc(encodeURIComponent(d.id))}&amp;day=${x.date}">Print a decision record</a>'));
  const page = fs.readFileSync(path.join(site, 'record.html'), 'utf8');
  assert.ok(page.includes('@page { size:A4 portrait') && page.includes('<title>Decision record · SwimSignal</title>') && page.includes('class="site-foot"'));
  assert.ok(/<script src="levels\.js"><\/script>\s*<script src="evidence\.js"><\/script>\s*<script src="organisers\.js"><\/script>\s*<script src="printed\.js"><\/script>\s*<script src="record\.js"><\/script>/.test(page));
});

// ------------------------------------------------------------------------------ OP2, OP3, OP4 (docs/ORGANISER-PIVOT-2026-10.md)
// The credits as scripts/build_site.py writes them (data_credits); tests/test_site_pages.py checks the build's side.
const LIC = {'CC BY 4.0': 'https://creativecommons.org/licenses/by/4.0/', 'CC BY-SA 4.0': 'https://creativecommons.org/licenses/by-sa/4.0/',
  'OGL v3.0': 'https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/', 'ODbL 1.0': 'https://opendatacommons.org/licenses/odbl/1-0/'};
const src = (use, credit, licence) => ({use, credit, licence, changed: `SwimSignal changed ${use}.`});
const CREDITS = {modified: 'Combined, filtered and modelled by SwimSignal.', endorsement: 'None of the providers endorses SwimSignal.', full: 'https://swimsignal.co.uk/terms.html#data', licences: LIC,
  companies: {'Yorkshire Water': 'Yorkshire Water', 'Anglian Water': 'Anglian Water Services'},
  sources: [src('overflows', 'Storm overflow status from {companies}, via the National Storm Overflow Hub', 'CC BY 4.0'),
    src('always', 'Environment Agency data © Environment Agency copyright and/or database right', 'OGL v3.0'),
    src('gauge', 'This uses Environment Agency flood and river level data from the real-time data API (Beta)', 'OGL v3.0'),
    src('always', 'Contains OS data © Crown copyright and database right 2026', 'OGL v3.0'),
    src('rain', 'Weather data by Open-Meteo.com', 'CC BY 4.0'), src('rain', 'Met Office data © Crown copyright, served by Open-Meteo', 'CC BY-SA 4.0'),
    src('model', 'Contains modified Copernicus Climate Change Service information 2026', ''),
    src('lake', 'Lake residence times from HydroLAKES v1.0', 'CC BY 4.0'),
    src('osm', 'Swim spot location © OpenStreetMap contributors, openstreetmap.org/copyright', 'ODbL 1.0')]};
const FULL = {...DATA, commit: '3ed1b5a', credits: CREDITS};
const credits = h => text(h.split('class="credits-h"')[1] || '');

test('the record credits every source it used, each with its licence and what SwimSignal changed, and no other', () => {
  const c = credits(Rec.view(ilkley, DAYS[1], FULL, VER, BASE, NOW));
  for (const t of ['Storm overflow status from Yorkshire Water, via the National Storm Overflow Hub, CC BY 4.0. SwimSignal changed overflows.',
    'Environment Agency data © Environment Agency copyright and/or database right, OGL v3.0.', 'real-time data API (Beta), OGL v3.0. SwimSignal changed gauge.',
    'Contains OS data © Crown copyright and database right 2026', 'Weather data by Open-Meteo.com, CC BY 4.0.', 'Met Office data © Crown copyright, served by Open-Meteo, CC BY-SA 4.0.',
    'Contains modified Copernicus'])
    assert.ok(c.includes(t), `${t} missing from: ${c}`);
  assert.ok(!c.includes('Anglian') && !c.includes('HydroLAKES') && !c.includes('OpenStreetMap'));   // not upstream, no lake, not an OSM spot
  // The licences are written out, since a printed link cannot be followed; ODbL only where OSM is credited.
  assert.ok(c.includes('Licences: CC BY 4.0, creativecommons.org/licenses/by/4.0; OGL v3.0, nationalarchives.gov.uk/doc/open-government-licence/version/3; CC BY-SA 4.0, creativecommons.org/licenses/by-sa/4.0.'));
  assert.ok(c.includes('None of the providers endorses SwimSignal. Full credits: swimsignal.co.uk/terms.html#data.'));
  // An OpenStreetMap spot carries the OSM line with its address written out; a lake whose sewage crosses it, HydroLAKES;
  // a spot with no river level or flood alerts shown, no flood API line.
  const osm = credits(Rec.view({...ilkley, source: 'openstreetmap', river_state: null, flood_alerts: undefined, upstream_summary: {...ilkley.upstream_summary, through_lake: true}}, DAYS[1], FULL, VER, BASE, NOW));
  assert.ok(osm.includes('Swim spot location © OpenStreetMap contributors, openstreetmap.org/copyright, ODbL 1.0.') && osm.includes('opendatacommons.org/licenses/odbl/1-0'));
  assert.ok(osm.includes('HydroLAKES') && !osm.includes('real-time data API'));
  // upstream_summary.companies, every company upstream, wins over the first few contributors.
  const both = credits(Rec.view({...ilkley, upstream_summary: {...ilkley.upstream_summary, companies: ['Anglian Water', 'Yorkshire Water', 'Dwr Cymru Welsh Water']}}, DAYS[1], FULL, VER, BASE, NOW));
  assert.ok(both.includes('Storm overflow status from Anglian Water Services and Yorkshire Water, via'));   // Dŵr Cymru: no data reused, so no credit
  // A file from before the sources were written: its one-line credit.
  assert.ok(credits(Rec.view(ilkley, DAYS[1], {...DATA, credits: {attribution: 'Old line.', modified: 'Changed.', full: CREDITS.full}}, VER, BASE, NOW)).includes('Old line. Changed. Full credits: swimsignal.co.uk/terms.html#data.'));
});

test('the issue id is the build and the issue time: the same for every copy of a build, new for the next', () => {
  const P = require('../src/dipcast/site/printed.js');
  assert.equal(P.issueId(FULL), '3ed1b5a-20261003T2316Z');   // 00:16 BST is 23:16 UTC the day before
  const a = Rec.view(ilkley, DAYS[1], FULL, VER, BASE, NOW), b = Rec.view(ilkley, DAYS[1], FULL, VER, BASE, NOW + 3600e3);
  const ids = h => [...text(h).matchAll(/Issue id ([0-9a-z]+-\d{8}T\d{4}Z)/gi)].map(m => m[1]);
  assert.deepEqual(ids(a), ['3ed1b5a-20261003T2316Z', '3ed1b5a-20261003T2316Z']);   // at the top and in the printed foot
  assert.deepEqual(ids(b), ids(a));   // printed an hour later from the same build
  assert.notDeepEqual(ids(Rec.view(ilkley, DAYS[1], {...FULL, generated_at: '2026-10-04T00:46:10+01:00'}, VER, BASE, NOW)), ids(a));
  assert.notDeepEqual(ids(Rec.view(ilkley, DAYS[1], {...FULL, commit: 'aaaaaaa'}, VER, BASE, NOW)), ids(a));
  // Without `commit`, the code part of a spot's model version, which every logged forecast carries.
  assert.equal(P.issueId({...DATA, spots: [ilkley]}), 'ed7c3ef-20261003T2316Z');
});

test('the record is one input to the organisation\'s own risk assessment, names what it does not cover, and leaves the decision to them', () => {
  const h = Rec.view(ilkley, DAYS[1], FULL, VER, BASE, NOW, '', 'Lakeside Adventure Ltd');
  const t = text(h.split('class="r-spot"')[0]);
  assert.ok(t.includes("for one spot on one day, prepared for Lakeside Adventure Ltd , to attach to a written decision.") || t.includes('prepared for Lakeside Adventure Ltd, to attach'));
  assert.ok(t.includes("It is one input to your own risk assessment. Use it beside lab tests, checks at the water, the Environment Agency's advice and the water companies' own spill alerts."));
  for (const hazard of ['algae', "leptospirosis (Weil's disease)", 'runoff from farms and roads', 'outfalls no one monitors', 'physical dangers'])
    assert.ok(t.includes(hazard), hazard);
  assert.ok(t.includes('Missing data never means low risk: treat it as unknown.'));
  assert.ok(t.includes('Your organisation makes the decision, and the people who sign below give the reasons.'));
  assert.ok(text(h).includes('Organisation: Lakeside Adventure Ltd'));   // on the decision lines too
  assert.ok(!text(Rec.view(ilkley, DAYS[1], FULL, VER, BASE, NOW)).includes('prepared for'));
  // The organisation's name is the reader's own text: escaped, and kept in the address.
  assert.ok(Rec.view(ilkley, DAYS[1], FULL, VER, BASE, NOW, '', '<b>x</b>').includes('&lt;b&gt;x&lt;/b&gt;'));
  assert.deepEqual(Rec.fromHash(Rec.toHash('a', DAYS[1], 'Club & co')), {spot: 'a', day: DAYS[1], org: 'Club & co'});
  // Never certified or verified, in any state.
  for (const [s, d] of [[ilkley, DAYS[0]], [ilkley, DAYS[1]], [lake, DAYS[0]], [null, DAYS[0]]])
    assert.doesNotMatch(text(Rec.view(s, d, FULL, VER, BASE, NOW, 'x', 'Org')), /\b(certif\w*|verified)\b/i);
});
