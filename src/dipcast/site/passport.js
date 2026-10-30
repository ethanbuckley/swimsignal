// The swim passport (Saved, first version, 28 Oct 2026; docs/NOTICES-WINDOWS-ACCESS-DECISIONS-2026-10.md, "Swim
// passport, profiles and badges"): a private record of the swimmer's outings, places and water types, with a few
// badges and points, built from the swim journal (journal.js, dipcast.swims) on this device.
//
// Private by default. Everything is worked out again from the journal each time the page draws, so the same journal
// always gives the same points and badges, however often it is drawn. All it keeps (PASSPORT_KEY) is the day an
// outing was first planned with a backup (Prepared planner), the day the Water-wise questions were first all
// answered right, and a name the swimmer chose, if any. Nothing is sent anywhere. Sharing is the swimmer's choice,
// one badge at a time, and says the badge's name and the site's address only: never a place, a day, a time or the name.
//
// What it never rewards (the doc's rules): speed, distance, cold, rough water, or going despite a poor forecast. A
// swim logged with the forecast at High risk or Very high risk (the journal keeps what the page showed) stays in the record but
// earns no points and counts towards no badge. No streaks: nothing counts days in a row, and a break loses nothing.
// No spot, forecast, guide or notice is ever behind a badge, and the Water-wise questions only repeat what the pages say.
//
// A plain script, as journal.js: globals in the page (names begin pp, passport or PASSPORT), exports in Node
// (tests/site_passport.test.cjs, tests/site_passport_profile.test.cjs). It asks for journal.js's reader when it is
// called, so it loads after it.

const PASSPORT_KEY = 'dipcast.passport';
// Points, adjustable in the pilot (the doc): a logged outing, and the first visit to a spot. Nothing else earns points.
const PASSPORT_XP = { outing: 10, newSpot: 15 };
const PASSPORT_RIVERS = 3;   // River explorer: this many different river spots
const PASSPORT_NAME_MAX = 30;
const PASSPORT_BADGES = [
  { id: 'first-outing', name: 'First outing', how: 'Log your first swim in the journal.' },
  { id: 'river-explorer', name: 'River explorer', how: `Swim at ${PASSPORT_RIVERS} different river spots.` },
  { id: 'lake-to-river', name: 'Lake-to-river', how: 'Swim at a lake and at a river.' },
  { id: 'prepared-planner', name: 'Prepared planner', how: 'Plan an outing with a backup spot on Plan a swim.' },
  { id: 'water-wise', name: 'Water-wise', how: 'Answer the four questions on reading the forecast, below.' },
];
const PP_POOR = new Set(['high', 'very high']);   // the forecast's levels at which a swim earns nothing
const PP_ISO = /^\d{4}-\d{2}-\d{2}$/;
const ppEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
// In Node (the tests), journal.js's reader of this browser's swims is made from its exports, as the page's journalNow reads them.
const ppJournal = () => {
  if (typeof journalEntries === 'function') return { journalEntries, journalNow: typeof journalNow === 'function' ? journalNow : () => [] };
  const J = require('./journal.js');
  return { ...J, journalNow: () => { try { return J.journalEntries(localStorage.getItem(J.JOURNAL_KEY)); } catch (e) { return []; } } };
};
const ppDay = iso => new Date(iso + 'T12:00:00Z').toLocaleDateString('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' });

// The passport from the journal's swims (journal.js entries) and kindOf(spot id): 'river', 'lake' or null (a spot no
// longer listed). Oldest first, so a badge's day is the swim that earned it. kept: what passportRead gives ({ planned,
// learned }), or the planned day alone as a string, as the first version took it. A swim seen twice (the same journal
// key, as an import of the same copy would bring) counts once.
function passportFrom(entries, kindOf, kept = {}) {
  const k = typeof kept === 'string' ? { planned: kept } : kept || {}, seen = new Set();
  const swims = entries.filter(e => { const key = e.key || `${e.id}@${e.date}`; if (seen.has(key)) return false; seen.add(key); return true; })
    .sort((a, b) => `${a.date} ${a.time || ''} ${a.at || ''}`.localeCompare(`${b.date} ${b.time || ''} ${b.at || ''}`));
  const places = new Set(), counted = new Set(), rivers = new Set(), lakes = new Set(), earned = {};
  let xp = 0, poor = 0;
  for (const e of swims) {
    places.add(e.id);
    const level = e.seen ? e.seen.level : e.level;
    if (PP_POOR.has(level)) { poor += 1; continue; }   // in the record, but no points and no badge
    xp += PASSPORT_XP.outing;
    if (!counted.has(e.id)) { counted.add(e.id); xp += PASSPORT_XP.newSpot; }
    const kind = kindOf(e.id);
    if (kind === 'river') rivers.add(e.id);
    if (kind === 'lake') lakes.add(e.id);
    if (!earned['first-outing']) earned['first-outing'] = e.date;
    if (!earned['river-explorer'] && rivers.size >= PASSPORT_RIVERS) earned['river-explorer'] = e.date;
    if (!earned['lake-to-river'] && rivers.size && lakes.size) earned['lake-to-river'] = e.date;
  }
  if (k.planned) earned['prepared-planner'] = k.planned;
  if (k.learned) earned['water-wise'] = k.learned;
  const kinds = swims.reduce((n, e) => { const t = kindOf(e.id); if (t) n[t].add(e.id); return n; }, { river: new Set(), lake: new Set() });
  return { outings: swims.length, places: places.size, rivers: kinds.river.size, lakes: kinds.lake.size, xp, poor, earned,
    first: swims.length ? swims[0].date : '', last: swims.length ? swims[swims.length - 1].date : '' };
}

// ------------------------------------------------------------------------------ what is kept
// A name as kept: no control characters, spaces run together, at most PASSPORT_NAME_MAX characters; '' for none.
const passportName = t => String(t ?? '').replace(/[\u0000-\u001f\u007f]/g, '').replace(/\s+/g, ' ').trim().slice(0, PASSPORT_NAME_MAX).trim();
// What is kept: { planned, learned, name }, each only where it is what this file writes. Anything else reads as nothing.
function passportRead(text) {
  let v; try { v = JSON.parse(text || 'null'); } catch (e) { return {}; }
  if (!v || typeof v !== 'object' || Array.isArray(v)) return {};
  const out = {};
  for (const k of ['planned', 'learned']) if (typeof v[k] === 'string' && PP_ISO.test(v[k])) out[k] = v[k];
  if (typeof v.name === 'string' && passportName(v.name)) out.name = passportName(v.name);
  return out;
}
// What to keep after a change: the kept fields with the patch over them (a name of '' is no name).
function passportMerge(was, patch) {
  const next = { ...passportRead(JSON.stringify(was || {})), ...patch };
  if ('name' in patch) { const n = passportName(patch.name); if (n) next.name = n; else delete next.name; }
  return passportRead(JSON.stringify(next));
}
const passportNow = () => { try { return passportRead(localStorage.getItem(PASSPORT_KEY)); } catch (e) { return {}; } };
const ppKeep = patch => { try { localStorage.setItem(PASSPORT_KEY, JSON.stringify(passportMerge(passportNow(), patch))); return true; } catch (e) { return false; } };
// Plan a swim calls this when an outing has both a spot and a backup (outing.js, drawOuting): the first day is kept.
function passportPlanned(today) {
  if (passportNow().planned) return false;
  return ppKeep({ planned: today });
}
// The day the Water-wise questions were first all answered right: the first day is kept, and answering again changes nothing.
function passportLearned(today) {
  if (passportNow().learned) return false;
  return ppKeep({ learned: today });
}

// ------------------------------------------------------------------------------ Water-wise
// Four questions on reading the forecast and notices (the doc: "a short lesson on reading forecasts and notices"),
// each answered in the pages' own words: a lower level is not safe water (outing.js and the spot pages), official
// advice comes first (eatoday.js), one level a day (outing.js), and what the forecast cannot see (levels.js,
// FOUND_NONE; the interview script's limits). `right` is the index of the right answer. No points: a badge only.
const PASSPORT_LESSON = [
  { q: 'Tomorrow shows Low risk at your spot. What does that tell you?',
    a: ['The water is fine to swim in tomorrow.', 'Spills from monitored overflows upstream look unlikely to reach it. It is not a water test.'], right: 1,
    why: 'A lower forecast level does not mean safe water. The forecast is of sewage spills, made from the water companies\' overflow data and the rain forecast. Check the signs at the water before you go in.' },
  { q: 'A spot shows Low risk and an official notice advising against swimming. Which do you follow?',
    a: ['The official advice, whatever the level says.', 'The level, if it is newer than the notice.'], right: 0,
    why: 'The level is the forecast\'s alone. Official advice comes from the authority that issued it: follow it first.' },
  { q: 'You plan to swim at 7 in the evening. Is there a level for that hour?',
    a: ['Yes: the level changes hour by hour.', 'No: there is one level for the whole day.'], right: 1,
    why: 'The forecast gives one level for the whole of a day; it does not change between morning and evening. A newer forecast may be issued, so look again before you leave.' },
  { q: 'A spot says "No monitored overflow found upstream". What does that mean?',
    a: ['No monitored overflow traces to it. Other pollution, such as farm runoff or misconnected drains, is not in the forecast.', 'Nothing can pollute this water.'], right: 0,
    why: 'The forecast sees only monitored storm overflows. Other sources are not in it, so check the signs at the water.' },
];
// Answers given (an index for each question, or null): which are right, and whether all are.
function passportLessonCheck(answers) {
  const wrong = PASSPORT_LESSON.map((x, i) => (answers || [])[i] === x.right ? null : i).filter(i => i !== null);
  return { right: PASSPORT_LESSON.length - wrong.length, wrong, done: !wrong.length };
}

// A badge to share: its name and the site's address, nothing about where or when, and never the passport's name.
const passportShareText = b => `I earned "${b.name}" on my SwimSignal swim passport.`;

// ------------------------------------------------------------------------------ the tile
// The name, on this device only: a fold, so it takes no room until wanted.
function ppNameForm(name) {
  return '<details class="fold"><summary>Name on your passport</summary><form class="rv-form" id="pp-name-form">'
    + `<label class="rv-q" for="pp-name">Name <span class="rv-opt">Optional. Kept on this device only; never shared, not even with a badge.</span></label>`
    + `<input type="text" id="pp-name" maxlength="${PASSPORT_NAME_MAX}" autocomplete="nickname" value="${ppEsc(name || '')}">`
    + `<p class="outing-acts"><button type="submit" class="btn">Save name</button>${name ? ' <button type="button" class="linkbtn small" id="pp-name-clear">Remove name</button>' : ''}</p></form></details>`;
}
// The questions: to answer, until all are right once; then, kept to read again, with why each answer is right.
// ask, done: the fold's summary before and after (the tile's own words, or the learning card's).
function ppLesson(learned, ask = 'Water-wise: reading the forecast (4 questions)', done = 'Water-wise: reading the forecast') {
  if (learned) return `<details class="fold" id="pp-lesson"><summary>${done}</summary><p class="small">You answered all four on ${ppEsc(ppDay(learned))}.</p>`
    + `<ol class="small">${PASSPORT_LESSON.map(x => `<li><b>${ppEsc(x.q)}</b> ${ppEsc(x.a[x.right])} ${ppEsc(x.why)}</li>`).join('')}</ol></details>`;
  return `<details class="fold" id="pp-lesson"><summary>${ask}</summary><form class="rv-form" id="pp-lesson-form">`
    + PASSPORT_LESSON.map((x, i) => `<fieldset><legend class="rv-q">${i + 1}. ${ppEsc(x.q)}</legend><div class="rv-choice">`
      + x.a.map((t, j) => `<label><input type="radio" name="pp-q${i}" value="${j}"><span>${ppEsc(t)}</span></label>`).join('')
      + `</div><p class="small muted" data-pp-why="${i}" hidden></p></fieldset>`).join('')
    + '<p class="outing-acts"><button type="submit" class="btn">Check my answers</button></p></form></details>';
}
// Before a swim is logged (30 Oct 2026): the questions on their own, where the passport will be, so a new visitor can
// learn to read the forecast first. No history, no points and no badges here; the same `learned` day is kept, and the
// passport shows Water-wise from it once the first swim is logged, when this card gives way to the passport tile.
function passportLessonCard(kept = {}) {
  const invite = kept.learned
    ? 'Water-wise will be on your swim passport from your first swim logged in the journal. The passport is private, on this device.'
    : 'Log a swim in your journal and your swim passport starts here: private, on this device. Get all four right first and Water-wise is on it from the start.';
  return '<section class="sec tile pp pp-learn" id="passport" aria-labelledby="pp-h"><h2 class="sec-h" id="pp-h">Water-wise: reading the forecast</h2>'
    + '<p class="sub">Four questions, each answered in the site\'s own words. No points, and nothing sent: this browser keeps only the day you get all four right.</p>'
    + ppLesson(kept.learned, 'Answer the four questions', 'The four answers, to read again')
    + `<p class="small muted">${invite}</p>`
    + '<p class="small muted msg" id="pp-msg" aria-live="polite"></p></section>';
}

// The tile on Saved, under the journal: '' until a swim is logged. kept: passportRead's (the name and the learned day).
function passportCard(p, kept = {}) {
  if (!p || !p.outings) return '';
  const parts = [`${p.outings} ${p.outings === 1 ? 'outing' : 'outings'}`, `${p.places} ${p.places === 1 ? 'place' : 'places'}`];
  const kinds = [p.rivers ? `${p.rivers} ${p.rivers === 1 ? 'river' : 'rivers'}` : '', p.lakes ? `${p.lakes} ${p.lakes === 1 ? 'lake' : 'lakes'}` : ''].filter(Boolean);
  const badges = PASSPORT_BADGES.map(b => { const on = p.earned[b.id];
    return `<li class="pp-badge${on ? ' on' : ''}"><b>${ppEsc(b.name)}</b> `
      + (on ? `<span class="k">earned ${ppEsc(ppDay(on))}</span> <button type="button" class="linkbtn small" data-pp-share="${ppEsc(b.id)}">Share</button>`
        : `<span class="k">not yet: ${ppEsc(b.how)}</span>`) + '</li>'; }).join('');
  const head = kept.name ? `Swim passport · ${ppEsc(kept.name)}` : 'Your swim passport';
  return `<section class="sec tile pp" id="passport" aria-labelledby="pp-h"><h2 class="sec-h" id="pp-h">${head}</h2>`
    + '<p class="sub">Built from your swim journal, on this device only: nothing is sent anywhere. No spot, forecast or guide is behind a badge.</p>'
    + `<p class="pp-sum"><b>${parts.join(' · ')}</b>${kinds.length ? ` (${kinds.join(', ')})` : ''} · ${p.xp} points</p>`
    + `<ul class="pp-badges">${badges}</ul>`
    + ppLesson(kept.learned) + ppNameForm(kept.name)
    + `<p class="small muted">${p.poor ? `${p.poor} ${p.poor === 1 ? 'swim was' : 'swims were'} logged when the forecast was at high risk or very high risk: kept in your record, with no points or badges. ` : ''}`
    + 'The passport never rewards going despite a poor forecast, nor speed, distance, cold or rough water, and it keeps no streaks: a break loses nothing.</p>'
    + '<p class="small muted msg" id="pp-msg" aria-live="polite"></p></section>';
}

// ------------------------------------------------------------------------------ in the page
// The card from the journal and the listed spots (the page's DATA.spots), and what its buttons and forms do.
let PP_SPOTS = [];
function passportSection(spots) {
  PP_SPOTS = spots || [];
  const kind = new Map(PP_SPOTS.map(s => [s.id, s.kind === 'lake' ? 'lake' : s.kind === 'river' ? 'river' : null]));
  const kept = passportNow(), p = passportFrom(ppJournal().journalNow(), id => kind.get(id) || null, kept);
  return p.outings ? passportCard(p, kept) : passportLessonCard(kept);
}
// Drawn again in place after a change, with a line said in it.
function ppRedraw(said) {
  const el = document.getElementById('passport'); if (!el) return;
  el.outerHTML = passportSection(PP_SPOTS);
  passportBind();
  const msg = document.getElementById('pp-msg'); if (msg && said) msg.textContent = said;
}
const ppToday = () => typeof today === 'function' ? today() : new Date().toISOString().slice(0, 10);
function passportBind() {
  document.querySelectorAll('[data-pp-share]').forEach(btn => btn.addEventListener('click', async () => {
    const b = PASSPORT_BADGES.find(x => x.id === btn.dataset.ppShare), msg = document.getElementById('pp-msg');
    if (!b) return;
    const text = passportShareText(b), url = new URL('./', document.baseURI).href;
    try {
      if (navigator.share) await navigator.share({ title: 'SwimSignal', text, url });
      else { await navigator.clipboard.writeText(`${text} ${url}`); if (msg) msg.textContent = 'Copied: paste it wherever you like.'; }
    } catch (e) { if (e && e.name !== 'AbortError' && msg) msg.textContent = 'Could not share it from this browser.'; }
  }));
  const nameForm = document.getElementById('pp-name-form');
  if (nameForm) nameForm.addEventListener('submit', e => { e.preventDefault();
    const n = passportName(document.getElementById('pp-name').value);
    ppRedraw(!ppKeep({ name: n }) ? 'This browser could not keep the name.' : n ? 'Name saved on this device.' : 'Name removed.'); });
  const clear = document.getElementById('pp-name-clear');
  if (clear) clear.addEventListener('click', () => ppRedraw(ppKeep({ name: '' }) ? 'Name removed.' : 'This browser could not change the name.'));
  const lesson = document.getElementById('pp-lesson-form');
  if (lesson) lesson.addEventListener('submit', e => { e.preventDefault();
    const answers = PASSPORT_LESSON.map((x, i) => { const r = lesson.querySelector(`input[name="pp-q${i}"]:checked`); return r ? Number(r.value) : null; });
    const c = passportLessonCheck(answers);
    lesson.querySelectorAll('[data-pp-why]').forEach(p => { const i = Number(p.dataset.ppWhy), bad = c.wrong.includes(i);
      p.hidden = !bad; p.textContent = bad ? (answers[i] === null ? 'Not answered yet.' : `Not quite. ${PASSPORT_LESSON[i].why}`) : ''; });
    if (!c.done) { const msg = document.getElementById('pp-msg'); if (msg) msg.textContent = `${c.right} of ${PASSPORT_LESSON.length} right. Try the others again.`; return; }
    passportLearned(ppToday());
    const kept = passportNow().learned, before = !!document.querySelector('#passport.pp-learn');
    ppRedraw(!kept ? 'All four right, but this browser could not keep it.' : before ? 'All four right. Water-wise will be on your passport from your first logged swim.' : 'All four right: Water-wise is on your passport.');
  });
}

if (typeof module === 'object' && module.exports) {
  module.exports = { PASSPORT_KEY, PASSPORT_XP, PASSPORT_RIVERS, PASSPORT_NAME_MAX, PASSPORT_BADGES, PASSPORT_LESSON, passportFrom, passportRead, passportMerge,
    passportName, passportLessonCheck, passportCard, passportLessonCard, passportSection, passportShareText, passportPlanned, passportLearned, passportNow };
}
