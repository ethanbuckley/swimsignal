// Evidence map (prototype, docs/EVIDENCE-MAP-2026-10.md): where a spot's forecast has evidence upstream,
// and where its knowledge ends. Shown only with ?evidence=1 in the address (index.html, mountEvMap), so
// the page is unchanged without it. The live status in words above the level (levels.js, liveLine) is not
// behind the flag: this is the drawing of it.
//
// The task it answers: "Before I go, show me where SwimSignal's forecast for this spot has evidence, and
// where its knowledge ends." The test it must pass: a reader shown a poorly covered spot does not take the
// water to be fine because the drawing looks empty or calm. So:
//   - "no live status" and "a live status that shows no spill" are told apart in words and in marks, never
//     by colour alone: a filled mark is a status reported at the last poll, a hollow one a gap, and the
//     line at the top of the tile leads with the counts;
//   - every mark, tapped or reached from the keyboard, says whose it is, when it was reported and how old
//     that is, and how it stands to the spot ("25.7 km upstream along the rivers; modelled travel time
//     about 36 h, at the model's assumed 0.2 m/s");
//   - gaps are drawn, not left out: overflows with no live feed, with no current status, or whose status
//     this update's file does not give; where the trace stops at 60 km up a river that goes on; the rivers
//     between the marks, along which nothing is measured; a spot with no lab samples.
// Nothing here says a spill caused anything at the spot, and an overflow's model weight is never given as
// the share of a spill that arrives: the weight folds in the model's travel and dilution assumptions, and
// is not a measured fraction of anything.
//
// Its data, all from the build (review of PR #463, 30 Oct 2026: nothing reconstructed in the page): the spot
// (spots-lite.json with data/spot/<id>.json: `now`'s counts, the ten `contributors`, river_state with the
// gauge's place, station_lat and station_lon), its trace (data/spot/<id>-trace.json, build_site.write_traces:
// the rivers as encoded lines and `cut_ends`, where the 60 km cap stops a river, trace.cut_ends) and every
// overflow upstream (data/upstream/<id>.json, build_site.write_upstream: with each one's status, data_state
// and feed time). A field an older file does not have is drawn and said as not known.
//
// A plain script, like replay.js: in the page its names are globals (each begins evmap or EVMAP), and in
// Node the last lines export them (tests/site_evmap.test.cjs). The rows under the drawing are the full
// text; the drawing repeats them for the eye, and a tap or an arrow key on it shows one row.

const EVMAP_FEED_H = 6;   // ingest.live.FEED_CURRENT_H: a status from a feed older than this is not current
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
const EVMAP_POLL = 'at the last poll before this update';

// An encoded polyline (trace.py, encode) as [lat, lon] points (index.html's decodeLine, under a name of its own).
function evmapDecode(str) {
  const pts = []; let i = 0, lat = 0, lon = 0;
  const next = () => { let shift = 0, res = 0, b; do { b = str.charCodeAt(i++) - 63; res |= (b & 31) << shift; shift += 5; } while (b >= 32); return res & 1 ? ~(res >> 1) : res >> 1; };
  while (i < str.length) { lat += next(); lon += next(); pts.push([lat / 1e5, lon / 1e5]); }
  return pts;
}
// Kilometres east and north of the spot: flat, which is near enough within 60 km for a drawing.
const evmapProj = (lat0, lon0) => { const k = Math.cos(lat0 * Math.PI / 180) * 111.32;
  return (lat, lon) => [(lon - lon0) * k, (lat - lat0) * 110.57]; };

// An overflow's status as forecast.live_counts counts it: discharging (or running when its company's feed
// last answered), a spill lately whose water the model still counts (now_contribution, the ten listed only),
// or a current "not discharging".
const evmapRunning = c => c.status === 1 || (c.status === -3 && c.last_status === 1);
const evmapRecent = c => !evmapRunning(c) && c.status !== -3 && Number(c.now_contribution) > 0;
const evmapFar = (o, d) => ((d.upstream_summary || {}).too_far || 0) > 0 && Math.round((Number(o.weight) || 0) * 100) === 0;

// The mark of one overflow, and so how it is drawn, from its own status (the ten listed in the spot's file,
// or its row in the upstream file):
//   spill    a spill reported running, or lately and still counted (filled, ringed)
//   live     a current "not discharging" (filled)
//   dark     in a live feed, but no current status: offline, a stale feed, a feed down, or a status now
//            over EVMAP_FEED_H old where the page is read (hollow, struck through)
//   nofeed   not in any live feed SwimSignal reads (hollow, dashed)
//   unheld   a row with no data_state (a file from before the build gave one): not known (hollow, a dot inside)
//   far      upstream, but too little of its water reaches here to count (small, hollow)
function evmapMark(c, nowMs) {
  if (c.has_live === false || c.data_state === 'no_feed' || c.status === -2) return 'nofeed';
  if (c.data_state === undefined || c.data_state === null) return evmapRunning(c) ? 'spill' : 'unheld';
  if (evmapRunning(c) || evmapRecent(c)) return 'spill';
  if (c.data_state === 'live' && c.status === 0) return nowMs - evmapMs(c.feed_updated_at) > EVMAP_FEED_H * 36e5 ? 'dark' : 'live';
  return 'dark';
}

// Where an overflow is from the spot, along the water, and the model's travel time, labelled as modelled.
function evmapRel(o, a = {}) {
  if (o.distance_km === null || o.distance_km === undefined) return '';
  const km = Number(o.distance_km) || 0, lake = Number(o.lake_distance_km) || 0, h = Number(o.travel_h);
  if (km + lake < 0.1) return 'At the spot.';
  const v = a.river_velocity_ms ?? 0.2, lv = a.lake_velocity_ms ?? 0.05;
  const when = !Number.isFinite(h) ? '' : h < 1 ? 'under an hour' : `about ${Math.round(h)}&nbsp;h`;
  const speed = lake > 0 ? `the model's assumed ${v}&nbsp;m/s in rivers and ${lv}&nbsp;m/s in lakes` : `the model's assumed ${v}&nbsp;m/s`;
  return `${evmapKm(km + lake)} upstream along the ${lake > 0 ? `water, ${evmapKm(lake)} of it across a lake` : 'rivers'}.`
    + (when ? ` Modelled travel time to the spot: ${when}, at ${speed}.` : '');
}

// What one overflow's mark says, as a row: what, when (at), what was reported (say), whose (src), and
// where it is from the spot (rel). `c` is its entry among the ten listed, where it is one; `o` its row in
// the upstream file (or the trace's [id, lat, lon] where that file did not load).
function evmapOverflow(o, c, d, nowMs) {
  const E = evmapEv(), x = { ...o, ...(c || {}) }, co = evmapCompany(x.company || ''), nm = evmapNames(x);
  const bare = !c && typeof o.has_live !== 'boolean';   // the trace's position and nothing else
  const mark = bare ? 'unheld' : evmapFar(x, d) ? 'far' : evmapMark(x, nowMs);
  const feed = co ? `${evmapOwn(co)} live feed, via the National Storm Overflow Hub` : 'Its company\'s live feed';
  const returns = "The Environment Agency's annual returns, for its place and past spills";
  const lately = x.latest_event_end && nowMs - evmapMs(x.latest_event_end) < 7 * 864e5 ? ` Its last reported spill ended ${E.evidenceSince(x.latest_event_end)}.` : '';
  let at = x.feed_updated_at || null, say, src = feed;
  if (bare) { say = 'Counted by the forecast; this page could not load its details, so its status is not shown.'; src = "SwimSignal's trace"; at = null; }
  else if (mark === 'far') { say = 'Upstream, but its model weight here is too small to count.'; src = returns; at = null; }
  else if (mark === 'nofeed') {
    const none = x.data_state === 'no_feed' || ((d.contributors || []).find(k => k.company === x.company) || {}).data_state === 'no_feed';
    say = `No live status: ${none ? `${co} has no live feed SwimSignal reads` : x.has_live === false && !x.data_state ? 'it is not in any live feed SwimSignal reads' : `it is not in ${evmapOwn(co)} live feed`}. `
      + 'The model estimates its spills from the rain forecast and its past spills.';
    src = `${returns}. No live feed`; at = null;
  } else if (mark === 'unheld') {
    say = 'In a live feed, but this update\'s file does not give its status, so it is not known here.'; at = null;
  } else if (mark === 'spill') say = evmapRunning(x)
    ? (x.status === 1 ? `Reported discharging ${EVMAP_POLL}${x.latest_event_start ? `, since ${E.evidenceSince(x.latest_event_start)}` : ''}.`
      : `Reported discharging when ${evmapOwn(co)} feed last answered; it has not answered since.`)
    : `Reported not discharging ${EVMAP_POLL}, after a spill${x.latest_event_end ? ` that ended ${E.evidenceSince(x.latest_event_end)}` : ' lately'}. The model still counts that spill's water here.`;
  else if (mark === 'live') say = `Reported not discharging ${EVMAP_POLL}.${lately}`;
  else say = (x.data_state === 'live' && x.status === 0 ? `Reported not discharging ${EVMAP_POLL}, but that status is now over ${EVMAP_FEED_H} hours old, so it is not current.`
      : x.data_state === 'stale' ? `No current status: ${evmapOwn(co)} feed had not updated within ${EVMAP_FEED_H} hours of the last poll, so its last status may be out of date.`
      : x.status === -3 ? `No current status: ${evmapOwn(co)} feed did not answer the last poll.`
      : 'No current status: the monitor was offline at the last poll.') + lately;
  return { id: String(x.site_id), kind: 'overflow', mark, lat: Number(o.lat ?? x.lat), lon: Number(o.lon ?? x.lon), weight: Number(x.weight) || 0,
    km: (Number(x.distance_km) || 0) + (Number(x.lake_distance_km) || 0),
    what: evmapEsc(nm.plain), own: nm.own ? evmapEsc(nm.own) : '', say, src, at,
    age: at ? E.evidenceAge(at, nowMs) : 'No status', rel: evmapRel(x, d.assumptions || {}), gap: !['live', 'spill'].includes(mark) };
}

// The line at the top of the tile: the counts first, then what they reported. The head's mark and words tell
// a spot with no live status from one whose statuses show no spill. Whether the reporting ones cover most of
// what the model weighs here is the page's own rule (levels.js, nowWatched and NOW_WATCHED_SHARE); the share
// itself is in the notes under the drawing, with what it is.
function evmapCoverage(d) {
  const n = d.now || {}, total = (d.upstream_summary || {}).overflows || 0, cap = (d.assumptions || {}).max_upstream_km ?? 60;
  if (!total) return { kind: 'none', mark: 'nofeed', head: 'No monitored overflow upstream.',
    said: `None was found on the rivers traced ${cap}&nbsp;km upstream, so there is no live status to give. `
      + 'An empty drawing does not mean nothing reaches the water: farms, wildlife and unmonitored sources are not modelled.' };
  const mon = Math.min(total, n.monitored_upstream || 0), w = Number(n.upstream_weight), share = w > 0 ? Math.min(1, (Number(n.monitored_weight) || 0) / w) : (mon / total);
  const cos = [...new Set(((d.upstream_summary || {}).companies || []).map(evmapCompany))];
  const dis = Math.min(mon, n.discharging_upstream || 0), rec = n.recent_upstream || 0, rest = total - mon;
  if (!mon) return { kind: 'little', mark: 'nofeed', head: 'Live sewage spill status unavailable.',
    said: `None of the ${total} overflows upstream reported a status${(n.no_feed_upstream || 0) >= total && cos.length === 1 ? `: ${cos[0]} has no live feed SwimSignal reads` : ''}. `
      + 'The level above is the model\'s estimate from the rain forecast and each overflow\'s past spills, not a reading. A quiet drawing here means not known.' };
  const shows = `${EVMAP_POLL[0].toUpperCase()}${EVMAP_POLL.slice(1)}: ${dis ? `${dis} discharging` : 'none discharging'}${rec ? `; ${rec} not discharging after a spill lately whose water the model still counts` : ''}.`
    + (rest ? ` ${rest} gave no current status, so could be spilling unseen.` : '');
  if (share < 0.5) return { kind: 'little', mark: 'dark', head: `Little live evidence: status from ${mon} of ${total} overflows upstream.`,
    said: `${shows} The overflows the model weighs most for this spot are among those with none, so the level above is mostly the model's estimate.` };
  return { kind: 'most', mark: dis || rec ? 'spill' : 'live', head: mon < total ? `Live status from ${mon} of ${total} overflows upstream.` : `Live status from all ${total} overflows upstream.`, said: shows };
}

// Everything the tile shows: the overflows, the spot's own evidence and gaps (the rain, the rating, the
// algae, the lab sample, from evidence.js, each with how it stands to the spot), the gauge, where the
// trace stops and the rivers between, and the notes on how the counts are made.
function evmapModel(d, trace, up, nowMs, generatedAt) {
  const E = evmapEv(), a = d.assumptions || {}, cap = a.max_upstream_km ?? (trace && trace.max_upstream_km) ?? 60, v = a.river_velocity_ms ?? 0.2;
  const listed = new Map((d.contributors || []).map(c => [c.site_id, c]));
  const fromTrace = ((trace && trace.overflows) || []).map(([site_id, lat, lon]) => ({ site_id, lat, lon }));
  const rows = up && Array.isArray(up.overflows) && up.overflows.length ? up.overflows : fromTrace.length ? fromTrace : [...listed.values()];
  const ovs = rows.map(o => evmapOverflow(o, listed.get(o.site_id), d, nowMs)).filter(o => Number.isFinite(o.lat) && Number.isFinite(o.lon));
  const sp = (d.location || {}).snapped || d, lat0 = Number(sp.lat), lon0 = Number(sp.lon);
  const lines = ((trace && trace.lines) || []).map(evmapDecode);
  const cuts = trace && Array.isArray(trace.cut_ends) ? trace.cut_ends.filter(p => Array.isArray(p) && p.length === 2).map(([lat, lon]) => ({ lat, lon })) : null;
  const items = [], gaps = [], notes = [];
  // The spot's own evidence, from evidence.js, with where each was read.
  const REL = { 'Rain here': "At the spot's own cell of the weather model. The spills are estimated from the rain at each overflow's cell.",
    'Environment Agency rating': 'For this bathing water, from the samples taken here.',
    'Algae at the last check': 'At this bathing water.', 'Latest lab sample': 'Taken at this bathing water.' };
  const ev = E.evidenceItems(d, nowMs, generatedAt);
  for (const r of ev.rows) if (r.what !== 'Overflows upstream')
    items.push({ id: r.what === 'Latest lab sample' ? 'sample' : r.what, kind: r.what === 'Latest lab sample' ? 'sample' : 'spot', mark: 'live', what: r.what,
      say: r.say, src: r.src, at: r.at || null, age: r.age || '', rel: REL[r.what] || 'At the spot.', gap: false });
  // The gauge, at the place in the EA's own station record where the build gives it.
  const rs = d.river_state, gx = rs && Number.isFinite(rs.station_lat) && Number.isFinite(rs.station_lon) ? { lat: rs.station_lat, lon: rs.station_lon } : null;
  if (rs && rs.station) items.push({ id: 'gauge', kind: 'gauge', mark: rs.stale ? 'dark' : 'live', what: `River level at ${evmapEsc(rs.station)}`, ...(gx || {}),
    say: `${rs.stale ? 'No current reading.' : `${Number(rs.level_m).toFixed(2)}&nbsp;m${rs.label ? `, ${evmapEsc({ low: 'low water', normal: 'its usual level', high: 'high water', 'very high': 'very high water' }[rs.label] || rs.label)}` : ''}.`} A river level, not part of the pollution level.`,
    src: 'The Environment Agency\'s real-time river levels', at: rs.observed_at || null, age: rs.observed_at ? E.evidenceAge(rs.observed_at, nowMs) : 'No reading',
    rel: `${evmapKm(rs.distance_km)} away in a straight line${rs.same_river === false ? ', on a different watercourse' : rs.same_river ? ', on the same river' : ''}.`
      + (gx ? '' : ' Not drawn: this update gives its distance, not its place.'), gap: !!rs.stale });
  else gaps.push({ id: 'gauge', kind: 'gauge', mark: 'nofeed', what: 'No river gauge', say: 'No Environment Agency river gauge with a reading within 15&nbsp;km.', src: '', at: null, age: '', rel: '', gap: true });
  // evidence.js's gaps, each under the name of what is missing.
  const named = g => /lab sample/.test(g) ? 'Lab samples' : /^Runoff|lists agriculture/.test(g) ? 'Runoff from farms' : /algae/i.test(g) ? 'Algae checks'
    : /rating/.test(g) ? 'Environment Agency rating' : /rain/.test(g) ? 'Rain' : /overflow/.test(g) ? 'Overflows upstream' : 'Not known here';
  for (const g of ev.gaps) gaps.push({ id: /lab sample/.test(g) ? 'sample' : `gap${gaps.length}`, kind: /lab sample/.test(g) ? 'sample' : 'spot', mark: 'nofeed',
    what: named(g), say: g, src: '', at: null, age: '', rel: /lab sample/.test(g) ? 'At this spot.' : '', gap: true });
  // Where the trace stops: the build's own cut ends (trace.cut_ends), or, from an older file, not known.
  const reach = `${Math.round(cap * 1000 / v / 3600)}&nbsp;h`;
  if (cuts && cuts.length) gaps.push({ id: 'limit', kind: 'limit', mark: 'limit', what: `Where the trace stops, ${cap}&nbsp;km up the rivers`,
    say: `The forecast follows the rivers ${cap}&nbsp;km upstream and stops. ${cuts.length === 1 ? 'This river goes on' : `These ${cuts.length} rivers go on`} above the bar${cuts.length === 1 ? '' : 's'}; overflows there are not counted, whatever they report.`,
    src: "SwimSignal's trace of OS Open Rivers, cut where the forecast's count stops", at: null, age: '',
    rel: `${cap}&nbsp;km upstream along the rivers. Modelled travel time from there: about ${reach}, at the model's assumed ${v}&nbsp;m/s.`, gap: true });
  else if (cuts) notes.push({ id: 'limit', kind: 'limit', mark: 'river', what: `The ${cap}&nbsp;km limit`, say: `Every river traced reaches its source within ${cap}&nbsp;km upstream, so the limit leaves nothing out here.`,
    src: "SwimSignal's trace of OS Open Rivers", at: null, age: '', rel: '', gap: false });
  else if (lines.length) gaps.push({ id: 'limit', kind: 'limit', mark: 'river', what: `The ${cap}&nbsp;km limit`,
    say: `The forecast follows the rivers ${cap}&nbsp;km upstream. Where it stopped a river that goes on is not in this update's file, so it is not drawn.`,
    src: "SwimSignal's trace of OS Open Rivers", at: null, age: '', rel: '', gap: true });
  if (lines.length) gaps.push({ id: 'river', kind: 'river', mark: 'river', what: 'The rivers traced upstream',
    say: 'Water from these rivers reaches the spot. Nothing along them is measured: only the overflows marked are counted, and farms, wildlife and other sources are not modelled.',
    src: "SwimSignal's trace of OS Open Rivers", at: null, age: '', rel: `Within ${cap}&nbsp;km upstream along the rivers.`, gap: true });
  // How the counts are made, said once.
  const n = d.now || {}, w = Number(n.upstream_weight), total = (d.upstream_summary || {}).overflows || 0;
  if (total && w > 0 && Number.isFinite(Number(n.monitored_weight))) notes.push({ id: 'weight', kind: 'note', mark: 'note', what: "Share of the model's weight reporting",
    say: `The overflows that reported a current status carry ${evmapPct(Math.min(1, Number(n.monitored_weight) / w))} of the model's weight for this spot. `
      + 'Each overflow\'s weight is the model\'s estimate of how much a spill there would count here, from its distance, the modelled travel time and the model\'s dilution assumptions; '
      + 'it is not a measured share of what reaches the water. Larger marks carry more of it.', src: 'SwimSignal\'s model', at: null, age: '', rel: '', gap: false });
  if (total) notes.push({ id: 'polls', kind: 'note', mark: 'note', what: 'What a status is',
    say: `Each status is what the company's feed said ${EVMAP_POLL}, issued ${E.evidenceSince(generatedAt)}, not a continuous reading. `
      + `A "not discharging" from a feed not updated within ${EVMAP_FEED_H} hours counts as no current status, and one that is now over ${EVMAP_FEED_H} hours old is shown as such.`,
    src: 'The water companies\' live feeds, polled by SwimSignal', at: null, age: '', rel: '', gap: false });
  return { spot: { lat: lat0, lon: lon0, name: d.name || '' }, lines, cuts: cuts || [], gauge: gx, overflows: ovs, items, gaps, notes, cover: evmapCoverage(d), cap, generatedAt,
    sampled: items.some(i => i.kind === 'sample') };
}

// The drawing's layout at a width in CSS pixels: every point in pixels, the spot at its place. Kept apart
// from the drawing so a tap can be matched to the nearest mark (evmapBind).
function evmapLayout(m, width = EVMAP_W) {
  const P = evmapProj(m.spot.lat, m.spot.lon), pts = [[0, 0]];
  const lines = m.lines.map(l => l.map(([a, b]) => P(a, b)));
  for (const l of lines) for (const p of l) pts.push(p);
  for (const o of m.overflows) pts.push(P(o.lat, o.lon));
  if (m.gauge) pts.push(P(m.gauge.lat, m.gauge.lon));
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]), pad = 22, top = 8;
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const wk = Math.max(x1 - x0, 2), hk = Math.max(y1 - y0, 2), maxH = Math.max(260, Math.min(560, width * 1.4));
  let s = (width - 2 * pad) / wk;
  if (hk * s + 2 * pad + top + 26 > maxH) s = (maxH - 2 * pad - top - 26) / hk;
  const height = Math.round(Math.max(200, hk * s + 2 * pad + top + 26)), ox = (width - wk * s) / 2, oy = pad + top + (height - 2 * pad - top - 26 - hk * s) / 2;
  const at = ([x, y]) => [ox + (x - x0) * s, oy + (y1 - y) * s];
  return { width, height, s, spot: at([0, 0]), lines: lines.map(l => l.map(at)), gauge: m.gauge ? at(P(m.gauge.lat, m.gauge.lon)) : null,
    overflows: m.overflows.map(o => at(P(o.lat, o.lon))), cuts: m.cuts.map(e => at(P(e.lat, e.lon))) };
}

// A mark's shape: filled for a status reported, hollow for a gap, so that a spot with nothing reporting
// draws as a scatter of open rings, not as an empty or quiet map. Colour only repeats it. The size follows
// the model's weight for the spot (larger: more weight), as the page's Upstream map does.
const evmapR = w => 5.5 + 3.5 * Math.sqrt(Math.max(0, Math.min(1, Number(w) || 0)));
function evmapShape(mark, x, y, r = 5) {
  const c = `cx="${x.toFixed(1)}" cy="${y.toFixed(1)}"`;
  if (mark === 'spill') return `<circle ${c} r="${(r + 3).toFixed(1)}" class="em-ring"/><circle ${c} r="${r.toFixed(1)}" class="em-spill"/>`;
  if (mark === 'live') return `<circle ${c} r="${r.toFixed(1)}" class="em-live"/>`;
  if (mark === 'dark') return `<circle ${c} r="${r.toFixed(1)}" class="em-open"/><path d="M${(x - r * 0.7).toFixed(1)} ${(y + r * 0.7).toFixed(1)}L${(x + r * 0.7).toFixed(1)} ${(y - r * 0.7).toFixed(1)}" class="em-strike"/>`;
  if (mark === 'unheld') return `<circle ${c} r="${r.toFixed(1)}" class="em-open"/><circle ${c} r="1.8" class="em-dot"/>`;
  if (mark === 'far') return `<circle ${c} r="2.5" class="em-open"/>`;
  if (mark === 'gauge') return `<path d="M${x.toFixed(1)} ${(y - 6).toFixed(1)}L${(x + 6).toFixed(1)} ${y.toFixed(1)}L${x.toFixed(1)} ${(y + 6).toFixed(1)}L${(x - 6).toFixed(1)} ${y.toFixed(1)}Z" class="em-gauge"/>`;
  return `<circle ${c} r="${r.toFixed(1)}" class="em-open em-dash"/>`;   // nofeed
}
// The key's words for each mark.
const EVMAP_KEY = {
  spill: 'spill reported at the last poll, or lately',
  live: 'not discharging at the last poll',
  dark: 'in a live feed, no current status',
  unheld: 'status not in this update\'s file',
  nofeed: 'not in any live feed: no status',
  far: 'model weight too small to count',
};
const evmapSwatch = mark => `<svg class="em-sw" viewBox="0 0 22 18" width="22" height="18" aria-hidden="true">${
  mark === 'river' ? '<path d="M1 12C6 4 12 16 21 6" class="em-river"/>'
    : mark === 'limit' ? '<path d="M1 9H13" class="em-river"/><path d="M14 3V15" class="em-limit"/>'
      : mark === 'spot' ? '<circle cx="11" cy="9" r="6" class="em-spot"/><circle cx="11" cy="9" r="2" class="em-spotdot"/>'
        : mark === 'sample' ? '<rect x="6" y="4" width="10" height="10" class="em-live"/>'
          : mark === 'nosample' ? '<rect x="6" y="4" width="10" height="10" class="em-open em-dash"/>'
            : mark === 'note' ? '<path d="M5 9H17" class="em-scale"/>' : evmapShape(mark, 11, 9, 5)}</svg>`;

// The drawing: the traced rivers, a bar where the trace stops, the gauge, the overflows' marks, and the spot,
// ringed, with a square beside it for its lab samples (filled where there is one, dashed where there is
// none). A scale bar, in straight-line km, since the rows give distances along the rivers. Focusable: the
// arrow keys step through the marks (evmapBind).
function evmapSvg(m, width = EVMAP_W) {
  const L = evmapLayout(m, width), f = v => v.toFixed(1);
  const rivers = L.lines.map(l => `<path d="M${l.map(p => `${f(p[0])} ${f(p[1])}`).join('L')}" class="em-river"/>`).join('');
  const bars = L.cuts.map(p => {
    // A short bar across the river's end, at right angles to the stretch that ends there.
    let best = null, dmin = Infinity;
    for (const l of L.lines) for (const [i, j] of [[0, 1], [l.length - 1, l.length - 2]]) if (l.length > 1) {
      const dd = Math.hypot(l[i][0] - p[0], l[i][1] - p[1]); if (dd < dmin) { dmin = dd; best = [l[i], l[j]]; } }
    let dx = 0, dy = 1;
    if (best && dmin < 3) { const [q, a] = best, h = Math.hypot(q[0] - a[0], q[1] - a[1]) || 1; dx = -(q[1] - a[1]) / h; dy = (q[0] - a[0]) / h; }
    return `<path d="M${f(p[0] - 6 * dx)} ${f(p[1] - 6 * dy)}L${f(p[0] + 6 * dx)} ${f(p[1] + 6 * dy)}" class="em-limit"/>`;
  }).join('');
  const order = { far: 0, nofeed: 1, unheld: 2, dark: 3, live: 4, spill: 5 };   // the statuses on top
  const marks = m.overflows.map((o, i) => [o, L.overflows[i]]).sort((a, b) => order[a[0].mark] - order[b[0].mark])
    .map(([o, p]) => evmapShape(o.mark, p[0], p[1], evmapR(o.weight))).join('');
  const gauge = L.gauge ? evmapShape('gauge', L.gauge[0], L.gauge[1]) : '';
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
  // A label for the bar nearest the top, inside the drawing.
  const lb = [...L.cuts].sort((a, b) => a[1] - b[1])[0], anchor = p => (p[0] > width - 120 ? 'end' : p[0] < 120 ? 'start' : 'middle');
  const label = lb ? `<text x="${f(lb[0])}" y="${f(Math.max(14, lb[1] - 10))}" text-anchor="${anchor(lb)}" class="em-lab">trace stops, ${m.cap} km</text>` : '';
  const km = [1, 2, 5, 10, 20, 50].find(k => k * L.s >= 50) || 50, by = L.height - 10;
  return `<svg class="em-svg" viewBox="0 0 ${width} ${L.height}" width="${width}" height="${L.height}" role="img" tabindex="0" aria-labelledby="em-cap" aria-describedby="em-keys">`
    + `<title id="em-cap">${evmapEsc(m.cover.head.replace(/&nbsp;/g, ' '))} The rivers traced upstream of the spot and the overflows on them.</title>`
    + `<desc id="em-keys">Use the arrow keys to step through the marks, nearest the spot first; each is described below the drawing. Every mark is also listed under "Every mark and gap in words".</desc>`
    + rivers + bars + gauge + `<circle cx="${f(sx)}" cy="${f(sy)}" r="2.5" class="em-spotdot"/>` + marks
    + `<circle cx="${f(sx)}" cy="${f(sy)}" r="12" class="em-spot"/>`   // open: an overflow at the spot shows inside the ring
    + `<rect x="${f(sx + qx)}" y="${f(sy + qy)}" width="10" height="10" class="${sq}"/>`
    + `<text x="${f(sx + tx)}" y="${f(sy + ty)}" text-anchor="${ta}" class="em-lab em-lab-spot">this spot</text>`
    + label
    + `<path d="M12 ${by}H${f(12 + km * L.s)}" class="em-scale"/><text x="${f(16 + km * L.s)}" y="${by + 4}" class="em-tick">${km} km</text>`
    + '<circle class="em-sel" r="0" cx="0" cy="0"/></svg>';
}

// One row in words, the one a tap shows: what, its age on the right, what it says, how it stands to the
// spot, and whose it is. The same shape as What the level rests on's rows (.factor).
const evmapRow = (it, n = '') => `<div class="factor em-row" data-em="${evmapEsc(it.id)}"><div class="f-l">${evmapSwatch(it.kind === 'sample' ? (it.gap ? 'nosample' : 'sample') : it.kind === 'gauge' && !it.gap ? 'gauge' : it.mark)}${it.what}${it.own ? ` <span class="own-name">(${it.own})</span>` : ''}${n}</div>`
  + `<div class="f-v">${it.age || ''}</div><div class="f-d">${it.say}${it.rel ? ` ${it.rel}` : ''}</div>${it.src ? `<div class="f-src">${it.src}.</div>` : ''}</div>`;

// The key: only the marks this spot has, and the river, the spot and its samples, which every spot has.
function evmapKey(m) {
  const have = new Set(m.overflows.map(o => o.mark));
  return `<p class="em-key">${['spill', 'live', 'dark', 'unheld', 'nofeed', 'far'].filter(k => have.has(k)).map(k => `<span>${evmapSwatch(k)}${EVMAP_KEY[k]}</span>`).join('')}`
    + `<span>${evmapSwatch('spot')}this spot</span><span>${evmapSwatch(m.sampled ? 'sample' : 'nosample')}${m.sampled ? 'lab sample held' : 'no lab sample held'}</span>`
    + (m.gauge ? `<span>${evmapSwatch('gauge')}river gauge (level only)</span>` : '')
    + `<span>${evmapSwatch('river')}river traced; nothing along it measured</span>${m.cuts.length ? `<span>${evmapSwatch('limit')}where the trace stops</span>` : ''}`
    + '<span>larger mark: more of the model\'s weight</span></p>';
}

// The marks in the order the keyboard steps through them: nearest the spot along the water first.
const evmapOrder = m => m.overflows.map((o, i) => [o, i]).sort((a, b) => a[0].km - b[0].km || a[1] - b[1]);

// The tile. Not folded: it is opened on purpose (?evidence=1), and the line at its top is the answer.
function evmapTile(d, trace, up, nowMs, generatedAt, width = EVMAP_W) {
  if (!d || d.unlisted || d.error) return '';
  const m = evmapModel(d, trace, up, nowMs, generatedAt), E = evmapEv(), c = m.cover;
  const counted = m.overflows.filter(o => o.mark !== 'far').length;
  const reported = m.overflows.filter(o => !o.gap).length;
  const evRows = [...m.overflows.filter(o => !o.gap), ...m.items.filter(i => !i.gap)];
  const gapRows = [...m.overflows.filter(o => o.gap), ...m.items.filter(i => i.gap), ...m.gaps];
  return `<section class="tile em" id="evmap" aria-labelledby="evmap-h"><h2 class="t-lab" id="evmap-h">${(typeof ICON === 'object' && ICON.map) || ''}<span>Where the evidence is</span></h2>`
    + `<p class="em-head">${evmapSwatch(c.mark)}<span><b>${c.head}</b> ${c.said}</span></p>`
    + (generatedAt ? `<p class="t-say em-asof">Statuses as at this update, issued ${E.evidenceSince(generatedAt)} (${E.evidenceAge(generatedAt, nowMs).replace(/^Today$/, 'today')}).</p>` : '')
    + (m.lines.length || m.overflows.length ? `<div class="em-draw">${evmapSvg(m, width)}</div>`
      + `<p class="t-say em-pick" aria-live="polite">${counted ? `${reported} of the ${counted} overflow marks are statuses reported at the last poll; the hollow ones are gaps. ` : ''}Tap a mark, the spot or a river, or use the arrow keys on the drawing, for its source, when it was reported and where it is from the spot.</p>`
      + evmapKey(m) : '')
    + `<details class="em-more"><summary>Every mark and gap in words (${evRows.length + gapRows.length})</summary>`
    + (evRows.length ? `<h3 class="em-h3">Statuses, readings and records</h3><div class="factors">${evRows.map(r => evmapRow(r)).join('')}</div>` : '')
    + `<h3 class="em-h3">Gaps: what is not known here</h3><div class="factors">${gapRows.map(r => evmapRow(r)).join('')}</div>`
    + (m.notes.length ? `<h3 class="em-h3">How these are counted</h3><div class="factors">${m.notes.map(r => evmapRow(r)).join('')}</div>` : '') + '</details>'
    + `<p class="sub">Prototype. Distances are along the rivers, as the forecast counts them; the drawing is in straight lines. `
    + 'Travel times are the model\'s, from its assumed speed. Statuses are what the companies\' live feeds said at the last poll before this update.</p></section>';
}

// A tap or click on the drawing: the nearest mark within reach, or the spot, the gauge or a river, shown as
// its row under the drawing. Taps on the same place step through the marks there, nearest first, since a
// town's overflows sit on top of each other. The arrow keys step through every mark, nearest first (evmapOrder).
// Browser only.
function evmapBind(host, d, trace, up, nowMs, generatedAt, width) {
  const svg = host.querySelector('.em-svg'), pick = host.querySelector('.em-pick');
  if (!svg || !pick) return;
  const m = evmapModel(d, trace, up, nowMs, generatedAt), L = evmapLayout(m, width), sel = svg.querySelector('.em-sel');
  const byId = new Map([...m.items, ...m.gaps, ...m.overflows].map(i => [i.id, i]));
  let last = { key: '', k: 0 }, step = -1;
  const show = (it, x, y, r, more = '') => {
    pick.innerHTML = evmapRow(it, more).replace('class="factor em-row"', 'class="factor em-row em-shown"');
    sel.setAttribute('cx', x.toFixed(1)); sel.setAttribute('cy', y.toFixed(1)); sel.setAttribute('r', String(r));
  };
  const seq = evmapOrder(m);
  svg.addEventListener('keydown', e => {
    const k = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!k || !seq.length) return;
    e.preventDefault();
    step = (step + k + seq.length) % seq.length;
    const [o, i] = seq[step], q = L.overflows[i];
    show(o, q[0], q[1], evmapR(o.weight) + 5, ` <span class="em-n">(${step + 1} of ${seq.length}: arrow keys for the next)</span>`);
  });
  svg.addEventListener('click', e => {
    const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse()), reach = 18;
    const near = m.overflows.map((o, i) => [Math.hypot(L.overflows[i][0] - p.x, L.overflows[i][1] - p.y), o, L.overflows[i]])
      .filter(([dd]) => dd <= reach).sort((a, b) => a[0] - b[0]);
    const ds = Math.hypot(L.spot[0] - p.x, L.spot[1] - p.y);
    if (ds <= reach && (!near.length || ds < near[0][0])) {
      const s = byId.get('sample'); if (s) return show(s, L.spot[0], L.spot[1], 14);
    }
    if (near.length) {
      const key = near.map(n => n[1].id).join('|'), k = last.key === key ? (last.k + 1) % near.length : 0;
      last = { key, k };
      const [, o, q] = near[k];
      return show(o, q[0], q[1], evmapR(o.weight) + 5, near.length > 1 ? ` <span class="em-n">(${k + 1} of ${near.length} here: tap again for the next)</span>` : '');
    }
    if (L.gauge && Math.hypot(L.gauge[0] - p.x, L.gauge[1] - p.y) <= reach && byId.get('gauge')) return show(byId.get('gauge'), L.gauge[0], L.gauge[1], 10);
    const end = L.cuts.findIndex(q => Math.hypot(q[0] - p.x, q[1] - p.y) <= reach);
    if (end >= 0 && byId.get('limit')) return show(byId.get('limit'), L.cuts[end][0], L.cuts[end][1], 10);
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
.em-svg:focus-visible { outline:2px solid var(--focus); outline-offset:2px; border-radius:var(--radius); }
.em-svg:focus:not(:focus-visible) { outline:none; }
.em-river { fill:none; stroke:var(--rain); stroke-width:1.5; stroke-opacity:.55; stroke-linejoin:round; stroke-linecap:round; }
.em-limit { fill:none; stroke:var(--ink); stroke-width:2; stroke-linecap:round; }
.em-live { fill:var(--ov-quiet); stroke:var(--card); stroke-width:1; }
.em-spill { fill:var(--veryhigh); stroke:var(--card); stroke-width:1; }
.em-ring { fill:none; stroke:var(--veryhigh); stroke-width:1.5; }
.em-open { fill:var(--card); stroke:var(--ink); stroke-width:1.75; }
.em-dash { stroke-dasharray:3 2; }
.em-strike { stroke:var(--ink); stroke-width:1.75; stroke-linecap:round; }
.em-dot { fill:var(--ink); }
.em-gauge { fill:var(--card); stroke:var(--rain); stroke-width:2; }
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
  module.exports = { evmapDecode, evmapMark, evmapRel, evmapOverflow, evmapCoverage, evmapModel, evmapLayout, evmapSvg, evmapOrder,
    evmapShape, evmapSwatch, evmapKey, evmapRow, evmapTile, evmapStyle, EVMAP_CSS, EVMAP_KEY, EVMAP_FEED_H };
}
