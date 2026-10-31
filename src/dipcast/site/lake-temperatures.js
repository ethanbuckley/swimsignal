// Measured lake temperatures (lake-temperatures.html): the water temperatures the Environment Agency measured in
// lakes, May to September 2000-2026 (docs/LAKE-TEMPERATURE-OBS-CONTRACT-v1.md, version 1), read from the files the
// build splits the research export into (build_site.write_lake_temperatures): data/research/lake-temperatures/index.json,
// every lake without its readings, and data/research/lake-temperatures/lake/<wb_id>.json, one lake whole.
//
// What it may say is the contract's, and only that: what was measured, at named sampling points, on dated visits; the
// median and the middle half by month, each with how many readings stand behind it; the years the readings span; how
// far a listed spot is from the nearest sampling point. Never today's temperature, never the temperature where you get
// in, never a forecast, nothing about safety. The export's own `claim.public_wording` stands beside the figures. Only
// May to September were fetched, so no other month is drawn or named as having a figure.
//
// A plain script, like lakes.js: in the page its names are globals (each begins lt or LT), and in Node the last lines
// export them (tests/site_lake_temperatures.test.cjs).

const LT_MONTHS = [5, 6, 7, 8, 9];
const LT_MONTH_NAMES = { 5: 'May', 6: 'June', 7: 'July', 8: 'August', 9: 'September' };
const LT_FEW = 10;   // a month with fewer readings is marked "few" beside its count
const ltEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
// "21 Sept 2026", from the reading's own date (the export's dates are days, without a time).
const ltDate = iso => new Date(String(iso).slice(0, 10) + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const ltNum = (v, dp = 1) => (typeof v === 'number' && Number.isFinite(v) ? v.toFixed(dp) : '');
const ltInt = n => Number(n || 0).toLocaleString('en-GB');
const ltCount = n => `${ltInt(n)} reading${n === 1 ? '' : 's'}`;
// How far a spot is from a sampling point, as the spot's link and the lake's page say it.
const ltDistance = m => (typeof m !== 'number' || !Number.isFinite(m) ? 'an unknown distance'
  : m < 10 ? 'under 10 m' : m < 1000 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1)} km`);
// An Environment Agency point label in capitals ("WINDERMERE N BASIN - LAKES TOUR"), in normal case.
const ltLabel = s => String(s || '').toLowerCase().replace(/(^|[\s(/-])([a-z])/g, (a, p, c) => p + c.toUpperCase());

// ------------------------------------------------------------------------------ the figures
// The five months, in order, each with its count (0 where the export has none): never a month outside May to September.
function ltMonthly(lake) {
  const by = new Map(((lake && lake.monthly) || []).filter(m => LT_MONTHS.includes(+m.month)).map(m => [+m.month, m]));
  return LT_MONTHS.map(k => ({ month: k, n: 0, median: null, p25: null, p75: null, ...(by.get(k) || {}) }));
}
// The table: each month's readings, its median and its middle half, the count on the same row as every figure. A
// month with no readings says so; one with too few for quartiles (the export gives them from four) says that.
function ltTable(lake) {
  const rows = ltMonthly(lake), few = rows.filter(r => r.n > 0 && r.n < LT_FEW);
  const span = ltSpanYears(lake);
  return `<div class="tw"><table class="lt-months"><caption>Each month's readings${span ? `, ${span}, all years together` : ''}. The middle half is where half of that month's readings fall; it needs 4 readings or more.</caption>`
    + '<thead><tr><th scope="col">Month</th><th scope="col" class="num">Readings</th><th scope="col" class="num">Median</th><th scope="col" class="num">Middle half</th></tr></thead><tbody>'
    + rows.map(r => `<tr><th scope="row">${LT_MONTH_NAMES[r.month]}</th><td class="num">${ltInt(r.n)}${r.n > 0 && r.n < LT_FEW ? ' (few)' : ''}</td>`
      + (r.n === 0 || typeof r.median !== 'number' ? '<td class="num">none</td><td class="num">none</td>'
        : `<td class="num">${ltNum(r.median)}&nbsp;°C</td><td class="num">${typeof r.p25 === 'number' && typeof r.p75 === 'number' ? `${ltNum(r.p25)} to ${ltNum(r.p75)}&nbsp;°C` : 'too few'}</td>`)
      + '</tr>').join('') + '</tbody></table></div>'
    + (few.length ? `<p class="lt-few">Few readings: ${few.map(r => `${LT_MONTH_NAMES[r.month]} has ${ltInt(r.n)}`).join(', ').replace(/, ([^,]*)$/, ' and $1')}. A median from fewer than ${LT_FEW} visits says little about a typical ${few.length === 1 ? LT_MONTH_NAMES[few[0].month] : 'month'}.</p>` : '');
}
// The years the readings span, "2000 to 2026", from the lake's summary (else its readings).
function ltSpanYears(lake) {
  const s = (lake && lake.summary) || {}, d = ((lake && lake.readings) || {}).date || [];
  const a = s.first || d[0], b = s.last || d[d.length - 1];
  if (!a || !b) return '';
  return a.slice(0, 4) === b.slice(0, 4) ? a.slice(0, 4) : `${a.slice(0, 4)} to ${b.slice(0, 4)}`;
}
// Said first and in bold: when the readings were taken, and in how many years.
function ltWhen(lake) {
  const s = (lake && lake.summary) || {};
  if (!s.first || !s.last) return '<p class="lt-when"><b>No readings.</b></p>';
  const years = typeof s.years === 'number' ? ` in ${s.years} different year${s.years === 1 ? '' : 's'}` : '';
  return `<p class="lt-when"><b>Measured on visits from ${ltEsc(ltDate(s.first))} to ${ltEsc(ltDate(s.last))}${years}: ${ltCount(s.readings)}, May to September only.</b></p>`;
}
// Each year with readings and how many: the years are uneven, so this says which ones the figures rest on.
function ltYears(lake) {
  const d = ((lake && lake.readings) || {}).date || [], by = new Map();
  d.forEach(x => { const y = String(x).slice(0, 4); by.set(y, (by.get(y) || 0) + 1); });
  if (!by.size) return '';
  return `<p class="lt-years">Readings each year: ${[...by.keys()].sort().map(y => `${y} (${by.get(y)})`).join(', ')}.</p>`;
}

// ------------------------------------------------------------------------------ the chart
// Every reading as a dot, all years together, placed by its day within May to September, with each month's median as a
// short line across that month. The axis runs from 1 May to 30 September only: no other month is drawn.
const LT_START = { 5: 0, 6: 31, 7: 61, 8: 92, 9: 123 }, LT_DAYS = 153;
const ltDay = iso => { const m = +String(iso).slice(5, 7), d = +String(iso).slice(8, 10); return LT_START[m] === undefined ? null : LT_START[m] + d - 1; };
function ltChart(lake, width) {
  const r = (lake && lake.readings) || {}, dates = r.date || [], temps = r.temp || [];
  const pts = dates.map((d, i) => ({ d, x: ltDay(d), t: temps[i] })).filter(p => p.x !== null && typeof p.t === 'number');
  if (!pts.length) return '';
  const lo = Math.min(5, Math.floor(Math.min(...pts.map(p => p.t)) / 5) * 5), hi = Math.max(25, Math.ceil(Math.max(...pts.map(p => p.t)) / 5) * 5);
  const W = Math.max(280, Math.min(720, Math.round(width || 600))), H = 220, padL = 34, padR = 6, padT = 8, padB = 22;
  const x = day => padL + (W - padL - padR) * (day + 0.5) / LT_DAYS, y = t => padT + (H - padT - padB) * (hi - t) / (hi - lo);
  let g = '';
  for (let t = lo; t <= hi; t += 5) g += `<line x1="${padL}" x2="${W - padR}" y1="${y(t).toFixed(1)}" y2="${y(t).toFixed(1)}" class="lt-grid"/><text x="${padL - 4}" y="${(y(t) + 4).toFixed(1)}" class="lt-ax" text-anchor="end">${t}°</text>`;
  LT_MONTHS.forEach(m => {
    const a = x(LT_START[m] - 0.5), b = x((m === 9 ? LT_DAYS : LT_START[m + 1]) - 0.5);
    if (m > 5) g += `<line x1="${a.toFixed(1)}" x2="${a.toFixed(1)}" y1="${padT}" y2="${H - padB}" class="lt-grid"/>`;
    g += `<text x="${((a + b) / 2).toFixed(1)}" y="${H - 6}" class="lt-ax" text-anchor="middle">${LT_MONTH_NAMES[m].slice(0, 3)}</text>`;
  });
  g += pts.map(p => `<circle cx="${x(p.x).toFixed(1)}" cy="${y(p.t).toFixed(1)}" r="2.5" class="lt-dot"/>`).join('');
  ltMonthly(lake).filter(m => m.n > 0 && typeof m.median === 'number').forEach(m => {
    const a = x(LT_START[m.month] + 3), b = x((m.month === 9 ? LT_DAYS : LT_START[m.month + 1]) - 4);
    g += `<line x1="${a.toFixed(1)}" x2="${b.toFixed(1)}" y1="${y(m.median).toFixed(1)}" y2="${y(m.median).toFixed(1)}" class="lt-med"><title>${LT_MONTH_NAMES[m.month]}: median ${ltNum(m.median)} °C from ${ltCount(m.n)}</title></line>`;
  });
  const t0 = Math.min(...pts.map(p => p.t)), t1 = Math.max(...pts.map(p => p.t)), span = ltSpanYears(lake);
  const label = `${ltCount(pts.length)} from ${span}, May to September, from ${ltNum(t0)} to ${ltNum(t1)} °C. The table above gives each month's median and count in words.`;
  return `<figure class="lt-fig"><svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${ltEsc(label)}">${g}</svg>`
    + `<figcaption>Each dot is one reading, from ${ltEsc(span)}, all years together, placed by its date within May to September. Each short line is that month's median. There are no readings from October to April in this record.</figcaption></figure>`;
}

// ------------------------------------------------------------------------------ where
// The sampling points: name, the Archive's id, how many readings and the years they span, and where on a map.
function ltPoints(lake) {
  const P = (lake && lake.points) || [], r = (lake && lake.readings) || {}, d = r.date || [], at = r.point || [];
  if (!P.length) return '';
  // A point's years: from its own first and last dates (1.1), else worked out from the readings.
  const span = (a, b) => a === b ? a : `${a} to ${b}`;
  const years = i => { const p = P[i];
    if (p && p.first && p.last) return span(String(p.first).slice(0, 4), String(p.last).slice(0, 4));
    const ys = d.filter((_, j) => at[j] === i).map(x => x.slice(0, 4)).sort(); return ys.length ? span(ys[0], ys[ys.length - 1]) : ''; };
  return `<ul class="lt-points">${P.map((p, i) => `<li><b>${ltEsc(ltLabel(p.label))}</b> (${ltEsc(p.point)}): ${ltCount(p.readings)}${years(i) ? `, ${years(i)}` : ''}.`
    + (typeof p.lat === 'number' && typeof p.lon === 'number' ? ` <a href="https://www.openstreetmap.org/?mlat=${p.lat}&amp;mlon=${p.lon}#map=15/${p.lat}/${p.lon}">On a map</a>` : '') + '</li>').join('')}</ul>`;
}
// The listed spots on or beside this lake, each with how far it is from the nearest sampling point.
function ltSpots(lake) {
  const S = (lake && lake.spots) || [];
  if (!S.length) return '';
  return `<p class="lt-spots">The readings were taken at the sampling points below, which are different places from where you get in. `
    + S.map(s => `<a href="spot/${ltEsc(encodeURIComponent(s.spot_id))}/">${ltEsc(s.name)}</a> is ${ltDistance(s.nearest_point_m)} from the nearest one`).join('; ') + '.</p>';
}

// ------------------------------------------------------------------------------ the list and one lake
function ltPicker(index, sel) {
  const by = (a, b) => String(a.name).localeCompare(String(b.name), 'en-GB');
  const L = (index && index.lakes) || [], withSpot = L.filter(x => (x.spots || []).length).sort(by), rest = L.filter(x => !(x.spots || []).length).sort(by);
  const opt = x => `<option value="${ltEsc(x.wb_id)}"${x.wb_id === sel ? ' selected' : ''}>${ltEsc(x.name)}, ${ltCount((x.summary || {}).readings)}</option>`;
  return `<label class="lt-pick" for="lt-select">Lake</label><select id="lt-select"><option value="">Choose a lake</option>`
    + [['Lakes with a SwimSignal spot', withSpot], ['Other lakes', rest]].filter(([, g]) => g.length)
      .map(([h, g]) => `<optgroup label="${ltEsc(h)}">${g.map(opt).join('')}</optgroup>`).join('') + '</select>';
}
// What the whole file holds, with its years first.
function ltSummary(index) {
  if (!index || !index.available) return `<p class="lt-none">No measured lake temperatures are published in this update${index && index.why ? ` (${ltEsc(index.why)})` : ''}.</p>`;
  const c = index.coverage || {}, p = index.period || {}, a = String(p.from || '').slice(0, 4), b = String(p.to || '').slice(0, 4);
  const linked = c.lakes_with_spots ?? (index.lakes || []).filter(x => (x.spots || []).length).length;
  return `<p class="lt-sum"><b>Readings from ${ltEsc(a)} to ${ltEsc(b)}, May to September only.</b> ${ltInt(c.readings)} readings in ${ltInt(c.lakes || (index.lakes || []).length)} lakes, at ${ltInt(c.points)} sampling points. ${linked} of the lakes have a SwimSignal spot on them.</p>`;
}
function ltLake(lake, index, width) {
  const meta = [lake.reservoir ? 'Reservoir' : '', typeof lake.area_km2 === 'number' ? `${ltNum(lake.area_km2, 2)}&nbsp;km² of water` : '',
    typeof lake.depth_m === 'number' ? `mean depth about ${ltNum(lake.depth_m, 0)}&nbsp;m` : ''].filter(Boolean).join(' · ');
  const claim = (index && index.claim && index.claim.public_wording) || '';
  return `<article class="lt-lake" aria-labelledby="lt-h"><h2 id="lt-h">${ltEsc(lake.name)}</h2>${meta ? `<p class="lt-meta">${meta}</p>` : ''}`
    + ltWhen(lake) + (claim ? `<p class="lt-claim">${ltEsc(claim)}</p>` : '') + ltSpots(lake)
    + '<h3>By month</h3>' + ltTable(lake) + ltChart(lake, width) + ltYears(lake)
    + '<h3>Where they were measured</h3>' + ltPoints(lake) + '</article>';
}

// ------------------------------------------------------------------------------ in the page
function ltMount(root) {
  const host = root.getElementById('lake-temps');
  if (!host) return;
  const base = 'data/research/lake-temperatures/';
  const get = p => fetch(p, { cache: 'no-cache' }).then(r => (r.ok ? r.json() : null)).catch(() => null);
  get(base + 'index.json').then(index => {
    if (!index) { host.innerHTML = '<p class="lt-none">The measured lake temperatures could not be loaded.</p>'; return; }
    const not = root.getElementById('lt-not'), attrib = root.getElementById('lt-attrib');
    if (not && index.claim && index.claim.not_claimed) not.innerHTML = index.claim.not_claimed.map(t => `<li>${ltEsc(t)}</li>`).join('');
    if (attrib && Array.isArray(index.attribution) && index.attribution.length) attrib.textContent = index.attribution.join('. ').replace(/\.?$/, '.');
    // The export's own words for the page (1.1): a lead for any lake, and its method in one sentence, shown first.
    const lead = root.getElementById('lt-lead'), said = root.getElementById('lt-method-said');
    if (lead && index.claim && index.claim.page_wording) lead.textContent = index.claim.page_wording;
    if (said && index.method && index.method.public_sentence) { said.textContent = index.method.public_sentence; said.hidden = false; }
    const pickId = () => decodeURIComponent((location.hash.match(/^#lake=([A-Za-z0-9_-]+)$/) || [])[1] || '');
    // The list once, so a keyboard keeps its place in it; the lake below it again at each pick.
    host.innerHTML = ltSummary(index) + (index.available ? ltPicker(index, pickId()) + '<div id="lt-one"></div>' : '');
    const sel = root.getElementById('lt-select'), one = root.getElementById('lt-one');
    if (!sel || !one) return;
    sel.addEventListener('change', () => { history.replaceState(null, '', sel.value ? `#lake=${encodeURIComponent(sel.value)}` : location.pathname + location.search); show(); });
    const show = () => {
      const id = pickId();
      if (sel.value !== id) sel.value = id;
      if (!id || !(index.lakes || []).some(x => x.wb_id === id)) { one.innerHTML = ''; return; }
      one.innerHTML = '<p class="lt-none">Loading…</p>';
      get(`${base}lake/${encodeURIComponent(id)}.json`).then(lake => {
        if (pickId() !== id) return;
        one.innerHTML = lake ? ltLake(lake, index, one.clientWidth) : '<p class="lt-none">This lake could not be loaded.</p>';
      });
    };
    window.addEventListener('hashchange', show);
    show();
  });
}
if (typeof document === 'object' && document.getElementById) ltMount(document);

if (typeof module === 'object' && module.exports) {
  module.exports = { LT_FEW, ltMonthly, ltTable, ltSpanYears, ltWhen, ltYears, ltChart, ltDay, ltPoints, ltSpots, ltPicker, ltSummary, ltLake,
    ltDistance, ltLabel, ltDate };
}
