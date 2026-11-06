import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker, {
  EA_MAX_BYTES, KEY_FAILURES, KEY_STOPPED, LIST_MAX_BYTES, MAX_REQUESTS, STOP_AFTER, guardedFetch, hourKey, issueHour, scheduled,
} from '../src/index.js';
import { FakeKV, LISTED, UNLISTED, hang, listingBody, makeNet } from './helpers.js';

const at = (iso) => ({ scheduledTime: Date.parse(iso), cron: '0 * * * *' });
const run = (kv, net, iso, extra = {}) =>
  scheduled(at(iso), { SHADOW: kv }, { fetch: net.fetch, now: () => Date.parse(iso) + 4000, timeoutMs: 50, ...extra });
const EA = 'environment.data.gov.uk';
const S3 = 'met-office-radar-obs-data.s3.amazonaws.com';

test('issue time is the UTC hour', () => {
  assert.equal(issueHour(Date.parse('2026-12-01T13:59:59.999Z')), '2026-12-01T13:00:00Z');
  assert.equal(issueHour(Date.parse('2026-12-01T00:00:00Z')), '2026-12-01T00:00:00Z');
});

test('a good run writes one record: only our measures, only radar keys in (issue - 3 h, issue]', async () => {
  const kv = new FakeKV();
  const net = makeNet();
  const out = await run(kv, net, '2026-12-01T13:00:02Z');
  assert.deepEqual(out, { issue: '2026-12-01T13:00:00Z', ok: true });
  assert.equal(net.calls.length, 2);
  assert.equal(net.calls[0].url, 'https://environment.data.gov.uk/flood-monitoring/data/readings?latest&parameter=level');
  assert.equal(net.calls[1].url, 'https://met-office-radar-obs-data.s3.amazonaws.com/?list-type=2&prefix=radar/2026/12/01/&max-keys=1000');
  for (const c of net.calls) {
    assert.equal(c.init.redirect, 'manual');
    assert.ok(c.init.signal instanceof AbortSignal);
  }
  const rec = kv.json(hourKey('2026-12-01T13:00:00Z'));
  assert.equal(rec.schema, 'swimsignal.river-shadow.hour');
  assert.equal(rec.version, 1);
  assert.equal(rec.issue, '2026-12-01T13:00:00Z');
  assert.equal(rec.fetched_at, '2026-12-01T13:00:06.000Z');
  assert.equal(rec.ea.status, 200);
  assert.equal(rec.ea.error, null);
  assert.equal(rec.ea.n_items_total, LISTED.length + UNLISTED.length);
  assert.deepEqual(rec.ea.items.map((i) => i.measure.split('/').pop()), LISTED);
  assert.deepEqual(Object.keys(rec.ea.items[0]), ['measure', 'dateTime', 'value']);
  assert.equal(rec.radar.status, 200);
  assert.equal(rec.radar.error, null);
  const times = rec.radar.keys.map((k) => k.key.slice(17, 29));
  assert.equal(times.length, 12);
  assert.equal(times[0], '202612011015');
  assert.equal(times.at(-1), '202612011300');
  assert.match(rec.radar.keys[0].etag, /^"[0-9a-f]+"$/);
  assert.equal(typeof rec.radar.keys[0].size, 'number');
  assert.match(rec.radar.keys[0].last_modified, /^2026-12-01T/);
  assert.equal(kv.writes, 1);                       // no failure count to reset
  assert.equal(kv.map.has(KEY_FAILURES), false);
});

test('a second fire in the same hour does nothing', async () => {
  const kv = new FakeKV();
  await kv.put(hourKey('2026-12-01T13:00:00Z'), '{}');
  kv.writes = 0;
  const net = makeNet();
  const out = await run(kv, net, '2026-12-01T13:00:30Z');
  assert.equal(out.skipped, 'duplicate');
  assert.equal(net.calls.length, 0);
  assert.equal(kv.writes, 0);
});

test('stopped: no request, no write', async () => {
  const kv = new FakeKV();
  await kv.put(KEY_STOPPED, '{"at":"x"}');
  kv.writes = 0;
  const net = makeNet();
  const out = await run(kv, net, '2026-12-01T14:00:00Z');
  assert.equal(out.skipped, 'stopped');
  assert.equal(net.calls.length, 0);
  assert.equal(kv.writes, 0);
});

const failures = {
  'EA non-200': [{ [EA]: () => new Response('busy', { status: 503 }) }, 'ea', /^http 503$/],
  'EA 3xx': [{ [EA]: () => new Response(null, { status: 301, headers: { location: 'https://elsewhere.example/' } }) }, 'ea', /^redirect 301$/],
  'radar 3xx': [{ [S3]: () => new Response(null, { status: 307, headers: { location: 'https://x.example/' } }) }, 'radar', /^redirect 307$/],
  'radar non-200': [{ [S3]: () => new Response('<Error/>', { status: 403 }) }, 'radar', /^http 403$/],
  'EA timeout': [{ [EA]: hang }, 'ea', /^timeout$/],
  'radar exception': [{ [S3]: () => { throw new TypeError('network connection lost'); } }, 'radar', /^fetch failed: network connection lost$/],
  'EA oversize body': [{ [EA]: () => new Response('x'.repeat(EA_MAX_BYTES + 1), { status: 200 }) }, 'ea', /^oversize/],
  'EA oversize declared': [{ [EA]: () => new Response('{}', { status: 200, headers: { 'content-length': String(EA_MAX_BYTES + 1) } }) }, 'ea', /^oversize: content-length/],
  'radar oversize body': [{ [S3]: () => new Response('x'.repeat(LIST_MAX_BYTES + 1), { status: 200 }) }, 'radar', /^oversize/],
  'EA not JSON': [{ [EA]: () => new Response('<html>', { status: 200 }) }, 'ea', /^parse: /],
  'radar not a listing': [{ [S3]: () => new Response('{"a":1}', { status: 200 }) }, 'radar', /^parse: not a ListBucketResult/],
};

for (const [name, [over, side, error]] of Object.entries(failures)) {
  test(`failure counted, never retried: ${name}`, async () => {
    const kv = new FakeKV();
    const net = makeNet(over);
    const out = await run(kv, net, '2026-12-01T13:00:00Z');
    assert.equal(out.ok, false);
    const rec = kv.json(hourKey('2026-12-01T13:00:00Z'));
    assert.match(rec[side].error, error);
    assert.equal(rec[side === 'ea' ? 'radar' : 'ea'].error, null);
    assert.equal(net.calls.length, 2);                                   // one each, no retry
    assert.equal(new Set(net.calls.map((c) => c.url)).size, 2);
    assert.equal(kv.json(KEY_FAILURES).count, 1);
    if (side === 'ea') assert.deepEqual(rec.ea.items, []);
  });
}

test('wrong host or plain http: refused without a request, counted as a failure', async () => {
  for (const [eaUrl, msg] of [['https://example.com/flood-monitoring/data/readings?latest', /host not allowed/],
    ['http://environment.data.gov.uk/flood-monitoring/data/readings?latest', /host not allowed: http:/],
    ['https://environment.data.gov.uk:8443/x', /host not allowed/]]) {
    const kv = new FakeKV();
    const net = makeNet();
    await run(kv, net, '2026-12-01T13:00:00Z', { eaUrl });
    assert.equal(net.calls.length, 1);                                   // only the radar listing went out
    assert.ok(net.calls.every((c) => new URL(c.url).hostname === S3));
    assert.match(kv.json(hourKey('2026-12-01T13:00:00Z')).ea.error, msg);
    assert.equal(kv.json(KEY_FAILURES).count, 1);
  }
});

test('six consecutive failed runs stop it; the seventh makes no request; clearing the stop restarts it', async () => {
  const kv = new FakeKV();
  const net = makeNet({ [EA]: () => new Response('down', { status: 500 }) });
  for (let h = 0; h < STOP_AFTER; h++) {
    const before = kv.writes;
    const out = await run(kv, net, `2026-12-02T${String(10 + h).padStart(2, '0')}:00:00Z`);
    assert.ok(kv.writes - before <= 3, 'at most 3 KV writes a run');
    if (h < STOP_AFTER - 1) {
      assert.equal(kv.json(KEY_FAILURES).count, h + 1);
      assert.equal(kv.map.has(KEY_STOPPED), false);
    } else {
      assert.equal(out.stopped, true);
    }
  }
  const stop = kv.json(KEY_STOPPED);
  assert.equal(stop.at, '2026-12-02T15:00:04.000Z');
  assert.match(stop.reason, /6 consecutive failed runs/);
  assert.equal(stop.last_errors.length, STOP_AFTER);
  assert.deepEqual(stop.last_errors[0], { issue: '2026-12-02T10:00:00Z', ea: 'http 500', radar: null });
  const n = net.calls.length;
  const out = await run(kv, net, '2026-12-02T16:00:00Z');
  assert.equal(out.skipped, 'stopped');
  assert.equal(net.calls.length, n);
  assert.equal(kv.map.has(hourKey('2026-12-02T16:00:00Z')), false);
  // A person deletes state/stopped: the next run asks again, with a fresh count.
  kv.map.delete(KEY_STOPPED);
  const good = makeNet();
  assert.equal((await run(kv, good, '2026-12-02T17:00:00Z')).ok, true);
  assert.equal(good.calls.length, 2);
});

test('a good run resets the failure count', async () => {
  const kv = new FakeKV();
  await kv.put(KEY_FAILURES, JSON.stringify({ count: 3, recent: [{ issue: 'x', ea: 'timeout', radar: null }] }));
  const out = await run(kv, makeNet(), '2026-12-01T13:00:00Z');
  assert.equal(out.ok, true);
  assert.deepEqual(kv.json(KEY_FAILURES), { count: 0, recent: [] });
});

test('the 00:00, 01:00 and 02:00 runs list the day before as well; 03:00 does not', async () => {
  for (const [hh, n] of [['00', 2], ['01', 2], ['02', 2], ['03', 1], ['23', 1]]) {
    const kv = new FakeKV();
    const net = makeNet();
    await run(kv, net, `2026-12-01T${hh}:00:00Z`);
    const listings = net.calls.filter((c) => new URL(c.url).hostname === S3).map((c) => new URL(c.url).searchParams.get('prefix'));
    assert.deepEqual(listings, n === 2 ? ['radar/2026/11/30/', 'radar/2026/12/01/'] : ['radar/2026/12/01/'], hh);
    assert.ok(net.calls.length <= MAX_REQUESTS);
    const keys = kv.json(hourKey(`2026-12-01T${hh}:00:00Z`)).radar.keys.map((k) => k.key.slice(17, 29));
    assert.equal(keys.length, 12, hh);
  }
  // Across midnight: 01:00 takes 22:15 to 23:45 of the day before and 00:00 to 01:00.
  const kv = new FakeKV();
  await run(kv, makeNet(), '2026-12-01T01:00:00Z');
  const keys = kv.json(hourKey('2026-12-01T01:00:00Z')).radar.keys.map((k) => k.key.slice(17, 29));
  assert.equal(keys[0], '202611302215');
  assert.equal(keys.at(-1), '202612010100');
  // Year boundary.
  const net = makeNet();
  await run(new FakeKV(), net, '2027-01-01T00:00:00Z');
  assert.deepEqual(net.calls.slice(1).map((c) => new URL(c.url).searchParams.get('prefix')), ['radar/2026/12/31/', 'radar/2027/01/01/']);
});

test('one listing of two failing fails the run, and the good one is still kept', async () => {
  const kv = new FakeKV();
  const net = makeNet({ [S3]: (url) => (url.includes('2026/11/30') ? new Response('', { status: 500 })
    : new Response(listingBody('2026-12-01'), { status: 200 })) });
  const out = await run(kv, net, '2026-12-01T01:00:00Z');
  assert.equal(out.ok, false);
  const rec = kv.json(hourKey('2026-12-01T01:00:00Z'));
  assert.equal(rec.radar.error, 'http 500');
  assert.equal(rec.radar.listings.length, 2);
  assert.equal(rec.radar.keys.length, 5);   // 00:00 to 01:00 of the second day
});

test('never more than 3 requests a run', async () => {
  const net = makeNet();
  const get = guardedFetch(net.fetch, 50);
  const url = 'https://met-office-radar-obs-data.s3.amazonaws.com/?list-type=2&prefix=radar/2026/12/01/&max-keys=1000';
  for (let i = 0; i < MAX_REQUESTS; i++) assert.equal((await get(url, LIST_MAX_BYTES)).error, null);
  const fourth = await get(url, LIST_MAX_BYTES);
  assert.equal(fourth.error, 'request cap reached');
  assert.equal(net.calls.length, MAX_REQUESTS);
  assert.equal(get.count(), MAX_REQUESTS);
});

test('the fetch handler answers 404 to everything', async () => {
  for (const [method, path] of [['GET', '/'], ['GET', '/h/2026-12-01T13:00:00Z'], ['POST', '/state/stopped'], ['GET', '/measures.json']]) {
    const res = await worker.fetch(new Request(`https://swimsignal-river-shadow.example.workers.dev${path}`, { method }), {});
    assert.equal(res.status, 404);
  }
});
