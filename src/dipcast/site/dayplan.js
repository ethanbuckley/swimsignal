// The day plan (31 Oct 2026, after an outside product review): Plan a swim answers "where should we go, when, and what
// do we need to know?". From what you do on the water, where you start and the day, a few options, each with what
// SwimSignal knows there and what it does not; then the plan for the day, with a backup, as a link and as a picture to
// send. Everything here is from data the page already has (the lite file and a spot's own file): no new requests to a
// weather service. The forecast is for the whole day, never by the hour, and every value says what kind it is and when.
//
// A plain script, as outing.js: the page (index.html, planOptions and drawOuting) calls it, and Node requires it for
// the tests (tests/site_dayplan.test.cjs).

const DP_SHOWN = 3;   // options: a few to choose between, not the list again
const DP_BOAT = ['paddle', 'sup'];
// The desk check of permission (access.py), short; the spot's page has it in full.
const DP_PERMIT = { unconfirmed: 'Permission at this point not confirmed.', restricted_guidance: 'Park guidance restricts river swimming.' };
// What kind of value each is: the page's valueTag (index.html; docs/DESIGN.md, "What kind of value"), or the same
// markup where Node runs this file alone.
const dpTag = (kind, words) => typeof valueTag === 'function' ? valueTag(kind, words) : `<span class="vt vt-${kind}">${words}</span>`;
const dpKind = (kind, words) => ' ' + dpTag(kind, words);
const DP_UNKNOWN = dpTag('none', 'Not known');
const dpEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const dpAgo = h => h < 1 ? 'under an hour ago' : h < 36 ? `${Math.round(h)} h ago` : `${Math.round(h / 24)} days ago`;
const dpDate = iso => new Date(iso + 'T12:00:00Z').toLocaleDateString('en-GB', { timeZone: 'UTC', weekday: 'short', day: 'numeric', month: 'short' });
// A check's date as people write it, "3 Oct 2026", not "2026-10-03"; anything else as given.
const dpWhen = iso => /^\d{4}-\d{2}-\d{2}$/.test(String(iso)) ? new Date(iso + 'T12:00:00Z').toLocaleDateString('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' }) : dpEsc(iso);

// ------------------------------------------------------------------------------ the options
// The plan's groups (plan.js, planSpots: low risk, nothing upstream to forecast from, moderate or higher, no level),
// each nearest first, as [{s, miles, level}]. The options are the first few of the first two that no official notice
// restricts (advised): a spot at moderate risk or higher, or with no level, is never offered as an option. For a boat
// or a board, a spot whose guide's rule says they are not allowed (dpNoBoats) is left out too. [] if none.
const dpNoBoats = s => !!s.boat_note && s.boat_note.topic === 'paddle' && /\bnot (allowed|permitted)\b/i.test(s.boat_note.text || '');
function dpOptions(groups, advised = () => false, act = null, n = DP_SHOWN) {
  return [...(groups[0] || []), ...(groups[1] || [])].filter(o => !advised(o.s) && !(DP_BOAT.includes(act) && dpNoBoats(o.s))).slice(0, n);
}

// ------------------------------------------------------------------------------ what is known at a spot
// The conditions for an option, as rows [label, HTML], each value with its kind and its time, and what is not known,
// as a list of words. s: the spot (its own file may not be in yet: s.detail_file && !s.detail_loaded); day: the plan's
// day; today: today's date; act: the plan's activity (null for a swim); byId: the listed spots, for finishes;
// nowMs: now, for the ages.
function dpConditions(s, day, today, act, byId = new Map(), nowMs = Date.now()) {
  const rows = [], missing = [], unk = [], boat = DP_BOAT.includes(act), river = s.kind === 'river';
  // The water's temperature: a sensor's reading, or the build's estimate, which is for today only.
  const w = s.water_temp, t = w && Date.parse(w.observed_at), e = s.water_temp_est;
  if (w && typeof w.temp_c === 'number' && Number.isFinite(t))
    rows.push(['Water', `${Math.round(w.temp_c)}&nbsp;°C` + dpKind('measured', `Measured ${dpEsc(w.where || 'nearby')}, ${dpAgo((nowMs - t) / 3.6e6)}`)]);
  else if (e && typeof e.temp_c === 'number' && e.date === today && (s.kind === 'river' || s.kind === 'lake'))
    rows.push(['Water', `About ${e.temp_c}&nbsp;°C today${day === today ? '' : `, none for ${dpDate(day)}`}`
      + dpKind('estimate', !e.route || e.route === 'river_model' ? 'Estimate' : 'Provisional estimate')]);
  else missing.push('water temperature');
  // Daylight on the day (the weather file's sunrise and sunset, local time).
  const wd = ((s.weather || {}).days || []).find(x => x && x.date === day);
  if (wd && wd.sunrise && wd.sunset) rows.push(['Daylight', `Sunrise ${dpEsc(wd.sunrise)}, sunset ${dpEsc(wd.sunset)}`]);
  else missing.push('daylight');
  // Access: the desk check of permission, then what the spot's guide covers, once its own file is in.
  const a = s.access && s.access.text ? s.access : null;
  const g = s.guide, facts = g && Array.isArray(g.facts) ? g.facts : [];
  const topics = boat ? [['launch', 'launching'], ['carry', 'carrying'], ['parking', 'parking'], ['exit', 'getting out']]
    : [['parking', 'parking'], ['path', 'the path'], ['entry', 'getting in'], ['exit', 'getting out']];
  const loading = s.detail_file && !s.detail_loaded && !s.detail_missing;
  const has = topics.filter(([k]) => facts.some(f => f && f.topic === k)).map(([, w]) => w);
  const lacks = topics.filter(([k]) => !facts.some(f => f && f.topic === k)).map(([, w]) => w);
  const permitWords = (DP_PERMIT[a && a.status] || dpEsc(a && a.text)).replace(/\.\s*$/, '');
  const permit = a ? `${permitWords} <span class="muted">(checked from published sources${a.checked_at ? `, ${dpWhen(a.checked_at)}` : ''})</span>.` : '';
  const guide = loading ? '<span class="muted">Loading its guide…</span>'
    : has.length ? `Its guide covers ${has.join(', ')}${g.checked ? ` <span class="muted">(checked ${dpWhen(g.checked)})</span>` : ''}.` : '';
  if (permit || guide) rows.push(['Access', [permit, guide].filter(Boolean).join(' ')]);
  if (!loading) missing.push(...(has.length ? lacks : [boat ? 'launching and access' : 'access']));
  if (boat) {
    // For a boat or a board, launching, rules, the river, a finish and wind each have a row, "Not known" where nothing
    // is: in the grey line under the facts the gaps read as small print beside a full table (31 Oct 2026). `unk` names
    // them so the line under the facts does not say them again.
    const b = s.boat_note, lf = facts.find(f => f && f.topic === 'launch');
    if (b && b.topic === 'paddle') rows.push(['Rules', `${dpEsc(b.text)} <span class="muted">(${dpEsc(b.source || 'its guide')})</span>`]);
    else { rows.push(['Rules', DP_UNKNOWN]); unk.push('rules for boats and boards'); }
    if (b && b.topic !== 'paddle') rows.push(['Launching', `${dpEsc(b.text)} <span class="muted">(${dpEsc(b.source || 'its guide')})</span>`]);
    else if (lf) rows.push(['Launching', `In its guide${g.checked ? ` <span class="muted">(checked ${dpWhen(g.checked)})</span>` : ''}`]);
    else if (!loading) { rows.push(['Launching', DP_UNKNOWN]); unk.push('launching', 'launching and access'); }
    if (!(b && b.topic === 'paddle')) missing.push('rules for boats and boards');
    // The river now, at the nearest gauge: an observation, not a forecast for the day.
    const rs = s.river_state;
    if (river && rs && !rs.stale && typeof rs.level_m === 'number') {
      const word = { low: 'Low water', normal: 'Usual level', high: 'High water', 'very high': 'Very high water' }[rs.label] || `${rs.level_m} m`;
      rows.push(['River level', `${word} at ${dpEsc(rs.station)}` + dpKind('measured', `Measured ${dpAgo(rs.age_hours ?? 0)}${day === today ? '' : '; a reading now, not a forecast'}`)]);
    } else if (river) { missing.push('river level'); unk.push('river level');
      // A reading past its age rule is said as such, not as no gauge at all.
      rows.push(['River level', DP_UNKNOWN + (rs && rs.stale && rs.station ? dpKind('stale', `Last reading at ${dpEsc(rs.station)}${typeof rs.age_hours === 'number' ? ` ${dpAgo(rs.age_hours)}` : ''}: too old to use`) : '')]); }
    // Finishes downstream (stretches.py), rivers only.
    const fins = (Array.isArray(s.downstream) ? s.downstream : []).filter(([id]) => byId.has(id)).slice(0, 2);
    if (fins.length) rows.push(['Finish', fins.map(([id, km]) => `${dpEsc(byId.get(id).name)} (${km < 10 ? km : Math.round(km)} km down)`).join(', ')]);
    else if (river) { missing.push('a finish downstream'); rows.push(['Finish', DP_UNKNOWN]); unk.push('a finish downstream'); }
    missing.push('wind');   // SwimSignal has no wind forecast: it would need new weather requests
    rows.push(['Wind', `${DP_UNKNOWN} <span class="muted">(SwimSignal has no wind forecast)</span>`]); unk.push('wind');
  }
  return { rows, missing, unk };
}

// What is the same at every option, said once above them, not under each (2 Nov 2026): rows whose words match at
// all of them (the day's daylight, today's water estimate, no wind forecast) and what none of them has. Access, rules,
// launching, the river and finishes stay with each option even when they match: they are the spot's own, and qualify
// its level. cs: each option's dpConditions. Returns the shared rows and gaps, and each option's conditions without
// them. With one option there is nothing to share.
const DP_OWN = ['Access', 'Rules', 'Launching', 'River level', 'Finish'];
const dpGaps = c => [...new Set(c.missing)].filter(w => !(c.unk || []).includes(w));   // not again what a row already says
function dpShared(cs) {
  if (cs.length < 2) return { rows: [], gaps: [], cs };
  const val = (c, k) => (c.rows.find(r => r[0] === k) || [])[1];
  const rows = cs[0].rows.filter(([k, v]) => !DP_OWN.includes(k) && cs.every(c => val(c, k) === v)), keys = rows.map(r => r[0]);
  const gaps = dpGaps(cs[0]).filter(w => cs.every(c => dpGaps(c).includes(w)));
  return { rows, gaps, cs: cs.map(c => ({ ...c, rows: c.rows.filter(([k]) => !keys.includes(k)), missing: c.missing.filter(w => !gaps.includes(w)) })) };
}

// One option, as HTML. o = {s, miles, level}; v = the page's words for it: { href, headline (HTML), tone, official
// (HTML: a notice, first), meta (text), chosen (it is the plan's spot) }; c = dpConditions; backup: the name of the option that would be its backup.
function dpOption(o, v, c, backup, i) {
  const gaps = dpGaps(c);
  return `<li class="dp-opt"><h3 class="dp-nm"><a href="${dpEsc(v.href)}" data-id="${dpEsc(o.s.id)}">${dpEsc(o.s.name)}</a></h3>`
    + `<p class="k">${dpEsc(v.meta)}</p>${v.official || ''}<p class="hl ${dpEsc(v.tone)}">${v.headline}</p>`
    + (c.rows.length ? `<dl class="dp-facts">${c.rows.map(([k, t]) => `<div><dt>${k}</dt><dd>${t}</dd></div>`).join('')}</dl>` : '')
    + (gaps.length ? `<p class="dp-gap">Not known here: ${dpEsc(gaps.join(', '))}.</p>` : '')
    + (v.chosen ? '<p class="dp-go small">In your plan, below.</p>'
      : `<p class="dp-go"><button type="button" class="btn${i === 0 ? ' primary' : ''}" data-dp-go="${dpEsc(o.s.id)}">Plan the day here</button>`
      + (backup ? ` <span class="small muted">with ${dpEsc(backup)} as backup</span>` : '') + '</p>') + '</li>';
}

// The tile: heading, one line on what the options are, what is the same at all of them (dpShared), and the options; or
// why there are none.
const DP_ALL = n => n === 2 ? 'both' : n === 3 ? 'all three' : `all ${n}`;
function dpSection(on, items, actWord, boat = false, unforecast = false, shared = null) {
  const same = shared && (shared.rows.length || shared.gaps.length) ? `<div class="dp-same"><p class="dp-same-h">The same at ${DP_ALL(items.length)}</p>`
    + (shared.rows.length ? `<dl class="dp-facts">${shared.rows.map(([k, t]) => `<div><dt>${k}</dt><dd>${t}</dd></div>`).join('')}</dl>` : '')
    + (shared.gaps.length ? `<p class="dp-gap">Not known at any of them: ${dpEsc(shared.gaps.join(', '))}.</p>` : '') + '</div>' : '';
  const head = `<h2 class="group-head" id="dp-h">Options ${dpEsc(on)}</h2>`;
  if (!items.length) return `<section class="group tile dp" id="dp" aria-labelledby="dp-h">${head}<p class="sub">No spot within reach is at low risk from sewage spills ${dpEsc(on)}, or has no overflow upstream to forecast from. The full list is below.</p></section>`;
  return `<section class="group tile dp" id="dp" aria-labelledby="dp-h">${head}`
    // The forecast is of pollution, whatever is done on the water: "a low forecast for paddleboarding" said otherwise
    // (31 Oct 2026). unforecast: some options have no overflow upstream, so no level at all.
    + `<p class="sub">The ${items.length === 1 ? 'nearest spot' : `${items.length} nearest spots`} at low risk from sewage spills${unforecast ? ' or with no monitored overflow upstream' : ''}, and what SwimSignal knows at each for ${actWord}. `
    + `${boat ? 'Spots whose guide says boats and boards are not allowed are left out. ' : ''}A forecast for the whole day, not by the hour, and not a water test: check the signs at the water before you go in.</p>`
    + same + `<ol class="dp-list">${items.join('')}</ol></section>`;
}

// ------------------------------------------------------------------------------ the day plan in words
// "Saturday morning at Windermere, Waterhead, with Rydal Water as backup": when (outing.js, outingWhen's words, passed
// in as `when`), where, and the backup. Kayaking or paddleboarding says so after the place.
function dpTitle(when, main, backup, actIng = '') {
  const w = when.replace(/^./, c => c.toUpperCase());
  return `${w} at ${main}${actIng ? `, ${actIng}` : ''}${backup ? `, with ${backup} as backup` : ''}`;
}

// ------------------------------------------------------------------------------ the picture
// A picture of the plan to send to friends, drawn here in the browser and sent nowhere until you share it: the plan
// in words, a map of the spots, each spot's level for the day with its water and daylight, when the forecast was
// issued and the site's address. 1080 x 1350 (a phone's portrait share). p = { title, spots: [{ role, name, lat, lon,
// level (words), colour, lines: [text] }], from: {lat, lon} or null, issued (text), url (text), tiles: { url, sub,
// credit } or null, colours: { bar, ink, muted, paper, line, brand } }. Returns the canvas.
const DP_W = 1080, DP_H = 1350, DP_MAP = { x: 0, y: 330, w: 1080, h: 500 };
// The map is shorter with a third spot (a finish), so every spot's block and the footer fit.
const dpMap = n => ({ ...DP_MAP, h: n > 2 ? 340 : DP_MAP.h });
const dpWorld = (lat, lon, z) => { const n = 256 * 2 ** z, r = lat * Math.PI / 180;
  return [(lon + 180) / 360 * n, (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * n]; };
// The zoom that fits the points in the map with room round them, between 8 and 13.
function dpZoom(points, w = DP_MAP.w, h = DP_MAP.h, pad = 120) {
  for (let z = 13; z > 8; z--) {
    const px = points.map(p => dpWorld(p.lat, p.lon, z)), xs = px.map(p => p[0]), ys = px.map(p => p[1]);
    if (Math.max(...xs) - Math.min(...xs) <= w - 2 * pad && Math.max(...ys) - Math.min(...ys) <= h - 2 * pad) return z;
  }
  return 8;
}
const dpWrap = (ctx, text, width) => {
  const words = String(text).split(' '), lines = [];
  let line = '';
  for (const w of words) { const t = line ? `${line} ${w}` : w; if (ctx.measureText(t).width > width && line) { lines.push(line); line = w; } else line = t; }
  if (line) lines.push(line);
  return lines;
};
async function dpPicture(p, doc = document) {
  const cv = doc.createElement('canvas'); cv.width = DP_W; cv.height = DP_H;
  const ctx = cv.getContext('2d'), C = p.colours, SERIF = '"Source Serif 4", Georgia, serif', SANS = '"Source Sans 3", system-ui, sans-serif';
  if (doc.fonts && doc.fonts.load) await Promise.all([doc.fonts.load(`600 56px ${SERIF}`), doc.fonts.load(`400 30px ${SANS}`), doc.fonts.load(`700 30px ${SANS}`)]).catch(() => {});
  ctx.fillStyle = C.paper; ctx.fillRect(0, 0, DP_W, DP_H);
  ctx.fillStyle = C.bar; ctx.fillRect(0, 0, DP_W, 96);
  ctx.fillStyle = '#fff'; ctx.font = `600 40px ${SERIF}`; ctx.textBaseline = 'middle'; ctx.fillText('SwimSignal', 56, 50);
  // The plan in words, whole: a long one in smaller type, so it never loses its end ("as backup").
  ctx.textBaseline = 'alphabetic'; ctx.fillStyle = C.ink;
  const [size, lines] = [54, 46, 40, 34].map(px => { ctx.font = `600 ${px}px ${SERIF}`; return [px, dpWrap(ctx, p.title, DP_W - 112)]; })
    .find(([px, l]) => px + (l.length - 1) * Math.round(px * 1.18) <= 186) || [34, null];   // the last line's foot clear of the map at 330
  ctx.font = `600 ${size}px ${SERIF}`;
  (lines || dpWrap(ctx, p.title, DP_W - 112)).slice(0, 5).forEach((l, i) => ctx.fillText(l, 56, 128 + size + i * Math.round(size * 1.18)));
  // The map: tiles where they load (a tile that fails, or a provider that does not allow it, leaves the paper), the
  // start as a small dot, the spots as numbered rings.
  const pts = p.spots.filter(s => Number.isFinite(s.lat) && Number.isFinite(s.lon)), M = dpMap(p.spots.length);
  if (pts.length) {
    const z = dpZoom(pts, M.w, M.h), xs = pts.map(s => dpWorld(s.lat, s.lon, z));
    const cx = (Math.min(...xs.map(q => q[0])) + Math.max(...xs.map(q => q[0]))) / 2, cy = (Math.min(...xs.map(q => q[1])) + Math.max(...xs.map(q => q[1]))) / 2;
    const ox = cx - M.w / 2, oy = cy - M.h / 2, at = (lat, lon) => { const q = dpWorld(lat, lon, z); return [q[0] - ox + M.x, q[1] - oy + M.y]; };
    ctx.save(); ctx.beginPath(); ctx.rect(M.x, M.y, M.w, M.h); ctx.clip();
    ctx.fillStyle = C.line; ctx.fillRect(M.x, M.y, M.w, M.h);
    if (p.tiles) await dpTiles(ctx, p.tiles, z, ox, oy, doc, M);
    if (p.from && Number.isFinite(p.from.lat)) { const [x, y] = at(p.from.lat, p.from.lon);
      ctx.fillStyle = C.ink; ctx.beginPath(); ctx.arc(x, y, 9, 0, 2 * Math.PI); ctx.fill(); }
    pts.forEach((s, i) => { const [x, y] = at(s.lat, s.lon);
      ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(x, y, 26, 0, 2 * Math.PI); ctx.fill();
      ctx.lineWidth = 8; ctx.strokeStyle = s.colour; ctx.beginPath(); ctx.arc(x, y, 26, 0, 2 * Math.PI); ctx.stroke();
      ctx.fillStyle = C.ink; ctx.font = `700 28px ${SANS}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(String(i + 1), x, y + 1);
      ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'; });
    ctx.restore();
    if (p.tiles && p.tiles.credit) { ctx.font = `400 20px ${SANS}`; ctx.fillStyle = C.muted; ctx.textAlign = 'right';
      ctx.fillText(`Map: ${p.tiles.credit}`, DP_W - 24, M.y + M.h + 28); ctx.textAlign = 'left'; }
  }
  // Each spot: its number, role and name, the level in its colour, and its lines.
  let y = M.y + M.h + 80;
  p.spots.forEach((s, i) => {
    ctx.fillStyle = C.muted; ctx.font = `700 26px ${SANS}`; ctx.fillText(`${i + 1}  ${s.role}`, 56, y);
    ctx.fillStyle = C.ink; ctx.font = `600 38px ${SERIF}`; ctx.fillText(dpWrap(ctx, s.name, DP_W - 112)[0], 56, y + 46);
    ctx.fillStyle = s.colour; ctx.font = `700 32px ${SANS}`; ctx.fillText(s.level, 56, y + 90);
    ctx.fillStyle = C.ink; ctx.font = `400 26px ${SANS}`;
    s.lines.slice(0, 1).forEach((l, j) => ctx.fillText(dpWrap(ctx, l, DP_W - 112)[0], 56, y + 128 + j * 34));
    y += p.spots.length > 2 ? 166 : 172;
  });
  ctx.fillStyle = C.muted; ctx.font = `400 24px ${SANS}`;
  dpWrap(ctx, `Forecast issued ${p.issued}. A forecast for the whole day, not a water test: check the signs at the water.`, DP_W - 112)
    .slice(0, 2).forEach((l, i) => ctx.fillText(l, 56, DP_H - 92 + i * 32));
  ctx.fillStyle = C.brand; ctx.font = `700 26px ${SANS}`; ctx.fillText(p.url, 56, DP_H - 24);
  return cv;
}
// The map's tiles, at zoom z, for the window whose top left is (ox, oy) in world pixels. Each tile is asked for as an
// image the canvas may read (crossOrigin); one that does not come in 5 s, or fails, is left out.
async function dpTiles(ctx, t, z, ox, oy, doc, M = DP_MAP) {
  const n = 2 ** z, jobs = [];
  for (let tx = Math.floor(ox / 256); tx <= Math.floor((ox + M.w) / 256); tx++)
    for (let ty = Math.floor(oy / 256); ty <= Math.floor((oy + M.h) / 256); ty++) {
      if (ty < 0 || ty >= n) continue;
      const x = ((tx % n) + n) % n, sub = t.sub && t.sub.length ? t.sub[Math.abs(x + ty) % t.sub.length] : '';
      const src = t.url.replace('{s}', sub).replace('{z}', z).replace('{x}', x).replace('{y}', ty).replace('{r}', '');
      jobs.push(new Promise(res => { const im = new (doc.defaultView || window).Image(); im.crossOrigin = 'anonymous';
        const done = ok => { clearTimeout(timer); res(ok ? [im, tx, ty] : null); }, timer = setTimeout(() => done(false), 5000);
        im.onload = () => done(true); im.onerror = () => done(false); im.src = src; }));
    }
  const got = (await Promise.all(jobs)).filter(Boolean);
  ctx.save(); ctx.filter = 'grayscale(0.85) brightness(1.04)';
  for (const [im, tx, ty] of got) ctx.drawImage(im, tx * 256 - ox + M.x, ty * 256 - oy + M.y, 256, 256);
  ctx.restore();
}
// The canvas as a PNG file, or null where the browser will not give it (a tile from a provider that did not allow it
// would taint the canvas: the page then draws it again without tiles).
const dpBlob = cv => new Promise(res => { try { cv.toBlob(b => res(b), 'image/png'); } catch (e) { res(null); } });

if (typeof module === 'object' && module.exports) {
  module.exports = { DP_SHOWN, DP_H, dpMap, dpNoBoats, dpOptions, dpConditions, dpShared, dpOption, dpSection, dpTitle, dpZoom, dpWorld, dpWrap };
}
