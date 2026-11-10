// SwimSignal's action counter (README). It adds one to a day's total when a page says an action happened,
// and keeps nothing else: no IP address, no user agent, no cookie, no identifier of any kind. A request
// carries an action's name and, for some actions, a spot's id; that is all it reads.
//
// One KV key a UTC day, d/YYYY-MM-DD. Two things keep it inside the free plan's KV writes (1,000 a day,
// which the push Worker and the river-shadow logger share):
//   - each isolate gathers what it is sent for FLUSH_MS and writes once, so a visitor who opens a spot,
//     picks a day and saves it costs one write, not three;
//   - a day's record counts its own writes, and once it reaches WRITE_CAP no more are made that day. The
//     day is then marked capped in what GET returns, so a total read from it is a floor, not a count.

export const EVENTS = ['spot', 'day', 'save', 'plan', 'alerts'];
const WITH_SPOT = new Set(['spot', 'day', 'save']);
const SPOT_ID = /^[A-Za-z0-9_-]{1,80}$/;
export const WRITE_CAP = 300;     // KV writes a UTC day for this Worker (README, "Writes")
export const MAX_SPOTS = 1000;    // distinct spots a day's record keeps counts for; the totals go on past it
export const FLUSH_MS = 5000;
const MAX_BODY = 300;             // bytes; a real one is under 60
const MAX_DAYS = 92;

const dayOf = (ms) => new Date(ms).toISOString().slice(0, 10);
const key = (day) => `d/${day}`;

// What this isolate has been sent and not yet written, by day: {counts: {event: n}, spots: {id: {event: n}}}.
let pending = new Map();
let flushing = null;
const capped = new Set();         // days this isolate has seen at the cap: nothing more is gathered for them

export function resetForTests() { pending = new Map(); flushing = null; capped.clear(); }

// The body, or null. Text, not JSON's content type, so sendBeacon needs no preflight.
export function parseEvent(text) {
  if (typeof text !== 'string' || text.length > MAX_BODY) return null;
  let o; try { o = JSON.parse(text); } catch { return null; }
  if (!o || typeof o !== 'object' || !EVENTS.includes(o.event)) return null;
  const spot = WITH_SPOT.has(o.event) && typeof o.spot_id === 'string' && SPOT_ID.test(o.spot_id) ? o.spot_id : null;
  return { event: o.event, spot };
}

// Adds counts in the shape above into another of the same shape.
function merge(into, add) {
  for (const [e, n] of Object.entries(add.counts)) into.counts[e] = (into.counts[e] || 0) + n;
  for (const [id, by] of Object.entries(add.spots)) {
    const s = into.spots[id] || (into.spots[id] = {});
    for (const [e, n] of Object.entries(by)) s[e] = (s[e] || 0) + n;
  }
}

function gather(day, { event, spot }) {
  const p = pending.get(day) || { counts: {}, spots: {} };
  merge(p, { counts: { [event]: 1 }, spots: spot ? { [spot]: { [event]: 1 } } : {} });
  pending.set(day, p);
}

// Adds what was gathered to each day's record: one read and at most one write a day.
export async function flush(env) {
  const work = pending; pending = new Map();
  for (const [day, add] of work) {
    try {
      const rec = JSON.parse(await env.COUNTS.get(key(day)) || 'null') || { counts: {}, spots: {}, writes: 0 };
      if (rec.writes >= WRITE_CAP) { capped.add(day); continue; }
      for (const [e, n] of Object.entries(add.counts)) rec.counts[e] = (rec.counts[e] || 0) + n;
      let distinct = Object.keys(rec.spots).length;
      for (const [id, by] of Object.entries(add.spots)) {
        if (!rec.spots[id]) { if (distinct >= MAX_SPOTS) continue; rec.spots[id] = {}; distinct++; }
        for (const [e, n] of Object.entries(by)) rec.spots[id][e] = (rec.spots[id][e] || 0) + n;
      }
      rec.writes++;
      await env.COUNTS.put(key(day), JSON.stringify(rec));
      if (rec.writes >= WRITE_CAP) capped.add(day);
    } catch {
      // KV refused (most likely a second write to the key within a second): keep it for the next flush.
      const p = pending.get(day) || { counts: {}, spots: {} };
      merge(p, add); pending.set(day, p);
    }
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function schedule(env, ctx, wait) {
  if (flushing) return;
  flushing = (async () => { await wait(); flushing = null; await flush(env); })();
  ctx.waitUntil(flushing);
}

function totals(rec) {
  if (!rec) return { counts: Object.fromEntries(EVENTS.map((e) => [e, 0])), spots: {}, writes: 0, capped: false };
  return { counts: Object.fromEntries(EVENTS.map((e) => [e, rec.counts[e] || 0])), spots: rec.spots || {},
           writes: rec.writes, capped: rec.writes >= WRITE_CAP };
}

// GET ?from=YYYY-MM-DD&to=YYYY-MM-DD (UTC days, both included; default the last 7 days to today).
async function read(url, env, now) {
  const iso = /^\d{4}-\d{2}-\d{2}$/;
  const to = url.searchParams.get('to') || dayOf(now);
  const from = url.searchParams.get('from') || dayOf(Date.parse(to + 'T00:00:00Z') - 6 * 864e5);
  if (!iso.test(from) || !iso.test(to) || Number.isNaN(Date.parse(from)) || Number.isNaN(Date.parse(to)) || from > to) {
    return json({ error: 'from and to must be dates, YYYY-MM-DD, from not after to' }, 400);
  }
  const days = [];
  for (let t = Date.parse(from + 'T00:00:00Z'); dayOf(t) <= to; t += 864e5) {
    if (days.length >= MAX_DAYS) return json({ error: `at most ${MAX_DAYS} days at once` }, 400);
    days.push(dayOf(t));
  }
  const recs = await Promise.all(days.map(async (d) => JSON.parse(await env.COUNTS.get(key(d)) || 'null')));
  return json({ events: EVENTS, write_cap: WRITE_CAP, timezone: 'UTC',
                days: days.map((d, i) => ({ date: d, ...totals(recs[i]) })) });
}

const json = (o, status = 200, headers = {}) => new Response(JSON.stringify(o), {
  status, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...headers } });

// Constant-time enough for a token of fixed length: compare every character.
function sameToken(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let d = 0; for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

export async function handle(request, env, ctx, { now = Date.now(), wait = () => sleep(FLUSH_MS) } = {}) {
  const url = new URL(request.url);
  if (url.pathname !== '/') return new Response('Not found', { status: 404 });
  if (request.method === 'POST') {
    // Only the site's own pages. A browser always sends Origin on a cross-site POST; anything can forge
    // it, which is why the totals are indicators, not proof (README).
    if (request.headers.get('Origin') !== env.ALLOWED_ORIGIN) return new Response(null, { status: 403 });
    const cors = { 'Access-Control-Allow-Origin': env.ALLOWED_ORIGIN, Vary: 'Origin' };
    const len = Number(request.headers.get('Content-Length') || 0);
    if (len > MAX_BODY) return new Response(null, { status: 413, headers: cors });
    const ev = parseEvent(await request.text());
    if (!ev) return new Response(null, { status: 400, headers: cors });
    const day = dayOf(now);
    if (!capped.has(day)) { gather(day, ev); schedule(env, ctx, wait); }
    return new Response(null, { status: 204, headers: cors });
  }
  if (request.method === 'GET') {
    // The totals are for the operator's weekly count, not the public: a secret token, or nothing.
    const auth = request.headers.get('Authorization') || '';
    if (!env.READ_TOKEN || !sameToken(auth, `Bearer ${env.READ_TOKEN}`)) return new Response('Not found', { status: 404 });
    return read(url, env, now);
  }
  return new Response(null, { status: 405, headers: { Allow: 'GET, POST' } });
}

export default { fetch: (request, env, ctx) => handle(request, env, ctx) };
