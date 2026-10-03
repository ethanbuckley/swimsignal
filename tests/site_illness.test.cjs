// Reports of illness after a swim, on a spot's page (src/dipcast/site/illness.js): the parts that need no page.
// node --test tests/site_illness.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const il = require('../src/dipcast/site/illness.js');

const TODAY = '2026-10-04';

test('the page has the same kinds of symptom, and the same days back, as the service', async () => {
  const rules = await import('../reviews/src/rules.js');
  assert.deepEqual(il.ILLNESS_SYMPTOMS.map(([id]) => id), rules.ILLNESS_SYMPTOMS);
  assert.equal(il.ILLNESS_DAYS_BACK, rules.ILLNESS_DAYS_BACK);
  assert.equal(il.ILLNESS_KEEP_DAYS, rules.ILLNESS_KEEP_DAYS);
  for (const [, words] of il.ILLNESS_SYMPTOMS) assert.ok(words.length > 2);
});

test('a count is worded as unverified reports, and a spot without one says why', () => {
  assert.deepEqual(il.illnessWords({ d30: 6, d365: 11 }, 5), { fig: [6, 'reports in the last 30 days'],
    say: '6 swimmers reported being ill after swimming here in the last 30 days, and 11 in the last 12 months.' });
  assert.deepEqual(il.illnessWords({ d30: null, d365: 7 }, 5), { fig: [7, 'reports in the last 12 months'],
    say: '7 swimmers reported being ill after swimming here in the last 12 months, fewer than 5 of them in the last 30 days.' });
  const none = il.illnessWords(undefined, 5);
  assert.equal(none.fig, null);
  assert.match(none.say, /^No count to show: fewer than 5 swimmers/);
});

test('the swim can be today or up to 14 days back, and an onset cannot fall after today', () => {
  const days = il.illnessDays(TODAY);
  assert.equal(days.length, 15);
  assert.deepEqual(days[0], ['2026-10-04', 'Today, Sunday 4 October']);
  assert.deepEqual(days[1], ['2026-10-03', 'Yesterday, Saturday 3 October']);
  assert.deepEqual(days[14], ['2026-09-20', 'Sunday 20 September']);
  assert.deepEqual(il.illnessOnsets(TODAY, TODAY), [0]);
  assert.deepEqual(il.illnessOnsets('2026-10-02', TODAY), [0, 1, 2]);
  assert.deepEqual(il.illnessOnsets('2026-09-25', TODAY), [0, 1, 2, 3]);
});

test('the form says what is missing, consent last, and sends only what the service keeps', () => {
  const good = { swam_on: '2026-10-02', symptoms: ['gut'], onset: 1, doctor: null, consent: true, website: '' };
  assert.equal(il.illnessProblem(good, TODAY), '');
  assert.match(il.illnessProblem({ ...good, swam_on: '2026-09-19' }, TODAY), /last 14 days/);
  assert.match(il.illnessProblem({ ...good, symptoms: [] }, TODAY), /at least one/);
  assert.match(il.illnessProblem({ ...good, onset: null }, TODAY), /when it started/);
  assert.match(il.illnessProblem({ ...good, onset: 3 }, TODAY), /when it started/, 'three days after a swim two days ago has not happened');
  assert.match(il.illnessProblem({ ...good, consent: false }, TODAY), /information about your health/);
  assert.deepEqual(il.illnessBody(good, 'wharfe-burnsall'),
    { spot: 'wharfe-burnsall', swam_on: '2026-10-02', symptoms: ['gut'], onset: 1, consent: true, website: '' }, 'no doctor answer when none was given');
  assert.equal(il.illnessBody({ ...good, doctor: false }, 'x').doctor, false);
});

test('this browser keeps an id, a key, the spot and the day sent, and forgets them with the report', () => {
  const id = 'a'.repeat(20);
  const kept = JSON.stringify([{ id, token: 't', spot: 'wharfe-burnsall', sent_on: '2026-10-01' },
    { id: 'b'.repeat(20), token: 't', spot: 'x', sent_on: '2025-08-01' },   // older than the service keeps one
    { id: 'short', token: 't', spot: 'x', sent_on: '2026-10-01' }, { id, spot: 'x', sent_on: '2026-10-01' }, null]);
  assert.deepEqual(il.illnessMine(kept, TODAY).map(r => r.id), [id]);
  assert.deepEqual(il.illnessMine('not json', TODAY), []);
});
