// What the level rests on (src/dipcast/site/evidence.js): each item with its age and source, and the
// gaps said plainly, on a fixed clock. node --test tests/site_evidence.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { join } = require('node:path');
const ev = require('../src/dipcast/site/evidence.js');

const NOW = Date.parse('2026-10-04T17:00:00+01:00');   // Sunday, 1 h 30 min after the build
const BUILT = '2026-10-04T15:29:52+01:00';
const URL_ = 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=uke4100-08901';
const day = (date, rain) => ({ date, risk: 0.01, label: 'low', rain_48h_mm: rain });
// As spots.json has Wharfe at Cromwheel, Ilkley at 15:29 on 4 Oct 2026, with the build's lab sample.
const cromwheel = (extra = {}) => ({
  id: 'bw-uke4100-08901', name: 'Wharfe at Cromwheel, Ilkley', source: 'designated', kind: 'river',
  assumptions: { max_upstream_km: 60 }, upstream_summary: { overflows: 15 },
  now: { discharging_upstream: 0, recent_upstream: 1, monitored_upstream: 15, feed_down_upstream: 0, feed_down: [], stale_upstream: 0, feed_stale: [], no_feed_upstream: 0 },
  days: [day('2026-10-04', 0), day('2026-10-05', 0.2), day('2026-10-06', 3.4), day('2026-10-07', 12.3), day('2026-10-08', 4)],
  classification: { class: 'poor', year: 2025, url: URL_ },
  algae: { date: '2026-09-24', level: 0, phrase: 'none seen', n_checks: 22, n_seen: 0, season: 2026 },
  lab_sample: { taken_at: '2026-09-24T10:35+01:00', ecoli: 380 },
  ...extra });
const rows = (d, now = NOW, built = BUILT) => ev.evidenceItems(d, now, built);
const row = (d, what, now) => rows(d, now).rows.find(r => r.what === what);

test('a bathing water: every item with its age and whose it is, in order, and no gaps', () => {
  const { rows: r, gaps } = rows(cromwheel());
  assert.deepEqual(r.map(x => x.what), ['Overflows upstream', 'Rain here', 'Environment Agency rating', 'Algae at the last check', 'Latest lab sample']);
  assert.deepEqual(r.map(x => x.age), ['1 h 30 min ago', '1 h 30 min ago', '2025', '10 days ago', '10 days ago']);
  assert.equal(r[0].say, '0 of 15 discharging, 1 stopped lately. All 15 report live.');
  assert.equal(r[0].src, "The water companies' live feeds");
  assert.equal(r[1].say, 'No rain in the 48&nbsp;h to midday today. The wettest day ahead is Wednesday, with 12&nbsp;mm.');
  assert.match(r[1].src, /^<a href="https:\/\/open-meteo\.com\/">Open-Meteo\.com<\/a>'s forecast$/);
  assert.equal(r[2].say, 'Poor.');
  assert.equal(r[2].src, `<a href="${URL_}">Environment Agency</a>, from its lab samples over up to four seasons`);
  assert.match(r[3].say, /^None seen, 24 Sept?\.$/);
  assert.match(r[4].say, /^380 E\.&nbsp;coli per 100&nbsp;ml, taken 24 Sept?: <a href="#about-ecoli">under 900<\/a>\.$/);
  assert.equal(gaps.length, 0);
  const html = ev.evidenceTile(cromwheel(), NOW, BUILT);
  // Folded whole, as the day-by-day numbers are: its figures are on the tiles above it.
  assert.match(html, /^<details class="tile fold" id="evidence"><summary><span class="t-lab" id="evidence-h">/);
  assert.ok(html.endsWith('</details>'));
  assert.match(html, /What the level rests on/);
  assert.match(html, /<div class="f-l">Latest lab sample<\/div><div class="f-v">10 days ago<\/div>/);
  assert.doesNotMatch(html, /ev-gap/, 'no gaps, no empty rule');
});

test('ages are counted when the page is read, in UK time, by the clock within a day and the calendar after', () => {
  const at = iso => ev.evidenceAge(iso, NOW);
  assert.equal(at('2026-10-04T16:15:00+01:00'), '45 min ago');
  assert.equal(at('2026-10-04T15:00:00+01:00'), '2 h ago');
  assert.equal(at('2026-10-04T18:00:00+01:00'), '0 min ago', 'a clock behind the build says no more than now');
  assert.equal(at('2026-10-03T23:30:00+01:00'), '17 h 30 min ago');
  assert.equal(at('2026-10-03T09:00:00+01:00'), 'Yesterday');
  assert.equal(at('2026-10-04'), 'Today');
  assert.equal(at('2026-10-03'), 'Yesterday');
  assert.equal(at('2026-09-24'), '10 days ago');
  assert.equal(at('2026-05-20'), '4 months ago');
  // A sample taken at 00:30 UK time is that UK day, not the UTC one before it.
  assert.equal(at('2026-10-03T00:30:00+01:00'), 'Yesterday');
  // A build ten hours old says so on every row read from it.
  assert.equal(row(cromwheel(), 'Overflows upstream', Date.parse('2026-10-05T01:29:52+01:00')).age, '10 h ago');
});

test('the overflows say which report live, and why the others do not, in the data states', () => {
  const say = now => row(cromwheel({ now: { discharging_upstream: 1, recent_upstream: 2, ...now } }), 'Overflows upstream').say;
  // forecast.live_counts with no_feed_upstream: offline monitors told from a company with no live feed.
  assert.equal(say({ monitored_upstream: 12, no_feed_upstream: 2, stale_upstream: 0, feed_down_upstream: 0 }),
    '1 of 15 discharging, 2 stopped lately. 12 of 15 report live. Not reporting: 1 offline; 2 with no live feed.');
  // A forecast from before that field: the two cannot be told apart, and the page does not guess.
  assert.equal(say({ monitored_upstream: 12, stale_upstream: 0, feed_down_upstream: 0 }),
    '1 of 15 discharging, 2 stopped lately. 12 of 15 report live. Not reporting: 3 offline or with no live feed.');
  // A stale feed and a feed that is down are named with their company, a stale one with its last update.
  assert.equal(say({ monitored_upstream: 10, no_feed_upstream: 0, stale_upstream: 3, feed_down_upstream: 2,
    feed_stale: [{ company: 'Southern Water', overflows: 3, since: '2026-10-03T08:12:00+00:00' }],
    feed_down: [{ company: 'Thames Water', overflows: 2, since: null }] }),
    "1 of 15 discharging, 2 stopped lately. 10 of 15 report live. Not reporting: 2 on Thames Water's feed, which is down; 3 on Southern Water's feed, not updated since 3 Oct, 09:12.");
  assert.match(say({ monitored_upstream: 14, no_feed_upstream: 0, stale_upstream: 1, feed_stale: [{ company: 'South West Water', overflows: 1, since: null }] }),
    /Not reporting: 1 on South West Water's feed, which gives no update time\.$/);
  // Every overflow on a company with no live feed (Dŵr Cymru Welsh Water's, upstream on the Wye).
  const wye = cromwheel({ upstream_summary: { overflows: 14 }, now: { discharging_upstream: 0, recent_upstream: 0, monitored_upstream: 0, no_feed_upstream: 14 } });
  assert.equal(row(wye, 'Overflows upstream').say, '0 of 14 discharging. None of 14 report live. Not reporting: 14 with no live feed.');
  const one = cromwheel({ upstream_summary: { overflows: 1 }, now: { discharging_upstream: 0, recent_upstream: 0, monitored_upstream: 1 } });
  assert.equal(row(one, 'Overflows upstream').say, '0 of 1 discharging. It reports live.');
  const html = ev.evidenceTile(cromwheel({ now: { monitored_upstream: 14, stale_upstream: 1, feed_stale: [{ company: '<b>X</b>', overflows: 1, since: null }] } }), NOW, BUILT);
  assert.match(html, /on &lt;b&gt;X&lt;\/b&gt;'s feed/, 'a company name from a feed is escaped');
});

test('what is missing is said plainly: no sample yet, a sample not in the data, no algae check, no rating yet', () => {
  assert.deepEqual(rows(cromwheel({ lab_sample: null })).gaps, ['No lab sample here this season.']);
  const absent = cromwheel(); delete absent.lab_sample;
  assert.deepEqual(rows(absent).gaps, [`The latest lab sample is not in this forecast's data: <a href="${URL_}">the Environment Agency's page</a> has it.`]);
  assert.ok(!rows(absent).rows.some(r => r.what === 'Latest lab sample'));
  assert.deepEqual(rows(cromwheel({ algae: undefined })).gaps, ['No algae check here this season.']);
  assert.deepEqual(rows(cromwheel({ classification: { url: URL_ } })).gaps, ['No Environment Agency rating yet: this bathing water is too new to have one.']);
  const html = ev.evidenceTile(cromwheel({ lab_sample: null, algae: undefined }), NOW, BUILT);
  assert.match(html, /<div class="ev-gap"><p>No algae check here this season\.<\/p><p>No lab sample here this season\.<\/p><\/div>/);
});

test('a lab count at a limit says so, and one from last season gives its year', () => {
  assert.match(row(cromwheel({ lab_sample: { taken_at: '2026-09-24T10:35+01:00', ecoli: 10, qualifier: '<' } }), 'Latest lab sample').say, /^Under 10 E\./);
  assert.match(row(cromwheel({ lab_sample: { taken_at: '2026-09-24T10:35+01:00', ecoli: 24196, qualifier: '>' } }), 'Latest lab sample').say, /^Over 24,196 E\./);
  const winter = Date.parse('2027-02-10T12:00:00Z');
  const r = row(cromwheel(), 'Latest lab sample', winter);
  assert.match(r.say, /taken 24 Sept? 2026: <a href="#about-ecoli">under 900<\/a>\.$/);
  assert.equal(r.age, '4 months ago');
  assert.equal(ev.evidenceAge('2026-08-05', NOW), '1 month ago');   // 60 days: months from there
});

test('a lab count says whether it is over 900, the line the E. coli estimate is about, where the count settles it', () => {
  const said = (ecoli, qualifier) => ev.evidenceSample({ taken_at: '2026-09-24T10:35+01:00', ecoli, ...(qualifier ? { qualifier } : {}) }, NOW)
    .replace(/ /g, ' ').replace(/Sept?/, 'Sep');
  assert.equal(said(380), '380 E. coli per 100 ml, taken 24 Sep: under 900.');
  assert.equal(said(899), '899 E. coli per 100 ml, taken 24 Sep: under 900.');
  assert.equal(said(900), '900 E. coli per 100 ml, taken 24 Sep: not over 900.', 'exactly 900 is not over it');
  assert.equal(said(901), '901 E. coli per 100 ml, taken 24 Sep: over 900.');
  assert.equal(said(3900), '3,900 E. coli per 100 ml, taken 24 Sep: over 900.');
  assert.equal(said(10, '<'), 'Under 10 E. coli per 100 ml, taken 24 Sep: under 900.');
  assert.equal(said(10000, '>'), 'Over 10,000 E. coli per 100 ml, taken 24 Sep: over 900.');
  assert.equal(said(900, '>'), 'Over 900 E. coli per 100 ml, taken 24 Sep: over 900.');
  // A limit that does not settle it is not compared: under 1,000 may be over 900, and over 500 may not.
  assert.equal(said(1000, '<'), 'Under 1,000 E. coli per 100 ml, taken 24 Sep.');
  assert.equal(said(500, '>'), 'Over 500 E. coli per 100 ml, taken 24 Sep.');
  assert.equal(ev.evidenceSample(null, NOW), '');
  assert.equal(ev.evidenceSample({ taken_at: '2026-09-24T10:35+01:00', ecoli: null }, NOW), '');
  // The words never call the water safe or rated by one sample; on the page the comparison links to
  // what 900 means (the About section: a 90th percentile over four seasons, not a test of one sample).
  for (const n of [10, 900, 3900]) assert.doesNotMatch(said(n), /safe|pass|fail|rating|rated|excellent|good|sufficient|poor/i);
  assert.match(ev.evidenceSample({ taken_at: '2026-09-24T10:35+01:00', ecoli: 3900 }, NOW, true), /: <a href="#about-ecoli">over 900<\/a>\.$/);
  const html = fs.readFileSync(join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  assert.match(html, /<dt id="about-ecoli">[^]*?900 is the threshold used in the inland "sufficient" classification, which is a 90th-percentile calculation over four seasons, not a pass\/fail test of one sample/);
});

test('the Compare table gives the latest sample in the same words, or says plainly there is none', () => {
  const { evidenceRows } = require('../src/dipcast/site/experience.js');
  const samples = s => Object.fromEntries(evidenceRows({ days: [], ...s }, '2026-10-04', '', BUILT, NOW))['Water samples'].replace(/ /g, ' ');
  const cl = { class: 'poor', year: 2025, url: URL_ };
  assert.match(samples({ source: 'designated', classification: cl, lab_sample: { taken_at: '2026-09-24T10:35+01:00', ecoli: 380 } }),
    /^380 E\. coli per 100 ml, taken 24 Sept?: under 900\. Check the Environment Agency’s page for every result and current advice\.$/);
  assert.equal(samples({ source: 'designated', classification: cl, lab_sample: null }), 'No lab sample this season. Check the Environment Agency’s page for every result and current advice.');
  assert.equal(samples({ source: 'designated', classification: cl }), 'No lab sample in this update. Check the Environment Agency’s page for every result and current advice.');
  assert.equal(samples({ source: 'designated' }), 'No lab sample in this update.');
  assert.equal(samples({ source: 'curated' }), 'No lab samples here.');
  // The panel and the table say the sample the same way.
  const s = { taken_at: '2026-09-24T10:35+01:00', ecoli: 1500 };
  assert.ok(samples({ source: 'designated', classification: cl, lab_sample: s }).startsWith(ev.evidenceSample(s, NOW).replace(/ /g, ' ')));
  assert.doesNotMatch(samples({ source: 'designated', classification: cl }), /not included/);
});

test('a river spot that is not a bathing water: the overflows and the rain, and no EA records', () => {
  const eden = { id: 'eden-armathwaite', source: 'curated', kind: 'river', assumptions: { max_upstream_km: 60 }, upstream_summary: { overflows: 60 },
    now: { discharging_upstream: 0, recent_upstream: 32, monitored_upstream: 60, no_feed_upstream: 0 },
    days: [day('2026-10-04', 10.8), day('2026-10-05', 3), day('2026-10-06', 1), day('2026-10-07', 6), day('2026-10-08', 2)] };
  const { rows: r, gaps } = rows(eden);
  assert.deepEqual(r.map(x => x.what), ['Overflows upstream', 'Rain here']);
  assert.equal(r[0].say, '0 of 60 discharging, 32 stopped lately. All 60 report live.');
  assert.equal(r[1].say, '11&nbsp;mm of rain in the 48&nbsp;h to midday today.', 'no wetter day ahead, none named');
  assert.deepEqual(gaps, ['No lab samples, algae checks or rating here.']);
});

test('no overflow upstream, and rain that did not arrive, are gaps; an old build names its day', () => {
  const tees = { id: 'tees-low-force', source: 'curated', kind: 'river', assumptions: { max_upstream_km: 60 }, upstream_summary: { overflows: 0 }, now: {},
    days: [day('2026-10-04', 0.3), day('2026-10-05', null), day('2026-10-06', 9), day('2026-10-07', undefined), day('2026-10-08', null)] };
  const { rows: r, gaps } = rows(tees);
  assert.deepEqual(r.map(x => x.what), ['Rain here']);
  assert.equal(r[0].say, 'Under 1&nbsp;mm of rain in the 48&nbsp;h to midday today. The wettest day ahead is Tuesday, with 9&nbsp;mm.');
  assert.deepEqual(gaps, [
    'No monitored overflow within 60&nbsp;km upstream, so no spills to go on; farms, wildlife and unmonitored sources are not modelled.',
    'No rain forecast arrived for Monday, Wednesday or Thursday.',
    'No lab samples, algae checks or rating here.']);
  // Today's rain missing: no rain row, and today among the gaps.
  const dry = { ...tees, days: [day('2026-10-04', null), day('2026-10-05', 2)] };
  assert.deepEqual(rows(dry).rows, []);
  assert.equal(rows(dry).gaps[1], 'No rain forecast arrived for today.');
  // Read the next morning, the build's first day is named rather than called today.
  assert.match(row(tees, 'Rain here', Date.parse('2026-10-05T08:00:00+01:00')).say, /to midday Sunday\./);
});

test('nothing for a point clicked on the map or a spot without a forecast', () => {
  assert.equal(ev.evidenceTile(cromwheel({ unlisted: true }), NOW, BUILT), '');
  assert.equal(ev.evidenceTile(cromwheel({ error: 'An isolated lake: no river reaches it.' }), NOW, BUILT), '');
  assert.equal(ev.evidenceTile(null, NOW, BUILT), '');
});

test("no other script of the page defines one of evidence.js's names", () => {
  // The page's scripts share one global scope: a later `function evidenceRows` (experience.js has one,
  // for the Compare table) silently replaced this file's when it had that name.
  const site = join(__dirname, '../src/dipcast/site');
  const names = src => new Set([...src.matchAll(/^(?:const|let|var|function|async function|class)\s+([A-Za-z_$][\w$]*)/gm)].map(m => m[1]));
  const mine = names(fs.readFileSync(join(site, 'evidence.js'), 'utf8'));
  const html = fs.readFileSync(join(site, 'index.html'), 'utf8');
  const others = [html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')),
    ...fs.readdirSync(site).filter(f => f.endsWith('.js') && !['evidence.js', 'sw.js'].includes(f)).map(f => fs.readFileSync(join(site, f), 'utf8'))];
  const clash = others.flatMap(src => [...names(src)].filter(n => mine.has(n)));
  assert.deepEqual(clash, []);
  assert.ok(mine.has('evidenceTile') && mine.size > 5);
  assert.ok(html.indexOf('src="evidence.js"') > 0 && html.indexOf('src="evidence.js"') < html.indexOf('<script>\n'), 'loaded before the page script that calls it');
});
