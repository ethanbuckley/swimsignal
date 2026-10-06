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
  assert.ok(first.includes('In live scoring from 29 September to 4 October 2026, it warned of 21% of the spills at the storm overflows it scores, and 41% of its warnings were followed by a spill.'));
  assert.ok(first.includes('A warning is a spill chance of 40% or more, the High risk line. So it misses most spills, and most of its warnings are false alarms.'));
  assert.ok(first.includes('That is 6 days of scores, too few to judge across different weather.'));
  assert.ok(h.indexOf('r-first') < h.indexOf('r-spot'));   // before anything about the spot
  // Without the scores, it says where they are rather than leaving them out silently.
  assert.ok(Rec.view(ilkley, DAYS[1], DATA, null, BASE, NOW).includes('The live accuracy figures could not be loaded. They are on https://swimsignal.co.uk/verification.html.'));
});

test('the level and why follow levels.js, with the overflows that matter most, how far and how long away', () => {
  L.setToday(DAYS[0]);
  const h = Rec.view(ilkley, DAYS[1], DATA, VER, BASE, NOW);
  assert.equal(L.dayHeadline(ilkley, DAYS[1]), 'High risk: rated poor');
  assert.ok(h.includes('<p class="r-level high">High risk</p><p class="r-why">Rated poor</p>'));
  assert.ok(h.includes('Low risk: about 1 of the 15 overflows upstream is expected to spill. Exposure index <b>8</b> of 100'));
  assert.match(h, /<b>Rivadale View storm overflow<\/b> \(Rivadale View\/CSO\): 0\.5 km upstream, sewage arrives in under an hour\. Spill chance 2%, reach 98%\./);
  assert.match(h, /<b>Burnsall CAR PK storm overflow<\/b> \(Burnsall CAR PK\/CSO\): 21\.8 km upstream, sewage arrives in about 12 h\. Spill chance 7%, reach 21%\./);
  assert.ok(h.includes('<dt>Discharging when the forecast was issued</dt><dd>0 of 15 discharging. All 15 report live.</dd>'));
  assert.ok(h.includes('6 mm in the 48 hours to midday on Monday, 5 October 2026.'));
  assert.ok(h.includes('1 day. In tests on past years, spill forecasts this far ahead were about 85% as good as same-day ones'));
  // A plain level: the words of the spot's page, and the other risks.
  const b = Rec.view(lake, DAYS[0], DATA, VER, BASE, NOW);
  assert.ok(b.includes('<p class="r-level clear">No sewage risk from monitored overflows</p>') && b.includes(L.OTHER_RISKS));
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
  assert.ok(inputs.includes('None in force nearby when the forecast was made.'));
  assert.ok(Rec.view(lake, DAYS[0], DATA, VER, BASE, NOW).includes('Not checked: the Environment Agency did not answer'));   // null is never "none"
});

test('what the forecast cannot see is the About page\'s list, word for word', () => {
  const about = fs.readFileSync(path.join(ROOT, 'src', 'dipcast', 'api', 'static', 'about.html'), 'utf8');
  const list = about.split('<h2>What it cannot see</h2>')[1].split('</ul>')[0];
  const items = [...list.matchAll(/<li>([\s\S]*?)<\/li>/g)].map(m => m[1].replace(/<[^>]+>/g, '').trim());
  assert.deepEqual(Rec.CANNOT_SEE, items);
  const h = Rec.view(ilkley, DAYS[1], DATA, VER, BASE, NOW);
  for (const t of items) assert.ok(text(h).includes(t.replace(/\s+/g, ' ')), t);
});

test('blank decision lines close a record within the five days', () => {
  const h = Rec.view(ilkley, DAYS[1], DATA, VER, BASE, NOW);
  for (const l of ['Decided by', 'Role', 'Decision (circle one): go / no-go / changed plan', 'Date and time', 'Notes', 'Signature']) assert.ok(h.includes(`<span>${l}</span>`), l);
  assert.ok(h.indexOf('What the forecast cannot see') < h.indexOf('id="r-decide"'));
  assert.ok(h.includes('Printed from https://swimsignal.co.uk/record.html#spot=bw-uke4100-08901&amp;day=2026-10-05'));
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
  assert.ok(/<script src="levels\.js"><\/script>\s*<script src="evidence\.js"><\/script>\s*<script src="organisers\.js"><\/script>\s*<script src="record\.js"><\/script>/.test(page));
});
