import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { handle, flush, parseEvent, resetForTests, WRITE_CAP, MAX_SPOTS, EVENTS } from '../src/index.js';

class FakeKV {
  constructor() { this.map = new Map(); this.writes = 0; this.fail = 0; }
  async get(k) { return this.map.has(k) ? this.map.get(k) : null; }
  async put(k, v) {
    if (this.fail > 0) { this.fail--; throw new Error('429 too many writes to one key'); }
    assert.equal(typeof v, 'string'); this.writes++; this.map.set(k, v);
  }
  json(k) { return JSON.parse(this.map.get(k)); }
}

const ORIGIN = 'https://swimsignal.co.uk';
const NOW = Date.parse('2026-11-10T12:00:00Z');
let env, ctx, waits;
beforeEach(() => {
  resetForTests();
  env = { COUNTS: new FakeKV(), ALLOWED_ORIGIN: ORIGIN, READ_TOKEN: 'a'.repeat(40) };
  waits = []; ctx = { waitUntil: (p) => waits.push(p) };
});

// The flush waits on a promise the test releases, so several posts can land in one batch.
function gate() { let open; const p = new Promise((r) => { open = r; }); return { wait: () => p, open }; }
const post = (body, { origin = ORIGIN, now = NOW, wait = () => Promise.resolve(), headers = {} } = {}) =>
  handle(new Request('https://w.example/', { method: 'POST', body: typeof body === 'string' ? body : JSON.stringify(body),
    headers: { 'Content-Type': 'text/plain;charset=UTF-8', ...(origin ? { Origin: origin } : {}), ...headers } }), env, ctx, { now, wait });
const get = (q = '', token = env.READ_TOKEN) => handle(new Request('https://w.example/' + q,
  { headers: token ? { Authorization: `Bearer ${token}` } : {} }), env, ctx, { now: NOW });
const settle = () => Promise.all(waits);

const NEW = ['dayalert', 'lowalert', 'logswim', 'feed', 'search', 'mapday'];   // the redesign's, 11 Nov 2026

test('parseEvent takes the eleven actions and a spot id only where one belongs', () => {
  assert.deepEqual(parseEvent('{"event":"spot","spot_id":"ilkley-lido"}'), { event: 'spot', spot: 'ilkley-lido' });
  assert.deepEqual(parseEvent('{"event":"plan","spot_id":"ilkley-lido"}'), { event: 'plan', spot: null });
  assert.deepEqual(parseEvent('{"event":"day","spot_id":"../x"}'), { event: 'day', spot: null });
  assert.equal(parseEvent('{"event":"changed"}'), null);   // no such control on the site (README)
  assert.equal(parseEvent('{"event":"spot","x":"' + 'y'.repeat(400) + '"}'), null);
  assert.equal(parseEvent('not json'), null);
  assert.deepEqual(EVENTS, ['spot', 'day', 'save', 'plan', 'alerts', ...NEW]);
});

test("the redesign's six are taken, and never with a spot, whatever the page sends", () => {
  for (const e of NEW) {
    assert.deepEqual(parseEvent(JSON.stringify({ event: e })), { event: e, spot: null }, e);
    assert.deepEqual(parseEvent(JSON.stringify({ event: e, spot_id: 'ilkley-lido' })), { event: e, spot: null }, e);
  }
});

test("the redesign's six are counted as day totals, in one write, with no per-spot record", async () => {
  const g = gate();
  for (const e of NEW) assert.equal((await post({ event: e, spot_id: 'a' }, { wait: g.wait })).status, 204, e);
  await post({ event: 'feed' }, { wait: g.wait });
  g.open(); await settle();
  assert.equal(env.COUNTS.writes, 1);
  assert.deepEqual(env.COUNTS.json('d/2026-11-10'), { counts: { dayalert: 1, lowalert: 1, logswim: 1, feed: 2, search: 1, mapday: 1 }, spots: {}, writes: 1 });
  const day = (await (await get('?from=2026-11-10&to=2026-11-10')).json()).days[0];
  assert.deepEqual(day.counts, { spot: 0, day: 0, save: 0, plan: 0, alerts: 0, dayalert: 1, lowalert: 1, logswim: 1, feed: 2, search: 1, mapday: 1 });
});

test('a day written before the six existed reads back with zeros for them', async () => {
  env.COUNTS.map.set('d/2026-11-10', JSON.stringify({ counts: { spot: 4, plan: 1 }, spots: {}, writes: 2 }));
  const day = (await (await get('?from=2026-11-10&to=2026-11-10')).json()).days[0];
  assert.deepEqual(day.counts, { spot: 4, day: 0, save: 0, plan: 1, alerts: 0, dayalert: 0, lowalert: 0, logswim: 0, feed: 0, search: 0, mapday: 0 });
});

test('a post is counted under its UTC day, with nothing about who sent it', async () => {
  const r = await post({ event: 'spot', spot_id: 'ilkley-lido' }, { headers: { 'User-Agent': 'Secret/1.0', 'CF-Connecting-IP': '203.0.113.9' } });
  assert.equal(r.status, 204);
  assert.equal(r.headers.get('Access-Control-Allow-Origin'), ORIGIN);
  await settle();
  const rec = env.COUNTS.json('d/2026-11-10');
  assert.deepEqual(rec, { counts: { spot: 1 }, spots: { 'ilkley-lido': { spot: 1 } }, writes: 1 });
  const stored = [...env.COUNTS.map.entries()].join();
  assert.ok(!stored.includes('203.0.113.9') && !stored.includes('Secret'));
});

test('posts gathered in one isolate are written once', async () => {
  const g = gate();
  for (const e of ['spot', 'day', 'save', 'plan', 'alerts']) await post({ event: e, spot_id: 'a' }, { wait: g.wait });
  assert.equal(waits.length, 1);   // one flush scheduled for all five
  g.open(); await settle();
  assert.equal(env.COUNTS.writes, 1);
  assert.deepEqual(env.COUNTS.json('d/2026-11-10').counts, { spot: 1, day: 1, save: 1, plan: 1, alerts: 1 });
  assert.deepEqual(env.COUNTS.json('d/2026-11-10').spots, { a: { spot: 1, day: 1, save: 1 } });
});

test('posts across midnight UTC go to their own days', async () => {
  const g = gate();
  await post({ event: 'plan' }, { now: Date.parse('2026-11-10T23:59:59Z'), wait: g.wait });
  await post({ event: 'plan' }, { now: Date.parse('2026-11-11T00:00:01Z'), wait: g.wait });
  g.open(); await settle();
  assert.equal(env.COUNTS.json('d/2026-11-10').counts.plan, 1);
  assert.equal(env.COUNTS.json('d/2026-11-11').counts.plan, 1);
});

test('the day stops writing at the cap and says so', async () => {
  env.COUNTS.map.set('d/2026-11-10', JSON.stringify({ counts: { spot: 7 }, spots: {}, writes: WRITE_CAP - 1 }));
  await post({ event: 'spot' }); await settle();
  assert.equal(env.COUNTS.json('d/2026-11-10').writes, WRITE_CAP);
  const before = env.COUNTS.writes;
  await post({ event: 'spot' }); await settle();
  await post({ event: 'save' }); await settle();
  assert.equal(env.COUNTS.writes, before);   // nothing more written that day
  assert.equal(waits.length, 1);             // and, once this isolate knows, nothing more even gathered
  const day = (await (await get('?from=2026-11-10&to=2026-11-10')).json()).days[0];
  assert.equal(day.capped, true);
  assert.equal(day.counts.spot, 8);
});

test('a refused write is kept and goes with the next flush', async () => {
  env.COUNTS.fail = 1;
  await post({ event: 'save', spot_id: 'a' }); await settle();
  assert.equal(env.COUNTS.map.size, 0);
  await post({ event: 'save', spot_id: 'a' }); await settle();
  assert.deepEqual(env.COUNTS.json('d/2026-11-10'), { counts: { save: 2 }, spots: { a: { save: 2 } }, writes: 1 });
});

test('per-spot counts stop at MAX_SPOTS distinct spots; the totals go on', async () => {
  const spots = Object.fromEntries(Array.from({ length: MAX_SPOTS }, (_, i) => [`s${i}`, { spot: 1 }]));
  env.COUNTS.map.set('d/2026-11-10', JSON.stringify({ counts: { spot: MAX_SPOTS }, spots, writes: 1 }));
  await post({ event: 'spot', spot_id: 'new-one' }); await settle();
  const rec = env.COUNTS.json('d/2026-11-10');
  assert.equal(rec.counts.spot, MAX_SPOTS + 1);
  assert.equal(rec.spots['new-one'], undefined);
});

test('posts from elsewhere, bad bodies and other paths are refused, and nothing is written', async () => {
  assert.equal((await post({ event: 'spot' }, { origin: 'https://evil.example' })).status, 403);
  assert.equal((await post({ event: 'spot' }, { origin: null })).status, 403);
  assert.equal((await post({ event: 'nope' })).status, 400);
  assert.equal((await post('x'.repeat(400))).status, 400);
  assert.equal((await post('{}', { headers: { 'Content-Length': '5000' } })).status, 413);
  assert.equal((await handle(new Request('https://w.example/other', { method: 'POST', body: '{}', headers: { Origin: ORIGIN } }), env, ctx)).status, 404);
  assert.equal((await handle(new Request('https://w.example/', { method: 'PUT', body: '{}' }), env, ctx)).status, 405);
  await settle();
  assert.equal(env.COUNTS.writes, 0);
});

test('GET needs the token; without a token set it is closed', async () => {
  assert.equal((await get('', null)).status, 404);
  assert.equal((await get('', 'b'.repeat(40))).status, 404);
  delete env.READ_TOKEN;
  assert.equal((await get('', 'a'.repeat(40))).status, 404);
});

test('GET returns every day in the range, zeros where nothing was counted', async () => {
  await post({ event: 'day', spot_id: 'x' }); await settle();
  const r = await get();
  assert.equal(r.status, 200);
  assert.equal(r.headers.get('Cache-Control'), 'no-store');
  const j = await r.json();
  assert.deepEqual(j.days.map((d) => d.date), ['2026-11-04', '2026-11-05', '2026-11-06', '2026-11-07', '2026-11-08', '2026-11-09', '2026-11-10']);
  const zeros = Object.fromEntries(EVENTS.map((e) => [e, 0]));
  assert.deepEqual(j.days[0], { date: '2026-11-04', counts: zeros, spots: {}, writes: 0, capped: false });
  assert.deepEqual(j.days[6].counts, { ...zeros, day: 1 });
  assert.deepEqual(j.events, EVENTS);
  assert.equal(j.write_cap, WRITE_CAP);
  assert.equal((await get('?from=2026-11-10&to=2026-11-01')).status, 400);
  assert.equal((await get('?from=2026-01-01&to=2026-12-31')).status, 400);
  assert.equal((await get('?from=bad')).status, 400);
});

test('flush with nothing gathered writes nothing', async () => {
  await flush(env);
  assert.equal(env.COUNTS.writes, 0);
});
