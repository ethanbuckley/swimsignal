// Click anywhere: a forecast for a point on the map that is not a listed spot, worked out in the
// browser from the files the build publishes under data/anypoint/ (scripts/build_any_point.py says
// what is in each). The steps are the API's, in the same order:
//  - where the click goes (model/transport.py, _locate): inside or within 150 m of a WFD lake, that
//    lake (by its real outline where the 15 m one is too close to call; one with no lake centreline
//    inside takes the centreline nearest the click within 1.5 km, and with none a click on its water
//    is the isolated lake and one on its shore goes on as if it were not there); else the nearest
//    link within 1.5 km, or the nearest lake centreline if it is less than twice as far; a click on
//    a small side channel near a much bigger river is traced as that river (_adopt_main_channel), and
//    then where the channel leaves it, as the build found (_click_at_head; the links file's `arms`);
//  - each upstream overflow's distance and dilution (upstream_overflows), from the link's record
//    for the click's place along it, or from the lake's inlets and the straight line across (in lake
//    distance "water", the shortest way through the lake's water, waterWay); a WFD lake crossed on the
//    way counts as lake, with its lake factor (lake path "lake", crossings), or, in lake path
//    "residence", as a well-mixed lake where it has a residence time (holds);
//  - travel at the river speed (the lake speed across a lake, the survivors' hours in a well-mixed
//    one), die-off 10^(-t / T90) times the share that leaves a well-mixed lake alive, weight =
//    die-off x dilution, less for an overflow placed by proximity alone (transportOf);
//  - each day's spill probability through the lead calibration (forecast.calibrate_by_lead),
//    moved later by the travel time and combined, 1 - prod(1 - p w) (transport.combine_daily),
//    with no figure where over 10% of the weight has no rain data (missing_share);
//  - right now from the live status (live_now_risk).
// No E. coli estimate: it needs the rain at the spot itself, which only the build fetches, for the
// listed spots. The card is the listed spot's card (index.html, render), marked as unlisted.
// A plain script, as levels.js: one global, AnyPoint; in Node the last lines export it.
const AnyPoint = (() => {
  const BASE = 'data/anypoint/';
  const FORMS = ['inlandRiver', 'tidalRiver', 'lake', 'canal'], LAKE = 2, RIVER_FORMS = [0, 1];
  const ADOPT = { radius: 500, min: 5000, ratio: 5 };   // transport.ADOPT_RADIUS_M, ADOPT_MIN_M, ADOPT_RATIO
  const BASE_UNIT = 10, SCALE = 10000, PATH_SCALE = 1e6, ARM_SCALE = 1e4;   // build_any_point.BASE_UNIT_M, DIL_SCALE, PATH_SCALE, ARM_FRAC_SCALE
  const HOLD_SCALE = 1e3, PASS_SCALE = 1e9;                // build_any_point.HOLD_SCALE, PASS_SCALE
  const DAYS_AHEAD = 4, KEEP = 10;                       // forecast_point's days, build_site.KEEP_CONTRIBUTORS
  const RAD = Math.PI / 180, A_ELL = 6378137, E2 = 0.00669438;   // WGS84

  // ------------------------------------------------------------------ the arithmetic
  // transport.history_days: the days before today the grid must start for the longest travel time.
  const historyDays = travel => travel.length ? Math.max(1, Math.ceil(Math.max(...travel) / 24) + 1) : 1;
  // numpy.interp: flat beyond the ends.
  function interp(x, xp, fp) {
    if (Number.isNaN(x)) return NaN;
    if (x <= xp[0]) return fp[0];
    const n = xp.length;
    if (x >= xp[n - 1]) return fp[n - 1];
    let lo = 0, hi = n - 1;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (xp[m] <= x) lo = m; else hi = m; }
    return fp[lo] + (fp[hi] - fp[lo]) * (x - xp[lo]) / (xp[hi] - xp[lo]);
  }
  // forecast._apply: the isotonic knots where fitted, else Platt.
  function calibrate(p, c) {
    if (!c) return p;
    if (c.iso_x) return interp(p, c.iso_x, c.iso_y);
    if (Number.isNaN(p)) return NaN;
    const q = Math.min(Math.max(p, 1e-6), 1 - 1e-6);
    return 1 / (1 + Math.exp(-(c.a + c.b * Math.log(q / (1 - q)))));
  }
  // transport.shift_by_travel: each overflow's days later by its travel time, a fraction split.
  function shiftByTravel(P, travel) {
    return P.map((row, i) => {
      const d = row.length, s = travel[i] / 24, k = Math.floor(s), a = s - k, out = new Array(d).fill(0);
      for (let j = 0; j < d; j++) {
        if (j + k < d) out[j + k] += (1 - a) * row[j];
        if (j + k + 1 < d) out[j + k + 1] += a * row[j];
      }
      return out;
    });
  }
  // transport.combine_daily: 1 - prod(1 - p w), a day with no rain data counting as no spill.
  const FEED_CURRENT_MS = 6 * 3600e3;   // ingest.live.FEED_CURRENT_H
  function combineDaily(P, w, travel, nd) {
    if (!P.length) return new Array(nd).fill(0);
    const eff = shiftByTravel(P.map(row => row.map(x => Number.isNaN(x) ? 0 : x)), travel);
    return eff[0].map((_, j) => 1 - eff.reduce((acc, row, i) => acc * (1 - Math.min(1, Math.max(0, row[j])) * w[i]), 1));
  }
  // transport.missing_share: the share of the weight arriving from days with no rain data.
  function missingShare(avail, w, travel, nd) {
    const tot = w.reduce((a, b) => a + b, 0);
    if (!avail.length || tot <= 0) return new Array(nd).fill(0);
    const miss = shiftByTravel(avail.map(row => row.map(ok => ok ? 0 : 1)), travel);
    return miss[0].map((_, j) => Math.min(1, Math.max(0, miss.reduce((a, row, i) => a + row[j] * w[i], 0) / tot)));
  }
  const riskLabel = r => r < 0.15 ? 'low' : r < 0.4 ? 'moderate' : r < 0.7 ? 'high' : 'very high';   // transport.risk_label
  const r3 = x => Math.round(x * 1000) / 1000, r1 = x => Math.round(x * 10) / 10;

  // WFD lakes crossed on the way (transport.upstream_overflows, lake path "lake"): k = flat triples
  // (overflow index, metres of lake, lake factor in millionths), as build_any_point.encode_record and
  // the lake inlets write them. overflow index -> [metres, factor]; empty from a build without them.
  function crossings(k) {
    const out = new Map();
    for (let j = 0; j + 2 < (k || []).length; j += 3) out.set(k[j], [k[j + 1], k[j + 2] / PATH_SCALE]);
    return out;
  }
  // Lake path "residence": h = flat quadruples (overflow index, metres of lake with a residence time, the
  // survivors' hours in it in thousandths, the share that leaves it alive in billionths). overflow index ->
  // {dres, hold, pass}; those metres are in dlake but travel as the hours, and the share multiplies the die-off.
  function holds(h) {
    const out = new Map();
    for (let j = 0; j + 3 < (h || []).length; j += 4) out.set(h[j], { dres: h[j + 1], hold: h[j + 2] / HOLD_SCALE, pass: h[j + 3] / PASS_SCALE });
    return out;
  }
  const NO_HOLD = { dres: 0, hold: 0, pass: 1 };
  // transport.upstream_overflows' travel time (hours) and die-off for a row at the default speeds in `a`.
  function transportOf(r, a) {
    const moving = (r.dist / a.river_velocity_ms + (r.dlake - (r.dres || 0)) / a.lake_velocity_ms) / 3600;
    return { travel: moving + (r.hold || 0), decay: Math.pow(10, -moving / a.t90_hours) * (r.pass === undefined ? 1 : r.pass) };
  }
  // A link record (links/<t>.json) at a click `frac` along the link: [{i, dist, dlake, dil}], as
  // upstream_overflows gives them (build_any_point.rows_at and Tracer say how). The cap is on the
  // whole distance along the network; a lake crossed on the way then moves its metres from dist to
  // dlake and multiplies the dilution by its factor. `p` is transport.DILUTION_POWER (assumptions.dilution_power):
  // the length ratio, capped at 1, is raised to it before any lake factor.
  function rowsAt(rec, frac, cap, l0, p = 1) {
    const offset = frac * rec.n, shrink = (rec.u + l0) / (rec.u + l0 + offset), out = [], path = crossings(rec.k), mixed = holds(rec.h);
    let i = 0;
    for (let k = 0; k < (rec.o || []).length; k += 3) {
      i += rec.o[k];
      const dist = rec.o[k + 1] * BASE_UNIT + offset, [lake, factor] = path.get(i) || [0, 1];
      if (dist <= cap) out.push({ i, dist: dist - lake, dlake: lake, dil: Math.pow(Math.min(1, rec.o[k + 2] / SCALE * shrink), p) * factor, ...(mixed.get(i) || NO_HOLD) });
    }
    for (let k = 0; k < (rec.s || []).length; k += 2)
      if (rec.s[k + 1] < offset) out.push({ i: rec.s[k], dist: offset - rec.s[k + 1], dlake: 0, dil: Math.pow(Math.min(1, shrink), p) });
    return out;
  }
  // Lake distance "water" (model/lake_water.py, water_distance): the shortest way from an inlet to the
  // click inside the lake's water. water (lake_water/<n>.json, fetched for a click on lake n): its reflex
  // corners, its outline widened by 10 m ("inside", which a straight way must stay in), its outline
  // ("shore"), and per inlet ("ways"): where it enters the water, the metres to there, and the metres on
  // to each corner (-1 where none). A click outside the widened outline first goes to the nearest point of
  // the shore. Returns inlet number -> metres, or null for a lake without water (the straight line, as the API).
  function crossesAny(p, q, rings) {
    const side = (a, b, c) => Math.sign((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]));
    for (const r of rings)
      for (let k = 0; k + 1 < r.length; k++)
        if (side(p, q, r[k]) * side(p, q, r[k + 1]) < 0 && side(r[k], r[k + 1], p) * side(r[k], r[k + 1], q) < 0) return true;
    return false;
  }
  function nearestPoint(rings) {   // the nearest point of the rings to the frame's origin
    let best = { d: Infinity, x: 0, y: 0 };
    for (const r of rings)
      for (let k = 0; k + 1 < r.length; k++) {
        const [x0, y0] = r[k], [x1, y1] = r[k + 1], dx = x1 - x0, dy = y1 - y0, l2 = dx * dx + dy * dy;
        const t = l2 > 0 ? Math.min(1, Math.max(0, -(x0 * dx + y0 * dy) / l2)) : 0, x = x0 + t * dx, y = y0 + t * dy, d = Math.hypot(x, y);
        if (d < best.d) best = { d, x, y };
      }
    return best;
  }
  function waterWay(water, at, xy) {
    if (!water) return null;
    const local = rings => rings.map(r => r.map(([lon, lat]) => xy(lat, lon)));
    const inside = local(water.inside), corners = water.corners.map(([lon, lat]) => xy(lat, lon));
    const inWater = inside.reduce((odd, r, k) => odd !== inRing(at[1], at[0], water.inside[k]), false);
    const near = inWater ? { d: 0, x: 0, y: 0 } : nearestPoint(local(water.shore)), q = [near.x, near.y];
    const seen = corners.map(c => !crossesAny(q, c, inside));
    return j => {
      const w = (water.ways || [])[j];
      if (!w) return null;
      const a = xy(w[1], w[0]);
      if (!crossesAny(a, q, inside)) return w[2] + Math.hypot(a[0] - q[0], a[1] - q[1]) + near.d;
      let best = Infinity;
      corners.forEach((c, k) => {
        const via = w[3 + k];
        if (seen[k] && via >= 0) best = Math.min(best, via + Math.hypot(c[0] - q[0], c[1] - q[1]));
      });
      return Number.isFinite(best) ? best + near.d : null;
    };
  }
  // A lake's inlets (lakes.json) for a click: the distance to the inlet, then the straight line
  // across (or the way through the water, waterWay); a WFD lake's area divides the dilution by
  // 1 + area / 5 km2. Another WFD lake crossed before the inlet moves its metres to the lake distance
  // and multiplies the dilution by its factor. `p` as in rowsAt.
  function lakeRows(lake, at, area, a0, water = null, p = 1) {
    const out = [], xy = frame(at[0], at[1]), div = area ? 1 + area / a0 : 1, way = waterWay(water, at, xy);
    for (const [j, inlet] of lake.inlets.entries()) {
      const [x, y] = xy(inlet.at[1], inlet.at[0]), path = crossings(inlet.k), mixed = holds(inlet.h);
      const across = (way && way(j)) ?? Math.hypot(x, y);
      for (let k = 0; k < inlet.o.length; k += 3) {
        const [crossed, factor] = path.get(inlet.o[k]) || [0, 1];
        out.push({ i: inlet.o[k], dist: inlet.o[k + 1] - crossed, dlake: across + crossed, dil: Math.pow(inlet.o[k + 2] / SCALE, p) / div * factor,
          ...(mixed.get(inlet.o[k]) || NO_HOLD) });
      }
    }
    return out;
  }

  // The forecast for upstream rows, as forecast_point builds it (gauge off, as for the listed
  // spots). od: overflow_days.json; cal: lead_calibration.leads; names: overflow_ids.json, for the
  // overflows that matter most (optional).
  function forecast(rows, od, cal, names = null, nowMs = Date.now()) {
    const a = od.assumptions, low = new Set(od.low), n = rows.length;
    const tr = rows.map(r => transportOf(r, a)), travel = tr.map(t => t.travel);
    const w = rows.map((r, k) => tr[k].decay * r.dil * (low.has(r.i) ? a.low_confidence_factor : 1));
    const hist = historyDays(travel), nd = hist + DAYS_AHEAD + 1, t0 = od.today;
    const P = rows.map(r => Array.from({ length: nd }, (_, j) => {
      const v = od.p[r.i][t0 - hist + j]; return v === null || v === undefined ? NaN : v / od.scale; }));
    const avail = P.map(row => row.map(x => !Number.isNaN(x)));
    const leads = Object.keys(cal || {}).map(Number), kmax = leads.length ? Math.max(...leads) : 0;
    const Pc = leads.length ? P.map(row => row.map((x, j) => calibrate(x, cal[String(Math.min(Math.max(j - hist, 0), kmax))]))) : P;
    const risk = combineDaily(Pc, w, travel, nd), miss = missingShare(avail, w, travel, nd);
    const days = [];
    for (let j = hist; j < nd; j++) {
      const known = !(miss[j] > a.max_missing_share), date = od.days[t0 + j - hist];
      const exp = Pc.reduce((s, row) => s + (Number.isNaN(row[j]) ? 0 : row[j]), 0);
      days.push({ date, risk: known ? r3(risk[j]) : null, label: known ? riskLabel(risk[j]) : 'unknown',
        expected_spilling_overflows: known ? r1(exp) : null,
        data_status: !known ? 'rain unavailable' : miss[j] > 0 ? 'partial' : 'ok', rain_missing_share: r3(miss[j]),
        in_validated_season: [5, 6, 7, 8, 9].includes(Number(date.slice(5, 7))) });
    }
    // Right now: transport.live_now_risk, and forecast.live_counts with ingest.live.data_states. A spill
    // counts in full until its water has passed this point (its end, from ended_h, plus the travel time
    // here; a running one's water is still coming), then dies off with T90 for recent_spill_hours. A file
    // from before 4 Oct 2026 has no ended_h: its `live` weights allow no travel time.
    // A spill running when its company's feed last answered counts as running (transport.running,
    // `last_running`), and a record that has stopped updating in a feed that has not is stale with its
    // own last update (ingest.live.frozen_records, `stale_rows`), as forecast.live_counts has them.
    const status = rows.map(r => od.status[r.i]), lastRunning = new Set(od.last_running || []), staleRows = od.stale_rows || {};
    const run = rows.map((r, k) => status[k] === 1 || (status[k] === -3 && lastRunning.has(r.i)));
    const extra = rows.map((r, k) => {
      if (!od.ended_h) return od.live[r.i] / od.scale;
      if (run[k]) return 1;
      const e = od.ended_h[r.i]; if (e === null || e === undefined) return 0;
      const age = e - travel[k];
      return age <= 0 ? 1 : age <= a.recent_spill_hours ? Math.pow(10, -age / a.t90_hours) : 0; });
    // A feed current at the build whose last update is over six hours old where the page is read: its quiet
    // readings are stale too (`feed_updated`), as on a spot's page (index.html, ageReadings). A discharge stays one.
    const fu = od.feed_updated || {}, aged = new Set(Object.keys(fu).filter(c => fu[c] && nowMs - Date.parse(fu[c]) > FEED_CURRENT_MS));
    const company = rows.map(r => od.companies[od.company[r.i]]), noFeed = new Set(od.no_feed || []);
    const staleSince = { ...Object.fromEntries([...aged].map(c => [c, fu[c]])), ...(od.feed_stale_since || {}) };
    const ownStale = rows.map((r, k) => !(company[k] in staleSince) && String(r.i) in staleRows);
    const state = status.map((s, k) => s === 0 || s === 1 ? ((company[k] in staleSince && (s === 0 || !aged.has(company[k]))) || ownStale[k] ? 'stale' : 'live')
      : s === -2 && noFeed.has(company[k]) ? 'no_feed' : 'offline');
    const contrib = rows.map((_, k) => w[k] * extra[k]);
    const nowRisk = 1 - contrib.reduce((acc, c) => acc * (1 - Math.min(1, Math.max(0, c))), 1);
    const down = status.map((s, k) => s === -3 && !run[k]), hasLive = status.map(s => s !== -2);
    const recent = contrib.map((c, k) => c > 0 && !run[k] && status[k] !== -3);
    const quiet = state.map((st, k) => st === 'live' && status[k] === 0 && !recent[k]);
    const stale = state.map((st, k) => st === 'stale' && !run[k] && !recent[k]);
    const monitored = run.filter((x, k) => x || recent[k] || quiet[k]).length, fd = {}, fs = {}, fr = {}, frSince = {};
    rows.forEach((r, k) => {
      if (down[k]) fd[company[k]] = (fd[company[k]] || 0) + 1;
      if (stale[k] && !ownStale[k]) fs[company[k]] = (fs[company[k]] || 0) + 1;
      if (stale[k] && ownStale[k]) { const c = company[k], t = staleRows[String(r.i)];
        fr[c] = (fr[c] || 0) + 1; if (t && (!frSince[c] || Date.parse(t) > Date.parse(frSince[c]))) frSince[c] = t; } });
    const now = { risk: r3(nowRisk), label: riskLabel(nowRisk), discharging_upstream: run.filter(Boolean).length,
      recent_upstream: recent.filter(Boolean).length, monitored_upstream: monitored,
      feed_down_upstream: down.filter(Boolean).length,
      feed_down: Object.keys(fd).sort().map(c => ({ company: c, overflows: fd[c], since: (od.feed_down_since || {})[c] ?? null })),
      stale_upstream: stale.filter(Boolean).length,
      feed_stale: Object.keys(fs).sort().map(c => ({ company: c, overflows: fs[c], since: staleSince[c] ?? null }))
        .concat(Object.keys(fr).sort().map(c => ({ company: c, overflows: fr[c], since: frSince[c] ?? null, records: true }))) };
    // The overflows that matter most: forecast_point's relevance, the build's ten.
    const ahead = Pc.map(row => row.slice(hist, hist + DAYS_AHEAD + 1));
    const order = rows.map((_, k) => k).sort((x, y) => relevance(y) - relevance(x)).slice(0, KEEP);
    function relevance(k) { return Math.max(contrib[k], w[k] * Math.max(0, ...ahead[k].map(x => Number.isNaN(x) ? 0 : x)), 0.1 * w[k]); }
    const contributors = order.map(k => { const r = rows[k], i = r.i, pd = ahead[k];
      return { site_id: names ? names.ids[i] : String(i), site_name: names ? names.name[i] : null, company: od.companies[od.company[i]],
        lat: names ? names.lat[i] : null, lon: names ? names.lon[i] : null, status: status[k], has_live: hasLive[k],
        data_state: state[k], feed_updated_at: state[k] !== 'stale' ? null : ownStale[k] ? staleRows[String(i)] ?? null : staleSince[company[k]] ?? null,
        ...(status[k] === -3 ? { last_status: lastRunning.has(i) ? 1 : null, feed_down_since: (od.feed_down_since || {})[company[k]] ?? null } : {}),
        snap_confidence: low.has(i) ? 'low' : null, distance_km: r1(r.dist / 1000), lake_distance_km: r1(r.dlake / 1000),
        travel_h: r1(travel[k]), weight: r3(w[k]), p_spill_today: r3(Number.isNaN(pd[0]) ? 0 : pd[0]),
        p_spill_tomorrow: r3(Number.isNaN(pd[1]) ? 0 : pd[1]), p_spill_days: pd.map(x => Number.isNaN(x) ? null : r3(x)),
        now_contribution: r3(contrib[k]), rain_h: od.rain_h ? od.rain_h[i] : null }; });
    return { now, days, contributors, upstream_summary: { overflows: n, with_live_feed: monitored, without_live_feed: n - monitored,
      sum_weight: r3(w.reduce((s, x) => s + x, 0)), history_days: hist, max_travel_h: n ? r1(Math.max(...travel)) : 0 },
      // The oldest rain forecast behind a weight that counts, in hours (a cell is fetched on a rota).
      rain_h: Math.max(0, ...rows.map((r, k) => w[k] >= 0.001 && od.rain_h && od.rain_h[r.i] !== null ? od.rain_h[r.i] : 0)) };
  }

  // Rain at a point with no overflow upstream, whose day rows show rain alone (index.html, dayRows): the
  // 48 h to midday on each day from today, from overflow_days.json's rain_48h, which has the build's rain
  // squares (0.1 degrees; those with an overflow in them). The point's own square; else the nearest of
  // the eight around it with a forecast, with how far its centre is (km), since the uplands' squares
  // often have no overflow; else null. A file from before 17 Oct 2026 has none.
  function rainAt(od, lat, lon) {
    const cells = od && od.rain_48h; if (!cells) return null;
    const snap = v => Math.round(v * 10) / 10, key = (a, b) => `${(a + 0).toFixed(1)},${(b + 0).toFixed(1)}`;
    const c = [snap(lat), snap(lon)];
    if (cells[key(...c)]) return { mm: cells[key(...c)], km: 0 };
    let best = null;
    for (const i of [-1, 0, 1]) for (const j of [-1, 0, 1]) {
      const a = snap(c[0] + i / 10), b = snap(c[1] + j / 10), mm = cells[key(a, b)]; if ((!i && !j) || !mm) continue;
      const km = Math.hypot((a - lat) * 111.2, (b - lon) * 111.2 * Math.cos(lat * RAD));
      if (!best || km < best.km) best = { mm, km: Math.round(km) };
    }
    return best;
  }

  // ------------------------------------------------------------------ where a click goes
  // Metres east and north of (lat0, lon0) on a flat local frame, as the British National Grid
  // measures them (the API's distances are grid metres): the ellipsoid's radii of curvature at that
  // latitude, times the grid's scale factor that far from its central meridian (2° W). Within 2 km
  // it is a few centimetres off.
  function frame(lat0, lon0) {
    const s = Math.sin(lat0 * RAD), w = 1 - E2 * s * s, n = A_ELL / Math.sqrt(w), m = A_ELL * (1 - E2) / (w * Math.sqrt(w));
    const east = (lon0 + 2) * RAD * n * Math.cos(lat0 * RAD), k = 0.9996012717 * (1 + east * east / (2 * n * m));
    const ky = m * RAD * k, kx = n * Math.cos(lat0 * RAD) * RAD * k;
    return (lat, lon) => [(lon - lon0) * kx, (lat - lat0) * ky];
  }
  // The nearest point of a line to the frame's origin: distance, and fraction along the line.
  function nearestOnLine(pts) {
    let best = Infinity, along = 0, tot = 0;
    for (let k = 0; k + 1 < pts.length; k++) {
      const [x0, y0] = pts[k], [x1, y1] = pts[k + 1], dx = x1 - x0, dy = y1 - y0, l2 = dx * dx + dy * dy, len = Math.sqrt(l2);
      const t = l2 > 0 ? Math.min(1, Math.max(0, -(x0 * dx + y0 * dy) / l2)) : 0, d = Math.hypot(x0 + t * dx, y0 + t * dy);
      if (d < best) { best = d; along = tot + t * len; }
      tot += len;
    }
    return { d: best, frac: tot > 0 ? along / tot : 0 };
  }
  // link_index/<t>.bin (build_any_point.pack_link_index).
  function decodeIndex(buf) {
    const h = new Int32Array(buf, 0, 6);
    if (h[0] !== 0x494C5353 || h[1] !== 1) throw new Error('unknown link index');
    const n = h[2], nv = h[3], nb = h[4];
    let off = 24;
    const take = (T, cnt) => { const a = new T(buf, off, cnt); off += 4 * cnt; return a; };
    const lno = take(Int32Array, n), meta = take(Int32Array, n), upstream = take(Float32Array, n), offsets = take(Int32Array, n + 1);
    const ll = take(Float32Array, 2 * nv);
    const names = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, off, nb)));
    return { n, lno, meta, upstream, offsets, ll, names };
  }
  // Every link in the squares given, measured from the click: one entry per link number.
  function candidates(lat, lon, tiles) {
    const xy = frame(lat, lon), seen = new Map();
    for (const [key, t] of Object.entries(tiles)) {
      const ix = t.index;
      for (let k = 0; k < ix.n; k++) {
        if (seen.has(ix.lno[k])) continue;
        const pts = [];
        for (let v = ix.offsets[k]; v < ix.offsets[k + 1]; v++) pts.push(xy(ix.ll[2 * v + 1], ix.ll[2 * v]));
        const { d, frac } = nearestOnLine(pts), nm = (ix.meta[k] >> 2) - 1;
        seen.set(ix.lno[k], { lno: ix.lno[k], tile: key, form: ix.meta[k] & 3, name: nm >= 0 ? ix.names[nm] : null, upstream: ix.upstream[k], d, frac });
      }
    }
    return [...seen.values()];
  }
  // Ray casting, and the distance in metres to a polygon's outline.
  function inRing(lon, lat, ring) {
    let inside = false;
    for (let a = 0, b = ring.length - 1; a < ring.length; b = a++) {
      const [xa, ya] = ring[a], [xb, yb] = ring[b];
      if ((ya > lat) !== (yb > lat) && lon < (xb - xa) * (lat - ya) / (yb - ya) + xa) inside = !inside;
    }
    return inside;
  }
  function outlineDistance(lat, lon, poly) {
    const xy = frame(lat, lon);
    return Math.min(...poly.rings.map(r => nearestOnLine(r.map(([x, y]) => xy(y, x))).d));
  }
  function polygonDistance(lat, lon, poly) {
    return poly.rings.some(r => inRing(lon, lat, r)) ? 0 : outlineDistance(lat, lon, poly);
  }
  // The WFD lakes within `reach` metres of a click, give or take each outline's err: [{i, d, e, edge}], d the
  // distance to the outline in lakes.json (simplified to 15 m), 0 inside it, e how far that can be from the
  // real one (0 where `outlines` has the real outline: {place in polygons: lake_outlines/<n>.json}), and
  // edge the distance to the outline from either side.
  function nearLakes(lat, lon, lakes, reach, outlines = {}) {
    const out = [];
    lakes.polygons.forEach((p, i) => {
      const real = outlines[i] && outlines[i].wb_id === p.wb_id ? outlines[i] : null, e = real ? 0 : (p.err || 0);
      const pad = (reach + (p.err || 0)) / 111000, padx = pad / Math.cos(lat * RAD), [w, s, east, n] = p.bbox;   // bbox: of the 15 m outline
      if (lon < w - padx || lon > east + padx || lat < s - pad || lat > n + pad) return;
      const d = polygonDistance(lat, lon, real || p);
      if (d - e <= reach) out.push({ i, d, e, edge: d > 0 ? d : outlineDistance(lat, lon, real || p) });
    });
    return out.sort((a, b) => a.d - b.d);
  }
  // transport._lake_polygon_at: the WFD lake the click is in, or within the shore distance of, by the
  // outlines given (lakes.json's, or the real ones where `outlines` has them).
  function lakePolygon(lat, lon, lakes, shore, outlines = {}) {
    const best = nearLakes(lat, lon, lakes, shore, outlines).find(c => c.d <= shore);
    return best ? { poly: lakes.polygons[best.i], d: best.d, i: best.i } : null;
  }
  // The real outlines (places in polygons) lakePolygon needs for this click: none where the simplified
  // ones settle it, else every lake within the shore distance give or take its err. For a lake with no
  // lake centreline inside (lake -1), whether the click is on its water matters too (place).
  function outlinesNeeded(lat, lon, lakes, shore, outlines = {}) {
    const near = nearLakes(lat, lon, lakes, shore, outlines);
    if (!near.length) return [];
    const [a, ...rest] = near;
    const water = lakes.polygons[a.i].lake === -1 && a.edge <= a.e;
    if (a.d + a.e <= shore && rest.every(b => b.d - b.e > a.d + a.e) && !water) return [];
    return near.filter(c => c.e > 0).map(c => c.i);
  }
  // Whether a click needs the squares' link index: not outside England, nor in a WFD lake with a lake
  // centreline inside (lakes.json has its inlets). A WFD lake with none (lake -1) takes the nearest one.
  const needsSquares = (lat, lon, lakes, cfg, outside, outlines = {}) => {
    if (outsideEngland(lat, lon, outside)) return false;
    const poly = lakePolygon(lat, lon, lakes, cfg.lake_shore_m, outlines);
    return !poly || poly.poly.lake === -1;
  };
  // transport._locate's second step, and _adopt_main_channel: river or lake centreline, and the
  // link a river click is traced along. cands: candidates(); cfg: tiles.json.
  function locate(cands, cfg) {
    const near = (pred, max) => cands.filter(c => pred(c) && c.d <= max).reduce((a, b) => !a || b.d < a.d ? b : a, null);
    const river = near(() => true, cfg.snap_m), lake = near(c => c.form === LAKE, cfg.lake_snap_m);
    if (lake && (!river || river.form === LAKE || lake.d * cfg.lake_bias < river.d)) return { mode: 'lake', link: lake };
    if (!river) return { mode: 'none' };
    let target = river, adopted = false;
    if (river.upstream < ADOPT.min) {
      const alt = cands.filter(c => RIVER_FORMS.includes(c.form) && c.lno !== river.lno && c.d <= ADOPT.radius)
        .reduce((a, b) => !a || b.upstream > a.upstream || (b.upstream === a.upstream && b.d < a.d) ? b : a, null);
      if (alt && alt.upstream >= Math.max(ADOPT.min, ADOPT.ratio * river.upstream)) { target = alt; adopted = true; }
    }
    return { mode: 'river', link: target, adopted, from: river };
  }
  // transport._click_at_head: a click moved from a side arm to a main channel goes where the arm leaves
  // the river of that channel's name. The build worked it out for each arm (build_any_point.arm_heads,
  // encode_arm): rows [link, square (0: the arm's; null: no record), fraction x ARM_SCALE, metres from
  // the arm's head, form, the channels that send a click there by name or link number, and the name
  // where there is no square]. {lno, tile, frac, d, form, name?}, or null where the click stays.
  function armMove(at, tiles) {
    if (!at.adopted || !RIVER_FORMS.includes(at.from.form)) return null;
    const row = (((tiles[at.from.tile] || {}).arms || {})[String(at.from.lno)] || [])
      .find(r => r[5].includes(at.link.lno) || (at.link.name !== null && r[5].includes(at.link.name)));
    if (!row) return null;
    const tile = row[1] === 0 ? at.from.tile : row[1];
    return { lno: row[0], tile, frac: row[2] / ARM_SCALE, d: row[3], form: row[4], name: tile === null ? row[6] : undefined };
  }
  // A link's name as the index of its square gives it.
  function indexName(t, lno) {
    const ix = t.index;
    for (let k = 0; k < ix.n; k++) if (ix.lno[k] === lno) { const nm = (ix.meta[k] >> 2) - 1; return nm >= 0 ? ix.names[nm] : null; }
    return null;
  }

  // ------------------------------------------------------------------ the files
  const tileKey = (lat, lon, deg) => `${Math.floor(lat / deg)}_${Math.floor(lon / deg)}`;
  const memo = new Map();
  const json = (name, fresh = false) => {
    if (fresh) memo.delete(name);
    if (!memo.has(name)) memo.set(name, fetch(BASE + name, { cache: 'no-cache' }).then(r => {
      if (!r.ok) throw new Error(`${name} answered ${r.status}`); return r.json(); }).catch(e => { memo.delete(name); throw e; }));
    return memo.get(name);
  };
  const tile = async (key, cfg) => {
    const name = `tile:${key}`;
    if (!memo.has(name)) memo.set(name, Promise.all([
      fetch(`${BASE}link_index/${key}.bin?n=${cfg.network}`).then(r => { if (!r.ok) throw new Error(`square ${key} answered ${r.status}`); return r.arrayBuffer(); }),
      json(`links/${key}.json`)]).then(([buf, links]) => ({ index: decodeIndex(buf), links: links.links, arms: links.arms || {}, ids: links.ids }))
      .catch(e => { memo.delete(name); throw e; }));
    return memo.get(name);
  };
  // The squares within the snap distance of a click that have files.
  function squares(lat, lon, cfg) {
    const dy = (cfg.snap_m + 100) / 111000, dx = dy / Math.cos(lat * RAD), have = new Set(cfg.tiles), out = new Set();
    for (const a of [lat - dy, lat, lat + dy]) for (const b of [lon - dx, lon, lon + dx]) { const k = tileKey(a, b, cfg.tile_deg); if (have.has(k)) out.add(k); }
    return [...out];
  }

  // Wales, Scotland and the island of Ireland, widened over their tidal rivers and estuaries
  // (outside_england.json, from scripts/make_outside_england.py). The overflow data is the English
  // water companies', so a click there has no forecast, though the squares near the Welsh and
  // Scottish borders have files. Where: '' (England, or a build without the file), 'wales_scotland',
  // 'northern_ireland' or 'republic_of_ireland'. A file from before Ireland was added has no parts:
  // all of it is Wales and Scotland.
  function outsideWhere(lat, lon, shape) {
    if (!shape) return '';
    const i = shape.geometry.coordinates.findIndex(poly => inRing(lon, lat, poly[0]));
    if (i < 0) return '';
    if ((shape.parts || [])[i] !== 'ireland') return 'wales_scotland';
    const ni = shape.northern_ireland;
    return ni && ni.coordinates.some(poly => inRing(lon, lat, poly[0])) ? 'northern_ireland' : 'republic_of_ireland';
  }
  const outsideEngland = (lat, lon, shape) => !!outsideWhere(lat, lon, shape);
  const ENGLAND_ONLY = 'SwimSignal has overflow data for England only, so it has no forecast here.';
  // What a click outside England says, and the official source for bathing waters there, in place of
  // the card's sentence about the Environment Agency, which tests England's (render's check). Nothing
  // about the water itself: SwimSignal knows nothing about it.
  const OUTSIDE = {
    wales_scotland: { error: ENGLAND_ONLY,
      see: 'In Wales and Scotland, Natural Resources Wales and the Scottish Environment Protection Agency publish bathing water results: '
        + 'links to both are on <a href="coverage.html">Coasts, Wales, Scotland, Ireland and algae</a>.' },
    northern_ireland: { error: 'SwimSignal has overflow data for England only, so it has no forecast in Northern Ireland.',
      see: 'The Department of Agriculture, Environment and Rural Affairs (DAERA) publishes results for Northern Ireland\'s bathing waters on its '
        + '<a href="https://www.daera-ni.gov.uk/articles/bathing-water-quality-dashboard" rel="noopener">Bathing Water Quality Dashboard</a>.' },
    republic_of_ireland: { error: 'SwimSignal has overflow data for England only, so it has no forecast in the Republic of Ireland.',
      see: 'The Environmental Protection Agency publishes bathing water results and any swimming restrictions in the Republic at '
        + '<a href="https://www.beaches.ie/" rel="noopener">beaches.ie</a>.' },
  };
  const CHECK_SIGNS = 'A forecast, not a water test: check the signs at the water before you swim.';

  // Where a click goes and the overflows upstream of it, from the files: {mode, kind, name,
  // location, rows} or, where there is no forecast, {error}. files: {cfg: tiles.json, lakes:
  // lakes.json, od: overflow_days.json, tiles: {square: {index, links}}} for the squares near it,
  // and outside: outside_england.json, or null from a build without it.
  // A reservoir can be filled by pumping from a river, which the network does not show.
  const ISOLATED = 'An isolated lake: the river network links no monitored storm overflow to it, '
    + 'so the forecast has nothing to say about it. A reservoir filled by pumping from a river can still take in river water. '
    + 'Risk from wildlife, runoff and bathers is not modelled.';
  function place(lat, lon, files) {
    const { cfg, lakes, od, tiles, outside = null, outlines = {}, waters = {} } = files, a = od.assumptions;
    const where = outsideWhere(lat, lon, outside);
    if (where) return { mode: 'none', kind: '', name: 'This point', error: OUTSIDE[where].error, outside: where };
    const poly = lakePolygon(lat, lon, lakes, cfg.lake_shore_m, outlines);
    // A WFD lake with no lake centreline inside takes the one nearest the click within 1.5 km
    // (transport._in_polygon). With none, a click on its water is the isolated lake, and one on its
    // shore is placed as if the lake were not there (transport._locate).
    const p = poly && poly.poly, link = p && p.lake === -1
      ? candidates(lat, lon, tiles).filter(c => c.form === LAKE && c.d <= cfg.lake_snap_m).reduce((x, y) => !x || y.d < x.d ? y : x, null) : null;
    if (p && p.lake === -1 && !link && poly.d === 0) return { mode: 'isolated', kind: 'lake', name: p.name || 'Unnamed lake', error: ISOLATED,
      location: { mode: 'isolated', watercourse: p.name, lake_area_km2: Math.round(p.area_km2 * 10) / 10, lake_source: 'polygon', form: 'lake' } };
    if (p && (p.lake !== -1 || link)) {
      const entry = link && tiles[link.tile].links[String(link.lno)];
      const lake = !link ? p.lake : entry && entry.lake !== undefined ? entry.lake : null;
      return { mode: 'lake', kind: 'lake', name: p.name || 'Unnamed lake', rows: lake === null ? [] : lakeRows(lakes.lakes[lake], [lat, lon], p.area_km2, a.lake_area_halving_km2, waters[lake], a.dilution_power ?? 1),
        ...(link ? { link } : {}), ...(lake === null ? {} : { lake }),
        location: { mode: 'lake', watercourse: p.name, lake_area_km2: Math.round(p.area_km2 * 10) / 10, lake_source: 'polygon', form: 'lake' } };
    }
    // A square has files where an overflow is, or a link with one upstream. In England, then, no square
    // near means no monitored overflow upstream of any water here; without the shape, ENGLAND_ONLY.
    if (!Object.keys(tiles).length) return { mode: 'none', kind: '', name: 'This point', error: !outside ? ENGLAND_ONLY
      : `No river or lake near this point has a monitored storm overflow within ${a.max_upstream_km} km upstream, so SwimSignal has no sewage spills to forecast here.` };
    const at = locate(candidates(lat, lon, tiles), cfg);
    if (at.mode === 'none') return { mode: 'none', kind: '', name: 'This point', error: 'No river or lake within 1.5 km of this point.' };
    const move = armMove(at, tiles);
    if (move) {
      if (move.tile && !tiles[move.tile]) return { need: [move.tile] };   // the arm's head can be a square away
      if (move.tile) move.name = indexName(tiles[move.tile], move.lno);
      at.link = move;
    }
    const entry = move && !move.tile ? null : tiles[at.link.tile].links[String(at.link.lno)], lake = at.mode === 'lake';
    const rows = !entry ? [] : lake ? (entry.lake === undefined ? [] : lakeRows(lakes.lakes[entry.lake], [lat, lon], null, a.lake_area_halving_km2, waters[entry.lake], a.dilution_power ?? 1))
      : rowsAt(entry, at.link.frac, a.max_upstream_km * 1000, a.l0_m, a.dilution_power ?? 1);
    return { mode: at.mode, kind: at.mode, name: at.link.name || (lake ? 'Unnamed lake' : 'Unnamed watercourse'), rows, link: at.link,
      ...(lake && entry && entry.lake !== undefined ? { lake: entry.lake } : {}),
      location: { mode: at.mode, watercourse: at.link.name, snap_distance_m: Math.round(at.link.d), form: FORMS[at.link.form],
        lake_source: lake ? 'centreline' : null, adopted_main_channel: !!at.adopted } };
  }

  // A point's forecast in the shape of a spot in spots.json, for the page's own card. The files of
  // one build name overflows by the same list; a deploy between two fetches is fetched again once.
  async function point(lat, lon, again = true) {
    const [cfg, lakes, od, outside] = await Promise.all([json('tiles.json'), json('lakes.json'), json('overflow_days.json'),
      json('outside_england.json').catch(() => null)]);
    const outlines = Object.fromEntries(await Promise.all(outlinesNeeded(lat, lon, lakes, cfg.lake_shore_m)
      .map(async i => [i, await json(`lake_outlines/${i}.json`).catch(() => null)])));
    const keys = needsSquares(lat, lon, lakes, cfg, outside, outlines) ? squares(lat, lon, cfg) : [];
    const tiles = Object.fromEntries(await Promise.all(keys.map(async k => [k, await tile(k, cfg)])));
    let at = place(lat, lon, { cfg, lakes, od, tiles, outside, outlines });
    if (at.need) {
      for (const k of at.need) tiles[k] = await tile(k, cfg);
      at = place(lat, lon, { cfg, lakes, od, tiles, outside, outlines });
    }
    // Lake distance "water": the lake's water, only for a click placed on a lake that has one; then place again.
    const water = at.lake !== undefined && (lakes.lakes[at.lake] || {}).water ? await json(`lake_water/${at.lake}.json`).catch(() => null) : null;
    if (water) at = place(lat, lon, { cfg, lakes, od, tiles, outside, outlines, waters: { [at.lake]: water } });
    const rows = at.rows || [];
    const ids = rows.length ? await json('overflow_ids.json') : null;
    const versions = new Set([cfg.ids, od.ids, lakes.ids, ...(water ? [water.ids] : []), ...Object.values(tiles).map(t => t.ids), ...(ids ? [ids.ids_version] : [])]);
    if (versions.size > 1) {
      if (!again) throw new Error('the forecast files changed while loading; try again in a minute');
      memo.clear();
      return point(lat, lon, false);
    }
    const base = { id: `point-${lat.toFixed(5)},${lon.toFixed(5)}`, unlisted: true, lat, lon, source: 'unlisted', name: at.name, kind: at.kind };
    if (at.error) return { ...base, error: at.error, ...(at.outside ? { outside: at.outside } : {}), location: { mode: at.mode },
      days: [], contributors: [], now: { risk: 0, label: 'unknown' } };
    const verif = await fetch('data/verification.json', { cache: 'no-cache' }).then(r => r.ok ? r.json() : {}).catch(() => ({}));
    const cal = ((verif || {}).lead_calibration || {}).leads || {};
    // No rows is the API's answer where no monitored overflow is upstream: every day 0.
    const f = forecast(rows, od, cal, ids);
    // Nothing upstream to spill: the days show the rain, as a listed spot's do.
    const rain = rows.length ? null : rainAt(od, lat, lon);
    if (rain) f.days.forEach((x, k) => { x.rain_48h_mm = rain.mm[k] ?? null; });
    const spot = (typeof DATA !== 'undefined' && DATA && DATA.spots.find(s => s.assumptions)) || {};
    const a = od.assumptions;
    return { ...base, location: at.location, ...f, ...(rain && rain.km ? { rain_km: rain.km } : {}),
      assumptions: { river_velocity_ms: a.river_velocity_ms, lake_velocity_ms: a.lake_velocity_ms, t90_hours: a.t90_hours,
        max_upstream_km: a.max_upstream_km, recent_spill_hours: a.recent_spill_hours, lead_calibration: Object.keys(cal).length > 0,
        model: (spot.assumptions || {}).model, version: (spot.assumptions || {}).version } };
  }

  // ------------------------------------------------------------------ the page
  // The spot card (index.html, render) for the point, then what differs for an unlisted point: the
  // mark, no Save, no share or swim log, and the request in their place.
  const REQUEST = 'https://github.com/ethanbuckley/swimsignal/issues/new';
  function request(d) {
    const q = new URLSearchParams({ template: 'spot-request.yml', title: `Spot request: ${d.name}`, name: d.name,
      location: `${d.lat.toFixed(5)}, ${d.lon.toFixed(5)}`, kind: d.kind === 'lake' ? 'lake' : 'river' });
    return `<div class="actions"><a class="btn primary" href="${REQUEST}?${esc(q.toString())}" rel="noopener">Request this as a spot</a></div>`
      + '<p class="small muted below">Opens a request on GitHub with this point\'s position filled in. A listed spot is checked by hand and gets its own rain forecast and E.&nbsp;coli estimate.</p>';
  }
  function show(d, push) {
    current = d; DAY = null; shown = null;
    render(d);
    const box = document.getElementById('result');
    const save = box.querySelector('#save'); if (save) save.remove();
    const kind = box.querySelector('.kind');
    // A point with no forecast has no other tags: without the empty one dropped, the line ended " · ".
    if (kind) kind.innerHTML = ['Unlisted point: not hand-checked', ...kind.innerHTML.split(' · ').filter(t => t && t !== 'Unlisted')].join(' · ');
    // Outside England, the official source there in place of the sentence about the Environment Agency.
    const chk = d.outside && (OUTSIDE[d.outside] || {}).see && box.querySelector('.check');
    if (chk) chk.innerHTML = `${CHECK_SIGNS} ${OUTSIDE[d.outside].see}`;
    const acts = box.querySelector('.actions');
    if (acts) {   // the spot's share, picture and swim-log buttons, and their notes
      let el = acts.nextElementSibling;
      while (el && el.matches('p.below')) { const nx = el.nextElementSibling; el.remove(); el = nx; }
      if (d.error && d.location.mode !== 'isolated') acts.remove(); else acts.outerHTML = request(d);
    }
    // Rain from the square next to this point's: say how far, under the days.
    const rows = d.rain_km && box.querySelector('.drows');
    if (rows) rows.insertAdjacentHTML('afterend', `<p class="t-key">Rain from the forecast for the area next to this point's, about ${d.rain_km}\u00a0km away.</p>`);
    if (d.rain_h >= 2) { const iss = box.querySelector('#answer-words .issued');
      if (iss) iss.insertAdjacentHTML('afterend', `<p class="issued">Uses rain forecasts up to ${d.rain_h} hours older than that</p>`); }
    selLayer.clearLayers();
    L.circleMarker([d.lat, d.lon], { radius: 14, color: RING(), weight: 3, fill: false, interactive: false }).addTo(selLayer);
    // A desktop shows the point in its page's own map tile (index.html, "Where it is" or Upstream): on
    // the point, close in, as a listed spot's is.
    if (!PHONE.matches && document.getElementById('spot-map')) map.setView([d.lat, d.lon], Math.max(map.getZoom(), 13), { animate: false });
    scrollTop();
    if (push) focusHeading();
  }
  const busy = h => { const from = (history.state || {}).from;   // the back link as render names it
    setPanel(`<div class="top-row"><a href="${esc(from === 'saved' ? savedPath() : ROOT.pathname)}" class="back" id="back">`
      + `${from === 'saved' ? 'Saved spots' : from === 'map' ? 'Map' : 'All spots'}</a></div>${h}`); };
  let ticket = 0;
  async function open(lat, lon, push = true) {
    const mine = ++ticket;
    // A history entry, as opening a spot makes (index.html, select): Back returns to the list, the
    // Saved page or the full map as they were.
    const fromMap = mapMode();
    if (push) {
      keepPlace();
      if (fromMap) { const c = map.getCenter(); history.replaceState({ ...history.state, mapView: [c.lat, c.lng, map.getZoom()] }, ''); }
      history.pushState({ point: [lat, lon], from: fromMap ? 'map' : shown }, '', ROOT.pathname);
    }
    if (fromMap) setMapMode(false);
    busy('<p class="muted" aria-live="polite">Working out the forecast for this point…</p>'); bindBack();
    try {
      const d = await point(lat, lon);
      if (mine === ticket) show(d, push);
    } catch (e) {
      if (mine === ticket) { busy(`<p class="notice">Could not make a forecast for this point: ${esc(e.message)}.</p>`); bindBack(); }
    }
  }
  // A click on the map away from a listed spot. On a phone only the full map takes one: the small
  // maps on a spot's page are for looking. Further out than POINT_ZOOM a pixel is half a kilometre or
  // more and the tiles draw only the big rivers, so a click there zooms in on itself instead, and the
  // line over the map says to tap the water: on the opening view of England a click can land in the
  // sea and answer "Not covered by the forecast".
  const POINT_ZOOM = 9, CLOSER = 2;
  function onMapClick(e) {
    if (typeof DATA === 'undefined' || !DATA || (PHONE.matches && !mapMode())) return;
    const at = map.latLngToContainerPoint(e.latlng);
    for (const s of DATA.spots) if (map.latLngToContainerPoint([s.lat, s.lon]).distanceTo(at) < 14) return;   // the marker's own click opens it
    const say = typeof mapSay === 'function' ? mapSay : () => {};
    if (typeof mapTapped === 'function') mapTapped();   // the first-tap line (index.html) does not come back
    if (map.getZoom() < POINT_ZOOM) {
      map.setView(e.latlng, POINT_ZOOM + CLOSER, typeof MOTION === 'function' ? MOTION() : {});
      say(`Zoomed in. Now ${typeof TOUCH !== 'undefined' && TOUCH ? 'tap' : 'click'} a river or lake for its forecast.`);
      return;
    }
    say('');
    open(e.latlng.lat, e.latlng.lng);
  }

  return { historyDays, interp, calibrate, shiftByTravel, combineDaily, missingShare, riskLabel, rowsAt, lakeRows, transportOf, forecast, rainAt,
    frame, nearestOnLine, waterWay, decodeIndex, candidates, inRing, polygonDistance, outlineDistance, nearLakes, lakePolygon, outlinesNeeded, needsSquares, outsideEngland, outsideWhere, OUTSIDE, locate, place, tileKey, squares, point, open, onMapClick, POINT_ZOOM };
})();

if (typeof window !== 'undefined' && typeof map !== 'undefined') {
  map.on('click', AnyPoint.onMapClick);
  // Forward to a point opened here: the page's own handler draws the list first.
  window.addEventListener('popstate', () => { const p = (history.state || {}).point; if (p && DATA) AnyPoint.open(p[0], p[1], false); });
}
if (typeof module === 'object' && module.exports) module.exports = AnyPoint;
