// SwimSignal, the redesign preview: the maps. Two of them: every place on the day shown (the Map view), and one
// place with the water that reaches it and the monitored overflows on that water (a place's Upstream section).
// The map library is the live site's copy of Leaflet 1.9.4 (vendor/leaflet/, with its licence) and is asked for
// only when a map is first opened. The tiles are the live map's: the build writes their address, credit and colour
// filter to preview/map.json (build_site.write_preview), so the two maps look the same. window.PVMap.
(function () {
'use strict';
const LIB = { css: ['vendor/leaflet/leaflet.css', 'sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY='], js: ['vendor/leaflet/leaflet.js', 'sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo='] };
const OSM = { url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', credit: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>', filter: '' };
// The level colours and the rings, as the live map has them (index.html, colour, PAPER, RING, ADVICE_RING).
const FILL = { 'lv-low': '#3b7d4f', 'lv-moderate': '#b7791f', 'lv-high': '#c2552a', 'lv-veryhigh': '#a32d2d', 'lv-clear': '#4aa39a', 'lv-none': '#98a2aa' };
const PAPER = '#f6f4ee', RING = '#0f5a61', ADVICE = '#e5a53a', QUIET = '#5b6470', NONE = '#7b848c', SPILL = '#a32d2d';
const TOUCH = matchMedia('(pointer: coarse)').matches, still = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
let ready = null, CONF = OSM, tint = null;

// The tiles' colours, worked out once per colour from the build's filter and drawn into a canvas as each tile
// loads (the live map's way: as a CSS filter, iOS Safari recomputed it on every frame of a pan).
function tinter(svg) {
  let f = null;
  try { f = new DOMParser().parseFromString(`<svg xmlns="http://www.w3.org/2000/svg">${svg}</svg>`, 'image/svg+xml').querySelector('filter'); } catch (e) { f = null; }
  if (!f) return null;
  const steps = [...f.children].map(e => ({ tag: e.tagName.replace(/^.*:/, ''), result: e.getAttribute('result'), in1: e.getAttribute('in'), in2: e.getAttribute('in2'), op: e.getAttribute('operator'),
    k: ['k1', 'k2', 'k3', 'k4'].map(a => +(e.getAttribute(a) || 0)), m: (e.getAttribute('values') || '').trim().split(/[\s,]+/).map(Number), nodes: [...e.children].map(n => n.getAttribute('in')) }));
  const cl = x => x < 0 ? 0 : x > 1 ? 1 : x, cache = new Map();
  return (r, g, b) => {
    const key = (r << 16) | (g << 8) | b, hit = cache.get(key); if (hit) return hit;
    const src = [r / 255, g / 255, b / 255, 1], got = { SourceGraphic: src }; let last = src;
    const take = n => (n && got[n]) || (n ? src : last);
    for (const st of steps) { let o;
      if (st.tag === 'feColorMatrix') { const i = take(st.in1), a = i[3], u = a ? [i[0] / a, i[1] / a, i[2] / a, a] : [0, 0, 0, 0], m = st.m;
        const row = j => cl(m[j] * u[0] + m[j + 1] * u[1] + m[j + 2] * u[2] + m[j + 3] * u[3] + m[j + 4]), oa = row(15); o = [row(0) * oa, row(5) * oa, row(10) * oa, oa]; }
      else if (st.tag === 'feComposite') { const i1 = take(st.in1), i2 = take(st.in2);
        if (st.op === 'in') o = i1.map(c => c * i2[3]);
        else { const [k1, k2, k3, k4] = st.k; o = i1.map((c, j) => cl(k1 * c * i2[j] + k2 * c + k3 * i2[j] + k4)); o = o.map((c, j) => j < 3 ? Math.min(c, o[3]) : c); } }
      else if (st.tag === 'feMerge') { o = [0, 0, 0, 0]; for (const n of st.nodes) { const i = take(n); o = o.map((c, j) => i[j] + c * (1 - i[3])); } }
      else continue;
      last = o; if (st.result) got[st.result] = o; }
    const a = last[3] || 1, out = [0, 1, 2].map(j => Math.round(cl(last[j] / a) * 255));
    cache.set(key, out); return out;
  };
}
function load() {
  if (ready) return ready;
  ready = new Promise((resolve, reject) => {
    const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = LIB.css[0]; css.integrity = LIB.css[1]; document.head.appendChild(css);
    if (window.L) { resolve(); return; }
    const js = document.createElement('script'); js.src = LIB.js[0]; js.integrity = LIB.js[1]; js.onload = resolve; js.onerror = () => reject(new Error('the map could not be read'));
    document.head.appendChild(js);
  }).then(() => fetch('preview/map.json').then(r => r.ok ? r.json() : null).catch(() => null)).then(c => {
    if (c && /^https:\/\/[^\s"'<>]+$/.test(c.url || '') && typeof c.credit === 'string') CONF = { url: c.url, credit: c.credit, filter: typeof c.filter === 'string' ? c.filter : '' };
    tint = CONF.filter ? tinter(CONF.filter) : null;
  });
  ready.catch(() => { ready = null; });
  return ready;
}
function tiles() {
  const opts = { maxZoom: 19, attribution: CONF.credit };
  if (!tint) return L.tileLayer(CONF.url, opts);
  const Tinted = L.TileLayer.extend({ createTile(coords, done) {
    const c = document.createElement('canvas'), img = new Image(); img.crossOrigin = 'anonymous';
    img.onload = () => { c.width = img.naturalWidth; c.height = img.naturalHeight;
      const g = c.getContext('2d', { willReadFrequently: true }); g.drawImage(img, 0, 0);
      try { const d = g.getImageData(0, 0, c.width, c.height), px = d.data;
        for (let i = 0; i < px.length; i += 4) { if (px[i + 3] !== 255) continue; const o = tint(px[i], px[i + 1], px[i + 2]); px[i] = o[0]; px[i + 1] = o[1]; px[i + 2] = o[2]; }
        g.putImageData(d, 0, 0); } catch (e) { /* a provider without CORS: its own colours */ }
      done(null, c); };
    img.onerror = e => done(e, c); img.src = this.getTileUrl(coords); return c; } });
  return new Tinted(CONF.url, opts);
}
// A map in an element of its own, which is moved into each new drawing of the page: the page is drawn again on
// every change, and a map made again each time would lose its place and its tiles.
function make(label, drag) {
  const el = document.createElement('div'); el.className = 'pv-map'; el.setAttribute('role', 'application'); el.setAttribute('aria-label', label);
  const map = L.map(el, { zoomControl: true, dragging: drag, zoomAnimation: !still(), fadeAnimation: !still(), markerZoomAnimation: !still(), inertia: !still() }).setView([53.6, -2.0], 6);
  map.attributionControl.setPrefix(false); tiles().addTo(map);
  if (!drag) { const hint = document.createElement('div'); let t = null; hint.className = 'pv-map-hint'; hint.setAttribute('aria-hidden', 'true'); hint.textContent = 'Use two fingers to move the map';
    el.appendChild(hint);
    el.addEventListener('touchmove', e => { if (e.touches.length !== 1) { hint.classList.remove('show'); return; } hint.classList.add('show'); clearTimeout(t); t = setTimeout(() => hint.classList.remove('show'), 1400); }, { passive: true }); }
  return { el, map, layer: L.layerGroup().addTo(map) };
}
const move = () => still() ? { animate: false } : {};
const tip = text => { const s = document.createElement('span'); s.textContent = text; return s; };
const seat = (m, slot) => { if (m.el.parentElement !== slot) slot.appendChild(m.el); m.map.invalidateSize(); };

// ------------------------------------------------------------------------------------------------ every place
let HOME = null;
// points: model.js mapPoints. picked: the place whose card is open. onPick(id or null). here: { lat, lon } or null.
// onWater(lat, lon, zoom): a tap that is on no listed place, which the page reads as a river or lake to forecast.
async function home(slot, points, picked, onPick, here, onWater) {
  await load(); if (!slot.isConnected) return;
  if (!HOME) { HOME = make('Map of every listed place. The same places are in the list.', true); HOME.fitted = false;
    // A tap picks the nearest place within a finger's width, so a 16 px dot is not a 16 px target.
    HOME.map.on('click', e => { const at = HOME.map.latLngToContainerPoint(e.latlng); let best = null, d = 26;
      for (const p of HOME.points) { const q = HOME.map.latLngToContainerPoint([p.lat, p.lon]), r = Math.hypot(q.x - at.x, q.y - at.y); if (r < d) { d = r; best = p; } }
      if (best || !HOME.onWater) HOME.onPick(best ? best.id : null); else HOME.onWater(e.latlng.lat, e.latlng.lng, HOME.map.getZoom()); }); }
  HOME.points = points; HOME.onPick = onPick; HOME.onWater = onWater || null; seat(HOME, slot);
  HOME.layer.clearLayers();
  const draw = (p, on) => L.circleMarker([p.lat, p.lon], { radius: on ? 11 : 8, color: on ? RING : p.advised ? ADVICE : PAPER, weight: on || p.advised ? 3 : 2, fillColor: FILL[p.cls] || FILL['lv-none'], fillOpacity: 1 })
    .bindTooltip(tip(`${p.name}: ${p.words}`), { direction: 'top', offset: [0, -8] }).addTo(HOME.layer);
  for (const p of points) if (p.id !== picked) draw(p, false);
  const sel = points.find(p => p.id === picked); if (sel) draw(sel, true);
  if (here) L.circleMarker([here.lat, here.lon], { radius: 6, color: '#fff', weight: 2, fillColor: '#1b2328', fillOpacity: 1, interactive: false }).bindTooltip('Where you are').addTo(HOME.layer);
  if (!HOME.fitted && points.length) { HOME.fitted = true; HOME.map.fitBounds(L.latLngBounds(points.map(p => [p.lat, p.lon])), { padding: [18, 18], animate: false }); }
}
const homeTo = (at, zoom = 10) => { if (HOME) HOME.map.setView([at.lat, at.lon], zoom, move()); };

// ------------------------------------------------------------------------------------------------ one place
let PLACE = null;
// s: the place { id, name, lat, lon, cls, advised }. points: model.js overflowPoints. lines: the traced water, or null.
async function place(slot, s, points, lines) {
  await load(); if (!slot.isConnected) return;
  if (!PLACE) { PLACE = make('Map of the water upstream of this place and its monitored overflows. The same overflows are listed under As a line.', !TOUCH);
    PLACE.map.createPane('trace').style.zIndex = 350; }
  seat(PLACE, slot); PLACE.layer.clearLayers();
  if (lines && lines.length) L.polyline(lines, { pane: 'trace', color: RING, weight: 2.5, opacity: .6, interactive: false }).addTo(PLACE.layer);
  const mark = p => p.mark === 'spilling' ? { radius: 8, color: PAPER, weight: 2, fillColor: SPILL, fillOpacity: 1 }
    : p.mark === 'quiet' ? { radius: 6, color: QUIET, weight: 2, fillColor: '#fff', fillOpacity: 1 } : { radius: 6, color: NONE, weight: 2, dashArray: '3 3', fillColor: PAPER, fillOpacity: 1 };
  // Spilling ones last, so they sit on top of the rest.
  for (const p of [...points].sort((a, b) => (a.mark === 'spilling') - (b.mark === 'spilling'))) { const box = document.createElement('div');
    const b = document.createElement('b'); b.textContent = p.name; const t = document.createElement('span'); t.textContent = p.said; const c = document.createElement('span'); c.textContent = p.company;
    box.className = 'pv-pop'; box.append(b, t, c);
    L.circleMarker([p.lat, p.lon], mark(p)).bindPopup(box).addTo(PLACE.layer); }
  L.circleMarker([s.lat, s.lon], { radius: 15, color: RING, weight: 3, fill: false, interactive: false }).addTo(PLACE.layer);
  L.circleMarker([s.lat, s.lon], { radius: 9, color: s.advised ? ADVICE : PAPER, weight: s.advised ? 3.5 : 2, fillColor: FILL[s.cls] || FILL['lv-none'], fillOpacity: 1, interactive: false }).addTo(PLACE.layer);
  const key = `${s.id}|${points.length}|${lines ? lines.length : 0}`;
  if (PLACE.key !== key) { PLACE.key = key;
    const b = L.latLngBounds([[s.lat, s.lon], ...points.map(p => [p.lat, p.lon])]);
    if (points.length) PLACE.map.fitBounds(b, { padding: [28, 28], maxZoom: 14, animate: false }); else PLACE.map.setView([s.lat, s.lon], 12, { animate: false }); }
}
window.PVMap = { home, homeTo, place, load };
})();
