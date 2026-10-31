import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import worker, { forgetOldPartnerFiles, parseCsv, partnerShape, sha256 } from '../src/index.js';
import { LIMITS, MAX_PARTNER_ROWS, MAX_PENDING_PARTNER, PARTNER_COLUMNS, PARTNER_KEEP_DAYS } from '../src/rules.js';
import { FakeD1, FakeKV } from './helpers.js';

// Partners' files of water-sample results: off until switched on, the shape of the contract or refused, held for the
// operator and never published, withdrawn by the sender's key, and deleted with the contact details after their time.

const ORIGIN = 'https://swimsignal.co.uk';
const BASE = 'https://swimsignal-reviews.example.workers.dev';
const ADMIN = 'an-admin-token-long-enough-to-guess-never';
const makeEnv = (on = true) => ({ DB: new FakeD1(), PHOTOS: new FakeKV(), ALLOWED_ORIGIN: ORIGIN, SITE_URL: 'https://swimsignal.co.uk/', ADMIN_TOKEN: ADMIN,
  ...(on ? { PARTNER_SAMPLES: 'on' } : {}) });

const ROW = { partner_id: 'example-club', sample_id: 'EC-1', site_name: 'Example Lake, "north" shore', site_lat: '54.4', site_lon: '-2.95',
  site_confirmed: 'yes', sampled_on: '2027-06-03', sampled_time: '08:30', timezone: 'Europe/London', determinand: 'ecoli', result: '10',
  qualifier: '<', unit: 'mpn/100ml', method_type: 'mpn', method: 'Colilert-18, Quanti-Tray/2000', lower_limit: '10', upper_limit: '2419.6',
  limits_written: 'qualifier', lab: 'Example Lab', lab_accredited: 'yes', sampler: 'club coach', licence: 'CC-BY-4.0', attribution: 'Example Club',
  publish_consent: 'yes', publish_consent_on: '2027-05-01', test_use: 'holdout', test_consent_on: '2027-05-01', consent_ref: 'email', received_on: '2027-06-06',
  notes: 'two lines\nin one cell' };
const cell = (v) => (/[",\n\r]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
const csvOf = (rows, cols = PARTNER_COLUMNS) => [cols.join(','), ...rows.map((r) => cols.map((c) => cell(r[c] ?? '')).join(','))].join('\r\n') + '\r\n';
// A season's file in the shape of the Waterhead one (data/research/partners/): 59 samples, two results each.
const WATERHEAD = csvOf(Array.from({ length: 59 }, (_, i) => ['ecoli', 'intestinal_enterococci'].map((det) => ({ ...ROW, partner_id: 'aafaf',
  sample_id: `wet-${i}`, sampled_on: new Date(Date.UTC(2025, 3, 16) + i * 7 * 86400_000).toISOString().slice(0, 10), determinand: det }))).flat());
const FIELDS = { organisation: 'Example Swim Club', contact_name: 'A. Organiser', email: 'results@example.org', message: 'Our June samples.', rights: 'yes' };

async function send(env, { fields = FIELDS, csv = csvOf([ROW]), name = 'june.csv', ip = '203.0.113.7', origin = ORIGIN } = {}) {
  const f = new FormData();
  for (const [k, v] of Object.entries(fields)) f.append(k, v);
  if (csv !== null) f.append('file', new Blob([csv], { type: 'text/csv' }), name);
  const r = new Response(f), body = await r.arrayBuffer();
  return worker.fetch(new Request(BASE + '/partners/samples', { method: 'POST', body,
    headers: { 'Content-Type': r.headers.get('Content-Type'), 'Content-Length': String(body.byteLength), 'CF-Connecting-IP': ip, ...(origin ? { Origin: origin } : {}) } }), env);
}
const post = (env, path, data, { admin = false, ip = '203.0.113.7' } = {}) => worker.fetch(new Request(BASE + path, {
  method: 'POST', body: JSON.stringify(data),
  headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': ip, ...(admin ? { Authorization: 'Bearer ' + ADMIN } : { Origin: ORIGIN }) },
}), env);
const get = (env, path, auth) => worker.fetch(new Request(BASE + path, { headers: auth ? { Authorization: 'Bearer ' + auth } : {} }), env);
const queue = async (env) => (await (await get(env, '/admin/queue', ADMIN)).json()).partners;

test('the Worker reads the contract\'s columns from the same template the checker does', () => {
  const template = readFileSync(new URL('../../docs/partner-samples-template-v1.csv', import.meta.url), 'utf8').trim().split(',');
  assert.deepEqual(PARTNER_COLUMNS, template);
});

test('CSV as spreadsheets write it: quotes, commas and line breaks in a cell, CRLF, a byte-order mark', () => {
  assert.deepEqual(parseCsv('﻿a,b\r\n"x, ""y""","1\n2"\r\n\r\n3,\n'), [['a', 'b'], ['x, "y"', '1\n2'], ['3', '']]);
  assert.throws(() => parseCsv('a,b\n"open,1\n'), /never closed/);
  const shape = partnerShape(WATERHEAD);
  assert.deepEqual(shape, { partner: 'aafaf', rows: 118, first: '2025-04-16', last: '2026-05-27' });
});

test('off unless switched on, and only from the site', async () => {
  const off = makeEnv(false);
  assert.equal((await send(off)).status, 404);
  const env = makeEnv();
  assert.equal((await send(env, { origin: 'https://example.com' })).status, 403);
  assert.equal(env.DB.rows('SELECT * FROM partner_submissions').length, 0);
});

test('a file is held whole, waiting, with who sent it and what it holds', async () => {
  const env = makeEnv();
  const res = await send(env, { csv: WATERHEAD, name: 'waterhead.csv' });
  assert.equal(res.status, 201);
  assert.equal(res.headers.get('Access-Control-Allow-Origin'), ORIGIN);
  const { id, token, rows } = await res.json();
  assert.equal(rows, 118);
  const [r] = env.DB.rows('SELECT * FROM partner_submissions');
  assert.equal(r.id, id);
  assert.equal(r.status, 'pending');
  assert.equal(r.csv, WATERHEAD, 'kept as sent');
  assert.equal(r.sha256, await sha256(WATERHEAD));
  assert.equal(r.token_hash, await sha256(token));
  assert.deepEqual([r.organisation, r.contact_name, r.email, r.partner_id, r.first_day, r.last_day, r.filename],
    ['Example Swim Club', 'A. Organiser', 'results@example.org', 'aafaf', '2025-04-16', '2026-05-27', 'waterhead.csv']);
  for (const table of ['partner_submissions', 'hits']) assert.ok(!JSON.stringify(env.DB.rows(`SELECT * FROM ${table}`)).includes('203.0.113.7'), table);
});

test('never published: /published says nothing of it, and the file answers only to the token', async () => {
  const env = makeEnv();
  const { id } = await (await send(env)).json();
  const text = await (await get(env, '/published')).text();
  for (const word of ['partner', 'example-club', 'Example Swim Club', 'results@example.org']) assert.ok(!text.includes(word), word);
  assert.equal((await get(env, `/admin/partners/${id}.csv`)).status, 401);
  assert.equal((await get(env, `/admin/partners/${id}.csv`, 'wrong')).status, 401);
  const file = await get(env, `/admin/partners/${id}.csv`, ADMIN);
  assert.equal(file.status, 200);
  assert.equal(file.headers.get('Cache-Control'), 'private, no-store');
  assert.match(file.headers.get('Content-Disposition'), new RegExp(`^attachment; filename="example-club-\\d{4}-\\d{2}-\\d{2}-${id}\\.csv"$`));
  assert.equal(await file.text(), csvOf([ROW]));
  // Accepting it publishes nothing either.
  assert.equal((await post(env, '/admin/partners/decide', { id, action: 'accept' }, { admin: true })).status, 204);
  assert.ok(!(await (await get(env, '/published')).text()).includes('example-club'));
});

test('a file that is not the contract\'s shape is refused, saying why', async () => {
  const env = makeEnv();
  const cases = [
    [{ csv: csvOf([ROW], PARTNER_COLUMNS.slice(0, -1)) }, /missing notes/],
    [{ csv: csvOf([ROW], [...PARTNER_COLUMNS, 'colour']) }, /not in the template: colour/],
    [{ csv: csvOf([]) }, /at least one result/],
    [{ csv: csvOf([ROW, { ...ROW, partner_id: 'another', sample_id: 'X' }]) }, /one partner per file/],
    [{ csv: csvOf([{ ...ROW, partner_id: 'Example Club' }]) }, /lower case/],
    [{ csv: csvOf([ROW]) + 'a,b\r\n' }, /row 3 has 2 cells, not 30/],
    [{ csv: csvOf(Array.from({ length: MAX_PARTNER_ROWS + 1 }, (_, i) => ({ partner_id: 'x', sample_id: `S${i}` }))) }, /at most 2000 results/],
    [{ csv: 'PK\u0003\u0004 a spreadsheet' }, /not a CSV/],
    [{ csv: null }, /attach the file/],
    [{ fields: { ...FIELDS, email: 'not an address' } }, /email address/],
    [{ fields: { ...FIELDS, organisation: ' ' } }, /which group/],
    [{ fields: { ...FIELDS, rights: '' } }, /your results/],
  ];
  for (const [i, [opts, says]] of cases.entries()) {
    const res = await send(env, { ...opts, ip: `198.51.100.${i + 1}` });
    assert.equal(res.status, 400, String(says));
    assert.match(await res.text(), says);
  }
  assert.equal(env.DB.rows('SELECT * FROM partner_submissions').length, 0);
});

test('a script filling the hidden field is told it worked, and nothing is kept', async () => {
  const env = makeEnv();
  assert.equal((await send(env, { fields: { ...FIELDS, website: 'http://spam.example' } })).status, 201);
  assert.equal(env.DB.rows('SELECT * FROM partner_submissions').length, 0);
});

test('a few files a day from one connection, and a capped queue for everyone', async () => {
  const env = makeEnv();
  for (let i = 0; i < LIMITS.partner; i++) assert.equal((await send(env)).status, 201);
  assert.equal((await send(env)).status, 429);
  const at = env.DB.db.prepare(`INSERT INTO partner_submissions (id, organisation, contact_name, email, message, filename, csv, sha256, partner_id, rows,
    status, created_at, token_hash) VALUES (?, 'x', '', 'a@b.co', '', 'f.csv', '', '', 'x', 1, 'pending', ?, 'x')`);
  for (let i = LIMITS.partner; i < MAX_PENDING_PARTNER; i++) at.run(String(i).padStart(20, '0'), new Date().toISOString());
  const full = await send(env, { ip: '198.51.100.9' });
  assert.equal(full.status, 503);
  assert.match(await full.text(), /hello@swimsignal\.co\.uk/);
});

test('the sender withdraws a file with the key their browser keeps, switched on or off', async () => {
  const env = makeEnv();
  const { id, token } = await (await send(env)).json();
  assert.equal((await post(env, '/partners/samples/delete', { id, token: 'wrong' })).status, 403);
  env.PARTNER_SAMPLES = 'off';
  assert.equal((await post(env, '/partners/samples/delete', { id, token })).status, 204);
  assert.equal(env.DB.rows('SELECT * FROM partner_submissions').length, 0);
  assert.equal((await post(env, '/partners/samples/delete', { id, token })).status, 204, 'already gone is done');
});

test('the operator lists, accepts and deletes; the list never carries the file itself', async () => {
  const env = makeEnv();
  const a = (await (await send(env)).json()).id, b = (await (await send(env, { csv: WATERHEAD })).json()).id;
  assert.equal((await get(env, '/admin/queue')).status, 401);
  let q = await queue(env);
  assert.equal(q.on, true);
  assert.equal(q.keep_days, PARTNER_KEEP_DAYS);
  assert.deepEqual(q.pending.map((f) => f.id).sort(), [a, b].sort());
  assert.ok(!('csv' in q.pending[0]) && !('token_hash' in q.pending[0]));
  assert.equal((await post(env, '/admin/partners/decide', { id: a, action: 'accept' })).status, 401, 'not without the token');
  assert.equal((await post(env, '/admin/partners/decide', { id: a, action: 'publish' }, { admin: true })).status, 400, 'there is no publishing');
  assert.equal((await post(env, '/admin/partners/decide', { id: a, action: 'accept' }, { admin: true })).status, 204);
  q = await queue(env);
  assert.deepEqual([q.pending.map((f) => f.id), q.accepted.map((f) => f.id)], [[b], [a]]);
  assert.ok(q.accepted[0].decided_at);
  assert.equal((await post(env, '/admin/partners/decide', { id: b, action: 'delete' }, { admin: true })).status, 204);
  assert.equal((await post(env, '/admin/partners/decide', { id: b, action: 'delete' }, { admin: true })).status, 404);
  assert.deepEqual(env.DB.rows('SELECT id FROM partner_submissions'), [{ id: a }]);
});

test('every file goes after its time, accepted or not, with the contact details', async () => {
  const env = makeEnv();
  const at = env.DB.db.prepare(`INSERT INTO partner_submissions (id, organisation, contact_name, email, message, filename, csv, sha256, partner_id, rows,
    status, created_at, token_hash) VALUES (?, 'x', '', 'a@b.co', '', 'f.csv', '', '', 'x', 1, ?, ?, 'x')`);
  const ago = (days) => new Date(Date.now() - days * 86400_000).toISOString();
  at.run('0'.repeat(20), 'accepted', ago(PARTNER_KEEP_DAYS + 1));
  at.run('1'.repeat(20), 'pending', ago(PARTNER_KEEP_DAYS + 1));
  at.run('2'.repeat(20), 'pending', ago(PARTNER_KEEP_DAYS - 1));
  await forgetOldPartnerFiles(env);
  assert.deepEqual(env.DB.rows('SELECT id FROM partner_submissions'), [{ id: '2'.repeat(20) }]);
  await worker.scheduled({}, env);
  assert.equal(env.DB.rows('SELECT * FROM partner_submissions').length, 1);
});

test('before the migration is applied, everything else carries on', async () => {
  const env = makeEnv();
  env.DB.db.exec('DROP TABLE partner_submissions');
  assert.equal((await get(env, '/published')).status, 200);
  const q = await get(env, '/admin/queue', ADMIN);
  assert.equal(q.status, 200);
  assert.equal((await q.json()).partners, null);
  await worker.scheduled({}, env);
  assert.equal((await get(env, `/admin/partners/${'0'.repeat(20)}.csv`, ADMIN)).status, 503);
  assert.equal((await send(env)).status, 503, 'the page is told the service is not ready');
});

test('the moderation page has the partner section, and no way to publish a file', async () => {
  const page = await (await get(env0(), '/moderate')).text();
  assert.match(page, /<section id="partners" hidden>/);
  assert.match(page, /Nothing here is published, by you or by the Worker/);
  const js = await (await get(env0(), '/moderate.js')).text();
  assert.match(js, /\/admin\/partners\/decide/);
  assert.ok(!/action: 'publish'[^\n]*partners/.test(js));
});
const env0 = () => makeEnv();
