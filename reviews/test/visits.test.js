import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker, { addDays, forgetEndedVisits, londonDay, sha256, visitUntil } from '../src/index.js';
import { VISIT_KINDS } from '../src/rules.js';
import { FakeD1, FakeKV, hasBytes, jpeg } from './helpers.js';

// Quick notes on a visit: what a spot was like today or yesterday. They expire; damage and closures
// can be confirmed by another swimmer; pollution and algae stay suspected until the operator verifies.

const ORIGIN = 'https://swimsignal.co.uk';
const BASE = 'https://swimsignal-reviews.example.workers.dev';
const ADMIN = 'an-admin-token-long-enough-to-guess-never';
const makeEnv = () => ({ DB: new FakeD1(), PHOTOS: new FakeKV(), ALLOWED_ORIGIN: ORIGIN, SITE_URL: 'https://swimsignal.co.uk/', ADMIN_TOKEN: ADMIN });
const today = londonDay();
const PHOTO = { full: jpeg({ exif: true }), thumb: jpeg({ width: 320, height: 240, exif: true }) };

async function send(env, fields, { photo, ip = '203.0.113.7' } = {}) {
  const f = new FormData();
  for (const [k, v] of Object.entries(fields)) for (const x of [].concat(v)) f.append(k, x);
  if (photo) {
    f.append('photo0', new Blob([photo.full], { type: 'image/jpeg' }), 'photo0.jpg');
    f.append('thumb0', new Blob([photo.thumb], { type: 'image/jpeg' }), 'thumb0.jpg');
  }
  const r = new Response(f), body = await r.arrayBuffer();
  return worker.fetch(new Request(BASE + '/visits', { method: 'POST', body,
    headers: { 'Content-Type': r.headers.get('Content-Type'), 'Content-Length': String(body.byteLength), 'CF-Connecting-IP': ip, Origin: ORIGIN } }), env);
}
const post = (env, path, data, { admin = false, ip = '203.0.113.7' } = {}) => worker.fetch(new Request(BASE + path, {
  method: 'POST', body: JSON.stringify(data),
  headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': ip, ...(admin ? { Authorization: 'Bearer ' + ADMIN } : { Origin: ORIGIN }) },
}), env);
const get = (env, path, auth) => worker.fetch(new Request(BASE + path, { headers: auth ? { Authorization: 'Bearer ' + auth } : {} }), env);
const published = async (env) => (await (await get(env, '/published')).json()).visits;
const NOTE = { spot: 'wharfe-burnsall', seen_on: today, kind: ['busy', 'steps'] };

test('a note of ticks alone is published at once, dated, with the last day it is shown', async () => {
  const env = makeEnv();
  const res = await send(env, NOTE);
  assert.equal(res.status, 201);
  const { id, token, published: atOnce } = await res.json();
  assert.equal(atOnce, true);
  const [row] = env.DB.rows('SELECT * FROM visits');
  assert.equal(row.status, 'published');
  assert.equal(row.token_hash, await sha256(token));
  assert.equal(row.until, addDays(today, 30), 'the steps last 30 days; busy only a day');
  assert.ok(!JSON.stringify(row).includes('203.0.113.7'));
  const [v] = await published(env);
  assert.equal(v.id, id);
  assert.deepEqual(v.kinds, ['busy', 'steps']);
  assert.equal(v.created_at, undefined, 'when it was sent is not public');
  assert.equal(v.verified, '');
});

test('a note with words or a photo waits for the operator, and its photo stays private until then', async () => {
  const env = makeEnv();
  const words = await (await send(env, { ...NOTE, text: 'The bottom step has gone.' })).json();
  assert.equal(words.published, false);
  assert.equal((await send(env, { ...NOTE, kind: 'sign' }, { photo: PHOTO })).status, 400, 'a photo needs the consent box');
  const pic = await (await send(env, { ...NOTE, kind: 'sign', consent: 'yes' }, { photo: PHOTO })).json();
  assert.equal(pic.published, false);
  for (const bytes of env.PHOTOS.map.values()) assert.ok(!hasBytes(bytes, 'GPSLatitude'));
  assert.deepEqual(await published(env), []);
  assert.equal((await get(env, `/photos/${pic.id}-0-t.jpg`)).status, 404);
  assert.equal((await get(env, `/photos/${pic.id}-0-t.jpg`, ADMIN)).status, 200);
  const q = await (await get(env, '/admin/queue', ADMIN)).json();
  assert.deepEqual(q.visits.pending.map((v) => v.id).sort(), [words.id, pic.id].sort());
  assert.equal((await post(env, '/admin/decide', { id: pic.id, action: 'publish' }, { admin: true })).status, 204);
  assert.deepEqual((await published(env)).map((v) => v.id), [pic.id]);
  assert.equal((await get(env, `/photos/${pic.id}-0.jpg`)).status, 200);
  const s = await (await get(env, '/admin/summary', ADMIN)).json();
  assert.equal(s.visits_pending, 1);
  assert.equal(s.visits_published, 1);
});

test('a note that is not one is refused', async () => {
  const env = makeEnv();
  for (const bad of [{ ...NOTE, kind: [] }, { ...NOTE, kind: 'lovely' }, { ...NOTE, seen_on: addDays(today, -3) },
    { ...NOTE, seen_on: addDays(today, 1) }, { ...NOTE, text: 'see www.example.com' }, { ...NOTE, text: 'x'.repeat(281) },
    { ...NOTE, spot: '../etc' }, { ...NOTE, kind: Object.keys(VISIT_KINDS) }]) {
    assert.equal((await send(env, bad)).status, 400, JSON.stringify(bad));
  }
  assert.equal((await send(env, { ...NOTE, seen_on: addDays(today, -1) })).status, 201, 'yesterday is fine');
  assert.equal(env.DB.rows('SELECT * FROM visits').length, 1);
});

test('another swimmer can say damage is still there, once a day, which starts its days again', async () => {
  const env = makeEnv();
  const { id } = await (await send(env, { ...NOTE, seen_on: addDays(today, -1) })).json();
  env.DB.db.prepare('UPDATE visits SET seen_on = ?, until = ? WHERE id = ?').run(addDays(today, -20), addDays(today, 10), id);
  const res = await post(env, '/visits/confirm', { id }, { ip: '198.51.100.1' });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { confirmed_on: today, confirmations: 1, until: addDays(today, 30) });
  const again = await (await post(env, '/visits/confirm', { id }, { ip: '198.51.100.1' })).json();
  assert.equal(again.confirmations, 1, 'the same connection counts once a day');
  assert.equal((await (await post(env, '/visits/confirm', { id }, { ip: '198.51.100.2' })).json()).confirmations, 2);

  const good = await (await send(env, { ...NOTE, kind: ['good', 'busy'] })).json();
  assert.equal((await post(env, '/visits/confirm', { id: good.id })).status, 400, 'a good day is not confirmed: it simply ends');
  env.DB.db.prepare('UPDATE visits SET until = ? WHERE id = ?').run(addDays(today, -1), id);
  assert.equal((await post(env, '/visits/confirm', { id })).status, 404, 'an ended note cannot be revived');
});

test('a good note does not shorten a warning, and "not like this any more" goes to the operator', async () => {
  const env = makeEnv();
  const warn = await (await send(env, { ...NOTE, kind: 'steps' })).json();
  await send(env, { ...NOTE, kind: ['good', 'clear'] }, { ip: '198.51.100.9' });
  const [steps] = env.DB.rows('SELECT until FROM visits WHERE id = ?', warn.id);
  assert.equal(steps.until, addDays(today, 30));
  assert.equal((await post(env, '/visits/report', { id: warn.id, reason: 'not-now' })).status, 204);
  assert.equal((await post(env, '/visits/report', { id: warn.id, reason: 'boring' })).status, 400);
  assert.equal((await published(env)).length, 2, 'a report does not take it down');
  const q = await (await get(env, '/admin/queue', ADMIN)).json();
  assert.deepEqual(q.visits.reported.map((v) => [v.id, v.reasons]), [[warn.id, ['not-now']]]);
  assert.equal((await post(env, '/admin/decide', { id: warn.id, action: 'delete' }, { admin: true })).status, 204);
  assert.equal((await published(env)).length, 1);
});

test('only the operator verifies suspected pollution or algae, naming the source', async () => {
  const env = makeEnv();
  const algae = await (await send(env, { ...NOTE, kind: 'algae' })).json();
  const busy = await (await send(env, { ...NOTE, kind: 'busy' })).json();
  const source = 'Environment Agency advice against bathing, 3 Oct';
  assert.equal((await post(env, '/admin/decide', { id: busy.id, action: 'verify', source }, { admin: true })).status, 400);
  assert.equal((await post(env, '/admin/decide', { id: algae.id, action: 'verify', source })).status, 401, 'not without the admin token');
  assert.equal((await post(env, '/admin/decide', { id: algae.id, action: 'verify', source }, { admin: true })).status, 204);
  assert.equal((await published(env)).find((v) => v.id === algae.id).verified, source);
});

test('the sender can delete a note, and ended notes leave with their photos', async () => {
  const env = makeEnv();
  const mine = await (await send(env, NOTE)).json();
  assert.equal((await post(env, '/visits/delete', { id: mine.id, token: 'wrong' })).status, 403);
  assert.equal((await post(env, '/visits/delete', { id: mine.id, token: mine.token })).status, 204);
  assert.deepEqual(await (await post(env, '/visits/status', { ids: [mine.id] })).json(), { [mine.id]: 'gone' });

  const old = await (await send(env, { ...NOTE, kind: 'busy', consent: 'yes' }, { photo: PHOTO })).json();
  const current = await (await send(env, { ...NOTE, kind: 'busy' })).json();
  env.DB.db.prepare('UPDATE visits SET until = ? WHERE id = ?').run(addDays(today, -2), old.id);
  assert.equal(env.PHOTOS.map.size, 2);
  await forgetEndedVisits(env);
  assert.deepEqual(env.DB.rows('SELECT id FROM visits').map((r) => r.id), [current.id]);
  assert.equal(env.PHOTOS.map.size, 0);
  assert.equal(env.DB.rows('SELECT * FROM photo_storage').length, 0);
});

test('days are London days, and a note lasts as long as its longest tick', () => {
  assert.equal(londonDay(Date.parse('2026-07-01T23:30:00Z')), '2026-07-02', 'summer time');
  assert.equal(londonDay(Date.parse('2026-12-01T23:30:00Z')), '2026-12-01', 'winter');
  assert.equal(londonDay(Date.parse('2026-10-25T00:30:00Z')), '2026-10-25', 'still summer time before 01:00 UTC');
  assert.equal(londonDay(Date.parse('2026-10-25T23:30:00Z')), '2026-10-25', 'winter time from 01:00 UTC');
  assert.equal(visitUntil(['busy'], '2026-10-03'), '2026-10-04');
  assert.equal(visitUntil(['busy', 'algae'], '2026-10-03'), '2026-10-10');
  assert.equal(visitUntil(['steps'], '2026-10-03', '2026-10-20'), '2026-11-19');
  assert.equal(visitUntil(['algae'], '2026-10-03', '2026-10-20'), '2026-10-10', 'algae is not confirmed, it is seen again');
});
