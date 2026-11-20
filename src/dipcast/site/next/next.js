// SwimSignal, the trial at /next/ (docs/DESIGN.md, "A second site at /next/"): a site about one person's water.
// It opens on one question, "Where do you swim?", and after that it is about that place: when (the five days),
// upstream (the river as a line to move along), the place (what is known at the water) and elsewhere (other places
// on a day). None of the live page's layout code is used. Two files of rules are, loaded before this one, because a
// level or an official notice must never read differently here: ../levels.js (the level, its words, what to do) and
// ../eatoday.js (official advice and its reviewed wording). Only names those two files export are used.
//
// The first half is the model: plain functions over the published data, which tests/site_next.test.cjs runs in Node.
// The second half draws them, and runs only where there is a document.
(function () {
'use strict';

// ------------------------------------------------------------------------------------------------ small helpers
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const capFirst = s => { s = String(s ?? ''); return s.charAt(0).toUpperCase() + s.slice(1); };
const isNil = v => v === null || v === undefined;
const httpsLink = u => /^https:\/\/[^\s"<>]+$/.test(u || '');
const fold = s => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const list = a => a.length <= 1 ? (a[0] || '') : `${a.slice(0, -1).join(', ')} and ${a[a.length - 1]}`;
const dayNm = iso => dayWord(iso).replace(/^on /, '');                       // "today", "tomorrow", "Sunday"
const longDate = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
const shortDate = iso => { const d = new Date(String(iso).length === 10 ? iso + 'T12:00:00' : iso);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', ...(d.getFullYear() === new Date().getFullYear() ? {} : { year: 'numeric' }) }); };
const clock = iso => new Date(iso).toLocaleString('en-GB', { weekday: 'short', hour: '2-digit', minute: '2-digit' });
const feedTime = iso => new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const agoWords = (ms, nowMs) => { const m = Math.max(0, Math.round((nowMs - ms) / 60000));
  return m < 60 ? `${m} min` : m < 48 * 60 ? `${Math.round(m / 60)} h` : `${Math.round(m / 1440)} days`; };
const num = (v, dp = 0) => Number(v).toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });

// ------------------------------------------------------------------------------------------------ distance
const KM_PER_MILE = 1.609344;
function kmBetween(a, b) {
  const R = 6371, rad = x => x * Math.PI / 180, dLat = rad(b.lat - a.lat), dLon = rad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
const COMPASS = ['north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west'];
function compass(a, b) {
  const rad = x => x * Math.PI / 180, y = Math.sin(rad(b.lon - a.lon)) * Math.cos(rad(b.lat));
  const x = Math.cos(rad(a.lat)) * Math.sin(rad(b.lat)) - Math.sin(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.cos(rad(b.lon - a.lon));
  return COMPASS[Math.round(((Math.atan2(y, x) * 180 / Math.PI) + 360) % 360 / 45) % 8];
}
// Straight-line miles, said as such where they show: "6 miles north-west", "under a mile east".
const milesSaid = (km, dir = '') => { const m = km / KM_PER_MILE;
  return `${m < 1 ? 'under a mile' : `${Math.round(m)} mile${Math.round(m) === 1 ? '' : 's'}`}${dir ? ' ' + dir : ''}`; };

// ------------------------------------------------------------------------------------------------ the data, as read
// Readings age where the page is read, as on the live page (index.html, ageReadings): a company's quiet feed whose
// time is over six hours old stops counting as a live "not discharging". Done once per spot.
const FEED_CURRENT_MS = 6 * 3600e3;
function ageSpot(s, nowMs) {
  const n = s.now; if (!n || !Array.isArray(n.quiet_by_feed)) return s;
  n.aged = n.aged || [];
  for (const f of n.quiet_by_feed) { const t = Date.parse(f.updated_at);
    if (!f.updated_at || !(nowMs - t > FEED_CURRENT_MS) || n.aged.includes(f.company)) continue;
    n.aged.push(f.company);
    n.monitored_upstream = Math.max(0, (n.monitored_upstream || 0) - f.overflows);
    if (Number.isFinite(n.monitored_weight) && Number.isFinite(f.weight)) n.monitored_weight = Math.max(0, n.monitored_weight - f.weight);
    n.stale_upstream = (n.stale_upstream || 0) + f.overflows; }
  return s;
}
// The data file made ready: the reader's day (levels.js, readerDay), each spot aged and moved on to that day.
function prepare(data, nowMs) {
  const day = readerDay(data.generated_at, nowMs), built = String(data.generated_at).slice(0, 10);
  setToday(day);
  for (const s of data.spots) { ageSpot(s, nowMs); fromDay(s, day, built); }
  return data;
}
// When the companies' live feeds were last read by the build, in ms; NaN without it. The file writes a space where
// ISO has a T, which Safari's Date.parse refuses.
const polledMs = data => Date.parse(String(((data || {}).build || {}).live_feeds ? data.build.live_feeds.polled_at || '' : '').replace(' ', 'T'));
const pollAt = data => { const t = polledMs(data); return Number.isFinite(t) ? clock(t) : ''; };
// "Issued Fri 12:24, 3 h ago." A forecast over eight hours old is said to be old: builds are a median 4.6 h apart.
const STALE_MS = 8 * 3600e3;
function issuedWords(data, nowMs) {
  const t = Date.parse(data.generated_at);
  if (!Number.isFinite(t)) return { text: 'Issue time not given.', stale: true };
  const stale = nowMs - t > STALE_MS;
  return { text: `Issued ${clock(t)}, ${agoWords(t, nowMs)} ago.`, stale,
    note: stale ? `This forecast is ${agoWords(t, nowMs)} old, older than usual. Levels and live readings may have changed since.` : '' };
}

// ------------------------------------------------------------------------------------------------ official advice
// A reviewed official notice comes before the forecast and is never folded into it (eatoday.js has the rules and
// the words). `restricts`: its reviewer marked it as restricting swimming; only then "advice" and "follow".
function official(s) {
  const items = eaTodayAdvice(s);
  if (!items.length) return null;
  const restricts = eaTodayRestricts(s);
  return { restricts, title: restricts ? 'Official advice' : 'Official notice',
    items: items.map(o => ({ line: o.line, publisher: o.publisher, link: httpsLink(o.link) ? o.link : '', checked: eaTodayChecked(o) })),
    first: `${restricts ? 'Follow this advice first' : 'Read this notice first'}. It is not SwimSignal's, and the forecast below does not include it.`,
    act: eaTodayAct(s), brief: eaTodayBrief(s) };
}

// ------------------------------------------------------------------------------------------------ when: the five days
const levelWords = l => COVER[l] || (ORDER[l] !== undefined ? `${capFirst(l)} risk` : 'No forecast for this day');
const cls = l => ORDER[l] !== undefined ? 'lv-' + l.replace(' ', '') : 'lv-none';
// The rain runs' range on days 3 to 5, where the bar is the spill risk's own (index.html, bandPlace and bandSaid).
function bandFor(s, x, i, r) {
  const b = x.band;
  if (i < 2 || !b || isNil(b.low) || isNil(b.high) || isNil(x.risk) || !(b.high - b.low >= 0.02) || !r.level || r.level !== x.label) return null;
  const a = spillLevel(b.low), z = spillLevel(b.high);
  return { low: b.low, high: b.high, said: `Range from three other Met Office rain runs: ${a === z ? `${a} risk` : `${a} to ${z} risk`}.` };
}
// One row for each day with a forecast: the level (levels.js, risk), what set it, and the sewage spill risk as shown.
function dayRows(s) {
  if (!daily(s)) return [];
  return (s.days || []).slice(0, 5).map((x, i) => { const has = !isNil(x.risk), r = has ? risk(s, x) : { level: null, by: null };
    return { date: x.date, x, r, level: r.level, score: has ? Math.round(x.risk * 100) : null, band: bandFor(s, x, i, r) }; });
}
// The plain "best time" answer over the five days: the days at the lowest level. Never said under official advice
// restricting swimming (the advice comes first), and a water rated poor says why no day is low.
function lowest(s) {
  const rows = dayRows(s).filter(o => o.level);
  if (!rows.length) return null;
  const min = Math.min(...rows.map(o => rank(o.level))), at = rows.filter(o => rank(o.level) === min);
  return { level: at[0].level, dates: at.map(o => o.date), all: at.length === rows.length, n: rows.length };
}
const COUNT = ['', 'one', 'two', 'three', 'four', 'five'];
function lowestWords(s) {
  const o = official(s);
  if (o && o.restricts) return '';
  const b = lowest(s);
  if (!b) return '';
  const poor = s.classification && String(s.classification.class).toLowerCase() === 'poor';
  if (poor && rank(b.level) >= 2) return 'Rated poor, so every day here is at least high risk.';
  if (b.all) return b.n === 1 ? '' : `${capFirst(b.level)} risk on all ${COUNT[b.n] || b.n} days.`;
  return `Lowest of the ${COUNT[b.n] || b.n} days: ${list(b.dates.map(dayNm))}, ${b.level} risk.`;
}
// How many overflows upstream are expected to spill on a day, as a clause (index.html, spilling): under one on a low
// day is a spill that is possible, not expected.
function spillingSaid(x, total, when = '') {
  const e = x.expected_spilling_overflows; if (isNil(e) || !total) return '';
  const k = Math.round(e), w = when ? ' ' + when : '';
  return k >= total ? (total === 1 ? `the overflow upstream is expected to spill${w}` : `all ${total} overflows upstream are expected to spill${w}`)
    : k >= 1 ? `about ${k} of the ${total} overflows upstream ${k === 1 ? 'is' : 'are'} expected to spill${w}`
    : ORDER[x.label] ? `a spill from a nearby overflow upstream is possible${w}`
    : `a spill from ${total === 1 ? 'the overflow' : `one of the ${total} overflows`} upstream is possible${w}, not expected`;
}
// The water temperature estimate, worded by what was measured for its route and nothing more (index.html, waterEstHow).
const WT_ROUTES = new Set(['river_model', 'lake_model', 'lake_curve', 'river_off_season', 'lake_off_season']);
function waterTempSaid(s, iso, nowMs) {
  const w = s.water_temp, e = s.water_temp_est, out = [];
  if (w && typeof w.temp_c === 'number' && w.observed_at && nowMs - Date.parse(w.observed_at) < 24 * 3600e3)
    out.push(`${num(w.temp_c, 1)} °C measured ${w.where || 'nearby'}${isNil(w.river_km) ? '' : `, ${num(w.river_km, 1)} km ${w.direction || 'away'} along the river`}, ${agoWords(Date.parse(w.observed_at), nowMs)} ago.`);
  if (e && typeof e.temp_c === 'number' && e.date === iso && iso === today() && (WT_ROUTES.has(e.route) || (!e.route && s.kind === 'river' && typeof e.within_c === 'number'))) {
    const how = !e.route || e.route === 'river_model' ? `estimated, typically within ${num(e.within_c ?? 2)} °C`
      : e.test === 'winter' && typeof e.typical_c === 'number' ? `provisional estimate; typically within ${num(e.within_c ?? 2)} °C in a test on past winters`
      : e.route.endsWith('_off_season') || typeof e.typical_c !== 'number' ? 'provisional estimate, not yet checked in these months'
      : `provisional estimate; typical error ${num(e.typical_c, 1)} °C at ${e.route.startsWith('river') ? 'rivers' : 'lakes'} in a summer test`;
    out.push(`About ${e.temp_c} °C here (${how}).`);
  }
  return out.join(' ');
}
// The answer for one day at one place: every line the When view shows, in the order it shows them. `iso` is a date
// among the place's days; a place with no daily forecast has one answer for every day.
function answer(s, iso, data, nowMs) {
  const o = official(s), isToday = iso === today(), l = level(s);
  const out = { date: iso, kicker: isToday ? `Today, ${longDate(iso)}` : capFirst(longDate(iso)), lead: '', head: '', sub: '', cls: 'lv-none',
    act: '', live: '', modelled: '', clears: '', score: null, facts: [], notes: [], unchecked: null };
  if (!daily(s)) {
    const [h, why] = headParts(s);
    out.kicker = 'Every day'; out.head = h; out.sub = capFirst(why); out.cls = cls(l);
    out.act = o ? o.act : levelAction(s);
    if (plainLevel(l)) out.notes.push(isolated(s) ? ISOLATED_WHY : 'The trace found no monitored storm overflow on the river network upstream of this place.', OTHER_RISKS);
    else if (COVER[l]) out.notes.push(String(s.error || ''));
  } else {
    const row = dayRows(s).find(d => d.date === iso), r = row ? row.r : { level: null };
    if (!row || !r.level) { out.head = 'No forecast for this day'; out.act = o ? o.act : PLAIN_ACTION; }
    else {
      const spills = spillSet(s, r), cover = liveCover(s), blind = isToday && cover && cover.kind === 'none';
      out.cls = cls(r.level); out.score = row.score;
      out.head = spills ? `${capFirst(r.level)} ${HEAD_SCOPE}` : `${capFirst(r.level)} risk`;
      out.sub = spills ? (r.now ? capFirst(nowBecause(s, r)) : '') : capFirst(r.by === 'record' ? poorReason(iso) : dayBecause(s, r));
      out.act = o ? o.act : dayAction(s, iso);
      if (isToday) {
        out.live = liveLine(s, pollAt(data));
        if (blind || nowUnknown(s)) { out.lead = liveHead(s) || 'Live sewage spill status not known'; out.modelled = MODELLED_FROM + '.'; }
        out.clears = clearWords(s, nowMs);
      }
      const x = row.x, total = (s.upstream_summary || {}).overflows || 0, say = spillingSaid(x, total, dayWord(iso));
      if (say) out.facts.push(['Upstream', `${capFirst(say)}.`]);
      if (row.band) out.facts.push(['Rain runs', row.band.said]);
      if (!isNil(x.rain_48h_mm)) out.facts.push(['Rain', `${num(x.rain_48h_mm, 1)} mm in the 48 hours to midday.${x.rain_missing_share > 0 ? ' Part of the rain data for this day is missing.' : ''}`]);
      else out.facts.push(['Rain', 'No rain figure for this day.']);
      if (ecoliBand(s, x)) out.facts.push(['E. coli', ecoliUntested(x) ? ECOLI_OFF_SAID
        : `${Math.round(x.p_ecoli_gt900 * 100)}% chance a sample would be over 900 E. coli per 100 ml: ${ecoliBand(s, x)} risk. ${riverUsual(x)}`.trim()]);
    }
    out.notes.push(levelScope(s, iso));
    if (walesWords(s)) out.notes.push(walesWords(s));
    if (trialWords(s)) out.notes.push(trialWords(s));
  }
  const w = ((s.weather || {}).days || []).find(d => d.date === iso);
  if (w) out.facts.push(['Daylight', `${w.sunrise} to ${w.sunset}.`], ['Air', `Up to ${w.tmax} °C. Wind ${w.wind_kmh} km/h, gusts ${w.gust_kmh}.`]);
  const wt = waterTempSaid(s, iso, nowMs);
  if (wt) out.facts.push(['Water', wt]);
  // The Environment Agency's own advice for today cannot be read by the build or the page: said, with where to look.
  if (!o && eaUnchecked(s)) out.unchecked = { text: "Today's official advice was not checked.", link: httpsLink((s.classification || {}).url) ? s.classification.url : '', words: 'Check Environment Agency advice' };
  return out;
}

// ------------------------------------------------------------------------------------------------ upstream: the river as a line
const runningAtLastAnswer = c => c.status === -3 && c.last_status === 1;
// An overflow's live status in words (index.html, statusText): a reading from a feed over six hours old says when
// it last updated, never "not discharging".
function statusSaid(c, nowMs) {
  const t = Date.parse(c.feed_updated_at), aged = c.status === 0 && c.data_state === 'live' && Number.isFinite(t) && nowMs - t > FEED_CURRENT_MS;
  if (runningAtLastAnswer(c)) return `discharging when the feed last answered${c.feed_down_since ? `, ${feedTime(c.feed_down_since)}` : ''}`;
  if (aged) return `not discharging at ${feedTime(c.feed_updated_at)}, over six hours ago, so not current`;
  if (c.data_state === 'stale') return c.status === 1 ? `discharging at its last update, ${c.feed_updated_at ? feedTime(c.feed_updated_at) : 'time not given'}`
    : c.feed_updated_at ? `no update since ${feedTime(c.feed_updated_at)}` : 'no update time from the company';
  if (c.status === -2 && c.data_state === 'offline') return 'not in the company’s live feed';
  return ({ 1: 'discharging', 0: 'not discharging', '-1': 'monitor offline', '-2': 'no live feed', '-3': 'company feed down' })[c.status] ?? 'status not given';
}
// How it is drawn: 'spilling', 'quiet' (a current "not discharging") or 'unknown' (everything else: never drawn as dry).
function markOf(c, nowMs) {
  if (c.status === 1 || runningAtLastAnswer(c)) return 'spilling';
  const t = Date.parse(c.feed_updated_at);
  return c.status === 0 && (!c.data_state || c.data_state === 'live') && !(Number.isFinite(t) && nowMs - t > FEED_CURRENT_MS) ? 'quiet' : 'unknown';
}
const hoursSaid = h => h < 36 ? `about ${Math.max(1, Math.round(h))} hour${Math.round(h) <= 1 ? '' : 's'}` : `about ${Math.round(h / 24)} days`;
const alongKm = c => (Number(c.distance_km) || 0) + (Number(c.lake_distance_km) || 0);
// The line: every monitored overflow the trace found, nearest first, and the listed places on the same water as
// waypoints to move to. `up` is data/upstream/<id>.json's list, `detail` data/spot/<id>.json (its ten heaviest
// overflows carry the forecast's chance of a spill); either may be missing, and the line then says what it has.
function riverLine(s, up, detail, spots, nowMs) {
  const extra = new Map(((detail || {}).contributors || []).map(c => [c.site_id, c]));
  const source = Array.isArray(up) && up.length ? up : ((detail || {}).contributors || []);
  const overflowsList = source.map(c => ({ ...c, ...(extra.get(c.site_id) || {}) })).map(c => {
    const nm = overflowNames(c), other = c.receiving_watercourse && c.receiving_watercourse !== '#N/A' && fold(c.receiving_watercourse) !== fold(s.river) ? c.receiving_watercourse : '';
    return { kind: 'overflow', id: String(c.site_id ?? ''), km: alongKm(c), name: nm.plain, own: nm.own, company: companyName(c.company), into: other ? nameCase(other) : '',
      where: overflowWhere(c) + travelSaid(c, hoursSaid), mark: markOf(c, nowMs), status: statusSaid(c, nowMs),
      long: longSpill(c, nowMs) ? LONG_SPILL : '', ended: c.status !== 1 && c.latest_event_end ? shortDate(c.latest_event_end) : '',
      spills: isNil(c.lta_spills) ? null : c.lta_spills, hours: isNil(c.spill_hours) ? null : c.spill_hours, weight: isNil(c.weight) ? null : c.weight,
      chance: Array.isArray(c.p_spill_days) && !isNil(c.p_spill_days[0]) ? c.p_spill_days[0] : null, upgrade: c.upgrade || null };
  });
  const byId = new Map((spots || []).map(p => [p.id, p]));
  const above = (spots || []).filter(p => p.id !== s.id && (p.downstream || []).some(([id]) => id === s.id))
    .map(p => ({ kind: 'place', id: p.id, km: p.downstream.find(([id]) => id === s.id)[1], name: p.name, level: levelWords(dayLevel(p, today())), cls: cls(dayLevel(p, today())) }));
  const below = (s.downstream || []).filter(([id]) => byId.has(id)).map(([id, km]) => { const p = byId.get(id);
    return { id, km, name: p.name, level: levelWords(dayLevel(p, today())), cls: cls(dayLevel(p, today())) }; }).sort((a, b) => a.km - b.km);
  const items = [...overflowsList, ...above].sort((a, b) => a.km - b.km || (a.kind === 'place' ? -1 : 1));
  const withHours = overflowsList.filter(o => o.hours !== null);
  return { items, below, total: overflowsList.length, spilling: overflowsList.filter(o => o.mark === 'spilling').length,
    unknown: overflowsList.filter(o => o.mark === 'unknown').length,
    hours: withHours.length ? { sum: withHours.reduce((a, o) => a + o.hours, 0), of: withHours.length } : null,
    reach: (s.assumptions || {}).max_upstream_km ?? 60, more: tooFarSaid(s) };
}
// The space before an item on the line, in px, from the water between it and the one before: the square root keeps a
// 30 km gap readable beside a 300 m one, and the label on a long gap says how far it is.
const gapPx = km => Math.round(Math.min(120, 10 + 22 * Math.sqrt(Math.max(0, km))));

// ------------------------------------------------------------------------------------------------ elsewhere: other places on a day
// Other listed places from a point, on one day, in four groups that are never mixed: low risk that day (nearest
// first); a higher level that day; under official advice restricting swimming, whatever the level; and places with
// no daily level, which are never "low". Within `miles`, or the nearest few where that leaves almost nothing.
function elsewhere(spots, from, iso, miles = 30, skip = null) {
  const rows = spots.filter(p => p.id !== skip).map(p => { const km = kmBetween(from, p), l = dayLevel(p, iso), o = official(p);
    return { id: p.id, name: p.name, water: p.river || '', km, said: milesSaid(km, compass(from, p)), level: l, words: levelWords(l), cls: cls(l),
      notice: o ? o.brief : '', group: o && o.restricts ? 'advice' : ORDER[l] === undefined ? 'plain' : l === 'low' ? 'low' : 'raised' }; })
    .sort((a, b) => a.km - b.km);
  let near = rows.filter(r => r.km <= miles * KM_PER_MILE), widened = false;
  if (near.length < 4) { near = rows.slice(0, 8); widened = true; }
  const g = k => near.filter(r => r.group === k);
  return { low: g('low'), raised: g('raised').sort((a, b) => rank(a.level) - rank(b.level) || a.km - b.km), advice: g('advice'), plain: g('plain'), widened, miles, n: near.length };
}

// ------------------------------------------------------------------------------------------------ finding a place
function findSpots(spots, q) {
  const words = fold(q).split(/[^a-z0-9']+/).filter(Boolean);
  if (!words.length) return [];
  return spots.filter(p => { const hay = fold(`${p.name} ${p.river || ''} ${p.area || ''}`); return words.every(w => hay.includes(w)); });
}
// A postcode typed in full or in part, as the keys of data/postcodes.json: its sector ("LS29 9") and district ("LS29").
function postcodeKeys(q) {
  const m = /^\s*([A-Za-z]{1,2}\d[A-Za-z\d]?)\s*(\d)?([A-Za-z]{0,2})\s*$/.exec(q || '');
  if (!m) return null;
  const district = m[1].toUpperCase();
  return { district, sector: m[2] ? `${district} ${m[2]}` : null };
}
function findTowns(places, q, max = 2) {
  const f = fold(q).trim();
  if (f.length < 3 || !Array.isArray(places)) return [];
  const hit = places.filter(p => fold(p[0]).startsWith(f));
  return hit.sort((a, b) => (fold(a[0]) === f ? 0 : 1) - (fold(b[0]) === f ? 0 : 1) || a[0].length - b[0].length).slice(0, max).map(p => ({ name: p[0], lat: p[1], lon: p[2] }));
}
function nearest(spots, from, n = 5, iso = null) {
  return spots.map(p => { const km = kmBetween(from, p), l = dayLevel(p, iso || today()), o = official(p);
    return { id: p.id, name: p.name, water: p.river || '', km, said: milesSaid(km, compass(from, p)), words: levelWords(l), cls: cls(l), notice: o ? o.brief : '' }; })
    .sort((a, b) => a.km - b.km).slice(0, n);
}

// ------------------------------------------------------------------------------------------------ the address
// "#/find", "#/<id>", "#/<id>/upstream", "#/<id>/place", "#/<id>/elsewhere", each with an optional "?d=<date>".
const VIEWS = ['when', 'upstream', 'place', 'elsewhere'];
function parseHash(hash) {
  const [path, query = ''] = String(hash || '').replace(/^#\/?/, '').split('?');
  const [id = '', view = ''] = path.split('/'), d = /(?:^|&)d=(\d{4}-\d{2}-\d{2})(?:&|$)/.exec(query);
  if (!id || id === 'find') return { screen: 'find', explicit: id === 'find' };
  return { screen: 'place', id, view: VIEWS.includes(view) ? view : 'when', day: d ? d[1] : null };
}
const hashFor = (id, view = 'when', day = null) => `#/${id}${view && view !== 'when' ? '/' + view : ''}${day ? `?d=${day}` : ''}`;

const api = { esc, kmBetween, compass, milesSaid, ageSpot, prepare, issuedWords, official, levelWords, dayRows, lowest, lowestWords, spillingSaid,
  waterTempSaid, answer, statusSaid, markOf, riverLine, gapPx, elsewhere, findSpots, postcodeKeys, findTowns, nearest, parseHash, hashFor, pollAt };
if (typeof module === 'object' && module.exports) module.exports = api;
if (typeof document === 'undefined') return;

// ================================================================================================ the page
const app = document.getElementById('app');
let DATA = null, PLACES = null, POSTCODES = null, here = null, hereNote = '', query = '', openArea = '', browse = false;
const expanded = new Set(), LINE_FIRST = 12;   // the places whose line upstream is shown whole
const details = new Map();   // id -> { detail, up } once fetched; a failed fetch is kept as null, and said
const now = () => Date.now();

// Your places: ids kept on this device only, the first being the one the site opens on.
const KEY = 'swimsignal.next.places';
const kept = () => { try { const v = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(v) ? v.filter(x => typeof x === 'string') : []; } catch (e) { return []; } };
const keep = ids => { try { localStorage.setItem(KEY, JSON.stringify(ids.slice(0, 8))); } catch (e) { /* private window: the page works without it */ } };
const spotOf = id => DATA.spots.find(p => p.id === id);
const keptSpots = () => kept().map(spotOf).filter(Boolean);

const chipName = iso => { const w = dayNm(iso); return w === 'today' || w === 'tomorrow' ? capFirst(w) : new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'short' }); };
const dot = c => `<i class="dot ${c}" aria-hidden="true"></i>`;
const placeRow = (r, day = null) => `<li><a class="row" href="${hashFor(r.id, 'when', day)}"><span class="row-main"><b>${esc(r.name)}</b>`
  + `<span class="row-sub">${esc([r.said, r.water && !fold(r.name).includes(fold(r.water)) ? r.water : ''].filter(Boolean).join(' · '))}</span>`
  + (r.notice ? `<span class="row-notice">Official: ${esc(r.notice)}</span>` : '')
  + `</span><span class="row-level">${dot(r.cls)}${esc(r.words)}</span></a></li>`;
const rowOf = (p, said = null) => { const l = dayLevel(p, today()), o = official(p);
  return { id: p.id, name: p.name, water: said === null ? p.river || '' : '', said: said === null ? p.area || '' : said, words: levelWords(l), cls: cls(l), notice: o ? o.brief : '' }; };

// -------------------------------------------------------------------------------- the opening
function findScreen() {
  const mine = keptSpots(), n = DATA.spots.length;
  const areas = [...new Set(DATA.spots.map(p => p.area).filter(Boolean))].sort();
  return `<main class="find" id="main">
    <p class="brand"><span>SwimSignal</span> <span class="trial">trial version</span></p>
    <h1 tabindex="-1">Where do you swim?</h1>
    <form class="ask" role="search" onsubmit="return false">
      <label for="q">A river, lake, town or postcode</label>
      <div class="ask-row"><input id="q" type="search" autocomplete="off" autocapitalize="none" spellcheck="false" value="${esc(query)}" enterkeyhint="search">
      <button type="button" class="btn" data-do="locate">Use where I am</button></div>
      <p class="quiet" id="here-note">${esc(hereNote || 'Your location stays in this browser. It is not sent anywhere.')}</p>
    </form>
    <div id="results" aria-live="polite">${resultsHtml()}</div>
    ${mine.length ? `<section class="block"><h2>Your places</h2><ul class="rows">${mine.map(p => placeRow(rowOf(p))).join('')}</ul></section>` : ''}
    <section class="block browse"><button type="button" class="area${browse ? ' is-on' : ''}" data-do="browse" aria-expanded="${browse}">Or pick from ${areas.length} areas <span class="quiet">${n} places</span></button>
      ${browse ? `<ul class="areas">${areas.map(a => `<li><button type="button" class="area${a === openArea ? ' is-on' : ''}" data-do="area" data-area="${esc(a)}" aria-expanded="${a === openArea}">${esc(a)} <span class="quiet">${DATA.spots.filter(p => p.area === a).length}</span></button>`
        + (a === openArea ? `<ul class="rows">${DATA.spots.filter(p => p.area === a).sort((x, y) => x.name.localeCompare(y.name)).map(p => placeRow(rowOf(p, p.river && !fold(p.name).includes(fold(p.river)) ? p.river : ''))).join('')}</ul>` : '') + '</li>').join('')}</ul>` : ''}
    </section>
    <p class="what">Sewage spill risk at ${n} rivers and lakes, for today and the next four days, from live storm overflow readings and the rain forecast. A forecast, not a test of the water. ${esc(issuedWords(DATA, now()).text)}</p>
    ${foot()}
  </main>`;
}
function resultsHtml() {
  const q = query.trim(); let out = '';
  if (here) out += `<section class="block"><h2>Nearest to you</h2><ul class="rows">${nearest(DATA.spots, here, 6).map(r => placeRow(r)).join('')}</ul><p class="quiet">Miles in a straight line. Levels are today's.</p></section>`;
  if (q.length < 2) return out;
  const hits = findSpots(DATA.spots, q).slice(0, 8);
  if (hits.length) out += `<section class="block"><h2>${hits.length === 1 ? 'One place matches' : `${hits.length} places match`}</h2><ul class="rows">${hits.map(p => placeRow(rowOf(p))).join('')}</ul></section>`;
  const pc = postcodeKeys(q); let points = [];
  if (pc && POSTCODES) { const at = (pc.sector && POSTCODES.sectors[pc.sector]) || POSTCODES.districts[pc.district];
    if (at) points.push({ name: pc.sector && POSTCODES.sectors[pc.sector] ? pc.sector : pc.district, lat: at[0], lon: at[1] }); }
  if (!points.length && PLACES) points = findTowns(PLACES.places, q);
  const shown = new Set(hits.map(p => p.id));
  for (const t of points) out += `<section class="block"><h2>Near ${esc(t.name)}</h2><ul class="rows">${nearest(DATA.spots.filter(p => !shown.has(p.id)), t, 5).map(r => placeRow(r)).join('')}</ul><p class="quiet">Miles in a straight line from ${esc(t.name)}. Levels are today's.</p></section>`;
  if (!hits.length && !points.length) out += `<p class="none">${(pc ? POSTCODES : PLACES) ? `Nothing found for “${esc(q)}”. Try a river, a lake, a town or the first half of a postcode.` : 'Looking…'}</p>`;
  return out;
}
const loadJson = async path => { const r = await fetch(path); if (!r.ok) throw new Error(`${path}: ${r.status}`); return r.json(); };
async function typed(v) {
  query = v;
  const box = document.getElementById('results'); if (box) box.innerHTML = resultsHtml();
  if (v.trim().length < 2) return;
  try {
    if (postcodeKeys(v) && !POSTCODES) { POSTCODES = await loadJson('../data/postcodes.json'); }
    else if (!PLACES) { PLACES = await loadJson('../data/places.json'); }
  } catch (e) { PLACES = PLACES || { places: [] }; POSTCODES = POSTCODES || { sectors: {}, districts: {} }; }
  const again = document.getElementById('results'); if (again && query === v) again.innerHTML = resultsHtml();
}
function locate(after) {
  const say = t => { hereNote = t; const n = document.getElementById('here-note'); if (n) n.textContent = t; };
  if (!navigator.geolocation) { say('This browser cannot give a location. Type a town or postcode instead.'); return; }
  say('Asking this browser where you are…');
  navigator.geolocation.getCurrentPosition(p => { here = { lat: p.coords.latitude, lon: p.coords.longitude }; hereNote = 'Using where you are. It stays in this browser.'; after(); },
    () => say('No location was given. Type a town or postcode instead.'), { maximumAge: 600000, timeout: 15000 });
}

// -------------------------------------------------------------------------------- one place
function placeScreen(route) {
  const s = spotOf(route.id);
  if (!s) return `<main class="find" id="main"><p class="brand"><span>SwimSignal</span> <span class="trial">trial version</span></p><h1 tabindex="-1">That place is not listed</h1><p>The address names a place this forecast does not cover, or one that has been removed.</p><p><a class="btn" href="#/find">Find a place</a></p>${foot()}</main>`;
  const rows = dayRows(s), day = rows.some(r => r.date === route.day) ? route.day : rows.length ? rows[0].date : today();
  const mine = kept(), isKept = mine.includes(s.id), others = keptSpots().filter(p => p.id !== s.id);
  const sub = [s.river && !fold(s.name).includes(fold(s.river)) ? s.river : '', s.kind === 'lake' && !/\b(water|mere|tarn|lake|loch|pond|reservoir|llyn)\b/i.test(s.name) ? 'Lake' : '', s.area].filter(Boolean).join(' · ');
  const tab = (v, label) => `<a href="${hashFor(s.id, v, v === 'when' || v === 'elsewhere' ? route.day : null)}"${route.view === v ? ' aria-current="page"' : ''}>${label}</a>`;
  return `<header class="top">
      <p class="brand"><a href="#/find">SwimSignal</a> <span class="trial">trial version</span></p>
      <h1 tabindex="-1">${esc(s.name)}</h1>
      <p class="sub">${esc(sub)}</p>
      <p class="tools"><button type="button" class="link" data-do="keep" aria-pressed="${isKept}">${isKept ? 'Kept as one of your places' : 'Keep as my place'}</button>
        <button type="button" class="link" data-do="share">Share</button> <a class="link" href="#/find">Change place</a></p>
      ${others.length ? `<p class="mine">Your other places: ${others.map(p => `<a href="${hashFor(p.id)}">${dot(cls(dayLevel(p, today())))}${esc(p.name)}<span class="vh">, ${esc(levelWords(dayLevel(p, today())).toLowerCase())} today</span></a>`).join(' ')}</p>` : ''}
    </header>
    <main class="place" id="main" data-view="${route.view}">
      <section class="view v-when" aria-labelledby="h-when">${whenHtml(s, day)}</section>
      <section class="view v-upstream" aria-labelledby="h-upstream">${upstreamHtml(s)}</section>
      <section class="view v-place" aria-labelledby="h-place">${placeHtml(s)}</section>
      <section class="view v-elsewhere" aria-labelledby="h-elsewhere">${elsewhereHtml(s, day)}</section>
    </main>
    ${foot()}
    <nav class="tabs" aria-label="This place">${tab('when', 'When')}${tab('upstream', 'Upstream')}${tab('place', 'The place')}${tab('elsewhere', 'Elsewhere')}</nav>`;
}

function whenHtml(s, day) {
  const a = answer(s, day, DATA, now()), o = official(s), rows = dayRows(s), issued = issuedWords(DATA, now()), best = lowestWords(s);
  const notice = !o ? '' : `<section class="official" aria-labelledby="h-official"><h3 id="h-official">${esc(o.title)}</h3>`
    + o.items.map(i => `<p class="o-line">${esc(i.line)}</p><p class="o-src">${i.link ? `<a href="${esc(i.link)}">Open the ${esc(i.publisher)} page</a>. ` : ''}${esc(i.checked)}</p>`).join('')
    + `<p class="o-first">${esc(o.first)}</p></section>`;
  const strip = !rows.length ? '' : `<ol class="days" aria-label="The next ${rows.length} days">${rows.map(r => {
      const on = r.date === day, label = `${capFirst(longDate(r.date))}: ${r.level ? `forecast ${r.level} risk` : 'no forecast'}.${r.score === null ? '' : ` Sewage spill risk ${r.score} of 100.`}${r.band ? ' ' + r.band.said : ''}`;
      return `<li><a class="day ${cls(r.level)}${on ? ' is-on' : ''}" href="${hashFor(s.id, 'when', r.date)}" aria-label="${esc(label)}"${on ? ' aria-current="true"' : ''}>`
        + `<span class="d-name">${r.date === today() ? 'Today' : new Date(r.date + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'short' })}</span>`
        + `<span class="d-bar">${r.score === null ? '' : `<i style="height:${Math.max(3, r.score)}%"></i>`}${r.band ? `<b style="bottom:${Math.round(r.band.low * 100)}%;height:${Math.max(2, Math.round((r.band.high - r.band.low) * 100))}%"></b>` : ''}</span>`
        + `<span class="d-score">${r.score === null ? '–' : r.score}</span><span class="d-level">${esc(r.level ? capFirst(r.level) : 'No forecast')}</span></a></li>`; }).join('')}</ol>
    <p class="quiet axis">Bars: sewage spill risk, 0 to 100. Words: the day's level.${rows.some(r => r.band) ? ' Thin line: the range from three other rain runs.' : ''} Tap a day.</p>`;
  return `<h2 id="h-when" class="vh">When</h2>
    ${issued.stale ? `<p class="stale">${esc(issued.note)}</p>` : ''}
    ${notice}
    <div class="answer ${a.cls}">
      <p class="kicker">${esc(a.kicker)}</p>
      ${a.lead ? `<p class="lead">${esc(a.lead)}</p>` : ''}
      <p class="head">${esc(a.head)}</p>
      ${a.sub ? `<p class="because">${esc(a.sub)}</p>` : ''}
      ${a.modelled ? `<p class="because">${esc(a.modelled)}</p>` : ''}
      ${a.score === null ? '' : `<p class="score">Sewage spill risk <b>${a.score}</b> of 100</p>`}
      <p class="act">${esc(a.act)}</p>
      ${o ? `<p class="quiet">This level is SwimSignal's forecast. The official ${o.restricts ? 'advice' : 'notice'} above is separate.</p>` : ''}
    </div>
    ${best ? `<p class="best">${esc(best)}</p>` : ''}
    ${strip}
    ${a.live || a.clears ? `<p class="live">${esc([a.live ? a.live + '.' : '', a.clears].filter(Boolean).join(' '))}</p>` : ''}
    <dl class="facts">${a.facts.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>
    ${a.unchecked ? `<p class="unchecked">${esc(a.unchecked.text)} ${a.unchecked.link ? `<a href="${esc(a.unchecked.link)}">${esc(a.unchecked.words)}</a>.` : ''}</p>` : ''}
    ${a.notes.filter(Boolean).map(n => `<p class="note">${esc(n)}</p>`).join('')}
    <p class="quiet">${esc(issued.text)} <a href="../methods.html">How the forecast is made</a></p>`;
}

function upstreamHtml(s) {
  const got = details.get(s.id), head = '<h2 id="h-upstream">Upstream</h2>';
  if (!daily(s)) return `${head}<p class="lede">${esc(levelWords(level(s)))}.</p><p class="note">${esc(isolated(s) ? ISOLATED_WHY : String(s.error || 'The trace found no monitored storm overflow on the river network upstream of this place.'))}</p><p class="note">${esc(OTHER_RISKS)}</p>`;
  if (got === undefined) return `${head}<p class="quiet">Reading the overflows upstream…</p>`;
  const L = riverLine(s, got && got.up, got && got.detail, DATA.spots, now());
  if (!L.items.length) return `${head}<p class="note">The list of overflows upstream could not be read just now. Try again in a minute.</p>`;
  // A long line is cut after the nearest dozen: the Avon at Warleigh Weir has 185 overflows upstream, a page 26,000 px
  // long. What is left out is counted by its status, any overflow discharging further up is still listed, and so are
  // the listed places, so nothing that is spilling is ever behind the button.
  const whole = expanded.has(s.id) || L.items.length <= LINE_FIRST + 3;
  const shown = whole ? L.items : L.items.slice(0, LINE_FIRST), rest = whole ? [] : L.items.slice(LINE_FIRST);
  const restO = rest.filter(i => i.kind === 'overflow'), count = m => restO.filter(i => i.mark === m).length;
  let prev = 0;
  const item = (it, tail = false) => { const gap = it.km - prev; prev = it.km;
    const far = !tail && gap >= 3 ? `<span class="gap-said">${num(gap, gap < 10 ? 1 : 0)} km of water</span>` : '';
    if (tail) it = { ...it, tailGap: true };
    if (it.kind === 'place') return `<li class="stop is-place" style="margin-top:${tail ? 20 : gapPx(gap)}px">${far}<span class="mk mk-place" aria-hidden="true"></span><a href="${hashFor(it.id, 'upstream')}"><b>${esc(it.name)}</b></a><span class="st">Another listed place, ${num(it.km, 1)} km upstream. ${dot(it.cls)}${esc(it.level)} today.</span></li>`;
    const more = [it.company, it.own ? `The company's name for it: ${it.own}` : '',
      it.spills === null ? '' : `Spills a year, long-term average: ${num(it.spills, 1)}`, it.hours === null ? '' : `Hours spilling in its latest annual return: ${num(it.hours, 1)}`,
      it.chance === null ? '' : `Forecast chance of a spill today: ${it.chance < 0.01 ? 'under 1' : Math.round(it.chance * 100)}%`,
      it.weight === null ? '' : `Weight here: ${Math.round(it.weight * 100)}%`,
      it.upgrade && it.upgrade.stage ? `Upgrade: ${it.upgrade.stage}, by the company's own page` : ''].filter(Boolean);
    return `<li class="stop is-${it.mark}" style="margin-top:${it.tailGap ? 20 : gapPx(gap)}px">${far}<span class="mk mk-${it.mark}" aria-hidden="true"></span>
      <b>${esc(it.name)}</b>
      <span class="st">${esc(capFirst(it.where))}${it.into ? `, into ${esc(it.into)}` : ''}.</span>
      <span class="st st-status">${esc(capFirst(it.status))}${it.ended ? `. Last spill ended ${esc(it.ended)}` : ''}.${it.long ? ' ' + esc(it.long) : ''}</span>
      <button type="button" class="link more" data-do="more" aria-expanded="false">More</button>
      <span class="more-box" hidden>${more.map(esc).join('<br>')}<br><a href="../overflow/${encodeURIComponent(it.id)}/">This overflow's record</a></span></li>`; };
  const below = L.below.length ? `<p class="below">Downstream of here: ${L.below.map(b => `<a href="${hashFor(b.id, 'upstream')}">${esc(b.name)}</a> <span class="quiet">${num(b.km, 1)} km, ${esc(b.level.toLowerCase())} today</span>`).join('; ')}.</p>` : '';
  const live = liveLine(s, pollAt(DATA));
  return `${head}
    <p class="lede">${L.total === 1 ? 'One monitored storm overflow' : `${L.total} monitored storm overflows`} within ${L.reach} km upstream of here.${L.more ? ' ' + esc(L.more) : ''}</p>
    ${live ? `<p class="live">${esc(live)}.</p>` : ''}
    ${L.hours ? `<p class="note">In their latest annual returns to the Environment Agency, ${L.hours.of === L.total ? (L.total === 1 ? 'it' : 'they') : `the ${L.hours.of} with a figure`} spilled for ${num(L.hours.sum)} hours in total.</p>` : ''}
    ${below}
    <ol class="line" aria-label="The water upstream, nearest first">
      <li class="stop is-here"><span class="mk mk-here" aria-hidden="true"></span><b>${esc(s.name)}</b><span class="st">This place. Each step down this list is further upstream.</span></li>
      ${shown.map(it => item(it)).join('')}
      ${rest.length ? `<li class="stop is-rest" style="margin-top:28px"><span class="mk mk-end" aria-hidden="true"></span><span class="st"><b>${restO.length} more ${restO.length === 1 ? 'overflow' : 'overflows'} further upstream</b>${[count('spilling') ? `${count('spilling')} discharging${rest.some(i => i.mark === 'spilling') ? ', listed below' : ''}` : '', count('quiet') ? `${count('quiet')} not discharging at the last poll` : '', count('unknown') ? `${count('unknown')} with no current reading` : ''].filter(Boolean).join('; ')}.</span><button type="button" class="link more" data-do="all">Show all ${L.total}</button></li>` : ''}
      ${rest.filter(i => i.mark === 'spilling' || i.kind === 'place').map(it => item(it, true)).join('')}
      <li class="stop is-end" style="margin-top:28px"><span class="mk mk-end" aria-hidden="true"></span><span class="st">The trace stops ${L.reach} km upstream. Overflows beyond it are not counted.</span></li>
    </ol>
    <p class="key"><span><span class="mk mk-spilling"></span> discharging</span> <span><span class="mk mk-quiet"></span> not discharging at the last poll</span> <span><span class="mk mk-unknown"></span> no current reading</span></p>
    <p class="note">A monitor reports when an overflow spills, not how much or what is in it. ${esc(WEIGHT_SAID)}</p>`;
}

const TOPICS = { parking: 'Parking', transport: 'Bus and train', path: 'Path to the water', entry: 'Getting in', exit: 'Getting out', toilets: 'Toilets', changing: 'Changing',
  fees: 'Fees and booking', hours: 'Opening times', rules: 'Who can swim', launch: 'Launching a boat or board', carry: 'Carrying to the water', paddle: 'Paddling here' };
function placeHtml(s) {
  const got = details.get(s.id), g = got && got.detail ? got.detail.guide : null, out = ['<h2 id="h-place">The place</h2>'];
  const photos = g && Array.isArray(g.photos) ? g.photos : [];
  if (photos.length) out.push(`<div class="photos">${photos.map(p => `<figure><img src="../guides/photos/${encodeURIComponent(p.file)}" width="${Number(p.w) || 640}" height="${Number(p.h) || 480}" alt="${esc(p.caption || s.name)}" loading="lazy">`
    + `<figcaption>${esc(p.caption || '')} ${p.status === 'historical' ? 'An older photo: the place may have changed. ' : ''}Photo: ${esc(p.credit || 'credit not given')}`
    + `${httpsLink(p.source) ? `, <a href="${esc(p.source)}">${esc(p.source_name || 'source')}</a>` : ''}${httpsLink(p.licence) ? `, <a href="${esc(p.licence)}">licence</a>` : ''}. ${esc(p.changes || '')}</figcaption></figure>`).join('')}</div>`);
  const facts = [];
  const c = s.classification;
  if (c && c.class) { const poor = String(c.class).toLowerCase() === 'poor';
    facts.push(['Rating', `Designated bathing water, rated ${esc(String(c.class).toLowerCase())} for ${esc(c.year)} by the Environment Agency. ${poor ? esc(poorAdvice(today())) + ' ' : ''}${httpsLink(c.url) ? `<a href="${esc(c.url)}">Its Environment Agency page</a>` : ''}`]); }
  else if (s.sepa && s.sepa.rating) facts.push(['Rating', `Designated bathing water, rated ${esc(String(s.sepa.rating.value).toLowerCase())} for ${esc(s.sepa.rating.year)} by SEPA. ${httpsLink(s.sepa.page) ? `<a href="${esc(s.sepa.page)}">Its SEPA page</a>` : ''}`]);
  const ls = s.lab_sample;
  if (ls && ls.taken_at && !isNil(ls.ecoli)) facts.push(['Last sample', `${esc(ls.qualifier || '')}${num(ls.ecoli)} E. coli per 100 ml on ${esc(shortDate(String(ls.taken_at).slice(0, 10)))}, by the Environment Agency. The line for a rating of sufficient is 900.`
    + (s.ecoli_typical ? ` Of ${s.ecoli_typical.samples} samples from ${s.ecoli_typical.first_year} to ${s.ecoli_typical.last_year}, ${s.ecoli_typical.over_line} were over it.` : '')]);
  if (s.algae && s.algae.date && s.algae.phrase) facts.push(['Algae', `At the Environment Agency's last check, ${esc(shortDate(s.algae.date))}: ${esc(s.algae.phrase)}. The check cannot tell blue-green algae from harmless kinds.`]);
  const rs = s.river_state;
  if (rs && !isNil(rs.level_m) && !rs.stale) { const word = ({ low: 'low water', normal: 'its usual level', high: 'high water', 'very high': 'very high water, above its usual range' })[rs.label];
    facts.push([rs.water === 'lake' ? 'Lake level' : 'River level', `${num(rs.level_m, 2)} m${word ? `, ${word}` : ''}, at ${esc(clock(rs.observed_at))}. Gauge at ${esc(rs.station)}, ${esc(rs.distance_km)} km away${rs.same_river === false ? ', on a different watercourse' : ''}. Not part of the level.`
      + (s.flow_state ? ` The river is ${esc(s.flow_state)}.` : '')]); }
  else if (rs && rs.stale) facts.push(['River level', 'No current reading from the nearest gauge.']);
  for (const f of s.flood_alerts || []) facts.push([esc(f.severity || 'Flood alert'), `${esc(f.area || '')}, from the Environment Agency${f.raised ? `, raised ${esc(shortDate(String(f.raised).slice(0, 10)))}` : ''}. ${httpsLink(f.url) ? `<a href="${esc(f.url)}">Read it</a>` : ''}`]);
  const wt = waterTempSaid(s, today(), now());
  if (wt) facts.push(['Water', esc(wt)]);
  if (s.access && s.access.text) facts.push(['Access', `${esc(s.access.text)} ${httpsLink(s.access.url) ? `<a href="${esc(s.access.url)}">Source</a>` : ''}${s.access.checked_at ? ` Checked ${esc(shortDate(s.access.checked_at))}.` : ''}`]);
  if (s.boat_note && s.boat_note.text) facts.push(['Boats and boards', `${esc(s.boat_note.text)}${s.boat_note.source ? ` Source: ${esc(s.boat_note.source)}.` : ''}`]);
  for (const f of (g && g.facts) || []) facts.push([TOPICS[f.topic] || esc(capFirst(f.topic)), `${esc(f.text)} ${f.status === 'confirmed' ? (httpsLink(f.source) ? `<a href="${esc(f.source)}">${esc(f.source_name || 'Source')}</a>` : esc(f.source_name || '')) : 'A swimmer’s suggestion, not checked.'}`]);
  if (got === undefined) out.push('<p class="quiet">Reading what is known about this place…</p>');
  const grouped = [];   // two facts on one topic share its heading
  for (const [k, v] of facts) { const last = grouped[grouped.length - 1]; if (last && last[0] === k) last[1].push(v); else grouped.push([k, [v]]); }
  out.push(facts.length ? `<dl class="facts wide">${grouped.map(([k, vs]) => `<div><dt>${k}</dt>${vs.map(v => `<dd>${v}</dd>`).join('')}</div>`).join('')}</dl>` : (got === undefined ? '' : '<p class="note">Nothing more is recorded about this place yet: no rating, sample, gauge or guide.</p>'));
  if (g && g.checked) out.push(`<p class="quiet">The practical notes were checked on ${esc(shortDate(g.checked))}${g.how === 'desk' ? ', from published sources, not on a visit' : ''}.</p>`);
  out.push(`<p class="quiet">${esc(s.source === 'openstreetmap' ? 'This place is from OpenStreetMap, © OpenStreetMap contributors.' : String(s.notes || '').replace(/([^.])$/, '$1.'))} A listing is not a right to swim or a check that it is allowed.</p>`);
  return out.join('');
}

function elsewhereHtml(s, day) {
  const from = here || s, E = elsewhere(DATA.spots, from, day, 30, here ? null : s.id);
  const dates = dayRows(s).map(r => r.date), days = dates.length ? dates : (DATA.spots.find(daily) || { days: [] }).days.slice(0, 5).map(d => d.date);
  const pick = days.map(d => `<a class="chip${d === day ? ' is-on' : ''}" href="${hashFor(s.id, 'elsewhere', d)}"${d === day ? ' aria-current="true"' : ''}>${chipName(d)}</a>`).join('');
  const group = (title, rows, note = '') => rows.length ? `<h3>${esc(title)}</h3>${note ? `<p class="quiet">${esc(note)}</p>` : ''}<ul class="rows">${rows.map(r => placeRow(r, day)).join('')}</ul>` : '';
  const when = dayWord(day);
  return `<h2 id="h-elsewhere">Somewhere else</h2>
    <p class="lede">${E.widened ? 'The nearest listed places' : `Listed places within ${E.miles} miles`} of ${here ? 'where you are' : esc(s.name)}, ${esc(when)}.</p>
    <p class="chips" aria-label="Day">${pick}</p>
    <p class="tools">${here ? '<button type="button" class="link" data-do="unlocate">Measure from this place instead</button>' : '<button type="button" class="link" data-do="locate">Measure from where I am</button>'}</p>
    ${group(`Low risk ${when}, nearest first`, E.low) || `<p class="note">No listed place ${E.widened ? 'nearby' : `within ${E.miles} miles`} is forecast at low risk ${esc(when)}.</p>`}
    ${group(`Higher ${when}`, E.raised)}
    ${group('Under official advice', E.advice, 'Follow the advice first, whatever the level beside it.')}
    ${group('No daily forecast', E.plain, 'No monitored overflow was found upstream of these, or they are not covered. That is not the same as low risk.')}
    <p class="note">Miles are in a straight line. Low risk is the forecast for pollution, not a safety check: look at the signs at the water before you swim.</p>`;
}

function foot() {
  const c = (DATA && DATA.credits) || {};
  return `<footer class="foot">
    <p>This is a trial of a different SwimSignal, built to be compared with <a href="../">the current site</a>. Both read the same forecast. Your places are kept on this device only.</p>
    <p><a href="../methods.html">Method and limits</a> · <a href="../verification.html">How accurate it has been</a> · <a href="../privacy.html">Privacy</a> · <a href="../terms.html">Terms</a></p>
    <details><summary>Data sources and licences</summary><p>${esc(c.attribution || '')}</p><p>${esc(c.modified || '')} ${esc(c.endorsement || '')} <a href="../terms.html#data">Full credits</a></p></details>
  </footer>`;
}

// -------------------------------------------------------------------------------- drawing and events
let lastKey = '';
function draw(focus = false) {
  const route = parseHash(location.hash), mine = kept();
  if (route.screen === 'find' && !route.explicit && mine.length && spotOf(mine[0])) { location.replace(hashFor(mine[0])); return; }
  if (route.screen === 'place' && spotOf(route.id) && !details.has(route.id)) loadDetail(route.id);
  const y = window.scrollY, key = route.screen === 'place' ? `${route.id}/${route.view}` : 'find';
  app.innerHTML = route.screen === 'find' ? findScreen() : placeScreen(route);
  const s = route.screen === 'place' ? spotOf(route.id) : null;
  document.title = s ? `${s.name} · SwimSignal trial` : 'Where do you swim? · SwimSignal trial';
  if (key !== lastKey) { window.scrollTo(0, 0); if (focus) { const h = app.querySelector('h1'); if (h) h.focus({ preventScroll: true }); } }
  else window.scrollTo(0, y);
  lastKey = key;
}
async function loadDetail(id) {
  const s = spotOf(id); if (!s) return;
  details.set(id, undefined);
  const get = p => loadJson(p).catch(() => null);
  const [detail, up] = await Promise.all([s.detail_file ? get(`../data/${s.detail_file}`) : null, daily(s) ? get(`../data/upstream/${encodeURIComponent(id)}.json`) : null]);
  details.set(id, { detail, up: up && Array.isArray(up.overflows) ? up.overflows : null });
  if (parseHash(location.hash).id === id) draw();
}

app.addEventListener('input', e => { if (e.target.id === 'q') typed(e.target.value); });
app.addEventListener('click', e => {
  const b = e.target.closest('[data-do]'); if (!b) return;
  const route = parseHash(location.hash), act = b.dataset.do;
  if (act === 'locate') locate(() => draw());
  else if (act === 'unlocate') { here = null; hereNote = ''; draw(); }
  else if (act === 'browse') { browse = !browse; draw(); const again = app.querySelector('[data-do="browse"]'); if (again) again.focus(); }
  else if (act === 'area') { openArea = openArea === b.dataset.area ? '' : b.dataset.area; draw(); const again = app.querySelector('.area.is-on'); if (again) again.focus(); }
  else if (act === 'keep' && route.id) { const ids = kept(); keep(ids.includes(route.id) ? ids.filter(x => x !== route.id) : [...ids, route.id]); draw(); const k = app.querySelector('[data-do="keep"]'); if (k) k.focus(); }
  else if (act === 'all' && route.id) { expanded.add(route.id); draw(); }
  else if (act === 'more') { const box = b.nextElementSibling, open = b.getAttribute('aria-expanded') === 'true'; b.setAttribute('aria-expanded', String(!open)); b.textContent = open ? 'More' : 'Less'; if (box) box.hidden = open; }
  else if (act === 'share') { const s = spotOf(route.id), url = location.href, done = t => { b.textContent = t; };
    if (navigator.share) navigator.share({ title: s ? s.name : 'SwimSignal', url }).catch(() => {});
    else if (navigator.clipboard) navigator.clipboard.writeText(url).then(() => done('Link copied'), () => done('Copy the address from the bar above'));
    else done('Copy the address from the bar above'); }
});
// The first place picked from the opening becomes your place, so the next visit opens on it.
app.addEventListener('click', e => { const a = e.target.closest('main.find a.row'); if (!a || kept().length) return;
  const r = parseHash(a.getAttribute('href')); if (r.id && spotOf(r.id)) keep([r.id]); });
window.addEventListener('hashchange', () => draw(true));

(async function start() {
  try { DATA = prepare(await loadJson('../data/spots-lite.json'), now()); }
  catch (e) { app.innerHTML = '<main class="find"><p class="brand"><span>SwimSignal</span></p><h1>The forecast could not be read</h1><p>Check the connection and load the page again. <a href="../">The current site</a> keeps a copy for offline use.</p></main>'; return; }
  draw();
})();
})();
