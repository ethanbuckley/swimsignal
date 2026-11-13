// The catchment workspace's what-if mode (CATCH-SIM, docs/CATCH-SIM-2026-12.md). Reads data/index.json and
// data/<place>.json, made by scripts/lab_catch_sim.py from the production spill model and cached inputs.
// Every figure is the model's answer on days already past: never "would cut", "will", or a prediction of an upgrade.
// A level word always has its noun ("High risk"). "Take away" means the overflow's term leaves the spot's
// combination; no covariate is edited (PR #298: lta_spills is not monotone). The setting lives in the URL hash.

const $ = s => document.querySelector(s);
const esc = LAB.esc;
const CUTS = [15, 40, 70];                      // transport.SCORE_CUTS: the shown score's level boundaries
const LEVELS = ['low', 'moderate', 'high', 'very high'];
const LWORD = ['Low risk', 'Moderate risk', 'High risk', 'Very high risk'];
const LVAR = ['--low', '--moderate', '--high', '--veryhigh'];
const lv = score => (score < CUTS[0] ? 0 : score < CUTS[1] ? 1 : score < CUTS[2] ? 2 : 3);
const ABBR = new Set(['STW', 'WWTW', 'WTW', 'CSO', 'SPS', 'PS', 'SSO', 'EO', 'WRC', 'DWF']);
// "ILKLEY MIDDLETON/CSO" -> "Ilkley Middleton/CSO": capitals kept for abbreviations and for words with a figure (3XDWF)
const nice = s => String(s || '').split(/(\s+|\/|-)/).map(w => (w === w.toUpperCase() && /[A-Z]{2}/.test(w) && !/\d/.test(w) && !ABBR.has(w.replace(/[^A-Z]/g, ''))) ? w[0] + w.slice(1).toLowerCase() : w).join('');
const n1 = v => Number(v).toLocaleString('en-GB', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const plural = (n, one, many = one + 's') => `${n.toLocaleString('en-GB')} ${n === 1 ? one : many}`;
const fmtD = (d, o = { day: 'numeric', month: 'short', year: 'numeric' }) => new Date(d + 'T12:00:00Z').toLocaleDateString('en-GB', { ...o, timeZone: 'UTC' });
const iso = (y, i) => new Date(Date.UTC(y, 0, 1 + i)).toISOString().slice(0, 10);
const scaleWord = s => (s === 1 ? 'as it fell' : `${s.toFixed(1)} times as it fell`);

let IDX, P = null, S = {};
const CACHE = {};

// ------------------------------------------------------------------ state <-> URL
function readHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  const ids = IDX.places.map(p => p.id);
  const s = Number(h.get('rain'));
  return {
    p: ids.includes(h.get('p')) ? h.get('p') : 'cromwheel',
    y: ['2024', '2025'].includes(h.get('y')) ? h.get('y') : '2025',
    s: Number.isFinite(s) && s >= 0.5 && s <= 1.5 ? Math.round(s * 10) / 10 : 1,
    drop: h.get('drop') || 'none',
  };
}
function writeHash() {
  const q = new URLSearchParams({ p: S.p, y: S.y, rain: S.s.toFixed(1) });
  if (S.drop !== 'none') q.set('drop', S.drop);
  history.replaceState(null, '', '#' + q.toString());
}

async function load(id) {
  if (!CACHE[id]) CACHE[id] = await fetch(`data/${id}.json`).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
  return CACHE[id];
}
async function choose(id) {
  P = await load(id);
  S.p = id;
  if (!P.rain_allowed) S.s = 1;
  if (S.drop !== 'none' && !P.overflows.some(o => o.id === S.drop)) S.drop = 'none';
  render();
}

// ------------------------------------------------------------------ figures from the export
const series = (y, s, drop) => P.series[y][s.toFixed(1)][drop];
function counts(arr) { const c = [0, 0, 0, 0]; for (const v of arr) c[lv(v)] += 1; return c; }
// an overflow's name, with its id where two upstream share one (the two Kettlewell/STW outlets)
const ovName = id => { const o = P.overflows.find(x => x.id === id); if (!o) return id; const same = P.overflows.filter(x => x.name === o.name).length > 1; return nice(o.name) + (same ? ` (${o.id})` : ''); };
function lowered(y, s, drop) {
  const a = series(y, s, 'none'), b = series(y, s, drop);
  let n = 0;
  for (let i = 0; i < a.length; i++) if (lv(b[i]) < lv(a[i])) n += 1;
  return n;
}

// ------------------------------------------------------------------ front
function renderFront() {
  const y = S.y, base = counts(series(y, 1, 'none')), now = counts(series(y, S.s, S.drop));
  const mod = c => c[1] + c[2] + c[3];
  const changed = S.s !== 1 || S.drop !== 'none';
  const what = [S.s !== 1 ? `the rain ${scaleWord(S.s)}` : '', S.drop !== 'none' ? `${ovName(S.drop)} taken away` : ''].filter(Boolean).join(' and ');
  const say = !changed
    ? `As fitted, the model gave ${esc(P.short)} <b>${plural(mod(base), 'day')}</b> at moderate risk or above in ${y}. Change the rain or take an overflow away to see what it would have said instead.`
    : `With ${esc(what)}, the model would have given ${esc(P.short)} <b>${plural(mod(now), 'day')}</b> at moderate risk or above in ${y}, against ${mod(base)} as fitted.`;
  const other = y === '2024' ? '2025' : '2024';
  const ob = counts(series(other, 1, 'none')), on = counts(series(other, S.s, S.drop));
  const cal = P.calibration[y];
  LAB.answer($('#front-answer'), say,
    `The same setting in ${other}: ${mod(on)} days against ${mod(ob)} as fitted. Two years is the only spread shown; it is not an interval. ` +
    `At ${esc(P.short)}'s ${P.overflows.length} overflows the model expected ${n1(cal.expected)} spill days in ${y} and the EA's records show ${cal.observed} ` +
    `(${cal.ratio < 1 ? 'fewer' : 'more'} than expected: ${cal.ratio.toFixed(2)} times).`, 'The other year, and how well the model matched');
  const pts = IDX.places.map(p => ({ id: p.id, lat: p.lat, lon: p.lon, name: p.name, mark: '<circle r="6" class="cm"/>' }));
  LAB.drawMap($('#overview'), pts, { box: { w: -4.6, e: -0.4, s: 53.2, n: 55.2 }, selected: P.place, label: P.short, maxH: 460, aria: 'The two places', onPick: id => { if (id !== S.p) choose(id); } });
  $('#overview-cap').textContent = `${P.name}: ${plural(P.overflows.length, 'monitored overflow')} upstream (${P.company}).`;
}

// ------------------------------------------------------------------ controls
function renderControls() {
  $('#p-seg').innerHTML = IDX.places.map(p => `<button type="button" data-p="${p.id}" aria-pressed="${p.id === S.p}">${esc(p.short)}</button>`).join('');
  $('#p-seg').querySelectorAll('button').forEach(b => { b.onclick = () => { if (b.dataset.p !== S.p) choose(b.dataset.p); }; });
  $('#y-seg').innerHTML = P.years.map(y => `<button type="button" data-y="${y}" aria-pressed="${String(y) === S.y}">${y}</button>`).join('');
  $('#y-seg').querySelectorAll('button').forEach(b => { b.onclick = () => { S.y = b.dataset.y; render(); }; });
  const r = $('#rain');
  r.value = String(Math.round((S.s - 0.5) * 10));
  r.disabled = !P.rain_allowed;
  r.setAttribute('aria-valuetext', scaleWord(S.s));
  r.oninput = () => { S.s = 0.5 + Number(r.value) / 10; S.s = Math.round(S.s * 10) / 10; render(); };
  $('#rain-out').textContent = scaleWord(S.s);
  const m = IDX.monotonicity;
  $('#rain-note').textContent = P.rain_allowed
    ? `Every hour's rain in the archive is multiplied by this number. Kept because the check passed: ${m.overflows - m.non_monotone} of ${m.overflows} overflows give more expected spill days whenever the rain goes up.`
    : `Rain scaling is switched off: ${m.non_monotone} of ${m.overflows} overflows gave fewer expected spill days when the rain went up, over the 10% the record allowed.`;
  $('#drop').innerHTML = `<option value="none">None (the model as fitted)</option>` +
    P.overflows.map(o => `<option value="${o.id}" ${o.id === S.drop ? 'selected' : ''}>${esc(ovName(o.id))}, weight ${o.weight >= 0.01 ? o.weight.toFixed(2) : 'under 0.01'}</option>`).join('');
  $('#drop').value = S.drop;
  $('#drop').onchange = () => { S.drop = $('#drop').value; render(); };
  $('#reset').disabled = S.s === 1 && S.drop === 'none';
  $('#reset').onclick = () => { S.s = 1; S.drop = 'none'; render(); };
}

// ------------------------------------------------------------------ the level strip
function renderStrip() {
  const y = S.y, a = series(y, 1, 'none'), b = series(y, S.s, S.drop), n = a.length;
  const el = $('#strip'), W = Math.max(300, Math.round(el.clientWidth || 700)), narrow = W < 560;
  const left = narrow ? 0 : 118, top = narrow ? 18 : 4, rowH = 22, gap = narrow ? 30 : 10, cw = (W - left) / n;
  const H = top + 2 * rowH + gap + 26;
  const rows = [['As fitted', a], [S.s === 1 && S.drop === 'none' ? 'The what-if (same)' : 'The what-if', b]];
  let g = '';
  rows.forEach(([label, arr], r) => {
    const y0 = top + r * (rowH + gap);
    g += `<text x="0" y="${narrow ? y0 - 5 : y0 + 15}" class="lane-t">${label}</text>`;
    for (let i = 0; i < n; i++) g += `<rect x="${(left + i * cw).toFixed(2)}" y="${y0}" width="${(cw + 0.3).toFixed(2)}" height="${rowH}" style="fill:var(${LVAR[lv(arr[i])]})"><title>${fmtD(iso(+y, i))}: ${LWORD[lv(arr[i])]}, score ${arr[i]}</title></rect>`;
  });
  const by = top + 2 * rowH + gap;
  for (let m = 0; m < 12; m++) {
    const i = Math.round((Date.UTC(+y, m, 1) - Date.UTC(+y, 0, 1)) / 864e5), x = left + i * cw;
    g += `<line x1="${x}" x2="${x}" y1="${by}" y2="${by + 5}" class="base"/>`;
    if (!narrow || m % 2 === 0) g += `<text x="${x + 2}" y="${by + 17}" class="lane-s">${new Date(Date.UTC(+y, m, 1)).toLocaleDateString('en-GB', { month: 'short', timeZone: 'UTC' })}</text>`;
  }
  for (const st of P.storms.filter(s => s.day.startsWith(y))) {
    const i = Math.round((Date.parse(st.day) - Date.UTC(+y, 0, 1)) / 864e5), x = left + (i + 0.5) * cw;
    g += `<path d="M${x - 5} ${by + 24} L${x + 5} ${by + 24} L${x} ${by + 16} Z" class="storm"><title>Storm replayed: ${fmtD(st.day)}</title></path>`;
  }
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H + 4}" width="${W}" height="${H + 4}" role="img" aria-label="Level each day of ${y} at ${esc(P.short)}, as fitted and in the what-if">${g}</svg>`;
  $('#strip-key').innerHTML = LWORD.map((w, k) => `<span><i style="background:var(${LVAR[k]})"></i>${w}</span>`).join('') + `<span><i class="storm"></i>a storm replayed in section 4</span>`;
  $('#lv-head').textContent = `${P.short}'s level, each day of ${y}`;
  const ca = counts(a), cb = counts(b);
  $('#counts').innerHTML = `<table><thead><tr><th>Days at</th>${LWORD.map(w => `<th>${w}</th>`).join('')}</tr></thead><tbody>` +
    `<tr><th>As fitted</th>${ca.map(v => `<td>${v}</td>`).join('')}</tr>` +
    `<tr><th>The what-if</th>${cb.map((v, k) => `<td>${v}${v !== ca[k] ? ` <small>(${v > ca[k] ? '+' : '−'}${Math.abs(v - ca[k])})</small>` : ''}</td>`).join('')}</tr></tbody></table>`;
}

// ------------------------------------------------------------------ overflows: map and table
function renderOverflows() {
  const y = S.y, k = Math.round((S.s - 0.5) * 10);
  const maxW = Math.max(...P.overflows.map(o => o.weight));
  const pts = P.overflows.map(o => {
    const r = 3 + 6 * Math.sqrt(o.weight / maxW), gone = o.id === S.drop;
    return { id: o.id, lat: o.lat, lon: o.lon, name: `${ovName(o.id)}: weight ${o.weight.toFixed(3)}`,
             mark: `<circle r="${r.toFixed(1)}" class="ov ${gone ? 'gone' : 'on'}"/>` + (gone ? `<path d="M-7 -7 L7 7 M7 -7 L-7 7" class="x"/>` : '') };
  });
  pts.push({ id: P.spot, lat: P.spot_lat, lon: P.spot_lon, name: P.name, mark: '<circle r="6.5" class="spot focus"/>' });
  LAB.drawMap($('#net'), pts, {
    box: P.box, maxH: innerWidth < 760 ? 420 : 560, selected: P.spot, label: P.short,
    lines: P.lines.map(l => ({ coords: l.coords, cls: l.form === 'lake' ? 'lake' : '' })),
    aria: `Rivers and overflows upstream of ${P.name}`,
    onPick: id => { if (P.overflows.some(o => o.id === id)) { S.drop = S.drop === id ? 'none' : id; render(); } },
  });
  $('#net-key').innerHTML = `<span><i class="spot"></i>${esc(P.short)}</span><span><i class="ln"></i>mapped river or lake path</span><span><i class="ov"></i>overflow (size: the model's weight here)</span><span>tap one to take it away</span>`;
  const rows = P.overflows.map(o => {
    const e1 = o.expected[y][5], es = o.expected[y][k], gone = o.id === S.drop, low = lowered(y, S.s, o.id);
    return `<tr class="${gone ? 'gone' : ''}"><td>${esc(ovName(o.id))}</td><td>${o.weight >= 0.01 ? o.weight.toFixed(2) : '<0.01'}</td>` +
      `<td>${n1(e1)}</td><td>${S.s === 1 ? '–' : n1(es)}</td><td>${o.events_in_file ? o.observed[y] : '<span class="na">no record</span>'}</td>` +
      `<td>${low}</td><td>${o.log_removal.lowered} of ${o.log_removal.days}</td></tr>`;
  }).join('');
  $('#ovs').innerHTML = `<table><thead><tr><th>Overflow</th><th>Weight here</th><th>Expected spill days, as fitted</th><th>At this rain</th><th>EA spill days</th>` +
    `<th>Days a level lower without it</th><th>Issued forecasts a level lower without it</th></tr></thead><tbody>${rows}</tbody></table>` +
    `<p class="note">Expected spill days: the model's daily chances added up over ${y}. EA spill days: days with a spill in the EA's start/stop records for ${y}. ` +
    `"Days a level lower" counts days of ${y} at this rain. "Issued forecasts": the ${P.issued.days} forecasts SwimSignal issued for 3 and 4 days ahead from ${fmtD(P.issued.first_issue.slice(0, 10))} to ${fmtD(P.issued.last_issue.slice(0, 10))}, with that overflow's chance left out.</p>`;
}

// ------------------------------------------------------------------ storms
function renderStorms() {
  const idx = {};
  for (const r of P.storm_levels) idx[`${r.day}|${r.scale.toFixed(1)}|${r.removed}`] = r.level;
  const cell = (d, s, drop) => { const L = idx[`${d}|${s.toFixed(1)}|${drop}`]; return L ? `<span class="lv" style="--c:var(${LVAR[LEVELS.indexOf(L)]})">${LWORD[LEVELS.indexOf(L)]}</span>` : '–'; };
  const rows = [];
  for (const st of P.storms) {
    const days = [...new Set(P.storm_levels.filter(r => r.storm === st.day).map(r => r.day))];
    days.forEach((d, i) => rows.push(`<tr><td>${i ? '' : `<b>${fmtD(st.day)}</b><br><small>${n1(st.cells_mean_mm)} mm, mean over the rain cells</small>`}</td><td>${fmtD(d, { weekday: 'short', day: 'numeric', month: 'short' })}</td><td>${cell(d, 1, 'none')}</td><td>${cell(d, S.s, S.drop)}</td></tr>`));
  }
  $('#storms').innerHTML = `<table><thead><tr><th>Storm</th><th>Day</th><th>As fitted</th><th>The what-if</th></tr></thead><tbody>${rows.join('')}</tbody></table>` +
    `<p class="note">The three wettest days here in 2024–25 by the archive rain, at least a week apart, chosen by that rule before anything was run. Each is shown with the two days after it.</p>`;
}

// ------------------------------------------------------------------ checks
function renderChecks() {
  const m = IDX.monotonicity, pm = P.monotonicity, iss = P.issued, c = P.calibration, o = P.outside_fitted_rain, op = P.outside_place_rain;
  const pct = v => (v * 100).toLocaleString('en-GB', { maximumFractionDigits: 1 }) + '%';
  $('#checks').innerHTML =
    `<dt>Does more rain always mean more spills, in the model?</dt><dd><b>Yes, at all ${m.overflows} overflows</b> (both places). Over 11 rain settings and both years, no overflow's expected spill days fell when the rain went up, and none of ${pm.overflow_day_steps.toLocaleString('en-GB')} single overflow-day steps here did. The record's stop rule was more than 10%. This says the model moves the right way; it does not say by how much.</dd>` +
    `<dt>Does it rebuild the published forecast?</dt><dd><b>${iss.level_equal} of ${iss.days}</b> issued levels at 3 and 4 days ahead rebuilt exactly from the forecast log (largest difference in risk ${iss.max_abs_risk_diff.toExponential(0)}). ${iss.issues_without_travel_time} earlier issues could not be rebuilt: the log kept no travel times before 12 Oct 2026.</dd>` +
    `<dt>How well did the model match the records?</dt><dd>Expected against the EA's spill days at these overflows: ${c['2024'].expected.toFixed(0)} against ${c['2024'].observed} in 2024 (${c['2024'].ratio.toFixed(2)} times), ${c['2025'].expected.toFixed(0)} against ${c['2025'].observed} in 2025 (${c['2025'].ratio.toFixed(2)} times).` +
    (P.company === 'United Utilities' ? ' The model was fitted on United Utilities 2023–2025, so this is on its own training years.' : ' The model was not fitted on Yorkshire Water overflows.') + `</dd>` +
    `<dt>How often is the rain past what the cache has seen?</dt><dd>At 1.5 times: ${pct(op.share['1.5'])} of overflow-days here go past the wettest day in this place's own cells in 2023–25 (${n1(op.max_daily_mm_2023_25)} mm). The record's stated measure, against all 8 cells: ${pct(o['1.5'])}.</dd>` +
    `<dt>What it ran on</dt><dd>The production spill model (${esc(P.model_version.split(';').slice(0, 2).join(', '))}), the same one that issued the latest logged forecast. ERA5-Land archive rain from the forecast's own cache. Nothing fetched; ${Object.keys(IDX.inputs.shared_sha256).length} cached inputs hashed before and after, unchanged. Made ${fmtD(IDX.made.slice(0, 10))}, commit ${esc(IDX.commit)}.</dd>`;
}

function render() {
  writeHash();
  renderControls(); renderFront(); renderStrip(); renderOverflows(); renderStorms(); renderChecks();
}

async function init() {
  try {
    [IDX] = await Promise.all([fetch('data/index.json').then(r => r.json()), LAB.loadOutline('../../')]);
  } catch (e) {
    LAB.failed($('#front-answer'), e);
    return;
  }
  S = readHash();
  let rt; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => P && render(), 150); });
  addEventListener('hashchange', () => { const h = readHash(); if (h.p !== S.p) { S = h; choose(S.p); } else { S = h; render(); } });
  $('#attrib').textContent = 'Contains Environment Agency data, OGL v3.0. Weather data by Open-Meteo.com (CC BY 4.0), ERA5-Land: Copernicus Climate Change Service. Contains OS data © Crown copyright and database right 2026.';
  await choose(S.p);
}
init();
