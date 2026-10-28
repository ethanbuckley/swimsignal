// The swim passport (Saved, first version, 28 Oct 2026; docs/NOTICES-WINDOWS-ACCESS-DECISIONS-2026-10.md, "Swim
// passport, profiles and badges"): a private record of the swimmer's outings, places and water types, with a few
// badges and points, built from the swim journal (journal.js, dipcast.swims) on this device.
//
// Private by default. Everything is worked out again from the journal each time the page draws; the only thing it
// keeps is the day an outing was first planned with a backup (PASSPORT_KEY), for the Prepared planner badge. Nothing
// is sent anywhere. Sharing is the swimmer's choice, one badge at a time, and says the badge's name and the site's
// address only: never a place, a day or a time.
//
// What it never rewards (the doc's rules): speed, distance, cold, rough water, or going despite a poor forecast. A
// swim logged with the forecast at High risk or Very high risk (the journal keeps what the page showed) stays in the record but
// earns no points and counts towards no badge. No streaks: nothing counts days in a row, and a break loses nothing.
// No spot, forecast, guide or notice is ever behind a badge.
//
// A plain script, as journal.js: globals in the page (names begin pp, passport or PASSPORT), exports in Node
// (tests/site_passport.test.cjs). It asks for journal.js's reader when it is called, so it loads after it.

const PASSPORT_KEY = 'dipcast.passport';
// Points, adjustable in the pilot (the doc): a logged outing, and the first visit to a spot.
const PASSPORT_XP = { outing: 10, newSpot: 15 };
const PASSPORT_RIVERS = 3;   // River explorer: this many different river spots
const PASSPORT_BADGES = [
  { id: 'first-outing', name: 'First outing', how: 'Log your first swim in the journal.' },
  { id: 'river-explorer', name: 'River explorer', how: `Swim at ${PASSPORT_RIVERS} different river spots.` },
  { id: 'lake-to-river', name: 'Lake-to-river', how: 'Swim at a lake and at a river.' },
  { id: 'prepared-planner', name: 'Prepared planner', how: 'Plan an outing with a backup spot on Plan a swim.' },
];
const PP_POOR = new Set(['high', 'very high']);   // the forecast's levels at which a swim earns nothing
const ppEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const ppJournal = () => typeof journalEntries === 'function' ? { journalEntries, journalNow: typeof journalNow === 'function' ? journalNow : () => [] }
  : require('./journal.js');
const ppDay = iso => new Date(iso + 'T12:00:00Z').toLocaleDateString('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' });

// The passport from the journal's swims (journal.js entries) and kindOf(spot id): 'river', 'lake' or null (a spot no
// longer listed). Oldest first, so a badge's day is the swim that earned it. `planned`: the day of the first outing
// planned with a backup, or ''.
function passportFrom(entries, kindOf, planned = '') {
  const swims = entries.slice().sort((a, b) => `${a.date} ${a.time || ''} ${a.at || ''}`.localeCompare(`${b.date} ${b.time || ''} ${b.at || ''}`));
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
  if (planned) earned['prepared-planner'] = planned;
  const kinds = swims.reduce((k, e) => { const t = kindOf(e.id); if (t) k[t].add(e.id); return k; }, { river: new Set(), lake: new Set() });
  return { outings: swims.length, places: places.size, rivers: kinds.river.size, lakes: kinds.lake.size, xp, poor, earned,
    first: swims.length ? swims[0].date : '', last: swims.length ? swims[swims.length - 1].date : '' };
}

// What is kept: { planned: 'YYYY-MM-DD' } or nothing. Anything else reads as nothing.
function passportRead(text) {
  try { const v = JSON.parse(text || 'null'); return v && typeof v === 'object' && typeof v.planned === 'string'
    && /^\d{4}-\d{2}-\d{2}$/.test(v.planned) ? { planned: v.planned } : {}; } catch (e) { return {}; }
}
const passportNow = () => { try { return passportRead(localStorage.getItem(PASSPORT_KEY)); } catch (e) { return {}; } };
// Plan a swim calls this when an outing has both a spot and a backup (outing.js, drawOuting): the first day is kept.
function passportPlanned(today) {
  if (passportNow().planned) return false;
  try { localStorage.setItem(PASSPORT_KEY, JSON.stringify({ planned: today })); return true; } catch (e) { return false; }
}

// A badge to share: its name and the site's address, nothing about where or when.
const passportShareText = b => `I earned "${b.name}" on my SwimSignal swim passport.`;

// The tile on Saved, under the journal: '' until a swim is logged.
function passportCard(p) {
  if (!p || !p.outings) return '';
  const parts = [`${p.outings} ${p.outings === 1 ? 'outing' : 'outings'}`, `${p.places} ${p.places === 1 ? 'place' : 'places'}`];
  const kinds = [p.rivers ? `${p.rivers} ${p.rivers === 1 ? 'river' : 'rivers'}` : '', p.lakes ? `${p.lakes} ${p.lakes === 1 ? 'lake' : 'lakes'}` : ''].filter(Boolean);
  const badges = PASSPORT_BADGES.map(b => { const on = p.earned[b.id];
    return `<li class="pp-badge${on ? ' on' : ''}"><b>${ppEsc(b.name)}</b> `
      + (on ? `<span class="k">earned ${ppEsc(ppDay(on))}</span> <button type="button" class="linkbtn small" data-pp-share="${ppEsc(b.id)}">Share</button>`
        : `<span class="k">not yet: ${ppEsc(b.how)}</span>`) + '</li>'; }).join('');
  return '<section class="sec tile pp" id="passport" aria-labelledby="pp-h"><h2 class="sec-h" id="pp-h">Your swim passport</h2>'
    + '<p class="sub">Built from your swim journal, on this device only: nothing is sent anywhere. No spot, forecast or guide is behind a badge.</p>'
    + `<p class="pp-sum"><b>${parts.join(' · ')}</b>${kinds.length ? ` (${kinds.join(', ')})` : ''} · ${p.xp} points</p>`
    + `<ul class="pp-badges">${badges}</ul>`
    + `<p class="small muted">${p.poor ? `${p.poor} ${p.poor === 1 ? 'swim was' : 'swims were'} logged when the forecast was at high risk or very high risk: kept in your record, with no points or badges. ` : ''}`
    + 'The passport never rewards going despite a poor forecast, nor speed, distance, cold or rough water, and it keeps no streaks: a break loses nothing.</p>'
    + '<p class="small muted msg" id="pp-msg" aria-live="polite"></p></section>';
}

// In the page: the card from the journal and the listed spots, and its share buttons.
function passportSection(spots) {
  const kind = new Map((spots || []).map(s => [s.id, s.kind === 'lake' ? 'lake' : s.kind === 'river' ? 'river' : null]));
  return passportCard(passportFrom(ppJournal().journalNow(), id => kind.get(id) || null, passportNow().planned || ''));
}
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
}

if (typeof module === 'object' && module.exports) {
  module.exports = { PASSPORT_KEY, PASSPORT_XP, PASSPORT_RIVERS, PASSPORT_BADGES, passportFrom, passportRead, passportCard, passportShareText };
}
