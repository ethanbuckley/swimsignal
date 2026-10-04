import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker, { runCron, subKey } from '../src/index.js';
import { addressId, cleanEmail, connectionOf, handleEmail, issuedWords, signedByService, unsubscribeToken } from '../src/email.js';
import { sendEmail } from '../src/mail.js';
import { FakeKV, makeUserAgent, makeVapidEnv } from './helpers.js';

const SITE = 'https://swimsignal.example/';
const ORIGIN = 'https://swimsignal.example';
const WORKER = 'https://push.example.workers.dev/';
const RESEND = 'https://api.resend.com/emails';
const vapid = await makeVapidEnv();

const spot = (id, rank, name = `Spot ${id}`, headline) =>
  [id, { name, rank, level: ['low', 'moderate', 'high', 'very high'][rank] ?? null, headline: headline ?? `${['Low', 'Moderate', 'High', 'Very high'][rank]} risk today: sewage spills`, url: `${SITE}spot/${id}/` }];
const alertsJson = (generated_at, spots) => ({ generated_at, spots: Object.fromEntries(spots) });

// A KV, an env with email set up, and a network that serves alerts.json, plays every push service
// and plays Resend: each email it is sent is kept, and its answer can be set per call.
function world({ email = true, answer = () => ({ status: 200, body: { id: 'x' } }), extra = {} } = {}) {
  const kv = new FakeKV();
  const env = {
    PUSH: kv, SITE_URL: SITE, ALLOWED_ORIGIN: ORIGIN, ...vapid,
    ...(email ? { MAIL_API_KEY: 're_test_key', MAIL_HASH_KEY: 'a test key that is long enough', EMAIL_FROM: 'SwimSignal <alerts@swimsignal.example>', EMAIL_REPLY_TO: 'hello@swimsignal.example', WORKER_URL: WORKER } : {}),
    ...extra,
  };
  const emails = [], pushes = [], logs = [], agents = {};
  let alerts = alertsJson('2026-10-04T06:00:00.000Z', [spot('a', 0), spot('b', 0)]);
  let clock = Date.parse('2026-10-04T07:00:00Z');
  const fetch = async (url, init = {}) => {
    if (url.startsWith(`${SITE}data/alerts.json`)) return Response.json(alerts);
    if (url === RESEND) {
      const sent = { headers: init.headers, body: JSON.parse(init.body) };
      const a = answer(sent, emails.length);
      if (a.status < 300) emails.push(sent);
      return new Response(JSON.stringify(a.body ?? {}), { status: a.status, headers: a.headers ?? {} });
    }
    if (agents[url]) {
      const { issued_at, expires_at, ...payload } = agents[url].read(init.body);
      pushes.push({ to: agents[url].name, payload });
      return new Response(null, { status: 201 });
    }
    throw new Error(`unexpected fetch ${url}`);
  };
  const deps = { fetch, now: () => clock, log: (m) => logs.push(m) };
  const call = (path, { method = 'POST', origin = ORIGIN, body, headers = {}, ip = '203.0.113.7' } = {}) =>
    handleEmail(new Request(WORKER.slice(0, -1) + path, {
      method,
      headers: { ...(origin ? { Origin: origin } : {}), 'Content-Type': 'application/json', 'CF-Connecting-IP': ip, ...headers },
      body: body === undefined ? undefined : typeof body === 'string' ? body : JSON.stringify(body),
    }), env, deps);
  const signUp = (address, spots = ['a', 'b'], opts = {}) => call('/email/subscribe', { body: { email: address, spots }, ...opts });
  const link = (text, path) => text.match(new RegExp(`${WORKER.replace(/\./g, '\\.')}email/${path}\\?[^\\s"<]+`))[0].replace(/&amp;/g, '&');
  // Signs up, opens the link in the email and presses Confirm.
  const subscribe = async (address, spots = ['a', 'b']) => {
    const before = emails.length;
    assert.equal((await signUp(address, spots, { ip: `198.51.100.${before}` })).status, 202);
    const url = new URL(link(emails[before].body.text, 'confirm'));
    assert.equal((await call(url.pathname + url.search, { origin: WORKER.slice(0, -1) })).status, 200);
  };
  const addPusher = async (name, spots) => {
    const ua = makeUserAgent(`https://fcm.googleapis.com/fcm/send/${name}`);
    agents[ua.subscription.endpoint] = { name, ...ua };
    await kv.put(await subKey(ua.subscription.endpoint), JSON.stringify({ subscription: ua.subscription, spots, updated: 'x' }), { metadata: { s: spots } });
  };
  return {
    kv, env, emails, pushes, logs, call, signUp, subscribe, link, addPusher, deps,
    setAlerts: (a) => { alerts = a; }, advance: (ms) => { clock += ms; }, now: () => clock,
    cron: () => runCron(env, deps),
  };
}

// ---- off until set up ----

test('with no email settings every /email/ address is 404 and the cron leaves email alone', async () => {
  const w = world({ email: false });
  assert.equal((await w.signUp('ann@example.org')).status, 404);
  assert.equal((await w.call('/email/confirm?id=x&n=y', { method: 'GET' })).status, 404);
  await w.kv.put('state', JSON.stringify({ generated_at: '2026-10-04T05:00:00.000Z', ranks: { a: 0 } }));
  w.setAlerts(alertsJson('2026-10-04T06:00:00.000Z', [spot('a', 2)]));
  const result = await w.cron();
  assert.equal(result.email, undefined);
  assert.equal(await w.kv.get('mailq'), null);
  // and the Worker's own router sends /email/ to the same place
  const res = await worker.fetch(new Request(`${WORKER}email/subscribe`, { method: 'POST', headers: { Origin: ORIGIN } }), w.env);
  assert.equal(res.status, 404);
});

// ---- sign-up ----

test('a sign-up stores a pending request for two days and sends only the confirmation', async () => {
  const w = world();
  const res = await w.signUp('  Ann@Example.org ');
  assert.equal(res.status, 202);
  assert.equal(res.headers.get('Access-Control-Allow-Origin'), ORIGIN);
  const id = await addressId(w.env, 'ann@example.org');
  const pending = await w.kv.get(`pend:${id}`, 'json');
  assert.deepEqual(Object.keys(pending).sort(), ['at', 'email', 'nonce', 'spots']);
  assert.equal(pending.email, 'ann@example.org');
  assert.deepEqual(pending.spots, ['a', 'b']);
  assert.equal(w.kv.ttl.get(`pend:${id}`), 172800);
  assert.equal(await w.kv.get(`mail:${id}`), null, 'nothing is subscribed before confirming');
  assert.equal(w.emails.length, 1);
  const [{ headers, body }] = w.emails;
  assert.equal(headers.Authorization, 'Bearer re_test_key');
  assert.deepEqual(body.to, ['ann@example.org']);
  assert.equal(body.from, 'SwimSignal <alerts@swimsignal.example>');
  assert.equal(body.reply_to, 'hello@swimsignal.example');
  assert.equal(body.subject, 'Confirm your SwimSignal email alerts');
  assert.match(body.text, /- Spot a\n- Spot b/);
  assert.match(body.text, new RegExp(`email/confirm\\?id=${id}&n=${pending.nonce}`));
  assert.equal(body.headers, undefined, 'a confirmation carries no list headers: nobody is on a list yet');
  assert.equal(await w.kv.get(`quota:2026-10-04`), '1');
});

test('the request is checked: origin, address, spots, honeypot and preflight', async () => {
  const w = world();
  assert.equal((await w.signUp('ann@example.org', ['a'], { origin: 'https://evil.example' })).status, 403);
  for (const bad of ['ann', 'ann@localhost', 'ann@@example.org', 'a b@example.org', 'ann@example.org\r\nBcc: x@y.z', 'ann@exa_mple.org', 'änn@example.org', '.ann@example.org']) {
    const res = await w.signUp(bad, ['a']);
    assert.equal(res.status, 400, bad);
  }
  assert.equal((await w.signUp('ann@example.org', [])).status, 400);
  assert.equal((await w.signUp('ann@example.org', ['not a spot'])).status, 400);
  assert.equal((await w.signUp('ann@example.org', ['zz'])).status, 400, 'a spot that is not in the forecast');
  const bot = await w.call('/email/subscribe', { body: { email: 'ann@example.org', spots: ['a'], website: 'http://spam.example' } });
  assert.equal(bot.status, 202);
  const pre = await w.call('/email/subscribe', { method: 'OPTIONS' });
  assert.equal(pre.status, 204);
  assert.equal(pre.headers.get('Access-Control-Allow-Methods'), 'POST');
  assert.equal(w.emails.length, 0);
  assert.equal([...w.kv.map.keys()].filter((k) => k.startsWith('pend:')).length, 0);
});

test('a sign-up while the forecast cannot be read stores and sends nothing', async () => {
  const w = world();
  const env = { ...w.env };
  const down = async (url) => { if (url.includes('alerts.json')) throw new TypeError('fetch failed'); throw new Error(url); };
  const res = await handleEmail(new Request(`${WORKER}email/subscribe`, { method: 'POST', headers: { Origin: ORIGIN, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'ann@example.org', spots: ['a'] }) }), env, { ...w.deps, fetch: down });
  assert.equal(res.status, 503);
  assert.equal([...w.kv.map.keys()].filter((k) => k.startsWith('pend:')).length, 0);
});

test('cleanEmail and connectionOf', () => {
  assert.equal(cleanEmail(' Ann.Lee+swim@Mail.Example.co.uk '), 'ann.lee+swim@mail.example.co.uk');
  assert.equal(connectionOf('2001:db8:1:2:3:4:5:6'), '2001:0db8:0001:0002::/64');
  assert.equal(connectionOf('2001:db8::1'), '2001:0db8:0000:0000::/64');
  assert.equal(connectionOf('203.0.113.7'), '203.0.113.7');
});

test('double opt-in: the link shows a button, and only pressing it subscribes', async () => {
  const w = world();
  await w.signUp('ann@example.org');
  const url = new URL(w.link(w.emails[0].body.text, 'confirm'));
  const id = await addressId(w.env, 'ann@example.org');
  const shown = await w.call(url.pathname + url.search, { method: 'GET', origin: null });
  assert.equal(shown.status, 200);
  const html = await shown.text();
  assert.match(html, /<form method="post"><p><button class="btn primary" type="submit">Confirm email alerts<\/button><\/p><\/form>/);
  assert.match(html, /ann@example\.org/);
  assert.match(shown.headers.get('Content-Security-Policy'), /default-src 'none'.*form-action 'self'/);
  assert.equal(shown.headers.get('Referrer-Policy'), 'no-referrer');
  assert.ok(!/<script/i.test(html));
  assert.equal(await w.kv.get(`mail:${id}`), null, 'opening the link (as a mail scanner would) does not subscribe');

  const wrong = new URL(url); wrong.searchParams.set('n', '0'.repeat(32));
  assert.equal((await w.call(wrong.pathname + wrong.search, { origin: null })).status, 404);
  assert.equal(await w.kv.get(`mail:${id}`), null);

  const done = await w.call(url.pathname + url.search, { origin: WORKER.slice(0, -1) });
  assert.equal(done.status, 200);
  assert.match(await done.text(), /Email alerts are on/);
  const record = await w.kv.get(`mail:${id}`, 'json');
  assert.deepEqual(Object.keys(record).sort(), ['confirmed', 'email', 'spots']);
  assert.deepEqual([record.email, record.spots, record.confirmed], ['ann@example.org', ['a', 'b'], new Date(w.now()).toISOString()]);
  assert.deepEqual(w.kv.meta.get(`mail:${id}`), { s: ['a', 'b'] });
  assert.equal(w.kv.ttl.has(`mail:${id}`), false);
  assert.equal(await w.kv.get(`pend:${id}`), null);
  assert.equal((await w.call(url.pathname + url.search, { method: 'GET', origin: null })).status, 404, 'a used link has expired');
  assert.equal(w.emails.length, 1, 'confirming sends nothing');
});

test('the sign-up\'s words carry "risk" after the level: the confirmation email and both pages', async () => {
  const w = world();
  await w.signUp('ann@example.org');
  const { text, html } = w.emails[0].body;
  const url = new URL(w.link(text, 'confirm'));
  const shown = await (await w.call(url.pathname + url.search, { method: 'GET', origin: null })).text();
  const done = await (await w.call(url.pathname + url.search, { origin: WORKER.slice(0, -1) })).text();
  const rule = 'when one of these spots reaches high or very high risk, at most once a day for each.';
  assert.ok(text.includes(`An alert comes ${rule}`) && html.includes(`An alert comes ${rule}`));
  assert.match(shown, /when one of your 2 saved spots reaches high or very high risk, at most once a day for each\.<\/p>/);
  assert.match(done, /You will get an email when one of your 2 saved spots reaches high or very high risk\.<\/p>/);
  // "turns high", "turns high or very high": a level word without "risk" (docs/DESIGN.md, Words).
  for (const words of [text, html, shown, done]) assert.doesNotMatch(words, /turns? (very )?high|very high(?! risk)/);
});

test('signing up again replaces the list only once the new one is confirmed', async () => {
  const w = world();
  await w.subscribe('ann@example.org', ['a']);
  const id = await addressId(w.env, 'ann@example.org');
  assert.equal((await w.signUp('ann@example.org', ['b'], { ip: '192.0.2.1' })).status, 202);
  assert.deepEqual((await w.kv.get(`mail:${id}`, 'json')).spots, ['a'], 'a sign-up alone changes nothing');
  const url = new URL(w.link(w.emails.at(-1).body.text, 'confirm'));
  await w.call(url.pathname + url.search, { origin: null });
  assert.deepEqual((await w.kv.get(`mail:${id}`, 'json')).spots, ['b']);
});

test('rate limits: per connection an hour, per address a day, and no address or IP stored in a key', async () => {
  const w = world();
  for (let i = 0; i < 5; i++) assert.equal((await w.signUp(`p${i}@example.org`, ['a'], { ip: '2001:db8:1:2::9' })).status, 202);
  const sixth = await w.signUp('p5@example.org', ['a'], { ip: '2001:db8:1:2::77' });   // the same /64
  assert.equal(sixth.status, 429);
  assert.match(await sixth.text(), /try again in an hour/);
  assert.equal(w.emails.length, 5);
  w.advance(3600e3);
  assert.equal((await w.signUp('p5@example.org', ['a'], { ip: '2001:db8:1:2::77' })).status, 202, 'a new hour, a new count');

  // An address gets at most three confirmations a day, and the fourth answer looks the same.
  const before = w.emails.length;
  for (let i = 0; i < 4; i++) assert.equal((await w.signUp('target@example.org', ['a'], { ip: `192.0.2.${i}` })).status, 202);
  assert.equal(w.emails.length - before, 3);

  for (const [key, value] of w.kv.map) {
    assert.ok(!key.includes('@') && !key.includes('2001') && !key.includes('192.0.2'), key);
    if (key.startsWith('rl:')) {
      assert.match(key, /^rl:(ip|to):[0-9a-f]{32}$/);
      assert.match(value, /^\d+$/);
      assert.ok([3660, 86460].includes(w.kv.ttl.get(key)), `${key} deletes itself`);
    }
  }
});

test('a full day refuses sign-ups, and so does the service saying its allowance is used', async () => {
  const w = world({ answer: (_, n) => n === 0 ? { status: 200, body: { id: '1' } } : { status: 429, body: { name: 'daily_quota_exceeded', message: 'You have exceeded your daily email sending quota.' } } });
  assert.equal((await w.signUp('ann@example.org', ['a'], { ip: '192.0.2.1' })).status, 202);
  const full = await w.signUp('bob@example.org', ['a'], { ip: '192.0.2.2' });
  assert.equal(full.status, 503);
  assert.match(await full.text(), /full for today/);
  const after = await w.signUp('cat@example.org', ['a'], { ip: '192.0.2.3' });
  assert.equal(after.status, 503);
  assert.equal(w.emails.length, 1, 'once the day is counted as full, the service is not asked again');
  assert.ok(w.logs.every((l) => !l.includes('@example.org')), 'logs never name an address');
});

// ---- unsubscribe ----

test('unsubscribe: the link shows a button, one-click POST deletes, and a bad token is refused', async () => {
  const w = world();
  await w.subscribe('ann@example.org');
  const id = await addressId(w.env, 'ann@example.org');
  const path = `/email/unsubscribe?id=${id}&t=${await unsubscribeToken(w.env, id)}`;
  const shown = await w.call(path, { method: 'GET', origin: null });
  assert.equal(shown.status, 200);
  assert.match(await shown.text(), /<button class="btn primary" type="submit">Unsubscribe<\/button>/);
  assert.ok(await w.kv.get(`mail:${id}`), 'opening the link does not unsubscribe');

  const forged = await w.call(`/email/unsubscribe?id=${id}&t=${'0'.repeat(32)}`, { origin: null });
  assert.equal(forged.status, 400);
  assert.ok(await w.kv.get(`mail:${id}`));

  // RFC 8058: the mail program POSTs the key/value pair from List-Unsubscribe-Post, with no Origin.
  const res = await w.call(path, { origin: null, body: 'List-Unsubscribe=One-Click', headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
  assert.equal(res.status, 200);
  assert.equal(await w.kv.get(`mail:${id}`), null);
  assert.equal(await w.kv.get(`pend:${id}`), null);
  const again = await w.call(path, { method: 'GET', origin: null });
  assert.match(await again.text(), /Nothing to unsubscribe/);
});

// ---- the cron ----

async function risen(w, spots) {
  await w.kv.put('state', JSON.stringify({ generated_at: '2026-10-04T05:00:00.000Z', ranks: { a: 0, b: 1 } }));
  w.setAlerts(alertsJson('2026-10-04T06:00:00.000Z', spots));
}

test('a rise queues push and email in one run; the next run sends the email, short and untracked', async () => {
  const w = world();
  await w.addPusher('pat', ['a']);
  await w.subscribe('ann@example.org', ['a', 'b']);
  await risen(w, [spot('a', 2, 'Pangbourne Meadow, River Thames'), spot('b', 1)]);
  w.emails.length = 0;
  const first = await w.cron();
  assert.deepEqual(first.risen, ['a']);
  assert.equal(w.emails.length, 0, 'sending starts next run');
  const id = await addressId(w.env, 'ann@example.org');
  const mailq = await w.kv.get('mailq', 'json');
  assert.deepEqual(mailq.items.map((i) => [i.id, Object.keys(i.spots)]), [[id, ['a']]]);
  assert.ok(!JSON.stringify(mailq).includes('@'), 'the queue holds no address');

  w.advance(120e3);
  const second = await w.cron();
  assert.deepEqual(second.email, { sent: 1, failed: 0, queued: 0 });
  assert.equal(w.pushes.length, 1);
  assert.equal(w.emails.length, 1);
  const [{ headers, body }] = w.emails;
  assert.equal(body.subject, 'High risk today at Pangbourne Meadow, River Thames');
  assert.deepEqual(body.to, ['ann@example.org']);
  const unsub = `${WORKER}email/unsubscribe?id=${id}&t=${await unsubscribeToken(w.env, id)}`;
  assert.deepEqual(body.headers, { 'List-Unsubscribe': `<${unsub}>`, 'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click' });
  assert.equal(headers['Idempotency-Key'], `alert-${id}-2026-10-04T06:00:00.000Z`);
  assert.equal(body.text, [
    'Pangbourne Meadow, River Thames', 'High risk today: sewage spills.', `${SITE}spot/a/`, '',
    'From the forecast issued at 07:00 on Sunday 4 October 2026. A forecast, not a water test: check the signs at the water before you swim.',
    'An alert can be late or not come at all, so no alert does not mean the water is clean.', '',
    'You get this because you asked for SwimSignal email alerts for your saved spots and confirmed it.',
    `Unsubscribe (deletes your address at once): ${unsub}`,
  ].join('\n'));
  // No tracking: nothing to fetch, and every link goes straight to the site or the Worker.
  assert.ok(!/<img|url\(|<link|<script|@import/i.test(body.html));
  for (const [, href] of body.html.matchAll(/href="([^"]+)"/g)) assert.ok(href.startsWith(SITE) || href.startsWith(WORKER), href);
  assert.match(body.html, /border-left:4px solid #c2552a/);
  assert.equal(await w.kv.get('mailq'), null);
});

test('a level word always carries "risk", and several spots make one email', async () => {
  const w = world();
  await w.subscribe('ann@example.org', ['a', 'b']);
  await risen(w, [spot('a', 2, 'Aston', 'Rated poor: advice against bathing'), spot('b', 3, 'Bray')]);
  w.emails.length = 0;
  await w.cron(); w.advance(120e3); await w.cron();
  assert.equal(w.emails.length, 1);
  const { body } = w.emails[0];
  assert.equal(body.subject, '2 of your saved spots are at high or very high risk');
  assert.match(body.text, /^Aston\nHigh risk\. Rated poor: advice against bathing\.\n.*spot\/a\/\n\nBray\nVery high risk today: sewage spills\./);
  assert.match(body.html, /color:#992a2a;">Very high risk today/);
});

test('at most EMAILS_PER_RUN a run, and alerts stop short of the daily cap to leave room for sign-ups', async () => {
  const w = world({ extra: { EMAIL_DAILY_CAP: '30', EMAIL_CONFIRM_RESERVE: '5', EMAILS_PER_RUN: '4' } });
  const id = await addressId(w.env, 'x@example.org');
  // 25 confirmed addresses, put in place directly (sign-ups would use the day's allowance).
  for (let i = 0; i < 25; i++) {
    const email = `p${i}@example.org`;
    await w.kv.put(`mail:${await addressId(w.env, email)}`, JSON.stringify({ email, spots: ['a'], confirmed: 'x' }), { metadata: { s: ['a'] } });
  }
  await w.kv.put('quota:2026-10-04', '10');   // ten already sent today
  await risen(w, [spot('a', 2), spot('b', 1)]);
  await w.cron();
  const counts = [];
  for (let run = 0; run < 6; run++) { w.advance(120e3); counts.push((await w.cron()).email.sent); }
  assert.deepEqual(counts, [4, 4, 4, 3, 0, 0], 'cap 30 - reserve 5 - 10 already sent = 15 today');
  assert.equal(await w.kv.get('quota:2026-10-04'), '25');
  assert.equal((await w.kv.get('mailq', 'json')).items.length, 10);
  assert.ok(w.logs.some((l) => /allowance for alerts is used/.test(l)));
  assert.ok(!id.includes('@'));
  // The next UTC day, but the forecast must be fresh too: a new build, same levels, nothing new rises.
  w.advance(18 * 3600e3);
  w.setAlerts(alertsJson(new Date(w.now() - 60e3).toISOString(), [spot('a', 2), spot('b', 1)]));
  const next = [];
  for (let run = 0; run < 4; run++) { w.advance(120e3); next.push((await w.cron()).email?.sent ?? 0); }
  assert.deepEqual(next, [4, 4, 2, 0], 'nothing new rose, so the run that compares the new build sends too');
});

test('the service\'s answers: a 5xx is retried later, a used allowance pauses until UTC midnight, a bad key pauses an hour, a refusal is dropped', async () => {
  let mode = 'busy';
  const answers = {
    busy: { status: 503, body: { name: 'service_unavailable' } },
    quota: { status: 429, body: { name: 'daily_quota_exceeded', message: 'quota' } },
    key: { status: 401, body: { name: 'missing_api_key' } },
    refuse: { status: 422, body: { name: 'invalid_parameter', message: 'Invalid `to` field: ann@example.org' } },
    ok: { status: 200, body: { id: 'y' } },
  };
  const w = world({ answer: (sent) => sent.body.subject.startsWith('Confirm') ? answers.ok : answers[mode] });
  await w.subscribe('ann@example.org', ['a']);
  await risen(w, [spot('a', 2), spot('b', 1)]);
  await w.cron();
  w.advance(120e3);
  let r = await w.cron();
  assert.deepEqual(r.email, { sent: 0, failed: 1, queued: 1 });
  let item = (await w.kv.get('mailq', 'json')).items[0];
  assert.equal(item.attempts, 1);
  assert.equal(item.next_attempt, w.now() + 120e3);
  w.advance(60e3); r = await w.cron();
  assert.equal(r.email.failed, 0, 'not due yet');

  mode = 'quota';
  w.advance(60e3); r = await w.cron();
  const q = await w.kv.get('mailq', 'json');
  assert.equal(q.paused_until, Date.parse('2026-10-05T00:00:00Z'));
  assert.equal(q.items[0].attempts, 1, 'a used allowance does not use up an attempt');
  w.advance(120e3); r = await w.cron();
  assert.ok(w.logs.at(-1).startsWith('email: paused until 2026-10-05T00:00:00.000Z'));

  await w.kv.put('mailq', JSON.stringify({ items: q.items }));   // as if midnight had come
  mode = 'key';
  w.advance(120e3); r = await w.cron();
  assert.equal((await w.kv.get('mailq', 'json')).paused_until, w.now() + 3600e3);
  assert.ok(w.logs.some((l) => l.includes('check MAIL_API_KEY and EMAIL_FROM')));

  await w.kv.put('mailq', JSON.stringify({ items: q.items }));
  mode = 'refuse';
  w.advance(120e3); r = await w.cron();
  assert.deepEqual(r.email, { sent: 0, failed: 1, queued: 0 });
  assert.equal(await w.kv.get('mailq'), null);
  assert.ok(w.logs.every((l) => !l.includes('ann@example.org')), 'an address in the service\'s reason is cut out');
  assert.ok(w.logs.some((l) => l.includes('<address>')));
});

test('an email waiting in the queue is checked when it goes: unsubscribed, dropped spot or lower level sends nothing', async () => {
  const w = world();
  await w.subscribe('ann@example.org', ['a']);
  await w.subscribe('bob@example.org', ['a']);
  await w.subscribe('cat@example.org', ['a', 'b']);
  await risen(w, [spot('a', 2), spot('b', 2)]);
  await w.cron();
  w.emails.length = 0;
  // Ann unsubscribes; Bob signs up again with only b; the next build has a back at moderate.
  const ann = await addressId(w.env, 'ann@example.org');
  await w.call(`/email/unsubscribe?id=${ann}&t=${await unsubscribeToken(w.env, ann)}`, { origin: null });
  const bob = await addressId(w.env, 'bob@example.org');
  await w.kv.put(`mail:${bob}`, JSON.stringify({ email: 'bob@example.org', spots: ['b'], confirmed: 'x' }));
  w.setAlerts(alertsJson('2026-10-04T06:30:00.000Z', [spot('a', 1), spot('b', 2)]));
  w.advance(120e3);
  await w.cron();
  assert.deepEqual(w.emails.map((e) => [e.body.to[0], e.body.subject]), [['cat@example.org', 'High risk today at Spot b']]);
});

test('an expired forecast pauses the email queue, as it pauses push', async () => {
  const w = world();
  await w.subscribe('ann@example.org', ['a']);
  await risen(w, [spot('a', 2), spot('b', 1)]);
  await w.cron();
  w.emails.length = 0;
  w.advance(9 * 3600e3);   // eight hours after issue, the forecast has expired
  const r = await w.cron();
  assert.deepEqual(r.email, { sent: 0, failed: 0, queued: 1 });
  assert.equal(w.emails.length, 0);
  assert.ok(w.logs.some((l) => /email: forecast expired; 1 emails wait/.test(l)));
});

// Push and email are filled from one list of risen spots, in the same run, so over any sequence of
// builds they alert for the same spots at the same builds. Here a spot rises, drops, rises again
// inside 20 hours (no alert), another rises a day later, and the first rises again.
test('push and email agree on every alert over a sequence of builds', async () => {
  const w = world();
  await w.addPusher('pat', ['a', 'b']);
  await w.subscribe('ann@example.org', ['a', 'b']);
  w.emails.length = 0;
  const names = (s) => [...new Set([...s.matchAll(/Spot (\w)/g)].map((m) => m[1]))].sort().join('');
  const steps = [[0, { a: 1, b: 0 }], [1, { a: 2, b: 0 }], [3, { a: 1, b: 0 }], [6, { a: 3, b: 0 }], [29, { a: 1, b: 2 }], [30, { a: 2, b: 3 }], [31, { a: 2, b: 3 }]];
  const seen = [];
  const start = Date.parse('2026-10-04T06:00:00Z');
  for (const [hours, ranks] of steps) {
    const at = start + hours * 3600e3;
    while (w.now() < at + 60e3) w.advance(60e3);
    w.setAlerts(alertsJson(new Date(at).toISOString(), Object.entries(ranks).map(([id, r]) => spot(id, r))));
    const [p0, e0] = [w.pushes.length, w.emails.length];
    for (let run = 0; run < 4; run++) { await w.cron(); w.advance(120e3); }
    seen.push([hours, w.pushes.slice(p0).map((p) => names(JSON.stringify(p.payload))).join(' '), w.emails.slice(e0).map((e) => names(e.body.text)).join(' ')]);
  }
  for (const [hours, push, email] of seen) assert.equal(email, push, `build at +${hours} h`);
  assert.deepEqual(seen.map(([h, p]) => [h, p]), [[0, ''], [1, 'a'], [3, ''], [6, ''], [29, 'b'], [30, 'a'], [31, '']]);
});

// ---- the provider module ----

// ---- the email service's reports: bounces, complaints and suppressions ----

// A webhook secret in Resend's form, and a report signed with it as Svix signs one.
const SECRET_BYTES = new Uint8Array(24).map((_, i) => i * 7 + 1);
const SECRET = 'whsec_' + btoa(String.fromCharCode(...SECRET_BYTES));
async function sign(body, { id = 'msg_2Lh9', ts, secret = SECRET_BYTES } = {}) {
  const key = await crypto.subtle.importKey('raw', secret, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = btoa(String.fromCharCode(...new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(`${id}.${ts}.${body}`)))));
  return { 'svix-id': id, 'svix-timestamp': String(ts), 'svix-signature': `v1,${sig}` };
}
// A report as Resend sends one (https://resend.com/docs/webhooks/emails/bounced, read 4 Oct 2026).
const report = (type, to, extra = {}) => ({ type, created_at: '2026-10-04T07:00:00.000Z',
  data: { email_id: '56761188-7520-42d8-8898-ff6fc54ce618', from: 'SwimSignal <alerts@swimsignal.example>', to, subject: 'High risk', ...extra } });
async function post(w, event, { headers, raw } = {}) {
  const body = raw ?? JSON.stringify(event);
  return w.call('/email/events', { origin: null, body, headers: headers ?? await sign(body, { ts: Math.floor(w.now() / 1000) }) });
}

test('a bounce for good, a complaint or a suppression deletes the address and stops its alerts at once', async () => {
  for (const [type, extra] of [['email.bounced', { bounce: { type: 'Permanent', subType: 'General', message: 'mailbox does not exist' } }],
    ['email.complained', {}], ['email.suppressed', { suppressed: { type: 'OnAccountSuppressionList' } }]]) {
    const w = world({ extra: { MAIL_WEBHOOK_SECRET: SECRET } });
    await w.subscribe('ann@example.org', ['a']);
    await w.signUp('ann@example.org', ['b'], { ip: '198.51.100.99' });   // a second sign-up, waiting for its confirmation
    const id = await addressId(w.env, 'ann@example.org');
    assert.ok(await w.kv.get(`mail:${id}`) && await w.kv.get(`pend:${id}`));
    const res = await post(w, report(type, ['Ann <ann@example.org>'], extra));
    assert.equal(res.status, 200, type);
    assert.equal(await w.kv.get(`mail:${id}`), null, type);
    assert.equal(await w.kv.get(`pend:${id}`), null, type);
    assert.ok(w.logs.some((l) => l === `email ${id.slice(0, 12)}: deleted after ${type.slice(6)}${type === 'email.bounced' ? ' (General)' : ''}`), w.logs.join('\n'));
    assert.ok(!w.logs.some((l) => l.includes('ann@')), 'no address in the logs');
    // Its alert, queued or not, no longer goes.
    await w.kv.put('state', JSON.stringify({ generated_at: '2026-10-04T05:00:00.000Z', ranks: { a: 0 } }));
    w.setAlerts(alertsJson('2026-10-04T06:00:00.000Z', [spot('a', 2)]));
    const sent = w.emails.length;
    await w.cron(); await w.cron();
    assert.equal(w.emails.length, sent, type);
  }
});

test('a bounce that is not for good, another event, or an address not signed up deletes nothing', async () => {
  const w = world({ extra: { MAIL_WEBHOOK_SECRET: SECRET } });
  await w.subscribe('ann@example.org', ['a']);
  const id = await addressId(w.env, 'ann@example.org');
  for (const event of [report('email.bounced', ['ann@example.org'], { bounce: { type: 'Transient', subType: 'MailboxFull' } }),
    report('email.delivered', ['ann@example.org']), report('email.delivery_delayed', ['ann@example.org'])]) {
    const res = await post(w, event);
    assert.equal(res.status, 200);
    assert.equal(await res.text(), 'Nothing to do');
  }
  assert.ok(await w.kv.get(`mail:${id}`));
  // Someone else's bounce, and an address that is not one: answered, and Ann is kept.
  assert.equal(await (await post(w, report('email.bounced', ['bob@example.org', 'not an address'], { bounce: { type: 'Permanent' } }))).text(), 'Deleted 1');
  assert.ok(await w.kv.get(`mail:${id}`));
});

test('a report is believed only with a valid signature from the last five minutes', async () => {
  const w = world({ extra: { MAIL_WEBHOOK_SECRET: SECRET } });
  await w.subscribe('ann@example.org', ['a']);
  const id = await addressId(w.env, 'ann@example.org');
  const body = JSON.stringify(report('email.complained', ['ann@example.org'])), ts = Math.floor(w.now() / 1000);
  const forged = await sign(body, { ts, secret: new Uint8Array(24) });
  const replayed = await sign(body, { ts: ts - 301 });
  const other = await sign(JSON.stringify(report('email.complained', ['bob@example.org'])), { ts });   // a real signature for another body
  for (const headers of [{}, forged, replayed, { ...other }, { ...await sign(body, { ts }), 'svix-signature': 'v2,abc' }]) {
    assert.equal((await post(w, null, { raw: body, headers })).status, 401);
  }
  assert.ok(await w.kv.get(`mail:${id}`), 'nothing deleted');
  // Several signatures, as after the secret is rotated: any valid one will do.
  const good = await sign(body, { ts });
  assert.equal((await post(w, null, { raw: body, headers: { ...good, 'svix-signature': `v1,AAAA ${good['svix-signature']}` } })).status, 200);
  assert.equal(await w.kv.get(`mail:${id}`), null);
  assert.equal(await signedByService({ MAIL_WEBHOOK_SECRET: 'whsec_***' }, new Headers(good), body, w.now()), false);   // a secret that is not base64
});

test('without MAIL_WEBHOOK_SECRET the address is 404, and only POST is taken', async () => {
  const w = world();
  assert.equal((await post(w, report('email.complained', ['ann@example.org']))).status, 404);
  const v = world({ extra: { MAIL_WEBHOOK_SECRET: SECRET } });
  assert.equal((await v.call('/email/events', { method: 'GET', origin: null })).status, 405);
  assert.equal((await post(v, null, { raw: 'x'.repeat(70 * 1024), headers: {} })).status, 400);   // too large, refused unread
});

test('sendEmail maps the service\'s answers to outcomes', async () => {
  const env = { MAIL_API_KEY: 'k', EMAIL_FROM: 'f@example.org' };
  const answer = (status, body = {}, headers = {}) => async () => new Response(JSON.stringify(body), { status, headers });
  const msg = { to: 'a@example.org', subject: 's', text: 't', html: 'h', idempotencyKey: 'i' };
  const at = Date.parse('2026-10-04T07:00:00Z');
  const run = (fetch) => sendEmail(env, msg, { fetch, now: () => at });
  assert.equal((await run(answer(200, { id: 'x' }))).outcome, 'sent');
  assert.equal((await run(answer(409, { name: 'invalid_idempotent_request' }))).outcome, 'sent');
  assert.deepEqual(await run(answer(429, { name: 'rate_limit_exceeded' }, { 'Retry-After': '30' })), { outcome: 'retry', after: at + 30e3, why: 'HTTP 429 rate_limit_exceeded' });
  assert.equal((await run(answer(429, { name: 'monthly_quota_exceeded' }))).outcome, 'quota');
  assert.equal((await run(answer(500))).outcome, 'retry');
  assert.equal((await run(answer(403, { name: 'validation_error', message: 'The domain is not verified' }))).outcome, 'config');
  assert.equal((await run(answer(422, { name: 'invalid_parameter' }))).outcome, 'rejected');
  assert.equal((await run(async () => { throw new TypeError('fetch failed'); })).outcome, 'retry');
});

test('issuedWords gives UK time on both sides of the clocks changing', () => {
  assert.equal(issuedWords('2026-10-04T06:00:00.000Z'), '07:00 on Sunday 4 October 2026');
  assert.equal(issuedWords('2026-12-01T06:00:00.000Z'), '06:00 on Tuesday 1 December 2026');
});
