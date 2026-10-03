// Quick notes on a visit, on a spot's page (src/dipcast/site/visits.js): the parts that need no page.
// node --test tests/site_visits.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const v = require('../src/dipcast/site/visits.js');

const TODAY = '2026-10-03';
const id = n => n.toString(16).padStart(20, '0');
const note = (n, kinds, extra = {}) => ({ id: id(n), kinds, seen_on: TODAY, confirmed_on: null, confirmations: 0, text: '', verified: '', photos: [], ...extra });
const rows = (list, mine = [], confirmed = {}) => v.visitRows(list, mine, 'wharfe-burnsall', TODAY, confirmed);

test('the page has the same ticks, days and tones as the service', async () => {
  const { VISIT_KINDS } = await import('../reviews/src/rules.js');
  const page = Object.fromEntries(Object.entries(v.VISIT_KINDS).map(([k, x]) => [k, { days: x.days, tone: x.tone, ...(x.confirm ? { confirm: true } : {}) }]));
  assert.deepEqual(page, VISIT_KINDS);
  for (const x of Object.values(v.VISIT_KINDS)) assert.ok(x.ask && x.say);
  assert.ok(v.VISIT_KINDS.pollution.say.startsWith('Suspected') && v.VISIT_KINDS.algae.say.startsWith('Suspected'));
});

test('each tick ends on its own day; damage lasts from its last confirmation', () => {
  assert.deepEqual(v.visitLive(note(1, ['busy', 'steps']), TODAY), ['steps', 'busy'], 'worst first');
  assert.deepEqual(v.visitLive(note(1, ['busy', 'steps']), '2026-10-05'), ['steps'], 'how busy it was lasts the day and the next');
  assert.deepEqual(v.visitLive(note(1, ['steps']), '2026-11-03'), []);
  assert.deepEqual(v.visitLive(note(1, ['steps'], { confirmed_on: '2026-10-20' }), '2026-11-03'), ['steps']);
  assert.deepEqual(v.visitLive(note(1, ['algae'], { confirmed_on: '2026-10-20' }), '2026-10-11'), [], 'algae is seen again, not confirmed');
  assert.deepEqual(v.visitLive(note(1, ['busy', 'something-new']), TODAY), ['busy'], 'a tick from a newer list is skipped');
  assert.equal(v.visitLasts(note(1, ['steps', 'busy']), ['steps', 'busy']), '2026-11-02');
  assert.equal(v.visitLasts(note(1, ['busy']), ['busy']), null);
});

test('warnings come first, good news last, and ended notes are gone', () => {
  const list = [note(1, ['good', 'clear']), note(2, ['busy']), note(3, ['algae'], { seen_on: '2026-10-02' }), note(4, ['steps'], { seen_on: '2026-09-20' }),
    note(5, ['good'], { seen_on: '2026-09-25' })];
  assert.deepEqual(rows(list).map(r => r.id), [id(3), id(4), id(2), id(1)]);
});

test('a good note never reads as cancelling a warning', () => {
  const [at, line] = v.visitCaveat(rows([note(1, ['good']), note(2, ['steps'])]), false);
  assert.equal(at, 1);
  assert.equal(line, 'A good visit does not cancel the warnings above.');
  assert.match(v.visitCaveat(rows([note(1, ['good']), note(2, ['pollution'])]), true)[1], /forecast and the notes above still apply/);
  assert.deepEqual(v.visitCaveat(rows([note(1, ['good'])]), true), [0, 'A good visit does not change the forecast above.']);
  assert.deepEqual(v.visitCaveat(rows([note(1, ['good']), note(2, ['busy'])]), false), [-1, ''], 'nothing warns: no line');
  assert.deepEqual(v.visitCaveat(rows([note(2, ['steps'])]), true), [-1, ''], 'no good note: no line');
  // One note with both: the warning is named first and the line still comes before it.
  const both = rows([note(1, ['clear', 'algae'])]);
  assert.equal(v.visitWords(both[0]), 'Suspected algae · Water looked clear');
  assert.equal(v.visitCaveat(both, false)[0], 0);
});

test('pollution and algae stay what one swimmer saw until the site names its source', () => {
  const [r] = rows([note(1, ['pollution'])]);
  assert.match(v.visitItem(r, TODAY), /Suspected pollution<\/p><p class="vn-flag">Not verified: what one swimmer saw, not a water test./);
  const [ok] = rows([note(1, ['pollution'], { verified: 'Environment Agency notice, 3 Oct' })]);
  assert.match(v.visitItem(ok, TODAY), /<p class="rv-v">Pollution<\/p><p class="vn-flag">Verified: Environment Agency notice, 3 Oct.<\/p>/);
  assert.doesNotMatch(v.visitItem(rows([note(1, ['busy'])])[0], TODAY), /vn-flag/);
});

test('a lasting note offers "Still like this" once it is a day old, and says until when', () => {
  const [old] = rows([note(1, ['steps'], { seen_on: '2026-10-01' })]);
  const html = v.visitItem(old, TODAY);
  assert.match(html, /data-confirm=/);
  assert.match(html, /Seen on 1 Oct · shown until 31 Oct unless confirmed again/);
  assert.doesNotMatch(v.visitItem(rows([note(1, ['steps'])])[0], TODAY), /data-confirm/, 'not on the day it was seen');
  assert.doesNotMatch(v.visitItem(rows([note(1, ['busy'], { seen_on: '2026-10-02' })])[0], TODAY), /data-confirm/, 'a day\'s crowd is not confirmed');
  const confirmed = rows([note(1, ['steps'], { seen_on: '2026-10-01' })], [], { [id(1)]: { confirmed_on: TODAY, confirmations: 1 } });
  const after = v.visitItem(confirmed[0], TODAY, { iConfirmed: true });
  assert.match(after, /confirmed by 1 more swimmer, the last today/);
  assert.doesNotMatch(after, /data-confirm/);
});

test('this browser\'s own notes: shown while the site catches up, deletable, forgotten when they end', () => {
  const mine = v.visitsMine(JSON.stringify([
    { id: id(7), token: 't', spot: 'wharfe-burnsall', kinds: ['sign'], seen_on: TODAY, text: 'New sign by the gate', published: false },
    { id: id(8), token: 't', spot: 'wharfe-burnsall', kinds: ['busy'], seen_on: TODAY, published: true },
    { id: id(9), spot: 'wharfe-burnsall', gone: true }, { id: 'not-an-id', spot: 'x', gone: true }, 'junk']));
  assert.equal(mine.length, 3);
  const list = rows([note(9, ['busy'])], mine);
  assert.deepEqual(list.map(r => r.id), [id(7), id(8)], 'the deleted one is left out');
  assert.match(v.visitItem(list[0], TODAY), /Your note · Seen today · waiting to be checked/);
  assert.match(v.visitItem(list[1], TODAY), /on this page at its next update/);
  assert.match(v.visitItem(list[1], TODAY), /data-vdelete=/);
  assert.equal(v.visitsTidy(mine, { visits: {} }, '2026-10-05').length, 1, 'the ended crowd note and the dropped deletion are forgotten');
});

test('the form says what is wrong before the service does', () => {
  const ok = { kinds: ['busy'], when: 'today', text: '', photo: false, consent: false };
  assert.equal(v.visitProblem(ok), '');
  assert.equal(v.visitProblem({ ...ok, kinds: [] }), 'Tick at least one thing you found.');
  assert.equal(v.visitProblem({ ...ok, kinds: ['a', 'b', 'c', 'd', 'e', 'f', 'g'] }), 'Tick at most 6.');
  assert.equal(v.visitProblem({ ...ok, when: 'last week' }), 'Say whether you were here today or yesterday.');
  assert.equal(v.visitProblem({ ...ok, text: 'x'.repeat(281) }), 'Keep it to 280 characters.');
  assert.equal(v.visitProblem({ ...ok, text: 'see example.com' }), 'Leave out web addresses.');
  assert.equal(v.visitProblem({ ...ok, photo: true }), 'Tick the box to say the photo is yours to share.');
});

test('words from a note are escaped', () => {
  const [r] = rows([note(1, ['busy'], { text: '<img src=x onerror=alert(1)>' })]);
  assert.match(v.visitItem(r, TODAY), /&lt;img src=x onerror=alert\(1\)&gt;/);
});
