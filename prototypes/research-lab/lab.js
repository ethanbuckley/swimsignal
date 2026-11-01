// Shared by the Research Lab exhibits: the drawn map of Great Britain and the dot-and-interval chart.
// Plain script; its one global is LAB. Each exhibit loads it before its own script.

const LAB = (() => {
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

  // ---------------------------------------------------------------- chart width: the note column, 280 to 520 px
  function noteW() { const n = document.querySelector('.fnote'); return Math.max(280, Math.min(520, Math.round(n ? n.clientWidth : 520))); }

  // ---------------------------------------------------------------- dot-and-interval rows
  // items: [{label, v, ci?: [lo, hi], c?: colour, strong?: bool}]; opts: {max, min = 0, fmt, ref: {v, label}}.
  // A faint track from min to max, a dot at the value, whiskers for an interval, the value written beside it.
  function dots(items, opts = {}) {
    const W = noteW(), narrow = W < 440, row = narrow ? 40 : 30, top = 6, H = items.length * row + top + (opts.ref ? 16 : 4);
    const pl = narrow ? 0 : 176, pr = 64, min = opts.min ?? 0, max = opts.max ?? 1, fmt = opts.fmt || (v => String(v));
    const x = v => pl + (Math.max(min, Math.min(max, v)) - min) / (max - min) * (W - pl - pr);
    let g = '';
    items.forEach((it, i) => {
      const y0 = top + i * row + (narrow ? 16 : 0), cy = y0 + 9, col = it.c || 'var(--rule)';
      g += `<text x="0" y="${narrow ? y0 - 3 : cy + 4}" style="${it.strong ? 'fill:var(--ink);font-weight:600' : ''}">${esc(it.label)}</text>`;
      g += `<line x1="${x(min)}" x2="${x(max)}" y1="${cy}" y2="${cy}" stroke="var(--hair)"/>`;
      if (it.ci) g += `<line x1="${x(it.ci[0])}" x2="${x(it.ci[1])}" y1="${cy}" y2="${cy}" stroke="${col}" stroke-width="2.5" stroke-linecap="round" opacity=".55"/>`;
      g += `<circle cx="${x(it.v)}" cy="${cy}" r="${it.strong ? 6 : 5}" fill="${col}" stroke="var(--paper)" stroke-width="1.5"/>`;
      g += `<text x="${x(Math.max(it.v, it.ci ? it.ci[1] : it.v)) + 10}" y="${cy + 4}" style="fill:var(--ink);font-family:var(--font-mono);font-size:11px">${fmt(it.v)}</text>`;
    });
    if (opts.ref) g += `<line x1="${x(opts.ref.v)}" x2="${x(opts.ref.v)}" y1="2" y2="${H - 14}" stroke="var(--pick)" stroke-dasharray="3 3"/><text x="${x(opts.ref.v)}" y="${H - 2}" text-anchor="middle" style="fill:var(--pick)">${esc(opts.ref.label)}</text>`;
    return `<svg viewBox="0 0 ${W} ${H}" style="max-width:${W}px">${g}</svg>`;
  }

  // ---------------------------------------------------------------- the drawn map
  // England's and its neighbours' outlines from assets/britain.json (ONS, OGL), an equirectangular projection scaled
  // at 53.5°N, a one-degree graticule and a 50 km bar. points: [{id, lat, lon, kind: 'pilot'|'hist'|'small', name}].
  let OUTLINE = null;
  const BOX = { w: -6.4, e: 2.0, s: 49.85, n: 55.95 }, K = Math.cos(53.5 * Math.PI / 180);
  async function loadOutline(base) {
    if (!OUTLINE) OUTLINE = await fetch(base + 'assets/britain.json').then(r => r.json());
    return OUTLINE;
  }
  // box: {w, e, s, n} to zoom (default England and Wales); maxH caps the height, widening the box to keep the scale true.
  function project(W, box = BOX, maxH = Infinity) {
    let b = { ...box };
    const k = Math.cos((b.s + b.n) / 2 * Math.PI / 180);
    let sx = W / ((b.e - b.w) * k), H = Math.round((b.n - b.s) * sx);
    if (H > maxH) {   // too tall: keep the height, widen west and east
      sx = maxH / (b.n - b.s); H = maxH;
      const half = W / sx / k / 2, mid = (b.w + b.e) / 2;
      b = { ...b, w: mid - half, e: mid + half };
    }
    return { H, b, k, x: lon => (lon - b.w) * k * sx, y: lat => (b.n - lat) * sx, sx };
  }
  const STEPS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1];
  const KMS = [0.5, 1, 2, 5, 10, 20, 50, 100];
  function ringPath(ring, p) {
    let d = '', last = '';
    for (const [lon, lat] of ring) {
      const pt = `${p.x(lon).toFixed(1)},${p.y(lat).toFixed(1)}`;
      if (pt !== last) { d += (d ? 'L' : 'M') + pt; last = pt; }
    }
    return d + 'Z';
  }
  function drawMap(el, points, opts = {}) {
    const W = Math.max(260, Math.round(el.clientWidth || 400)), p = project(W, opts.box || BOX, opts.maxH), H = p.H, b = p.b;
    const step = STEPS.find(v => (b.n - b.s) / v <= 7) || 1, dp = step < 0.1 ? 2 : step < 1 ? 1 : 0;
    const from = v => Math.ceil(v / step - 1e-9) * step;
    let g = `<rect width="${W}" height="${H}" fill="var(--sea)"/>`;
    for (let lon = from(b.w); lon <= b.e; lon += step) g += `<line x1="${p.x(lon)}" x2="${p.x(lon)}" y1="0" y2="${H}" class="grat"/>`;
    for (let lat = from(b.s); lat <= b.n; lat += step) g += `<line x1="0" x2="${W}" y1="${p.y(lat)}" y2="${p.y(lat)}" class="grat"/>`;
    for (const [name, rings] of Object.entries(OUTLINE.countries)) {
      g += `<path d="${rings.map(r => ringPath(r, p)).join('')}" class="land ${name === 'England' ? 'eng' : 'other'}"/>`;
    }
    // lines on the land: [{coords: [[lon, lat], ...], cls}]
    for (const ln of opts.lines || []) g += `<path d="${ringPath(ln.coords, p).slice(0, -1)}" class="ln ${ln.cls || ''}"${ln.id ? ` data-line="${ln.id}"` : ''}/>`;
    for (let lat = from(b.s); lat <= b.n; lat += step) g += `<text x="4" y="${p.y(lat) - 3}" class="gl">${lat.toFixed(dp)}°N</text>`;
    let lonN = 0;
    for (let lon = from(b.w); lon <= b.e; lon += step) if (lonN++ % 2 === 0) g += `<text x="${p.x(lon) + 3}" y="${H - 5}" class="gl">${Math.abs(lon).toFixed(dp)}°${lon < 0 ? 'W' : 'E'}</text>`;
    const km = KMS.find(v => v / 111.32 * p.sx >= W * 0.12) || 100, kmPx = km / 111.32 * p.sx;
    g += `<g transform="translate(${W - kmPx - 14},${H - 26})"><line x1="0" x2="${kmPx}" y1="0" y2="0" stroke="var(--ink)" stroke-width="1.5"/><line x1="0" x2="0" y1="-4" y2="4" stroke="var(--ink)"/><line x1="${kmPx}" x2="${kmPx}" y1="-4" y2="4" stroke="var(--ink)"/><text x="${kmPx / 2}" y="-7" text-anchor="middle" class="gl">${km} km</text></g>`;
    g += `<g transform="translate(${W - 22},18)"><path d="M0 -10 L5 4 L0 1 L-5 4 Z" fill="var(--ink)"/><text y="16" text-anchor="middle" class="gl">N</text></g>`;
    const order = [...points].sort((a, b) => (a.id === opts.selected) - (b.id === opts.selected) || (a.kind === 'pilot') - (b.kind === 'pilot'));
    for (const pt of order) {
      const cx = p.x(pt.lon), cy = p.y(pt.lat), on = pt.id === opts.selected;
      const mark = pt.mark ? pt.mark : pt.kind === 'pilot' ? `<circle r="5" class="pt-pilot"/>` : pt.kind === 'small' ? `<circle r="3.5" class="pt-small"/>` : `<circle r="3.5" class="pt-hist"/>`;
      g += `<g class="pt${on ? ' on' : ''}" transform="translate(${cx.toFixed(1)},${cy.toFixed(1)})" data-id="${pt.id}" tabindex="0" role="button" aria-label="${esc(pt.name)}"><title>${esc(pt.name)}</title>${on ? '<circle r="10" class="pt-ring"/>' : ''}${mark}<circle r="11" fill="transparent"/></g>`;
    }
    const sel = points.find(pt => pt.id === opts.selected);
    if (sel) {
      // beside the mark where it fits (about 7 px a character), else centred below it, kept inside the map
      const cx = p.x(sel.lon), cy = p.y(sel.lat), text = opts.label || sel.name, tw = text.length * 7;
      let x, y = cy + 4, anchor;
      if (cx + 16 + tw <= W - 4) { x = cx + 16; anchor = 'start'; }
      else if (cx - 16 - tw >= 4) { x = cx - 16; anchor = 'end'; }
      else { x = Math.min(W - 4 - tw / 2, Math.max(4 + tw / 2, cx)); y = cy + (cy > H - 40 ? -16 : 24); anchor = 'middle'; }
      g += `<text x="${x}" y="${y}" text-anchor="${anchor}" class="pt-label">${esc(text)}</text>`;
    }
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="group" aria-label="${esc(opts.aria || 'Map of the sites')}">${g}</svg>`;
    el.querySelectorAll('.pt').forEach(n => {
      n.onclick = () => opts.onPick && opts.onPick(n.dataset.id);
      if (opts.onHover) { n.onmouseenter = () => opts.onHover(n.dataset.id); n.onmouseleave = () => opts.onHover(null); }
      n.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); opts.onPick && opts.onPick(n.dataset.id); } };
    });
  }

  // ---------------------------------------------------------------- "Data as of"
  // The element with data-asof names the parts this page draws on; refresh.json (build_site.write_lab_refresh) says
  // when each was made and how it is refreshed. Only a site build writes that file: run from the repository there is
  // none, and the line stays empty. A part older than its refresh should leave it is named, not hidden.
  async function asOf() {
    const el = document.querySelector('[data-asof]');
    if (!el) return;
    let doc;
    try { const r = await fetch((el.dataset.base || '') + 'refresh.json'); if (!r.ok) return; doc = await r.json(); } catch { return; }
    const day = d => new Date(d.slice(0, 10) + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
    const items = el.dataset.asof.split(',').map(k => doc.parts[k]).filter(Boolean);
    if (!items.length) return;
    const age = p => (Date.now() - Date.parse(p.as_of.slice(0, 10) + 'T00:00:00Z')) / 864e5;
    const old = items.filter(p => p.stale_days && age(p) > p.stale_days);
    el.innerHTML = '<b>Data as of.</b> ' + items.map(p => `${esc(p.label)}: ${day(p.as_of)}${p.outcomes_to ? `, outcomes to ${day(p.outcomes_to)}` : ''} (${esc(p.refresh)})`).join('; ') + '.'
      + (old.length ? ` <b>Older than its refresh should leave it:</b> ${old.map(p => `${esc(p.label)}, ${Math.floor(age(p))} days`).join('; ')}.` : '');
  }
  asOf();

  return { esc, noteW, dots, loadOutline, drawMap, credit: () => OUTLINE && OUTLINE.credit };
})();
