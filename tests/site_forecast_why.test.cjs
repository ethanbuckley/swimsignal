// Why a forecast changed (src/dipcast/site/since.js, whyFacts and whySaid; prototype, ?why=1): a day whose level
// moved between the note kept on the device and the forecast on screen, explained from the inputs both notes
// kept, and from nothing else. First on two real issues of the live site (tests/fixtures/forecast_why: three spots
// from 29 Oct 18:57 and 30 Oct 17:49 UTC), then on made-up spots for the kinds those 23 hours did not have.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const S = require('../src/dipcast/site/since.js');

const FIX = path.join(__dirname, 'fixtures', 'forecast_why');
const issue = f => JSON.parse(fs.readFileSync(path.join(FIX, f), 'utf8'));
const A = issue('issue-2026-10-29T1857.json'), B = issue('issue-2026-10-30T1749.json');
// Each note as the page makes it: on the forecast's own UK day.
function notes(doc, day) {
  L.setToday(day);
  return new Map(doc.spots.map(s => [s.id, S.seenRecord(s, doc.generated_at, Date.parse(doc.generated_at))]));
}
const WAS = notes(A, '2026-10-29'), NOW = notes(B, '2026-10-30');   // leaves today at 30 Oct for the real cases

test('real issues: the day became today, a spill stopped, and right now fell, each said as what it is', () => {
  L.setToday('2026-10-30');
  const was = WAS.get('medway-tonbridge'), now = NOW.get('medway-tonbridge'), f = S.whyFacts(was, now, '2026-10-30');
  assert.deepEqual([f.was.level, f.now.level], ['low', 'very high']);
  assert.deepEqual(f.facts.map(x => x.kind), ['time', 'reported', 'time']);
  assert.equal(S.whySaid(was, now, '2026-10-30'), 'The level was set by sewage spills then; it is now set by recent sewage spills.'
    + ' What changed: Overflows upstream reported discharging: 1 then, 0 now.'
    + " And time passed: Then this day was tomorrow; today's level also counts right now, from spills upstream."
    + ' Right now, worked out from spills upstream as their water moves on and dies off, was 81 of 100 then and is 77 now.');
  // The headline (worst of right now, today and tomorrow) moved with today: today is the day explained.
  assert.equal(S.whyHeadlineDay(was, now), '2026-10-30');
});

test('real issues: a spill forecast revised for the day before, and a small move across a line', () => {
  L.setToday('2026-10-30');
  assert.equal(S.whySaid(WAS.get('avon-warleigh-weir'), NOW.get('avon-warleigh-weir'), '2026-11-02'),
    'What changed: Overflows upstream expected to spill on Sunday, the day before: 2 then, 1.4 now.');
  // Nothing kept moved: the spill risk itself, which crossed the line between moderate and low by 2.
  assert.equal(S.whySaid(WAS.get('osm-dart-dartington'), NOW.get('osm-dart-dartington'), '2026-11-02'),
    'A small change: sewage spill risk 16 of 100 then, 14 now, and moderate risk starts at 15.');
});

test('real issues: a headline that fell because its day passed says so, and no day under it is blamed', () => {
  L.setToday('2026-10-30');
  const was = WAS.get('avon-warleigh-weir'), now = NOW.get('avon-warleigh-weir');
  assert.deepEqual([was.level, now.level], ['high', 'moderate']);
  assert.equal(S.whyHeadlineDay(was, now), null);   // today and tomorrow were moderate risk in both
  assert.equal(S.whyHeadlinePassed(was, now), 'Then high risk was for Thursday, which has passed. That forecast already had today and tomorrow at moderate risk.');
});

// ------------------------------------------------------------------------------ made-up spots
const DATES = ['2026-10-30', '2026-10-31', '2026-11-01', '2026-11-02', '2026-11-03'];
const OLD = '2026-10-30T07:30:00+00:00', NEW = '2026-10-30T17:30:00+00:00';
const label = r => r < 0.15 ? 'low' : r < 0.4 ? 'moderate' : r < 0.7 ? 'high' : 'very high';
// A river spot with ten overflows upstream; risks by day, and anything else to change.
function spot(risks, {now = {}, day = {}, ...extra} = {}) {
  return {id: 'eden', name: 'Eden', kind: 'river', source: 'curated', upstream_summary: {overflows: 10}, location: {mode: 'river'},
    assumptions: {version: 'spill=aaaa;cal=bbbb;ecoli=cccc;code=0.1.0+1111;rain=open-meteo-forecast'},
    now: {label: 'low', risk: 0.02, discharging_upstream: 0, recent_upstream: 0, feed_down_upstream: 0, stale_upstream: 0, ...now},
    days: DATES.map((date, i) => ({date, risk: risks[i], label: label(risks[i]), rain_48h_mm: 2, expected_spilling_overflows: 0.4,
      rain_missing_share: 0, ...(day[date] || {})})), ...extra};
}
const BASE = [0.05, 0.1, 0.1, 0.1, 0.1];
const note = (s, f = OLD) => { L.setToday('2026-10-30'); return S.seenRecord(s, f, Date.parse(f)); };
const why = (was, now, d = '2026-10-31') => S.whySaid(note(was), note(now, NEW), d);
const kinds = (was, now, d = '2026-10-31') => S.whyFacts(note(was), note(now, NEW), d).facts.map(x => x.kind);

test('a revised rain and spill forecast is a change in conditions', () => {
  const now = spot([0.05, 0.45, 0.1, 0.1, 0.1], {day: {'2026-10-31': {rain_48h_mm: 14.2, expected_spilling_overflows: 2.1}}});
  assert.deepEqual(kinds(spot(BASE), now), ['forecast', 'forecast']);
  assert.equal(why(spot(BASE), now), 'What changed: Rain here in the 48 hours to midday: 2 mm forecast then, 14 mm now.'
    + ' Overflows upstream expected to spill tomorrow: 0.4 then, 2.1 now. Sewage spill risk: 10 of 100 then, 45 now.');
  // Under the sizes the page shows (whole millimetres, one decimal place of spills): not said.
  const slight = spot([0.05, 0.16, 0.1, 0.1, 0.1], {day: {'2026-10-31': {rain_48h_mm: 3.4, expected_spilling_overflows: 0.7}}});
  // And a move of 6 is more than the small one (5): said as not explained by what is kept, not as small.
  assert.equal(why(spot(BASE), slight), 'None of the inputs kept here moved enough to explain it. Sewage spill risk: 10 of 100 then, 16 now.');
});

test('a feed back, rain data filled in, or a new model is what SwimSignal knows, not necessarily the water', () => {
  // Today: a feed upstream was down, so the count was not known; now it reports, and right now is raised.
  const down = spot(BASE, {now: {feed_down_upstream: 2}}), back = spot([0.2, 0.1, 0.1, 0.1, 0.1]);
  assert.deepEqual(kinds(down, back, '2026-10-30'), ['ours']);
  assert.match(why(down, back, '2026-10-30'), /^What SwimSignal knows changed, not necessarily the water: A feed upstream was down or late then; every feed is reporting now\./);
  const gap = spot(BASE, {day: {'2026-10-31': {rain_missing_share: 0.3}}}), full = spot([0.05, 0.2, 0.1, 0.1, 0.1]);
  assert.match(why(gap, full), /^What SwimSignal knows changed, not necessarily the water: Rain data was missing for 30% of the water upstream then, none now\./);
  // A new spill model and calibration, named; a new build of the page alone (code=) is no model change.
  const model = {...spot([0.05, 0.2, 0.1, 0.1, 0.1]), assumptions: {version: 'spill=dddd;cal=eeee;ecoli=cccc;code=0.1.0+2222;rain=open-meteo-forecast'}};
  assert.match(why(spot(BASE), model), /SwimSignal changed its spill model and calibration between the two forecasts\./);
  const code = {...spot([0.05, 0.2, 0.1, 0.1, 0.1]), assumptions: {version: 'spill=aaaa;cal=bbbb;ecoli=cccc;code=0.1.0+9999;rain=open-meteo-forecast'}};
  assert.doesNotMatch(why(spot(BASE), code), /SwimSignal changed/);
  // Both kinds: the conditions first, then what SwimSignal knows, "too".
  const both = {...spot([0.05, 0.45, 0.1, 0.1, 0.1], {day: {'2026-10-31': {rain_48h_mm: 14}}}), assumptions: model.assumptions};
  assert.match(why(spot(BASE), both), /^What changed: Rain here .* What SwimSignal knows changed too: SwimSignal changed its spill model/);
});

test('reported things: a spill starting, a new sample, a new rating', () => {
  const on = spot([0.45, 0.1, 0.1, 0.1, 0.1], {now: {label: 'high', risk: 0.45, discharging_upstream: 2}});
  assert.match(why(spot(BASE), on, '2026-10-30'), /What changed: Overflows upstream reported discharging: 0 then, 2 now\./);
  const sampled = spot(BASE, {lab_sample: {taken_at: '2026-10-29T10:00+00:00', ecoli: 1200}});
  assert.match(why(spot(BASE, {lab_sample: {taken_at: '2026-09-24T10:00+00:00', ecoli: 80}}), sampled, '2026-10-30'),
    /A new Environment Agency lab sample has arrived\./);
  const poor = spot(BASE, {classification: {class: 'Poor', year: 2026}});
  assert.match(why(spot(BASE, {classification: {class: 'Good', year: 2025}}), poor),
    /^The level was set by sewage spills then; it is now set by rated poor\. What changed: The Environment Agency rating changed: rated good for 2025 then, rated poor for 2026 now\./);
});

test('nothing is said that a note does not hold', () => {
  const now = spot([0.05, 0.45, 0.1, 0.1, 0.1], {day: {'2026-10-31': {rain_48h_mm: 14}}});
  // A note from before 30 Oct 2026 has no inputs: the line may still say the level moved, but no why.
  const {days, recent, nowLevel, nowScore, clears, sample, algae, model, ...old} = note(spot(BASE));
  assert.equal(S.whySaid(old, note(now, NEW), '2026-10-31'), '');
  assert.equal(S.readSeen(JSON.stringify([old])).size, 1);   // and it still reads as a note
  // The same level, or a day one note does not have: nothing.
  assert.equal(why(spot(BASE), spot([0.05, 0.12, 0.1, 0.1, 0.1])), '');
  assert.equal(S.whySaid(note(spot(BASE)), note(now, NEW), '2026-11-05'), '');
  // A rain figure missing from either note is not compared.
  const noRain = spot(BASE, {day: {'2026-10-31': {rain_48h_mm: null}}});
  assert.doesNotMatch(why(noRain, now), /Rain here/);
  // A note whose inputs are not what this file writes is dropped, as any odd note is.
  const bad = {...note(spot(BASE)), days: [{date: '2026-10-31', level: 'dire', by: null, score: 1, rain: 0, expect: 0, missing: 0}]};
  assert.equal(S.readSeen(JSON.stringify([bad])).size, 0);
});

test('the outing day gets a line of its own when only it moved', () => {
  const plan = 'spot=eden&day=2026-11-01&when=morning';
  assert.equal(S.whyOutingDay('eden', plan), '2026-11-01');
  assert.equal(S.whyOutingDay('eden', 'spot=eden&day=2026-10-29'), null);   // a day that has passed
  assert.equal(S.whyOutingDay('wharfe', plan), null);
  const now = spot([0.05, 0.1, 0.5, 0.1, 0.1], {day: {'2026-11-01': {rain_48h_mm: 20, expected_spilling_overflows: 3}}});
  const was = {...note(spot(BASE)), at: new Date(2026, 9, 30, 9, 5).getTime()};
  assert.equal(S.whyDayLine(was, note(now, NEW), '2026-11-01'), 'Sunday, the day of your outing, was low risk when you looked today at 09:05; now high risk.');
  assert.match(S.whySaid(was, note(now, NEW), '2026-11-01'), /^What changed: Rain here in the 48 hours to midday: 2 mm forecast then, 20 mm now\./);
});

test('no word says safe, clean or caused', () => {
  const said = [];
  for (const [w, n, d] of [[WAS.get('medway-tonbridge'), NOW.get('medway-tonbridge'), '2026-10-30'],
    [WAS.get('avon-warleigh-weir'), NOW.get('avon-warleigh-weir'), '2026-11-02']]) { L.setToday('2026-10-30'); said.push(S.whySaid(w, n, d)); }
  for (const t of said) assert.doesNotMatch(t, /\b(safe|clean|caus)/i);
});
