// SwimSignal, the redesign preview (src/dipcast/site/preview/). This file is the model: plain functions over the
// published data, with no document, so tests/site_preview.test.cjs can run them in Node. app.js draws what they return.
//
// Two files of rules are loaded before this one, because a level or an official notice must never read differently
// here: ../levels.js (the level, its words, what to do) and ../eatoday.js (official advice and its reviewed wording).
// Only names those two files define are used. The place-first shape and the river as a line come from the /next/
// trial (PR #729), whose model this began as.
(function () {
'use strict';

// ------------------------------------------------------------------------------------------------ small helpers
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const capFirst = s => { s = String(s ?? ''); return s.charAt(0).toUpperCase() + s.slice(1); };
const isNil = v => v === null || v === undefined;
const httpsLink = u => /^https:\/\/[^\s"<>]+$/.test(u || '');
const fold = s => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const list = a => a.length <= 1 ? (a[0] || '') : `${a.slice(0, -1).join(', ')} and ${a[a.length - 1]}`;
const noon = iso => new Date(iso + 'T12:00:00');
const dayNm = iso => dayWord(iso).replace(/^on /, '');                       // "today", "tomorrow", "Sunday"
const longDate = iso => noon(iso).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
const weekday = iso => noon(iso).toLocaleDateString('en-GB', { weekday: 'long' });
const shortDate = iso => { const d = new Date(String(iso).length === 10 ? iso + 'T12:00:00' : iso);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', ...(d.getFullYear() === new Date().getFullYear() ? {} : { year: 'numeric' }) }); };
const clock = iso => new Date(iso).toLocaleString('en-GB', { weekday: 'short', hour: '2-digit', minute: '2-digit' });
const hm = iso => new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
const feedTime = iso => new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const agoWords = (ms, nowMs) => { const m = Math.max(0, Math.round((nowMs - ms) / 60000));
  return m < 60 ? `${m} min` : m < 48 * 60 ? `${Math.round(m / 60)} h` : `${Math.round(m / 1440)} days`; };
const num = (v, dp = 0) => Number(v).toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
// A tab's name for a day: "Today", then the short weekday. The date beside it is the day of the month.
const tabName = iso => iso === today() ? 'Today' : noon(iso).toLocaleDateString('en-GB', { weekday: 'short' });
// A day as a sentence uses it: "today", "tomorrow", "on Saturday" (levels.js, dayWord); as a heading: "Saturday".
const headDay = iso => iso === today() ? 'today' : weekday(iso);

// Two of levels.js's own one-liners that it does not export, said again here in its words: how many monitored
// overflows the trace found upstream, and whether the water is rated poor.
const upstreamCount = s => (s.upstream_summary || {}).overflows || 0;
const ratedPoor = s => !!(s.classification && s.classification.class) && String(s.classification.class).toLowerCase() === 'poor';

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
// One place that is not in the forecast's list (a point tapped on the map, worked out in the browser by anypoint.js),
// made ready as the listed ones are: its readings aged, its days from the reader's own day.
function prepareOne(s, data, nowMs) {
  ageSpot(s, nowMs); fromDay(s, readerDay(data.generated_at, nowMs), String(data.generated_at).slice(0, 10));
  return s;
}
// The dates the forecast covers, from the first spot with a daily forecast.
const dates = data => ((data.spots.find(daily) || {}).days || []).slice(0, 5).map(d => d.date);
// When the companies' live feeds were last read by the build, in ms; NaN without it. The file writes a space where
// ISO has a T, which Safari's Date.parse refuses.
const polledMs = data => Date.parse(String(((data || {}).build || {}).live_feeds ? data.build.live_feeds.polled_at || '' : '').replace(' ', 'T'));
const pollAt = data => { const t = polledMs(data); return Number.isFinite(t) ? clock(t) : ''; };
// "Issued Tue 13:21, 14 min ago". A forecast over eight hours old is said to be old: builds are a median 4.6 h apart.
const STALE_MS = 8 * 3600e3;
function issuedWords(data, nowMs) {
  const t = Date.parse(data.generated_at);
  if (!Number.isFinite(t)) return { text: 'Issue time not given', stale: true, note: 'This forecast gives no issue time, so its age is not known.' };
  const stale = nowMs - t > STALE_MS, sameDay = new Date(t).toDateString() === new Date(nowMs).toDateString();
  return { text: `Issued ${sameDay ? hm(t) : clock(t)}, ${agoWords(t, nowMs)} ago`, stale,
    note: stale ? `This forecast is ${agoWords(t, nowMs)} old, older than usual. Levels and live readings may have changed since it was issued.` : '' };
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

// ------------------------------------------------------------------------------------------------ the five days
const levelWords = l => COVER[l] || (ORDER[l] !== undefined ? `${capFirst(l)} risk` : 'No forecast for this day');
const shortLevel = l => ORDER[l] !== undefined ? capFirst(l) : plainLevel(l) ? 'No daily level' : 'No forecast';
const cls = l => ORDER[l] !== undefined ? 'lv-' + l.replace(' ', '') : plainLevel(l) ? 'lv-clear' : 'lv-none';
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
    return { date: x.date, x, r, level: r.level, score: has ? Math.round(x.risk * 100) : null, own: has ? x.label : null, band: bandFor(s, x, i, r) }; });
}
// The five tabs for a place: every date the forecast covers, with this place's level on it. A place with no daily
// forecast has one level for every day, and its tabs say so.
function dayTabs(s, data) {
  const rows = dayRows(s), by = new Map(rows.map(r => [r.date, r])), l = level(s);
  return dates(data).map(d => { const r = by.get(d), lv = daily(s) ? (r && r.level) || NO_FORECAST : l;
    return { date: d, name: tabName(d), dom: noon(d).getDate(), level: lv, cls: daily(s) ? cls(lv) : '', short: daily(s) ? shortLevel(lv) : '',
      said: `${capFirst(longDate(d))}: ${daily(s) ? (r && r.level ? `${r.level} risk` : 'no forecast') : levelWords(l).toLowerCase() + ', the same every day'}` }; });
}
// The first later day whose level is lower than the day shown: [date, level], low first, else moderate. Never at a
// water rated poor (every day is at least high) or under official advice restricting swimming.
function lowerDay(s, iso) {
  const o = official(s);
  if (!daily(s) || (o && o.restricts) || ratedPoor(s)) return null;
  const rows = dayRows(s).filter(r => r.level), at = rows.find(r => r.date === iso);
  if (!at || rank(at.level) < 1) return null;
  for (const want of [0, 1]) { const hit = rows.find(r => r.date !== iso && rank(r.level) === want && rank(r.level) < rank(at.level));
    if (hit) return { date: hit.date, level: hit.level }; }
  return null;
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
function waterTemp(s, iso, nowMs) {
  const w = s.water_temp, e = s.water_temp_est;
  if (w && typeof w.temp_c === 'number' && w.observed_at && nowMs - Date.parse(w.observed_at) < 24 * 3600e3 && iso === today())
    return { value: `${num(w.temp_c, 1)} °C`, note: `Measured ${w.where || 'nearby'}, ${agoWords(Date.parse(w.observed_at), nowMs)} ago.` };
  if (e && typeof e.temp_c === 'number' && e.date === iso && iso === today() && (WT_ROUTES.has(e.route) || (!e.route && s.kind === 'river' && typeof e.within_c === 'number'))) {
    const how = !e.route || e.route === 'river_model' ? `An estimate, typically within ${num(e.within_c ?? 2)} °C.`
      : e.test === 'winter' && typeof e.typical_c === 'number' ? `A provisional estimate, typically within ${num(e.within_c ?? 2)} °C in a test on past winters.`
      : e.route.endsWith('_off_season') || typeof e.typical_c !== 'number' ? 'A provisional estimate, not yet checked in these months.'
      : `A provisional estimate; typical error ${num(e.typical_c, 1)} °C at ${e.route.startsWith('river') ? 'rivers' : 'lakes'} in a summer test.`;
    return { value: `About ${e.temp_c} °C`, note: how };
  }
  return null;
}
// The answer for one day at one place: every line the opening of a place's page shows. `iso` is a date the forecast
// covers; a place with no daily forecast has one level for every day, and its date still sets the conditions.
function answer(s, iso, data, nowMs) {
  const o = official(s), isToday = iso === today(), l = level(s);
  const out = { date: iso, dateLabel: isToday ? `Today, ${longDate(iso)}` : capFirst(longDate(iso)), everyDay: false, lead: '', head: '', why: [],
    cls: 'lv-none', level: null, act: '', modelled: '', clears: '', apart: '', score: null, conditions: [], notes: [], unchecked: null };
  if (!daily(s)) {
    const [h, why] = headParts(s);
    out.everyDay = true; out.head = h; out.cls = cls(l); out.level = l;
    if (why) out.why.push(capFirst(why) + '.');
    out.act = o ? o.act : levelAction(s);
    if (plainLevel(l)) out.why.push(isolated(s) ? ISOLATED_WHY : `The trace found no monitored storm overflow within ${(s.assumptions || {}).max_upstream_km ?? 60} km upstream of here, so there is no daily level to give.`);
    else if (COVER[l] && s.error) out.why.push(String(s.error));
    if (plainLevel(l)) out.notes.push(OTHER_RISKS);
  } else {
    const row = dayRows(s).find(d => d.date === iso), r = row ? row.r : { level: null };
    if (!row || !r.level) { out.head = 'No forecast for this day'; out.act = o ? o.act : PLAIN_ACTION; }
    else {
      const spills = spillSet(s, r), cover = liveCover(s), blind = isToday && cover && cover.kind === 'none';
      const x = row.x, total = (s.upstream_summary || {}).overflows || 0, say = spillingSaid(x, total, dayWord(iso));
      out.cls = cls(r.level); out.level = r.level; out.score = row.score;
      out.head = spills ? `${capFirst(r.level)} ${HEAD_SCOPE}` : `${capFirst(r.level)} risk`;
      if (r.by === 'record') out.why.push(ratedPoor(s) && inBathingSeason(iso) ? 'Rated poor, with advice against bathing. Every day here is at least high risk.' : 'Rated poor, so every day here is at least high risk.');
      else if (!spills) out.why.push(capFirst(dayBecause(s, r)) + '.');
      else if (r.now) out.why.push(capFirst(nowBecause(s, r)) + '.');
      if (say && r.by !== 'record') out.why.push(capFirst(say) + '.');
      out.act = o ? o.act : dayAction(s, iso);
      if (isToday) {
        if (blind || nowUnknown(s)) { out.lead = liveHead(s) || 'Live sewage spill status not known'; out.modelled = MODELLED_FROM + '.'; }
        out.clears = clearWords(s, nowMs);
      }
    }
    if (walesWords(s)) out.notes.push(walesWords(s));
    if (trialWords(s)) out.notes.push(trialWords(s));
  }
  const x = (s.days || []).find(d => d.date === iso), w = ((s.weather || {}).days || []).find(d => d.date === iso);
  if (x && !isNil(x.rain_48h_mm)) out.conditions.push({ k: 'Rain', v: `${num(x.rain_48h_mm, x.rain_48h_mm < 1 ? 1 : 0)} mm`, note: 'in the 48 hours to midday' });
  if (w) out.conditions.push({ k: 'Air', v: `${w.tmax}°`, note: `high; wind ${w.wind_kmh} km/h` }, { k: 'Daylight', v: `${w.sunrise} to ${w.sunset}`, note: '' });
  const wt = waterTemp(s, iso, nowMs);
  if (wt) out.conditions.push({ k: 'Water', v: wt.value, note: wt.note });
  if (o) out.apart = `This level is SwimSignal's forecast. The official ${o.restricts ? 'advice' : 'notice'} above is separate.`;
  // The Environment Agency's own advice for today cannot be read by the build or the page: said, with where to look.
  if (!o && eaUnchecked(s)) out.unchecked = { text: "Today's official advice was not checked.", link: httpsLink((s.classification || {}).url) ? s.classification.url : '', words: 'Check Environment Agency advice' };
  return out;
}

// ------------------------------------------------------------------------------------------------ behind the level
// Three things a level word alone runs together, kept apart: the level and what set it; the modelled sewage spill
// risk, 0 to 100, with its own word; and what the forecast could not see (overflows with no live reading, water
// across a border, overflows too far up). Each row: { key, label, value, cls, lines, meter }.
function ledger(s, iso, data, nowMs) {
  const rows = [], isToday = iso === today(), when = dayWord(iso), o = official(s);
  if (!daily(s)) {
    const l = level(s), [h, why] = headParts(s);
    rows.push({ key: 'level', label: 'Level, every day', value: h, cls: cls(l),
      lines: [plainLevel(l) ? 'Not a low level: there is no forecast to give here, low or high.' : why ? `Set by: ${why}.` : ''].filter(Boolean) });
    rows.push({ key: 'spill', label: 'Sewage spill risk, modelled', value: 'None here', cls: 'lv-none',
      lines: [isolated(s) ? 'The model has no overflow to work from at this lake.' : 'The model works from monitored overflows upstream, and the trace found none.'] });
    rows.push({ key: 'cover', label: 'Not covered', value: 'Everything else', cls: 'lv-none',
      lines: ['Unmonitored outfalls, treated sewage from sewage works, runoff from farmland and roads, wildlife and other bathers.'] });
    return rows;
  }
  const row = dayRows(s).find(d => d.date === iso), r = row ? row.r : { level: null }, total = upstreamCount(s);
  if (!row || !r.level) {
    rows.push({ key: 'level', label: `Level ${when}`, value: 'No forecast', cls: 'lv-none', lines: ['This update has no forecast for this day here.'] });
    return rows;
  }
  const c = s.classification || {};
  const setBy = r.by === 'record' ? `Set by the Environment Agency's rating: poor${c.year ? ` for ${c.year}` : ''}. The rating keeps every day at high risk or above.`
    : r.by === 'spill' ? (r.now ? `Set by ${nowBecause(s, r)}, from the overflows' live readings.` : 'Set by the sewage spill risk below.')
    : r.by === 'water' ? 'Set by the E. coli estimate below, which is higher than the sewage spill risk.'
    : r.by === 'sample' ? 'Set by a recent Environment Agency sample over 900 E. coli per 100 ml.'
    : r.by === 'algae' ? "Set by algae at the Environment Agency's last check." : '';
  rows.push({ key: 'level', label: `Level ${when}`, value: `${capFirst(r.level)} risk`, cls: cls(r.level),
    lines: [setBy, o ? `SwimSignal's forecast. The official ${o.restricts ? 'advice' : 'notice'} is separate and comes first.` : ''].filter(Boolean) });
  // The modelled score: its own word, which the level above may be higher than.
  const x = row.x, say = spillingSaid(x, total, when), join = tileLine(s, 'spill', iso);
  rows.push({ key: 'spill', label: 'Sewage spill risk, modelled', value: `${row.score} of 100`, word: row.own, cls: cls(row.own),
    week: dayRows(s).map(d => ({ date: d.date, name: tabName(d.date), score: d.score, cls: cls(d.own || NO_FORECAST), on: d.date === iso })),
    meter: { score: row.score, cuts: SPILL_CUTS.map(v => Math.round(v * 100)), band: row.band ? [Math.round(row.band.low * 100), Math.round(row.band.high * 100)] : null },
    lines: [[join && join !== 'This sets the level above.' ? join : '', say ? capFirst(say) + '.' : ''].filter(Boolean).join(' '), row.band ? row.band.said : '',
      'A score for sewage from upstream reaching here, after travel time, die-off and dilution. Not a probability.',
      x.rain_missing_share > 0 ? 'Part of the rain data for this day is missing.' : ''].filter(Boolean) });
  // The E. coli estimate, where the model gives one: in season it can set the level; out of season it is not counted.
  if (ecoliBand(s, x)) rows.push(ecoliUntested(x)
    ? { key: 'ecoli', label: 'E. coli estimate, experimental', value: 'Out of season', cls: 'lv-none', lines: ['Tested only for May to September, so it is not counted in the level now.'] }
    : { key: 'ecoli', label: 'E. coli estimate, experimental', value: `${Math.round(x.p_ecoli_gt900 * 100)}%`, word: ecoliBand(s, x), cls: cls(ecoliBand(s, x)),
        lines: [`Chance a water sample would show over 900 E. coli per 100 ml ${when}. ${riverUsual(x)}`.trim(), tileLine(s, 'water', iso)].filter(Boolean) });
  // What was not seen: live readings missing, and what the trace leaves out.
  const cover = liveCover(s), n = s.now || {}, gaps = [];
  if (cover) {
    const rest = cover.total - cover.mon, k = Math.min(cover.mon, n.discharging_upstream || 0), at = pollAt(data);
    const value = cover.kind === 'none' ? 'No live reading' : cover.kind === 'full' ? (cover.total === 1 ? 'It reports' : `All ${cover.total} report`) : `${cover.mon} of ${cover.total} report`;
    const lines = [];
    if (cover.kind === 'none') lines.push(`${cover.total === 1 ? 'The overflow upstream does not report live' : `None of the ${cover.total} overflows upstream reports live`}, so a spill would not be seen. The level is modelled from rain and past spills.`);
    else lines.push(`${k ? `${k} spilling` : cover.total === 1 ? 'Not spilling' : 'None spilling'} at the last poll${at ? ` (${at})` : ''}.${rest ? ` ${rest} ${rest === 1 ? 'does' : 'do'} not report, so could be spilling unseen.` : ''}`);
    if (!isToday) lines.push(`These are readings from now. ${capFirst(weekday(iso))}'s level comes from the rain forecast and each overflow's past spills.`);
    if (n.aged && n.aged.length) lines.push(`${list(n.aged)}'s feed is over six hours old, so its readings are not counted as current.`);
    rows.push({ key: 'cover', label: 'Live readings upstream', value, cls: cover.kind === 'full' ? 'lv-ink' : 'lv-gap', lines });
  }
  if (walesWords(s)) gaps.push(walesWords(s));
  if (tooFarSaid(s)) gaps.push(tooFarSaid(s));
  if (trialWords(s)) gaps.push(trialWords(s));
  gaps.push(levelScope(s, iso).replace(/^This forecast counts[^.]*\.\s*/, ''));
  rows.push({ key: 'gaps', label: 'Not counted', value: '', cls: 'lv-none', lines: gaps.filter(Boolean) });
  return rows;
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
  return ({ 1: 'discharging now', 0: 'not discharging', '-1': 'monitor offline', '-2': 'no live feed', '-3': 'company feed down' })[c.status] ?? 'status not given';
}
// How it is drawn: 'spilling', 'quiet' (a current "not discharging") or 'unknown' (everything else: never drawn as dry).
function markOf(c, nowMs) {
  if (c.status === 1 || runningAtLastAnswer(c)) return 'spilling';
  const t = Date.parse(c.feed_updated_at);
  return c.status === 0 && (!c.data_state || c.data_state === 'live') && !(Number.isFinite(t) && nowMs - t > FEED_CURRENT_MS) ? 'quiet' : 'unknown';
}
const hoursSaid = h => h < 36 ? `about ${Math.max(1, Math.round(h))} hour${Math.round(h) <= 1 ? '' : 's'}` : `about ${Math.round(h / 24)} days`;
const alongKm = c => (Number(c.distance_km) || 0) + (Number(c.lake_distance_km) || 0);
const kmSaid = km => km < 0.1 ? 'Here' : `${num(km, km < 10 ? 1 : 0)} km`;
// The line: every monitored overflow the trace found, nearest first, and the listed places on the same water as
// waypoints to move to. `up` is data/upstream/<id>.json's list, `detail` data/spot/<id>.json (its ten heaviest
// overflows carry the forecast's chance of a spill on each day); either may be missing, and the line says what it has.
// `iso` picks the day whose chance each overflow shows.
function riverLine(s, up, detail, spots, nowMs, iso = null) {
  const extra = new Map(((detail || {}).contributors || []).map(c => [c.site_id, c]));
  const source = Array.isArray(up) && up.length ? up : ((detail || {}).contributors || []);
  const di = Math.max(0, (s.days || []).slice(0, 5).findIndex(d => d.date === (iso || today())));
  const overflowsList = source.map(c => ({ ...c, ...(extra.get(c.site_id) || {}) })).map(c => {
    const nm = overflowNames(c), other = c.receiving_watercourse && c.receiving_watercourse !== '#N/A' && fold(c.receiving_watercourse) !== fold(s.river) ? c.receiving_watercourse : '';
    return { kind: 'overflow', id: String(c.site_id ?? ''), km: alongKm(c), kmSaid: kmSaid(alongKm(c)), name: nm.plain, own: nm.own, company: companyName(c.company), into: other ? nameCase(other) : '',
      where: overflowWhere(c) + travelSaid(c, hoursSaid), mark: markOf(c, nowMs), status: statusSaid(c, nowMs),
      long: longSpill(c, nowMs) ? LONG_SPILL : '', ended: c.status !== 1 && c.latest_event_end ? shortDate(c.latest_event_end) : '',
      spills: isNil(c.lta_spills) ? null : c.lta_spills, hours: isNil(c.spill_hours) ? null : c.spill_hours, weight: isNil(c.weight) ? null : c.weight,
      chance: Array.isArray(c.p_spill_days) && !isNil(c.p_spill_days[di]) ? c.p_spill_days[di] : null, upgrade: c.upgrade || null };
  });
  const byId = new Map((spots || []).map(p => [p.id, p])), day = iso || today();
  const above = (spots || []).filter(p => p.id !== s.id && (p.downstream || []).some(([id]) => id === s.id))
    .map(p => ({ kind: 'place', id: p.id, km: p.downstream.find(([id]) => id === s.id)[1], name: p.name, level: levelWords(dayLevel(p, day)), cls: cls(dayLevel(p, day)) }));
  const below = (s.downstream || []).filter(([id]) => byId.has(id)).map(([id, km]) => { const p = byId.get(id);
    return { id, km, name: p.name, level: levelWords(dayLevel(p, day)), cls: cls(dayLevel(p, day)) }; }).sort((a, b) => a.km - b.km);
  for (const p of above) p.kmSaid = kmSaid(p.km);
  const items = [...overflowsList, ...above].sort((a, b) => a.km - b.km || (a.kind === 'place' ? -1 : 1));
  const withHours = overflowsList.filter(o => o.hours !== null);
  return { items, below, total: overflowsList.length, spilling: overflowsList.filter(o => o.mark === 'spilling').length,
    quiet: overflowsList.filter(o => o.mark === 'quiet').length, unknown: overflowsList.filter(o => o.mark === 'unknown').length,
    hours: withHours.length ? { sum: withHours.reduce((a, o) => a + o.hours, 0), of: withHours.length } : null,
    reach: (s.assumptions || {}).max_upstream_km ?? 60, more: tooFarSaid(s) };
}

// ------------------------------------------------------------------------------------------------ elsewhere: other places on a day
// One row for a place in a list, on one day: its level then, its five days as marks, and its distance from a point.
function placeRow(p, iso, from = null, data = null) {
  const l = dayLevel(p, iso), o = official(p), km = from ? kmBetween(from, p) : null;
  return { id: p.id, name: p.name, water: p.river && !fold(p.name).includes(fold(p.river)) ? p.river : '', area: p.area || '', km,
    said: km === null ? '' : milesSaid(km, compass(from, p)), level: l, words: levelWords(l), cls: cls(l), notice: o ? o.brief : '', restricts: !!(o && o.restricts),
    week: daily(p) ? dayRows(p).map(r => ({ date: r.date, cls: cls(r.level || NO_FORECAST), on: r.date === iso })) : [],
    group: o && o.restricts ? 'advice' : ORDER[l] === undefined ? 'plain' : l === 'low' ? 'low' : 'raised' };
}
// Other listed places from a point, on one day, in four groups that are never mixed: low risk that day (nearest
// first); a higher level that day; under official advice restricting swimming, whatever the level; and places with
// no daily level, which are never "low". Within `miles`; where that holds under three, the nearest eight instead.
function elsewhere(spots, from, iso, miles = 20, skip = null, hereLevel = null) {
  const rows = spots.filter(p => p.id !== skip).map(p => placeRow(p, iso, from)).sort((a, b) => a.km - b.km);
  let near = rows.filter(r => r.km <= miles * KM_PER_MILE), widened = false;
  if (near.length < 3) { near = rows.slice(0, 8); widened = true; }
  const g = k => near.filter(r => r.group === k), raised = g('raised').sort((a, b) => rank(a.level) - rank(b.level) || a.km - b.km);
  // Seen from a place at high or very high risk, a moderate place is a lower one, and is offered as such; from a
  // low or moderate place it is not. A place at high or very high risk is never offered as lower (docs/DESIGN.md,
  // "Lower risk nearby never offers a spot at high or very high risk").
  const lowerThan = rank(hereLevel) >= 2, moderate = raised.filter(r => r.level === 'moderate');
  return { low: g('low'), moderate, lowerThan, folded: lowerThan ? raised.filter(r => r.level !== 'moderate') : raised, raised, advice: g('advice'), plain: g('plain'), widened, miles, n: near.length };
}
// What to do next from a place on a day, in order: the buttons under the answer. Each { kind, label, date? }.
// A lower place is offered only where one is at low risk that day and not under advice restricting swimming; a lower
// day only where this place has one. A low day, or a place with no daily level, has nothing to steer away from.
function nextSteps(s, iso, spots, miles = 20) {
  const o = official(s), l = dayLevel(s, iso), raised = rank(l) >= 1, E = elsewhere(spots, s, iso, miles, s.id, l), out = [];
  const where = E.widened ? 'nearby' : `within ${miles} miles`, lower = E.low.length + (E.lowerThan ? E.moderate.length : 0);
  if (raised || (o && o.restricts)) {
    // "Lower-risk" only where this place's own level is raised: under official advice at a low-risk place they are
    // simply the places at low risk.
    if (lower) out.push({ kind: 'nearby', n: lower, label: raised ? `${lower === 1 ? 'One lower-risk place' : `${lower} lower-risk places`} nearby`
      : `${lower === 1 ? 'One place' : `${lower} places`} at low risk nearby` });
    const d = lowerDay(s, iso);
    if (d) out.push({ kind: 'day', date: d.date, label: `${capFirst(d.level)} risk here ${dayWord(d.date)}` });
    if (!lower) out.push({ kind: 'nearby-none', label: `No listed place ${where} is at lower risk ${dayWord(iso)}` });
  }
  return out;
}

// ------------------------------------------------------------------------------------------------ the waters, for browsing
// The listed places of one area, grouped by their water: a river's places in order from the top of the river down
// (from each place's `downstream` list), a lake's together, and the rest one by one.
function waters(spots, iso) {
  const groups = new Map();
  for (const p of spots) { const key = p.river || (/^(.*?)(?:,| at | in )/.exec(p.name) || [])[1] || p.name;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(p); }
  return [...groups.entries()].map(([name, ps]) => {
    // Further up the river means more of the group's places lie downstream of it, counted through the others: a
    // place lists only the ones within the trace's reach, so the chain is followed from each to the next.
    const ids = new Set(ps.map(p => p.id)), byId = new Map(ps.map(p => [p.id, p])), memo = new Map();
    const below = p => { if (memo.has(p.id)) return memo.get(p.id);
      const seen = new Set(); memo.set(p.id, seen);
      for (const [id] of p.downstream || []) if (ids.has(id) && id !== p.id) { seen.add(id); for (const x of below(byId.get(id))) seen.add(x); }
      return seen; };
    const sorted = [...ps].sort((a, b) => below(b).size - below(a).size || a.name.localeCompare(b.name));
    // Said to be in order only where each place leads to the next: a river whose places are too far apart to link is not.
    const ordered = ps.length > 1 && sorted.slice(0, -1).every((p, i) => below(p).has(sorted[i + 1].id));
    return { name, river: !!ps[0].river, ordered, rows: sorted.map(p => placeRow(p, iso)) };
  }).sort((a, b) => b.rows.length - a.rows.length || a.name.localeCompare(b.name));
}
// How many places are at low risk on a day, of all of them: the one line the opening keeps of the earlier home page's
// count. Low is a row's own group (placeRow), so a place under official advice, one with no monitored overflow
// found upstream and one with no forecast for the day are never counted as low.
function tally(spots, iso) { return { n: spots.length, low: spots.filter(p => placeRow(p, iso).group === 'low').length }; }
function areas(spots, iso) {
  const names = [...new Set(spots.map(p => p.area).filter(Boolean))];
  return names.map(a => { const ps = spots.filter(p => p.area === a), rows = ps.map(p => placeRow(p, iso));
    return { name: a, n: ps.length, low: rows.filter(r => r.group === 'low').length, ids: ps.map(p => p.id) }; }).sort((a, b) => b.n - a.n || a.name.localeCompare(b.name));
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
const nearest = (spots, from, iso, n = 5) => spots.map(p => placeRow(p, iso, from)).sort((a, b) => a.km - b.km).slice(0, n);

// ------------------------------------------------------------------------------------------------ saved, plan and map
// The saved places on a day, in the order they were saved. An id the forecast no longer lists is counted, not shown.
function savedRows(spots, ids, iso) {
  const by = new Map(spots.map(p => [p.id, p])), rows = ids.filter(id => by.has(id)).map(id => placeRow(by.get(id), iso));
  return { rows, gone: ids.length - rows.length, low: rows.filter(r => r.group === 'low').length };
}
// A plan's places as rows, in the live site's four groups (plan.js, planSpots: low risk; no monitored overflow found
// upstream; moderate or higher; no level). `found` is planSpots' answer; each row says how far it is from the start.
const PLAN_HEADS = ['Low risk', 'No monitored overflow found upstream', 'Moderate risk or higher', 'No level'];
function planRows(found, iso, from) {
  const far = o => { const m = o.miles, n = m < 10 ? Math.round(m * 10) / 10 : Math.round(m);
    return `${m < 1 ? 'under a mile' : `${n} mile${n === 1 ? '' : 's'}`}${from ? ' ' + compass(from, o.s) : ''}`; };
  return found.groups.map((g, i) => ({ key: ['low', 'plain', 'raised', 'none'][i], head: PLAN_HEADS[i], rows: g.map(o => ({ ...placeRow(o.s, iso), km: o.miles * KM_PER_MILE, said: far(o) })) })).filter(g => g.rows.length);
}
// Every place as a point for the map, on one day: where it is, its level's class and whether official advice rings it.
const mapPoints = (spots, iso) => spots.filter(p => Number.isFinite(p.lat) && Number.isFinite(p.lon)).map(p => { const l = dayLevel(p, iso);
  return { id: p.id, name: p.name, lat: p.lat, lon: p.lon, level: l, cls: cls(l), words: levelWords(l), advised: !!official(p) }; });
// The overflows upstream as points for the map: the line's own items (riverLine) at their positions in the upstream
// file, so the map's mark, name and words for an overflow are the line's and the two cannot disagree.
function overflowPoints(items, up) {
  const at = new Map((Array.isArray(up) ? up : []).filter(c => Number.isFinite(c.lat) && Number.isFinite(c.lon)).map(c => [String(c.site_id ?? ''), c]));
  return (items || []).filter(i => i.kind === 'overflow' && at.has(i.id)).map(i => ({ id: i.id, name: i.name, lat: at.get(i.id).lat, lon: at.get(i.id).lon, mark: i.mark,
    said: `${capFirst(i.status)}. ${i.kmSaid === 'Here' ? 'At this place' : `${i.kmSaid} upstream`}.`, company: i.company }));
}
// An encoded line (src/dipcast/trace.py, encode) as [lat, lon] points: the river the forecast traced upstream.
function decodeLine(str) {
  const pts = []; let i = 0, lat = 0, lon = 0; str = String(str || '');
  const next = () => { let shift = 0, res = 0, b; do { b = str.charCodeAt(i++) - 63; res |= (b & 31) << shift; shift += 5; } while (b >= 32 && i <= str.length); return res & 1 ? ~(res >> 1) : res >> 1; };
  while (i < str.length) { lat += next(); lon += next(); pts.push([lat / 1e5, lon / 1e5]); }
  return pts;
}

// ------------------------------------------------------------------------------------------------ the address
// A place has an address of its own, "spot/<id>/?day=<date>", under where these pages are published, so the build can
// write a page there for a reader without scripts and for a link's preview (build_site.write_preview). The opening is
// "?q=<text>&day=<date>" or "?area=<name>", and "?view=map", "?view=saved" or "?view=plan" its three other views.
// "?spot=<id>" still opens a place: the links made before places had addresses. A link someone shares keeps its day, so the
// person who opens it sees the day that was meant; a day that has passed is said. A plan's own choices (where it
// starts, how far, which waters) sit after the #, as on the live site (plan.js), so they never reach a server.
const VIEWS = ['map', 'plan', 'saved'];
// "#point=<lat>,<lon>" is a point tapped on the map that is not a listed place: its forecast is worked out in the
// browser (anypoint.js). Where someone tapped is theirs, so it sits after the #, which never reaches a server (the
// live page keeps it out of the address altogether; here a link to it can be kept or sent). To five places, within
// Britain and Ireland.
const POINT_ID = /^point-(-?\d{1,2}\.\d{1,5}),(-?\d{1,2}\.\d{1,5})$/;
function pointOf(text) {
  const m = String(text || '').match(/^(-?\d{1,2}(?:\.\d{1,6})?),(-?\d{1,2}(?:\.\d{1,6})?)$/); if (!m) return null;
  const lat = Number(m[1]), lon = Number(m[2]);
  return lat > 49 && lat < 61.5 && lon > -11 && lon < 2.5 ? { lat, lon, id: `point-${lat.toFixed(5)},${lon.toFixed(5)}` } : null;
}
function parseQuery(search) {
  const q = new URLSearchParams(String(search || '').replace(/^\?/, '')), d = /^\d{4}-\d{2}-\d{2}$/.test(q.get('day') || '') ? q.get('day') : null;
  const id = /^[A-Za-z0-9_-]+$/.test(q.get('spot') || '') ? q.get('spot') : null, view = VIEWS.includes(q.get('view')) ? q.get('view') : '';
  return id ? { screen: 'place', id, day: d } : { screen: 'find', view, day: d, q: view ? '' : q.get('q') || '', area: view ? '' : q.get('area') || '' };
}
// The address in the bar, read against where the pages are published (base, a path ending in "/").
// "plan/" and "saved/" are the live site's addresses for its Plan a swim and its Saved page: where these pages are the
// site's own, a link to either opens that view here. So does "?map=1", the live site's link to its map.
function parseAddress(pathname, search, base, hash = '') {
  const path = String(pathname || ''), rel = base && path.startsWith(base) ? path.slice(base.length) : '';
  const m = rel.match(/^spot\/([A-Za-z0-9_-]+)\/(?:index\.html)?$/), r = parseQuery(search);
  // The live page's links to a place on a day end "#day=2026-11-28" (a shared place, an outing's calendar file): read too.
  const hd = (String(hash || '').match(/^#day=(\d{4}-\d{2}-\d{2})$/) || [])[1] || null;
  if (m) return { screen: 'place', id: m[1], day: r.day || hd };
  const pt = rel === '' || rel === 'index.html' ? pointOf((String(hash || '').match(/^#point=([^&]+)$/) || [])[1]) : null;
  if (pt) return { screen: 'place', id: pt.id, point: [pt.lat, pt.lon], day: r.day };
  const v = rel.match(/^(plan|saved)\/(?:index\.html)?$/);
  if (r.screen === 'find' && !r.view) { if (v) return { ...r, view: v[1], q: '', area: '' };
    if (new URLSearchParams(String(search || '').replace(/^\?/, '')).get('map') === '1') return { ...r, view: 'map', q: '', area: '' }; }
  return r;
}
// An address for a link, relative to where the pages are published: every page carries a <base> there.
function queryFor(r) {
  const q = new URLSearchParams(), pt = r.id ? String(r.id).match(POINT_ID) : null;
  if (!r.id) { if (VIEWS.includes(r.view)) q.set('view', r.view); else { if (r.q) q.set('q', r.q); if (r.area) q.set('area', r.area); } }
  if (r.day && r.day !== today()) q.set('day', r.day);
  const s = q.toString();
  if (pt) return `${s ? '?' + s : './'}#point=${pt[1]},${pt[2]}`;
  return r.id ? `spot/${r.id}/${s ? '?' + s : ''}` : s ? '?' + s : './';
}

const api = { esc, capFirst, fold, list, num, longDate, weekday, shortDate, tabName, headDay, dayNm, kmBetween, compass, milesSaid, ageSpot, prepare, dates, issuedWords,
  official, levelWords, shortLevel, cls, dayRows, dayTabs, lowerDay, spillingSaid, waterTemp, answer, ledger, statusSaid, markOf, riverLine, placeRow, elsewhere,
  nextSteps, waters, areas, tally, findSpots, postcodeKeys, findTowns, nearest, parseQuery, parseAddress, queryFor, pointOf, prepareOne, pollAt, httpsLink, isNil,
  savedRows, planRows, PLAN_HEADS, mapPoints, overflowPoints, decodeLine, VIEWS };
if (typeof module === 'object' && module.exports) module.exports = api;
else window.PV = api;
})();
