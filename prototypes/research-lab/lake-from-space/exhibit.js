// The lake from space: Research Lab exhibit 1. Reads the committed research files as they are:
//   data/research/lake_observations.v1.json  readings and lab values (docs/LAKE-OBSERVATIONS-CONTRACT-v1.md)
//   data/research/lake_imagery.v1.json       real Sentinel-2 pictures of the pilot sites (docs/LAKE-IMAGERY-CONTRACT-v1.md)
//   exploration.json                         scripts/lake_from_space_explore.py (exploratory, on seen data)
// Nothing is interpolated or generated: a date without a clear image has no reading and no picture, and a gap in the
// record is drawn as a gap. The index and the lab values each keep their own axis and unit.

const DATA = '../../../data/research/';
const RECENT_GAP = 14;              // days without a clear reading before a gap is drawn
const X0 = [5, 1], X1 = [10, 31];   // the record's window each year: May to October (October experimental)
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const fmt = (iso, opt = {}) => new Date(iso.slice(0, 10) + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: opt.noYear ? undefined : 'numeric', timeZone: 'UTC' });
const utcTime = iso => new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) + ' UTC';
const num = (v, dp = 2) => (v == null ? '–' : (v < 0 ? '−' : '') + Math.abs(v).toFixed(dp));
const pct = v => `${Math.round(v * 100)}%`;
const dayMs = iso => Date.parse(iso.slice(0, 10) + 'T12:00:00Z');
const daysBetween = (a, b) => Math.round((dayMs(b) - dayMs(a)) / 864e5);
const todayISO = new Date().toISOString().slice(0, 10);
const plural = (n, one, many = one + 's') => `${n.toLocaleString('en-GB')} ${n === 1 ? one : many}`;
const sat = item => (item || '').slice(0, 3).replace('S2', 'Sentinel-2');

let OBS, IMG, EXP, WIDE, RUNS, LAKES = {}, PICS = {}, WPIC = {}, heroLake = 'wqa-SW-50900003', flipTimer = null;
const S = { lake: null, date: null, year: null, layer: 'tci', bright: true, compare: null };

// ------------------------------------------------------------------ colour of the index, the imagery manifest's legend
function ndciColour(v) {
  const L = IMG.method.index_legend, c = L.colours, t = Math.max(0, Math.min(1, (v - L.min) / (L.max - L.min))) * (c.length - 1);
  const i = Math.min(c.length - 2, Math.floor(t)), f = t - i;
  return `rgb(${c[i].map((x, k) => Math.round(x + (c[i + 1][k] - x) * f)).join(',')})`;
}
function rampCSS() {
  const c = IMG.method.index_legend.colours;
  return `linear-gradient(90deg, ${c.map((x, i) => `rgb(${x.join(',')}) ${i / (c.length - 1) * 100}%`).join(', ')})`;
}

// ------------------------------------------------------------------ the lakes
function region(l) {
  if (l.lon > 1.2) return 'Norfolk Broads';
  if (l.lat > 54.2 && l.lon < -2.6) return 'Lake District';
  if (l.lat > 53.7) return 'Pennines and the North';
  if (l.lat > 52.3) return 'Midlands and Cheshire';
  return 'South of England';
}
const REGIONS = ['Lake District', 'Pennines and the North', 'Midlands and Cheshire', 'Norfolk Broads', 'South of England'];
const primaries = l => l.series.filter(s => s.primary);
const kind = l => (l.site_ids?.bathing_water ? 'Bathing water' : 'EA chlorophyll point');
const isPilot = l => !!l.operation?.pilot;
const small = l => !l.mask?.passes_size_rule;

function lakeTag(l) {
  if (small(l)) return 'too small';
  if (PICS[l.lake_id]?.scenes.length) return 'weekly · pictures';
  if (isPilot(l)) return 'weekly';
  return `${primaries(l).length} readings`;
}

// ------------------------------------------------------------------ hash state
function readHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  return { lake: h.get('lake'), date: h.get('date') };
}
function writeHash() {
  const h = new URLSearchParams();
  if (S.lake) h.set('lake', S.lake);
  if (S.date) h.set('date', S.date);
  history.replaceState(null, '', '#' + h.toString());
}

// ------------------------------------------------------------------ frontispiece
function renderFront() {
  const r = EXP.reproduction, w = EXP.within_season, cal = EXP.direction.calendar;
  $('#front-answer').innerHTML =
    `A little, and less than it first appears. Across ${r.record_386.lakes} lakes the satellite index ranks lab chlorophyll ` +
    `moderately well (rank correlation ${num(r.record_386.rho)}). Within one lake's summer it moves with the lab values ` +
    `only weakly once the time of year is taken out (${num(w.month_removed.rho)}), and it calls the direction of a change ` +
    `no better than the calendar does (${pct(cal.index_same_direction)} against ${pct(cal.calendar_same_direction)}). ` +
    `It cannot tell harmful algae from harmless, and cloud leaves gaps of weeks.`;
  const pics = IMG.sites.flatMap(s => s.scenes.filter(c => c.quality === 'shown')).map(c => c.datetime).sort();
  $('#front-status').innerHTML =
    `<b>Exploratory.</b> Historical record May–September 2020–2026, ${plural(OBS.coverage.usable, 'clear reading')} at ` +
    `${OBS.coverage.with_reading} sites. Five lakes checked weekly since 31 October 2026; newest picture ${fmt(pics[pics.length - 1])}.`;

  renderHero();
  $('#contact').addEventListener('click', e => { const b = e.target.closest('button[data-hero]'); if (b) { heroLake = b.dataset.hero; renderHero(); } });
}

// A wide picture: 4 km of the real scene, the 800 m plate window and the reading's 300 m circle marked on it.
function wideHTML(lid, opts = {}) {
  const w = WPIC[lid], l = LAKES[lid];
  if (!w) return '';
  const km = 1000 / (2 * WIDE.radius_m) * 100;
  return `<div class="im" style="aspect-ratio:${opts.ratio || '1'}"><img src="../${w.file}" alt="True-colour Sentinel-2 picture, 4 km across, around ${esc(l.water_body)}, ${fmt(w.datetime)}">
      <span class="box" title="the 800 m plate; dashed: the 300 m the reading uses"></span><span class="bar" style="width:100%"><i style="width:${km}%"></i>1 km</span></div>
    <figcaption><b>${esc(l.water_body)}</b>, ${fmt(w.datetime)}, ${utcTime(w.datetime)}, ${sat(w.item_id)}. 4 km across; the square is the 800 m plate below, the dashed circle the 300 m the reading uses. Cloud is shown as it was. Brightened for viewing.</figcaption>`;
}
function renderHero() {
  $('#hero').innerHTML = wideHTML(heroLake);
  $('#contact').innerHTML = OBS.pilot.sites.map(id => {
    const w = WPIC[id], l = LAKES[id];
    return `<button type="button" data-hero="${id}" aria-current="${id === heroLake}"><span class="im">${w ? `<img src="../${w.file}" alt="">` : ''}</span><span class="cap"><b>${esc(l.water_body.replace(' Great Pond', ''))}</b>${w ? fmt(w.datetime) : ''}</span></button>`;
  }).join('') + `<p class="contact-note"><a href="#lake=${heroLake}" style="color:var(--deep-ink)" id="hero-open">Open ${esc(LAKES[heroLake].water_body)} below</a>. The five lakes checked weekly, each on its newest picture.</p>`;
  $('#hero-open').onclick = e => { e.preventDefault(); selectLake(heroLake); $('#s-lake').scrollIntoView({ behavior: 'smooth' }); };
}

// ------------------------------------------------------------------ atlas: index, picker, map
function renderAtlas() {
  const byRegion = {};
  for (const l of OBS.lakes) (byRegion[region(l)] ||= []).push(l);
  $('#atlas-aside').textContent = `${OBS.coverage.lakes} sites on ${OBS.coverage.water_bodies} water bodies`;
  $('#lake-index').innerHTML = REGIONS.filter(r => byRegion[r]).map(r =>
    `<h4>${r}</h4>` + byRegion[r].sort((a, b) => a.name.localeCompare(b.name)).map(l =>
      `<button type="button" data-lake="${l.lake_id}"><span class="nm">${esc(l.name)}</span><span class="tg">${lakeTag(l)}</span>` +
      `<span class="sb">${kind(l)}${l.lab.length ? ` · ${l.lab.length} lab values` : ''}</span></button>`).join('')).join('');
  $('#lake-index').addEventListener('click', e => { const b = e.target.closest('button[data-lake]'); if (b) selectLake(b.dataset.lake); });
  $('#lake-select').innerHTML = REGIONS.filter(r => byRegion[r]).map(r =>
    `<optgroup label="${r}">${byRegion[r].map(l => `<option value="${l.lake_id}">${esc(l.name)} (${lakeTag(l)})</option>`).join('')}</optgroup>`).join('');
  $('#lake-select').addEventListener('change', e => selectLake(e.target.value));

  drawAtlasMap();
}
function drawAtlasMap() {
  LAB.drawMap($('#map'), OBS.lakes.map(l => ({ id: l.lake_id, lat: l.lat, lon: l.lon, name: l.name, kind: small(l) ? 'small' : isPilot(l) ? 'pilot' : 'hist' })),
    { selected: S.lake, onPick: id => selectLake(id) });
}

// ------------------------------------------------------------------ selection
function selectLake(id, date) {
  const l = LAKES[id];
  if (!l) return;
  S.lake = id; S.compare = null;
  document.querySelectorAll('#lake-index [data-lake]').forEach(b => b.setAttribute('aria-current', b.dataset.lake === id));
  $('#lake-select').value = id;
  const ps = primaries(l);
  const pics = (PICS[id]?.scenes || []).filter(c => c.quality === 'shown');
  S.date = date && ps.some(s => s.date === date) ? date
    : pics.length ? pics[pics.length - 1].datetime.slice(0, 10)
    : ps.length ? ps[ps.length - 1].date : null;
  S.year = S.date ? +S.date.slice(0, 4) : null;
  renderLakeHead(); renderYears(); selectDate(S.date, { keepYear: true });
  drawAtlasMap(); renderContext(); renderFlip(); drawScatter();
}

function selectDate(date, opt = {}) {
  S.date = date;
  if (date && !opt.keepYear) S.year = +date.slice(0, 4);
  renderPlates(); renderReading(); renderYears(); renderChart(); renderTable(); writeHash();
}

// ------------------------------------------------------------------ lake heading and facts
function renderLakeHead() {
  const l = LAKES[S.lake], ps = primaries(l), seasons = l.seasons.filter(s => s.scenes);
  const scenes = seasons.reduce((a, s) => a + s.scenes, 0), usable = seasons.reduce((a, s) => a + s.usable, 0);
  $('#lk-name').textContent = l.name;
  const share = l.shares_water_body_with?.length ? ` · shares ${esc(l.water_body)} with ${plural(l.shares_water_body_with.length, 'other site')}` : '';
  $('#lk-meta').innerHTML = `${kind(l)} · ${region(l)} · ${l.lat.toFixed(4)}°N ${Math.abs(l.lon).toFixed(4)}°${l.lon < 0 ? 'W' : 'E'}${share}`;
  $('#lk-link').innerHTML = isPilot(l) ? `Checked weekly · last check ${fmt(l.operation.last_run_at)}` : 'Historical record only';
  const lab = l.lab.map(x => x.value);
  const latest = l.latest;
  const age = latest ? daysBetween(latest.date, todayISO) : null;
  $('#lk-facts').innerHTML = [
    ['Latest clear reading', latest ? fmt(latest.date) : 'none', latest ? `${plural(age, 'day')} ago` : small(l) ? 'too small for 20 m pixels' : ''],
    ['Clear images', small(l) ? '–' : `${usable.toLocaleString('en-GB')} of ${scenes.toLocaleString('en-GB')}`, l.series_scope === 'every_scene' ? 'every image May–Sep' : 'only images within a day of a lab sample'],
    ['Lab chlorophyll samples', lab.length ? String(lab.length) : 'none', lab.length ? `${num(Math.min(...lab), 1)}–${num(Math.max(...lab), 0)} µg/l` : 'no EA samples at this point'],
    ['Depth', l.depth_m ? `${num(l.depth_m, 1)} m` : 'not recorded', l.lake_type ? `${l.lake_type} (mean depth, HydroLAKES)` : ''],
  ].map(([t, v, s]) => `<div><dt>${t}</dt><dd>${v}<small>${s || '&nbsp;'}</small></dd></div>`).join('');
  $('#rec-aside').textContent = `${plural(ps.length, 'reading')} · ${plural(l.lab.length, 'lab value')}`;
  $('#rec-intro').textContent = l.series_scope === 'every_scene'
    ? 'Every image of this site from May to September was checked. Each dot is a clear reading; hatching marks two weeks or more with no clear image. Below, the Environment Agency\'s lab chlorophyll on its own scale.'
    : 'For this point only images within a day of a lab sample were read, so the space between dots is not cloud: those images were never read. An × marks a lab sample with no clear image within a day.';
}

// ------------------------------------------------------------------ plates
function scenesWithPictures() { return (PICS[S.lake]?.scenes || []).filter(c => c.quality === 'shown' || c.quality.startsWith('excluded')); }
function sceneFor(date) { return (PICS[S.lake]?.scenes || []).find(c => c.quality === 'shown' && c.datetime.slice(0, 10) === date); }

function plateHTML(scene, n, label) {
  const l = LAKES[S.lake];
  if (!scene) {
    const site = PICS[S.lake];
    const why = !site && !isPilot(l) ? 'Pictures are kept only for the five lakes checked weekly. This lake has its index readings but no saved picture.'
      : site && site.scenes.length ? 'This date has a reading but no saved picture yet. Pictures of older readings are being added a few a week.'
      : `No clear image of ${esc(l.water_body)} has been taken since the weekly checks began.`;
    return `<figure class="plate"><div class="frame empty"><div class="msg"><b>No picture</b>${why}</div></div>
      <figcaption><span class="plate-no">Plate ${n}.</span> ${esc(l.name)}${S.date ? `, ${fmt(S.date)}` : ''}</figcaption></figure>`;
  }
  const idx = scene.index_url ? `<img class="layer index" src="${DATA + scene.index_url}" alt="">` : '';
  const excluded = scene.quality.startsWith('excluded');
  return `<figure class="plate"><div class="frame" data-layer="${S.layer}">
      <img class="tci${S.bright ? ' bright' : ''}" src="${DATA + scene.image_url}" alt="True-colour Sentinel-2 picture, 800 m across, of ${esc(l.water_body)} on ${fmt(scene.datetime)}">
      ${idx}<img class="layer mask" src="${DATA + scene.mask_url}" alt="">
      <span class="ring"></span><span class="pin"></span>
      <span class="north"><svg width="10" height="12" viewBox="0 0 10 12"><path d="M5 0l5 12-5-3-5 3z" fill="#fff"/></svg>N</span>
      <span class="scale"><i></i>100 m</span>
    </div>
    <figcaption><span class="plate-no">Plate ${n}${label ? ` · ${label}` : ''}.</span> ${esc(l.water_body)}, ${fmt(scene.datetime)}, ${utcTime(scene.datetime)}.
      ${excluded ? 'Not used: ' + esc(scene.quality.split(':')[1].replace(/_/g, ' ')) + '.' : ''}
      <span class="log">${sat(scene.item_id)} · tile ${esc(scene.tile.replace('MGRS-', ''))} · clear ${pct(scene.clear_share_in_core)} of core · index on ${plural(scene.index_pixels || 0, 'pixel')}${scene.ndci != null ? ` · NDCI ${num(scene.ndci, 3)}` : ''}</span></figcaption></figure>`;
}

function renderPlates() {
  const main = S.date ? sceneFor(S.date) : null, all = scenesWithPictures();
  const cmp = S.compare ? all.find(c => c.item_id === S.compare) : null;
  $('#plates').className = 'plates' + (cmp ? ' two' : '');
  $('#plates').innerHTML = plateHTML(main, 1, cmp ? 'selected' : '') + (cmp ? plateHTML(cmp, 2, 'compare') : '');
  const hasPic = !!main, hasIdx = !!main?.index_url;
  const others = all.filter(c => c !== main);
  $('#plate-controls').innerHTML = !all.length ? '' : `
    <div class="seg" role="group" aria-label="Layer">
      ${[['tci', 'True colour'], ['index', 'Index on read pixels'], ['mask', 'Not-clear mask']].map(([k, t]) =>
        `<button type="button" data-layer="${k}" aria-pressed="${S.layer === k}" ${!hasPic || (k === 'index' && !hasIdx) ? 'disabled' : ''}>${t}</button>`).join('')}
    </div>
    <label class="chk"><input type="checkbox" id="bright" ${S.bright ? 'checked' : ''}> Brighten for viewing</label>
    <label class="chk">Compare with <select id="cmp" style="font:inherit;min-height:36px;margin-left:4px">
      <option value="">nothing</option>${others.map(c => `<option value="${c.item_id}" ${S.compare === c.item_id ? 'selected' : ''}>${fmt(c.datetime)}${c.quality.startsWith('excluded') ? ' (not used)' : ''}${c.item_id.slice(0, 3) !== (main?.item_id || '').slice(0, 3) ? '' : ''}</option>`).join('')}
    </select></label>
    <div class="legend">${S.layer === 'mask' ? '<span class="cloud"></span> cloud, shadow, snow or no data' : `<span>${num(IMG.method.index_legend.min, 1)}</span><span class="ramp" style="background:${rampCSS()}"></span><span>${num(IMG.method.index_legend.max, 1)}</span><span>NDCI, drawn only on the pixels the reading used</span>`}</div>
    <p class="note" style="margin-top:8px">Brightening changes only what you see; readings come from the unaltered bands. Each square is 10 m.</p>`;
  $('#plate-controls').querySelectorAll('[data-layer]').forEach(b => b.onclick = () => { S.layer = b.dataset.layer; renderPlates(); });
  const br = $('#bright'); if (br) br.onchange = () => { S.bright = br.checked; renderPlates(); };
  const cs = $('#cmp'); if (cs) cs.onchange = () => { S.compare = cs.value || null; renderPlates(); };
  if (!hasIdx && S.layer === 'index') { S.layer = 'tci'; renderPlates(); }
}

// ------------------------------------------------------------------ the reading beside the plate
function renderReading() {
  const l = LAKES[S.lake], ps = primaries(l), i = ps.findIndex(s => s.date === S.date), s = ps[i];
  if (!s) {
    $('#reading').innerHTML = `<p class="big">–</p><p>${small(l) ? 'This site is too small for the satellite\'s 20 m pixels: fewer than 9 pixels of open water lie wholly inside the 300 m circle, so no reading is made.' : 'No clear reading.'}</p><p class="claim">${esc(OBS.claim.public_wording)}</p>`;
    return;
  }
  const lab = l.lab.map(x => ({ ...x, d: daysBetween(s.date, x.sample_time) })).filter(x => Math.abs(x.d) <= 3).sort((a, b) => Math.abs(a.d) - Math.abs(b.d))[0];
  const labLine = lab ? `${lab.censored === '<' ? 'below ' : lab.censored === '>' ? 'above ' : ''}${num(lab.value, lab.value < 10 ? 1 : 0)} µg/l, ${lab.d === 0 ? 'the same day' : `${plural(Math.abs(lab.d), 'day')} ${lab.d > 0 ? 'later' : 'earlier'}`}`
    : 'none within 3 days';
  const age = daysBetween(s.date, todayISO);
  const pics = scenesWithPictures().filter(c => c.quality === 'shown');
  const exp = s.experimental || s.season === 'out_of_season';
  $('#reading').innerHTML = `
    <div class="stepper"><button type="button" id="prev" ${i <= 0 ? 'disabled' : ''}>← Earlier reading</button><button type="button" id="next" ${i >= ps.length - 1 ? 'disabled' : ''}>Later reading →</button><span class="pos">${i + 1} of ${ps.length}</span></div>
    <div class="when">${fmt(s.date)} <span class="muted" style="font-weight:400">· ${utcTime(s.datetime)} · ${plural(age, 'day')} ago</span></div>
    <p class="big"><span style="display:inline-block;width:18px;height:18px;border:1px solid var(--hair);vertical-align:2px;margin-right:10px;background:${ndciColour(s.ndci)}"></span>${num(s.ndci, 3)}<small>NDCI, an index from −1 to 1</small></p>
    <div>${exp ? '<span class="tagline exp">experimental: outside May–September</span>' : '<span class="tagline">May–September</span>'}${s.source !== 'test_cache' ? '<span class="tagline">weekly check</span>' : ''}</div>
    <dl>
      <dt>Satellite</dt><dd>${sat(s.item_id)}, tile ${esc(s.tile.replace('MGRS-', ''))}</dd>
      <dt>Open water read</dt><dd>${s.clear_core} of ${s.n_core} core pixels clear (${pct(s.clear_core / s.n_core)})</dd>
      ${s.sun_elevation_deg != null ? `<dt>Sun height</dt><dd>${num(s.sun_elevation_deg, 1)}°</dd>` : ''}
      <dt>Lab chlorophyll</dt><dd>${labLine}</dd>
      <dt>Picture</dt><dd>${sceneFor(s.date) ? 'saved, Plate 1' : pics.length ? 'none saved for this date' : isPilot(l) ? 'none yet: no clear image since weekly checks began' : 'not kept for this lake'}</dd>
    </dl>
    <p class="note">Two readings of one lake on one day differ by ${num(OBS.quality.same_date_abs_difference_median, 2)} at the median and by ${num(OBS.quality.same_date_abs_difference_p90, 2)} one time in ten, so a change smaller than that may be the measurement, not the water.</p>
    <p class="claim">${esc(OBS.claim.public_wording)}</p>`;
  $('#prev').onclick = () => selectDate(ps[i - 1].date);
  $('#next').onclick = () => selectDate(ps[i + 1].date);
}

// ------------------------------------------------------------------ the record: one barcode row per season
function yearSpan(y) { return [Date.UTC(y, X0[0] - 1, X0[1], 12), Date.UTC(y, X1[0] - 1, X1[1], 12)]; }
function renderYears() {
  const l = LAKES[S.lake];
  const years = [...new Set([...l.seasons.map(s => s.year), ...primaries(l).map(s => +s.date.slice(0, 4))])].sort();
  const W = 600, H = 22;
  $('#years').innerHTML = years.map(y => {
    const [a, b] = yearSpan(y), x = iso => (dayMs(iso) - a) / (b - a) * W;
    const sea = l.seasons.find(s => s.year === y) || {};
    const reads = primaries(l).filter(s => s.date.startsWith(y));
    const labs = l.lab.filter(x2 => x2.sample_time.startsWith(y) && dayMs(x2.sample_time) >= a && dayMs(x2.sample_time) <= b);
    const oct = (Date.UTC(y, 9, 1, 12) - a) / (b - a) * W;
    const reason = sea.reason === 'no_source_images' ? 'no images in the archive collection' : sea.reason === 'no_lab_sample_dates' ? 'not read: no lab sample that summer' : '';
    const svg = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true"><rect class="bg" x="0" y="0.5" width="${W}" height="${H - 1}" fill="none" stroke="var(--line)"/>
      <rect x="${oct}" y="1" width="${W - oct}" height="${H - 2}" fill="var(--paper-2)"/>
      ${reads.map(s => `<rect x="${x(s.date) - 1}" y="3" width="2.2" height="11" fill="${s.season === 'out_of_season' ? '#8a6a2c' : 'var(--ink)'}"/>`).join('')}
      ${labs.map(s => `<rect x="${x(s.sample_time) - 1.5}" y="16" width="3" height="3" fill="var(--lab)"/>`).join('')}</svg>`;
    const cnt = reason ? '–' : `${plural(reads.length, 'reading')}`;
    return `<button type="button" class="yr" data-year="${y}" aria-pressed="${S.year === y}" ${reads.length ? '' : 'disabled'}><span class="yl">${y}</span><span class="ys">${svg}${reason ? `<span class="yr-why">${reason}</span>` : ''}</span><span class="yc">${cnt}${labs.length ? ` · ${labs.length} lab` : ''}</span></button>`;
  }).join('');
  $('#years').querySelectorAll('.yr').forEach(b => b.onclick = () => {
    S.year = +b.dataset.year;
    const r = primaries(LAKES[S.lake]).filter(s => s.date.startsWith(S.year));
    selectDate(r.length ? r[r.length - 1].date : S.date, { keepYear: true });
  });
}

// ------------------------------------------------------------------ the record: the chosen season in detail
function renderChart() {
  const l = LAKES[S.lake], y = S.year;
  if (!y) { $('#chart').innerHTML = ''; $('#chart-note').innerHTML = ''; return; }
  const W = Math.max(300, Math.round($('#chart').clientWidth || 1000)), narrow = W < 600;
  const padL = narrow ? 40 : 64, padR = narrow ? 8 : 16, laneA = [30, 190], laneB = [232, 330], H = 362;
  const [a, b] = yearSpan(y), x = iso => padL + (dayMs(iso) - a) / (b - a) * (W - padL - padR);
  const NMIN = -0.3, NMAX = 0.5, yN = v => laneA[1] - (Math.max(NMIN, Math.min(NMAX, v)) - NMIN) / (NMAX - NMIN) * (laneA[1] - laneA[0]);
  const reads = primaries(l).filter(s => s.date.startsWith(y));
  const labs = l.lab.filter(s => s.sample_time.startsWith(y) && dayMs(s.sample_time) >= a && dayMs(s.sample_time) <= b);
  const allLab = l.lab.map(s => s.value).filter(v => v > 0);
  const lo = Math.pow(10, Math.floor(Math.log10(Math.min(1, ...allLab)))), hi = Math.pow(10, Math.ceil(Math.log10(Math.max(10, ...allLab))));
  const yL = v => laneB[1] - (Math.log10(Math.max(lo, v)) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo)) * (laneB[1] - laneB[0]);
  const oct = x(`${y}-10-01`);
  const months = ['May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct'];
  let g = '';
  g += `<rect x="${oct}" y="${laneA[0] - 14}" width="${W - padR - oct}" height="${laneB[1] - laneA[0] + 14}" fill="var(--paper-2)"/>`;
  g += `<text x="${oct + 6}" y="${laneA[0] - 2}" style="font:11px var(--font-text);fill:var(--faint)">${narrow ? 'Oct' : 'outside the tested season'}</text>`;
  // gaps: only where every image was read
  if (l.series_scope === 'every_scene') {
    const inS = reads.filter(s => s.season === 'in_season').map(s => s.date);
    const edges = [`${y}-05-01`, ...inS, `${y}-09-30`];
    for (let k = 1; k < edges.length; k++) {
      const gd = daysBetween(edges[k - 1], edges[k]);
      if (gd > RECENT_GAP) g += `<rect x="${x(edges[k - 1]) + 3}" y="${laneA[0]}" width="${Math.max(0, x(edges[k]) - x(edges[k - 1]) - 6)}" height="${laneA[1] - laneA[0]}" fill="url(#hatch)"><title>${gd} days without a clear image</title></rect>`;
    }
  }
  for (let m = 0; m < 6; m++) {
    const xm = x(`${y}-${String(m + 5).padStart(2, '0')}-01`);
    g += `<line x1="${xm}" x2="${xm}" y1="${laneA[0] - 14}" y2="${laneB[1]}" stroke="var(--hair)"/>${narrow && m === 5 ? '' : `<text x="${xm + 4}" y="${H - 8}">${months[m]}</text>`}`;
  }
  for (const v of [-0.2, 0, 0.2, 0.4]) g += `<line x1="${padL}" x2="${W - padR}" y1="${yN(v)}" y2="${yN(v)}" stroke="${v === 0 ? 'var(--rule)' : 'var(--hair)'}"/><text x="${padL - 8}" y="${yN(v) + 4}" text-anchor="end">${num(v, 1)}</text>`;
  for (let v = lo; v <= hi; v *= 10) g += `<line x1="${padL}" x2="${W - padR}" y1="${yL(v)}" y2="${yL(v)}" stroke="var(--hair)"/><text x="${padL - 8}" y="${yL(v) + 4}" text-anchor="end">${v >= 1 ? v : v.toFixed(1)}</text>`;
  g += `<text class="lane-label" x="${padL}" y="${laneA[0] - 18}">Satellite index (NDCI)</text>`;
  g += `<text class="lane-label" x="${padL}" y="${laneB[0] - 12}">Lab chlorophyll, µg/l (log scale)</text>`;
  if (!labs.length) g += `<text x="${padL + 12}" y="${(laneB[0] + laneB[1]) / 2 + 4}" style="font:12px var(--font-text);fill:var(--faint)">${l.lab.length ? `No lab sample at this point in ${y}` : 'The Environment Agency takes no chlorophyll samples at this point'}</text>`;
  // lab samples with no clear image within a day (near-lab points): an x on the index lane's floor
  if (l.series_scope !== 'every_scene') {
    for (const s of labs) {
      if (dayMs(s.sample_time) > Date.UTC(y, 8, 30, 23)) continue;
      const hit = reads.some(r => Math.abs(daysBetween(r.date, s.sample_time)) <= 1);
      if (!hit) { const xx = x(s.sample_time); g += `<path d="M${xx - 4} ${laneA[1] - 10}l8 8m0 -8l-8 8" stroke="var(--faint)" stroke-width="1.5"><title>Lab sample ${fmt(s.sample_time)}: no clear image within a day</title></path>`; }
    }
  }
  for (const s of labs) {
    const xx = x(s.sample_time), yy = yL(s.value), open = s.censored === '<';
    g += `<path d="M${xx} ${yy - 5}l5 5-5 5-5-5z" fill="${open ? 'var(--card)' : 'var(--lab)'}" stroke="var(--lab)" stroke-width="1.5"><title>${fmt(s.sample_time)}: ${open ? 'below ' : ''}${s.value} µg/l</title></path>`;
  }
  for (const s of reads) {
    const xx = x(s.date), yy = yN(s.ndci), on = s.date === S.date, clip = s.ndci < NMIN || s.ndci > NMAX;
    g += `<g class="dot" tabindex="0" role="button" data-date="${s.date}" aria-label="${fmt(s.date)}, NDCI ${num(s.ndci, 3)}${s.season === 'out_of_season' ? ', experimental' : ''}">
      ${on ? `<line x1="${xx}" x2="${xx}" y1="${laneA[0] - 4}" y2="${laneB[1]}" stroke="var(--pick)" stroke-dasharray="3 3"/>` : ''}
      <circle cx="${xx}" cy="${yy}" r="${on ? 7 : 5}" fill="${ndciColour(s.ndci)}" stroke="${on ? 'var(--pick)' : s.season === 'out_of_season' ? '#8a6a2c' : 'var(--ink)'}" stroke-width="${on ? 2.5 : 1}" ${s.season === 'out_of_season' ? 'stroke-dasharray="2 1.5"' : ''}/>
      ${clip ? `<text x="${xx + 8}" y="${yy + 4}">${num(s.ndci, 2)}</text>` : ''}
      ${sceneFor(s.date) ? `<rect x="${xx - 2}" y="${laneA[1] + 6}" width="4" height="4" fill="var(--brand)"><title>picture saved</title></rect>` : ''}
      <circle cx="${xx}" cy="${yy}" r="12" fill="transparent"/></g>`;
  }
  $('#chart').innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="Readings and lab values for ${y}">
    <defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="var(--gap)" stroke-width="1.2"/></pattern></defs>${g}</svg>`;
  $('#chart').querySelectorAll('.dot').forEach(d => {
    d.onclick = () => selectDate(d.dataset.date);
    d.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectDate(d.dataset.date); requestAnimationFrame(() => document.querySelector(`.dot[data-date="${d.dataset.date}"]`)?.focus()); } };
  });
  $('#chart-note').innerHTML = `<span><span class="sw" style="background:${rampCSS()}"></span>clear reading, coloured by value</span>` +
    (l.series_scope === 'every_scene' ? `<span><span class="sw gap"></span>over ${RECENT_GAP} days with no clear image</span>` : '<span>× lab sample, no clear image within a day</span>') +
    `<span><span class="sw" style="background:var(--lab)"></span>lab sample (open: below the lab's limit)</span><span><span class="sw off"></span>October: experimental</span><span><span class="sw" style="background:var(--brand);width:6px"></span>picture saved</span>`;
}

function renderTable() {
  const l = LAKES[S.lake], y = String(S.year || '');
  const rows = [
    ...primaries(l).filter(s => s.date.startsWith(y)).map(s => ({ d: s.date, k: 'Satellite', v: `NDCI ${num(s.ndci, 3)}`, n: `${sat(s.item_id)}, ${s.clear_core}/${s.n_core} clear${s.season === 'out_of_season' ? ', experimental' : ''}` })),
    ...l.lab.filter(s => s.sample_time.startsWith(y)).map(s => ({ d: s.sample_time.slice(0, 10), k: 'Lab', v: `${s.censored || ''}${s.value} µg/l`, n: 'EA determinand 7887' })),
  ].sort((p, q) => p.d.localeCompare(q.d));
  $('#rec-table .scroll').innerHTML = `<table><thead><tr><th>Date</th><th>Kind</th><th>Value</th><th>Note</th></tr></thead><tbody>${rows.map(r => `<tr><td>${fmt(r.d)}</td><td>${r.k}</td><td class="mono">${esc(r.v)}</td><td>${esc(r.n)}</td></tr>`).join('')}</tbody></table>`;
}

// ------------------------------------------------------------------ section 2: the 4 km view and every pass
function renderContext() { $('#context').innerHTML = WPIC[S.lake] ? wideHTML(S.lake, { ratio: '16 / 7' }) : ''; $('#context').hidden = !WPIC[S.lake]; }

// Every satellite pass the weekly checks read at this lake, clear or not, one frame a date (the clearest tile).
function passes(lid) {
  const byDate = {};
  for (const run of RUNS) for (const r of run.rows || []) {
    if (r.lake_id !== lid) continue;
    const k = r.scene_date, cur = byDate[k];
    if (!cur || r.clear_core / r.n_core > cur.clear_core / cur.n_core) byDate[k] = r;
  }
  const pics = Object.fromEntries((PICS[lid]?.scenes || []).filter(c => c.image_url).map(c => [c.item_id, c]));
  return Object.values(byDate).sort((a, b) => a.datetime.localeCompare(b.datetime)).map(r => ({ ...r, pic: pics[r.item_id] }));
}
function renderFlip() {
  clearInterval(flipTimer); flipTimer = null;
  const F = passes(S.lake), el = $('#flipbook');
  if (!F.length) { el.innerHTML = ''; return; }
  const win = RUNS[0].window;
  let i = Math.max(0, F.map(f => !!f.pic).lastIndexOf(true));
  el.innerHTML = `<div class="sec-head" style="margin-top:36px;border-top-color:var(--line)"><h3 style="margin:0">Every pass since the weekly checks began</h3><span class="aside">${fmt(win.from)} to ${fmt(F[F.length - 1].datetime)} · ${plural(F.length, 'date')}</span></div>
    <div class="flip"><div><div id="flip-frame"></div>
      <div class="ctl"><button type="button" id="flip-play">Play</button><input type="range" id="flip-range" min="0" max="${F.length - 1}" value="${i}" aria-label="Pass date"></div></div>
      <div><p class="note" style="margin-top:0">Sentinel-2 passed over ${esc(LAKES[S.lake].water_body)} on ${plural(F.length, 'date')} in the fortnight. A picture is kept only when at least 80% of the reading's open water was clear; every other pass is shown blank, with how much of that water the satellite could see. Nothing is filled in between.</p>
        <div class="strip" id="flip-strip">${F.map((f, k) => `<button type="button" data-k="${k}" aria-label="${fmt(f.datetime)}">${f.pic ? `<img src="${DATA + f.pic.image_url}" alt="">` : ''}<span>${f.scene_date.slice(8)}</span></button>`).join('')}</div></div></div>`;
  const show = k => {
    i = k; const f = F[k], clear = f.clear_core / f.n_core;
    $('#flip-frame').innerHTML = f.pic
      ? `<div class="frame"><img class="tci bright" src="${DATA + f.pic.image_url}" alt="True-colour picture, ${fmt(f.datetime)}"><span class="ring"></span><span class="stamp">${fmt(f.datetime)}</span></div><figcaption><span class="log">${sat(f.item_id)} · ${pct(clear)} of core clear · ${f.pic.quality.startsWith('excluded') ? 'not used: ' + esc(f.pic.quality.split(':')[1].replace(/_/g, ' ')) : 'NDCI ' + num(f.pic.ndci, 3)}</span></figcaption>`
      : `<div class="frame cloud"><span class="stamp">${fmt(f.datetime)}</span><div class="msg"><b>${clear === 0 ? 'No clear water' : pct(clear) + ' clear'}</b>${clear === 0 ? 'Cloud or shadow over all of the reading\'s open water' : 'Not enough clear water for a reading'}</div></div><figcaption><span class="log">${sat(f.item_id)} · ${f.core_cloud_high ? f.core_cloud_high + ' of ' + f.n_core + ' core pixels high cloud' : 'unknown, not clean'}</span></figcaption>`;
    $('#flip-range').value = k;
    el.querySelectorAll('#flip-strip button').forEach(b => b.setAttribute('aria-current', +b.dataset.k === k));
  };
  show(i);
  $('#flip-range').oninput = e => show(+e.target.value);
  $('#flip-strip').onclick = e => { const b = e.target.closest('button'); if (b) show(+b.dataset.k); };
  $('#flip-play').onclick = () => {
    if (flipTimer) { clearInterval(flipTimer); flipTimer = null; $('#flip-play').textContent = 'Play'; return; }
    if (i >= F.length - 1) show(0);
    $('#flip-play').textContent = 'Pause';
    flipTimer = setInterval(() => { if (i >= F.length - 1) { clearInterval(flipTimer); flipTimer = null; $('#flip-play').textContent = 'Play'; return; } show(i + 1); }, 650);
  };
}

// ------------------------------------------------------------------ findings
const noteW = LAB.noteW;
function scatterSVG() {
  const P = EXP.pairs, W = noteW(), H = W < 440 ? 240 : 300, pl = 44, pb = 30, pt = 10, pr = 10;
  const x = v => pl + (Math.max(-0.3, Math.min(0.5, v)) + 0.3) / 0.8 * (W - pl - pr);
  const y = v => H - pb - (Math.log10(Math.max(0.3, v)) - Math.log10(0.3)) / (Math.log10(300) - Math.log10(0.3)) * (H - pb - pt);
  let g = '';
  for (const v of [-0.2, 0, 0.2, 0.4]) g += `<line x1="${x(v)}" x2="${x(v)}" y1="${pt}" y2="${H - pb}" stroke="var(--hair)"/><text x="${x(v)}" y="${H - 12}" text-anchor="middle">${num(v, 1)}</text>`;
  for (const v of [1, 10, 100]) g += `<line x1="${pl}" x2="${W - pr}" y1="${y(v)}" y2="${y(v)}" stroke="var(--hair)"/><text x="${pl - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
  g += `<text x="${W - pr}" y="${H}" text-anchor="end">satellite index (NDCI) →</text><text x="4" y="${pt + 4}" >µg/l</text>`;
  const on = P.filter(p => p.lake_id === S.lake), off = P.filter(p => p.lake_id !== S.lake);
  g += off.map(p => `<circle cx="${x(p.ndci)}" cy="${y(p.chl)}" r="3" fill="${p.censored === '<' ? 'none' : 'rgba(27,35,40,.28)'}" stroke="rgba(27,35,40,.45)" stroke-width=".8"/>`).join('');
  g += on.map(p => `<circle cx="${x(p.ndci)}" cy="${y(p.chl)}" r="5" fill="var(--pick)" stroke="#fff" stroke-width="1"><title>${fmt(p.sample_day)}: NDCI ${num(p.ndci, 3)}, ${p.chl} µg/l</title></circle>`).join('');
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Scatter of ${P.length} satellite readings against lab chlorophyll, ${on.length} at the chosen lake">${g}</svg>`;
}
function drawScatter() { const el = $('#scatter'); if (el && S.lake) { el.innerHTML = scatterSVG(); const n = EXP.pairs.filter(p => p.lake_id === S.lake).length; $('#scatter-cap').textContent = n ? `Orange: ${esc(LAKES[S.lake].name)}, ${plural(n, 'pair')}.` : `${LAKES[S.lake].name} has no pairs: no lab sample with a clear image within a day.`; } }

function bars(items, max = 1, ref = null, fmtv = pct) { return LAB.dots(items, { max, ref, fmt: fmtv }); }

function renderNotes() {
  const r = EXP.reproduction, w = EXP.within_season, dir = EXP.direction, cal = dir.calendar, dc = EXP.detectable_change, gp = EXP.gaps, py = EXP.pairing_yield;
  const shallow = py.table.filter(t => t.group === 'shallow' && t.season !== 2022);
  const flags = EXP.quality_flags.slice(0, 6);
  $('#notes').innerHTML = `
  <div class="fnote"><span class="tag">Note 1 · across lakes · the #386 test, stated in advance</span>
    <p class="fig">ρ ${num(r.record_386.rho)} <small>rank correlation, ${r.record_386.pairs} pairs at ${r.record_386.lakes} lakes</small></p>
    <div id="scatter"></div><p class="note" id="scatter-cap"></p>
    <p>Greener-looking lakes tend to have more chlorophyll in the lab. The test set its bar before the values were fetched and missed it by 0.0003 on the interval's lower end (${num(r.record_386.ci[0], 4)}), so its verdict stays <i>fails as stated; promising, not validated</i>. Rebuilt here from the published files: ${r.pairs} pairs, ρ ${num(r.pooled_rho)} (${num(r.ci[0])} to ${num(r.ci[1])}).</p></div>

  <div class="fnote"><span class="tag">Note 2 · within one lake's summer · exploratory</span>
    <p class="fig">ρ ${num(w.month_removed.rho)} <small>after removing each lake's summer level and the time of year</small></p>
    ${bars([{ label: 'Lake and summer level removed', v: w.rho, ci: w.ci, c: 'var(--rule)' }, { label: '…and the month removed', v: w.month_removed.rho, ci: w.month_removed.ci, c: 'var(--brand)' }], 0.7, null, v => num(v))}
    <p>Most of the headline correlation is between lakes: the Broads are green, Wast Water is clear. Inside one lake's summer the index still moves with the lab values (${num(w.rho)}), but part of that is both rising through the summer. With the month taken out, ${num(w.month_removed.rho)} remains (${num(w.month_removed.ci[0])} to ${num(w.month_removed.ci[1])}, ${w.lakes} lakes): a real but weak day-to-day signal.</p></div>

  <div class="fnote"><span class="tag">Note 3 · the direction of a change · exploratory</span>
    <p class="fig">${pct(cal.index_same_direction)} <small>against ${pct(cal.calendar_same_direction)} for the calendar alone</small></p>
    ${bars([{ label: 'Index, same direction as lab', v: cal.index_same_direction, c: 'var(--brand)' }, { label: 'Calendar guess', v: cal.calendar_same_direction }], 1, { v: 0.5, label: 'coin toss' })}
    <p>Between two lab samples a month or more apart, the index moved the same way as the lab value ${pct(cal.index_same_direction)} of the time (${cal.changes} changes). Guessing from the time of year alone did as well or better: the difference is ${num(cal.index_minus_calendar * 100, 0)} points (${num(cal.ci[0] * 100, 0)} to ${num(cal.ci[1] * 100, 0)}). So the record does not yet show that the index tells you more about a rise or fall than the calendar would.</p></div>

  <div class="fnote"><span class="tag">Note 4 · how big a change means anything</span>
    <p class="fig">${num(dc.repeat_p90)} <small>NDCI: one repeat reading in ten differs by this much</small></p>
    ${bars([{ label: 'Repeat, median', v: dc.repeat_median }, { label: 'Repeat, 1 in 10', v: dc.repeat_p90, c: 'var(--pick)' }, { label: 'A typical summer\'s spread', v: dc.season_spread_p10_p90_median, c: 'var(--brand)' }], 0.25, null, v => num(v))}
    <p>Two images of one lake on the same day usually agree within ${num(dc.repeat_median)}, but one pair in ten differs by ${num(dc.repeat_p90)} or more. A typical lake's whole summer spans about ${num(dc.season_spread_p10_p90_median)} (10th to 90th percentile, ${dc.lake_seasons} lake-summers). Only ${pct(dc.share_spread_over_repeat_p90)} of summers spread wider than that repeat noise.</p></div>

  <div class="fnote"><span class="tag">Note 5 · how often the sky allows a look</span>
    <p class="fig">${gp.median_gap_days} days <small>median wait between clear readings, May–September</small></p>
    <p>At the ${gp.lakes} lakes where every image was read, half the waits were ${gp.median_gap_days} days or less, but ${pct(gp.share_gaps_over_14_days)} ran past two weeks and the longest was ${gp.longest_gap_days} days. The exhibit draws those as gaps. It never joins two readings with a line.</p></div>

  <div class="fnote"><span class="tag">Note 6 · enough data to test it properly in 2027?</span>
    <p class="fig">${Math.min(...py.shallow_pairs_per_season)}–${Math.max(...py.shallow_pairs_per_season)} <small>shallow-lake pairs a summer, against a minimum of ${py.protocol_minimum.pairs}</small></p>
    ${bars(shallow.map(t => ({ label: `${t.season}: ${t.samples} samples`, v: t.pairs, c: t.pairs >= 30 ? 'var(--brand)' : 'var(--rule)' })), 40, { v: 30, label: 'minimum' }, v => String(v))}
    <p>The draft 2027 test needs ${py.protocol_minimum.pairs} pairs at ${py.protocol_minimum.lakes} or more shallow lakes. Only 2026 reached that, with a higher pairing rate (${pct(shallow[shallow.length - 1].pairs / shallow[shallow.length - 1].samples)}) that may come from a third satellite in orbit (inferred, not checked). Weekly checks do not add pairs, because every image is already archived; what limits pairs is a lab sample falling within a day of a clear image.</p></div>

  <div class="fnote wide"><span class="tag">Note 7 · readings to look at twice</span>
    <p>These clear readings sit far outside their lake's usual range (more than 5 robust standard deviations). They may be real, or glint, haze or weed the cloud mask missed. They stay in the record, flagged here, not removed.</p>
    <table style="width:100%;border-collapse:collapse;font-size:13px">${flags.map(f => `<tr style="border-top:1px solid var(--hair)"><td style="padding:6px 8px 6px 0"><a href="#lake=${f.lake_id}&date=${f.date}" data-jump="${f.lake_id}|${f.date}">${esc(f.name)}</a></td><td class="mono">${fmt(f.date)}</td><td class="mono">NDCI ${num(f.ndci, 2)}</td><td class="mono muted">usual ${num(f.lake_median, 2)}</td></tr>`).join('')}</table></div>`;
  $('#notes').querySelectorAll('[data-jump]').forEach(a => a.onclick = e => { e.preventDefault(); const [id, d] = a.dataset.jump.split('|'); selectLake(id, d); $('#s-lake').scrollIntoView({ behavior: 'smooth' }); });
  drawScatter();
}

function renderQuestions() {
  const qs = [
    ['Does the index add anything to the calendar inside a lake\'s summer?', 'Note 2 found a weak signal beyond the time of year; Note 3 found the direction call no better than the calendar. Both were measured on data already examined.', 'A statement written before 1 May 2027 and scored on 2027 pairs only: the within-summer correlation with the month removed, and direction against the calendar guess, each with intervals over lakes.', 'The interval for "index minus calendar" sits across zero again, or the month-removed correlation\'s interval reaches zero.'],
    ['Can a shallow-lake calibration turn the index into a chlorophyll estimate with honest intervals?', 'The draft 2027 protocol (docs/SATELLITE-RECOVERY-2026-10.md, section 5). Note 6 suggests one summer may not provide 30 pairs.', 'Settle now whether 2027 and 2028 pool under one frozen calibration, or arrange lab samples timed to clear overpasses with a partner who samples anyway (an outside contact, Ethan\'s).', 'Skill against the lake\'s own mean with an interval reaching zero, or 80% intervals holding outside 70–90% of samples.'],
    ['Which outlying readings are artefacts?', 'Note 7 lists readings far outside their lake\'s range. The raw bands were not kept, so the cause cannot be checked offline.', 'Re-read the bands and scene classification for the flagged scenes (about 10 requests each, within the pilot allocation), and write a screening rule that never looks at lab values.', 'A rule that improves agreement with the lab only because it was tuned on the same lab values.'],
    ['Does 300 m of open water speak for the lake?', 'Every reading is the median of a 300 m circle. Blooms often gather at shores and in bays.', 'For the five pilot lakes, read the index over the whole lake on the same clear dates and compare with the circle; a bigger window costs more bytes, so measure one lake first.', 'Differences between the circle and the lake no larger than the repeat noise of Note 4: then the circle is not the limiting factor.'],
  ];
  $('#qs').innerHTML = qs.map(([q, what, how, bad]) => `<li><div><h3>${q}</h3><p><span class="k">Where it stands.</span> ${what}</p><p><span class="k">What would settle it.</span> ${how}</p><p style="margin:0"><span class="k">Unconvincing if.</span> ${bad}</p></div></li>`).join('');
}

// ------------------------------------------------------------------ start
Promise.all([DATA + 'lake_observations.v1.json', DATA + 'lake_imagery.v1.json', 'exploration.json', '../assets/wide/wide.json', DATA + 'satellite/pilot_runs.json'].map(u => fetch(u).then(r => { if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); })))
  .then(async ([o, i, e, w, runs]) => {
    OBS = o; IMG = i; EXP = e; WIDE = w; RUNS = runs;
    for (const p of WIDE.pictures) WPIC[p.lake_id] = p;
    await LAB.loadOutline('../');
    for (const l of OBS.lakes) LAKES[l.lake_id] = l;
    for (const s of IMG.sites) PICS[s.lake_id] = s;
    $('#attrib').textContent = [...new Set([...OBS.attribution, ...IMG.attribution])].join('. ') + '. Map: ' + LAB.credit() + '.';
    renderFront(); renderAtlas(); renderNotes(); renderQuestions();
    const h = readHash();
    selectLake(LAKES[h.lake] ? h.lake : OBS.pilot.sites[0], h.date);
    let rz; window.addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => { renderChart(); renderNotes(); drawAtlasMap(); }, 150); });
    window.addEventListener('hashchange', () => { const k = readHash(); if (k.lake && (k.lake !== S.lake || k.date !== S.date)) selectLake(k.lake, k.date); });
  })
  .catch(err => { $('#front-answer').textContent = `Could not read the research files (${err.message}). Serve the repository root: see README.md beside this page.`; });
