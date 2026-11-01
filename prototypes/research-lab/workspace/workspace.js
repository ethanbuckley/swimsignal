// The catchment workspace, Research Lab exhibit 4 (prototype). Reads data/index.json and data/<catchment>.json, made by
// scripts/lab_catchment_workspace.py from committed research files and the forecast's own caches.
// Every layer is drawn on one date axis. A stretch with no record is hatched and never drawn as zero. Hindsight estimates
// say "would have flagged", never "warned"; a weight is a factor from 0 to 1, never a share arriving; NDCI is an index.
// The investigation (catchment, dates, layers, day, spot) lives in the URL hash, so a link reopens it exactly.
// The CSV holds exactly the rows the timeline draws: same catchment, same dates, same layers.

const $ = s => document.querySelector(s);
const esc = LAB.esc;
const num = (v, dp = 1) => (v == null ? '–' : Number(v).toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp }));
const plural = (n, one, many = one + 's') => `${Number(n).toLocaleString('en-GB')} ${n === 1 ? one : many}`;
const ABBR = new Set(['STW', 'WWTW', 'WTW', 'CSO', 'SPS', 'PS', 'SSO', 'EO', 'STC', 'TPS', 'SO', 'WRC', 'SWO', 'UV', 'DWF']);
// "ILKLEY MIDDLETON/CSO" -> "Ilkley Middleton/CSO": capitals only where the source shouted, words split at spaces and slashes
const nice = s => String(s || '').split(/(\s+|\/)/).map(w => (w === w.toUpperCase() && /[A-Z]{2}/.test(w) && !ABBR.has(w.replace(/[^A-Z]/g, ''))) ? w[0] + w.slice(1).toLowerCase() : w).join('');
const fmtW = w => (w == null ? '–' : w >= 0.1 ? w.toFixed(2) : w >= 0.001 ? w.toPrecision(2) : '<0.001');
const DAY = 864e5;
const dn = iso => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / DAY;    // ISO date -> day number
const iso = n => new Date(n * DAY).toISOString().slice(0, 10);
const LON = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' });
const ukDate = t => LON.format(new Date(t));                                                    // instant -> UK date
const fmtD = (d, o = { day: 'numeric', month: 'short', year: 'numeric' }) => new Date(d + 'T12:00:00Z').toLocaleDateString('en-GB', { ...o, timeZone: 'UTC' });
const fmtT = t => new Date(t).toLocaleString('en-GB', { timeZone: 'Europe/London', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const sampleMs = s => Date.parse(s.t.length > 10 ? s.t : s.t + 'T12:00:00Z');

const LAYERS = [
  { id: 'rain', name: 'Rain', sw: 'var(--rain)' },
  { id: 'spills', name: 'Overflow spills', sw: 'var(--ov)' },
  { id: 'ecoli', name: 'E. coli samples', sw: 'var(--ink)' },
  { id: 'temp', name: 'Water temperature', sw: 'var(--temp)' },
  { id: 'sat', name: 'Satellite index', sw: 'var(--sat)' },
];
const PRESETS = [['2024 season', '2024-05-01', '2024-09-30'], ['2025 season', '2025-05-01', '2025-09-30'], ['2026 season', '2026-05-01', '2026-09-30'], ['Whole record', '2024-01-01', '2026-09-30']];
const MIN = '2024-01-01', MAX = '2026-09-30', LOOKBACK = 2;   // a day's panel and map count spills on the day and the two before

let IDX, C = null, S = {};
const CACHE = {};

// ------------------------------------------------------------------ state <-> URL
function readHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  const ids = IDX.catchments.map(c => c.id);
  const ok = d => /^\d{4}-\d{2}-\d{2}$/.test(d || '') && d >= MIN && d <= MAX;
  let from = ok(h.get('from')) ? h.get('from') : null, to = ok(h.get('to')) ? h.get('to') : null;
  if (from && to && from > to) [from, to] = [to, from];
  return {
    c: ids.includes(h.get('c')) ? h.get('c') : 'wharfe-ilkley',
    from, to,
    day: ok(h.get('day')) ? h.get('day') : null,
    off: new Set((h.get('off') || '').split(',').filter(x => LAYERS.some(l => l.id === x))),
    spot: h.get('spot') || null,
  };
}
function writeHash() {
  const p = new URLSearchParams({ c: S.c, from: S.from, to: S.to, day: S.day });
  if (S.off.size) p.set('off', [...S.off].join(','));
  if (S.spot && S.spot !== C.spots[0].id) p.set('spot', S.spot);
  history.replaceState(null, '', '#' + p.toString());
}
const on = id => !S.off.has(id);

// ------------------------------------------------------------------ loading
async function load(id) {
  if (!CACHE[id]) CACHE[id] = await fetch(`data/${id}.json`).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
  return CACHE[id];
}
async function choose(id, keep) {
  C = await load(id);
  S.c = id;
  if (!C.spots.some(s => s.id === S.spot)) S.spot = C.spots.find(s => C.layers.ecoli.rows.some(r => r.spot === s.id))?.id || C.spots[0].id;
  if (!keep || !S.from) { S.from = '2025-05-01'; S.to = '2025-09-30'; }
  if (!keep || !S.day || S.day < S.from || S.day > S.to) S.day = highestDay();
  renderAll();
}
function highestDay() {   // open on the highest sample in the window: the obvious first question
  const rows = C.layers.ecoli.rows.filter(r => r.date >= S.from && r.date <= S.to);
  if (!rows.length) return S.from;
  return rows.reduce((a, b) => (b.ecoli > a.ecoli ? b : a)).date;
}

// ------------------------------------------------------------------ rows on screen
function rowsInView() {
  const L = C.layers, inD = d => d >= S.from && d <= S.to, out = {};
  out.rain = on('rain') ? L.rain.rows.filter(r => inD(r.date)) : [];
  out.spills = on('spills') ? L.spills.rows.filter(r => ukDate(r.end) >= S.from && ukDate(r.start) <= S.to) : [];
  out.ecoli = on('ecoli') ? L.ecoli.rows.filter(r => inD(r.date)) : [];
  out.temp = on('temp') ? L.temp.rows.filter(r => inD(r.date)) : [];
  out.sat = on('sat') ? L.sat.rows.filter(r => inD(r.date)) : [];
  return out;
}
const ovById = id => C.overflows.find(o => o.id === id);
const spotById = id => C.spots.find(s => s.id === id);
// a hindsight estimate is the model's chance of over 900, refitted without that year: "would have flagged", never "warned"
const NO_EST = { before_2024: 'taken before 2024', no_overflow_upstream: 'no overflow upstream', archive_only: "not in the study's sample file", not_ea: 'WET sample, outside the study' };
const flagWord = r => (r.hindsight == null ? `no estimate: ${NO_EST[r.hindsight_reason] || 'none'}`
  : `${r.hindsight >= C.layers.ecoli.meta.warn_at ? 'would have flagged' : 'would not have flagged'} (chance over 900: ${r.hindsight.toFixed(2)})`);

// ------------------------------------------------------------------ frontispiece
function renderFront() {
  // Exploratory count on outcomes already read: samples in 2024-25 (the years with spill records) and whether any
  // overflow upstream of that sample's spot had a recorded spill in the 48 hours before it was taken.
  const L = C.layers, byOv = {};
  for (const e of L.spills.rows) (byOv[e.overflow] ||= []).push([Date.parse(e.start), Date.parse(e.end)]);
  const tally = { over: [0, 0], under: [0, 0] };
  for (const s of L.ecoli.rows) {
    if (s.date > '2025-12-31') continue;
    const t = sampleMs(s), ups = C.overflows.filter(o => o.at[s.spot]).map(o => o.id);
    const hit = ups.some(id => (byOv[id] || []).some(([a, b]) => a <= t && b >= t - 48 * 36e5));
    const k = s.ecoli > L.ecoli.meta.line ? 'over' : 'under';
    tally[k][0] += hit; tally[k][1] += 1;
  }
  const pct = ([a, n]) => (n ? Math.round(100 * a / n) + '%' : '–');
  const lead = `${esc(C.name)}, 2024–25: `;
  $('#front-answer').innerHTML = !tally.over[1]
    ? lead + `no sample over 900 E. coli per 100 ml at its ${C.spots.length} spots. <b>${tally.under[0]} of ${tally.under[1]}</b> samples (${pct(tally.under)}) followed a recorded spill at an overflow upstream within 48 hours, and none came back high. The workspace shows what the overflows and the rain did around each one.`
    : lead + `of ${plural(tally.over[1], 'sample')} over 900 E. coli per 100 ml, <b>${tally.over[0]}</b> (${pct(tally.over)}) followed a recorded spill at an overflow upstream within 48 hours. ` +
      `So did <b>${tally.under[0]} of ${tally.under[1]}</b> samples under 900 (${pct(tally.under)}). ` +
      (tally.over[0] / tally.over[1] > tally.under[0] / Math.max(1, tally.under[1]) + 0.1
        ? 'High samples followed spills more often, but low ones often did too: a spill alone does not explain a high sample.'
        : 'High and low samples followed spills about as often: spills alone do not separate them here.');
  $('#front-status').innerHTML = `<b>Exploratory, on outcomes already read.</b> A count, not a test. 2026 is left out because its spill records are not published yet. Nothing after 30 Sep 2026.`;
  const pts = IDX.catchments.map(c => ({ id: c.id, lat: c.lat, lon: c.lon, name: c.name, mark: '<circle r="6" class="cm"/>' }));
  LAB.drawMap($('#overview'), pts, { box: { w: -4.6, e: -0.4, s: 53.2, n: 55.2 }, selected: C.id, label: C.short, maxH: 460, aria: 'The two catchments', onPick: id => { S.from = null; choose(id); } });
  $('#overview-cap').textContent = `The two catchments in this first version. ${C.intro}`;
}

// ------------------------------------------------------------------ controls
function renderControls() {
  $('#c-seg').innerHTML = IDX.catchments.map(c => `<button type="button" data-c="${c.id}" aria-pressed="${c.id === S.c}">${esc(c.short)}</button>`).join('');
  $('#c-seg').querySelectorAll('button').forEach(b => { b.onclick = () => { if (b.dataset.c !== S.c) choose(b.dataset.c, true); }; });
  $('#d-from').value = S.from; $('#d-to').value = S.to;
  $('#presets').innerHTML = PRESETS.map(([n, a, b]) => `<button type="button" data-a="${a}" data-b="${b}" aria-pressed="${S.from === a && S.to === b}">${n}</button>`).join('');
  $('#presets').querySelectorAll('button').forEach(b => { b.onclick = () => setRange(b.dataset.a, b.dataset.b); });
  $('#layers').innerHTML = LAYERS.map(l => {
    const applies = l.id === 'temp' ? C.layers.temp.meta.applies : l.id === 'sat' ? C.layers.sat.meta.applies : true;
    return `<label><input type="checkbox" data-l="${l.id}" ${on(l.id) ? 'checked' : ''}><span class="sw" style="background:${l.sw}"></span>${l.name}${applies ? '' : ' <span class="muted">(none here)</span>'}</label>`;
  }).join('');
  $('#layers').querySelectorAll('input').forEach(i => { i.onchange = () => { i.checked ? S.off.delete(i.dataset.l) : S.off.add(i.dataset.l); renderView(); }; });
  $('#c-intro').textContent = C.intro;
}
function setRange(a, b) {
  if (!a || !b) return;
  if (a < MIN) a = MIN; if (b > MAX) b = MAX;
  if (a > b) [a, b] = [b, a];
  S.from = a; S.to = b;
  if (S.day < a || S.day > b) S.day = highestDay();
  renderControls(); renderView();
}

// ------------------------------------------------------------------ the timeline
function renderTimeline(V) {
  const el = $('#timeline'), W = Math.max(300, Math.round(el.clientWidth)), narrow = W < 640;
  const gut = narrow ? 0 : 168, x0 = gut, x1 = W - 4, d0 = dn(S.from), d1 = dn(S.to) + 1;
  const X = d => x0 + (d - d0) / (d1 - d0) * (x1 - x0), dayW = (x1 - x0) / (d1 - d0);
  const L = C.layers;
  let y = 4, g = '';
  const head = (t, sub) => {
    g += narrow ? `<text x="0" y="${y + 11}" class="lane-t">${esc(t)}</text><text x="0" y="${y + 25}" class="lane-s">${esc(sub)}</text>`
      : `<text x="0" y="${y + 12}" class="lane-t">${esc(t)}</text><text x="0" y="${y + 26}" class="lane-s">${esc(sub)}</text>`;
    if (narrow) y += 30;
  };
  const band = (a, b, top, h, cls = 'gapband') => {   // a stretch with no record (or outside what was fetched)
    const lo = Math.max(dn(a), d0), hi = Math.min(dn(b) + 1, d1);
    if (hi > lo) g += `<rect x="${X(lo)}" y="${top}" width="${X(hi) - X(lo)}" height="${h}" class="${cls}"/>`;
  };
  const lanes = [];   // [top, height] of each lane, for the day line

  // rain
  if (on('rain')) {
    const h = 54, top = y; head('Rain', 'mm a day, ERA5-Land'); const t = narrow ? y : top;
    const have = new Set(V.rain.map(r => r.date)), mx = Math.max(20, ...V.rain.map(r => r.mm));
    for (let d = d0; d < d1; d++) if (!have.has(iso(d))) band(iso(d), iso(d), t, h);
    for (const r of V.rain) { const bh = r.mm / mx * (h - 2); if (bh > 0) g += `<rect x="${X(dn(r.date))}" y="${t + h - bh}" width="${Math.max(1, dayW - (dayW > 3 ? 1 : 0))}" height="${bh}" class="rain"/>`; }
    g += `<line x1="${x0}" x2="${x1}" y1="${t + h}" y2="${t + h}" class="base"/><text x="${x1}" y="${t + 10}" text-anchor="end" class="lane-s">${Math.round(mx)} mm</text>`;
    lanes.push([t, h]); y = t + h + 18;
  }
  // spills: one row per overflow, by the model's weight at the chosen spot
  if (on('spills')) {
    const top = y; head('Overflow spills', 'EA start/stop records'); const t = narrow ? y : top + (narrow ? 0 : 34);
    const ovs = orderedOverflows(), rh = narrow ? 22 : 13;
    ovs.forEach((o, i) => {
      const ry = t + i * rh, bar = narrow ? ry + 12 : ry, bh = narrow ? 8 : 9;
      const n = o.events_in_window ? '' : ' none';
      if (narrow) g += `<text x="0" y="${ry + 9}" class="row-n${n}">${esc(nice(o.name).slice(0, 44))}${o.events_in_window ? '' : ' · no events in file'}</text>`;
      else g += `<text x="${gut - 8}" y="${ry + 8}" text-anchor="end" class="row-n${n}">${esc(nice(o.name).slice(0, 24))}</text>`;
      g += `<line x1="${x0}" x2="${x1}" y1="${bar + bh / 2}" y2="${bar + bh / 2}" class="base"/>`;
      band(L.spills.meta.not_covered[0], L.spills.meta.not_covered[1], bar, bh);
      for (const e of V.spills) {
        if (e.overflow !== o.id) continue;
        const a = Math.max(d0, Date.parse(e.start) / DAY), b = Math.min(d1, Date.parse(e.end) / DAY);
        g += `<rect x="${X(a)}" y="${bar}" width="${Math.max(1.2, X(b) - X(a))}" height="${bh}" class="spill"/>`;
      }
    });
    const h = ovs.length * rh + (narrow ? 0 : 0);
    lanes.push([t, h]); y = t + h + 18;
  }
  // E. coli on a log scale, the 900 line dashed
  if (on('ecoli')) {
    const h = 96, top = y; head('E. coli', 'per 100 ml, log scale'); const t = narrow ? y : top;
    const Y = v => t + h - (Math.log10(Math.max(1, v)) / 5) * h;
    for (const v of [10, 100, 1000, 10000]) g += `<line x1="${x0}" x2="${x1}" y1="${Y(v)}" y2="${Y(v)}" class="base" opacity=".5"/><text x="${x1}" y="${Y(v) - 2}" text-anchor="end" class="lane-s">${v.toLocaleString('en-GB')}</text>`;
    g += `<line x1="${x0}" x2="${x1}" y1="${Y(L.ecoli.meta.line)}" y2="${Y(L.ecoli.meta.line)}" class="line900"/>`;
    for (const r of V.ecoli) {
      const cx = X(dn(r.date) + 0.5), cy = Y(r.ecoli), cls = r.q === '<' ? 'cens' : r.ecoli > L.ecoli.meta.line ? 'over' : r.src === 'WET' ? 'wet' : '';
      if (r.hindsight != null && r.hindsight >= L.ecoli.meta.warn_at) g += `<circle cx="${cx}" cy="${cy}" r="7" class="flag"/>`;
      g += r.src === 'WET' && cls !== 'over' ? `<rect x="${cx - 3.5}" y="${cy - 3.5}" width="7" height="7" class="smp ${cls}"/>` : `<circle cx="${cx}" cy="${cy}" r="${r.spot === S.spot ? 4.5 : 3.5}" class="smp ${cls}"/>`;
    }
    if (!V.ecoli.length) g += `<text x="${(x0 + x1) / 2}" y="${t + h / 2}" text-anchor="middle" class="na">No samples in these dates</text>`;
    lanes.push([t, h]); y = t + h + 18;
  }
  // water temperature: only May to September was fetched
  if (on('temp')) {
    const h = 56, top = y; head('Water temperature', L.temp.meta.applies ? '°C, EA readings in the lake' : 'none in the repository'); const t = narrow ? y : top;
    if (!L.temp.meta.applies) { band(S.from, S.to, t, h); g += `<text x="${(x0 + x1) / 2}" y="${t + h / 2 + 4}" text-anchor="middle" class="na">No measured water temperature here in the repository</text>`; }
    else {
      offSeason(t, h, L.temp.meta.months, band);
      const Y = v => t + h - (v / 25) * h;
      for (const v of [10, 20]) g += `<line x1="${x0}" x2="${x1}" y1="${Y(v)}" y2="${Y(v)}" class="base" opacity=".5"/><text x="${x1}" y="${Y(v) - 2}" text-anchor="end" class="lane-s">${v}°</text>`;
      for (const r of V.temp) g += `<circle cx="${X(dn(r.date) + 0.5)}" cy="${Y(r.temp_c)}" r="2.8" class="tmp"/>`;
    }
    lanes.push([t, h]); y = t + h + 18;
  }
  // satellite NDCI at each bathing water
  if (on('sat')) {
    const h = 56, top = y; head('Satellite index (NDCI)', L.sat.meta.applies ? 'Sentinel-2, clear days only' : 'lakes only'); const t = narrow ? y : top;
    if (!L.sat.meta.applies) { band(S.from, S.to, t, h); g += `<text x="${(x0 + x1) / 2}" y="${t + h / 2 + 4}" text-anchor="middle" class="na">Not drawn for rivers: the index is processed for lakes</text>`; }
    else {
      offSeason(t, h, L.sat.meta.season_months, band);
      const Y = v => t + h - ((Math.max(-0.2, Math.min(0.4, v)) + 0.2) / 0.6) * h;
      g += `<line x1="${x0}" x2="${x1}" y1="${Y(0)}" y2="${Y(0)}" class="base"/><text x="${x1}" y="${Y(0) - 2}" text-anchor="end" class="lane-s">0</text>`;
      for (const r of V.sat) g += `<circle cx="${X(dn(r.date) + 0.5)}" cy="${Y(r.ndci)}" r="2.8" class="ndci${r.experimental ? ' exp' : ''}"/>`;
    }
    lanes.push([t, h]); y = t + h + 18;
  }
  // month ticks
  const ax = y; let lastM = '', ticks = 0;
  const span = d1 - d0, every = span > 600 ? 3 : span > 200 ? 1 : 1;
  for (let d = d0; d < d1; d++) {
    const s = iso(d);
    if (s.slice(8) === '01' && s.slice(0, 7) !== lastM) {
      lastM = s.slice(0, 7);
      const m = +s.slice(5, 7);
      if ((m - 1) % every) continue;
      const lab = span > 200 ? (m === 1 ? s.slice(0, 4) : new Date(s + 'T12:00Z').toLocaleDateString('en-GB', { month: 'short', timeZone: 'UTC' })) : fmtD(s, { day: 'numeric', month: 'short' });
      if (narrow && span > 200 && ticks++ % 2) continue;
      g += `<line x1="${X(d)}" x2="${X(d)}" y1="4" y2="${ax}" class="base" opacity=".35"/><text x="${X(d) + 2}" y="${ax + 12}" class="lane-s">${lab}</text>`;
    }
  }
  if (span <= 62) for (let d = d0; d < d1; d++) { const s = iso(d); if (s.slice(8) === '15') g += `<text x="${X(d) + 2}" y="${ax + 12}" class="lane-s">15</text>`; }
  // the chosen day
  const sd = dn(S.day);
  g += `<rect x="${X(sd)}" y="0" width="${Math.max(2, dayW)}" height="${ax}" class="daysel-bg"/><line x1="${X(sd + 0.5)}" x2="${X(sd + 0.5)}" y1="0" y2="${ax}" class="daysel"/>`;
  const H = ax + 20;
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" height="${H}" role="img" aria-label="Timeline of ${esc(C.name)}, ${fmtD(S.from)} to ${fmtD(S.to)}"><defs><pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="5" height="5" fill="var(--paper)"/><line x1="0" y1="0" x2="0" y2="5" stroke="var(--gap)" stroke-width="1.2"/></pattern></defs>${g}</svg>`;
  const svg = el.querySelector('svg');
  svg.onclick = e => {
    const b = svg.getBoundingClientRect(), px = (e.clientX - b.left) * W / b.width;
    if (px < x0) return;
    const d = Math.floor(d0 + (px - x0) / (x1 - x0) * (d1 - d0));
    setDay(iso(Math.max(d0, Math.min(d1 - 1, d))));
  };
  $('#t-key').innerHTML = [
    on('rain') && '<span><i class="sw rain"></i>rain a day</span>',
    on('spills') && '<span><i class="sw spill"></i>an overflow spilling</span>',
    '<span><i class="sw gap"></i>no record: not zero</span>',
    (on('temp') || on('sat')) && C.layers.temp.meta.applies && '<span><i class="sw off"></i>not fetched (outside May to September)</span>',
    on('ecoli') && '<span><i class="dot"></i>sample</span><span><i class="dot over"></i>over 900</span><span><i class="dot cens"></i>below the lab\'s limit</span>',
    on('ecoli') && C.layers.ecoli.rows.some(r => r.src === 'WET') && '<span><i class="dot wet"></i>WET sample, Waterhead</span>',
    on('ecoli') && `<span><i class="dot flag"></i>the hindsight estimate would have flagged it${C.kind === 'lake' ? ' (river line, comparison only)' : ''}</span>`,
  ].filter(Boolean).join('');
}
function offSeason(t, h, months, band) {
  for (let y = +S.from.slice(0, 4); y <= +S.to.slice(0, 4); y++) {
    const first = String(Math.min(...months)).padStart(2, '0'), last = Math.max(...months);
    band(`${y}-01-01`, iso(dn(`${y}-${first}-01`) - 1), t, h, 'offband');
    band(iso(dn(`${y}-${String(last + 1).padStart(2, '0')}-01`)), `${y}-12-31`, t, h, 'offband');
  }
}
function orderedOverflows() {
  const w = o => (o.at[S.spot] ? o.at[S.spot].weight : -1);
  return [...C.overflows].sort((a, b) => w(b) - w(a) || Math.max(...Object.values(b.at).map(v => v.weight)) - Math.max(...Object.values(a.at).map(v => v.weight)));
}

// ------------------------------------------------------------------ the chosen day: map and readings
function spilledIn(id, a, b) {   // UK dates a..b inclusive
  return C.layers.spills.rows.filter(e => e.overflow === id && ukDate(e.end) >= a && ukDate(e.start) <= b);
}
function renderDay() {
  const d = S.day, from = iso(dn(d) - LOOKBACK), L = C.layers, sp = spotById(S.spot);
  const known = d >= L.spills.meta.covered[0] && d <= L.spills.meta.covered[1];
  $('#day-label').textContent = fmtD(d, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
  $('#day-head').textContent = fmtD(d, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

  // map: overflows filled if they spilled on the day or the two before; dashed where no record exists
  const maxW = Math.max(1e-6, ...C.overflows.map(o => o.at[S.spot]?.weight || 0));
  const pts = C.overflows.map(o => {
    const w = o.at[S.spot]?.weight, r = 3 + 6 * Math.sqrt((w || 0) / maxW), st = !known ? 'unk' : spilledIn(o.id, from, d).length ? 'on' : '';
    return { id: o.id, lat: o.lat, lon: o.lon, name: `${nice(o.name)}: weight ${fmtW(w)} at ${sp.name}`, mark: `<circle r="${r.toFixed(1)}" class="ov ${st}"/>` };
  });
  for (const p of (on('temp') ? C.temp_points : [])) pts.push({ id: 't:' + p.id, lat: p.lat, lon: p.lon, name: `Temperature point: ${nice(p.label)}`, mark: '<rect x="-2.5" y="-2.5" width="5" height="5" class="tpt"/>' });
  for (const s of C.spots) pts.push({ id: s.id, lat: s.lat, lon: s.lon, name: s.name, mark: `<circle r="${s.id === S.spot ? 6.5 : 5}" class="spot${s.id === S.spot ? ' focus' : ''}"/>` });
  LAB.drawMap($('#net'), pts, {
    box: C.box, maxH: innerWidth < 760 ? 440 : 600, selected: S.spot, label: shortSpot(sp.name),
    lines: C.lines.map(l => ({ coords: l.coords, cls: l.form === 'lake' ? 'lake' : '' })),
    aria: `Rivers, overflows and swim spots of ${C.name}`,
    onPick: id => { if (C.spots.some(s => s.id === id)) { S.spot = id; renderView(); } },
  });
  $('#net-key').innerHTML = `<span><i class="spot"></i>swim spot (filled: the one in focus)</span><span><i class="ln"></i>mapped river or lake path</span>` +
    (known ? `<span><i class="ov"></i>overflow that spilled on the day or the two before</span><span><i class="ovoff"></i>no spill recorded then</span>` : `<span><i class="ovunk"></i>overflow: no spill records for this date</span>`) +
    `<span>size: the model's weight at the spot in focus</span>` + (on('temp') && C.temp_points.length ? `<span><i class="tpt"></i>EA temperature point</span>` : '');

  // readings
  let h = `<label class="focus-pick">Spot in focus (weights and samples)<select id="spot-sel">${C.spots.map(s => `<option value="${s.id}" ${s.id === S.spot ? 'selected' : ''}>${esc(s.name)}</option>`).join('')}</select></label>`;
  if (on('rain')) {
    const by = Object.fromEntries(L.rain.rows.map(r => [r.date, r.mm]));
    h += `<h3>Rain</h3><div class="rainrow">` + [3, 2, 1, 0].map(k => { const dd = iso(dn(d) - k), v = by[dd]; return `<div>${k ? `${k} day${k > 1 ? 's' : ''} before` : 'the day'}<b class="${v == null ? 'gap' : ''}">${v == null ? 'no record' : num(v) + ' mm'}</b></div>`; }).join('') + `</div>`;
  }
  if (on('spills')) {
    h += `<h3>Spills on the day and the two before</h3>`;
    if (!known) h += `<p class="gapnote">No spill records for this date. The EA publishes each year's start/stop records the following spring, so 2026 is not yet available. Not the same as no spills.</p>`;
    else {
      const rows = C.overflows.map(o => ({ o, ev: spilledIn(o.id, from, d) })).filter(x => x.ev.length).sort((a, b) => (b.o.at[S.spot]?.weight || 0) - (a.o.at[S.spot]?.weight || 0));
      h += rows.length ? `<table><thead><tr><th>Overflow</th><th>Spill hours</th><th>Weight at spot</th></tr></thead><tbody>` + rows.map(({ o, ev }) => {
        const a = Date.parse(from + 'T00:00:00Z') - 36e5, b = Date.parse(d + 'T24:00:00Z');
        const hrs = ev.reduce((s, e) => s + Math.max(0, Math.min(b, Date.parse(e.end)) - Math.max(a, Date.parse(e.start))) / 36e5, 0);
        return `<tr><td>${esc(nice(o.name))}<br><span class="muted" style="font-size:12px">${plural(ev.length, 'event')}, first ${fmtT(ev[0].start)}</span></td><td class="n">${num(hrs)}</td><td class="n">${o.at[S.spot] ? fmtW(o.at[S.spot].weight) : 'not upstream'}</td></tr>`;
      }).join('') + `</tbody></table>` : `<p class="none">None of the ${C.overflows.length} overflows has a recorded spill in these three days.</p>`;
    }
  }
  if (on('ecoli')) {
    const rows = L.ecoli.rows.filter(r => r.date === d);
    h += `<h3>E. coli samples that day</h3>` + (rows.length ? `<table><thead><tr><th>Where</th><th>E. coli /100 ml</th><th>In hindsight</th></tr></thead><tbody>` + rows.map(r =>
      `<tr><td>${esc(shortSpot(spotById(r.spot).name))}<br><span class="muted" style="font-size:12px">${r.src === 'WET' ? 'WET project' : 'Environment Agency'}${r.t.length > 10 ? ', ' + fmtT(r.t) : ''}</span></td><td class="n">${r.q || ''}${r.ecoli.toLocaleString('en-GB')}</td><td class="${r.hindsight != null && r.hindsight >= L.ecoli.meta.warn_at ? 'flagged' : ''}">${esc(flagWord(r))}</td></tr>`).join('') + `</tbody></table>`
      : `<p class="none">No sample that day. Use Previous sample or Next sample to step between them.</p>`);
  }
  if (on('temp') && L.temp.meta.applies) {
    const rows = L.temp.rows.filter(r => r.date === d);
    h += `<h3>Water temperature</h3>` + (rows.length ? `<table><tbody>` + rows.map(r => `<tr><td>${esc(nice(C.temp_points.find(p => p.id === r.point)?.label || r.point))}</td><td class="n">${num(r.temp_c)} °C</td></tr>`).join('') + `</tbody></table>` : `<p class="none">No reading that day.</p>`);
  }
  if (on('sat') && L.sat.meta.applies) {
    const rows = L.sat.rows.filter(r => r.date === d);
    h += `<h3>Satellite index</h3>` + (rows.length ? `<table><tbody>` + rows.map(r => `<tr><td>${esc(shortSpot(C.sat_sites.find(s => s.id === r.site)?.name || r.site))}${r.experimental ? ' <span class="muted">(outside the tested season)</span>' : ''}</td><td class="n">NDCI ${r.ndci.toFixed(3)}</td></tr>`).join('') + `</tbody></table><p class="none" style="margin-top:6px">An index of how green the water looked. Not a toxin measurement and not a chlorophyll concentration.</p>` : `<p class="none">No clear image that day. Cloud or no satellite pass is not a reading.</p>`);
  }
  $('#day').innerHTML = h;
  $('#spot-sel').onchange = e => { S.spot = e.target.value; renderView(); };
}
const shortSpot = n => n.replace(/^Windermere, /, '').replace(/^Wharfe at /, '');

// ------------------------------------------------------------------ evidence rows and CSV
const COLS = ['layer', 'date_uk', 'start_utc', 'end_utc', 'place_id', 'place', 'value', 'unit', 'qualifier', 'note', 'source'];
function evidenceRows(V) {
  const L = C.layers, out = [];
  for (const r of V.rain) out.push(['rain', r.date, '', '', 'cells:' + L.rain.meta.cells.map(c => c.join('/')).join(';'), C.name + ' (mean of cells)', r.mm, 'mm/day', '', '', 'Open-Meteo ERA5-Land']);
  for (const e of V.spills) { const o = ovById(e.overflow); out.push(['spill', ukDate(e.start), e.start, e.end, e.overflow, nice(o.name), e.hours, 'hours', '', `weight at ${S.spot}: ${o.at[S.spot] ? o.at[S.spot].weight : 'not upstream'} (0-1 factor)`, 'EA EDM start/stop']); }
  for (const r of V.ecoli) out.push(['ecoli', r.date, r.t.length > 10 ? new Date(r.t).toISOString().slice(0, 16) + 'Z' : '', '', r.spot, spotById(r.spot).name, r.ecoli, 'per 100 ml', r.q || '', 'hindsight: ' + flagWord(r), r.src === 'WET' ? 'WET (Ambleside Action for a Future)' : 'Environment Agency (' + r.src.slice(3) + ')']);
  for (const r of V.temp) out.push(['water_temp', r.date, '', '', r.point, r.lake, r.temp_c, '°C', '', '', 'EA Water Quality Archive']);
  for (const r of V.sat) out.push(['ndci', r.date, '', '', r.site, C.sat_sites.find(s => s.id === r.site)?.name || r.site, r.ndci, 'index', '', `${r.experimental ? 'outside tested season; ' : ''}scene ${r.scene}`, 'Copernicus Sentinel-2 L2A']);
  return out.sort((a, b) => a[1].localeCompare(b[1]) || a[0].localeCompare(b[0]));
}
function csvCell(v) { const s = String(v ?? ''); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; }
function csv(V) {
  const L = C.layers, rows = evidenceRows(V), src = C.sources, used = LAYERS.filter(l => on(l.id));
  const gaps = [
    on('rain') && `rain: ${L.rain.meta.gap_days} days with no complete record in the full file, including every day after ${L.rain.meta.last}`,
    on('spills') && `spills: no start/stop records after ${L.spills.meta.covered[1]}; overflows with no events in the file: ${C.overflows.filter(o => !o.events_in_window).map(o => o.id).join(', ') || 'none'}`,
    on('temp') && (L.temp.meta.applies ? 'water temperature: May to September only were fetched' : 'water temperature: none in the repository for this catchment'),
    on('sat') && (L.sat.meta.applies ? 'satellite: clear images only; cloud is not a reading' : 'satellite: not processed for rivers'),
  ].filter(Boolean);
  const head = [
    'SwimSignal Research Lab, catchment workspace (prototype). A record of the past: not a forecast and not swimming advice.',
    `Investigation: ${location.href}`,
    `Catchment: ${C.name}; dates ${S.from} to ${S.to} (UK dates); layers: ${used.map(l => l.name).join(', ')}; spot in focus: ${spotById(S.spot).name}`,
    `Data: prototypes/research-lab/workspace/data/${C.id}.json, exported at commit ${C.commit} on ${C.made} by scripts/lab_catchment_workspace.py (sha256 ${C.code_sha256.slice(0, 16)}...)`,
    ...['rain', 'spills', 'ecoli', 'wet', 'hindsight', 'temp', 'sat'].filter(k => k === 'wet' || k === 'hindsight' ? on('ecoli') : on(k)).map(k => `Source (${k}): ${src[k].name}. Licence: ${src[k].licence}. Credit: ${src[k].credit}`),
    `Source (spots): ${src.spots.name}. Licence: ${src.spots.licence}. Credit: ${src.spots.credit}`,
    `Gaps (no record is not zero): ${gaps.join('; ')}`,
    `Notes: "would have flagged" = SwimSignal's model refitted without that year's samples, at or above ${L.ecoli.meta.warn_at}; never issued. Weight is a 0-1 factor, not the share of bacteria arriving. NDCI is a satellite index, not a toxin or chlorophyll measurement.`,
    `Rows: ${rows.length}`,
  ];
  return head.map(l => '# ' + l.replace(/\n/g, ' ')).join('\n') + '\n' + COLS.join(',') + '\n' + rows.map(r => r.map(csvCell).join(',')).join('\n') + '\n';
}
function renderRows(V) {
  const n = Object.fromEntries(Object.entries(V).map(([k, v]) => [k, v.length]));
  const total = Object.values(n).reduce((a, b) => a + b, 0);
  const parts = [on('rain') && plural(n.rain, 'day') + ' of rain', on('spills') && plural(n.spills, 'spill event'), on('ecoli') && plural(n.ecoli, 'sample'), on('temp') && C.layers.temp.meta.applies && plural(n.temp, 'temperature reading'), on('sat') && C.layers.sat.meta.applies && plural(n.sat, 'satellite reading')].filter(Boolean);
  $('#rows-sum').textContent = `${plural(total, 'row')} on screen: ${parts.join(', ') || 'no layer switched on'}. ${fmtD(S.from)} to ${fmtD(S.to)}. The download holds exactly these rows, with a header naming each source, its licence, its gaps and the commit the data was exported at.`;
  const t = $('#rows-table');
  const fill = () => {
    const rows = evidenceRows(V);
    $('#rows-scroll').innerHTML = `<table><thead><tr>${COLS.map(c => `<th>${c}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(v => `<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  };
  t.ontoggle = () => { if (t.open) fill(); };
  if (t.open) fill();
  $('#dl').onclick = () => {
    const blob = new Blob([csv(V)], { type: 'text/csv;charset=utf-8' }), a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = `swimsignal-${C.id}-${S.from}-to-${S.to}.csv`;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  const s = C.sources, sl = k => `<dt>${esc({ rain: 'Rain', spills: 'Spills', ecoli: 'E. coli', wet: 'Waterhead samples', hindsight: 'Hindsight', temp: 'Water temperature', sat: 'Satellite', map: 'Map', spots: 'Swim spots' }[k])}</dt><dd>${esc(s[k].name)}. <i>${esc(s[k].licence)}</i>.</dd>`;
  $('#sources').innerHTML = `<dl>${['rain', 'spills', 'ecoli', ...(C.layers.ecoli.rows.some(r => r.src === 'WET') ? ['wet'] : []), 'hindsight', ...(C.layers.temp.meta.applies ? ['temp'] : []), ...(C.layers.sat.meta.applies ? ['sat'] : []), 'map', 'spots'].map(sl).join('')}</dl>`;
  $('#attrib').textContent = Object.values(s).map(x => x.credit).join('. ') + '. ' + (LAB.credit() ? 'Outline: ' + LAB.credit() + '.' : '');
}

// ------------------------------------------------------------------ stepping
function setDay(d) { S.day = d; renderView(true); }
function stepSample(dir) {
  const dates = [...new Set(C.layers.ecoli.rows.map(r => r.date))].sort();
  const next = dir > 0 ? dates.find(x => x > S.day) : [...dates].reverse().find(x => x < S.day);
  if (!next) return;
  if (next < S.from || next > S.to) { const len = dn(S.to) - dn(S.from); let a = dn(next) - Math.floor(len / 2); a = Math.max(dn(MIN), Math.min(dn(MAX) - len, a)); S.from = iso(a); S.to = iso(a + len); renderControls(); }
  setDay(next);
}

// ------------------------------------------------------------------ render
function renderView(dayOnly) {
  const V = rowsInView();
  renderTimeline(V);
  renderDay();
  if (!dayOnly) renderRows(V);
  writeHash();
}
function renderAll() { renderFront(); renderControls(); renderView(); }

async function init() {
  try {
    [IDX] = await Promise.all([fetch('data/index.json').then(r => r.json()), LAB.loadOutline('../')]);
  } catch (e) {
    $('#front-answer').textContent = 'Could not read the workspace files. Start the server in the repository root (see the Research Lab README).';
    return;
  }
  S = readHash();
  $('#d-from').onchange = () => setRange($('#d-from').value, S.to);
  $('#d-to').onchange = () => setRange(S.from, $('#d-to').value);
  $('#prev-day').onclick = () => setDay(iso(Math.max(dn(S.from), dn(S.day) - 1)));
  $('#next-day').onclick = () => setDay(iso(Math.min(dn(S.to), dn(S.day) + 1)));
  $('#prev-sample').onclick = () => stepSample(-1);
  $('#next-sample').onclick = () => stepSample(1);
  $('#copy').onclick = async () => {
    try { await navigator.clipboard.writeText(location.href); $('#copy-msg').textContent = 'Link copied. It reopens these dates, layers and day.'; }
    catch { $('#copy-msg').textContent = 'Copy the address bar: it holds this investigation.'; }
  };
  let rt; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => C && renderView(true), 150); });
  addEventListener('hashchange', () => { const h = readHash(); if (h.c !== S.c || h.from !== S.from || h.to !== S.to || h.day !== S.day) { S = h; choose(S.c, true); } });
  await choose(S.c, true);
}
init();
