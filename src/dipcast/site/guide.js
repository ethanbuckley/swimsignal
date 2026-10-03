// A spot's practical guide: where to park, the path to the water, where to get in and out, toilets,
// changing, fees and opening times. The build reads guides/<spot id>.toml (src/dipcast/guides.py,
// guides/README.md) into spots.json, and this draws it as one tile after the forecast's.
//
// Every fact says who says so. Verified: the landowner's, operator's or council's own page (linked),
// or seen on site by SwimSignal (status "confirmed" in the files). A swimmer's suggestion: who and
// when, and that it has not been checked. The two are told apart in words, not colour: a colour on
// this page means a risk level. "Verified" is the word the notes on a visit (visits.js) use for a
// fact checked against an official source; there "confirmed" means a swimmer saying it is still so.
//
// A plain script, like reviews.js: in the page its names are globals (each begins guide or GUIDE,
// clear of the page's own), and in Node the last lines export them (tests/site_guide.test.cjs).

// The topics in the order a swimmer meets them, as src/dipcast/guides.py lists them.
const GUIDE_TOPICS = [['parking', 'Parking'], ['path', 'Path to the water'], ['entry', 'Getting in'], ['exit', 'Getting out'],
  ['toilets', 'Toilets'], ['changing', 'Changing'], ['fees', 'Fees and booking'], ['hours', 'Opening times'], ['rules', 'Who can swim']];
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
// guide's first line gives the day they were checked), or the day it was seen; a swimmer's
// suggestion says who, when, and that it is not checked.
function guideSource(x) {
  if (x.status === 'suggested') {
    return `<span class="g-who">A swimmer's suggestion</span>, from ${guideEsc(x.from)}, ${guideDay(x.on)}. Not yet checked by SwimSignal.`;
  }
  const parts = [];
  if (guideHttps(x.source)) parts.push(`<a href="${guideEsc(x.source)}">${guideEsc(x.source_name || 'Source')}</a>`);
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
  const topics = GUIDE_TOPICS.filter(([k]) => by.has(k)), fold = topics.length > GUIDE_SHOW + 1;
  return '<dl class="g-facts">' + topics.map(([k, label], i) => `<div class="g-row"${fold && i >= GUIDE_SHOW ? ' hidden' : ''}><dt>${label}</dt>`
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
  const gaps = GUIDE_TOPICS.filter(([k]) => !have.has(k)).map(([, label]) => label.toLowerCase());
  return gaps.length ? `<p class="g-gap">Not in this guide yet: ${gaps.join(', ')}.</p>` : '';
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
    : guideSource(p);
  return `<figure class="g-photo"><div class="g-pic" style="aspect-ratio:${w} / ${h}">`
    + `<img src="guides/photos/${p.file}" width="${w}" height="${h}" loading="lazy" decoding="async" alt="${alt}">${pins}</div>`
    + `<figcaption>${key}<p class="g-cap">${guideEsc(p.caption)} Photo: ${guideEsc(p.credit)}, ${guideDay(p.taken)}.</p>`
    + `<p class="g-src">${by}</p></figcaption></figure>`;
}

// What to do when the guide is wrong or has a gap: the feedback page, set to a guide, with the spot.
const guideAsk = (d, has) => `<p class="g-ask">${has ? 'Something here wrong or out of date, or missing?' : 'Know this spot?'} `
  + `<a href="feedback.html?type=guide&amp;spot=${encodeURIComponent(d.name || '')}">${has ? 'Tell us' : 'Tell us where you parked, the way down, and where you got in and out'}</a>; photos are welcome.</p>`;

// The tile. Without a guide, a short one asking for what a swimmer knows: that is how a guide starts.
function guideTile(d, today) {
  if (!d || d.unlisted) return '';   // a point clicked on the map (anypoint.js) is not a spot anyone has guided
  const g = d.guide;
  const head = `<h2 class="t-lab" id="guide-h">${guideIcon()}<span>Practical guide</span></h2>`;
  if (!g || !Array.isArray(g.facts) || !g.facts.length) {
    return `<section class="tile g-tile" id="guide" aria-labelledby="guide-h">${head}`
      + '<p class="t-say">No guide for this spot yet: parking, the path to the water, where to get in and out, toilets and fees.</p>'
      + guideAsk(d, false) + '</section>';
  }
  return `<section class="tile g-tile" id="guide" aria-labelledby="guide-h">${head}`
    + `<p class="t-say">${guideChecked(g, today)}</p>`
    + guideFacts(g) + guideGaps(g)
    + (g.photos || []).map((p, i) => guidePhoto(p, i, g)).join('')
    + guideAsk(d, true) + '</section>';
}

if (typeof module === 'object' && module.exports) {
  module.exports = { GUIDE_TOPICS, GUIDE_STALE_DAYS, GUIDE_SHOW, guideTile, guideChecked, guideSource, guideRuns, guideFacts, guideGaps, guidePhoto, guideDays, guideClick, showRest };
}
