// Named lists of saved spots (the Saved page, saved/), and the links that share a list or a plan.
// The page draws them (index.html, renderSaved and renderShared); the rules are here, where Node can
// test them.
//
// A plain script, as plan.js: globals in the page, exports in Node. Every name here is a global in the
// page, so each is one the page's other scripts do not use.
//
// Kept in this browser's local storage, under 'dipcast.lists':
//   {"v": 1, "current": "l2", "lists": [{"id": "l1", "name": "My spots", "spots": ["wharfe-burnsall"]}, ...]}
// "current" is the list the Saved page shows, and the one Save on a spot's page adds to. Before
// lists (October 2026) the saved spots were one list of ids under 'dipcast.saved'. The page still
// writes that key, as every spot in every list, so that a page from an older build (a tab left open,
// or the offline copy before it updates) and a rolled-back build still see every saved spot.
const listsRules = () => typeof storedList === 'function' ? { storedList } : require('./experience.js');

const LISTS_KEY = 'dipcast.lists';
const FIRST_LIST = 'My spots';       // the name the one list from before lists takes
const SHARED_LIST = 'Shared list';   // a link without a name: the saved/#spots= links made before lists
const LIST_NAME_MAX = 40;            // characters in a list's name
const LINK_SPOTS_MAX = 200;          // spots read from a link (there are about 100 spots in all)
const SPOT_ID_MAX = 100;             // characters in a spot's id, from storage or a link

// ------------------------------------------------------------------------------ reading them safely
// A name as typed, or as a link or storage gives it: text only, control and direction characters
// taken out, spaces collapsed, at most LIST_NAME_MAX characters (counted as a reader sees them, so an
// emoji is not cut in half). Anything but text is no name.
const listName = t => typeof t !== 'string' ? ''
  : Array.from(t.replace(/[\u0000-\u001f\u007f-\u009f\u00ad\u200b-\u200f\u2028-\u202e\u2060-\u2069\ufeff]/g, ' ').replace(/\s+/g, ' ').trim())
    .slice(0, LIST_NAME_MAX).join('').trim();
// Spot ids: text of a sane length, each once, in order.
const listIds = ids => [...new Set((Array.isArray(ids) ? ids : []).filter(id => typeof id === 'string' && id.length > 0 && id.length <= SPOT_ID_MAX))];
const sameListName = (a, b) => a.toLocaleLowerCase('en-GB') === b.toLocaleLowerCase('en-GB');
// A name no other list has: "Weekend", then "Weekend 2", "Weekend 3". except: the list being renamed.
function freeListName(lists, name, except = null) {
  const taken = n => lists.some(l => l.id !== except && sameListName(l.name, n));
  if (!taken(name)) return name;
  for (let k = 2; ; k++) {
    const tail = ` ${k}`, n = Array.from(name).slice(0, LIST_NAME_MAX - tail.length).join('').trim() + tail;
    if (!taken(n)) return n;
  }
}
const freeListId = lists => { let k = 1; while (lists.some(l => l.id === `l${k}`)) k++; return `l${k}`; };

// The lists, from what storage holds: the lists' text (LISTS_KEY) and the old single list's
// ('dipcast.saved'). Nothing saved is lost and nothing stored can stop the page:
// - no lists yet (the first visit since lists came), or lists that cannot be read: the old list
//   becomes the first list, "My spots";
// - a list that is not an object is skipped; a name that is not text reads "My spots"; spots that are
//   not ids are dropped; a list without a usable id gets a new one;
// - a spot in the old list that no list holds is added to the first list. A page from before lists
//   can only have added it, and dropping it would lose a saved spot. A spot missing from the old list
//   is never taken out of a list: the old list may be empty or broken for other reasons.
function readLists(text, savedText) {
  let v = null; try { v = JSON.parse(text || 'null'); } catch (e) { v = null; }
  const lists = [];
  for (const l of v && typeof v === 'object' && Array.isArray(v.lists) ? v.lists : []) {
    if (!l || typeof l !== 'object' || Array.isArray(l)) continue;
    const id = typeof l.id === 'string' && /^[A-Za-z0-9_-]{1,16}$/.test(l.id) && !lists.some(x => x.id === l.id) ? l.id : freeListId(lists);
    lists.push({ id, name: freeListName(lists, listName(l.name) || FIRST_LIST), spots: listIds(l.spots) });
  }
  if (!lists.length) lists.push({ id: 'l1', name: FIRST_LIST, spots: [] });
  const have = new Set(lists.flatMap(l => l.spots));
  for (const id of listIds(listsRules().storedList(savedText))) if (!have.has(id)) { lists[0].spots.push(id); have.add(id); }
  const current = v && typeof v === 'object' && lists.some(l => l.id === v.current) ? v.current : lists[0].id;
  return { current, lists };
}
// What a change to storage holds, if it is lists at all: another tab's write is followed only then.
const listsReadable = text => { try { const v = JSON.parse(text); return !!v && typeof v === 'object' && Array.isArray(v.lists); } catch (e) { return false; } };
const listsText = state => JSON.stringify({ v: 1, current: state.current, lists: state.lists });
// Every saved spot, each once, in the lists' order: the old key, the alerts and the list's Saved group.
const allSaved = state => [...new Set(state.lists.flatMap(l => l.spots))];
const listById = (state, id) => state.lists.find(l => l.id === id) || state.lists[0];
const shownList = state => listById(state, state.current);

// ------------------------------------------------------------------------------ changing them
// Each returns new lists and leaves the old ones as they were.
const withSpots = (state, id, f) => ({ ...state, lists: state.lists.map(l => l.id === id ? { ...l, spots: f(l.spots) } : l) });
// A spot into a list, at a place (Undo puts it back where it was) or at the end; once only.
const addToList = (state, id, spot, at = Infinity) => withSpots(state, id, s => s.includes(spot) ? s : [...s.slice(0, at), spot, ...s.slice(at)]);
const removeFromList = (state, id, spot) => withSpots(state, id, s => s.filter(x => x !== spot));
const moveToList = (state, spot, from, to) => from === to ? state : addToList(removeFromList(state, from, spot), to, spot);
const copyToList = (state, spot, to) => addToList(state, to, spot);
// A new list, shown from now on. A name in use gets a number.
function makeList(state, name, spots = []) {
  const id = freeListId(state.lists);
  return { current: id, lists: [...state.lists, { id, name: freeListName(state.lists, listName(name) || 'New list'), spots: listIds(spots) }] };
}
// A shared list added to my lists (the shared view's Add to my lists). Someone with nothing saved has
// only the empty "My spots" that readLists makes on a first visit; the shared list takes its place, so a
// newcomer from a link has one list, not an empty "My spots" chip beside it (phone audit, 25 Oct 2026).
// Anything saved, another list, or "My spots" renamed: added beside them, as makeList.
function addSharedList(state, name, spots) {
  const only = state.lists.length === 1 ? state.lists[0] : null;
  if (only && !only.spots.length && only.name === FIRST_LIST) return makeList({ current: only.id, lists: [] }, name, spots);
  return makeList(state, name, spots);
}
function renameList(state, id, name) {
  const n = listName(name); if (!n) return state;
  return { ...state, lists: state.lists.map(l => l.id === id ? { ...l, name: freeListName(state.lists, n, id) } : l) };
}
// The last list deleted leaves an empty "My spots", so there is always a list to save to.
function deleteList(state, id) {
  const lists = state.lists.filter(l => l.id !== id);
  if (!lists.length) return { current: 'l1', lists: [{ id: 'l1', name: FIRST_LIST, spots: [] }] };
  return { current: lists.some(l => l.id === state.current) ? state.current : lists[0].id, lists };
}
const pickList = (state, id) => state.lists.some(l => l.id === id) ? { ...state, current: id } : state;
// Spots gone from the forecast, out of every list.
const keepSpots = (state, keep) => ({ ...state, lists: state.lists.map(l => ({ ...l, spots: l.spots.filter(keep) })) });
// A list with this name and these spots, in any order: a shared list already added.
function sameList(state, name, spots) {
  const want = [...new Set(spots)].sort().join('\n');
  return state.lists.find(l => sameListName(l.name, name) && [...l.spots].sort().join('\n') === want) || null;
}

// ------------------------------------------------------------------------------ in a link
// A list in a link: saved/#list=Weekend&spots=wharfe-burnsall,grasmere. A plan's adds its day:
// saved/#list=Plan%20for%20Saturday%2010%20Oct&day=2026-10-10&spots=... The link holds that and
// nothing else: not where a plan starts from, not the other lists. After the #, so it never reaches a
// server. The spots come last, so a link an app cuts short loses spots rather than the name.
function shareHash(name, spots, day = null) {
  return `#list=${encodeURIComponent(listName(name))}${day ? `&day=${day}` : ''}&spots=${listIds(spots).map(encodeURIComponent).join(',')}`;
}
// What a link holds, or null when it is not a list. A link from before lists (#spots=a,b) has no
// name and reads "Shared list". Valid dates outside the forecast window remain as requestedDay;
// malformed dates are ignored. Unreadable names or ids are dropped, and at most LINK_SPOTS_MAX spots are read.
function readShared(hash, dates = []) {
  const parts = String(hash || '').replace(/^#/, '').split('&').map(p => { const i = p.indexOf('='); return i < 0 ? [p, ''] : [p.slice(0, i), p.slice(i + 1)]; });
  const raw = k => { const p = parts.find(([key]) => key === k); return p ? p[1] : null; };
  const dec = s => { try { return decodeURIComponent(s); } catch (e) { return ''; } };
  if (raw('spots') === null) return null;
  const spots = listIds(raw('spots').split(',').map(dec)).slice(0, LINK_SPOTS_MAX);
  const name = listName(dec((raw('list') || '').replace(/\+/g, ' ')));
  const day = raw('day');
  const validDay = /^\d{4}-\d{2}-\d{2}$/.test(day || '') && !Number.isNaN(Date.parse(day)) && new Date(day).toISOString().slice(0, 10) === day;
  return { name: name || SHARED_LIST, spots, day: dates.includes(day) ? day : null,
    ...(validDay && dates.length && !dates.includes(day) ? { requestedDay: day } : {}) };
}
// A list's link, pasted on the Saved page. The Home Screen app on an iPhone has no address bar to open
// a link in, and keeps its lists apart from Safari's (phone audit, 25 Oct 2026), so a link someone sent,
// or one copied with Share this list in Safari, is pasted there and opens as a shared list. Only a
// link to a Saved page of this site that holds a list is taken: { hash } (the part after the #, read
// again by readShared when it is shown), or { why } for anything else. origin: the page's own; a link
// to swimsignal.co.uk is this site's too, wherever the page is served from. The path may be under a
// folder (the site works at any address) and may lack its last slash, as a link typed by hand can.
const PASTE_MAX = 8000;   // characters in a pasted link: a list of every spot (about 100 ids) is under this
const SITE_HOSTS = ['swimsignal.co.uk', 'www.swimsignal.co.uk'];
function pastedList(text, origin) {
  const t = typeof text === 'string' ? text.trim() : '';
  if (!t) return { why: 'empty' };
  if (t.length > PASTE_MAX) return { why: 'long' };
  let u = null, here = null;
  try { u = new URL(t); } catch (e) { return { why: 'notlink' }; }
  try { here = new URL(origin); } catch (e) { here = null; }
  if (!/^https?:$/.test(u.protocol) || !(SITE_HOSTS.includes(u.host) || (here && u.host === here.host))) return { why: 'site' };
  const sh = /\/saved(\/(index\.html)?)?$/.test(u.pathname) ? readShared(u.hash) : null;
  return sh && sh.spots.length ? { hash: u.hash } : { why: 'notlist' };
}
// A list as a sites view (sites.html, sites.js): one printable page with each spot's five days, for a
// centre, a club or a council. sites.html#spots=wharfe-burnsall,grasmere&name=Club%20launches: the spots
// and the name, nothing else, after the # as a shared list's link. Without a name, no name part.
function sitesHash(name, spots) {
  const n = listName(name);
  return `#spots=${listIds(spots).map(encodeURIComponent).join(',')}${n ? `&name=${encodeURIComponent(n)}` : ''}`;
}
// A plan, shared as a list, is named for its day: "Plan for Saturday 10 Oct".
const planListName = iso => 'Plan for ' + new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short' });

// ------------------------------------------------------------------------------ the Saved page as a starting page
// The places on it, grouped (2 Nov 2026): with more than one list, the list shown is the group, under its
// name, since its chips already choose it and Share, Compare and Save act on it; with one list, its spots by
// area, in the order saved inside each area and the areas in the order their first spot was saved.
// spots: [{id, area}], in the list's order. Returns [[heading, spots]]; a spot without an area goes under "Other".
function savedGroups(spots, listNameShown = null) {
  if (listNameShown) return spots.length ? [[listNameShown, spots]] : [];
  const out = new Map();
  for (const s of spots) { const a = s.area || 'Other'; if (!out.has(a)) out.set(a, []); out.get(a).push(s); }
  return [...out];
}
// The spots alerts cover: every saved spot the forecast has, less those turned off one by one (off). The
// browser's record of what it sent (index.html, PUSH_KEY) keeps `off`; the saved lists are untouched.
const alertSpots = (saved, known, off = []) => [...saved].filter(id => known.has(id) && !off.includes(id));
// What a saved spot's card says about alerts, from what the page knows:
//   push, email   the build set up notifications (DATA.push) or email alerts (DATA.email)
//   can           'yes', or why this browser cannot have notifications: 'blocked' (refused in its settings),
//                 'ios' (iPhone or iPad outside the Home Screen app), 'inapp' (Facebook's or Instagram's browser),
//                 'offline' (the offline copy is turned off) or 'none' (no web push)
//   on            notifications on in this browser, off, or null while that is being checked
//   off           this spot turned off on its own
//   down          the alert service did not answer the last change asked of it
// Returns { kind, text, toggle, checked, link }: toggle, a tick for this spot; link, "Set up alerts" to the
// Alerts tile, which holds the consent wording, so nothing is turned on from a card.
function spotAlert({ push = false, email = false, can = 'none', on = null, off = false, down = false } = {}) {
  const r = (kind, text, extra = {}) => ({ kind, text, toggle: false, checked: false, link: false, ...extra });
  if (!push && !email) return r('none', '');
  if (push && can === 'yes' && on === true) {
    const t = { toggle: true, checked: !off };
    if (down) return r('down', 'The alert service did not answer, so alerts for this spot are as they were. Try again later.', t);
    return off ? r('muted', 'No alerts for this spot. Your other saved spots still have them.', t)
      : r('on', 'A notification if it reaches high or very high risk.', t);
  }
  if (down) return r('down', 'The alert service did not answer, so alerts could not be checked. Try again later.', { link: true });
  if (push && can === 'yes') return on === null ? r('checking', '') : r('off', 'Alerts are off.', { link: true });
  if (push && can === 'blocked') return r('blocked', 'Notifications are blocked for this site in your browser settings.', { link: email });
  if (push && !email) return r('unavailable', 'Notifications cannot be had in this browser.', { link: true });
  return r('email', 'Notifications cannot be had in this browser. Alerts by email cover the spots saved when you sign up.', { link: true });
}

if (typeof module === 'object' && module.exports) {
  module.exports = { LISTS_KEY, FIRST_LIST, SHARED_LIST, LIST_NAME_MAX, LINK_SPOTS_MAX, listName, listIds, freeListName, readLists, listsReadable,
    listsText, allSaved, listById, shownList, addToList, removeFromList, moveToList, copyToList, makeList, renameList, deleteList, pickList,
    keepSpots, sameList, shareHash, readShared, PASTE_MAX, pastedList, planListName, sitesHash, addSharedList, savedGroups, alertSpots, spotAlert };
}
