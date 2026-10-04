// The swim journal: a swimmer's own record of where and when they swam, with a short note, the minutes
// in the water and photos if they like, and what SwimSignal showed for the spot when the swim was logged:
// the level and what set it, the rain, the overflows discharging, and the river level and the water
// temperature where the page shows them. So later they can look back at what the forecast said on the
// days they swam.
//
// Only on this device. The swims are in localStorage under dipcast.swims, the key of the one-tap log
// ("I swam here today") this replaces, whose entries it still reads; the photos are in IndexedDB. This
// file makes no request of any kind: unlike reviews (reviews.js) and notes on a visit (visits.js), which
// are public and go to the reviews Worker, nothing in the journal leaves the browser unless the swimmer
// saves a copy as a file, which is how it moves to another browser or phone. No health questions: the
// illness reports (illness.js) are separate.
//
// A plain script, as plan.js: globals in the page (names begin jn, journal or JOURNAL), exports in Node
// (tests/site_journal.test.cjs). It asks for the level rules (levels.js) when it is called, and for
// reviews.js's photo shrinking (reviewShrink) when a photo is added, so in the page it loads after both.

const JOURNAL_KEY = 'dipcast.swims';
// swims: the most kept; photos: a swim's, and allPhotos all of them, which bounds what the journal holds on
// the device; full and thumb: the largest photo a copy may bring back, in bytes; file: the largest copy read.
const JOURNAL_LIMITS = { swims: 500, note: 280, minutes: 600, photos: 3, allPhotos: 200, full: 3 * 1024 * 1024, thumb: 512 * 1024, file: 150 * 1024 * 1024 };
const JOURNAL_SHOW = 5;                  // swims listed before "Show all"
const JOURNAL_FILE = 'swimsignal-journal';   // a copy's name, and its kind inside it
const jnRules = () => typeof dayHeadline === 'function' ? { ORDER, rank, daily, dayLevel, dayHeadline, nowBecause } : require('./levels.js');

const jnEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const jnPad = n => String(n).padStart(2, '0');
const jnLocal = (d = new Date()) => `${d.getFullYear()}-${jnPad(d.getMonth() + 1)}-${jnPad(d.getDate())}`;
const jnClock = (d = new Date()) => `${jnPad(d.getHours())}:${jnPad(d.getMinutes())}`;
const jnCap = s => s.charAt(0).toUpperCase() + s.slice(1);
const JN_CLOCK = /^([01]\d|2[0-3]):[0-5]\d$/;
const JN_LEVELS = ['low', 'moderate', 'high', 'very high'];
const JN_PLAIN = ['no overflows', 'no river connection', 'not covered', 'no forecast'];   // levels.js's levels without a risk
const JN_RIVER = { low: 'low water', normal: 'usual level', high: 'high water', 'very high': 'very high water' };   // the River level tile's words
const JN_CLOSE = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';

// ------------------------------------------------------------------------------ no page needed

// Read back safely: a value is kept only if it is the kind expected, and anything else reads as absent.
const jnIsDay = s => typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s) && s >= '2000-01-01' && s <= '2100-12-31'
  && !Number.isNaN(Date.parse(s + 'T12:00:00Z')) && new Date(s + 'T12:00:00Z').toISOString().slice(0, 10) === s;   // 2026-02-30 is not a day
const jnText = (v, n) => typeof v === 'string' ? v.trim().slice(0, n) : '';
const jnNum = (v, lo, hi) => typeof v === 'number' && Number.isFinite(v) && v >= lo && v <= hi ? v : null;
const jnInt = (v, lo, hi) => Number.isInteger(v) && v >= lo && v <= hi ? v : null;
const jnWhen = v => typeof v === 'string' && v.length <= 40 && /^\d{4}-\d{2}-\d{2}T/.test(v) && !Number.isNaN(Date.parse(v)) ? v : '';   // a time and date, as toISOString writes them
const jnObj = v => !!v && typeof v === 'object' && !Array.isArray(v);

// What SwimSignal showed with a swim, checked field by field, or null.
function jnSeenOk(s) {
  if (!jnObj(s)) return null;
  const head = jnText(s.head, 120); if (!head) return null;
  const of = jnInt(s.of, 1, 100000), dis = of === null ? null : jnInt(s.dis, 0, of);
  return { head, level: JN_LEVELS.includes(s.level) || JN_PLAIN.includes(s.level) ? s.level : null, issued: jnWhen(s.issued),
    rain: jnNum(s.rain, 0, 2000), dis, of: dis === null ? null : of,
    river: jnObj(s.river) && jnNum(s.river.m, -50, 100) !== null ? { m: s.river.m, word: jnText(s.river.word, 40) } : null,
    temp: jnObj(s.temp) && jnNum(s.temp.c, -5, 45) !== null ? { c: s.temp.c } : null };
}

// One swim, or null. The one-tap log kept { id, date, level }: those three stay, so an older copy of the
// page still reads the list, and such an entry gets the key id@date, which that log kept unique.
function journalEntry(x) {
  if (!jnObj(x)) return null;
  const id = jnText(x.id, 120); if (!id || !jnIsDay(x.date)) return null;
  return { id, date: x.date, level: JN_LEVELS.includes(x.level) ? x.level : null,
    key: typeof x.key === 'string' && /^[A-Za-z0-9_.@-]{4,160}$/.test(x.key) ? x.key : `${id}@${x.date}`,
    name: jnText(x.name, 120), time: typeof x.time === 'string' && JN_CLOCK.test(x.time) ? x.time : '',
    minutes: jnInt(x.minutes, 1, JOURNAL_LIMITS.minutes), note: jnText(x.note, JOURNAL_LIMITS.note),
    photos: jnInt(x.photos, 0, JOURNAL_LIMITS.photos) ?? 0, at: jnWhen(x.at), seen: jnSeenOk(x.seen) };
}
// The stored list (localStorage's text, or a list), read back safely, as storedList is in experience.js:
// anything but a list reads as empty, and what is not a swim is dropped, so the page cannot stop on a
// hand edit, another version's format or a broken write. A key seen twice keeps its first swim.
function journalEntries(v) {
  if (typeof v === 'string' || v === null || v === undefined) { try { v = JSON.parse(v || '[]'); } catch (e) { return []; } }
  if (!Array.isArray(v)) return [];
  const keys = new Set(), out = [];
  for (const x of v) { const e = journalEntry(x); if (e && !keys.has(e.key)) { keys.add(e.key); out.push(e); } }
  return out;
}
// Newest first: the day, then the time (a swim without one after those with), then when it was logged.
const jnOrder = e => `${e.date} ${e.time || '00:00'} ${e.at}`;
const journalSort = list => list.slice().sort((a, b) => jnOrder(b).localeCompare(jnOrder(a)));
const journalPhotoCount = list => list.reduce((n, e) => n + e.photos, 0);

// Why a swim keeps no forecast, in the form's words, or '' when it keeps one. A forecast is kept only for
// a swim on the device's `today` at or after the forecast was issued (`issued`), at `time`: the page has
// no forecast for the days before, and one issued after the swim was not there when they swam. Without a
// time that cannot be told, so none is kept either. Nor where the forecast does not cover the day.
function journalSeenWhy(d, date, time, today, issued) {
  if (date < today) return 'No forecast: the page has none for the days before today.';
  if (date !== today) return 'No forecast: a swim is logged on its day or after.';
  const at = Date.parse(issued), when = Number.isNaN(at) ? '' : jnLocal(new Date(at)) === date ? ` at ${jnClock(new Date(at))}` : ` ${jnIssued(issued)}`;
  if (!JN_CLOCK.test(time || '')) return `No forecast: without the time of your swim, it may have been before this forecast was issued${when}.`;
  if (!Number.isNaN(at) && Date.parse(`${date}T${time}:00`) < at) return `No forecast: this one was issued${when}, after your swim.`;
  const x = (Array.isArray(d.days) ? d.days.slice(0, 5) : []).find(y => y && y.date === date);
  if (jnRules().daily(d) && !x) return 'No forecast: the one on this device does not cover that day.';
  return '';
}
// What the spot's page shows for a swim on `date` at `time`, kept with it, or null (journalSeenWhy says
// why). The level and what set it, as a picked day's headline says them (dayHeadline); right now's spills
// instead, where they are worse than the day's forecast, since that is what the answer showed. The rain
// in the 48 h to midday, the overflows upstream discharging, and the river level and the water
// temperature where the page shows a figure for them (index.html, riverTile and waterTile).
function journalSeen(d, date, today, issued, time) {
  if (journalSeenWhy(d, date, time, today, issued)) return null;
  const R = jnRules(), x = (Array.isArray(d.days) ? d.days.slice(0, 5) : []).find(y => y && y.date === date);
  let level = R.dayLevel(d, date), head = R.dayHeadline(d, date);
  const total = (d.upstream_summary || {}).overflows || 0, now = d.now || {};
  if (R.daily(d) && R.rank(now.label) >= 1 && R.rank(now.label) > R.rank(level)) { level = now.label; head = `${jnCap(level)} risk: ${R.nowBecause(d, { level, by: 'spill' })}`; }   // "recent sewage spills" with none discharging
  const rs = d.river_state || {}, wt = d.water_temp || {};
  const temp = typeof wt.temp_c === 'number' && !Number.isNaN(Date.parse(wt.observed_at)) && typeof wt.river_km === 'number'
    && ['upstream', 'downstream'].includes(wt.direction) ? { c: wt.temp_c } : null;
  return jnSeenOk({ head, level, issued, rain: x && typeof x.rain_48h_mm === 'number' ? Math.round(x.rain_48h_mm * 10) / 10 : null,
    dis: total ? now.discharging_upstream || 0 : null, of: total || null,
    river: !rs.stale && typeof rs.level_m === 'number' ? { m: rs.level_m, word: JN_RIVER[rs.label] || '' } : null, temp });
}
// The figures kept with a swim, as phrases: the rain, the overflows, the river and the water.
function journalSeenWords(s) {
  const out = [];
  if (s.rain !== null) out.push(s.rain === 0 ? 'no rain in the last two days' : s.rain < 0.5 ? 'under 1 mm of rain in the last two days' : `${Math.round(s.rain)} mm of rain in the last two days`);
  if (s.of) out.push(s.of === 1 ? `the overflow upstream ${s.dis ? '' : 'not '}discharging` : s.dis ? `${s.dis} of ${s.of} overflows upstream discharging` : `none of the ${s.of} overflows upstream discharging`);
  if (s.river) out.push(`river ${s.river.m.toFixed(2)} m${s.river.word ? ', ' + s.river.word : ''}`);
  if (s.temp) out.push(`water ${Math.round(s.temp.c)}°C`);
  return out;
}
// A level in its text colour, never a filled label (docs/DESIGN.md): the plain one with no overflows in its teal.
const jnBadge = l => l === 'no overflows' ? 'b-clear' : JN_LEVELS.includes(l) ? 'b-' + l.replace(' ', '') : 'b-na';
const jnIssued = iso => new Date(iso).toLocaleString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const journalSeenHtml = s => { const w = journalSeenWords(s);
  return `<p class="jn-seen"><span class="badge ${jnBadge(s.level)}">${jnEsc(s.head)}</span> <span class="jn-k">in the forecast${s.issued ? ` issued ${jnEsc(jnIssued(s.issued))}` : ''}</span></p>`
    + (w.length ? `<p class="rv-meta">${jnEsc(jnCap(w.join(' · ')))}</p>` : ''); };

// The first thing wrong with a draft, in the form's words, or ''. `count`: the swims already kept.
function journalProblem(d, today, count = 0) {
  if (count >= JOURNAL_LIMITS.swims) return `The journal holds ${JOURNAL_LIMITS.swims} swims, the most it keeps. Save a copy and delete older swims to add more.`;
  if (!jnIsDay(d.date) || d.date > today) return 'Choose the day you swam: today or before.';
  if (d.time && !JN_CLOCK.test(d.time)) return 'Give the time in hours and minutes, or leave it empty.';
  const m = String(d.minutes ?? '').trim();
  if (m && jnInt(Number(m), 1, JOURNAL_LIMITS.minutes) === null) return `Minutes in the water: a whole number from 1 to ${JOURNAL_LIMITS.minutes}, or leave it empty.`;
  if ((d.note || '').length > JOURNAL_LIMITS.note) return `Keep the note to ${JOURNAL_LIMITS.note} characters.`;
  return '';
}
// A new swim from a draft the form has checked, with what the page showed (seen, from journalSeen).
function journalNew(d, draft, seen, now = new Date(), rand = Math.random) {
  const m = String(draft.minutes ?? '').trim();
  return journalEntry({ id: d.id, date: draft.date, level: seen && JN_LEVELS.includes(seen.level) ? seen.level : null,
    key: `j${now.getTime().toString(36)}${Math.floor(rand() * 36 ** 4).toString(36).padStart(4, '0')}`, name: d.name, time: draft.time || '',
    minutes: m ? Number(m) : null, note: draft.note || '', photos: 0, at: now.toISOString(), seen });
}

// ------------------------------------------------------------------------------ a copy, as a file

// A photo from a copy: a JPEG, PNG or WebP as a data address, within the size the page makes, or null.
function jnPhotoOk(p) {
  if (!jnObj(p) || !['image/jpeg', 'image/png', 'image/webp'].includes(p.type)) return null;
  const ok = (v, max) => { const pre = `data:${p.type};base64,`;
    if (typeof v !== 'string' || !v.startsWith(pre)) return false;
    const b = v.slice(pre.length);
    return b.length > 0 && b.length % 4 === 0 && /^[A-Za-z0-9+/]+={0,2}$/.test(b) && b.length * 3 / 4 <= max; };
  return ok(p.full, JOURNAL_LIMITS.full) && ok(p.thumb, JOURNAL_LIMITS.thumb) ? { type: p.type, full: p.full, thumb: p.thumb } : null;
}
// The file: what it is, when it was made, the swims, and each swim's photos under key-0, key-1, key-2.
function journalFile(list, photos = {}, at = new Date().toISOString()) {
  return JSON.stringify({ kind: JOURNAL_FILE, version: 1, made: at,
    about: 'A copy of a SwimSignal swim journal, made on the device that kept it. It holds notes and photos: keep it private.',
    swims: list, photos }, null, 1);
}
// A copy read back: { swims, photos: { key: [photo, ...] } }, each swim's photos the good ones in order,
// or null when the text is not a journal (a copy, or a bare list of swims).
function journalRead(text) {
  let v; try { v = JSON.parse(text); } catch (e) { return null; }
  const raw = Array.isArray(v) ? v : jnObj(v) && v.kind === JOURNAL_FILE && Array.isArray(v.swims) ? v.swims : null;
  if (!raw) return null;
  const pics = jnObj(v) && jnObj(v.photos) ? v.photos : {}, photos = {};
  const swims = journalEntries(raw).map(e => {
    const got = [];
    for (let n = 0; n < JOURNAL_LIMITS.photos; n++) { const p = Object.hasOwn(pics, `${e.key}-${n}`) ? jnPhotoOk(pics[`${e.key}-${n}`]) : null; if (p) got.push(p); }
    if (got.length) photos[e.key] = got;
    return { ...e, photos: got.length };
  });
  return { swims, photos };
}
// Swims from a copy added to the journal: those already in it (the same key) are left, the newest kept
// first if the journal fills, and photos beyond the room left go without them.
// { list, added, same, over, photosLeft }.
function journalMerge(have, incoming, limit = JOURNAL_LIMITS.swims, allPhotos = JOURNAL_LIMITS.allPhotos) {
  const keys = new Set(have.map(e => e.key)), added = [];
  let same = 0, over = 0, photosLeft = 0, room = Math.max(0, allPhotos - journalPhotoCount(have));
  for (const e of journalSort(incoming)) {
    if (keys.has(e.key)) { same++; continue; }
    if (have.length + added.length >= limit) { over++; continue; }
    const k = Math.min(e.photos, room); photosLeft += e.photos - k; room -= k;
    keys.add(e.key); added.push({ ...e, photos: k });
  }
  return { list: [...have, ...added], added, same, over, photosLeft };
}

// ------------------------------------------------------------------------------ what the page shows

const jnDay = (iso, now = new Date()) => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB',
  { weekday: 'short', day: 'numeric', month: 'short', ...(iso.slice(0, 4) === String(now.getFullYear()) ? {} : { year: 'numeric' }) });
const jnFeedback = () => typeof FEEDBACK === 'string' ? FEEDBACK : 'feedback.html?type=feedback';

// One swim in the list, built as a review's row: the day and time as its headline, the spot (linked
// while it is in the forecast) and the minutes, what the forecast showed, the note, the photos, and
// Delete. No link that sends anything: the journal is private. o: { hidden, spot (the spot now, if
// listed), href (its page), now }.
function journalItem(e, o = {}) {
  const name = (o.spot && o.spot.name) || e.name || e.id, when = jnDay(e.date, o.now) + (e.time ? `, ${e.time}` : '');
  const where = o.spot ? `<a href="${jnEsc(o.href || `spot/${e.id}/`)}" data-jn-spot="${jnEsc(e.id)}">${jnEsc(name)}</a>` : jnEsc(name);
  const seen = e.seen ? journalSeenHtml(e.seen)
    : e.level ? `<p class="jn-seen"><span class="badge ${jnBadge(e.level)}">${jnCap(e.level)} risk</span> <span class="jn-k">in the day's forecast</span></p>`
    : e.at ? '<p class="rv-meta">No forecast was kept with this swim.</p>' : '';
  const pics = !e.photos ? '' : `<ul class="rv-pics">${Array.from({ length: e.photos }, (_, n) => `<li><button type="button" class="rv-pic" data-jn-photo="${jnEsc(e.key)}-${n}"`
    + ` aria-label="Photo ${n + 1} of ${e.photos}, ${jnEsc(when)}"><img data-jn-thumb="${jnEsc(e.key)}-${n}" width="72" height="72" alt=""></button></li>`).join('')}</ul>`;
  return `<li class="rv jn"${o.hidden ? ' hidden' : ''} data-key="${jnEsc(e.key)}"><p class="rv-v">${jnEsc(when)}</p>`
    + `<p class="jn-where">${where}${e.minutes ? ` · ${e.minutes} minute${e.minutes === 1 ? '' : 's'} in the water` : ''}</p>`
    + seen + (e.note ? `<p class="rv-text">${jnEsc(e.note)}</p>` : '') + pics
    + `<div class="rv-acts"><button type="button" class="linkbtn small" data-jn-delete="${jnEsc(e.key)}">Delete</button></div></li>`;
}

// The journal on the Saved page: one tile, "Only on this device" first, the swims newest first (five,
// then "Show all"), and the copy. o: { all (every swim shown), say (a line after an action), spots
// (a Map of the listed spots by id), href (a spot's page), now }.
function journalSection(list, o = {}) {
  const swims = journalSort(list), n = swims.length, spots = o.spots || new Map();
  let h = '<section class="sec tile" id="journal" tabindex="-1" aria-labelledby="jn-h"><h2 class="sec-h" id="jn-h">Swim journal</h2>'
    + `<p class="sub"><b>Only on this device.</b> ${n ? `${n === 1 ? 'One swim' : `${n} swims`}, newest first, each with what the forecast showed when you logged it.`
      : 'Log a swim from a spot\'s page: the day, a note, photos and what the forecast showed are kept here.'} Nothing in it is sent anywhere.</p>`;
  if (n) h += `<ol class="rv-list" id="jn-list">${swims.map((e, i) => journalItem(e, { hidden: !o.all && i >= JOURNAL_SHOW, spot: spots.get(e.id),
      href: o.href ? o.href(e.id) : '', now: o.now })).join('')}</ol>`
    + (!o.all && n > JOURNAL_SHOW ? `<button type="button" class="btn quiet" id="jn-all" aria-expanded="false">Show all ${n}</button>` : '');
  h += `<div class="jn-file" id="jn-file-row">${n ? '<button type="button" class="linkbtn" id="jn-export">Save a copy</button>' : ''}`
    + '<button type="button" class="linkbtn" id="jn-import">Add swims from a copy</button>'
    + (n ? '<button type="button" class="linkbtn" id="jn-clear">Delete all</button>' : '')
    + '<input type="file" id="jn-file" accept=".json,application/json" hidden></div>'
    + `<p class="small muted msg">${n ? 'A copy is a file of your swims, notes and photos: keep it private. Adding it on another phone or browser moves the journal there'
      : 'A copy saved on another phone or browser brings that journal here'}; on an iPhone, Safari and the Home Screen app keep separate journals.</p>`
    + (o.say ? `<p class="rv-said jn-said" id="jn-said" tabindex="-1" role="status">${o.say}</p>` : '<p class="rv-said jn-said" id="jn-said" tabindex="-1" role="status" hidden></p>');
  return h + '</section>';
}

// What will be kept with a swim, under the form's fields, in the journal's own words: what the page shows
// (seen), or why no forecast is kept (why, from journalSeenWhy).
function journalKeptHtml(seen, why = '') {
  return '<div class="jn-kept" id="jn-kept"><p class="rv-q">Kept with the swim</p>'
    + (seen ? journalSeenHtml(seen) : `<p class="rv-meta">${jnEsc(why)}</p>`) + '</div>';
}
// The form, in a tile after the spot's buttons: the day and time, the minutes, a note, photos (where the
// browser can keep them) and what will be kept with it. Nothing in it is sent.
function journalFormHtml(today, clock, photos = true) {
  return '<section class="sec tile jn-box" id="jn-box" aria-labelledby="jn-box-h"><h2 class="sec-h" id="jn-box-h" tabindex="-1">Log a swim</h2>'
    + '<p class="sub"><b>Only on this device.</b> Your journal stays in this browser and is sent nowhere. It is on the Saved page.</p>'
    // data-keep-page: the page does not reload itself for a newer forecast while this is open (index.html).
    + '<form class="rv-form" id="jn-form" novalidate data-keep-page><div class="jn-when">'
    + `<label><span class="rv-q">Day</span><input type="date" id="jn-date" value="${today}" min="2000-01-01" max="${today}"></label>`
    + `<label><span class="rv-q">Time <span class="rv-opt">Optional</span></span><input type="time" id="jn-time" value="${clock}"></label></div>`
    + `<label class="rv-q" for="jn-min">Minutes in the water <span class="rv-opt">Optional</span></label><input type="number" id="jn-min" inputmode="numeric" min="1" max="${JOURNAL_LIMITS.minutes}" step="1">`
    + `<label class="rv-q" for="jn-note">Note <span class="rv-opt">Optional</span></label><textarea id="jn-note" rows="3" maxlength="${JOURNAL_LIMITS.note}" placeholder="The water, the weather, getting in"></textarea>`
    + (photos ? `<p class="rv-q" id="jn-ph">Photos <span class="rv-opt">Up to ${JOURNAL_LIMITS.photos}, optional</span></p><ul class="rv-previews" id="jn-previews" aria-labelledby="jn-ph"></ul>`
      + '<label class="btn rv-add" id="jn-add"><input type="file" class="rv-file" id="jn-pick" accept="image/*" multiple>Add photos</label>' : '')
    + '<div id="jn-kept-host"></div>'
    + '<div class="rv-send"><button type="submit" class="btn primary">Save to journal</button><button type="button" class="btn" id="jn-cancel">Cancel</button></div>'
    + '<p class="rv-msg" id="jn-msg" role="status"></p></form></section>';
}

// ------------------------------------------------------------------------------ the page

// The photos, in IndexedDB: one store, a record a photo under its swim's key and number ("key-0"),
// { type, full, thumb } with the two as ArrayBuffers, which every browser keeps (Blobs not always).
const JN_DB = 'dipcast-journal', JN_STORE = 'photos';
let jnDbOpen = null;
function jnDb() {
  if (jnDbOpen) return jnDbOpen;
  jnDbOpen = new Promise((ok, no) => {
    if (typeof indexedDB === 'undefined') { no(new Error('this browser keeps no photos')); return; }
    let r; try { r = indexedDB.open(JN_DB, 1); } catch (e) { no(e); return; }
    r.onupgradeneeded = () => { if (!r.result.objectStoreNames.contains(JN_STORE)) r.result.createObjectStore(JN_STORE); };
    r.onsuccess = () => { const db = r.result; db.onversionchange = () => { db.close(); jnDbOpen = null; }; ok(db); };
    r.onerror = () => no(r.error || new Error('the photo store would not open'));
    r.onblocked = () => no(new Error('the photo store is busy in another tab'));
  });
  jnDbOpen.catch(() => { jnDbOpen = null; });   // asked again next time
  return jnDbOpen;
}
// One transaction: work queues its requests on the store and returns what to answer with once it is done.
const jnTx = (mode, work) => jnDb().then(db => new Promise((ok, no) => {
  const t = db.transaction(JN_STORE, mode), out = work(t.objectStore(JN_STORE));
  t.oncomplete = () => ok(typeof out === 'function' ? out() : out);
  t.onerror = t.onabort = () => no(t.error || new Error('the photo store failed'));
}));
const jnPhotoPut = (key, recs) => jnTx('readwrite', s => { recs.forEach((p, n) => s.put(p, `${key}-${n}`)); });
const jnPhotoGet = keys => jnTx('readonly', s => { const got = {};
  keys.forEach(k => { const r = s.get(k); r.onsuccess = () => { if (r.result) got[k] = r.result; }; }); return got; });
const jnPhotoDel = keys => jnTx('readwrite', s => { keys.forEach(key => { for (let n = 0; n < JOURNAL_LIMITS.photos; n++) s.delete(`${key}-${n}`); }); });
const jnPhotoClear = () => jnTx('readwrite', s => { s.clear(); });
// Photos whose swim is gone (deleted in another tab, or a write that failed half way) are let go.
const jnPhotoTidy = list => { const want = new Set(list.flatMap(e => Array.from({ length: e.photos }, (_, n) => `${e.key}-${n}`)));
  return jnTx('readonly', s => { const r = s.getAllKeys(); return () => r.result || []; })
    .then(keys => { const gone = keys.filter(k => !want.has(k)); return gone.length ? jnTx('readwrite', s => { gone.forEach(k => s.delete(k)); }) : null; }); };
const jnRecord = async p => ({ type: 'image/jpeg', full: await p.full.arrayBuffer(), thumb: await p.thumb.arrayBuffer() });
const jnBlob = (rec, part) => new Blob([rec[part]], { type: rec.type || 'image/jpeg' });
const jnB64 = buf => { const b = new Uint8Array(buf); let s = '';
  for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000)); return btoa(s); };
const jnUnB64 = url => { const s = atob(url.slice(url.indexOf(',') + 1)), b = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) b[i] = s.charCodeAt(i); return b.buffer; };

const journalNow = () => { try { return journalEntries(localStorage.getItem(JOURNAL_KEY)); } catch (e) { return []; } };
const journalKeep = list => { try { localStorage.setItem(JOURNAL_KEY, JSON.stringify(list)); return true; } catch (e) { return false; } };

// "Log a swim" on a spot's page (index.html, actions): the form opens in a tile under the buttons.
// issued: the forecast's time, kept with the swim.
function journalLogBind(d, issued) {
  const b = document.getElementById('swam'); if (!b) return;
  b.addEventListener('click', () => {
    const open = document.getElementById('jn-box');
    if (open) { open.querySelector('#jn-box-h').focus(); return; }
    journalOpenForm(d, issued, b);
  });
}
function journalOpenForm(d, issued, b) {
  const acts = b.closest('.actions'); if (!acts) return;
  const today = jnLocal(), photosOn = typeof reviewShrink === 'function' && typeof indexedDB !== 'undefined';
  acts.insertAdjacentHTML('afterend', journalFormHtml(today, jnClock(), photosOn));
  b.setAttribute('aria-expanded', 'true'); b.setAttribute('aria-controls', 'jn-box');
  const box = document.getElementById('jn-box'), f = box.querySelector('form'), $ = s => f.querySelector(s);
  const msg = $('#jn-msg'), send = f.querySelector('[type=submit]'), photos = [];
  let busy = 0;
  const say = (text, bad = false) => { msg.textContent = text; msg.classList.toggle('bad', bad); };
  const kept = () => { const date = $('#jn-date').value, time = $('#jn-time').value, today = jnLocal();
    $('#jn-kept-host').innerHTML = journalKeptHtml(journalSeen(d, date, today, issued, time), journalSeenWhy(d, date, time, today, issued)); };
  kept();
  for (const el of [$('#jn-date'), $('#jn-time')]) { el.addEventListener('change', kept); el.addEventListener('input', kept); }
  const close = () => { photos.forEach(p => URL.revokeObjectURL(p.url)); box.remove(); b.setAttribute('aria-expanded', 'false'); b.removeAttribute('aria-controls'); };
  if (photosOn) {
    const list = $('#jn-previews'), pick = $('#jn-pick');
    const draw = () => { list.innerHTML = photos.map((p, i) => `<li><img src="${p.url}" alt="Photo ${i + 1}"><button type="button" class="linkbtn small" data-drop="${i}">Remove</button></li>`).join('');
      $('#jn-add').hidden = photos.length >= JOURNAL_LIMITS.photos; };
    list.addEventListener('click', e => { const x = e.target.closest('[data-drop]'); if (!x) return;
      const [p] = photos.splice(Number(x.dataset.drop), 1); URL.revokeObjectURL(p.url); draw(); pick.focus(); });
    pick.addEventListener('change', async () => {
      const files = [...pick.files]; pick.value = '';
      busy++; send.disabled = true; say('Getting the photos ready…');
      let note = '';
      for (const x of files) {
        if (photos.length >= JOURNAL_LIMITS.photos) { note = `Up to ${JOURNAL_LIMITS.photos} photos a swim.`; break; }
        if (x.size > REVIEW_LIMITS.file) { note = 'A photo was too large to use.'; continue; }
        // The reviews' shrinking: 1280 px on its long side and a thumbnail, saved again without the camera's location.
        try { photos.push(await reviewShrink(x)); draw(); } catch (err) { note = 'A photo could not be read here. A JPEG or a PNG works anywhere.'; }
      }
      busy--; send.disabled = busy > 0; say(note, Boolean(note));
    });
  }
  $('#jn-cancel').addEventListener('click', () => { close(); b.focus(); });
  f.addEventListener('submit', async e => {
    e.preventDefault(); if (busy) return;
    const draft = { date: $('#jn-date').value, time: $('#jn-time').value, minutes: $('#jn-min').value, note: $('#jn-note').value.trim() };
    const have = journalNow();
    const problem = journalProblem(draft, jnLocal(), have.length)
      || (journalPhotoCount(have) + photos.length > JOURNAL_LIMITS.allPhotos ? `The journal holds ${JOURNAL_LIMITS.allPhotos} photos, the most it keeps on this device. Delete older swims to add more.` : '');
    if (problem) { say(problem, true); return; }
    busy++; send.disabled = true;
    const entry = journalNew(d, draft, journalSeen(d, draft.date, jnLocal(), issued, draft.time));
    let lost = false;
    if (photos.length) {
      try { await jnPhotoPut(entry.key, await Promise.all(photos.map(jnRecord))); entry.photos = photos.length; } catch (err) { lost = true; }
    }
    const ok = journalKeep([...journalNow(), entry]);
    if (!ok && entry.photos) jnPhotoDel([entry.key]).catch(() => {});
    close();
    const m = document.getElementById('swam-msg'), saved = typeof savedPath === 'function' ? savedPath() : 'saved/';
    if (m) m.innerHTML = !ok ? 'This browser is not keeping site data, so the swim could not be kept.'
      : `Logged in your swim journal, only on this device${lost ? ', without its photos: this browser would not keep them' : ''}. `
        + `<a href="${jnEsc(saved)}#journal" data-jn-open>Your journal</a> is on the Saved page. <a href="${jnFeedback()}&amp;spot=${encodeURIComponent(`${d.name}, ${jnDay(entry.date)} ${entry.date}`)}">Tell Ethan how the water was</a>.`;
    b.focus();
  });
  // "Your journal": the Saved page, at the journal, without leaving the app.
  const m = document.getElementById('swam-msg');
  if (m) m.onclick = e => { const a = e.target.closest('[data-jn-open]');
    if (!a || typeof openSaved !== 'function' || (typeof plainClick === 'function' && !plainClick(e))) return;
    e.preventDefault(); openSaved(); journalFocus(); };
  box.querySelector('#jn-box-h').focus({ preventScroll: true });
  box.scrollIntoView({ block: 'nearest', behavior: typeof SCROLL === 'function' ? SCROLL() : 'auto' });
}

// The journal on the Saved page (index.html, renderSaved). Thumbnails come from IndexedDB once drawn.
let JN_ALL = false, jnUrls = [];
const jnSpots = () => typeof DATA !== 'undefined' && DATA ? new Map(DATA.spots.map(s => [s.id, s])) : new Map();
const jnHref = id => typeof spotPath === 'function' ? spotPath(id) : `spot/${id}/`;
const journalCard = (say = '') => journalSection(journalNow(), { all: JN_ALL, say, spots: jnSpots(), href: jnHref });
function journalBindSection(arrived = true) {
  const sec = document.getElementById('journal'); if (!sec) return;
  sec.onclick = e => journalClick(e, sec);
  sec.querySelector('#jn-file').onchange = e => journalAdd(e.target);
  jnFillThumbs(sec);
  jnPhotoTidy(journalNow()).catch(() => {});
  if (arrived && location.hash === '#journal') journalFocus();   // saved/#journal, from a link
}
function journalFocus() {
  const sec = document.getElementById('journal'); if (!sec) return;
  sec.scrollIntoView({ block: 'start' }); sec.focus({ preventScroll: true });
}
function journalRedraw(say = '') {
  const sec = document.getElementById('journal'); if (!sec) return;
  sec.outerHTML = journalCard(say);
  journalBindSection(false);
  if (say) document.getElementById('jn-said').focus();
}
async function jnFillThumbs(sec) {
  jnUrls.forEach(u => URL.revokeObjectURL(u)); jnUrls = [];
  const imgs = [...sec.querySelectorAll('img[data-jn-thumb]')]; if (!imgs.length) return;
  let got; try { got = await jnPhotoGet(imgs.map(i => i.dataset.jnThumb)); } catch (e) { return; }
  for (const img of imgs) { const r = got[img.dataset.jnThumb]; if (!r || !img.isConnected) continue;
    const u = URL.createObjectURL(jnBlob(r, 'thumb')); jnUrls.push(u); img.src = u; }
}
function journalClick(e, sec) {
  const a = e.target.closest('a[data-jn-spot]');
  if (a) { if (typeof select === 'function' && (typeof plainClick !== 'function' || plainClick(e))) { e.preventDefault(); select(a.dataset.jnSpot, true); } return; }
  const t = e.target.closest('button'); if (!t || !sec.contains(t)) return;
  const said = sec.querySelector('#jn-said');
  if (t.id === 'jn-all') { JN_ALL = true; const rows = sec.querySelectorAll('#jn-list > [hidden]');
    if (typeof showRest === 'function') showRest(rows, t); else { rows.forEach(x => { x.hidden = false; }); t.remove(); } return; }
  if (t.dataset.jnPhoto) return jnShow(t);
  if (t.id === 'jn-export') return journalSave(t, said);
  if (t.id === 'jn-import') return sec.querySelector('#jn-file').click();
  if (t.id === 'jn-clear') {
    const n = journalNow().length, row = sec.querySelector('#jn-file-row');
    row.innerHTML = `<span class="rv-sure">Delete ${n === 1 ? 'the one swim' : `all ${n} swims`} and their photos from this device?</span> <button type="button" class="linkbtn" data-jn-wipe="1">Delete all</button> <button type="button" class="linkbtn" data-jn-keep="1">Keep them</button>`;
    row.querySelector('[data-jn-wipe]').focus(); return;
  }
  if (t.dataset.jnWipe) {
    const n = journalNow().length;
    if (!journalKeep([])) return journalRedraw('This browser would not let the journal change.');
    jnPhotoClear().catch(() => {});
    return journalRedraw(`Deleted ${n === 1 ? 'the one swim' : `all ${n} swims`} from this device.`);
  }
  if (t.dataset.jnDelete) {
    const p = t.parentElement;
    p.innerHTML = `<span class="rv-sure">Delete this swim${sec.querySelector(`[data-key="${CSS.escape(t.dataset.jnDelete)}"] .rv-pic`) ? ' and its photos' : ''}?</span> <button type="button" class="linkbtn small" data-jn-sure="${jnEsc(t.dataset.jnDelete)}">Delete it</button> <button type="button" class="linkbtn small" data-jn-keep="1">Keep it</button>`;
    p.querySelector('[data-jn-sure]').focus(); return;
  }
  if (t.dataset.jnKeep) return journalRedraw();
  if (t.dataset.jnSure) {
    const list = journalNow(), e2 = list.find(x => x.key === t.dataset.jnSure); if (!e2) return journalRedraw();
    if (!journalKeep(list.filter(x => x !== e2))) return journalRedraw('This browser would not let the journal change.');
    if (e2.photos) jnPhotoDel([e2.key]).catch(() => {});
    return journalRedraw(`Deleted the swim of ${jnEsc(jnDay(e2.date))}.`);
  }
}

// A photo at full size over the page, in the reviews' viewer's style (dialog.rv-view): its own dialog,
// since the photo is a file from IndexedDB, not one of the site's.
let jnViewer = null, jnViewUrl = '';
async function jnShow(btn) {
  let r; try { r = (await jnPhotoGet([btn.dataset.jnPhoto]))[btn.dataset.jnPhoto]; } catch (e) { r = null; }
  if (!r) return;
  if (jnViewUrl) URL.revokeObjectURL(jnViewUrl);
  jnViewUrl = URL.createObjectURL(jnBlob(r, 'full'));
  if (!window.HTMLDialogElement) { window.open(jnViewUrl, '_blank', 'noopener'); return; }
  if (!jnViewer) {
    jnViewer = document.createElement('dialog'); jnViewer.className = 'rv-view';
    jnViewer.innerHTML = `<button type="button" class="rv-close" aria-label="Close the photo">${JN_CLOSE}</button><figure><img alt=""><figcaption></figcaption></figure>`;
    jnViewer.addEventListener('click', e => { if (e.target === jnViewer || e.target.closest('.rv-close')) jnViewer.close(); });
    jnViewer.addEventListener('close', () => { jnViewer.querySelector('img').removeAttribute('src'); URL.revokeObjectURL(jnViewUrl); jnViewUrl = ''; });
    document.body.append(jnViewer);
  }
  const row = btn.closest('.jn');
  jnViewer.querySelector('img').src = jnViewUrl; jnViewer.querySelector('img').alt = btn.getAttribute('aria-label');
  jnViewer.querySelector('figcaption').textContent = row ? `${row.querySelector('.rv-v').textContent} · ${row.querySelector('.jn-where').textContent}` : '';
  jnViewer.showModal();
}

// Save a copy: a file on the device (a phone offers its share sheet, from which it can go to Files).
async function journalSave(t, said) {
  const list = journalNow(); if (!list.length) return;
  t.disabled = true;
  const keys = list.flatMap(e => Array.from({ length: e.photos }, (_, n) => `${e.key}-${n}`)), photos = {};
  try { const got = await jnPhotoGet(keys);
    for (const [k, r] of Object.entries(got)) photos[k] = { type: r.type, full: `data:${r.type};base64,${jnB64(r.full)}`, thumb: `data:${r.type};base64,${jnB64(r.thumb)}` };
  } catch (e) { /* the swims without their photos */ }
  const name = `${JOURNAL_FILE}-${jnLocal()}.json`, file = new File([journalFile(list, photos)], name, { type: 'application/json' });
  let how = 'saved';
  if (matchMedia('(pointer: coarse)').matches && navigator.canShare && navigator.canShare({ files: [file] })) {
    try { await navigator.share({ files: [file], title: 'Swim journal' }); how = 'shared'; } catch (e) { how = e.name === 'AbortError' ? '' : 'saved'; }
  }
  if (how === 'saved') { const a = document.createElement('a'); a.href = URL.createObjectURL(file); a.download = name; document.body.append(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000); }
  t.disabled = false;
  if (!how) return;
  const p = Object.keys(photos).length;
  said.hidden = false;
  said.textContent = `${how === 'saved' ? 'Saved' : 'Made'} ${name}: ${list.length === 1 ? 'one swim' : `${list.length} swims`}${p ? ` and ${p} photo${p === 1 ? '' : 's'}` : ''}. It holds your notes, so keep it somewhere private.`;
}
// Add swims from a copy: read on the device; the swims not already here are added with their photos.
async function journalAdd(input) {
  const f = input.files[0]; input.value = ''; if (!f) return;
  if (f.size > JOURNAL_LIMITS.file) return journalRedraw('That file is too large to be a journal copy.');
  let text = ''; try { text = await f.text(); } catch (e) { return journalRedraw('That file could not be read.'); }
  const got = journalRead(text);
  if (!got) return journalRedraw(`${jnEsc(f.name)} is not a copy of a SwimSignal journal.`);
  const have = journalNow(), r = journalMerge(have, got.swims);
  let lost = 0;
  for (const e of r.added) {
    if (!e.photos) continue;
    try { await jnPhotoPut(e.key, got.photos[e.key].slice(0, e.photos).map(p => ({ type: p.type, full: jnUnB64(p.full), thumb: jnUnB64(p.thumb) }))); }
    catch (err) { lost += e.photos; e.photos = 0; }
  }
  if (r.added.length && !journalKeep([...have, ...r.added])) return journalRedraw('This browser is not keeping site data, so nothing could be added.');
  const n = r.added.length, p = journalPhotoCount(r.added), s = k => (k === 1 ? '' : 's');
  const parts = [n ? `Added ${n} swim${s(n)}${p ? ` and ${p} photo${s(p)}` : ''} from ${jnEsc(f.name)}.` : `Nothing to add from ${jnEsc(f.name)}.`,
    r.same ? `${r.same} ${r.same === 1 ? 'was' : 'were'} here already.` : '',
    r.over ? `${r.over} left out: the journal keeps at most ${JOURNAL_LIMITS.swims} swims.` : '',
    r.photosLeft || lost ? `${r.photosLeft + lost} photo${s(r.photosLeft + lost)} left out: ${lost ? 'this browser would not keep them' : `the journal keeps at most ${JOURNAL_LIMITS.allPhotos}`}.` : ''];
  journalRedraw(parts.filter(Boolean).join(' '));
}

// Another tab logged or deleted a swim: the Saved page here follows.
if (typeof window !== 'undefined' && window.addEventListener) {
  window.addEventListener('storage', e => { if (e.key === JOURNAL_KEY && document.getElementById('journal')) journalRedraw(); });
}

if (typeof module === 'object' && module.exports) {
  module.exports = { JOURNAL_KEY, JOURNAL_LIMITS, JOURNAL_SHOW, journalEntry, journalEntries, journalSort, journalPhotoCount, journalSeen, journalSeenWords,
    journalSeenWhy, journalProblem, journalNew, jnPhotoOk, journalFile, journalRead, journalMerge, journalItem, journalSection, journalKeptHtml, journalFormHtml };
}
