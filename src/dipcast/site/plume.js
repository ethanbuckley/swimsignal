// The spill map (docs/PLUME-MAP-2026-10.md): on a spot's page, where water from each spill reported upstream
// in the last 48 hours may be, moved down its river at the forecast's own travel time, from 48 hours before
// the update to 48 hours after it, with a slider and play.
//
// What it draws, and how each kind is told apart in words as well as marks:
//   reported   a spill's times as its company's live feed gave them (the catchment replay's, replay.py).
//   estimated  where that water may be: released at each moment of the spill, it reaches the end of its
//              route (the spot) `travel_h` later, the overflow's modelled travel time (model.transport), and
//              fades as its bacteria die off (T90). A model estimate, said so on every line; never a
//              measurement of pollution, and never "clean" or "safe" where nothing is drawn.
//   unsure     water from a part of a spill the feed did not confirm: an end it never reported, or after
//              the update while a spill was still running ("if it kept spilling"). Dashed.
//   not known  an overflow with no current reading or no live feed: a grey hollow mark, counted in words.
//              A spill there would not be drawn. A route through a lake is not drawn as moving water.
// Spills that start after the update are not drawn: this shows reported spills, not forecast ones.
//
// Its data, all from the build (no request but these files): the replay (data/spot/<id>-replay.json, the
// spills and arrival times), the routes (data/spot/<id>-plume.json, src/dipcast/plume.py) and the trace
// (data/spot/<id>-trace.json, the rivers drawn grey). index.html adds this script, and asks for the files,
// when the map's place on the page comes near the screen (mountPlume).
//
// A plain script, like replay.js: in the page its names are globals (each begins plume or PLUME), and in
// Node the last lines export them (tests/site_plume.test.cjs).

const PLUME_TZ = 'Europe/London';
const PLUME_BACK_H = 48, PLUME_AHEAD_H = 48;   // the slider's reach either side of the update
const PLUME_STEP_H = 0.25;                       // the slider's step: 15 minutes
const PLUME_PLAY_H = 8;                          // hours of the slider a second of play moves through
const PLUME_PIECES = 4;                          // each stretch of water is drawn in this many parts, each faded by its age
const plumeEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const plumeMs = iso => (iso ? Date.parse(iso) : NaN);
const plumeName = o => (typeof overflowNames === 'function' ? overflowNames({ site_id: o.site_id, site_name: o.name }).plain : (o.name || o.site_id || ''));
const plumeCompany = c => (typeof companyName === 'function' ? companyName(c) : String(c ?? ''));
const PLUME_ESTIMATE = 'A model estimate of where water from reported spills may be, not a measurement of pollution.';
const PLUME_STATE = {
  stale: 'its feed had not updated within 6 hours, so its reading may be out of date',
  offline: 'no current reading: the monitor or its feed was not reporting',
  no_feed: 'no live feed from its company',
};

// "Sat 14:00" in UK time; "Sat 31 Oct 14:00" with the date.
function plumeTime(ms, withDate = false) {
  const p = new Intl.DateTimeFormat('en-GB', { timeZone: PLUME_TZ, weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    ...(withDate ? { day: 'numeric', month: 'short' } : {}) }).formatToParts(new Date(ms));
  const v = t => (p.find(x => x.type === t) || {}).value;
  return withDate ? `${v('weekday')} ${v('day')} ${v('month')} ${v('hour')}:${v('minute')}` : `${v('weekday')} ${v('hour')}:${v('minute')}`;
}
// "6 h after the update", "45 min before the update", "1 day 2 h after the update", "at the update"
function plumeFromUpdate(t, gen) {
  const m = Math.round((t - gen) / 6e4), a = Math.abs(m);
  if (a < 8) return 'at the update';
  const d = Math.floor(a / 1440), h = Math.round((a - d * 1440) / 60);
  const said = a < 60 ? `${a} min` : [d ? `${d} day${d === 1 ? '' : 's'}` : '', h ? `${h} h` : ''].filter(Boolean).join(' ');
  return `${said} ${m > 0 ? 'after' : 'before'} the update`;
}

// An encoded polyline (trace.py, encode) as [lat, lon] points.
function plumeDecode(str) {
  const pts = []; let i = 0, lat = 0, lon = 0;
  const next = () => { let shift = 0, res = 0, b; do { b = str.charCodeAt(i++) - 63; res |= (b & 31) << shift; shift += 5; } while (b >= 32); return res & 1 ? ~(res >> 1) : res >> 1; };
  while (i < str.length) { lat += next(); lon += next(); pts.push([lat / 1e5, lon / 1e5]); }
  return pts;
}
// Each point's distance along the line, in km (flat: near enough within 60 km), ending at the total.
function plumeMeasure(pts) {
  const out = [0];
  for (let i = 1; i < pts.length; i++) {
    const k = Math.cos(pts[i][0] * Math.PI / 180) * 111.32, dx = (pts[i][1] - pts[i - 1][1]) * k, dy = (pts[i][0] - pts[i - 1][0]) * 110.57;
    out.push(out[i - 1] + Math.hypot(dx, dy));
  }
  return out;
}
// The part of a line from fraction f0 to f1 of its length (0 the overflow, 1 the spot).
function plumeSlice(pts, cum, f0, f1) {
  const total = cum[cum.length - 1];
  if (!(total > 0) || f1 <= f0) return [];
  const at = f => { const d = f * total; let i = 1; while (i < cum.length - 1 && cum[i] < d) i++;
    const s = cum[i] - cum[i - 1], u = s > 0 ? (d - cum[i - 1]) / s : 0;
    return { i, p: [pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * u, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * u] }; };
  const a = at(f0), b = at(f1);
  return [a.p, ...pts.slice(a.i, b.i), b.p];
}

// What a spill released, as stretches of time: `sure` where the feed reported it discharging, unsure where it
// did not say (an end it never gave: from the last poll that saw it to the stop the feed gave, or to the update;
// and, while it was running at the update, on after it, as if it kept spilling: `b` Infinity).
function plumeReleases(sp, gen) {
  const a = plumeMs(sp.start);
  if (!Number.isFinite(a)) return [];
  if (sp.end_known && Number.isFinite(plumeMs(sp.end))) return [{ a, b: plumeMs(sp.end), sure: true }];
  if (sp.running) return [{ a, b: gen, sure: true }, { a: gen, b: Infinity, sure: false, kept: true }];
  const seen = Number.isFinite(plumeMs(sp.end_after)) ? plumeMs(sp.end_after) : a, by = Number.isFinite(plumeMs(sp.end_by)) ? plumeMs(sp.end_by) : gen;
  return [...(seen > a ? [{ a, b: seen, sure: true }] : []), ...(by > seen ? [{ a: seen, b: by, sure: false }] : [])];
}
// Where water released over [rel.a, rel.b] is at time t along a route travel_h long: fractions of the route,
// 0 the overflow and 1 the spot, and the ages (hours) of its oldest and newest water. Null when none of it is on
// the route at t: not released yet, or all past the spot. `past` true when some of it has passed the spot.
function plumeWater(rel, travelH, t) {
  if (!(travelH > 0) || t <= rel.a) return null;
  const T = travelH * 36e5, last = Math.min(rel.b, t);
  const head = (t - rel.a) / T, tail = (t - last) / T;
  if (tail >= 1) return null;
  return { f0: Math.max(tail, 0), f1: Math.min(head, 1), ageHead: (t - rel.a) / 36e5, ageTail: (t - last) / 36e5, past: head > 1, sure: rel.sure, kept: !!rel.kept };
}
// Where an overflow's water stands at t, from all its spills: 'coming' (on its way, not at the spot), 'at'
// (reaching the spot), 'passed' (all of it modelled past the spot, within the model's recent_h after), or null.
function plumeStand(row, gen, t, recentH = 48) {
  const T = (row.travel_h || 0) * 36e5;
  if (!(T > 0)) return null;
  let stand = null;
  for (const sp of row.spills || []) for (const rel of plumeReleases(sp, gen)) {
    if (t <= rel.a) continue;
    const w = plumeWater(rel, row.travel_h, t);
    if (w && w.past) return 'at';
    if (w) stand = 'coming';
    else if (Number.isFinite(rel.b) && t - Math.min(rel.b, t) - T <= recentH * 36e5 && stand === null) stand = 'passed';
  }
  return stand;
}
const plumeFade = (ageH, t90) => 0.45 + 0.55 * Math.pow(10, -Math.max(ageH, 0) / (t90 || 72));

// One line for the slider's time: how many spills' water stands where, said as an estimate. Never "clean":
// with nothing drawn it says what was and was not reported.
function plumeSaid(rows, gen, t, gaps, recentH = 48) {
  const n = { coming: 0, at: 0, passed: 0 };
  for (const r of rows) { const s = plumeStand(r, gen, t, recentH); if (s) n[s]++; }
  const when = `${plumeTime(t)} (${plumeFromUpdate(t, gen)})`, sp = k => (n[k] === 1 ? 'one overflow' : `${n[k]} overflows`);
  const parts = [];
  if (n.at) parts.push(`water from ${sp('at')} is modelled to be reaching the spot`);
  if (n.coming) parts.push(`water from ${sp('coming')} is modelled to be on its way down the river`);
  if (n.passed) parts.push(`water from ${sp('passed')} is modelled to have passed the spot in the last ${recentH} hours`);
  const gap = gaps ? ` ${gaps} overflow${gaps === 1 ? '' : 's'} upstream had no current reading, so a spill there would not show.` : '';
  if (!parts.length) return `${when}: no reported spill's water is modelled to be on these rivers. That is what the feeds reported, not a measurement of the water.${gap}`;
  const s = parts.join('; ');
  return `${when}: ${s[0].toUpperCase()}${s.slice(1)}. Model estimate.${gap}`;
}

// One overflow's spills in words, the reported times and then the modelled arrival, each a sentence. Times carry
// the date: a spill a week old has the same weekday as today.
function plumeRowSaid(row) {
  const name = plumeEsc(plumeName(row)), co = plumeEsc(plumeCompany(row.company)), at = ms => plumeTime(ms, true);
  const where = `${Number(row.km).toFixed(1)}&nbsp;km upstream`;
  const spills = (row.spills || []).map(sp => {
    const a = plumeMs(sp.start), b = plumeMs(sp.end);
    let s = sp.running ? `Spilling from ${at(a)}, still at the last poll before the update`
      : sp.end_known ? `Spilled ${at(a)} to ${at(b)}` : `Spilled from ${at(a)}; the feed did not report when it stopped`;
    const arr = sp.arrival;
    if (row.lake_route || !arr) s += '; its water crosses a lake, so its arrival is not drawn';
    else if (Number.isFinite(plumeMs(arr.from))) s += `; modelled to reach the spot from ${at(plumeMs(arr.from))}${Number.isFinite(plumeMs(arr.to)) ? ` to ${at(plumeMs(arr.to))}` : ''}`;
    return `${s}.`;
  });
  const state = row.state && row.state !== 'live' ? ` Now: ${PLUME_STATE[row.state] || 'no current reading'}.` : '';
  const more = row.earlier_spills ? ` ${row.earlier_spills} earlier spill${row.earlier_spills === 1 ? '' : 's'} not listed.` : '';
  return `<li><b>${name}</b>, ${co}, ${where}${row.travel_h ? `, about ${Math.round(row.travel_h)}&nbsp;h away by the model` : ''}. ${spills.join(' ')}${state}${more}</li>`;
}

// What the map cannot show, in words: overflows with no reading, routes not drawn, spills left out.
function plumeGapsSaid(replay, doc) {
  const q = replay.quiet || {}, n = k => (q[k] || {}).n || 0, out = [];
  const dark = ['stale', 'offline', 'no_feed'].reduce((m, k) => m + n(k), 0);
  if (dark) out.push(`${dark} counted overflow${dark === 1 ? ' has' : 's have'} no current reading or no live feed (grey rings): whether ${dark === 1 ? 'it was' : 'they were'} spilling is not known.`);
  if (n('no_history') || n('late_history')) out.push(`${n('no_history') + n('late_history')} counted overflow${n('no_history') + n('late_history') === 1 ? ' has' : 's have'} no poll history for all of these hours, so earlier spills there are not known.`);
  if (replay.history && replay.history.unavailable) out.push('This update had no poll history, so only spills still reported at the update are known.');
  if (replay.more_with_events) out.push(`${replay.more_with_events} more overflow${replay.more_with_events === 1 ? '' : 's'} with reported spills or gaps, of smaller model weight here, ${replay.more_with_events === 1 ? 'is' : 'are'} not drawn.`);
  if (doc.unrouted) out.push(`${doc.unrouted} route${doc.unrouted === 1 ? '' : 's'} down to the spot could not be drawn.`);
  const lake = (replay.overflows || []).filter(r => r.lake_route).length;
  if (lake) out.push(`${lake} overflow${lake === 1 ? "'s" : "s'"} water crosses a lake on the way, where the model's travel time is too coarse to draw.`);
  return out.join(' ');
}

// The slider's ends and step count: 48 hours either side of the update, on whole quarter hours of the clock.
function plumeRange(gen) {
  const step = PLUME_STEP_H * 36e5, min = Math.floor((gen - PLUME_BACK_H * 36e5) / step) * step, max = Math.ceil((gen + PLUME_AHEAD_H * 36e5) / step) * step;
  return { min, max, step, steps: Math.round((max - min) / step) };
}
const plumeIcon = () => (typeof ICON === 'object' && ICON.map ? ICON.map : '');
// The tile: official notice first, then the slider, the map, its key and the words. The map is drawn by plumeBind.
function plumeTile(d, doc, replay, gen, t) {
  const rows = replay.overflows || [];
  const brief = typeof eaTodayBrief === 'function' ? eaTodayBrief(d) : '';
  const official = brief ? `<p class="pl-official"><b>Official: ${plumeEsc(brief)}.</b> ${typeof eaTodayFirst === 'function' ? eaTodayFirst(d) : 'Read the official notice first'}; this map is SwimSignal's model estimate only.</p>` : '';
  const v = doc.river_velocity_ms ? ` at the model's ${doc.river_velocity_ms}&nbsp;m/s` : '';
  const { min, max, step, steps } = plumeRange(gen), pos = Math.round((Math.min(Math.max(t, min), max) - min) / step);
  const listed = rows.filter(r => (r.spills || []).length);
  return `<section class="tile pl" id="spill-map" aria-labelledby="pl-h"><h2 class="t-lab" id="pl-h">${plumeIcon()}<span>Where spill water may be</span></h2>`
    + official
    + `<p class="t-say">${PLUME_ESTIMATE} Each reported spill's water moves down its river at the forecast's travel time${v}, and fades as its bacteria die off (90% in ${doc.t90_hours || 72}&nbsp;h). Spills that start after the update are not drawn.</p>`
    + `<div class="pl-ctl"><button type="button" class="btn pl-play" aria-pressed="false">Play</button>`
    + `<label class="pl-range"><span class="pl-when" aria-hidden="true"></span><input type="range" min="0" max="${steps}" step="1" value="${pos}" aria-label="Time, from 48 hours before the update to 48 hours after"></label></div>`
    + `<div class="pl-map" role="img" aria-label="Map of the rivers upstream of the spot, with where water from reported spills may be at the chosen time. The words under the map say the same."></div>`
    + `<p class="pl-said" aria-live="polite"></p>`
    + `<p class="t-key pl-key"><span><i class="pl-sw"></i>water from a reported spill (model estimate)</span><span><i class="pl-sw pl-sw-unsure"></i>not confirmed by the feed</span>`
    + `<span><i class="pl-dot pl-dot-spill"></i>overflow that spilled</span><span><i class="pl-dot pl-dot-gap"></i>no current reading</span><span><i class="pl-dot pl-dot-spot"></i>the spot</span></p>`
    + (listed.length ? `<details class="pl-more"><summary>Spills reported upstream in the last 48 hours (${listed.length})</summary><ul class="pl-list">${listed.map(r => plumeRowSaid(r)).join('')}</ul></details>` : '')
    + `<p class="t-say pl-gaps">${plumeGapsSaid(replay, doc) || 'Every counted overflow upstream had a current reading at the update.'} Spill status as of the update at ${plumeTime(gen, true)}.</p>`
    + '</section>';
}

// Draw the map into a tile from plumeTile and wire the slider and play. `L` is Leaflet, already on the page.
function plumeBind(host, d, doc, replay, trace, gen, start) {
  const el = host.querySelector('.pl-map'), range = host.querySelector('input[type=range]'), play = host.querySelector('.pl-play');
  const said = host.querySelector('.pl-said'), when = host.querySelector('.pl-when');
  if (!el || typeof L !== 'object') return null;
  const touch = matchMedia('(pointer: coarse)').matches, still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const map = L.map(el, { dragging: !touch, scrollWheelZoom: false, zoomAnimation: !still, fadeAnimation: !still, markerZoomAnimation: !still, attributionControl: true });
  map.attributionControl.setPrefix(false);
  (typeof tiles === 'function' ? tiles() : L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' })).addTo(map);
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const brick = css('--veryhigh') || '#a32d2d', grey = css('--unknown') || '#98a2aa', teal = css('--brand') || '#0f5a61', river = css('--muted') || '#5a6166';
  const bounds = L.latLngBounds([doc.pin]);
  for (const s of (trace && trace.lines) || []) { const p = plumeDecode(s); L.polyline(p, { color: river, weight: 1.5, opacity: 0.45, interactive: false }).addTo(map); p.forEach(x => bounds.extend(x)); }
  const rows = (replay.overflows || []).map(r => { const o = (doc.overflows || []).find(x => x.site_id === r.site_id) || {};
    const pts = o.path ? plumeDecode(o.path) : null; return { ...r, at: o.at, pts, cum: pts ? plumeMeasure(pts) : null }; });
  const gaps = doc.gaps || [];
  for (const g of gaps) L.circleMarker(g.at, { radius: 5, color: grey, weight: 2, fill: false, dashArray: '2 2' })
    .bindTooltip(`${plumeEsc(g.site_id)}: ${PLUME_STATE[g.state] || 'no current reading'}`).addTo(map);
  for (const r of rows) {
    if (!r.at) continue;
    bounds.extend(r.at);
    const dark = r.state && r.state !== 'live';
    L.circleMarker(r.at, { radius: 6, color: dark ? grey : '#fff', weight: 2, fillColor: brick, fillOpacity: 1, ...(dark ? { dashArray: '2 2' } : {}) })
      .bindTooltip(`${plumeEsc(plumeName(r))}${dark ? `: now ${PLUME_STATE[r.state] || 'no current reading'}` : ''}`).addTo(map);
  }
  L.circleMarker(doc.pin, { radius: 8, color: teal, weight: 3, fill: true, fillColor: '#fff', fillOpacity: 1 }).bindTooltip('The spot').addTo(map);
  map.fitBounds(bounds.pad(0.08), { animate: false, maxZoom: 13 });
  const water = L.layerGroup().addTo(map), gapN = ['stale', 'offline', 'no_feed'].reduce((m, k) => m + ((replay.quiet || {})[k] || {}).n || 0, 0)
    + rows.filter(r => r.state && r.state !== 'live').length;
  const { min, step } = plumeRange(gen), t90 = doc.t90_hours || 72, recent = doc.recent_spill_hours || 48;
  const draw = (t, speak) => {
    water.clearLayers();
    for (const r of rows) {
      if (!r.pts || !(r.travel_h > 0)) continue;
      for (const sp of r.spills || []) for (const rel of plumeReleases(sp, gen)) {
        const w = plumeWater(rel, r.travel_h, t);
        if (!w || w.f1 <= w.f0) continue;
        for (let k = 0; k < PLUME_PIECES; k++) {   // tail to head: the newest water at f0, the oldest at f1
          const f0 = w.f0 + (w.f1 - w.f0) * k / PLUME_PIECES, f1 = w.f0 + (w.f1 - w.f0) * (k + 1) / PLUME_PIECES;
          const age = w.ageTail + (w.ageHead - w.ageTail) * (k + 0.5) / PLUME_PIECES;
          const line = plumeSlice(r.pts, r.cum, f0, f1);
          if (line.length > 1) L.polyline(line, { color: brick, weight: 6, opacity: plumeFade(age, t90), lineCap: 'butt', interactive: false,
            ...(w.sure ? {} : { dashArray: '6 5' }) }).addTo(water);
        }
      }
    }
    when.textContent = `${plumeTime(t, true)}, ${plumeFromUpdate(t, gen)}`;
    range.setAttribute('aria-valuetext', `${plumeTime(t, true)}, ${plumeFromUpdate(t, gen)}`);
    const s = plumeSaid(rows, gen, t, gapN, recent);
    if (speak !== false && said.textContent !== s) said.textContent = s;
  };
  const at = () => min + Number(range.value) * step;
  range.addEventListener('input', () => draw(at()));
  let raf = 0, last = 0;
  const stop = () => { cancelAnimationFrame(raf); raf = 0; play.textContent = 'Play'; play.setAttribute('aria-pressed', 'false'); draw(at()); };
  const tick = ts => {
    if (!host.isConnected) return stop();
    const dv = last ? (ts - last) / 1000 * PLUME_PLAY_H / PLUME_STEP_H : 0; last = ts;
    const v = Math.min(Number(range.max), Number(range.value) + dv);
    range.value = String(v); draw(min + v * step, false);
    if (v >= Number(range.max)) return stop();
    raf = requestAnimationFrame(tick);
  };
  if (still) play.hidden = true;   // reduced motion: the slider alone, moved by the reader
  play.addEventListener('click', () => {
    if (raf) return stop();
    if (Number(range.value) >= Number(range.max)) range.value = '0';
    play.textContent = 'Pause'; play.setAttribute('aria-pressed', 'true'); last = 0; raf = requestAnimationFrame(tick);
  });
  draw(start != null ? start : at());
  return map;
}

const PLUME_CSS = `
.pl-official { margin:10px 0 0; font-size:var(--fs-note); line-height:1.4; }
.pl-ctl { display:flex; align-items:center; gap:10px; margin:12px 0 8px; }
.pl-play { flex:none; min-width:76px; }
.pl-range { flex:1; display:flex; flex-direction:column; gap:2px; min-width:0; }
.pl-when { font-size:var(--fs-meta); color:var(--ink); font-variant-numeric:tabular-nums; }
.pl-range input { width:100%; min-height:32px; margin:0; accent-color:var(--brand); }
.pl-map { height:300px; border-radius:var(--radius); overflow:hidden; background:var(--bg); }
@media (min-width: 801px) { .pl-map { height:400px; } }
.pl-said { margin:10px 0 0; font-size:var(--fs-note); line-height:1.4; }
.pl-key { display:flex; flex-wrap:wrap; align-items:center; gap:4px 14px; }
.pl-key > span { white-space:nowrap; display:inline-flex; align-items:center; gap:6px; }
.pl-sw { display:inline-block; width:22px; height:0; border-top:5px solid var(--veryhigh); }
.pl-sw-unsure { border-top-style:dashed; width:26px; }
.pl-dot { display:inline-block; flex:none; width:10px; height:10px; border-radius:50%; vertical-align:middle; box-sizing:border-box; }
.pl-dot-spill { background:var(--veryhigh); }
.pl-dot-gap { border:2px dashed var(--unknown); }
.pl-dot-spot { border:3px solid var(--brand); background:var(--card); width:14px; height:14px; }
.pl-more { margin:10px 0 0; font-size:var(--fs-note); }
.pl-more summary { cursor:pointer; min-height:44px; display:flex; align-items:center; font-weight:600; }
.pl-list { margin:0; padding-left:18px; line-height:1.4; }
.pl-list li + li { margin-top:6px; }
`;
function plumeStyle(doc) {
  if (!doc || doc.getElementById('pl-style')) return;
  const s = doc.createElement('style');
  s.id = 'pl-style';
  s.textContent = PLUME_CSS;
  doc.head.appendChild(s);
}

if (typeof module === 'object' && module.exports) {
  module.exports = { plumeRange, plumeTime, plumeFromUpdate, plumeDecode, plumeMeasure, plumeSlice, plumeReleases, plumeWater, plumeStand, plumeFade,
    plumeSaid, plumeRowSaid, plumeGapsSaid, plumeTile, plumeBind, plumeStyle, PLUME_CSS, PLUME_ESTIMATE, PLUME_BACK_H, PLUME_AHEAD_H, PLUME_STEP_H };
}
