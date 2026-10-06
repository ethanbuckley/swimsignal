// SwimSignal push alerts. The site's pages subscribe here; every 2 minutes the cron
// compares the site's alerts.json with the last run and pushes to people whose saved
// spots have just become high. On Thursday evenings, runs with no alert to send also send the
// weekly note to those who asked for it (weekly.js).

import { importEcdhPublic, sendPush, unb64url, vapidSigner } from './webpush.js';
import {
  HIGH, Invalid, MAX_ATTEMPTS, MAX_RETRY_WAIT, check, cleanSpots, forecastExpiry, isObject, listKeys, nextAttempt, readJson, reply, retryAfter,
} from './shared.js';
import { drainEmails, emailOn, handleEmail, queueEmails } from './email.js';
import { runWeekly } from './weekly.js';
import { cleanDates, dateFor, dateNews, datesOf, dayLevels, londonToday, pairKey } from './dates.js';

export { forecastExpiry };

// At most one alert a spot in 20 hours: the site is rebuilt several times a day, and a spot near
// the line can cross it, drop back and cross again, which would alert people each time.
const QUIET_MS = 20 * 3600 * 1000;
const CONCURRENCY = 6; // Workers allow six open connections per invocation.
// The browsers' push services. Accepting any https URL would let anyone make the Worker
// POST to a host of their choosing.
const PUSH_HOSTS = ['fcm.googleapis.com', 'updates.push.services.mozilla.com', 'web.push.apple.com'];
const PUSH_SUFFIXES = ['.push.apple.com', '.notify.windows.com'];
// Records whose dates have passed, rewritten without them in one run (dates.js): two KV operations
// each, and at most one write a record a day, since a run that finds news looks at every record.
const TIDY_PER_RUN = 20;

export default {
  fetch: (request, env) => handleRequest(request, env),
  async scheduled(controller, env) { await runCron(env); },
};

// ---- HTTP ----

const ROUTES = new Map([['/subscribe', subscribe], ['/unsubscribe', unsubscribe]]);

export async function handleRequest(request, env, { now = Date.now } = {}) {
  const path = new URL(request.url).pathname;
  if (path.startsWith('/email/')) return handleEmail(request, env);   // email.js: off until set up
  const route = ROUTES.get(path);
  if (!route) return reply(404, 'Not found');
  if (request.method !== 'POST' && request.method !== 'OPTIONS') return reply(405, 'Method not allowed', { Allow: 'POST, OPTIONS' });
  // Browsers always send Origin on these requests, so a missing one is not the site either.
  if (request.headers.get('Origin') !== env.ALLOWED_ORIGIN) return reply(403, 'Origin not allowed');
  const cors = { 'Access-Control-Allow-Origin': env.ALLOWED_ORIGIN, Vary: 'Origin' };
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: {
      ...cors,
      'Access-Control-Allow-Methods': 'POST',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age': '86400',
    } });
  }
  try {
    await route(await readJson(request), env, { now });
    return new Response(null, { status: 204, headers: cors });
  } catch (err) {
    if (err instanceof Invalid) return reply(400, err.message, cors);
    throw err;
  }
}

function checkEndpoint(endpoint) {
  check(typeof endpoint === 'string' && endpoint.length < 1024, 'endpoint must be a string under 1024 characters');
  let url;
  try { url = new URL(endpoint); } catch { throw new Invalid('endpoint is not a URL'); }
  check(url.protocol === 'https:', 'endpoint must be https');
  return endpoint;
}

export function isPushService(endpoint) {
  let url;
  try { url = new URL(endpoint); } catch { return false; }
  const host = url.hostname;
  return url.protocol === 'https:' && url.port === '' && !url.username && !url.password
    && (PUSH_HOSTS.includes(host) || PUSH_SUFFIXES.some((suffix) => host.endsWith(suffix)));
}

function decodeKey(value, name, bytes, maxChars) {
  check(typeof value === 'string' && value.length <= maxChars, `${name} has the wrong length`);
  let raw;
  try { raw = unb64url(value); } catch { throw new Invalid(`${name} is not base64url`); }
  check(raw.length === bytes, `${name} must decode to ${bytes} bytes`);
  return raw;
}

// Keeps only the fields push needs, so nothing else a client sends is ever stored.
async function cleanSubscription(sub) {
  check(isObject(sub), 'subscription missing');
  const endpoint = checkEndpoint(sub.endpoint);
  check(isPushService(endpoint), 'unsupported push service');
  const { expirationTime = null, keys } = sub;
  check(expirationTime === null || Number.isFinite(expirationTime), 'expirationTime must be a number or null');
  check(isObject(keys), 'subscription keys missing');
  const p256dh = decodeKey(keys.p256dh, 'p256dh', 65, 90);
  check(p256dh[0] === 4, 'p256dh must be an uncompressed P-256 point');
  // Catches points that are not on the curve now, rather than failing at every alert.
  try { await importEcdhPublic(p256dh); } catch { throw new Invalid('p256dh is not a P-256 point'); }
  decodeKey(keys.auth, 'auth', 16, 24);
  const strip = (s) => s.replace(/=+$/, '');
  return { endpoint, expirationTime, keys: { p256dh: strip(keys.p256dh), auth: strip(keys.auth) } };
}

export async function subKey(endpoint) {
  const hash = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(endpoint)));
  return 'sub:' + Array.from(hash, (b) => b.toString(16).padStart(2, '0')).join('');
}

// The app (the Saved page) sends the saved spots and the weekly note, and never dates; the
// organisers' page sends dates alone ("Alerts for a date", dates.js). What a request leaves out is
// kept from the record: the app does not know the dates, and the organisers' page does not know the
// saved spots. A request with spots and no weekly turns the note off, as it always has.
async function subscribe(data, env, { now }) {
  check(isObject(data), 'body must be a JSON object');
  const subscription = await cleanSubscription(data.subscription);
  check(data.spots !== undefined || data.dates !== undefined, 'spots must be an array');
  const spots = data.spots === undefined ? undefined : cleanSpots(data.spots);
  // The weekly note (weekly.js): off unless the page says true. Kept only when on.
  check(data.weekly === undefined || typeof data.weekly === 'boolean', 'weekly must be true or false');
  const today = londonToday(now());
  const dates = data.dates === undefined ? undefined : cleanDates(data.dates, today);
  const key = await subKey(subscription.endpoint);
  const old = spots === undefined || dates === undefined ? await env.PUSH.get(key, 'json') : null;
  const record = {
    subscription,
    spots: spots ?? (Array.isArray(old?.spots) ? old.spots : []),
    weekly: data.weekly !== undefined ? data.weekly : spots === undefined && old?.weekly === true,
    dates: (dates ?? datesOf(old)).filter((d) => d.date >= today),
  };
  if (record.spots.length === 0 && record.dates.length === 0) { await env.PUSH.delete(key); return; }
  await putRecord(env, key, record, now);
}

// A record, with its spots, the note's w: 1 and its dates also in the key's metadata (at most 1024
// bytes), so the cron finds who to alert from a list of keys alone instead of reading every
// record. Too many for the metadata, and the cron reads the record. Fields that are off are left
// out, so a record that never asked for the note or a date is as it was before them.
async function putRecord(env, key, { subscription, spots, weekly, dates }, now) {
  const metadata = { s: spots, ...(weekly ? { w: 1 } : {}), ...(dates.length ? { d: dates.map((d) => pairKey(d.spot, d.date)) } : {}) };
  const meta = JSON.stringify(metadata).length <= 1024 ? { metadata } : {};
  await env.PUSH.put(key, JSON.stringify({ subscription, spots, ...(weekly ? { weekly: true } : {}), ...(dates.length ? { dates } : {}),
    updated: new Date(now()).toISOString() }), meta);
}

async function unsubscribe(data, env) {
  check(isObject(data), 'body must be a JSON object');
  await env.PUSH.delete(await subKey(checkEndpoint(data.endpoint)));
}

// ---- Cron ----
// Every 2 minutes. A run reads alerts.json, then either sends the next batch of queued alerts,
// each checked against that forecast, or, with nothing queued, queues one alert for each
// subscriber of the spots that have just turned high. On the free plan a run gets 50 outgoing
// requests and 10 ms of CPU, and one notification took about 0.3 ms of CPU in Node, so a run
// sends at most SENDS_PER_RUN (15, or the env's; raise it on the Paid plan): about 450 an hour. KV can take a minute to show a write everywhere, and a
// repeat of a batch is silent (a notification with the same tag replaces the last one).
const SENDS_PER_RUN = 15;

// Logs name a subscription by part of its key hash. Its endpoint is enough, with the VAPID key, to
// push to that browser, so it is cut out of any message logged: a push service's reason for
// refusing (a VAPID key mismatch, say) is kept, since without it a failure cannot be diagnosed.
export function redact(text, endpoint) {
  let out = String(text ?? '');
  const parts = [endpoint];
  try { const u = new URL(endpoint); parts.push(u.pathname + u.search, ...u.pathname.split('/'), ...u.searchParams.values()); } catch { /* not a URL */ }
  for (const part of parts.filter((x) => typeof x === 'string' && x.length >= 8).sort((a, b) => b.length - a.length)) out = out.split(part).join('<endpoint>');
  return out.replace(/\s+/g, ' ').trim().slice(0, 200);   // after cutting, so a cut cannot leave half an endpoint
}

// Email alerts (email.js), when set up, ride on the same run: the spots that rose are found once,
// below, and queued for push and email together; then email sends its own next batch, checked
// against the same alerts.json. Its queue is separate because it drains more slowly (the email
// service's daily allowance), and a slow email queue must not hold back the next push alerts.
export async function runCron(env, { fetch = globalThis.fetch, log = console.log, now = Date.now } = {}) {
  const seen = {};
  const result = await runPush(env, { fetch, log, now }, seen);
  // Not in the run that queued them: the queue was just written, and KV allows one write a second to a key.
  if (seen.alerts && emailOn(env) && !seen.emailsQueued) Object.assign(result, await drainEmails(env, seen.alerts, seen.expires, { fetch, log, now }));
  return result;
}

async function runPush(env, { fetch, log, now }, seen) {
  const authorize = vapidSigner(env); // fails on bad config every run, not only when a spot rises
  const configured = Number(env.SENDS_PER_RUN);
  const perRun = Number.isSafeInteger(configured) && configured > 0 ? configured : SENDS_PER_RUN;
  const tally = { sent: 0, removed: 0, failed: 0 };
  const queued = await env.PUSH.get('queue', 'json');
  const t = now();
  // Revalidate even while draining: a queued warning must not outlive a newer lower forecast.
  const res = await fetch(`${env.SITE_URL}data/alerts.json?t=${Math.floor(t / 60000)}`, { signal: AbortSignal.timeout(15000) });
  if (!res.ok) throw new Error(`alerts.json: HTTP ${res.status}`);
  const alerts = await res.json();
  if (typeof alerts?.generated_at !== 'string' || !isObject(alerts.spots)) throw new Error('alerts.json: unexpected shape');
  const issued = Date.parse(alerts.generated_at), expires = forecastExpiry(alerts.generated_at);
  if (!Number.isFinite(issued) || issued > t + 5 * 60e3) throw new Error('alerts.json: invalid or future issue time');
  Object.assign(seen, { alerts, expires });
  if (queued?.items?.length) {
    const state = await env.PUSH.get('state', 'json');
    const checkpointAt = Date.parse(queued.state?.generated_at);
    if (issued < checkpointAt || issued < Date.parse(state?.generated_at)) throw new Error('alerts.json: issue time moved backwards');
    if (queued.state && (!state || Date.parse(state.generated_at) < checkpointAt)) {
      await env.PUSH.put('state', JSON.stringify(queued.state));
    }
    // An expired forecast (8 hours old, or past UK midnight, when "today" in its wording has
    // passed) pauses the queue rather than ending it: every alert is checked against the forecast
    // of the run that sends it, so the next fresh forecast decides what still goes out, in its words.
    if (expires <= t) {
      log(`cron: forecast expired; ${queued.items.length} alerts wait for the next one`);
      return { risen: [], ...tally, queued: queued.items.length };
    }
    return drain(env, queued, perRun, authorize, tally, { fetch, log, now, alerts, expires });
  }
  if (expires <= t) {
    log('cron: forecast expired; nothing compared or sent');
    return { risen: [], ...tally, queued: 0 };
  }
  // A run whose alerts send and queue nothing: on a Thursday evening its sends go to the weekly note.
  const quiet = async (result) => {
    const weekly = await runWeekly(env, alerts, { log, now, perRun,
      deliver: (batch, messageFor, counts) => send(env, batch, authorize, counts, { fetch, log, now, alerts, expires, messageFor }) });
    return weekly ? { ...result, weekly } : result;
  };

  const prev = await env.PUSH.get('state', 'json');
  if (issued < Date.parse(prev?.generated_at)) throw new Error('alerts.json: issue time moved backwards');
  if (prev?.generated_at === alerts.generated_at) {
    log(`cron: alerts.json unchanged (${alerts.generated_at})`);
    return quiet({ risen: [], ...tally, queued: 0 });
  }
  const ranks = {};
  for (const [id, spot] of Object.entries(alerts.spots)) ranks[id] = Number.isInteger(spot?.rank) ? spot.rank : -1;

  const alerted = Object.fromEntries(Object.entries(prev?.alerted ?? {}).filter(([, at]) => t - Date.parse(at) < QUIET_MS));
  // Each spot's level on each day (dates.js): what the next build's days are compared with.
  const days = dayLevels(alerts, prev?.days);
  let risen = [], items = [], tidy = [];
  if (!prev) {
    // A first run has nothing to compare with; alerting now would alert everyone.
    log(`cron: first run, saved ranks for ${Object.keys(ranks).length} spots, sent nothing`);
  } else {
    risen = Object.keys(ranks).filter((id) => ranks[id] >= HIGH && (prev.ranks?.[id] ?? -1) < HIGH && !alerted[id]);
    for (const id of risen) alerted[id] = new Date(t).toISOString();
    const news = dateNews(alerts, prev.days);
    if (risen.length || news.size) ({ items, tidy } = await queueFor(env, alerts, new Set(risen), news, londonToday(t), tally, log));
    // Before the state below, like the push queue: if the state is not written, the rise is found
    // again next run, and queueEmails merges it with what is already queued for each address.
    if (risen.length && emailOn(env)) seen.emailsQueued = await queueEmails(env, alerts, new Set(risen));
    const dated = items.filter((x) => x.dates).length;
    log(`cron: ${alerts.generated_at}: ${risen.length} spots rose to high, ${items.length - dated} alerts to send${dated ? `, ${dated} date notices` : ''}${seen.emailsQueued ? `, ${seen.emailsQueued} emails queued` : ''}`);
  }
  const state = { generated_at: alerts.generated_at, ranks, ...(Object.keys(alerted).length ? { alerted } : {}), ...(Object.keys(days).length ? { days } : {}) };
  // Persist the complete queue BEFORE advancing the comparison state. If this write fails,
  // the previous ranks remain and the next run can discover the rise again. Sending begins
  // next run: putting and then checkpointing the same KV key within a second is rate-limited.
  if (items.length) await env.PUSH.put('queue', JSON.stringify({ items, state }));
  await env.PUSH.put('state', JSON.stringify(state));
  if (tidy.length) await forgetPast(env, tidy, t, log);
  if (!items.length) return quiet({ risen, ...tally, queued: 0 });
  return { risen, ...tally, queued: items.length };
}

// One alert per subscriber of a risen spot, [{key, spots}], and one notice per subscriber with a
// date that is news (dates.js), [{key, dates: [{spot, date, from}]}]. The spots and dates come
// from each key's metadata; a record without them (too many to fit) is read. Also the records that
// still hold a date before today, to forget it (tidy), at most TIDY_PER_RUN a run.
async function queueFor(env, alerts, risen, news, today, tally, log) {
  const items = [], tidy = [];
  for (const { name: key, metadata } of await listKeys(env.PUSH, 'sub:')) {
    let spots = metadata?.s, dates = (Array.isArray(metadata?.d) ? metadata.d : []).map((p) => { const [spot, date] = String(p).split(' '); return { spot, date }; });
    if (!Array.isArray(spots)) {
      const record = await env.PUSH.get(key, 'json').catch(() => null);
      if (record && !isPushService(record.subscription?.endpoint)) {
        await env.PUSH.delete(key); // stored before its host was dropped from the list
        tally.removed++;
        log(`push ${key.slice(4, 16)}: removed, push service not allowed`);
        continue;
      }
      spots = record?.spots ?? [];
      dates = datesOf(record);
    }
    const hits = spots.filter((id) => risen.has(id));
    if (hits.length) items.push({ key, spots: Object.fromEntries(hits.map(id => [id, alerts.spots[id]])) });
    const told = dates.filter((d) => news.has(pairKey(d.spot, d.date))).map((d) => ({ ...d, from: news.get(pairKey(d.spot, d.date)) }));
    if (told.length) items.push({ key, dates: told });
    if (tidy.length < TIDY_PER_RUN && dates.some((d) => d.date < today)) tidy.push(key);
  }
  return { items, tidy };
}

// Rewrites each record without its dates before today, or deletes it if nothing is left. After
// `state`, and on its own: a failure here is logged and tried again at the next build with news.
async function forgetPast(env, keys, t, log) {
  const today = londonToday(t);
  for (const key of keys) {
    try {
      const record = await env.PUSH.get(key, 'json');
      if (!record) continue;
      const dates = datesOf(record).filter((d) => d.date >= today), spots = Array.isArray(record.spots) ? record.spots : [];
      if (!spots.length && !dates.length) await env.PUSH.delete(key);
      else await putRecord(env, key, { subscription: record.subscription, spots, weekly: record.weekly === true, dates }, () => t);
    } catch (err) { log(`push ${key.slice(4, 16)}: dates not tidied: ${err?.message}`); }
  }
  log(`dates: forgot past dates in ${keys.length} records`);
}

// Sends the first perRun alerts and keeps the rest in 'queue' for the next runs.
async function drain(env, queued, perRun, authorize, tally, { fetch, log, now, alerts, expires }) {
  const batch = [], rest = [], at = now();
  for (const item of queued.items) {
    if ((item.next_attempt ?? 0) <= at && batch.length < perRun) batch.push(item);
    else rest.push(item);
  }
  const alert = alertFor(alerts, env.SITE_URL), date = dateFor(alerts, env.SITE_URL);
  const messageFor = (record, item) => (item.dates ? date(record, item) : alert(record, item));
  const kept = await send(env, batch, authorize, tally, { fetch, log, now, alerts, expires, messageFor });
  rest.push(...kept); // retries do not block recipients who have not had an attempt yet
  if (rest.length) await env.PUSH.put('queue', JSON.stringify({ ...queued, items: rest }));
  else await env.PUSH.delete('queue');
  log(`cron: sent ${tally.sent}, removed ${tally.removed}, failed ${tally.failed}; ${rest.length} still queued`);
  return { risen: [], ...tally, queued: rest.length };
}

// An alert for a queued item, from this run's forecast: only the spots still saved and still high.
const alertFor = (alerts, siteUrl) => (record, { spots }) => {
  const ids = Object.keys(spots ?? {}).filter(id => record.spots?.includes(id) && alerts.spots[id]?.rank >= HIGH);
  return ids.length ? alertPayload(ids, alerts.spots, siteUrl) : null;
};

// Returns the alerts to keep in the queue: retries, and any the forecast expired under. messageFor
// makes each one's title, body, link and tag from the record, or null when there is nothing to say
// any more: an alert (alertFor) or the weekly note (weekly.js).
async function send(env, batch, authorize, tally, { fetch, log, now, alerts, expires, messageFor }) {
  const kept = [];
  const fail = (key, why) => { tally.failed++; log(`push ${key.slice(4, 16)}: ${why}`); };
  await eachLimit(batch, CONCURRENCY, async item => {
    const { key } = item;
    const attempt = (item.attempts ?? 0) + 1;
    const retry = (after = 0) => {
      const at = now(), next = nextAttempt(attempt, at, after);
      if (attempt >= MAX_ATTEMPTS) log(`push ${key.slice(4, 16)}: given up after ${attempt} attempts`);
      else if (next - at > MAX_RETRY_WAIT) log(`push ${key.slice(4, 16)}: given up, the push service asked for a wait of over an hour`);
      else kept.push({ ...item, attempts: attempt, next_attempt: next });
    };
    let endpoint;
    try {
      let record;
      try { record = await env.PUSH.get(key, 'json'); }
      catch { fail(key, 'subscription read unavailable'); retry(); return; }
      if (!record) return;
      endpoint = record.subscription?.endpoint;
      const message = messageFor(record, item);
      if (!message) return;
      if (!isPushService(endpoint)) {
        await env.PUSH.delete(key); tally.removed++; return;
      }
      const ttl = Math.floor((expires - now()) / 1000);
      if (ttl <= 0) { kept.push(item); return; }   // expired during this run: waits like the rest
      const payload = { ...message, issued_at: alerts.generated_at, expires_at: new Date(expires).toISOString() };
      // Retry only transient transport/service failures. A malformed subscription or encryption
      // error is permanent and must not keep consuming delivery attempts.
      let res;
      try { res = await sendPush(record.subscription, payload, authorize, { fetch: async (...args) => {
        try { return await fetch(...args); } catch (err) { throw new TransportError(err?.message); }
      }, ttl }); }
      catch (err) { if (err instanceof TransportError) { fail(key, `network failure: ${redact(err.message, endpoint)}`); retry(); return; } throw err; }
      const status = res.status, after = retryAfter(res.headers.get('Retry-After'), now());
      if (status === 404 || status === 410) {
        await res.body?.cancel();
        await env.PUSH.delete(key); tally.removed++;
      } else if (res.ok) {
        await res.body?.cancel();
        tally.sent++;
      } else {
        const why = redact(await res.text().catch(() => ''), endpoint);
        fail(key, `HTTP ${status}${why ? `: ${why}` : ''}`);
        if (status === 408 || status === 429 || status >= 500) retry(after);
      }
    } catch (err) {
      fail(key, redact(err?.message || 'failed', endpoint));
    }
  });
  return kept;
}
class TransportError extends Error {}

async function eachLimit(items, limit, fn) {
  let next = 0;
  const lane = async () => { while (next < items.length) await fn(items[next++]); };
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, lane));
}

// One spot: its headline, then what to do (levels.js levelAction, `action` in alerts.json), as the page
// says them under the level; the site's worker adds the issue time. The headline comes first: Android
// shows about one line until the notification is opened, an iPhone's lock screen about four. An
// alerts.json from before 4 Oct 2026 has no action. Several spots: their names, since each has its own line.
export function alertPayload(ids, spots, siteUrl) {
  if (ids.length === 1) {
    const [id] = ids;
    const spot = spots[id];
    const body = spot.headline && spot.action ? `${spot.headline}. ${spot.action}` : spot.headline ?? '';
    return { title: spot.name ?? id, body, url: spot.url ?? `${siteUrl}spot/${id}/`, tag: `dipspot-${id}` };
  }
  const names = ids.map((id) => spots[id].name ?? id).join(', ');
  return {
    title: `${ids.length} of your saved spots are at high or very high risk`,
    body: names.length > 200 ? names.slice(0, 199) + '…' : names,
    url: `${siteUrl}saved/`,
    tag: 'dipspot-saved',
  };
}
