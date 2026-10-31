// The headline a group leader reads must not be wrong or falsely reassuring (red-team review, 11 Oct 2026).
// Each test is one finding of that review, on the rule levels.js or the page now follows; the fixtures
// copy the spots as the live spots.json had them that evening. node --test tests/site_honest_headlines.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const L = require('../src/dipcast/site/levels.js');
const Embed = require('../src/dipcast/site/embed.js');
const Sites = require('../src/dipcast/site/sites.js');
const O = require('../src/dipcast/site/organisers.js');
const ev = require('../src/dipcast/site/evidence.js');

const DATES = ['2026-10-11', '2026-10-12', '2026-10-13', '2026-10-14', '2026-10-15'];   // Sunday to Thursday
const GEN = '2026-10-11T20:17:38+01:00', NOW = Date.parse('2026-10-11T21:30:00+01:00');
const RISK = { low: 0.01, moderate: 0.23, high: 0.5, 'very high': 0.8 };
const week = (labels, extra = {}) => ({ id: 'x', name: 'A river', kind: 'river', source: 'curated', upstream_summary: { overflows: 3 },
  location: { mode: 'river' }, now: { label: 'low', risk: 0, discharging_upstream: 0, monitored_upstream: 3 }, contributors: [],
  assumptions: { max_upstream_km: 60, recent_spill_hours: 48 },
  days: labels.map((l, i) => ({ date: DATES[i], label: l, risk: RISK[l], p_ecoli_gt900: 0.03, in_validated_season: false, rain_48h_mm: 1 })), ...extra });
L.setToday(DATES[0]);

// Top-level definitions taken from index.html's script, as tests/site_planner.test.cjs does.
const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const pageSrc = html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n');
const pageDefs = names => names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`) || l.startsWith(`let ${n} =`));
  assert.ok(i >= 0, `no ${n} in index.html`);
  let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
  return pageSrc.slice(i, j).join('\n'); }).join('\n');
class FixedDate extends Date { constructor(...a) { if (!a.length) super(NOW); else super(...a); } static now() { return NOW; } }
function page(names, extra = {}) {
  const ctx = vm.createContext({ Date: FixedDate, ROOT: { pathname: '/' }, milesAway: m => `${m.toFixed(1)} miles away`, MILE_KM: 1.609, ...extra });
  const dir = path.join(__dirname, '../src/dipcast/site/');
  vm.runInContext(fs.readFileSync(dir + 'experience.js', 'utf8'), ctx);
  vm.runInContext(fs.readFileSync(dir + 'levels.js', 'utf8') + `\nsetToday("${DATES[0]}");`, ctx);
  vm.runInContext(pageDefs(names), ctx);
  return ctx;
}
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;| /g, ' ').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();
// The helpers nearby() calls for each row's reason and the other-water rule (site_nearby_reasons.test.cjs).
const NEAR_REASONS = ['joined', 'otherWater', 'unread', 'fewerUnread', 'nearWhy', 'otherAsWell'];
const ANSWER = ['esc', 'tone', 'headTone', 'rainSaid', 'answerParts', 'flowLine', 'ageMin', 'ago', 'issued', 'nextDay', 'yesterdayLine', 'answerWords',
  'sinceTime', 'spillFor', 'overflowSaid', 'longSpillLine', 'eaSaid', 'coverWords', 'coverLine', 'answerAfter'];

// ------------------------------------------------------------------------------ 1. the EA's advice for today
// Frensham Great Pond: "Low risk for the next five days" and "Usual care", while the EA's own panel said
// "Bathing is not advised today due to pollution from harmful algae". Neither the build nor the page can read it.
const frensham = week(['low', 'low', 'low', 'low', 'low'], { id: 'bw-ukj2310-11945', name: 'Frensham Great Pond', kind: 'lake', source: 'designated',
  location: { mode: 'lake' }, upstream_summary: { overflows: 1 },
  classification: { class: 'excellent', year: 2025, url: 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945' } });

test('at every designated bathing water the answer says the EA advice could not be checked, beside the level and what to do', () => {
  assert.equal(L.eaUnchecked(frensham), true);
  assert.equal(L.eaUnchecked({ ...frensham, source: 'curated', classification: undefined }), false);
  assert.equal(L.eaUnchecked({ ...frensham, unlisted: true }), false);   // a point clicked on the map
  assert.equal(L.headline(frensham), 'Low risk for the next five days');   // the level itself does not pretend to know
  const ctx = page(ANSWER, { DATA: { generated_at: GEN } });
  // Since 20 Oct 2026 a clause of the line on what the forecast could read (coverLine), just above the issue
  // time, short, with where to look; what to do follows the five days (answerAfter).
  const h = vm.runInContext('answerWords', ctx)(frensham);
  // The live status leads the answer (levels.js, liveLine); the line on what it could read keeps the EA advice.
  assert.match(h, /^<p class="live">Live status from the overflow upstream: not spilling at the last poll\.<\/p><h2 /);
  assert.match(h, /<p class="cover">Today's EA advice not checked: <a href="https:\/\/environment\.data\.gov\.uk\/bwq\/profiles\/profile\.html\?site=ukj2310-11945">see the EA's page<\/a> before you swim\.<\/p><p class="issued">/);
  // The embed card says it under what to do, and links the EA's page.
  const card = Embed.card(frensham, { generated_at: GEN }, NOW);
  assert.match(text(card), /Usual care: [^.]+\. The Environment Agency's advice for today could not be checked\. The Environment Agency’s page says when bathing is not advised\./);
  L.setToday(DATES[0]);
  // The shared picture and the sites page say it short.
  assert.match(html, /eaUnchecked\(d\) \? "Today's EA advice not checked: see the EA's page"/);
  assert.match(Sites.words(frensham).why, /Today's EA advice not checked: see the EA's page\./);
});

// ------------------------------------------------------------------------------ 2. a recent failed sample
test('a sample over 900 E. coli in the last 14 days makes every day at least moderate, and the headline names it', () => {
  const sample = (taken, ecoli, qualifier) => week(['low', 'low', 'low', 'low', 'low'], { source: 'designated', classification: { class: 'excellent', year: 2025 },
    lab_sample: { taken_at: `${taken}T11:00+01:00`, ecoli, ...(qualifier ? { qualifier } : {}) } });
  const rutland = sample('2026-10-04', 3800);
  assert.equal(L.sampleLevel(rutland), 'moderate');
  assert.equal(L.level(rutland), 'moderate');
  assert.equal(L.headline(rutland), 'Moderate risk right now: a recent EA sample over 900 E. coli');
  assert.deepEqual(DATES.map(iso => L.dayLevel(rutland, iso)), ['moderate', 'moderate', 'moderate', 'moderate', 'moderate']);
  assert.equal(L.dayHeadline(rutland, DATES[2]), 'Moderate risk: a recent EA sample over 900 E. coli');
  assert.equal(L.levelAction(rutland), L.ACTION.moderate);
  assert.equal(L.tileLine(rutland, 'spill'), 'On its own: low risk. A recent EA sample over 900 E. coli raises the level to moderate risk.');
  // The window: 14 days, as the algae check from the same visit. Rutland's real sample (24 Sep) was 17 days old on 11 Oct.
  assert.equal(L.sampleLevel(sample('2026-09-27', 3800)), 'moderate');
  assert.equal(L.sampleLevel(sample('2026-09-24', 3800)), null);
  assert.equal(L.headline(sample('2026-09-24', 3800)), 'Low risk for the next five days');
  // The line: over 900, as the estimate and the sample row say it; a limit counts only where it settles it.
  assert.equal(L.sampleLevel(sample('2026-10-08', 900)), null);
  assert.equal(L.sampleLevel(sample('2026-10-08', 901)), 'moderate');
  assert.equal(L.sampleLevel(sample('2026-10-08', 10000, '>')), 'moderate');
  assert.equal(L.sampleLevel(sample('2026-10-08', 1000, '<')), null);
  // A worse forecast still sets the level; a poor rating is still named.
  assert.equal(L.level({ ...rutland, days: week(['high', 'low', 'low', 'low', 'low']).days }), 'high');
  assert.equal(L.headline({ ...rutland, classification: { class: 'poor', year: 2025 } }), 'High risk: rated poor');
  // Where the level does not change from day to day (nothing upstream), the sample still raises it.
  const lake = { id: 'l', days: [], upstream_summary: { overflows: 0 }, location: { mode: 'lake' }, source: 'designated',
    classification: { class: 'good', year: 2025 }, lab_sample: { taken_at: '2026-10-06T10:00+01:00', ecoli: 1400 } };
  assert.equal(L.level(lake), 'moderate');
  assert.equal(L.headline(lake), 'Moderate risk: a recent EA sample over 900 E. coli');
  assert.equal(L.levelAction(lake), L.ACTION.moderate);
  assert.equal(L.level({ ...lake, lab_sample: { ...lake.lab_sample, taken_at: '2026-09-22T10:52+01:00' } }), L.NO_OVERFLOWS);
});

test('the sample row says whether the sample counts in the level', () => {
  const row = s => ev.evidenceItems(s, NOW, GEN).rows.find(r => r.what === 'Latest lab sample').say.replace(/<[^>]+>/g, '');
  const base = week(['low', 'low', 'low', 'low', 'low'], { source: 'designated', classification: { class: 'excellent', year: 2025 } });
  assert.match(row({ ...base, lab_sample: { taken_at: '2026-10-06T10:00+01:00', ecoli: 1400 } }), /over 900\. It makes the level at least moderate risk\.$/);
  assert.match(row({ ...base, lab_sample: { taken_at: '2026-09-22T10:52+01:00', ecoli: 1400 } }), /over 900\. Over two weeks old, so not counted in the level\.$/);
  assert.match(row({ ...base, lab_sample: { taken_at: '2026-10-06T10:00+01:00', ecoli: 120 } }), /under 900\.$/);
});

// ------------------------------------------------------------------------------ 3. today and right now
// Greenholme: "Very high risk right now", over a five days whose Today said moderate, and an overflow row
// reading "discharging" beside "spill 1% today".
const YWS = { site_id: 'YWS02298', company: 'Yorkshire Water', site_name: null, receiving_watercourse: '#N/A', lat: 53.93, lon: -1.8, status: 1,
  data_state: 'live', latest_event_start: '2026-10-06T10:46:39+00:00', latest_event_end: null, distance_km: 4.4, lake_distance_km: 0, travel_h: 2.4,
  weight: 0.749, p_spill_today: 0.011, position_source: 'live' };
const greenholme = week(['moderate', 'low', 'very high', 'moderate', 'very high'], { id: 'osm-wharfe-greenholme', name: 'River Wharfe, Greenholme',
  upstream_summary: { overflows: 25 }, contributors: [YWS],
  now: { risk: 0.798, label: 'very high', discharging_upstream: 1, recent_upstream: 3, monitored_upstream: 23,
    source: { site_id: 'YWS02298', site_name: null, receiving_watercourse: '#N/A', status: 1, distance_km: 4.4, lake_distance_km: 0, travel_h: 2.4, share: 0.865, spread_over: 2 } } });

test("today is at least right now's level, and says it comes from the spills under way", () => {
  assert.equal(L.headline(greenholme), 'Very high risk right now: sewage spills');
  assert.equal(L.dayLevel(greenholme, DATES[0]), 'very high');
  assert.equal(L.dayHeadline(greenholme, DATES[0]), 'Very high risk: sewage spills right now');
  assert.equal(L.dayLevel(greenholme, DATES[1]), 'low');   // tomorrow is the forecast's
  assert.equal(L.tileLine(greenholme, 'spill', DATES[0]), "Spills right now raise today's level to very high risk.");
  // Recent spills, none running: said so.
  const recent = { ...greenholme, now: { ...greenholme.now, label: 'moderate', discharging_upstream: 0 } };
  assert.equal(L.dayHeadline({ ...recent, days: week(['low', 'low', 'low', 'low', 'low']).days }, DATES[0]), 'Moderate risk: recent sewage spills');
  // A low right now raises nothing, and a day without a forecast stays without one.
  const calm = week(['low', 'low', 'low', 'low', 'low']); calm.days[0] = { date: DATES[0], label: 'unknown', risk: null };
  assert.equal(L.dayHeadline(calm, DATES[0]), 'No forecast for this day');
  // The week's bars and the five days' rows go by the same rule.
  const ctx = page(['esc', 'fmt', 'tone', 'initial', 'week', 'spilling', 'summary', 'daysSentence']);
  assert.match(vm.runInContext('week', ctx)(greenholme), /^<span class="week"[^>]*><span class="wk first"><i class="veryhigh">/);
  // Each day carries its letter and its short name; the wide list (1,200 px and up) shows the name.
  const shortName = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'short' });
  assert.deepEqual([...vm.runInContext('week', ctx)(greenholme).matchAll(/<span class="d3">([^<]+)<\/span>/g)].map(m => m[1]), DATES.slice(0, 5).map(shortName));
  assert.match(text(vm.runInContext('daysSentence', ctx)(greenholme)), /^1 upstream overflow is discharging now: very high risk from it right now\. /);
});

test('an overflow discharging now says since when, not a chance of a spill, and a long one may be a fault', () => {
  const ctx = page(['esc', 'fmt', 'feedTime', 'endedOn', 'runningAtLastAnswer', 'statusText', 'colourFor', 'drawnStatus', 'sinceTime', 'spillFor', 'statusSaid',
    'overflowSaid', 'longSpillLine', 'glyph', 'ICON', 'PAGE_ID', 'upgradeDay', 'upgradeNote', 'EA_EVENTS', 'dryWeatherNote', 'overflowTile'],
  { L: { circleMarker: () => ({ bindTooltip: () => ({ addTo: () => {} }) }) }, contribLayer: {} });
  const row = text(vm.runInContext('overflowTile', ctx)(greenholme, 25));
  assert.match(row, /YWS02298 Yorkshire Water · discharging since Tue 6 Oct, 11:46, for over 5 days: a spill this long may be a monitor fault · 4\.4 km upstream, about 2 h away/);
  assert.match(row, /75% weight discharging now/);
  assert.doesNotMatch(row, /spill 1% today/);
  // Under two days: since when, and nothing about a fault.
  const fresh = { ...YWS, latest_event_start: '2026-10-11T15:00:00+00:00' };
  assert.equal(vm.runInContext('statusSaid', ctx)(fresh), 'discharging since Sun 11 Oct, 16:00');
  // Beside the answer: the overflow that sets right now's level, since when, and that it may be a fault.
  assert.equal(text(vm.runInContext('longSpillLine', ctx)(greenholme)), 'Most of the risk right now comes from Yorkshire Water overflow YWS02298 (no name in its feed), '
    + 'which has reported discharging since Tue 6 Oct, 11:46, for over 5 days. A spill this long is unusual and may be a monitor fault. It still counts in the risk.');
  assert.equal(vm.runInContext('longSpillLine', ctx)({ ...greenholme, contributors: [fresh] }), '');
  assert.equal(L.longSpill(YWS, NOW), true);
  assert.equal(L.spillStart({ ...YWS, latest_event_end: '2026-10-07T10:00:00+00:00' }), null);   // ended: not under way
  // The map's pop-up says it too.
  assert.match(html, /<br>Status: \$\{statusSaid\(p\)\}<br>/);
});

// ------------------------------------------------------------------------------ 4. a worse later day
// The Eden at Lazonby: "Moderate risk today" while Tuesday and Thursday were very high.
const lazonby = week(['moderate', 'moderate', 'very high', 'high', 'very high'], { id: 'eden-lazonby', name: 'River Eden, Lazonby' });
test('a later day worse than the headline is named after it, wherever the headline shows', () => {
  assert.deepEqual(L.headParts(lazonby), ['Moderate risk today', 'sewage spills', 'Very high risk on Tuesday']);
  assert.equal(L.headline(lazonby), 'Moderate risk today: sewage spills · Very high risk on Tuesday');
  assert.equal(L.weekNext(lazonby), 'Very high risk on Tuesday');
  // Not where it is no worse: Greenholme's very high Tuesday under its very high right now.
  assert.equal(L.headParts(greenholme)[2], '');
  // A water rated poor, high every day, with a very high later day.
  const poor = { ...lazonby, days: week(['low', 'low', 'very high', 'low', 'low']).days, classification: { class: 'poor', year: 2025 } };
  assert.equal(L.headline(poor), 'High risk: rated poor · Very high risk on Tuesday');
  assert.equal(L.weekNext(poor), 'At least high risk every day; very high risk on Tuesday');
  // The embed says it once; the sites page in its line; the list row and the map's tooltip through headline().
  const card = Embed.card(lazonby, { generated_at: GEN }, NOW);
  assert.ok(card.includes('<p class="hl moderate">Moderate risk today: sewage spills · Very high risk on Tuesday</p>'));
  assert.equal((card.match(/Very high risk on Tuesday/g) || []).length, 1);
  L.setToday(DATES[0]);
  assert.match(Sites.words(lazonby).why, /^Sewage spills\. Very high risk on Tuesday\./);
  // The shared picture draws the third part: the list's, or with the answer's scoped words, laterWords.
  assert.match(html, /\[head, why, later\] = scoped \? \[`\$\{ans\.word\} \$\{ans\.noun\}`, iso \? dateLabel\(iso\) : ans\.why, iso \? '' : laterWords\(d\)\]\n\s+: iso \? \[dayHeadline\(d, iso\), dateLabel\(iso\), ''\] : headParts\(d\)/);
});

// ------------------------------------------------------------------------------ the headline's scope
// An outside review (20 Oct 2026) read "Moderate risk" at Long Bridges, Oxford, as a verdict on the water and
// asked for a headline that says what it covers. Where the spills set the level, the answer's noun names
// them (levels.js, HEAD_SCOPE) and the line under it says when. Where something else set it (a poor
// rating, algae, the E. coli estimate), "<Level> risk" over its cause, as before. Every level keeps its noun.
const J = x => JSON.parse(JSON.stringify(x));   // out of the page's realm
test('the answer names what its level covers where the spills set it, and every level keeps its noun', () => {
  const parts = vm.runInContext('answerParts', page(ANSWER, { DATA: { generated_at: GEN } }));
  const head = (s, iso = null) => { const m = parts(s, iso); return J([m.word ? `${m.word} ${m.noun}` : m.head, m.why]); };
  const spill = week(['low', 'high', 'low', 'low', 'low']);
  const recent = week(['low', 'low', 'low', 'low', 'low'], { now: { label: 'moderate', risk: 0.2, discharging_upstream: 0, recent_upstream: 2, monitored_upstream: 3 } });
  const poor = { ...week(['low', 'low', 'low', 'low', 'low']), source: 'designated', classification: { class: 'poor', year: 2025 } };
  const algae = week(['low', 'low', 'low', 'low', 'low'], { algae: { level: 3, date: DATES[0], phrase: 'algae present' } });
  const summer = week(['low', 'low', 'low', 'low', 'low']);
  summer.days = summer.days.map(x => ({ ...x, p_ecoli_gt900: 0.6, in_validated_season: true }));
  const cases = [
    [spill, null, ['High risk from sewage spills', 'Tomorrow']],
    [greenholme, null, ['Very high risk from sewage spills', 'Right now']],
    [recent, null, ['Moderate risk from sewage spills', 'Recent spills, right now']],
    [week(['low', 'low', 'low', 'low', 'low']), null, ['Low risk from sewage spills', 'For the next five days']],
    [spill, DATES[1], ['High risk from sewage spills', '']],   // a picked day: its date follows
    [poor, null, ['High risk', 'Rated poor']],
    [algae, null, ['High risk', 'Algae at the last check right now']],   // as on main
    [summer, null, ['Very high risk', 'High E. coli likely today']]];
  for (const [s, iso, want] of cases) {
    assert.deepEqual(head(s, iso), want);
    assert.match(want[0], /^(Low|Moderate|High|Very high) risk( from sewage spills)?$/);   // the level word keeps its noun
  }
  // The rendered answer: one heading, every word at one size (the .big class), then when.
  const h = vm.runInContext('answerWords', page(ANSWER, { DATA: { generated_at: GEN } }))(spill);
  assert.match(h, /^<p class="live">Live status from all 3 overflows upstream: none spilling at the last poll\.<\/p><h2 class="big high" id="risk-headline">High risk from sewage spills<\/h2><div class="wn"><p class="why">Tomorrow<\/p>/);
  // A saved card keeps "High risk" beside the week, with the cause in its line, as a list row does.
  assert.equal(parts(spill).sub, 'Sewage spills tomorrow');
  // The list, the map's tooltips, Nearby and the alerts keep headline(): the cause after a colon.
  assert.equal(L.headline(spill), 'High risk tomorrow: sewage spills');
  // Plain levels do not change.
  const clear = { ...week(['low', 'low', 'low', 'low', 'low']), upstream_summary: { overflows: 0 } };
  assert.equal(head(clear)[0], 'No monitored overflow found upstream');
});

// ------------------------------------------------------------------------------ 5. none of the overflows reports
// Hereford, Symonds Yat and Sandy Lane: "0 of 14 discharging", where none of the 14, all Dŵr Cymru's, reports.
const hereford = week(['low', 'low', 'moderate', 'low', 'low'], { id: 'wye-hereford', name: "River Wye, Bishop's Meadow, Hereford", upstream_summary: { overflows: 14, wales_share: 0.29 },
  now: { risk: 0, label: 'low', discharging_upstream: 0, recent_upstream: 0, monitored_upstream: 0, no_feed_upstream: 14 },
  contributors: [{ site_id: 'DCW1', company: 'Dwr Cymru Welsh Water', site_name: 'HAY ON WYE/STW', status: -2, data_state: 'no_feed', distance_km: 30, lake_distance_km: 0, travel_h: 16, weight: 0.3, p_spill_today: 0.02 }] });
const TILES = ['esc', 'fmt', 'feedTime', 'runningAtLastAnswer', 'statusText', 'feedDown', 'feedStale', 'liveSay', 'recentSay', 'overflowDots', 'glyph', 'ICON', 'noFeedSaid', 'nowTile'];
test('where none of the overflows reports, Right now is unknown, never "0 of 14 discharging"', () => {
  const ctx = page(TILES);
  const t = vm.runInContext('nowTile', ctx)(hereford, 14);
  assert.equal(t.fig, 'Unknown');
  assert.equal(t.unit, undefined);
  assert.equal(text(t.say), 'None of the 14 overflows upstream report live, so whether any is discharging is not known. Dŵr Cymru Welsh Water has no live feed SwimSignal reads.');
  // Some report: the count alone, and how many report. Which do not, and that they could be spilling
  // unseen, is a row of Not known here since 20 Oct 2026 (unknowns): the tile says what is observed.
  const some = vm.runInContext('nowTile', ctx)(greenholme, 25);
  assert.deepEqual([some.fig, some.unit], [1, 'discharging']);
  assert.match(text(some.say), /23 of 25 report live\.$/);
  assert.doesNotMatch(some.say, /unseen/);
  // All report: as before.
  assert.deepEqual([vm.runInContext('nowTile', ctx)(week(['low', 'low', 'low', 'low', 'low']), 3).unit], ['of 3 discharging']);
  // The evidence row says the same.
  assert.match(ev.evidenceOverflows(hereford, GEN).say, /^Whether any is discharging is not known\. None of 14 report live\./);
});

// The review of this work (12 Oct 2026) found the headline still took a right now with no reading behind
// it as a real low: five live spots read "Low risk on every day with a forecast" beside an Unknown tile.
test('where no overflow upstream reports live, the headline does not claim a low right now', () => {
  const quiet = { ...hereford, days: week(['low', 'low', 'low', 'low', 'low']).days };
  assert.equal(L.nowUnknown(quiet), true);
  assert.equal(L.risk(quiet, quiet.now, true).level, null);
  assert.equal(L.level(quiet), 'low');   // the forecast's level, from the days
  assert.equal(L.headline(quiet), 'Live sewage spill status unavailable: low risk forecast');
  const later = { ...hereford, days: week(['low', 'low', 'moderate', 'low', 'low']).days };
  assert.equal(L.headline(later), 'Live sewage spill status unavailable: low risk forecast · Moderate risk on Tuesday');
  assert.doesNotMatch(L.headline(later), /now ·/);
  // A forecast day above low says its own day, as before; it claims nothing about now.
  // With nothing upstream reporting, it says the level is modelled (review of PR #463).
  assert.equal(L.headline({ ...hereford, days: week(['low', 'moderate', 'low', 'low', 'low']).days }), 'Moderate risk tomorrow: sewage spills (modelled, no live status)');
  // Right now raised from spills that stopped lately still counts, reporting or not.
  const recent = { ...quiet, now: { ...quiet.now, label: 'moderate', risk: 0.2 } };
  assert.equal(L.nowUnknown(recent), false);
  assert.equal(L.headline(recent), 'Moderate risk right now: recent sewage spills');
  // Some report: right now is known for those, and the headline is as before.
  const some = { ...quiet, now: { ...quiet.now, monitored_upstream: 3 } };
  assert.equal(L.nowUnknown(some), false);
  assert.equal(L.headline(some), 'Low risk for the next five days');
  // Judged by weight where the build gives it (12 Oct 2026): Sandy Lane, 1 of 13 reporting with 0.3% of
  // the weight, is not known; the Medway at Tonbridge, 65 of 67 with 66%, is.
  const sandy = { ...quiet, upstream_summary: { overflows: 13 }, now: { ...quiet.now, monitored_upstream: 1, monitored_weight: 0.0097, upstream_weight: 2.839 } };
  assert.equal(L.nowUnknown(sandy), true);
  assert.equal(L.headline(sandy), 'Live status from 1 of 13 overflows upstream: low risk forecast');
  const medway = { ...quiet, upstream_summary: { overflows: 67 }, now: { ...quiet.now, monitored_upstream: 65, monitored_weight: 1.5, upstream_weight: 2.261 } };
  assert.equal(L.nowUnknown(medway), false);
  assert.equal(L.headline(medway), 'Low risk for the next five days');
  assert.equal(L.nowUnknown({ ...sandy, now: { ...sandy.now, discharging_upstream: 1, label: 'low' } }), false);   // a discharge is known
  // A Northumbrian spot whose feed went stale: the same rule (no no_feed count needed).
  const stale = { ...quiet, now: { label: 'low', risk: 0, discharging_upstream: 0, monitored_upstream: 0, stale_upstream: 8 }, upstream_summary: { overflows: 8 } };
  assert.equal(L.headline(stale), 'Live sewage spill status unavailable: low risk forecast');
  // The spot's page: the live status first, then the level labelled as the modelled forecast, with its inputs.
  const ctx = page(ANSWER, { DATA: { generated_at: GEN } });
  const h = text(vm.runInContext('answerWords', ctx)(quiet));
  assert.match(h, /^Live sewage spill status unavailable: none of the 14 overflows upstream reports live, so whether any is spilling is not known\. Modelled forecast Low risk from sewage spills From the rain forecast and each overflow's past spills, not from live readings/);
  assert.match(vm.runInContext('answerWords', ctx)(quiet), /^<p class="live live-off">Live sewage spill status unavailable: .*<\/p><p class="modelled">Modelled forecast<\/p><h2 class="big low"/);
  // The embed and the sites page give the same headline.
  assert.match(text(Embed.card(quiet, { generated_at: GEN }, NOW)), /Live sewage spill status unavailable: low risk forecast/);
  assert.match(Sites.words(quiet).head, /^Live sewage spill status unavailable$/);
  assert.match(Sites.words(quiet).why, /^Low risk forecast\./);
});

test('"Lower risk nearby" does not count a day with no forecast as no higher, nor offer a spot whose right now is not known', () => {
  const near = (id, labels, extra = {}) => week(labels, { id, name: id, lat: 53.93, lon: -1.83, ...extra });
  const here = near('here', ['high', 'high', 'high', 'high', 'high']);
  const gaps = near('gaps', ['low', 'low', 'low', 'low', 'low']); gaps.days[3] = { date: DATES[3], label: 'unknown', risk: null }; gaps.days[4] = { date: DATES[4], label: 'unknown', risk: null };
  const unknownNow = near('dark', ['low', 'low', 'low', 'low', 'low'], { now: { label: 'low', risk: 0, discharging_upstream: 0, monitored_upstream: 0 } });
  const fine = near('fine', ['low', 'low', 'low', 'low', 'low']);
  const ctx = page(['esc', 'tone', 'km', 'away', 'PAGE_ID', 'spotPath', 'glyph', 'ICON', 'headNote', 'NEAR_KM', 'notHigherAnyDay', 'allFiveDays', 'ratedBetter', ...NEAR_REASONS, 'nearby'],
    { DATA: { spots: [here, gaps, unknownNow, fine] } });
  vm.runInContext('var DAY = null;', ctx);
  const h = vm.runInContext('nearby', ctx)(here);
  assert.ok(h.includes('data-id="fine"'));
  assert.ok(!h.includes('data-id="gaps"'), 'two days with no forecast are not "no higher"');
  assert.ok(!h.includes('data-id="dark"'), 'right now not known is not "lower now"');
  assert.match(text(h), /Lower now, and no higher on any of the five days\./);
  // This spot without a fifth day: the claim says which days it compared.
  const short = near('short', ['high', 'high', 'high', 'high', 'high']); short.days[4] = { date: DATES[4], label: 'unknown', risk: null };
  vm.runInContext('DATA.spots.push', ctx).call(vm.runInContext('DATA.spots', ctx), short);
  assert.match(text(vm.runInContext('nearby', ctx)(short)), /Lower now, and no higher on any day with a forecast here\./);
});

test('a plan row does not say spills are unlikely to reach a spot where spills right now raised today', () => {
  const ctx = page(['esc', 'spilling', 'planWhy'], { DATA: { generated_at: GEN } });
  const why = (s, day) => vm.runInContext('planWhy', ctx)(s, day);
  const g = { ...greenholme, days: week(['low', 'low', 'low', 'low', 'low']).days, classification: undefined };
  g.days[0].expected_spilling_overflows = 1.4;
  assert.equal(L.dayHeadline(g, DATES[0]), 'Very high risk: sewage spills right now');
  assert.doesNotMatch(why(g, DATES[1]), /unlikely to reach/);   // tomorrow's forecast, with nothing expected
  const today = why(g, DATES[0]);
  assert.match(today, /About 1 of the 25 overflows upstream is expected to spill\./);
  assert.doesNotMatch(today, /unlikely to reach here/);
  // With no spill right now, the low day still says why.
  const calm = { ...g, now: { ...g.now, label: 'low', risk: 0, discharging_upstream: 0 } };
  assert.match(why(calm, DATES[0]), /but sewage from them is unlikely to reach here\./);
});

test('Dŵr Cymru is spelt with its circumflex wherever a page names it', () => {
  assert.equal(L.companyName('Dwr Cymru Welsh Water'), 'Dŵr Cymru Welsh Water');
  assert.equal(L.companyName('Yorkshire Water'), 'Yorkshire Water');
  assert.equal(O.overflowRows(hereford)[0].company, 'Dŵr Cymru Welsh Water');
  for (const f of ['index.html', 'organisers.js', 'record.js', 'evidence.js', 'embed.js', 'sites.js'])
    assert.doesNotMatch(fs.readFileSync(path.join(__dirname, '../src/dipcast/site', f), 'utf8').replace(/\/\/[^\n]*/g, ''), /'[^']*\bDwr Cymru/, f);
});

// ------------------------------------------------------------------------------ 7, 10. where an overflow is
test('an overflow in the same lake is across it, one through a lake is by river and lake, a checked join says so', () => {
  const at = (r, l, extra = {}) => L.overflowWhere({ distance_km: r, lake_distance_km: l, ...extra }).replace(/ /g, ' ');
  assert.equal(at(0, 2.6), '2.6 km across the lake');   // Glebe Road PS to Millerground: Bowness is down the lake
  assert.equal(at(1.4, 0.4), '1.8 km upstream by river and lake');   // Ambleside WwTW to Waterhead, by the Rothay
  assert.equal(at(6, 0), '6.0 km upstream');
  assert.equal(at(0, 0, { position_source: 'join' }), "at the spot: its stream joins the river here, to within the map's precision (checked on a map)");   // Culham STW
  assert.equal(at(0, 0), 'at the spot');   // Friday Street SPS at Henley, on its live position (G5, 16 Oct 2026)
  assert.equal(at(0.1, 0), '0.1 km upstream');
  assert.equal(at(0.4, 0, { position_source: 'join' }), '0.4 km upstream, where its stream joins the river (checked on a map)');   // CSO behind Lager's Store
  // The organisers' table and its CSV note.
  const lake = week(['low', 'low', 'low', 'low', 'low'], { upstream_summary: { overflows: 1 }, contributors: [{ site_id: 'UUP00804', site_name: 'Glebe Road PS', company: 'United Utilities',
    receiving_watercourse: 'Lake Windermere', distance_km: 0, lake_distance_km: 2.6, travel_h: 14.3, weight: 0.117, has_live: true }] });
  assert.match(O.overflows(lake), /data-l="Distance">2\.6 km across the lake</);
  assert.match(O.overflows(lake), /<b>Travel<\/b>: how long sewage takes to arrive, at the model's river speed, and across a lake at its slower lake speed\./);
});

// ------------------------------------------------------------------------------ 8. one label for no overflow
test('one honest label where no monitored overflow is found upstream, isolated lake or not', () => {
  const beck = { id: 'b', days: [], upstream_summary: { overflows: 0 }, location: { mode: 'lake' } };
  const tarn = { id: 't', days: [], error: 'An isolated lake: the river network links no monitored storm overflow to it, so the forecast has nothing to say about it.' };
  assert.equal(L.headline(beck), 'No monitored overflow found upstream');
  assert.equal(L.headline(tarn), 'No monitored overflow found upstream');
  for (const w of Object.values(L.COVER)) assert.doesNotMatch(w, /no (sewage )?risk/i);
  // The isolated lake's own reason, where it adds something: the spills row, in plain words, not "An isolated lake".
  const ctx = page(['esc', 'factorRow', 'factors']);
  const row = text(vm.runInContext('factors', ctx)(tarn));
  assert.equal(row, `Sewage spills None found upstream ${L.ISOLATED_WHY} Risk from farms, wildlife, runoff and bathers is not modelled.`);
  assert.doesNotMatch(row, /isolated/i);
  // One colour on the map and in the list, the clear teal.
  const c = page(['tone', 'colour']);
  assert.equal(vm.runInContext('tone', c)(L.NO_RIVER), 'clear');
  assert.equal(vm.runInContext('colour', c)(L.NO_RIVER), vm.runInContext('colour', c)(L.NO_OVERFLOWS));
});

// ------------------------------------------------------------------------------ 9. lower risk nearby
test('"Lower risk nearby" compares the same days, and at a water rated poor offers only better-rated waters', () => {
  const near = (id, labels, extra = {}) => week(labels, { id, name: id, lat: 53.93, lon: -1.83, ...extra });
  const ilkley = near('ilkley', ['low', 'low', 'low', 'low', 'low'], { source: 'designated', classification: { class: 'poor', year: 2025 } });
  const burnsall = near('burnsall', ['low', 'low', 'moderate', 'low', 'very high']);   // low until then, very high on Thursday
  const rated = near('rated', ['low', 'low', 'low', 'low', 'low'], { source: 'designated', classification: { class: 'good', year: 2025 } });
  const unrated = near('calfclose', ['low', 'low', 'low', 'low', 'low']);
  const ctx = page(['esc', 'tone', 'km', 'away', 'PAGE_ID', 'spotPath', 'glyph', 'ICON', 'headNote', 'NEAR_KM', 'notHigherAnyDay', 'allFiveDays', 'ratedBetter', ...NEAR_REASONS, 'nearby'],
    { DATA: { spots: [ilkley, burnsall, rated, unrated] } });
  vm.runInContext('var DAY = null;', ctx);
  const h = vm.runInContext('nearby', ctx)(ilkley);
  assert.ok(h.includes('Lower risk nearby') && h.includes('data-id="rated"'));
  assert.ok(!h.includes('data-id="burnsall"') && !h.includes('data-id="calfclose"'));
  assert.match(text(h), /Rated better than poor by the Environment Agency, and lower now, and no higher on any of the five days\./);
  // Not rated poor: lower on the same days, rated or not; Burnsall is still out, its Thursday very high above high.
  const high = near('high', ['high', 'high', 'high', 'high', 'high']);
  vm.runInContext('DATA.spots.push', ctx).call(vm.runInContext('DATA.spots', ctx), high);
  const g = vm.runInContext('nearby', ctx)(high);
  assert.ok(g.includes('data-id="calfclose"') && !g.includes('data-id="burnsall"'));
  // A picked day compares that day alone.
  vm.runInContext(`DAY = "${DATES[1]}"`, ctx);
  assert.ok(vm.runInContext('nearby', ctx)(high).includes('data-id="burnsall"'));
});

// ------------------------------------------------------------------------------ 11. a lake's gauge
test("a lake's own gauge is a lake level, in or out of its usual range, with nothing about a river", () => {
  const ctx = page(['esc', 'fmt', 'glyph', 'ICON', 'rangeBar', 'riverTile']);
  const windermere = { station: 'Far Sawrey', river: 'Windermere', level_m: 0.73, typical_low_m: 0.228, typical_high_m: 1.0, label: 'high', stale: false,
    observed_at: '2026-10-11T18:45:00Z', distance_km: 3.3, same_river: true, water: 'lake', rloi: '5164' };
  const t = vm.runInContext('riverTile', ctx)(windermere);
  assert.deepEqual([t.label, t.word], ['Lake level', 'In its usual range']);
  assert.doesNotMatch(t.more, /river runs faster/);
  assert.match(text(t.say), /Gauge at Far Sawrey on Windermere, 3\.3 km away/);
  assert.equal(vm.runInContext('riverTile', ctx)({ ...windermere, level_m: 1.2 }).word, 'Above its usual range');
  // A river's gauge keeps its words.
  assert.equal(vm.runInContext('riverTile', ctx)({ ...windermere, water: undefined, river: 'River Wharfe' }).word, 'High water');
});

// ------------------------------------------------------------------------------ 12. the overflows' caption
test("the overflows' caption says what their order is", () => {
  const ov = html.slice(html.indexOf('function overflowTile('), html.indexOf('\n}\n', html.indexOf('function overflowTile(')));
  assert.doesNotMatch(ov, /with the most reach/);
  assert.match(ov, /that matter most this week`/);
});

// ------------------------------------------------------------------------------ Wales and the E. coli estimate
test('overflows in Wales are said not to be counted, with how much of the river is in Wales, wherever the headline shows', () => {
  assert.equal(L.walesWords(hereford).replace(/ /g, ' '), 'Overflows in Wales are not counted: about 29% of the river within 60 km above this spot is in Wales.');
  assert.equal(L.walesWords(hereford, true), 'Overflows in Wales not counted (29% of the river above)');
  assert.equal(L.walesWords(lazonby), '');
  assert.equal(L.walesWords({ ...hereford, upstream_summary: { overflows: 14, wales_share: 0.004 } }, true), 'Overflows in Wales not counted (1% of the river above)');
  const ctx = page(ANSWER, { DATA: { generated_at: GEN } });
  assert.match(text(vm.runInContext('answerWords', ctx)(hereford)), /^Live sewage spill status unavailable: .* Modelled forecast .* Overflows in Wales not counted \(29% of the river above\)\. Issued/);
  const row = page(['esc', 'fmt', 'tone', 'initial', 'VIEW', 'km', 'dist', 'away', 'PAGE_ID', 'spotPath', 'week', 'rainMeta', 'mapLevel', 'listHeadline', 'openDay', 'listPath', 'headNote', 'spotItem']);
  assert.match(vm.runInContext('spotItem', row)(hereford), /<span class="hl-note">Overflows in Wales not counted \(29% of the river above\)<\/span>/);
  assert.match(text(Embed.card(hereford, { generated_at: GEN }, NOW)), /Overflows in Wales are not counted: about 29%/);
  L.setToday(DATES[0]);
  assert.match(Sites.words(hereford).why, /Overflows in Wales not counted \(29% of the river above\)\./);
  assert.match(html, /const notes = \[walesWords\(d, true\), /);   // the shared picture
});

test('the E. coli estimate is labelled with what is true today: its season, its live record, and the Welsh test', () => {
  const check = { live: { n_samples: 37, n_sites: 26, auc: 0.52, brier: 0.107, climatology_brier: 0.104, skill: false },
    wales: { n_samples: 185, mean: 0.324, observed: 0.059 } };
  const off = hereford.days[0], on = { ...off, in_validated_season: true };
  assert.deepEqual(L.ecoliNotes(hereford, check, off), [
    'The level above counts sewage spills. This estimate counts E. coli from any source, but it is tested only for May to September, so it is not part of the level now.',
    'It has not yet shown skill on live samples: on the 37 Environment Agency samples since the forecast began, it did no better than chance at picking out the ones over 900.',
    'A test on 185 Welsh river samples found it far too high: it averaged 32% where 5.9% were over 900.']);
  assert.match(L.ecoliNotes(lazonby, check, on)[0], /is part of the level above from May to September, the only months it is tested for\.$/);
  assert.equal(L.ecoliNotes(lazonby, check, on).length, 2);   // not from Wales
  assert.match(L.ecoliNotes(lazonby, { ...check, live: { ...check.live, skill: true } }, on)[1], /did better than chance/);
  assert.equal(L.ecoliNotes(lazonby, null, on).length, 1);   // a forecast from before the build wrote the record
  // On the page: the full width for its sentences. Out of season (20 Oct 2026) no figure, band or scale in
  // view: "Out of season", named experimental, last, with the figures under "Experimental estimate".
  const ctx = page(ECOLI_PAGE, { DATA: { generated_at: GEN, ecoli_check: check } });
  const facts = vm.runInContext('facts', ctx), tiles = facts({ ...hereford, days: hereford.days.map(x => ({ ...x, p_ecoli_gt900: 0.16 })) });
  const tile = tiles.find(t => /coli/.test(t.label));
  assert.deepEqual([tile.label, tile.fig, tile.word, tile.vis, tile.wide], ['Experimental E.&nbsp;coli estimate', 'Out of season', undefined, undefined, true]);
  assert.equal(tiles[tiles.length - 1], tile);   // after the tiles of what is observed
  assert.equal(text(tile.say), 'The level above counts sewage spills. This estimate counts E. coli from any source, but it is tested only for May to September, so it is not part of the level now.');
  assert.match(tile.fold, /^<details class="more"><summary>Experimental estimate<\/summary>/);
  assert.match(text(tile.fold), /over 900 per 100 ml: 16% today, 16% tomorrow\. It has not yet shown skill .* far too high: it averaged 32% where 5\.9% were over 900\.$/);
  assert.match(tile.more, /AUC is 0\.52: 0\.5 is chance, 1 is perfect/);
  // In season, as before: the figure, its band and its scale, beside the spills and Right now.
  const summer = facts({ ...hereford, days: hereford.days.map(x => ({ ...x, p_ecoli_gt900: 0.16, in_validated_season: true })) });
  const sun = summer.find(t => /coli/.test(t.label));
  assert.deepEqual([sun.label, sun.fig, sun.word, sun.fold], ['E.&nbsp;coli estimate', '16%', 'Moderate risk', undefined]);
  assert.ok(sun.vis.includes('class="scale"') && summer[summer.length - 1] !== sun);
  assert.match(text(sun.say), /^Chance a water sample would show E\. coli over 900 per 100 ml today; 16% tomorrow\. This estimate counts E\. coli from any source, and is part of the level/);
});

// ------------------------------------------------------------------------------ no figure out of season
// Long Bridges, Oxford, 20 Oct 2026 (an outside review): "Moderate risk" over an E. coli tile reading "56%",
// labelled "Untested in October", read as two answers. From October to April no percentage is in a tile's
// figure or sentence, a picked day's row or its value, the shared picture, or the organisers' and the
// decision record's rows. The folded day-by-day numbers keep them, marked †.
const ECOLI_PAGE = ['esc', 'glyph', 'ICON', 'tone', 'scaleBar', 'untested', 'explain', 'factorRow', 'ecoliName', 'ecoliFold', 'ecoliCheck', 'ecoliSaid', 'ecoliMore',
  'noFeedSaid', 'nowTile', 'feedDown', 'feedStale', 'liveSay', 'recentSay', 'overflowDots', 'runningAtLastAnswer', 'statusText', 'feedTime', 'fmt', 'riverTile', 'rangeBar',
  'WT_ROUTES', 'waterEstOk', 'waterEstHow', 'waterEstSay', 'WT_AIR', 'WT_TAIL', 'waterEstMore', 'waterTile', 'weatherOn', 'spilling', 'bandWords', 'initial', 'rainCols', 'sunPath', 'facts', 'UNLISTED_ECOLI', 'water'];
const longBridges = week(['low', 'moderate', 'moderate', 'moderate', 'high'], { id: 'osm-thames-long-bridges', name: 'River Thames, Long Bridges, Oxford',
  source: 'openstreetmap', upstream_summary: { overflows: 45 },
  now: { risk: 0.1, label: 'low', discharging_upstream: 2, recent_upstream: 0, monitored_upstream: 44 },
  access: { status: 'unconfirmed', checked_at: '2026-10-03', url: 'https://www.oxford.gov.uk/news/article/1860/new-signage-to-be-installed-to-improve-water-safety-in-oxford',
    text: 'Oxford City Council lists Longbridges among places receiving water-safety signs and discourages wild swimming. Check the current signs; listing this place does not confirm permission or a maintained entry point.' },
  days: week(['low', 'moderate', 'moderate', 'moderate', 'high']).days.map((x, i) => ({ ...x, p_ecoli_gt900: [0.565, 0.7, 0.712, 0.754, 0.795][i], rain_48h_mm: 16 })) });
// A tile or a row as a reader sees it with nothing opened: everything but its folds.
const inView = h => text(String(h || '').replace(/<details[\s\S]*?<\/details>/g, ''));

test('out of season no E. coli percentage is in view: the tiles, a picked day, the shared picture, the organisers and the record', () => {
  const ctx = page(ECOLI_PAGE, { DATA: { generated_at: GEN, ecoli_check: null } });
  for (const t of vm.runInContext('facts', ctx)(longBridges))
    for (const k of ['label', 'fig', 'unit', 'word', 'vis', 'rel', 'say', 'note'])
      assert.doesNotMatch(inView(t[k]), /\d%/, `${text(t.label)}: ${k}`);
  // A picked day: the value says out of season; the day's figure is under the fold.
  const row = vm.runInContext('water', ctx)(longBridges, [longBridges.days[1]]);
  assert.match(row, /<div class="f-l">Experimental E.&nbsp;coli estimate<\/div><div class="f-v na">Out of season<\/div>/);
  assert.doesNotMatch(inView(row), /\d%/);
  assert.match(text(row), /Experimental estimate Chance a water sample would show E\. coli over 900 per 100 ml: 70% tomorrow\./);
  // In season the row keeps its figure in view.
  const june = { ...longBridges.days[1], in_validated_season: true };
  assert.match(inView(vm.runInContext('water', ctx)(longBridges, [june])), /70% tomorrow/);
  // The shared picture: the E. coli row only while all five days are in season, else the rain.
  assert.match(html, /pct = ecoliTested\(d\) && !anyUntested\(d\)/);
  assert.doesNotMatch(html, /untested\(x\) \? '†'/);
  // The organisers' page and the decision record give the words, not the figure.
  L.setToday(DATES[0]);
  const O_ = O.view(longBridges, DATES[1], { generated_at: GEN, spots: [longBridges] }, 'https://example.org/', NOW);
  assert.ok(O_.includes(L.ECOLI_OFF_SAID) && !/\b70%/.test(O_));
  assert.doesNotMatch(L.ECOLI_OFF_SAID, /\d%/);
});

// ------------------------------------------------------------------------------ Not known here
// What the page could not see, gathered in one tile after the five days (20 Oct 2026, same review): live
// readings missing, overflows in Wales, today's EA advice, access, flood warnings. Each was a sentence
// somewhere else: the Right now tile, the answer, a paragraph under the five days, a note under River level.
const UNKNOWN_PAGE = ['esc', 'glyph', 'ICON', 'factorRow', 'feedTime', 'feedDown', 'feedStale', 'liveSay', 'noFeedSaid', 'eaSaid', 'accessSaid', 'unknowns', 'unknownTile'];
test('Not known here: a row for each gap, in the words it had, and no tile without one', () => {
  const ctx = page(UNKNOWN_PAGE, { DATA: { generated_at: GEN } }), rows = vm.runInContext('unknowns', ctx);
  const said = s => JSON.parse(JSON.stringify(rows(s).map(([l, v, w]) => [l, v, text(w)])));   // out of the page's realm
  assert.deepEqual(said(longBridges), [
    ['Live readings', '1 of 45 not reporting', '44 of 45 report live; the one that does not could be spilling unseen. Each overflow\'s monitor tells its water company\'s live feed when it is discharging, and when its last spill started and ended. It does not measure how much, or what is in it. With no reading, a spill is not known either way.'],
    ['Access', 'Not confirmed', 'Oxford City Council lists Longbridges among places receiving water-safety signs and discourages wild swimming. Check the current signs; listing this place does not confirm permission or a maintained entry point. Authority guidance . Desk check 2026-10-03; current signs have not been inspected.']]);
  assert.deepEqual(said(hereford), [
    ['Live readings', '14 of 14 not reporting', '0 of 14 report live; the 14 that do not could be spilling unseen. Dŵr Cymru Welsh Water has no live feed SwimSignal reads. Each overflow\'s monitor tells its water company\'s live feed when it is discharging, and when its last spill started and ended. It does not measure how much, or what is in it. With no reading, a spill is not known either way.'],
    ['Overflows in Wales', 'Not counted', 'Overflows in Wales are not counted: about 29% of the river within 60 km above this spot is in Wales.']]);
  assert.deepEqual(said(frensham), [["Today's EA advice", 'Not checked', "The Environment Agency's advice for today could not be checked. Open the EA's page before you swim: it says when bathing is not advised."]]);
  // Every overflow reporting, no access note, not a bathing water: no gap, and no tile.
  const quiet = week(['low', 'low', 'low', 'low', 'low']);
  assert.equal(rows(quiet).length, 0);
  assert.equal(vm.runInContext('unknownTile', ctx)(quiet), '');
  const tile = vm.runInContext('unknownTile', ctx)(longBridges);
  assert.match(tile, /^<section class="tile" id="unknowns" aria-labelledby="unknowns-h"><h2 class="t-lab" id="unknowns-h"><svg[^>]*>.*<\/svg><span>Not known here<\/span><\/h2><div class="factors">/);
  // The page puts it straight after the five days, on a failed forecast too (access is still a gap there).
  assert.match(html, /\$\{daysTile\(d\)\}\$\{conditionsSummary\(d\)\}\$\{unknownTile\(d\)\}/);
  assert.match(html, /\$\{factors\(d\)\}\$\{check\(d\)\}<\/div>\$\{unknownTile\(d\)\}/);
});

// ------------------------------------------------------------------------------ G7: when will it clear
// docs/REVIEW-2026-10-16.md, G7: now.clears_at said as a clock time on the Right now tile and in the
// alerts (levels.js clearWords, written to alerts.json as `clears`), and the first day back at low in the
// sentence over the five days (backToLow).
const spilt = (now, labels = ['high', 'moderate', 'low', 'low', 'low']) => week(labels, {
  now: { label: 'high', risk: 0.5, discharging_upstream: 0, recent_upstream: 3, monitored_upstream: 3, clears_at: '2026-10-13T22:47:00+01:00', clears_by: 'die-off', ...now } });

test('after a spill, the time it should have cleared, in UK time, while right now is raised', () => {
  assert.equal(L.clearWords(spilt({}), NOW), 'The spills upstream should have passed and died off by Tuesday 22:47.');
  assert.equal(L.clearWords(spilt({ recent_upstream: 1 }), NOW), 'The spill upstream should have passed and died off by Tuesday 22:47.');
  assert.equal(L.clearWords(spilt({ clears_at: '2026-10-11T23:05:00+01:00' }), NOW), 'The spills upstream should have passed and died off by Sunday 23:05.');   // the weekday, never today
  assert.equal(L.clearWords(spilt({ clears_at: '2026-10-11T23:05:00Z' }), NOW), 'The spills upstream should have passed and died off by Monday 00:05.');   // UK time, not UTC
  assert.equal(L.clearWords(spilt({ discharging_upstream: 1, recent_upstream: 0, clears_by: 'travel' }), NOW),
    'If the overflow discharging upstream stops now, its spill should have passed and died off by Tuesday 22:47.');
  assert.equal(L.clearWords(spilt({ discharging_upstream: 2, recent_upstream: 1 }), NOW),
    'If the 2 overflows discharging upstream stop now, the spills should have passed and died off by Tuesday 22:47.');
  // Nothing to say: right now low, no time, a time already past, right now not known.
  assert.equal(L.clearWords(spilt({ label: 'low', risk: 0.1 }), NOW), '');
  assert.equal(L.clearWords(spilt({ clears_at: null }), NOW), '');
  assert.equal(L.clearWords(spilt({ clears_at: '2026-10-11T21:00:00+01:00' }), NOW), '');
  assert.equal(L.clearWords({ ...spilt({}), upstream_summary: { overflows: 0 } }, NOW), '');
});

test('the Right now tile and the alerts say it; the five days name the first day back at low', () => {
  const s = spilt({});
  const ctx = page(['esc', 'glyph', 'ICON', 'nowTile', 'feedDown', 'feedStale', 'liveSay', 'recentSay', 'overflowDots', 'feedTime', 'fmt',
    'tone', 'initial', 'week', 'spilling', 'summary', 'daysSentence'], { DATA: { generated_at: GEN } });
  assert.match(text(vm.runInContext('nowTile', ctx)(s, 3).say), /3 report live\. The spills upstream should have passed and died off by Tuesday 22:47\.$/);
  assert.doesNotMatch(text(vm.runInContext('nowTile', ctx)(spilt({ label: 'low', risk: 0.1 }), 3).say), /died off/);
  assert.equal(L.backToLow(s), 'Back to low risk on Tuesday.');
  assert.match(text(vm.runInContext('daysSentence', ctx)(s)), / Back to low risk on Tuesday\.$/);
  assert.equal(L.backToLow(week(['moderate', 'low', 'low', 'high', 'low'])), 'Back to low risk tomorrow.');   // the first raised day's
  assert.equal(L.backToLow(week(['low', 'low', 'low', 'low', 'low'])), '');
  assert.equal(L.backToLow(week(['low', 'high', 'high', 'moderate', 'moderate'])), '');   // not back within the five days
  assert.equal(L.backToLow(week(['high', 'low', 'low', 'low', 'low'], { classification: { class: 'poor', year: 2025 } })), '');   // rated poor: never low
  // Right now raises today: back at low the next day.
  assert.equal(L.backToLow(spilt({}, ['low', 'low', 'low', 'low', 'low'])), 'Back to low risk tomorrow.');
  // The alerts: scripts/alerts.js writes `clears` beside the headline and the action, at the build's time.
  const dir = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'alerts-'));
  const gen = new Date(Date.now() - 3600e3).toISOString(), later = new Date(Date.now() + 26 * 3600e3).toISOString();
  const day0 = gen.slice(0, 10), mk = (id, now) => ({ ...spilt(now), id, days: spilt(now).days.map((x, i) => ({ ...x, date: new Date(Date.parse(day0) + i * 864e5).toISOString().slice(0, 10) })) });
  fs.writeFileSync(path.join(dir, 'spots.json'), JSON.stringify({ generated_at: gen, spots: [mk('a', { clears_at: later }), mk('b', { label: 'low', risk: 0.1, clears_at: later })] }));
  require('node:child_process').execFileSync('node', [path.join(__dirname, '../scripts/alerts.js'), path.join(dir, 'spots.json'), path.join(dir, 'alerts.json'), 'https://example.org/']);
  const out = JSON.parse(fs.readFileSync(path.join(dir, 'alerts.json'), 'utf8')).spots;
  assert.match(out.a.clears, /^The spills upstream should have passed and died off by (Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day \d\d:\d\d\.$/);
  assert.equal(out.b.clears, undefined);
  fs.rmSync(dir, { recursive: true });
});
