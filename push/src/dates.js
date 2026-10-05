// Alerts for a date (README.md, "Alerts for a date"): a browser with alerts on asks about up to
// MAX_DATES pairs of a spot and a date, from the organisers' page. The cron tells it when that day
// first enters the forecast, and again each time the day's level changes; a pair is forgotten once
// its date has passed.
//
// Who to tell is decided once a build, for everyone at once, as the high-risk alerts are: `state`
// keeps each spot's level on each of the forecast's days (`days`), and a day whose level is new or
// different in the next build is news to everyone who asked about it. So the cron writes nothing
// for a subscriber it tells, and nothing more than it already wrote for `state`. One consequence: a
// pair asked for while its day is already in the forecast hears only of changes after that.
//
// The levels and words are the page's own: scripts/alerts.js writes the five days (`dates`) and, at
// each spot whose level changes from day to day, each day's [level, headline, action] (`days`, the
// sentences as places in `words`). Elsewhere a day's level is the spot's own.

import { check, isObject } from './shared.js';

export const MAX_DATES = 10;        // pairs a browser may ask about
export const MAX_AHEAD_DAYS = 400;  // about a year ahead, and a season's bookings
const SPOT_ID = /^[A-Za-z0-9_-]{1,80}$/;
const ISO = /^\d{4}-\d{2}-\d{2}$/;
// The levels a day can be told in: the four, and the two plain ones ("No sewage risk from monitored
// overflows", "No river connection"), which do not change but do answer "what will it be".
const ORDER = { low: 0, moderate: 1, high: 2, 'very high': 3 };
const KNOWN = new Set([...Object.keys(ORDER), 'no overflows', 'no river connection']);

const realDate = (iso) => { if (typeof iso !== 'string' || !ISO.test(iso)) return false; const d = new Date(iso + 'T00:00:00Z'); return !isNaN(d) && d.toISOString().slice(0, 10) === iso; };
export const addDays = (iso, n) => { const d = new Date(iso + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const london = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' });
export const londonToday = (t) => london.format(t);
export const pairKey = (spot, date) => `${spot} ${date}`;   // a spot id has no space

// What a page sends, checked: [{spot, date}], none passed (UK time) and none more than
// MAX_AHEAD_DAYS ahead, no pair twice. Only the two fields are kept.
export function cleanDates(dates, today) {
  check(Array.isArray(dates), 'dates must be an array');
  check(dates.length <= MAX_DATES, `at most ${MAX_DATES} dates`);
  const last = addDays(today, MAX_AHEAD_DAYS);
  const out = dates.map((d) => {
    check(isObject(d) && typeof d.spot === 'string' && SPOT_ID.test(d.spot), 'bad spot id in dates');
    check(realDate(d.date), 'a date must be yyyy-mm-dd');
    check(d.date >= today, 'that date has passed');
    check(d.date <= last, `that date is more than ${MAX_AHEAD_DAYS} days ahead`);
    return { spot: d.spot, date: d.date };
  });
  check(new Set(out.map((d) => pairKey(d.spot, d.date))).size === out.length, 'the same spot and date twice');
  return out;
}

// A record's pairs as stored, or [] (a record from before dates, or one that never asked).
export const datesOf = (record) => (Array.isArray(record?.dates) ? record.dates.filter((d) => isObject(d) && typeof d.spot === 'string' && typeof d.date === 'string') : []);

// The day in this alerts.json: {level, headline, action}, or null where the day is not in the
// forecast or has no level. An alerts.json from before dates has no `dates`, so nothing is news.
export function dayOf(alerts, id, date) {
  const spot = alerts?.spots?.[id];
  if (!isObject(spot) || !Array.isArray(alerts.dates)) return null;
  const j = alerts.dates.indexOf(date);
  if (j < 0) return null;
  if (Array.isArray(spot.days)) {
    const d = spot.days[j], words = Array.isArray(alerts.words) ? alerts.words : [];
    if (!Array.isArray(d) || !KNOWN.has(d[0])) return null;
    return { level: d[0], headline: words[d[1]] ?? '', action: words[d[2]] ?? '' };
  }
  return KNOWN.has(spot.level) ? { level: spot.level, headline: spot.headline ?? '', action: spot.action ?? '' } : null;
}

// Every spot's level on each day of this build, {id: {date: level}}, for `state`. A day that has
// no level in this build keeps the last one it had, so a day missing from one build (its rain
// forecast late) is not "new" again in the next; days before this build's first are dropped.
export function dayLevels(alerts, prev = {}) {
  const out = {};
  if (!Array.isArray(alerts.dates) || !alerts.dates.length) return out;
  const first = alerts.dates[0];
  for (const id of Object.keys(alerts.spots)) {
    const levels = {};
    for (const [date, level] of Object.entries(isObject(prev[id]) ? prev[id] : {})) if (date >= first) levels[date] = level;
    for (const date of alerts.dates) { const d = dayOf(alerts, id, date); if (d) levels[date] = d.level; }
    if (Object.keys(levels).length) out[id] = levels;
  }
  return out;
}

// The days that are news in this build: Map of pairKey -> the level before (null: first seen).
export function dateNews(alerts, prev = {}) {
  const news = new Map();
  if (!Array.isArray(alerts.dates)) return news;
  for (const id of Object.keys(alerts.spots)) {
    for (const date of alerts.dates) {
      const d = dayOf(alerts, id, date), before = isObject(prev[id]) ? prev[id][date] ?? null : null;
      if (d && d.level !== before) news.set(pairKey(id, date), before);
    }
  }
  return news;
}

const dayWords = (iso) => new Date(iso + 'T12:00:00Z').toLocaleDateString('en-GB', { timeZone: 'UTC', weekday: 'long', day: 'numeric', month: 'long' });
const shortDay = (iso) => new Date(iso + 'T12:00:00Z').toLocaleDateString('en-GB', { timeZone: 'UTC', weekday: 'short', day: 'numeric', month: 'short' });
const sentence = (s) => (s && !/[.!?]$/.test(s) ? `${s}.` : s);
const join = (...parts) => parts.filter(Boolean).join(' ');

// One pair: the spot and the day, then the day's headline (it comes first: Android shows about one
// line until the notification is opened), what to do, and whether it is the first forecast or a
// change. The site's worker adds the issue time. It opens the organisers' page at that spot and day.
// Several pairs in one build: a line each.
export function datePayload(lines, spots, siteUrl, issued) {
  const link = ({ spot, date }) => `${siteUrl}organisers.html#spot=${encodeURIComponent(spot)}&date=${date}`;
  const name = (id) => spots[id]?.name ?? id;
  if (lines.length === 1) {
    const [{ spot, date, from, day }] = lines;
    const what = from === null ? 'This is the first forecast for this day, and it can change.'
      : ORDER[from] !== undefined ? `Was ${from} risk.` : 'Changed since the last forecast.';
    return { title: `${name(spot)} · ${dayWords(date)}`, body: from === null ? join(sentence(day.headline), sentence(day.action), what) : join(sentence(day.headline), what, sentence(day.action)),
      url: link(lines[0]), tag: `dipspot-${spot}-${date}-${day.level.replace(/ /g, '')}` };
  }
  const body = lines.map(({ spot, date, day }) => `${name(spot)} · ${shortDay(date)}: ${sentence(day.headline)}`).join('\n');
  return { title: `New forecasts for ${lines.length} of your dates`, body: body.length > 600 ? body.slice(0, 599) + '…' : body,
    url: link(lines[0]), tag: `dipspot-dates-${issued}` };
}

// The notice for a queued item ({key, dates: [{spot, date, from}]}), from this run's forecast: only
// the pairs still asked for, still in the forecast, and still different from what they were; null
// when none is left.
export const dateFor = (alerts, siteUrl) => (record, item) => {
  const asked = new Set(datesOf(record).map((d) => pairKey(d.spot, d.date)));
  const lines = (item.dates ?? []).filter((p) => asked.has(pairKey(p.spot, p.date)))
    .map((p) => ({ ...p, day: dayOf(alerts, p.spot, p.date) })).filter((p) => p.day && p.day.level !== p.from)
    .sort((a, b) => a.date.localeCompare(b.date) || a.spot.localeCompare(b.spot));
  return lines.length ? datePayload(lines, alerts.spots, siteUrl, alerts.generated_at) : null;
};

