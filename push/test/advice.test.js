// Official advice at a saved spot (README.md, "Official advice at a saved spot"): one alert when a notice
// appears at a saved spot, whatever its level, once the build says so (alerts.json `advice_alerts`, from the
// repository variable DIPCAST_PUSH_ADVICE). None when a notice lifts. Each spot at most once in 20 hours.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { alertPayload, handleRequest, newAdvice, runCron, subKey } from '../src/index.js';
import { FakeKV, makeUserAgent, makeVapidEnv } from './helpers.js';

const SITE = 'https://swimsignal.example/', ORIGIN = 'https://swimsignal.example';
const vapid = await makeVapidEnv();
const NOTICE = 'EA advice against bathing (harmful algae) · since 8 Jun';
const ACTION = `Official: ${NOTICE} · checked 8 Jun. Read the official notice first; the level is SwimSignal's sewage forecast only.`;

const spot = (name, rank, id) => ({ name, rank, level: ['low', 'moderate', 'high', 'very high'][rank], headline: `${['Low', 'Moderate', 'High', 'Very high'][rank]} risk`,
  action: 'Usual care.', url: `${SITE}spot/${id}/` });
// A build: three spots, `notices` {id: the check's words or a whole brief}, `ranks` {id: rank}. dates are
// there because the Worker keeps notices only for an alerts.json that has them (dates.js noticesOf).
function build(generated_at, { notices = {}, ranks = {}, on = true } = {}) {
  const spots = { a: spot('Frensham Great Pond', ranks.a ?? 0, 'a'), b: spot('Wharfe at Burley', ranks.b ?? 0, 'b'), c: spot('Thames at Henley', ranks.c ?? 1, 'c') };
  for (const [id, brief] of Object.entries(notices)) spots[id] = { ...spots[id], official: brief, action: ACTION };
  return { generated_at, dates: [generated_at.slice(0, 10)], words: [], spots, ...(on ? { advice_alerts: true } : {}) };
}

async function setup(clock = Date.parse('2027-06-07T05:10:00Z')) {
  const kv = new FakeKV(), env = { PUSH: kv, SITE_URL: SITE, ALLOWED_ORIGIN: ORIGIN, ...vapid }, agents = {}, pushes = [], logs = [];
  let alerts;
  const subscribe = async (name, spots) => {
    const ua = makeUserAgent(`https://fcm.googleapis.com/fcm/send/${name}`); agents[ua.subscription.endpoint] = { name, ...ua };
    const res = await handleRequest(new Request('https://push.example/subscribe', { method: 'POST', headers: { Origin: ORIGIN, 'Content-Type': 'application/json' },
      body: JSON.stringify({ subscription: ua.subscription, spots }) }), env, { now: () => clock });
    assert.equal(res.status, 204);
  };
  const fetch = async (url, init) => {
    if (url.startsWith(`${SITE}data/alerts.json`)) return Response.json(alerts);
    const { issued_at, expires_at, ...payload } = agents[url].read(init.body);
    pushes.push({ to: agents[url].name, ...payload });
    return new Response(null, { status: 201 });
  };
  const run = (a) => { if (a) alerts = a; return runCron(env, { fetch, log: (m) => logs.push(m), now: () => clock }); };
  // A new build at `iso` (ten minutes after it): the run that finds it, then the run that sends.
  const deliver = async (a) => { clock = Date.parse(a.generated_at) + 600e3; const first = await run(a); clock += 120e3; const second = await run(); return { first, second }; };
  await subscribe('ann', ['a']); await subscribe('bob', ['b']); await subscribe('cat', ['a', 'b']);
  return { kv, run, deliver, pushes, logs, at: (t) => { clock = t; } };
}

test('a notice appearing at a saved low-risk spot sends one alert to those who saved it, under a tag of its own', async () => {
  const t = await setup();
  await t.deliver(build('2027-06-07T05:00:00.000Z'));
  const r = await t.deliver(build('2027-06-07T09:00:00.000Z', { notices: { a: `${NOTICE} · checked 7 Jun` } }));
  assert.deepEqual([r.first.advised, r.first.queued, r.second.sent], [['a'], 2, 2]);
  assert.ok(t.logs.includes('cron: 2027-06-07T09:00:00.000Z: 0 spots rose to high, 1 with new official advice, 2 alerts to send'), t.logs.join('\n'));
  assert.deepEqual(t.pushes.map((p) => p.to).sort(), ['ann', 'cat']);
  const p = t.pushes[0];
  assert.equal(p.title, 'Frensham Great Pond');
  assert.equal(p.body, `New official notice · Low risk. ${ACTION}`);
  assert.equal(p.url, `${SITE}spot/a/`);
  // Not dipspot-a, which a high-risk alert for the spot uses: the same tag would replace it without a sound.
  assert.match(p.tag, /^dipspot-a-n[0-9a-f]{8}$/);
  assert.ok((await t.kv.get('state', 'json')).advised.a);
});

test('a re-check, a lift and a return within 20 hours send nothing; after 20 hours a return is news again', async () => {
  const t = await setup();
  await t.deliver(build('2027-06-07T05:00:00.000Z'));
  await t.deliver(build('2027-06-07T09:00:00.000Z', { notices: { a: `${NOTICE} · checked 7 Jun` } }));
  assert.equal(t.pushes.length, 2);
  // Re-checked, or gone stale: the same notice (shared.js noticeKey).
  assert.equal((await t.deliver(build('2027-06-07T13:00:00.000Z', { notices: { a: `${NOTICE} · not re-checked since 7 Jun` } }))).first.queued, 0);
  // Lifted: no saved-spot alert (a lift is not an all-clear).
  assert.equal((await t.deliver(build('2027-06-07T17:00:00.000Z'))).first.queued, 0);
  // Back the same evening: inside the spot's 20 hours, nothing.
  const back = await t.deliver(build('2027-06-07T21:00:00.000Z', { notices: { a: `${NOTICE} · checked 7 Jun` } }));
  assert.deepEqual([back.first.queued, 'advised' in back.first], [0, false]);
  // Lifted overnight and back the next afternoon, more than 20 hours after the first alert.
  await t.deliver(build('2027-06-08T05:00:00.000Z'));
  const again = await t.deliver(build('2027-06-08T09:10:00.000Z', { notices: { a: `${NOTICE} · checked 8 Jun` } }));
  assert.deepEqual([again.first.advised, again.second.sent], [['a'], 2]);
  assert.equal(t.pushes.length, 4);
});

test('a notice that changes to another is news; the advice and the high-risk alerts keep separate 20 hours', async () => {
  const t = await setup();
  await t.deliver(build('2027-06-07T05:00:00.000Z'));
  // b rises to high: the rise alert.
  await t.deliver(build('2027-06-07T09:00:00.000Z', { ranks: { b: 2 } }));
  assert.deepEqual(t.pushes.map((p) => p.to).sort(), ['bob', 'cat']);
  // That afternoon a notice appears at b: its own alert, though b's rise was alerted this morning.
  const r = await t.deliver(build('2027-06-07T13:00:00.000Z', { ranks: { b: 2 }, notices: { b: `${NOTICE} · checked 7 Jun` } }));
  assert.deepEqual(r.first.advised, ['b']);
  assert.equal(t.pushes.length, 4);
  assert.ok(t.pushes[2].body.startsWith('New official notice · High risk.'), t.pushes[2].body);
  // At a, a notice appears and is then replaced by a different one: a is told once (its 20 hours).
  await t.deliver(build('2027-06-07T17:00:00.000Z', { ranks: { b: 2 }, notices: { a: `${NOTICE} · checked 7 Jun`, b: `${NOTICE} · checked 7 Jun` } }));
  assert.equal(t.pushes.length, 6);
  const other = 'EA advice against bathing (pollution incident) · since 7 Jun · checked 7 Jun';
  assert.deepEqual(newAdvice(build('x', { notices: { a: other } }), { a: NOTICE }), ['a']);
  assert.equal((await t.deliver(build('2027-06-07T21:00:00.000Z', { ranks: { b: 2 }, notices: { a: other, b: `${NOTICE} · checked 7 Jun` } }))).first.queued, 0);
});

test('a spot that rises to high with a new notice gets one alert, the rise, which leads with the notice', async () => {
  const t = await setup();
  await t.deliver(build('2027-06-07T05:00:00.000Z'));
  const r = await t.deliver(build('2027-06-07T09:00:00.000Z', { ranks: { a: 2 }, notices: { a: `${NOTICE} · checked 7 Jun` } }));
  assert.deepEqual([r.first.risen, 'advised' in r.first, r.first.queued], [['a'], false, 2]);
  assert.deepEqual(t.pushes.map((p) => [p.to, p.tag]).sort(), [['ann', 'dipspot-a'], ['cat', 'dipspot-a']]);
  assert.equal(t.pushes[0].body, `Official notice shown · High risk. ${ACTION}`);
  // Its notice counts as told: it does not alert again when the spot falls back to low the same day.
  assert.equal((await t.deliver(build('2027-06-07T13:00:00.000Z', { notices: { a: `${NOTICE} · checked 7 Jun` } }))).first.queued, 0);
  assert.ok((await t.kv.get('state', 'json')).advised.a);
});

test('a queued advice alert whose notice lifts before it is sent says nothing', async () => {
  const t = await setup();
  await t.deliver(build('2027-06-07T05:00:00.000Z'));
  t.at(Date.parse('2027-06-07T09:10:00Z'));
  assert.equal((await t.run(build('2027-06-07T09:00:00.000Z', { notices: { a: `${NOTICE} · checked 7 Jun` } }))).queued, 2);
  t.at(Date.parse('2027-06-07T09:12:00Z'));
  const sent = await t.run(build('2027-06-07T09:05:00.000Z'));
  assert.deepEqual([sent.sent, sent.queued, t.pushes.length], [0, 0, 0]);
});

test('off until the build says so, and nothing from a state with no notices kept: deploying the Worker changes nothing', async () => {
  const t = await setup();
  await t.deliver(build('2027-06-07T05:00:00.000Z', { on: false }));
  const off = await t.deliver(build('2027-06-07T09:00:00.000Z', { on: false, notices: { a: `${NOTICE} · checked 7 Jun` } }));
  assert.deepEqual([off.first.queued, 'advised' in off.first, 'advised' in (await t.kv.get('state', 'json'))], [0, false, false]);
  // Turned on with the notice already showing: it was in the last build, so it is not new.
  assert.equal((await t.deliver(build('2027-06-07T13:00:00.000Z', { notices: { a: `${NOTICE} · checked 7 Jun` } }))).first.queued, 0);
  assert.deepEqual(newAdvice(build('x', { notices: { a: NOTICE } }), undefined), []);   // a state from before notices
  assert.equal(t.pushes.length, 0);
});

test('several spots: the title says what they share, new notices first and marked, under a tag that changes with them', () => {
  const s = build('x', { ranks: { c: 3 }, notices: { a: `${NOTICE} · checked 7 Jun`, b: `${NOTICE} · checked 7 Jun` } }).spots;
  const advice = alertPayload(['a', 'b'], s, SITE, new Set(['a', 'b']));
  assert.equal(advice.title, 'New official advice at 2 of your saved spots');
  assert.equal(advice.body, 'New official notice · Frensham Great Pond, New official notice · Wharfe at Burley');
  assert.match(advice.tag, /^dipspot-saved-n[0-9a-f]{8}$/);
  const mixed = alertPayload(['c', 'a'], s, SITE, new Set(['a']));
  assert.equal(mixed.title, '2 of your saved spots: high risk or new official advice');
  assert.equal(mixed.body, 'New official notice · Frensham Great Pond, Thames at Henley');
  assert.notEqual(alertPayload(['a'], s, SITE, new Set(['a'])).tag, alertPayload(['a'], { a: { ...s.a, official: 'Other notice' } }, SITE, new Set(['a'])).tag);
  // Without new advice, as before: every spot high, and the old tag.
  assert.deepEqual([alertPayload(['c'], s, SITE).tag, alertPayload(['c', 'c2'], { ...s, c2: s.c }, SITE).title], ['dipspot-c', '2 of your saved spots are at high or very high risk']);
});
