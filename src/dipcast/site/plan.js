// Plan a swim (the plan/ page): the spots within a distance of where you start, on one day, those at
// low risk that day first, then those with no monitored overflow found upstream, then the rest, nearest first. The page draws it (index.html,
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
// An open comparison (Compare these spots) is in it too, as the spots it shows:
// &compare=thames-port-meadow,bw-ukj1403-11947. `compare` is there only while it is open; empty, it is
// open on the first spots shown (planCompareIds).
// An outing's time: a part of the day, or an hour ("07"), as outing.js offers them.
const PLAN_WHEN = /^(morning|afternoon|evening|[01]\d|2[0-3])$/;
// What the outing is for, and where to meet: fixed choices only, never words (docs/SWIM-TOGETHER-2026-10.md,
// decision 1 of 29 Oct 2026), so a link can carry nothing anyone typed. Where to meet is at the spot, as its
// guide gives it: the parking or where you get in.
const OUTING_ACTS = ['swim', 'paddle', 'sup'];
const OUTING_MEETS = ['parking', 'entry'];
const OUTING_FINISH_ACTS = ['paddle', 'sup'];
// In a shared outing (outing.js, outingShared): the forecast it was sent from, as its issue time in UTC to
// the minute ("20261029T1216Z", printed.js's form), and the level the spot and the backup had then, so the
// one who opens it can be told what has changed since; a paddle's finish has its own (flv). Only the levels a spot can have (levels.js).
const PLAN_SENT = /^\d{8}T\d{4}Z$/;
const PLAN_LEVELS = ['low', 'moderate', 'high', 'very high', 'no forecast', 'no overflows', 'not covered', 'no river connection'];
const inGB = (lat, lon) => lat > 49.8 && lat < 61 && lon > -8.7 && lon < 2;
const COMPARE_MAX = 3;
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
  // Ids as lists.js reads a link's (listIds: text of a sane length, each once), at most three.
  if (q.has('compare')) p.compare = [...new Set(q.get('compare').split(',').filter(id => id && id.length <= 100))].slice(0, COMPARE_MAX);
  // An outing (outing.js): when on the day, the spot, and a backup spot, each only where the address has
  // it, so a plan from before 27 Oct 2026 (an old link, or the copy kept in dipcast.plan) reads as it did.
  const when = q.get('when'), one = id => typeof id === 'string' && id.length > 0 && id.length <= 100;
  if (PLAN_WHEN.test(when || '')) p.when = when;
  if (one(q.get('spot'))) p.spot = q.get('spot');
  if (one(q.get('backup')) && q.get('backup') !== p.spot) p.backup = q.get('backup');
  if (OUTING_ACTS.includes(q.get('act'))) p.act = q.get('act');
  // A paddle's finish (stretches.py; outing.js, outingStretch): another listed spot, read only for a paddle or a board.
  if (p.spot && OUTING_FINISH_ACTS.includes(p.act) && one(q.get('finish')) && q.get('finish') !== p.spot) p.finish = q.get('finish');
  if (p.spot && OUTING_MEETS.includes(q.get('meet'))) p.meet = q.get('meet');
  // A send's stamp only with a spot to say it of; each level only with its spot.
  if (p.spot && PLAN_SENT.test(q.get('sent') || '')) {
    p.sent = q.get('sent');
    if (PLAN_LEVELS.includes(q.get('lv'))) p.lv = q.get('lv');
    if (p.backup && PLAN_LEVELS.includes(q.get('blv'))) p.blv = q.get('blv');
    if (p.finish && PLAN_LEVELS.includes(q.get('flv'))) p.flv = q.get('flv');
  }
  // A day the address names that is not one of the five (a shared outing opened after its day): the plan is
  // shown for the first day, so the time and the stamp, which were that day's, go, as planKept drops them.
  if (planDayOff(hash, dates)) { delete p.when; delete p.sent; delete p.lv; delete p.blv; delete p.flv; }
  return p;
}
// That day, if the address names one outside the five; else null. The page says so on an outing from a link.
const PLAN_ISO = /^\d{4}-\d{2}-\d{2}$/;
function planDayOff(hash, dates) {
  const d = new URLSearchParams(String(hash || '').replace(/^#/, '')).get('day');
  return PLAN_ISO.test(d || '') && !dates.includes(d) ? d : null;
}
function planHash(p) {
  const q = new URLSearchParams();
  if (p.day) q.set('day', p.day);
  if (p.from && p.from.here) q.set('from', 'here');
  else if (p.from) { q.set('from', p.from.name); q.set('at', `${p.from.lat},${p.from.lon}`); }
  q.set('within', String(p.within));
  if (p.kind !== 'all') q.set('kind', p.kind);
  if (Array.isArray(p.compare)) q.set('compare', p.compare.join(','));
  if (p.when) q.set('when', p.when);
  if (p.spot) q.set('spot', p.spot);
  if (p.backup) q.set('backup', p.backup);
  if (p.act) q.set('act', p.act);
  if (p.finish) q.set('finish', p.finish);
  if (p.meet) q.set('meet', p.meet);
  if (p.sent) q.set('sent', p.sent);
  if (p.lv) q.set('lv', p.lv);
  if (p.blv) q.set('blv', p.blv);
  if (p.flv) q.set('flv', p.flv);
  return '#' + q.toString();
}
// The plan kept in this browser (index.html, PLAN_KEY: planHash's string for the plan last shown), as the
// first plan a page shows, so after a reload or on a later visit the header's link does not open an empty
// plan. It is read as an address is, so it never holds your own position. Its day only while it is one of the
// five, and a day picked on the list in this visit (listDay) before it; else none, which readPlan makes the
// first day.
function planKept(hash, dates, listDay = null) {
  const p = readPlan(hash || '', dates), d = new URLSearchParams(String(hash || '').replace(/^#/, '')).get('day');
  const day = dates.includes(listDay) ? listDay : dates.includes(d) ? d : null;
  // An outing's time was for its own day: on another day it is dropped, and its spots kept.
  if (p.when && day !== d) delete p.when;
  if (p.sent && day !== d) { delete p.sent; delete p.lv; delete p.blv; delete p.flv; }   // the levels sent were that day's
  return { ...p, day };
}
// The outing to come back to on Explore (index.html, outingResume): the kept plan's spot, backup, time and
// activity, only while its own day is one of the five days and its spot is still listed (has: an id is on the
// list), and while it has a starting place. The kept plan itself, not a new one: its address opens Plan a swim
// on it. Null for anything else.
function planOuting(hash, dates, has = () => true) {
  const d = new URLSearchParams(String(hash || '').replace(/^#/, '')).get('day');
  if (!dates.includes(d)) return null;   // no day kept, or a day gone by
  const p = planKept(hash, dates);
  if (!p.spot || !has(p.spot)) return null;
  if (!p.from) return null;   // Plan a swim draws an outing only under a starting place: without one its link would open an empty plan
  const backup = p.backup && has(p.backup) ? p.backup : null;
  return { day: d, spot: p.spot, backup, when: p.when || null, act: p.act || null, hash: planHash(backup ? p : { ...p, backup: undefined }) };
}
// An outing opened from a link is shown, not kept (index.html, PLAN_PREVIEW): the plan kept in this browser, and
// what its outing has noted (outingwatch.js), stay as they are until "Keep this outing" (29 Oct 2026). Before,
// opening a friend's outing replaced your own without a word, as the browser keeps one plan. An outing is the
// plan's day, spot, backup, time, what for, where to meet and a paddle's finish (planOutingKey); the stamp and where the plan starts
// from are not part of it, so your own outing opened again (a reload, Explore's card, your own shared link) is not
// a new one. plan: the plan about to be shown; kept: planKept's; address: the address it came from had an outing;
// was: this page's plan was already one.
const planOutingKey = p => p && p.spot ? [p.day, p.spot, p.backup, p.when, p.act, p.meet, p.finish].map(x => x || '').join('|') : '';
const planInvited = (plan, kept, address, was = false) => !!plan.spot && planOutingKey(plan) !== planOutingKey(kept) && (address || was);
// ------------------------------------------------------------------------------ what you do on the water
// An optional choice on the Saved page (index.html, actsChips): swimming, paddling and paddleboarding, any of them, kept in
// this browser (ACTS_KEY) and sent nowhere. It changes what is offered first (a new outing's activity, finishes downstream
// for a paddle, the access a paddle needs), never a level: the forecast is for the water, whoever is in it.
const ACTS_KEY = 'dipcast.acts';
function readActs(raw) {
  let v; try { v = JSON.parse(raw || '[]'); } catch (e) { return []; }
  return Array.isArray(v) ? OUTING_ACTS.filter(a => v.includes(a)) : [];
}
// The activity a new outing starts with: the one boat or board chosen ('paddle' over 'sup' when both), else none (a swim).
const actDefault = acts => acts.includes('paddle') ? 'paddle' : acts.includes('sup') ? 'sup' : null;

// "Plan a swim here", on a spot's page (index.html, actions): the plan with that spot as the outing's, starting
// from the spot (as a shared outing does: outing.js, outingShared), on the day the page shows if it is one of the
// five, else the plan's own day. How far, the kind and what the outing is for carry over from base (the plan kept).
// The planner is the one Plan a swim already is: nothing new is drawn for it.
// finish: a listed spot downstream (a paddle's, stretches.py), only with a boat or board.
function planFromSpot(s, base, day = null, finish = null) {
  const act = OUTING_ACTS.includes(base.act) ? base.act : null;
  return planHash({ ...PLAN_DEFAULT, day: day || base.day, within: base.within || PLAN_DEFAULT.within,
    from: { name: s.name, lat: s.lat, lon: s.lon }, spot: s.id, ...(act ? { act } : {}),
    ...(finish && OUTING_FINISH_ACTS.includes(act) ? { finish } : {}) });
}
// Whether the plan kept here holds an outing that is still to come (its day one of the five, with a spot), which a
// new outing started here would replace: then it waits for "Keep this outing", as one from a link does.
const planHasOuting = (kept, dates) => !!(kept && kept.spot && dates.includes(kept.day));
// A plan from a town typed in the list's search (index.html, offerOnMap), as the address says it: a search
// for "Ilkley" lists the one spot named for it, and Plan a swim should not want the town typed again. base:
// the plan to start from (the one shown last, or planKept), for how far and its day; kind: the list's chip,
// as the plan's kinds are the same. A comparison was of other spots, so it is left out. What the outing is for
// (act) carries over, so a paddler's next plan starts as paddling; it changes only the outing's words, never a level.
function planFromPlace(place, base, kind = 'all') {
  return planHash({ ...PLAN_DEFAULT, day: base.day, within: base.within, kind: PLAN_KINDS.includes(kind) ? kind : 'all',
    from: { name: place.name, lat: place.lat, lon: place.lon }, ...(OUTING_ACTS.includes(base.act) ? { act: base.act } : {}) });
}
// The spots a comparison shows, as ids: those asked for (the address, or the choices made) that the plan
// still shows, in the order asked; with fewer than two of those, the first spots shown fill it to three,
// as many as there are. shown: the plan's spots in the order on the page. So a link opens on the same
// spots while they are within reach, and a wider or narrower plan never leaves an empty table.
function planCompareIds(asked, shown) {
  const ids = shown.map(s => s.id), keep = [...new Set(asked || [])].filter(id => ids.includes(id)).slice(0, COMPARE_MAX);
  if (keep.length >= 2) return keep;
  for (const id of ids) { if (keep.length >= COMPARE_MAX) break; if (!keep.includes(id)) keep.push(id); }
  return keep;
}
// The line most of a plan's rows share, if two or more do, said once under the count (index.html, planBasis)
// rather than the same sentence under each of eight Oxford rows. lines: one a row, in the page's order, ''
// for a row with none (no forecast). A tie goes to the earlier row's line. n: the rows that share it; m: the
// rows with a line at all.
function planShared(lines) {
  const tally = new Map(), m = lines.filter(Boolean).length;
  for (const l of lines) if (l) tally.set(l, (tally.get(l) || 0) + 1);
  const [line, n] = [...tally].sort((x, y) => y[1] - x[1])[0] || ['', 0];
  return n >= 2 ? { line, n, m } : { line: '', n: 0, m };
}
// Who it is said of, of the `of` rows shown. Counted among the rows with a forecast where some have none, so
// that "2 of these 5 spots" does not leave the reader to work out which two.
function planSharedWho(n, m, of) {
  const spots = m === of ? 'spots' : 'spots with a forecast';
  return n < m ? `${n} of ${m === of ? 'these' : 'the'} ${m} ${spots}` : n === 2 ? `Both ${spots}` : `All ${n} ${spots}`;
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
// The place typed in full when it is the only one offered (offers: placeMatches's): there is nothing left to
// choose, so the plan can start as if it had been picked (index.html, planType). Typing "Ilkley" whole leaves
// one offer, "Ilkley", and on an iPhone tapping it changes nothing in the field, so no plan would start until
// Search was pressed. Null while another place begins with what is typed.
const placeOnly = (offers, text) => offers.length === 1 && offers[0].key === placeKey(text) ? offers[0] : null;

// ------------------------------------------------------------------------------ rivers and lakes
// data/waters.json (scripts/make_waters.py): OS Open Rivers' named rivers and the WFD lakes in England,
// longest first. The home page's search offers them on the map (index.html, offerOnMap).
const WATER_WORDS = new Set(['river', 'afon', 'beck', 'brook', 'water', 'the', 'stream', 'lake', 'mere', 'tarn', 'reservoir', 'of', 'and', 'at', 'near']);
const waterIndex = doc => (doc && Array.isArray(doc.waters) ? doc.waters : [])
  .filter(w => Array.isArray(w) && typeof w[0] === 'string' && inGB(w[8], w[9]))
  .map(([name, alt, kind, near, s, west, n, e, lat, lon, km]) => ({ name, alt: alt || '', kind: kind === 'lake' ? 'lake' : 'river', near,
    box: [[s, west], [n, e]], lat, lon, km,
    own: placeKey(`${name} ${alt || ''}`).split(' '), all: placeKey(`${name} ${alt || ''} ${near}`).split(' ') }));
// Up to n waters for what has been typed: each word typed begins a word of the name, its other name or the
// town it is near ("kennet", "river kennet", "derwent malton"), and one that is not a generic word
// (WATER_WORDS) begins a word of the name itself, so "river" alone, or a town's name alone, finds none:
// a town is offered as a place. In the file's order, the longest first.
function waterMatches(index, text, n = 4) {
  const typed = placeKey(text).split(' ').filter(Boolean), own = typed.filter(t => !WATER_WORDS.has(t));
  if (own.join('').length < 3) return [];
  const out = [];
  for (const w of index) {
    if (typed.every(t => w.all.some(x => x.startsWith(t))) && own.some(t => w.own.some(x => x.startsWith(t)))) {
      out.push(w); if (out.length === n) break; }
  }
  return out;
}

// ------------------------------------------------------------------------------ the spots
// Which group a spot is in on the day: 0 at low risk, 1 at a plain level (no monitored overflow found
// upstream, so nothing to forecast from), 2 at moderate risk or higher (a rating of poor included), 3
// with no level (no forecast that day, out of the forecast's reach). The first two are apart: as one
// group, "Nothing flagged", they read as the same answer, a forecast that looked and found the risk low
// and one with nothing to look at.
const PLAN_GROUPS = 4;
// Whether a spot has reviewed official advice shown that restricts swimming (eatoday.js, eaTodayRestricts:
// spots.json `official`, all but a notice marked not restricting). It
// never changes the level or the group; within the low group and the plain one, those spots go last, and
// they are not counted as low risk where the plan suggests an area or a day, or shared as a plan.
const planAdvised = s => { const f = typeof eaTodayRestricts === 'function' ? eaTodayRestricts
  : typeof require === 'function' ? require('./eatoday.js').eaTodayRestricts : null;
  return !!f && f(s); };
function planGroup(level) {
  const R = planRules();
  return level === 'low' ? 0 : R.plainLevel(level) ? 1 : R.rank(level) >= 1 ? 2 : 3;
}
const kindMatch = (s, kind) => kind === 'all' || (kind === 'designated' ? s.source === 'designated' : s.kind === kind);
// The plan's spots: those of the kind chosen within its distance, in four groups (planGroup), each
// nearest first, the moderate-or-higher one by its level first. milesOf(s) is the spot's distance from the start.
// With none within reach, the nearest of that kind, so the page can say how far it is.
function planSpots(spots, p, milesOf) {
  const R = planRules(), reach = p.within || Infinity;
  const all = spots.filter(s => kindMatch(s, p.kind)).map(s => ({ s, miles: milesOf(s), level: R.dayLevel(s, p.day) }));
  const near = all.filter(o => o.miles <= reach), groups = Array.from({ length: PLAN_GROUPS }, () => []);
  for (const o of near) groups[planGroup(o.level)].push(o);
  for (const g of groups) g.sort((a, b) => a.miles - b.miles);
  for (const g of [groups[0], groups[1]]) g.sort((a, b) => planAdvised(a.s) - planAdvised(b.s) || a.miles - b.miles);
  groups[2].sort((a, b) => R.rank(a.level) - R.rank(b.level) || a.miles - b.miles);
  const nearest = near.length ? null : all.reduce((a, b) => !a || b.miles < a.miles ? b : a, null);
  return { groups, count: near.length, nearest };
}
// Another of the five days when clearly more of these spots are at low risk than on the day picked
// (two more, and a quarter more: 19 against 18 is not worth moving a swim for), or null. Only spots
// whose forecast changes from day to day count (bestDay): the rest are the same every day.
// Spots with official advice are left out of both counts (planAdvised).
function betterDay(spots, day, dates) {
  spots = spots.filter(s => !planAdvised(s));
  const R = planRules(), b = R.bestDay(spots, dates);
  if (!b || b.date === day) return null;
  const low = spots.filter(s => R.daily(s) && R.dayLevel(s, day) === 'low').length;
  return b.low >= low + 2 && b.low >= low * 1.25 ? { date: b.date, low: b.low, was: low } : null;
}
// The next distance that reaches a spot this far away, or 0 (any distance).
const reachFor = miles => RADII.find(r => r >= miles) || 0;

// ------------------------------------------------------------------------------ where a plan starts
// Where a plan starts when neither its address nor the plan kept in this browser names a place: your position
// if this page already has it, because "Near me" on the list took it (here); else nowhere, and the page
// suggests areas (planAreas). The page never asks for a position to start a plan: a prompt nobody asked for is
// hostile, and the privacy notice promises it only on "Near me" or "Use my location". The position is kept
// in no storage, as the notice says, so a new page load starts without it.
const planStart = (from, here) => from || (Array.isArray(here) && here.length === 2 ? { here: true } : null);
// The areas (spots.csv's `area`) with the most spots of the plan's kind at low risk on its day (official advice
// not counted as low: planAdvised), most first, then
// by name: at most n, and only those with one or more at low risk. Each as a place to start a plan from: the
// middle of its spots (mean position, rounded for the address), and the distance that reaches all of them,
// at most the longest offered so a plan from the middle of a wide area still has a ring. None while any spot
// has no area, as the list's A-Z groups. milesBetween(a, b): straight-line miles between [lat, lon] pairs.
function planAreas(spots, p, milesBetween, n = 3) {
  const R = planRules(), xs = spots.filter(s => kindMatch(s, p.kind));
  if (!xs.length || spots.some(s => !s.area)) return [];
  const by = new Map();
  for (const s of xs) { if (!by.has(s.area)) by.set(s.area, []); by.get(s.area).push(s); }
  const mean = v => v.reduce((a, b) => a + b, 0) / v.length, round = x => Math.round(x * 1e4) / 1e4;
  return [...by].map(([area, ys]) => {
    const lat = round(mean(ys.map(s => s.lat))), lon = round(mean(ys.map(s => s.lon)));
    const far = Math.max(...ys.map(s => milesBetween([lat, lon], [s.lat, s.lon])));
    return { area, lat, lon, total: ys.length, low: ys.filter(s => R.dayLevel(s, p.day) === 'low' && !planAdvised(s)).length,
      within: reachFor(far) || RADII[RADII.length - 1] };
  }).filter(a => a.low > 0).sort((a, b) => b.low - a.low || a.area.localeCompare(b.area)).slice(0, n);
}
// The address of a plan from one of those areas: the plan as it stands, from the area's middle, at its distance.
const planFromArea = (a, p) => planHash({ day: p.day, kind: p.kind, within: a.within, from: { name: a.area, lat: a.lat, lon: a.lon },
  ...(OUTING_ACTS.includes(p.act) ? { act: p.act } : {}) });
const milesAway = m => { if (m < 1) return 'under a mile away'; const n = m < 10 ? Math.round(m * 10) / 10 : Math.round(m);
  return `${n} mile${n === 1 ? '' : 's'} away`; };

if (typeof module === 'object' && module.exports) {
  module.exports = { MILE_KM, RADII, COMPARE_MAX, PLAN_WHEN, PLAN_DEFAULT, OUTING_ACTS, OUTING_MEETS, OUTING_FINISH_ACTS, PLAN_SENT, PLAN_LEVELS, readPlan, planDayOff, planHash, planKept, planOuting, planOutingKey, planInvited, planFromSpot, planHasOuting, ACTS_KEY, readActs, actDefault, planFromPlace, planCompareIds, planShared, planSharedWho, placeKey, placeIndex, placeMatches, placeNamed, placeOnly, looksLikePostcode, waterIndex, waterMatches,
    planGroup, planAdvised, planSpots, betterDay, reachFor, milesAway, planStart, planAreas, planFromArea };
}
