import { test } from 'node:test';
import assert from 'node:assert/strict';
import { handleRequest, runCron, subKey } from '../src/index.js';
import { cleanDates, dateNews, dayLevels, dayOf } from '../src/dates.js';
import { FakeKV, makeUserAgent, makeVapidEnv } from './helpers.js';

const SITE = 'https://swimsignal.example/', ORIGIN = 'https://swimsignal.example';
const vapid = await makeVapidEnv();

// The sentences as scripts/alerts.js writes them: `words`, and each day [level, headline, action].
const WORDS = ['Low risk', 'Usual care: cover cuts, try not to swallow water and wash your hands before eating.',
  'Moderate risk: sewage spills', 'Take more care: young children, older people and anyone with a weakened immune system may want a lower day or spot.',
  'High risk: sewage spills', 'Better to choose a lower day or spot. If you do swim, try not to swallow any water.'];
const DAY = { low: ['low', 0, 1], moderate: ['moderate', 2, 3], high: ['high', 4, 5] };
const addDays = (iso, n) => { const d = new Date(iso + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
// A build issued at 06:00 UK time on `first`, whose five days start then. levels: {spot: [five levels or null]}.
function build(first, levels = {}) {
  const dates = [0, 1, 2, 3, 4].map((n) => addDays(first, n));
  const daily = (id, name) => ({ name, rank: 0, level: 'low', headline: 'Low risk for the next five days', action: WORDS[1], url: `${SITE}spot/${id}/`,
    days: (levels[id] ?? ['low', 'low', 'low', 'low', 'low']).map((l) => (l ? DAY[l] : null)) });
  return { generated_at: `${first}T05:00:00.000Z`, dates, words: WORDS, spots: {
    a: daily('a', 'Wharfe at Cromwheel, Ilkley'), b: daily('b', 'Thames at Henley'),
    c: { name: 'Semerwater', rank: -1, level: 'no overflows', headline: 'No sewage risk from monitored overflows',
      action: 'After heavy rain, wait a couple of days before swimming if you can.', url: `${SITE}spot/c/` } } };
}
const at = (iso) => Date.parse(`${iso}T05:10:00Z`);   // ten minutes after that day's build

async function setup({ clock = at('2027-06-07'), status = () => 201 } = {}) {
  const kv = new FakeKV();
  const env = { PUSH: kv, SITE_URL: SITE, ALLOWED_ORIGIN: ORIGIN, ...vapid };
  const agents = {};
  const post = async (path, name, body) => {
    if (!agents[name]) { const ua = makeUserAgent(`https://fcm.googleapis.com/fcm/send/${name}`); agents[name] = ua; agents[ua.subscription.endpoint] = { name, ...ua }; }
    return handleRequest(new Request(`https://push.example/${path}`, { method: 'POST', headers: { Origin: ORIGIN, 'Content-Type': 'application/json' },
      body: JSON.stringify(path === 'unsubscribe' ? { endpoint: agents[name].subscription.endpoint } : { subscription: agents[name].subscription, ...body }) }), env, { now: () => clock });
  };
  const subscribe = async (name, body) => { const res = await post('subscribe', name, body); assert.equal(res.status, 204, await res.text()); };
  const pushes = [], logs = [];
  let alerts;
  const fetch = async (url, init) => {
    if (url.startsWith(`${SITE}data/alerts.json`)) return Response.json(alerts);
    const agent = agents[url];
    const { issued_at, expires_at, ...payload } = agent.read(init.body);
    pushes.push({ to: agent.name, payload, issued_at });
    return new Response(null, { status: status(agent.name) });
  };
  const run = (a) => { if (a) alerts = a; return runCron(env, { fetch, log: (m) => logs.push(m), now: () => clock }); };
  // A new build: the run that finds the news and queues it, then the run two minutes later that sends.
  const deliver = async (a) => { const first = await run(a); clock += 120e3; const second = await run(); return { first, second }; };
  const key = (name) => subKey(`https://fcm.googleapis.com/fcm/send/${name}`);
  const record = async (name) => kv.get(await key(name), 'json');
  return { kv, env, post, subscribe, run, deliver, pushes, logs, key, record, at: (t) => { clock = t; } };
}

test('a page subscribes with dates; the app\'s requests, which never send dates, keep them', async () => {
  const t = await setup();
  await t.subscribe('ann', { spots: ['b'], weekly: true });
  // The organisers' page sends the dates alone: the saved spots and the weekly note stay.
  await t.subscribe('ann', { dates: [{ spot: 'a', date: '2027-06-12' }, { spot: 'c', date: '2027-07-01' }] });
  let r = await t.record('ann');
  assert.deepEqual([r.spots, r.weekly, r.dates], [['b'], true, [{ spot: 'a', date: '2027-06-12' }, { spot: 'c', date: '2027-07-01' }]]);
  assert.deepEqual(t.kv.meta.get(await t.key('ann')), { s: ['b'], w: 1, d: ['a 2027-06-12', 'c 2027-07-01'] });
  // The app sends its spots again, without dates: the dates stay; without weekly: the note is off, as always.
  await t.subscribe('ann', { spots: ['b', 'c'] });
  r = await t.record('ann');
  assert.deepEqual([r.spots, 'weekly' in r, r.dates.length], [['b', 'c'], false, 2]);
  // Removing every saved spot keeps a record that still has dates; with none left either, it goes.
  await t.subscribe('ann', { spots: [] });
  assert.deepEqual((await t.record('ann')).spots, []);
  assert.deepEqual(t.kv.meta.get(await t.key('ann')), { s: [], d: ['a 2027-06-12', 'c 2027-07-01'] });
  await t.subscribe('ann', { dates: [] });
  assert.equal(await t.record('ann'), null);
  // A browser with no record yet may ask about a date alone.
  await t.subscribe('bob', { dates: [{ spot: 'a', date: '2027-06-12' }] });
  assert.deepEqual(await t.record('bob').then((x) => [x.spots, x.dates]), [[], [{ spot: 'a', date: '2027-06-12' }]]);
  // Turning alerts off deletes everything, dates too.
  assert.equal((await t.post('unsubscribe', 'bob')).status, 204);
  assert.equal(await t.record('bob'), null);
});

test('dates are checked: none passed, none over 400 days ahead, at most 10, each a real date and a listed kind of id', async () => {
  const t = await setup({ clock: Date.parse('2027-06-07T22:30:00Z') });   // 23:30 in the UK: still 7 June there
  const refuse = async (body, why) => { const res = await t.post('subscribe', 'ann', body); assert.equal(res.status, 400, why); assert.match(await res.text(), why); };
  await refuse({ dates: [{ spot: 'a', date: '2027-06-06' }] }, /that date has passed/);
  await refuse({ dates: [{ spot: 'a', date: addDays('2027-06-07', 401) }] }, /more than 400 days ahead/);
  await refuse({ dates: Array.from({ length: 11 }, (_, i) => ({ spot: 'a', date: addDays('2027-06-08', i) })) }, /at most 10 dates/);
  await refuse({ dates: [{ spot: 'a', date: '2027-02-30' }] }, /yyyy-mm-dd/);
  await refuse({ dates: [{ spot: 'a', date: '12/06/2027' }] }, /yyyy-mm-dd/);
  await refuse({ dates: [{ spot: 'a b', date: '2027-06-12' }] }, /bad spot id/);
  await refuse({ dates: [{ spot: 'a', date: '2027-06-12' }, { spot: 'a', date: '2027-06-12' }] }, /twice/);
  await refuse({ dates: 'a 2027-06-12' }, /dates must be an array/);
  await refuse({}, /spots must be an array/);   // neither: as an old page's mistake was answered
  await t.subscribe('ann', { dates: [{ spot: 'a', date: '2027-06-07' }, { spot: 'a', date: addDays('2027-06-07', 400) },
    ...Array.from({ length: 8 }, (_, i) => ({ spot: 'b', date: addDays('2027-06-08', i) }))] });
  assert.equal((await t.record('ann')).dates.length, 10);
  // Only the two fields are kept.
  assert.deepEqual(cleanDates([{ spot: 'a', date: '2027-06-12', note: 'x' }], '2027-06-07'), [{ spot: 'a', date: '2027-06-12' }]);
});

test('the day the date enters the forecast, one notice with its level and what to do; then one each time its level changes', async () => {
  const t = await setup();
  await t.subscribe('ann', { dates: [{ spot: 'a', date: '2027-06-12' }] });
  await t.subscribe('bob', { spots: ['a'] });                                  // saved the spot, asked about no date
  await t.subscribe('cat', { dates: [{ spot: 'a', date: '2027-06-13' }] });    // a later day
  await t.run(build('2027-06-07'));                                              // first run: state only
  assert.equal(t.pushes.length, 0);
  assert.deepEqual((await t.kv.get('state', 'json')).days.a, { '2027-06-07': 'low', '2027-06-08': 'low', '2027-06-09': 'low', '2027-06-10': 'low', '2027-06-11': 'low' });
  // The next morning's build reaches Saturday 12 June.
  t.at(at('2027-06-08'));
  const { first, second } = await t.deliver(build('2027-06-08', { a: ['low', 'low', 'low', 'low', 'moderate'] }));
  assert.deepEqual([first.queued, second.sent, second.queued], [1, 1, 0]);
  assert.ok(t.logs.includes('cron: 2027-06-08T05:00:00.000Z: 0 spots rose to high, 0 alerts to send, 1 date notices'));
  assert.deepEqual(t.pushes.map((p) => p.to), ['ann']);
  assert.deepEqual(t.pushes[0].payload, {
    title: 'Wharfe at Cromwheel, Ilkley · Saturday 12 June',
    body: `Moderate risk: sewage spills. ${WORDS[3]} This is the first forecast for this day, and it can change.`,
    url: `${SITE}organisers.html#spot=a&date=2027-06-12`, tag: 'dipspot-a-2027-06-12-moderate' });
  assert.equal(t.pushes[0].issued_at, '2027-06-08T05:00:00.000Z');
  // A later build the same day: Saturday rises to high.
  t.at(Date.parse('2027-06-08T09:10:00Z'));
  const later = { ...build('2027-06-08', { a: ['low', 'low', 'low', 'low', 'high'] }), generated_at: '2027-06-08T09:00:00.000Z' };
  await t.deliver(later);
  assert.equal(t.pushes.length, 2);
  assert.deepEqual(t.pushes[1].payload, {
    title: 'Wharfe at Cromwheel, Ilkley · Saturday 12 June',
    body: `High risk: sewage spills. Was moderate risk. ${WORDS[5]}`,
    url: `${SITE}organisers.html#spot=a&date=2027-06-12`, tag: 'dipspot-a-2027-06-12-high' });
  // Back down the next day.
  t.at(at('2027-06-09'));
  await t.deliver(build('2027-06-09', { a: ['low', 'low', 'low', 'low', 'low'] }));
  // Ann's change and Cat's first notice (13 June enters the forecast) go out in the same run, in
  // either order: each person gets one notice, and which is sent first does not matter.
  const last = t.pushes.slice(2);
  assert.deepEqual(last.map((p) => p.to).sort(), ['ann', 'cat']);
  assert.equal(last.find((p) => p.to === 'ann').payload.body, `Low risk. Was high risk. ${WORDS[1]}`);
  assert.deepEqual(t.pushes.slice(0, 2).map((p) => p.to), ['ann', 'ann']);
});

test('no notice when the day\'s level is unchanged, nor when its rain forecast is late for one build', async () => {
  const t = await setup();
  await t.subscribe('ann', { dates: [{ spot: 'a', date: '2027-06-10' }] });
  await t.run(build('2027-06-07', { a: ['low', 'low', 'low', 'moderate', 'low'] }));   // already in the forecast when asked
  for (const [h, levels] of [[9, ['low', 'low', 'low', 'moderate', 'low']], [13, ['low', 'low', 'low', null, 'low']], [17, ['low', 'low', 'low', 'moderate', 'low']]]) {
    const hh = String(h).padStart(2, '0');
    t.at(Date.parse(`2027-06-07T${hh}:10:00Z`));
    const r = await t.run({ ...build('2027-06-07', { a: levels }), generated_at: `2027-06-07T${hh}:00:00.000Z` });
    assert.equal(r.queued, 0, `${h}:00`);
  }
  assert.equal(t.pushes.length, 0);
  assert.equal(await t.kv.get('queue'), null);
});

test('a pair is forgotten after its date: the record loses it, or goes if nothing is left', async () => {
  const t = await setup();
  await t.subscribe('ann', { spots: ['b'], dates: [{ spot: 'a', date: '2027-06-08' }, { spot: 'a', date: '2027-06-20' }] });
  await t.subscribe('bob', { dates: [{ spot: 'a', date: '2027-06-08' }] });
  await t.run(build('2027-06-07'));
  t.at(at('2027-06-09'));   // 8 June has passed; the new build has news (11 to 13 June)
  await t.run(build('2027-06-09'));
  const ann = await t.record('ann');
  assert.deepEqual([ann.spots, ann.dates], [['b'], [{ spot: 'a', date: '2027-06-20' }]]);
  assert.deepEqual(t.kv.meta.get(await t.key('ann')), { s: ['b'], d: ['a 2027-06-20'] });
  assert.equal(await t.record('bob'), null);
  assert.ok(t.logs.includes('dates: forgot past dates in 2 records'));
  // A page sending its old list again cannot bring a passed date back.
  const res = await t.post('subscribe', 'ann', { dates: [{ spot: 'a', date: '2027-06-08' }] });
  assert.equal(res.status, 400);
  // The app's request without dates drops any that have passed while it is about it.
  await t.kv.put(await t.key('ann'), JSON.stringify({ ...ann, dates: [{ spot: 'a', date: '2027-06-01' }, { spot: 'a', date: '2027-06-20' }] }));
  await t.subscribe('ann', { spots: ['b'] });
  assert.deepEqual((await t.record('ann')).dates, [{ spot: 'a', date: '2027-06-20' }]);
});

test('records and builds from before dates work as they did', async () => {
  const t = await setup();
  // An old record, written by the Worker before dates, and an old alerts.json without `dates`.
  const ua = makeUserAgent('https://fcm.googleapis.com/fcm/send/old');
  await t.kv.put(await subKey(ua.subscription.endpoint), JSON.stringify({ subscription: ua.subscription, spots: ['a'], updated: 'x' }), { metadata: { s: ['a'] } });
  const old = (gen, rank) => ({ generated_at: gen, spots: { a: { name: 'Wharfe', rank, level: rank >= 2 ? 'high' : 'low', headline: 'h', url: `${SITE}spot/a/` } } });
  await t.run(old('2027-06-07T05:00:00.000Z', 0));
  assert.deepEqual(await t.kv.get('state', 'json'), { generated_at: '2027-06-07T05:00:00.000Z', ranks: { a: 0 } });   // no days
  assert.deepEqual(dayLevels(old('x', 0)), {});
  assert.equal(dayOf(old('x', 0), 'a', '2027-06-07'), null);
  // A new build with days: the old record asked about no date, so it hears only its high-risk alert.
  t.at(Date.parse('2027-06-07T09:10:00Z'));
  const risen = { ...build('2027-06-07', { a: ['high', 'high', 'low', 'low', 'low'] }), generated_at: '2027-06-07T09:00:00.000Z' };
  risen.spots.a = { ...risen.spots.a, rank: 2, level: 'high', headline: 'High risk today: sewage spills', action: WORDS[5] };
  const agents = { [ua.subscription.endpoint]: ua };
  const pushes = [];
  const fetch = async (url, init) => url.startsWith(SITE) ? Response.json(risen) : (pushes.push(agents[url].read(init.body)), new Response(null, { status: 201 }));
  await runCron(t.env, { fetch, log: () => {}, now: () => Date.parse('2027-06-07T09:10:00Z') });
  await runCron(t.env, { fetch, log: () => {}, now: () => Date.parse('2027-06-07T09:12:00Z') });
  assert.deepEqual(pushes.map((p) => [p.title, p.tag]), [['Wharfe at Cromwheel, Ilkley', 'dipspot-a']]);
  // An old subscribe body (spots, weekly) is answered as before.
  const res = await handleRequest(new Request('https://push.example/subscribe', { method: 'POST', headers: { Origin: ORIGIN },
    body: JSON.stringify({ subscription: ua.subscription, spots: ['a'], weekly: true }) }), t.env);
  assert.equal(res.status, 204);
  assert.deepEqual(t.kv.meta.get(await subKey(ua.subscription.endpoint)), { s: ['a'], w: 1 });
  assert.equal('dates' in JSON.parse(t.kv.map.get(await subKey(ua.subscription.endpoint))), false);
});

test('several dates with news in one build make one notice; a pair dropped or changed back before sending is skipped', async () => {
  const t = await setup();
  await t.subscribe('ann', { dates: [{ spot: 'a', date: '2027-06-12' }, { spot: 'c', date: '2027-06-12' }, { spot: 'b', date: '2027-06-12' }] });
  await t.subscribe('bob', { dates: [{ spot: 'a', date: '2027-06-12' }] });
  await t.run(build('2027-06-07'));
  t.at(at('2027-06-08'));
  const b8 = build('2027-06-08', { a: ['low', 'low', 'low', 'low', 'moderate'], b: ['low', 'low', 'low', 'low', null] });   // b has no level yet
  const queued = await t.run(b8);
  assert.equal(queued.queued, 2);
  await t.subscribe('bob', { dates: [] });   // bob stops it before it goes
  t.at(at('2027-06-08') + 120e3);
  await t.run();
  assert.deepEqual(t.pushes.map((p) => p.to), ['ann']);
  assert.deepEqual(t.pushes[0].payload, { title: 'New forecasts for 2 of your dates',
    body: 'Wharfe at Cromwheel, Ilkley · Sat 12 Jun: Moderate risk: sewage spills.\nSemerwater · Sat 12 Jun: No sewage risk from monitored overflows.',
    url: `${SITE}organisers.html#spot=a&date=2027-06-12`, tag: 'dipspot-dates-2027-06-08T05:00:00.000Z' });
  // Queued as a change, then changed back in the build that sends it: nothing to say.
  t.at(Date.parse('2027-06-08T09:10:00Z'));
  const nob = ['low', 'low', 'low', 'low', null];
  assert.equal((await t.run({ ...build('2027-06-08', { a: ['low', 'low', 'low', 'low', 'high'], b: nob }), generated_at: '2027-06-08T09:00:00.000Z' })).queued, 1);
  t.at(Date.parse('2027-06-08T09:12:00Z'));
  const r = await t.run({ ...build('2027-06-08', { a: ['low', 'low', 'low', 'low', 'moderate'], b: nob }), generated_at: '2027-06-08T09:01:00.000Z' });
  assert.deepEqual([r.sent, r.queued], [0, 0]);
  assert.equal(t.pushes.length, 1);
});

test('the news is decided from the levels alone: new days, changed days, and days with no level', () => {
  const prev = dayLevels(build('2027-06-07', { a: ['low', 'low', 'low', 'moderate', null] }));
  assert.deepEqual(prev.a, { '2027-06-07': 'low', '2027-06-08': 'low', '2027-06-09': 'low', '2027-06-10': 'moderate' });
  assert.deepEqual(prev.c['2027-06-11'], 'no overflows');
  const next = build('2027-06-08', { a: ['low', 'low', 'high', null, 'low'] });
  const news = dateNews(next, prev);
  // 10 June changed; 11 June has no level in either build; 12 June is new.
  assert.deepEqual([...news].filter(([k]) => k.startsWith('a ')), [['a 2027-06-10', 'moderate'], ['a 2027-06-12', null]]);
  assert.deepEqual(dayLevels(next, prev).a, { '2027-06-08': 'low', '2027-06-09': 'low', '2027-06-10': 'high', '2027-06-12': 'low' });
  // A day missing from one build keeps its last level, so it is not new in the next.
  const gap = dayLevels(build('2027-06-08', { a: ['low', null, 'high', null, 'low'] }), dayLevels(next, prev));
  assert.equal(gap.a['2027-06-09'], 'low');
  assert.equal(dateNews(build('2027-06-08', { a: ['low', 'low', 'high', null, 'low'] }), gap).has('a 2027-06-09'), false);
});

test('date notices share the alerts\' queue: SENDS_PER_RUN a run, and no KV write for each one told', async () => {
  const t = await setup();
  for (let i = 0; i < 20; i++) await t.subscribe(`u${String(i).padStart(2, '0')}`, { dates: [{ spot: 'a', date: '2027-06-12' }] });
  await t.run(build('2027-06-07'));
  t.at(at('2027-06-08'));
  const writes = [];
  for (let i = 0; i < 4; i++) {
    const before = t.kv.writes, r = await t.run(i === 0 ? build('2027-06-08') : undefined);
    writes.push([r.sent, r.queued, t.kv.writes - before]);
    t.at(at('2027-06-08') + (i + 1) * 120e3);
  }
  // Queue and state; then the queue after each batch (deleted when empty); then nothing.
  assert.deepEqual(writes, [[0, 20, 2], [15, 5, 1], [5, 0, 1], [0, 0, 0]]);
  assert.equal(new Set(t.pushes.map((p) => p.to)).size, 20);
  // A build with nothing new for anyone lists no keys.
  t.at(Date.parse('2027-06-08T09:10:00Z'));
  let listed = 0; const list = t.kv.list.bind(t.kv); t.kv.list = (o) => { listed++; return list(o); };
  await t.run({ ...build('2027-06-08'), generated_at: '2027-06-08T09:00:00.000Z' });
  assert.equal(listed, 0);
});
