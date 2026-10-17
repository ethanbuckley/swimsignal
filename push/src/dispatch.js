// The site's build, started from here (docs/REVIEW-2026-10-16.md, task B1). GitHub treats the
// workflow's own half-hourly schedule as best effort: 289 runs in 29 days against 1,392 asked
// (20.8%), a median gap of 2 h and a longest of 7.7 h, and a day with a gap over 8 h is dropped from
// the scores (8 and 9 Oct 2026). Every 30 minutes this asks GitHub to run site.yml now, unless a
// build started under 20 minutes ago. GitHub's schedule stays as the fallback, and the workflow's
// `concurrency: site` keeps the runs one at a time.
//
// The token (GITHUB_DISPATCH_TOKEN, a Worker secret) is a fine-grained one with Actions: write on
// this repository alone: it can start, cancel and re-run workflows, and read and delete their logs,
// but not change code (README, "Starting the site's build"). Unset, this does nothing.

export const DISPATCH_CRON = '*/30 * * * *';   // as written in wrangler.toml: the scheduled event names its cron
export const FRESH_MS = 20 * 60e3;             // a build that started this recently is not asked for again
// DISPATCH_FRESH_MIN in wrangler.toml's [vars] changes that: 50 asks about once an hour, not twice
// (README, "What it costs": each build asks Open-Meteo for rain, and the free tier is 10,000 calls a day).
const freshMs = (env) => { const m = Number(env.DISPATCH_FRESH_MIN); return Number.isFinite(m) && m > 0 ? m * 60e3 : FRESH_MS; };
const REPO = 'ethanbuckley/swimsignal', WORKFLOW = 'site.yml', REF = 'main';
const API = 'https://api.github.com';

// Returns what it did, for the log and the tests: {dispatched} or {skipped: why}. Throws when GitHub
// refuses, so the run shows as failed in the Worker's cron events (an expired token, say).
export async function runDispatch(env, { fetch = globalThis.fetch, log = console.log, now = Date.now } = {}) {
  const token = env.GITHUB_DISPATCH_TOKEN;
  if (!token) {
    log('dispatch: GITHUB_DISPATCH_TOKEN not set; GitHub\'s own schedule only');
    return { skipped: 'no token' };
  }
  const t = now(), age = await buildAge(env, t, { fetch, log });
  if (age !== null && age < freshMs(env)) {
    log(`dispatch: the last build started ${Math.round(age / 60e3)} min ago; not asked`);
    return { skipped: 'fresh', age_min: Math.round(age / 60e3) };
  }
  const res = await fetch(`${API}/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'swimsignal-push',   // GitHub refuses a request without one
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ ref: REF }),
    signal: AbortSignal.timeout(15000),
  });
  if (!res.ok) {
    const why = (await res.text().catch(() => '')).replace(/\s+/g, ' ').slice(0, 200);
    const hint = res.status === 401 ? ': the token has expired or was deleted; make a new one (README)'
      : res.status === 403 || res.status === 404 ? ': the token lacks Actions: write on this repository, or the workflow moved (README)'
      : res.status === 422 ? ': site.yml has no workflow_dispatch trigger' : '';
    log(`dispatch: HTTP ${res.status}${hint}${why ? ` (${why})` : ''}`);
    throw new Error(`dispatch: HTTP ${res.status}${hint}`);
  }
  await res.body?.cancel();
  log(`dispatch: site.yml asked to run${age === null ? ' (the last build\'s time could not be read)' : `; the last build started ${Math.round(age / 60e3)} min ago`}`);
  return { dispatched: true, ...(age === null ? {} : { age_min: Math.round(age / 60e3) }) };
}

// How long ago the live site's build started, from data/spots-lite.json's generated_at (build_site
// sets it as the forecasts are made, a few minutes before the pages go live), or null when that
// cannot be read: then the build is asked for anyway, since a site that cannot be read needs one most.
// generated_at is the file's first field, so only its first few KB are read: the whole file (434 KB on
// 16 Oct 2026) would take much of the free plan's 10 ms of CPU to parse.
const HEAD_BYTES = 4096;
async function buildAge(env, t, { fetch, log }) {
  try {
    const res = await fetch(`${env.SITE_URL}data/spots-lite.json?t=${Math.floor(t / 60000)}`, { signal: AbortSignal.timeout(15000) });
    if (!res.ok) { await res.body?.cancel(); throw new Error(`HTTP ${res.status}`); }
    const at = Date.parse(firstField(await head(res, HEAD_BYTES), 'generated_at'));
    if (!Number.isFinite(at)) throw new Error('no generated_at near its start');
    return Math.max(0, t - at);
  } catch (err) {
    log(`dispatch: spots-lite.json: ${err?.message || err}`);
    return null;
  }
}

// The first `bytes` of a response's body as text; the rest is not downloaded.
async function head(res, bytes) {
  if (!res.body) return '';
  const reader = res.body.getReader(), parts = [];
  let n = 0;
  while (n < bytes) {
    const { done, value } = await reader.read();
    if (done) break;
    parts.push(value); n += value.length;
  }
  await reader.cancel().catch(() => {});
  const all = new Uint8Array(n); let at = 0;
  for (const p of parts) { all.set(p, at); at += p.length; }
  return new TextDecoder().decode(all.subarray(0, bytes));
}

// A top-level string field near the start of a JSON text, "name":"value" (build_site writes it with
// no spaces, json.dumps with separators), or undefined.
export function firstField(text, name) {
  const m = text.match(new RegExp(`^\\{\\s*"${name}"\\s*:\\s*"([^"\\\\]*)"`));
  return m ? m[1] : undefined;
}
