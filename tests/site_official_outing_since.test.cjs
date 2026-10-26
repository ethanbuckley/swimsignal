// Official advice (#379, eatoday.js's eaTodayBrief/eaTodayTag) in a plan's outing (outing.js) and in what
// changed since you last looked (since.js): the shared compact line under each outing column's level, and a
// notice appearing, changing or no longer shown as a change of its own, with its state, never an all-clear,
// never a level. The notice is Frensham Great Pond's, as data/advisories/approved.json has it (26 Oct 2026).
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const S = require('../src/dipcast/site/since.js');
const O = require('../src/dipcast/site/outing.js');
const E = require('../src/dipcast/site/eatoday.js');
L.setToday('2026-10-26');
// The compact words as eatoday.js gives them now (#391 may add the cause): the tests ask the helper.
const brief = s => E.eaTodayBrief(s);

const APPROVED = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/advisories/approved.json'), 'utf8')).approvals
  .find(a => a.spot_id === 'bw-ukj2310-11945');
// As the build writes it (src/dipcast/official_advice.py, shown): one item, newest first.
const notice = (state = 'checked', checked = '2026-10-26') => ({line: APPROVED.line, publisher: APPROVED.publisher, link: APPROVED.link,
  since: APPROVED.start, checked, state});
const DATES = ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30'];
const frensham = (official = [], l = 'low') => ({id: 'bw-ukj2310-11945', name: 'Frensham Great Pond', kind: 'lake', source: 'designated',
  upstream_summary: {overflows: 2}, location: {mode: 'river'},
  now: {label: 'low', risk: 0, discharging_upstream: 0, feed_down_upstream: 0, stale_upstream: 0},
  days: DATES.map(date => ({date, label: l, risk: 0.05})), official});
const OLD = '2026-10-26T07:00:00', NEW = '2026-10-26T21:40:00';
const LOOKED = new Date(2026, 9, 26, 7, 5).getTime(), NOW = new Date(2026, 9, 26, 22, 0).getTime();
const pair = (a, b) => [S.seenRecord(a, OLD, LOOKED), S.seenRecord(b, NEW, NOW)];

test('the real approved entry reads in the shared compact words', () => {
  assert.equal(APPROVED.line, 'Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026');
  // Its parts, not its exact words (#391 may add the cause): who, what, since when, checked when.
  const b = brief(frensham([notice()]));
  for (const part of ['EA', 'advice against bathing', 'since 19 Jun', 'checked 26 Oct']) assert.ok(b.includes(part), `${part} in ${b}`);
});

// ------------------------------------------------------------------------------ the outing
test('each outing column shows the shared compact notice under its level, and only where there is one', () => {
  assert.equal(O.outingOfficial(frensham([notice()])), E.eaTodayTag(frensham([notice()]), 'p'));   // the shared helper, as is
  assert.match(O.outingOfficial(frensham([notice()])), /^<p class="o-tag">.*checked 26 Oct<\/p>$/);
  assert.equal(O.outingOfficial(frensham([])), '');
  assert.equal(O.outingOfficial({id: 'x'}), '');   // spots-lite without the field
  assert.match(O.outingOfficial(frensham([notice('stale', '2026-10-12')])), /not re-checked since 12 Oct<\/p>$/);
  const col = (id, name, s) => ({id, name, href: `spot/${id}/`, tone: 'low', headline: 'Low risk', official: O.outingOfficial(s), why: '', ev: ''});
  const h = O.outingSection({day: '2026-10-27', when: 'morning', spot: 'bw-ukj2310-11945', backup: 'b', groups: [], backupGroups: [], missing: [], issued: 'x', open: true,
    main: col('bw-ukj2310-11945', 'Frensham Great Pond', frensham([notice()])), alt: col('b', 'Backup water', frensham([]))});
  // The level stays the forecast's: the notice is a line of its own after it, in the spot's column only.
  assert.match(h, /Frensham Great Pond.*<p class="hl low">Low risk<\/p><p class="o-tag">[^<]+<\/p>.*Backup water.*<p class="hl low">Low risk<\/p><\/div>/s);
  assert.ok(h.includes(E.eaTodayTag(frensham([notice()]), 'p')));
  assert.equal((h.match(/o-tag/g) || []).length, 1);
});

test('the page loads eatoday.js before the outing and since scripts use it', () => {
  const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  const at = f => page.indexOf(`<script src="${f}"></script>`);
  assert.ok(at('eatoday.js') > 0 && at('eatoday.js') < at('since.js') && at('eatoday.js') < at('outing.js'));
});

// ------------------------------------------------------------------------------ since you last looked
test('a notice appearing is a change of its own, with its words, its state and that the level is not it', () => {
  const [a, b] = pair(frensham([]), frensham([notice()]));
  assert.equal(a.official, null);
  assert.deepEqual(b.official, {key: `Environment Agency|${APPROVED.line}|2026-06-19`, brief: brief(frensham([notice()])), publisher: 'Environment Agency'});
  assert.equal(a.level, b.level);   // the level never moves for it
  assert.equal(S.sinceLine(a, b), `No official advice was shown when you looked today at 07:05; now: ${brief(frensham([notice()]))}. Follow it first.`);
  // Said once: the line has the notice, the evidence whose it is.
  const ev = S.sinceEvidence(a, b, NOW);
  assert.match(ev, /The official advice is the Environment Agency's, not part of this level\./);
  assert.doesNotMatch(ev, /since 19 Jun/);
});

test('a notice no longer shown is said so, and never as an all-clear', () => {
  const [a, b] = pair(frensham([notice()]), frensham([]));
  const said = S.sinceLine(a, b) + ' ' + S.sinceEvidence(a, b, NOW);
  assert.equal(S.sinceLine(a, b), `Official advice was shown when you looked today at 07:05 (${brief(frensham([notice()]))}); it is no longer shown here.`);
  assert.match(said, /That is not an all-clear: check the Environment Agency's own page before you swim\./);
  assert.doesNotMatch(said, /\b(safe|lifted|ended|clear to swim|all clear)\b/i);
});

test('a notice not re-checked keeps its stale state in the words; a new check day alone is no change', () => {
  const [a, b] = pair(frensham([notice()]), frensham([notice('checked', '2026-10-27')]));
  assert.equal(S.sinceLine(a, b), '');   // same notice, checked again
  const [c, d] = pair(frensham([notice()]), frensham([notice('unverified', '2026-10-26')]));
  assert.equal(S.officialChange(c, d), '');
  // When something else changed, the line gives the notice as it stands now, stale state and all.
  const stale = frensham([notice('stale', '2026-10-12')], 'moderate');
  const e = S.seenRecord(frensham([notice()], 'low'), OLD, LOOKED), f = S.seenRecord(stale, NEW, NOW);
  assert.match(brief(stale), /not re-checked since 12 Oct/);
  assert.equal(S.sinceLine(e, f), `Was low risk when you looked today at 07:05; now moderate risk. Official advice still shown: ${brief(stale)}. Follow it first.`);
});

test('another notice in place of the first is said as changed', () => {
  const other = {...notice(), line: 'Environment Agency: advice against bathing (pollution) since 20 Oct 2026', since: '2026-10-20'};
  const [a, b] = pair(frensham([notice()]), frensham([other]));
  assert.equal(S.officialChange(a, b), 'other');
  assert.equal(S.sinceLine(a, b), `Official advice changed since you looked today at 07:05; now: ${brief(frensham([other]))}. Follow it first.`);
});

test('nothing is made up from a missing field: old notes, and a page without eatoday.js', () => {
  const before = {id: 'bw-ukj2310-11945', level: 'low', discharging: 0, rating: null, gap: false, forecast: OLD, at: LOOKED};   // no official
  const read = S.readSeen(JSON.stringify([before])).get('bw-ukj2310-11945');
  assert.deepEqual(read, before);
  const now = S.seenRecord(frensham([notice()]), NEW, NOW);
  assert.equal(S.officialChange(read, now), '');
  assert.equal(S.sinceLine(read, now), '');
  // Odd stored values are not what the page writes: not seen.
  for (const odd of [{key: '', brief: 'x', publisher: 'y'}, {brief: 'x'}, 'EA', 1]) assert.equal(S.readSeen(JSON.stringify([{...before, official: odd}])).size, 0, JSON.stringify(odd));
  // In the page without eatoday.js the record has no official field to compare.
  const vm = require('node:vm'), ctx = vm.createContext({});
  for (const f of ['experience.js', 'levels.js', 'since.js']) vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/', f), 'utf8'), ctx);
  vm.runInContext('setToday("2026-10-26")', ctx);
  assert.equal(vm.runInContext('seenRecord', ctx)(frensham([notice()]), NEW, NOW).official, undefined);
});

test('on a Saved card in the page: the notice appearing, escaped, with eatoday.js loaded as the page loads it', () => {
  const vm = require('node:vm');
  const items = new Map([[S.SEEN_KEY, JSON.stringify([S.seenRecord(frensham([]), OLD, LOOKED)])]]);
  const ctx = vm.createContext({URLSearchParams, localStorage: {getItem: k => items.has(k) ? items.get(k) : null, setItem: (k, v) => items.set(k, v), removeItem: k => items.delete(k)}});
  for (const f of ['experience.js', 'eatoday.js', 'levels.js', 'since.js']) vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/', f), 'utf8'), ctx);
  vm.runInContext('setToday("2026-10-26")', ctx);
  const h = vm.runInContext('sinceSaid', ctx)(frensham([notice()]), NEW);
  assert.ok(h.startsWith(`<p class="place-since">No official advice was shown when you looked today at 07:05; now: ${brief(frensham([notice()])).replace(/'/g, '&#39;')}. Follow it first.`), h);
  assert.match(h, /The official advice is the Environment Agency&#39;s, not part of this level\./);
  assert.equal((h.match(/since 19 Jun/g) || []).length, 1);
});

// S6 (integrated review, 27 Oct 2026): Frensham's card read "Was moderate risk …; now low risk." while the
// EA's advice against bathing showed both then and now, so no appeared/cleared line fired. A lower sewage
// level must never read as an all-clear while official advice shows: the line itself carries the notice.
test('a lower level while official advice still shows carries the notice in the line, never as good news alone', () => {
  const was = frensham([notice()], 'moderate'), now = frensham([notice()], 'low');
  const [a, b] = pair(was, now);
  assert.equal(S.officialChange(a, b), '');   // the same notice then and now
  const line = S.sinceLine(a, b);
  assert.equal(line, `Was moderate risk when you looked today at 07:05; now low risk. Official advice still shown: ${brief(now)}. Follow it first.`);
  assert.doesNotMatch(line + S.sinceEvidence(a, b, NOW), /\b(safe|all-clear|all clear|lifted)\b/i);
  // A spill stopping, the level the same: the notice rides on that line too.
  const [c, d] = pair(frensham([notice()], 'low'), frensham([notice()], 'low'));
  c.discharging = 2; d.discharging = 0;
  assert.equal(S.sinceLine(c, d), `2 overflows upstream were discharging when you looked today at 07:05; all have stopped. Official advice still shown: ${brief(now)}. Follow it first.`);
  // A note from before the official field: "shown", not "still shown".
  const {official, ...old} = a;
  assert.match(S.sinceLine(old, b), new RegExp(`now low risk\\. Official advice shown: .*\\. Follow it first\\.$`));
  // The level fell and the notice is no longer shown: both said, and the evidence says it is not an all-clear.
  const [e, f] = pair(frensham([notice()], 'moderate'), frensham([], 'low'));
  assert.equal(S.sinceLine(e, f), `Was moderate risk when you looked today at 07:05; now low risk. Official advice shown then (${brief(was)}) is no longer shown here.`);
  assert.match(S.sinceEvidence(e, f, NOW), /That is not an all-clear/);
});

test('S6 on the Saved card in the page: the notice is in the visible line, not only in the evidence', () => {
  const vm = require('node:vm');
  const items = new Map([[S.SEEN_KEY, JSON.stringify([S.seenRecord(frensham([notice()], 'moderate'), OLD, LOOKED)])]]);
  const ctx = vm.createContext({URLSearchParams, localStorage: {getItem: k => items.has(k) ? items.get(k) : null, setItem: (k, v) => items.set(k, v), removeItem: k => items.delete(k)}});
  for (const f of ['experience.js', 'eatoday.js', 'levels.js', 'since.js']) vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/', f), 'utf8'), ctx);
  vm.runInContext('setToday("2026-10-26")', ctx);
  const now = frensham([notice()], 'low'), h = vm.runInContext('sinceSaid', ctx)(now, NEW);
  const visible = h.replace(/<span class="since-ev">.*$/, '');
  assert.ok(visible.includes(`now low risk. Official advice still shown: ${brief(now)}. Follow it first.`), visible);
});
