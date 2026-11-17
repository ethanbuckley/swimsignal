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
  assert.match(a, /^The evidence changes near the start\. Henley sewage works overflow reaches the river in the first 350 m of the swim\./);
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
    assert.ok(t.includes('Reconstruction. Laid out on'), d.id);
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
  assert.equal(C.render(DOC, 'nope'), C.render(DOC, 'routine'));
  assert.ok(page('gap').includes('Reconstruction. Not issued on the day.'));
});
