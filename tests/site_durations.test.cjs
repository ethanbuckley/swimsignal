// Spill durations (src/dipcast/site/durations.js, the viewer on durations.html): how long overflows' spills lasted in
// 2024 and 2025, and how often a spill already running was still running hours later, and only that. Cut from the
// research export (tests/fixtures/spill_durations_v1_sample.json, docs/SPILL-DURATIONS-CONTRACT-v1.md): three companies,
// their "still running" rows and all nine's, and six overflows (a long-running Yorkshire Water overflow, two with few
// spills, one whose longest ran 44 days, one whose spills were mostly under an hour).
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const D = require('../src/dipcast/site/durations.js');

const DOC = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'spill_durations_v1_sample.json'), 'utf8'));
const INDEX = { ...DOC, available: true, spots: [{ id: 'wharfe-ilkley', name: 'Wharfe at Ilkley', overflows: 4, absent: 1 }] };
delete INDEX.overflows;
const plain = h => h.replace(/\u00a0/g, ' ').replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/\s+/g, ' ').trim();
// One spot's file as build_site.write_spill_durations writes it: the export's rows for the overflows upstream, in the
// upstream file's order, and the ones it lacks.
const row = i => Object.fromEntries(['site_id', 'spills_2024', 'spills_2025', 'median_h', 'p90_h', 'longest_h', 'share_over_6h', 'few'].map(k => [k, DOC.overflows[k][i]]));
const SPOT = { id: 'wharfe-ilkley', name: 'Wharfe at Ilkley', period: DOC.period,
  overflows: [0, 1, 3, 4].map(i => ({ ...row(i), name: `Overflow ${i}`, own: i === 0 ? 'Own Name/CSO' : '', company: DOC.companies[DOC.overflows.company[i]] })),
  absent: [{ site_id: 'DCW0001', name: 'A Welsh overflow', own: '', company: 'Dwr Cymru Welsh Water' }] };

test('a spill length is said in minutes, hours or days, as the overflow history page says it', () => {
  const said = [0, 0.004, 0.07, 0.5, 0.73, 1.57, 2.0, 9.83, 9.99, 18.58, 47.4, 99.5, 1054.5].map(D.durationsHours).map(t => t.replace(/\u00a0/g, ' '));
  assert.equal(D.durationsHours(0.5), '30\u00a0min');   // number and unit on one line
  assert.deepEqual(said, ['under 1 min', 'under 1 min', '4 min', '30 min', '44 min', '1.6 h', '2 h', '9.8 h', '10 h', '19 h', '47 h', '4.1 days', '44 days']);
  assert.equal(D.durationsHours(null), '–');
});

test('the years come first and the page says the records are history', () => {
  assert.deepEqual(D.durationsYears(DOC.period), { from: '2024', to: '2025', said: '2024 and 2025', short: '2024-25', span: '1 January 2024 to 31 December 2025' });
  const s = plain(D.durationsSummary(INDEX));
  assert.ok(s.startsWith('History: 1 January 2024 to 31 December 2025. Nothing after that is in these records.'), s);
  assert.match(s, /802,781 spills at 12,908 storm overflows of the nine English water companies/);
  assert.match(s, /1,606 of the overflows had fewer than 5 spills in the two years\./);
});

test('a missing or foreign export says nothing is published, and why', () => {
  assert.equal(plain(D.durationsSummary({ available: false, why: 'no export in this build' })), 'No spill durations are published in this update (no export in this build).');
  assert.equal(plain(D.durationsSummary(null)), 'No spill durations are published in this update.');
});

test("each company's lengths, with the counts behind them", () => {
  const t = plain(D.durationsCompanies(INDEX));
  assert.match(t, /Company Overflows Spills, 2024-25 Typical spill/);   // the rows' own years (1.1), in a visible header
  assert.match(t, /Thames Water 535 28,814 3.1 h 27 h 35% 11%/);
  assert.match(t, /United Utilities 2,089 161,700 1.1 h 10 h 16% 4%/);
  assert.match(D.durationsCompanies(INDEX), /aria-label="Spill lengths by company, 2024-25, scrolls sideways"/);
});

test('spills already running: the all-nine sentence names its years, its count and that it is no forecast', () => {
  assert.deepEqual(D.durationsAts(INDEX), [0, 1, 3, 6, 12, 24]);
  const nine = D.durationsRunning(INDEX, 3);
  assert.deepEqual(nine.map(r => r.company), ['Thames Water', 'United Utilities', 'Yorkshire Water', 'all nine']);   // all nine last
  assert.equal(D.durationsStillSentence(nine[3], 3, 6, DOC.period),
    'Across all nine companies in 2024 and 2025, a spill that had already run at least 3 hours was still running 6 hours later at 71% of the 3,174,952 hours checked, in 228,078 spills.');
  assert.equal(D.durationsStillSentence(nine[0], 3, 1, DOC.period),
    "At Thames Water's overflows in 2024 and 2025, a spill that had already run at least 3 hours was still running 1 hour later at 94% of the 223,549 hours checked, in 13,731 spills.");
  const any = D.durationsRunning(INDEX, 0).find(r => r.company === 'all nine');
  assert.match(D.durationsStillSentence(any, 0, 1, DOC.period), /a spill that was running was still running 1 hour later at 87% of the 4,400,886 hours checked, in 580,213 spills\.$/);
  const block = plain(D.durationsStill(INDEX, 3));
  assert.ok(block.includes('That describes 2024 and 2025. It does not say when a spill running now will end.'), block);
  // Every company's row gives the spills and hours behind it, then the five later times.
  assert.match(block, /All nine 228,078 3,174,952 93% 83% 71% 55% 38%/);
  // Only spills reaching a whole hour count (1.1): "any spill already running" rests on 580,213 of the 802,781.
  assert.match(plain(D.durationsStill(INDEX, 0)), /these figures rest on 580,213 of the 802,781 spills; the shortest never reach one\./);
  assert.match(D.durationsStill(INDEX, 0), /aria-label="Still running, any spill already running, 2024-25, scrolls sideways"/);
  assert.equal(D.durationsStill(INDEX, 7), '');   // no such rows: nothing drawn
  // The export's own words for each length (1.1, label); without them, the page's.
  assert.match(D.durationsAtPicker(INDEX, 3), /<option value="3" selected>Spills already running at least 3 hours<\/option>/);
  assert.match(D.durationsAtPicker(INDEX, 3), /<option value="0">Any spill already running<\/option>/);
  const bare = { ...INDEX, still_running: INDEX.still_running.map(({ label, ...r }) => r) };
  assert.match(D.durationsAtPicker(bare, 3), /<option value="0">Spills that were running, at any point<\/option>/);
});

test("a spot's overflows: the export's sentence before the figures, few spills marked, no row never said as no spills", () => {
  const h = D.durationsSpot(SPOT, INDEX), t = plain(h);
  assert.ok(t.startsWith(`Wharfe at Ilkley History: 2024 and 2025. ${DOC.claim.public_wording}`), t);
  assert.ok(t.indexOf(DOC.claim.public_wording) < t.indexOf('Typical spill, 2024-25'));
  assert.match(t, /Overflow 0 Own Name\/CSO · YWS00011 Yorkshire Water 2 h 19 h 4.1 days 188 34/);
  assert.match(t, /Overflow 1 YWS00007 Yorkshire Water 30 min, few spills 1.3 h 1.5 h 2 1/);
  assert.match(t, /Overflow 3 TWL00102 Thames Water 3 h 19 h 44 days 145 93/);
  // An overflow without a row, in the export's own words (1.1, absent_note), never as no spills.
  assert.ok(t.includes(`1 of the 5 overflows upstream has no spill in these 2024-25 records (Dŵr Cymru Welsh Water's overflows are not in them). ${DOC.absent_note}`), t);
  assert.match(DOC.absent_note, /not the same as "no spills"/);
  assert.match(plain(D.durationsSpot(SPOT, { ...INDEX, absent_note: undefined })), /That is not the same as no spills\./);
  assert.match(h, /<a href="spot\/wharfe-ilkley\/profile\/">Its overflow history<\/a>/);
  const none = plain(D.durationsSpot({ ...SPOT, overflows: [], absent: SPOT.absent.concat([{ site_id: 'X', company: 'Yorkshire Water' }]) }, INDEX));
  assert.match(none, /None of the 2 overflows upstream has a spill in these 2024-25 records/);
  assert.doesNotMatch(none, /Typical spill/);
});

test('a typical spill under a minute is explained from the export, never as nothing discharged', () => {
  assert.equal(D.durationsZero(SPOT.overflows, INDEX), '');   // no such row here
  const short = [{ ...SPOT.overflows[0], median_h: 0 }];
  const z = plain(D.durationsZero(short, INDEX));
  assert.match(z, /^A typical spill shown as under 1 min means most of that overflow's spills lasted under a minute as recorded, or were recorded with the same start and stop time \(1,110 such events in these records, mostly at Wessex Water and South West Water\)\. It does not mean nothing was discharged\.$/);
  assert.equal(DOC.method.events_same_start_stop, 1110);
  assert.ok(plain(D.durationsSpot({ ...SPOT, overflows: short }, INDEX)).includes('It does not mean nothing was discharged.'));
  assert.equal(D.durationsRowYears([{ years: '2024-2025' }], D.durationsYears(DOC.period)), '2024-25');
  assert.equal(D.durationsRowYears([], D.durationsYears(DOC.period)), '2024-25');
});

test('the picker lists the spots with a file, by name', () => {
  const p = D.durationsSpotPicker({ spots: [{ id: 'b', name: 'Bravo' }, { id: 'a', name: 'Alpha' }] }, 'b');
  assert.ok(p.indexOf('Alpha') < p.indexOf('Bravo') && /<option value="b" selected>Bravo<\/option>/.test(p));
});

test('nothing the page draws says safe, clean or harmless, or when a spill will end', () => {
  const all = plain([D.durationsSummary(INDEX), D.durationsCompanies(INDEX), ...D.durationsAts(INDEX).map(a => D.durationsStill(INDEX, a)),
    D.durationsSpot(SPOT, INDEX)].join(' '));
  assert.doesNotMatch(all.replace(DOC.claim.public_wording, ''), /\bsafe|\bclean|harmless|\bvolume|will (?:likely |probably )?(?:end|stop)\b(?<!running now will end)/i);
  // The only sentence about a spill's end is the one that says the page does not forecast it.
  assert.equal((all.match(/will end/g) || []).length, D.durationsAts(INDEX).length);
  assert.equal((all.match(/It does not say when a spill running now will end\./g) || []).length, D.durationsAts(INDEX).length);
});
