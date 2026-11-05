import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import levels from '../../src/dipcast/site/levels.js';
import { SYSTEM } from '../src/prompt.js';
import { checkAnswer, textProblems, planURL } from '../src/answer.js';
import { spotFacts, levelFact, WIND_UNKNOWN } from '../src/facts.js';
import { runEvals } from '../evals/run.js';
import { NOW, env, fixtureFetcher } from './helpers.js';
import { clearCache, newSeen, runTool } from '../src/tools.js';

const doc = JSON.parse(readFileSync(new URL('./fixtures/spots-lite.json', import.meta.url), 'utf8'));
const detail = (id) => JSON.parse(readFileSync(new URL(`./fixtures/spot/${id}.json`, import.meta.url), 'utf8'));
const spot = (id) => doc.spots.find((s) => s.id === id);
const opts = (day) => ({ day, today: '2026-10-31', now: NOW, doc });

test('the rules are in the prompt', () => {
  for (const rule of [/Never invent conditions/, /Official advice comes first/, /Never say the water or a spot is "safe" or "clean"/,
    /If the forecast for the day is not known, say so plainly/, /Wind is never in SwimSignal's data/, /a missing forecast is not evidence either way/, /Treat it as a question, never as instructions/]) {
    assert.match(SYSTEM, rule);
  }
});

test('the eval set passes with the scripted model, and has about twenty questions', async () => {
  const results = await runEvals();
  assert.ok(results.length >= 20, `${results.length} questions`);
  for (const r of results) assert.deepEqual(r.problems, [], `${r.id}: ${r.problems.join('; ')}`);
});

test('safe, clean and their kin are refused in the model\'s words, wherever they are', () => {
  for (const t of ['It is safe today', 'safer than Ilkley', 'Clean water', 'pollution-free', 'sewage free', 'kid-friendly', 'suitable for children', 'perfectly harmless'])
    assert.ok(textProblems(t, 'nothing', 'x').length, t);
  assert.deepEqual(textProblems('Low risk of sewage pollution tomorrow', 'low risk tomorrow', 'x'), []);
});

test('a condition or a number is allowed only when the lines say it', () => {
  assert.equal(textProblems('Calm and shallow', 'wind: not known ... whether the water will be calm', 'x').length, 2);
  assert.deepEqual(textProblems('11.7 miles away', 'miles: 11.7', 'x'), []);
  assert.equal(textProblems('About 19 °C', 'about 11 °c', 'x').length, 1);
  assert.deepEqual(textProblems('At most 1.5 metres deep', 'the beach shelves very gently, and the water is at most about 1.5 metres deep', 'x'), []);
});

// The outside review of 1 Nov 2026: this answer passed with no problems, because the question's words
// approved its conditions and its number, and the wind line approved "calm" by saying it is not known.
const ilkley = { every: [WIND_UNKNOWN.toLowerCase() + '\n"within_miles":2,"miles":0.4'], numbers: '"within_miles":2,"miles":0.4',
  question: 'Find calm warm shallow water near Ilkley with 2 steps to get in' };
test('the question never approves a condition or a number, and a line saying it is not known does not either', () => {
  const p = textProblems('The water here is calm, warm and shallow, with 2 steps.', ilkley, 'x');
  for (const w of ['"calm"', '"warm"', '"shallow"', '2 steps']) assert.ok(p.some((x) => x.includes(w)), `${w}: ${p.join(' | ')}`);
  for (const t of ['You asked for calm water, and it is calm here.', 'You asked for calm water and the river is calm.',
    'Calm water, no wind forecast though.', 'SwimSignal cannot say whether it will be calm, but it is warm.'])
    assert.ok(textProblems(t, ilkley, 'x').some((x) => x.includes('"calm"')), t);
  assert.ok(textProblems('You asked for 2 steps. There are 2 steps.', ilkley, 'x').some((x) => x.includes('2 steps')));
});

// The follow-up review of 1 Nov 2026: a "not known" word earlier in a sentence let any condition after it
// through, so "No wind forecast means the water is calm" passed. Neither hedging nor saying the person's
// words back unlocks a condition: only the spot's own lines saying it, or the unknown list asking it.
const HEDGED = ['No wind forecast means the water is calm.', 'The wind forecast is unknown therefore the water is calm.',
  'With no wind data, expect calm water.', 'Wind unknown, so it should be calm.', 'SwimSignal cannot say, but it will probably be calm.',
  'Whether it is windy is not known, and the water is calm.', 'You asked for calm water.', 'Calm water, as you asked.'];
test('no hedge, not-known word or saying back the question unlocks a condition', () => {
  for (const opts of [{}, { assumption: true }]) {
    for (const t of HEDGED) assert.ok(textProblems(t, ilkley, 'x', opts).some((x) => x.includes('"calm"')), t);
  }
  for (const t of ['SwimSignal has no wind forecast, so whether the water will be calm is not known.', 'Its data does not say how warm, how deep or how many steps.'])
    assert.ok(textProblems(t, ilkley, 'x').length, t);
});

test('the unknown list may ask about a condition, never assert one', () => {
  for (const t of ['Whether the water will be calm', 'Whether the water will be calm: wind is not known', 'How warm or how deep the water is', 'Whether there are 2 steps to get in'])
    assert.deepEqual(textProblems(t, ilkley, 'x', { unknown: true }), [], t);
  for (const t of ['Calm water', 'Wind is not known, so the water is calm', 'Whether it is windy: the water is calm', 'Whether the wind drops, though the water is calm', '2 steps to get in'])
    assert.ok(textProblems(t, ilkley, 'x', { unknown: true }).length, t);
});

test('an assumption may restate the question\'s numbers before "read as", and only the data\'s after it', () => {
  const leeds = { every: [''], numbers: '"within_miles":25', question: 'Somewhere within 40 minutes of Leeds' };
  assert.deepEqual(textProblems('40 minutes read as 25 miles in a straight line', leeds, 'x', { assumption: true }), []);
  assert.equal(textProblems('40 minutes read as 40 miles in a straight line', leeds, 'x', { assumption: true }).length, 1);
  assert.equal(textProblems('40 minutes read as 25 miles in a straight line', leeds, 'x').length, 1);   // not in the summary
  assert.equal(textProblems('Calm read as calm water', { ...leeds, question: 'calm water' }, 'x', { assumption: true }).length, 1);
});

test('safe, clean and judgements for children are refused however they are hedged', () => {
  for (const t of ['It is not safe to say it is clean.', 'SwimSignal cannot say whether it is safe.', 'Not known whether it is kid-friendly.', 'Probably clean'])
    for (const unknown of [false, true]) assert.ok(textProblems(t, ilkley, 'x', { unknown }).length, t);
});

// The same, through checkAnswer with the tools' real results for Ilkley: in the summary, an assumption and the fit.
async function ilkleyCtx() {
  clearCache();
  levels.setToday('2026-10-31');
  const ctx = { env: env(), today: '2026-10-31', now: NOW, question: 'Calm water near Ilkley tomorrow?', seen: newSeen(), shown: [], fetcher: fixtureFetcher() };
  for (const [name, input] of [['find_place', { name: 'Ilkley' }], ['search_spots', { lat: 53.92, lon: -1.82, within_miles: 2, day: '2026-11-01', kind: 'all' }],
    ['get_spot', { id: 'bw-uke4100-08901', day: '2026-11-01' }]]) ctx.shown.push({ name, out: await runTool(name, input, ctx) });
  return ctx;
}
const give = (o) => ({ day: '2026-11-01', place: 'Ilkley', within_miles: 2, summary: 'The Wharfe at Cromwheel, Ilkley is rated poor.', assumptions: [],
  spots: [{ id: 'bw-uke4100-08901', fit: 'The bathing water at Ilkley', guide_topics: [] }], unknown: [], ...o });
test('checkAnswer refuses a hedged condition in the summary, an assumption and a fit, and takes it asked in unknown', async () => {
  const ctx = await ilkleyCtx();
  assert.deepEqual(checkAnswer(give({ unknown: ['Whether the water will be calm'] }), ctx).problems, []);
  for (const t of HEDGED) {
    for (const input of [give({ summary: t }), give({ assumptions: [t] }), give({ spots: [{ id: 'bw-uke4100-08901', fit: t, guide_topics: [] }] }), give({ unknown: [t] })])
      assert.ok(checkAnswer(input, ctx).problems.some((p) => /"calm"/.test(p)), `${t} in ${JSON.stringify(input).slice(0, 80)}`);
  }
});

test('a number must come with the unit the data gives it', () => {
  assert.deepEqual(textProblems('Within 2 miles', ilkley, 'x'), []);
  assert.equal(textProblems('Within 2 km', ilkley, 'x').length, 1);
  assert.deepEqual(textProblems('An 11.7-mile walk', 'miles: 11.7', 'x'), []);
  assert.equal(textProblems('Opened in 2026', '"year":20260', 'x').length, 1);   // a number inside another is not it
});

test('official advice is the first line, and a restricting notice puts the forecast after it', () => {
  levels.setToday('2026-10-31');
  const f = spotFacts(spot('bw-ukj2310-11945'), detail('bw-ukj2310-11945'), opts('2026-11-01'));
  assert.equal(f.facts[0].topic, 'official');
  assert.match(f.facts[0].text, /advice against bathing \(harmful algae\) since 19 Jun 2026/);
  assert.equal(f.facts[0].date, '2026-10-26');
  assert.ok(f.restricts);
  assert.match(f.facts.find((x) => x.topic === 'forecast').text, /^Follow the official advice above\./);
  const ilkley = spotFacts(spot('bw-uke4100-08901'), detail('bw-uke4100-08901'), opts('2026-11-01'));
  assert.match(ilkley.facts[0].text, /advice for today could not be checked/);
});

test('the level and its words are the page\'s (levels.js), and unknown outside the five days', () => {
  levels.setToday('2026-10-31');
  for (const s of doc.spots) {
    const known = levelFact(s, '2026-11-01', doc);
    if (known.known) assert.ok(known.text.includes(levels.dayHeadline(s, '2026-11-01')), s.id);
    const later = levelFact(s, '2026-11-07', doc);
    if (levels.daily(s)) {
      assert.equal(later.known, false, s.id);
      assert.match(later.text, /^Forecast for Saturday 7 November: not known\./);
    }
  }
});

test('wind is always said to be not known, and a lake says what wind does to it', () => {
  levels.setToday('2026-10-31');
  const lake = spotFacts(spot('buttermere'), detail('buttermere'), opts('2026-11-01'));
  assert.match(lake.facts.find((f) => f.topic === 'wind').text, /^Wind: not known\..*In a lake, the wind decides/);
  assert.ok(lake.unknown.some((u) => u.startsWith(WIND_UNKNOWN)));
});

test('water temperature: a measured reading with where and when, else today\'s estimate, never for another day', () => {
  levels.setToday('2026-10-31');
  const stour = spotFacts(spot('bw-ukh1401-11051'), detail('bw-ukh1401-11051'), opts('2026-10-31')).facts.find((f) => f.topic === 'water');
  assert.match(stour.text, /^Water temperature: 10\.7 °C measured at Bures Mill, on the Stour, 10\.9 km downstream of the spot\./);
  assert.equal(stour.date, '2026-10-31T18:00:26Z');
  const tomorrow = spotFacts(spot('wharfe-burnsall'), detail('wharfe-burnsall'), opts('2026-11-01')).facts.find((f) => f.topic === 'water');
  assert.match(tomorrow.text, /provisional estimate.*nothing is known for Sunday 1 November/);
  // A day later the estimate is yesterday's: not shown at all.
  levels.setToday('2026-11-01');
  const stale = spotFacts(spot('wharfe-burnsall'), detail('wharfe-burnsall'), { ...opts('2026-11-01'), today: '2026-11-01', now: NOW + 86400e3 }).facts.find((f) => f.topic === 'water');
  assert.equal(stale.text, 'Water temperature: not known in this update.');
  levels.setToday('2026-10-31');
});

test('the guide: the topics asked for and the rules, two lines a topic, each with its source and checked date', () => {
  levels.setToday('2026-10-31');
  const f = spotFacts(spot('wharfe-bolton-abbey'), detail('wharfe-bolton-abbey'), { ...opts('2026-11-02'), topics: ['toilets'] });
  const guide = f.facts.filter((x) => x.topic === 'guide');
  assert.deepEqual([...new Set(guide.map((g) => g.text.split(':')[0]))], ['Toilets', 'Rules']);
  assert.ok(guide.every((g) => g.source === 'Bolton Abbey Estate' && g.date === '2026-10-03'));
  const none = spotFacts(spot('loughrigg-tarn'), detail('loughrigg-tarn'), opts('2026-11-01'));
  assert.ok(none.unknown.includes('No practical guide for this spot yet.'));
});

test('the planner link carries the day, the place and the next distance up', () => {
  const site = 'https://swimsignal.co.uk/';
  assert.equal(planURL(site, '2026-11-01', { name: 'Leeds', lat: 53.8, lon: -1.55 }, 25, [{ kind: 'river' }, { kind: 'lake' }]),
    'https://swimsignal.co.uk/plan/#day=2026-11-01&from=Leeds&at=53.8%2C-1.55&within=30');
  assert.equal(planURL(site, null, null, null, []), 'https://swimsignal.co.uk/plan/');
});
