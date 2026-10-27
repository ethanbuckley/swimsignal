// Official advice in the messages. scripts/alerts.js (#392) writes `official` (eatoday.js eaTodayBrief)
// and, while a notice shows, makes `action` (and each day's) the notice itself. The texts that give the
// action already say it once; the Worker adds it only to those that do not: the weekly note, a list of
// dates, a combined push and the email. Words only: with or without the field the same browsers are told
// at the same runs, and an alerts.json from before the field gives the same messages as before.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { alertPayload, runCron, subKey } from '../src/index.js';
import { datePayload } from '../src/dates.js';
import { weeklyPayload } from '../src/weekly.js';
import { alertEmail } from '../src/email.js';
import { officialMark, officialWords } from '../src/shared.js';
import { FakeKV, makeUserAgent, makeVapidEnv } from './helpers.js';

const SITE = 'https://swimsignal.co.uk/';
const BRIEF = 'EA advice against bathing (harmful algae) · since 19 Jun · checked 26 Oct';
const OFFICIAL = `Official: ${BRIEF}. Follow it first; the level is SwimSignal's sewage forecast only.`;
const count = (text, s) => text.split(s).length - 1;
// A spot as scripts/alerts.js writes it: with advice, `official` and an `action` that is the notice.
const frensham = (advised, extra = {}) => ({ name: 'Frensham Great Pond', rank: 2, level: 'high', headline: 'High risk today: sewage spills',
  action: advised ? OFFICIAL : 'Best not to swim today.', url: `${SITE}spot/f/`, ...(advised ? { official: BRIEF } : {}), ...extra });

test('officialWords: alerts.js\'s own line, or nothing for a missing, empty or odd field', () => {
  assert.equal(officialWords({ official: BRIEF }), OFFICIAL);
  for (const s of [{}, { official: '' }, { official: 3 }, { official: [BRIEF] }, null, undefined]) assert.equal(officialWords(s), '');
});

test('officialMark follows the check: shown when checked, "not re-checked since" when stale, unverified, gone or changed', () => {
  assert.equal(officialMark({ official: BRIEF }), 'Official notice shown');
  const old = BRIEF.replace('checked 26 Oct', 'not re-checked since 19 Oct');
  assert.equal(officialMark({ official: old }), 'Official notice, not re-checked since 19 Oct');
  assert.equal(officialMark({ official: `${old} · 1 more` }), 'Official notice, not re-checked since 19 Oct');
  for (const s of [{}, { official: '' }, { official: 3 }, null]) assert.equal(officialMark(s), '');
  // Nowhere does the Worker claim more than the notice: no "in force".
  const many = Object.fromEntries(Array.from({ length: 12 }, (_, i) => [`s${i}`, { ...frensham(false), name: `A long spot name number ${i}` }]));
  const stale = { ...frensham(true), official: old };
  const body = alertPayload([...Object.keys(many), 'f'], { ...many, f: stale }, SITE).body;
  assert.ok(body.length <= 200 && body.startsWith('Official notice, not re-checked since 19 Oct · Frensham Great Pond, '));   // the cut keeps it
  assert.doesNotMatch(body, /in force/);
  const lines = Object.keys(many).map((spot) => ({ spot, date: '2026-10-31', from: null, day: { level: 'low', headline: 'Low risk forecast: no overflow upstream reports live', action: 'x' } }));
  const list = datePayload([...lines, { spot: 'f', date: '2026-10-31', from: null, day: { level: 'low', headline: 'Low risk', action: OFFICIAL } }],
    { ...many, f: stale }, SITE, 'x').body;
  assert.ok(list.length <= 600 && list.startsWith('Official notice, not re-checked since 19 Oct · Frensham Great Pond · Sat 31 Oct: Low risk. Official:'));
});

test('a push for one spot says the notice once, through `action`; several spots mark the advised name', () => {
  assert.equal(alertPayload(['f'], { f: frensham(false) }, SITE).body, 'High risk today: sewage spills. Best not to swim today.');
  const one = alertPayload(['f'], { f: frensham(true) }, SITE).body;
  assert.equal(one, `Official notice shown · High risk today: sewage spills. ${OFFICIAL}`);
  assert.equal(count(one, 'Official:'), 1);
  const other = { ...frensham(false), name: 'Other' };
  assert.equal(alertPayload(['o', 'f'], { f: frensham(true), o: other }, SITE).body, 'Official notice shown · Frensham Great Pond, Other');   // advised first
  assert.equal(alertPayload(['f', 'o'], { f: frensham(false), o: other }, SITE).body, 'Frensham Great Pond, Other');
});

test('dated notices: one pair says it once through the day\'s action; a list adds it to the advised line', () => {
  const line = { spot: 'f', date: '2026-10-31', from: null, day: { level: 'low', headline: 'Low risk', action: OFFICIAL } };
  const one = datePayload([line], { f: frensham(true) }, SITE, 'x').body;
  assert.equal(one, `Official notice shown · Low risk. ${OFFICIAL} This is the first forecast for this day, and it can change.`);
  assert.equal(count(one, 'Official:'), 1);
  const plain = { spot: 'o', date: '2026-10-31', from: null, day: { level: 'low', headline: 'Low risk', action: 'Usual care' } };
  const two = datePayload([line, plain], { f: frensham(true), o: { name: 'Other' } }, SITE, 'x').body;
  assert.equal(two, `Official notice shown · Frensham Great Pond · Sat 31 Oct: Low risk. ${OFFICIAL}\nOther · Sat 31 Oct: Low risk.`);
  assert.equal(datePayload([line, plain], { f: frensham(false), o: { name: 'Other' } }, SITE, 'x').body,
    'Frensham Great Pond · Sat 31 Oct: Low risk.\nOther · Sat 31 Oct: Low risk.');
});

test('the weekly note: "low risk every day" carries the notice once; order, link and tag unchanged', () => {
  const best = { date: '2026-10-27', level: 'low', words: 'low risk every day from tomorrow to Friday' };
  const spots = (o) => ({ f: { name: 'Frensham Great Pond', url: `${SITE}spot/f/`, best, ...o }, o: { name: 'Other', best: { ...best, level: 'moderate', words: 'Saturday, moderate risk' } } });
  const was = weeklyPayload(['o', 'f'], spots({}), SITE), now = weeklyPayload(['o', 'f'], spots({ official: BRIEF }), SITE);
  assert.equal(was.body, 'Frensham Great Pond: low risk every day from tomorrow to Friday.\nOther: Saturday, moderate risk.');
  assert.deepEqual(now, { ...was, body: `Official notice shown · Frensham Great Pond: low risk every day from tomorrow to Friday. ${OFFICIAL}\nOther: Saturday, moderate risk.` });
  assert.equal(count(now.body, 'Official:'), 1);
});

test('the alert email says the notice once, above the level, in text and HTML; same subject, recipient, headers', () => {
  const env = { SITE_URL: SITE };
  const was = alertEmail(env, 'a@example.com', ['f'], { f: frensham(false) }, '2026-10-26T22:00:00Z', 'https://u');
  const now = alertEmail(env, 'a@example.com', ['f'], { f: frensham(true) }, '2026-10-26T22:00:00Z', 'https://u');
  assert.equal(now.to, was.to); assert.equal(now.subject, was.subject); assert.deepEqual(now.headers, was.headers);
  assert.doesNotMatch(was.text, /Official/); assert.doesNotMatch(was.html, /Official/);
  assert.ok(now.text.startsWith(`Frensham Great Pond\n${OFFICIAL}\nHigh risk today: sewage spills.\n`));
  assert.equal(count(now.text, 'Official:'), 1);
  assert.equal(count(now.html, 'Official:'), 1);
});

// The cron with and without advice: the same browsers get a push at the same runs, and state is the same.
const vapid = await makeVapidEnv();
async function day(advised) {
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
  const o = advised ? { official: BRIEF, action: OFFICIAL } : { action: 'A' };
  const spot = (rank, extra = { action: 'A' }) => ({ name: 'S', rank, level: ['low', 'moderate', 'high', 'very high'][rank], headline: 'H', ...extra });
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
  for (const p of now.pushes) assert.ok(count(p.body, 'Official:') <= 1);
  assert.equal(count(now.pushes.find((p) => p.to === 'ann').body, 'Official:'), 1);
  assert.ok(!was.pushes.some((p) => p.body.includes('Official')));
});
