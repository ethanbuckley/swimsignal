// Your outing, on a plan (the plan/ page): when on the plan's day you mean to swim, the spot, and a backup
// spot, the two side by side for that day with what each level rests on. Drawn from what the page already
// has (spots.json): it asks for nothing more. Kept as the plan is, in the plan's address and its copy in
// this browser (plan.js, readPlan and planHash: when=, spot=, backup=; index.html, PLAN_KEY), so a reload,
// Back and a copied link keep it, and nothing reaches a server. The page calls drawOuting from drawPlan;
// the words and the markup are here, where Node can test them.
//
// The forecast gives one level a day. A time on the day is the swimmer's own plan, not a finer forecast:
// the tile says so, and it says when the time has already passed today.
//
// A plain script, as plan.js: globals in the page, exports in Node.
const outingRules = () => typeof dayLevel === 'function' ? { dayWord, today } : require('./levels.js');
// eatoday.js's compact official-advice line (eaTodayTag, #379), the one every list, card and row uses.
const outingTag = () => typeof eaTodayTag === 'function' ? eaTodayTag : require('./eatoday.js').eaTodayTag;
const outDay = iso => outingRules().dayWord(iso).replace(/^on /, '');   // "today", "tomorrow", "Monday" (levels.js, dayName)
const outEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

// ------------------------------------------------------------------------------ when
// The parts of a day as hours on the device's clock [from, to), and the hours offered one by one.
const OUTING_PARTS = { morning: [6, 12], afternoon: [12, 17], evening: [17, 21] };
const OUTING_HOURS = Array.from({ length: 17 }, (_, i) => String(i + 5).padStart(2, '0'));   // 05:00 to 21:00
const outingSpan = when => OUTING_PARTS[when] || (/^\d\d$/.test(when || '') ? [Number(when), Number(when) + 1] : null);
// "Saturday morning", "this evening", "tomorrow at 07:00"; the day alone with no time.
function outingWhen(day, when) {
  const d = outDay(day);
  if (!when) return d;
  if (OUTING_PARTS[when]) return d === 'today' ? `this ${when}` : `${d} ${when}`;
  return `${d} at ${when}:00`;
}
// What the time does and does not mean, as sentences: the level is for the whole day; and on today, a
// time already past. nowMs: the device's clock.
function outingTimeNote(day, when, nowMs = Date.now()) {
  // The daily caveat always, with or without a time picked, so a time never reads as an hourly forecast.
  const R = outingRules(), span = outingSpan(when);
  const out = [`The forecast gives one level for the whole of ${outDay(day)}; it does not change between morning and evening.`];
  if (span && day === R.today() && new Date(nowMs).getHours() >= span[1]) out.push('That time has already passed today.');
  return out;
}

// The plan after its day has changed (the day strip, a better day, the next visit): a time was for the day it
// was picked on, so it goes; the spot and the backup stay. lastDay: the day the outing was last shown for
// (null on the page's first draw, which changes nothing).
function outingForDay(plan, lastDay) {
  if (!plan.when || lastDay === null || lastDay === plan.day) return plan;
  const { when, ...rest } = plan;
  return rest;
}

// ------------------------------------------------------------------------------ which spots
// The spots offered for the outing and its backup, as [[heading, spots]]: your saved spots first, then the
// plan's own (shown, in the page's order) that are not saved, each once. except: an id left out (the
// outing's spot, from the backup's choices). Saved spots no longer listed are skipped.
function outingOptions(shown, savedIds, byId, except = null) {
  const saved = [...(savedIds || [])].map(id => byId.get(id)).filter(s => s && s.id !== except);
  const ids = new Set(saved.map(s => s.id)), plan = shown.filter(s => s.id !== except && !ids.has(s.id));
  return [['Your saved spots', saved], ['In this plan', plan]].filter(([, g]) => g.length);
}
// The plan's spot and backup as spots, and the ids asked for that are no longer listed (a link from an
// older forecast, or a spot taken off the site), so the tile can say so rather than drop them silently.
function outingPair(plan, byId) {
  const missing = [plan.spot, plan.backup].filter(id => id && !byId.has(id));
  return { main: byId.get(plan.spot) || null, backup: plan.backup !== plan.spot ? byId.get(plan.backup) || null : null, missing };
}

// Official advice at the spot (spots.json and spots-lite.json `official`, #379), in eatoday.js's compact
// form, a line of its own under the column's level, never in it: the level is the forecast's alone. The same
// helper as the list, Saved and the plan's rows, so the outing says what they say. '' without advice.
const outingOfficial = s => outingTag()(s, 'p');

// ------------------------------------------------------------------------------ the tile
// A column for a spot: c = { id, name, href, tone, headline, why, ev, meta }, headline/why/ev already
// HTML (the page's own words, escaped where they were made), the rest text.
const outingCol = (c, role) => `<div class="outing-col"><p class="outing-role">${role}</p>`
  + `<h3 class="outing-nm"><a href="${outEsc(c.href)}" data-id="${outEsc(c.id)}">${outEsc(c.name)}</a></h3>`
  + (c.meta ? `<p class="k">${outEsc(c.meta)}</p>` : '')
  + `<p class="hl ${outEsc(c.tone)}">${c.headline}</p>` + (c.official || '') + (c.why ? `<p class="why">${c.why}</p>` : '') + (c.ev || '') + '</div>';
// The whole tile. o = { day, when, spot, backup, groups (outingOptions for the spot), backupGroups,
// main, alt (columns, or null), missing (ids), issued (text: "15:29, 2 h ago"), open, nowMs }.
function outingSection(o) {
  const opt = (groups, sel) => groups.map(([h, g]) => `<optgroup label="${outEsc(h)}">`
    + g.map(s => `<option value="${outEsc(s.id)}"${s.id === sel ? ' selected' : ''}>${outEsc(s.name)}</option>`).join('') + '</optgroup>').join('');
  const times = `<option value="">Any time</option>` + Object.keys(OUTING_PARTS).map(p => `<option value="${p}"${o.when === p ? ' selected' : ''}>${p.charAt(0).toUpperCase() + p.slice(1)}</option>`).join('')
    + `<optgroup label="An hour">${OUTING_HOURS.map(h => `<option value="${h}"${o.when === h ? ' selected' : ''}>${h}:00</option>`).join('')}</optgroup>`;
  // The names are in the columns' heads: the line says only when, and what is side by side.
  const said = o.main ? `${outingWhen(o.day, o.when).replace(/^./, c => c.toUpperCase())}: ${o.alt ? 'your spot and a backup, side by side' : 'your spot'}.` : '';
  const notes = outingTimeNote(o.day, o.when, o.nowMs);
  const gone = o.missing && o.missing.length ? `<p class="small muted">${o.missing.length === 1 ? 'A spot in this outing is' : 'Spots in this outing are'} no longer listed, so ${o.missing.length === 1 ? 'it is' : 'they are'} left out.</p>` : '';
  const body = !o.main ? '<p class="sub">Choose a spot to see it here, with a backup beside it.</p>'
    : `<p class="outing-said">${said}</p><div class="outing-pair${o.alt ? '' : ' one'}">${outingCol(o.main, 'Your spot')}${o.alt ? outingCol(o.alt, 'Backup') : ''}</div>`
      + `<p class="small muted">${[...notes, `Issued ${outEsc(o.issued)}.`, 'A lower forecast level does not mean safe water: check the signs at the water before you swim.'].join(' ')}</p>`;
  return `<details class="sec tile outing" id="outing"${o.open ? ' open' : ''}><summary><span>Your outing${o.main ? `<span class="k">${outEsc(o.main.name)}${o.alt ? `, backup ${outEsc(o.alt.name)}` : ''}</span>` : ''}</span></summary>`
    + `<p class="sub">When you mean to go, where, and somewhere else to go instead. Kept in this browser and in this plan's link; sent nowhere.</p>`
    + `<div class="outing-fields"><label>When<select data-outing="when">${times}</select></label>`
    + `<label>Spot<select data-outing="spot"><option value="">Choose a spot</option>${opt(o.groups, o.spot)}</select></label>`
    + `<label>Backup (optional)<select data-outing="backup"><option value="">No backup</option>${opt(o.backupGroups, o.backup)}</select></label></div>`
    + gone + body + '</details>';
}

// ------------------------------------------------------------------------------ in the page
// Draws the tile at the top of the plan's results (index.html, drawPlan), from the page's own spots and
// sentences (planWhy, planEvidence, dayHeadline), and keeps a change in the plan (planAddress). shown: the
// plan's rows, as {s, miles, level}. Its open state stays as it was across redraws.
let OUTING_OPEN = null, OUTING_DAY = null;
function drawOuting(box, shown) {
  const old = document.getElementById('outing'); if (old) old.remove();
  const kept = outingForDay(PLAN, OUTING_DAY); OUTING_DAY = PLAN.day;
  if (kept !== PLAN) { delete PLAN.when; planAddress(); }   // a time picked for another day
  const byId = new Map(DATA.spots.map(s => [s.id, s])), miles = new Map(shown.map(o => [o.s.id, o.miles])), from = planFrom();
  const away = s => miles.has(s.id) ? miles.get(s.id) : from ? km(from, [s.lat, s.lon]) / MILE_KM : null;
  const col = s => { const m = away(s);
    return { id: s.id, name: s.name, href: spotPath(s.id) + (daily(s) ? '#day=' + PLAN.day : ''), tone: tone(dayLevel(s, PLAN.day)),
      headline: dayHeadline(s, PLAN.day), official: outingOfficial(s), why: planWhy(s, PLAN.day), ev: planEvidence(s),
      meta: [m === null ? null : cap(milesAway(m)), cap(s.kind)].filter(Boolean).join(' · ') }; };
  const pair = outingPair(PLAN, byId), list = shown.map(o => o.s);
  if (OUTING_OPEN === null) OUTING_OPEN = !!(PLAN.spot || PLAN.when);
  box.insertAdjacentHTML('afterbegin', outingSection({ day: PLAN.day, when: PLAN.when, spot: PLAN.spot, backup: PLAN.backup,
    groups: outingOptions(list, SAVED, byId), backupGroups: outingOptions(list, SAVED, byId, PLAN.spot),
    main: pair.main && col(pair.main), alt: pair.backup && col(pair.backup), missing: pair.missing,
    issued: `${issued()}, ${ago(ageMin())} ago`, open: OUTING_OPEN, nowMs: Date.now() }));
  const tile = document.getElementById('outing');
  tile.addEventListener('toggle', () => { OUTING_OPEN = tile.open; });
  tile.querySelectorAll('[data-outing]').forEach(el => el.addEventListener('change', () => {
    const k = el.dataset.outing;
    if (el.value) PLAN[k] = el.value; else delete PLAN[k];
    if (PLAN.backup && PLAN.backup === PLAN.spot) delete PLAN.backup;
    planAddress(); drawOuting(box, shown);
    const again = document.querySelector(`[data-outing="${k}"]`); if (again) again.focus();
  }));
  tile.querySelectorAll('a[data-id]').forEach(a => a.addEventListener('click', e => { if (!plainClick(e)) return; e.preventDefault(); select(a.dataset.id, true, true, PLAN.day); }));
}

if (typeof module === 'object' && module.exports) {
  module.exports = { OUTING_PARTS, OUTING_HOURS, outingOfficial, outingSpan, outingWhen, outingTimeNote, outingForDay, outingOptions, outingPair, outingSection };
}
