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
  ? { level, ORDER, NO_OVERFLOWS, NO_FORECAST, COVER, daily, today, dayWord, storedList, overflowNames, spillStart, risk, dayBecause,
      ...(typeof eaTodayAdvice === 'function' ? { eaTodayAdvice, eaTodayBrief } : {}),
      ...(typeof eaTodayRestricts === 'function' ? { eaTodayRestricts } : {}), ...(typeof liveCover === 'function' ? { liveCover } : {}) }
  : { ...require('./levels.js'), ...require('./experience.js'), ...require('./eatoday.js') };

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
    rating: rating && RATED.test(rating) ? rating : null, gap, official: seenOfficial(s), forecast, at, ...seenInputs(s) };
}
// What each day's level rested on, for what changed in the inputs (whyFacts). Added 30 Oct 2026; a note from before has
// none of these, and is explained by nothing. Per day: its level and the part that set it, in the page's words
// (levels.js, risk and dayBecause: "sewage spills", "rated poor"); the sewage spill risk as the day's sheet shows
// it, 0 to 100; the rain forecast here for the 48 hours to midday; the overflows upstream expected to spill that
// day; and the share of the rain forecast upstream that was missing. Then the overflows whose spills ended within
// 48 hours, right now's level and spill risk and when it was expected back to low risk (now.clears_at), the
// latest lab sample's time and algae check's day, and the forecast's model stamp without its code part
// (assumptions.version: a new build of the page is not a new model).
const seenNum = v => typeof v === 'number' && Number.isFinite(v) ? v : null;
function seenInputs(s) {
  const R = sinceRules(), n = s.now || {}, v = (s.assumptions || {}).version;
  const days = (s.days || []).slice(0, 5).filter(x => /^\d{4}-\d{2}-\d{2}$/.test(x.date || '')).map(x => {
    const r = R.risk(s, x), sp = seenNum(x.risk);
    return { date: x.date, level: r.level, by: r.level ? R.dayBecause(s, r).slice(0, 80) : null, score: sp === null ? null : Math.round(sp * 100),
      rain: seenNum(x.rain_48h_mm), expect: seenNum(x.expected_spilling_overflows), missing: seenNum(x.rain_missing_share) };
  });
  const nowScore = R.daily(s) && R.ORDER[n.label] !== undefined ? seenNum(n.risk) : null;
  // How many overflows upstream gave a live status at the last poll, of how many (levels.js, liveCover; 31 Oct 2026).
  const cover = typeof R.liveCover === 'function' ? R.liveCover(s) : null;
  return { days, reporting: cover ? cover.mon : null, upstream: cover ? cover.total : null, recent: R.daily(s) && Number.isInteger(n.recent_upstream) && n.recent_upstream >= 0 ? n.recent_upstream : null,
    nowLevel: nowScore === null ? null : n.label, nowScore: nowScore === null ? null : Math.round(nowScore * 100),
    clears: nowScore !== null && typeof n.clears_at === 'string' && Number.isFinite(Date.parse(n.clears_at)) ? n.clears_at.slice(0, 40) : null,
    sample: typeof (s.lab_sample || {}).taken_at === 'string' ? s.lab_sample.taken_at.slice(0, 40) : null,
    algae: typeof (s.algae || {}).date === 'string' ? s.algae.date.slice(0, 10) : null,
    model: typeof v === 'string' ? v.split(';').filter(p => !p.startsWith('code=')).join(';').slice(0, 200) : null };
}
// The official advice the spot showed (eatoday.js, #379: the reviewed notices in `official`): null for none,
// else the first notice as the compact line says it (eaTodayBrief: "EA advice against bathing · since 19 Jun
// · checked 26 Oct"), its publisher, and a key of what it says and since when, so a new check day alone is
// not a change. Its state (checked, or not re-checked since) is in the brief. Undefined where the page has
// no eatoday.js, so nothing is compared. Added 27 Oct 2026; notes from before have none, and compare nothing.
function seenOfficial(s) {
  const R = sinceRules();
  if (typeof R.eaTodayAdvice !== 'function') return undefined;
  const o = R.eaTodayAdvice(s)[0];
  return o ? { key: `${o.publisher}|${o.line}|${o.since || ''}`.slice(0, 300), brief: R.eaTodayBrief(s).slice(0, 300), publisher: o.publisher.slice(0, 100),
    restricts: typeof R.eaTodayRestricts === 'function' && R.eaTodayRestricts(s) } : null;
}
// How a note's notice is named and what it asks (28 Oct 2026): "advice" and "follow" only for one its reviewer
// marked as restricting swimming (eatoday.js, eaTodayRestricts); a note from before has no `restricts`, and reads
// as a notice to read. A reviewer reclassifying the same notice is a change (officialChange), but only where both
// notes say true or false: a note without the field is never given a past classification.
const seenNoun = o => o && o.restricts === true ? 'advice' : 'notice';
const seenAsk = o => o && o.restricts === true ? 'Follow it first.' : 'Read it first.';

// The notes as stored. Anything that is not what this file writes reads as not seen, rather than stop
// the page, as the saved list does (experience.js, storedList): the spot then gets no line this time.
function seenOK(x) {
  const R = sinceRules();
  return !!x && typeof x === 'object' && typeof x.id === 'string' && Number.isFinite(x.at)
    && typeof x.forecast === 'string' && Number.isFinite(Date.parse(x.forecast))
    && (x.level === null || (typeof x.level === 'string' && (R.ORDER[x.level] !== undefined || x.level === R.NO_OVERFLOWS)))
    && (x.discharging === null || (Number.isInteger(x.discharging) && x.discharging >= 0))
    && (x.rating === null || (typeof x.rating === 'string' && RATED.test(x.rating)))
    && (x.gap === undefined || typeof x.gap === 'boolean')
    && (x.official === undefined || x.official === null || (typeof x.official === 'object'
      && ['key', 'brief', 'publisher'].every(k => typeof x.official[k] === 'string' && x.official[k].length > 0 && x.official[k].length <= 300)
      && (x.official.restricts === undefined || typeof x.official.restricts === 'boolean')))
    && seenInputsOK(x);
}
// The inputs (seenInputs), each absent in a note from before 30 Oct 2026, else as written there.
const seenNumOK = v => v === null || (typeof v === 'number' && Number.isFinite(v));
const seenStrOK = (v, n) => v === null || (typeof v === 'string' && v.length <= n);
function seenInputsOK(x) {
  const R = sinceRules();
  return (x.days === undefined || (Array.isArray(x.days) && x.days.length <= 5 && x.days.every(d => !!d && typeof d === 'object'
      && typeof d.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(d.date)
      && (d.level === null || R.ORDER[d.level] !== undefined) && seenStrOK(d.by, 80)
      && ['score', 'rain', 'expect', 'missing'].every(k => seenNumOK(d[k])))))
    && ['recent', 'nowScore', 'reporting', 'upstream'].every(k => x[k] === undefined || x[k] === null || (Number.isInteger(x[k]) && x[k] >= 0))
    && (x.nowLevel === undefined || x.nowLevel === null || R.ORDER[x.nowLevel] !== undefined)
    && (x.clears === undefined || x.clears === null || (typeof x.clears === 'string' && x.clears.length <= 40 && Number.isFinite(Date.parse(x.clears))))
    && [['sample', 40], ['algae', 10], ['model', 200]].every(([k, n]) => x[k] === undefined || seenStrOK(x[k], n));
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

// Official advice appearing ('shown'), no longer shown ('gone'), another notice ('other'), or none of these
// (''). Only where both notes know (a note from before 27 Oct 2026, or a page without eatoday.js, has
// undefined): never a change made up from a missing field.
function officialChange(was, now) {
  const a = was.official, b = now.official;
  if (a === undefined || b === undefined) return '';
  if (!a && b) return 'shown';
  if (a && !b) return 'gone';
  const reclassified = typeof a?.restricts === 'boolean' && typeof b?.restricts === 'boolean' && a.restricts !== b.restricts;
  return a && b && (a.key !== b.key || reclassified) ? 'other' : '';
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
  const when = lookedWhen(was.at), o = officialChange(was, now), a = was.discharging, b = now.discharging;
  let line = '';
  if (was.level && now.level && was.level !== now.level) line = `Was ${levelWords(was.level)} when you looked ${when}; now ${levelWords(now.level)}.`;
  else if (was.rating && now.rating && was.rating !== now.rating) line = `Was ${ratingWords(was.rating)} when you looked ${when}; now ${ratingWords(now.rating)}.`;
  else if (o === 'shown') return `No official notice was shown when you looked ${when}; now: ${now.official.brief}. ${seenAsk(now.official)}`;
  else if (o === 'gone') return `Official ${seenNoun(was.official)} was shown when you looked ${when} (${was.official.brief}); it is no longer shown here.`;
  else if (o === 'other') return `Official ${seenNoun(now.official)} changed since you looked ${when}; now: ${now.official.brief}. ${seenAsk(now.official)}`;
  else if (a !== null && b !== null && (a > 0) !== (b > 0)) line = b > 0 ? `No overflow upstream was discharging when you looked ${when}; now ${b === 1 ? '1 is' : `${b} are`}.`
    : `${a === 1 ? '1 overflow upstream was' : `${a} overflows upstream were`} discharging when you looked ${when}; ${a === 1 ? 'it has' : 'all have'} stopped.`;
  if (!line) return '';
  // A level, a rating or a spill that changed while official advice shows: the notice in the same line, in the
  // shared helper's words (eaTodayBrief, kept in the note), so a lower sewage level never reads as an
  // all-clear. "Still" only where the note from then had it too.
  if (now.official) return `${line} Official ${seenNoun(now.official)} ${o === 'shown' ? 'now' : o === 'other' ? 'changed, now' : was.official ? 'still' : ''} shown: ${now.official.brief}. ${seenAsk(now.official)}`.replace(/ {2}shown:/, ' shown:');
  if (o === 'gone') return `${line} Official ${seenNoun(was.official)} shown then (${was.official.brief}) is no longer shown here.`;
  return line;
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
  // Official advice: the notice now, in the shared compact words with its state (checked, or not re-checked
  // since); and where one shown before is not shown now, that this is no all-clear. The level never moves for it.
  const oc = officialChange(was, now);
  // A notice that has just appeared is in the line already: the evidence adds only whose it is.
  // The line carries the notice whenever one shows (sinceLine): here only whose it is, said once.
  if (now.official) out.push(`The official ${seenNoun(now.official)} is the ${now.official.publisher}'s, not part of this level.`);
  else if (oc === 'gone') out.push(`That is not an all-clear: check the ${was.official.publisher}'s own page before you swim.`);
  if (extra.outing) out.push(extra.outing);
  const age = (nowMs - Date.parse(now.forecast)) / 60000;
  if (age > SINCE_STALE_MIN) out.push(`This forecast is ${Math.round(age / 60)} hours old, so the change may be out of date.`);
  return out.join(' ');
}
const cap1 = t => t.charAt(0).toUpperCase() + t.slice(1);
const esc1 = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);   // overflow names are data
// The spot's overflows discharging now, earliest first, from those its forecast lists (contributors: the
// ones that matter most, so possibly fewer than the count): [{name, since}], since in ms. Only where the spot
// carries `contributors`: the Saved page and the list draw from spots-lite.json, which leaves them out (kept
// lean), so there this is [] and the card links to the spot's page for which overflows (sinceSaid).
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

// ------------------------------------------------------------------------------ what changed in the inputs
// Prototype, shown only with ?why=1 in the address (sinceWhyOn), so the page is unchanged without it
// (docs/FORECAST-CHANGES-2026-10.md). Under a day whose level moved between the note and the forecast on
// screen, the inputs both notes kept (seenInputs) that changed, and nothing else: a fact either note lacks is
// not said. The model has no breakdown of a level by input, so these are what changed beside the level, never
// proof of why it moved. Each fact is one of five kinds, because a reader needs to know whether the water may
// have changed or only what SwimSignal knows about it:
//   reported   something observed: overflows reported discharging or stopped, a new lab sample, a new algae
//              check, a new rating, an official notice shown or gone
//   forecast   the weather forecast and the spill forecast made from it, for that day and the day before
//              (the model's travel times run from hours to a couple of days)
//   time       right now, modelled from spills upstream as their water moves on and dies off: it changes
//              between forecasts with nothing new reported, and the model's own clearing time says when
//   coverage   how many overflows upstream gave a live status, then and now (today only, as the statuses)
//   ours       SwimSignal's own information: a feed upstream back or lost, rain data missing or complete, a
//              new model
// The live statuses count towards right now, which raises today only (levels.js, risk), so the reported
// spills are said for today alone. Rain and spill changes under these sizes are not said: the page rounds
// rain to whole millimetres and expected spills to one decimal place.
const WHY_RAIN_MM = 2, WHY_EXPECT = 0.5, WHY_MISSING = 0.1;
// Where each level starts on the 0-100 sewage spill risk (src/dipcast/model/transport.py, SCORE_CUTS;
// tests/test_since.py checks they agree), and the largest move called small when it crosses one of them.
const WHY_CUTS = [[15, 'moderate'], [40, 'high'], [70, 'very high']], WHY_SMALL = 5;
const WHY_MODEL = { spill: 'spill model', cal: 'calibration', ecoli: 'E. coli model', rain: 'weather source' };
const whyDay = (note, date) => (note.days || []).find(x => x.date === date) || null;
const whyMM = v => `${Math.round(v)} mm`;
const whyIssueDay = iso => new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London' }).format(new Date(iso));   // a forecast's UK day
const whyStamp = v => new Map(String(v).split(';').map(p => p.split('=')).filter(p => p.length === 2));
// The facts for one day (date), or null where either note has no inputs for it or its level did not move.
function whyFacts(was, now, date) {
  const a = was && whyDay(was, date), b = now && whyDay(now, date);
  if (!a || !b || !a.level || !b.level || a.level === b.level) return null;
  const R = sinceRules(), facts = [], fact = (kind, text) => facts.push({ kind, text });
  // The day turned into today between the two (a note from Friday evening, Saturday's forecast now): today's
  // level includes right now, a later day's does not (levels.js, risk).
  const then = whyIssueDay(was.forecast);
  if (date === R.today() && then < date && b.by !== a.by && /right now|recent/.test(b.by)) fact('time', `Then this day was ${
    then === new Date(Date.parse(date + 'T12:00:00Z') - 864e5).toISOString().slice(0, 10) ? 'tomorrow' : 'a later day'}; today's level also counts right now, from spills upstream.`);
  if (date === R.today()) {
    const x = was.discharging, y = now.discharging;
    if (Number.isInteger(x) && Number.isInteger(y) && x !== y) fact('reported', `Overflows upstream reported discharging: ${x} then, ${y} now.`);
    const r = was.recent, q = now.recent;
    if (Number.isInteger(r) && Number.isInteger(q) && r !== q) fact('reported', `Overflows upstream whose spills ended in the last 48 hours: ${r} then, ${q} now.`);
    const p = was.nowScore, n = now.nowScore;
    if (Number.isInteger(p) && Number.isInteger(n) && p !== n) {
      const back = was.clears && n < p && Date.parse(was.clears) <= Date.parse(now.forecast) ? ` The model expected it back to low risk by ${issuedWords(was.clears)}.` : '';
      fact('time', `Right now, as modelled from spills upstream while their water moves on and dies off, was ${p} of 100 then and is ${n} now.${back}`);
    }
    const c = was.reporting, d = now.reporting;
    if (Number.isInteger(c) && Number.isInteger(d) && (c !== d || was.upstream !== now.upstream))
      fact('coverage', `Overflows upstream giving a live status: ${c} of ${was.upstream} then, ${d} of ${now.upstream} now.`);
    if (typeof was.gap === 'boolean' && typeof now.gap === 'boolean' && was.gap !== now.gap) fact('ours', was.gap
      ? 'A feed upstream was down or late then; every feed is reporting now.' : 'A feed upstream is down or late now, so its overflows are not counted.');
  }
  if (was.sample !== undefined && now.sample && was.sample !== now.sample) fact('reported', 'A new Environment Agency lab sample has arrived.');
  if (was.algae !== undefined && now.algae && was.algae !== now.algae) fact('reported', 'A new algae check has arrived.');
  if (was.rating && now.rating && was.rating !== now.rating) fact('reported', `The Environment Agency rating changed: ${ratingWords(was.rating)} then, ${ratingWords(now.rating)} now.`);
  const o = officialChange(was, now);
  if (o === 'shown' || o === 'other') fact('reported', `Official ${seenNoun(now.official)} is shown now: ${now.official.brief}.`);
  else if (o === 'gone') fact('reported', `Official ${seenNoun(was.official)} shown then is no longer shown.`);
  if (a.rain !== null && b.rain !== null && Math.abs(b.rain - a.rain) >= WHY_RAIN_MM)
    fact('forecast', `Rain here in the 48 hours to midday: ${whyMM(a.rain)} forecast then, ${whyMM(b.rain)} now.`);
  // That day and the day before, where both notes have them: its water may still be arriving.
  const prev = new Date(Date.parse(date + 'T12:00:00Z') - 864e5).toISOString().slice(0, 10);
  const spills = [[whyDay(was, prev), whyDay(now, prev), `${R.dayWord(prev)}, the day before`], [a, b, R.dayWord(date)]]
    .filter(([x, y]) => x && y && x.expect !== null && y.expect !== null && Math.abs(y.expect - x.expect) >= WHY_EXPECT);
  if (spills.length) fact('forecast', `Overflows upstream expected to spill ${spills.map(([x, y, w]) => `${w}: ${x.expect} then, ${y.expect} now`).join('; ')}.`);
  if (a.missing !== null && b.missing !== null && Math.abs(b.missing - a.missing) >= WHY_MISSING) fact('ours', a.missing > b.missing
    ? `Rain data was missing for overflows carrying ${Math.round(a.missing * 100)}% of the model's weight here then, ${b.missing ? `${Math.round(b.missing * 100)}%` : 'none'} now.`
    : `Rain data is missing for overflows carrying ${Math.round(b.missing * 100)}% of the model's weight here now, against ${Math.round(a.missing * 100)}% then.`);
  if (was.model && now.model && was.model !== now.model) {
    const m = whyStamp(was.model), n = whyStamp(now.model), parts = [...new Set([...m.keys(), ...n.keys()])].filter(k => m.get(k) !== n.get(k));
    fact('ours', `SwimSignal changed its ${parts.map(k => WHY_MODEL[k] || 'forecast').join(' and ')} between the two forecasts.`);
  }
  return { date, was: a, now: b, facts };
}
// The facts as one passage, or ''. First what set the level, where that changed; then the facts, under what
// kind of change they are; and where no fact was found, the spill risk itself, called small where it moved by
// WHY_SMALL or less across the line between two levels, and otherwise said plainly to have no kept input beside it.
function whySaid(was, now, date) {
  const f = whyFacts(was, now, date);
  if (!f) return '';
  const { was: a, now: b } = f, out = [];
  if (a.by !== b.by) out.push(`The level was set by ${a.by} then; it is now set by ${b.by}.`);
  const of = k => f.facts.filter(x => x.kind === k).map(x => x.text), time = of('time'), ours = [...of('coverage'), ...of('ours')];
  const real = [...of('reported'), ...of('forecast')];
  if (real.length) out.push(`Reported or forecast: ${real.join(' ')}`);
  if (time.length) out.push(`${real.length ? 'With time' : 'With time, and nothing new reported'}: ${time.join(' ')}`);
  if (ours.length) out.push(`In what SwimSignal knows, not necessarily the water: ${ours.join(' ')}`);
  const sc = a.score !== null && b.score !== null && a.score !== b.score;
  if (!f.facts.length && sc) {
    const lo = Math.min(a.score, b.score), hi = Math.max(a.score, b.score), cut = WHY_CUTS.find(([c]) => lo < c && c <= hi);
    out.push(hi - lo <= WHY_SMALL && cut && a.by === b.by
      ? `A small change: sewage spill risk ${a.score} of 100 then, ${b.score} now, and ${cut[1]} risk starts at ${cut[0]}.`
      : `No other input kept here changed by enough to show. Sewage spill risk: ${a.score} of 100 then, ${b.score} now.`);
  } else if (sc && Math.abs(b.score - a.score) >= WHY_SMALL) out.push(`Sewage spill risk: ${a.score} of 100 then, ${b.score} now.`);
  else if (!f.facts.length && a.by === b.by) out.push('No input kept here changed by enough to show.');
  return out.join(' ');
}
// Which day to explain under a line about the headline (sinceLine): today or tomorrow, whichever now has the
// headline's level and changed, today first. The headline is the worst of right now, today and tomorrow.
function whyHeadlineDay(was, now) {
  const R = sinceRules(), t = R.today(), days = (now.days || []).filter(d => d.date >= t).slice(0, 2);
  const moved = days.filter(d => { const a = whyDay(was, d.date); return a && a.level && d.level && a.level !== d.level; });
  return (moved.find(d => d.level === now.level) || moved[0] || {}).date || null;
}
// Why the headline moved where no day under it did: the day that set it then has passed ("Then high risk was for
// Thursday, which has passed."), and, where that forecast already had the days left at the level shown now, so.
// Or ''. The headline is the worst of right now, today and tomorrow, so it moves when its window does.
function whyHeadlinePassed(was, now) {
  const R = sinceRules(), t = R.today(), gone = (was.days || []).find(d => d.date < t && d.level === was.level);
  if (!gone || !was.level || !now.level || R.ORDER[was.level] === undefined || R.ORDER[now.level] === undefined) return '';
  const left = (was.days || []).filter(d => d.date >= t).slice(0, 2), worst = left.reduce((w, d) => !w || R.ORDER[d.level] > R.ORDER[w] ? d.level : w, null);
  const wd = new Date(gone.date + 'T12:00:00Z').toLocaleDateString('en-GB', { weekday: 'long', timeZone: 'UTC' });
  return `Then ${levelWords(was.level)} was for ${wd}, which has passed.` + (left.length === 2 && worst === now.level
    ? ` That forecast already had today and tomorrow at ${levelWords(now.level)}.` : '');
}
// The day of the outing planned at this spot (the plan kept in this browser, as sinceOuting reads it), or null.
function whyOutingDay(id, planText) {
  if (!planText) return null;
  const q = new URLSearchParams(String(planText).replace(/^#/, '')), day = q.get('day');
  return (q.get('spot') === id || q.get('backup') === id) && /^\d{4}-\d{2}-\d{2}$/.test(day || '') && day >= sinceRules().today() ? day : null;
}
// A line for the outing's day when the headline did not move but that day did: "Saturday, the day of your
// outing, was moderate risk when you looked today at 09:05; now high risk." Or ''.
function whyDayLine(was, now, day) {
  const a = was && whyDay(was, day), b = now && whyDay(now, day);
  if (!a || !b || !a.level || !b.level || a.level === b.level || !(Date.parse(now.forecast) > Date.parse(was.forecast))) return '';
  const d = sinceRules().dayWord(day).replace(/^on /, '');
  return `${cap1(d)}, the day of your outing, was ${levelWords(a.level)} when you looked ${lookedWhen(was.at)}; now ${levelWords(b.level)}.`;
}
const sinceWhyOn = () => { try { return new URLSearchParams(location.search).get('why') === '1'; } catch (e) { return false; } };

// ------------------------------------------------------------------------------ since the last update
// For every visitor, no saved spot or earlier visit needed (docs/ISSUED-HISTORY-2026-10.md; prototype, ?why=1):
// the build keeps each issue's records (src/dipcast/issue_history.py, the same seenRecord as the notes above, made
// at issue time by scripts/issue_records.cjs) and publishes the previous successful issue's in
// data/since-last.json. The spot's page compares that record with the forecast on screen, day by day, with the
// facts above (whySaid): what changed beside a level, never why it moved.
const LAST_DAYS_SAID = 3;   // at most this many days with a level that moved
// How long before this issue the previous one was, in words: "30 min", "5 h 10 min", "1 day 2 h".
function lastGap(ms) {
  const m = Math.max(0, Math.round(ms / 60000)), d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), r = m % 60;
  return d ? `${d} day${d === 1 ? '' : 's'}${h ? ` ${h} h` : ''}` : h ? `${h} h${r ? ` ${r} min` : ''}` : `${r} min`;
}
// The days whose level moved between the two records, in date order: [{ date, was, now, said }].
function lastChanges(prev, cur) {
  return (cur.days || []).filter(d => { const a = whyDay(prev, d.date); return a && a.level && d.level && a.level !== d.level; })
    .map(d => ({ date: d.date, was: whyDay(prev, d.date).level, now: d.level, said: whySaid(prev, cur, d.date) }));
}
// The passage for a spot, as { head, days } (lastParts) or one plain text (lastSaid), or '' where there is no file
// to compare with. meta: since-last.json without its spots; prev: its record for this spot (null where the spot was
// not in that issue); cur: this issue's record for it (seenRecord). Every case says what it compared with, so a
// quiet line is never read as "nothing happened" without saying against what.
function lastParts(meta, prev, cur) {
  if (!meta || !cur) return null;
  const R = sinceRules(), p = meta.previous;
  if (!p) return { head: meta.why === 'stale' ? 'No earlier update within a day to compare with.'
    : meta.why === 'not kept' ? 'The update shown before this one is not on record, so there is nothing to compare with.'
    : 'No earlier update on record to compare with yet.', days: [] };
  if (Date.parse(p.issued_at) >= Date.parse(cur.forecast)) return null;   // an old page against a newer file: say nothing
  const head = `Since the update issued ${issuedWords(p.issued_at)}, ${lastGap(Date.parse(cur.forecast) - Date.parse(p.issued_at))} before this one:`;
  if (!prev) return { head: `${head} this spot was not in that update, so there is nothing to compare.`, days: [] };
  const moved = lastChanges(prev, cur);
  if (!moved.length) return { head: `${head} no level changed.`, days: [] };
  const days = moved.slice(0, LAST_DAYS_SAID).map(x => ({ day: cap1(R.dayWord(x.date).replace(/^on /, '')),
    text: `${levelWords(x.was)} then, ${levelWords(x.now)} now.` + (x.said ? ` What changed in the inputs: ${x.said}` : ' The earlier update did not keep the inputs for this day.') }));
  const more = moved.length - LAST_DAYS_SAID;
  if (more > 0) days.push({ day: '', text: `${more} more day${more === 1 ? '' : 's'} changed too.` });
  return { head, days };
}
function lastSaid(meta, prev, cur) {
  const x = lastParts(meta, prev, cur);
  return !x ? '' : [x.head, ...x.days.map(d => d.day ? `${d.day}: ${d.text}` : d.text)].join(' ');
}
// On the spot's page: the file once a visit (it is the same for every spot), then the passage into the host.
let LAST_FILE = null;
function mountLast(d, forecast, host) {
  if (!host) return;
  LAST_FILE = LAST_FILE || fetch('data/since-last.json', { cache: 'no-cache' }).then(r => (r.ok ? r.json() : null)).catch(() => null);
  LAST_FILE.then(f => { if (!host.isConnected || !f || f.issued_at !== forecast) return;   // a file from another issue than the page's: nothing
    const x = lastParts(f, (f.spots || {})[d.id] || null, seenRecord(d, forecast, Date.now()));
    host.innerHTML = !x ? '' : `<div class="since-last"><p>${esc1(x.head)}</p>`
      + x.days.map(y => `<p>${y.day ? `<b>${esc1(y.day)}</b>: ` : ''}${esc1(y.text)}</p>`).join('') + '</div>'; });
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
  const was = LOOKED.get(s.id), now = seenRecord(s, forecast, Date.now());
  let plan = null;
  try { plan = localStorage.getItem(KEPT_PLAN_KEY); } catch (e) { /* no plan kept: no outing to read against */ }
  // ?why=1 (prototype): the outing's day when only it moved, and under either line, why (whySaid).
  const why = sinceWhyOn(), outing = why ? whyOutingDay(s.id, plan) : null;
  // Only under a line about the level: a line about a spill or a notice already says what changed.
  const moved = why && !!was && !!now && !!was.level && was.level !== now.level;
  let t = sinceLine(was, now), day = t && moved ? whyHeadlineDay(was, now) : null;
  if (!t && outing) { t = whyDayLine(was, now, outing); day = t ? outing : null; }
  if (!t) return '';
  const said = day ? whySaid(was, now, day) : t && moved ? whyHeadlinePassed(was, now) : '';
  const spills = sinceSpills(s), ev = sinceEvidence(was, now, Date.now(), { spills, outing: sinceOuting(s.id, plan) });
  // Discharging now but no names in this data (spots-lite.json): which ones, and since when, are on the spot's
  // page (its "Overflows that matter most"), one tap away, rather than names this card does not have.
  const which = now.discharging > 0 && !spills.length && typeof spotPath === 'function'
    ? ` <a href="${esc1(spotPath(s.id))}" data-id="${esc1(s.id)}">Which overflows: the spot's page</a>` : '';
  return `<p class="place-since">${esc1(t)}${said ? ` <span class="since-why">What changed in the inputs: ${esc1(said)}</span>` : ''} <span class="since-ev">${esc1(ev)}${which}</span></p>`;
}

// ------------------------------------------------------------------------------ the Saved page's summary
// Over the places on the Saved page (2 Nov 2026): one sentence on what changed at the list's spots since this
// browser last showed them, by the same rules as each card's line (sinceLine), so it never says more than the
// cards do, and never why. rows: [{ name, was, now }], was the note kept (or undefined) and now this
// forecast's record (seenRecord; null where the spot has no forecast). Returns { state, text, changed }:
//   none      no spot has a note: nothing to compare yet
//   same      notes, but the forecast on screen is the one already seen
//   quiet     a newer forecast and no change the cards would say
//   changed   the spots whose card has a line, by name
// The time is said only where every note compared was made at the same look; otherwise "since you last
// looked at each", as the cards give each one's time.
function sinceSummary(rows) {
  const notes = rows.filter(r => r.was && r.now), newer = notes.filter(r => Date.parse(r.now.forecast) > Date.parse(r.was.forecast));
  const n = rows.length, spots = k => `${k} spot${k === 1 ? '' : 's'}`;
  if (!notes.length) return { state: 'none', changed: [], text: n === 1 ? 'This browser has not shown this spot before, so there is nothing to compare yet. Next time, what changed since now is said here.'
    : 'This browser has not shown these spots before, so there is nothing to compare yet. Next time, what changed since now is said here.' };
  const whens = [...new Set(notes.map(r => lookedWhen(r.was.at)))], when = whens.length === 1 ? `you looked ${whens[0]}` : 'you last looked at each';
  const left = n - notes.length, also = left ? ` ${left === 1 ? 'One spot has' : `${left} spots have`} nothing to compare with yet.` : '';
  if (!newer.length) return { state: 'same', changed: [], text: `No new forecast since ${when}.${also}` };
  const changed = newer.filter(r => sinceLine(r.was, r.now)).map(r => r.name);
  if (!changed.length) return { state: 'quiet', changed, text: `Since ${when}, no level, rating or official notice changed at ${n === 1 ? 'this spot' : notes.length === n ? `your ${spots(n)}` : `${notes.length} of your ${spots(n)}`}, and no overflow upstream was reported starting or stopping.${also}` };
  // Names hold commas ("River Wharfe, Burnsall"), so a list of them is kept apart with semicolons.
  const sep = changed.some(x => x.includes(',')) ? '; ' : ', ';
  const names = changed.length === 1 ? changed[0] : `${changed.slice(0, -1).join(sep)}${sep === '; ' ? '; and' : ' and'} ${changed.at(-1)}`;
  return { state: 'changed', changed, text: `Since ${when}, ${n === 1 ? 'this spot' : `${changed.length} of your ${spots(n)}`} changed${n === 1 ? '' : `: ${names}`}. ${changed.length === 1 ? 'Its card says' : 'Each card says'} what changed and which forecasts it compares.${also}` };
}
// In the page: the list's spots against the notes as they were when the page opened (LOOKED).
function sinceSummaryFor(spots, forecast) {
  seenStore();
  return sinceSummary(spots.map(s => ({ name: s.name, was: LOOKED.get(s.id), now: seenRecord(s, forecast, Date.now()) })));
}

if (typeof module === 'object' && module.exports) {
  module.exports = { sinceSummary, sinceSummaryFor, lastGap, lastChanges, lastParts, lastSaid, mountLast, LAST_DAYS_SAID, SEEN_KEY, SINCE_STALE_MIN, WHY_CUTS, whyFacts, whySaid, whyHeadlineDay, whyHeadlinePassed, whyOutingDay, whyDayLine, levelWords, seenRecord, seenOfficial, officialChange, sinceEvidence, sinceSpills, sinceOuting, issuedWords, readSeen, noteSeen, lookedWhen, sinceLine, seenStore, writeSeen, lookedAt, sinceSaid };
}
