import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker, { addDays, forgetOldIllness, illnessCounts, londonDay, sha256 } from '../src/index.js';
import { ILLNESS_KEEP_DAYS, ILLNESS_MIN, ILLNESS_SPOT_DAY, LIMITS } from '../src/rules.js';
import { FakeD1, FakeKV } from './helpers.js';

// Reports of illness after a swim: health information, so off until switched on, as little stored as
// will test a forecast, and only counts of five or more ever published.

const ORIGIN = 'https://swimsignal.co.uk';
const BASE = 'https://swimsignal-reviews.example.workers.dev';
const ADMIN = 'an-admin-token-long-enough-to-guess-never';
const makeEnv = (on = true) => ({ DB: new FakeD1(), PHOTOS: new FakeKV(), ALLOWED_ORIGIN: ORIGIN, SITE_URL: 'https://swimsignal.co.uk/', ADMIN_TOKEN: ADMIN,
  ...(on ? { ILLNESS_REPORTS: 'on' } : {}) });
const today = londonDay();
const REPORT = { spot: 'wharfe-burnsall', swam_on: addDays(today, -2), symptoms: ['gut'], onset: 1, doctor: false, consent: true };

const post = (env, path, data, { admin = false, ip = '203.0.113.7' } = {}) => worker.fetch(new Request(BASE + path, {
  method: 'POST', body: JSON.stringify(data),
  headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': ip, ...(admin ? { Authorization: 'Bearer ' + ADMIN } : { Origin: ORIGIN }) },
}), env);
const get = (env, path, auth) => worker.fetch(new Request(BASE + path, { headers: auth ? { Authorization: 'Bearer ' + auth } : {} }), env);
const published = async (env) => (await (await get(env, '/published')).json());
// Reports as if they had arrived on earlier days: n of them for a spot, received `ago` days before today.
function seed(env, spot, ago, n, extra = {}) {
  const day = addDays(today, -ago), at = env.DB.db.prepare(`INSERT INTO illness (id, spot, swam_on, symptoms, onset, doctor, received_on, token_hash)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'x')`);
  for (let i = 0; i < n; i++) {
    at.run(Math.random().toString(16).slice(2).padEnd(20, '0').slice(0, 20), spot, addDays(day, -1), extra.symptoms || '["gut"]', extra.onset ?? 1, extra.doctor ?? null, day);
  }
}

test('off unless switched on: no form to send to, and nothing in /published', async () => {
  const env = makeEnv(false);
  assert.equal((await post(env, '/illness', REPORT)).status, 404);
  assert.equal(env.DB.rows('SELECT * FROM illness').length, 0);
  assert.equal('illness' in (await published(env)), false);
  // Off with reports still held: the build keeps the privacy section until the last one is deleted.
  seed(env, 'wharfe-burnsall', 3, 1);
  assert.deepEqual((await published(env)).illness, { on: false });
});

test('a report keeps the spot, the day, the ticks, the onset and the doctor answer, and nothing else', async () => {
  const env = makeEnv();
  const res = await post(env, '/illness', { ...REPORT, symptoms: ['skin', 'gut', 'gut'], doctor: true });
  assert.equal(res.status, 201);
  assert.equal(res.headers.get('Access-Control-Allow-Origin'), ORIGIN);
  const { id, token } = await res.json();
  const [row] = env.DB.rows('SELECT * FROM illness');
  assert.deepEqual(Object.keys(row).sort(), ['doctor', 'id', 'onset', 'received_on', 'spot', 'swam_on', 'symptoms', 'token_hash']);
  assert.equal(row.id, id);
  assert.equal(row.symptoms, '["gut","skin"]', 'one order, each once');
  assert.equal(row.doctor, 1);
  assert.equal(row.received_on, today, 'the day it arrived, not the time');
  assert.equal(row.token_hash, await sha256(token));
  for (const table of ['illness', 'hits']) assert.ok(!JSON.stringify(env.DB.rows(`SELECT * FROM ${table}`)).includes('203.0.113.7'), table);
  // The doctor question may be left out.
  await post(env, '/illness', { ...REPORT, doctor: undefined }, { ip: '198.51.100.2' });
  assert.equal(env.DB.rows('SELECT doctor FROM illness WHERE id != ?', id)[0].doctor, null);
});

test('a report that is not one is refused', async () => {
  const env = makeEnv();
  for (const bad of [{ ...REPORT, consent: undefined }, { ...REPORT, consent: 'yes' }, { ...REPORT, swam_on: addDays(today, -16) },
    { ...REPORT, swam_on: addDays(today, 1) }, { ...REPORT, swam_on: '2026-02-30' }, { ...REPORT, symptoms: [] }, { ...REPORT, symptoms: ['cough'] },
    { ...REPORT, symptoms: 'gut' }, { ...REPORT, onset: 4 }, { ...REPORT, onset: '1' }, { ...REPORT, swam_on: today, onset: 1 },
    { ...REPORT, doctor: 'yes' }, { ...REPORT, spot: '../etc' }, ['not', 'an', 'object']]) {
    assert.equal((await post(env, '/illness', bad, { ip: `198.51.100.${Math.floor(Math.random() * 250)}` })).status, 400, JSON.stringify(bad));
  }
  assert.equal((await post(env, '/illness', { ...REPORT, swam_on: addDays(today, -14), onset: 3 })).status, 201, 'two weeks back is fine');
  assert.equal((await post(env, '/illness', { ...REPORT, swam_on: today, onset: 0 }, { ip: '198.51.100.251' })).status, 201, 'ill the same day');
  assert.equal(env.DB.rows('SELECT * FROM illness').length, 2);
  // Only from the site's own pages.
  const elsewhere = await worker.fetch(new Request(BASE + '/illness', { method: 'POST', body: JSON.stringify(REPORT),
    headers: { 'Content-Type': 'application/json', Origin: 'https://example.com' } }), env);
  assert.equal(elsewhere.status, 403);
});

test('a script filling the hidden field is told it worked, and nothing is kept', async () => {
  const env = makeEnv();
  const res = await post(env, '/illness', { ...REPORT, website: 'http://spam.example' });
  assert.equal(res.status, 201);
  assert.match((await res.json()).id, /^[0-9a-f]{20}$/);
  assert.equal(env.DB.rows('SELECT * FROM illness').length, 0);
});

test('a connection sends a few a day, and a spot takes a capped number a day', async () => {
  const env = makeEnv();
  for (let i = 0; i < LIMITS.illness; i++) assert.equal((await post(env, '/illness', REPORT)).status, 201);
  assert.equal((await post(env, '/illness', REPORT)).status, 429);
  assert.equal((await post(env, '/illness', REPORT, { ip: '198.51.100.1' })).status, 201, 'another connection is counted apart');
  seed(env, 'river-x', 0, ILLNESS_SPOT_DAY);
  assert.equal((await post(env, '/illness', { ...REPORT, spot: 'river-x' }, { ip: '198.51.100.3' })).status, 503);
  assert.equal((await post(env, '/illness', REPORT, { ip: '198.51.100.3' })).status, 201, 'other spots still take reports');
});

test('only counts of five or more are published, counted from the day after a report arrives', async () => {
  const env = makeEnv();
  seed(env, 'busy-spot', 3, 4); seed(env, 'busy-spot', 40, 3);    // 4 in 30 days, 7 in 365
  seed(env, 'cluster', 1, ILLNESS_MIN);                           // 5 yesterday
  seed(env, 'quiet-spot', 5, ILLNESS_MIN - 1);                    // 4: never shown
  seed(env, 'old-spot', 370, 9);                                  // past the year
  seed(env, 'today-spot', 0, 9);                                  // today: from tomorrow
  const { illness } = await published(env);
  assert.deepEqual(illness, { on: true, min: ILLNESS_MIN, through: addDays(today, -1),
    spots: { 'busy-spot': { d30: null, d365: 7 }, cluster: { d30: 5, d365: 5 } } });
  // Tomorrow, today's count shows; the day the year ends for a report, it leaves.
  const tomorrow = await illnessCounts(env, Date.now() + 86400_000);
  assert.deepEqual(tomorrow.spots['today-spot'], { d30: 9, d365: 9 });
  // Nothing about one report reaches /published: no day of a swim, no symptom.
  const text = JSON.stringify(await published(env));
  for (const word of ['swam_on', 'symptoms', 'gut', 'onset', 'doctor']) assert.ok(!text.includes(word), word);
});

test('the sender can delete their report with the key their browser keeps, switched on or off', async () => {
  const env = makeEnv();
  const { id, token } = await (await post(env, '/illness', REPORT)).json();
  assert.equal((await post(env, '/illness/delete', { id, token: 'wrong' })).status, 403);
  env.ILLNESS_REPORTS = 'off';
  assert.equal((await post(env, '/illness/delete', { id, token })).status, 204);
  assert.equal(env.DB.rows('SELECT * FROM illness').length, 0);
  assert.equal((await post(env, '/illness/delete', { id, token })).status, 204, 'already gone is done');
});

test('the operator sees batches, deletes one whole, and downloads the reports per spot and day of swimming', async () => {
  const env = makeEnv();
  seed(env, 'wharfe-burnsall', 2, 6, { symptoms: '["gut","skin"]', doctor: 1 });
  seed(env, 'wharfe-burnsall', 0, 2);
  seed(env, 'river-x', 2, 1, { onset: 3 });
  assert.equal((await get(env, '/admin/queue')).status, 401);
  const q = (await (await get(env, '/admin/queue', ADMIN)).json()).illness;
  assert.equal(q.on, true);
  assert.equal(q.held, 9);
  assert.equal(q.arrived_today, 2);
  assert.equal(q.day, today);
  assert.deepEqual(q.shown, { 'wharfe-burnsall': { d30: 6, d365: 6 } });
  const batch = q.batches.find((b) => b.spot === 'wharfe-burnsall' && b.received_on === addDays(today, -2));
  assert.equal(batch.n, 6); assert.equal(batch.kinds, 1, 'six alike'); assert.equal(batch.gut, 6); assert.equal(batch.skin, 6); assert.equal(batch.ear, 0);
  assert.equal(q.batches[0].received_on, today, 'newest first');

  const csv = await get(env, '/admin/illness.csv', ADMIN);
  assert.equal(csv.status, 200);
  assert.match(csv.headers.get('Content-Type'), /^text\/csv/);
  assert.equal(csv.headers.get('Cache-Control'), 'private, no-store');
  const lines = (await csv.text()).trim().split('\n');
  assert.match(lines[0], /^# .*Private/);
  assert.equal(lines[1], 'spot,swam_on,reports,gut,ear,eye,skin,other,onset_0,onset_1,onset_2,onset_3_or_more,doctor_yes,doctor_no');
  assert.ok(lines.includes(`wharfe-burnsall,${addDays(today, -3)},6,6,0,0,6,0,0,6,0,0,6,0`), lines.join('\n'));
  assert.ok(lines.includes(`river-x,${addDays(today, -3)},1,1,0,0,0,0,0,0,0,1,0,0`));
  assert.equal((await get(env, '/admin/illness.csv')).status, 401);

  assert.equal((await post(env, '/admin/illness/delete', { spot: 'wharfe-burnsall', received_on: addDays(today, -2) })).status, 401, 'not without the token');
  assert.equal((await post(env, '/admin/illness/delete', { spot: 'wharfe-burnsall', received_on: 'yesterday' }, { admin: true })).status, 400);
  const del = await post(env, '/admin/illness/delete', { spot: 'wharfe-burnsall', received_on: addDays(today, -2) }, { admin: true });
  assert.deepEqual(await del.json(), { deleted: 6 });
  assert.equal(env.DB.rows('SELECT * FROM illness').length, 3);
  assert.deepEqual((await published(env)).illness.spots, {});
});

test('reports leave after their time, and the daily job runs them out', async () => {
  const env = makeEnv();
  seed(env, 'wharfe-burnsall', ILLNESS_KEEP_DAYS + 1, 2);
  seed(env, 'wharfe-burnsall', ILLNESS_KEEP_DAYS, 1);
  await forgetOldIllness(env);
  assert.equal(env.DB.rows('SELECT * FROM illness').length, 1);
  await worker.scheduled({}, env);
  assert.equal(env.DB.rows('SELECT * FROM illness').length, 1);
});

test('before the migration is applied, reviews, notes and moderation carry on', async () => {
  const env = makeEnv();
  env.DB.db.exec('DROP TABLE illness');
  const p = await get(env, '/published');
  assert.equal(p.status, 200);
  assert.equal('illness' in (await p.json()), false);
  const q = await get(env, '/admin/queue', ADMIN);
  assert.equal(q.status, 200);
  assert.equal((await q.json()).illness, null);
  await worker.scheduled({}, env);   // the daily job does not stop on it
  assert.equal((await get(env, '/admin/illness.csv', ADMIN)).status, 503);
  assert.equal((await post(env, '/illness', REPORT)).status, 500, 'the page is told the service had a problem');
});
