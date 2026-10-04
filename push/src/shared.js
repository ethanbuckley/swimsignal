// What push (index.js) and email (email.js) share: the checks on what a page sends, and the rules
// for when an alert may go out. Whether a spot has just risen is decided once a run, in index.js,
// and both queues are filled from that one decision; at sending, both check the latest forecast
// with the same rank (HIGH) and the same expiry, so the two can never disagree.

import { concat } from './webpush.js';

const MAX_BODY = 8 * 1024;
export const MAX_SPOTS = 100;
const SPOT_ID = /^[A-Za-z0-9_-]{1,80}$/;
export const HIGH = 2;

export class Invalid extends Error {}
export const check = (ok, reason) => { if (!ok) throw new Invalid(reason); };
export const isObject = (v) => typeof v === 'object' && v !== null && !Array.isArray(v);
export const reply = (status, text, headers = {}) =>
  new Response(text, { status, headers: { 'Content-Type': 'text/plain; charset=utf-8', ...headers } });

// Reads at most max bytes, so an oversized body is refused without buffering it.
export async function readText(request, max = MAX_BODY) {
  check(!(Number(request.headers.get('Content-Length')) > max), 'Body too large');
  const chunks = [];
  let size = 0;
  const reader = request.body?.getReader();
  while (reader) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > max) { await reader.cancel(); throw new Invalid('Body too large'); }
    chunks.push(value);
  }
  return new TextDecoder().decode(concat(...chunks));
}
export async function readJson(request) {
  const text = await readText(request);
  try { return JSON.parse(text); } catch { throw new Invalid('Body is not JSON'); }
}

export function cleanSpots(spots) {
  check(Array.isArray(spots), 'spots must be an array');
  check(spots.length <= MAX_SPOTS, `at most ${MAX_SPOTS} spots`);
  check(spots.every((s) => typeof s === 'string' && SPOT_ID.test(s)), 'bad spot id');
  check(new Set(spots).size === spots.length, 'duplicate spot id');
  return spots;
}

export const MAX_FORECAST_AGE = 8 * 3600e3; // same freshness limit as the site's warning
const londonDate = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' });
const londonOffset = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', timeZoneName: 'shortOffset' });

export function forecastExpiry(issued) {
  const at = Date.parse(issued);
  if (!Number.isFinite(at)) return NaN;
  const parts = Object.fromEntries(londonDate.formatToParts(at).map(p => [p.type, p.value]));
  const midnight = Date.UTC(+parts.year, +parts.month - 1, +parts.day + 1);
  // At 00:00 UTC the offset still matches the approaching local midnight on both DST changes.
  const offset = londonOffset.formatToParts(midnight).find(p => p.type === 'timeZoneName').value === 'GMT+1' ? 3600e3 : 0;
  return Math.min(at + MAX_FORECAST_AGE, midnight - offset);
}

export async function listKeys(kv, prefix) {
  const keys = [];
  let cursor;
  do {
    const page = await kv.list({ prefix, cursor });
    keys.push(...page.keys);
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return keys;
}

export function retryAfter(value, at) {
  if (!value) return 0;
  const seconds = Number(value);
  const time = Number.isFinite(seconds) ? at + Math.max(0, seconds) * 1000 : Date.parse(value);
  return Number.isFinite(time) ? time : 0;
}

// A queued alert's next try: 2, 4, then 8 minutes after this one, or later if the service asked.
export const MAX_ATTEMPTS = 4;
// A service's Retry-After longer than this gives that alert up: while anything is queued, no new
// rise is looked for, so one slow recipient must not hold everyone else's next alert.
export const MAX_RETRY_WAIT = 3600e3;
export const nextAttempt = (attempt, at, after = 0) => Math.max(at + 120000 * 2 ** (attempt - 1), after);
