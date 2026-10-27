// A plan's outing (src/dipcast/site/outing.js, with plan.js's address): when on the day, the spot and a
// backup, kept in the plan's address and its copy in dipcast.plan; and the tile that shows the two side by side.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const P = require('../src/dipcast/site/plan.js');
const O = require('../src/dipcast/site/outing.js');
L.setToday('2026-10-31');   // a Saturday
const DATES = ['2026-10-31', '2026-11-01', '2026-11-02', '2026-11-03', '2026-11-04'];
const FROM = {name: 'Oxford', lat: 51.752, lon: -1.2577};

// ------------------------------------------------------------------------------ the address and storage
test('a plan from before outings reads exactly as it did, in the address and in dipcast.plan', () => {
  // Strings as the page wrote them before 27 Oct 2026 (planHash), unchanged.
  const old = '#day=2026-11-01&from=Oxford&at=51.752%2C-1.2577&within=30&compare=a%2Cb';
  const read = P.readPlan(old, DATES);
  assert.deepEqual(read, {day: '2026-11-01', from: FROM, within: 30, kind: 'all', compare: ['a', 'b']});
  assert.equal(P.planHash(read), old);   // written back the same: no new keys for a plan without an outing
  assert.deepEqual(P.planKept(old, DATES), read);
  // Nothing kept, or rubbish kept: the default plan, never an error.
  for (const kept of [null, '', 'not a hash', '#when=dawn&spot=&backup=' + 'x'.repeat(101)]) {
    const p = P.planKept(kept, DATES);
    assert.equal('when' in p || 'spot' in p || 'backup' in p, false, String(kept));
  }
});

test('an outing survives the address: when, the spot and the backup', () => {
  const plan = {day: '2026-10-31', from: FROM, within: 20, kind: 'all', when: 'morning', spot: 'thames-port-meadow', backup: 'bw-ukj1403-11947'};
  const hash = P.planHash(plan);
  assert.match(hash, /&when=morning&spot=thames-port-meadow&backup=bw-ukj1403-11947$/);
  assert.deepEqual(P.readPlan(hash, DATES), plan);
  assert.deepEqual(P.readPlan(P.planHash({...plan, when: '07'}), DATES).when, '07');
  // The header's link (no hash) keeps the outing last shown, as it keeps the rest of the plan.
  assert.deepEqual(P.readPlan('', DATES, plan), plan);
  // A link from a town or an area is a new plan: no outing from before.
  assert.doesNotMatch(P.planFromPlace({name: 'Ilkley', lat: 53.92, lon: -1.82}, plan), /when|spot|backup/);
});

test('an odd outing in the address is dropped, not trusted', () => {
  const r = h => P.readPlan('#from=Oxford&at=51.752,-1.2577&' + h, DATES);
  assert.equal(r('when=dawn').when, undefined);
  assert.equal(r('when=24').when, undefined);
  assert.equal(r('when=7').when, undefined);   // hours are two digits
  assert.equal(r('when=21').when, '21');
  assert.equal(r('spot=' + 'x'.repeat(101)).spot, undefined);
  assert.equal(r('spot=').spot, undefined);
  // A backup the same as the spot is no backup.
  assert.deepEqual([r('spot=a&backup=a').spot, r('spot=a&backup=a').backup], ['a', undefined]);
});

test('a kept outing time is for its own day: on another day it is dropped and its spots kept', () => {
  const kept = '#day=2026-10-28&from=Oxford&at=51.752%2C-1.2577&within=20&when=evening&spot=a&backup=b';   // a day gone by
  const p = P.planKept(kept, DATES);
  assert.equal(p.day, null);
  assert.equal(p.when, undefined);
  assert.deepEqual([p.spot, p.backup], ['a', 'b']);
  // Still among the five days: kept whole. A day picked on the list instead: the time goes.
  assert.equal(P.planKept(kept.replace('2026-10-28', '2026-11-01'), DATES).when, 'evening');
  assert.equal(P.planKept(kept.replace('2026-10-28', '2026-11-01'), DATES, '2026-11-02').when, undefined);
});

test('a day changed in the page drops the time and keeps the spot and the backup', () => {
  const plan = {day: '2026-11-01', from: FROM, within: 20, kind: 'all', when: 'evening', spot: 'a', backup: 'b'};
  assert.equal(O.outingForDay(plan, null), plan);   // the first draw changes nothing
  assert.equal(O.outingForDay(plan, '2026-11-01'), plan);   // the same day
  assert.deepEqual(O.outingForDay(plan, '2026-10-31'), {day: '2026-11-01', from: FROM, within: 20, kind: 'all', spot: 'a', backup: 'b'});
  const {when, ...none} = plan;
  assert.equal(O.outingForDay(none, '2026-10-31'), none);   // no time: nothing to drop
});

// ------------------------------------------------------------------------------ words for the time
test('the time in words, and what it does not mean', () => {
  assert.equal(O.outingWhen('2026-10-31', 'morning'), 'this morning');
  assert.equal(O.outingWhen('2026-11-01', 'evening'), 'tomorrow evening');
  assert.equal(O.outingWhen('2026-11-02', 'afternoon'), 'Monday afternoon');
  assert.equal(O.outingWhen('2026-11-02', '07'), 'Monday at 07:00');
  assert.equal(O.outingWhen('2026-11-02', undefined), 'Monday');
  // One level a day: said whenever a time is picked; nothing said without one.
  const at = h => new Date(2026, 9, 31, h, 30).getTime();
  // The daily caveat stays with no time picked (after a day change drops it, say).
  assert.deepEqual(O.outingTimeNote('2026-10-31', undefined, at(9)), ['The forecast gives one level for the whole of today; it does not change between morning and evening.']);
  assert.deepEqual(O.outingTimeNote('2026-11-02', 'morning', at(9)),
    ['The forecast gives one level for the whole of Monday; it does not change between morning and evening.']);
  // Today, after the time: said so. During it, or another day: not.
  assert.match(O.outingTimeNote('2026-10-31', 'morning', at(13)).join(' '), /That time has already passed today\./);
  assert.doesNotMatch(O.outingTimeNote('2026-10-31', 'morning', at(11)).join(' '), /passed/);
  assert.match(O.outingTimeNote('2026-10-31', '07', at(8)).join(' '), /passed/);
  assert.doesNotMatch(O.outingTimeNote('2026-11-01', '07', at(8)).join(' '), /passed/);
});

// ------------------------------------------------------------------------------ which spots
const spot = (id, name) => ({id, name});
const BY = new Map(['a', 'b', 'c', 'd'].map(id => [id, spot(id, id.toUpperCase())]));

test('backups on offer: saved spots first, then the plan\'s, each once, without the outing\'s own spot', () => {
  const shown = [BY.get('a'), BY.get('b'), BY.get('c')];
  const o = O.outingOptions(shown, new Set(['c', 'd', 'gone']), BY);
  assert.deepEqual(o.map(([h, g]) => [h, g.map(s => s.id)]), [['Your saved spots', ['c', 'd']], ['In this plan', ['a', 'b']]]);
  const b = O.outingOptions(shown, new Set(['c', 'd']), BY, 'c');
  assert.deepEqual(b.map(([h, g]) => [h, g.map(s => s.id)]), [['Your saved spots', ['d']], ['In this plan', ['a', 'b']]]);
  // Nothing saved: only the plan's; an empty group is left out.
  assert.deepEqual(O.outingOptions(shown, new Set(), BY).map(([h]) => h), ['In this plan']);
});

test('spots no longer listed are named as missing, not dropped silently', () => {
  assert.deepEqual(O.outingPair({spot: 'a', backup: 'b'}, BY), {main: BY.get('a'), backup: BY.get('b'), missing: []});
  assert.deepEqual(O.outingPair({spot: 'a', backup: 'zz'}, BY), {main: BY.get('a'), backup: null, missing: ['zz']});
  assert.deepEqual(O.outingPair({}, BY), {main: null, backup: null, missing: []});
});

// ------------------------------------------------------------------------------ the tile
const col = (id, name, extra = {}) => ({id, name, href: `spot/${id}/#day=2026-11-01`, tone: 'low', headline: 'Low risk tomorrow',
  why: '1 overflow upstream may spill tomorrow.', ev: '<p class="ev-line">Thames Water warnings: …</p>', meta: '3.2 miles away · River', ...extra});
const tile = (o = {}) => O.outingSection({day: '2026-11-01', when: 'evening', spot: 'a', backup: 'b',
  groups: [['In this plan', [BY.get('a'), BY.get('b')]]], backupGroups: [['In this plan', [BY.get('b')]]],
  main: col('a', 'Port Meadow'), alt: col('b', 'Wolvercote <Mill>', {tone: 'moderate', headline: 'Moderate risk tomorrow'}),
  missing: [], issued: '15:29, 2 h ago', open: true, nowMs: new Date(2026, 9, 31, 9).getTime(), ...o});

test('the spot and its backup side by side for the day, each with what its level rests on', () => {
  const h = tile();
  assert.match(h, /<details class="sec tile outing" id="outing" open>/);
  // Closed, the summary still names the spot and the backup.
  assert.match(h, /<summary><span>Your outing<span class="k">Port Meadow, backup Wolvercote &lt;Mill&gt;<\/span><\/span><\/summary>/);
  assert.match(h, /<p class="outing-said">Tomorrow evening: your spot and a backup, side by side\.<\/p>/);
  assert.match(h, /<div class="outing-pair">.*Your spot.*Port Meadow.*Low risk tomorrow.*Backup.*Wolvercote &lt;Mill&gt;.*Moderate risk tomorrow/s);
  assert.equal((h.match(/class="ev-line"/g) || []).length, 2);   // the evidence under each
  assert.match(h, /Issued 15:29, 2 h ago\./);
  assert.match(h, /one level for the whole of tomorrow/);
  // Never a claim of safety: "safe" appears only in the sentence that says a lower level is not it.
  assert.deepEqual(h.match(/[^.>]*\bsafe\b[^.<]*/g).map(x => x.trim()), ['A lower forecast level does not mean safe water: check the signs at the water before you swim']);
  // The choices, as selects, the saved ones chosen.
  assert.match(h, /<select data-outing="when">.*<option value="evening" selected>Evening<\/option>.*<option value="07">07:00<\/option>/s);
  assert.match(h, /<select data-outing="backup"><option value="">No backup<\/option><optgroup label="In this plan"><option value="b" selected>B<\/option>/);
  assert.match(h, /sent nowhere/);
});

test('one spot alone takes the width; none yet asks for one; a missing one is said', () => {
  const one = tile({alt: null, backup: undefined});
  assert.match(one, /<div class="outing-pair one">/);
  assert.doesNotMatch(one, /Backup<\/p>/);
  assert.match(one, /Tomorrow evening: your spot\.<\/p>/);
  const none = tile({main: null, alt: null, spot: undefined, open: false});
  assert.match(none, /<details class="sec tile outing" id="outing"><summary><span>Your outing<\/span><\/summary>/);
  assert.match(none, /Choose a spot to see it here/);
  assert.doesNotMatch(none, /outing-pair/);
  assert.match(tile({missing: ['zz']}), /A spot in this outing is no longer listed, so it is left out\./);
});

test('the page loads outing.js after plan.js, and the plan draws it', () => {
  const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  assert.ok(page.indexOf('<script src="plan.js"></script>') < page.indexOf('<script src="outing.js"></script>'));
  assert.match(page, /typeof drawOuting === 'function'\) drawOuting\(box, r\.groups\.flat\(\)\)/);
  const sw = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/sw.js'), 'utf8');
  assert.match(sw, /`outing\.js\?v=\$\{BUILD\}`/);
});

// The storage keys the doc and the privacy notice describe are the keys the code uses, exactly.
test('storage keys: the code, the doc and the privacy notice agree', () => {
  const read = f => fs.readFileSync(path.join(__dirname, '..', f), 'utf8');
  const page = read('src/dipcast/site/index.html'), since = read('src/dipcast/site/since.js'), brief = read('src/dipcast/site/brief.js');
  const doc = read('docs/PLANNER-OUTING-BACKUP-2026-10.md'), privacy = read('src/dipcast/pages/privacy.html');
  assert.match(page, /const PLAN_KEY = 'dipcast\.plan';/);
  assert.match(since, /const SEEN_KEY = 'dipcast\.seen';/);
  assert.match(since, /const KEPT_PLAN_KEY = 'dipcast\.plan'/);   // reads the plan's key, never another
  assert.match(brief, /const ACK_KEY = 'dipcast\.briefacks'/);
  for (const k of ['dipcast.plan', 'dipcast.seen', 'dipcast.briefacks', 'dipcast.pushdates', 'dipcast.outingdates']) assert.ok(doc.includes('`' + k + '`'), k);
  // outing.js keeps the outing in the plan's address. It writes one key of its own, the pairs its alerts asked
  // for (only once someone presses "Alert me about this outing"), and the alerts' list through spotdate.js's
  // storeDates, the organisers' page's key.
  const outing = read('src/dipcast/site/outing.js');
  assert.match(outing, /const OUTING_ASKED_KEY = 'dipcast\.outingdates';/);
  assert.equal((outing.match(/localStorage\.setItem\(([^,]+),/g) || []).join(), 'localStorage.setItem(OUTING_ASKED_KEY,');
  assert.match(read('src/dipcast/site/spotdate.js'), /const DATES_KEY = 'dipcast\.pushdates'/);
  assert.equal((brief.match(/localStorage\.setItem\(([^,]+),/g) || []).join(), 'localStorage.setItem(ACK_KEY,');
  // The privacy notice names both: the outing in the kept plan, and the read tick.
  assert.match(privacy, /the time, spot and backup spot of an outing you chose/);
  assert.match(privacy, /"I have read version …" keeps a note in your browser's local storage/);
});

test('official advice: whatever eatoday.js\'s compact line gives, under the level, before the reasons', () => {
  assert.equal(O.outingOfficial({id: 'a', official: [{text: 'not what the build writes'}]}), '');   // eatoday.js drops odd items
  const h = O.outingSection({day: '2026-11-01', when: undefined, spot: 'a', groups: [], backupGroups: [], missing: [], issued: 'x', open: true,
    main: {id: 'a', name: 'A', href: 'spot/a/', tone: 'low', headline: 'Low risk', official: '<p class="o-mark">MARK</p>', why: 'Why.', ev: ''}, alt: null});
  assert.match(h, /Low risk<\/p><p class="o-mark">MARK<\/p><p class="why">/);
});
