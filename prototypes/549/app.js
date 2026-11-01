// The #549 prototype: Explore / My waters, a spot, Plan and Research, with the #550 satellite explorer, drawn from
// the live site's public data (swimsignal.co.uk/data, which allows any origin). Nothing is sent anywhere; saved spots
// and a plan are kept in this browser under proto549.* keys, apart from the live site's own.
//
// The words for levels and official advice follow levels.js and eatoday.js. What is new is where they go: official
// advice once and first, the answer, then conditions with the kind of each value (Measured, Estimated, Forecast,
// Observed) and its time at the value, and the methods in named disclosures.
//
// Levels and their words come from the live site's own levels.js (app.html loads it, with experience.js and
// eatoday.js, before this file): level, dayLevel, headParts, dayHeadline, weekNext, COVER. So a level here can never
// disagree with the live page. This file is wrapped so that none of its names clash with those globals.
(() => {

const LIVE = 'https://swimsignal.co.uk/';
const DATA = LIVE + 'data/';
const EARTH_SEARCH = 'https://earth-search.aws.element84.com/v1/collections/sentinel-2-c1-l2a/items/';
const SAVED_KEY = 'proto549.saved', PLAN_KEY = 'proto549.plan';
const DEFAULT_SAVED = ['eden-lazonby', 'bw-ukj2310-11945', 'dove-dovedale'];
const LEVEL_CLASS = { low: 'l-low', moderate: 'l-moderate', high: 'l-high', 'very high': 'l-veryhigh' };

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const store = { get(k, d) { try { const v = JSON.parse(localStorage.getItem(k)); return v ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private window: the page still works */ } } };
const ukTime = iso => new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/London' });
const ukDay = (iso, opts = { weekday: 'short', day: 'numeric', month: 'short' }) => new Date(iso.length === 10 ? iso + 'T12:00:00Z' : iso).toLocaleDateString('en-GB', { ...opts, timeZone: 'Europe/London' });
const todayISO = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London' }).format(new Date());
const dname = (iso, i) => i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : ukDay(iso, { weekday: 'long' });
const miles = km => Math.round(km / 1.609344);
const kmBetween = (a, b) => { const R = 6371, r = x => x * Math.PI / 180, dLat = r(b.lat - a.lat), dLon = r(b.lon - a.lon);
  return 2 * R * Math.asin(Math.sqrt(Math.sin(dLat / 2) ** 2 + Math.cos(r(a.lat)) * Math.cos(r(b.lat)) * Math.sin(dLon / 2) ** 2)); };

let LITE = null, LAKES = null, CORES = null;
const lakeCache = new Map();
const loadLite = () => LITE ? Promise.resolve(LITE) : fetch(DATA + 'spots-lite.json').then(r => r.json()).then(d => { setToday(new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London' }).format(new Date(d.generated_at))); return (LITE = d); });
const loadLakes = () => LAKES ? Promise.resolve(LAKES) : fetch(DATA + 'research/lakes.json').then(r => r.json()).then(d => (LAKES = d));
const loadCores = () => CORES ? Promise.resolve(CORES) : fetch('data/cores.geojson').then(r => r.json()).then(d => (CORES = d)).catch(() => (CORES = { features: [] }));
const loadLake = id => lakeCache.has(id) ? Promise.resolve(lakeCache.get(id)) : fetch(DATA + `research/lake/${encodeURIComponent(id)}.json`).then(r => r.json()).then(d => (lakeCache.set(id, d), d));
const spotById = id => LITE.spots.find(s => s.id === id);
const saved = () => store.get(SAVED_KEY, DEFAULT_SAVED).filter(id => spotById(id));

// ------------------------------------------------------------------------------ what a spot says
const levelWords = l => ORDER[l] !== undefined ? `${cap(l)} risk` : (COVER[l] || 'No forecast');
const noOverflows = s => !(s.upstream_summary && s.upstream_summary.overflows);
// The answer at the top of a spot: today's level as the live headline gives it (right now, today or tomorrow,
// whichever is worst), and where that headline is the live status instead (no overflow reports), the level itself
// with the status said under it.
function answer(s) {
  const [head, why] = headParts(s), lv = level(s);
  if (ORDER[lv] === undefined) return { cls: 'l-na', head, why: '', label: null };
  const own = head.toLowerCase().startsWith(lv);
  // Beside official advice the level is never bare: it is about sewage spills only, and says so.
  const sewage = advice(s).length || !own;
  return { cls: LEVEL_CLASS[lv], head: sewage ? `${cap(lv)} risk from sewage spills` : head,
    why: own ? (sewage ? `${head.slice(lv.length + 6)}`.trim() : why) : 'today · modelled: no live spill status upstream', label: lv };
}
const dayLv = (s, iso) => dayLevel(s, iso);
const change = s => weekNext(s) || '';
function reason(s) {
  if (noOverflows(s)) return s.days && s.days.length
    ? 'No storm overflow is traced upstream within 60 km. Other risks apply: algae, wildlife, runoff and bathers.'
    : 'No river or beck is drawn into this water, so no overflow can be traced to it. Other risks apply.';
  const d = (s.days || [])[0], n = s.upstream_summary.overflows;
  // Raised right now by a spill already reported upstream: name it and say when it should have passed (levels.js).
  if (worstNear(s)[1] === 'right now' && rank(worstNear(s)[0].level) >= 1) {
    const src = (s.now || {}).source;
    return `${src ? `${titleCase(src.site_name)}, ${Math.round(src.distance_km)} km upstream, spilled recently. ` : 'An overflow upstream spilled recently. '}${clearWords(s)}`;
  }
  if (!d) return '';
  const e = d.expected_spilling_overflows;
  return e >= 0.5 ? `About ${Math.round(e)} of the ${n} overflows upstream expected to spill today.`
    : `${n === 1 ? 'A spill from the overflow' : `A spill from one of the ${n} overflows`} upstream is possible, not expected.`;
}
// Live status and its gaps, short. Stale or down feeds are said here, at the level, not in a fold.
function liveLine(s) {
  const n = s.now || {}, u = s.upstream_summary || {};
  if (noOverflows(s)) return '';
  const parts = [];
  if (n.discharging_upstream) parts.push(`<b>${n.discharging_upstream} spilling now</b>`);
  else if (u.with_live_feed) parts.push(`None spilling at the last report (${u.with_live_feed} of ${u.overflows} report live)`);
  else parts.push('<span class="warn">No live status: the overflow upstream does not report</span>');
  const stale = (n.stale_upstream || 0) + (n.feed_down_upstream || 0);
  if (stale) parts.push(`<span class="warn">${stale} feed${stale === 1 ? '' : 's'} not updating</span>`);
  return parts.join(' · ');
}
function waterTemp(s) {
  const w = s.water_temp_est;
  if (!w || w.temp_c == null) return { lab: 'Water', val: 'No estimate', kind: 'missing', how: 'No water temperature estimate in this update' };
  return { lab: 'Water', val: `About ${w.temp_c} °C`, kind: 'Estimated', how: `From recent air (${w.air_7d_c} °C), not measured${w.tested ? '' : '; not yet checked at this time of year'}` };
}
function riverCond(s) {
  const r = s.river_state;
  if (!r) return { lab: s.kind === 'lake' ? 'Lake level' : 'River level', val: 'No gauge', kind: 'missing', how: 'No gauge reading here' };
  if (r.stale || r.level_m == null) return { lab: 'River level', val: 'No recent reading', kind: 'stale',
    how: `${r.station}: last ${r.last_level_m ?? '?'} m on ${ukDay(r.observed_at)}` };
  return { lab: 'River level', val: `${r.level_m.toFixed(2)} m · ${r.label}`, kind: 'Measured',
    how: `${r.station} gauge${r.distance_km > 1 ? `, ${r.distance_km.toFixed(0)} km away` : ''} · ${ukTime(r.observed_at)}` };
}
function weatherCond(s) {
  const w = s.weather && s.weather.days && s.weather.days[0];
  if (!w) return null;
  return { lab: 'Weather today', val: `${w.tmax} °C high`, kind: 'Forecast', how: `Light ${w.sunrise} to ${w.sunset}` };
}
function algaeCond(s) {
  const a = s.algae;
  if (!a) return null;
  return { lab: 'Algae check', val: cap(a.phrase), kind: 'Observed', how: `Environment Agency, ${ukDay(a.date)}` };
}
const condHtml = c => c ? `<div class="cond"><p class="lab">${esc(c.lab)} <span class="kind ${/stale|missing/.test(c.kind) ? c.kind : ''}">${esc(c.kind === 'stale' ? 'Stale' : c.kind === 'missing' ? 'Missing' : c.kind)}</span></p>`
  + `<p class="val${c.val.length > 14 ? ' small' : ''}">${esc(c.val)}</p><p class="how">${esc(c.how)}</p></div>` : '';
const advice = s => (s.official || []);
const restricts = s => advice(s).some(a => a.restricts);
function adviceHtml(s) {
  const a = advice(s);
  if (!a.length) return '';
  const r = restricts(s);
  return `<section class="advice" aria-labelledby="adv-h"><h2 id="adv-h">${r ? 'Official advice' : 'Official notice'}</h2>`
    + a.map(x => `<p><b>${esc(x.line)}</b>. Checked ${esc(ukDay(x.checked))}. <a href="${esc(x.link)}" rel="noopener">Read it on the ${esc(x.publisher)} site</a></p>`).join('')
    + `<p>${r ? 'Follow it first.' : 'Read it first.'} SwimSignal's level below is separate and does not include it.</p></section>`;
}
const barHtml = (d, lv) => `<span class="bar" aria-hidden="true"><i style="width:${Math.max(4, Math.min(100, Math.round((d.risk || 0) * 250)))}%;background:var(--${{ low: 'low', moderate: 'moderate', high: 'high', 'very high': 'veryhigh' }[lv] || 'unknown'})"></i></span>`;

// ------------------------------------------------------------------------------ screens
const ICON = {
  explore: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/></svg>',
  map: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2Zm6-2v16m6-14v16"/></svg>',
  plan: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4m6-4v4"/></svg>',
  saved: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h12v18l-6-4-6 4Z"/></svg>',
  more: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>',
};
const nav = cur => `<nav class="pnav" aria-label="Main">${[['explore', '#/explore', 'Explore'], ['map', LIVE + '?map=1', 'Map'], ['plan', '#/plan', 'Plan'], ['saved', '#/explore', 'Saved'], ['more', '#/research', 'More']]
  .map(([k, h, t]) => `<a href="${h}"${k === cur ? ' aria-current="page"' : ''}>${ICON[k]}${t}</a>`).join('')}</nav>`;
const issued = () => `Forecast issued ${ukDay(LITE.generated_at, { weekday: 'short' })} ${ukTime(LITE.generated_at)}`;

function savedRow(s) {
  const a = answer(s), w = s.water_temp_est, adv = advice(s), r = s.river_state, n = s.now || {};
  const flags = [];
  if (adv.length) flags.push(`<span class="flag">${restricts(s) ? 'Official advice against bathing' : 'Official notice'}</span>`);
  if (r && r.stale) flags.push('<span class="flag">River gauge stale</span>');
  if ((n.stale_upstream || 0) + (n.feed_down_upstream || 0)) flags.push('<span class="flag">A live feed is not updating</span>');
  return `<li><a class="row" href="#/spot/${esc(s.id)}"><span class="nm">${esc(s.name)}</span>`
    + (flags.length ? `<span class="line">${flags.join('')}</span>` : '')
    + `<span class="line"><span class="${a.cls}"><b>${esc(a.head)}</b></span>`
    + (w ? `<span>About ${w.temp_c} °C <span class="kind">Estimated</span></span>` : '') + `</span></a></li>`;
}

function explore(q = '') {
  const mine = saved().map(spotById);
  const ql = q.trim().toLowerCase();
  const hits = ql ? LITE.spots.filter(s => [s.name, s.area, s.river].join(' ').toLowerCase().includes(ql)).slice(0, 30) : [];
  return `<div class="wrap"><h1>My waters</h1><p class="fresh">${esc(issued())}</p>`
    + (mine.length ? `<ul class="rows" style="margin-top:12px">${mine.map(savedRow).join('')}</ul>` : '<p>Save a water to see it here first.</p>')
    + `<h2>Find a water</h2><label class="sr" for="q">River, lake or town</label><input class="search" id="q" type="search" placeholder="River, lake or town" value="${esc(q)}" autocomplete="off">`
    + `<div id="hits">${hitsHtml(hits, ql)}</div>`
    + `<div class="actions"><a class="btn" href="${LIVE}?map=1">Open the map</a><a class="btn primary" href="#/plan">Choose a swim time</a></div>`
    + `<details class="more" style="margin-top:20px"><summary>All ${LITE.spots.length} spots by area</summary><div>${byArea()}</div></details>`
    + `</div>` + nav('explore');
}
const hitsHtml = (hits, ql) => !ql ? '' : hits.length ? `<ul class="rows" style="margin-top:8px">${hits.map(savedRow).join('')}</ul>` : '<p class="sub" style="margin-top:8px">No spot matches. Try a river or a town.</p>';
function byArea() {
  const g = {};
  for (const s of LITE.spots) (g[s.area] = g[s.area] || []).push(s);
  return Object.keys(g).sort().map(a => `<p><b>${esc(a)}</b><br>${g[a].map(s => `<a href="#/spot/${esc(s.id)}">${esc(s.name)}</a>`).join(' · ')}</p>`).join('');
}

function spot(id) {
  const s = spotById(id);
  if (!s) return `<div class="wrap"><p>No spot with that id.</p><a href="#/explore">Back</a></div>`;
  const a = answer(s), isSaved = saved().includes(id);
  const conds = [waterTemp(s), riverCond(s), weatherCond(s), algaeCond(s)].filter(Boolean);
  const t0 = today(), near = alternatives(s, t0, 2);
  const why = (s.days || [])[0]?.source;
  return `<div class="wrap"><div class="top-row"><a class="back" href="#/explore">‹ My waters</a>`
    + `<button class="btn" id="save" aria-pressed="${isSaved}">${isSaved ? 'Saved' : 'Save this water'}</button></div>`
    + `<h1>${esc(s.name)}</h1><p class="sub">${esc(cap(s.kind))}${s.river && s.kind === 'river' ? ` · ${esc(s.river)}` : ''} · ${esc(s.area)}</p>`
    + adviceHtml(s)
    + `<section class="answer" aria-label="SwimSignal's level"><p class="level ${a.cls}">${esc(a.head)}</p>`
    + (a.label ? `<p class="when">${esc(cap(a.why || ''))}${a.why && change(s) ? ' · ' : ''}${esc(change(s))}</p>` : '')
    + `<p class="reason">${esc(reason(s))}</p>`
    + `<p class="fresh">${liveLine(s) ? liveLine(s) + '<br>' : ''}${esc(issued())}</p></section>`
    + `<div class="conds">${conds.map(condHtml).join('')}${conds.length % 2 ? '<div class="cond"></div>' : ''}</div>`
    + ((s.days || []).length && !noOverflows(s) ? `<ul class="days" aria-label="Pollution risk, next five days">${s.days.slice(0, 5).map((d, i) => `<li><span>${esc(i === 0 ? 'Today' : ukDay(d.date, { weekday: 'short' }))}</span>${barHtml(d, dayLv(s, d.date))}<span class="${LEVEL_CLASS[dayLv(s, d.date)] || 'l-na'}"><b>${esc(ORDER[dayLv(s, d.date)] !== undefined ? cap(dayLv(s, d.date)) : '–')}</b></span></li>`).join('')}</ul>` : '')
    + `<div class="actions"><a class="btn primary" href="#/plan?spot=${esc(id)}">Choose a swim time</a><a class="btn" href="#/plan?spot=${esc(id)}&compare=1">Compare another spot</a></div>`
    + (near.length ? `<h2>Nearby today</h2><ul class="rows">${near.map(n => altRow(s, n, t0)).join('')}</ul>` : '')
    + `<h2 class="sr">More about this forecast</h2>`
    + `<details class="more" style="margin-top:20px"><summary>Why this level</summary><div>${why ? `<p>The largest share today comes from ${esc(titleCase(why.site_name))}, ${why.distance_km.toFixed(0)} km upstream on ${esc(why.receiving_watercourse)}, about ${Math.round(why.travel_h)} hours' travel away.</p>` : ''}<p>The level combines each overflow's chance of spilling, from the rain forecast and its past spills, with how far the water has to travel.</p><p><a href="${LIVE}spot/${esc(id)}/">The live page has the full breakdown</a>.</p></div></details>`
    + `<details class="more"><summary>What this forecast cannot see</summary><div><p>Farm and road runoff, wildlife, algae, unmonitored outfalls, and anything at the water itself. A forecast, not a water test: check the signs at the water.</p></div></details>`
    + `<details class="more"><summary>Methods and sources</summary><div><p>Storm overflow status from the water companies via the National Storm Overflow Hub; river levels from the Environment Agency; weather from Open-Meteo. <a href="${LIVE}methods.html">How it works</a> · <a href="${LIVE}verification.html">How accurate it is</a></p></div></details>`
    + `</div>` + nav('explore');
}
const titleCase = s => String(s || '').toLowerCase().replace(/\b(\w)/g, c => c.toUpperCase()).replace(/\bWwtw\b/, 'WwTW');
function alternatives(s, iso, n) {
  const rk = x => ORDER[dayLv(x, iso)] ?? 9, mine = rk(s);
  return LITE.spots.filter(x => x.id !== s.id && x.lat && ORDER[dayLv(x, iso)] !== undefined)
    .map(x => ({ x, km: kmBetween(s, x) })).filter(o => o.km < 40 && rk(o.x) <= mine)
    .sort((a, b) => (rk(a.x) - rk(b.x)) || a.km - b.km).slice(0, n);
}
function altRow(s, o, iso) {
  const x = o.x, lv = dayLv(x, iso), same = s.river && x.river && s.river === x.river;
  return `<li><a class="row" href="#/spot/${esc(x.id)}"><span class="nm">${esc(x.name)}</span><span class="line"><span class="${LEVEL_CLASS[lv]}"><b>${esc(dayHeadline(x, iso))}</b></span>`
    + `<span>${miles(o.km)} miles</span>${same ? '<span>Same river</span>' : ''}${advice(x).length ? '<span class="flag">Official advice</span>' : ''}</span></a></li>`;
}

// Plan: one flow. When, where (spot, then backup), your plan side by side, save.
function plan(params) {
  const days = (LITE.spots.find(s => (s.days || []).length >= 5) || { days: [] }).days.slice(0, 5).map(d => d.date);
  const keep = store.get(PLAN_KEY, {});
  const p = { day: params.get('day') || keep.day || days[1] || days[0], when: params.get('when') || keep.when || 'morning',
    spot: params.get('spot') || keep.spot || saved()[0], backup: params.get('backup') ?? keep.backup ?? '' };
  if (!days.includes(p.day)) p.day = days[0];
  const di = days.indexOf(p.day), s = spotById(p.spot);
  const sug = s ? alternatives(s, p.day, 3) : [];
  if (!p.backup && params.get('compare') && sug[0]) p.backup = sug[0].x.id;
  const b = p.backup && spotById(p.backup);
  const opt = (id, sel) => `<option value="${esc(id)}"${id === sel ? ' selected' : ''}>${esc(spotById(id).name)}</option>`;
  const ids = [...new Set([...saved(), ...LITE.spots.map(x => x.id)])];
  const col = (x, role) => {
    if (!x) return `<div class="col"><h3>${role}</h3><p>Choose one to compare.</p></div>`;
    const lv = dayLv(x, p.day), w = x.water_temp_est, r = riverCond(x);
    return `<div class="col"><h3>${role}: ${esc(x.name)}</h3>${advice(x).length ? `<p class="flag">${restricts(x) ? 'Official advice against bathing' : 'Official notice'}: follow it first</p>` : ''}`
      + `<p class="level ${LEVEL_CLASS[lv] || 'l-na'}">${esc(dayHeadline(x, p.day))}</p>`
      + (w ? `<p>Water about ${w.temp_c} °C <span class="kind">Estimated</span></p>` : '')
      + `<p>${esc(r.lab)}: ${esc(r.val)} <span class="kind ${/stale|missing/.test(r.kind) ? r.kind : ''}">${esc(r.kind === 'stale' ? 'Stale' : r.kind === 'missing' ? 'Missing' : r.kind)}</span></p></div>`;
  };
  return `<div class="wrap"><h1>Plan a swim</h1><p class="fresh">${esc(issued())}</p>`
    + `<section class="step"><h2>1. When</h2><div class="strip" role="group" aria-label="Day">${days.map((d, i) => `<button data-day="${d}" aria-pressed="${d === p.day}">${esc(i === 0 ? 'Today' : ukDay(d, { weekday: 'short' }))}<br>${esc(ukDay(d, { day: 'numeric', month: 'short' }))}</button>`).join('')}</div>`
    + `<div class="chips" role="group" aria-label="Time of day">${['morning', 'afternoon', 'evening'].map(w => `<button class="chip" data-when="${w}" aria-pressed="${w === p.when}">${cap(w)}</button>`).join('')}</div></section>`
    + `<section class="step"><h2>2. Where</h2><label class="f" for="pspot">Your spot</label><select id="pspot">${ids.map(i => opt(i, p.spot)).join('')}</select>`
    + `<label class="f" for="pback">Backup</label><select id="pback"><option value="">None</option>${ids.filter(i => i !== p.spot).map(i => opt(i, p.backup)).join('')}</select>`
    + (sug.length ? `<p class="meta" style="margin:8px 0 0">Suggested backups, ${esc(dname(p.day, di).toLowerCase())}:</p><div class="chips" style="margin-top:6px">${sug.map(o => `<button class="chip" data-backup="${esc(o.x.id)}" aria-pressed="${o.x.id === p.backup}">${esc(o.x.name)} · ${esc(levelWords(dayLv(o.x, p.day)))}</button>`).join('')}</div>` : '')
    + `</section><section class="step"><h2>3. Your plan: ${esc(dname(p.day, di))}, ${esc(p.when)}</h2><div class="pair">${col(s, 'Spot')}${col(b, 'Backup')}</div>`
    + `<p class="meta">One level covers the whole day; the time is your plan, not a finer forecast.</p></section>`
    + `<div class="actions"><button class="btn primary" id="psave">${keep.spot === p.spot && keep.day === p.day && keep.backup === p.backup && keep.when === p.when ? 'Plan saved' : 'Save this plan'}</button><a class="btn" href="${LIVE}plan/">Add to calendar or alerts</a></div>`
    + `<p class="illus">Calendar and alerts: on the live site's Plan a swim; not rebuilt in this prototype.</p>`
    + `<details class="more" style="margin-top:16px"><summary>What would change this plan</summary><div><p>A new official notice, a level change for ${esc(dname(p.day, di).toLowerCase())}, or a river rising. Look again before you leave: forecasts are reissued every half hour.</p></div></details>`
    + `</div>` + nav('plan');
}

// Research: what each viewer lets you do and how fresh it is; methods on demand.
function research() {
  const L = LAKES, pilot = L.pilot.runs[L.pilot.runs.length - 1];
  const latest = L.lakes.map(x => x.latest && x.latest.date).filter(Boolean).sort().pop();
  return `<div class="wrap"><h1>Research</h1><p class="sub">Observations and tests behind SwimSignal. Each one opens on a phone.</p>`
    + `<div class="cards" style="margin-top:16px">`
    + `<a class="card" href="#/lakes"><h3>Explore satellite observations</h3><p>How green ${L.lakes.length} lake locations looked from space, on a map, by date.</p><p class="meta">Latest usable image ${esc(ukDay(latest, { day: 'numeric', month: 'short', year: 'numeric' }))} · five lakes checked weekly, last ${esc(ukDay(pilot.finished, { day: 'numeric', month: 'short' }))}</p></a>`
    + `<a class="card" href="${LIVE}lake-temperatures.html"><h3>Measured lake temperatures</h3><p>Readings from lake sensors, against SwimSignal's estimates.</p></a>`
    + `<a class="card" href="${LIVE}durations.html"><h3>How long spills last</h3><p>Past spill durations for the overflows upstream of each spot.</p></a>`
    + `<a class="card" href="${LIVE}samples.html"><h3>E. coli samples</h3><p>Lab results sent in by groups, next to what the forecast said.</p></a></div>`
    + `<details class="more" style="margin-top:20px"><summary>Prototypes you can try</summary><div><p><a href="${LIVE}saved/?why=1">What changed since the last forecast</a> · <a href="${LIVE}spot/wye-symonds-yat/?evidence=1">Evidence map</a> · <a href="${LIVE}spot/bw-uke4100-08901/?arrive=1">Arrival guide</a> · <a href="${LIVE}spot/bw-uke4100-08901/?replay=1">Catchment replay</a></p></div></details>`
    + `<details class="more"><summary>Tests and their results</summary><div><p><a href="${LIVE}verification.html">How accurate the forecast is</a> and <a href="https://github.com/ethanbuckley/swimsignal/tree/main/docs">every test's record</a>.</p></div></details>`
    + `<details class="more"><summary>How a prototype becomes part of the forecast</summary><div><p>Each is tested against data it was not built on; the record says what passed and what did not. <a href="${LIVE}research.html">The full Research page</a>.</p></div></details>`
    + `</div>` + nav('more');
}

// ------------------------------------------------------------------------------ satellite explorer (#550 milestone 1)
const STATUS_WORDS = { new_reading: 'a new clear image', no_new_clear_image: 'no new clear image (cloud or no pass)', failed: 'the check failed', partial: 'the check was partial' };
function lakesPage(id, date) {
  const pilotIds = LAKES.pilot.sites;
  const L = LAKES.lakes.find(x => x.lake_id === id) || LAKES.lakes.find(x => x.lake_id === pilotIds[0]);
  const opts = [...pilotIds.map(i => LAKES.lakes.find(x => x.lake_id === i)).filter(Boolean), ...LAKES.lakes.filter(x => !pilotIds.includes(x.lake_id)).sort((a, b) => a.name.localeCompare(b.name))];
  return `<div class="wrap"><a class="back" href="#/research">‹ Research</a><h1>Satellite observations</h1>`
    + `<p class="sub">How green the water looked from space near a point. Not a test for harmful algae or toxins, and not swimming advice.</p>`
    + `<label class="f" for="lake">Lake location</label><select id="lake"><optgroup label="Checked weekly">${opts.slice(0, pilotIds.length).map(x => `<option value="${esc(x.lake_id)}"${x.lake_id === L.lake_id ? ' selected' : ''}>${esc(x.name)}</option>`).join('')}</optgroup>`
    + `<optgroup label="Historical record">${opts.slice(pilotIds.length).map(x => `<option value="${esc(x.lake_id)}"${x.lake_id === L.lake_id ? ' selected' : ''}>${esc(x.name)}</option>`).join('')}</optgroup></select>`
    + `<div id="lakebody" data-lake="${esc(L.lake_id)}" data-date="${esc(date || '')}"><p class="meta">Loading readings…</p></div></div>` + nav('more');
}
async function drawLake(host) {
  const id = host.dataset.lake, want = host.dataset.date;
  const [lake, cores] = await Promise.all([loadLake(id), loadCores()]);
  const op = lake.operation || {}, pilot = LAKES.pilot.sites.includes(id);
  // One reading a date, as lakes.js lakesShown: the contract's `primary` picks it where two images share a date.
  const usable = (lake.series || []).filter(r => r && r.date && typeof r.ndci === 'number' && r.primary !== false).sort((a, b) => a.datetime.localeCompare(b.datetime));
  const latest = usable[usable.length - 1];
  let sel = usable.findIndex(r => r.date === want); if (sel < 0) sel = usable.length - 1;
  const core = cores.features.find(f => f.properties.lake_id === id);
  host.innerHTML = `<p class="level" style="font-size:var(--fs-head);margin-top:16px">Latest usable observation: ${latest ? esc(ukDay(latest.date, { day: 'numeric', month: 'short', year: 'numeric' })) : 'none'}</p>`
    + (latest && (latest.experimental || latest.season !== 'in_season') ? '<p class="fresh"><b>Outside May to September: experimental.</b> The index was tested only in those months.</p>' : '')
    + (pilot ? `<p class="fresh">Last checked ${esc(ukDay(op.last_run_at || op.last_success_at, { day: 'numeric', month: 'short', year: 'numeric' }))}: ${esc(STATUS_WORDS[op.last_status] || op.last_status || 'unknown')}. Checked weekly.</p>`
      : `<p class="fresh">Historical record to ${esc(ukDay(lake.processed_to, { day: 'numeric', month: 'short', year: 'numeric' }))}. Not checked weekly.</p>`)
    + `<div id="map" role="img" aria-label="Map of the 300 metre reading area at ${esc(lake.name)}"></div>`
    + `<p class="meta">Dashed circle: within 300 m of the point. ${core ? `Shaded: the ${core.properties.core_pixels} open-water pixels (20 m) the reading uses.` : 'The open-water pixels used are published for the five weekly lakes only.'}</p>`
    + `<div class="stepper"><button id="prev" aria-label="Earlier usable image">‹</button><div style="text-align:center"><b id="seldate"></b><br><span class="meta" id="selgap"></span></div><button id="next" aria-label="Later usable image">›</button></div>`
    + `<div class="scene"><div class="noimg">No true-colour image saved for this date yet</div><div id="selinfo"></div></div>`
    + `<div id="chartwrap"></div>`
    + `<details class="more" style="margin-top:12px"><summary>Readings as a table</summary><div id="tbl"></div></details>`
    + `<details class="more"><summary>How the readings are made</summary><div><p>${esc(LAKES.claim.definition)}</p><p>${esc(LAKES.claim.public_wording)} Not claimed: ${esc(LAKES.claim.not_claimed.join('; '))}.</p><p>${esc(LAKES.attribution.join(' · '))}</p></div></details>`
    + `<p class="illus" style="margin-top:12px">Images: true-colour pictures of each usable date come with #550 milestone 2 (extracted from Sentinel-2 B4, B3, B2 for the five weekly lakes). Nothing is shown until then.</p>`;
  drawMap(lake, core);
  const show = i => {
    sel = i; const r = usable[i];
    document.getElementById('seldate').textContent = r ? ukDay(r.datetime, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }) : 'No usable image';
    const prev = usable[i - 1];
    document.getElementById('selgap').textContent = r ? `${i + 1} of ${usable.length} usable images${prev ? ` · ${Math.round((Date.parse(r.date) - Date.parse(prev.date)) / 864e5)} days after the one before` : ''}` : '';
    document.getElementById('prev').disabled = i <= 0; document.getElementById('next').disabled = i >= usable.length - 1;
    document.getElementById('selinfo').innerHTML = r ? `<p class="lab meta" style="margin:0">Greenness index (NDCI) <span class="kind">Observed</span></p><p class="val" style="font-size:var(--fs-head);font-weight:600;margin:2px 0">${r.ndci.toFixed(2)}</p>`
      + `<p class="meta" style="margin:0">${r.clear_core} of ${r.n_core} open-water pixels clear · ${esc(ukTime(r.datetime))} UK${r.experimental || r.season !== 'in_season' ? ' · <b>outside May to September: experimental</b>' : ''}</p>`
      + `<p class="meta" style="margin:4px 0 0"><a href="${EARTH_SEARCH}${esc(r.item_id)}" rel="noopener">Scene ${esc(r.item_id)}</a></p>` : '';
    const keyed = document.activeElement && document.activeElement.classList.contains('pt');
    drawChart(usable, i, show);
    if (keyed) document.querySelector(`.chart .pt[data-k="${i}"]`)?.focus();   // the chart is redrawn: keep the keyboard on the chosen dot
    const h = `#/lakes/${encodeURIComponent(id)}${r ? `?date=${r.date}` : ''}`;
    if (location.hash !== h) history.replaceState(null, '', h);
  };
  document.getElementById('prev').onclick = () => show(Math.max(0, sel - 1));
  document.getElementById('next').onclick = () => show(Math.min(usable.length - 1, sel + 1));
  document.getElementById('tbl').innerHTML = `<table class="t"><thead><tr><th>Date</th><th>NDCI</th><th>Clear pixels</th><th>Season</th></tr></thead><tbody>${usable.slice().reverse().map(r => `<tr><td>${esc(r.date)}</td><td>${r.ndci.toFixed(3)}</td><td>${r.clear_core}/${r.n_core}</td><td>${r.season === 'in_season' ? 'May–Sep' : 'outside'}</td></tr>`).join('')}</tbody></table>`;
  if (usable.length) show(sel);
}
// The series for the selected image's year: real dates on the axis, so uneven gaps and missing months show.
function drawChart(usable, i, show) {
  const r = usable[i]; if (!r) return;
  const yr = r.date.slice(0, 4), pts = usable.map((x, k) => ({ x, k })).filter(o => o.x.date.startsWith(yr));
  const t0 = Date.parse(`${yr}-03-01`), t1 = Date.parse(`${yr}-11-30`), W = 340, H = 150, P = { l: 34, r: 8, t: 10, b: 24 };
  const vals = usable.map(x => x.ndci), lo = Math.min(-0.1, ...vals), hi = Math.max(0.2, ...vals);
  const X = d => P.l + (Date.parse(d) - t0) / (t1 - t0) * (W - P.l - P.r), Y = v => P.t + (hi - v) / (hi - lo) * (H - P.t - P.b);
  const months = ['03', '05', '07', '09', '11'].map(m => `<text x="${X(`${yr}-${m}-01`)}" y="${H - 6}" font-size="10" text-anchor="middle" fill="var(--muted)">${ukDay(`${yr}-${m}-15`, { month: 'short' })}</text>`).join('');
  const season = `<rect x="${X(`${yr}-05-01`)}" y="${P.t}" width="${X(`${yr}-10-01`) - X(`${yr}-05-01`)}" height="${H - P.t - P.b}" fill="var(--brand-tint)"/>`;
  const ticks = [lo, 0, hi].map(v => `<text x="${P.l - 4}" y="${Y(v) + 3}" font-size="10" text-anchor="end" fill="var(--muted)">${v.toFixed(1)}</text>`).join('');
  const dots = pts.map(({ x, k }) => `<circle class="pt" data-k="${k}" tabindex="0" role="button" aria-label="${esc(ukDay(x.date, { day: 'numeric', month: 'short' }))}: ${x.ndci.toFixed(2)}" cx="${X(x.date)}" cy="${Y(x.ndci)}" r="${k === i ? 6 : 4}" fill="${x.season === 'in_season' ? 'var(--brand)' : 'var(--card)'}" stroke="var(--brand)" stroke-width="${k === i ? 2.5 : 1.5}"/>`).join('');
  const years = [...new Set(usable.map(x => x.date.slice(0, 4)))];
  document.getElementById('chartwrap').innerHTML = `<div class="chips" role="group" aria-label="Year">${years.map(y => `<button class="chip" data-year="${y}" aria-pressed="${y === yr}">${y}</button>`).join('')}</div>`
    + `<svg class="chart" viewBox="0 0 ${W} ${H}" aria-label="Greenness index through ${yr}; shaded months May to September"><line x1="${P.l}" x2="${W - P.r}" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--line)"/>${season}${months}${ticks}${dots}</svg>`
    + `<p class="meta">Each dot is one usable image; gaps are cloud or no pass, not zero. Hollow: outside May to September, experimental.</p>`;
  document.querySelectorAll('.chart .pt').forEach(c => { const go = () => show(+c.dataset.k); c.addEventListener('click', go); c.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } }); });
  document.querySelectorAll('[data-year]').forEach(b => b.addEventListener('click', () => { const k = usable.map(x => x.date.slice(0, 4)).lastIndexOf(b.dataset.year); if (k >= 0) show(k); }));
}
let MAP = null;
function drawMap(lake, core) {
  if (!window.L) return;
  if (MAP) { MAP.remove(); MAP = null; }
  MAP = L.map('map', { zoomControl: true, attributionControl: true, scrollWheelZoom: false });
  // OpenStreetMap's own tiles for the review build (the live site's CARTO key is tied to its domain).
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' }).addTo(MAP);
  const c = L.circle([lake.lat, lake.lon], { radius: lake.mask?.site_radius_m || 300, color: '#0f5a61', weight: 2, dashArray: '5 5', fill: false }).addTo(MAP);
  if (core) L.geoJSON(core, { style: { color: '#0f5a61', weight: 0, fillOpacity: 0.35 } }).addTo(MAP);
  L.circleMarker([lake.lat, lake.lon], { radius: 4, color: '#fff', weight: 2, fillColor: '#1b2328', fillOpacity: 1 }).addTo(MAP);
  MAP.fitBounds(L.latLng(lake.lat, lake.lon).toBounds(2 * (lake.mask?.site_radius_m || 300)), { padding: [12, 12] });
}

// ------------------------------------------------------------------------------ routing
async function route() {
  const app = document.getElementById('app');
  const [path, qs] = (location.hash.slice(1) || '/explore').split('?');
  const params = new URLSearchParams(qs || ''), parts = path.split('/').filter(Boolean);
  try {
    await loadLite();
    if (parts[0] === 'spot') app.innerHTML = spot(decodeURIComponent(parts[1] || ''));
    else if (parts[0] === 'plan') app.innerHTML = plan(params);
    else if (parts[0] === 'research') { await loadLakes(); app.innerHTML = research(); }
    else if (parts[0] === 'lakes') { await loadLakes(); app.innerHTML = lakesPage(decodeURIComponent(parts[1] || ''), params.get('date')); await drawLake(document.getElementById('lakebody')); }
    else app.innerHTML = explore(params.get('q') || '');
  } catch (e) { app.innerHTML = `<div class="wrap"><p>Could not load the live data: ${esc(e.message)}</p></div>`; }
  bind(parts[0], params);
  if (!parts[0] || parts[0] === 'explore') return;
  window.scrollTo(0, 0);
}
function bind(view, params) {
  const save = document.getElementById('save');
  if (save) save.onclick = () => { const id = location.hash.split('/')[2]; const s = new Set(saved()); s.has(id) ? s.delete(id) : s.add(id); store.set(SAVED_KEY, [...s]); route(); };
  const q = document.getElementById('q');
  if (q) q.oninput = () => { const ql = q.value.trim().toLowerCase(); document.getElementById('hits').innerHTML = hitsHtml(ql ? LITE.spots.filter(s => [s.name, s.area, s.river].join(' ').toLowerCase().includes(ql)).slice(0, 30) : [], ql); };
  if (view === 'plan') {
    const set = (k, v) => { params.set(k, v); if (k === 'spot') params.delete('backup'); params.delete('compare'); location.hash = '#/plan?' + params.toString(); };
    const cur = () => ({ day: document.querySelector('[data-day][aria-pressed=true]')?.dataset.day, when: document.querySelector('[data-when][aria-pressed=true]')?.dataset.when, spot: document.getElementById('pspot').value, backup: document.getElementById('pback').value });
    for (const k of ['day', 'when', 'backup']) document.querySelectorAll(`[data-${k}]`).forEach(b => b.onclick = () => { const c = cur(); for (const [a, v] of Object.entries(c)) params.set(a, v); set(k, b.dataset[k]); });
    document.getElementById('pspot').onchange = e => { const c = cur(); for (const [a, v] of Object.entries(c)) params.set(a, v); set('spot', e.target.value); };
    document.getElementById('pback').onchange = e => { const c = cur(); for (const [a, v] of Object.entries(c)) params.set(a, v); set('backup', e.target.value); };
    document.getElementById('psave').onclick = () => { store.set(PLAN_KEY, cur()); route(); };
  }
  const lake = document.getElementById('lake');
  if (lake) lake.onchange = () => { location.hash = `#/lakes/${encodeURIComponent(lake.value)}`; };
}
window.addEventListener('hashchange', route);
route();
})();
