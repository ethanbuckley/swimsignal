// countAction in index.html: the action counter's helper (actions/, the Worker). Off unless the build put the Worker's
// address in <meta name="swimsignal-actions">; then one small beacon an action, holding the action and, for a spot's,
// the spot's id, and nothing at all where the browser has objected.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const start = page.indexOf('const ACTIONS_URL'), end = page.indexOf('\n}\n', page.indexOf('function countAction')) + 3;
const helper = page.slice(start, end);

function run(calls, {url = 'https://swimsignal-actions.example.workers.dev/', stored = null, storage = true, gpc, dnt, beacon = true} = {}) {
  const sent = [], fetched = [];
  const document = {querySelector: q => (q === 'meta[name="swimsignal-actions"]' && url ? {content: url} : null)};
  const localStorage = {getItem: k => { if (!storage) throw new Error('blocked'); return k === 'dipcast.count' ? stored : null; }};
  const navigator = {globalPrivacyControl: gpc, doNotTrack: dnt,
    ...(beacon === null ? {} : {sendBeacon: (u, b) => { sent.push([u, b]); return beacon; }})};
  const fetch = (u, o) => { fetched.push([u, o]); return Promise.resolve(); };
  vm.runInNewContext(helper + '\n' + calls, {document, localStorage, navigator, fetch, JSON});
  return {sent, fetched};
}

test('off: no address in the page, nothing is sent', () => {
  const r = run("countAction('spot', 'a')", {url: null});
  assert.equal(r.sent.length + r.fetched.length, 0);
});

test('on: one beacon an action, with the action and the spot only', () => {
  const r = run("countAction('spot', 'wharfe-ilkley'); countAction('plan')");
  assert.deepEqual(r.sent, [['https://swimsignal-actions.example.workers.dev/', '{"event":"spot","spot_id":"wharfe-ilkley"}'],
                            ['https://swimsignal-actions.example.workers.dev/', '{"event":"plan"}']]);
  assert.equal(r.fetched.length, 0);
});

test('a browser that objected sends nothing: the choice, Global Privacy Control, Do Not Track', () => {
  for (const o of [{stored: 'off'}, {gpc: true}, {dnt: '1'}]) {
    const r = run("countAction('save', 'a')", o);
    assert.equal(r.sent.length + r.fetched.length, 0, JSON.stringify(o));
  }
  assert.equal(run("countAction('save', 'a')", {dnt: '0'}).sent.length, 1);
});

test('no sendBeacon, or one that refuses: a fetch that sends no credentials and is never waited on', () => {
  for (const beacon of [null, false]) {
    const r = run("countAction('alerts')", {beacon});
    assert.equal(r.fetched.length, 1);
    assert.equal(r.fetched[0][1].credentials, 'omit');
    assert.equal(r.fetched[0][1].keepalive, true);
    assert.equal(r.fetched[0][1].body, '{"event":"alerts"}');
  }
});

test('blocked storage does not stop the page or the count', () => {
  assert.equal(run("countAction('day', 'a')", {storage: false}).sent.length, 1);
});

test('the five places that count, and only those', () => {
  const calls = [...page.matchAll(/countAction\('(\w+)'/g)].map(m => m[1]);
  assert.deepEqual(calls.sort(), ['alerts', 'alerts', 'day', 'plan', 'save', 'spot']);   // alerts: the browser's and the email sign-up
  assert.match(page, /function openSpot\(s, fly, push, day\) \{\n[^\n]*\n  countAction\('spot', id\);/);
  assert.match(page, /if \(iso\) countAction\('day', d\.id\);/);
  assert.match(page, /if \(on\) countAction\('save', d\.id\);/);
  assert.match(page, /if \(on\) countAction\('alerts'\);/);
  assert.ok(!/countAction\('changed'/.test(page));   // no "changed my plans" control exists (actions/README.md)
});
