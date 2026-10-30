// A spot's practical guide: where to park, the path to the water, where to get in and out, toilets,
// changing, fees and opening times. The build reads guides/<spot id>.toml (src/dipcast/guides.py,
// guides/README.md) into spots.json, and this draws it as one tile after the forecast's.
//
// Every fact says who says so. Verified: the landowner's, operator's or council's own page (linked),
// or seen on site by SwimSignal (status "confirmed" in the files). A swimmer's suggestion: who and
// when, and that it has not been checked. The two are told apart in words, not colour: a colour on
// this page means a risk level. "Verified" is the word the notes on a visit (visits.js) use for a
// fact checked against an official source; there "confirmed" means a swimmer saying it is still so.
// A fact from a dated record (source_date, a consultation's month, say) is as that record listed it,
// not a current check, so it says "Source" and the month instead of "Verified".
//
// A plain script, like reviews.js: in the page its names are globals (each begins guide or GUIDE,
// clear of the page's own), and in Node the last lines export them (tests/site_guide.test.cjs).

// The topics in the order a swimmer meets them, as src/dipcast/guides.py lists them.
const GUIDE_TOPICS = [['parking', 'Parking'], ['transport', 'Bus and train'], ['path', 'Path to the water'], ['entry', 'Getting in'], ['exit', 'Getting out'],
  ['toilets', 'Toilets'], ['changing', 'Changing'], ['fees', 'Fees and booking'], ['hours', 'Opening times'], ['rules', 'Who can swim'],
  ['launch', 'Launching a boat or board'], ['carry', 'Carrying to the water'], ['paddle', 'Paddling here']];
// The topics for boats and boards (guides.py, TOPICS): shown where a guide has them, never listed as missing.
const GUIDE_PADDLE = new Set(['launch', 'carry', 'paddle']);
// Bus and train (30 October 2026): shown where a guide has it, and not listed as missing here either, since the
// guides written before it would all grow the same new gap. The arrival guide (arrive.js, ?arrive=1) does list it.
const GUIDE_OPTIONAL = new Set(['transport']);
const GUIDE_STALE_DAYS = 365;   // fees, hours and paths change: older than this, the guide says so
const GUIDE_SHOW = 4;           // topics shown before "Show all", when at least two more would fold
const guideEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const guideDay = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
const guideIcon = () => (typeof ICON === 'object' && ICON.route) || '';
const guideHttps = u => /^https:\/\/[^\s<>"']+$/.test(String(u || ''));
// Only these shapes reach the page: the build checks them, and this checks again before writing a
// file name or a number into an attribute.
const guideFile = f => /^[a-z0-9][a-z0-9-]{0,78}\.jpe?g$/.test(String(f || ''));
const guideNum = (v, lo, hi) => { const n = Number(v); return Number.isFinite(n) && n >= lo && n <= hi ? n : null; };

// "2026-02" as "February 2026": a dated record's month (source_date).
const guideMonth = ym => /^\d{4}-(0[1-9]|1[0-2])$/.test(String(ym || ''))
  ? new Date(ym + '-15T12:00:00').toLocaleDateString('en-GB', { month: 'long', year: 'numeric' }) : '';

// Days between two ISO dates, b minus a.
const guideDays = (a, b) => Math.round((Date.parse(b + 'T12:00:00Z') - Date.parse(a + 'T12:00:00Z')) / 864e5);

// "Checked 3 Oct 2026 from the published pages linked below, not on site." The one line that says
// how far to trust the whole guide, and, past a year, that it may be out of date.
function guideChecked(g, today) {
  const when = guideDay(g.checked);
  if (![...(g.facts || []), ...(g.photos || [])].some(x => x.status === 'confirmed')) {
    return `Swimmers' suggestions only, gathered up to ${when}: nothing here has been checked by SwimSignal yet.`;
  }
  const line = g.how === 'visit' ? `Checked on site ${when}.` : `Checked ${when} from the published pages linked below, not on site.`;
  const old = today && guideDays(g.checked, today) > GUIDE_STALE_DAYS
    ? ' That is over a year ago: fees, opening times and paths may have changed.' : '';
  return line + old;
}

// Under a fact or a photo: who says so. A verified fact names the page it came from, linked (the
// guide's first line gives the day they were checked), or the day it was seen; a fact from a dated
// record names the page and the record's month, as "Source", not "Verified"; a swimmer's
// suggestion says who, when, and that it is not checked.
function guideSource(x) {
  if (x.status === 'suggested') {
    return `<span class="g-who">A swimmer's suggestion</span>, from ${guideEsc(x.from)}, ${guideDay(x.on)}. Not yet checked by SwimSignal.`;
  }
  const parts = [];
  if (guideHttps(x.source)) parts.push(`<a href="${guideEsc(x.source)}">${guideEsc(x.source_name || 'Source')}</a>`);
  const month = guideMonth(x.source_date);
  if (month && parts.length) return `<span class="g-who">Source</span>: ${parts[0]}, ${month}.`;
  if (x.seen) parts.push(`seen on site ${guideDay(x.seen)}`);
  return `<span class="g-who">Verified</span>: ${parts.join('; ')}.`;
}

const guideMap = f => {
  const lat = guideNum(f.lat, -90, 90), lon = guideNum(f.lon, -180, 180);
  return lat === null || lon === null ? ''
    : ` <a href="https://www.openstreetmap.org/?mlat=${lat}&amp;mlon=${lon}#map=17/${lat}/${lon}">On a map</a>.`;
};

// One topic's facts in runs: facts in a row whose line of who says so is the same share it, once,
// after the last of them. The line compared is the one a reader sees, so a run never joins a
// suggestion to a verified fact, two pages, or two days; and it never spans two topics.
function guideRuns(facts) {
  const runs = [];
  for (const f of facts) {
    const src = guideSource(f) + guideMap(f), last = runs[runs.length - 1];
    if (last && last.src === src) last.texts.push(f.text); else runs.push({ src, texts: [f.text] });
  }
  return runs;
}

// The facts as a ruled list: each topic's heading, then its facts, verified first (src/dipcast/guides.py
// sorts them). Past five topics the first four show and "Show all 7 topics" opens the rest, as the
// reviews' and the notes' "Show all" do; at five or fewer all show, so the button never hides one.
function guideFacts(g) {
  const by = new Map();
  for (const f of g.facts || []) { if (!by.has(f.topic)) by.set(f.topic, []); by.get(f.topic).push(f); }
  // Who can swim stays in view wherever it falls (30 October 2026): with bus and train a sixth topic, Cromwheel's
  // rules went behind "Show all", and permission is the one thing a first-time reader must not have to open.
  const topics = GUIDE_TOPICS.filter(([k]) => by.has(k)), shown = (k, i) => i < GUIDE_SHOW || k === 'rules';
  const fold = topics.filter(([k], i) => !shown(k, i)).length >= 2;
  return '<dl class="g-facts">' + topics.map(([k, label], i) => `<div class="g-row"${fold && !shown(k, i) ? ' hidden' : ''}><dt>${label}</dt>`
    + guideRuns(by.get(k)).map(r => `<dd>${r.texts.map(t => `<p class="g-text">${guideEsc(t)}</p>`).join('')}<p class="g-src">${r.src}</p></dd>`).join('')
    + '</div>').join('') + '</dl>'
    + (fold ? `<button type="button" class="btn quiet" id="g-all" aria-expanded="false">Show all ${topics.length} topics</button>` : '');
}

// "Show all" in the guide, the notes (visits.js) and the reviews (reviews.js): the rest show, the button
// goes, and focus moves to the first one shown, so a keyboard or screen reader is not left on nothing.
function showRest(rows, button) {
  const first = rows[0];
  rows.forEach(x => { x.hidden = false; });
  button.remove();
  if (first && first.focus) { first.tabIndex = -1; first.focus(); }
}

// The page writes the tile as text (index.html), so one listener on the document opens the rest for
// any spot. As in reviews.js and visits.js, the rows show and the button goes.
function guideClick(e) {
  const t = e.target && e.target.closest ? e.target.closest('#g-all') : null; if (!t) return;
  showRest(t.closest('#guide').querySelectorAll('.g-row[hidden]'), t);
}
if (typeof document === 'object' && document.addEventListener) document.addEventListener('click', guideClick);

// "Not in this guide yet: toilets, changing." So a missing topic reads as unknown, not as none.
function guideGaps(g) {
  const have = new Set((g.facts || []).map(f => f.topic));
  const gaps = GUIDE_TOPICS.filter(([k]) => !have.has(k) && !GUIDE_PADDLE.has(k) && !GUIDE_OPTIONAL.has(k)).map(([, label]) => label.toLowerCase());
  return gaps.length ? `<p class="g-gap">Not in this guide yet: ${gaps.join(', ')}.</p>` : '';
}

// A historical photo (status "historical", guides.py): someone else's published photograph under an open licence,
// Geograph's under CC BY-SA 2.0. Its line names the photographer, the day it was taken, its title linked to its page,
// the licence linked to its deed, what was changed, and that the copy here is under the same licence. Then, beside it
// every time, what it cannot show: it is not SwimSignal's, and it shows that day, not today's access, permission,
// water level or conditions. A licence the page does not know is not linked or named.
const GUIDE_LICENCES = { 'https://creativecommons.org/licenses/by-sa/2.0/': 'CC BY-SA 2.0' };
function guideHistorical(p) {
  const lic = GUIDE_LICENCES[p.licence], page = guideHttps(p.source)
    ? `<a href="${guideEsc(p.source)}">${guideEsc(p.title || 'the photo')}</a> on ${guideEsc(p.source_name || 'its publisher')}` : guideEsc(p.title || '');
  const terms = lic ? ` Licensed under <a href="${guideEsc(p.licence)}">${lic}</a>; ${guideEsc(String(p.changes || '').replace(/[.\s]+$/, ''))}. `
    + `This copy is also under ${lic}.` : '';
  return `<span class="g-who">Historical photo</span> by ${guideEsc(p.credit)}, taken ${guideDay(p.taken)}: ${page}.${terms} `
    + 'Not taken by SwimSignal. It shows that day only, not today\'s access, permission, water level or conditions.';
}

// A photo at the tile's width, its numbered labels placed on it, and the key beneath: a number on the
// picture, the same number in the list. The box holds the photo's shape while it loads.
function guidePhoto(p, i, g) {
  if (!guideFile(p.file)) return '';
  const w = guideNum(p.w, 1, 4000) || 4, h = guideNum(p.h, 1, 4000) || 3;
  const labels = (p.labels || []).map(l => ({ x: guideNum(l.x, 0, 100), y: guideNum(l.y, 0, 100), text: l.text })).filter(l => l.x !== null && l.y !== null);
  const pins = labels.map((l, n) => `<span class="g-pin" style="left:${l.x}%;top:${l.y}%" aria-hidden="true">${n + 1}</span>`).join('');
  const key = labels.length ? `<ol class="g-key">${labels.map(l => `<li>${guideEsc(l.text)}</li>`).join('')}</ol>` : '';
  const alt = guideEsc(String(p.caption || '').replace(/[.\s]+$/, '')) + (labels.length ? `. Labelled: ${labels.map((l, n) => `${n + 1}, ${guideEsc(l.text)}`).join('; ')}.` : '.');
  const by = p.status === 'suggested' ? `A swimmer's photo, from ${guideEsc(p.from)}; the labels are theirs and not yet checked.`
    : p.status === 'historical' ? guideHistorical(p) : guideSource(p);
  return `<figure class="g-photo"><div class="g-pic" style="aspect-ratio:${w} / ${h}">`
    + `<img src="guides/photos/${p.file}" width="${w}" height="${h}" loading="lazy" decoding="async" alt="${alt}">${pins}</div>`
    + `<figcaption>${key}<p class="g-cap">${guideEsc(p.caption)}${p.status === 'historical' ? '' : ` Photo: ${guideEsc(p.credit)}, ${guideDay(p.taken)}.`}</p>`
    + `<p class="g-src">${by}</p></figcaption></figure>`;
}

// What to do when the guide is wrong or has a gap: the feedback page, set to a guide, with the spot.
const guideAsk = d => '<p class="g-ask">Something here wrong or out of date, or missing? '
  + `<a href="feedback.html?type=guide&amp;spot=${encodeURIComponent(d.name || '')}">Tell us</a>; photos are welcome.</p>`;

// One tile for what swimmers have not added yet: with no guide, no recent notes and no reviews, three
// tiles would each say so, on nearly every page. "Know this spot?" holds a line
// for each section with nothing in it, in the order the tiles come; a section with something keeps its
// own tile. The guide's line is written with the page; the notes' and the reviews' join once their file
// says they have none (visits.js, reviews.js, knowAdd), and their button opens that section's form.
const KNOW = ['guide', 'visits', 'reviews'];
function knowItem(kind, d) {
  if (kind === 'guide') return `<li data-know="guide"><a href="feedback.html?type=guide&amp;spot=${encodeURIComponent(d.name || '')}">Add a practical guide</a>`
    + '<span>Where you parked, the way down, where you got in and out. Photos are welcome.</span></li>';
  if (kind === 'visits') return '<li data-know="visits"><button type="button" class="linkbtn">Say what it\'s like today</button>'
    + '<span>A note on the day: getting in, parking, how busy it was. It ends after a few days.</span></li>';
  return '<li data-know="reviews"><button type="button" class="linkbtn">Write a review</button>'
    + '<span>Whether you would swim here again, and what it was like. Checked before it appears.</span></li>';
}
const knowTile = (d, kinds, id = 'know') => `<section class="tile know" id="${id}" aria-labelledby="know-h">`
  + `<h2 class="t-lab" id="know-h">${guideIcon()}<span>Know this spot?</span></h2>`
  + `<ul class="know-list">${KNOW.filter(k => kinds.includes(k)).map(k => knowItem(k, d)).join('')}</ul></section>`;

// The guide's tile. Without a guide, the shared tile with the guide's line, in the guide's place
// (id guide: the notes and the reviews mount after it).
function guideTile(d, today) {
  if (!d || d.unlisted) return '';   // a point clicked on the map (anypoint.js) is not a spot anyone has guided
  if (d.detail_missing) return '';   // its guide is in data/spot/<id>.json, which did not arrive: not "no guide yet"
  const g = d.guide;
  if (!g || !Array.isArray(g.facts) || !g.facts.length) return knowTile(d, ['guide'], 'guide');
  const head = `<h2 class="t-lab" id="guide-h">${guideIcon()}<span>Practical guide</span></h2>`;
  return `<section class="tile g-tile" id="guide" aria-labelledby="guide-h">${head}`
    + `<p class="t-say">${guideChecked(g, today)}</p>`
    + guideFacts(g) + guideGaps(g)
    + (g.photos || []).map((p, i) => guidePhoto(p, i, g)).join('')
    + guideAsk(d) + '</section>';
}

// In the page: a section's line in the shared tile, the tile made after the last community tile if
// there is none; `open` runs on its button. False where the page has no place for it.
function knowAdd(kind, d, open) {
  const stack = document.querySelector('#result .stack'); if (!stack) return false;
  let tile = stack.querySelector('.know');   // in the stack or in one of a desktop's columns
  if (!tile) {
    const after = ['#reviews', '#visits', '#guide', '.tiles'].map(q => stack.querySelector(q)).find(Boolean);
    if (!after) return false;
    after.insertAdjacentHTML('afterend', knowTile(d, [])); tile = after.nextElementSibling;
  }
  const list = tile.querySelector('.know-list');
  let li = list.querySelector(`[data-know="${kind}"]`);
  if (!li) {
    const box = document.createElement('ul'); box.innerHTML = knowItem(kind, d); li = box.firstChild;
    list.insertBefore(li, [...list.children].find(x => KNOW.indexOf(x.dataset.know) > KNOW.indexOf(kind)) || null);
  }
  const b = li.querySelector('button'); if (b) b.onclick = open;
  return true;
}
// A section given a tile of its own: its tile goes after the shared one, its line goes, and the
// shared tile with its last line.
function knowOpen(kind, sec) {
  const li = document.querySelector(`#result .know [data-know="${kind}"]`); if (!li) return false;
  const tile = li.closest('.know'), next = kind === 'visits' && document.getElementById('reviews');
  if (next) next.before(sec); else (kind === 'reviews' && document.getElementById('visits') || tile).after(sec);
  li.remove(); if (!tile.querySelector('li')) tile.remove();
  return true;
}

if (typeof module === 'object' && module.exports) {
  module.exports = { GUIDE_TOPICS, GUIDE_PADDLE, GUIDE_OPTIONAL, GUIDE_STALE_DAYS, GUIDE_SHOW, guideTile, knowTile, KNOW, guideChecked, guideSource, guideRuns, guideFacts, guideGaps, guidePhoto, guideHistorical, GUIDE_LICENCES, guideDays, guideClick, showRest };
}
