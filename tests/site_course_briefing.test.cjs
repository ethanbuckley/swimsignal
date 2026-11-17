// The course briefing prototype's page (prototypes/course-briefing/course.js) on the committed Henley Classic file:
// what each of the three dates says, what is labelled a reconstruction, and what the page never gives.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const C = require('../prototypes/course-briefing/course.js');
const DOC = require('../prototypes/course-briefing/henley-classic/course.json');

const text = html => html.replace(/<svg[\s\S]*?<\/svg>/g, ' ').replace(/<[^>]+>/g, ' ').replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/\s+/g, ' ');
const page = id => text(C.render(DOC, id));

test('the answer says where the evidence changes, and what is not known', () => {
  const a = C.answer(DOC);
  assert.match(a, /^The evidence changes near the start\. The maps place Henley sewage works overflow upstream of the first 350 m of the swim\./);
  assert.match(a, /Whether it also reaches the next 510 m is not known\./);
  assert.match(a, /The last 1\.25 km to the finish is above it\.$/);
});

test('every date keeps the briefing limits, the caveat, and gives no E. coli figure or verdict', () => {
  const py = fs.readFileSync(path.join(__dirname, '..', 'scripts', 'briefing.py'), 'utf8');
  assert.ok(py.includes('It is a forecast, not a water test: nothing was sampled at the water for it.'));
  for (const d of DOC.dates) {
    const t = page(d.id);
    assert.ok(t.includes(DOC.limits), d.id);
    assert.ok(t.includes(DOC.decides), d.id);
    assert.ok(t.includes('A forecast and an evidence map, not a water test. The organiser decides.'), d.id);
    assert.ok(t.includes('This page gives no E. coli reading and no range.'), d.id);
    assert.doesNotMatch(t, /cfu|per 100 ml|E\. coli estimate|\bundefined\b|\bNaN\b|\bnull\b/, d.id);
    assert.doesNotMatch(t.replace(DOC.limits, ''), /\bsafe\b|\bclean\b|go ahead|cancel/i, d.id);
    assert.ok(t.includes('Reconstruction. Prepared on'), d.id);
    assert.ok(t.includes(d.replay ? 'The course at the same time' : 'Historical view: later records'), d.id);
    assert.ok(t.includes('Not covered in any section:'), d.id);
  }
});

test('a level is shown only where one was issued, with its issue id', () => {
  const routine = C.render(DOC, 'routine'), differs = C.render(DOC, 'differs');
  assert.match(routine, /<p class="c-level low">Low risk from sewage spills<\/p>/);
  assert.ok(text(routine).includes('4deeedd-20261101T0832Z'));
  assert.doesNotMatch(differs, /c-level/);
  assert.ok(text(differs).includes("Nothing was issued. SwimSignal's forecast log starts on 12 September 2026"));
  assert.ok(text(differs).includes('Which monitors were reporting: not known.'));
});

test('the spill day differs by section, from the Environment Agency record', () => {
  const t = page('differs');
  assert.ok(t.includes('Henley sewage works overflow on this date: recorded spilling 11:45 to 12:45. Environment Agency start and stop record.'));
  assert.ok(t.includes('Not resolved. A ditch on the map may carry Henley sewage works overflow water'));
  assert.ok(t.includes('Upstream of this section: the 50 above, and nothing more.'));
});

test('the gap day names the monitor with no reading, and never calls that low', () => {
  const t = page('gap');
  assert.ok(t.includes('48 of 49 overflows upstream gave a status at the last poll.'));
  assert.ok(t.includes('Friday Street (Henley) pumping station overflow , 0.3 km above the finish: no reading at any of 6 polls.'));
  assert.ok(t.includes('the largest of the 50. Missing data never means low risk.'));
  assert.ok(t.includes('02:50 to 02:54 on 13 November'));
});

test('an unknown date falls back to the first, and the rebuilt index is labelled', () => {
  assert.equal(C.render(DOC, 'nope'), C.render(DOC, 'gap'));
  assert.ok(page('gap').includes('Reconstruction. Not issued on the day.'));
  assert.ok(page('gap').includes('using spill records for the whole day'));
});

test('the walkthrough starts with the same-date pin and hides the course evidence', () => {
  for (const date of DOC.dates) {
    const before = C.renderWalkthrough(DOC, date, false);
    assert.match(before, /What the Henley page showed/);
    assert.match(before, /Show the course evidence/);
    if (date.issued) assert.ok(before.includes(date.issued.issue));
    else assert.match(before, /Nothing was issued/);
    assert.doesNotMatch(before, /Reconstruction|Friday Street|350 m|monitor silent|evidence differs along the course|same time|<svg/);
  }
});

test('the same-time reveal answers three questions from what had been received by the decision time', () => {
  const gap = DOC.dates.find(d => d.id === 'gap'), after = text(C.renderWalkthrough(DOC, gap, true));
  assert.ok(after.includes(`Decision time ${C.clock(gap.as_of)} on ${C.longDay(gap.day)}`));
  for (const q of ['Where does the evidence change?', 'What could I check there?', 'What is still unknown?']) assert.ok(after.includes(q), q);
  assert.ok(after.includes('Only what SwimSignal had received by 07:30 on Saturday 14 November 2026'));
  assert.ok(after.includes('Friday Street (Henley) pumping station overflow , 0.3 km above the finish: no status at the 07:13 poll.'));
  assert.ok(after.includes('spilled 02:50 to 02:54 on 13 November. SwimSignal had it by 04:12 on 13 November.'));
  assert.ok(after.includes('Unknown. Whether Friday Street (Henley) pumping station overflow was spilling. Missing data never means low risk.'));
  assert.ok(after.includes('Henley sewage works overflow , upstream of the first section only: not spilling at the 07:13 poll.'));
  assert.match(after, /Back to the Henley pin/);
  // The three answers come before anything gathered later, which sits in its own labelled fold.
  const fold = after.indexOf('Later records, not available at 07:30');
  assert.ok(fold > after.indexOf('What is still unknown?'));
  assert.ok(!after.slice(0, fold).includes('no reading at any of 6 polls'));   // the whole day's count is a later record
  assert.ok(after.slice(fold).includes('no reading at any of 6 polls'));
});

test('every reveal keeps the inferred ends, the unresolved link and the kind of each line in view', () => {
  for (const date of DOC.dates) {
    const after = text(C.renderWalkthrough(DOC, date, true));
    assert.ok(after.includes('Modelled connection. The evidence changes near the start.'), date.id);
    assert.ok(after.includes('Inferred. The start and the finish. About 60 m either way.'), date.id);
    assert.ok(after.includes('The Fawley Court link is unresolved.'), date.id);
    assert.ok(after.includes(date.replay ? 'Observation.' : 'Later record.'), date.id);
    assert.ok(after.includes(DOC.limits), date.id);
  }
});

test('a quiet day says plainly that nothing received differs along the course', () => {
  const after = text(C.renderWalkthrough(DOC, DOC.dates.find(d => d.id === 'routine'), true));
  assert.ok(after.includes('Nothing received by 08:40 differs along the course. The map still does.'));
  assert.ok(after.includes('50 of 50 overflows upstream of the whole course gave a status at the 08:29 poll, none spilling.'));
});

test('the 2024 date is a historical view, never a same-time comparison', () => {
  const d = DOC.dates.find(x => x.id === 'differs'), after = text(C.renderWalkthrough(DOC, d, true));
  assert.equal(d.replay, null);
  assert.ok(after.includes('Historical view: later records'));
  assert.ok(after.includes('Not a same-time comparison. SwimSignal kept no archive in 2024'));
  assert.ok(after.includes('Later record. Henley sewage works overflow , upstream of the first section only: recorded spilling 11:45 to 12:45.'));
  assert.doesNotMatch(after, /Observation\.|The course at the same time|had received by/);
});

test('changing the date, or going back, returns to the archived pin before any reveal', () => {
  let s = { date: 'routine', revealed: false };
  s = C.step(s, { type: 'reveal' });
  assert.equal(s.revealed, true);
  s = C.step(s, { type: 'date', date: 'gap' });
  assert.deepEqual(s, { date: 'gap', revealed: false });
  assert.equal(C.step(C.step(s, { type: 'reveal' }), { type: 'reset' }).revealed, false);
  const gap = DOC.dates.find(d => d.id === 'gap'), shown = C.renderWalkthrough(DOC, gap, s.revealed);
  assert.ok(shown.includes(gap.issued.issue));
  assert.doesNotMatch(shown, /Friday Street|The course at the same time|<svg/);
});
