// Brief versions and a leader's "read" tick (src/dipcast/site/brief.js, a local prototype on record.html):
// the version a record shows, the tick kept in this browser only, and what a later version does to it.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const B = require('../src/dipcast/site/brief.js');

const spot = (label = 'low', extra = {}) => ({id: 'wharfe-ilkley', name: 'Wharfe, Ilkley', kind: 'river',
  days: [{date: '2026-10-31', label, risk: 0.05}], now: {discharging_upstream: 0}, ...extra});
const AT = '2026-10-31T06:12:00+00:00', ISSUE = 'c4a13af-20261031T0612Z', DAY = '2026-10-31';
const v = (s = spot(), at = AT, issue = ISSUE) => B.version(s, DAY, at, issue);

test('a version is the issue id and a check of the data, the same for the same data in any key order', () => {
  const a = v();
  assert.equal(a.issue, ISSUE);
  assert.match(a.hash, /^[0-9a-f]{8}$/);
  assert.equal(B.label(a), `${ISSUE} · ${a.hash}`);
  // Keys in another order: the same version.
  const reordered = {now: {discharging_upstream: 0}, days: [{risk: 0.05, label: 'low', date: '2026-10-31'}], kind: 'river', name: 'Wharfe, Ilkley', id: 'wharfe-ilkley'};
  assert.deepEqual(v(reordered), a);
  // A changed level, a new spill, a new issue time or another day: another check.
  assert.notEqual(v(spot('moderate')).hash, a.hash);
  assert.notEqual(v(spot('low', {now: {discharging_upstream: 1}})).hash, a.hash);
  assert.notEqual(v(spot(), '2026-10-31T14:40:00+00:00').hash, a.hash);
  assert.notEqual(B.version(spot(), '2026-11-01', AT, ISSUE).hash, a.hash);
  // FNV-1a's published test values, so the check is the algorithm it says it is.
  assert.equal(B.fnv(''), '811c9dc5');
  assert.equal(B.fnv('a'), 'e40c292c');
  assert.equal(B.fnv('foobar'), 'bf9cf968');
});

test('a tick is for one version: a later version shows it as for an earlier one', () => {
  const a = v(), b = v(spot('moderate'), '2026-10-31T14:40:00+00:00', 'c4a13af-20261031T1440Z');
  assert.deepEqual(B.ackState([], 'wharfe-ilkley', DAY, a), {state: 'none', ack: null});
  const acks = B.setAck([], 'wharfe-ilkley', DAY, a, true, 1000);
  assert.deepEqual(acks, [{spot: 'wharfe-ilkley', day: DAY, issue: ISSUE, hash: a.hash, at: 1000}]);
  assert.equal(B.ackState(acks, 'wharfe-ilkley', DAY, a).state, 'read');
  assert.equal(B.ackState(acks, 'wharfe-ilkley', DAY, b).state, 'older');
  assert.equal(B.ackState(acks, 'wharfe-ilkley', '2026-11-01', a).state, 'none');   // another day's brief
  // The same issue id with other data (the check differs) is another version too.
  assert.equal(B.ackState(acks, 'wharfe-ilkley', DAY, {...a, hash: 'deadbeef'}).state, 'older');
  // Ticking the new version replaces the old tick; unticking removes it.
  const again = B.setAck(acks, 'wharfe-ilkley', DAY, b, true, 2000);
  assert.equal(again.length, 1);
  assert.equal(B.ackState(again, 'wharfe-ilkley', DAY, b).state, 'read');
  assert.deepEqual(B.setAck(again, 'wharfe-ilkley', DAY, b, false, 3000), []);
});

test('the ticks kept: odd values read as none, and at most thirty, the newest', () => {
  for (const text of [null, '', 'garbage', '{}', '42', 'null']) assert.deepEqual(B.readAcks(text), [], String(text));
  const good = {spot: 'a', day: DAY, issue: ISSUE, hash: '0123abcd', at: 5};
  const odd = [{...good, spot: ''}, {...good, spot: 7}, {...good, day: '31/10/2026'}, {...good, hash: 'XYZ'}, {...good, hash: '0123abcd0'},
    {...good, issue: ''}, {...good, at: '5'}, {...good, at: null}, null, 'x'];
  assert.deepEqual(B.readAcks(JSON.stringify([...odd, good])), [good]);
  const many = Array.from({length: 40}, (_, i) => ({...good, spot: `s${i}`, at: i}));
  const kept = B.readAcks(JSON.stringify(many));
  assert.equal(kept.length, B.MAX);
  assert.equal(kept[0].spot, 's10');
  let acks = [];
  for (let i = 0; i < 35; i++) acks = B.setAck(acks, `s${i}`, DAY, v(), true, i);
  assert.equal(acks.length, B.MAX);
});

test('the box says the version, what the tick is, and that nothing is sent', () => {
  const a = v(), h = B.section(a, {state: 'none', ack: null});
  assert.match(h, /^<section class="screen-only brief-ack"/);   // never on the printed record
  assert.match(h, new RegExp(`Version <b>${ISSUE} · ${a.hash}</b>`));
  assert.match(h, new RegExp(`<input type="checkbox" id="brief-ack"> I have read version ${a.hash}</label>`));
  assert.match(h, /Not ticked as read on this device\./);
  assert.match(h, /Nothing is sent to SwimSignal, your club or anyone else/);
  assert.match(h, /not a record of who read what/);
  const read = B.section(a, {state: 'read', ack: {spot: 'x', day: DAY, issue: ISSUE, hash: a.hash, at: new Date(2026, 9, 31, 7, 5).getTime()}});
  assert.match(read, /id="brief-ack" checked>/);
  assert.match(read, /You ticked this version as read on Sat 31 Oct at 07:05\./);
  const older = B.section(v(spot('high')), {state: 'older', ack: {spot: 'x', day: DAY, issue: ISSUE, hash: a.hash, at: new Date(2026, 9, 31, 7, 5).getTime()}});
  assert.doesNotMatch(older, /checked/);
  assert.match(older, new RegExp(`You ticked an earlier version \\(${ISSUE} · ${a.hash}\\) as read on Sat 31 Oct at 07:05\\. The brief has changed since: read this version before you tick it\\.`));
  assert.match(B.section(a, {state: 'none', ack: null}, false), /here only until the page closes/);
});

// ------------------------------------------------------------------ in the page
// brief.js's draw with a stand-in record box and storage: the tick is kept, read back on the next visit,
// and a blocked storage keeps it for the page only, without an error.
function page({blocked = false} = {}) {
  const items = new Map(), store = {
    getItem: k => { if (blocked) throw new Error('SecurityError'); return items.has(k) ? items.get(k) : null; },
    setItem: (k, val) => { if (blocked) throw new Error('SecurityError'); items.set(k, String(val)); } };
  // The smallest box draw needs: insertAdjacentHTML, querySelector for the box and the tick.
  const out = {html: '', insertAdjacentHTML(_, h) { this.html += h; },
    querySelector(q) {
      if (q === '.brief-ack') return this.html.includes('brief-ack') ? {remove: () => { this.html = this.html.replace(/<section class="screen-only brief-ack"[\s\S]*<\/section>/, ''); }} : null;
      if (q === '#brief-ack') { const box = this; return {focus() {}, addEventListener(_, f) { box.tick = f; }}; }
      return null; }};
  const ctx = vm.createContext({localStorage: store});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/brief.js'), 'utf8') + '\nthis.BriefAck = BriefAck;', ctx);
  return {ctx, out, items};
}

test('ticking in the page keeps it in this browser, and the next visit reads it back', () => {
  const p = page();
  p.ctx.BriefAck.draw(p.out, spot(), DAY, {generated_at: AT}, ISSUE);
  assert.match(p.out.html, /Not ticked as read on this device\./);
  p.out.tick({target: {checked: true}});
  assert.match(p.out.html, /You ticked this version as read on/);
  const kept = JSON.parse(p.items.get(B.ACK_KEY));
  assert.deepEqual(kept.map(a => [a.spot, a.day, a.issue]), [['wharfe-ilkley', DAY, ISSUE]]);
  // The next forecast: the same page, a new version.
  p.ctx.BriefAck.draw(p.out, spot('moderate'), DAY, {generated_at: '2026-10-31T14:40:00+00:00'}, 'c4a13af-20261031T1440Z');
  assert.match(p.out.html, /You ticked an earlier version/);
  assert.equal((p.out.html.match(/class="screen-only brief-ack"/g) || []).length, 1);   // one box, redrawn, not two
});

test('blocked storage: the tick lasts for the page, and says so', () => {
  const p = page({blocked: true});
  assert.doesNotThrow(() => p.ctx.BriefAck.draw(p.out, spot(), DAY, {generated_at: AT}, ISSUE));
  assert.match(p.out.html, /here only until the page closes/);
  p.out.tick({target: {checked: true}});
  assert.match(p.out.html, /You ticked this version as read on/);
});

test('the record page loads brief.js before record.js, and record.js draws it only under a record', () => {
  const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/record.html'), 'utf8');
  assert.ok(html.indexOf('<script src="brief.js"></script>') > html.indexOf('<script src="printed.js"></script>'));
  assert.ok(html.indexOf('<script src="brief.js"></script>') < html.indexOf('<script src="record.js"></script>'));
  const js = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/record.js'), 'utf8');
  assert.match(js, /if \(s && typeof BriefAck === 'object' && document\.getElementById\('r-decide'\)\) BriefAck\.draw\(out, s, iso, data, P\.issueId\(data\)\);/);
});
