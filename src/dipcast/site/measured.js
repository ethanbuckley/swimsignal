// Lab results an organisation sent: water samples it had taken at the spot and tested by a lab
// (samples/README.md, src/dipcast/samples.py). The build puts a spot's published ones from the last 30
// days in spots.json as `measured`, and this draws them in a tile of their own on the spot's page,
// apart from every forecast and estimate, and with who supplied them.
//
// What the tile says and does not. Each result: when it was taken (UK time), how long ago, the count
// per 100 ml, who sent it, and the lab and its method as the sender gives them; whether the lab is
// UKAS-accredited only as the sender says, never as SwimSignal's claim. That SwimSignal did not take or
// check the samples, and that they do not change the forecast: they are not part of the level (an EA
// sample is, levels.js, sampleLevel). Never "verified" or "safe". An E. coli count is set against 900
// per 100 ml, the line the E. coli estimate uses, with the About section's own words for what it is:
// the inland "sufficient" rating's threshold, worked out over four seasons, not a pass or fail for one
// sample. Intestinal enterococci have no line on the page, so their count stands alone. No colour: a
// colour on this page means a risk level, and a count is not one.
//
// A plain script, like guide.js: in the page its names are globals (each begins measured or MEASURED,
// clear of the page's own and the other scripts'), and in Node the last lines export them
// (tests/site_measured.test.cjs).

const MEASURED_DAYS = 30;   // as src/dipcast/samples.py's WINDOW_DAYS: older, a count says little about the water now
const MEASURED_SHOW = 3;    // results shown before "Show all", when at least two more would fold
const MEASURED_LINE = 900;  // E. coli per 100 ml: the E. coli estimate's line (levels.js, SAMPLE_LINE)
const MEASURED_TZ = 'Europe/London';
const measuredEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const measuredNum = v => (typeof v === 'number' && Number.isFinite(v) && v >= 0 ? v : null);
// A test tube, in the page's one stroke set (index.html, ICON): the EA rating's flask is the EA's samples.
const MEASURED_ICON = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M8.5 3h7M10 3v14.5a2 2 0 0 0 4 0V3"/><path d="M10 11.5h4"/></svg>';
// How old, as "What the level rests on" says it (evidence.js, evidenceAge): the page loads it before
// this file, Node requires it.
const measuredAge = (t, nowMs) => (typeof evidenceAge === 'function' ? evidenceAge : require('./evidence.js').evidenceAge)(t, nowMs);
const measuredYear = ms => new Intl.DateTimeFormat('en-GB', { timeZone: MEASURED_TZ, year: 'numeric' }).format(new Date(ms));
// "17 Oct" in UK time, with the year when it is not this one; "17 Oct, 08:30" with the time.
const measuredDay = (t, nowMs) => new Date(t).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: MEASURED_TZ,
  ...(measuredYear(t) === measuredYear(nowMs) ? {} : { year: 'numeric' }) });
const measuredWhen = (iso, nowMs) => `${measuredDay(Date.parse(iso), nowMs)}, `
  + new Date(Date.parse(iso)).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: MEASURED_TZ });

// "1,200", "under 10", "over 24,196": a count given as a limit says so.
function measuredCount(n, q) {
  const k = (Math.round(n * 10) / 10).toLocaleString('en-GB');
  return q === '<' ? `under ${k}` : q === '>' ? `over ${k}` : k;
}
// Against 900, as evidence.js's sample row and levels.js's sampleOver: a limit only where it settles it.
function measuredVs(n, q) {
  if (q === '<') return n <= MEASURED_LINE ? 'under 900' : '';
  if (q === '>') return n >= MEASURED_LINE ? 'over 900' : '';
  return n > MEASURED_LINE ? 'over 900' : n === MEASURED_LINE ? 'not over 900' : 'under 900';
}

// The spot's results from the last MEASURED_DAYS when the page is read, newest first: an old page kept
// offline does not go on showing a count as recent. Only the shapes the build writes.
function measuredRecent(d, nowMs) {
  const since = nowMs - MEASURED_DAYS * 864e5;
  return (Array.isArray(d && d.measured) ? d.measured : [])
    .filter(s => s && Number.isFinite(Date.parse(s.sampled_at)) && Date.parse(s.sampled_at) >= since && s.supplier
      && (measuredNum(s.ecoli) !== null || measuredNum(s.enterococci) !== null))
    .sort((a, b) => Date.parse(b.sampled_at) - Date.parse(a.sampled_at));
}

// What was found: "E. coli: 1,200 per 100 ml, over 900. Intestinal enterococci: under 10 per 100 ml."
function measuredSays(s) {
  const out = [];
  const e = measuredNum(s.ecoli), i = measuredNum(s.enterococci);
  if (e !== null) {
    const vs = measuredVs(e, s.ecoli_qualifier);
    out.push(`E.&nbsp;coli: ${measuredCount(e, s.ecoli_qualifier)} per 100&nbsp;ml${vs ? `, ${vs}` : ''}.`);
  }
  if (i !== null) out.push(`Intestinal enterococci: ${measuredCount(i, s.enterococci_qualifier)} per 100&nbsp;ml.`);
  return out.join(' ');
}

// Who says so: who sent it and when, then the lab, its accreditation in the sender's words, and the method.
function measuredSource(s, nowMs) {
  const who = measuredEsc(s.supplier);
  const sent = /^\d{4}-\d{2}-\d{2}$/.test(s.received || '') ? `, ${measuredDay(Date.parse(s.received + 'T12:00:00Z'), nowMs)}` : '';
  const ukas = s.ukas === true ? `, which ${who} says is UKAS-accredited` : s.ukas === false ? `, which ${who} says is not UKAS-accredited` : '';
  const lab = s.lab ? `Lab: ${measuredEsc(s.lab)}${ukas}.` : 'The lab is not named.';
  return `Sent by ${who}${sent}. ${lab}${s.method ? ` Method: ${measuredEsc(s.method)}.` : ''}`;
}

const measuredRow = (s, nowMs) => '<div class="factor">'
  + `<div class="f-l">Sampled ${measuredWhen(s.sampled_at, nowMs)}</div><div class="f-v">${measuredAge(s.sampled_at, nowMs)}</div>`
  + `<div class="f-d">${measuredSays(s)}</div><div class="f-src">${measuredSource(s, nowMs)}</div></div>`;

// The tile, in the spot's "at the water" part after the EA's rating (index.html, render). Nothing where
// there is no recent result: most spots have none, and a tile saying so on every page would be noise.
function measuredTile(d, nowMs) {
  if (!d || d.unlisted || d.detail_missing) return '';   // a point clicked on the map has none; a missing file is not "none"
  const rows = measuredRecent(d, nowMs);
  if (!rows.length) return '';
  const fold = rows.length > MEASURED_SHOW + 1, ecoli = rows.some(s => measuredNum(s.ecoli) !== null);
  return `<section class="tile" id="measured" aria-labelledby="measured-h"><h2 class="t-lab" id="measured-h">${MEASURED_ICON}<span>Measured: lab results sent to SwimSignal</span></h2>`
    + '<p class="t-say">Water samples taken here and tested by a lab, sent to SwimSignal by the organisation named under each result. '
    + 'SwimSignal did not take or check the samples, and they do not change the forecast.</p>'
    + `<div class="factors">${(fold ? rows.slice(0, MEASURED_SHOW) : rows).map(s => measuredRow(s, nowMs)).join('')}`
    // The rest in a box of their own: a row is a grid, which the hidden attribute alone would not hide.
    + (fold ? `<div class="m-more" hidden>${rows.slice(MEASURED_SHOW).map(s => measuredRow(s, nowMs)).join('')}</div>` : '') + '</div>'
    + (fold ? `<button type="button" class="btn quiet" id="m-all" aria-expanded="false">Show all ${rows.length} results</button>` : '')
    + '<div class="ev-gap"><p>Each count is for the moment its sample was taken: after rain it can change within hours.</p>'
    + (ecoli ? `<p>900 per 100&nbsp;ml is the line the <a href="#about-ecoli">E.&nbsp;coli estimate</a> uses: the threshold in the inland "sufficient" rating, `
      + 'which is worked out over four seasons, not a pass or fail for one sample.</p>' : '')
    + '</div></section>';
}

// "Show all": the rest show and the button goes, as the guide's (guide.js, showRest).
function measuredClick(e) {
  const t = e.target && e.target.closest ? e.target.closest('#m-all') : null; if (!t) return;
  const rows = t.closest('#measured').querySelectorAll('.m-more[hidden]');
  if (typeof showRest === 'function') showRest(rows, t); else { rows.forEach(x => { x.hidden = false; }); t.remove(); }
}
if (typeof document === 'object' && document.addEventListener) document.addEventListener('click', measuredClick);

if (typeof module === 'object' && module.exports) {
  module.exports = { MEASURED_DAYS, MEASURED_SHOW, MEASURED_LINE, measuredTile, measuredRecent, measuredSays, measuredSource, measuredCount, measuredVs, measuredWhen, measuredClick };
}
