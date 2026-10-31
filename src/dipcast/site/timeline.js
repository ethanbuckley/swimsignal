// The evidence timeline: one dated list on a spot's page, newest first, of everything the site already holds about
// the water there. Official notices, the Environment Agency's lab samples and algae checks, lab results an
// organisation sent, a partner group's samples (Waterhead first, docs/PARTNER-SAMPLES-CONTRACT-v1.md), satellite
// index readings where the spot's lake has them, swimmers' notes on a visit, and the forecast itself. A fold in the
// "more" column, closed when the page draws: opening it fetches the files it needs, once a page view, so a reader
// who never opens it costs nothing.
//
// Each line says what kind of thing it is, in words, never a colour or a badge:
//  - Measurement: a laboratory or an instrument measured something (a sample's count, a satellite index);
//  - Report: what someone saw or published (an official notice, the EA sampler's look at algae, a swimmer's note);
//  - Forecast: worked out ahead by SwimSignal, not observed.
// Then whose it is, and its review status: whether anyone checked it, and who. The rules it keeps
// (docs/PARTNER-PROGRAMME-2026-11.md, AGENTS.md):
//  - A swimmer's note is always a report. Suspected pollution or algae says "Suspected" and "what one swimmer saw, not
//    a water test", even after the operator matched it to an official source: the source's own notice is the warning,
//    and the line points to it.
//  - A satellite reading is a dated index, never a toxin measurement, a chlorophyll concentration or a swimming
//    clearance. Days with no clear image are not listed, and the foot says a missing image is not a clear result.
//  - A count below a method's limit is said as "below 10", never 0; a partner's recorded 0 whose meaning is not
//    confirmed says so.
//  - Nothing here changes the level, and the forecast's own line says it is not a measurement.
//
// A plain script, like measured.js: in the page its names are globals (each begins timeline or TIMELINE), and in
// Node the last lines export them (tests/site_timeline.test.cjs).

const TIMELINE_SHOW = 12;   // lines before "Show all"
const TIMELINE_TZ = 'Europe/London';
const TIMELINE_KINDS = { measurement: 'Measurement', report: 'Report', forecast: 'Forecast' };
const TIMELINE_ORDER = { measurement: 0, report: 1, forecast: 2 };   // on one day: what was measured, then said, then forecast
const timelineEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const timelineNum = v => (typeof v === 'number' && Number.isFinite(v) && v >= 0 ? v : null);
const timelineIsDay = v => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && new Date(v + 'T12:00:00Z').toISOString().slice(0, 10) === v;
// The UK day of an instant with its offset, or a plain day as it is.
const timelineDay = t => timelineIsDay(t) ? t : Number.isFinite(Date.parse(t))
  ? new Intl.DateTimeFormat('en-CA', { timeZone: TIMELINE_TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(Date.parse(t))) : null;
// "13 Sept 2026": always with the year, since the list runs over several.
const timelineDate = day => new Date(day + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
// How old, as "What the level rests on" says it (evidence.js): the page loads it before this file, Node requires it.
const timelineAge = (day, nowMs) => (typeof evidenceAge === 'function' ? evidenceAge : require('./evidence.js').evidenceAge)(day, nowMs);
// The ticks of a note on a visit (visits.js): its words and tones, so the two cannot drift apart.
const timelineTicks = () => (typeof VISIT_KINDS === 'object' ? VISIT_KINDS : require('./visits.js').VISIT_KINDS);
// A count in words, with its qualifier: "below 10", "above 2,419.6", "520".
function timelineCount(n, q) {
  const k = (Math.round(n * 10) / 10).toLocaleString('en-GB');
  return q === '<' ? `below ${k}` : q === '>' ? `above ${k}` : k;
}
// "E. coli 520 and intestinal enterococci below 10, per 100 ml." Empty without either count.
function timelineCounts(e, eq, i, iq) {
  const parts = [];
  if (timelineNum(e) !== null) parts.push(`E.&nbsp;coli ${timelineCount(e, eq)}`);
  if (timelineNum(i) !== null) parts.push(`intestinal enterococci ${timelineCount(i, iq)}`);
  return parts.length ? `${parts.join(' and ').replace(/^./, c => c.toUpperCase())}, per 100&nbsp;ml.` : '';
}

// ------------------------------------------------------------------------------ the items, one source at a time
// Each returns a list of { day, kind, what, says, source, status }, every string already HTML (escaped here).

// The forecast: one line, the issue, so the list says plainly what is worked out rather than seen.
function timelineForecast(d, generatedAt) {
  const day = timelineDay(generatedAt);
  if (!day || !Array.isArray(d.days) || !d.days.length || d.error) return [];
  return [{ day, kind: 'forecast', what: "SwimSignal's five-day forecast",
    says: 'The pollution risk shown above, worked out from rain forecasts and overflow records. Not a measurement of the water.',
    source: 'SwimSignal', status: 'A forecast: no one has measured the water for it' }];
}

// Official notices (spots.json `official`, eatoday.js): the publisher's words, its start, and when it was last checked.
function timelineOfficial(d) {
  const ok = typeof eaTodayAdvice === 'function' ? eaTodayAdvice(d) : (Array.isArray(d.official) ? d.official : []).filter(o => o && o.line && o.publisher);
  const checked = o => typeof eaTodayChecked === 'function' ? eaTodayChecked(o) : '';
  return ok.filter(o => timelineIsDay(o.since)).map(o => ({ day: o.since, kind: 'report',
    what: o.restricts === true ? 'Official advice' : 'Official notice', says: timelineEsc(o.line),
    source: /^https:\/\/[^\s"<>]+$/.test(o.link || '') ? `<a href="${timelineEsc(o.link)}">${timelineEsc(o.publisher)}</a>` : timelineEsc(o.publisher),
    status: `Read and checked against the ${timelineEsc(o.publisher)}'s own record by SwimSignal. ${timelineEsc(checked(o))}`.trim() }));
}

// The EA sampler's look at algae (spots.json `algae`): a report, since it is a look, not a lab test.
function timelineAlgae(d) {
  const a = d.algae;
  if (!a || !timelineIsDay(a.date) || !a.phrase) return [];
  return [{ day: a.date, kind: 'report', what: 'Algae check', says: `${timelineEsc(String(a.phrase).replace(/^./, c => c.toUpperCase()))}.`,
    source: 'Environment Agency', status: "The sampler's look at the water, as the Environment Agency records it: not a lab test" }];
}

// The Environment Agency's lab samples: every one in the research export (data/research/ecoli/<id>.json, samples.js)
// where the file came, else the latest in spots.json (`lab_sample`).
function timelineAgency(d, ecoli) {
  const src = `<a href="samples.html#spot=${timelineEsc(d.id)}">Environment Agency</a>`;
  const rows = ecoli && Array.isArray(ecoli.samples) ? ecoli.samples.map(s => ({ t: s.t, e: s.ecoli, eq: s.q, i: s.ie, iq: s.ie_q }))
    : d.lab_sample && d.lab_sample.ecoli !== null && d.lab_sample.ecoli !== '' && d.lab_sample.ecoli !== undefined
      ? [{ t: d.lab_sample.taken_at, e: Number(d.lab_sample.ecoli), eq: d.lab_sample.qualifier, i: null, iq: null }] : [];
  return rows.filter(s => timelineDay(s.t) && timelineCounts(s.e, s.eq, s.i, s.iq)).map(s => ({ day: timelineDay(s.t), at: s.t, kind: 'measurement',
    what: 'Lab sample', says: timelineCounts(s.e, s.eq, s.i, s.iq), source: ecoli ? src : 'Environment Agency',
    status: 'Official bathing water sample, as the Environment Agency publishes it' }));
}

// Lab results an organisation sent (spots.json `measured`, measured.js): the last 30 days only, as the build gives them.
function timelineMeasured(d) {
  return (Array.isArray(d.measured) ? d.measured : []).filter(s => s && s.supplier && timelineDay(s.sampled_at)
    && timelineCounts(s.ecoli, s.ecoli_qualifier, s.enterococci, s.enterococci_qualifier))
    .map(s => ({ day: timelineDay(s.sampled_at), at: s.sampled_at, kind: 'measurement', what: 'Lab result sent to SwimSignal',
      says: timelineCounts(s.ecoli, s.ecoli_qualifier, s.enterococci, s.enterococci_qualifier),
      source: `${timelineEsc(s.supplier)}${s.lab ? `; lab: ${timelineEsc(s.lab)}` : ''}${s.method ? `; method: ${timelineEsc(s.method)}` : ''}`,
      status: `Sent by ${timelineEsc(s.supplier)}. SwimSignal did not take or check the sample` }));
}

// A partner group's samples (data/research/local-samples.json names the file; for Waterhead, waterhead_wet.json):
// every sample, each with who took it. A recorded 0 is said as recorded, with what is not known about it.
function timelinePartner(link, doc) {
  if (!link || !doc || !Array.isArray(doc.samples) || !link.by) return [];
  const page = /^[a-z0-9-]+\.html$/.test(link.href || '') ? link.href : null;
  const by = timelineEsc(link.by);
  return doc.samples.filter(s => timelineIsDay(s.date) && timelineCounts(s.ecoli, null, s.ie, null)).map(s => ({ day: s.date, kind: 'measurement',
    what: `Sample by ${by}`,
    says: timelineCounts(s.ecoli, null, s.ie, null) + (s.ecoli === 0 || s.ie === 0 ? ' A recorded 0 may mean below the lab\'s detection limit, not none.' : ''),
    source: page ? `<a href="${page}">${by}</a>` : by,
    status: `Published with ${by}'s permission. SwimSignal did not take or check the sample` }));
}

// Satellite index readings round a point on the spot's lake (data/research/lake/<id>.json, lakes.js): one a date, the
// primary reading. Never harmful algae, toxins or a clearance; a reading outside May to September is experimental.
function timelineSatellite(lake) {
  if (!lake || !Array.isArray(lake.series)) return [];
  return lake.series.filter(r => r && r.primary && timelineIsDay(r.date) && typeof r.ndci === 'number' && Number.isFinite(r.ndci))
    .map(r => ({ day: r.date, at: r.datetime, kind: 'measurement', what: 'Satellite colour index (NDCI)',
      says: `${r.ndci.toFixed(2)}, from a Sentinel-2 image of the water round a point on ${timelineEsc(lake.water_body || 'the lake')}.`
        + (r.experimental || r.season === 'out_of_season' ? ' Outside May to September: experimental.' : ''),
      source: '<a href="lakes.html">Copernicus Sentinel-2, read by SwimSignal</a>',
      status: 'A research index of green pigment seen from space: not a toxin measurement, and not a sign the water is safe' }));
}

// Swimmers' notes on a visit still showing (reviews/index.json `visits`, visits.js): always a report.
function timelineVisits(d, index, nowMs) {
  const K = timelineTicks(), today = timelineDay(new Date(nowMs).toISOString());
  const live = v => typeof visitLive === 'function' ? visitLive(v, today)
    : (Array.isArray(v.kinds) ? v.kinds.filter(k => Object.hasOwn(K, k)) : []).filter(() => !v.until || v.until >= today);
  return (index && Array.isArray(index.visits) ? index.visits : []).filter(v => v && v.spot === d.id && timelineIsDay(v.seen_on))
    .map(v => ({ v, ticks: live(v) })).filter(x => x.ticks.length).map(({ v, ticks }) => {
      const seen = ticks.filter(k => K[k].tone === 'observation');
      const words = ticks.map(k => K[k].say).join('; ');   // "Suspected pollution", never the verified word
      const matched = seen.length && v.verified ? ` SwimSignal matched it to ${timelineEsc(v.verified)}: follow that source's own notice.` : '';
      return { day: v.seen_on, kind: 'report', what: "A swimmer's note",
        says: `${timelineEsc(words)}.${v.text ? ` “${timelineEsc(v.text)}”` : ''}${seen.length ? ' What one swimmer saw, not a water test.' : ''}${matched}`,
        source: 'A swimmer, unnamed',
        status: v.text || (Array.isArray(v.photos) && v.photos.length) ? 'Read by SwimSignal before it was published; not checked at the water'
          : 'Ticks from a fixed list, published as sent; not checked' };
    });
}

// Every item, newest first; on one day, measurements, then reports, then the forecast.
function timelineItems(d, files, nowMs, generatedAt) {
  const f = files || {};
  const all = [...timelineForecast(d, generatedAt), ...timelineOfficial(d), ...timelineAlgae(d), ...timelineAgency(d, f.ecoli),
    ...timelineMeasured(d), ...timelinePartner(f.partnerLink, f.partner), ...timelineSatellite(f.lake), ...timelineVisits(d, f.reviews, nowMs)];
  return all.filter(x => x.day).sort((a, b) => b.day.localeCompare(a.day) || TIMELINE_ORDER[a.kind] - TIMELINE_ORDER[b.kind]
    || String(b.at || '').localeCompare(String(a.at || '')));
}

// ------------------------------------------------------------------------------ the fold
const TIMELINE_ICON = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4v16"/><circle cx="6" cy="7" r="1.6"/><circle cx="6" cy="17" r="1.6"/><path d="M10 7h9M10 12h7M10 17h9"/></svg>';
let TIMELINE_SPOT = null, TIMELINE_LOADED = null;

const timelineRow = (x, nowMs) => '<div class="factor">'
  + `<div class="f-l">${TIMELINE_KINDS[x.kind]} · ${timelineDate(x.day)}</div><div class="f-v">${timelineAge(x.day, nowMs)}</div>`
  + `<div class="f-d"><b>${x.what}.</b> ${x.says}</div><div class="f-src">${x.source}. ${x.status}.</div></div>`;

// The list once its files are in: the newest TIMELINE_SHOW, the rest behind "Show all", then what is not listed.
function timelineBody(d, files, nowMs, generatedAt) {
  const items = timelineItems(d, files, nowMs, generatedAt), fold = items.length > TIMELINE_SHOW + 1;
  const sat = files && files.lake && Array.isArray(files.lake.series);
  return (items.length ? `<div class="factors">${(fold ? items.slice(0, TIMELINE_SHOW) : items).map(x => timelineRow(x, nowMs)).join('')}`
      + (fold ? `<div class="m-more" hidden>${items.slice(TIMELINE_SHOW).map(x => timelineRow(x, nowMs)).join('')}</div>` : '') + '</div>'
      + (fold ? `<button type="button" class="btn quiet" id="tl-all" aria-expanded="false">Show all ${items.length}</button>` : '')
    : '<p class="t-say">Nothing dated is held for this spot yet.</p>')
    + '<div class="ev-gap"><p>Each measurement is for the moment it was taken: the water can change within hours after rain.</p>'
    + (sat ? '<p>Satellite days with no clear image are not listed. A missing image is not a clear result: it says nothing about algae.</p>' : '')
    + '<p>Nothing here changes the level. A swimmer\'s note is never a verified warning: official notices are.</p></div>';
}

// The fold, closed, for the page's "more" column (index.html, render). Not on a point clicked on the map.
function timelineTile(d) {
  if (!d || d.unlisted || !/^[A-Za-z0-9_-]+$/.test(d.id || '')) return '';
  TIMELINE_SPOT = d; TIMELINE_LOADED = null;
  return `<details class="tile fold" id="timeline" data-spot="${timelineEsc(d.id)}"><summary><span class="t-lab" id="timeline-h">${TIMELINE_ICON}<span>Evidence timeline</span></span></summary>`
    + '<p class="t-say">Everything dated SwimSignal holds about the water here, newest first: what was measured, what was reported, and the forecast, each with whose it is and who checked it.</p>'
    + '<div id="tl-body"><p class="t-say">Loading…</p></div></details>';
}

// The files a spot's list needs, each only where it can exist, each null when it does not come.
function timelineFiles(d) {
  const get = p => fetch(p, { cache: 'no-cache' }).then(r => (r.ok ? r.json() : null)).catch(() => null);
  const partner = d.kind === 'lake' ? get('data/research/local-samples.json').then(ix => {
    const link = ix && ix.available && (ix.spots || {})[d.id];
    return link && /^data\/research\/[a-z0-9_-]+\.json$/.test(link.data || '') ? get(link.data).then(doc => ({ link, doc })) : null;
  }) : Promise.resolve(null);
  const reviews = typeof reviewsLoad === 'function' ? reviewsLoad().catch(() => null) : get('reviews/index.json');
  return Promise.all([d.sample_history ? get(`data/research/ecoli/${d.id}.json`) : null,
    d.kind === 'lake' && /^bw-/.test(d.id) ? get(`data/research/lake/${d.id}.json`) : null, partner, reviews])
    .then(([ecoli, lake, p, rv]) => ({ ecoli, lake, partnerLink: p && p.link, partner: p && p.doc, reviews: rv && rv.visits ? rv : null }));
}

function timelineOpen(e) {
  const t = e.target;
  if (!t || t.id !== 'timeline' || !t.open || !TIMELINE_SPOT || t.dataset.spot !== TIMELINE_SPOT.id || TIMELINE_LOADED) return;
  const d = TIMELINE_SPOT;
  TIMELINE_LOADED = timelineFiles(d).then(files => {
    const box = document.getElementById('tl-body');
    if (box && TIMELINE_SPOT === d) box.innerHTML = timelineBody(d, files, Date.now(), typeof DATA === 'object' && DATA ? DATA.generated_at : null);
  });
}
function timelineClick(e) {
  const t = e.target && e.target.closest ? e.target.closest('#tl-all') : null; if (!t) return;
  const rows = t.closest('#timeline').querySelectorAll('.m-more[hidden]');
  if (typeof showRest === 'function') showRest(rows, t); else { rows.forEach(x => { x.hidden = false; }); t.remove(); }
}
if (typeof document === 'object' && document.addEventListener) {
  document.addEventListener('toggle', timelineOpen, true);   // a details element's toggle does not bubble: caught on the way down
  document.addEventListener('click', timelineClick);
}

if (typeof module === 'object' && module.exports) {
  module.exports = { TIMELINE_SHOW, timelineItems, timelineBody, timelineTile, timelineCount, timelineCounts, timelineForecast, timelineOfficial,
    timelineAlgae, timelineAgency, timelineMeasured, timelinePartner, timelineSatellite, timelineVisits };
}
