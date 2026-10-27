// What would change this plan: under the outing's two columns on Plan a swim (outing.js), for its spot and
// its backup, the things that would change the plan, and which of them have changed since the swimmer
// planned it. For each spot: the official advice for that water first, in eatoday.js's shared words and
// never softened; the level for the outing's day (levels.js, dayLevel); the river or lake at the spot's
// gauge, where it has one (spots.json `river_state` and `flow_state`, as the River level tile reads them);
// then which forecast the levels were checked against, by its issue time, and what to look at again
// before leaving. outing.js calls outingWatchDraw from drawOuting; the rules are here, where Node can test them.
//
// When the outing has a spot, this browser keeps a note of what the spot and the backup showed for its
// day (OUTING_WATCH_KEY), sent nowhere. A spot's note stays until the outing's day changes or that spot
// leaves the outing, so each later visit compares with what it showed when it was planned, not with the
// last visit (since.js compares a saved spot with the last look instead). The notice is compared by
// since.js's rules (seenOfficial, officialChange), and the levels are said in its words (levelWords).
//
// A plain script, as since.js: globals in the page, exports in Node. It asks for the other scripts' rules
// when it is called, so in the page it only has to load before the outing is drawn.
const owRules = () => typeof dayLevel === 'function'
  ? { dayLevel, daily, today, dayWord, ORDER, NO_FORECAST, NO_OVERFLOWS, NO_RIVER, NOT_COVERED, COVER, flowFacts }
  : { ...require('./levels.js'), ...require('./experience.js') };
const owSince = () => typeof seenOfficial === 'function' ? { seenOfficial, officialChange, issuedWords, levelWords } : require('./since.js');

const OUTING_WATCH_KEY = 'dipcast.outingwatch';
const owEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const owDay = iso => owRules().dayWord(iso).replace(/^on /, '');   // "today", "tomorrow", "Saturday"
const owLong = iso => new Date(iso + 'T12:00:00Z').toLocaleDateString('en-GB', { timeZone: 'UTC', weekday: 'long', day: 'numeric', month: 'long' });
const owWhen = ms => owSince().issuedWords(new Date(ms).toISOString());   // "Mon 18:20", on the device's clock
const OW_ISO = /^\d{4}-\d{2}-\d{2}$/;

// ------------------------------------------------------------------------------ what a spot showed
// The river at the spot's gauge in the River level tile's words: "low water", "usual level", "high water",
// "very high water", or a lake's place against its usual range; "rising fast" while experience.js's
// flowFacts says so (a rise it still counts as current); "no current reading" for a reading the build
// found over a day old. Null without a gauge, or with nothing to say. Not part of the pollution level.
const OW_RIVER = { low: 'low water', normal: 'usual level', high: 'high water', 'very high': 'very high water' };
function owRiver(s, nowMs, generatedAt) {
  const rs = s.river_state, R = owRules();
  if (!rs || typeof rs.station !== 'string' || !rs.station || (!rs.stale && (rs.level_m === null || rs.level_m === undefined))) return null;
  const lake = rs.water === 'lake', lo = rs.typical_low_m, hi = rs.typical_high_m, ranged = Number.isFinite(lo) && Number.isFinite(hi) && hi > lo;
  const word = rs.stale ? 'no current reading'
    : R.flowFacts(s, nowMs, generatedAt).some(f => f.lead === 'River rising fast') ? 'rising fast'
    : lake ? (!ranged ? '' : rs.level_m < lo ? 'below its usual range' : rs.level_m > hi ? 'above its usual range' : 'in its usual range')
    : OW_RIVER[rs.label] || '';
  return word ? { word, gauge: rs.station.slice(0, 100), lake } : null;
}
// What a spot shows for the outing's day: its level that day (one of levels.js's, NO_FORECAST where this
// forecast has none for the day), its official advice (since.js, seenOfficial: undefined where the page has
// no eatoday.js), the river at its gauge, the forecast it came from and when the note was made.
function outingWatchRecord(s, day, forecast, at, nowMs = at) {
  return { id: s.id, day, level: owRules().dayLevel(s, day), official: owSince().seenOfficial(s), river: owRiver(s, nowMs, forecast), forecast, at };
}

// The note as stored, read back safely: anything that is not what this file writes reads as no note, so the
// outing is noted afresh rather than the page stopping.
const owLevels = () => { const R = owRules(); return new Set([...Object.keys(R.ORDER), R.NO_FORECAST, R.NO_OVERFLOWS, R.NO_RIVER, R.NOT_COVERED]); };
const owText = (x, n) => typeof x === 'string' && x.length > 0 && x.length <= n;
function outingWatchOK(r, day) {
  return !!r && typeof r === 'object' && owText(r.id, 100) && r.day === day && owLevels().has(r.level)
    && Number.isFinite(r.at) && typeof r.forecast === 'string' && Number.isFinite(Date.parse(r.forecast))
    && (r.official === undefined || r.official === null || (typeof r.official === 'object' && ['key', 'brief', 'publisher'].every(k => owText(r.official[k], 300))))
    && (r.river === null || (typeof r.river === 'object' && owText(r.river.word, 60) && owText(r.river.gauge, 100) && typeof r.river.lake === 'boolean'));
}
function outingWatchRead(text) {
  let v; try { v = JSON.parse(text || 'null'); } catch (e) { return null; }
  if (!v || typeof v !== 'object' || !OW_ISO.test(v.day || '') || !Array.isArray(v.items)) return null;
  const items = v.items.filter(r => outingWatchOK(r, v.day)).slice(0, 2);
  return items.length ? { day: v.day, items } : null;
}
// The note for the outing now: plan = { day, ... }, pair = outing.js's outingPair (main, backup, either
// null). A spot noted before for the same day keeps its note; a new spot, or a new day, is noted now.
// Null with no spot: nothing kept.
function outingWatchNote(old, plan, pair, forecast, nowMs) {
  if (!pair.main || !OW_ISO.test(plan.day || '')) return null;
  const kept = old && old.day === plan.day ? old.items : [];
  return { day: plan.day, items: [pair.main, pair.backup].filter(Boolean)
    .map(s => kept.find(r => r.id === s.id) || outingWatchRecord(s, plan.day, forecast, nowMs)) };
}

// ------------------------------------------------------------------------------ the words
// A level in its own words, with its noun (docs/DESIGN.md, Words): since.js's for the four and "no monitored
// overflow found upstream"; the others from levels.js's COVER; no forecast for the day said as that.
function owLevel(l, day) {
  const R = owRules(), low1 = t => t.charAt(0).toLowerCase() + t.slice(1);
  if (R.ORDER[l] !== undefined || l === R.NO_OVERFLOWS) return owSince().levelWords(l);
  if (l === R.NO_FORECAST) return `no forecast for ${owDay(day)} in this update`;
  return low1(R.COVER[l] || l);
}
// Each thing for one spot, as plain sentences (escaped where they are drawn): official advice first, the
// level for the day, then the river at its gauge. was: its note (null for none); now: what it shows now.
// Compared only where was comes from an older forecast than now's: the same forecast cannot have changed,
// and an older one on screen (a copy opened offline) is not news. Returns { lines, changed, compared }.
function outingWatchLines(was, now) {
  const S = owSince(), R = owRules(), day = now.day, out = [];
  const compared = !!was && Date.parse(now.forecast) > Date.parse(was.forecast);
  let changed = 0;
  const say = (label, value, before) => {
    if (!compared || before === null) return out.push(`${label}: ${value}.`);
    if (before === value) return out.push(`${label}: ${value}. No change since then.`);
    changed++; out.push(`${label}: ${value}. Changed: was ${before}.`);
  };
  // Official advice, never softened: a notice that is no longer shown is not an all-clear (since.js's words).
  if (now.official !== undefined) {
    const o = compared ? S.officialChange(was, now) : '';
    if (now.official) {
      const lead = `Official advice: ${now.official.brief}. Follow it first.`;
      if (!compared || was.official === undefined) out.push(lead);
      else if (o === 'shown') { changed++; out.push(`${lead} Changed: none was shown then.`); }
      else if (o === 'other') { changed++; out.push(`${lead} Changed: was ${was.official.brief}.`); }
      else out.push(`${lead} No change since then.`);
    } else if (o === 'gone') {
      changed++;
      out.push(`Official advice: none shown here now. Changed: was ${was.official.brief}. That is not an all-clear: check the ${was.official.publisher}'s own page before you swim.`);
    } else say('Official advice', 'none shown', compared && was.official !== undefined ? 'none shown' : null);
  }
  say(`Level for ${owDay(day)}`, owLevel(now.level, day), compared ? owLevel(was.level, day) : null);
  // The river now, at the gauge. A gauge with no reading in this update, where the note had one, says so.
  const rv = now.river || (compared && was.river ? { ...was.river, word: 'no reading in this update' } : null);
  if (rv) say(`${rv.lake ? 'Lake' : 'River'} at the gauge at ${rv.gauge}`, rv.word,
    compared && was.river && was.river.gauge === rv.gauge ? was.river.word : null);
  return { lines: out, changed, compared };
}

// The whole section, as HTML. w = { day (the outing's), today, spots: [{ name, role ('your spot' or 'your
// backup'), was, now }], passed (an earlier outing's day that has gone by, or null), kept (false where this
// browser could not keep the note), forecast (the issue time on screen) }.
function outingWatchSection(w) {
  const S = owSince(), R = owRules();
  if (!w.spots.length) return '';
  const head = '<h3 class="outing-watch-h">What would change this plan</h3>';
  const passed = w.passed ? `<p>Your outing on ${owEsc(owLong(w.passed))} has passed.</p>` : '';
  if (w.day < w.today) return `<div class="outing-watch">${head}<p>This outing's day has passed, so nothing is compared with it.</p></div>`;
  const parts = w.spots.map(x => ({ ...x, ...outingWatchLines(x.was, x.now) }));
  const compared = parts.filter(p => p.compared), changed = parts.reduce((n, p) => n + p.changed, 0);
  const older = parts.find(p => p.was && Date.parse(p.now.forecast) < Date.parse(p.was.forecast));
  let lead = '';
  if (compared.length) lead = changed ? `${changed === 1 ? '1 thing has' : `${changed} things have`} changed since you planned this outing.` : 'Nothing has changed since you planned this outing.';
  else if (!w.kept) lead = 'This browser cannot keep a note, so it cannot say later what has changed.';
  else if (!older) lead = `${w.passed ? `It now follows the same spots for ${owDay(w.day)}. ` : 'This browser has noted what each shows now. '}When a newer forecast is issued, this says what has changed.`;
  const spots = parts.map(p => `<p class="outing-watch-who"><b>${owEsc(p.name)}</b>, ${p.role}${p.was && p.compared ? `, planned ${owEsc(owWhen(p.was.at))}` : ''}</p>`
    + `<ul class="outing-watch-list">${p.lines.map(t => `<li>${owEsc(t)}</li>`).join('')}</ul>`).join('');
  // Which forecast: the one on screen, against the one planned with; an older copy compares nothing.
  const first = compared.length ? compared.map(p => p.was.forecast).sort((a, b) => Date.parse(a) - Date.parse(b))[0] : null;
  const notes = [older ? `This copy shows the forecast issued ${S.issuedWords(w.forecast)}, older than the one you planned against (${S.issuedWords(older.was.forecast)}), so nothing is compared. Open the site online for the latest.`
    : first ? `Checked against the forecast issued ${S.issuedWords(w.forecast)}; you planned against the one issued ${S.issuedWords(first)}.`
    : `Checked against the forecast issued ${S.issuedWords(w.forecast)}.`];
  // No forecast for the day at a spot whose level changes from day to day: said, never guessed.
  const none = parts.filter(p => p.now.level === R.NO_FORECAST).map(p => p.name);
  if (none.length) notes.push(`This update has no forecast for ${owDay(w.day)} at ${none.join(' or ')}: look again before you go.`);
  const river = parts.some(p => p.now.river), d = owDay(w.day);
  if (river) notes.push('The river is a separate hazard, not part of the pollution level.');
  notes.push(`Before you leave${d === 'today' ? '' : ` ${/^[A-Z]/.test(d) ? 'on ' : ''}${d}`}, look again at the official advice, ${d}'s level${river ? ' and the river' : ''}: `
    + `${river ? 'each' : 'both'} can change, and a newer forecast may be issued. Then check the signs at the water.`);
  return `<div class="outing-watch">${head}${passed}${lead ? `<p>${owEsc(lead)}</p>` : ''}${spots}<p class="small muted">${owEsc(notes.join(' '))}</p></div>`;
}

// ------------------------------------------------------------------------------ in the page
// Under the outing's two columns (drawOuting, after the tile is drawn): note the outing in this browser,
// and say what has changed since. pair: outingPair's; forecast: the forecast's issue time (DATA.generated_at).
// The note as it was when the page opened is kept for the visit (OUTING_WATCH_OPENED, as since.js keeps
// LOOKED): the page draws the tile more than once, and an earlier outing's day that has passed is said each time.
let OUTING_WATCH_OPENED;
function outingWatchDraw(tile, plan, pair, forecast, nowMs = Date.now()) {
  let text = null, kept = true;
  try { text = localStorage.getItem(OUTING_WATCH_KEY); } catch (e) { kept = false; }
  const old = outingWatchRead(text), note = outingWatchNote(old, plan, pair, forecast, nowMs);
  if (OUTING_WATCH_OPENED === undefined) OUTING_WATCH_OPENED = old;
  try { if (note) localStorage.setItem(OUTING_WATCH_KEY, JSON.stringify(note)); else localStorage.removeItem(OUTING_WATCH_KEY); }
  catch (e) { kept = false; }
  const box = tile && tile.querySelector('.outing-pair');
  if (!note || !box) return;
  const was = old && old.day === plan.day ? old.items : [], t = owRules().today();
  const spots = [[pair.main, 'your spot'], [pair.backup, 'your backup']].filter(([s]) => s)
    .map(([s, role]) => ({ name: s.name, role, was: was.find(r => r.id === s.id) || null, now: outingWatchRecord(s, plan.day, forecast, nowMs) }));
  box.insertAdjacentHTML('afterend', outingWatchSection({ day: plan.day, today: t, spots, kept, forecast,
    passed: OUTING_WATCH_OPENED && OUTING_WATCH_OPENED.day !== plan.day && OUTING_WATCH_OPENED.day < t ? OUTING_WATCH_OPENED.day : null }));
}

if (typeof module === 'object' && module.exports) {
  module.exports = { OUTING_WATCH_KEY, outingWatchRecord, outingWatchOK, outingWatchRead, outingWatchNote, outingWatchLines, outingWatchSection, outingWatchDraw, owRiver, owLevel };
}
