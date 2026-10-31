// An outing opened from a link is shown, not kept (29 Oct 2026): the plan kept in this browser and the note of
// what its outing showed stay as they are until "Keep this outing". Before, opening a friend's shared outing
// replaced your own without a word. Also: what the outing is for carries into a new plan, a link whose day has
// passed drops its time and stamp, and the privacy notice says what an outing link holds.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const P = require('../src/dipcast/site/plan.js');
const O = require('../src/dipcast/site/outing.js');
const W = require('../src/dipcast/site/outingwatch.js');
const SITE = path.join(__dirname, '../src/dipcast/site');
L.setToday('2026-10-26');   // a Monday
const DATES = ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30'];
const WED = DATES[2];

// Your own outing, kept: Henley on Wednesday morning with a backup. A friend's: Port Meadow on Wednesday, paddling.
const MINE = `#day=${WED}&from=Reading&at=51.45,-0.97&within=20&when=morning&spot=henley&backup=sonning`;
const FRIEND = `#day=${WED}&from=Port+Meadow&at=51.77,-1.28&within=20&when=evening&spot=port-meadow&backup=wolvercote&act=paddle&sent=20261026T0700Z&lv=low&blv=moderate`;
const kept = P.planKept(MINE, DATES);

test('a friend\'s outing from a link is not kept; your own outing opened again is', () => {
  assert.equal(P.planInvited(P.readPlan(FRIEND, DATES), kept, true), true);
  // Nothing kept yet: still shown, not kept, as a shared list is.
  assert.equal(P.planInvited(P.readPlan(FRIEND, DATES), P.planKept(null, DATES), true), true);
  // Your own outing: a reload, Explore's card, or your own shared link (its stamp and start are not the outing).
  assert.equal(P.planInvited(P.readPlan(MINE, DATES), kept, true), false);
  const ownShared = P.planHash(O.outingShared(P.readPlan(MINE, DATES), {name: 'Henley', lat: 51.53, lon: -0.9}, {sent: '20261026T0700Z', lv: 'low', blv: 'low'}));
  assert.equal(P.planInvited(P.readPlan(ownShared, DATES), kept, true), false);
  // A plan with no outing (a town from the list's search) is a new plan you started.
  assert.equal(P.planInvited(P.readPlan('#from=Kendal&at=54.33,-2.75&within=20', DATES), kept, true), false);
  // The header's link in the same visit (no address): still the friend's outing, still not kept.
  assert.equal(P.planInvited(P.readPlan(FRIEND, DATES), kept, false, true), true);
  assert.equal(P.planInvited(P.readPlan(FRIEND, DATES), kept, false, false), false);
  // Its time or what it is for changed in place: still not yours until kept.
  assert.equal(P.planInvited({...P.readPlan(MINE, DATES), when: 'evening'}, kept, true), true);
});

test('what an outing is for carries into a new plan, and changes nothing else', () => {
  const town = {name: 'Ilkley', lat: 53.92, lon: -1.82};
  assert.equal(P.readPlan(P.planFromPlace(town, {...P.PLAN_DEFAULT, act: 'sup'}), DATES).act, 'sup');
  assert.equal('act' in P.readPlan(P.planFromPlace(town, P.PLAN_DEFAULT), DATES), false);
  assert.equal('act' in P.readPlan(P.planFromPlace(town, {...P.PLAN_DEFAULT, act: 'kite'}), DATES), false);
  const area = P.planFromArea({area: 'Oxford', lat: 51.75, lon: -1.25, within: 10}, {day: WED, kind: 'river', act: 'paddle'});
  assert.deepEqual(P.readPlan(area, DATES), {day: WED, from: {name: 'Oxford', lat: 51.75, lon: -1.25}, within: 10, kind: 'river', act: 'paddle'});
});

test('a link whose day has passed is shown for the first day, without its time or its stamp', () => {
  const old = '#day=2026-10-24&from=A&at=51.5,-1.2&spot=a&backup=b&when=morning&sent=20261023T0700Z&lv=very+high&blv=low';
  const p = P.readPlan(old, DATES);
  assert.equal(p.day, DATES[0]);
  for (const k of ['when', 'sent', 'lv', 'blv']) assert.equal(k in p, false, k);
  assert.equal(p.spot, 'a');
  assert.equal(P.planDayOff(old, DATES), '2026-10-24');
  assert.equal(P.planDayOff(FRIEND, DATES), null);
  assert.equal(P.planDayOff('#day=nonsense', DATES), null);
  assert.equal(O.outingOff('2026-10-24', DATES[0]), 'It was for Saturday 24 October, which has passed, so it is shown for today, without its time.');
  assert.match(O.outingOff('2026-11-02', DATES[0]), /Monday 2 November, past the days this forecast covers/);
});

// ------------------------------------------------------------------------------ the tile
const col = (id, name) => ({id, name, href: `spot/${id}/`, tone: 'low', headline: 'Low risk on Wednesday', why: '', ev: '', meta: ''});
const tile = (o = {}) => O.outingSection({day: WED, when: 'evening', spot: 'port-meadow', backup: 'wolvercote', act: 'paddle',
  groups: [], backupGroups: [], main: col('port-meadow', 'Port Meadow'), alt: col('wolvercote', 'Wolvercote'), missing: [],
  issued: '07:00, 2 h ago', open: true, nowMs: new Date(2026, 9, 26, 9).getTime(), ...o});
const BY = new Map([['henley', {id: 'henley', name: 'Henley'}]]);

test('the tile says the outing is not kept, what keeping it replaces, and offers to keep it', () => {
  const mine = O.outingReplaces(kept, BY);
  assert.equal(mine, 'your own outing to Henley on Wednesday');
  const h = tile({shared: 'Mon 07:00', preview: {mine, off: null}});
  assert.match(h, /<summary><span>Outing shared with you/);
  assert.match(h, /Shared with you, from the forecast issued Mon 07:00\. .*Not kept in this browser until you keep it\.<\/p>/);
  assert.match(h, /<button type="button" class="btn" id="outing-keep-it">Keep this outing<\/button>/);
  assert.match(h, /Until then, your own outing to Henley on Wednesday stays as it is\. Keeping this one puts it in its place, in this browser, sent nowhere\./);
  assert.doesNotMatch(h, /becomes your own plan/);
  // Changed in place, the stamp has gone: from a link, still not kept.
  const changed = tile({shared: '', preview: {mine: '', off: null}});
  assert.match(changed, /<summary><span>Outing from a link/);
  assert.match(changed, /From a link\. Not kept in this browser until you keep it\.<\/p>/);
  assert.match(changed, /Keeping it makes it the plan Plan a swim opens on, in this browser, sent nowhere\./);
  // The link's day had passed.
  assert.match(tile({shared: '', day: DATES[0], preview: {mine: '', off: '2026-10-24'}}), /From a link\. It was for Saturday 24 October, which has passed, so it is shown for today, without its time\. Not kept/);
  // Kept: no button, and the shared words say it is kept.
  const keptTile = tile({shared: 'Mon 07:00', preview: null});
  assert.doesNotMatch(keptTile, /outing-keep-it/);
  assert.match(keptTile, /Kept in this browser and in this page's link; sent nowhere\. Change anything here and it becomes your own plan\./);
  // What keeping replaces: a kept plan with no outing, nothing kept, or a kept outing whose day has gone.
  assert.equal(O.outingReplaces(P.planKept('#from=Kendal&at=54.33,-2.75&within=20', DATES), BY), 'the plan kept in this browser');
  assert.equal(O.outingReplaces(P.planKept(null, DATES), BY), '');
  assert.equal(O.outingReplaces(P.planKept(MINE.replace(WED, '2026-10-20'), DATES), BY), 'the plan kept in this browser');   // its day has gone
});

// ------------------------------------------------------------------------------ the note of what the outing showed
// Frensham Great Pond's reviewed notice, so the official-advice line is checked in the preview too.
const APPROVED = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/advisories/approved.json'), 'utf8')).approvals
  .find(a => a.spot_id === 'bw-ukj2310-11945');
const RISK = {low: 0.05, moderate: 0.2, high: 0.5, 'very high': 0.8};
const spot = (id, name, l, extra = {}) => ({id, name, kind: 'lake', source: 'designated', upstream_summary: {overflows: 2}, location: {mode: 'river'},
  now: {label: 'low', risk: 0, discharging_upstream: 0, feed_down_upstream: 0, stale_upstream: 0}, official: [],
  days: DATES.map(date => ({date, label: date === WED ? l : 'low', risk: RISK[date === WED ? l : 'low']})), ...extra});
const frensham = spot('bw-ukj2310-11945', 'Frensham Great Pond', 'high', {official: [{line: APPROVED.line, publisher: APPROVED.publisher,
  link: APPROVED.link, since: APPROVED.start, checked: '2026-10-26', state: 'checked', restricts: true}]});
const henley = spot('henley', 'Henley', 'low');
function store(init) {
  const m = new Map(Object.entries(init));
  return {getItem: k => m.has(k) ? m.get(k) : null, setItem: (k, v) => m.set(k, String(v)), removeItem: k => m.delete(k), m};
}
function draw(plan, pair, preview, st) {
  globalThis.localStorage = st;
  let html = '';
  const tileStub = {querySelector: () => ({insertAdjacentHTML: (_, h) => { html = h; }})};
  W.outingWatchDraw(tileStub, plan, pair, new Date(2026, 9, 26, 9).toISOString(), new Date(2026, 9, 26, 9, 30).getTime(), preview);
  delete globalThis.localStorage;
  return html.replace(/<[^>]+>/g, ' ').replace(/&#39;/g, "'").replace(/\s+/g, ' ');
}

test('a preview leaves the kept note alone and compares only with the link\'s stamp; keeping notes it', () => {
  const mineNote = JSON.stringify({day: WED, items: [W.outingWatchRecord(henley, WED, new Date(2026, 9, 25, 7).toISOString(), Date.now())]});
  const st = store({[W.OUTING_WATCH_KEY]: mineNote});
  const plan = {day: WED, spot: frensham.id};
  const text = draw(plan, {main: frensham, backup: null}, true, st);
  assert.equal(st.getItem(W.OUTING_WATCH_KEY), mineNote);   // your own outing's note, untouched
  assert.match(text, /Nothing is noted in this browser until you keep this outing/);
  assert.match(text, /Official advice: .+ Follow it first\./);   // the notice is said as it is now, first
  assert.match(text, /Level for Wednesday: high risk\./);
  // Stamped by its sender: compared with the stamp, still without writing.
  const sent = draw({...plan, sent: '20261025T0700Z', lv: 'low'}, {main: frensham, backup: null}, true, st);
  assert.equal(st.getItem(W.OUTING_WATCH_KEY), mineNote);
  assert.match(sent, /changed since this outing was shared with you/);
  assert.match(sent, /Level for Wednesday: high risk\. Changed: was low risk\./);
  // Kept: the note becomes this outing's.
  draw(plan, {main: frensham, backup: null}, false, st);
  assert.equal(W.outingWatchRead(st.getItem(W.OUTING_WATCH_KEY)).items[0].id, frensham.id);
});

// ------------------------------------------------------------------------------ the page
test('the page keeps a preview out of storage until Keep this outing', () => {
  const app = fs.readFileSync(path.join(SITE, 'index.html'), 'utf8'), out = fs.readFileSync(path.join(SITE, 'outing.js'), 'utf8');
  assert.match(app, /if \(!PLAN_PREVIEW\) try \{ localStorage\.setItem\(PLAN_KEY, h\); \}/);
  assert.match(app, /PLAN_PREVIEW = planInvited\(PLAN, keptNow, location\.hash\.length > 1, PLAN_PREVIEW\)/);   // and planHere's exception (site_plan_here)
  assert.match(app, /const keepPlan = \(\) => \{ PLAN_PREVIEW = false; planAddress\(\); \};/);
  // A link opened while Plan a swim is open: its day is the link's, not a change of day that drops its time and stamp.
  assert.match(app, /if \(location\.hash\.length > 1 && typeof OUTING_DAY !== 'undefined'\) OUTING_DAY = null;/);
  assert.match(out, /outingWatchDraw\(tile, PLAN, \{ \.\.\.pair, finish: fin \}, DATA\.generated_at, Date\.now\(\), !!preview\)/);
  assert.match(out, /keepPlan\(\); drawOuting\(box, shown\);/);
  // Looking at a friend's outing earns no badge and keeps nothing offline.
  assert.match(out, /if \(pair\.backup && !preview && typeof passportPlanned === 'function'\)/);
  assert.match(out, /if \(typeof OutingPack === 'object' && !preview\) OutingPack\.draw\(\{ \.\.\.pair, finish: fin \}\);/);
});

test('the privacy notice says what an outing link holds and that opening one keeps nothing', () => {
  const privacy = fs.readFileSync(path.join(__dirname, '../src/dipcast/pages/privacy.html'), 'utf8');
  const para = privacy.split('\n').find(l => l.startsWith('<p>"Share this outing"'));
  assert.ok(para, 'the outing link paragraph');
  // Every field the link carries (plan.js, planHash with outingShared's stamp), and what it never does.
  for (const said of ["the outing's day", 'its time', 'its spot and backup spot', 'what it is for', 'where to meet',
    "the forecast's issue time", "each spot's level for that day", 'never holds where you start from', 'no words anyone typed',
    'shows the outing without keeping it', '"Keep this outing"']) assert.ok(para.includes(said), said);
  assert.ok(privacy.includes('Last updated 31 October 2026.'));
});
