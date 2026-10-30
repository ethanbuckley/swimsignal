// Satellite lake observations (lakes.html, linked from the Research page): what the research export holds for each
// lake site (docs/LAKE-OBSERVATIONS-CONTRACT-v1.md, version 1), read from the files the build splits it into
// (build_site.write_lake_observations): data/research/lakes.json, every lake without its readings, and
// data/research/lake/<id>.json, one lake whole.
//
// What it may say is the contract's, and only that: a dated satellite reading of an index (NDCI) at a lake, how many
// images were clear enough to read, and how old the latest is. Never harmful algae, toxins, "clear" or "safe", never a
// chlorophyll concentration, never swimming advice: the export's own `claim.public_wording` stands beside every
// reading, and its `not_claimed` list is said in full. A laboratory value is a measurement and is shown apart, in its
// own unit, never on the same axis as the index.
//
// How old a reading is goes by the image's own date against today's (UK), not by when the file was made: a page read
// in March says a September image is stale even if the export is a day old. The day limits are the export's own
// (freshness_rules).
//
// A plain script, like replay.js: in the page its names are globals (each begins lakes or LAKES), and in Node the last
// lines export them (tests/site_lakes.test.cjs).

const LAKES_TZ = 'Europe/London';
const lakesEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const lakesISO = ms => new Intl.DateTimeFormat('en-CA', { timeZone: LAKES_TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(ms));
const lakesDays = (a, b) => Math.round((Date.parse(b + 'T12:00:00Z') - Date.parse(a + 'T12:00:00Z')) / 864e5);   // b minus a
// "30 Sep 2026"; "30 Sep 2026, 11:26 UTC" for an image's own time (its acquisition time, in UTC as the source gives it).
const lakesDate = iso => new Date(iso.slice(0, 10) + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const lakesTime = iso => `${lakesDate(iso)}, ${new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })} UTC`;
const lakesNum = (v, dp = 2) => (typeof v === 'number' && Number.isFinite(v) ? v.toFixed(dp).replace(/^-0\.00$/, '0.00') : '');
const lakesPct = v => `${Math.round(v * 100)}%`;
const LAKES_SOURCE = 'https://github.com/ethanbuckley/swimsignal/blob/main/docs/';

// ------------------------------------------------------------------------------ how old
// Days since the latest usable image (UK dates), and the export's word for it: recent, older, stale; none without one.
function lakesFresh(latest, todayISO, rules) {
  if (!latest || !latest.date) return { age: null, freshness: 'none' };
  const age = Math.max(0, lakesDays(latest.date, todayISO)), r = rules || {};
  return { age, freshness: age <= (r.recent_days ?? 14) ? 'recent' : age <= (r.older_days ?? 60) ? 'older' : 'stale' };
}
const lakesAgeWords = n => n === 0 ? 'today' : n === 1 ? 'yesterday' : `${n} days ago`;
const LAKES_FRESH_WORDS = { recent: 'recent', older: 'older', stale: 'stale: more than two months old', none: 'no usable image' };
// Why there is no reading, or no recent one: the contract's fixed reasons, in plain words.
function lakesReason(r, doc) {
  const p = (doc && doc.processing) || {};
  return {
    too_small: "The water here is too narrow for the satellite's 20 m pixels, so no reading is made.",
    no_usable_scene: 'Images were taken, but cloud, haze or shadow covered too much of the water in every one.',
    season_closed: 'Images are read for May to September only, so the latest is from the last season.',
    not_refreshed: `No newer images have been read since this export${p.processed_to ? `, which runs to ${lakesDate(p.processed_to)}` : ''}.`,
    series_partial: 'Only images within a day of a laboratory sample were read here, so this is not a full record of every image.',
  }[r] || '';
}

// ------------------------------------------------------------------------------ the list
// The lakes in the order the picker shows them: bathing waters, whose every image was read, then other monitoring
// points, read only near their lab samples; by name within each. Each group as [heading, lakes].
function lakesGroups(index) {
  const by = (a, b) => String(a.name).localeCompare(String(b.name), 'en-GB');
  const all = (index && index.lakes) || [];
  return [['Designated bathing waters: every image read', all.filter(x => x.series_scope === 'every_scene').sort(by)],
    ['Other monitoring points: images near lab samples only', all.filter(x => x.series_scope !== 'every_scene').sort(by)]].filter(([, g]) => g.length);
}
function lakesPicker(index, sel) {
  return `<label class="lk-pick">Monitoring location<select id="lk-select"><option value="">Choose a location</option>${lakesGroups(index).map(([h, g]) => `<optgroup label="${lakesEsc(h)}">`
    + g.map(x => `<option value="${lakesEsc(x.lake_id)}"${x.lake_id === sel ? ' selected' : ''}>${lakesEsc(x.name)}${x.water_body && x.water_body !== x.name && !String(x.name).includes(x.water_body) ? ` (${lakesEsc(x.water_body)})` : ''}</option>`).join('')
    + '</optgroup>').join('')}</select></label>`;
}

// ------------------------------------------------------------------------------ one lake
// The latest reading: its image's own time and how old it is now (counted today, from the image's date, so a file that
// is never refreshed can never stay "recent"), the index value with the clear share it rests on, and the approved
// sentence beside it. Then every reason the export gives for a gap. A series of images chosen near laboratory sample
// dates (series_scope near_lab_samples) is a historical selection, not the satellite record: its headline says "in this
// historical dataset", and the selection is said beside it, before any figure.
const lakesSelected = lake => lake.series_scope !== 'every_scene';
const LAKES_SELECTED = 'Images here were chosen near laboratory sample dates, so this is a selection, not every image: its readings and season medians are not full monitoring of the lake.';
function lakesLatest(lake, doc, todayISO) {
  const L = lake.latest || {}, f = lakesFresh(L.date ? L : null, todayISO, doc.freshness_rules), sel = lakesSelected(lake);
  const reasons = (L.reasons || []).filter(r => !(sel && r === 'series_partial')).map(r => lakesReason(r, doc)).filter(Boolean);
  const scope = sel ? `<p class="lk-scope-sel">${LAKES_SELECTED}</p>` : '';
  if (!L.date) return `<p class="lk-none"><b>No usable satellite reading at this location.</b></p>` + scope + (reasons.length ? `<ul class="lk-reasons">${reasons.map(r => `<li>${lakesEsc(r)}</li>`).join('')}</ul>` : '');
  return `<p class="lk-latest"><b>${sel ? 'Latest in this historical dataset' : 'Latest usable image read'}: ${lakesEsc(lakesTime(L.datetime || L.date))}</b>, ${lakesAgeWords(f.age)} (${lakesEsc(LAKES_FRESH_WORDS[f.freshness])}).</p>`
    + scope
    + `<p class="lk-value">NDCI <b>${lakesNum(L.ndci)}</b>, the median over the clear water within 300 m (${lakesPct(L.clear_share)} of it clear in that image).</p>`
    + `<p class="lk-claim">${lakesEsc((doc.claim || {}).public_wording)}</p>`
    + (reasons.length ? `<ul class="lk-reasons">${reasons.map(r => `<li>${lakesEsc(r)}</li>`).join('')}</ul>` : '');
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
// The readings as dots, one row a season (May to September on the same scale each row), so a cloudy summer shows as
// few dots, not as a line drawn across it. The index's own scale, no conversion; the zero line drawn.
function lakesChart(series, width, selected = false) {
  const pts = (series || []).filter(p => p && p.date && typeof p.ndci === 'number');
  if (!pts.length) return '';
  const seen = [...new Set(pts.map(p => +p.date.slice(0, 4)))].sort(), years = [];
  for (let y = seen[0]; y <= seen[seen.length - 1]; y++) years.push(y);   // a year between with no reading keeps its row, empty
  const lo = Math.min(-0.1, ...pts.map(p => p.ndci)), hi = Math.max(0.2, ...pts.map(p => p.ndci));
  const W = Math.max(260, Math.min(720, width || 600)), padL = 44, padR = 8, rowH = 54, gap = 14, H = years.length * (rowH + gap) + 24;
  const x = d => { const y = d.slice(0, 4), t0 = Date.parse(`${y}-05-01T00:00Z`), t1 = Date.parse(`${y}-10-01T00:00Z`);
    return padL + (W - padL - padR) * Math.min(1, Math.max(0, (Date.parse(d + 'T12:00Z') - t0) / (t1 - t0))); };
  const yv = (v, r) => r * (rowH + gap) + rowH - (rowH * (v - lo)) / (hi - lo);
  let g = '';
  years.forEach((yr, r) => {
    const top = r * (rowH + gap);
    g += `<text x="0" y="${top + rowH / 2 + 4}" class="lk-yr">${yr}</text><rect x="${padL}" y="${top}" width="${W - padL - padR}" height="${rowH}" class="lk-band"/>`
      + (lo < 0 && hi > 0 ? `<line x1="${padL}" x2="${W - padR}" y1="${yv(0, r).toFixed(1)}" y2="${yv(0, r).toFixed(1)}" class="lk-zero"/>` : '')
      + (seen.includes(yr) ? '' : `<text x="${padL + 8}" y="${top + rowH / 2 + 4}" class="lk-mo">No clear image this season</text>`)
      + pts.filter(p => +p.date.slice(0, 4) === yr).map(p => `<circle cx="${x(p.date).toFixed(1)}" cy="${yv(p.ndci, r).toFixed(1)}" r="3" class="lk-dot"><title>${lakesEsc(lakesDate(p.date))}: NDCI ${lakesNum(p.ndci)}</title></circle>`).join('');
  });
  const bottom = years.length * (rowH + gap);
  g += ['May', 'Jun', 'Jul', 'Aug', 'Sep'].map((m, i) => `<text x="${(padL + (W - padL - padR) * [0, 31, 61, 92, 123][i] / 153).toFixed(1)}" y="${bottom + 10}" class="lk-mo">${m}</text>`).join('');
  const label = `NDCI readings by date, ${pts.length} clear images in ${seen.length} season${seen.length === 1 ? '' : 's'}, ranging from ${lakesNum(Math.min(...pts.map(p => p.ndci)))} to ${lakesNum(Math.max(...pts.map(p => p.ndci)))}. The seasons table above gives the same in words.`;
  return `<figure class="lk-fig"><svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${lakesEsc(label)}">${g}</svg>`
    + `<figcaption>Each dot is one clear image's reading; each row is one season, May to September.${selected ? ' Only images near laboratory sample dates were read, so gaps between dots are not gaps in the satellite record, and the dots are not a trend for the lake.' : ''} Higher means greener-looking water, on the index's own scale (${lakesNum(lo)} to ${lakesNum(hi)} here). It is not a chlorophyll measurement.</figcaption></figure>`;
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
// One lake whole.
function lakesLake(lake, doc, todayISO, width) {
  const spot = lake.site_ids && lake.site_ids.bathing_water ? `<a href="spot/${lakesEsc(lake.lake_id)}/">Its pollution forecast</a>` : '';
  const scope = lakesSelected(lake) ? '' : 'Every image from May to September of each season read was used here.';
  return `<article class="lk-lake"><h2 id="lk-h">${lakesEsc(lake.name)}</h2>`
    + `<p class="lk-meta">${[lake.water_body, lake.lake_type ? `${lake.lake_type} lake${lake.depth_m ? `, mean depth about ${lakesNum(lake.depth_m, 0)} m` : ''}` : '', spot].filter(Boolean).join(' · ')}</p>`
    + lakesLatest(lake, doc, todayISO) + (scope ? `<p class="lk-scope">${lakesEsc(scope)}</p>` : '')
    + lakesSeasons(lake) + lakesChart(lake.series, width, lakesSelected(lake)) + lakesLab(lake, doc) + '</article>';
}
// What the file is, over the whole list: monitoring locations (each a 300 m circle of water round a point; several can
// share one lake, so they are not counted as lakes), how many named waters they are on, how many have a reading,
// the newest image anywhere with its age today, and the date the images were read to: the file is historical, and
// nothing after that date is in it.
function lakesSummary(index, todayISO) {
  if (!index || !index.available) return `<p class="lk-none">No satellite observations are published in this update${index && index.why ? ` (${lakesEsc(index.why)})` : ''}.</p>`;
  const L = index.lakes || [], withR = L.filter(x => x.latest && x.latest.date), newest = withR.map(x => x.latest.date).sort().pop();
  // Counted by the water's name: the export's water body ids are missing for some locations and split Windermere into basins.
  const bodies = new Set(L.map(x => String(x.water_body || x.lake_id).toLowerCase())).size, full = L.filter(x => !lakesSelected(x)).length;
  const to = ((index.processing || {}).processed_to);
  return `<p class="lk-sum">${L.length} monitoring locations on ${bodies} named water${bodies === 1 ? "" : "s"}; ${withR.length} have a usable reading. Every image was read at ${full} of them; at the other ${L.length - full === 1 ? 'one' : L.length - full}, only images near laboratory sample dates.`
    + `${to ? ` Images are read up to ${lakesEsc(lakesDate(to))}: this is a historical dataset, and nothing after that date is in it.` : ''}`
    + `${newest ? ` The newest image is from ${lakesEsc(lakesDate(newest))}, ${lakesAgeWords(lakesDays(newest, todayISO))}.` : ''}</p>`;
}

// ------------------------------------------------------------------------------ in the page
function lakesMount(root) {
  const host = root.getElementById('lakes'), today = lakesISO(Date.now());
  if (!host) return;
  const get = p => fetch(p, { cache: 'no-cache' }).then(r => (r.ok ? r.json() : null)).catch(() => null);
  get('data/research/lakes.json').then(index => {
    if (!index) { host.innerHTML = '<p class="lk-none">The satellite observations could not be loaded.</p>'; return; }
    const claim = root.getElementById('lk-claim'), not = root.getElementById('lk-not');
    if (claim && index.claim) claim.textContent = index.claim.public_wording;
    if (not && index.claim && index.claim.not_claimed) not.innerHTML = index.claim.not_claimed.map(t => `<li>${lakesEsc(t)}</li>`).join('');
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
        one.innerHTML = lake ? lakesLake(lake, index, today, one.clientWidth) : '<p class="lk-none">This lake could not be loaded.</p>';
      });
    };
    window.addEventListener('hashchange', draw);
    draw();
  });
}
if (typeof document === 'object' && document.getElementById) lakesMount(document);

if (typeof module === 'object' && module.exports) {
  module.exports = { lakesYears, LAKES_SELECTED, lakesSelected, LAKES_FRESH_WORDS, lakesFresh, lakesReason, lakesGroups, lakesPicker, lakesLatest, lakesSeasons, lakesChart, lakesLab, lakesLake, lakesSummary, lakesDate, lakesTime, lakesISO };
}
