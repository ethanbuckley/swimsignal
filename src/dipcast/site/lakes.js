// Satellite lake observations (lakes.html, linked from the Research page): what the research export holds for each
// monitoring location (docs/LAKE-OBSERVATIONS-CONTRACT-v1.md, version 1.1), read from the files the build splits it
// into (build_site.write_lake_observations): data/research/lakes.json, every location without its readings, and
// data/research/lake/<id>.json, one location whole.
//
// What it may say is the contract's, and only that: a dated satellite reading of an index (NDCI) round a point on a
// lake, how many images were clear enough to read, and how old the latest is. Never harmful algae, toxins, "clear" or
// "safe", never a chlorophyll concentration, never swimming advice: the export's own `claim.public_wording` stands
// beside every reading, and its `not_claimed` list is said in full. A laboratory value is a measurement and is shown
// apart, in its own unit, never on the same axis as the index.
//
// The dataset is historical: it runs to the date its images were read to (`processed_to`, per location, extended
// where a refresh has been applied), so its newest reading is the latest in the dataset, not the latest image there
// is. How old a reading is goes by the image's own date against today's (UK), never by the export's own age, so a
// frozen file cannot stay "recent". A reading from outside May to September (`season` out_of_season) is experimental:
// the index was tested against algae and chlorophyll only in those months, so it is labelled and drawn apart.
//
// A location is a 300 m circle of water round a point, not a lake: several can share one water body
// (`water_body_key`, `shares_water_body_with`), so they are counted as locations and their sharing is said.
//
// A plain script, like replay.js: in the page its names are globals (each begins lakes or LAKES), and in Node the last
// lines export them (tests/site_lakes.test.cjs).

const LAKES_TZ = 'Europe/London';
const lakesEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const lakesISO = ms => new Intl.DateTimeFormat('en-CA', { timeZone: LAKES_TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(ms));
const lakesDays = (a, b) => Math.round((Date.parse(b + 'T12:00:00Z') - Date.parse(a + 'T12:00:00Z')) / 864e5);   // b minus a
// "30 Sept 2026"; "30 Sept 2026, 11:26 UTC" for an image's own time (its acquisition time, in UTC as the source gives it).
const lakesDate = iso => new Date(iso.slice(0, 10) + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const lakesTime = iso => `${lakesDate(iso)}, ${new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })} UTC`;
const lakesNum = (v, dp = 2) => (typeof v === 'number' && Number.isFinite(v) ? v.toFixed(dp).replace(/^-0\.00$/, '0.00') : '');
const lakesPct = v => `${Math.round(v * 100)}%`;
const lakesPlural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

// ------------------------------------------------------------------------------ how old
// Days since the latest reading (UK dates), and the contract's word for it: recent, older, stale; none without one.
function lakesFresh(latest, todayISO, rules) {
  if (!latest || !latest.date) return { age: null, freshness: 'none' };
  const age = Math.max(0, lakesDays(latest.date, todayISO)), r = rules || {};
  return { age, freshness: age <= (r.recent_days ?? 14) ? 'recent' : age <= (r.older_days ?? 60) ? 'older' : 'stale' };
}
const lakesAgeWords = n => n === 0 ? 'today' : n === 1 ? 'yesterday' : `${n} days ago`;
const LAKES_FRESH_WORDS = { recent: 'recent', older: 'older', stale: 'stale: more than two months old', none: 'no usable image' };
// The date a location's images were read to: its own (a refresh extends it), else the export's.
const lakesTo = (lake, doc) => (lake && lake.processed_to) || ((doc && doc.processing) || {}).processed_to || null;
// Why there is no reading, or no recent one: the contract's fixed reasons, in plain words.
function lakesReason(r, doc, lake) {
  const to = lakesTo(lake, doc);
  return {
    too_small: "The water here is too narrow for the satellite's 20 m pixels, so no reading is made.",
    no_usable_scene: 'Images were taken, but cloud, haze or shadow covered too much of the water in every one.',
    season_closed: 'Images are read for May to September, the season the index was tested in, so the latest here is from the last season.',
    not_refreshed: `No images after ${to ? lakesDate(to) : 'the export'} have been read here.`,
    series_partial: 'Only images within a day of a laboratory sample were read here, so this is not a full record of every image.',
  }[r] || '';
}
const LAKES_EXCLUDED = { invalid_band_values: 'invalid band values', snow_or_ice_in_core: 'snow or ice on the water', sun_too_low: 'the sun too low',
  core_not_classed_water: 'too little of the water classed as water' };

// ------------------------------------------------------------------------------ the list
// The locations in the order the picker shows them: bathing waters, whose every image was read, then other monitoring
// points, read only near their lab samples; by name within each. Each group as [heading, locations].
const lakesSelected = lake => lake.series_scope !== 'every_scene';
function lakesGroups(index) {
  const by = (a, b) => String(a.name).localeCompare(String(b.name), 'en-GB');
  const all = (index && index.lakes) || [];
  return [['Designated bathing waters: every image read', all.filter(x => !lakesSelected(x)).sort(by)],
    ['Other monitoring points: images near lab samples only', all.filter(lakesSelected).sort(by)]].filter(([, g]) => g.length);
}
function lakesPicker(index, sel) {
  return `<label class="lk-pick">Monitoring location<select id="lk-select"><option value="">Choose a location</option>${lakesGroups(index).map(([h, g]) => `<optgroup label="${lakesEsc(h)}">`
    + g.map(x => `<option value="${lakesEsc(x.lake_id)}"${x.lake_id === sel ? ' selected' : ''}>${lakesEsc(x.name)}${x.water_body && x.water_body !== x.name && !String(x.name).includes(x.water_body) ? ` (${lakesEsc(x.water_body)})` : ''}</option>`).join('')
    + '</optgroup>').join('')}</select></label>`;
}

// ------------------------------------------------------------------------------ one location
// The latest reading in the dataset: its image's own time and how old it is now, the index value with the clear share it
// rests on, and the approved sentence beside it; an out-of-season reading said to be experimental. Then every reason the
// export gives for a gap. A series of images chosen near laboratory sample dates is a historical selection: its headline
// says "in this historical dataset", and the selection is said beside it, before any figure.
const LAKES_SELECTED = 'Images here were chosen near laboratory sample dates, so this is a selection, not every image: its readings and season medians are not full monitoring of the lake.';
const LAKES_EXPERIMENTAL = 'Taken outside May to September: an experimental reading. The index was tested against chlorophyll and algae only in May to September, so nothing about either is read from it.';
function lakesLatest(lake, doc, todayISO) {
  const L = lake.latest || {}, f = lakesFresh(L.date ? L : null, todayISO, doc.freshness_rules), sel = lakesSelected(lake);
  // The partial series is said beside the headline; a season closed is not, where the latest is itself out of season.
  const reasons = (L.reasons || []).filter(r => !(sel && r === 'series_partial') && !(L.experimental && r === 'season_closed'))
    .map(r => lakesReason(r, doc, lake)).filter(Boolean);
  const scope = sel ? `<p class="lk-scope-sel">${LAKES_SELECTED}</p>` : '';
  const why = reasons.length ? `<ul class="lk-reasons">${reasons.map(r => `<li>${lakesEsc(r)}</li>`).join('')}</ul>` : '';
  if (!L.date) return `<p class="lk-none"><b>No usable satellite reading at this location.</b></p>` + scope + why;
  return `<p class="lk-latest"><b>${sel ? 'Latest in this historical dataset' : 'Latest in this dataset'}: ${lakesEsc(lakesTime(L.datetime || L.date))}</b>, ${lakesAgeWords(f.age)} (${lakesEsc(LAKES_FRESH_WORDS[f.freshness])}).</p>`
    + scope + (L.experimental ? `<p class="lk-exp">${LAKES_EXPERIMENTAL}</p>` : '')
    + `<p class="lk-value">NDCI <b>${lakesNum(L.ndci)}</b>, the median over the clear water within 300 m (${lakesPct(L.clear_share)} of it clear in that image).</p>`
    + `<p class="lk-claim">${lakesEsc((doc.claim || {}).public_wording)}</p>` + why;
}
// The seasons from the first to the last, with any year between that has no images said as such rather than left out
// (2022 has none in the collection read): [{year, missing}] or the export's own season.
function lakesYears(seasons) {
  const by = new Map((seasons || []).map(y => [+y.year, y])), ys = [...by.keys()].sort();
  if (!ys.length) return [];
  const out = [];
  for (let y = ys[0]; y <= ys[ys.length - 1]; y++) out.push(by.get(y) || { year: y, missing: true });
  return out;
}
// Each season: images over the site, how many were clear enough, and the median of those readings.
function lakesSeasons(lake) {
  const s = lakesYears(lake.seasons), sel = lakesSelected(lake);
  if (!s.length) return '';
  return `<table class="lk-seasons"><caption>${sel ? 'The selected images each season (near laboratory sample dates, not every image)' : 'Images read each season, May to September'}</caption><thead><tr><th scope="col">Year</th><th scope="col">${sel ? 'Selected images' : 'Images'}</th><th scope="col">Clear enough</th><th scope="col">${sel ? 'Median of these' : 'Median NDCI'}</th><th scope="col">First and last clear</th></tr></thead><tbody>`
    + s.map(y => y.missing ? `<tr><th scope="row">${y.year}</th><td colspan="4">No images read this season.</td></tr>` : `<tr><th scope="row">${y.year}</th><td>${y.scenes}</td><td>${y.usable} (${lakesPct(y.usable_share || 0)})</td><td>${y.usable ? lakesNum(y.median_ndci) : 'none'}</td><td>${y.first ? `${lakesEsc(lakesDate(y.first)).replace(/ \d{4}$/, '')} to ${lakesEsc(lakesDate(y.last)).replace(/ \d{4}$/, '')}` : 'none'}</td></tr>`).join('')
    + '</tbody></table>';
}
// The readings shown, one a date (`primary`: the test's own rule picks it where two images share a date; a series from
// before 1.1 has no `primary`, and all of it is shown).
const lakesShown = series => (series || []).filter(p => p && p.date && typeof p.ndci === 'number' && p.primary !== false);
// The readings as dots, one row a season, each row on the same months, so a cloudy summer shows as few dots, not as a
// line drawn across it. May to September, widened to any month a reading falls in; an out-of-season reading is a
// hollow dot. The index's own scale, no conversion; the zero line drawn.
const LAKES_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function lakesChart(series, width, selected = false) {
  const pts = lakesShown(series);
  if (!pts.length) return '';
  const seen = [...new Set(pts.map(p => +p.date.slice(0, 4)))].sort(), years = [];
  for (let y = seen[0]; y <= seen[seen.length - 1]; y++) years.push(y);   // a year between with no reading keeps its row, empty
  const months = pts.map(p => +p.date.slice(5, 7)), m0 = Math.min(5, ...months), m1 = Math.max(9, ...months);
  const lo = Math.min(-0.1, ...pts.map(p => p.ndci)), hi = Math.max(0.2, ...pts.map(p => p.ndci));
  const W = Math.max(260, Math.min(720, width || 600)), padL = 44, padR = 8, rowH = 54, gap = 14, H = years.length * (rowH + gap) + 24;
  const span = (y, m) => Date.parse(`${y}-${String(m).padStart(2, '0')}-01T00:00Z`);
  const x = d => { const y = +d.slice(0, 4), t0 = span(y, m0), t1 = m1 === 12 ? span(y + 1, 1) : span(y, m1 + 1);
    return padL + (W - padL - padR) * Math.min(1, Math.max(0, (Date.parse(d + 'T12:00Z') - t0) / (t1 - t0))); };
  const yv = (v, r) => r * (rowH + gap) + rowH - (rowH * (v - lo)) / (hi - lo);
  let g = '';
  years.forEach((yr, r) => {
    const top = r * (rowH + gap);
    g += `<text x="0" y="${top + rowH / 2 + 4}" class="lk-yr">${yr}</text><rect x="${padL}" y="${top}" width="${W - padL - padR}" height="${rowH}" class="lk-band"/>`
      + (lo < 0 && hi > 0 ? `<line x1="${padL}" x2="${W - padR}" y1="${yv(0, r).toFixed(1)}" y2="${yv(0, r).toFixed(1)}" class="lk-zero"/>` : '')
      + (seen.includes(yr) ? '' : `<text x="${padL + 8}" y="${top + rowH / 2 + 4}" class="lk-mo">No clear image this season</text>`)
      + pts.filter(p => +p.date.slice(0, 4) === yr).map(p => `<circle cx="${x(p.date).toFixed(1)}" cy="${yv(p.ndci, r).toFixed(1)}" r="3" class="${p.experimental ? 'lk-dot-exp' : 'lk-dot'}"><title>${lakesEsc(lakesDate(p.date))}: NDCI ${lakesNum(p.ndci)}${p.experimental ? ', out of season, experimental' : ''}</title></circle>`).join('');
  });
  const bottom = years.length * (rowH + gap), mx = m => padL + (W - padL - padR) * (span(2001, m) - span(2001, m0)) / ((m1 === 12 ? span(2002, 1) : span(2001, m1 + 1)) - span(2001, m0));
  for (let m = m0; m <= m1; m++) g += `<text x="${mx(m).toFixed(1)}" y="${bottom + 10}" class="lk-mo">${LAKES_MONTHS[m - 1]}</text>`;
  const exp = pts.filter(p => p.experimental).length;
  const label = `NDCI readings by date, ${lakesPlural(pts.length, 'clear image')} in ${lakesPlural(seen.length, 'season')}, ranging from ${lakesNum(Math.min(...pts.map(p => p.ndci)))} to ${lakesNum(Math.max(...pts.map(p => p.ndci)))}${exp ? `, ${exp} of them out of season and experimental` : ''}. The seasons table above gives the same in words.`;
  return `<figure class="lk-fig"><svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${lakesEsc(label)}">${g}</svg>`
    + `<figcaption>Each dot is one clear image's reading; each row is one year.${exp ? ' Hollow dots are from outside May to September, experimental.' : ''}${selected ? ' Only images near laboratory sample dates were read, so gaps between dots are not gaps in the satellite record, and the dots are not a trend for the lake.' : ''} Higher means greener-looking water, on the index's own scale (${lakesNum(lo)} to ${lakesNum(hi)} here). It is not a chlorophyll measurement.</figcaption></figure>`;
}
// How far one reading can be trusted, measured on the data (the export's `quality`): two images of one location on one
// date. Said under the dots, so a small step between two of them is not read as a change in the water.
function lakesQuality(doc) {
  const q = doc.quality;
  if (!q || typeof q.same_date_abs_difference_median !== 'number') return '';
  return `<p class="lk-quality">Two readings of one location on the same date differ by ${lakesNum(q.same_date_abs_difference_median)} in the middle case, and by ${lakesNum(q.same_date_abs_difference_p90)} or more one time in ten (${q.same_date_pairs} pairs). So a small change between dates may be the measurement, not the water.</p>`;
}
// A refresh applied here: what was read, and the clear images not shown and why. An image left out is not an observation.
function lakesRefreshed(lake) {
  const rs = lake.refreshes || [], ex = lake.excluded || [];
  if (!rs.length && !ex.length) return '';
  const why = Object.entries(ex.reduce((a, e) => ({ ...a, [e.reason]: (a[e.reason] || 0) + 1 }), {}))
    .map(([r, n]) => `${n} for ${LAKES_EXCLUDED[r] || r.replace(/_/g, ' ')}`).join(', ');
  return `<p class="lk-refresh">${rs.map(r => `Images from ${lakesEsc(lakesDate(r.from))} to ${lakesEsc(lakesDate(r.to))} were read later: ${lakesPlural(r.scenes, 'image')}, ${r.shown} shown.`).join(' ')}`
    + `${ex.length ? ` ${lakesPlural(ex.length, 'clear image')} left out (${lakesEsc(why)}): not shown, and not an observation of the water.` : ''}</p>`;
}
// Laboratory values, measured, apart: their own heading, unit and definition, never mixed with the index.
function lakesLab(lake, doc) {
  const lab = lake.lab || [], d = doc.lab_definition || {};
  if (!lab.length) return '';
  const rows = [...lab].sort((a, b) => String(b.sample_time).localeCompare(String(a.sample_time)));
  return `<section class="lk-lab" aria-labelledby="lk-lab-h"><h3 id="lk-lab-h">Measured in a laboratory</h3>`
    + `<p>${lakesEsc(d.target || 'Chlorophyll')}, ${lakesEsc(d.unit || '')}, from water samples taken here (${lakesEsc(d.source || 'Environment Agency')}). ${lakesEsc(d.method_note || '')} These are measurements; the satellite index above is not, and the two are not on one scale.</p>`
    + `<table class="lk-labt"><thead><tr><th scope="col">Sampled</th><th scope="col">${lakesEsc(d.unit || 'Value')}</th></tr></thead><tbody>`
    + rows.slice(0, 12).map(r => `<tr><td>${lakesEsc(lakesDate(String(r.sample_time)))}</td><td>${r.censored === '<' ? `below ${lakesEsc(r.value)}` : r.censored === '>' ? `above ${lakesEsc(r.value)}` : lakesEsc(r.value)}</td></tr>`).join('')
    + `</tbody></table>${rows.length > 12 ? `<p class="lk-more">The 12 most recent of ${rows.length} samples.</p>` : ''}</section>`;
}
// The other locations on this water body, by name (from the index): they share imagery and weather.
function lakesShares(lake, index) {
  const ids = lake.shares_water_body_with || [];
  if (!ids.length) return '';
  const names = ids.map(id => ((index && index.lakes) || []).find(x => x.lake_id === id)).filter(Boolean)
    .map(x => `<a href="#lake=${lakesEsc(encodeURIComponent(x.lake_id))}">${lakesEsc(x.name)}</a>`);
  return `<p class="lk-shares">${lakesEsc(lake.water_body)} has ${lakesPlural(ids.length, 'other location')} here${names.length ? `: ${names.join(', ')}` : ''}. They share images and weather, so they are not independent readings of separate lakes.</p>`;
}
// One location whole.
function lakesLake(lake, doc, todayISO, width, index = null) {
  const spot = lake.site_ids && lake.site_ids.bathing_water ? `<a href="spot/${lakesEsc(lake.lake_id)}/">Its pollution forecast</a>` : '';
  const to = lakesTo(lake, doc);
  const scope = lakesSelected(lake) ? '' : `Every image from May to September was read here${to ? `, up to ${lakesDate(to)}` : ''}.`;
  return `<article class="lk-lake"><h2 id="lk-h">${lakesEsc(lake.name)}</h2>`
    + `<p class="lk-meta">${[lake.water_body, lake.lake_type ? `${lake.lake_type} lake${lake.depth_m ? `, mean depth about ${lakesNum(lake.depth_m, 0)} m` : ''}` : '', spot].filter(Boolean).join(' · ')}</p>`
    + lakesLatest(lake, doc, todayISO) + (scope ? `<p class="lk-scope">${lakesEsc(scope)}</p>` : '') + lakesRefreshed(lake) + lakesShares(lake, index || doc)
    + lakesSeasons(lake) + lakesChart(lake.series, width, lakesSelected(lake)) + lakesQuality(doc) + lakesLab(lake, doc) + '</article>';
}
// What the file is, over the whole list: monitoring locations (each a 300 m circle of water round a point; several can
// share one lake, so they are not counted as lakes), how many named waters they are on, how many have a reading, the
// date the images were read to (and where a refresh took one further), and the newest image with its age today.
function lakesSummary(index, todayISO) {
  if (!index || !index.available) return `<p class="lk-none">No satellite observations are published in this update${index && index.why ? ` (${lakesEsc(index.why)})` : ''}.</p>`;
  const L = index.lakes || [], withR = L.filter(x => x.latest && x.latest.date), newest = withR.map(x => x.latest.date).sort().pop();
  // Water bodies among the locations listed: by the export's water_body_key (1.1), else by the water's name.
  const bodies = new Set(L.map(x => String(x.water_body_key || x.water_body || x.lake_id).toLowerCase())).size;
  const full = L.filter(x => !lakesSelected(x)).length, base = (index.processing || {}).processed_to;
  const later = L.filter(x => x.processed_to && base && x.processed_to > base);
  return `<p class="lk-sum">${lakesPlural(L.length, 'monitoring location')} on ${lakesPlural(bodies, 'named water')}; ${withR.length} have a usable reading. Every image was read at ${full} of them; at the other ${L.length - full === 1 ? 'one' : L.length - full}, only images near laboratory sample dates.`
    + `${base ? ` This is a historical dataset: images are read up to ${lakesEsc(lakesDate(base))}${later.length ? `, and to ${lakesEsc(lakesDate(later.map(x => x.processed_to).sort().pop()))} at ${lakesPlural(later.length, 'location')} read again later` : ''}. Nothing after that is in it.` : ''}`
    + `${newest ? ` The newest image is from ${lakesEsc(lakesDate(newest))}, ${lakesAgeWords(lakesDays(newest, todayISO))}.` : ''}</p>`;
}

// ------------------------------------------------------------------------------ in the page
function lakesMount(root) {
  const host = root.getElementById('lakes'), today = lakesISO(Date.now());
  if (!host) return;
  const get = p => fetch(p, { cache: 'no-cache' }).then(r => (r.ok ? r.json() : null)).catch(() => null);
  get('data/research/lakes.json').then(index => {
    if (!index) { host.innerHTML = '<p class="lk-none">The satellite observations could not be loaded.</p>'; return; }
    const claim = root.getElementById('lk-claim'), not = root.getElementById('lk-not'), attrib = root.getElementById('lk-attrib');
    if (claim && index.claim) claim.textContent = index.claim.public_wording;
    if (not && index.claim && index.claim.not_claimed) not.innerHTML = index.claim.not_claimed.map(t => `<li>${lakesEsc(t)}</li>`).join('');
    if (attrib && Array.isArray(index.attribution) && index.attribution.length) attrib.textContent = index.attribution.join('. ').replace(/\.?$/, '.');
    const pickId = () => decodeURIComponent((location.hash.match(/^#lake=([A-Za-z0-9_-]+)$/) || [])[1] || '');
    const draw = () => {
      const id = pickId();
      host.innerHTML = lakesSummary(index, today) + (index.available ? lakesPicker(index, id) + '<div id="lk-one"></div>' : '');
      const sel = root.getElementById('lk-select');
      if (sel) sel.addEventListener('change', () => { location.hash = sel.value ? `lake=${encodeURIComponent(sel.value)}` : ''; });
      const one = root.getElementById('lk-one');
      if (!one || !id || !(index.lakes || []).some(x => x.lake_id === id)) return;
      one.innerHTML = '<p class="lk-none">Loading…</p>';
      get(`data/research/lake/${encodeURIComponent(id)}.json`).then(lake => {
        if (pickId() !== id) return;
        one.innerHTML = lake ? lakesLake(lake, index, today, one.clientWidth, index) : '<p class="lk-none">This location could not be loaded.</p>';
      });
    };
    window.addEventListener('hashchange', draw);
    draw();
  });
}
if (typeof document === 'object' && document.getElementById) lakesMount(document);

if (typeof module === 'object' && module.exports) {
  module.exports = { lakesYears, lakesShown, lakesQuality, lakesRefreshed, lakesShares, LAKES_SELECTED, LAKES_EXPERIMENTAL, lakesSelected, LAKES_FRESH_WORDS,
    lakesFresh, lakesReason, lakesGroups, lakesPicker, lakesLatest, lakesSeasons, lakesChart, lakesLab, lakesLake, lakesSummary, lakesDate, lakesTime, lakesISO };
}
