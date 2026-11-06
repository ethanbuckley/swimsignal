// SwimSignal river-rises shadow logger (docs/RIVER-RISES-C3-2026-11.md, "The shadow log"). Once an hour it
// records, as published at that hour, the EA levels of the research run's gauges and the list of Met Office
// radar composites, for an offline evaluation later. It makes no prediction and publishes nothing: no page,
// no endpoint (every request gets 404), no Open-Meteo call. Not part of the site or the push Worker.

import { MEASURE_IDS } from './measures.js';

export const WORKER_VERSION = 'river-shadow/1';

const EA_HOST = 'environment.data.gov.uk';
const RADAR_HOST = 'met-office-radar-obs-data.s3.amazonaws.com';
const HOSTS = new Set([EA_HOST, RADAR_HOST]);
// The EA's own advice for bulk use: one call for every latest level reading, not one a station.
export const EA_URL = `https://${EA_HOST}/flood-monitoring/data/readings?latest&parameter=level`;
export const RADAR_URL = (date) =>
  `https://${RADAR_HOST}/?list-type=2&prefix=radar/${date.slice(0, 4)}/${date.slice(5, 7)}/${date.slice(8, 10)}/&max-keys=1000`;

export const MAX_REQUESTS = 3;            // the EA call and at most two day listings
export const TIMEOUT_MS = 20_000;
export const EA_MAX_BYTES = 8 * 1024 * 1024;       // the answer was 1.3 MB on 26 Oct 2026
export const LIST_MAX_BYTES = 2 * 1024 * 1024;     // a day is 96 keys, about 35 kB
export const STOP_AFTER = 6;              // consecutive failed runs, then nothing until a person clears the stop
export const WINDOW_H = 3;                // radar composites in (issue - 3 h, issue]
const HOUR_MS = 3_600_000;
const HEADERS = { 'User-Agent': 'swimsignal-river-shadow (+https://github.com/ethanbuckley/swimsignal; hello@swimsignal.co.uk)' };

export const KEY_STOPPED = 'state/stopped';
export const KEY_FAILURES = 'state/failures';
export const hourKey = (issue) => `h/${issue}`;

const WANT = new Set(MEASURE_IDS);
const measureId = (uri) => String(uri ?? '').replace(/\/+$/, '').split('/').pop();

export default {
  fetch: () => new Response('Not found', { status: 404 }),
  // Workers passes (controller, env, ctx); ctx is not deps.
  scheduled: (controller, env) => scheduled(controller, env),
};

// The run's UTC hour, as "2026-12-01T13:00:00Z".
export function issueHour(ms) {
  return new Date(Math.floor(ms / HOUR_MS) * HOUR_MS).toISOString().replace('.000Z', 'Z');
}

export async function scheduled(controller, env, deps = {}) {
  const now = deps.now ?? Date.now;
  const kv = env.SHADOW;
  const issue = issueHour(controller?.scheduledTime ?? now());
  if (await kv.get(KEY_STOPPED) !== null) return { skipped: 'stopped', issue };
  if (await kv.get(hourKey(issue)) !== null) return { skipped: 'duplicate', issue };

  const get = guardedFetch(deps.fetch ?? fetch, deps.timeoutMs ?? TIMEOUT_MS);
  const urls = { ea: deps.eaUrl ?? EA_URL, radar: deps.radarUrl ?? RADAR_URL };
  const issueMs = Date.parse(issue);

  const ea = await readEa(get, urls.ea);
  const days = [issue.slice(0, 10)];
  if (new Date(issueMs).getUTCHours() < WINDOW_H) days.unshift(new Date(issueMs - 86_400_000).toISOString().slice(0, 10));
  const radar = await readRadar(get, days.map(urls.radar), issueMs);

  const record = {
    schema: 'swimsignal.river-shadow.hour', version: 1, issue, fetched_at: new Date(now()).toISOString(),
    worker_version: WORKER_VERSION, n_requests: get.count(), ea, radar,
  };
  await kv.put(hourKey(issue), JSON.stringify(record));

  const failed = ea.error !== null || radar.error !== null;
  const prev = await readFailures(kv);
  if (!failed) {
    if (prev.count !== 0) await kv.put(KEY_FAILURES, JSON.stringify({ count: 0, recent: [] }));
    return { issue, ok: true };
  }
  const recent = [...prev.recent, { issue, ea: ea.error, radar: radar.error }].slice(-STOP_AFTER);
  const count = prev.count + 1;
  if (count >= STOP_AFTER) {
    await kv.put(KEY_STOPPED, JSON.stringify({ at: record.fetched_at, reason: `${count} consecutive failed runs`, last_errors: recent }));
    // A fresh count once a person clears the stop.
    await kv.put(KEY_FAILURES, JSON.stringify({ count: 0, recent: [] }));
    return { issue, ok: false, stopped: true };
  }
  await kv.put(KEY_FAILURES, JSON.stringify({ count, recent }));
  return { issue, ok: false };
}

async function readFailures(kv) {
  try {
    const v = JSON.parse(await kv.get(KEY_FAILURES) ?? 'null');
    if (v && Number.isInteger(v.count) && v.count >= 0) return { count: v.count, recent: Array.isArray(v.recent) ? v.recent : [] };
  } catch { /* a person's edit; counted afresh */ }
  return { count: 0, recent: [] };
}

// fetch with the rules: allowlisted https hosts, no redirects followed, a timeout, a size cap, a cap on the
// number of requests a run, never a retry. Answers { status, bytes, text, error }; never throws.
export function guardedFetch(fetchFn, timeoutMs) {
  let n = 0;
  const get = async (url, maxBytes) => {
    let u;
    try { u = new URL(url); } catch { return fail(null, 'bad url'); }
    if (u.protocol !== 'https:' || !HOSTS.has(u.hostname) || u.port !== '' || u.username || u.password) {
      return fail(null, `host not allowed: ${u.protocol}//${u.host}`);
    }
    if (n >= MAX_REQUESTS) return fail(null, 'request cap reached');
    n++;
    try {
      const res = await fetchFn(u.toString(), { method: 'GET', redirect: 'manual', headers: HEADERS, signal: AbortSignal.timeout(timeoutMs) });
      if (res.status >= 300 && res.status < 400) return fail(res.status, `redirect ${res.status}`);
      if (res.status !== 200) return fail(res.status, `http ${res.status}`);
      const declared = Number(res.headers.get('content-length'));
      if (declared > maxBytes) return fail(res.status, `oversize: content-length ${declared}`);
      const { text, bytes, over } = await readCapped(res, maxBytes);
      if (over) return fail(res.status, `oversize: over ${maxBytes} bytes`, bytes);
      return { status: res.status, bytes, text, error: null };
    } catch (e) {
      const name = e?.name ?? '';
      return fail(null, name === 'TimeoutError' || name === 'AbortError' ? 'timeout' : `fetch failed: ${String(e?.message ?? e).slice(0, 200)}`);
    }
  };
  get.count = () => n;
  return get;
}

const fail = (status, error, bytes = 0) => ({ status, bytes, text: null, error });

// The body as text, stopping as soon as it passes maxBytes (the size of the text, after any decompression).
async function readCapped(res, maxBytes) {
  if (!res.body) {
    const text = await res.text();
    const bytes = new TextEncoder().encode(text).length;
    return { text, bytes, over: bytes > maxBytes };
  }
  const reader = res.body.getReader();
  const chunks = [];
  let bytes = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    bytes += value.byteLength;
    if (bytes > maxBytes) {
      await reader.cancel().catch(() => {});
      return { text: null, bytes, over: true };
    }
    chunks.push(value);
  }
  const all = new Uint8Array(bytes);
  let at = 0;
  for (const c of chunks) { all.set(c, at); at += c.byteLength; }
  return { text: new TextDecoder().decode(all), bytes, over: false };
}

async function readEa(get, url) {
  const r = await get(url, EA_MAX_BYTES);
  const out = { status: r.status, bytes: r.bytes, error: r.error, n_items_total: null, items: [] };
  if (r.error) return out;
  try {
    const { total, items } = filterReadings(r.text);
    out.n_items_total = total;
    out.items = items;
  } catch (e) {
    out.error = `parse: ${String(e?.message ?? e).slice(0, 200)}`;
  }
  return out;
}

// The EA answer's items whose measure is one of ours, as { measure, dateTime, value } (value as published).
export function filterReadings(text) {
  const doc = JSON.parse(text);
  if (!doc || !Array.isArray(doc.items)) throw new Error('no items list');
  const items = [];
  for (const it of doc.items) {
    if (it && typeof it === 'object' && WANT.has(measureId(it.measure))) {
      items.push({ measure: it.measure, dateTime: it.dateTime ?? null, value: it.value ?? null });
    }
  }
  return { total: doc.items.length, items };
}

async function readRadar(get, urls, issueMs) {
  const listings = [];
  const keys = [];
  for (const url of urls) {
    const r = await get(url, LIST_MAX_BYTES);
    const one = { url, status: r.status, bytes: r.bytes, error: r.error, n_keys: null, truncated: null };
    if (!r.error) {
      try {
        const parsed = parseListing(r.text);
        one.n_keys = parsed.contents.length;
        one.truncated = parsed.truncated;
        keys.push(...inWindow(parsed.contents, issueMs));
      } catch (e) {
        one.error = `parse: ${String(e?.message ?? e).slice(0, 200)}`;
      }
    }
    listings.push(one);
  }
  const bad = listings.find((l) => l.error !== null);
  return {
    status: bad ? bad.status : 200,
    bytes: listings.reduce((s, l) => s + l.bytes, 0),
    error: bad ? bad.error : null,
    keys,
    listings,
  };
}

const unxml = (s) => s.replace(/&(quot|amp|lt|gt|apos|#(\d+)|#x([0-9a-fA-F]+));/g, (m, name, dec, hex) =>
  dec ? String.fromCodePoint(Number(dec)) : hex ? String.fromCodePoint(parseInt(hex, 16))
    : { quot: '"', amp: '&', lt: '<', gt: '>', apos: "'" }[name]);
const tag = (block, name) => {
  const m = block.match(new RegExp(`<${name}>([\\s\\S]*?)</${name}>`));
  return m ? unxml(m[1].trim()) : null;
};

// An S3 ListObjectsV2 answer: its <Contents> entries and whether it was cut short. No dependencies.
export function parseListing(xml) {
  if (typeof xml !== 'string' || !/<ListBucketResult[\s>]/.test(xml)) throw new Error('not a ListBucketResult');
  const contents = [];
  for (const m of xml.matchAll(/<Contents>([\s\S]*?)<\/Contents>/g)) {
    const size = tag(m[1], 'Size');
    contents.push({ key: tag(m[1], 'Key'), size: size === null ? null : Number(size), last_modified: tag(m[1], 'LastModified'), etag: tag(m[1], 'ETag') });
  }
  return { contents, truncated: tag(xml, 'IsTruncated') === 'true' };
}

const KEY_RE = /^radar\/\d{4}\/\d{2}\/\d{2}\/(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})_ODIM_ng_radar_rainrate_composite_1km_UK\.h5$/;

// The composites whose time, from the name, is in (issue - 3 h, issue].
export function inWindow(contents, issueMs) {
  const lo = issueMs - WINDOW_H * HOUR_MS;
  const out = [];
  for (const c of contents) {
    const m = KEY_RE.exec(c.key ?? '');
    if (!m) continue;
    const t = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]);
    if (t > lo && t <= issueMs) out.push(c);
  }
  return out;
}
