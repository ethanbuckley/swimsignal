// SwimSignal, the redesign preview: the page. model.js (window.PV) works everything out; this file draws it and
// answers taps and keys. The opening ("Where do you swim?") has three other views, Map, Plan and Saved; a place has
// its own page, which keeps one date for everything on it: the tabs, the answer, what is behind the level, the water
// upstream (as a line or on a map) and the places elsewhere.
// Saved places, the plan and the alerts are the live site's own (lists.js, plan.js, the alert service), kept under
// the live site's keys in this browser, so a place saved on either page is saved on both.
(function () {
'use strict';
const P = window.PV, app = document.getElementById('app'), saidEl = document.getElementById('said');
const { esc, capFirst, num } = P;
let DATA = null, HERO = {}, PLACES = null, POSTCODES = null, here = null, hereNote = '', route = null;
let miles = 20, upView = 'line', mapPick = null, PLAN = null, planPreview = false, planOff = null, planNew = false, planFresh = false, planSeen = null, planTyped = null, listForm = null, alertsOn = null, alertsSaid = '', alertsRefused = 0;
const expanded = new Set(), LINE_FIRST = 6;   // the places whose line upstream is shown whole
const traces = new Map();                     // id -> the traced water's lines, null if there is none; undefined while reading
const details = new Map();                    // id -> { detail, up } once fetched; undefined while reading
const now = () => Date.now();
// A point tapped on the map that is no listed place (anypoint.js): its forecast, worked out here, by its id
// ("point-<lat>,<lon>"). undefined while it is being worked out; { failed } if it could not be.
const POINTS = new Map();
const spotOf = id => DATA.spots.find(p => p.id === id) || (POINTS.get(id) && !POINTS.get(id).failed ? POINTS.get(id) : undefined);
const say = t => { saidEl.textContent = ''; setTimeout(() => { saidEl.textContent = t; }, 60); };

// Saved places, kept on this device only, as the live site keeps them: named lists under 'dipcast.lists', and every
// saved place under the older 'dipcast.saved' too, which the live page and its alerts still read (lists.js).
// Until 24 November 2026 this preview kept a list of its own; what it held is moved across once.
const stored = key => { try { return localStorage.getItem(key); } catch (e) { return null; } };
const SAVED_KEY = 'dipcast.saved', PLAN_KEY = 'dipcast.plan', OLD_KEY = 'swimsignal.preview.places';
let LISTS = readLists(stored(LISTS_KEY), stored(SAVED_KEY));
const storeLists = () => { try { localStorage.setItem(LISTS_KEY, listsText(LISTS)); localStorage.setItem(SAVED_KEY, JSON.stringify(allSaved(LISTS))); return true; } catch (e) { return false; } };
(function carryOver() { let old = []; try { old = JSON.parse(stored(OLD_KEY) || '[]'); } catch (e) { old = []; }
  if (!Array.isArray(old) || !old.length) return;
  for (const id of old) if (typeof id === 'string') LISTS = addToList(LISTS, LISTS.current, id);
  if (storeLists()) try { localStorage.removeItem(OLD_KEY); } catch (e) { /* tried again next visit */ } })();
const savedIds = () => allSaved(LISTS), knownSaved = () => savedIds().filter(id => DATA && spotOf(id));
// Change the lists. Returns false when the browser would not keep them. The alert service is told a second later.
let syncTimer = null;
const syncSoon = () => { clearTimeout(syncTimer); syncTimer = setTimeout(() => { if (DATA && DATA.push) window.PVAlerts.sync(DATA.push, knownSaved()).catch(() => {}); }, 1000); };
function setLists(next) { LISTS = next; const ok = storeLists(); syncSoon();
  if (typeof writeSeen === 'function') writeSeen(new Set(allSaved(LISTS)));   // since.js: a place unsaved loses its note
  return ok; }
// Another tab changed them (the live site, say): follow it, or this tab's next change would undo that one.
window.addEventListener('storage', e => {
  if (e.key === LISTS_KEY) { if (!listsReadable(e.newValue)) return; LISTS = readLists(e.newValue, null); }
  else if (e.key === SAVED_KEY) LISTS = readLists(stored(LISTS_KEY) || listsText(LISTS), e.newValue);
  else return;
  if (DATA) draw();
});

// ------------------------------------------------------------------------------------------------ icons and small parts
// The live site's stroke set: 1.75 px, round caps, inheriting the text colour.
const glyph = d => `<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const IC = {
  search: glyph('<circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/>'),
  pin: glyph('<path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.3"/>'),
  back: glyph('<path d="m14.5 5-7 7 7 7"/>'),
  go: glyph('<path d="m9.5 5 7 7-7 7"/>'),
  down: glyph('<path d="m5 9.5 7 7 7-7"/>'),
  save: glyph('<path d="M6 3h12v18l-6-4-6 4Z"/>'),
  share: glyph('<path d="M12 15V3.5M8 7l4-3.5L16 7"/><path d="M6 11.5H5a1 1 0 0 0-1 1V20a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7.5a1 1 0 0 0-1-1h-1"/>'),
  today: glyph('<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M4.6 4.6 6 6M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4"/>'),
  map: glyph('<path d="m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2Zm6-2v16m6-14v16"/>'),
  plan: glyph('<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4m6-4v4"/>'),
  x: glyph('<path d="m6 6 12 12M18 6 6 18"/>'),
  water: glyph('<path d="M3 9c1.5-1.2 3-1.2 4.5 0s3 1.2 4.5 0 3-1.2 4.5 0 3 1.2 4.5 0M3 14c1.5-1.2 3-1.2 4.5 0s3 1.2 4.5 0 3-1.2 4.5 0 3 1.2 4.5 0M3 19c1.5-1.2 3-1.2 4.5 0s3 1.2 4.5 0 3-1.2 4.5 0 3 1.2 4.5 0"/>'),
};
const MARK = '<svg viewBox="0 0 512 512" aria-hidden="true"><rect width="512" height="512" fill="#0f5a61"/><path d="M430-20C330 110 470 230 300 290S110 380 190 540" fill="none" stroke="#5CC2B5" stroke-width="70" stroke-linecap="round"/><circle cx="318" cy="138" r="38" fill="#F08A4B"/><circle cx="165" cy="358" r="46" fill="none" stroke="#fff" stroke-width="22"/></svg>';
// Every address this script writes is read against the site's root, where each page's <base> points: the live
// site's own scripts (the saved lists, the plan) ask for the site's files that way, so they run here unchanged.
// HOME is where these pages are under that root: "preview/" while this is a preview beside the site, and nothing
// once these are the site's own pages (build_site.write_redesign; the build writes it on <html data-home>).
const SITE = new URL('./', document.baseURI).pathname, HOME = document.documentElement.dataset.home || '', BASE = SITE + HOME;
const PREVIEW = HOME !== '';
// The app these pages were made to replace. Beside a preview it is the site, at the root; once these pages are the
// site it lives on at classic/, for what is not here yet (build_site.write_classic).
const classic = (path = '') => ((PREVIEW ? '' : 'classic/') + path) || './';
const OLD = PREVIEW ? 'the current site' : 'the earlier version';
const link = r => { const a = P.queryFor(r); return a === './' ? HOME || './' : HOME + a; };
const dates = () => P.dates(DATA);
// The plan kept in this browser, as the live site keeps it (plan.js, planKept): never your own position.
const keptPlan = () => planKept(stored(PLAN_KEY), dates());
// A plan's address: "?view=plan" and its choices after the #, as the live site writes them (plan.js, planHash).
const planLink = (day, over = {}) => { const k = PLAN || keptPlan(); return HOME + '?view=plan' + planHash({ ...k, day: dates().includes(day) ? day : k.day || dates()[0], ...over }); };
// The four places a phone's bar at the bottom holds (docs/DESIGN.md, "Plan a swim"): Today, Map, Plan, Saved.
const NAV = [['', 'Today', 'today', 'Today'], ['map', 'Map', 'map', 'Map'], ['plan', 'Plan', 'plan', 'Plan a swim'], ['saved', 'Saved', 'save', 'Saved places']];
const navHref = v => v === 'plan' ? planLink(route.day) : link({ view: v, day: route.day });
const navOn = v => route.screen === 'find' && (route.view || '') === v;
const bar = (onPlace = false) => `<header class="bar"><a class="brand" href="${link({ day: route.day })}">${MARK}SwimSignal</a>${PREVIEW ? '<span class="tag">Preview</span>' : ''}
  <nav aria-label="Site">${onPlace ? `<a class="hbtn" href="${link({ day: route.day })}#find" aria-label="Find another place">${IC.search}<span class="wide-only">Find a place</span></a>` : ''}
  ${NAV.slice(1).map(([v, , , long]) => `<a class="hlink wide-only" href="${navHref(v)}"${navOn(v) ? ' aria-current="page"' : ''}>${esc(long)}</a>`).join('')}
  <a class="hlink wide-only" href="verification.html">Accuracy</a><a class="hlink wide-only" href="about.html">About</a><a class="hlink wide-only" href="${classic()}">${PREVIEW ? 'Current site' : 'Earlier version'}</a></nav></header>`;
const tabbar = () => { const n = knownSaved().length;
  return `<nav class="tabbar" aria-label="Main">${NAV.map(([v, name, ic, long]) => `<a href="${navHref(v)}"${navOn(v) ? ' aria-current="page"' : ''} aria-label="${esc(v === 'saved' && n ? `Saved places: ${n}` : long)}">${IC[ic]}<span>${esc(name)}</span>${v === 'saved' && n ? `<span class="n" aria-hidden="true">${n}</span>` : ''}</a>`).join('')}</nav>`; };
const photoOf = id => HERO[id] || null;
const thumb = id => { const p = photoOf(id);
  return p ? `<img class="thumb" src="guides/photos/${encodeURIComponent(p.file)}" width="${p.w}" height="${p.h}" alt="" loading="lazy" decoding="async">` : `<span class="thumb none">${IC.water}</span>`; };
// A place's five days as five marks, the day shown ringed. The words beside it carry the level; these are a glance.
const week = r => r.week.length ? `<span class="week" aria-hidden="true">${r.week.map(d => `<i class="${d.cls}${d.on ? ' on' : ''}"></i>`).join('')}</span>` : '';
const rowLink = (r, day) => `<a class="row" href="${link({ id: r.id, day })}">${thumb(r.id)}<span class="row-main"><b>${esc(r.name)}</b>`
  + `<span class="row-level ${r.cls}">${esc(r.words)}</span>`
  + (r.notice ? `<span class="row-notice">Official: ${esc(r.notice)}</span>` : '')
  + `<span class="row-sub">${esc([r.said, r.water || (r.said ? '' : r.area)].filter(Boolean).join(' · '))}</span></span>${week(r)}</a>`;
const rowHtml = (r, day) => `<li>${rowLink(r, day)}</li>`;
const rows = (list, day) => `<ul class="rows">${list.map(r => rowHtml(r, day)).join('')}</ul>`;
// The day control: every date the forecast covers. On the opening it sets the day the lists show; on a place, the page.
function dayTabsHtml(tabs, day, label, hrefFor) {
  return `<nav class="daytabs" aria-label="${esc(label)}"><ol>${tabs.map(t => { const on = t.date === day;
    return `<li><a class="daytab ${t.cls || ''}${on ? ' on' : ''}" href="${hrefFor(t.date)}" data-day="${t.date}"${on ? ' aria-current="true"' : ''} aria-label="${esc(t.said || P.longDate(t.date))}">`
      + `<span class="dt-top"><span class="dt-name">${esc(t.name)}</span> <span class="dt-dom">${t.dom}</span></span>${t.short ? `<span class="dt-mark" aria-hidden="true"></span><span class="dt-level">${esc(t.short)}</span>` : ''}</a></li>`; }).join('')}</ol></nav>`;
}
const stale = () => { const i = P.issuedWords(DATA, now()); return i.stale ? `<p class="notice" role="note"><b>Older forecast.</b> ${esc(i.note)}</p>` : ''; };
// "Saved spots, offline use and your data": what is kept in this browser, and the two things a visitor can turn off,
// the offline copy and the page-view counter. The privacy notice sends people here by this name, "at the bottom of
// the home page", for both, and the law asks for a free, simple way to object to each (PECR, Schedule A1). So where
// these pages are the site's own they carry it, on every page's foot, in the live page's words and with the live
// page's keys ('dipcast.offline', 'dipcast.count'), which the worker's start (below) and the counter (counter.js)
// already read. From 19:53 to the evening of 24 November 2026 the redesign was the home page without it.
let dataOpen = false, offlineSaid = '', countSaid = '';
const stayOff = key => { try { return localStorage.getItem(key) === 'off'; } catch (e) { return false; } };
const startWorker = () => navigator.serviceWorker.register(new URL('sw.js', document.baseURI)).catch(() => {});
const noTrack = () => navigator.globalPrivacyControl === true || navigator.doNotTrack === '1';
function yourDataHtml() {
  if (PREVIEW) return '';   // beside a preview the home page is the app's, which has it
  // The counter's row only where the build put the counter in. Its script is asked for by name: the build's stand-in
  // for a browser (prerender_preview.js) answers every id, and the built page must not say visits are counted there.
  const c = document.getElementById('page-counter'), counted = !!c && c.tagName === 'SCRIPT';
  return `<details class="yourdata" id="your-data"${dataOpen ? ' open' : ''}><summary>Saved spots, offline use and your data</summary>
    <p>Saved spots, the names of your lists and your swim journal are kept in this browser, and sent nowhere unless you turn on alerts on the Saved page (alerts send which spots are saved, not the lists' names or the journal). After a first visit the page and the latest forecast are stored on your device, so the site opens without signal at the water's edge; it then says how old the forecast is. <a href="privacy.html">Privacy notice</a>.</p>
    ${'serviceWorker' in navigator ? `<p><button type="button" class="textbtn" data-do="offline">${stayOff('dipcast.offline') ? 'Turn the offline copy back on' : 'Turn off the offline copy'}</button> <span id="offline-msg" role="status">${esc(offlineSaid)}</span></p>` : ''}
    ${counted ? `<p>Page views are counted, without cookies. ${noTrack() ? '' : `<button type="button" class="textbtn" data-do="count">${stayOff('dipcast.count') ? 'Count my visits again' : "Don't count my visits"}</button> `}<span id="count-msg" role="status">${esc(noTrack() ? 'Your browser asks sites not to track it, so your visits are not counted.' : countSaid)}</span></p>` : ''}
  </details>`;
}
// Turn the offline copy off or on (index.html, setOffline). Off removes the worker and everything it stored, an
// outing kept for offline use with it, and turns alerts off first, since they arrive through the worker: the alert
// service then deletes its record now. Returns false when the browser would not keep the choice.
async function setOffline(on) {
  let kept = true;
  try { if (on) localStorage.removeItem('dipcast.offline'); else localStorage.setItem('dipcast.offline', 'off'); } catch (e) { kept = false; }
  if (on) { startWorker(); return kept; }
  for (const r of await navigator.serviceWorker.getRegistrations()) await r.unregister();
  if ('caches' in window) for (const k of await caches.keys()) if (k.startsWith('dipcast-') || k === 'swimsignal-outing') await caches.delete(k);
  try { localStorage.removeItem('dipcast.outingpack'); } catch (e) { /* nothing kept */ }
  return kept;
}
async function offlineToggle() {
  const on = stayOff('dipcast.offline');
  const alerts = !on && DATA && DATA.push && window.PVAlerts.can() === 'yes' ? await window.PVAlerts.turnOff(DATA.push).catch(() => false) : false;
  const kept = await setOffline(on).catch(() => false);
  if (alerts) { alertsOn = false; alertsSaid = ''; }
  offlineSaid = !kept ? 'This browser is not keeping site data, so this lasts only until you close the page.'
    : on ? 'The offline copy is on again.' : `The offline copy is off, and deleted from this device.${alerts ? ' Alerts are off too: they need it.' : ''}`;
  dataOpen = true; draw(); const b = app.querySelector('[data-do="offline"]'); if (b) b.focus({ preventScroll: true });
}
function countToggle() {
  const was = stayOff('dipcast.count'); let kept = true;
  try { if (was) localStorage.removeItem('dipcast.count'); else localStorage.setItem('dipcast.count', 'off'); } catch (e) { kept = false; }
  countSaid = !kept ? 'This browser is not keeping site data, so it cannot keep this choice.'
    : was ? 'Your visits will be counted again from the next page you open.' : 'Your visits from this browser are not counted from the next page you open.';
  dataOpen = true; draw(); const b = app.querySelector('[data-do="count"]'); if (b) b.focus({ preventScroll: true });
}
const foot = () => { const c = (DATA && DATA.credits) || {};
  return `<footer class="foot"><p>${PREVIEW ? `This is a preview of a redesign, kept beside <a href="${classic()}">the current SwimSignal</a>. Both read the same forecast, and a place saved on one is saved on the other.`
      : `Keeping an outing for offline use, and a plan as a picture to send, are still on <a href="${classic()}">the earlier version of SwimSignal</a>, which reads the same forecast. A place saved on one is saved on the other.`} Saved places stay on this device.</p>
    <p><a href="methods.html">Method and limits</a> · <a href="verification.html">How accurate it has been</a> · <a href="privacy.html">Privacy</a> · <a href="terms.html">Terms</a></p>
    ${yourDataHtml()}
    <details><summary>Data sources and licences</summary><p>${esc(c.attribution || '')}</p><p>${esc(c.modified || '')} ${esc(c.endorsement || '')} <a href="terms.html#data">Full credits</a></p></details></footer>`; };
// One quiet line under a photo, the day first since the photo is of that day. Each part keeps to one line with its
// dot after it, so a narrow phone's second line never starts with a dot (the live page's rule).
const credit = p => [`Photo from ${esc(P.shortDate(p.taken))}`, esc(p.credit), p.licence_name ? `<a href="${esc(p.licence)}">${esc(p.licence_name)}</a>` : '',
  P.httpsLink(p.source) ? `<a href="${esc(p.source)}">Geograph</a>` : ''].filter(Boolean).map((t, i, a) => `<span class="cr">${t}${i < a.length - 1 ? ' ·' : ''}</span>`).join(' ');

// ------------------------------------------------------------------------------------------------ the opening
const homeDay = () => { const ds = P.dates(DATA); return ds.includes(route.day) ? route.day : ds[0] || today(); };
const plainTabs = () => dates().map(d => ({ date: d, name: P.tabName(d), dom: new Date(d + 'T12:00:00').getDate() }));
// One line under the opening's days: how many of all the places are at low risk on the day shown, so the days say
// something before a place is found. All that is kept of the earlier home page's count (decided 25 November 2026).
// Not while a search or an area is shown, whose own rows say it.
function tallyHtml(day) {
  if (route.q || route.area) return '';
  const t = P.tally(DATA.spots, day), on = esc(dayWord(day));
  return `<p class="tally">${t.low ? `${t.low} of the ${t.n} places ${t.low === 1 ? 'is' : 'are'} at low risk ${on}.` : `None of the ${t.n} places is at low risk ${on}.`}</p>`;
}
function homeHtml() {
  if (route.view === 'map') return mapViewHtml();
  if (route.view === 'saved') return savedHtml();
  if (route.view === 'plan') return planHtml();
  const day = homeDay(), tabs = P.dates(DATA).map(d => ({ date: d, name: P.tabName(d), dom: new Date(d + 'T12:00:00').getDate() }));
  const n = DATA.spots.length, issued = P.issuedWords(DATA, now());
  return `${bar()}<main id="main" class="home">
    <section class="opening">
      <h1 id="title" tabindex="-1">Where do you swim?</h1>
      <p class="lede">Sewage pollution risk for the next five days at ${n} rivers and lakes. A forecast, not a water test.</p>
      <form class="ask" role="search" onsubmit="return false" id="find">
        <label class="sr" for="q">A river, lake, town or postcode</label>
        <div class="field">${IC.search}<input id="q" type="search" placeholder="River, lake, town or postcode" autocomplete="off" autocapitalize="none" spellcheck="false" enterkeyhint="search" value="${esc(route.q || '')}">
          </div>
        <p class="near"><button type="button" class="textbtn" data-do="locate">${IC.pin}Places near me</button><span class="meta" id="here-note">${esc(hereNote)}</span></p>
      </form>
    </section>
    ${stale()}
    <div class="home-body">
      ${dayTabsHtml(tabs, day, 'Day shown', d => link({ q: route.q, area: route.area, day: d }))}
      ${tallyHtml(day)}
      <div id="results">${resultsHtml(day)}</div>
      <p class="issued">${esc(issued.text)}. Levels are for ${esc(P.headDay(day) === 'today' ? 'today' : P.longDate(day))}.</p>
      ${researchHtml()}
    </div>
    ${foot()}
  </main>${tabbar()}`;
}
// The research line, after the list (docs/DESIGN.md, "After the review: near me, the record, the research, a shorter
// phone page", 12 November 2026, ported here 25 November): what is being tested beside the live forecast, from the
// scorecard's own file, read once a visit after the page is drawn, with the way to the scorecard and the Research Lab.
// Until the file is read, or if it cannot be, the plain line; the built page has the plain line, so it is the same
// height when the count arrives.
let researchSaid = '', researchAsked = false;
const researchHtml = () => `<p class="meta research-line"><span id="research-now">${esc(researchSaid || P.RESEARCH_PLAIN)}</span> <a href="models.html">What is being tested now</a> · <a href="lab/">Research Lab</a>.</p>`;
function researchLine() {
  if (researchAsked || typeof fetch !== 'function') return;
  researchAsked = true;
  loadJson('data/research/model_scorecard.json').then(doc => { researchSaid = P.researchNow(doc, today());
    const el = document.getElementById('research-now'); if (el && researchSaid) el.textContent = researchSaid; }).catch(() => {});
}
// The place whose photo stands for each area, picked by eye on 24 November 2026 from the photos the guides hold: open
// water in good light, level horizon, no boat or sign filling the frame. An area not named here, or whose place has
// gone, takes its first landscape photo.
const AREA_PHOTO = { 'Cumbria and the Lake District': 'wastwater', Yorkshire: 'bw-uke4100-08901', Scotland: 'scot-lomond-rowardennan', 'Thames Valley': 'thames-lechlade',
  'South West': 'teign-fingle-bridge', 'Severn and the Welsh borders': 'bw-ukg2200-36060', 'East of England': 'cam-grantchester', 'South and South East': 'bw-ukj3308-19001',
  'Peak District and Sheffield': 'derwent-slippery-stones', London: 'bw-uki1101-11920', Midlands: 'bw-ukf2208-09701', 'North East': 'tees-low-force', Lancashire: 'lune-crook-o-lune' };
// Everything under the day control: what was searched for, or a picked area, or the first look.
function resultsHtml(day) {
  const q = (route.q || '').trim(); let out = '';
  if (here) out += `<section class="block"><h2>Nearest to you</h2>${rows(P.nearest(DATA.spots, here, day, 6), day)}<p class="meta">Miles in a straight line.</p></section>`;
  if (q.length >= 2) {
    const hits = P.findSpots(DATA.spots, q).slice(0, 8).map(p => P.placeRow(p, day));
    if (hits.length) out += `<section class="block"><h2>${hits.length === 1 ? 'One place matches' : `${hits.length} places match`}</h2>${rows(hits, day)}</section>`;
    const pc = P.postcodeKeys(q); let points = [];
    if (pc && POSTCODES) { const at = (pc.sector && POSTCODES.sectors[pc.sector]) || POSTCODES.districts[pc.district];
      if (at) points.push({ name: pc.sector && POSTCODES.sectors[pc.sector] ? pc.sector : pc.district, lat: at[0], lon: at[1] }); }
    if (!points.length && PLACES) points = P.findTowns(PLACES.places, q);
    const shown = new Set(hits.map(p => p.id));
    for (const t of points) out += `<section class="block"><h2>Near ${esc(t.name)}</h2>${rows(P.nearest(DATA.spots.filter(p => !shown.has(p.id)), t, day, 5), day)}<p class="meta">Miles in a straight line from ${esc(t.name)}.</p></section>`;
    // A postcode that is not in the file (Northern Ireland's are not) is said as that, in the live page's words.
    if (!hits.length && !points.length) out += `<p class="none">${!(pc ? POSTCODES : PLACES) ? 'Looking…' : pc ? `No postcode found for “${esc(q)}”: type a town, a village or a river.`
      : `Nothing found for “${esc(q)}”. Try a river, a lake, a town or the first half of a postcode.`}</p>`;
    return out;
  }
  if (route.area) {
    const ps = DATA.spots.filter(p => p.area === route.area);
    if (ps.length) return `<section class="block area-page"><p class="backline"><a href="${link({ day })}">${IC.back}All areas</a></p><h2 class="area-h" tabindex="-1">${esc(route.area)}</h2>
      ${P.waters(ps, day).map(w => `<div class="water${w.ordered ? ' ordered' : ''}">${w.rows.length > 1 ? `<h3>${esc(w.name)}${w.ordered ? ' <span class="meta">from the top of the river down</span>' : ''}</h3>` : ''}${rows(w.rows.map(r => ({ ...r, area: '' })), day)}</div>`).join('')}</section>`;
  }
  const mine = knownSaved().map(spotOf);
  if (mine.length) out += `<section class="block"><h2>Your places</h2>${rows(mine.slice(0, 6).map(p => P.placeRow(p, day)), day)}<p class="meta"><a href="${link({ view: 'saved', day })}">${mine.length > 6 ? `All ${mine.length} saved places` : 'Saved places'} and alerts</a></p></section>`;
  const used = [];
  out += `<section class="block"><h2>${mine.length || here ? 'Every area' : 'Or pick an area'}</h2><ul class="areas">${P.areas(DATA.spots, day).map(a => {
    const id = (AREA_PHOTO[a.name] && a.ids.includes(AREA_PHOTO[a.name]) && photoOf(AREA_PHOTO[a.name]) ? AREA_PHOTO[a.name] : '')
      || a.ids.find(i => photoOf(i) && photoOf(i).w / photoOf(i).h >= 1.3) || a.ids.find(photoOf), p = id && photoOf(id);
    if (p) used.push([id, p]);
    return `<li><a class="area" href="${link({ area: a.name, day })}">${p ? `<img src="guides/photos/${encodeURIComponent(p.file)}" width="${p.w}" height="${p.h}" alt="" loading="lazy" decoding="async">` : `<span class="noimg">${IC.water}</span>`}
      <span class="area-name">${esc(a.name)}</span><span class="area-n">${a.n} places · ${a.low} at low risk ${esc(dayWord(day))}</span></a></li>`; }).join('')}</ul>
    <details class="credits"><summary>Photo credits</summary><ul>${used.map(([id, p]) => `<li>${esc(spotOf(id).name)}: ${credit(p)}</li>`).join('')}</ul><p>Older photos, each of one day. The place may have changed.</p></details></section>`;
  return out;
}
const loadJson = async path => { const r = await fetch(path); if (!r.ok) throw new Error(`${path}: ${r.status}`); return r.json(); };
// The towns or the postcodes, read the first time one is searched for, then the results drawn again with them. A
// search that arrives in the address (a link, or Back from a place) needs them as much as one being typed.
async function loadNear(v) {
  const pc = !!P.postcodeKeys(v) || (typeof looksLikePostcode === 'function' && looksLikePostcode(v));
  if (String(v).trim().length < 2 || (pc ? POSTCODES : PLACES)) return;
  try {
    if (pc) POSTCODES = await loadJson('data/postcodes.json');
    else PLACES = await loadJson('data/places.json');
  } catch (e) { PLACES = PLACES || { places: [] }; POSTCODES = POSTCODES || { sectors: {}, districts: {} }; }
}
async function nearWords(v) {
  if (v.trim().length < 2 || (P.postcodeKeys(v) ? POSTCODES : PLACES)) return;
  await loadNear(v);
  const again = document.getElementById('results'); if (again && route.screen === 'find' && !route.view && (route.q || '') === v) again.innerHTML = resultsHtml(homeDay());
}
function typed(v) {
  route.q = v; route.area = '';
  history.replaceState(null, '', link(route));
  const box = document.getElementById('results'); if (box) box.innerHTML = resultsHtml(homeDay());
  nearWords(v);
}
function locate(after) {
  const note = t => { hereNote = t; const n = document.getElementById('here-note'); if (n) n.textContent = t; };
  if (!navigator.geolocation) { note('This browser cannot give a location. Type a town or postcode instead.'); return; }
  note('Asking this browser where you are…');
  navigator.geolocation.getCurrentPosition(p => { here = { lat: p.coords.latitude, lon: p.coords.longitude }; hereNote = 'Using where you are. It stays in this browser.'; after(); },
    () => note('No location was given. Type a town or postcode instead.'), { maximumAge: 600000, timeout: 15000 });
}

// ------------------------------------------------------------------------------------------------ the map
const TOUCH = matchMedia('(pointer: coarse)').matches;
const KEYS = [['lv-low', 'Low'], ['lv-moderate', 'Moderate'], ['lv-high', 'High'], ['lv-veryhigh', 'Very high'], ['lv-clear', 'No monitored overflow found upstream'], ['lv-none', 'No level']];
function mapCardHtml(day) {
  const s = mapPick && spotOf(mapPick);
  return s ? `<div class="picked"><ul class="rows"><li class="has-x">${rowLink(P.placeRow(s, day, here), day)}<button type="button" class="x" data-do="map-close" aria-label="Close ${esc(s.name)}">${IC.x}</button></li></ul></div>`
    : `<p class="meta map-tip" id="map-tip" role="status">${esc(mapSaid || `${TOUCH ? 'Tap' : 'Click'} a place for its forecast ${dayWord(day)}${typeof AnyPoint === 'object' ? ', or any river or lake' : ''}.`)}</p>`;
}
function mapViewHtml() {
  const day = homeDay();
  return `${bar()}<main id="main" class="home view-map">
    <h1 id="title" class="sr" tabindex="-1">Map</h1>
    ${stale()}
    <div class="home-body">
      ${dayTabsHtml(plainTabs(), day, 'Day shown', d => link({ view: 'map', day: d }))}
      <div class="mapbox"><div class="map-slot" id="home-map"><p class="meta map-wait">Reading the map…</p></div>
        <button type="button" class="chip map-near" data-do="map-near">${IC.pin}Near me</button></div>
      <div class="map-side"><div id="map-card" aria-live="polite">${mapCardHtml(day)}</div>
      <p class="mapkey"><b>Pollution risk ${esc(dayWord(day))}</b>${KEYS.map(([c, w]) => `<span><i class="${c}"></i>${w}</span>`).join('')}<span><i class="adv"></i>Ringed: an official notice</span></p>
      <p class="meta" id="here-note">${esc(hereNote)}</p>
      <p class="meta">The map shows the ${DATA.spots.length} listed places. <a href="${link({ day })}">The same places as a list</a>. A river or lake that is not listed has a forecast too: zoom in and ${TOUCH ? 'tap' : 'click'} the water.</p></div>
    </div>
    ${foot()}
  </main>${tabbar()}`;
}
let mapGoHere = false, mapSaid = '';
// A tap on the map that is on no listed place: a river or lake to forecast. Further out than this a pixel is half a
// kilometre or more and only the big rivers are drawn, so the map zooms in on the tap and asks again (anypoint.js,
// POINT_ZOOM and CLOSER, the live map's own rule).
function tapWater(lat, lon, zoom) {
  if (typeof AnyPoint !== 'object') return;
  const need = AnyPoint.POINT_ZOOM || 9;
  if (zoom < need) { window.PVMap.homeTo({ lat, lon }, need + 2); mapSaid = `Zoomed in. Now ${TOUCH ? 'tap' : 'click'} a river or lake for its forecast.`;
    const said = document.getElementById('map-tip'); if (said) said.textContent = mapSaid; return; }
  const pt = P.pointOf(`${lat.toFixed(5)},${lon.toFixed(5)}`), tip = document.getElementById('map-tip');
  if (!pt) { mapSaid = 'That point is outside Britain and Ireland, so there is no forecast to work out for it.'; if (tip) tip.textContent = mapSaid; return; }
  mapSaid = '';
  leftAt.set(location.pathname + location.search, { y: window.scrollY, href: '' });
  history.pushState(null, '', link({ id: pt.id, day: route.day })); draw({ focus: true });
}
function mountHomeMap() {
  const slot = document.getElementById('home-map'); if (!slot) return;
  const day = homeDay(), points = P.mapPoints(DATA.spots, day);
  const pick = id => { mapPick = id; mapSaid = ''; const card = document.getElementById('map-card'); if (card) card.innerHTML = mapCardHtml(day); window.PVMap.home(slot, points, mapPick, pick, here, tapWater).catch(() => {}); };
  window.PVMap.home(slot, points, mapPick, pick, here, tapWater).then(() => { const w = slot.querySelector('.map-wait'); if (w) w.remove();
    if (mapGoHere && here) { mapGoHere = false; window.PVMap.homeTo(here); } })
    .catch(() => { slot.innerHTML = `<p class="none">The map could not be read just now. <a href="${link({ day })}">The same places as a list</a></p>`; });
}

// ------------------------------------------------------------------------------------------------ saved places and alerts
// The alerts' words are the live page's, word for word (index.html, alertsCard): what is sent, to whom and how to
// take it back is what makes the consent informed, and it was reviewed there. tests/site_preview.test.cjs holds
// the two together.
function alertsHtml() {
  const push = DATA.push; if (!push) return '';
  const A = window.PVAlerts, w = A.where, can = A.can();
  const what = 'A notification when one of your saved spots reaches high or very high risk, at most once a day for each.' + (push.advice ? ' Another when official advice is newly shown at one of them, also at most once a day for each.' : '');
  const sends = 'Turning alerts on sends your browser\'s push address and the list of your saved spots, and nothing else about you, to SwimSignal\'s alert service. Ticking the weekly note adds only that you want it. ' + (push.clears === true ? 'Asking, on a spot\'s page, to hear when it is back to low risk adds only that spot. ' : '') + 'Alerts reach you through your browser maker\'s push service (Google, Apple, Mozilla or Microsoft), encrypted so it cannot read them. '
    + 'You can turn them off here at any time, which deletes what the alert service holds. An alert can be late or not come at all, so no alert does not mean the water is clean. <a href="privacy.html">Privacy notice</a>.';
  const body = can === 'offline' ? '<p class="meta">Alerts need the offline copy, which is turned off in this browser. <a href="' + (PREVIEW ? classic('#your-data') : '#your-data') + '" data-do="to-data">Turn it back on</a> to use them.</p>'
    : can === 'blocked' ? `<p class="meta" id="alerts-blocked" tabindex="-1">Notifications are blocked for this site in your browser settings, so alerts cannot be turned on. ${esc(unblockHow(w))}</p>`
    : can === 'yes' ? `<p class="alerts-go"><button type="button" class="btn" data-do="alerts"${alertsOn === null ? ' disabled' : ''}>${alertsOn ? 'Turn off alerts' : 'Turn on alerts'}</button></p>`
      + `<label class="tick"${alertsOn ? '' : ' hidden'}><input type="checkbox" id="alerts-week"${alertsOn && A.weeklyOn() ? ' checked' : ''}><span>Also a weekly note on Thursday evenings: the days with the lowest pollution risk, Friday to Monday, at each saved spot.</span></label>`
    : can === 'inapp' ? `<p class="meta">Alerts cannot be turned on in the ${esc(w.inApp)} app's browser. Open this page in ${esc(w.own)} (the ${esc(w.inApp)} app's menu has an option for it) and save your places there.</p>`
    // An iPhone's Home Screen app opens the site's own first page. Beside a preview that is the current site; once
    // these pages are the site it is this page, and the words are the live tile's.
    : can === 'ios' ? (PREVIEW ? '<p class="meta">On iPhone and iPad, alerts work only in the Home Screen app, which opens the current site and keeps its own saved places. <a href="' + classic('saved/') + '">Set them up there</a>.</p>'
      : '<p class="meta">On iPhone and iPad, alerts work only in the Home Screen app: tap <b>Share</b>, then <b>Add to Home Screen</b>, open SwimSignal from there and save your spots in it.</p>')
    : '<p class="meta">This browser cannot show notifications from websites.</p>';
  return `<section class="alerts" id="alerts" aria-labelledby="alerts-h"><h2 id="alerts-h">Alerts</h2><p class="sec-lede">${what}</p>
    <details class="consent"><summary>What turning alerts on sends</summary><p>${sends}</p></details>${body}<p class="meta" id="alerts-msg" role="status">${esc(alertsSaid)}</p></section>`;
}
const redrawAlerts = () => { const sec = document.getElementById('alerts'); if (!sec) return; const open = !!sec.querySelector('details[open]'); sec.outerHTML = alertsHtml();
  const d = document.querySelector('#alerts details'); if (d) d.open = open; };
async function alertsToggle() {
  const A = window.PVAlerts, on = !alertsOn; alertsOn = null; alertsSaid = ''; redrawAlerts();
  try { if (on) await A.turnOn(DATA.push, knownSaved()); else await A.turnOff(DATA.push);
    alertsOn = on; alertsSaid = on ? 'Alerts are on for your saved spots.' : 'Alerts are off.'; }
  catch (e) { alertsOn = !on;
    alertsSaid = e.answer && A.can() === 'blocked' ? '' : e.answer ? notAllowedSaid({ answer: e.answer, again: alertsRefused++ > 0, ...A.where })
      : A.serviceDown(e) ? 'Could not reach the alert service, so alerts are as they were. Try again later.' : `Could not change alerts: ${e.message}.`; }
  redrawAlerts();
  const to = document.getElementById('alerts-blocked') || document.querySelector('[data-do="alerts"]'); if (to) to.focus({ preventScroll: true });
}
// A list someone shared (saved/#list=...&spots=..., lists.js, readShared): shown, not kept, with one thing to do,
// add it to my lists. It stays in the address while it is shown, so a reload or Back shows it again. The words are
// the live page's (index.html, renderShared).
function sharedHtml(sh) {
  const day = dates().includes(sh.day) ? sh.day : homeDay(), spots = sh.spots.map(spotOf).filter(Boolean), gone = sh.spots.length - spots.length;
  const have = spots.length ? sameList(LISTS, sh.name, spots.map(s => s.id)) : null, inApp = window.PVAlerts.where.inApp, own = window.PVAlerts.where.ios ? 'Safari' : 'your own browser';
  return `${bar()}<main id="main" class="home view-saved">
    <section class="opening slim"><p class="backline"><a href="${link({ view: 'saved' })}">${IC.back}Saved</a></p><h1 id="title" tabindex="-1">${esc(sh.name)}</h1>
      <p class="lede">Someone shared this list${spots.length ? ` of ${spots.length === 1 ? 'one spot' : `${spots.length} spots`}` : ''} with you.${spots.length ? ' It is not kept on this device unless you add it.' : ''}${spots.length && !have && DATA.push ? ' Once added, it stays under Saved, where you can set up alerts for its spots.' : ''}</p></section>
    ${stale()}
    <div class="home-body">
      ${inApp && spots.length && !have ? `<p class="notice" role="note">You are in the ${esc(inApp)} app's browser. A list added here stays in the ${esc(inApp)} app, not in ${own}, and alerts cannot be turned on here. To keep it in ${own}, open this page there: the ${esc(inApp)} app's menu has an option for it.</p>` : ''}
      ${have ? `<p class="shared-act" role="status">It is in your lists already, as ${esc(have.name)}. <button type="button" class="textbtn" data-do="shared-show" data-list="${esc(have.id)}">Show it</button></p>`
        : spots.length ? '<p class="shared-act"><button type="button" class="btn primary" data-do="shared-add">Add to my lists</button></p>' : ''}
      <section class="block">
        ${spots.length ? `<h2>${spots.length === 1 ? 'The place' : `The ${spots.length} places`} <span class="meta">${esc(dayWord(day))}</span></h2>${rows(spots.map(p => P.placeRow(p, day)), day)}`
          : `<h2>No spots to show</h2><p class="sec-lede">None of the spots in this link is in the forecast now, or the link was cut short.</p><p><a class="btn primary" href="${link({ day })}">Find a place</a></p>`}
        ${gone && spots.length ? `<p class="meta">${gone === 1 ? 'One spot in the link is' : `${gone} spots in the link are`} not in the forecast now, so ${gone === 1 ? 'it is' : 'they are'} left out.</p>` : ''}
      </section>
      <p class="issued">${esc(P.issuedWords(DATA, now()).text)}. Forecasts, not water tests: check the signs at the water before you swim.</p>
    </div>
    ${foot()}
  </main>${tabbar()}`;
}
// Share the list shown: a link that opens it on another phone or for a friend (lists.js, shareHash). The phone's own
// share sheet where there is one, else the link is copied; if neither can be done the link is written out.
async function shareList() {
  const cur = shownList(LISTS), ids = cur.spots.filter(spotOf), msg = document.getElementById('share-list-msg');
  const url = new URL(link({ view: 'saved' }), document.baseURI).href + shareHash(cur.name, ids), say = t => { if (msg) msg.textContent = t; };
  try { if (TOUCH && navigator.share) await navigator.share({ title: `${cur.name} · SwimSignal`, url }); else { await navigator.clipboard.writeText(url); say('Link copied.'); } }
  catch (e) { if (e.name !== 'AbortError') say(url); }
}
// Move or copy a place between lists (the live page's "Your lists": lists.js moveToList, copyToList). Offered with
// two lists or more. It opens from the list shown to the next one, or into the list shown when that is empty, as a
// list just made is. The form stays up after a move, since sorting a list is several moves.
let moveSaid = '';
function moveFormHtml(cur, movable) {
  const here = cur.spots.some(spotOf), to = here ? LISTS.lists.find(l => l.id !== cur.id) : cur;
  return `<form class="listform moveform" onsubmit="return false"><h3 id="mv-h">Move or copy a place</h3>
      <p class="picks"><label for="mv-spot">Place<select id="mv-spot">${movable.map(x => `<optgroup label="${esc(x.l.name)}">${x.spots.map((s, i) => `<option value="${esc(x.l.id)} ${esc(s.id)}"${here && x.l.id === cur.id && !i ? ' selected' : ''}>${esc(s.name)}</option>`).join('')}</optgroup>`).join('')}</select></label>
        <label for="mv-to">To<select id="mv-to">${LISTS.lists.map(l => `<option value="${esc(l.id)}"${l.id === to.id ? ' selected' : ''}>${esc(l.name)}</option>`).join('')}</select></label></p>
      <p class="chips"><button type="button" class="btn" data-do="list-move">Move</button><button type="button" class="btn" data-do="list-copy">Copy</button><button type="button" class="textbtn" data-do="list-cancel">Done</button></p>
      <p class="meta" id="mv-said" role="status">${esc(moveSaid)}</p></form>`;
}
function listMove(copy) {
  const pick = document.getElementById('mv-spot'), dest = document.getElementById('mv-to'); if (!pick || !dest) return;
  const v = pick.value, at = v.indexOf(' '), fromId = v.slice(0, at), id = v.slice(at + 1), s = spotOf(id), to = listById(LISTS, dest.value), from = listById(LISTS, fromId);
  if (!s || !to || !from) return;
  const say = t => { moveSaid = t; draw(); const b = app.querySelector(`[data-do="${copy ? 'list-copy' : 'list-move'}"]`) || app.querySelector('[data-do="list-open"]'); if (b) b.focus({ preventScroll: true }); };
  if (to.spots.includes(id)) { say(`${s.name} is in ${to.name} already.`); return; }
  const kept = setLists(copy ? copyToList(LISTS, id, to.id) : moveToList(LISTS, id, fromId, to.id));
  say(!kept ? 'This browser is not keeping site data, so this change lasts only for this visit.' : `${copy ? 'Copied' : 'Moved'} ${s.name} ${copy ? 'to' : `from ${from.name} to`} ${to.name}.`);
}
// Open a list from its link (lists.js pastedList): the Home Screen app on an iPhone has no address bar, so a list
// sent to someone, or copied in Safari, is pasted here and opens as a shared list with its own "Add to my lists".
// Nothing is read from the clipboard: the reader pastes. Only a link to a Saved page of this site is taken.
const OPEN_WHY = { empty: 'Paste a link to a SwimSignal list first.', long: 'That is too long to be a link to a list.',
  notlink: 'That is not a link. Paste the whole link, starting https://.', site: 'That is a link to another website, not SwimSignal.',
  notlist: "That link has no list of spots in it. A list's link has saved/#list= in it." };
const openFormHtml = () => `<form class="listform" onsubmit="return false"><label for="list-link">Open a list from a link</label>
      <p class="meta">Paste a link to a list, sent to you or copied with Share this list${navigator.standalone ? ' in Safari' : ''}, to see it and add it here.</p>
      <div class="field"><input id="list-link" type="text" inputmode="url" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" maxlength="${PASTE_MAX}" enterkeyhint="go" placeholder="https://swimsignal.co.uk/saved/#list=…"></div>
      <p class="chips"><button type="button" class="btn" data-do="list-opened">Open</button><button type="button" class="textbtn" data-do="list-cancel">Cancel</button></p>
      <p class="meta" id="list-link-said" role="status"></p></form>`;
function listOpen() {
  const box = document.getElementById('list-link'), said = document.getElementById('list-link-said'); if (!box) return;
  const got = pastedList(box.value, location.origin);
  if (got.why) { said.textContent = OPEN_WHY[got.why]; box.focus(); return; }
  listForm = null; history.pushState(null, '', link({ view: 'saved', day: route.day }) + got.hash); draw({ focus: true });
}
// Compare your places: up to three saved places side by side, a column each. The five days first, the day shown
// shaded; then the water today, and what each level rests on and leaves out. The rules and the words are the live
// site's own (experience.js, compareDays and compareRows; plan.js, planCompareIds), so every cell says something:
// where the data is missing it says it is not known. No column is called the best: the reader decides which to look
// into further. Opens on the first three places of the list shown, until others are chosen; the choice is kept
// while the page is open, not stored.
let cmpIds = null, cmpOpen = false;
const vt = (kind, words) => `<span class="vt vt-${kind}">${words}</span>`;
window.valueTag = vt;   // compareRows marks each value's kind with the page's own tag
// The water today, as two cells: the temperature (model.js, waterTemp: measured, or an estimate said as one) and the
// level at the place's gauge, which is named, since places on one river often share one.
function compareWater(s) {
  const w = P.waterTemp(s, today(), now()), rs = s.river_state, at = rs && rs.station ? ` at ${esc(rs.station)}` : '';
  const word = rs && ({ low: 'low', normal: 'normal', high: 'high', 'very high': 'very high' })[rs.label];
  return [w ? `${esc(w.value)} ${vt(/^Measured/.test(w.note) ? 'measured' : 'estimate', esc(w.note.replace(/\.$/, '')))}` : vt('none', 'No reading'),
    !rs || P.isNil(rs.level_m) ? vt('none', 'No gauge') : rs.stale ? `${vt('none', 'No current reading')} ${vt('stale', `Last reading${at}: too old to use`)}`
      : `${num(rs.level_m, 2)}&nbsp;m${word ? `, ${word}` : ''} ${vt('measured', `Measured${at}`)}`];
}
function compareHtml(mine, day) {
  if (mine.length < 2 || typeof compareRows !== 'function' || typeof evidenceRows !== 'function') return '';
  const ids = cmpIds = planCompareIds(cmpIds, mine), ds = dates();
  // A place as its own file fills it out (its guide, for Access); until the file comes the cell says so.
  const full = s => { const got = details.get(s.id); return got ? { ...s, ...(got.detail || {}), detail_loaded: true, detail_missing: !got.detail && !!s.detail_file } : s; };
  const spots = ids.map(spotOf).filter(Boolean).map(full), n = spots.length;
  const opts = i => mine.map(s => `<option value="${esc(s.id)}"${s.id === ids[i] ? ' selected' : ''}>${esc(s.name)}</option>`).join('');
  // On a phone the three selects fold under "Choose the places" once two are chosen: open, they put the first day's
  // levels off the first screen (the live page's finding, 6 November 2026). The table's heads name the places chosen.
  const fold = !matchMedia('(min-width: 700px)').matches && ids.length >= 2 && !cmpOpen;
  const picks = `<details class="cmp-choose"${fold ? '' : ' open'}><summary>Choose the places</summary><p class="picks cmp-picks">${[0, 1, 2].map(i => `<label for="cmp-${i}">Place ${i + 1}${i === 2 ? ' (optional)' : ''}<select id="cmp-${i}" data-cmp="${i}"><option value="">Choose a place</option>${opts(i)}</select></label>`).join('')}</p></details>`;
  const head = `<section class="compare" id="compare" aria-labelledby="compare-h"><h2 id="compare-h">Compare your places</h2>
    <p class="sec-lede">Up to three saved places side by side: the next ${ds.length === 4 ? 'four' : 'five'} days, and what each level rests on.</p>${picks}`;
  if (n < 2) return `${head}<p class="meta" role="status">Choose at least two different places.</p></section>`;
  const days = spots.map(s => compareDays(s, ds)), facts = spots.map(s => compareRows(s, day, DATA.generated_at)), water = spots.map(compareWater);
  const cell = x => `<span class="lvl ${P.cls(x.level)}">${esc(x.words)}</span>`, hd = (r, j) => ` headers="${r} cmp-s${j}"`;
  // A row's label is a band across the columns, with what every column shares said once under it.
  const lab = (id, t, note = '') => `<tr class="lab"><th colspan="${n}" id="${id}"><span>${t}${note ? `<span class="lab-note">${note}</span>` : ''}</span></th></tr>`;
  // A row whose cells all say the same is one cell across the columns.
  const across = (id, cells) => cells.every(c => c === cells[0]) ? `<tr><td colspan="${n}" headers="${id} ${spots.map((s, j) => `cmp-s${j}`).join(' ')}">${cells[0]}</td></tr>`
    : `<tr>${cells.map((c, j) => `<td${hd(id, j)}>${c}</td>`).join('')}</tr>`;
  return `${head}<p class="meta">${esc(P.issuedWords(DATA, now()).text)}. A lower level is the forecast for sewage pollution, not a safety check: check the signs at the water.</p>
    <div class="cmp-scroll" tabindex="0" role="region" aria-label="Place comparison"><table class="cmp" style="--cols:${n}">
    <thead><tr>${spots.map((s, j) => `<th scope="col" id="cmp-s${j}"><a href="${link({ id: s.id, day: daily(s) ? day : null })}">${esc(s.name)}</a>${canPlanHere(s) ? `<a class="cmp-plan" href="${esc(planHereLink(s, day))}" data-plan-new aria-label="Plan an outing at ${esc(s.name)}">Plan here</a>` : ''}</th>`).join('')}</tr></thead><tbody>
    ${lab('cmp-days', `Pollution risk, next ${ds.length === 4 ? 'four' : 'five'} days`)}
    ${ds.map((iso, i) => `<tr${iso === day ? ' class="on" aria-current="true"' : ''}>${days.map((d, j) => !d.same
        ? `<td${hd('cmp-days', j)}><span class="day">${shortDay(iso)}</span>${cell(d.days[i])}</td>`
        : i ? '' : `<td class="same" rowspan="${ds.length}"${hd('cmp-days', j)}>${cell(d.days[0])}. The same on every day.</td>`).join('')}</tr>`).join('')}
    ${lab('cmp-temp', 'Water temperature', 'Today')}${across('cmp-temp', water.map(w => w[0]))}
    ${lab('cmp-level', 'Water level', 'Now. Not part of the level')}${across('cmp-level', water.map(w => w[1]))}
    ${facts[0].map(([label, , note], k) => lab(`cmp-r${k}`, label, note) + across(`cmp-r${k}`, facts.map(f => f[k][1]))).join('')}
    </tbody></table></div></section>`;
}
// The comparison drawn again where it is, the table kept where it was scrolled to: a place chosen, or a place's own
// file arrived. The files of the places compared are asked for once each.
function redrawCompare() {
  const el = document.getElementById('compare'); if (!el || route.view !== 'saved') return;
  const sc = el.querySelector('.cmp-scroll'), left = sc ? sc.scrollLeft : 0, focus = document.activeElement && document.activeElement.id;
  const t = document.createElement('template'); t.innerHTML = compareHtml(shownList(LISTS).spots.map(spotOf).filter(Boolean), homeDay());
  el.replaceWith(t.content); mountCompare();
  const sc2 = document.querySelector('#compare .cmp-scroll'); if (sc2) sc2.scrollLeft = left;
  if (focus && /^cmp-\d$/.test(focus)) { const f = document.getElementById(focus); if (f) f.focus({ preventScroll: true }); }
}
function mountCompare() {
  if (!document.getElementById('compare')) return;
  for (const id of cmpIds || []) if (!details.has(id)) loadDetail(id).then(redrawCompare);
}
function savedHtml() {
  const sh = readShared(location.hash, dates()); if (sh) return sharedHtml(sh);
  const day = homeDay(), cur = shownList(LISTS), many = LISTS.lists.length > 1, S = P.savedRows(DATA.spots, cur.spots, day);
  const mine = cur.spots.map(spotOf).filter(Boolean), isToday = day === today();
  // What changed since this browser last showed each place (since.js): a line under a place's row and one over them
  // all, only while today is shown, since the note kept is of today's level. Nothing over them on a first look.
  const sum = isToday && mine.length && typeof sinceSummaryFor === 'function' ? sinceSummaryFor(mine, DATA.generated_at) : null;
  const since = id => isToday && typeof sinceSaid === 'function' ? sinceSaid(spotOf(id), DATA.generated_at) : '';
  const row = r => `<li class="has-x">${rowLink(r, day)}<button type="button" class="x" data-do="unsave" data-id="${esc(r.id)}" aria-label="Remove ${esc(r.name)} from ${many ? esc(cur.name) : 'your saved places'}">${IC.x}</button>${since(r.id)}</li>`;
  const movable = LISTS.lists.map(l => ({ l, spots: l.spots.map(spotOf).filter(Boolean) })).filter(x => x.spots.length);
  const tools = listForm === 'new' || listForm === 'rename' ? `<form class="listform" onsubmit="return false"><label for="list-name">${listForm === 'new' ? 'Name the new list' : 'A new name for this list'}</label>
      <div class="field"><input id="list-name" type="text" maxlength="40" autocomplete="off" enterkeyhint="done" value="${listForm === 'rename' ? esc(cur.name) : ''}"></div>
      <p class="chips"><button type="button" class="btn" data-do="list-save">${listForm === 'new' ? 'Make the list' : 'Rename'}</button><button type="button" class="textbtn" data-do="list-cancel">Cancel</button></p></form>`
    : listForm === 'delete' ? `<p class="confirm" role="group" aria-label="Delete this list">Delete “${esc(cur.name)}”${cur.spots.length ? ` and what is saved in it? A place saved in another list stays there.` : '?'}
      <span class="chips"><button type="button" class="btn" data-do="list-delete">Delete the list</button><button type="button" class="textbtn" data-do="list-cancel">Keep it</button></span></p>`
    : listForm === 'move' && movable.length ? moveFormHtml(cur, movable)
    : listForm === 'open' ? openFormHtml()
    : `<p class="chips listtools">${S.rows.length || many ? `<button type="button" class="textbtn" data-do="list-new">New list</button><button type="button" class="textbtn" data-do="list-rename">Rename this list</button>${many ? '<button type="button" class="textbtn" data-do="list-del">Delete this list</button>' : ''}` : ''}${
        many && movable.length ? '<button type="button" class="textbtn" data-do="list-mv">Move or copy a place</button>' : ''}<button type="button" class="textbtn" data-do="list-open">Open a list from a link</button></p>`;
  return `${bar()}<main id="main" class="home view-saved">
    <section class="opening slim"><h1 id="title" tabindex="-1">Saved</h1><p class="lede">Your places, kept in this browser and nowhere else.</p></section>
    ${stale()}
    <div class="home-body">
      ${dayTabsHtml(plainTabs(), day, 'Day shown', d => link({ view: 'saved', day: d }))}
      ${many ? `<p class="chips" role="group" aria-label="Which list">${LISTS.lists.map(l => `<button type="button" class="chip${l.id === cur.id ? ' on' : ''}" data-do="list" data-list="${esc(l.id)}" aria-pressed="${l.id === cur.id}">${esc(l.name)} <span class="chip-n">${l.spots.filter(spotOf).length}</span></button>`).join('')}</p>` : ''}
      ${sum && sum.state !== 'none' ? `<section class="since-sum ${sum.state}" aria-labelledby="since-h"><h2 id="since-h">Since you last looked</h2><p>${esc(sum.text)}</p></section>` : ''}
      <section class="block">
        <h2>${many ? esc(cur.name) : 'Your places'}${S.rows.length ? ` <span class="meta">${S.low} of ${S.rows.length} at low risk ${esc(dayWord(day))}</span>` : ''}</h2>
        ${S.rows.length ? `<ul class="rows">${S.rows.map(row).join('')}</ul>` : `<p class="none">Nothing saved ${many ? 'in this list ' : ''}yet. Open a place and press Save. <a href="${link({ day })}">Find a place</a></p>`}
        ${S.gone ? `<p class="meta">${S.gone === 1 ? 'One saved place is' : `${S.gone} saved places are`} no longer in the forecast, so ${S.gone === 1 ? 'it is' : 'they are'} not shown.</p>` : ''}
        ${tools}<p class="meta" id="list-said" role="status"></p>
      </section>
      ${mine.length > 1 && typeof fwSection === 'function' ? fwSection(mine, dates(), s => link({ id: s.id })) : ''}
      ${compareHtml(mine, day)}
      ${alertsHtml()}
      ${mine.length ? `<section class="sharelist" aria-labelledby="share-list-h"><h2 id="share-list-h">Share this list</h2>
        <p class="sec-lede">A link that opens this list on another phone or browser, or for a friend, who can then add it to their own lists. It holds the list's name, ${esc(cur.name)}, and which spots are in it, nothing else.</p>
        <p><button type="button" class="btn" data-do="share-list">${TOUCH && navigator.share ? 'Share this list' : 'Copy link to this list'}</button></p><p class="meta" id="share-list-msg" role="status"></p>
        <p class="meta">For a club or a centre: these spots on one page to print, each with its five days. <a href="sites.html${esc(sitesHash(cur.name, mine.map(s => s.id)))}">Open the sites view</a>.</p></section>` : ''}
      ${journalHtml()}
      <p class="meta">A place saved here is saved on <a href="${classic('saved/')}">${OLD}</a> too, in this browser, and so is the journal.</p>
    </div>
    ${foot()}
  </main>${tabbar()}`;
}

// ------------------------------------------------------------------------------------------------ plan a swim
// The live site's plan (plan.js): the places within a distance of where you start, on one day, in its groups. Its
// choices are in the address after the #, in the live site's own form, so a plan's link opens on either.
let PLACE_INDEX = null;
const planPoint = () => { const f = PLAN.from; return !f ? null : f.here ? here : { lat: f.lat, lon: f.lon }; };
function planOffers(v) {
  v = String(v || '').trim(); if (v.length < 2) return [];
  if (looksLikePostcode(v)) { const p = POSTCODES ? postcodePlace(postcodeIndex(POSTCODES), v) : null; return p ? [p] : []; }
  if (!PLACE_INDEX && PLACES) PLACE_INDEX = placeIndex(PLACES);
  return PLACE_INDEX ? placeMatches(PLACE_INDEX, v, 6) : [];
}
function offersHtml(v) {
  v = String(v || '').trim(); if (planTyped === null || v.length < 2) return '';
  const offers = planOffers(v), ready = looksLikePostcode(v) ? POSTCODES : PLACES;
  return offers.length ? `<ul class="offers" aria-label="Places that match">${offers.map(o => `<li><button type="button" data-do="plan-from" data-name="${esc(o.name)}" data-lat="${o.lat}" data-lon="${o.lon}">${IC.pin}${esc(o.name)}</button></li>`).join('')}</ul>`
    : `<p class="none">${!ready ? 'Looking…' : looksLikePostcode(v) ? `No postcode found for “${esc(v)}”: type a town or a village.` : `No town or village found for “${esc(v)}”. Try the first half of a postcode.`}</p>`;
}
function planResultsHtml() {
  const day = PLAN.day, f = PLAN.from, when = dayWord(day);
  if (!f) { const as = planAreas(DATA.spots, PLAN, (a, b) => P.kmBetween({ lat: a[0], lon: a[1] }, { lat: b[0], lon: b[1] }) / MILE_KM, 3);
    return `<section class="block"><h2>Where do you start?</h2><p class="sec-lede">Type a town, a village or the first half of a postcode above.</p>
      ${as.length ? `<p class="meta">Or start from an area with places at low risk ${esc(when)}:</p><ul class="starts">${as.map(a => `<li><a href="${HOME}?view=plan${planFromArea(a, PLAN)}">${esc(a.area)}</a> <span class="meta">${a.low} of ${a.total} at low risk</span></li>`).join('')}</ul>` : ''}</section>`; }
  if (f.here && !here) return `<section class="block"><h2>This plan starts from where you are</h2><p class="sec-lede">Your position is never kept or put in a link, so this browser is asked for it again.</p>
    <p><button type="button" class="btn primary" data-do="plan-here">${IC.pin}Use my location</button></p></section>`;
  const start = planPoint(), found = planSpots(DATA.spots, PLAN, s => P.kmBetween(start, s) / MILE_KM), name = f.here ? 'where you are' : f.name;
  // What is counted, by the waters chosen: several listed places can be on one lake, so it is places that are counted.
  const [one, some] = ({ river: ['place on a river', 'places on rivers'], lake: ['place on a lake', 'places on lakes'], designated: ['designated bathing water', 'designated bathing waters'] })[PLAN.kind] || ['place', 'places'];
  const within = PLAN.within ? `within ${PLAN.within} miles of` : 'at any distance from';
  if (!found.count) { const n = found.nearest, reach = n ? reachFor(n.miles) : 0;
    return `<section class="block"><h2>No listed ${one} ${esc(within)} ${esc(name)}</h2>${n ? `<p class="sec-lede">The nearest is <a href="${link({ id: n.s.id, day })}">${esc(n.s.name)}</a>, ${esc(milesAway(n.miles))}.</p>
      <p><button type="button" class="btn" data-do="plan-within" data-within="${reach}">${reach ? `Look within ${reach} miles` : 'Look at any distance'}</button></p>` : '<p class="sec-lede">No place of that kind is listed.</p>'}</section>`; }
  const G = P.planRows(found, day, start), g = k => G.find(x => x.key === k), better = betterDay(found.groups.flat().map(o => o.s), day, dates());
  const low = g('low'), plain = g('plain'), raised = g('raised'), none = g('none');
  return `<section class="block"><h2>${found.count === 1 ? `One ${one}` : `${found.count} ${some}`} ${esc(within)} ${esc(name)}</h2>
    <p class="sec-lede">${esc(P.headDay(day) === 'today' ? 'Today' : P.longDate(day))}. Miles in a straight line.</p>
    ${better ? `<p class="better">More of these are at low risk ${esc(dayWord(better.date))}: ${better.low}, against ${better.was} ${esc(when)}. <a href="${planLink(better.date)}" data-day="${better.date}">Show ${esc(P.weekday(better.date))}</a></p>` : ''}
    ${low ? `<h3>Low risk ${esc(when)}, nearest first</h3>${rows(low.rows, day)}` : `<p class="none">No place here is forecast at low risk ${esc(when)}.</p>`}
    ${plain ? `<h3>No daily level</h3><p class="meta">No monitored overflow was found upstream of these. That is not the same as low risk.</p>${rows(plain.rows, day)}` : ''}
    ${raised ? `<details class="raised"${low ? '' : ' open'}><summary>${raised.rows.length === 1 ? 'One place' : `${raised.rows.length} places`} at moderate risk or higher ${esc(when)}</summary>${rows(raised.rows, day)}</details>` : ''}
    ${none ? `<h3>No level</h3>${rows(none.rows, day)}` : ''}
    <p class="meta">Low risk is the forecast for sewage pollution, not a safety check.</p></section>`;
}
function planHtml() {
  const day = PLAN.day, f = PLAN.from, typed = planTyped !== null ? planTyped : f && !f.here ? f.name : '';
  const KINDS = [['all', 'All waters'], ['river', 'Rivers'], ['lake', 'Lakes'], ['designated', 'Designated bathing waters']];
  return `${bar()}<main id="main" class="home view-plan">
    <section class="opening slim"><h1 id="title" tabindex="-1">Plan a swim</h1>
      ${f ? '' : '<p class="lede">The listed places within reach of where you start, on one day, lowest pollution risk first.</p>'}
      <form class="ask" role="search" onsubmit="return false">
        <label class="sr" for="from">Where you start: a town, a village or a postcode</label>
        <div class="field">${IC.pin}<input id="from" type="search" placeholder="Start from a town, village or postcode" autocomplete="off" autocapitalize="none" spellcheck="false" enterkeyhint="search" value="${esc(typed)}"></div>
        <div id="offers">${offersHtml(typed)}</div>
        <p class="near"><button type="button" class="textbtn" data-do="plan-here">${IC.pin}Start from where I am</button><span class="meta" id="here-note">${esc(hereNote)}</span></p>
      </form>
    </section>
    ${stale()}
    <div class="home-body">
      ${dayTabsHtml(plainTabs(), day, 'Day of the swim', d => planLink(d))}
      <p class="picks"><label for="plan-within">How far<select id="plan-within">${[...RADII, 0].map(m => `<option value="${m}"${PLAN.within === m ? ' selected' : ''}>${m ? `${m} miles` : 'Any distance'}</option>`).join('')}</select></label>
        <label for="plan-kind">Which waters<select id="plan-kind">${KINDS.map(([k, w]) => `<option value="${k}"${PLAN.kind === k ? ' selected' : ''}>${w}</option>`).join('')}</select></label></p>
      <div id="outing-box" class="outing-box"></div>
      <div id="results">${planResultsHtml()}</div>
      <p class="issued">${esc(P.issuedWords(DATA, now()).text)}.</p>
    </div>
    ${foot()}
  </main>${tabbar()}`;
}
// ------------------------------------------------------------------------------------------------ your outing
// A plan's outing (outing.js, the live site's own, with outingwatch.js and spotdate.js): when on the plan's day, the
// spot, a backup beside it, what for and where to meet; what would change the plan; the calendar file, the link to
// send, and alerts for its date. The script draws its own tile and answers its own controls, as on the live page:
// drawOuting(box, shown) is called after each draw of Plan, and the names it expects of its page are given below.
// It is kept as the plan is, in the plan's address and in this browser (PLAN_KEY), so an outing made on either design
// opens on the other.
//
// An outing opened from a link is shown, not kept (plan.js, planInvited): the plan kept here stays as it was until
// "Keep this outing". planArrived settles that once for each address that arrives (a link opened, Back, a link
// pasted over this one), never for this page's own changes, which planAddress writes and notes in planSeen.
function planAddress() {
  const h = planHash(PLAN);
  history.replaceState(null, '', HOME + '?view=plan' + h); planSeen = location.hash;
  if (!planPreview) try { localStorage.setItem(PLAN_KEY, h); } catch (e) { /* kept for this visit only */ }
}
function planArrived() {
  const hash = location.hash; if (planSeen === hash) return;
  const kept = keptPlan(), had = hash.length > 1, started = planNew;
  planPreview = planInvited(PLAN, kept, had, planPreview) && !(planNew && !planHasOuting(kept, dates()));
  planFresh = planPreview && (planNew || planFresh); planNew = false;
  planOff = planPreview && had ? planDayOff(hash, dates()) : null;
  // "Plan a swim here" with no outing still to come in this browser: kept at once, as on the live page.
  if (started && !planPreview) try { localStorage.setItem(PLAN_KEY, planHash(PLAN)); } catch (e) { /* kept for this visit only */ }
  if (typeof OUTING_DAY !== 'undefined') OUTING_DAY = null;   // an address's day is not a change of day (outing.js, outingForDay)
  planSeen = hash;
}
// "Plan a swim here", on a place's page and in a comparison's column (plan.js, planFromSpot): the plan with that place
// as the outing's, starting from the place, on the day shown. Not for a point tapped on the map.
function canPlanHere(s) { return typeof planFromSpot === 'function' && !!s && Number.isFinite(s.lat) && Number.isFinite(s.lon) && !s.unlisted; }
// The plan a new outing starts from: the one kept here, as what this browser last chose to do on the water (plan.js,
// readActs: a kayak or a board chosen on the live page's Plan a swim), so the link and its words follow it.
function planBase() { const b = keptPlan(), a = actDefault(readActs(stored(ACTS_KEY))); return a ? { ...b, act: a } : b; }
function planHereLink(s, day) { const base = planBase(); return HOME + '?view=plan' + planFromSpot(s, base, dates().includes(day) ? day : null); }
function planHereWords() { const a = planBase().act; return OUTING_FINISH_ACTS.includes(a) && typeof OUTING_ACT_WORDS === 'object' ? `Plan ${OUTING_ACT_WORDS[a][1]} here` : 'Plan a swim here'; }
// A place's own file, into the place itself, as the live page does (index.html, spotDetail): the outing reads the
// guide, the link between two places and a paddle's stretches from the place it was given.
async function spotDetail(s) {
  if (!s || s.detail_loaded || s.detail_missing) return s;
  if (!details.get(s.id)) await loadDetail(s.id);
  const got = details.get(s.id), d = got && got.detail;
  if (d) { for (const k of ['guide', 'linked', 'stretches']) if (k in d) s[k] = d[k]; s.detail_loaded = true; } else s.detail_missing = true;
  return s;
}
// The two readings the outing's conditions give beside the weather, in the shape the live page's tiles have
// (index.html, waterTile and riverTile): the figure, whether it is measured, and the level's own word.
function outWater(w, e, kind) {
  const t = P.waterTemp({ water_temp: w, water_temp_est: e, kind }, today(), now()); if (!t) return null;
  return /^Measured/.test(t.note) ? { live: true, fig: `${Math.round(w.temp_c)}°`, unit: 'C', say: esc(t.note) }
    : { fig: `${e.temp_c}°`, unit: /provisional/i.test(t.note) ? 'C, provisional estimate' : 'C, estimated', say: esc(t.note) };
}
function outLevel(rs) {
  if (!rs || (!rs.stale && P.isNil(rs.level_m))) return null;
  const lake = rs.water === 'lake', label = lake ? 'Lake level' : 'River level'; if (rs.stale) return { label, fig: '–' };
  const lo = rs.typical_low_m, hi = rs.typical_high_m, ranged = !P.isNil(lo) && !P.isNil(hi) && hi > lo;
  const word = lake ? (!ranged ? '' : rs.level_m < lo ? 'Below its usual range' : rs.level_m > hi ? 'Above its usual range' : 'In its usual range')
    : (({ low: 'Low water', normal: 'Usual level', high: 'High water', 'very high': 'Very high water' })[rs.label] || '') + (rs.label === 'very high' ? ', above its usual range' : '');
  return { label, fig: num(rs.level_m, 2), word, vis: '' };
}
// How much evidence sits behind a column's level (evidence.js; index.html, planEvidence): on a plan for today, a low
// level whose right now is not known; and whose overflows these are, with how the live warnings have done there,
// once the Accuracy page's figures are in.
let planWarn = null, planWarnAsked = false;
function planEvidence(s) {
  if (typeof evidenceNowGap !== 'function') return '';
  const line = [evidenceNowGap(s, PLAN.day === today() && dayLevel(s, PLAN.day) === 'low'), evidenceCompanyLine(s, planWarn)].filter(Boolean).join(' ');
  return line ? `<p class="ev-line">${line}</p>` : '';
}
function bindShareLink(b, m, url, title, copyLabel) {
  const touch = TOUCH && navigator.share; if (!touch) b.textContent = copyLabel;
  b.addEventListener('click', async () => {
    try { if (touch) await navigator.share({ title, url }); else { await navigator.clipboard.writeText(url); m.textContent = 'Link copied.'; } }
    catch (e) { if (e.name !== 'AbortError') m.textContent = url; } });
}
// What outing.js expects of its page, by the names it uses there. PLAN and the three flags are read where they are.
Object.defineProperties(window, { PLAN: { get: () => PLAN, configurable: true }, PLAN_PREVIEW: { get: () => planPreview, configurable: true },
  PLAN_OFF: { get: () => planOff, configurable: true }, PLAN_FRESH: { get: () => planFresh, configurable: true }, SAVED: { get: () => knownSaved(), configurable: true } });
Object.assign(window, { planAddress, keptPlan, keepPlan: () => { planPreview = false; planAddress(); }, spotDetail, planEvidence, bindShareLink,
  planFrom: () => { const p = PLAN && PLAN.from ? planPoint() : null; return p ? [p.lat, p.lon] : null; },
  km: (a, b) => P.kmBetween({ lat: a[0], lon: a[1] }, { lat: b[0], lon: b[1] }),
  tone: level => P.cls(level),
  // Why a place has its level on the plan's day: this page's own sentences for that day (model.js, answer).
  planWhy: (s, day) => esc((P.answer(s, day, DATA, now()).why || []).join(' ')),
  waterTile: outWater, riverTile: outLevel,
  // "13:21, 14 min ago", from this page's own issue line, in the three parts outing.js joins.
  issued: () => P.issuedWords(DATA, now()).text.replace(/^Issued /, '').replace(/, [^,]* ago$/, ''),
  ageMin: () => (P.issuedWords(DATA, now()).text.match(/, ([^,]*) ago$/) || [])[1] || '', ago: t => t,
  plainClick: e => !(e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button),
  // A place's name in the tile, and its link to Saved, are plain links to these pages' own addresses: the page's own
  // click handler follows them, once, so the two names the script calls for that do nothing here.
  select: () => {}, openSaved: () => {},
  // The plan's own address from the site's root, where a link to send must point: plan/ on the site, as both designs read.
  planPath: () => { const u = new URL(PREVIEW ? HOME + '?view=plan' : 'plan/', document.baseURI); return u.pathname + u.search; },
  SITE_ROOT: new URL('./', document.baseURI), BRAND: 'SwimSignal', TOUCH,
  canPush: () => window.PVAlerts.capable(), pushSub: () => window.PVAlerts.subscription() });
if (window.PVAlerts) { const w = window.PVAlerts.where; Object.assign(window, { IOS: w.ios, IN_APP: w.inApp, STANDALONE: w.app, SAFARI_MAC: w.safari }); }
// The outing's tile, at the top of the plan's results, as on the live page: under a plan that has a start, or one
// that already has a spot. shown: the plan's places, nearest first in their groups, which the tile offers first.
function mountOuting() {
  const box = document.getElementById('outing-box'); if (!box || typeof drawOuting !== 'function') return;
  const start = PLAN.from ? planPoint() : null;
  if (!start && !PLAN.spot) return;
  drawOuting(box, start ? planSpots(DATA.spots, PLAN, s => P.kmBetween(start, s) / MILE_KM).groups.flat() : []);
  if (!planWarnAsked && typeof evidenceWarnings === 'function') { planWarnAsked = true;
    evidenceWarnings().then(W => { if (!W) return; planWarn = W;
      if (route && route.view === 'plan' && !(document.activeElement && box.contains(document.activeElement))) mountOuting(); }); }
}
// A change to the plan: kept in this browser as the live site keeps it, written to the address, and drawn.
function planSet(over) {
  // An outing made on the live site keeps its place here, but its time and the levels it was sent with were for its
  // own day: on another day they go, as the live plan drops them (plan.js, planKept).
  if (over.day && over.day !== PLAN.day) for (const k of ['when', 'sent', 'lv', 'blv', 'flv']) delete PLAN[k];
  PLAN = { ...PLAN, ...over }; planTyped = null;
  planAddress(); draw();
}
function planTyping(v) {
  planTyped = v; const box = document.getElementById('offers'); if (box) box.innerHTML = offersHtml(v);
  loadNear(v).then(() => { const again = document.getElementById('offers'); if (again && planTyped === v) again.innerHTML = offersHtml(v); });
}

// ------------------------------------------------------------------------------------------------ a picture to share
// A place's forecast for the day shown, drawn into a picture on the device for a swim group's chat, in the earlier
// version's layout and type sizes (index.html, shareImage) with this page's colours and fonts. What it says is
// model.js's (pictureOf). Nothing leaves the device until the share sheet; without one (a desktop browser) the picture
// is saved instead. Drawn only when asked for: the build runs this file where there is no canvas.
function wrapText(g, text, x, y, maxW, lh) {
  let line = '';
  for (const w of String(text).split(' ')) { const t = line ? `${line} ${w}` : w;
    if (line && g.measureText(t).width > maxW) { g.fillText(line, x, y); y += lh; line = w; } else line = t; }
  if (line) { g.fillText(line, x, y); y += lh; }
  return y;
}
function saveFile(blob, name) { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000); }
// Said in the line under the place's name, looked up when said: the page may have been drawn again meanwhile.
const toolSaid = msg => { const t = document.getElementById('tool-said'); if (t) t.textContent = msg; };
async function sharePicture(s, day) {
  const p = P.pictureOf(s, day, DATA, now()), W = 1080, H = 1350, c = document.createElement('canvas'); c.width = W; c.height = H;
  const v = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const g = c.getContext('2d'), F = v('--font-text'), FD = v('--font-display');
  if (document.fonts && document.fonts.load) await Promise.all([document.fonts.load(`600 66px ${FD}`), document.fonts.load(`600 30px ${F}`)]).catch(() => {});
  g.fillStyle = v('--bg'); g.fillRect(0, 0, W, H);
  // The site's header: the wordmark in teal on the paper, the host, and a hairline under them.
  g.fillStyle = v('--brand'); g.font = `600 56px ${FD}`; g.fillText(p.brand, 60, 96);
  g.fillStyle = v('--muted'); g.font = `600 30px ${F}`; g.textAlign = 'right'; g.fillText(location.host, W - 60, 96); g.textAlign = 'left';
  g.fillStyle = v('--line'); g.fillRect(0, 148, W, 2);
  g.fillStyle = v('--ink'); g.font = `600 66px ${FD}`; let y = wrapText(g, p.name, 60, 270, W - 120, 78);
  // An official notice first, with its rule beside it as on the page: a picture in a chat is read as the answer.
  if (p.notice) { const top = y + 44; g.fillStyle = v('--ink'); g.font = `600 34px ${F}`; y = wrapText(g, p.notice, 84, top, W - 144, 44);
    g.fillStyle = v('--notice-line'); g.fillRect(60, top - 32, 6, y - top - 2); }
  // The day it is for, then the answer as the page gives it that day: the live status first where it leads.
  g.fillStyle = v('--muted'); g.font = `600 32px ${F}`; y = wrapText(g, p.when, 60, y + 24, W - 120, 42);
  if (p.lead) { g.fillStyle = v('--ink'); g.font = `700 40px ${F}`; y = wrapText(g, p.lead, 60, y + 28, W - 120, 50) - 30; }
  g.fillStyle = v(`--k-${p.tone}`) || v('--ink'); g.font = `700 60px ${F}`; y = wrapText(g, p.head, 60, y + 40, W - 120, 70);
  if (p.why.length) { g.fillStyle = v('--muted'); g.font = `600 36px ${F}`; y = wrapText(g, p.why.join(' '), 60, y + 6, W - 120, 46); }
  if (p.notes.length) { g.fillStyle = v('--ink'); g.font = `500 30px ${F}`; y = wrapText(g, p.notes.join('. ') + '.', 60, y + 10, W - 120, 40); }
  // The five days: a bar in the level's colour, the day, the level with "risk" under it, and the rain.
  // As many columns as there are days: after midnight, before the next forecast, there are four.
  const cw = (W - 120) / Math.max(1, p.days.length); y += 30;
  p.days.forEach((d, i) => { const lx = 60 + i * cw;
    if (i) { g.fillStyle = v('--line'); g.fillRect(lx, y, 2, 230); }
    g.fillStyle = d.level ? v(`--${d.tone}`) : v('--unknown'); g.fillRect(lx, y, cw, 12);
    g.textAlign = 'center'; g.fillStyle = v('--muted'); g.font = `600 30px ${F}`; g.fillText(d.name, lx + cw / 2, y + 62);
    g.fillStyle = d.level ? v(`--k-${d.tone}`) : v('--muted'); g.font = `700 32px ${F}`; g.fillText(d.word, lx + cw / 2, y + 112);
    if (d.risk) g.fillText(d.risk, lx + cw / 2, y + 150);
    g.fillStyle = v('--muted'); g.font = `600 28px ${F}`; g.fillText(d.rain, lx + cw / 2, y + 200); g.textAlign = 'left'; });
  if (p.days.length) y += 230 + 40;
  g.fillStyle = v('--muted'); g.font = `500 28px ${F}`;
  if (p.caption) y = wrapText(g, p.caption, 60, y, W - 120, 38);
  y = wrapText(g, p.issued, 60, y + 16, W - 120, 38);
  // Cut the canvas to its content, then the place's own page for the day shown along the bottom.
  const out = document.createElement('canvas'); out.width = W; out.height = Math.min(H, Math.max(900, Math.round(y + 120)));
  const o = out.getContext('2d'); o.drawImage(c, 0, 0);
  o.fillStyle = v('--link'); o.font = `700 30px ${F}`; o.fillText(new URL(link({ id: s.id, day }), document.baseURI).href.replace(/^https?:\/\//, ''), 60, out.height - 50);
  const blob = await new Promise(res => out.toBlob(res, 'image/png'));
  if (!blob) throw new Error('the browser would not make the image');
  const file = new File([blob], `swimsignal-${s.id}.png`, { type: 'image/png' });
  if (navigator.canShare && navigator.canShare({ files: [file] })) {
    try { await navigator.share({ files: [file], title: `${s.name} · ${p.brand}` }); }
    catch (e) { if (e.name !== 'AbortError') { saveFile(blob, file.name); toolSaid('The share sheet would not open, so the picture was saved instead.'); } }
  } else { saveFile(blob, file.name); toolSaid('The picture has been saved to your downloads.'); }
}

// ------------------------------------------------------------------------------------------------ one place
const placeDay = s => { const ds = P.dates(DATA); return ds.includes(route.day) ? route.day : ds[0] || today(); };
function kindLine(s) {
  if (s.unlisted) return ['Unlisted point: not hand-checked', s.kind === 'lake' ? 'Lake' : s.kind === 'river' ? 'River' : ''].filter(Boolean).join(' · ');
  const lake = s.kind === 'lake' && !/\b(water|mere|tarn|lake|loch|pond|reservoir|llyn)\b/i.test(s.name + ' ' + (s.river || ''));
  return [s.river, lake ? 'Lake' : '', s.area, s.source === 'designated' ? 'Designated bathing water' : ''].filter(Boolean).join(' · ');
}
function officialHtml(o) {
  return !o ? '' : `<section class="official" aria-labelledby="official-h"><h2 id="official-h">${esc(o.title)}</h2>`
    + o.items.map(i => `<p class="o-line">${esc(i.line)}</p><p class="o-src">${i.link ? `<a href="${esc(i.link)}">Open the ${esc(i.publisher)} page</a>. ` : ''}${esc(i.checked)}</p>`).join('')
    + `<p class="o-first">${esc(o.first)}</p></section>`;
}
function answerHtml(s, day) {
  const a = P.answer(s, day, DATA, now()), o = P.official(s), issued = P.issuedWords(DATA, now()), steps = P.nextSteps(s, day, DATA.spots, miles);
  // The action's first sentence, up to its first full stop or colon, is the bold one. Split without a lookbehind:
  // Safari before 16.4 refuses that pattern, and one refused pattern stops the whole script.
  const act = String(a.act || ''), cut = act.search(/[.:]\s/), first = cut < 0 ? act : act.slice(0, cut + 1), rest = cut < 0 ? '' : act.slice(cut + 2);
  const raised = rank(a.level) >= 1 || !!o;
  const btn = (st, primary) => st.kind === 'nearby' ? `<a class="btn${primary ? ' primary' : ''}" href="#nearby" data-do="jump" data-to="nearby">${esc(st.label)}${IC.down}</a>`
    : st.kind === 'day' ? `<a class="btn${primary ? ' primary' : ''}" href="${link({ id: s.id, day: st.date })}" data-day="${st.date}">${esc(st.label)}</a>`
    : `<p class="act-none">${esc(st.label)}. <a href="#nearby" data-do="jump" data-to="nearby">See what is nearby</a></p>`;
  const unchecked = a.unchecked ? `<p class="unchecked">${esc(a.unchecked.text)} ${a.unchecked.link ? `<a href="${esc(a.unchecked.link)}">${esc(a.unchecked.words)}</a>.` : ''}</p>` : '';
  return `<section class="answer" aria-labelledby="answer-h">
    <p class="when" id="when">${esc(a.dateLabel)}${a.everyDay ? ' <span class="when-note">The level here is the same every day.</span>' : ''}</p>
    ${a.lead ? `<p class="lead">${esc(a.lead)}</p>` : ''}
    <h2 class="level ${a.cls}" id="answer-h">${esc(a.head)}</h2>
    ${a.modelled ? `<p class="why">${esc(a.modelled)}</p>` : ''}
    ${a.why.length ? `<p class="why">${a.why.map(esc).join(' ')}</p>` : ''}
    ${a.clears ? `<p class="why">${esc(a.clears)}</p>` : ''}
    ${a.apart ? `<p class="apart">${esc(a.apart)}</p>` : ''}
    ${raised ? `<div class="act"><p class="act-line"><b>${esc(first)}</b>${rest ? ' ' + esc(rest) : ''}</p>${steps.length ? `<div class="act-go">${steps.map((st, i) => btn(st, i === 0)).join('')}</div>` : ''}${unchecked}</div>`
      : `<p class="act-plain">${esc(a.act)} <a href="#nearby" data-do="jump" data-to="nearby">Compare places nearby</a></p>${unchecked}`}
    ${a.notes.map(t => `<p class="scope">${esc(t)}</p>`).join('')}
    <p class="issued">${esc(issued.text)} · A forecast, not a water test: check the signs at the water.</p>
  </section>`;
}
// The day's conditions at the place: rain, air, daylight and, for today, the water's temperature. Under the answer on
// a phone; under the photo on a wide screen, where they describe the place as the photo does.
function condsHtml(s, day) {
  const a = P.answer(s, day, DATA, now());
  return a.conditions.length ? `<section class="condbox" aria-label="Conditions ${esc(dayWord(day))}"><h2 class="conds-h">Conditions ${esc(dayWord(day))}</h2><dl class="conds">${a.conditions.map(c => `<div><dt>${esc(c.k)}</dt><dd>${esc(c.v)}${c.note ? `<span>${esc(c.note)}</span>` : ''}</dd></div>`).join('')}</dl></section>` : '';
}
function behindHtml(s, day) {
  const L = P.ledger(s, day, DATA, now());
  // The score on its four bands (levels.js, SPILL_CUTS): the band it falls in takes its colour, a mark sits at the
  // score, and on days 3 to 5 a line under the bands gives the range from the other rain runs.
  const meter = (m, c) => { const edges = [0, ...m.cuts, 100], names = ['low', 'moderate', 'high', 'very high'];
    const at = names.findIndex((_, i) => m.score >= edges[i] && (m.score < edges[i + 1] || i === 3));
    return `<span class="meter" aria-hidden="true">${names.map((n, i) => `<i class="seg${i === at ? ' on ' + c : ''}" style="width:${edges[i + 1] - edges[i]}%"></i>`).join('')}<i class="at" style="left:${Math.min(99, Math.max(1, m.score))}%"></i>${m.band ? `<i class="band" style="left:${m.band[0]}%;width:${Math.max(2, m.band[1] - m.band[0])}%"></i>` : ''}</span>
      <span class="meter-key" aria-hidden="true">${names.map((n, i) => `<span style="width:${edges[i + 1] - edges[i]}%">${n}</span>`).join('')}</span>`; };
  // The score on each of the five days, the day shown marked: at a water rated poor every tab reads "High", and this
  // is where the days differ.
  const spark = w => `<span class="spark" role="img" aria-label="${esc('Sewage spill risk by day: ' + w.map(d => `${d.name} ${d.score === null ? 'none' : d.score}`).join(', '))}">${w.map(d =>
    `<span class="sp${d.on ? ' on' : ''}"><i class="${d.cls}" style="height:${d.score === null ? 2 : Math.max(3, Math.round(d.score * 0.56))}px"></i><b>${d.score === null ? '–' : d.score}</b><span>${esc(d.name)}</span></span>`).join('')}</span>`;
  return `<section class="behind" aria-labelledby="behind-h"><h2 id="behind-h">Behind the level</h2>
    <dl class="ledger">${L.map(r => `<div class="lg lg-${r.key}"><dt>${esc(r.label)}</dt>
      <dd>${r.value ? `<span class="lg-value ${r.cls}">${esc(r.value)}${r.word ? `<span class="lg-word"> · ${esc(r.word)} on its own</span>` : ''}</span>` : ''}${r.meter ? meter(r.meter, r.cls) : ''}${r.lines.slice(0, 1).map(t => `<span class="lg-line">${esc(t)}</span>`).join('')}${r.week ? spark(r.week) : ''}${r.lines.slice(1).map(t => `<span class="lg-line dim">${esc(t)}</span>`).join('')}</dd></div>`).join('')}</dl>
    <p class="meta"><a href="methods.html">How the forecast is made</a> · <a href="verification.html">How accurate it has been</a></p></section>`;
}
// The space before a stop on the line, in px, from the water between it and the one before: the square root keeps a
// 30 km gap readable beside a 300 m one.
const gapPx = km => Math.round(Math.min(72, 6 + 16 * Math.sqrt(Math.max(0, km))));
// The spill map (plume.js, the live site's own; docs/PLUME-MAP-2026-10.md): where water from the spills reported
// upstream in the last 48 hours may be, moved at the forecast's travel time, with a slider from 48 hours before the
// update to 48 after. A model estimate, said so on every line. After "Upstream" on a listed place with a daily
// forecast. The script, the map's library and the place's three files (its routes, the replay and the trace) are
// asked for when its place on the page comes within a screen of view, not before. A place with no routes file (a
// lake, or one the build could not place) loses the section quietly. What is drawn is kept and put back when the
// page is drawn again, so the slider stays where it was left.
let plume = null, plumeLib = null;   // plume: { id, el, map }
const plumeWanted = s => !s.unlisted && !!s.detail_file && daily(s);
const plumeGone = () => { if (plume && plume.map) plume.map.remove(); plume = null; };
function mountPlume(s) {
  const slot = document.getElementById('plume-slot'); if (!slot) { plumeGone(); return; }
  if (plume && plume.id === s.id) { slot.replaceWith(plume.el); return; }
  plumeGone();
  // Empty, it takes no room and draws no rule, but is still on the page for the browser to say when it is near.
  const el = document.createElement('div'); el.id = 'plume-host'; el.className = 'spill'; slot.replaceWith(el);
  const mine = plume = { id: s.id, el, map: null };
  const go = () => {
    plumeLib = plumeLib || new Promise((ok, no) => { const sc = document.createElement('script'); sc.src = 'plume.js'; sc.onload = ok; sc.onerror = no; document.head.appendChild(sc); });
    plumeLib.catch(() => { plumeLib = null; });
    const get = p => loadJson(`data/${s.detail_file.replace(/\.json$/, p)}`).catch(() => null);
    Promise.all([plumeLib, window.PVMap.load(), get('-plume.json'), get('-replay.json'), get('-trace.json')]).then(([, , doc, replay, trace]) => {
      if (plume !== mine) return;
      if (!doc || !replay) return;
      const gen = Date.parse((replay.window && replay.window.to) || doc.generated_at);
      window.tiles = window.PVMap.tiles;   // plume.js draws on the page's own tiles where the page has them, by this name
      plumeStyle(document); el.classList.add('on'); el.innerHTML = plumeTile(s, doc, replay, gen, now()); mine.map = plumeBind(el, s, doc, replay, trace, gen);
    }).catch(() => { if (plume === mine) { el.classList.add('on'); el.innerHTML = '<p class="meta">The map of where spill water may be could not be loaded.</p>'; } });
  };
  if (!('IntersectionObserver' in window)) { go(); return; }
  const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { io.disconnect(); go(); } }, { rootMargin: '100% 0px' });
  io.observe(el);
}
function upstreamHtml(s, day) {
  const got = details.get(s.id), head = '<h2 id="upstream-h">Upstream</h2>';
  if (!daily(s)) return `<section class="upstream" id="upstream" aria-labelledby="upstream-h">${head}<p class="sec-lede">${isolated(s) ? 'No river or beck is drawn into this lake, so no monitored overflow can be traced to it.' : 'The trace found no monitored storm overflow on the river network upstream of here.'}</p>
    <ol class="line"><li class="stop is-here"><span class="km"></span><span class="node" aria-hidden="true"></span><span class="stop-body"><b>${esc(s.name)}</b><span class="st">This place.</span></span></li>
    <li class="stop is-end" style="margin-top:28px"><span class="km"></span><span class="node" aria-hidden="true"></span><span class="stop-body"><span class="st">Nothing monitored upstream within ${(s.assumptions || {}).max_upstream_km ?? 60} km. Unmonitored outfalls and runoff are not traced.</span></span></li></ol></section>`;
  if (got === undefined) return `<section class="upstream loading" id="upstream" aria-labelledby="upstream-h">${head}<p class="meta">Reading the overflows upstream…</p></section>`;
  const L = P.riverLine(s, got && got.up, got && got.detail, DATA.spots, now(), day);
  if (!L.items.length) return `<section class="upstream" id="upstream" aria-labelledby="upstream-h">${head}<p class="sec-lede">The list of overflows upstream could not be read just now. Try again in a minute.</p></section>`;
  // A long line is cut after the nearest few: the Avon at Warleigh Weir has 185 overflows upstream. What is left out
  // is counted by its status, and any overflow discharging further up is still drawn, so nothing spilling is hidden.
  const whole = expanded.has(s.id) || L.items.length <= LINE_FIRST + 2;
  const shown = whole ? L.items : L.items.slice(0, LINE_FIRST), rest = whole ? [] : L.items.slice(LINE_FIRST);
  const restO = rest.filter(i => i.kind === 'overflow'), count = m => restO.filter(i => i.mark === m).length;
  let prev = 0;
  const item = (it, tail = false) => { const gap = it.km - prev; prev = it.km; const mt = tail ? 16 : gapPx(gap);
    if (it.kind === 'place') return `<li class="stop is-place" style="margin-top:${mt}px"><span class="km">${esc(it.kmSaid)}</span><span class="node" aria-hidden="true"></span><span class="stop-body"><a href="${link({ id: it.id, day })}"><b>${esc(it.name)}</b></a><span class="st">Another listed place. <span class="${it.cls}">${esc(it.level)}</span> ${esc(dayWord(day))}.</span></span></li>`;
    const more = [it.company + (it.own ? `, as “${it.own}”` : ''), it.into ? `Into ${it.into}` : '', capFirst(it.where),
      it.spills === null ? '' : `${num(it.spills, 1)} spills a year, long-term average`, it.hours === null ? '' : `${num(it.hours, 1)} hours spilling in its latest annual return`,
      it.weight === null ? '' : `Model weight here: ${Math.round(it.weight * 100)}%`, it.upgrade && it.upgrade.stage ? `Upgrade: ${it.upgrade.stage}, by the company's own page` : ''].filter(Boolean);
    return `<li class="stop is-${it.mark}" style="margin-top:${mt}px"><span class="km">${esc(it.kmSaid)}</span><span class="node" aria-hidden="true"></span><span class="stop-body">
      <b>${esc(it.name)}</b><span class="st">${esc(capFirst(it.status))}${it.ended ? `. Last spill ended ${esc(it.ended)}` : ''}.${it.long ? ' ' + esc(it.long) : ''}</span>
      <span class="st st-row">${it.chance === null ? '' : `<span>Chance of a spill ${esc(dayWord(day))}: ${it.chance < 0.01 ? 'under 1' : Math.round(it.chance * 100)}%</span>`}<button type="button" class="textbtn" data-do="more" aria-expanded="false" aria-label="Details of ${esc(it.name)}">Details</button></span><span class="more-box" hidden>${more.map(esc).join('<br>')}<br><a href="overflow/${encodeURIComponent(it.id)}/">This overflow's record</a></span></span></li>`; };
  const below = L.below.length ? `<p class="below">Downstream of here: ${L.below.map(b => `<a href="${link({ id: b.id, day })}">${esc(b.name)}</a> <span class="meta">${num(b.km, 1)} km, ${esc(b.level.toLowerCase())} ${esc(dayWord(day))}</span>`).join('; ')}.</p>` : '';
  const counts = [L.spilling ? `<b class="lv-veryhigh">${L.spilling} discharging now</b>` : 'none discharging now', `${L.quiet} not discharging at the last poll`, L.unknown ? `${L.unknown} with no current reading` : ''].filter(Boolean).join(', ');
  const lede = `<p class="sec-lede">${L.total === 1 ? 'One monitored storm overflow' : `${L.total} monitored storm overflows`} within ${L.reach} km upstream: ${counts}.${L.more ? ' ' + esc(L.more) : ''}</p>
    <p class="chips" role="group" aria-label="How the water upstream is shown">${[['line', 'As a line'], ['map', 'On a map']].map(([k, w]) => `<button type="button" class="chip${upView === k ? ' on' : ''}" data-do="up" data-up="${k}" aria-pressed="${upView === k}">${w}</button>`).join('')}</p>`;
  const key = `<p class="key"><span class="k is-spilling"><i></i>discharging</span><span class="k is-quiet"><i></i>not discharging at the last poll</span><span class="k is-unknown"><i></i>no current reading</span>${upView === 'map' ? '<span class="k is-water"><i></i>the water that reaches this place</span>' : ''}</p>`;
  const note = `<p class="meta">A monitor reports when an overflow spills, not how much or what is in it. Live readings are from the last poll${P.pollAt(DATA) ? ` (${esc(P.pollAt(DATA))})` : ''}, whichever day is shown.</p>`;
  if (upView === 'map') return `<section class="upstream" id="upstream" aria-labelledby="upstream-h">${head}${lede}
    <div class="map-slot place-map" id="up-map"><p class="meta map-wait">Reading the map…</p></div>
    ${key}<p class="meta">${TOUCH ? 'Tap' : 'Click'} an overflow for its name and what it is doing. Each one is listed under As a line, with its distance upstream.</p>${below}${note}</section>`;
  return `<section class="upstream" id="upstream" aria-labelledby="upstream-h">${head}${lede}
    <ol class="line" aria-label="The water upstream of here, nearest first">
      <li class="stop is-here"><span class="km"></span><span class="node" aria-hidden="true"></span><span class="stop-body"><b>${esc(s.name)}</b><span class="st">This place. Each step down the line is further upstream.</span></span></li>
      ${shown.map(it => item(it)).join('')}
      ${rest.length ? `<li class="stop is-rest" style="margin-top:20px"><span class="km"></span><span class="node" aria-hidden="true"></span><span class="stop-body"><b>${restO.length} more further upstream</b><span class="st">${[count('spilling') ? `${count('spilling')} discharging, drawn below` : '', count('quiet') ? `${count('quiet')} not discharging at the last poll` : '', count('unknown') ? `${count('unknown')} with no current reading` : ''].filter(Boolean).join('; ')}.</span><button type="button" class="textbtn" data-do="all">Show all ${L.total}</button></span></li>` : ''}
      ${rest.filter(i => i.mark === 'spilling').map(it => item(it, true)).join('')}
      <li class="stop is-end" style="margin-top:20px"><span class="km">${L.reach} km</span><span class="node" aria-hidden="true"></span><span class="stop-body"><span class="st">The trace stops here. Overflows further up are not counted.</span></span></li>
    </ol>
    ${key}
    ${below}
    ${note}</section>`;
}
// The place's map: the water the forecast traced upstream (data/spot/<id>-trace.json, asked for when the map is first
// opened) and the overflows on it, with the line's own marks. It is drawn again when the trace arrives.
function mountPlaceMap() {
  const s = spotOf(route.id), slot = document.getElementById('up-map'), got = s && details.get(s.id); if (!slot || !got) return;
  if (!traces.has(s.id)) { traces.set(s.id, undefined);
    (s.detail_file && !isolated(s) ? loadJson(`data/${s.detail_file.replace(/\.json$/, '-trace.json')}`) : Promise.resolve(null))
      .then(j => j && j.id === s.id && Array.isArray(j.lines) ? j.lines.map(P.decodeLine) : null).catch(() => null)
      .then(lines => { traces.set(s.id, lines); if (route.id === s.id && upView === 'map') mountPlaceMap(); }); }
  const day = placeDay(s), L = P.riverLine(s, got.up, got.detail, DATA.spots, now(), day);
  window.PVMap.place(slot, { id: s.id, name: s.name, lat: s.lat, lon: s.lon, cls: P.cls(dayLevel(s, day)), advised: !!P.official(s) }, P.overflowPoints(L.items, got.up), traces.get(s.id) || null)
    .then(() => { const w = slot.querySelector('.map-wait'); if (w) w.remove(); })
    .catch(() => { slot.innerHTML = '<p class="none">The map could not be read just now. The overflows are listed under As a line.</p>'; });
}
function nearbyHtml(s, day) {
  const from = here || s, E = P.elsewhere(DATA.spots, from, day, miles, here ? null : s.id, dayLevel(s, day)), when = dayWord(day);
  const group = (title, list, note = '') => list.length ? `<h3>${esc(title)}</h3>${note ? `<p class="meta">${esc(note)}</p>` : ''}${rows(list, day)}` : '';
  const chip = m => `<button type="button" class="chip${miles === m ? ' on' : ''}" data-do="miles" data-miles="${m}" aria-pressed="${miles === m}">${m} miles</button>`;
  return `<section class="nearby" id="nearby" aria-labelledby="nearby-h"><h2 id="nearby-h" tabindex="-1">Elsewhere ${esc(when)}</h2>
    <p class="sec-lede">${E.widened ? 'The nearest listed places to' : `Listed places within ${E.miles} miles of`} ${here ? 'where you are' : esc(s.name)}, ${esc(day === today() ? 'today' : P.longDate(day))}.</p>
    <p class="chips" role="group" aria-label="How far">${[10, 20, 40].map(chip).join('')}
      ${here ? '<button type="button" class="textbtn" data-do="unlocate">Measure from this place</button>' : `<button type="button" class="textbtn" data-do="locate">${IC.pin}From where I am</button>`}</p>
    ${group(`Low risk ${when}, nearest first`, E.low) || `<p class="none">No listed place ${E.widened ? 'nearby' : `within ${E.miles} miles`} is forecast at low risk ${esc(when)}.</p>`}
    ${E.lowerThan ? group(`Moderate risk ${when}: lower than here`, E.moderate) : ''}
    ${group('No daily level', E.plain, 'No monitored overflow was found upstream of these. That is not the same as low risk.')}
    ${group('Under official advice', E.advice, 'Follow the advice first, whatever the level beside it.')}
    ${E.folded.length ? `<details class="raised"><summary>${E.folded.length === 1 ? 'One place' : `${E.folded.length} places`} ${E.lowerThan ? 'at high or very high risk' : 'at moderate risk or higher'} ${esc(when)}</summary>${rows(E.folded, day)}</details>` : ''}
    <p class="meta">Miles in a straight line. Low risk is the forecast for sewage pollution, not a safety check. <a href="${planLink(day, { from: { name: s.name.slice(0, 80), lat: Math.round(s.lat * 1e4) / 1e4, lon: Math.round(s.lon * 1e4) / 1e4 } })}">Plan a swim from here</a></p></section>`;
}
const TOPICS = { parking: 'Parking', transport: 'Bus and train', path: 'Path to the water', entry: 'Getting in', exit: 'Getting out', toilets: 'Toilets', changing: 'Changing',
  fees: 'Fees and booking', hours: 'Opening times', rules: 'Who can swim', launch: 'Launching a boat or board', carry: 'Carrying to the water', paddle: 'Paddling here' };
// For someone taking a group in, and for telling Ethan: the live page's two lines under a place's buttons, in its
// words. The event page, the clubs' tools and the decision record are pages of their own (organisers.html, clubs.html,
// record.html), and each reads its place, and the record its day, from after the #. The record is for the day shown,
// where the live page has a link under each day. Not for a point tapped on the map, which those pages cannot open.
const groupLinks = s => { if (s.unlisted) return ''; const id = encodeURIComponent(s.id), day = placeDay(s);
  return `<p class="meta">Taking a group in the water here, or running an event? <a href="organisers.html#spot=${id}">The event page</a>, with the overflows upstream, a checklist and signs; <a href="clubs.html">tools for clubs and centres</a>; and <a href="record.html#spot=${id}&amp;day=${esc(day)}">a decision record for ${esc(dayName(day))}</a> to print.</p>
    <p class="meta">Did the forecast change where or when you swam? <a href="feedback.html?type=feedback&amp;spot=${encodeURIComponent(s.name)}">Tell&nbsp;Ethan</a>.</p>`; };
function placeFactsHtml(s) {
  const got = details.get(s.id), g = got && got.detail ? got.detail.guide : null, hero = photoOf(s.id), facts = [], guide = [];
  const c = s.classification;
  if (c && c.class) { const poor = String(c.class).toLowerCase() === 'poor';
    facts.push(['Rating', `Rated <b>${esc(String(c.class).toLowerCase())}</b> for ${esc(c.year)} by the Environment Agency. ${poor ? esc(poorAdvice(today())) + ' ' : ''}${P.httpsLink(c.url) ? `<a href="${esc(c.url)}">Its Environment Agency page</a>` : ''}`]); }
  else if (s.sepa && s.sepa.rating) facts.push(['Rating', `Rated <b>${esc(String(s.sepa.rating.value).toLowerCase())}</b> for ${esc(s.sepa.rating.year)} by SEPA. ${P.httpsLink(s.sepa.page) ? `<a href="${esc(s.sepa.page)}">Its SEPA page</a>` : ''}`]);
  const ls = s.lab_sample;
  if (ls && ls.taken_at && !P.isNil(ls.ecoli)) facts.push(['Last sample', `${esc(ls.qualifier || '')}${num(ls.ecoli)} E. coli per 100 ml on ${esc(P.shortDate(String(ls.taken_at).slice(0, 10)))}, by the Environment Agency. The line for a rating of sufficient is 900.`
    + (s.ecoli_typical ? ` Of ${s.ecoli_typical.samples} samples from ${s.ecoli_typical.first_year} to ${s.ecoli_typical.last_year}, ${s.ecoli_typical.over_line} were over it.` : '')]);
  if (s.algae && s.algae.date && s.algae.phrase) facts.push(['Algae', `At the Environment Agency's last check, ${esc(P.shortDate(s.algae.date))}: ${esc(s.algae.phrase)}. The check cannot tell blue-green algae from harmless kinds.`]);
  const rs = s.river_state;
  if (rs && !P.isNil(rs.level_m) && !rs.stale) { const word = ({ low: 'low water', normal: 'its usual level', high: 'high water', 'very high': 'very high water, above its usual range' })[rs.label];
    facts.push([rs.water === 'lake' ? 'Lake level' : 'River level', `${num(rs.level_m, 2)} m${word ? `, ${word}` : ''}. Gauge at ${esc(rs.station)}, ${esc(rs.distance_km)} km away${rs.same_river === false ? ', on a different watercourse' : ''}. Not part of the level.`]); }
  for (const f of s.flood_alerts || []) facts.push([esc(f.severity || 'Flood alert'), `${esc(f.area || '')}, from the Environment Agency. ${P.httpsLink(f.url) ? `<a href="${esc(f.url)}">Read it</a>` : ''}`]);
  if (s.access && s.access.text) facts.push(['Access', `${esc(s.access.text)} ${P.httpsLink(s.access.url) ? `<a href="${esc(s.access.url)}">Source</a>` : ''}`]);
  for (const f of (g && g.facts) || []) guide.push([TOPICS[f.topic] || esc(capFirst(f.topic)), `${esc(f.text)} ${f.status === 'confirmed' ? (P.httpsLink(f.source) ? `<a href="${esc(f.source)}">${esc(f.source_name || 'Source')}</a>` : esc(f.source_name || '')) : 'A swimmer’s suggestion, not checked.'}`]);
  const merge = list => { const out = []; for (const [k, v] of list) { const last = out[out.length - 1]; if (last && last[0] === k) last[1].push(v); else out.push([k, [v]]); } return out; };
  const dl = list => `<dl class="facts">${merge(list).map(([k, vs]) => `<div><dt>${k}</dt>${vs.map(v => `<dd>${v}</dd>`).join('')}</div>`).join('')}</dl>`;
  const photos = (g && Array.isArray(g.photos) ? g.photos : []).filter(p => !hero || p.file !== hero.file);
  return `<section class="theplace" id="place" aria-labelledby="place-h"><h2 id="place-h">The place</h2>
    ${got === undefined ? '<p class="meta">Reading what is known about this place…</p>' : ''}
    ${facts.length ? dl(facts) : got === undefined ? '' : '<p class="sec-lede">No rating, sample or gauge is recorded for this place.</p>'}
    ${guide.length ? `<details class="guide"><summary>Getting there and getting in: ${guide.length} checked notes</summary>${dl(guide)}${g.checked ? `<p class="meta">Checked on ${esc(P.shortDate(g.checked))}${g.how === 'desk' ? ', from published sources, not on a visit' : ''}.</p>` : ''}</details>` : ''}
    ${photos.length ? `<div class="photos">${photos.map(p => `<figure><img src="guides/photos/${encodeURIComponent(p.file)}" width="${Number(p.w) || 640}" height="${Number(p.h) || 480}" alt="${esc(p.caption || s.name)}" loading="lazy" decoding="async"><figcaption>${esc(p.caption || '')} ${credit({ ...p, licence_name: p.licence && /by-sa\/2\.0/.test(p.licence) ? 'CC BY-SA 2.0' : '' })}</figcaption></figure>`).join('')}</div>` : ''}
    <p class="meta">${esc(s.source === 'openstreetmap' ? 'This place is from OpenStreetMap, © OpenStreetMap contributors.' : String(s.notes || '').replace(/([^.])$/, '$1.'))} A listing is not a right to swim or a check that it is allowed. <a href="${classic(`spot/${encodeURIComponent(s.id)}/`)}">This place on ${OLD}</a></p>
    ${groupLinks(s)}</section>`;
}
// A point's request to be listed, as the live page's (anypoint.js, request): a GitHub form with its position filled in.
function requestHtml(s) {
  const q = new URLSearchParams({ template: 'spot-request.yml', title: `Spot request: ${s.name}`, name: s.name, location: `${s.lat.toFixed(5)}, ${s.lon.toFixed(5)}`, kind: s.kind === 'lake' ? 'lake' : 'river' });
  return `<p><a class="btn" href="https://github.com/ethanbuckley/swimsignal/issues/new?${esc(q.toString())}" rel="noopener">Request this as a spot</a></p>
    <p class="meta">Opens a request on GitHub with this point's position filled in. A listed spot is checked by hand and gets its own rain forecast and E.&nbsp;coli estimate.</p>`;
}
// A point with no forecast: outside England, off the river network, or an isolated lake. Its reason in the live
// script's own words, the official source for where it is, and the listed places near it.
function pointNoneHtml(s, day) {
  const see = s.outside && typeof AnyPoint === 'object' && (AnyPoint.OUTSIDE[s.outside] || {}).see;
  return `${bar(true)}<main id="main" class="place">
    <div class="top"><div class="tools"><a class="tool" href="${link({ view: 'map', day })}">${IC.back}<span>Map</span></a></div>
      <div class="head"><h1 id="title" tabindex="-1">${esc(s.name || 'This point')}</h1><p class="kind">${esc(kindLine(s))}</p></div>
      <div class="first"><section class="answer"><h2 class="level lv-none" id="answer-h">No forecast here</h2><p class="why">${esc(s.error)}</p>
        ${see ? `<p class="why">${see}</p>` : ''}<p class="issued">A forecast, not a water test: check the signs at the water before you swim.</p></section></div></div>
    <div class="more">${nearbyHtml(s, day)}</div>
    ${s.location && s.location.mode === 'isolated' ? `<section class="theplace">${requestHtml(s)}</section>` : ''}
    ${foot()}
  </main>${tabbar()}`;
}
function placeHtml() {
  const s = spotOf(route.id), pt = route.point ? POINTS.get(route.id) : null;
  if (!s && route.point) return `${bar(true)}<main id="main" class="home"><section class="opening"><p class="backline"><a href="${link({ view: 'map', day: route.day })}">${IC.back}Map</a></p>
    <h1 id="title" tabindex="-1">${pt && pt.failed ? 'No forecast could be made' : 'Working out the forecast'}</h1>
    <p class="lede" role="status">${pt && pt.failed ? `Could not make a forecast for this point: ${esc(pt.failed)}.` : 'For the point you picked on the map…'}</p></section>${foot()}</main>${tabbar()}`;
  if (s && s.unlisted && s.error) return pointNoneHtml(s, placeDay(s));
  if (!s) return `${bar(true)}<main id="main" class="home"><section class="opening"><h1 id="title" tabindex="-1">That place is not listed</h1><p class="lede">The link names a place this forecast does not cover, or one that has been removed.</p><p><a class="btn primary" href="${HOME || './'}">Find a place</a></p></section>${foot()}</main>${tabbar()}`;
  const day = placeDay(s), hero = photoOf(s.id), isKept = shownList(LISTS).spots.includes(s.id), o = P.official(s);
  const missed = route.day && route.day !== day ? `<p class="notice" role="note"><b>This link was for ${esc(P.longDate(route.day))}.</b> That day is no longer in the forecast, so this shows today.</p>` : '';
  const tools = `<div class="tools"><a class="tool" href="${s.unlisted ? link({ view: 'map', day }) : link({ day })}">${IC.back}<span>${s.unlisted ? 'Map' : 'All places'}</span></a><span class="tools-r">${s.unlisted ? '' : `<button type="button" class="tool" data-do="keep" aria-pressed="${isKept}">${IC.save}<span>${isKept ? 'Saved' : 'Save'}</span></button>`}<button type="button" class="tool" data-do="share" aria-label="Share this forecast">${IC.share}</button></span></div>`;
  return `${bar(true)}<main id="main" class="place${hero ? ' has-photo' : ''}">
    <div class="top">
      ${hero ? `<figure class="hero"><img src="guides/photos/${encodeURIComponent(hero.file)}" width="${hero.w}" height="${hero.h}" alt="${esc(String(hero.caption || s.name).replace(/[.\s]+$/, ''))}." decoding="async" fetchpriority="high">${tools}<figcaption>${credit(hero)}</figcaption></figure>` : tools}
      <div class="head"><h1 id="title" tabindex="-1">${esc(s.name)}</h1><p class="kind">${esc(kindLine(s))}</p><p class="meta" id="tool-said" role="status"></p></div>
      <div class="first">${stale()}${missed}${officialHtml(o)}
        <i class="tabs-top" aria-hidden="true"></i>${dayTabsHtml(P.dayTabs(s, DATA), day, 'Day', d => link({ id: s.id, day: d }))}
        ${answerHtml(s, day)}${canPlanHere(s) || !s.unlisted ? `<p class="planhere">${canPlanHere(s) ? `<a class="btn" href="${esc(planHereLink(s, day))}" data-plan-new>${esc(planHereWords())}</a>` : ''}${
          s.unlisted ? '' : '<button type="button" class="btn" data-do="share-picture">Share as a picture</button>'}</p>` : ''}</div>
      ${condsHtml(s, day)}
    </div>
    <div class="more">${behindHtml(s, day)}${upstreamHtml(s, day)}${plumeWanted(s) ? '<div id="plume-slot"></div>' : ''}${nearbyHtml(s, day)}</div>
    ${recordHtml(s)}
    ${s.unlisted ? `<section class="theplace" aria-labelledby="place-h"><h2 id="place-h">This point</h2><p class="sec-lede">Not one of the listed places: nobody has checked it by hand, and it has no rain forecast of its own and no E.&nbsp;coli estimate.${s.rain_km ? ` Rain is from the forecast for the area next to this point's, about ${esc(s.rain_km)} km away.` : ''}</p>${requestHtml(s)}</section>` : placeFactsHtml(s)}
    ${logHtml(s)}
    ${swimmersHtml(s)}
    ${foot()}
  </main>${tabbar()}`;
}
// The record here: what the level rests on (evidence.js: each item's age and source, and the gaps), how the forecast
// has done at the overflows upstream since live scoring began (spotscores.js), on how many days of each month a spill
// was reported upstream (seasonal.js), lab results an organisation sent (measured.js), and everything dated the site
// holds about the water here (timeline.js, read when its fold is opened). Sources and history, not a forecast, and
// none of it changes with the day picked. Each is the live site's own script giving its part as markup, from the
// place's own file and data/spot_scores.json. What is drawn is kept and put back when the page is drawn again, so a
// fold opened stays open. For a listed place; a point tapped on the map has no record.
let rec = null, SCORES = null, scoresAsked = false, scoresRead = false;   // rec: { key, el }
const recordHtml = s => typeof evidenceTile !== 'function' || s.unlisted ? ''
  : `<section class="record" id="record" aria-labelledby="record-h"><h2 id="record-h">The record here</h2>
    <p class="sec-lede">What the level rests on, and what has happened here before. Sources and history, not a forecast: it does not change with the day picked.</p><div id="record-slot"></div></section>`;
function mountRecord(s) {
  const slot = document.getElementById('record-slot') || document.getElementById('record-body'); if (!slot) return;
  const wanted = typeof scoresWanted === 'function' && scoresWanted(s);
  if (wanted && !scoresAsked) { scoresAsked = true;
    scoresLoad().then(d => { SCORES = d || null; scoresRead = true; const now = route && route.id && spotOf(route.id); if (now) mountRecord(now); }); }
  const got = details.get(s.id), key = `${s.id}|${got ? 1 : 0}|${!wanted || scoresRead ? 1 : 0}`;
  if (rec && rec.key === key) { if (slot !== rec.el) slot.replaceWith(rec.el); return; }
  const open = rec && rec.el.isConnected ? [...rec.el.querySelectorAll('details[open]')].map(d => d.id || d.className) : [];
  const el = document.createElement('div'); el.id = 'record-body';
  // The place as its own file fills it out: the overflows that count most, its samples and its monthly history.
  const full = got ? { ...s, ...(got.detail || {}) } : null, at = now();
  const parts = !full ? ['<p class="meta">Reading the record…</p>'] : [evidenceTile(full, at, DATA.generated_at),
    typeof measuredTile === 'function' ? measuredTile(full, at) : '',
    !wanted ? '' : !scoresRead ? '<p class="meta">Reading how the forecast has done here…</p>' : scoresTile(s, SCORES),
    typeof seasonalTile === 'function' ? seasonalTile(full) : '', typeof timelineTile === 'function' ? timelineTile(full) : ''];
  el.innerHTML = parts.join('') || '<p class="meta">Nothing is recorded for this place yet.</p>';
  el.querySelectorAll('details').forEach(d => { if (open.includes(d.id || d.className)) d.open = true; });
  slot.replaceWith(el); rec = { key, el };
}

// Your swims: the swim journal (journal.js), a swimmer's own record, kept on this device and sent nowhere. On a
// place's page it is one button, "Log a swim", whose form opens under it and keeps what the forecast showed. The
// live script binds the button and draws the form; it looks for them by the live page's names (#swam, .actions,
// #swam-msg). Kept and put back when the page is drawn again, as the reviews are, so a form half written stays.
let jlog = null;   // { id, el }
const logHtml = s => typeof journalLogBind !== 'function' || !reviewable(s) ? ''
  : `<section class="yourswims" id="yourswims" aria-labelledby="yourswims-h"><h2 id="yourswims-h">Your swims</h2>
    <p class="sec-lede">A private journal: where and when you swam, and what the forecast showed. Kept on this device only.</p><div id="log-slot"></div></section>`;
function mountLog(s) {
  const slot = document.getElementById('log-slot'); if (!slot) return;
  if (jlog && jlog.id === s.id) { slot.replaceWith(jlog.el); return; }
  const el = document.createElement('div'); el.id = 'log-body';
  el.innerHTML = `<div class="actions"><button type="button" class="btn" id="swam" aria-expanded="false">Log a swim</button></div><p class="meta" id="swam-msg" role="status" aria-live="polite"></p>`;
  slot.replaceWith(el); jlog = { id: s.id, el };
  journalLogBind(s, DATA.generated_at);
}
// On Saved: the journal itself and the passport made from it (passport.js), each drawn and redrawn by its own
// script. One element holds both and is put back when the page is drawn again.
let jsaved = null;
const journalHtml = () => typeof journalCard !== 'function' ? '' : '<div id="journal-slot"></div>';
function mountJournal() {
  const slot = document.getElementById('journal-slot'); if (!slot) return;
  if (jsaved) { slot.replaceWith(jsaved); return; }
  const el = document.createElement('div'); el.id = 'journal-body';
  el.innerHTML = journalCard() + (typeof passportSection === 'function' ? passportSection(DATA.spots) : '');
  slot.replaceWith(el); jsaved = el;
  journalBindSection(); if (typeof passportBind === 'function') passportBind();
}

// From swimmers: notes on a visit, reviews and reports of illness, each the live site's own script (visits.js,
// reviews.js, illness.js), which draws its own part and takes what a swimmer sends. They look for the place they
// draw into by the live page's names (#result .stack .tiles), so the slot here is given those. What they have drawn
// is kept and put back each time the page is drawn again (a day picked, the place's file arriving), so a form half
// written is not lost. Nothing is here until their list has been read; nothing at all if reviews are off.
let swim = null;   // { id, el }: what the three have drawn for the place open
const swimmersHtml = s => typeof mountReviews !== 'function' || !reviewable(s) ? ''
  : `<section class="swimmers" id="swimmers" aria-labelledby="swimmers-h"><h2 id="swimmers-h">From swimmers</h2>
    <p class="sec-lede">What people who have been here say. One person's day, not a water test: it does not change the forecast.</p><div id="swimmers-slot"></div></section>`;
function mountSwimmers(s) {
  const slot = document.getElementById('swimmers-slot'); if (!slot) return;
  if (swim && swim.id === s.id) { slot.replaceWith(swim.el); return; }
  const el = document.createElement('div'); el.id = 'result';
  el.innerHTML = '<div class="stack"><div class="tiles" hidden></div><p class="meta swim-wait">Reading what swimmers have sent…</p></div>';
  slot.replaceWith(el); swim = { id: s.id, el };
  // Each draws only if another place has not been opened since (their own check), and removes nothing of ours.
  const done = () => { const w = el.querySelector('.swim-wait'); if (w) w.remove(); if (!el.querySelector('.rv-tile')) el.insertAdjacentHTML('beforeend', '<p class="meta">Reviews and notes are not being taken just now.</p>'); };
  Promise.resolve(typeof reviewsLoad === 'function' ? reviewsLoad() : null).then(() => {
    mountReviews(s); if (typeof mountVisits === 'function') mountVisits(s); if (typeof mountIllness === 'function') mountIllness(s);
    setTimeout(done, 400); });
}

// ------------------------------------------------------------------------------------------------ drawing and events
let lastKey = '';
// Draw the screen for the address. Focus is kept on the control that was used (a day's tab, a distance), found
// again by what it does, so a keyboard stays where it was; a new screen puts focus on its heading.
function draw(opts = {}) {
  route = P.parseAddress(location.pathname, location.search, BASE, location.hash);
  // A link from before places had addresses ("?spot=<id>"): the same place, at its address.
  if (route.screen === 'place' && !route.point && !location.pathname.startsWith(BASE + 'spot/')) history.replaceState(null, '', link(route) + location.hash);
  // A day that came after the # (the live page's form) is put where these pages keep it, so a day picked next is not undone by it.
  if (route.screen === 'place' && /^#day=/.test(location.hash)) history.replaceState(null, '', link(route));
  // A point on the map: worked out once, by the live site's own arithmetic, then drawn as a place is.
  if (route.point && !POINTS.has(route.id) && typeof AnyPoint === 'object') { const id = route.id; POINTS.set(id, undefined);
    AnyPoint.point(route.point[0], route.point[1]).then(d => { P.prepareOne(d, DATA, now()); d.id = id; POINTS.set(id, d);
      details.set(id, { detail: { contributors: d.contributors || [] }, up: null }); })
      .catch(e => { POINTS.set(id, { failed: (e && e.message) || 'the files could not be read' }); })
      .then(() => { if (route && route.id === id) draw({ focus: true }); }); }
  if (route.screen === 'place' && spotOf(route.id) && !details.has(route.id)) loadDetail(route.id);
  if (route.screen === 'find' && route.q) nearWords(route.q);
  // A plan's day is the plan's own, from its address or the plan kept in this browser.
  if (route.view === 'plan') { PLAN = readPlan(location.hash, dates(), keptPlan()); route.day = PLAN.day; planArrived(); }
  else { PLAN = null; planTyped = null; planPreview = planFresh = planNew = false; planOff = planSeen = null; }
  if (route.view !== 'saved') listForm = null;
  const y = window.scrollY, key = route.screen === 'place' ? `place/${route.id}` : `find/${route.view || ''}/${route.area || ''}`;
  const active = document.activeElement, ds = active && active !== document.body && app.contains(active) ? active.dataset : null;
  const pick = ds && ['up', 'list', 'within', 'kind', 'miles', 'id'].find(k => ds[k] !== undefined);
  const sel = !ds ? '' : ds.day ? `.daytabs [data-day="${ds.day}"]` : pick ? `[data-do="${ds.do}"][data-${pick}="${ds[pick]}"]` : ds.do ? `[data-do="${ds.do}"]` : active.id ? `#${active.id}` : '';
  const caret = active && (active.id === 'q' || active.id === 'from') ? active.selectionStart : null;
  app.innerHTML = route.screen === 'find' ? homeHtml() : placeHtml();
  const s = route.screen === 'place' ? spotOf(route.id) : null;
  document.title = `${s ? s.name : ({ map: 'Map', plan: 'Plan a swim', saved: 'Saved' })[route.view] || 'Where do you swim?'} · SwimSignal${PREVIEW ? ' preview' : ''}`;
  if (route.view === 'map') mountHomeMap();
  if (route.screen === 'find' && !route.view) researchLine();
  if (s && upView === 'map') mountPlaceMap();
  // since.js: these places' levels are on screen, with no other day picked, so the note of what they showed is kept.
  if (typeof lookedAt === 'function') { const saved = new Set(savedIds());
    if (s && placeDay(s) === today()) lookedAt([s], DATA.generated_at, saved);
    else if (route.view === 'saved' && homeDay() === today() && !readShared(location.hash, dates())) lookedAt(shownList(LISTS).spots.map(spotOf).filter(Boolean), DATA.generated_at, saved); }
  if (s) { const typing = swim && swim.id === s.id && active && swim.el.contains(active) ? active : null;
    const writing = jlog && jlog.id === s.id && active && jlog.el.contains(active) ? active : null;
    mountPlume(s); mountRecord(s); mountLog(s); mountSwimmers(s); if (typing || writing) (typing || writing).focus({ preventScroll: true }); } else { swim = null; rec = null; jlog = null; plumeGone(); }
  if (route.view === 'saved' && !readShared(location.hash, dates())) { mountJournal(); mountCompare(); } else jsaved = null;
  if (route.view === 'plan') mountOuting();
  // Whether alerts are on is the browser's to say, and it answers a moment after the page is drawn.
  if (route.view === 'saved' && DATA.push && alertsOn === null && window.PVAlerts.can() === 'yes') window.PVAlerts.isOn().catch(() => false).then(on => { alertsOn = on; redrawAlerts(); });
  if (key !== lastKey) {
    window.scrollTo(0, opts.y || 0);
    if (location.hash === '#find') { const q = document.getElementById('q'); if (q) q.focus(); }
    else if (opts.focus) { const h = app.querySelector(route.area ? '.area-h' : 'h1'); if (h) h.focus({ preventScroll: true }); }
  } else {
    window.scrollTo(0, y);
    const again = sel && app.querySelector(sel);
    if (again) { again.focus({ preventScroll: true }); if (caret !== null && again.setSelectionRange) again.setSelectionRange(caret, caret); }
  }
  // "Your journal", from a swim just logged or from a link (saved/#journal): the journal, not the top of Saved.
  if (key !== lastKey && route.view === 'saved' && location.hash === '#journal' && typeof journalFocus === 'function') journalFocus();
  lastKey = key;
  watchTabs();
}
// On a phone the day tabs stay at the top of the screen for the whole page, so the date shown is always in view.
// Once they have left their own place they drop the level word and keep the day and its mark.
let tabsSeen = null;
function watchTabs() {
  if (tabsSeen) tabsSeen.disconnect();
  const mark = app.querySelector('.tabs-top'), tabs = app.querySelector('.place .daytabs');
  if (!mark || !tabs || !('IntersectionObserver' in window)) return;
  tabsSeen = new IntersectionObserver(([e]) => tabs.classList.toggle('stuck', !e.isIntersecting && e.boundingClientRect.top < 0));
  tabsSeen.observe(mark);
}
async function loadDetail(id) {
  const s = spotOf(id); if (!s) return;
  details.set(id, undefined);
  const get = p => loadJson(p).catch(() => null);
  const [detail, up] = await Promise.all([s.detail_file ? get(`data/${s.detail_file}`) : null, daily(s) ? get(`data/upstream/${encodeURIComponent(id)}.json`) : null]);
  details.set(id, { detail, up: up && Array.isArray(up.overflows) ? up.overflows : null });
  if (route && route.id === id) draw();
}
function setDay(d) {
  if (route.view === 'plan') { planSet({ day: d }); say(`The plan now shows ${P.headDay(d) === 'today' ? 'today' : P.longDate(d)}.`); return; }
  const r = { ...route, day: d }; history.replaceState(null, '', link(r) + (!route.point && location.hash && location.hash !== '#find' ? location.hash : '')); draw();
  const s = route.id && spotOf(route.id);
  say(s ? `${P.dayTabs(s, DATA).find(t => t.date === d).said}. The page now shows ${P.headDay(d) === 'today' ? 'today' : P.longDate(d)}.` : `Levels shown for ${P.headDay(d) === 'today' ? 'today' : P.longDate(d)}.`);
}
function jump(id) { const el = document.getElementById(id); if (!el) return;
  const h = el.querySelector('h2') || el; el.scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); h.focus({ preventScroll: true }); }

app.addEventListener('input', e => { if (e.target.id === 'q') typed(e.target.value); else if (e.target.id === 'from') planTyping(e.target.value); });
document.addEventListener('toggle', e => { if (e.target && e.target.classList && e.target.classList.contains('cmp-choose')) cmpOpen = e.target.open; }, true);
app.addEventListener('change', async e => {
  if (e.target.id === 'plan-within') { planSet({ within: Number(e.target.value) || 0 }); return; }
  if (e.target.id === 'plan-kind') { planSet({ kind: e.target.value }); return; }
  if (e.target.dataset.cmp) { cmpIds = comparisonIds([...app.querySelectorAll('[data-cmp]')].map(x => x.value), shownList(LISTS).spots.map(spotOf).filter(Boolean)); redrawCompare();
    const n = cmpIds.length; say(n < 2 ? 'Choose at least two different places.' : `${n} places side by side.`); return; }
  if (e.target.id !== 'alerts-week') return;
  const box = e.target, want = box.checked; box.disabled = true;
  try { await window.PVAlerts.setWeekly(DATA.push, knownSaved(), want); alertsSaid = want ? 'The weekly note is on: Thursday evenings.' : 'The weekly note is off.'; }
  catch (err) { alertsSaid = `Could not change the weekly note: ${err.message}.`; }
  redrawAlerts(); const again = document.getElementById('alerts-week'); if (again) again.focus({ preventScroll: true });
});
// The list's name, as typed: made or renamed, and said.
function listSave() {
  const box = document.getElementById('list-name'), name = box ? box.value : '', cur = shownList(LISTS);
  if (!listName(name)) { if (box) box.focus(); return; }
  const ok = setLists(listForm === 'new' ? makeList(LISTS, name) : renameList(LISTS, cur.id, name)), made = listForm === 'new';
  listForm = null; draw();
  const t = document.getElementById('list-said'); if (t) t.textContent = !ok ? 'This browser is not keeping site data, so this lasts only until you close the page.' : made ? `“${shownList(LISTS).name}” is ready. Save on a place's page adds to it.` : `Renamed to “${shownList(LISTS).name}”.`;
}
app.addEventListener('keydown', e => {
  if (e.target.id === 'q' && e.key === 'Enter') { const first = app.querySelector('#results a.row'); if (first) { e.preventDefault(); first.click(); } }
  if (e.target.id === 'from' && e.key === 'Enter') { const first = app.querySelector('#offers button'); if (first) { e.preventDefault(); first.click(); } }
  if (e.target.id === 'list-name' && e.key === 'Enter') { e.preventDefault(); listSave(); }
  if (e.target.id === 'list-link' && e.key === 'Enter') { e.preventDefault(); listOpen(); }
  if (e.target.id === 'list-link' && e.key === 'Escape') { listForm = null; draw(); const b = app.querySelector('[data-do="list-open"]'); if (b) b.focus(); }
  if (e.target.id === 'list-name' && e.key === 'Escape') { listForm = null; draw(); const b = app.querySelector('[data-do="list-new"]'); if (b) b.focus(); }
  // Left and right move along the days, as tabs do.
  const tab = e.target.closest && e.target.closest('.daytab');
  if (tab && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) { const all = [...app.querySelectorAll('.daytab')], i = all.indexOf(tab), to = all[i + (e.key === 'ArrowRight' ? 1 : -1)];
    if (to) { e.preventDefault(); to.focus(); } }
});
app.addEventListener('click', e => {
  // Before the forecast is read a built page's links are plain links, and each has a page of its own to open.
  if (!DATA || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
  const a = e.target.closest('a[href]'), b = e.target.closest('[data-do]');
  if (b) { const act = b.dataset.do;
    if (act === 'jump') { e.preventDefault(); jump(b.dataset.to); return; }
    if (act === 'locate') { locate(() => draw()); return; }
    if (act === 'unlocate') { here = null; hereNote = ''; draw(); return; }
    if (act === 'miles') { miles = Number(b.dataset.miles) || 20; draw(); return; }
    if (act === 'all' && route.id) { expanded.add(route.id); draw();
      // The button has gone: focus moves to the first overflow it brought, so a keyboard carries on down the line.
      const next = app.querySelectorAll('.line .stop .textbtn')[LINE_FIRST]; if (next) next.focus({ preventScroll: true }); return; }
    if (act === 'more') { const box = b.nextElementSibling, open = b.getAttribute('aria-expanded') === 'true'; b.setAttribute('aria-expanded', String(!open)); b.textContent = open ? 'Details' : 'Hide details'; const box2 = b.closest('.st-row') ? b.closest('.st-row').nextElementSibling : box; if (box2) box2.hidden = open; return; }
    if (act === 'keep' && route.id) { const cur = shownList(LISTS), on = cur.spots.includes(route.id), many = LISTS.lists.length > 1;
      const ok = setLists(on ? removeFromList(LISTS, cur.id, route.id) : addToList(LISTS, cur.id, route.id)); draw();
      const t = document.getElementById('tool-said'); if (t) t.textContent = on ? `Removed from ${many ? `“${cur.name}”` : 'your saved places'}.`
        : !ok ? 'Saved for this visit only: this browser is not keeping site data.'
        : `Saved ${many ? `to “${cur.name}”` : 'on this device'}. It is under Saved${DATA.push && window.PVAlerts.can() === 'yes' ? ', where alerts can be turned on' : ''}.`; return; }
    if (act === 'up') { upView = b.dataset.up === 'map' ? 'map' : 'line'; draw(); return; }
    if (act === 'map-close') { mapPick = null; draw(); const m = document.querySelector('#home-map .pv-map'); if (m) m.focus({ preventScroll: true }); return; }
    if (act === 'map-near') { const go = () => { mapGoHere = true; draw(); }; if (here) go(); else locate(go); return; }
    if (act === 'unsave') { const cur = shownList(LISTS), s = spotOf(b.dataset.id); setLists(removeFromList(LISTS, cur.id, b.dataset.id)); draw();
      const t = document.getElementById('list-said'); if (t) t.textContent = `${s ? s.name : 'That place'} was removed.`;
      const h = app.querySelector('.view-saved .block h2'); if (h) { h.tabIndex = -1; h.focus({ preventScroll: true }); } return; }
    if (act === 'list') { setLists(pickList(LISTS, b.dataset.list)); draw(); return; }
    if (act === 'list-new' || act === 'list-rename' || act === 'list-del') { listForm = act === 'list-new' ? 'new' : act === 'list-rename' ? 'rename' : 'delete'; draw();
      const to = document.getElementById('list-name') || app.querySelector('[data-do="list-delete"]'); if (to) { to.focus(); if (to.select) to.select(); } return; }
    if (act === 'list-mv' || act === 'list-open') { listForm = act === 'list-mv' ? 'move' : 'open'; moveSaid = ''; draw();
      const to = document.getElementById(act === 'list-mv' ? 'mv-spot' : 'list-link'); if (to) to.focus(); return; }
    if (act === 'list-move' || act === 'list-copy') { listMove(act === 'list-copy'); return; }
    if (act === 'list-opened') { listOpen(); return; }
    if (act === 'list-cancel') { const was = listForm; listForm = null; moveSaid = ''; draw();
      const to = app.querySelector(`[data-do="${was === 'move' ? 'list-mv' : was === 'open' ? 'list-open' : 'list-new'}"]`) || app.querySelector('[data-do="list-open"]'); if (to) to.focus(); return; }
    if (act === 'list-save') { listSave(); return; }
    if (act === 'list-delete') { const gone = shownList(LISTS).name; setLists(deleteList(LISTS, shownList(LISTS).id)); listForm = null; draw();
      const t = document.getElementById('list-said'); if (t) t.textContent = `“${gone}” was deleted.`; const h = document.getElementById('title'); if (h) h.focus({ preventScroll: true }); return; }
    if (act === 'alerts') { alertsToggle(); return; }
    if (act === 'offline') { offlineToggle(); return; }
    if (act === 'to-data' && !PREVIEW) { e.preventDefault(); dataOpen = true; draw(); const d = document.getElementById('your-data'); if (d) { d.scrollIntoView(); const b = d.querySelector('button'); if (b) b.focus({ preventScroll: true }); } return; }
    if (act === 'count') { countToggle(); return; }
    if (act === 'share-list') { shareList(); return; }
    if (act === 'shared-add' || act === 'shared-show') { const sh = readShared(location.hash, dates()); if (!sh) return;
      const ids = sh.spots.filter(spotOf), kept = setLists(act === 'shared-add' ? addSharedList(LISTS, sh.name, ids) : pickList(LISTS, b.dataset.list));
      history.replaceState(null, '', link({ view: 'saved', day: route.day })); draw({ focus: true });
      const t = document.getElementById('list-said'); if (t && act === 'shared-add') t.textContent = kept ? `Added to your lists as ${shownList(LISTS).name}.` : 'This browser is not keeping site data, so this list is kept only for this visit.';
      const h = document.getElementById('title'); if (h) h.focus({ preventScroll: true }); return; }
    if (act === 'plan-here') { const go = () => planSet({ from: { here: true } }); if (here) go(); else locate(go); return; }
    if (act === 'plan-from') { const lat = Number(b.dataset.lat), lon = Number(b.dataset.lon); if (Number.isFinite(lat) && Number.isFinite(lon)) planSet({ from: { name: String(b.dataset.name).slice(0, 80), lat, lon } });
      const h = app.querySelector('#results h2'); if (h) { h.tabIndex = -1; h.focus({ preventScroll: true }); } return; }
    if (act === 'plan-within') { planSet({ within: Number(b.dataset.within) || 0 }); return; }

    if (act === 'share') { const s = spotOf(route.id), day = placeDay(s), url = new URL(link({ id: s.id, day }), document.baseURI).href, t = document.getElementById('tool-said');
      const done = msg => { if (t) t.textContent = msg; };
      const title = `${s.name}: ${P.levelWords(dayLevel(s, day)).toLowerCase()} ${dayWord(day)} (SwimSignal forecast)`;
      if (navigator.share) navigator.share({ title, url }).catch(() => {});
      else if (navigator.clipboard) navigator.clipboard.writeText(url).then(() => done(`Link copied. It opens this place on ${P.headDay(day) === 'today' ? 'today' : P.longDate(day)}.`), () => done('Copy the address from the bar above.'));
      else done('Copy the address from the bar above.');
      return; }
    if (act === 'share-picture') { const s = spotOf(route.id); if (!s || s.unlisted) return;
      sharePicture(s, placeDay(s)).catch(e => toolSaid(`Could not make the picture: ${e.message}.`)); return; }
  }
  // Only these pages' own addresses are drawn here (the opening and its views, and a place); a link to the live
  // site, or out, is left to the browser.
  const rel = a && !a.target && a.origin === location.origin && a.pathname.startsWith(BASE) ? a.pathname.slice(BASE.length) : null;
  // plan/ and saved/ are these pages' own too, where they are the site's: the live scripts link to Saved by that
  // address (host.js, savedPath), and two of them (journal.js, outing.js) stop the browser following their link
  // because their own page opens Saved itself. Here this handler is what opens it, so it must take the address.
  if (rel === null || !(rel === '' || /^(spot\/[A-Za-z0-9_-]+|plan|saved)\/$/.test(rel))) return;
  if (a.getAttribute('href').startsWith('#')) return;
  if (a.dataset.day) { e.preventDefault(); setDay(a.dataset.day); return; }
  if (a.dataset.planNew !== undefined) planNew = true;   // "Plan a swim here": started here, not opened from a link
  e.preventDefault(); leftAt.set(location.pathname + location.search, { y: window.scrollY, href: a.getAttribute('href') }); history.pushState(null, '', a.getAttribute('href')); draw({ focus: true });
});
// A link to a part of this page ("#main", the skip link): with a <base> the browser would read it as a link to the
// opening, so it is followed here.
document.addEventListener('click', e => {
  const a = e.target.closest && e.target.closest('a[href^="#"]'); if (!a || a.dataset.do || e.defaultPrevented) return;
  const el = document.getElementById(a.getAttribute('href').slice(1)); e.preventDefault(); if (!el) return;
  el.scrollIntoView(); if (!el.hasAttribute('tabindex')) el.tabIndex = -1; el.focus({ preventScroll: true });
});
// Back returns to where the page was left: the list of places elsewhere, not the top of the page.
const leftAt = new Map();
if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
// The fold over a visitor's data stays as they left it when the page is drawn again (a details' toggle does not bubble).
document.addEventListener('toggle', e => { if (e.target && e.target.id === 'your-data') dataOpen = e.target.open; }, true);
// A plan's choices, and a shared list, are after the #: an address typed or pasted over this one is drawn.
window.addEventListener('hashchange', () => { if (route && (route.view === 'plan' || route.view === 'saved' || route.point || /^#point=/.test(location.hash))) draw({ focus: true }); });
window.addEventListener('popstate', () => { const at = leftAt.get(location.pathname + location.search) || { y: 0 };
  draw({ focus: true, y: at.y });
  // A keyboard comes back to the link it followed, so the next Tab goes on from there.
  const from = at.href && [...app.querySelectorAll('a[href]')].find(x => x.getAttribute('href') === at.href);
  if (from) from.focus({ preventScroll: true }); });

// For the build (scripts/prerender_preview.js runs this file in Node): the opening and each place's page as this
// script draws them, at the moment the forecast was issued. The build writes them into the pages, so a page has its
// answer before this script runs, and for a reader or a crawler without scripts. files: the place's own file and
// its overflows upstream, which the page would otherwise fetch.
window.PVBuilt = {
  load(data, hero) { DATA = P.prepare(data, now()); HERO = hero || {}; },
  home() { route = { screen: 'find', view: '', day: null, q: '', area: '' }; return homeHtml(); },
  place(id, files) { route = { screen: 'place', id, day: null }; details.set(id, files || { detail: null, up: null }); return placeHtml(); },
};

// As the site's own pages they are kept for the water's edge as the app's are, by the site's worker (sw.js), unless
// the offline copy has been turned off in this browser (the app's "Your data"). A preview starts no worker: it is
// kept only where the worker is already running.
if (!PREVIEW && 'serviceWorker' in navigator) { let off = false; try { off = localStorage.getItem('dipcast.offline') === 'off'; } catch (e) { off = false; }
  if (!off) startWorker(); }

(async function start() {
  try { const [data, hero] = await Promise.all([loadJson('data/spots-lite.json'), loadJson('preview/hero-photos.json').catch(() => ({}))]);
    DATA = P.prepare(data, now()); HERO = hero || {};
    window.DATA = DATA; }   // journal.js names a swim's place from the forecast the page holds, by this name, as on the live page
  catch (e) {
    // A page the build wrote keeps what it says, with a line on what it is: the forecast as at the build.
    if (app.hasAttribute && app.hasAttribute('data-built')) { const m = app.querySelector('main');
      if (m) m.insertAdjacentHTML('afterbegin', '<p class="notice" role="note"><b>The latest forecast could not be read.</b> This page shows the forecast as it was when the page was made. Check the connection and load it again.</p>');
      return; }
    app.innerHTML = `<header class="bar"><a class="brand" href="${HOME || './'}">SwimSignal</a></header><main id="main" class="home"><section class="opening"><h1>The forecast could not be read</h1><p class="lede">Check the connection and load the page again.${PREVIEW ? ` <a href="${classic()}">The current site</a> keeps a copy for offline use.` : ''}</p></section></main>`; return; }
  draw({ first: true }); syncSoon();
})();
})();
