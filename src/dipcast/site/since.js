// Since you last looked: what changed at a saved spot between the forecast this browser last showed
// for it and the one on screen, as one line on its card, on the Saved page and in the list's Saved
// spots: "Was low risk when you looked on Friday at 18:20; now moderate risk." The page draws the
// cards and says when it has shown a spot (index.html: savedCard, renderSaved, drawSpots, render); the
// rules and the note kept on the device are here, where Node can test them.
//
// A spot counts as looked at when its level is on screen with no day picked: its card on the Saved
// page or in the list, or its own page. The note for each saved spot is what it showed then, the
// forecast it came from and the time, in this browser's local storage (SEEN_KEY), sent nowhere, and
// dropped when the spot is unsaved. The lines compare with the notes as they were when the page
// opened, so they stay for the whole visit and are gone on the next one unless something changes again.
//
// A plain script, as levels.js: globals in the page, exports in Node. It asks for the level rules
// when it is called, so in the page it only has to load before it is used.
const sinceRules = () => typeof level === 'function'
  ? { level, ORDER, NO_OVERFLOWS, NO_FORECAST, COVER, daily, today, dayWord, storedList }
  : { ...require('./levels.js'), ...require('./experience.js') };

const SEEN_KEY = 'dipcast.seen';
const RATED = /^((excellent|good|sufficient|poor) \d{4}|unrated)$/;

// ------------------------------------------------------------------------------ what a spot showed
// Its level where there is one to compare: the four, or "No sewage risk from monitored overflows". An
// isolated lake's "No river connection" and "Not covered" have none (null), and do not change from day
// to day. How many overflows upstream were discharging, where that is known (null otherwise). Its
// Environment Agency rating with the year ("good 2025"), or "unrated" for a bathing water too new to
// have one. Null for a spot whose forecast failed in this update: the note kept from before stays, so
// the next forecast is compared with the last one that had a level.
function seenRecord(s, forecast, at) {
  const R = sinceRules(), l = R.level(s);
  if (l === R.NO_FORECAST) return null;
  const n = s.now || {}, k = n.discharging_upstream;
  // None discharging is known only while every feed upstream is current: a feed that is down, or has
  // not updated within six hours, drops its overflows from the count, which is not a spill stopping.
  // A discharge counts whatever the feed's state, as in the count itself (forecast.py).
  const known = R.daily(s) && Number.isInteger(k) && k >= 0 && (k > 0 || (!n.feed_down_upstream && !n.stale_upstream));
  const c = s.classification, rating = !c ? null : c.class ? `${String(c.class).toLowerCase()} ${c.year}` : 'unrated';
  return { id: s.id, level: R.ORDER[l] !== undefined || l === R.NO_OVERFLOWS ? l : null, discharging: known ? k : null,
    rating: rating && RATED.test(rating) ? rating : null, forecast, at };
}

// The notes as stored. Anything that is not what this file writes reads as not seen, rather than stop
// the page, as the saved list does (experience.js, storedList): the spot then gets no line this time.
function seenOK(x) {
  const R = sinceRules();
  return !!x && typeof x === 'object' && typeof x.id === 'string' && Number.isFinite(x.at)
    && typeof x.forecast === 'string' && Number.isFinite(Date.parse(x.forecast))
    && (x.level === null || (typeof x.level === 'string' && (R.ORDER[x.level] !== undefined || x.level === R.NO_OVERFLOWS)))
    && (x.discharging === null || (Number.isInteger(x.discharging) && x.discharging >= 0))
    && (x.rating === null || (typeof x.rating === 'string' && RATED.test(x.rating)));
}
const readSeen = text => new Map(sinceRules().storedList(text, seenOK).map(x => [x.id, x]));

// Note what these spots showed, now. A note from a newer forecast than the one on screen (an old copy
// opened offline) is kept: going back to it would turn the next line round.
function noteSeen(seen, spots, forecast, at) {
  for (const s of spots) {
    const r = seenRecord(s, forecast, at), old = seen.get(s.id);
    if (r && !(old && Date.parse(old.forecast) > Date.parse(forecast))) seen.set(s.id, r);
  }
  return seen;
}

// ------------------------------------------------------------------------------ the line
// The day in the forecast's own words (levels.js, dayWord): "today", "on Friday", within the week
// before the forecast's day. Further back, or after it (a phone's clock ahead of an old forecast), the
// date: "on 24 September", with the year if it is another one.
const isoDay = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
function lookedWhen(at) {
  const R = sinceRules(), d = new Date(at), iso = isoDay(d), t = R.today();
  const back = Math.round((Date.parse(t + 'T12:00:00') - Date.parse(iso + 'T12:00:00')) / 864e5);
  const day = back >= 0 && back < 7 ? R.dayWord(iso)
    : 'on ' + d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', ...(iso.slice(0, 4) === t.slice(0, 4) ? {} : { year: 'numeric' }) });
  return `${day} at ${d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`;
}
// A level always says "risk" (docs/DESIGN.md, Words); the plain level in its own words.
const levelWords = l => { const R = sinceRules(); return l === R.NO_OVERFLOWS ? R.COVER[l].charAt(0).toLowerCase() + R.COVER[l].slice(1) : `${l} risk`; };
const ratingWords = r => r === 'unrated' ? 'not yet rated' : `rated ${r.replace(' ', ' for ')}`;
// One line for a spot, or '' when nothing has changed, or there is nothing to compare: a first look, or
// the same forecast as last time. One change is said, the first of: the level, the rating, and an
// overflow upstream starting or stopping (a level that moved usually did so because of it, and the
// card's own line says what set the level).
function sinceLine(was, now) {
  if (!was || !now || !(Date.parse(now.forecast) > Date.parse(was.forecast))) return '';
  const when = lookedWhen(was.at);
  if (was.level && now.level && was.level !== now.level) return `Was ${levelWords(was.level)} when you looked ${when}; now ${levelWords(now.level)}.`;
  if (was.rating && now.rating && was.rating !== now.rating) return `Was ${ratingWords(was.rating)} when you looked ${when}; now ${ratingWords(now.rating)}.`;
  const a = was.discharging, b = now.discharging;
  if (a === null || b === null || (a > 0) === (b > 0)) return '';
  return b > 0 ? `No overflow upstream was discharging when you looked ${when}; now ${b === 1 ? '1 is' : `${b} are`}.`
    : `${a === 1 ? '1 overflow upstream was' : `${a} overflows upstream were`} discharging when you looked ${when}; ${a === 1 ? 'it has' : 'all have'} stopped.`;
}

// ------------------------------------------------------------------------------ in the page
// The notes, read on first use (the first card drawn), and a copy as they were then, which the lines
// compare with for the rest of the visit.
let SEEN = null, LOOKED = null;
function seenStore() {
  if (SEEN) return SEEN;
  let text = null;
  try { text = localStorage.getItem(SEEN_KEY); } catch (e) { /* storage blocked: nothing kept, no lines */ }
  SEEN = readSeen(text); LOOKED = new Map(SEEN);
  return SEEN;
}
// Keep the notes for the saved spots (a Set of ids) only, and store them; none left, none stored.
function writeSeen(saved) {
  const seen = seenStore();
  for (const id of [...seen.keys()]) if (!saved.has(id)) seen.delete(id);
  try { if (seen.size) localStorage.setItem(SEEN_KEY, JSON.stringify([...seen.values()])); else localStorage.removeItem(SEEN_KEY); }
  catch (e) { /* not kept: no line next time */ }
}
// These spots' levels are on screen: note the saved ones.
function lookedAt(spots, forecast, saved) {
  noteSeen(seenStore(), spots.filter(s => saved.has(s.id)), forecast, Date.now());
  writeSeen(saved);
}
// A card's line, as HTML (the words are this file's own), or ''.
function sinceSaid(s, forecast) {
  seenStore();
  const t = sinceLine(LOOKED.get(s.id), seenRecord(s, forecast, Date.now()));
  return t ? `<p class="place-since">${t}</p>` : '';
}

if (typeof module === 'object' && module.exports) {
  module.exports = { SEEN_KEY, seenRecord, readSeen, noteSeen, lookedWhen, sinceLine, seenStore, writeSeen, lookedAt, sinceSaid };
}
