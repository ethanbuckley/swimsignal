// Since the last update (src/dipcast/site/since.js, lastSaid; prototype, ?why=1): the forecast on a spot's page
// against the previous issue's record (data/since-last.json, src/dipcast/issue_history.py), for every visitor. Each
// case says what it compared with; a level that moved gets what changed in the inputs, never a cause.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const S = require('../src/dipcast/site/since.js');

const FIX = path.join(__dirname, 'fixtures', 'forecast_why');
const issue = f => JSON.parse(fs.readFileSync(path.join(FIX, f), 'utf8'));
const A = issue('issue-2026-10-29T1857.json'), B = issue('issue-2026-10-30T1749.json');
// Records as the build keeps them (scripts/issue_records.cjs): on the issue's own day, without `id` and `at`.
function records(doc, day) {
  L.setToday(day);
  return Object.fromEntries(doc.spots.map(s => { const { id, at, ...r } = S.seenRecord(s, doc.generated_at, Date.parse(doc.generated_at)); return [id, r]; }));
}
const PREV = records(A, '2026-10-29');
const META = { issue_id: '746eddb-20261030T1749Z', issued_at: B.generated_at, previous: { issue_id: '92a4ebd-20261029T1857Z', issued_at: A.generated_at }, spots: PREV };
const cur = id => { L.setToday('2026-10-30'); return S.seenRecord(B.spots.find(s => s.id === id), B.generated_at, Date.now()); };
const said = (id, meta = META, prev = PREV[id]) => { const c = cur(id); return S.lastSaid(meta, prev, c); };

test('a level that moved: the day, then and now, and what changed in the inputs, against the issue named', () => {
  const t = said('medway-tonbridge');
  assert.match(t, /^Since the update issued Thu 18:57, 22 h 52 min before this one: Today: low risk then, very high risk now\. What changed in the inputs: /);
  assert.match(t, /Reported or forecast: Overflows upstream reported discharging: 1 then, 0 now\./);
  assert.match(t, /With time: Then this day was tomorrow;/);
  // A small drift across a line is said as small, with the line.
  assert.match(said('osm-dart-dartington'), /Monday: moderate risk then, low risk now\. What changed in the inputs: A small change: sewage spill risk 16 of 100 then, 14 now, and moderate risk starts at 15\.$/);
});

test('nothing to compare is said, never left quiet', () => {
  assert.equal(said('medway-tonbridge', { ...META, previous: null, why: 'first', spots: {} }, null), 'No earlier update on record to compare with yet.');
  assert.equal(said('medway-tonbridge', { ...META, previous: null, why: 'stale', spots: {} }, null), 'No earlier update within a day to compare with.');
  // A spot that was not in the earlier update.
  assert.match(said('medway-tonbridge', META, null), /: this spot was not in that update, so there is nothing to compare\.$/);
  // The same record: no level changed, said against the issue named.
  const same = cur('medway-tonbridge');
  assert.match(S.lastSaid(META, { ...same }, same), /: no level changed\.$/);
  // A file older than the page's forecast is never compared the wrong way round.
  assert.equal(S.lastSaid({ ...META, previous: { issued_at: B.generated_at } }, PREV['medway-tonbridge'], cur('medway-tonbridge')), '');
});

test('an input the earlier record lacks is not said; one with nothing kept says so', () => {
  // The earlier record without any inputs for its days (an older or partial record): no fact made up.
  const bare = { ...PREV['avon-warleigh-weir'], days: PREV['avon-warleigh-weir'].days.map(d => ({ date: d.date, level: d.level, by: d.by, score: null, rain: null, expect: null, missing: null })) };
  const t = said('avon-warleigh-weir', META, bare);
  assert.match(t, /Monday: moderate risk then, low risk now\. What changed in the inputs: No input kept here changed by enough to show\./);
  assert.doesNotMatch(t, /expected to spill|Rain here/);
});

test('a change in how many overflows gave a live status is coverage, not the water', () => {
  const c = cur('medway-tonbridge');
  const prev = { ...c, forecast: A.generated_at, reporting: c.reporting + 2, days: c.days.map((d, i) => i ? d : { ...d, level: 'low', by: 'sewage spills' }) };
  const t = S.lastSaid({ ...META, previous: { issued_at: A.generated_at } }, prev, c);
  assert.match(t, new RegExp(`In what SwimSignal knows, not necessarily the water: Overflows upstream giving a live status: ${c.reporting + 2} of ${c.upstream} then, ${c.reporting} of ${c.upstream} now\\.`));
});

test('the gap in words, and at most three days said', () => {
  assert.deepEqual([S.lastGap(30 * 6e4), S.lastGap(310 * 6e4), S.lastGap(26 * 36e5), S.lastGap(48 * 36e5)], ['30 min', '5 h 10 min', '1 day 2 h', '2 days']);
  assert.equal(S.LAST_DAYS_SAID, 3);
});

test('no word says safe, clean or caused', () => {
  for (const id of ['medway-tonbridge', 'osm-dart-dartington', 'avon-warleigh-weir']) assert.doesNotMatch(said(id), /\b(safe|clean|caus)/i);
});
