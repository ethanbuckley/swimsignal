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
  ? { level, ORDER, NO_OVERFLOWS, NO_FORECAST, COVER, daily, today, dayWord, storedList, overflowNames, spillStart }
  : { ...require('./levels.js'), ...require('./experience.js') };

const SEEN_KEY = 'dipcast.seen';
const RATED = /^((excellent|good|sufficient|poor) \d{4}|unrated)$/;

// ------------------------------------------------------------------------------ what a spot showed
// Its level where there is one to compare: the four, or "No monitored overflow found upstream". An
// isolated lake (the same words, levels.js COVER) and "Not covered" have none (null), and do not
// change from day to day. How many overflows upstream were discharging, where that is known (null
// otherwise). Its
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
  // gap: the count is not known because a feed upstream is down or late (the evidence line says so, rather
  // than say nothing). Added 26 Oct 2026; a note kept before then has none, and reads as no gap.
  const gap = !!(R.daily(s) && Number.isInteger(k) && !known);
  return { id: s.id, level: R.ORDER[l] !== undefined || l === R.NO_OVERFLOWS ? l : null, discharging: known ? k : null,
    rating: rating && RATED.test(rating) ? rating : null, gap, forecast, at };
}

// The notes as stored. Anything that is not what this file writes reads as not seen, rather than stop
// the page, as the saved list does (experience.js, storedList): the spot then gets no line this time.
function seenOK(x) {
  const R = sinceRules();
  return !!x && typeof x === 'object' && typeof x.id === 'string' && Number.isFinite(x.at)
    && typeof x.forecast === 'string' && Number.isFinite(Date.parse(x.forecast))
    && (x.level === null || (typeof x.level === 'string' && (R.ORDER[x.level] !== undefined || x.level === R.NO_OVERFLOWS)))
    && (x.discharging === null || (Number.isInteger(x.discharging) && x.discharging >= 0))
    && (x.rating === null || (typeof x.rating === 'string' && RATED.test(x.rating)))
    && (x.gap === undefined || typeof x.gap === 'boolean');
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

// The evidence under a line (sinceSaid): a change is never said without it. Which two forecasts were
// compared, by their issue times ("issued Fri 17:31 and Sun 15:29"); what the overflow feeds upstream
// report now, against then where both are known; where the count is not known, why; for a rating, whose
// it is; and a forecast older than the page calls stale (index.html, STALE_MIN: 8 h), said as out of date.
// No word here says safe: a lower level is a lower forecast risk, nothing more.
const SINCE_STALE_MIN = 8 * 60;
const issuedWords = iso => { const d = new Date(iso);
  return `${d.toLocaleDateString('en-GB', { weekday: 'short' })} ${d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`; };
const overflowsWord = n => n === 1 ? '1 overflow upstream' : `${n} overflows upstream`;
// HOOK (#379, official advice): once #379's `official` list is final in spots.json, official advice
// appearing or clearing since the last look is one more field in seenRecord's note, compared here and said
// with its source and time. Until then nothing is said about it here.
// extra.spills: which overflows are discharging now and since when (sinceSpills), named where the spot's
// forecast names them; extra.outing: the outing planned at this spot (sinceOuting), so the change is read
// against it.
function sinceEvidence(was, now, nowMs = Date.now(), extra = {}) {
  if (!was || !now) return '';
  const out = [`Forecasts compared: issued ${issuedWords(was.forecast)} and ${issuedWords(now.forecast)}.`];
  const a = was.discharging, b = now.discharging, then = a === null || a === undefined ? '' : `, against ${a} then`;
  const named = (extra.spills || []).slice(0, 2), more = Number.isInteger(b) ? b - named.length : 0;
  const which = !named.length || !b ? '' : `: ${named.map(x => `${x.name} since ${issuedWords(new Date(x.since).toISOString())}`).join(', ')}${more > 0 ? `, and ${more} more` : ''}`;
  if (Number.isInteger(b)) out.push(b ? `${cap1(overflowsWord(b))} reported discharging now${then}${which}.` : `No overflow upstream reported discharging now${then}.`);
  else if (now.gap) out.push('How many overflows upstream are discharging now is not known: a feed upstream is down or has not updated within six hours.');
  else if (now.level) out.push('No live overflow count for this spot.');
  if (was.rating && now.rating && was.rating !== now.rating) out.push("The rating is the Environment Agency's, from its yearly bathing water classification.");
  if (extra.outing) out.push(extra.outing);
  const age = (nowMs - Date.parse(now.forecast)) / 60000;
  if (age > SINCE_STALE_MIN) out.push(`This forecast is ${Math.round(age / 60)} hours old, so the change may be out of date.`);
  return out.join(' ');
}
const cap1 = t => t.charAt(0).toUpperCase() + t.slice(1);
const esc1 = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);   // overflow names are data
// The spot's overflows discharging now, earliest first, from those its forecast lists (contributors: the
// ones that matter most, so possibly fewer than the count): [{name, since}], since in ms.
function sinceSpills(s) {
  const R = sinceRules();
  return (s.contributors || []).map(c => ({ c, since: R.spillStart(c) })).filter(x => x.since !== null)
    .sort((x, y) => x.since - y.since).map(x => ({ name: R.overflowNames(x.c).plain.slice(0, 80), since: x.since }));
}
// The outing planned on Plan a swim (outing.js), as the plan kept in this browser holds it (index.html,
// PLAN_KEY, dipcast.plan: the plan's address, with when=, spot= and backup=): a sentence when this spot is
// its spot or its backup and its day has not passed, else ''.
const KEPT_PLAN_KEY = 'dipcast.plan', OUTING_WHEN = /^(morning|afternoon|evening|[01]\d|2[0-3])$/;
function sinceOuting(id, planText) {
  if (!planText) return '';
  const R = sinceRules(), q = new URLSearchParams(String(planText).replace(/^#/, ''));
  const day = q.get('day'), when = q.get('when'), role = q.get('spot') === id ? 'spot' : q.get('backup') === id ? 'backup' : null;
  if (!role || !/^\d{4}-\d{2}-\d{2}$/.test(day || '') || day < R.today()) return '';
  const d = R.dayWord(day).replace(/^on /, ''), part = OUTING_WHEN.test(when || '') ? when : null;
  const w = !part ? d : /^\d/.test(part) ? `${d} at ${part}:00` : d === 'today' ? `this ${part}` : `${d} ${part}`;
  return role === 'spot' ? `This is the spot of your outing ${w}.` : `This is the backup for your outing ${w}.`;
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
  const was = LOOKED.get(s.id), now = seenRecord(s, forecast, Date.now()), t = sinceLine(was, now);
  if (!t) return '';
  let plan = null;
  try { plan = localStorage.getItem(KEPT_PLAN_KEY); } catch (e) { /* no plan kept: no outing to read against */ }
  const ev = sinceEvidence(was, now, Date.now(), { spills: sinceSpills(s), outing: sinceOuting(s.id, plan) });
  return `<p class="place-since">${t} <span class="since-ev">${esc1(ev)}</span></p>`;
}

if (typeof module === 'object' && module.exports) {
  module.exports = { SEEN_KEY, SINCE_STALE_MIN, seenRecord, sinceEvidence, sinceSpills, sinceOuting, issuedWords, readSeen, noteSeen, lookedWhen, sinceLine, seenStore, writeSeen, lookedAt, sinceSaid };
}
