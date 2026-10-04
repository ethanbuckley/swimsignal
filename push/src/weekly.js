// The weekly note: once a week, for each browser that asked for it, the lowest level of the four
// days after today at each saved spot, in the page's words ("Saturday, low risk"). The words are made
// in the build by scripts/alerts.js (each spot's `best`) with levels.js, so the note says what the
// page says. Off unless asked: the Saved page sends weekly: true, and the record and its key's
// metadata (w: 1) keep it. Push only; email alerts do not offer it (README.md, "The weekly note").
//
// When: from 18:00 UK time on a Thursday, the first run queues every browser that asked (in `weekq`);
// later runs send SENDS_PER_RUN at a time, but only runs in which the high-risk alerts had nothing to
// send or queue: those come first (index.js). Each note is made from the alerts.json of the run that
// sends it, as an alert is. What is not sent by UK midnight is dropped: the note's "tomorrow" is
// Thursday's, and the window bounds a week's cost (README.md): 180 runs, so at most 181 KV writes and
// 180 × SENDS_PER_RUN notes. Outside the window the cron reads nothing for it.

import { isObject, listKeys } from './shared.js';

export const WEEKLY_DAY = 'Thu', WEEKLY_HOUR = 18;   // UK time
const MAX_LINES = 5;   // one line a spot; the rest are on the Saved page
const ORDER = { low: 0, moderate: 1, high: 2, 'very high': 3 };
const uk = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', weekday: 'short', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23' });

// The UK date of this Thursday evening, or null outside the window.
export function weeklyWindow(t) {
  const p = Object.fromEntries(uk.formatToParts(t).map((x) => [x.type, x.value]));
  return p.weekday === WEEKLY_DAY && Number(p.hour) >= WEEKLY_HOUR ? `${p.year}-${p.month}-${p.day}` : null;
}

// One line a spot, the lowest level first, then the earliest day, then the order they were saved in:
// "Nidd at the Lido, Knaresborough: Saturday, low risk." The title is the Saved page's own words.
export function weeklyPayload(ids, spots, siteUrl) {
  const rows = ids.map((id, i) => ({ id, i, best: spots[id].best }))
    .sort((a, b) => (ORDER[a.best.level] ?? 9) - (ORDER[b.best.level] ?? 9) || String(a.best.date).localeCompare(String(b.best.date)) || a.i - b.i);
  const lines = rows.slice(0, MAX_LINES).map(({ id, best }) => `${spots[id].name ?? id}: ${best.words}.`);
  if (rows.length > MAX_LINES) lines.push(`And ${rows.length - MAX_LINES} more on your Saved page.`);
  const url = ids.length === 1 ? spots[ids[0]].url ?? `${siteUrl}spot/${ids[0]}/` : `${siteUrl}saved/`;
  return { title: 'Lowest pollution risk this week', body: lines.join('\n'), url, tag: 'dipspot-week' };
}

// The note for a record, from this run's forecast, or null: turned off since it was queued, or none
// of its spots has a forecast that changes from day to day.
const noteFor = (alerts, siteUrl) => (record) => {
  if (record.weekly !== true) return null;
  const ids = (record.spots ?? []).filter((id) => isObject(alerts.spots[id]?.best) && typeof alerts.spots[id].best.words === 'string');
  return ids.length ? weeklyPayload(ids, alerts.spots, siteUrl) : null;
};

// Every browser that asked, from the list of keys; a record with too many spots for its metadata is read.
async function wanting(env) {
  const items = [];
  for (const { name: key, metadata } of await listKeys(env.PUSH, 'sub:')) {
    if (Array.isArray(metadata?.s)) { if (metadata.w === 1) items.push({ key }); continue; }
    const record = await env.PUSH.get(key, 'json').catch(() => null);
    if (record?.weekly === true) items.push({ key });
  }
  return items;
}

// Called by index.js in a run whose alerts sent and queued nothing. deliver(batch, noteFor, tally)
// sends as the alerts do (retries, 404 and 410, the forecast's TTL) and returns the notes to keep.
export async function runWeekly(env, alerts, { log, now, perRun, deliver }) {
  const week = weeklyWindow(now());
  if (!week) return null;
  const queued = await env.PUSH.get('weekq', 'json');
  if (queued?.week !== week) {
    if (queued?.items?.length) log(`weekly: ${queued.items.length} notes from ${queued.week} were not sent before midnight`);
    const items = await wanting(env);
    // Sending starts next run: KV allows one write a second to a key.
    await env.PUSH.put('weekq', JSON.stringify({ week, items }));
    log(`weekly: ${week}: ${items.length} weekly notes to send`);
    return { sent: 0, removed: 0, failed: 0, queued: items.length };
  }
  if (!queued.items?.length) return null;   // this week's have gone
  const t = now(), batch = [], rest = [];
  for (const item of queued.items) ((item.next_attempt ?? 0) <= t && batch.length < perRun ? batch : rest).push(item);
  const tally = { sent: 0, removed: 0, failed: 0 };
  if (!batch.length) return { ...tally, queued: rest.length };   // all waiting to retry
  const left = [...rest, ...await deliver(batch, noteFor(alerts, env.SITE_URL), tally)];
  await env.PUSH.put('weekq', JSON.stringify({ week, items: left }));   // an empty list marks the week done
  log(`weekly: sent ${tally.sent}, removed ${tally.removed}, failed ${tally.failed}; ${left.length} still queued`);
  return { ...tally, queued: left.length };
}
