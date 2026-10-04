import { test } from 'node:test';
import assert from 'node:assert/strict';
import { handleRequest, runCron, subKey } from '../src/index.js';
import { weeklyPayload, weeklyWindow } from '../src/weekly.js';
import { FakeKV, makeUserAgent, makeVapidEnv } from './helpers.js';

const SITE = 'https://swimsignal.example/', ORIGIN = 'https://swimsignal.example';
const vapid = await makeVapidEnv();
// Thursday 8 October 2026: 15:30 BST, 18:00 BST is 17:00 UTC.
const GEN = '2026-10-08T14:30:00.000Z', THU_6PM = Date.parse('2026-10-08T17:00:00Z');

const best = (date, level, words) => ({ date, level, words });
const SPOTS = {
  a: { name: 'Aston', rank: 0, level: 'low', headline: 'Low risk for the next five days', url: `${SITE}spot/a/`, best: best('2026-10-10', 'low', 'Saturday, low risk') },
  b: { name: 'Bray', rank: 1, level: 'moderate', headline: 'Moderate risk today: sewage spills', url: `${SITE}spot/b/`, best: best('2026-10-09', 'moderate', 'tomorrow and Sunday, moderate risk') },
  c: { name: 'Coniston', rank: -1, level: 'no overflows', headline: 'No sewage risk from monitored overflows', url: `${SITE}spot/c/` },   // no best: the same every day
};
const ranks = (spots) => Object.fromEntries(Object.entries(spots).map(([id, s]) => [id, s.rank]));

// Browsers subscribed through the Worker's own /subscribe, so the record and metadata are the real ones.
async function setup({ users, clock = THU_6PM, spots = SPOTS, generated_at = GEN, status = () => 201 }) {
  const kv = new FakeKV();
  const env = { PUSH: kv, SITE_URL: SITE, ALLOWED_ORIGIN: ORIGIN, ...vapid };
  const agents = {};
  const subscribe = async (name, body) => {
    const res = await handleRequest(new Request('https://push.example/subscribe', { method: 'POST',
      headers: { Origin: ORIGIN, 'Content-Type': 'application/json' }, body: JSON.stringify({ subscription: agents[name].subscription, ...body }) }), env);
    assert.equal(res.status, 204, await res.text());
  };
  for (const [name, { spots: saved, weekly }] of Object.entries(users)) {
    const ua = makeUserAgent(`https://fcm.googleapis.com/fcm/send/${name}`);
    agents[name] = ua; agents[ua.subscription.endpoint] = { name, ...ua };
    await subscribe(name, { spots: saved, ...(weekly === undefined ? {} : { weekly }) });
  }
  await kv.put('state', JSON.stringify({ generated_at, ranks: ranks(spots) }));
  kv.writes = 0;
  const read = [], get = kv.get.bind(kv);
  kv.get = (key, type) => { read.push(key); return get(key, type); };
  const pushes = [], logs = [];
  let alerts = { generated_at, spots };
  const fetch = async (url, init) => {
    if (url.startsWith(`${SITE}data/alerts.json`)) return Response.json(alerts);
    const agent = agents[url];
    const { issued_at, expires_at, ...payload } = agent.read(init.body);
    pushes.push({ to: agent.name, payload, issued_at, expires_at, ttl: init.headers.TTL });
    return new Response(null, { status: status(agent.name) });
  };
  const run = () => runCron(env, { fetch, log: (m) => logs.push(m), now: () => clock });
  return { kv, env, run, pushes, logs, read, subscribe, setAlerts: (a) => { alerts = a; }, advance: (ms) => { clock += ms; }, at: (t) => { clock = t; } };
}

test('the page\'s weekly: true is kept in the record and the key\'s metadata; absent or false keeps nothing', async () => {
  const t = await setup({ users: { ann: { spots: ['a'], weekly: true }, bob: { spots: ['a'] }, cat: { spots: ['a'], weekly: false } } });
  const key = (n) => subKey(`https://fcm.googleapis.com/fcm/send/${n}`);
  assert.equal((await t.kv.get(await key('ann'), 'json')).weekly, true);
  assert.deepEqual(t.kv.meta.get(await key('ann')), { s: ['a'], w: 1 });
  for (const n of ['bob', 'cat']) {
    assert.equal('weekly' in (await t.kv.get(await key(n), 'json')), false);
    assert.deepEqual(t.kv.meta.get(await key(n)), { s: ['a'] });
  }
  const res = await handleRequest(new Request('https://push.example/subscribe', { method: 'POST', headers: { Origin: ORIGIN },
    body: JSON.stringify({ subscription: makeUserAgent('https://fcm.googleapis.com/fcm/send/x').subscription, spots: ['a'], weekly: 'yes' }) }), t.env);
  assert.equal(res.status, 400);
  assert.match(await res.text(), /weekly must be true or false/);
});

test('Thursday 18:00 UK queues those who asked; the next run sends; then nothing until next week', async () => {
  const t = await setup({ users: {
    ann: { spots: ['b', 'a', 'c'], weekly: true }, bob: { spots: ['a'] }, cat: { spots: ['c'], weekly: true }, dan: { spots: ['a'], weekly: true } } });
  const first = await t.run();
  assert.deepEqual(first.weekly, { sent: 0, removed: 0, failed: 0, queued: 3 });
  assert.equal(t.pushes.length, 0);   // KV allows one write a second to a key: sending starts next run
  assert.equal(t.kv.writes, 1);
  assert.deepEqual((await t.kv.get('weekq', 'json')).week, '2026-10-08');
  t.advance(120e3);
  const second = await t.run();
  assert.deepEqual(second, { risen: [], sent: 0, removed: 0, failed: 0, queued: 0, weekly: { sent: 2, removed: 0, failed: 0, queued: 0 } });
  const by = Object.fromEntries(t.pushes.map((p) => [p.to, p]));
  assert.deepEqual(Object.keys(by).sort(), ['ann', 'dan']);   // bob did not ask; cat's one spot is the same every day
  assert.deepEqual(by.ann.payload, { title: 'Lowest pollution risk this week',
    body: 'Aston: Saturday, low risk.\nBray: tomorrow and Sunday, moderate risk.', url: `${SITE}saved/`, tag: 'dipspot-week' });
  assert.deepEqual(by.dan.payload, { title: 'Lowest pollution risk this week', body: 'Aston: Saturday, low risk.', url: `${SITE}spot/a/`, tag: 'dipspot-week' });
  // Issued and expiring as an alert is: the forecast's time, and 8 hours on (before UK midnight).
  assert.equal(by.ann.issued_at, GEN);
  assert.equal(by.ann.expires_at, '2026-10-08T22:30:00.000Z');
  assert.equal(by.ann.ttl, String((Date.parse('2026-10-08T22:30:00Z') - (THU_6PM + 120e3)) / 1000));
  t.advance(120e3);
  const third = await t.run();
  assert.equal('weekly' in third, false);
  assert.equal(t.pushes.length, 2);
  // Next Thursday, again.
  t.at(THU_6PM + 7 * 86400e3);
  const next = { generated_at: '2026-10-15T14:30:00.000Z', spots: SPOTS };
  t.setAlerts(next);
  assert.equal((await t.run()).weekly.queued, 3);
  t.advance(120e3);
  assert.equal((await t.run()).weekly.sent, 2);
});

test('outside Thursday evening the cron reads nothing for the note', async () => {
  for (const at of ['2026-10-07T17:00:00Z', '2026-10-08T16:59:00Z', '2026-10-08T23:00:00Z', '2026-10-09T17:00:00Z']) {
    const t = await setup({ users: { ann: { spots: ['a'], weekly: true } }, clock: Date.parse(at),
      generated_at: new Date(Date.parse(at) - 3600e3).toISOString() });
    const result = await t.run();
    assert.equal('weekly' in result, false, at);
    assert.equal(t.read.includes('weekq'), false, at);
    assert.equal(t.kv.writes, 0, at);
  }
});

test('the window is 18:00 to midnight UK time, in summer and in winter', () => {
  assert.equal(weeklyWindow(Date.parse('2026-10-08T16:59:59Z')), null);
  assert.equal(weeklyWindow(Date.parse('2026-10-08T17:00:00Z')), '2026-10-08');   // 18:00 BST
  assert.equal(weeklyWindow(Date.parse('2026-10-08T22:59:59Z')), '2026-10-08');
  assert.equal(weeklyWindow(Date.parse('2026-10-08T23:00:00Z')), null);            // Friday in the UK
  assert.equal(weeklyWindow(Date.parse('2026-11-05T17:59:59Z')), null);
  assert.equal(weeklyWindow(Date.parse('2026-11-05T18:00:00Z')), '2026-11-05');   // 18:00 GMT
  assert.equal(weeklyWindow(Date.parse('2026-11-05T23:59:59Z')), '2026-11-05');
});

test('the high-risk alerts come first: the note waits until their queue is empty', async () => {
  const t = await setup({ users: { ann: { spots: ['a'], weekly: true } } });
  // The last build had a low; this one has it high: an alert to queue and send.
  t.setAlerts({ generated_at: '2026-10-08T16:30:00.000Z', spots: { ...SPOTS, a: { ...SPOTS.a, rank: 2, level: 'high', headline: 'High risk today: sewage spills' } } });
  const staged = await t.run();
  assert.deepEqual([staged.risen, staged.queued, 'weekly' in staged], [['a'], 1, false]);
  t.advance(120e3);
  const drained = await t.run();
  assert.deepEqual([drained.sent, 'weekly' in drained], [1, false]);
  assert.equal(t.pushes[0].payload.tag, 'dipspot-a');
  t.advance(120e3);
  assert.equal((await t.run()).weekly.queued, 1);
  t.advance(120e3);
  assert.equal((await t.run()).weekly.sent, 1);
  assert.equal(t.pushes[1].payload.tag, 'dipspot-week');
});

test('a run sends SENDS_PER_RUN notes and writes the queue once', async () => {
  const users = Object.fromEntries(Array.from({ length: 20 }, (_, i) => [`u${String(i).padStart(2, '0')}`, { spots: ['a'], weekly: true }]));
  const t = await setup({ users });
  const writes = [];
  for (let i = 0; i < 4; i++) {
    const before = t.kv.writes;
    const r = await t.run();
    writes.push([r.weekly?.sent ?? null, r.weekly?.queued ?? null, t.kv.writes - before]);
    t.advance(120e3);
  }
  assert.deepEqual(writes, [[0, 20, 1], [15, 5, 1], [5, 0, 1], [null, null, 0]]);
  assert.equal(new Set(t.pushes.map((p) => p.to)).size, 20);
  assert.equal(t.pushes.length, 20);
});

test('what is not sent by UK midnight is dropped, and said so next Thursday', async () => {
  const late = '2026-10-08T20:00:00.000Z';   // 21:00 BST: expires at UK midnight, 23:00 UTC
  const users = { ann: { spots: ['a'], weekly: true }, bob: { spots: ['a'], weekly: true }, cat: { spots: ['a'], weekly: true } };
  const t = await setup({ users, generated_at: late, clock: Date.parse('2026-10-08T22:56:00Z') });
  t.env.SENDS_PER_RUN = '1';
  assert.equal((await t.run()).weekly.queued, 3);
  t.advance(120e3);
  assert.equal((await t.run()).weekly.sent, 1);
  t.advance(120e3);   // 23:00 UTC, midnight in the UK: the forecast has expired, and so has the window
  const after = await t.run();
  assert.equal('weekly' in after, false);
  assert.equal(t.pushes.length, 1);
  t.at(Date.parse('2026-10-15T17:00:00Z'));
  t.setAlerts({ generated_at: '2026-10-15T14:30:00.000Z', spots: SPOTS });
  assert.equal((await t.run()).weekly.queued, 3);
  assert.ok(t.logs.includes('weekly: 2 notes from 2026-10-08 were not sent before midnight'));
});

test('a note is not sent once it is turned off, or the alerts are, or the push service says the address is gone', async () => {
  const t = await setup({ users: { ann: { spots: ['a'], weekly: true }, bob: { spots: ['a'], weekly: true }, cat: { spots: ['a'], weekly: true } },
    status: (name) => (name === 'cat' ? 410 : 201) });
  await t.run();
  await t.subscribe('ann', { spots: ['a'], weekly: false });
  await handleRequest(new Request('https://push.example/unsubscribe', { method: 'POST', headers: { Origin: ORIGIN },
    body: JSON.stringify({ endpoint: 'https://fcm.googleapis.com/fcm/send/bob' }) }), t.env);
  t.advance(120e3);
  const r = await t.run();
  assert.deepEqual(r.weekly, { sent: 0, removed: 1, failed: 0, queued: 0 });
  assert.deepEqual(t.pushes.map((p) => p.to), ['cat']);   // tried, and 410 deleted it
  assert.equal(await t.kv.get(await subKey('https://fcm.googleapis.com/fcm/send/cat')), null);
});

test('a record with too many spots for its metadata is read to see whether it asked', async () => {
  const many = Array.from({ length: 100 }, (_, i) => `a-long-spot-identifier-${i}`);
  const spots = { ...SPOTS, [many[7]]: { ...SPOTS.a, name: 'Far' } };
  const t = await setup({ users: { ann: { spots: many, weekly: true } }, spots });
  assert.equal((await t.run()).weekly.queued, 1);
  t.advance(120e3);
  await t.run();
  assert.equal(t.pushes[0].payload.body, 'Far: Saturday, low risk.');
});

test('one line a spot, the lowest level and earliest day first, at most five', () => {
  const spots = {
    p: { name: 'P', best: best('2026-10-09', 'high', 'tomorrow, high risk') },
    q: { name: 'Q', best: best('2026-10-11', 'low', 'Sunday, low risk') },
    r: { name: 'R', best: best('2026-10-09', 'low', 'low risk every day from tomorrow to Monday') },
    s: { name: 'S', best: best('2026-10-09', 'high', 'at least high risk every day') },
    u: { name: 'U', best: best('2026-10-10', 'moderate', 'Saturday, moderate risk') },
    v: { name: 'V', best: best('2026-10-12', 'very high', 'Monday, very high risk') },
    w: { name: 'W', best: best('2026-10-10', 'low', 'Saturday, low risk') },
  };
  const { body, url } = weeklyPayload(Object.keys(spots), spots, SITE);
  assert.equal(body, ['R: low risk every day from tomorrow to Monday.', 'W: Saturday, low risk.', 'Q: Sunday, low risk.',
    'U: Saturday, moderate risk.', 'P: tomorrow, high risk.', 'And 2 more on your Saved page.'].join('\n'));
  assert.equal(url, `${SITE}saved/`);
  assert.ok(new TextEncoder().encode(JSON.stringify(weeklyPayload(Object.keys(spots), spots, SITE))).length < 1000);
});
