// Email alerts: the same alerts as push, by email, for people whose browser cannot take push (on an
// iPhone, push needs the site on the Home Screen). Off until MAIL_API_KEY, MAIL_HASH_KEY, EMAIL_FROM
// and WORKER_URL are all set (README.md, "Email alerts"); until then every /email/ address is 404 and
// the cron leaves email alone.
//
// Sign-up is double opt-in. The Saved page sends an address and its saved spots' ids; the Worker
// keeps them for two days as a pending request and emails a link to confirm. Nothing else is sent to
// that address until the link is opened and Confirm pressed. Confirming stores the address, the spots
// and the time (UK GDPR Article 7(1): the controller must be able to show that consent was given).
// Every alert carries an unsubscribe link and the List-Unsubscribe and List-Unsubscribe-Post headers
// (RFC 8058), and unsubscribing deletes the record at once. The emails have no images, pixels or
// redirected links, and the email service's open and click tracking stay off (README.md).
//
// When to alert is not decided here: index.js finds the spots that rose, once a run, and queues push
// and email from that one list (queueEmails). Each email is checked again against the latest
// alerts.json when it is sent, with the same rank (HIGH) and expiry as push, so the two agree.
//
// KV (the PUSH namespace, shared with push) holds, under keys that never contain an address:
//   mail:<id>     a confirmed address: { email, spots, confirmed }, the spots also in the metadata
//   pend:<id>     a request waiting for its confirmation, deleted by KV after two days
//   mailq         the alerts waiting to go, by <id> and spot, with no address in them
//   quota:<day>   how many emails went out that UTC day, for the email service's daily allowance
//   rl:ip:<hash>  sign-ups from one connection in one hour, deleted by KV after the hour
//   rl:to:<hash>  confirmation emails to one address in one day, deleted by KV after the day
// <id> and the hashes are HMAC-SHA-256 under the secret MAIL_HASH_KEY, so the keys say nothing
// without it, and the counts cannot be matched to an address or across hours and days.
//
// The email service reports, to /email/events, an email that bounced for good, one marked as spam,
// and one it would not send to an address on its suppression list; each deletes that address's
// mail:<id> and pend:<id> at once (gone). Off until MAIL_WEBHOOK_SECRET is set (README.md, step 11).

import {
  HIGH, Invalid, MAX_ATTEMPTS, MAX_RETRY_WAIT, check, cleanSpots, isObject, listKeys, nextAttempt, readJson, readText, reply,
} from './shared.js';
import { sendEmail } from './mail.js';

const PENDING_TTL = 2 * 86400;          // seconds a confirmation link works
const SIGNUPS_PER_HOUR = 5;             // from one connection
const CONFIRMS_PER_DAY = 3;             // confirmation emails to one address
// Resend's free plan: 100 emails a day, counted by UTC day, and 3,000 a month (README.md). Alerts
// stop short of the cap by CONFIRM_RESERVE, so a busy day of alerts still leaves room for sign-ups.
const DAILY_CAP = 100;
const CONFIRM_RESERVE = 20;
// A run's outgoing requests on the free plan are 50: alerts.json, up to 15 pushes (index.js), and
// these. One email is one request of a few hundred bytes of JSON, so CPU is not the limit.
const EMAILS_PER_RUN = 10;
const ID = /^[0-9a-f]{32}$/;
const PAGE_NAV = [['', 'Explore'], ['verification.html', 'Accuracy'], ['about.html', 'About'], ['feedback.html', 'Feedback']];

export const emailOn = (env) => Boolean(env.MAIL_API_KEY && env.MAIL_HASH_KEY && env.EMAIL_FROM && env.WORKER_URL);
const setting = (value, fallback) => { const n = Number(value); return Number.isSafeInteger(n) && n >= 0 ? n : fallback; };

// ---- keys and tokens ----

const hex = (bytes) => Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, '0')).join('');
const hmacKeys = new Map();
async function mac(env, text) {
  let key = hmacKeys.get(env.MAIL_HASH_KEY);
  if (!key) {
    key = await crypto.subtle.importKey('raw', new TextEncoder().encode(env.MAIL_HASH_KEY), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
    hmacKeys.set(env.MAIL_HASH_KEY, key);
  }
  return hex(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(text))).slice(0, 32);
}
export const addressId = (env, email) => mac(env, `address\n${email}`);
// The unsubscribe link's token is derived, not stored, so a link keeps working after the record has
// gone (it then says there is nothing to delete) and needs no write to make.
export const unsubscribeToken = (env, id) => mac(env, `unsubscribe\n${id}`);
export const unsubscribeUrl = async (env, id) => `${env.WORKER_URL}email/unsubscribe?id=${id}&t=${await unsubscribeToken(env, id)}`;

// Equal strings, in a time that does not depend on where they differ: both are hashed first.
async function same(a, b) {
  const digest = async (s) => new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(String(s))));
  const [x, y] = await Promise.all([digest(a), digest(b)]);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

// The connection to count: an IPv4 address whole, an IPv6 one by its first 64 bits, the block one
// home or phone is given, so that one host cannot count as millions of connections. The same rule
// as the reviews Worker (reviews/src/index.js, connectionOf).
export function connectionOf(ip) {
  const a = String(ip || '').trim().toLowerCase();
  if (!a.includes(':')) return a || 'unknown';
  if (a.includes('.')) return a.slice(a.lastIndexOf(':') + 1);   // an IPv4 address written as IPv6
  const [head, tail] = a.split('::'), h = head ? head.split(':') : [], t = tail ? tail.split(':') : [];
  const groups = tail === undefined ? h : [...h, ...Array(Math.max(0, 8 - h.length - t.length)).fill('0'), ...t];
  return groups.slice(0, 4).map((g) => g.padStart(4, '0')).join(':') + '::/64';
}

// An address as typed, checked and in one form: no spaces or control characters (nothing that could
// become a second header), one @, a domain of dotted labels. Lower case, so the same mailbox has one
// record. Unicode addresses are refused: few email services accept them.
const LOCAL = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}$/;
const LABEL = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/;
export function cleanEmail(value) {
  check(typeof value === 'string', 'email must be a string');
  const email = value.trim().toLowerCase();
  check(email.length >= 6 && email.length <= 254, 'that does not look like an email address');
  const at = email.lastIndexOf('@'), local = email.slice(0, at), labels = email.slice(at + 1).split('.');
  check(at > 0 && LOCAL.test(local) && !local.startsWith('.') && !local.endsWith('.') && !local.includes('..'), 'that does not look like an email address');
  check(labels.length >= 2 && labels.every((l) => LABEL.test(l)) && /^[a-z]{2,63}$/.test(labels.at(-1)), 'that does not look like an email address');
  return email;
}

// ---- counts ----

const utcDay = (t) => new Date(t).toISOString().slice(0, 10);
const nextUtcMidnight = (t) => (Math.floor(t / 86400e3) + 1) * 86400e3;   // the email service's day (README.md)

// Adds one to a count that KV deletes after ttl seconds, and says whether it is now over the limit.
// KV can take up to a minute to show a write in other places, so a burst spread across Cloudflare's
// locations can pass a few more; the email service's own limits stop the rest.
async function overLimit(env, key, limit, ttl) {
  const n = Number(await env.PUSH.get(key)) || 0;
  if (n >= limit) return true;
  await env.PUSH.put(key, String(n + 1), { expirationTtl: ttl });
  return false;
}

async function sentToday(env, t) { return Number(await env.PUSH.get(`quota:${utcDay(t)}`)) || 0; }
async function countSent(env, t, n, log = console.log) {
  if (!n) return;
  const key = `quota:${utcDay(t)}`;
  try { await env.PUSH.put(key, String((await sentToday(env, t)) + n), { expirationTtl: 2 * 86400 }); }
  catch (err) { log(`email: could not count ${n} sent: ${err?.message}`); }   // the service's own cap still holds
}

// ---- HTTP ----

const SAFE = { 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'X-Robots-Tag': 'noindex', 'Cache-Control': 'no-store' };

export async function handleEmail(request, env, { fetch = globalThis.fetch, now = Date.now, log = console.log } = {}) {
  if (!emailOn(env)) return reply(404, 'Not found');
  const url = new URL(request.url);
  try {
    if (url.pathname === '/email/subscribe') return await subscribe(request, env, { fetch, now, log });
    if (url.pathname === '/email/confirm') return await confirm(request, env, url, { now });
    if (url.pathname === '/email/unsubscribe') return await unsubscribe(request, env, url);
    if (url.pathname === '/email/events') return await gone(request, env, { now, log });
    return reply(404, 'Not found');
  } catch (err) {
    if (err instanceof Invalid) return reply(400, err.message, corsFor(request, env));
    throw err;
  }
}

const corsFor = (request, env) => request.headers.get('Origin') === env.ALLOWED_ORIGIN ? { 'Access-Control-Allow-Origin': env.ALLOWED_ORIGIN, Vary: 'Origin' } : {};

// POST {email, spots, website} from the Saved page. "website" is a field people never see: a bot that
// fills it in gets the same answer as everyone, and nothing is sent. The answer is the same whether
// or not the address has signed up before, so the form cannot be used to find out who has.
async function subscribe(request, env, { fetch, now, log }) {
  if (request.method !== 'POST' && request.method !== 'OPTIONS') return reply(405, 'Method not allowed', { Allow: 'POST, OPTIONS' });
  if (request.headers.get('Origin') !== env.ALLOWED_ORIGIN) return reply(403, 'Origin not allowed');
  const cors = corsFor(request, env);
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: { ...cors, 'Access-Control-Allow-Methods': 'POST', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Max-Age': '86400' } });
  }
  const accepted = () => new Response(null, { status: 202, headers: cors });
  const data = await readJson(request);
  check(isObject(data), 'body must be a JSON object');
  if (data.website) return accepted();
  const email = cleanEmail(data.email);
  const spots = cleanSpots(data.spots);
  check(spots.length > 0, 'save a spot first');
  const t = now();
  const ip = connectionOf(request.headers.get('CF-Connecting-IP'));
  const hour = new Date(t).toISOString().slice(0, 13);
  if (await overLimit(env, `rl:ip:${await mac(env, `ip\n${hour}\n${ip}`)}`, SIGNUPS_PER_HOUR, 3600 + 60)) {
    return reply(429, 'too many sign-ups from this connection; try again in an hour', cors);
  }
  if (await overLimit(env, `rl:to:${await mac(env, `to\n${utcDay(t)}\n${email}`)}`, CONFIRMS_PER_DAY, 86400 + 60)) return accepted();

  // The names in the confirmation come from the site's own alerts.json, never from the request.
  let alerts = null;
  try {
    const res = await fetch(`${env.SITE_URL}data/alerts.json?t=${Math.floor(t / 600000)}`, { signal: AbortSignal.timeout(15000) });
    if (res.ok) alerts = await res.json();
  } catch { /* answered below */ }
  if (!isObject(alerts?.spots)) return reply(503, 'the forecast could not be read; try again later', cors);
  const known = spots.filter((id) => isObject(alerts.spots[id]));
  check(known.length > 0, 'none of these spots is in the forecast');

  const cap = setting(env.EMAIL_DAILY_CAP, DAILY_CAP);
  if (await sentToday(env, t) >= cap) return reply(503, 'email sign-up is full for today; try again tomorrow', cors);
  const id = await addressId(env, email);
  const nonce = hex(crypto.getRandomValues(new Uint8Array(16)));
  await env.PUSH.put(`pend:${id}`, JSON.stringify({ email, spots: known, nonce, at: new Date(t).toISOString() }), { expirationTtl: PENDING_TTL });
  const link = `${env.WORKER_URL}email/confirm?id=${id}&n=${nonce}`;
  const sent = await sendEmail(env, confirmEmail(env, email, link, known.map((s) => alerts.spots[s].name ?? s)), { fetch, now });
  if (sent.outcome === 'sent') { await countSent(env, t, 1, log); return accepted(); }
  log(`email ${id.slice(0, 12)}: confirmation not sent: ${String(sent.why).split(email).join('<address>')}`);
  if (sent.outcome === 'quota') { await countSent(env, t, cap, log); return reply(503, 'email sign-up is full for today; try again tomorrow', cors); }
  return reply(502, 'the confirmation email could not be sent; try again later', cors);
}

async function confirm(request, env, url, { now }) {
  if (request.method !== 'GET' && request.method !== 'POST') return reply(405, 'Method not allowed', { Allow: 'GET, POST' });
  const id = url.searchParams.get('id') ?? '', nonce = url.searchParams.get('n') ?? '';
  const pending = ID.test(id) ? await env.PUSH.get(`pend:${id}`, 'json') : null;
  if (!pending || !(await same(pending.nonce, nonce))) {
    return page(env, 404, 'Link expired', 'This link has expired',
      '<p>It may have been used already, or it is more than two days old. If you confirmed, your email alerts are on. '
      + `If not, sign up again on your <a href="${esc(env.SITE_URL)}saved/">Saved page</a>.</p>`);
  }
  const n = pending.spots.length, which = n === 1 ? 'your saved spot' : `one of your ${n} saved spots`;
  // A GET only shows the button: mail scanners open links in emails on their own, and that must not confirm.
  if (request.method === 'GET') {
    return page(env, 200, 'Confirm email alerts', 'Confirm email alerts',
      `<p class="lead">Email alerts to <b>${esc(pending.email)}</b> when ${which} reaches high or very high risk, at most once a day for each.</p>`
      + '<form method="post"><p><button class="btn primary" type="submit">Confirm email alerts</button></p></form>'
      + '<p>Every alert has a link to unsubscribe, which deletes your address at once. '
      + `<a href="${esc(env.SITE_URL)}privacy.html#email-alerts">Privacy notice</a>.</p>`);
  }
  const record = { email: pending.email, spots: pending.spots, confirmed: new Date(now()).toISOString() };
  const meta = JSON.stringify(record.spots).length <= 1000 ? { metadata: { s: record.spots } } : {};
  await env.PUSH.put(`mail:${id}`, JSON.stringify(record), meta);
  await env.PUSH.delete(`pend:${id}`);
  return page(env, 200, 'Email alerts are on', 'Email alerts are on',
    `<p class="lead">You will get an email when ${which} reaches high or very high risk.</p>`
    + '<p>An alert can be late or not come at all, so no alert does not mean the water is clean. '
    + 'To change the spots, sign up again on the Saved page: the new list replaces this one once you confirm it.</p>'
    + `<p><a href="${esc(await unsubscribeUrl(env, id))}">Unsubscribe</a> · <a href="${esc(env.SITE_URL)}saved/">Your saved spots</a></p>`);
}

// GET shows the button; POST unsubscribes. Mail programs that offer one-click unsubscribe POST
// "List-Unsubscribe=One-Click" here (RFC 8058) and expect 200 or 202, which this is.
async function unsubscribe(request, env, url) {
  if (request.method !== 'GET' && request.method !== 'POST') return reply(405, 'Method not allowed', { Allow: 'GET, POST' });
  const id = url.searchParams.get('id') ?? '', token = url.searchParams.get('t') ?? '';
  if (!ID.test(id) || !(await same(await unsubscribeToken(env, id), token))) {
    return page(env, 400, 'Link not complete', 'This link is not complete',
      '<p>Use the unsubscribe link in one of the alert emails, copied whole, or reply to an alert and ask to be removed.</p>');
  }
  if (request.method === 'GET') {
    const record = await env.PUSH.get(`mail:${id}`, 'json');
    if (!record) return page(env, 200, 'Not subscribed', 'Nothing to unsubscribe', '<p>This address gets no email alerts, and SwimSignal holds nothing for it.</p>');
    return page(env, 200, 'Unsubscribe', 'Unsubscribe from email alerts',
      `<p class="lead">Stop email alerts to <b>${esc(record.email)}</b> and delete the address.</p>`
      + '<form method="post"><p><button class="btn primary" type="submit">Unsubscribe</button></p></form>');
  }
  await env.PUSH.delete(`mail:${id}`);
  await env.PUSH.delete(`pend:${id}`);
  return page(env, 200, 'Unsubscribed', 'You are unsubscribed',
    '<p class="lead">Your address and your list of spots are deleted. No more alerts will be sent to it.</p>'
    + `<p>You can still see the forecasts on <a href="${esc(env.SITE_URL)}">SwimSignal</a>.</p>`);
}

// ---- the email service's reports ----
// Resend reports by webhook (https://resend.com/docs/webhooks/emails/bounced, /complained and
// /suppressed, read 4 Oct 2026): email.bounced when the receiving server rejected an email for good
// (data.bounce.type "Permanent"), email.complained when the recipient marked it as spam, and
// email.suppressed when Resend would not send to an address on its suppression list. Each names the
// address in data.to. Any of them deletes that address's record and any sign-up waiting, at once, so
// nothing more goes to it: before this a dead address stayed until removed by hand, and Resend counts
// bounces and complaints against the sender. A bounce that is not permanent is a server saying "later",
// and deletes nothing. Every other event is acknowledged and ignored, so Resend does not send it again.
const GONE = new Set(['email.bounced', 'email.complained', 'email.suppressed']);
const MAX_EVENT = 64 * 1024;   // a report is under 1 kB; a long bounce message stays well within this
// Resend signs reports as Svix does (https://docs.svix.com/receiving/verifying-payloads/how-manual,
// read 4 Oct 2026): HMAC-SHA-256 of "<svix-id>.<svix-timestamp>.<body>" under the base64 secret after
// "whsec_", in base64; svix-signature holds one or more "v1,<signature>", separated by spaces. A
// timestamp more than 5 minutes from now is refused, as Svix's own libraries do, so a report cannot be
// replayed later.
const SIGNED_WITHIN = 300;
export async function signedByService(env, headers, body, t) {
  const id = headers.get('svix-id'), ts = headers.get('svix-timestamp'), sigs = headers.get('svix-signature');
  if (!id || !sigs || !/^\d{1,12}$/.test(ts ?? '') || Math.abs(t / 1000 - Number(ts)) > SIGNED_WITHIN) return false;
  let secret;
  try { secret = Uint8Array.from(atob(String(env.MAIL_WEBHOOK_SECRET).replace(/^whsec_/, '')), (c) => c.charCodeAt(0)); } catch { return false; }
  const key = await crypto.subtle.importKey('raw', secret, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const want = btoa(String.fromCharCode(...new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(`${id}.${ts}.${body}`)))));
  for (const entry of sigs.split(' ')) {
    const [version, sig] = entry.split(',');
    if (version === 'v1' && sig && await same(sig, want)) return true;
  }
  return false;
}
// An address as the report gives it: plain, or "Name <address>".
const reported = (value) => { const v = String(value ?? ''), m = /<([^<>]+)>\s*$/.exec(v); return m ? m[1] : v; };

async function gone(request, env, { now, log }) {
  if (!env.MAIL_WEBHOOK_SECRET) return reply(404, 'Not found');
  if (request.method !== 'POST') return reply(405, 'Method not allowed', { Allow: 'POST' });
  const body = await readText(request, MAX_EVENT);
  if (!(await signedByService(env, request.headers, body, now()))) return reply(401, 'Signature not valid');
  let event;
  try { event = JSON.parse(body); } catch { throw new Invalid('Body is not JSON'); }
  const type = event?.type, data = isObject(event?.data) ? event.data : {};
  const bounce = isObject(data.bounce) ? data.bounce : {};
  if (!GONE.has(type) || (type === 'email.bounced' && bounce.type !== undefined && bounce.type !== 'Permanent')) return reply(200, 'Nothing to do');
  let removed = 0;
  for (const value of Array.isArray(data.to) ? data.to : []) {
    let email;
    try { email = cleanEmail(reported(value)); } catch { continue; }
    const id = await addressId(env, email);
    await env.PUSH.delete(`mail:${id}`);
    await env.PUSH.delete(`pend:${id}`);
    log(`email ${id.slice(0, 12)}: deleted after ${type.slice('email.'.length)}${type === 'email.bounced' && bounce.subType ? ` (${String(bounce.subType).slice(0, 40)})` : ''}`);
    removed++;
  }
  return reply(200, `Deleted ${removed}`);
}

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const MARK = '<svg viewBox="0 0 512 512" aria-hidden="true"><rect width="512" height="512" fill="#0f5a61"/>'
  + '<path d="M430-20C330 110 470 230 300 290S110 380 190 540" fill="none" stroke="#5CC2B5" stroke-width="70" stroke-linecap="round"/>'
  + '<circle cx="318" cy="138" r="38" fill="#F08A4B"/><circle cx="165" cy="358" r="46" fill="none" stroke="#fff" stroke-width="22"/></svg>';

// A page in the site's look: its header and the stylesheet and fonts from the site itself (as the
// reviews Worker's moderation page does). No script; the one form posts back to this address.
function page(env, status, title, heading, body) {
  const site = env.SITE_URL, origin = new URL(site).origin;
  const nav = PAGE_NAV.map(([href, label]) => `<a href="${esc(site + href)}">${label}</a>`).join('');
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)} · SwimSignal</title>
<meta name="robots" content="noindex">
<meta name="theme-color" content="#3d5b5d">
<link rel="icon" href="${esc(site)}icons/icon.svg" type="image/svg+xml">
<link rel="stylesheet" href="${esc(site)}page.css">
</head><body>
<header class="top"><a class="brand" href="${esc(site)}">${MARK}SwimSignal</a><nav aria-label="Site">${nav}</nav></header>
<main class="doc">
<h1>${esc(heading)}</h1>
${body}
</main>
</body></html>`;
  const csp = [`default-src 'none'`, `style-src ${origin}`, `font-src ${origin}`, `img-src ${origin}`, `form-action 'self'`,
    `base-uri 'none'`, `frame-ancestors 'none'`].join('; ');
  return new Response(html, { status, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Content-Security-Policy': csp, ...SAFE } });
}

// ---- the emails ----
// Short: the spot, its level with "risk", the day and why (the headline, in the page's own words from
// alerts.json), when the forecast was issued, and a link. Plain text first, and a small HTML version
// in the site's colours with nothing fetched from anywhere: no images, no web fonts, no tracking.

const cap1 = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const KTEXT = { high: '#a04623', 'very high': '#992a2a' };   // the level colours for text (page.css --k-*)
const KRULE = { high: '#c2552a', 'very high': '#a32d2d' };   // and for the 4 px rule
const london = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
export function issuedWords(iso) {
  const p = Object.fromEntries(london.formatToParts(Date.parse(iso)).map((x) => [x.type, x.value]));
  return `${p.hour}:${p.minute} on ${p.weekday} ${p.day} ${p.month} ${p.year}`;
}
// "High risk today: sewage spills" already says the level; "Rated poor: advice against bathing" does
// not, so it gets "High risk." in front: a level word always carries "risk".
function spotLines(spot) {
  const words = `${cap1(spot.level ?? 'high')} risk`, headline = spot.headline || words;
  return { words, line: headline.startsWith(words) ? headline : `${words}. ${headline}`, head: headline.startsWith(words) ? headline.split(': ')[0] : words };
}

const FONT = `'Source Sans 3',-apple-system,'Segoe UI',Roboto,Arial,sans-serif`, SERIF = `'Source Serif 4',Georgia,serif`;
function htmlShell(subject, inner, foot) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(subject)}</title></head>`
    + `<body style="margin:0;padding:0;background:#f6f4ee;"><div style="max-width:560px;margin:0 auto;padding:24px 20px;font:17px/1.5 ${FONT};color:#1b2328;">`
    + `<p style="margin:0 0 20px;font:600 20px/1 ${SERIF};color:#0f5a61;">SwimSignal</p>${inner}`
    + `<p style="margin:24px 0 0;padding-top:12px;border-top:1px solid #e0dbd0;font-size:13px;line-height:1.45;color:#5a6166;">${foot}</p></div></body></html>`;
}
const linkStyle = 'color:#0f5a61;';

export function confirmEmail(env, to, link, names) {
  const subject = 'Confirm your SwimSignal email alerts';
  const list = names.slice(0, 20), more = names.length - list.length;
  const text = ['Someone, probably you, asked for SwimSignal email alerts at this address for these spots:', '',
    ...list.map((n) => `- ${n}`), ...(more > 0 ? [`- and ${more} more`] : []), '',
    'To confirm, open this link and press Confirm:', link, '',
    'The link works for two days. If you did not ask, ignore this email: nothing more will be sent, and the request is deleted.', '',
    'An alert comes when one of these spots reaches high or very high risk, at most once a day for each. Every alert has a link to unsubscribe.',
    '', `SwimSignal · ${env.SITE_URL}`].join('\n');
  const inner = `<h1 style="margin:0 0 8px;font:600 20px/1.25 ${SERIF};">Confirm your email alerts</h1>`
    + '<p style="margin:0 0 8px;">Someone, probably you, asked for SwimSignal email alerts at this address for these spots:</p>'
    + `<ul style="margin:0 0 16px;padding-left:20px;">${list.map((n) => `<li>${esc(n)}</li>`).join('')}${more > 0 ? `<li>and ${more} more</li>` : ''}</ul>`
    + `<p style="margin:0 0 16px;"><a href="${esc(link)}" style="display:inline-block;padding:10px 16px;border-radius:8px;background:#0f5a61;color:#fff;font-weight:600;text-decoration:none;">Confirm email alerts</a></p>`
    + '<p style="margin:0;">An alert comes when one of these spots reaches high or very high risk, at most once a day for each. Every alert has a link to unsubscribe.</p>';
  const foot = 'The link works for two days. If you did not ask, ignore this email: nothing more will be sent, and the request is deleted.';
  return { to, subject, text, html: htmlShell(subject, inner, foot) };
}

export function alertEmail(env, to, ids, spots, issuedAt, unsubscribe) {
  const issued = issuedWords(issuedAt), one = ids.length === 1;
  const first = spots[ids[0]];
  const subject = one ? `${spotLines(first).head} at ${first.name ?? ids[0]}` : `${ids.length} of your saved spots are at high or very high risk`;
  const url = (id) => spots[id].url ?? `${env.SITE_URL}spot/${id}/`;
  const text = [
    ...ids.flatMap((id) => [spots[id].name ?? id, `${spotLines(spots[id]).line}.`, url(id), '']),
    `From the forecast issued at ${issued}. A forecast, not a water test: check the signs at the water before you swim.`,
    'An alert can be late or not come at all, so no alert does not mean the water is clean.', '',
    'You get this because you asked for SwimSignal email alerts for your saved spots and confirmed it.',
    `Unsubscribe (deletes your address at once): ${unsubscribe}`,
  ].join('\n');
  const inner = ids.map((id) => {
    const s = spots[id], { line } = spotLines(s), level = s.level === 'very high' ? 'very high' : 'high';
    return `<div style="margin:0 0 20px;padding-left:12px;border-left:4px solid ${KRULE[level]};">`
      + `<h1 style="margin:0 0 4px;font:600 20px/1.25 ${SERIF};">${esc(s.name ?? id)}</h1>`
      + `<p style="margin:0 0 4px;font-weight:600;color:${KTEXT[level]};">${esc(line)}</p>`
      + `<p style="margin:0;font-size:15px;"><a href="${esc(url(id))}" style="${linkStyle}">See the forecast</a></p></div>`;
  }).join('')
    + `<p style="margin:0;font-size:15px;color:#5a6166;">From the forecast issued at ${esc(issued)}. A forecast, not a water test: check the signs at the water before you swim. `
    + 'An alert can be late or not come at all, so no alert does not mean the water is clean.</p>';
  const foot = 'You get this because you asked for SwimSignal email alerts for your saved spots and confirmed it. '
    + `<a href="${esc(unsubscribe)}" style="${linkStyle}">Unsubscribe</a> deletes your address at once.`;
  return {
    to, subject, text, html: htmlShell(subject, inner, foot),
    headers: { 'List-Unsubscribe': `<${unsubscribe}>`, 'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click' },
  };
}

// ---- the queue ----

// One email per confirmed address that saved a spot in risen, merged into what is already queued for
// it. Called by index.js with the spots it found rising, the same list push is queued from. Returns
// how many addresses were queued (0 writes nothing).
export async function queueEmails(env, alerts, risen) {
  const fresh = [];
  for (const { name: key, metadata } of await listKeys(env.PUSH, 'mail:')) {
    let spots = metadata?.s;
    if (!Array.isArray(spots)) spots = (await env.PUSH.get(key, 'json').catch(() => null))?.spots ?? [];
    const hits = spots.filter((id) => risen.has(id));
    if (hits.length) fresh.push({ id: key.slice(5), at: alerts.generated_at, spots: Object.fromEntries(hits.map((id) => [id, alerts.spots[id]])) });
  }
  if (!fresh.length) return 0;
  const queued = (await env.PUSH.get('mailq', 'json')) ?? { items: [] };
  const byId = new Map(queued.items.map((item) => [item.id, item]));
  // A merged item starts again (new time, no attempts), so its idempotency key is new: an email for
  // the earlier spot that may have gone already can repeat, but the new spot is never lost.
  for (const item of fresh) {
    const old = byId.get(item.id);
    byId.set(item.id, old ? { id: item.id, at: item.at, spots: { ...old.spots, ...item.spots } } : item);
  }
  await env.PUSH.put('mailq', JSON.stringify({ ...queued, items: [...byId.values()] }));
  return fresh.length;
}

// Sends the next emails from mailq, each checked against this run's alerts.json: only spots still
// saved in the record and still high, in the latest wording. Paused while the forecast is expired (as
// push is), while the day's allowance is used, and for an hour after the service refuses the key.
export async function drainEmails(env, alerts, expires, { fetch = globalThis.fetch, log = console.log, now = Date.now } = {}) {
  const tally = { sent: 0, failed: 0 };
  const done = (queued) => ({ email: { ...tally, queued } });
  const queued = await env.PUSH.get('mailq', 'json');
  const items = queued?.items ?? [];
  if (!items.length) return done(0);
  const t = now();
  if (expires <= t) { log(`email: forecast expired; ${items.length} emails wait for the next one`); return done(items.length); }
  if (queued.paused_until > t) { log(`email: paused until ${new Date(queued.paused_until).toISOString()}; ${items.length} queued`); return done(items.length); }
  const cap = setting(env.EMAIL_DAILY_CAP, DAILY_CAP), reserve = Math.min(cap, setting(env.EMAIL_CONFIRM_RESERVE, CONFIRM_RESERVE));
  const room = Math.min(setting(env.EMAILS_PER_RUN, EMAILS_PER_RUN), cap - reserve - await sentToday(env, t));
  if (room <= 0) { log(`email: today's allowance for alerts is used; ${items.length} wait`); return done(items.length); }

  const batch = [], rest = [];
  for (const item of items) ((item.next_attempt ?? 0) <= t && batch.length < room ? batch : rest).push(item);
  const kept = [];
  let paused = 0;
  for (const item of batch) {
    if (paused) { kept.push(item); continue; }
    const short = item.id.slice(0, 12), attempt = (item.attempts ?? 0) + 1;
    const retry = (after = 0) => {
      const at = now(), next = nextAttempt(attempt, at, after);
      if (attempt >= MAX_ATTEMPTS) log(`email ${short}: given up after ${attempt} attempts`);
      else if (next - at > MAX_RETRY_WAIT) log(`email ${short}: given up, the email service asked for a wait of over an hour`);
      else kept.push({ ...item, attempts: attempt, next_attempt: next });
    };
    let record;
    try { record = await env.PUSH.get(`mail:${item.id}`, 'json'); }
    catch { tally.failed++; log(`email ${short}: record read unavailable`); retry(); continue; }
    if (!record?.email) continue;   // unsubscribed
    const ids = Object.keys(item.spots ?? {}).filter((id) => record.spots?.includes(id) && alerts.spots[id]?.rank >= HIGH);
    if (!ids.length) continue;
    const msg = alertEmail(env, record.email, ids, alerts.spots, alerts.generated_at, await unsubscribeUrl(env, item.id));
    msg.idempotencyKey = `alert-${item.id}-${item.at}`;
    const r = await sendEmail(env, msg, { fetch, now });
    const why = String(r.why ?? '').split(record.email).join('<address>');
    if (r.outcome === 'sent') { tally.sent++; continue; }
    tally.failed++;
    if (r.outcome === 'retry') { log(`email ${short}: ${why}`); retry(r.after); }
    else if (r.outcome === 'quota') { log(`email: the email service's allowance is used (${why}); paused until tomorrow`); kept.push(item); paused = nextUtcMidnight(t); }
    else if (r.outcome === 'config') { log(`email: the email service refused the key or sender (${why}); check MAIL_API_KEY and EMAIL_FROM. Paused for an hour`); kept.push(item); paused = t + 3600e3; }
    else log(`email ${short}: refused, not retried: ${why}`);
  }
  await countSent(env, t, tally.sent, log);
  const left = [...rest, ...kept];   // retries go behind those not yet tried, as push does
  if (left.length) await env.PUSH.put('mailq', JSON.stringify({ items: left, ...(paused ? { paused_until: paused } : {}) }));
  else await env.PUSH.delete('mailq');
  log(`email: sent ${tally.sent}, failed ${tally.failed}; ${left.length} still queued`);
  return done(left.length);
}
