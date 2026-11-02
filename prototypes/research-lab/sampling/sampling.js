// Sampling gaps, Research Lab exhibit 5. Reads the sampling planner's file (data/research/sampling_planner.v1.json,
// docs/SAMPLING-PLANNER-CONTRACT-v1.md) for each bathing water's samples, the simulation and its failed verdict, and
// gaps.json (scripts/lab_sampling_gaps.py) for every spot's place, the calendar and the fixed-day rain shares.
// The comparison is arithmetic on samples already taken: places, months, samples, cost and gaps filled. It never says
// which season would teach the model more, and the failed verdict stands beside it. A spot with no samples is "no
// samples", never clean. The three seasons and the chosen spot live in the URL hash, so a link reopens them.

const $ = s => document.querySelector(s);
const esc = LAB.esc;
const DATA = '../../../data/research/';
const num = (v, d = 0) => Number(v).toLocaleString('en-GB', { maximumFractionDigits: d });
const gbp = v => '£' + Number(v).toLocaleString('en-GB', { minimumFractionDigits: v % 1 ? 2 : 0, maximumFractionDigits: 2 });
const pct = v => `${Math.round(v * 100)}%`;
const small = v => v.toFixed(6).replace('-', '−');
const plural = (n, one, many = one + 's') => `${num(n)} ${n === 1 ? one : many}`;
const MONTH = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const MM = MONTH.map((_, i) => String(i + 1).padStart(2, '0'));
const SEASON = ['05', '06', '07', '08', '09'];   // the EA's bathing season: every sample in the record is in it
const FREQ = { w: ['Weekly', 52 / 12], f: ['Every two weeks', 26 / 12], m: ['Monthly', 1] };
const NEAR = 1.5;   // a simulated run is near when samples per never-sampled site are within this factor of its own
const KEYS = ['a', 'b', 'c'];
// a page of the site, from the header's brand link: relative in a site build, the live site from the repository
const siteURL = path => new URL(path, (document.querySelector('.top .brand') || {}).href || 'https://swimsignal.co.uk/').href;

let P, G, BY = {}, CAL = {}, PLANS = [], SPOT = null, COST = { lab: 100, travel: 0 };

// ------------------------------------------------------------------ the spots and what each has
const status = s => (s.ea ? 'ea' : s.local ? 'local' : 'none');
const oneSeason = () => P.coverage.sites.filter(s => s.by_year.filter(Boolean).length === 1).map(s => s.spot_id);
const fewestWet = () => P.coverage.sites.filter(s => s.kind === 'river' && s.rain_rows)
  .sort((a, b) => a.wet_rows - b.wet_rows || a.name.localeCompare(b.name)).slice(0, 4).map(s => s.spot_id);
const noneIn = area => G.spots.filter(s => s.area === area && status(s) === 'none').map(s => s.id);
const areas = () => [...new Set(G.spots.map(s => s.area))].sort();
// samples at a spot in each calendar month, all years together (January first)
const monthly = id => MM.map((_, m) => (CAL[id] || []).reduce((t, r) => t + r.by_month.reduce((u, y) => u + y[m], 0), 0));

function presets() {
  const out = [['one', 'The bathing waters with one season of samples', oneSeason()],
    ['dry', 'The rivers with fewest samples after rain', fewestWet()]];
  for (const a of areas()) { const ids = noneIn(a); if (ids.length) out.push([`none:${a}`, `Spots with no samples: ${a}`, ids]); }
  return out;
}
const DEFAULTS = () => [
  { name: 'Example A', sites: oneSeason(), months: new Set(SEASON), freq: 'f' },
  { name: 'Example B', sites: noneIn('Yorkshire'), months: new Set(SEASON), freq: 'm' },
  { name: 'Example C', sites: oneSeason(), months: new Set(['04', '10']), freq: 'm' },
];

// ------------------------------------------------------------------ state <-> URL
function readHash() {
  const h = new URLSearchParams(location.hash.slice(1)), ids = new Set(G.spots.map(s => s.id));
  PLANS = DEFAULTS();
  KEYS.forEach((k, i) => {
    const v = h.get(k);
    if (!v) return;
    const [f, m, list] = v.split('.');
    PLANS[i] = { name: `Season ${k.toUpperCase()}`, freq: FREQ[f] ? f : 'm',
      months: new Set(MM.filter((_, j) => (m || '')[j] === '1')),
      sites: [...new Set((list || '').split(',').filter(x => ids.has(x)))] };
  });
  for (const [k, d] of [['lab', 100], ['travel', 0]]) { const x = Number(h.get(k)); COST[k] = h.has(k) && x >= 0 ? x : d; }
  return h.get('spot');
}
function writeHash() {
  const p = new URLSearchParams();
  if (SPOT) p.set('spot', SPOT);
  PLANS.forEach((pl, i) => p.set(KEYS[i], `${pl.freq}.${MM.map(m => (pl.months.has(m) ? 1 : 0)).join('')}.${pl.sites.join(',')}`));
  p.set('lab', COST.lab); p.set('travel', COST.travel);
  history.replaceState(null, '', '#' + p.toString());
}

// ------------------------------------------------------------------ the opening
// What the export covers, said beside the figures: the spots in SwimSignal's list when it was made and the last sample.
// The site's list grows; a spot added since is not here, and the page must never read as complete current coverage.
const population = () => `This export holds the ${G.spots.length} spots in SwimSignal's list on ${LAB.day(G.made)} and lab samples to ` +
  `${LAB.day(G.outcomes_to)}. Spots added to the site since are not in it.`;
function front() {
  $('#scope').textContent = `Exploratory: a planning aid on samples already taken. ${population()} It allocates no sample and changes nothing in the forecast.`;
  $('#pop').textContent = population();
  const c = P.coverage, sp = c.spots, none = sp.total - sp.with_ea - sp.with_local, w = c.wet, one = oneSeason().length;
  const local = G.spots.filter(s => s.local);
  LAB.answer($('#front-answer'),
    `Thin almost everywhere but the ${c.sites.length} bathing waters. ${none} of the ${sp.total} spots in this export have no lab samples, ` +
    `none was taken from October to April, and about ${pct(w.wet_rows / w.rows)} of those from 2024 to 2026 followed heavy rain. Below, compare what a season of ` +
    'extra samples would fill and cost. No rule for choosing them has been shown to help.',
    `${num(c.samples)} Environment Agency samples at ${c.sites.length} inland bathing waters, ${c.years[0]} to ${c.years.at(-1)}, the last on ` +
    `${LAB.day(G.outcomes_to)}. ${one} bathing waters have only one season. ${num(w.wet_rows)} of the ${num(w.rows)} samples from 2024 to 2026 with ` +
    `archived rain came after more than ${w.mm_48h} mm in 48 hours. ` +
    (local.length ? `One spot, ${esc(local[0].name)}, has a local group's samples instead (${num(local[0].local)}, April to October), which the model does not use. ` : '') +
    `The one tested rule for choosing samples failed its test against equal coverage: ${(P.simulation.runs[0].info_vs.COVER.share_info_lower * 100).toFixed(1)}% of simulated worlds, 60% needed.`);
  LAB.drawMap($('#overview'), marks(), { inert: true });
  $('#overview-cap').textContent = `The ${sp.total} spots in this export, ${LAB.day(G.made)}. Filled: lab samples; ringed: none. Map: ${LAB.credit()}.`;
}

function marks() {
  return G.spots.map(s => {
    const k = status(s), r = k === 'ea' ? 2.4 + Math.sqrt(s.ea) / 3 : 3.4;
    return { id: s.id, lat: s.lat, lon: s.lon, name: `${s.name}: ${k === 'none' ? 'no lab samples' : plural(s.ea || s.local, 'sample')}`,
      mark: `<circle r="${r.toFixed(1)}" class="m-${k}"/>` };
  });
}

// ------------------------------------------------------------------ 1. where
function where(asked) {
  const sel = $('#spot-select');
  sel.innerHTML = areas().map(a => `<optgroup label="${esc(a)}">${G.spots.filter(s => s.area === a).sort((x, y) => x.name.localeCompare(y.name))
    .map(s => `<option value="${esc(s.id)}">${esc(s.name)}${status(s) === 'none' ? ' (no samples)' : ''}</option>`).join('')}</optgroup>`).join('');
  sel.onchange = () => pick(sel.value);
  if (asked && !G.spots.some(s => s.id === asked)) {
    $('#spot-note').textContent = `That spot is not in this export, made ${LAB.day(G.made)}. Showing ${G.spots.find(s => s.id === oneSeason()[0]).name} instead.`;
  }
  SPOT = G.spots.some(s => s.id === asked) ? asked : oneSeason()[0];
  const rows = areas().map(a => {
    const ss = G.spots.filter(s => s.area === a);
    return { a, n: ss.length, ea: ss.filter(s => s.ea).length, local: ss.filter(s => !s.ea && s.local).length, none: ss.filter(s => status(s) === 'none').length };
  }).sort((x, y) => y.none - x.none || x.a.localeCompare(y.a));
  $('#areas').innerHTML = '<caption>The spots in this export by area, most without samples first.</caption><thead><tr><th scope="col">Area</th>'
    + '<th scope="col" class="num">Spots</th><th scope="col" class="num">EA samples</th><th scope="col" class="num">A group\'s</th><th scope="col" class="num">None</th></tr></thead><tbody>'
    + rows.map(r => `<tr${r.none === r.n ? ' class="none-row"' : ''}><th scope="row">${esc(r.a)}</th><td class="num">${r.n}</td><td class="num">${r.ea}</td><td class="num">${r.local}</td><td class="num">${r.none}</td></tr>`).join('')
    + '</tbody>';
}

function pick(id) {
  SPOT = id;
  $('#spot-select').value = id;
  const s = G.spots.find(x => x.id === id), k = status(s), b = BY[id];
  LAB.drawMap($('#map'), marks(), { selected: id, label: s.name, onPick: pick, aria: 'Map of every SwimSignal spot, by its lab samples' });
  let h = `<h3>${esc(s.name)}</h3><p class="meta">${s.kind === 'lake' ? 'Lake' : 'River'} · ${esc(s.area)} · <a href="${LAB.spotURL(id)}">Today's forecast for ${esc(s.name)}</a></p>`;
  if (k === 'ea') {
    h += `<p class="big">${num(s.ea)}<small>Environment Agency samples, ${P.coverage.years[0]}–${P.coverage.years.at(-1)}</small></p>`
      + `<p>By year: ${P.coverage.years.map((y, i) => `${y} ${b.by_year[i]}`).join(', ')}. By month: ${SEASON.map((m, i) => `${MONTH[+m - 1].slice(0, 3)} ${b.by_month[i]}`).join(', ')}; none from October to April.</p>`
      + (b.rain_rows ? `<p>${b.wet_rows} of ${b.rain_rows} samples from 2024 to 2026 came after more than ${P.coverage.wet.mm_48h} mm in 48 hours.</p>`
        : '<p>No monitored overflow upstream, so no rain figures here.</p>');
  } else if (k === 'local') {
    const m = monthly(id);
    h += `<p class="big">${num(s.local)}<small>samples by a local group, none by the Environment Agency</small></p>`
      + `<p>By month: ${MM.map((x, i) => (m[i] ? `${MONTH[i].slice(0, 3)} ${m[i]}` : '')).filter(Boolean).join(', ')}. Not part of the model's data: <a href="${siteURL('waterhead.html')}">their own page</a>.</p>`;
  } else {
    h += '<p class="big">0<small>lab samples</small></p><p>No lab sample here in this record. The model learns nothing from this spot\'s own water; its estimate rests on samples elsewhere. That says nothing about whether the water is clean.</p>';
  }
  h += '<div class="sg-add" role="group" aria-label="Add this spot to a season">'
    + PLANS.map((pl, i) => `<button type="button" data-i="${i}" aria-pressed="${pl.sites.includes(id)}">${pl.sites.includes(id) ? 'In' : 'Add to'} season ${KEYS[i].toUpperCase()}</button>`).join('') + '</div>';
  $('#spot').innerHTML = h;
  $('#spot').querySelectorAll('.sg-add button').forEach(btn => btn.onclick = () => {
    const pl = PLANS[+btn.dataset.i];
    pl.sites = pl.sites.includes(id) ? pl.sites.filter(x => x !== id) : [...pl.sites, id];
    pick(id); plans();
  });
  writeHash();
}

// ------------------------------------------------------------------ 2. when
function calendar() {
  const rows = [...G.calendar].sort((a, b) => a.area.localeCompare(b.area) || a.name.localeCompare(b.name));
  const W = 1080, lw = 230, top = 34, rh = 14, cols = G.years.length * 12, cw = (W - lw) / cols, last = G.outcomes_to.slice(0, 7);
  let g = '<defs><pattern id="sg-hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="4" height="4" fill="var(--card)"/><line x1="0" y1="0" x2="0" y2="4" stroke="var(--gap)" stroke-width="1.4"/></pattern></defs>';
  G.years.forEach((y, i) => {
    g += `<text x="${lw + i * 12 * cw + 2}" y="12" class="yr">${y}</text>`;
    MM.forEach((m, j) => { if (j % 3 === 0) g += `<text x="${lw + (i * 12 + j) * cw + 1}" y="26">${MONTH[j][0]}</text>`; });
  });
  let y = top, area = null;
  for (const r of rows) {
    if (r.area !== area) { area = r.area; y += 6; g += `<text x="0" y="${y + 8}" class="area">${esc(area)}</text>`; y += 12; }
    g += `<text x="0" y="${y + rh - 4}" class="nm">${esc(r.name.length > 34 ? r.name.slice(0, 33) + '…' : r.name)}${r.who === 'local' ? ' (group)' : ''}</text><title>${esc(r.name)}</title>`;
    r.by_month.forEach((yr, i) => yr.forEach((n, j) => {
      const x = lw + (i * 12 + j) * cw, ym = `${G.years[i]}-${MM[j]}`;
      const cls = ym > last ? 'later' : n ? r.who : 'gap';
      g += `<rect x="${(x + .5).toFixed(1)}" y="${y + 1}" width="${(cw - 1).toFixed(1)}" height="${rh - 2}" class="${cls}"${n ? ` opacity="${Math.min(1, .35 + n / 6).toFixed(2)}"` : ''}><title>${esc(r.name)}, ${MONTH[j]} ${G.years[i]}: ${ym > last ? 'not in this record yet' : plural(n, 'sample')}</title></rect>`;
    }));
    y += rh;
  }
  $('#calendar').innerHTML = `<svg viewBox="0 0 ${W} ${y + 6}" role="img" aria-label="Lab samples a month at each place with samples, ${G.years[0]} to ${G.years.at(-1)}: none from October to April at any bathing water">${g}</svg>`;
}

// ------------------------------------------------------------------ 3. after rain
function rain() {
  const r = G.fixed_day_rain, mx = v => Math.ceil(Math.max(...v) * 10) / 10;
  const byA = Object.entries(r.by_area).map(([a, v]) => ({ label: `${a} (${v.rows})`, v: v.wet / v.rows })).sort((a, b) => b.v - a.v);
  const byM = Object.entries(r.by_month).map(([m, v]) => ({ label: `${MONTH[+m - 1]} (${v.rows})`, v: v.wet / v.rows }));
  const w = P.coverage.wet, missing = areas().filter(a => !r.by_area[a]);
  $('#rain').innerHTML = `<div class="fnote"><span class="tag">exploratory · by area</span><p class="fig">${pct(w.wet_rows / w.rows)}<small> of ${num(w.rows)} samples followed more than ${r.mm_48h} mm in 48 hours</small></p>`
    + `<p>The Environment Agency fixes its sampling days in advance, so this share is about what a fixed schedule in the same area would get. Samples in brackets.</p><div id="rain-a"></div>`
    + `<p class="note">No figure for ${missing.map(esc).join(' or ')}: no bathing water there with an overflow upstream. Each bathing water's own count is on <a href="${siteURL('sampling-planner.html')}">the sampling planner</a>.</p></div>`
    + `<div class="fnote"><span class="tag">exploratory · by month</span><p class="fig">${pct(Math.max(...byM.map(x => x.v)))}<small> at most, in any month of the season</small></p>`
    + `<p>A sampler who waits for rain would get more. How many more was not measured: wet-day sampling was not simulated as such, and nobody has tried it here.</p><div id="rain-m"></div>`
    + `<p class="note">${esc(r.note)}</p></div>`;
  $('#rain-a').innerHTML = LAB.dots(byA, { max: mx(byA.map(x => x.v)), fmt: pct });
  $('#rain-m').innerHTML = LAB.dots(byM, { max: mx(byA.map(x => x.v)), fmt: pct });
}

// ------------------------------------------------------------------ 4. compare
function figures(pl) {
  const vpm = FREQ[pl.freq][1], ss = pl.sites.map(id => G.spots.find(s => s.id === id)), months = MM.filter(m => pl.months.has(m));
  const per = months.length * vpm, samples = Math.round(ss.length * per);
  const r = G.fixed_day_rain.by_area;
  let wet = 0, withFig = 0, newPairs = 0;
  for (const s of ss) {
    const m = monthly(s.id);
    for (const mo of months) {
      if (!m[+mo - 1]) newPairs++;
      const a = r[s.area];
      if (a && SEASON.includes(mo)) { wet += vpm * a.wet / a.rows; withFig += vpm; }
    }
  }
  const none = ss.filter(s => status(s) === 'none'), one = new Set(oneSeason());
  return { ss, months, per, samples, cost: samples * (COST.lab + COST.travel), none: none.length, one: ss.filter(s => one.has(s.id)).length,
    newPairs, pairs: ss.length * months.length, wet: Math.round(wet), withFig: Math.round(withFig),
    offSeason: months.filter(m => !SEASON.includes(m)).length, areas: new Set(ss.map(s => s.area)).size };
}

function strip(pl, f) {
  const before = MM.map((_, j) => f.ss.reduce((t, s) => t + monthly(s.id)[j], 0)), cw = 26, W = 12 * cw + 70;
  let g = `<defs><pattern id="sg-hatch-s" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="4" height="4" fill="var(--card)"/><line x1="0" y1="0" x2="0" y2="4" stroke="var(--gap)" stroke-width="1.4"/></pattern></defs>`;
  MM.forEach((m, j) => {
    const x = 70 + j * cw, add = pl.months.has(m) ? Math.round(f.ss.length * FREQ[pl.freq][1]) : 0;
    g += `<text x="${x + cw / 2}" y="10" text-anchor="middle">${MONTH[j][0]}</text>`;
    g += `<rect x="${x + .5}" y="14" width="${cw - 1}" height="18" class="${before[j] ? 'now' : 'gap'}"${before[j] ? ' opacity=".8"' : ''}/>`;
    if (before[j]) g += `<text x="${x + cw / 2}" y="27" text-anchor="middle" style="fill:var(--paper)">${before[j] > 99 ? '99+' : before[j]}</text>`;
    g += `<rect x="${x + .5}" y="36" width="${cw - 1}" height="18" class="${add ? 'add' : 'gap'}"/>`;
    if (add) g += `<text x="${x + cw / 2}" y="49" text-anchor="middle" style="fill:var(--paper)">${add}</text>`;
  });
  g += '<text x="0" y="27">2023–26</text><text x="0" y="49">This season</text>';
  return `<svg viewBox="0 0 ${W} 58" role="img" aria-label="Samples a month at these spots: those already taken, 2023 to 2026, and this season's">${g}</svg>`;
}

function plans() {
  const pre = presets();
  $('#plans').innerHTML = PLANS.map((pl, i) => {
    const k = KEYS[i], f = figures(pl);
    return `<div class="sg-plan" data-i="${i}"><h3>Season ${k.toUpperCase()}${pl.name.startsWith('Example') ? ' <small class="note">(an example)</small>' : ''}</h3>`
      + `<label>Start from<select class="pre"><option value="">Keep these spots</option><option value="clear">No spots</option>${pre.map(([v, t, ids]) => `<option value="${esc(v)}">${esc(t)} (${ids.length})</option>`).join('')}</select></label>`
      + `<label>Add a spot<select class="add"><option value="">Choose…</option>${areas().map(a => `<optgroup label="${esc(a)}">${G.spots.filter(s => s.area === a && !pl.sites.includes(s.id)).sort((x, y) => x.name.localeCompare(y.name)).map(s => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join('')}</optgroup>`).join('')}</select></label>`
      + `<ul class="sg-sites" aria-label="Spots in season ${k.toUpperCase()}">${f.ss.length ? f.ss.map(s => `<li><span>${esc(s.name)}<small>${status(s) === 'none' ? 'no samples' : plural(s.ea || s.local, 'sample')}${status(s) === 'local' ? ' (group)' : ''}</small></span><button type="button" class="rm" data-id="${esc(s.id)}" aria-label="Remove ${esc(s.name)}">Remove</button></li>`).join('') : '<li class="empty">No spots yet.</li>'}</ul>`
      + `<fieldset><legend>Months (dashed: no Environment Agency sample in any year)</legend><div class="sg-months">${MM.map((m, j) => `<label class="${SEASON.includes(m) ? '' : 'no-ea'}" title="${MONTH[j]}"><input type="checkbox" value="${m}"${pl.months.has(m) ? ' checked' : ''} aria-label="${MONTH[j]}">${MONTH[j].slice(0, 3)}</label>`).join('')}</div></fieldset>`
      + `<label>How often at each spot<select class="freq">${Object.entries(FREQ).map(([v, [t]]) => `<option value="${v}"${pl.freq === v ? ' selected' : ''}>${t}</option>`).join('')}</select></label>`
      + `<div class="sg-strip">${strip(pl, f)}</div></div>`;
  }).join('');
  $('#plans').querySelectorAll('.sg-plan').forEach(el => {
    const pl = PLANS[+el.dataset.i], redo = () => { pl.name = `Season ${KEYS[+el.dataset.i].toUpperCase()}`; plans(); if (SPOT) pick(SPOT); };
    el.querySelector('.pre').onchange = e => { const v = e.target.value; if (!v) return; pl.sites = v === 'clear' ? [] : [...pre.find(p => p[0] === v)[2]]; redo(); };
    el.querySelector('.add').onchange = e => { if (e.target.value) { pl.sites.push(e.target.value); redo(); } };
    el.querySelector('.freq').onchange = e => { pl.freq = e.target.value; redo(); };
    el.querySelectorAll('.sg-months input').forEach(c => c.onchange = () => { c.checked ? pl.months.add(c.value) : pl.months.delete(c.value); redo(); });
    el.querySelectorAll('.rm').forEach(b => b.onclick = () => { pl.sites = pl.sites.filter(x => x !== b.dataset.id); redo(); });
  });
  compare();
  writeHash();
}

// The simulated run nearest a season's samples per never-sampled spot, if within NEAR of it (sampling-planner.js spNearest).
function nearest(perSite) {
  let best = null;
  for (const r of P.simulation.runs.filter(x => x.tau > 0)) {   // the τ = 0 run is a world with no site differences, not a budget
    const off = Math.abs(Math.log(perSite / r.per_site));
    if (off <= Math.log(NEAR) && (!best || off < best.off)) best = { r, off };
  }
  return best && best.r;
}

function compare() {
  const F = PLANS.map(figures);
  const row = (label, cell) => `<tr><th scope="row">${label}</th>${F.map((f, i) => `<td>${cell(f, PLANS[i])}</td>`).join('')}</tr>`;
  const sim = f => {
    if (!f.none) return 'No spot without samples here.<small>The simulation\'s whole difference was at sites never sampled before.</small>';
    const r = nearest(f.per);
    if (!r) return `About ${num(f.per, 1)} per spot without samples: outside the simulated ${P.simulation.runs.filter(x => x.tau > 0).map(x => num(x.per_site)).join(' and ')}.<small>It says nothing about this season.</small>`;
    const c = r.info_vs.COVER;
    return `Nearest: ${num(r.per_site)} per new site. The information rule beat equal coverage in ${(c.share_info_lower * 100).toFixed(1)}% of worlds.`
      + `<small>${r.run === 'main' ? 'The test needed 60%: it failed.' : 'A check that decided nothing.'} Made-up worlds, not real water.</small>`;
  };
  $('#compare').innerHTML = `<caption>The three seasons side by side. Lab bill at ${gbp(COST.lab)} a sample, plus ${gbp(COST.travel)} travel and time, both your assumptions.</caption>`
    + `<thead><tr><th scope="col">Measure</th>${KEYS.map(k => `<th scope="col">Season ${k.toUpperCase()}</th>`).join('')}</tr></thead><tbody>`
    + row('Spots', f => `${f.ss.length}<small>in ${plural(f.areas, 'area')}</small>`)
    + row('Of them with no lab samples now', f => `${f.none}${f.one ? `<small>and ${f.one} with one season</small>` : ''}`)
    + row('When', (f, pl) => `${f.months.length ? f.months.map(m => MONTH[+m - 1].slice(0, 3)).join(', ') : 'No months'}<small>${FREQ[pl.freq][0].toLowerCase()}${f.offSeason ? `; ${f.offSeason} outside May–September` : ''}</small>`)
    + row('Samples in the season', f => `about ${num(f.samples)}<small>${f.ss.length ? `${num(f.per, 1)} a spot` : ''}</small>`)
    + row('Cost', f => `${gbp(f.cost)}<small>${gbp(f.samples * COST.lab)} lab, ${gbp(f.samples * COST.travel)} travel and time</small>`)
    + row('Spot-months with no sample before', f => `${f.newPairs} of ${f.pairs}<small>a spot in a month it has never been sampled in, 2023–26</small>`)
    + row('After rain, on fixed days', f => (f.withFig ? `about ${num(f.wet)} of ${num(f.withFig)}<small>by the area's share; ${f.samples - f.withFig > 0 ? `${num(f.samples - f.withFig)} samples have no figure` : 'every sample has a figure'}</small>` : 'No figure<small>no months in May–September, or no area share</small>'))
    + row('What the simulation says', sim)
    + '</tbody>';
}

// ------------------------------------------------------------------ 5. simulation
function simulation() {
  const s = P.simulation, main = s.runs[0], st = main.strategies;
  const runName = r => ({ main: `The test: ${num(r.per_site)} per new site`, tau0: `Check: sites truly alike`, budget120: `Check: ${num(r.per_site)} per new site` }[r.run] || r.run);
  const items = s.runs.map(r => ({ label: runName(r), v: r.info_vs.COVER.mean_gain, ci: r.info_vs.COVER.ci95, c: r.run === 'main' ? 'var(--ink)' : 'var(--rule)', strong: r.run === 'main' }));
  const lo = Math.min(0, ...items.map(x => x.ci[0])), hi = Math.max(...items.map(x => x.ci[1]));
  $('#sim').innerHTML = `<div class="fnote"><span class="tag">stated in advance · simulation</span><p class="fig">${(main.info_vs.COVER.share_info_lower * 100).toFixed(1)}%<small> of ${main.replications} made-up worlds, against 60% needed: failed</small></p>`
    + `<p>A simulation tried four ways of choosing where and when to take ${main.budget} extra samples in one season. ${esc(s.world.note)}</p>`
    + `<dl>${P.policies.map(p => `<dt>${esc(p.name)}</dt><dd>${esc(p.rule)}</dd>`).join('')}</dl>`
    + `<div class="tw"><table class="sg-policies"><caption>Means over ${main.replications} worlds. Error: how far the model's rate for each site was from the true rate a season later; lower is better.</caption>`
    + '<thead><tr><th scope="col">Policy</th><th scope="col" class="num">Error</th><th scope="col" class="num">At never-sampled sites</th><th scope="col" class="num">High results</th></tr></thead><tbody>'
    + P.policies.map(p => `<tr><th scope="row">${esc(p.name)}</th><td class="num">${st[p.id].P.toFixed(5)}</td><td class="num">${st[p.id].P_never.toFixed(5)}</td><td class="num">${st[p.id].S4_exceedances.toFixed(1)}</td></tr>`).join('')
    + '</tbody></table></div></div>'
    + `<div class="fnote"><span class="tag">stated in advance · the information rule against equal coverage</span><p class="fig">${small(main.info_vs.COVER.mean_gain)}<small> mean gain, about ${Math.round(100 * main.info_vs.COVER.mean_gain / st.COVER.P)}% of equal coverage's error</small></p>`
    + `<p>Gain in error, with its 95% interval, in each run. Only the first decided anything; the others were checks.</p><div id="sim-dots"></div>`
    + `<p>${esc(s.verdict_words)} Almost all of the difference was at sites never sampled before, where equal coverage went too. With about 10 samples per new site, equal coverage caught up.</p>`
    + `<p class="note">No rule here has been tried in real water. Only a field study could show one works: <a href="https://github.com/ethanbuckley/swimsignal/blob/main/${esc(P.field_study)}">the study set out in advance</a>.</p></div>`;
  $('#sim-dots').innerHTML = LAB.dots(items, { min: lo, max: hi * 1.15, fmt: small, ref: { v: 0, label: 'no gain' } });
}

// ------------------------------------------------------------------ start
function costs() {
  for (const [id, k] of [['#lab-price', 'lab'], ['#travel', 'travel']]) {
    const el = $(id);
    el.value = COST[k];
    el.oninput = () => { const v = Number(el.value); if (el.value !== '' && v >= 0) { COST[k] = v; compare(); writeHash(); } };
  }
}

Promise.all([fetch(DATA + 'sampling_planner.v1.json').then(r => r.json()), fetch('gaps.json').then(r => r.json()), LAB.loadOutline('../')])
  .then(([p, g]) => {
    if (p.schema !== 'swimsignal.sampling-planner' || !String(p.version).startsWith('1.')) throw new Error(`the planner's file is ${p.schema} ${p.version}`);
    P = p; G = g;
    for (const s of P.coverage.sites) BY[s.spot_id] = s;
    for (const r of G.calendar) (CAL[r.spot_id] = CAL[r.spot_id] || []).push(r);
    const asked = readHash();
    front(); where(asked); calendar(); rain(); costs(); simulation(); plans(); pick(SPOT);
    $('#attrib').textContent = `${G.attribution.map(a => a.replace(/\.$/, '')).join('. ')}. Map: ${LAB.credit()}.`;
    $('#copy').onclick = () => {
      writeHash();
      (navigator.clipboard ? navigator.clipboard.writeText(location.href) : Promise.reject(new Error('no clipboard')))
        .then(() => { $('#copy-msg').textContent = 'Link copied.'; }, () => { $('#copy-msg').textContent = `Copy this address: ${location.href}`; });
    };
  })
  .catch(err => LAB.failed($('#front-answer'), err));
