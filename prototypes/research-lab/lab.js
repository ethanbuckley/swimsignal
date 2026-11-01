// Shared by the Research Lab exhibits (prototype): the drawn map of Great Britain and the dot-and-interval chart.
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
  function project(W) {
    const sx = W / ((BOX.e - BOX.w) * K), H = Math.round((BOX.n - BOX.s) * sx);
    return { H, x: lon => (lon - BOX.w) * K * sx, y: lat => (BOX.n - lat) * sx, sx };
  }
  function ringPath(ring, p) {
    let d = '', last = '';
    for (const [lon, lat] of ring) {
      const pt = `${p.x(lon).toFixed(1)},${p.y(lat).toFixed(1)}`;
      if (pt !== last) { d += (d ? 'L' : 'M') + pt; last = pt; }
    }
    return d + 'Z';
  }
  function drawMap(el, points, opts = {}) {
    const W = Math.max(260, Math.round(el.clientWidth || 400)), p = project(W), H = p.H;
    let g = `<rect width="${W}" height="${H}" fill="var(--sea)"/>`;
    for (let lon = -6; lon <= 2; lon++) g += `<line x1="${p.x(lon)}" x2="${p.x(lon)}" y1="0" y2="${H}" class="grat"/>`;
    for (let lat = 50; lat <= 55; lat++) g += `<line x1="0" x2="${W}" y1="${p.y(lat)}" y2="${p.y(lat)}" class="grat"/>`;
    for (const [name, rings] of Object.entries(OUTLINE.countries)) {
      g += `<path d="${rings.map(r => ringPath(r, p)).join('')}" class="land ${name === 'England' ? 'eng' : 'other'}"/>`;
    }
    for (let lat = 50; lat <= 55; lat++) g += `<text x="4" y="${p.y(lat) - 3}" class="gl">${lat}°N</text>`;
    for (let lon = -5; lon <= 1; lon += 2) g += `<text x="${p.x(lon) + 3}" y="${H - 5}" class="gl">${Math.abs(lon)}°${lon < 0 ? 'W' : 'E'}</text>`;
    const km50 = 50 / 111.32 * p.sx;
    g += `<g transform="translate(${W - km50 - 14},${H - 26})"><line x1="0" x2="${km50}" y1="0" y2="0" stroke="var(--ink)" stroke-width="1.5"/><line x1="0" x2="0" y1="-4" y2="4" stroke="var(--ink)"/><line x1="${km50}" x2="${km50}" y1="-4" y2="4" stroke="var(--ink)"/><text x="${km50 / 2}" y="-7" text-anchor="middle" class="gl">50 km</text></g>`;
    g += `<g transform="translate(${W - 22},18)"><path d="M0 -10 L5 4 L0 1 L-5 4 Z" fill="var(--ink)"/><text y="16" text-anchor="middle" class="gl">N</text></g>`;
    const order = [...points].sort((a, b) => (a.id === opts.selected) - (b.id === opts.selected) || (a.kind === 'pilot') - (b.kind === 'pilot'));
    for (const pt of order) {
      const cx = p.x(pt.lon), cy = p.y(pt.lat), on = pt.id === opts.selected;
      const mark = pt.kind === 'pilot' ? `<circle r="5" class="pt-pilot"/>` : pt.kind === 'small' ? `<circle r="3.5" class="pt-small"/>` : `<circle r="3.5" class="pt-hist"/>`;
      g += `<g class="pt${on ? ' on' : ''}" transform="translate(${cx.toFixed(1)},${cy.toFixed(1)})" data-id="${pt.id}" tabindex="0" role="button" aria-label="${esc(pt.name)}"><title>${esc(pt.name)}</title>${on ? '<circle r="10" class="pt-ring"/>' : ''}${mark}<circle r="11" fill="transparent"/></g>`;
    }
    const sel = points.find(pt => pt.id === opts.selected);
    if (sel) {
      const cx = p.x(sel.lon), cy = p.y(sel.lat), left = cx > W * 0.6;
      g += `<text x="${cx + (left ? -16 : 16)}" y="${cy + 4}" text-anchor="${left ? 'end' : 'start'}" class="pt-label">${esc(opts.label || sel.name)}</text>`;
    }
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="group" aria-label="Map of the sites">${g}</svg>`;
    el.querySelectorAll('.pt').forEach(n => {
      n.onclick = () => opts.onPick && opts.onPick(n.dataset.id);
      n.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); opts.onPick && opts.onPick(n.dataset.id); } };
    });
  }

  return { esc, noteW, dots, loadOutline, drawMap, credit: () => OUTLINE && OUTLINE.credit };
})();
