// Plan a swim (the plan/ page): the spots within a distance of where you start, on one day, the
// ones nothing flags that day first, then the rest, nearest first. The page draws it (index.html,
// renderPlan); the rules are here, where Node can test them.
//
// A plain script, as levels.js: globals in the page, exports in Node. It asks for the level rules
// when it is called, so in the page it only has to load before it is used.
const planRules = () => typeof dayLevel === 'function' ? { dayLevel, plainLevel, rank, daily, bestDay } : require('./levels.js');

const MILE_KM = 1.609344;
const RADII = [5, 10, 20, 30, 50];   // miles; 0 is any distance
const PLAN_KINDS = ['all', 'river', 'lake', 'designated'];   // as the list's chips (FILTERS)
const PLAN_DEFAULT = { day: null, from: null, within: 20, kind: 'all' };

// ------------------------------------------------------------------------------ the plan in the address
// After the #, so it never reaches a server, and Back, a reload or a copied link opens the same plan:
// plan/#day=2026-10-04&from=Kendal&at=54.33,-2.75&within=20&kind=lake. A place carries its own
// position, so a link opens without the list of places. Your own location is never written there:
// "from=here" asks again on the device that opens it. An address without a plan (the header's link)
// keeps the plan last shown (was); one with a plan is read on its own, so what it leaves out is the
// default, not what happened to be chosen before.
const inGB = (lat, lon) => lat > 49.8 && lat < 61 && lon > -8.7 && lon < 2;
function readPlan(hash, dates, was = PLAN_DEFAULT) {
  const q = new URLSearchParams(String(hash || '').replace(/^#/, ''));
  const p = { ...PLAN_DEFAULT, ...([...q.keys()].length ? { day: was.day } : was) };
  if (dates.includes(q.get('day'))) p.day = q.get('day');
  if (!dates.includes(p.day)) p.day = dates[0];
  const w = q.get('within');
  if (w !== null && (w === '0' || RADII.includes(Number(w)))) p.within = Number(w);
  if (PLAN_KINDS.includes(q.get('kind'))) p.kind = q.get('kind');
  const from = q.get('from'), at = String(q.get('at') || '').split(',').map(Number);
  if (from === 'here') p.from = { here: true };
  else if (from && at.length === 2 && inGB(at[0], at[1])) p.from = { name: from.slice(0, 80), lat: at[0], lon: at[1] };
  return p;
}
function planHash(p) {
  const q = new URLSearchParams();
  if (p.day) q.set('day', p.day);
  if (p.from && p.from.here) q.set('from', 'here');
  else if (p.from) { q.set('from', p.from.name); q.set('at', `${p.from.lat},${p.from.lon}`); }
  q.set('within', String(p.within));
  if (p.kind !== 'all') q.set('kind', p.kind);
  return '#' + q.toString();
}

// ------------------------------------------------------------------------------ places
// data/places.json (scripts/make_places.py): England's and Wales's cities, towns, districts and
// villages from OS Open Names, biggest first. Matched as the list's search matches spots (fold in
// index.html): case, accents and punctuation do not count.
const placeKey = t => String(t ?? '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
const placeIndex = doc => (doc && Array.isArray(doc.places) ? doc.places : [])
  .filter(p => Array.isArray(p) && typeof p[0] === 'string' && inGB(p[1], p[2]))
  .map(([name, lat, lon]) => ({ name, lat, lon, key: placeKey(name), bare: placeKey(name.split(',')[0]) }));
// Up to n places for what has been typed: names that begin with it, then names with a later word
// that does ("Bridge" finds "Pooley Bridge"), each in the file's order.
function placeMatches(index, text, n = 8) {
  const k = placeKey(text); if (!k) return [];
  const first = [], later = [];
  for (const p of index) {
    if (p.key.startsWith(k)) { first.push(p); if (first.length === n) break; }
    else if (later.length < n && p.key.includes(' ' + k)) later.push(p);
  }
  return first.concat(later).slice(0, n);
}
// The place typed, if there is one: the name as offered ("Newport, Isle of Wight"), or a name on its
// own, which is the biggest place of that name. Otherwise null, and the page says it found none.
function placeNamed(index, text) {
  const k = placeKey(text); if (!k) return null;
  return index.find(p => p.key === k) || index.find(p => p.bare === k) || null;
}
// "LA22 9", "SW1A": OS Open Names has postcodes, but not in the file the page fetches.
const looksLikePostcode = text => /^[a-z]{1,2}[0-9][0-9a-z]?(\s*[0-9][a-z]{0,2})?$/i.test(String(text).trim());

// ------------------------------------------------------------------------------ the spots
// Which group a spot is in on the day: 0 when nothing flags it (low risk, or a plain level, where no
// monitored overflow can reach it), 1 at moderate risk or higher (a rating of poor included), 2 with
// no level (no forecast that day, out of the forecast's reach).
function planGroup(level) {
  const R = planRules();
  return level === 'low' || R.plainLevel(level) ? 0 : R.rank(level) >= 1 ? 1 : 2;
}
const kindMatch = (s, kind) => kind === 'all' || (kind === 'designated' ? s.source === 'designated' : s.kind === kind);
// The plan's spots: those of the kind chosen within its distance, in three groups (planGroup), each
// nearest first, the second by its level first. milesOf(s) is the spot's distance from the start.
// With none within reach, the nearest of that kind, so the page can say how far it is.
function planSpots(spots, p, milesOf) {
  const R = planRules(), reach = p.within || Infinity;
  const all = spots.filter(s => kindMatch(s, p.kind)).map(s => ({ s, miles: milesOf(s), level: R.dayLevel(s, p.day) }));
  const near = all.filter(o => o.miles <= reach), groups = [[], [], []];
  for (const o of near) groups[planGroup(o.level)].push(o);
  groups[0].sort((a, b) => a.miles - b.miles);
  groups[1].sort((a, b) => R.rank(a.level) - R.rank(b.level) || a.miles - b.miles);
  groups[2].sort((a, b) => a.miles - b.miles);
  const nearest = near.length ? null : all.reduce((a, b) => !a || b.miles < a.miles ? b : a, null);
  return { groups, count: near.length, nearest };
}
// Another of the five days when clearly more of these spots are at low risk than on the day picked
// (two more, and a quarter more: 19 against 18 is not worth moving a swim for), or null. Only spots
// whose forecast changes from day to day count (bestDay): the rest are the same every day.
function betterDay(spots, day, dates) {
  const R = planRules(), b = R.bestDay(spots, dates);
  if (!b || b.date === day) return null;
  const low = spots.filter(s => R.daily(s) && R.dayLevel(s, day) === 'low').length;
  return b.low >= low + 2 && b.low >= low * 1.25 ? { date: b.date, low: b.low, was: low } : null;
}
// The next distance that reaches a spot this far away, or 0 (any distance).
const reachFor = miles => RADII.find(r => r >= miles) || 0;
const milesAway = m => { if (m < 1) return 'under a mile away'; const n = m < 10 ? Math.round(m * 10) / 10 : Math.round(m);
  return `${n} mile${n === 1 ? '' : 's'} away`; };

if (typeof module === 'object' && module.exports) {
  module.exports = { MILE_KM, RADII, readPlan, planHash, placeKey, placeIndex, placeMatches, placeNamed, looksLikePostcode,
    planGroup, planSpots, betterDay, reachFor, milesAway };
}
