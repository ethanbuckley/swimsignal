import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { DISPATCH_CRON, FRESH_MS, firstField, runDispatch } from '../src/dispatch.js';
import { scheduled } from '../src/index.js';
import { FakeKV, makeVapidEnv } from './helpers.js';

const SITE = 'https://swimsignal.co.uk/';
const DISPATCH = 'https://api.github.com/repos/ethanbuckley/swimsignal/actions/workflows/site.yml/dispatches';
const NOW = Date.parse('2026-10-16T20:30:00Z');
const minutesAgo = (m) => new Date(NOW - m * 60e3).toISOString().replace('Z', '+00:00');

// spots-lite.json as the build writes it: generated_at first, then much more (434 KB on 16 Oct 2026).
const lite = (generated_at) => `{"generated_at":"${generated_at}","version":"0.1.0","n":105,"spots":[${'{"id":"x"},'.repeat(40000)}{"id":"y"}]}`;

// A network that serves spots-lite.json in 1 KB chunks and plays GitHub's API.
function setup({ site = () => new Response(lite(minutesAgo(45))), github = () => new Response(null, { status: 204 }), token = 'github_pat_test' } = {}) {
  const calls = [], logs = [];
  let chunksRead = 0;
  const fetch = async (url, init = {}) => {
    calls.push({ url, ...init });
    if (url.startsWith(`${SITE}data/spots-lite.json`)) {
      const res = site();
      if (!res.ok || !res.body) return res;
      const bytes = new Uint8Array(await res.arrayBuffer());
      let at = 0;
      const body = new ReadableStream({ pull(c) { if (at >= bytes.length) return c.close(); chunksRead++; c.enqueue(bytes.slice(at, at += 1024)); } });
      return new Response(body, { headers: res.headers });
    }
    if (url === DISPATCH) return github(init);
    throw new Error(`unexpected fetch ${url}`);
  };
  const env = { SITE_URL: SITE, ...(token ? { GITHUB_DISPATCH_TOKEN: token } : {}) };
  const run = () => runDispatch(env, { fetch, log: (m) => logs.push(m), now: () => NOW });
  return { env, fetch, run, calls, logs, chunks: () => chunksRead };
}

test('a build over 20 minutes old: asks GitHub to run site.yml on main, with the token', async () => {
  const t = setup();
  assert.deepEqual(await t.run(), { dispatched: true, age_min: 45 });
  const post = t.calls.find((c) => c.url === DISPATCH);
  assert.equal(post.method, 'POST');
  assert.equal(post.headers.Authorization, 'Bearer github_pat_test');
  assert.equal(post.headers.Accept, 'application/vnd.github+json');
  assert.equal(post.headers['X-GitHub-Api-Version'], '2022-11-28');
  assert.ok(post.headers['User-Agent']);   // GitHub refuses requests without one
  assert.deepEqual(JSON.parse(post.body), { ref: 'main' });
  assert.ok(post.signal instanceof AbortSignal);
  assert.match(t.calls[0].url, /spots-lite\.json\?t=\d+$/);   // a new address each minute, past Pages' 10-minute cache
  assert.match(t.logs.at(-1), /site\.yml asked to run; the last build started 45 min ago/);
});

test('GitHub answering 200 with the run (newer API) counts as dispatched too', async () => {
  const t = setup({ github: () => Response.json({ workflow_run_id: 1 }, { status: 200 }) });
  assert.equal((await t.run()).dispatched, true);
});

test('a build under 20 minutes old: nothing asked', async () => {
  for (const m of [0, 5, 19.9]) {
    const t = setup({ site: () => new Response(lite(minutesAgo(m))) });
    assert.equal((await t.run()).skipped, 'fresh', `${m} min`);
    assert.ok(!t.calls.some((c) => c.url === DISPATCH));
  }
  const t = setup({ site: () => new Response(lite(minutesAgo(FRESH_MS / 60e3))) });
  assert.equal((await t.run()).dispatched, true);   // 20 minutes exactly: asked
});

test('DISPATCH_FRESH_MIN widens the window: 50 asks about once an hour', async () => {
  const t = setup({ site: () => new Response(lite(minutesAgo(45))) });
  t.env.DISPATCH_FRESH_MIN = '50';
  assert.equal((await t.run()).skipped, 'fresh');
  for (const bad of ['', '0', '-5', 'soon']) {   // anything else: the 20 minutes
    const u = setup({ site: () => new Response(lite(minutesAgo(25))) });
    u.env.DISPATCH_FRESH_MIN = bad;
    assert.equal((await u.run()).dispatched, true, bad);
  }
});

test('no token: nothing fetched, nothing asked, and the log says why', async () => {
  const t = setup({ token: null });
  assert.deepEqual(await t.run(), { skipped: 'no token' });
  assert.equal(t.calls.length, 0);
  assert.match(t.logs[0], /GITHUB_DISPATCH_TOKEN not set/);
  const empty = setup({ token: '' });
  assert.deepEqual(await empty.run(), { skipped: 'no token' });
});

test('only the start of spots-lite.json is read', async () => {
  const t = setup();
  await t.run();
  assert.ok(t.chunks() <= 5, `${t.chunks()} chunks read`);   // 4 KB of about 400 KB
});

test('a site that cannot be read is built anyway', async () => {
  for (const site of [() => new Response('gone', { status: 503 }), () => new Response('not json at all'),
    () => new Response('{"version":"0.1.0","generated_at":"2026-10-16T20:25:00+00:00"}'), () => { throw new TypeError('network down'); }]) {
    const t = setup({ site });
    assert.equal((await t.run()).dispatched, true);
    assert.ok(t.logs.some((m) => m.startsWith('dispatch: spots-lite.json:')));
    assert.match(t.logs.at(-1), /could not be read/);
  }
});

test('GitHub refusing throws, so the run shows as failed, and says what to check', async () => {
  for (const [status, words] of [[401, /expired or was deleted/], [403, /lacks Actions: write/], [404, /lacks Actions: write/], [422, /no workflow_dispatch/], [500, /HTTP 500/]]) {
    const t = setup({ github: () => new Response('{"message":"Bad credentials"}', { status }) });
    await assert.rejects(t.run(), words);
    assert.match(t.logs.at(-1), new RegExp(`HTTP ${status}`));
    assert.ok(!t.logs.join('\n').includes('github_pat_test'));   // the token is never logged
  }
});

test('the scheduled handler sends the 30-minute cron to dispatch and every other to the alerts', async () => {
  const t = setup();
  const result = await scheduled({ cron: DISPATCH_CRON }, t.env, { fetch: t.fetch, log: () => {}, now: () => NOW });
  assert.equal(result.dispatched, true);
  // The 2-minute cron runs the alerts, which read alerts.json, never GitHub's API.
  const asked = [];
  const alerts = async (url) => { asked.push(url); return new Response('down', { status: 503 }); };
  await assert.rejects(scheduled({ cron: '*/2 * * * *' }, { ...t.env, PUSH: new FakeKV(), ...(await makeVapidEnv()) }, { fetch: alerts, log: () => {}, now: () => NOW }), /alerts\.json: HTTP 503/);
  assert.ok(asked.length && asked.every((u) => u.includes('alerts.json')));
});

test("wrangler.toml lists both crons, the second exactly as dispatch.js names it", () => {
  const toml = readFileSync(new URL('../wrangler.toml', import.meta.url), 'utf8');
  const crons = JSON.parse(toml.match(/^crons\s*=\s*(\[.*\])/m)[1]);
  assert.deepEqual(crons, ['*/2 * * * *', DISPATCH_CRON]);
  assert.ok(!/GITHUB_DISPATCH_TOKEN\s*=/.test(toml), 'the token is a secret, never a var in this public file');
});

test('generated_at is read from the start of the file only', () => {
  assert.equal(firstField('{"generated_at":"2026-10-16T23:24:15.271548+01:00","version":"0.1.0"', 'generated_at'), '2026-10-16T23:24:15.271548+01:00');
  assert.equal(firstField('{ "generated_at" : "x" }', 'generated_at'), 'x');
  assert.equal(firstField('{"spots":[{"generated_at":"x"}]}', 'generated_at'), undefined);
  assert.equal(firstField('{"generated_at":"2026-10-16T23:2', 'generated_at'), undefined);   // cut off: not a time
});
