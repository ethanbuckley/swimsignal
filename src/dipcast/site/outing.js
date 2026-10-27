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
// spotdate.js: the calendar file and the alerts for a date, as the organisers' page makes and sends them.
const outingDates = () => typeof SpotDate === 'object' ? SpotDate : require('./spotdate.js');
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

// ------------------------------------------------------------------------------ alerts for the outing
// "Alert me about this outing": the outing's spot and its backup, each on the plan's day, asked for through
// the push Worker's alerts for a date (push/README.md, "Alerts for a date"), exactly as the organisers' page
// asks (spotdate.js: the same list in this browser, the same request, the same cap of 10 pairs shared with
// the organisers' page). The plan's day is always one of the forecast's five, so the Worker tells of each
// change in that day's level from then on; it forgets each pair after its date. Only where the build says
// the Worker takes dates (push.dates), and only in a browser with alerts on already: turning them on, and
// its consent, stays the Saved page's.
//
// The pairs this tile asked for are noted in this browser too (OUTING_ASKED_KEY), so that after the spot,
// the backup or the day changes, the tile can say that the earlier pairs are still on and stop them.
const OUTING_ASKED_KEY = 'dipcast.outingdates';
const outLong = iso => new Date(iso + 'T12:00:00Z').toLocaleDateString('en-GB', { timeZone: 'UTC', weekday: 'long', day: 'numeric', month: 'long' });
const outNames = ps => { const n = [...new Set(ps.map(p => outEsc(p.name || p.spot)))]; return n.length > 1 ? `${n.slice(0, -1).join(', ')} and ${n[n.length - 1]}` : n[0] || ''; };
// The outing's pairs: its spot, then its backup, on its day. byId: names, and only spots still listed.
function outingPairs(plan, byId = null) {
  const ids = [plan.spot, plan.backup !== plan.spot ? plan.backup : null].filter(id => id && (!byId || byId.has(id)));
  return plan.day ? ids.map(id => ({ spot: id, date: plan.day, ...(byId ? { name: byId.get(id).name } : {}) })) : [];
}
// Against the list this browser asked for: the pairs already on, those that fit under the cap (the spot
// before the backup), and those left out by it.
function outingAsk(list, pairs, max = outingDates().MAX_DATES) {
  const D = outingDates(), on = pairs.filter(p => D.hasDate(list, p.spot, p.date)), want = pairs.filter(p => !D.hasDate(list, p.spot, p.date));
  const room = Math.max(0, max - list.length);
  return { on, add: want.slice(0, room), left: want.slice(room) };
}
// The whole list to send: these pairs added, or taken out. Only the two fields go, as the organisers' page sends them.
const outingList = (list, pairs, on) => pairs.reduce((l, p) => outingDates().withDate(l, p.spot, p.date, on), list);
// The pairs this tile asked for earlier that are still on and are not this outing's now.
const outingEarlier = (asked, list, pairs) => asked.filter(a => outingDates().hasDate(list, a.spot, a.date) && !pairs.some(p => p.spot === a.spot && p.date === a.date));

// What the alerts part of the tile says, as HTML. a = { state, pairs, list, earlier, saved (the Saved page's
// address), app (an in-app browser's name) }. state: 'none' (the site's date alerts are off: nothing said),
// 'cannot', 'ios', 'inapp', 'blocked' (no notifications here: the calendar file instead), 'off' (alerts not
// on in this browser), 'on'.
function outingAlert(a) {
  const instead = 'Add it to your calendar instead.';
  switch (a.state) {
    case 'cannot': return `<p class="small">This browser cannot show notifications from websites, so SwimSignal cannot alert you about this outing. ${instead}</p>`;
    case 'ios': return `<p class="small">On iPhone and iPad, notifications work only in the Home Screen app, so SwimSignal cannot alert you about this outing here. ${instead}</p>`;
    case 'inapp': return `<p class="small">Alerts cannot be turned on in the ${outEsc(a.app)} app's browser, so SwimSignal cannot alert you about this outing here. ${instead}</p>`;
    case 'blocked': return `<p class="small">Notifications are blocked for this site in your browser settings, so SwimSignal cannot alert you about this outing. ${instead}</p>`;
    case 'off': return `<p class="small">To be alerted about this outing, first turn on alerts in this browser, on the <a href="${outEsc(a.saved)}" id="outing-to-alerts">Saved page</a>.</p>`;
    case 'on': break;
    default: return '';
  }
  const D = outingDates(), { pairs, list, earlier = [] } = a, k = outingAsk(list, pairs);
  if (!pairs.length) return '';
  const day = pairs[0].date, whose = `${outDay(day)}'s`;   // "today's", "Saturday's"
  let h = '';
  if (k.on.length) h += `<p class="outing-alert-on"><b>Alerts are on for ${k.on.length === pairs.length ? 'this outing' : outNames(k.on)}.</b> A notification each time ${whose} level or official advice changes at ${outNames(k.on)}.</p>`
    + `<p class="small">Stored by SwimSignal's alert service: this browser's push address, with ${outNames(k.on)} on ${outLong(day)}. ${k.on.length > 1 ? 'Each is' : 'It is'} forgotten after that day.</p>`;
  if (k.add.length) {
    if (!k.on.length) h += `<p>A notification each time ${whose} level or official advice changes at ${outNames(k.add)}.</p>`;
    h += '<details class="fold"><summary>What asking sends</summary><p class="small">Asking sends the spot'
      + `${pairs.length > 1 ? 's' : ''} and the day of this outing, with your browser's push address, to SwimSignal's alert service, and nothing else about you: `
      + `not the time, where you start from or the rest of the plan. It keeps them with any dates you asked about on the organisers' page, up to ${D.MAX_DATES} in all, `
      + 'and forgets each one after its date. You can stop them here at any time; turning alerts off on the Saved page deletes them all. '
      + 'A notification opens the organisers\' page for that spot and day. An alert can be late or not come at all, so no alert does not mean the water is clean. '
      + '<a href="privacy.html">Privacy notice</a>.</p></details>';
  }
  if (k.left.length) h += `<p class="small">${k.add.length || k.on.length ? `Alerts can cover ${D.MAX_DATES} dates at most, so ${outNames(k.left)} is left out.`
    : `You have alerts for ${D.MAX_DATES} dates, the most there can be. Stop one of them to add this outing.`}</p>`;
  const buttons = (k.add.length ? `<button type="button" class="btn" data-outing-alert="add">${k.on.length || k.left.length ? `Alert me about ${outNames(k.add)}` : 'Alert me about this outing'}</button>` : '')
    + (k.on.length ? '<button type="button" class="btn" data-outing-alert="stop">Stop alerts for this outing</button>' : '');
  if (buttons) h += `<p class="outing-acts">${buttons}</p>`;
  if (earlier.length) h += `<p class="small">Alerts are still on from an earlier choice for this outing: ${earlier.map(p => `${outNames([p])} on ${outLong(p.date)}`).join('; ')}. `
    + '<button type="button" class="linkbtn small" data-outing-alert="earlier">Stop those</button></p>';
  return h;
}

// ------------------------------------------------------------------------------ the calendar file
// "Add to calendar": one event for the outing, made in this browser and sent nowhere (iCalendar, RFC 5545,
// with spotdate.js's lines, folding and escapes, as the organisers' page's file). The time is the swimmer's
// own, on the device's clock, so it is written as a local ("floating") time; with no time picked, the
// event is the whole day. It carries the spot's name and links back to the spot's page and the plan,
// never a forecast level, which would be out of date by the time the calendar shows it. One UID per day
// and spot, so importing the file again after changing the time updates the event rather than adding one.
// c = { day, when, main: {id, name, url}, backup: {name, url} | null, plan (the plan's address), host }.
const OUTING_CHECK = 'Check SwimSignal and any official advice before you go.';
function outingIcs(c, now = Date.now()) {
  const D = outingDates(), span = outingSpan(c.when), hh = h => String(h).padStart(2, '0') + '0000';
  const next = (() => { const d = new Date(c.day + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + 1); return d.toISOString().slice(0, 10); })();
  const when = span ? [`DTSTART:${D.icsDay(c.day)}T${hh(span[0])}`, `DTEND:${D.icsDay(c.day)}T${hh(span[1])}`]
    : [`DTSTART;VALUE=DATE:${D.icsDay(c.day)}`, `DTEND;VALUE=DATE:${D.icsDay(next)}`];
  const text = [OUTING_CHECK, `Your spot: ${c.main.name}, ${c.main.url}`, ...(c.backup ? [`Backup: ${c.backup.name}, ${c.backup.url}`] : []), `Your plan: ${c.plan}`].join('\n');
  return D.icsCalendar('-//SwimSignal//Outing//EN', [['BEGIN:VEVENT', `UID:outing-${c.day}-${c.main.id}@${c.host}`, `DTSTAMP:${D.icsStamp(now)}`, ...when,
    `SUMMARY:${D.icsEsc(`Swim: ${c.main.name}`)}`, `LOCATION:${D.icsEsc(c.main.name)}`, `DESCRIPTION:${D.icsEsc(text)}`, `URL:${c.main.url}`,
    ...(span ? [] : ['TRANSP:TRANSPARENT']), 'END:VEVENT']]);
}
// The part of the tile that keeps the outing: the alerts (filled in once this browser's push state is
// known: outingAlert), then the calendar file.
const outingKeep = () => '<div class="outing-keep"><div id="outing-alert"></div>'
  + '<p class="outing-acts"><button type="button" class="btn" id="outing-ics">Add to calendar</button></p>'
  + '<p class="small muted">A calendar file made in this browser and sent nowhere: the time, the spots and links back here, without a level, which would go out of date.</p>'
  + '<p class="small muted msg" id="outing-alert-msg" aria-live="polite"></p></div>';

// ------------------------------------------------------------------------------ the tile
// A column for a spot: c = { id, name, href, tone, headline, why, ev, meta }, headline/why/ev already
// HTML (the page's own words, escaped where they were made), the rest text.
const outingCol = (c, role) => `<div class="outing-col"><p class="outing-role">${role}</p>`
  + `<h3 class="outing-nm"><a href="${outEsc(c.href)}" data-id="${outEsc(c.id)}">${outEsc(c.name)}</a></h3>`
  + (c.meta ? `<p class="k">${outEsc(c.meta)}</p>` : '')
  + `<p class="hl ${outEsc(c.tone)}">${c.headline}</p>` + (c.official || '') + (c.why ? `<p class="why">${c.why}</p>` : '') + (c.ev || '') + '</div>';
// The whole tile. o = { day, when, spot, backup, groups (outingOptions for the spot), backupGroups,
// main, alt (columns, or null), missing (ids), issued (text: "15:29, 2 h ago"), open, nowMs, dateAlerts (the
// site's alerts for a date are on, so the outing can be sent if asked) }.
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
      + `<p class="small muted">${[...notes, `Issued ${outEsc(o.issued)}.`, 'A lower forecast level does not mean safe water: check the signs at the water before you swim.'].join(' ')}</p>`
      + outingKeep();
  return `<details class="sec tile outing" id="outing"${o.open ? ' open' : ''}><summary><span>Your outing${o.main ? `<span class="k">${outEsc(o.main.name)}${o.alt ? `, backup ${outEsc(o.alt.name)}` : ''}</span>` : ''}</span></summary>`
    + `<p class="sub">When you mean to go, where, and somewhere else to go instead. Kept in this browser and in this plan's link; sent nowhere${o.dateAlerts ? ' unless you ask for alerts about it' : ''}.</p>`
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
    issued: `${issued()}, ${ago(ageMin())} ago`, open: OUTING_OPEN, nowMs: Date.now(), dateAlerts: outingDates().dateAlertsOn(DATA) }));
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
  if (typeof outingWatchDraw === 'function') outingWatchDraw(tile, PLAN, pair, DATA.generated_at);   // outingwatch.js: what would change this plan, and what has
  if (!pair.main) return;
  if (typeof OutingPack === 'object') OutingPack.draw(pair);   // outingpack.js: keep this outing for offline use
  // The calendar file, made here when asked (organisers.html's way of handing a file over).
  document.getElementById('outing-ics').addEventListener('click', () => {
    const abs = p => new URL(p, location.href).href, link = s => abs(spotPath(s.id) + (daily(s) ? '#day=' + PLAN.day : ''));
    const text = outingIcs({ day: PLAN.day, when: PLAN.when, main: { id: pair.main.id, name: pair.main.name, url: link(pair.main) },
      backup: pair.backup && { name: pair.backup.name, url: link(pair.backup) }, plan: abs(planPath() + planHash(PLAN)), host: location.hostname });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type: 'text/calendar;charset=utf-8' }));
    a.download = `swimsignal-outing-${PLAN.day}.ics`; document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  bindOutingAlert(byId);
}

// What this browser can do about alerts (index.html's canPush, pushSub, IOS and IN_APP, as the Saved page's
// alerts tile reads them). Nothing is asked of the browser beyond what it already holds: no permission prompt.
async function outingPushState() {
  if (!outingDates().dateAlertsOn(DATA)) return { state: 'none' };
  if (!canPush()) return { state: IN_APP ? 'inapp' : IOS && !navigator.standalone ? 'ios' : 'cannot' };
  if (Notification.permission === 'denied') return { state: 'blocked' };
  const sub = Notification.permission === 'granted' ? await pushSub().catch(() => null) : null;
  return sub ? { state: 'on', sub } : { state: 'off' };
}
// The alerts part of the tile, once the push state is known. Nothing is sent until a button is pressed;
// then the whole list goes, as on the organisers' page.
async function bindOutingAlert(byId) {
  const el = document.getElementById('outing-alert'), msg = document.getElementById('outing-alert-msg');
  const D = outingDates(), st = await outingPushState();
  if (!el || !el.isConnected) return;   // the tile was drawn again meanwhile
  const t = outingRules().today(), pairs = outingPairs(PLAN, byId), endpoint = st.sub && st.sub.endpoint;
  let mem = null;   // the list as last sent, where this browser cannot keep it
  const kept = key => { try { return D.keptDates(localStorage.getItem(key), endpoint, t); } catch (e) { return []; } };
  const read = () => mem || kept(D.DATES_KEY), asked = () => kept(OUTING_ASKED_KEY);
  const named = ps => ps.map(p => ({ ...p, name: byId.has(p.spot) ? byId.get(p.spot).name : p.spot }));
  const paint = () => {
    const list = read();
    el.innerHTML = outingAlert({ state: st.state, pairs, list, earlier: named(outingEarlier(asked(), list, pairs)), saved: savedPath(), app: IN_APP });
    const go = document.getElementById('outing-to-alerts');
    if (go) go.addEventListener('click', e => { if (!plainClick(e)) return; e.preventDefault(); openSaved();
      const h = document.getElementById('alerts-h'); if (h) { h.tabIndex = -1; h.scrollIntoView({ block: 'start' }); h.focus({ preventScroll: true }); } });
    el.querySelectorAll('[data-outing-alert]').forEach(b => b.addEventListener('click', async () => {
      const how = b.dataset.outingAlert, list = read(), k = outingAsk(list, pairs);
      const these = how === 'add' ? k.add : how === 'stop' ? k.on : outingEarlier(asked(), list, pairs), on = how === 'add';
      const next = outingList(list, these, on);
      el.querySelectorAll('button').forEach(x => { x.disabled = true; }); msg.textContent = '';
      try {
        await D.sendDates(DATA.push.url, st.sub, next);
        mem = next; D.storeDates(st.sub, next);
        try { localStorage.setItem(OUTING_ASKED_KEY, JSON.stringify({ endpoint, dates: outingList(asked(), these, on) })); } catch (e) { /* the earlier-choice line needs it only */ }
        paint();
        const names = [...new Set(named(these).map(p => p.name))].join(' and ');
        msg.textContent = on ? `Alerts are on for ${names}.` : how === 'stop' ? 'Alerts for this outing are off.' : `Alerts are off for ${names}.`;
      } catch (e) { el.querySelectorAll('button').forEach(x => { x.disabled = false; }); msg.textContent = `Could not change alerts for this outing: ${e.message}.`; }
    }));
  };
  paint();
}

if (typeof module === 'object' && module.exports) {
  module.exports = { OUTING_PARTS, OUTING_HOURS, OUTING_CHECK, OUTING_ASKED_KEY, outingOfficial, outingSpan, outingWhen, outingTimeNote, outingForDay, outingOptions, outingPair, outingSection,
    outingPairs, outingAsk, outingList, outingEarlier, outingAlert, outingIcs };
}
