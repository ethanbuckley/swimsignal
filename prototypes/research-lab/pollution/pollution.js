// Where does the pollution go? Research Lab exhibit 2 (prototype). Reads:
//   ../assets/paths/index.json, <spot>.json, overview.json   scripts/lab_pollution_paths.py: each spot's upstream overflows
//        with the forecast's own distance, travel time and weight, and the mapped rivers that join them to the spot
//   data/research/research_catalogue.v1.json                the recorded verdicts of the transport studies
// The rivers are mapped geometry; travel times and weights are model settings. The clock only shows when water would
// arrive at the model's speed, and says so beside it: no spill's path was tracked and nothing moves along the rivers.

const DATA = '../../../data/research/', PATHS = '../assets/paths/';
const $ = s => document.querySelector(s);
const esc = LAB.esc;
const num = (v, dp = 1) => (v == null ? '–' : Number(v).toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp }));
const plural = (n, one, many = one + 's') => `${Number(n).toLocaleString('en-GB')} ${n === 1 ? one : many}`;
const ABBR = new Set(['STW', 'WWTW', 'WTW', 'CSO', 'SPS', 'PS', 'SSO', 'EO', 'STC', 'TPS', 'SO', 'WRC', 'SWO', 'UV']);
// "AMBLESIDE WwTW" -> "Ambleside WwTW": capitals only where the source shouted
const nice = s => String(s || '').split(/\s+/).map(w => (w === w.toUpperCase() && /[A-Z]{2}/.test(w) && !ABBR.has(w.replace(/[^A-Z]/g, ''))) ? w[0] + w.slice(1).toLowerCase() : w).join(' ');
// A weight is a relative factor between 0 and 1, never a percentage: a percentage reads as the share of bacteria arriving
const fmtW = w => (w >= 0.1 ? w.toFixed(2) : w >= 0.001 ? w.toPrecision(2) : '<0.001');
const hours = h => (h == null ? '–' : h < 1 ? 'under 1 h' : h < 48 ? `${Math.round(h)} h` : `${(h / 24).toFixed(1)} days`);

let IDX, CAT, SPOT = null, T = 0, clockTimer = null, showAll = false;

// ------------------------------------------------------------------ frontispiece
function renderFront(ov) {
  const sp = IDX.spots, withOv = sp.filter(s => s.overflows > 0), none = sp.filter(s => s.overflows === 0 && !s.note), off = sp.filter(s => s.note);
  const set = IDX.settings, kmDay = set.river_velocity_ms * 86.4;
  const total = sp.reduce((a, s) => a + (s.overflows || 0), 0);
  $('#front-answer').innerHTML =
    `SwimSignal traces every monitored overflow on the mapped rivers within ${set.max_upstream_km} km upstream of a spot: ${plural(total, 'link')} from overflow to spot across ${withOv.length} of ${sp.length} spots. ` +
    `It assumes river water moves at ${set.river_velocity_ms} m/s (about ${Math.round(kmDay)} km a day), that bacteria fall tenfold every ${set.t90_h} hours, and that a bigger river dilutes more. ` +
    `Those settings were fitted to Environment Agency samples and passed their test. Attempts to refine them with river flow, wind, sunlight and near-shore mixing did not. No spill's actual path has been measured.`;
  $('#front-status').innerHTML = `<b>Model geometry, not tracking.</b> ${none.length} spots have no monitored overflow upstream within ${set.max_upstream_km} km; ${off.length} sit off the mapped river network. Network and overflows as the forecast uses them, exported ${new Date(IDX.made).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}.`;
  LAB.drawMap($('#overview'), sp.map(s => ({ id: s.id, lat: s.lat, lon: s.lon, name: s.name, kind: 'hist', mark: '<circle r="2.2" class="pt-hist"/>' })),
    { lines: ov.lines.map(c => ({ coords: c })), maxH: 560, aria: 'Every swim spot and the rivers joining its overflows', onPick: id => { selectSpot(id); $('#s-net').scrollIntoView({ behavior: 'smooth' }); } });
  $('#overview-cap').textContent = `Every listed swim spot (white) and the ${ov.lines.length.toLocaleString('en-GB')} mapped river reaches that join its overflows to it. Click a spot to open it.`;
}

// ------------------------------------------------------------------ choosing a spot
function renderPicker() {
  const by = {};
  for (const s of IDX.spots) (by[s.area || 'Elsewhere'] ||= []).push(s);
  $('#pick-aside').textContent = `${IDX.spots.length} spots`;
  $('#spot-select').innerHTML = Object.keys(by).sort().map(a => `<optgroup label="${esc(a)}">${by[a].sort((x, y) => x.name.localeCompare(y.name)).map(s =>
    `<option value="${s.id}">${esc(s.name)}${s.note ? ' (off the river network)' : s.overflows ? ` (${s.overflows} upstream)` : ' (none upstream)'}</option>`).join('')}</optgroup>`).join('');
  $('#spot-select').onchange = e => selectSpot(e.target.value);
}

async function selectSpot(id) {
  const meta = IDX.spots.find(s => s.id === id);
  if (!meta) return;
  $('#spot-select').value = id;
  history.replaceState(null, '', '#spot=' + id);
  stopClock(); showAll = false;
  SPOT = meta.note ? { ...meta, overflows: [], lines: [] } : await fetch(PATHS + id + '.json').then(r => r.json());
  SPOT.meta = meta;
  const maxH = Math.max(0, ...SPOT.overflows.map(o => o.travel_h || 0));
  T = Math.ceil(Math.min(maxH, 240));
  renderHead(); drawNet(); renderClock(); renderTable();
}

function renderHead() {
  const s = SPOT, o = s.overflows, m = s.meta;
  $('#sp-name').textContent = s.name;
  $('#sp-meta').innerHTML = `${m.kind === 'lake' ? 'Lake' : 'River'} spot${s.area ? ' · ' + esc(s.area) : ''} · ${s.pin ? (s.pin.mode === 'lake' ? 'traced from the lake\'s outlet, through the lake' : 'placed on the mapped river') : 'not on the mapped river network'}`;
  const strongest = o[0];
  const nearest = [...o].sort((a, b) => (a.travel_h ?? 1e9) - (b.travel_h ?? 1e9))[0];
  const spills = o.reduce((a, x) => a + (x.spills_a_year || 0), 0);
  $('#sp-facts').innerHTML = [
    ['Overflows upstream', String(o.length), `within ${IDX.settings.max_upstream_km} km along the rivers`],
    ['Nearest, by model time', nearest ? hours(nearest.travel_h) : '–', nearest ? `${nice(nearest.name)}, ${num(nearest.distance_km)} km` : ''],
    ['Highest model weight', strongest ? fmtW(strongest.weight) : '–', strongest ? `${nice(strongest.name)}: survival times dilution, 0 to 1` : ''],
    ['Spills a year, all of them', o.length ? Math.round(spills).toLocaleString('en-GB') : '–', 'sum of each overflow\'s yearly average (EDM)'],
  ].map(([t, v, n]) => `<div><dt>${t}</dt><dd>${v}<small>${esc(n) || '&nbsp;'}</small></dd></div>`).join('');
}

// ------------------------------------------------------------------ the network map
function boxOf(s) {
  const pts = [[s.lon, s.lat], ...s.overflows.map(o => [o.lon, o.lat]), ...s.lines.flatMap(l => l.coords)];
  let w = Math.min(...pts.map(p => p[0])), e = Math.max(...pts.map(p => p[0])), so = Math.min(...pts.map(p => p[1])), n = Math.max(...pts.map(p => p[1]));
  const padY = Math.max(0.01, (n - so) * 0.08), padX = Math.max(0.016, (e - w) * 0.08);
  return { w: w - padX, e: e + padX, s: so - padY, n: n + padY };
}
function ovMark(o, maxW) {
  const r = Math.min(12, 3 + 2.2 * Math.sqrt((o.spills_a_year || 0) / 10));
  return `<circle r="${r.toFixed(1)}" class="ov" data-w="${(0.25 + 0.75 * Math.min(1, (o.weight || 0) / maxW)).toFixed(2)}"/>`;
}
function drawNet() {
  const s = SPOT, maxW = Math.max(1e-6, ...s.overflows.map(o => o.weight || 0));
  const pts = s.overflows.map(o => ({ id: o.id, lat: o.lat, lon: o.lon, name: `${nice(o.name)}: ${num(o.distance_km)} km, ${hours(o.travel_h)} by the model`, mark: ovMark(o, maxW) }));
  pts.push({ id: '__spot', lat: s.lat, lon: s.lon, name: s.name, mark: '<circle r="7" class="spot"/>' });
  const isPhone = innerWidth < 760;
  LAB.drawMap($('#net'), pts, {
    box: boxOf(s), maxH: isPhone ? 420 : 580, selected: '__spot', label: s.name,
    lines: s.lines.map(l => ({ coords: l.coords, cls: l.form === 'lake' ? 'lake' : '' })),
    aria: `Rivers and overflows upstream of ${s.name}`,
    onHover: id => hl(id), onPick: id => id !== '__spot' && hl(id, true),
  });
  $('#net-key').innerHTML = s.overflows.length
    ? `<span><i class="spot"></i>the swim spot</span><span><i class="ln"></i>mapped river joining an overflow</span><span><i class="ov"></i>overflow: size, spills a year; darker, more weight</span><span><i class="wait"></i>not yet arrived on the model's clock</span>`
    : '';
  applyClock();
}
function hl(id, scroll) {
  document.querySelectorAll('#net .pt').forEach(n => n.classList.toggle('hl', n.dataset.id === id));
  document.querySelectorAll('#ovtable tr[data-id]').forEach(r => r.classList.toggle('hl', r.dataset.id === id));
  if (scroll && id) document.querySelector(`#ovtable tr[data-id="${CSS.escape(id)}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// ------------------------------------------------------------------ the model's clock (an illustration)
function renderClock() {
  const s = SPOT, set = IDX.settings;
  if (!s.overflows.length) {
    $('#clock').innerHTML = `<span class="tag">Upstream</span><p class="big">None</p><p>${s.meta.note ? 'This spot sits off the mapped river network (a pond, quarry lake or sea-fed water), so nothing is traced to it.' : `No monitored overflow lies on the mapped rivers within ${set.max_upstream_km} km upstream.`}</p><p class="note">That is not the same as clean water: farms, drains, birds and unmonitored outfalls are not in this map.</p>`;
    return;
  }
  $('#clock').innerHTML = `<span class="tag">The model's clock, if every overflow spilled at hour 0</span>
    <p class="big" id="ck-big"></p><p id="ck-line" style="margin:0"></p>
    <div class="ctl"><button type="button" id="ck-play">Play</button><input type="range" id="ck-range" min="0" max="${Math.max(1, T)}" value="${T}" aria-label="Hours after a spill"></div>
    <p class="illus"><b>Illustration.</b> When water would arrive at the model's assumed speed: ${set.river_velocity_ms} m/s in rivers, about ${Math.round(set.river_velocity_ms * 86.4)} km a day, with a lake holding water for its residence time. A real spill moves faster in a flood and slower in a dry spell. No spill's path was tracked.</p>`;
  $('#ck-range').oninput = e => { stopClock(); setT(+e.target.value); };
  $('#ck-play').onclick = () => {
    if (clockTimer) return stopClock();
    const max = +$('#ck-range').max;
    let t = T >= max ? 0 : T;
    $('#ck-play').textContent = 'Pause';
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    clockTimer = setInterval(() => { t = Math.min(max, t + Math.max(1, max / (reduce ? 4 : 90))); setT(Math.round(t)); if (t >= max) stopClock(); }, reduce ? 600 : 60);
  };
  setT(T);
}
function stopClock() { clearInterval(clockTimer); clockTimer = null; const b = $('#ck-play'); if (b) b.textContent = 'Play'; }
function setT(t) {
  T = t;
  if ($('#ck-range')) $('#ck-range').value = t;
  const o = SPOT.overflows, arrived = o.filter(x => x.travel_h != null && x.travel_h <= t);
  const wAll = o.reduce((a, x) => a + (x.weight || 0), 0), wIn = arrived.reduce((a, x) => a + (x.weight || 0), 0);
  if ($('#ck-big')) {
    $('#ck-big').innerHTML = `${t < 48 ? t + ' h' : (t / 24).toFixed(1) + ' days'}<small>after the spill</small>`;
    $('#ck-line').innerHTML = `Water from <b>${arrived.length} of ${o.length}</b> overflows would have reached the spot, ${wAll ? Math.round(100 * wIn / wAll) : 0}% of the summed model weight at this spot.`;
  }
  applyClock();
}
function applyClock() {
  const by = Object.fromEntries((SPOT?.overflows || []).map(o => [o.id, o]));
  document.querySelectorAll('#net .pt').forEach(n => {
    const o = by[n.dataset.id], c = n.querySelector('.ov');
    if (!o || !c) return;
    const wait = o.travel_h == null || o.travel_h > T;
    c.classList.toggle('wait', wait);
    c.style.fillOpacity = wait ? '' : c.dataset.w;
  });
}

// ------------------------------------------------------------------ overflow by overflow
function renderTable() {
  const o = SPOT.overflows;
  if (!o.length) { $('#list-intro').textContent = 'Nothing to list for this spot.'; $('#ovtable').innerHTML = ''; return; }
  const maxW = Math.max(...o.map(x => x.weight || 0));
  const rows = showAll ? o : o.slice(0, 15);
  $('#list-intro').innerHTML = `The model's weight is how strongly it counts a spill from that overflow at this spot, from 0 to 1: the survival factor for the journey (${IDX.settings.t90_h} h for a tenfold fall) times a dilution factor that is lower when the overflow joins a much smaller river than the one at the spot. Dilution lowers concentration by mixing; it removes no bacteria. So the weight is not the share of a spill that arrives, and without each spill's volume it cannot say what share of the spot's pollution an overflow causes. Its settings were fitted to samples; nothing was measured at this spot. Hover a row to find it on the map.`;
  $('#ovtable').innerHTML = `<table><thead><tr><th>Overflow</th><th>Into</th><th>Along the rivers</th><th>Model travel</th><th>Survival × dilution</th><th>Spills a year</th><th>Model weight</th></tr></thead><tbody>${rows.map(x =>
    `<tr data-id="${esc(x.id)}"><td><span class="nm">${esc(nice(x.name))}</span><span class="sub">${esc(x.company || '')} · ${esc(x.id)}</span></td><td>${esc(nice(x.water) || '–')}</td>
     <td class="n">${num(x.distance_km)} km${x.lake_km ? `<span class="sub">${num(x.lake_km)} km of it in a lake</span>` : ''}</td><td class="n">${hours(x.travel_h)}</td>
     <td class="n">${x.decay != null ? fmtW(x.decay) : '–'} × ${x.dilution != null ? fmtW(x.dilution) : '–'}</td><td class="n">${num(x.spills_a_year, 0)}</td>
     <td class="n"><span class="w" style="width:${Math.max(2, 70 * (x.weight || 0) / maxW)}px"></span>${fmtW(x.weight || 0)}</td></tr>`).join('')}</tbody></table>
    ${o.length > 15 ? `<div class="more"><button type="button" id="more">${showAll ? 'Show the first 15' : `Show all ${o.length}`}</button></div>` : ''}`;
  $('#ovtable').querySelectorAll('tr[data-id]').forEach(r => { r.onmouseenter = () => hl(r.dataset.id); r.onmouseleave = () => hl(null); });
  const m = $('#more'); if (m) m.onclick = () => { showAll = !showAll; renderTable(); };
}

// ------------------------------------------------------------------ the research, by leg of the journey
function renderJourney() {
  const set = IDX.settings, E = Object.fromEntries(CAT.entries.map(e => [e.id, e]));
  const legs = [
    ['How fast does it travel?', `Now: ${set.river_velocity_ms} m/s in every river, about ${Math.round(set.river_velocity_ms * 86.4)} km a day, whatever the flow.`, ['transport-fit', 'transport-grid-2']],
    ['How much is diluted?', 'Now: dilution grows with the length of river upstream of the spot against the overflow (the square root, from the transport fit).', ['flow-dilution', 'spill-size-proxies']],
    ['How long do bacteria survive?', `Now: a tenfold fall every ${set.t90_h} hours of the journey, the same in sun and shade.`, ['dieoff-weather']],
    ['What does a lake do?', 'Now: a lake on the way holds the water for its residence time and mixes it; distance inside the spot\'s lake is measured through the water.', ['lake-transport', 'lake-direction', 'lake-near-field', 'lake-wind']],
    ['Would better rain or flow data help?', 'Now: forecast rain feeds the spill model; the journey uses no river flow at all.', ['radar-rain', 'glofas']],
    ['Are the overflows in the right place?', 'Now: each overflow is placed on the mapped river by its outfall position, with checked corrections.', ['overflow-positions', 'outfall-channel', 'overflow-catchments']],
  ];
  const first = t => { const m = String(t).match(/^.*?[.!?](\s|$)/); return m ? m[0] : t; };
  $('#journey').innerHTML = legs.map(([q, now, ids]) => `<div class="leg"><h3>${q}</h3><p class="now">${esc(now)}</p>${ids.filter(i => E[i]).map(i => {
    const e = E[i];
    return `<div class="rec"><span class="st ${e.stage}">${e.stage}</span><b>${esc(e.title)}.</b> ${esc(first(e.verdict))}
      <details><summary>The record</summary><p>${esc(e.verdict)}</p>${e.scope ? `<p>${esc(e.scope)}</p>` : ''}${e.stage_note ? `<p>${esc(e.stage_note)}</p>` : ''}${e.reopen_when ? `<p><i>Reopen when:</i> ${esc(e.reopen_when)}</p>` : ''}</details></div>`;
  }).join('')}</div>`).join('');
}

function renderQuestions() {
  const sp = IDX.spots, total = sp.reduce((a, s) => a + (s.overflows || 0), 0), drawn = sp.reduce((a, s) => a + (s.with_path || 0), 0);
  const qs = [
    ['How fast does a spill really travel?', `Every river uses one speed, ${IDX.settings.river_velocity_ms} m/s, fitted to samples. A flow-based speed and dilution was tried and failed, partly because archived gauge data lagged.`, 'Compare the model\'s arrival times with measured ones: the Environment Agency\'s time-of-travel surveys where they exist (an outside data request), or samples taken in the hours after a spill the live feed reports at a few frequently sampled spots.', 'Agreement only on the reaches the speed was fitted on, or timing errors no smaller than the gap between samples.'],
    ['Why do some overflows have no drawn path?', `${total - drawn} of ${total.toLocaleString('en-GB')} overflow links reached their spot in the forecast's own tracing, but the line walk here found no unbroken mapped route (a gap the network mends with a short repair, or a braided channel).`, 'List them with their repair links, draw the repairs, and check each against the map. A deterministic data fix, not a model change.', 'Any fix that changes a forecast without its own regression example.'],
    ['Which overflows weigh most across all spots?', 'Each overflow\'s weight is per spot. Summed over every spot it affects and times its spills a year, it would show which outfalls most often reach swimmers.', 'One offline table from these files, published as a research observation with careful wording: exposure in the model, not blame or measured harm.', 'A ranking that moves a lot when the 60 km cut-off or the speed changes within its tested range.'],
    ['Does the 60 km cut-off leave anything out?', 'Overflows beyond 60 km are dropped because the model gives them very little weight.', 'Trace to 100 km for every spot and add up the weight beyond 60 km. Cheap and offline.', 'If the weight beyond 60 km is a sizeable share at large rivers, the cut-off needs its own test.'],
  ];
  $('#qs').innerHTML = qs.map(([q, what, how, bad]) => `<li><div><h3>${q}</h3><p><span class="k">Where it stands.</span> ${what}</p><p><span class="k">What would settle it.</span> ${how}</p><p style="margin:0"><span class="k">Unconvincing if.</span> ${bad}</p></div></li>`).join('');
}

// ------------------------------------------------------------------ start
Promise.all([PATHS + 'index.json', PATHS + 'overview.json', DATA + 'research_catalogue.v1.json'].map(u => fetch(u).then(r => { if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); })))
  .then(async ([idx, ov, cat]) => {
    IDX = idx; CAT = cat;
    await LAB.loadOutline('../');
    $('#attrib').textContent = [...IDX.credit, 'Map: ' + LAB.credit()].join('. ') + '.';
    renderFront(ov); renderPicker(); renderJourney(); renderQuestions();
    const h = new URLSearchParams(location.hash.slice(1)).get('spot');
    await selectSpot(IDX.spots.some(s => s.id === h) ? h : 'bw-uke4100-08901');
    window.addEventListener('hashchange', () => { const k = new URLSearchParams(location.hash.slice(1)).get('spot'); if (k && k !== SPOT?.id) selectSpot(k); });
    let rz, w = innerWidth;
    window.addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => { if (innerWidth === w) return; w = innerWidth; drawNet(); }, 200); });
  })
  .catch(err => { $('#front-answer').textContent = `Could not read the research files (${err.message}). Serve the repository root: see README.md in the Research Lab folder.`; });
