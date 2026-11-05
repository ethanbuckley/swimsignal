import test from 'node:test';
import assert from 'node:assert/strict';
import { handleRequest, forgetOldHits, reservation, costOf, PRICES, MAX_QUESTION, cleanQuestion, connectionOf } from '../src/index.js';
import { clearCache } from '../src/tools.js';
import { NOW, env, fixtureFetcher, post, scriptedClient } from './helpers.js';
import { EVALS } from '../evals/run.js';

const script = () => EVALS.questions.find((q) => q.id === 'leeds-sup-tomorrow').mock;
const deps = (client = scriptedClient(script())) => ({ client, fetcher: fixtureFetcher(), now: () => NOW });

test.beforeEach(() => clearCache());

test('answers a question from the site, with the CORS header', async () => {
  const e = env();
  const res = await handleRequest(post({ question: 'Paddleboarding within 20 miles of Leeds tomorrow morning?' }), e, deps());
  assert.equal(res.status, 200);
  assert.equal(res.headers.get('Access-Control-Allow-Origin'), 'https://swimsignal.co.uk');
  assert.equal(res.headers.get('Cache-Control'), 'no-store');
  const { answer } = await res.json();
  assert.equal(answer.day, '2026-11-01');
  assert.equal(answer.spots[0].id, 'osm-wharfe-greenholme');
  assert.equal(answer.spots[0].facts[0].topic, 'official');
  assert.match(answer.plan_url, /^https:\/\/swimsignal\.co\.uk\/plan\/#day=2026-11-01&from=Leeds&at=53\.8%2C-1\.55&within=20&kind=river$/);
});

test('keeps no question: the database holds a hashed count and the day\'s totals only', async () => {
  const e = env();
  const q = 'Paddleboarding within 20 miles of Leeds tomorrow morning?';
  await handleRequest(post({ question: q }), e, deps());
  const dump = JSON.stringify([...e.DB.rows('SELECT * FROM hits'), ...e.DB.rows('SELECT * FROM spend')]);
  assert.ok(!dump.includes('Leeds') && !dump.includes('203.0.113.7'), dump);
  assert.match(e.DB.rows('SELECT key FROM hits')[0].key, /^[0-9a-f]{32}$/);
});

test('refuses other origins, other methods and other paths', async () => {
  assert.equal((await handleRequest(post({ question: 'Leeds tomorrow?' }, { origin: 'https://evil.example' }), env(), deps())).status, 403);
  assert.equal((await handleRequest(new Request('https://ask.example/ask', { method: 'GET', headers: { Origin: 'https://swimsignal.co.uk' } }), env(), deps())).status, 405);
  assert.equal((await handleRequest(new Request('https://ask.example/other', { method: 'POST' }), env(), deps())).status, 404);
  const pre = await handleRequest(new Request('https://ask.example/ask', { method: 'OPTIONS', headers: { Origin: 'https://swimsignal.co.uk' } }), env(), deps());
  assert.equal(pre.status, 204);
  assert.equal(pre.headers.get('Access-Control-Allow-Methods'), 'POST');
});

test('off until ASK_ON is "on" and both secrets are set, and never with a model it cannot price', async () => {
  const client = scriptedClient(script());
  for (const over of [{ ASK_ON: 'off' }, { ASK_ON: undefined }, { ANTHROPIC_API_KEY: '' }, { ASK_HASH_KEY: undefined }, { ASK_MODEL: 'claude-unknown-1' }]) {
    const res = await handleRequest(post({ question: 'Leeds tomorrow?' }), env(over), deps(client));
    assert.equal(res.status, 503, JSON.stringify(over));
  }
  assert.equal(client.requests.length, 0);
});

test('checks the question', async () => {
  for (const body of [{}, { question: 7 }, { question: ' ' }, { question: 'x'.repeat(MAX_QUESTION + 1) }]) {
    assert.equal((await handleRequest(post(body), env(), deps())).status, 400, JSON.stringify(body).slice(0, 40));
  }
  const nul = String.fromCharCode(0), rlo = String.fromCharCode(0x202e);   // a control character and a right-to-left override
  assert.equal(cleanQuestion(`  Leeds${nul} ${rlo} tomorrow?\n`), 'Leeds tomorrow?');
});

test('limits each connection to ASK_PER_CONNECTION questions a day, IPv6 by its /64', async () => {
  const e = env({ ASK_PER_CONNECTION: '2' });
  const ask = (ip) => handleRequest(post({ question: 'Paddleboarding within 20 miles of Leeds tomorrow morning?' }, { ip }), e, deps());
  assert.equal((await ask('2001:db8:1:2::5')).status, 200);
  assert.equal((await ask('2001:db8:1:2:aaaa::9')).status, 200);
  assert.equal((await ask('2001:db8:1:2::77')).status, 429);
  assert.equal((await ask('198.51.100.4')).status, 200);
  assert.equal(connectionOf('2001:db8:1:2::5'), '2001:0db8:0001:0002::/64');
  await forgetOldHits(e, NOW + 2 * 86400 * 1000);
  assert.equal(e.DB.rows('SELECT * FROM hits').length, 0);
});

test('the daily cap: a question first reserves the most it could cost, then pays what it did', async () => {
  const model = 'claude-haiku-5-5';
  const most = reservation(model);
  // Room for two reservations and not three.
  const e = env({ ASK_DAILY_CAP_USD: String(most * 2.5) });
  const ask = (ip) => handleRequest(post({ question: 'Paddleboarding within 20 miles of Leeds tomorrow morning?' }, { ip }), e, deps());
  assert.equal((await ask('198.51.100.1')).status, 200);
  const day = e.DB.rows('SELECT * FROM spend')[0];
  assert.equal(day.reserved_micro, 0);
  assert.ok(day.spent_micro > 0 && day.spent_micro < most * 1e6 / 4, JSON.stringify(day));
  assert.equal((await ask('198.51.100.2')).status, 200);
  // Spent is small, so a third still fits: the cap counts what was spent, not what was reserved.
  assert.equal((await ask('198.51.100.3')).status, 200);
  const tight = env({ ASK_DAILY_CAP_USD: String(most / 2) });
  const client = scriptedClient(script());
  const res = await handleRequest(post({ question: 'Leeds tomorrow?' }), tight, deps(client));
  assert.equal(res.status, 503);
  assert.equal(client.requests.length, 0, 'no call to the API once the cap is reached');
});

test('the daily count of questions', async () => {
  const e = env({ ASK_QUESTIONS_PER_DAY: '1' });
  const ask = (ip) => handleRequest(post({ question: 'Paddleboarding within 20 miles of Leeds tomorrow morning?' }, { ip }), e, deps());
  assert.equal((await ask('198.51.100.1')).status, 200);
  assert.equal((await ask('198.51.100.2')).status, 503);
});

test('an API failure is a 500 with a plain message, and its reservation stays counted', async () => {
  const e = env();
  const client = { messages: { create: async () => { throw new Error('overloaded'); } } };
  const res = await handleRequest(post({ question: 'Leeds tomorrow?' }), e, deps(client));
  assert.equal(res.status, 500);
  assert.match((await res.json()).error, /Plan a swim works as always/);
  const day = e.DB.rows('SELECT * FROM spend')[0];
  assert.equal(day.spent_micro, Math.ceil(reservation('claude-haiku-5-5') * 1e6));
});

test('cost from the usage the API reports, by model', () => {
  const usage = { input_tokens: 1_000_000, output_tokens: 1_000_000, cache_creation_input_tokens: 1_000_000, cache_read_input_tokens: 1_000_000 };
  assert.equal(costOf('claude-haiku-5-5', usage).toFixed(4), (0.10 + 0.50 + 0.125 + 0.01).toFixed(4));
  assert.equal(costOf('claude-sonnet-5-5', usage).toFixed(2), (2 + 10 + 2.5 + 0.2).toFixed(2));
  assert.deepEqual(Object.keys(PRICES).sort(), ['claude-haiku-5-5', 'claude-opus-5-5', 'claude-sonnet-5-5']);
});

test('what the API is sent: the model, the four tools, the cached rules, the day and the question', async () => {
  const client = scriptedClient(script());
  await handleRequest(post({ question: 'Paddleboarding within 20 miles of Leeds tomorrow morning?' }), env({ ASK_EFFORT: 'low' }), deps(client));
  const first = client.requests[0];
  assert.equal(first.model, 'claude-haiku-5-5');
  assert.deepEqual(first.tools.map((t) => t.name), ['find_place', 'search_spots', 'get_spot', 'give_answer']);
  assert.ok(first.tools.every((t) => t.strict === true && t.input_schema.additionalProperties === false));
  assert.deepEqual(first.cache_control, { type: 'ephemeral' });
  assert.deepEqual(first.output_config, { effort: 'low' });
  assert.equal(first.thinking, undefined);   // Claude Haiku 5.5 thinks adaptively by default; effort is the control
  assert.equal(first.tool_choice, undefined);
  assert.match(first.messages[0].content, /Today in London is Saturday 31 October \(2026-10-31\)/);
  assert.match(first.messages[0].content, /<question>\nPaddleboarding within 20 miles of Leeds tomorrow morning\?\n<\/question>/);
  assert.ok(!first.system[0].text.includes('2026'), 'nothing that changes between questions is in the cached rules');
});

test('reads only SwimSignal\'s published files', async () => {
  const fetcher = fixtureFetcher();
  for (const q of EVALS.questions) {
    clearCache();
    await handleRequest(post({ question: q.question }, { ip: `198.51.100.${EVALS.questions.indexOf(q)}` }), env(), { client: scriptedClient(q.mock), fetcher, now: () => NOW });
  }
  assert.ok(fetcher.calls.length > 0);
  for (const path of fetcher.calls) assert.match(path, /^(spots-lite\.json|places\.json|spot\/[A-Za-z0-9_-]+\.json)$/);
});
