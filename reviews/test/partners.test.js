import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import worker, { forgetOldPartnerFiles, parseCsv, partnerShape, sha256 } from '../src/index.js';
import { LIMITS, MAX_PARTNER_ROWS, MAX_PENDING_PARTNER, PARTNER_KEEP_DAYS, SAMPLE_COLUMNS, SAMPLE_COLUMNS_V1 } from '../src/rules.js';
import { FakeD1, FakeKV } from './helpers.js';

// Partners' files of water-sample results: off until switched on, the shape of the contract or refused, held for the
// operator and never published, withdrawn by the sender's key, and deleted with the contact details after their time.

const ORIGIN = 'https://swimsignal.co.uk';
const BASE = 'https://swimsignal-reviews.example.workers.dev';
const ADMIN = 'an-admin-token-long-enough-to-guess-never';
const makeEnv = (on = true) => ({ DB: new FakeD1(), PHOTOS: new FakeKV(), ALLOWED_ORIGIN: ORIGIN, SITE_URL: 'https://swimsignal.co.uk/', ADMIN_TOKEN: ADMIN,
  ...(on ? { PARTNER_SAMPLES: 'on' } : {}) });

// A row in the samples/ format, version 2 (samples/README.md, docs/PARTNER-SAMPLES-CONTRACT-v1.md).
const ROW = { spot_id: 'bw-uke4100-08901', sampled_at: '2027-06-03 08:30', timezone: 'Europe/London', ecoli_per_100ml: '<10',
  enterococci_per_100ml: '35', lab: 'Example Lab', ukas_accredited: 'yes', method: 'Colilert-18, Quanti-Tray/2000', lab_ref: '', supplier: 'Example Swim Club',
  received: '2027-06-06', publish: 'true', evaluate: 'true', time_known: '', site_name: 'Example Lake, "north" shore', site_lat: '54.4', site_lon: '-2.95',
  site_confirmed: 'yes', ecoli_basis: 'mpn', enterococci_basis: 'mpn', ecoli_lower_limit: '10', ecoli_upper_limit: '2419.6', enterococci_lower_limit: '10',
  enterococci_upper_limit: '2419.6', limits_written: 'qualifier', sampler: 'club coach', licence: 'CC-BY-4.0', attribution: 'Example Club',
  publish_agreed: '2027-05-01', evaluate_use: 'holdout', evaluate_agreed: '2027-05-01' };
const cell = (v) => (/[",\n\r]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
const csvOf = (rows, cols = SAMPLE_COLUMNS) => [cols.join(','), ...rows.map((r) => cols.map((c) => cell(r[c] ?? '')).join(','))].join('\r\n') + '\r\n';
// A file in the shape of the Waterhead one (data/research/partners/aafaf-waterhead.samples.csv): 59 samples, no times.
const WATERHEAD = csvOf(Array.from({ length: 59 }, (_, i) => ({ ...ROW, supplier: 'Ambleside Action for a Future', time_known: 'no',
  sampled_at: new Date(Date.UTC(2025, 3, 16) + i * 7 * 86400_000).toISOString().slice(0, 10) })));
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

test('the Worker reads the samples/ format\'s columns from the same template add_samples.py does', () => {
  const template = readFileSync(new URL('../../docs/samples-template-v2.csv', import.meta.url), 'utf8').trim().split(',');
  assert.deepEqual(SAMPLE_COLUMNS, template);
  assert.deepEqual(SAMPLE_COLUMNS.slice(0, 13), SAMPLE_COLUMNS_V1);
});

test('CSV as spreadsheets write it: quotes, commas and line breaks in a cell, CRLF, a byte-order mark', () => {
  assert.deepEqual(parseCsv('﻿a,b\r\n"x, ""y""","1\n2"\r\n\r\n3,\n'), [['a', 'b'], ['x, "y"', '1\n2'], ['3', '']]);
  assert.throws(() => parseCsv('a,b\n"open,1\n'), /never closed/);
  const shape = partnerShape(WATERHEAD);
  assert.deepEqual(shape, { supplier: 'Ambleside Action for a Future', rows: 59, first: '2025-04-16', last: '2026-05-27' });
  // A version 1 file, and a UK-style date.
  assert.deepEqual(partnerShape(csvOf([{ ...ROW, sampled_at: '03/06/2027 08:30' }], SAMPLE_COLUMNS_V1)),
    { supplier: 'Example Swim Club', rows: 1, first: '2027-06-03', last: '2027-06-03' });
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
  assert.equal(rows, 59);
  const [r] = env.DB.rows('SELECT * FROM partner_submissions');
  assert.equal(r.id, id);
  assert.equal(r.status, 'pending');
  assert.equal(r.csv, WATERHEAD, 'kept as sent');
  assert.equal(r.sha256, await sha256(WATERHEAD));
  assert.equal(r.token_hash, await sha256(token));
  assert.deepEqual([r.organisation, r.contact_name, r.email, r.supplier, r.first_day, r.last_day, r.filename],
    ['Example Swim Club', 'A. Organiser', 'results@example.org', 'Ambleside Action for a Future', '2025-04-16', '2026-05-27', 'waterhead.csv']);
  for (const table of ['partner_submissions', 'hits']) assert.ok(!JSON.stringify(env.DB.rows(`SELECT * FROM ${table}`)).includes('203.0.113.7'), table);
});

test('never published: /published says nothing of it, and the file answers only to the token', async () => {
  const env = makeEnv();
  const { id } = await (await send(env)).json();
  const text = await (await get(env, '/published')).text();
  for (const word of ['partner', 'Example Lake', 'Example Swim Club', 'results@example.org']) assert.ok(!text.includes(word), word);
  assert.equal((await get(env, `/admin/partners/${id}.csv`)).status, 401);
  assert.equal((await get(env, `/admin/partners/${id}.csv`, 'wrong')).status, 401);
  const file = await get(env, `/admin/partners/${id}.csv`, ADMIN);
  assert.equal(file.status, 200);
  assert.equal(file.headers.get('Cache-Control'), 'private, no-store');
  assert.match(file.headers.get('Content-Disposition'), new RegExp(`^attachment; filename="example-swim-club-\\d{4}-\\d{2}-\\d{2}-${id}\\.csv"$`));
  assert.equal(await file.text(), csvOf([ROW]));
  // Accepting it publishes nothing either.
  assert.equal((await post(env, '/admin/partners/decide', { id, action: 'accept' }, { admin: true })).status, 204);
  assert.ok(!(await (await get(env, '/published')).text()).includes('Example Lake'));
});

test('a file that is not the contract\'s shape is refused, saying why', async () => {
  const env = makeEnv();
  const cases = [
    [{ csv: csvOf([ROW], SAMPLE_COLUMNS.slice(0, -1)) }, /missing evaluate_agreed/],
    [{ csv: csvOf([ROW], [...SAMPLE_COLUMNS, 'colour']) }, /not in the template: colour/],
    [{ csv: csvOf([]) }, /at least one sample/],
    [{ csv: csvOf([ROW, { ...ROW, supplier: 'Another Club' }]) }, /one supplier per file/],
    [{ csv: csvOf([{ ...ROW, supplier: '' }]) }, /needs the supplier/],
    [{ csv: csvOf([ROW]) + 'a,b\r\n' }, /row 3 has 2 cells, not 31/],
    [{ csv: csvOf(Array.from({ length: MAX_PARTNER_ROWS + 1 }, (_, i) => ({ supplier: 'x', spot_id: `S${i}` }))) }, /at most 2000 samples/],
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
  const at = env.DB.db.prepare(`INSERT INTO partner_submissions (id, organisation, contact_name, email, message, filename, csv, sha256, supplier, rows,
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
  const at = env.DB.db.prepare(`INSERT INTO partner_submissions (id, organisation, contact_name, email, message, filename, csv, sha256, supplier, rows,
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
