// Evidence map (prototype, docs/EVIDENCE-MAP-2026-10.md): where a spot's forecast has evidence upstream,
// and where its knowledge ends. Shown only with ?evidence=1 in the address (index.html, mountEvmap), so
// the page is unchanged without it.
//
// The task it answers: "Before I go, show me where SwimSignal's forecast for this spot has evidence, and
// where its knowledge ends." The test it must pass: a reader shown a poorly covered spot does not take the
// water to be fine because the drawing looks empty or calm. So:
//   - "little evidence here" and "the evidence there is shows no spill" are told apart in words and in
//     marks, never by colour alone: a filled mark is a reading, a hollow one a gap, and the line at the
//     top of the tile says which of the two the spot has;
//   - every mark, tapped, says whose it is, when it was read and how old that is, and how it stands to
//     the spot ("25.7 km upstream, about 36 h at the model's 0.2 m/s");
//   - gaps are drawn, not left out: overflows with no live feed, with no current reading, or whose
//     reading this page's data does not hold one by one; where the trace stops, 60 km up the rivers; the
//     rivers between the marks, along which nothing is measured; a spot with no lab samples.
// Nothing here says a spill caused anything at the spot: "reported upstream", "modelled to reach".
//
// Its data, all of it already published: the spot (spots-lite.json with data/spot/<id>.json, whose
// `contributors` are the ten overflows that matter most this week, each with its live state), its trace
// (data/spot/<id>-trace.json, build_site.write_traces: the rivers within 60 km upstream, as encoded lines)
// and every overflow upstream (data/upstream/<id>.json, build_site.write_upstream: names, distances,
// reach and has_live, but not the live state). An overflow outside the ten gets its state from the spot's
// counts (`now`, forecast.live_counts) only where the counts leave one answer (evmapOthers); otherwise
// it is drawn as a reading this page does not hold, and the counts are said in words.
//
// A plain script, like replay.js: in the page its names are globals (each begins evmap or EVMAP), and in
// Node the last lines export them (tests/site_evmap.test.cjs). The rows under the drawing are the full
// text; the drawing repeats them for the eye, and a tap on it shows one row.

const EVMAP_FEED_H = 6;   // ingest.live.FEED_CURRENT_H: a reading from a feed older than this is not current
// A dead end of the trace this share of the 60 km or further along the rivers is taken as a place where
// the trace was cut, not a stream's source. The trace file does not say which ends were cut, and its lines
// are simplified to 25 m, which shortens them. On the files of 30 Oct 2026 the Wye at Symonds Yat has eight
// ends between 58.7 and 59.5 km and the next at 56.7; the Wharfe at Cromwheel's run evenly from 58.7 down,
// so there a source near 58 km cannot be told from a cut. An estimate, said so on the page and in the doc:
// a cut end missed is better than a beck's source called the edge of the forecast. The build could flag
// the cut ends (transport.traced_lines knows which lines it shortened).
const EVMAP_CUT = 0.97;
const EVMAP_W = 480;
const evmapEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const evmapMs = iso => (iso ? Date.parse(iso) : NaN);
const evmapNames = c => (typeof overflowNames === 'function' ? overflowNames(c) : { plain: String(c.site_name || c.site_id || ''), own: '' });
const evmapCompany = c => (typeof companyName === 'function' ? companyName(c) : String(c ?? ''));
const evmapOwn = co => `${co}${/s$/.test(co) ? "'" : "'s"}`;   // "United Utilities'", "Yorkshire Water's"
// What the level rests on (evidence.js): its rows, gaps, ages and times, so the two tiles say things alike.
// The page loads it before the page script; Node requires it.
const evmapEv = () => (typeof evidenceItems === 'function' ? { evidenceItems, evidenceAge, evidenceSince } : require('./evidence.js'));
const evmapKm = v => `${Number(v).toFixed(1)}&nbsp;km`;
const evmapPct = w => (w > 0 && w < 0.005 ? 'under 1%' : `${Math.round(w * 100)}%`);

// An encoded polyline (trace.py, encode) as integer [lat, lon] pairs in 1e-5 degrees, so the ends of two
// lines that meet compare equal (index.html's decodeLine gives degrees).
function evmapDecode(str) {
  const pts = []; let i = 0, lat = 0, lon = 0;
  const next = () => { let shift = 0, res = 0, b; do { b = str.charCodeAt(i++) - 63; res |= (b & 31) << shift; shift += 5; } while (b >= 32); return res & 1 ? ~(res >> 1) : res >> 1; };
  while (i < str.length) { lat += next(); lon += next(); pts.push([lat, lon]); }
  return pts;
}
// Kilometres east and north of the spot: flat, which is near enough within 60 km for a drawing and for
// adding up a line's length.
const evmapProj = (lat0, lon0) => { const k = Math.cos(lat0 * Math.PI / 180) * 111.32;
  return (lat, lon) => [(lon - lon0) * k, (lat - lat0) * 110.57]; };

// Where the trace stops: the dead ends of the traced rivers that lie EVMAP_CUT of the cap or further
// along them from the spot. The lines meet end to end (trace.encoded_lines splits them at every fork), so
// they make a graph; the walk starts at the end nearest the spot, which on a river is the spot's own line.
// A part the walk cannot reach (a gap the network repairs without a line) is left unmarked. Returns
// [{ lat, lon, km }], the furthest first.
function evmapEnds(lines, lat0, lon0, capKm = 60) {
  const P = evmapProj(lat0, lon0), key = p => `${p[0]},${p[1]}`, adj = new Map(), at = new Map();
  const len = l => { let s = 0; for (let i = 1; i < l.length; i++) { const a = P(l[i - 1][0] / 1e5, l[i - 1][1] / 1e5), b = P(l[i][0] / 1e5, l[i][1] / 1e5); s += Math.hypot(a[0] - b[0], a[1] - b[1]); } return s; };
  for (const l of lines) {
    if (l.length < 2) continue;
    const a = key(l[0]), b = key(l[l.length - 1]), L = len(l);
    at.set(a, l[0]); at.set(b, l[l.length - 1]);
    for (const [u, v] of [[a, b], [b, a]]) { if (!adj.has(u)) adj.set(u, []); adj.get(u).push([v, L]); }
  }
  let start = null, near = Infinity;
  for (const [k, p] of at) { const d = Math.hypot(...P(p[0] / 1e5, p[1] / 1e5)); if (d < near) { near = d; start = k; } }
  if (start === null) return [];
  const dist = new Map([[start, near]]), todo = [[near, start]];
  while (todo.length) {
    todo.sort((x, y) => x[0] - y[0]);
    const [d, u] = todo.shift();
    if (d > dist.get(u)) continue;
    for (const [v, L] of adj.get(u) || []) if (!dist.has(v) || d + L < dist.get(v)) { dist.set(v, d + L); todo.push([d + L, v]); }
  }
  return [...adj].filter(([k, e]) => e.length === 1 && k !== start && dist.get(k) >= EVMAP_CUT * capKm)
    .map(([k]) => ({ lat: at.get(k)[0] / 1e5, lon: at.get(k)[1] / 1e5, km: Math.round(dist.get(k) * 10) / 10 }))
    .sort((a, b) => b.km - a.km);
}

// One of the ten listed overflows as the forecast counted it at issue (forecast.live_counts): discharging
// (or running when its company's feed last answered), a spill lately whose water the model still counts,
// or a current "not discharging". Those are the ones it calls reporting live.
const evmapRunning = c => c.status === 1 || (c.status === -3 && c.last_status === 1);
const evmapRecent = c => !evmapRunning(c) && c.status !== -3 && Number(c.now_contribution) > 0;
const evmapCounted = c => evmapRunning(c) || evmapRecent(c) || (c.data_state === 'live' && c.status === 0);
const evmapFar = (o, d) => ((d.upstream_summary || {}).too_far || 0) > 0 && Math.round((Number(o.weight) || 0) * 100) === 0;

// The mark of one listed overflow, and so how it is drawn:
//   spill    a spill reported running, or lately, whose water the model still counts (filled, ringed)
//   live     a current "not discharging" (filled)
//   dark     in a live feed, but no current reading: offline, a stale feed, a feed down, or a reading
//            now over EVMAP_FEED_H old where the page is read (hollow, struck through)
//   nofeed   not in any live feed SwimSignal reads (hollow, dashed)
// and for the others, outside the ten: `unheld`, a reading this page's data does not hold one by one
// (hollow, a dot inside), or `far`, upstream but too little of its water reaches here to count.
function evmapMark(c, nowMs) {
  if (evmapRunning(c) || evmapRecent(c)) return 'spill';
  if (c.data_state === 'no_feed' || (c.status === -2)) return 'nofeed';
  if (c.data_state === 'live' && c.status === 0) return nowMs - evmapMs(c.feed_updated_at) > EVMAP_FEED_H * 36e5 ? 'dark' : 'live';
  return 'dark';
}

// The overflows outside the ten that are in a live feed (has_live): how many of them the spot's counts
// say reported live at issue, and how many a spill, by taking the ten's own away. Where every one of them
// reported quietly, or none reported, the counts settle each one's state; otherwise they do not.
function evmapOthers(d, rows, listed) {
  const n = d.now || {}, total = (d.upstream_summary || {}).overflows || 0;
  const others = rows.filter(o => !listed.has(o.site_id) && o.has_live === true && !evmapFar(o, d));
  const ten = [...listed.values()];
  const live = Math.max(0, Math.min(others.length, Math.min(total, n.monitored_upstream || 0) - ten.filter(evmapCounted).length));
  const spill = Math.max(0, (n.discharging_upstream || 0) - ten.filter(evmapRunning).length) + Math.max(0, (n.recent_upstream || 0) - ten.filter(evmapRecent).length);
  return { n: others.length, live, spill, state: !others.length || spill ? 'unheld' : live === others.length ? 'live' : live === 0 ? 'dark' : 'unheld' };
}

// Where an overflow is from the spot, along the water, and how long the model takes its water to arrive:
// "25.7 km upstream, about 36 h at the model's 0.2 m/s". Across a lake the lake's slower speed is named too.
function evmapRel(o, a = {}) {
  if (o.distance_km === null || o.distance_km === undefined) return '';
  const km = Number(o.distance_km) || 0, lake = Number(o.lake_distance_km) || 0, h = Number(o.travel_h);
  if (km + lake < 0.1) return 'At the spot.';
  const v = a.river_velocity_ms ?? 0.2, lv = a.lake_velocity_ms ?? 0.05;
  const when = !Number.isFinite(h) ? '' : h < 1 ? ', under an hour' : `, about ${Math.round(h)}&nbsp;h`;
  const speed = lake > 0 ? ` at the model's ${v}&nbsp;m/s in rivers and ${lv}&nbsp;m/s in lakes` : ` at the model's ${v}&nbsp;m/s`;
  return `${evmapKm(km + lake)} upstream${lake > 0 ? `, ${evmapKm(lake)} of it across a lake` : ''}${when ? when + speed : ''}.`
    + (Number.isFinite(Number(o.weight)) ? ` The model expects ${evmapPct(Number(o.weight))} of a spill's bacteria to reach the spot.` : '');
}

// What one overflow's mark says, as a row: what, when (at), what it reported (say), whose (src), and
// where it is from the spot (rel). `c` is its listed entry, where it is one of the ten; `o` its row
// from the upstream file; `oth` evmapOthers' counts.
function evmapOverflow(o, c, d, oth, nowMs) {
  const E = evmapEv(), x = c || o, co = evmapCompany(x.company || ''), nm = evmapNames(x);
  const quiet = ((d.now || {}).quiet_by_feed || []).find(f => f.company === x.company);
  // No details (the upstream file did not load, so the trace's position is all there is): not known.
  const bare = !c && typeof o.has_live !== 'boolean';
  const mark = bare ? 'unheld' : evmapFar(o, d) ? 'far' : c ? evmapMark(c, nowMs) : o.has_live === false ? 'nofeed'
    : oth.state === 'live' && quiet && nowMs - evmapMs(quiet.updated_at) > EVMAP_FEED_H * 36e5 ? 'dark' : oth.state;
  const feed = co ? `${evmapOwn(co)} live feed, via the National Storm Overflow Hub` : 'Its company\'s live feed';
  const returns = "The Environment Agency's annual returns, for its place and past spills";
  let at = null, say, src = feed;
  if (bare) { say = 'Counted by the forecast; this page could not load its details, so what it reported is not shown.'; src = "SwimSignal's trace"; }
  else if (mark === 'far') { say = 'Upstream, but too little of its water would reach here to count.'; src = returns; }
  else if (mark === 'nofeed') {
    // A company with no live feed is named as such where one of the ten says so (data_state no_feed).
    const none = (c || (d.contributors || []).find(k => k.company === x.company) || {}).data_state === 'no_feed';
    say = `No live reading: ${none ? `${co} has no live feed SwimSignal reads` : c ? `it is not in ${evmapOwn(co)} live feed` : 'it is not in any live feed SwimSignal reads'}. `
      + 'The model estimates its spills from the rain forecast and its past spills.';
    src = `${returns}. No live feed`;
  } else if (!c && mark !== 'dark') {
    // Outside the ten: what the counts can say.
    at = quiet && mark === 'live' ? quiet.updated_at : null;
    say = mark === 'live' ? 'Reported not discharging at issue, going by the spot\'s counts: this page lists the ten overflows that matter most one by one, and the rest only as counts.'
      : `In the live feed, but this page's data does not say what it reported. Of the ${oth.n} overflows upstream like it, `
      + `${oth.live} reported live at issue${oth.spill ? ` (${oth.spill} with a spill running or lately)` : ''} and ${oth.n - oth.live} did not; which is which is not in the data.`;
  } else if (!c) {
    say = quiet && oth.state === 'live' ? `Reported not discharging at issue, going by the spot's counts, but ${evmapOwn(co)} feed had last updated ${E.evidenceSince(quiet.updated_at)}, over ${EVMAP_FEED_H} hours ago.`
      : 'No current reading at issue, going by the spot\'s counts: offline, or its feed not current.';
    at = quiet ? quiet.updated_at : null;
  } else {
    at = c.feed_updated_at || null;
    if (mark === 'spill') say = evmapRunning(c)
      ? (c.status === 1 ? `Reported discharging at the last poll${c.latest_event_start ? `, since ${E.evidenceSince(c.latest_event_start)}` : ''}.`
        : `Reported discharging when ${evmapOwn(co)} feed last answered; it has not answered since.`)
      : `Reported a spill${c.latest_event_end ? ` that ended ${E.evidenceSince(c.latest_event_end)}` : ' lately'}. The model still counts its water here.`;
    else if (mark === 'live') say = 'Reported not discharging at the last poll.';
    else say = c.data_state === 'live' && c.status === 0 ? `Reported not discharging at the last poll, but that reading is now over ${EVMAP_FEED_H} hours old.`
      : c.data_state === 'stale' ? `Its last reading is from a feed not updated within ${EVMAP_FEED_H} hours, so it may be out of date.`
      : c.status === -3 ? `No reading: ${evmapOwn(co)} feed did not answer the last poll.`
      : 'No reading: the monitor was offline at the last poll.';
  }
  return { id: String(x.site_id), kind: 'overflow', mark, lat: Number(o.lat ?? x.lat), lon: Number(o.lon ?? x.lon),
    what: evmapEsc(nm.plain), own: nm.own ? evmapEsc(nm.own) : '', say, src, at,
    age: at ? E.evidenceAge(at, nowMs) : 'No reading', rel: evmapRel(x, d.assumptions || {}), gap: !['live', 'spill'].includes(mark) };
}

// How much the overflows upstream are watched, as the line at the top of the tile: the head and its
// glyph tell a spot with little evidence from one whose evidence shows no spill. The share is of the
// modelled reach (now: monitored_weight over upstream_weight), as levels.js's nowWatched counts it, and
// its half-way line (NOW_WATCHED_SHARE) is the one where the page stops giving a right-now level.
function evmapCoverage(d) {
  const n = d.now || {}, total = (d.upstream_summary || {}).overflows || 0, cap = (d.assumptions || {}).max_upstream_km ?? 60;
  if (!total) return { kind: 'none', mark: 'nofeed', head: 'No overflow evidence here.',
    said: `No monitored overflow on the rivers traced ${cap}&nbsp;km upstream, so there is nothing for the forecast to read. `
      + 'An empty drawing does not mean nothing reaches the water: farms, wildlife and unmonitored sources are not modelled.' };
  const mon = Math.min(total, n.monitored_upstream || 0), w = Number(n.upstream_weight), share = w > 0 ? Math.min(1, (Number(n.monitored_weight) || 0) / w) : (mon / total);
  const cos = [...new Set(((d.upstream_summary || {}).companies || []).map(evmapCompany))];
  if (!mon) return { kind: 'little', mark: 'nofeed', head: 'Little evidence here.',
    said: `None of the ${total} overflows upstream reports live${(n.no_feed_upstream || 0) >= total && cos.length === 1 ? `: ${cos[0]} has no live feed SwimSignal reads` : ''}. `
      + 'The level above is the model\'s estimate from the rain forecast and each overflow\'s past spills, not a reading. A quiet drawing here means not known.' };
  const dis = n.discharging_upstream || 0, rec = n.recent_upstream || 0;
  const shows = `What they reported at issue: ${dis ? `${dis} discharging` : 'none discharging'}${rec ? `, ${rec} with a spill lately whose water the model still counts` : ''}.`;
  if (share < 0.5) return { kind: 'little', mark: 'dark', head: 'Little live evidence here.',
    said: `${mon} of ${total} overflows upstream report live, but they carry ${evmapPct(share)} of the modelled reach: the ones that matter most here do not report. ${shows}` };
  return { kind: 'most', mark: dis || rec ? 'spill' : 'live', head: 'Live evidence for most of the reach.',
    said: `${mon} of ${total} overflows upstream report live, carrying ${evmapPct(share)} of the modelled reach. ${shows}` };
}

// Everything the tile shows: the overflows, the spot's own evidence and gaps (the rain, the rating, the
// algae, the lab sample, from evidence.js, each with how it stands to the spot), the gauge, where the
// trace stops and the rivers between. `trace` is the trace file, `up` the upstream file (either may be null).
function evmapModel(d, trace, up, nowMs, generatedAt) {
  const E = evmapEv(), a = d.assumptions || {}, cap = a.max_upstream_km ?? (trace && trace.max_upstream_km) ?? 60;
  const listed = new Map((d.contributors || []).map(c => [c.site_id, c]));
  const fromTrace = ((trace && trace.overflows) || []).map(([site_id, lat, lon]) => ({ site_id, lat, lon }));
  const rows = up && Array.isArray(up.overflows) && up.overflows.length ? up.overflows : fromTrace.length ? fromTrace.map(o => ({ ...listed.get(o.site_id), ...o })) : [...listed.values()];
  const oth = evmapOthers(d, rows, listed);
  const ovs = rows.map(o => evmapOverflow(o, listed.get(o.site_id), d, oth, nowMs)).filter(o => Number.isFinite(o.lat) && Number.isFinite(o.lon));
  const sp = (d.location || {}).snapped || d, lat0 = Number(sp.lat), lon0 = Number(sp.lon);
  const lines = ((trace && trace.lines) || []).map(evmapDecode);
  const ends = evmapEnds(lines, lat0, lon0, cap);
  const items = [], gaps = [];
  // The spot's own evidence, from evidence.js, with where each was read.
  const REL = { 'Rain here': "At the spot's own cell of the weather model. The spills are estimated from the rain at each overflow's cell.",
    'Environment Agency rating': 'For this bathing water, from the samples taken here.',
    'Algae at the last check': 'At this bathing water.', 'Latest lab sample': 'Taken at this bathing water.' };
  const ev = E.evidenceItems(d, nowMs, generatedAt);
  for (const r of ev.rows) if (r.what !== 'Overflows upstream')
    items.push({ id: r.what === 'Latest lab sample' ? 'sample' : r.what, kind: r.what === 'Latest lab sample' ? 'sample' : 'spot', mark: 'live', what: r.what,
      say: r.say, src: r.src, at: r.at || null, age: r.age || '', rel: REL[r.what] || 'At the spot.', gap: false });
  const rs = d.river_state;
  if (rs && rs.station) items.push({ id: 'gauge', kind: 'gauge', mark: rs.stale ? 'dark' : 'live', what: `River level at ${evmapEsc(rs.station)}`,
    say: `${rs.stale ? 'No current reading.' : `${Number(rs.level_m).toFixed(2)}&nbsp;m${rs.label ? `, ${evmapEsc({ low: 'low water', normal: 'its usual level', high: 'high water', 'very high': 'very high water' }[rs.label] || rs.label)}` : ''}.`} Not part of the pollution level.`,
    src: 'The Environment Agency\'s real-time river levels', at: rs.observed_at || null, age: rs.observed_at ? E.evidenceAge(rs.observed_at, nowMs) : 'No reading',
    rel: `${evmapKm(rs.distance_km)} away in a straight line${rs.same_river === false ? ', on a different watercourse' : rs.same_river ? ', on the same river' : ''}. Not drawn: this page's data gives its distance, not its place.`, gap: !!rs.stale });
  else gaps.push({ id: 'gauge', kind: 'gauge', mark: 'nofeed', what: 'No river gauge', say: 'No Environment Agency river gauge with a reading within 15&nbsp;km.', src: '', at: null, age: '', rel: '', gap: true });
  // evidence.js's gaps, each under the name of what is missing.
  const named = g => /lab sample/.test(g) ? 'Lab samples' : /^Runoff|lists agriculture/.test(g) ? 'Runoff from farms' : /algae/i.test(g) ? 'Algae checks'
    : /rating/.test(g) ? 'Environment Agency rating' : /rain/.test(g) ? 'Rain' : /overflow/.test(g) ? 'Overflows upstream' : 'Not known here';
  for (const g of ev.gaps) gaps.push({ id: /lab sample/.test(g) ? 'sample' : `gap${gaps.length}`, kind: /lab sample/.test(g) ? 'sample' : 'spot', mark: 'nofeed',
    what: named(g), say: g, src: '', at: null, age: '', rel: /lab sample/.test(g) ? 'At this spot.' : '', gap: true });
  if (ends.length) gaps.push({ id: 'limit', kind: 'limit', mark: 'limit', what: `Where the trace stops, ${cap}&nbsp;km up the rivers`,
    say: `The forecast follows the rivers ${cap}&nbsp;km upstream and stops. Overflows above these ${ends.length === 1 ? 'point' : `${ends.length} points`} are not counted, whatever they report.`,
    src: "SwimSignal's trace of OS Open Rivers", at: null, age: '',
    rel: `About ${cap}&nbsp;km upstream along the rivers: water from there would take over ${Math.round(cap * 1000 / (a.river_velocity_ms ?? 0.2) / 3600)}&nbsp;h at the model's ${a.river_velocity_ms ?? 0.2}&nbsp;m/s. Marked where a traced river ends ${Math.round(EVMAP_CUT * cap)}&nbsp;km or more along it, an estimate.`, gap: true });
  if (lines.length) gaps.push({ id: 'river', kind: 'river', mark: 'river', what: 'The rivers traced upstream',
    say: 'Water from these rivers reaches the spot. Nothing along them is measured: only the overflows marked are counted, and farms, wildlife and other sources are not modelled.',
    src: "SwimSignal's trace of OS Open Rivers", at: null, age: '', rel: `Within ${cap}&nbsp;km upstream along the rivers.`, gap: true });
  return { spot: { lat: lat0, lon: lon0, name: d.name || '' }, lines, ends, overflows: ovs, items, gaps, cover: evmapCoverage(d), cap, generatedAt,
    sampled: items.some(i => i.kind === 'sample') };
}

// The drawing's layout at a width in CSS pixels: every point in pixels, the spot at its place. Kept apart
// from the drawing so a tap can be matched to the nearest mark (evmapBind).
function evmapLayout(m, width = EVMAP_W) {
  const P = evmapProj(m.spot.lat, m.spot.lon), pts = [[0, 0]];
  const lines = m.lines.map(l => l.map(([a, b]) => P(a / 1e5, b / 1e5)));
  for (const l of lines) for (const p of l) pts.push(p);
  for (const o of m.overflows) pts.push(P(o.lat, o.lon));
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]), pad = 22, top = 8;
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const wk = Math.max(x1 - x0, 2), hk = Math.max(y1 - y0, 2), maxH = Math.max(260, Math.min(560, width * 1.4));
  let s = (width - 2 * pad) / wk;
  if (hk * s + 2 * pad + top + 26 > maxH) s = (maxH - 2 * pad - top - 26) / hk;
  const height = Math.round(Math.max(200, hk * s + 2 * pad + top + 26)), ox = (width - wk * s) / 2, oy = pad + top + (height - 2 * pad - top - 26 - hk * s) / 2;
  const at = ([x, y]) => [ox + (x - x0) * s, oy + (y1 - y) * s];
  return { width, height, s, spot: at([0, 0]), lines: lines.map(l => l.map(at)),
    overflows: m.overflows.map(o => at(P(o.lat, o.lon))), ends: m.ends.map(e => at(P(e.lat, e.lon))) };
}

// A mark's shape: filled for a reading, hollow for a gap, so that a spot with nothing live upstream
// draws as a scatter of open rings, not as an empty or quiet map. Colour only repeats it.
const evmapR = w => 5.5 + 3.5 * Math.sqrt(Math.max(0, Math.min(1, Number(w) || 0)));
function evmapShape(mark, x, y, r = 5) {
  const c = `cx="${x.toFixed(1)}" cy="${y.toFixed(1)}"`;
  if (mark === 'spill') return `<circle ${c} r="${(r + 3).toFixed(1)}" class="em-ring"/><circle ${c} r="${r.toFixed(1)}" class="em-spill"/>`;
  if (mark === 'live') return `<circle ${c} r="${r.toFixed(1)}" class="em-live"/>`;
  if (mark === 'dark') return `<circle ${c} r="${r.toFixed(1)}" class="em-open"/><path d="M${(x - r * 0.7).toFixed(1)} ${(y + r * 0.7).toFixed(1)}L${(x + r * 0.7).toFixed(1)} ${(y - r * 0.7).toFixed(1)}" class="em-strike"/>`;
  if (mark === 'unheld') return `<circle ${c} r="${r.toFixed(1)}" class="em-open"/><circle ${c} r="1.6" class="em-dot"/>`;
  if (mark === 'far') return `<circle ${c} r="2.5" class="em-open"/>`;
  return `<circle ${c} r="${r.toFixed(1)}" class="em-open em-dash"/>`;   // nofeed
}
// The key's swatch for a mark, 16 by 14, and the mark's words.
const EVMAP_KEY = {
  spill: 'reported a spill, running or lately',
  live: 'reported not discharging',
  dark: 'in a live feed, no current reading',
  unheld: "in a live feed, its reading not in this page's data",
  nofeed: 'not in any live feed: no reading',
  far: 'too far to count',
};
const evmapSwatch = mark => `<svg class="em-sw" viewBox="0 0 22 18" width="22" height="18" aria-hidden="true">${
  mark === 'river' ? '<path d="M1 12C6 4 12 16 21 6" class="em-river"/>'
    : mark === 'limit' ? '<path d="M1 9H13" class="em-river"/><path d="M14 3V15" class="em-limit"/>'
      : mark === 'spot' ? '<circle cx="11" cy="9" r="6" class="em-spot"/><circle cx="11" cy="9" r="2" class="em-spotdot"/>'
        : mark === 'sample' ? '<rect x="6" y="4" width="10" height="10" class="em-live"/>'
          : mark === 'nosample' ? '<rect x="6" y="4" width="10" height="10" class="em-open em-dash"/>' : evmapShape(mark, 11, 9, 5)}</svg>`;

// The drawing: the traced rivers, a bar where the trace stops, the overflows' marks, and the spot,
// ringed, with a square beside it for its lab samples (filled where there is one, dashed where there is
// none). A scale bar, in straight-line km, since the rows give distances along the rivers.
function evmapSvg(m, width = EVMAP_W) {
  const L = evmapLayout(m, width), f = v => v.toFixed(1);
  const rivers = L.lines.map(l => `<path d="M${l.map(p => `${f(p[0])} ${f(p[1])}`).join('L')}" class="em-river"/>`).join('');
  const bars = L.ends.map((p, i) => {
    // A short bar across the river's end, at right angles to its last stretch where it can be found.
    const e = m.ends[i], line = L.lines.find(l => { const q = l[0], r = l[l.length - 1]; return Math.hypot(q[0] - p[0], q[1] - p[1]) < 0.01 || Math.hypot(r[0] - p[0], r[1] - p[1]) < 0.01; });
    let dx = 0, dy = 1;
    if (line && line.length > 1) { const a = Math.hypot(line[0][0] - p[0], line[0][1] - p[1]) < 0.01 ? line[1] : line[line.length - 2], h = Math.hypot(p[0] - a[0], p[1] - a[1]) || 1; dx = -(p[1] - a[1]) / h; dy = (p[0] - a[0]) / h; }
    return `<path d="M${f(p[0] - 6 * dx)} ${f(p[1] - 6 * dy)}L${f(p[0] + 6 * dx)} ${f(p[1] + 6 * dy)}" class="em-limit" data-km="${e.km}"/>`;
  }).join('');
  const order = { far: 0, nofeed: 1, unheld: 2, dark: 3, live: 4, spill: 5 };   // the readings on top
  const marks = m.overflows.map((o, i) => [o, L.overflows[i]]).sort((a, b) => order[a[0].mark] - order[b[0].mark])
    .map(([o, p]) => evmapShape(o.mark, p[0], p[1], evmapR((o.weight ?? 0)))).join('');
  const [sx, sy] = L.spot, sq = m.sampled ? 'em-live' : 'em-open em-dash';
  // The spot's square and label go on whichever side has the fewest marks under them and stays inside the
  // drawing: a town's overflows sit round a spot, and a label over them hides the marks that matter most.
  // Below or above, the label is moved along to stay inside the edges.
  const mid = Math.min(Math.max(sx, 40), width - 40) - sx;
  const sides = [[15, -5, 29, 4, 'start', sx + 6, sx + 96], [-25, -5, -29, 4, 'end', sx - 96, sx - 6],
    [-5, 16, mid, 44, 'middle', sx + mid - 34, sx + mid + 34], [-5, -26, mid, -32, 'middle', sx + mid - 34, sx + mid + 34]];
  const under = ([, qy, , ty, , a, b]) => L.overflows.filter(([x, y]) => x >= a - 6 && x <= b + 6 && y >= sy + Math.min(qy, ty - 12) - 6 && y <= sy + Math.max(qy + 10, ty) + 6).length
    + (a < 0 || b > width || sy + ty < 14 || sy + ty > L.height - 24 ? 99 : 0);
  const [qx, qy, tx, ty, ta] = sides.reduce((best, s) => (under(s) < under(best) ? s : best));
  // A label for the first bar, inside the drawing.
  const lb = L.ends[0], anchor = p => (p[0] > width - 120 ? 'end' : p[0] < 120 ? 'start' : 'middle');
  const label = lb ? `<text x="${f(lb[0])}" y="${f(Math.max(14, lb[1] - 10))}" text-anchor="${anchor(lb)}" class="em-lab">trace stops, ${m.cap} km</text>` : '';
  const km = [1, 2, 5, 10, 20, 50].find(k => k * L.s >= 50) || 50, by = L.height - 10;
  return `<svg class="em-svg" viewBox="0 0 ${width} ${L.height}" width="${width}" height="${L.height}" role="img" aria-labelledby="em-cap">`
    + `<title id="em-cap">${evmapEsc(m.cover.head.replace(/&nbsp;/g, ' '))} The rivers traced upstream of the spot and the overflows on them; every mark is described in words below the drawing.</title>`
    + rivers + bars + `<circle cx="${f(sx)}" cy="${f(sy)}" r="2.5" class="em-spotdot"/>` + marks
    + `<circle cx="${f(sx)}" cy="${f(sy)}" r="12" class="em-spot"/>`   // open: an overflow at the spot shows inside the ring
    + `<rect x="${f(sx + qx)}" y="${f(sy + qy)}" width="10" height="10" class="${sq}"/>`
    + `<text x="${f(sx + tx)}" y="${f(sy + ty)}" text-anchor="${ta}" class="em-lab em-lab-spot">this spot</text>`
    + label
    + `<path d="M12 ${by}H${f(12 + km * L.s)}" class="em-scale"/><text x="${f(16 + km * L.s)}" y="${by + 4}" class="em-tick">${km} km</text>`
    + '<circle class="em-sel" r="0" cx="0" cy="0"/></svg>';
}

// One row in words, the one a tap shows: what, its age on the right, what it says, how it stands to the
// spot, and whose it is. The same shape as What the level rests on's rows (.factor).
const evmapRow = (it, n = '') => `<div class="factor em-row" data-em="${evmapEsc(it.id)}"><div class="f-l">${evmapSwatch(it.kind === 'sample' ? (it.gap ? 'nosample' : 'sample') : it.kind === 'gauge' && !it.gap ? 'live' : it.mark)}${it.what}${it.own ? ` <span class="own-name">(${it.own})</span>` : ''}${n}</div>`
  + `<div class="f-v">${it.age || ''}</div><div class="f-d">${it.say}${it.rel ? ` ${it.rel}` : ''}</div>${it.src ? `<div class="f-src">${it.src}.</div>` : ''}</div>`;

// The key: only the marks this spot has, and the river, the spot and its samples, which every spot has.
function evmapKey(m) {
  const have = new Set(m.overflows.map(o => o.mark));
  return `<p class="em-key">${['spill', 'live', 'dark', 'unheld', 'nofeed', 'far'].filter(k => have.has(k)).map(k => `<span>${evmapSwatch(k)}${EVMAP_KEY[k]}</span>`).join('')}`
    + `<span>${evmapSwatch('spot')}this spot</span><span>${evmapSwatch(m.sampled ? 'sample' : 'nosample')}${m.sampled ? 'lab sample held' : 'no lab sample held'}</span>`
    + `<span>${evmapSwatch('river')}river traced; nothing along it measured</span>${m.ends.length ? `<span>${evmapSwatch('limit')}where the trace stops</span>` : ''}</p>`;
}

// The tile. Not folded: it is opened on purpose (?evidence=1), and the line at its top is the answer.
function evmapTile(d, trace, up, nowMs, generatedAt, width = EVMAP_W) {
  if (!d || d.unlisted || d.error) return '';
  const m = evmapModel(d, trace, up, nowMs, generatedAt), E = evmapEv(), c = m.cover;
  const counted = m.overflows.filter(o => o.mark !== 'far').length;
  const readings = m.overflows.filter(o => !o.gap).length;
  const evRows = [...m.overflows.filter(o => !o.gap), ...m.items.filter(i => !i.gap)];
  const gapRows = [...m.overflows.filter(o => o.gap), ...m.items.filter(i => i.gap), ...m.gaps];
  return `<section class="tile em" id="evmap" aria-labelledby="evmap-h"><h2 class="t-lab" id="evmap-h">${(typeof ICON === 'object' && ICON.map) || ''}<span>Where the evidence is</span></h2>`
    + `<p class="em-head">${evmapSwatch(c.mark)}<span><b>${c.head}</b> ${c.said}</span></p>`
    + (generatedAt ? `<p class="t-say em-asof">Readings as at this update, issued ${E.evidenceSince(generatedAt)} (${E.evidenceAge(generatedAt, nowMs).replace(/^Today$/, 'today')}).</p>` : '')
    + (m.lines.length || m.overflows.length ? `<div class="em-draw">${evmapSvg(m, width)}</div>`
      + `<p class="t-say em-pick" aria-live="polite">${counted ? `${readings} of the ${counted} overflow marks are readings; the hollow ones are gaps. ` : ''}Tap a mark, the spot or a river for its source, when it was read and where it is from the spot.</p>`
      + evmapKey(m) : '')
    + `<details class="em-more"><summary>Every mark and gap in words (${evRows.length + gapRows.length})</summary>`
    + (evRows.length ? `<h3 class="em-h3">Readings and records</h3><div class="factors">${evRows.map(r => evmapRow(r)).join('')}</div>` : '')
    + `<h3 class="em-h3">Gaps: what is not known here</h3><div class="factors">${gapRows.map(r => evmapRow(r)).join('')}</div></details>`
    + `<p class="sub">Prototype. Distances and travel times are along the rivers, as the forecast counts them; the drawing is in straight lines. `
    + 'Reported: what the companies\' live feeds said at the last poll before this update. Modelled: the forecast\'s estimate.</p></section>';
}

// A tap or click on the drawing: the nearest mark within reach, or the spot, or a river, shown as its row
// under the drawing. Taps on the same place step through the marks there, nearest first, since a town's
// overflows sit on top of each other. Browser only.
function evmapBind(host, d, trace, up, nowMs, generatedAt, width) {
  const svg = host.querySelector('.em-svg'), pick = host.querySelector('.em-pick');
  if (!svg || !pick) return;
  const m = evmapModel(d, trace, up, nowMs, generatedAt), L = evmapLayout(m, width), sel = svg.querySelector('.em-sel');
  const byId = new Map([...m.items, ...m.gaps, ...m.overflows].map(i => [i.id, i]));
  let last = { key: '', k: 0 };
  const show = (it, x, y, r, more = '') => {
    pick.innerHTML = evmapRow(it, more).replace('class="factor em-row"', 'class="factor em-row em-shown"');
    sel.setAttribute('cx', x.toFixed(1)); sel.setAttribute('cy', y.toFixed(1)); sel.setAttribute('r', String(r));
  };
  svg.addEventListener('click', e => {
    const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse()), reach = 18;
    const near = m.overflows.map((o, i) => [Math.hypot(L.overflows[i][0] - p.x, L.overflows[i][1] - p.y), o, L.overflows[i]])
      .filter(([dd]) => dd <= reach).sort((a, b) => a[0] - b[0]);
    const ds = Math.hypot(L.spot[0] - p.x, L.spot[1] - p.y);
    if (ds <= reach && (!near.length || ds < near[0][0])) {
      const s = byId.get('sample'); if (s) return show(s, L.spot[0], L.spot[1], 12);
    }
    if (near.length) {
      const key = near.map(n => n[1].id).join('|'), k = last.key === key ? (last.k + 1) % near.length : 0;
      last = { key, k };
      const [, o, q] = near[k];
      return show(o, q[0], q[1], evmapR(o.weight) + 5, near.length > 1 ? ` <span class="em-n">(${k + 1} of ${near.length} here: tap again for the next)</span>` : '');
    }
    const end = L.ends.findIndex(q => Math.hypot(q[0] - p.x, q[1] - p.y) <= reach);
    if (end >= 0 && byId.get('limit')) return show(byId.get('limit'), L.ends[end][0], L.ends[end][1], 10);
    // A river: the nearest stretch within reach.
    const seg = (a, b) => { const vx = b[0] - a[0], vy = b[1] - a[1], t = Math.max(0, Math.min(1, ((p.x - a[0]) * vx + (p.y - a[1]) * vy) / (vx * vx + vy * vy || 1)));
      return Math.hypot(a[0] + t * vx - p.x, a[1] + t * vy - p.y); };
    if (byId.get('river') && L.lines.some(l => l.some((q, i) => i && seg(l[i - 1], q) <= 10))) return show(byId.get('river'), p.x, p.y, 8);
  });
}

// The page's styles for the tile, added once when it is first shown: only tokens (docs/DESIGN.md, Rules).
const EVMAP_CSS = `
.em-head { display:flex; gap:8px; align-items:flex-start; margin:10px 0 0; font-size:var(--fs-note); line-height:1.45; }
.em-head .em-sw { flex:none; margin-top:2px; }
.em-draw { margin:10px 0 0; }
.em-svg { display:block; max-width:100%; height:auto; font-family:var(--font-text); cursor:pointer; -webkit-tap-highlight-color:transparent; }
.em-river { fill:none; stroke:var(--rain); stroke-width:1.5; stroke-opacity:.55; stroke-linejoin:round; stroke-linecap:round; }
.em-limit { fill:none; stroke:var(--ink); stroke-width:2; stroke-linecap:round; }
.em-live { fill:var(--ov-quiet); stroke:var(--card); stroke-width:1; }
.em-spill { fill:var(--veryhigh); stroke:var(--card); stroke-width:1; }
.em-ring { fill:none; stroke:var(--veryhigh); stroke-width:1.5; }
.em-open { fill:var(--card); stroke:var(--ink); stroke-width:1.75; }
.em-dash { stroke-dasharray:3 2; }
.em-strike { stroke:var(--ink); stroke-width:1.75; stroke-linecap:round; }
.em-dot { fill:var(--ink); }
.em-spot { fill:none; stroke:var(--brand); stroke-width:2.5; }
.em-spotdot { fill:var(--brand); }
.em-sel { fill:none; stroke:var(--ink); stroke-width:2; }
.em-lab { font-size:var(--fs-meta); fill:var(--ink); paint-order:stroke; stroke:var(--card); stroke-width:3px; stroke-linejoin:round; }
.em-lab-spot { font-weight:600; }
.em-scale { stroke:var(--muted); stroke-width:1.5; }
.em-tick { font-size:var(--fs-meta); fill:var(--muted); }
.em-sw { display:inline-block; vertical-align:-4px; margin-right:4px; }
.em-key { display:flex; flex-wrap:wrap; gap:4px 14px; margin:8px 0 0; font-size:var(--fs-meta); color:var(--muted); }
.em-pick { min-height:44px; }
.em-pick .factor { border-top:1px solid var(--hair); }
.em-n { font-weight:400; color:var(--muted); }
.em-more { margin:10px 0 0; }
.em-more > summary { cursor:pointer; font-weight:600; font-size:var(--fs-note); min-height:44px; display:flex; align-items:center; }
.em-more > summary:focus-visible { outline:2px solid var(--focus); outline-offset:2px; border-radius:var(--radius-ring); }
.em-h3 { font:600 var(--fs-note)/1.3 var(--font-text); margin:12px 0 0; }
.em .f-l { color:var(--ink); }
.em .sub { margin:10px 0 0; font-size:var(--fs-meta); }
`;
function evmapStyle(doc) {
  if (!doc || doc.getElementById('em-style')) return;
  const s = doc.createElement('style');
  s.id = 'em-style';
  s.textContent = EVMAP_CSS;
  doc.head.appendChild(s);
}

if (typeof module === 'object' && module.exports) {
  module.exports = { evmapDecode, evmapEnds, evmapMark, evmapOthers, evmapRel, evmapOverflow, evmapCoverage, evmapModel, evmapLayout, evmapSvg,
    evmapShape, evmapSwatch, evmapKey, evmapRow, evmapTile, evmapStyle, EVMAP_CSS, EVMAP_KEY, EVMAP_CUT, EVMAP_FEED_H };
}
