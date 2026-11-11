// Back to low risk (README.md, "Back to low risk"): a browser with alerts on asks, from a raised spot's
// page, to hear when that spot is at low risk again. One message, the first time a build gives the spot
// the level low, and the request is then deleted; it lapses unsent after CLEAR_DAYS.
//
// Until 11 Nov 2026 no message said a spot had fallen back, on purpose: it "would read as an all-clear,
// which neither SwimSignal's level nor a lifted notice is" (index.js, newAdvice). Ethan chose to offer
// this one, asked for spot by spot. So it is hedged every way the page is:
// - it is sent only when the build says so (alerts.json `clear_alerts`, from the repository variable
//   DIPCAST_PUSH_CLEARS), in the same build that changes the page and the privacy notice to say it;
// - never while official advice restricting swimming shows at the spot (alerts.json `official_restricts`):
//   the request waits, and is sent if the level is still low once the notice has lifted;
// - the level is the spot's own (`rank` 0: levels.js level, which takes right now, today and tomorrow),
//   so a spot low today and raised tomorrow is not "back to low";
// - its words are the page's (`headline` and `action`), a marker first where any official notice shows,
//   and it ends with the page's own caveat: a forecast, not a water test.
// Who to tell is decided once a build, as every alert is. Unlike the others the cron then writes to the
// record, to delete the request it has answered: one write for one message.

import { check, isObject, officialMark } from './shared.js';
import { addDays } from './dates.js';

export const MAX_CLEARS = 10;   // spots a browser may ask about
export const CLEAR_DAYS = 14;   // a request not answered in this many days is forgotten
const SPOT_ID = /^[A-Za-z0-9_-]{1,80}$/;
export const CAVEAT = 'A forecast, not a water test: check the signs at the water before you swim.';

// What a page sends, checked: the ids of the spots asked about, none twice.
export function cleanClears(ids) {
  check(Array.isArray(ids), 'clears must be an array');
  check(ids.length <= MAX_CLEARS, `at most ${MAX_CLEARS} spots to hear about`);
  check(ids.every((s) => typeof s === 'string' && SPOT_ID.test(s)), 'bad spot id in clears');
  check(new Set(ids).size === ids.length, 'the same spot twice in clears');
  return ids;
}

// A record's requests as stored, [{spot, until}], or [] (a record from before them, or one that never asked).
export const clearsOf = (record) => (Array.isArray(record?.clears)
  ? record.clears.filter((c) => isObject(c) && typeof c.spot === 'string' && typeof c.until === 'string') : []);

// The list a page sent, each with the day it lapses: a spot already asked about keeps its day, so sending
// the list again (the page sends it whole) does not put the day off.
export const withUntil = (ids, old, today) => ids.map((spot) => ({ spot, until: old.find((c) => c.spot === spot)?.until ?? addDays(today, CLEAR_DAYS) }));

// May this spot's request be answered from this alerts.json?
const lowNow = (alerts, id) => alerts?.clear_alerts === true && alerts.spots?.[id]?.rank === 0 && alerts.spots[id].official_restricts !== true;

// The spots at low risk in this build, with no notice restricting swimming: empty unless the build turned
// the alert on.
export function clearedNow(alerts) {
  if (alerts?.clear_alerts !== true || !isObject(alerts.spots)) return new Set();
  return new Set(Object.keys(alerts.spots).filter((id) => lowNow(alerts, id)));
}

// One spot: its name, then the page's headline and what to do, then the caveat. Several: how many, their
// names, the caveat. The tag is its own, so it never silently replaces a high-risk alert for the spot.
export function clearPayload(ids, spots, siteUrl) {
  const mark = (id) => officialMark(spots[id]);
  if (ids.length === 1) {
    const [id] = ids, spot = spots[id];
    const said = [spot.headline ? `${spot.headline}.` : 'Low risk.', spot.action ?? '', CAVEAT].filter(Boolean).join(' ');
    return { title: `${spot.name ?? id}: back to low risk`, body: mark(id) ? `${mark(id)} · ${said}` : said, url: spot.url ?? `${siteUrl}spot/${id}/`, tag: `dipspot-${id}-low` };
  }
  const names = ids.map((id) => (mark(id) ? `${mark(id)} · ` : '') + (spots[id].name ?? id)).join(', ');
  return { title: `${ids.length} spots you asked about are back to low risk`,
    body: `${names.length > 160 ? names.slice(0, 159) + '…' : names}. ${CAVEAT}`, url: siteUrl, tag: 'dipspot-low' };
}

// The message for a queued item, from this run's forecast: only the spots still asked about, not lapsed,
// and still at low risk with no restricting notice. Null when none is: nothing is sent, and the request
// waits for the next build that says low.
export const clearFor = (alerts, siteUrl, today) => (record, { clears }) => {
  const asked = clearsOf(record);
  const ids = (clears ?? []).filter((id) => lowNow(alerts, id) && asked.some((c) => c.spot === id && c.until >= today));
  return ids.length ? clearPayload(ids, alerts.spots, siteUrl) : null;
};
