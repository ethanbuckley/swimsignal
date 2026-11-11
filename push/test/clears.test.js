// Back to low risk (README.md, "Back to low risk"; src/clears.js): a browser with alerts on asks to hear
// when a spot is at low risk again. One message, the first time a build gives it the level low, once the
// build says so (alerts.json `clear_alerts`, from the repository variable DIPCAST_PUSH_CLEARS); never
// while a notice restricting swimming shows there; the request is then deleted, or lapses after 14 days.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { handleRequest, runCron, subKey } from '../src/index.js';
import { CAVEAT, CLEAR_DAYS, MAX_CLEARS, clearPayload, clearedNow, cleanClears } from '../src/clears.js';
import { FakeKV, makeUserAgent, makeVapidEnv } from './helpers.js';

const SITE = 'https://swimsignal.example/', ORIGIN = 'https://swimsignal.example';
const vapid = await makeVapidEnv();
const LEVELS = ['low', 'moderate', 'high', 'very high'], HEADS = ['Low risk for the next five days', 'Moderate risk today: sewage spills', 'High risk today: sewage spills', 'Very high risk today: sewage spills'];
const ACTS = ['Usual care: cover cuts, try not to swallow water and wash your hands before eating.', 'Take more care.', 'Better to choose a lower day or spot.', 'Avoid swimming here today: choose a lower day or spot.'];
const spot = (name, rank, id, extra = {}) => ({ name, rank, level: LEVELS[rank], headline: HEADS[rank], action: ACTS[rank], url: `${SITE}spot/${id}/`, ...extra });
// A build: two spots at the ranks given; `on`: the build turned the alert on.
const build = (generated_at, { a = 3, b = 1, on = true, extra = {} } = {}) => ({ generated_at, dates: [generated_at.slice(0, 10)], words: [],
  spots: { a: spot('River Dart, Dartington Pontoon', a, 'a', extra.a), b: spot('River Dart, Spitchwick', b, 'b', extra.b) }, ...(on ? { clear_alerts: true } : {}) });

async function setup(clock = Date.parse('2026-11-11T07:10:00Z')) {
  const kv = new FakeKV(), env = { PUSH: kv, SITE_URL: SITE, ALLOWED_ORIGIN: ORIGIN, ...vapid }, agents = {}, pushes = [], logs = [];
  let alerts;
  const post = async (name, body) => {
    const endpoint = `https://fcm.googleapis.com/fcm/send/${name}`;
    const ua = Object.values(agents).find((x) => x.name === name) ?? makeUserAgent(endpoint); agents[endpoint] = { name, ...ua };
    return handleRequest(new Request('https://push.example/subscribe', { method: 'POST', headers: { Origin: ORIGIN, 'Content-Type': 'application/json' },
      body: JSON.stringify({ subscription: ua.subscription, ...body }) }), env, { now: () => clock });
  };
  const record = async (name) => kv.get(await subKey(`https://fcm.googleapis.com/fcm/send/${name}`), 'json');
  const fetch = async (url, init) => {
    if (url.startsWith(`${SITE}data/alerts.json`)) return Response.json(alerts);
    const { issued_at, expires_at, ...payload } = agents[url].read(init.body);
    pushes.push({ to: agents[url].name, ...payload });
    return new Response(null, { status: 201 });
  };
  const run = (a) => { if (a) alerts = a; return runCron(env, { fetch, log: (m) => logs.push(m), now: () => clock }); };
  // A new build (ten minutes after it is issued): the run that finds it, then the run that sends.
  const deliver = async (a) => { clock = Date.parse(a.generated_at) + 600e3; const first = await run(a); clock += 120e3; const second = await run(); return { first, second }; };
  return { kv, post, record, run, deliver, pushes, logs, at: (x) => { clock = x; } };
}

test('what a page may send: up to ten spot ids, none twice', () => {
  assert.deepEqual(cleanClears(['a', 'osm-dart-dartington']), ['a', 'osm-dart-dartington']);
  assert.throws(() => cleanClears('a'), /clears must be an array/);
  assert.throws(() => cleanClears(['a', 'a']), /the same spot twice/);
  assert.throws(() => cleanClears(['a b']), /bad spot id in clears/);
  assert.throws(() => cleanClears(Array.from({ length: MAX_CLEARS + 1 }, (_, i) => `s${i}`)), /at most 10 spots to hear about/);
});

test('a request is kept with the day it lapses, beside the saved spots, which a later request from the Saved page leaves as they were', async () => {
  const t = await setup();
  assert.equal((await t.post('ann', { spots: ['b'], weekly: true })).status, 204);
  assert.equal((await t.post('ann', { clears: ['a'] })).status, 204);
  const until = '2026-11-25';   // 14 days after 11 Nov
  assert.equal(CLEAR_DAYS, 14);
  let r = await t.record('ann');
  assert.deepEqual([r.spots, r.weekly, r.clears], [['b'], true, [{ spot: 'a', until }]]);
  assert.deepEqual(t.kv.meta.get(await subKey('https://fcm.googleapis.com/fcm/send/ann')), { s: ['b'], w: 1, c: [`a ${until}`] });
  // The Saved page sends its spots again: the request stays. An empty list of spots keeps the record while it holds one.
  await t.post('ann', { spots: [] });
  r = await t.record('ann');
  assert.deepEqual([r.spots, r.clears], [[], [{ spot: 'a', until }]]);
  // Stopping it (an empty list) with nothing else left deletes the record.
  await t.post('ann', { clears: [] });
  assert.equal(await t.record('ann'), null);
  assert.equal((await t.post('bob', { clears: ['a', 'a'] })).status, 400);
  assert.equal(await (await t.post('bob', { clears: ['a', 'a'] })).text(), 'the same spot twice in clears');
});

test('one message the first time a build gives the spot low risk, in the page\'s words with its caveat; then the request is gone', async () => {
  const t = await setup();
  await t.post('ann', { clears: ['a'] }); await t.post('bob', { spots: ['a'] });
  await t.deliver(build('2026-11-11T07:00:00.000Z'));   // the first build: nothing to compare
  let r = await t.deliver(build('2026-11-12T07:00:00.000Z', { a: 2 }));   // high: not low yet
  assert.deepEqual([r.first.queued, t.pushes.length], [0, 0]);
  r = await t.deliver(build('2026-11-13T07:00:00.000Z', { a: 1 }));   // moderate: still not
  assert.equal(t.pushes.length, 0);
  r = await t.deliver(build('2026-11-14T07:00:00.000Z', { a: 0 }));
  assert.deepEqual([r.first.queued, r.second.sent], [1, 1]);
  assert.ok(t.logs.includes('cron: 2026-11-14T07:00:00.000Z: 0 spots rose to high, 0 alerts to send, 1 back to low risk'), t.logs.join('\n'));
  assert.deepEqual(t.pushes, [{ to: 'ann', title: 'River Dart, Dartington Pontoon: back to low risk',
    body: `Low risk for the next five days. Usual care: cover cuts, try not to swallow water and wash your hands before eating. ${CAVEAT}`,
    url: `${SITE}spot/a/`, tag: 'dipspot-a-low' }]);
  assert.doesNotMatch(t.pushes[0].body, /\b(safe|clean|all clear)\b/i);
  assert.equal(await t.record('ann'), null, 'the request was all the record held');
  assert.ok(await t.record('bob'), 'who saved the spot and did not ask hears nothing, and keeps their record');
  // The next builds, still low: nothing more.
  await t.deliver(build('2026-11-14T13:00:00.000Z', { a: 0 }));
  await t.deliver(build('2026-11-15T07:00:00.000Z', { a: 0 }));
  assert.equal(t.pushes.length, 1);
});

test('nothing is sent until the build turns it on, and the request waits', async () => {
  const t = await setup();
  await t.post('ann', { clears: ['a'] });
  await t.deliver(build('2026-11-11T07:00:00.000Z', { on: false }));
  const r = await t.deliver(build('2026-11-12T07:00:00.000Z', { a: 0, on: false }));
  assert.deepEqual([r.first.queued, t.pushes.length], [0, 0]);
  assert.deepEqual((await t.record('ann')).clears, [{ spot: 'a', until: '2026-11-25' }]);
  assert.equal(clearedNow(build('2026-11-12T07:00:00.000Z', { a: 0, on: false })).size, 0);
  await t.deliver(build('2026-11-12T13:00:00.000Z', { a: 0 }));
  assert.equal(t.pushes.length, 1);
});

test('never while a notice restricting swimming shows at the spot; any other notice goes first in the message', async () => {
  const t = await setup();
  const algae = { official: 'EA advice against bathing (harmful algae) · since 8 Jun · checked 13 Nov', official_restricts: true };
  await t.post('ann', { clears: ['a'] });
  await t.deliver(build('2026-11-11T07:00:00.000Z'));
  await t.deliver(build('2026-11-13T07:00:00.000Z', { a: 0, extra: { a: algae } }));
  assert.equal(t.pushes.length, 0, 'low for sewage, under advice against bathing: no message');
  assert.ok((await t.record('ann')).clears.length, 'and the request waits');
  // The notice lifts while the level is still low: now it is sent.
  await t.deliver(build('2026-11-14T07:00:00.000Z', { a: 0 }));
  assert.equal(t.pushes.length, 1);
  // A notice that does not restrict swimming: the message leads with its marker.
  const p = clearPayload(['a'], { a: spot('Frensham Great Pond', 0, 'a', { official: 'EA notice · checked 13 Nov', action: 'Official: EA notice. Read the official notice first; the level is SwimSignal\'s sewage forecast only.' }) }, SITE);
  assert.match(p.body, /^Official notice shown · Low risk for the next five days\. Official: EA notice\./);
  assert.ok(p.body.endsWith(CAVEAT));
});

test('a spot that rises again before the message is sent gets none, and the request waits for the next low', async () => {
  const t = await setup();
  await t.post('ann', { clears: ['a'] });
  await t.deliver(build('2026-11-11T07:00:00.000Z'));
  // Found low and queued, then a newer build raises it before the sending run.
  t.at(Date.parse('2026-11-12T07:10:00Z'));
  const first = await t.run(build('2026-11-12T07:00:00.000Z', { a: 0 }));
  assert.equal(first.queued, 1);
  t.at(Date.parse('2026-11-12T07:12:00Z'));
  await t.run(build('2026-11-12T07:05:00.000Z', { a: 1 }));
  assert.equal(t.pushes.length, 0);
  assert.ok((await t.record('ann')).clears.length);
});

test('several spots asked about and low in one build are one message; a request not answered in 14 days is forgotten', async () => {
  const t = await setup();
  await t.post('ann', { clears: ['a', 'b'] });
  await t.deliver(build('2026-11-11T07:00:00.000Z'));
  await t.deliver(build('2026-11-12T07:00:00.000Z', { a: 0, b: 0 }));
  assert.deepEqual(t.pushes, [{ to: 'ann', title: '2 spots you asked about are back to low risk',
    body: `River Dart, Dartington Pontoon, River Dart, Spitchwick. ${CAVEAT}`, url: SITE, tag: 'dipspot-low' }]);
  assert.equal(await t.record('ann'), null);
  // Lapsed: asked on 11 Nov, the spot is low only on 26 Nov. Nothing is sent, and the record is tidied away.
  const u = await setup();
  await u.post('cat', { clears: ['a'] });
  await u.deliver(build('2026-11-11T07:00:00.000Z'));
  await u.deliver(build('2026-11-26T07:00:00.000Z', { a: 0 }));
  assert.equal(u.pushes.length, 0);
  assert.equal(await u.record('cat'), null);
});
