// Official advice in the messages (alerts.json `official`, scripts/alerts.js from eatoday.js eaTodayBrief).
// Words only: with or without the field the same browsers are told at the same runs, and an alerts.json
// from before the field gives the same messages as before.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { alertPayload, runCron, subKey } from '../src/index.js';
import { datePayload } from '../src/dates.js';
import { weeklyPayload } from '../src/weekly.js';
import { alertEmail } from '../src/email.js';
import { officialWords } from '../src/shared.js';
import { FakeKV, makeUserAgent, makeVapidEnv } from './helpers.js';

const SITE = 'https://swimsignal.co.uk/';
const BRIEF = 'EA advice against bathing · since 19 Jun · checked 26 Oct';
const OFFICIAL = `Official: ${BRIEF}. Follow it first.`;
const frensham = (extra = {}) => ({ name: 'Frensham Great Pond', rank: 2, level: 'high', headline: 'High risk today: sewage spills',
  action: 'Best not to swim today.', url: `${SITE}spot/f/`, ...extra });

test('officialWords: the line, or nothing for a missing, empty or odd field', () => {
  assert.equal(officialWords({ official: BRIEF }), OFFICIAL);
  for (const s of [{}, { official: '' }, { official: 3 }, { official: [BRIEF] }, null, undefined]) assert.equal(officialWords(s), '');
});

test('a push for one spot puts the official line first; without the field it is as before', () => {
  const was = alertPayload(['f'], { f: frensham() }, SITE);
  assert.equal(was.body, 'High risk today: sewage spills. Best not to swim today.');
  const now = alertPayload(['f'], { f: frensham({ official: BRIEF }) }, SITE);
  assert.deepEqual(now, { ...was, body: `${OFFICIAL} High risk today: sewage spills. Best not to swim today.` });
  const both = alertPayload(['f', 'o'], { f: frensham({ official: BRIEF }), o: { ...frensham(), name: 'Other' } }, SITE);
  assert.equal(both.body, 'Frensham Great Pond (official advice in force), Other');
  assert.equal(alertPayload(['f', 'o'], { f: frensham(), o: { ...frensham(), name: 'Other' } }, SITE).body, 'Frensham Great Pond, Other');
});

test('a dated notice at low risk never reads as clean beside official advice', () => {
  const day = { level: 'low', headline: 'Low risk', action: 'Usual care' };
  const line = { spot: 'f', date: '2026-10-31', from: null, day };
  const was = datePayload([line], { f: frensham() }, SITE, 'x');
  assert.equal(was.body, 'Low risk. Usual care. This is the first forecast for this day, and it can change.');
  const now = datePayload([line], { f: frensham({ official: BRIEF }) }, SITE, 'x');
  assert.deepEqual(now, { ...was, body: `${OFFICIAL} ${was.body}` });
  const two = datePayload([line, { ...line, spot: 'o' }], { f: frensham({ official: BRIEF }), o: { name: 'Other' } }, SITE, 'x');
  assert.equal(two.body, `Frensham Great Pond · Sat 31 Oct: Low risk. ${OFFICIAL}\nOther · Sat 31 Oct: Low risk.`);
});

test('the weekly note: "Saturday, low risk" carries the official line; order and link unchanged', () => {
  const best = { date: '2026-10-31', level: 'low', words: 'Saturday, low risk' };
  const spots = (o) => ({ f: { name: 'Frensham Great Pond', url: `${SITE}spot/f/`, best, ...o }, o: { name: 'Other', best: { ...best, level: 'moderate', words: 'Saturday, moderate risk' } } });
  const was = weeklyPayload(['o', 'f'], spots({}), SITE), now = weeklyPayload(['o', 'f'], spots({ official: BRIEF }), SITE);
  assert.equal(was.body, 'Frensham Great Pond: Saturday, low risk.\nOther: Saturday, moderate risk.');
  assert.deepEqual(now, { ...was, body: `Frensham Great Pond: Saturday, low risk. ${OFFICIAL}\nOther: Saturday, moderate risk.` });
});

test('the alert email says the official line above the level, in text and HTML; same subject and recipient', () => {
  const env = { SITE_URL: SITE };
  const was = alertEmail(env, 'a@example.com', ['f'], { f: frensham() }, '2026-10-26T22:00:00Z', 'https://u');
  const now = alertEmail(env, 'a@example.com', ['f'], { f: frensham({ official: BRIEF }) }, '2026-10-26T22:00:00Z', 'https://u');
  assert.equal(now.to, was.to); assert.equal(now.subject, was.subject); assert.deepEqual(now.headers, was.headers);
  assert.doesNotMatch(was.text, /Official/); assert.doesNotMatch(was.html, /Official/);
  assert.match(now.text, new RegExp(`^Frensham Great Pond\n${OFFICIAL}\nHigh risk today: sewage spills\\.\n`));
  assert.ok(now.html.includes(`<p style="margin:0 0 4px;font-weight:600;">${OFFICIAL}</p>`));
});

// The cron with and without `official`: the same browsers get a push at the same runs, and state is the same.
const vapid = await makeVapidEnv();
async function day(withOfficial) {
  const kv = new FakeKV(), agents = {}, pushes = [];
  for (const [name, spots] of Object.entries({ ann: ['f'], bob: ['o'], cat: ['f', 'o'], dan: ['q'] })) {
    const ua = makeUserAgent(`https://fcm.googleapis.com/fcm/send/${name}`);
    agents[ua.subscription.endpoint] = { name, ...ua };
    await kv.put(await subKey(ua.subscription.endpoint), JSON.stringify({ subscription: ua.subscription, spots, updated: 'x' }));
  }
  let alerts, clock = Date.parse('2026-10-26T22:10:00Z');
  const fetch = async (url, init) => {
    if (url.startsWith(`${SITE}data/alerts.json`)) return Response.json(alerts);
    const { issued_at, expires_at, ...payload } = agents[url].read(init.body);
    pushes.push({ run: alerts.generated_at, to: agents[url].name, tag: payload.tag, body: payload.body });
    return new Response(null, { status: 201 });
  };
  const env = { PUSH: kv, SITE_URL: SITE, ...vapid };
  const o = withOfficial ? { official: BRIEF } : {};
  const spot = (rank, extra = {}) => ({ name: 'S', rank, level: ['low', 'moderate', 'high', 'very high'][rank], headline: 'H', ...extra });
  const builds = [
    ['2026-10-26T21:00:00Z', { f: spot(0, o), o: spot(1), q: spot(0) }],
    ['2026-10-26T22:00:00Z', { f: spot(2, o), o: spot(3), q: spot(1) }],
    ['2026-10-26T22:05:00Z', { f: spot(2, o), o: spot(3), q: spot(1) }],
  ];
  for (const [generated_at, spots] of builds) {
    alerts = { generated_at, spots };
    for (let i = 0; i < 3; i++) { await runCron(env, { fetch, log: () => {}, now: () => clock }); clock += 120e3; }
  }
  return { pushes, state: await kv.get('state', 'json') };
}

test('same recipients, runs, tags and state with or without official advice; only the words differ', async () => {
  const was = await day(false), now = await day(true);
  assert.ok(was.pushes.length > 0);
  const who = (p) => p.map(({ run, to, tag }) => `${run} ${to} ${tag}`).sort();
  assert.deepEqual(who(now.pushes), who(was.pushes));
  assert.deepEqual(now.state, was.state);
  const ann = now.pushes.find((p) => p.to === 'ann');
  assert.ok(ann.body.startsWith(OFFICIAL));
  assert.ok(!was.pushes.find((p) => p.to === 'ann').body.includes('Official'));
});
