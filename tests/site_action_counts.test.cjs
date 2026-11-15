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

function run(calls, {url = 'https://swimsignal-actions.example.workers.dev/', stored = null, storage = true, gpc, dnt, beacon = true, fetchWith} = {}) {
  const sent = [], fetched = [];
  const document = {querySelector: q => (q === 'meta[name="swimsignal-actions"]' && url ? {content: url} : null)};
  const localStorage = {getItem: k => { if (!storage) throw new Error('blocked'); return k === 'dipcast.count' ? stored : null; }};
  const navigator = {globalPrivacyControl: gpc, doNotTrack: dnt,
    ...(beacon === null ? {} : {sendBeacon: (u, b) => { sent.push([u, b]); return beacon; }})};
  const fetch = (u, o) => { fetched.push([u, o]); return fetchWith ? fetchWith() : Promise.resolve(); };
  const out = vm.runInNewContext(helper + '\n' + calls, {document, localStorage, navigator, fetch, JSON});
  return {sent, fetched, out};
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

test('the eleven places that count, and only those', () => {
  const calls = [...page.matchAll(/countAction\('(\w+)'/g)].map(m => m[1]);
  assert.deepEqual(calls.sort(), ['alerts', 'alerts', 'day', 'feed', 'logswim', 'mapday', 'plan', 'save', 'search', 'spot']);   // alerts: the browser's and the email sign-up
  assert.match(page, /function openSpot\(s, fly, push, day\) \{\n[^\n]*\n  countAction\('spot', id\);/);
  assert.match(page, /if \(iso\) countAction\('day', d\.id\);/);
  assert.match(page, /if \(on\) countAction\('save', d\.id\);/);
  assert.match(page, /if \(on\) countAction\('alerts'\);/);
  assert.ok(!/countAction\('changed'/.test(page));   // no "changed my plans" control exists (actions/README.md)
});

// The redesign's six (11 Nov 2026, PRs #673-#676). None sends a spot's id: the Worker keeps per-spot totals for the
// first three actions only, and the privacy notice says so.
test("the redesign's six: each counted where it happens, none with a spot", () => {
  // An alert for a date or for back to low risk: counted after the alert service took it (sendClears or sendDates
  // resolved), inside the try, so a refusal or a failed request counts nothing; turning one off counts nothing.
  const clear = page.slice(page.indexOf('async function mountClear'), page.indexOf('\nfunction actions(d)'));
  const tryAt = clear.indexOf('try {\n        if (kind === \'low\')'), sentAt = clear.indexOf('await D.sendDates'),
    countAt = clear.indexOf("if (turnOn) countAction(kind === 'low' ? 'lowalert' : 'dayalert');"), catchAt = clear.indexOf('} catch (e) { b.disabled = false;');
  assert.ok(tryAt > 0 && sentAt > tryAt && countAt > sentAt && catchAt > countAt, 'the alert count sits after the send, before the catch');
  // "Log a swim here": counted on the press.
  assert.match(page, /querySelector\('#log-here button'\)\.addEventListener\('click', \(\) => \{ document\.getElementById\('swam'\)\.click\(\); countAction\('logswim'\);/);
  // A row of the home spill feed: each link, as the feed is drawn (the spot it opens also counts 'spot').
  assert.match(page, /bindItems\(host\);\n  host\.querySelectorAll\('a\[data-id\]'\)\.forEach\(a => a\.addEventListener\('click', \(\) => countAction\('feed'\)\)\);/);
  assert.match(page, /async function mountHomeFeed\(saved\) \{[\s\S]*?countAction\('feed'\)[\s\S]*?\n\}/);
  // The phone's search button: opened, not closed.
  assert.match(page, /getElementById\('searchbtn'\)\.addEventListener\('click', \(\) => \{ const on = !SEARCH_OPEN; openSearch\(on\);\n  if \(on\) countAction\('search'\);/);
  // The phone map's five-day strip: a day picked (the select beside it, for Saved and Plan a swim, is not counted).
  assert.match(page, /querySelector\('#mapdays'\)\.addEventListener\('change', e => \{ setMapDay\(e\.target\.value\); if \(e\.target\.value\) countAction\('mapday'\); \}\);/);
  assert.match(page, /querySelector\('select'\)\.addEventListener\('change', e => setMapDay\(e\.target\.value\)\);/);
  for (const e of ['dayalert', 'lowalert', 'logswim', 'feed', 'search', 'mapday'])
    assert.ok(!new RegExp(`countAction\\('${e}', `).test(page), `${e} goes without a spot`);
});

test('the six are among the names the Worker takes, so none is refused by the Worker in this commit', () => {
  const worker = fs.readFileSync(path.join(__dirname, '../actions/src/index.js'), 'utf8');
  const events = [...worker.match(/export const EVENTS = \[([^\]]*)\]/)[1].matchAll(/'(\w+)'/g)].map(m => m[1]);
  const used = new Set([...page.matchAll(/countAction\('(\w+)'/g)].map(m => m[1]));
  used.add('dayalert'); used.add('lowalert');   // named in one call, by the alert's kind
  for (const e of used) assert.ok(events.includes(e), `${e} is in actions/src/index.js EVENTS`);
});

// A Worker deployed before this commit refuses the new names with 400. The page never reads the answer: a beacon is
// queued and forgotten, and the fetch it falls back to is no-cors, so a 400 resolves, and a failure is caught. Either
// way countAction returns at once, throws nothing, and leaves no rejected promise behind.
test('a count the Worker refuses, or that fails, does nothing to the page', async () => {
  const unhandled = [];
  const onUnhandled = r => unhandled.push(r);
  process.on('unhandledRejection', onUnhandled);
  try {
    for (const [name, opts] of [
      ['beacon queued, Worker answers 400 unseen', {}],
      ['no beacon, fetch answers 400', {beacon: null, fetchWith: () => Promise.resolve({ok: false, status: 400, type: 'opaque'})}],
      ['no beacon, fetch rejects', {beacon: null, fetchWith: () => Promise.reject(new TypeError('Failed to fetch'))}],
      ['no beacon, fetch throws at once', {beacon: null, fetchWith: () => { throw new TypeError('blocked'); }}],
    ]) {
      const r = run("countAction('feed'); countAction('lowalert'); 'page goes on'", opts);
      assert.equal(r.out, 'page goes on', name);
    }
    const thrower = run("navigator.sendBeacon = () => { throw new Error('quota'); }; countAction('search'); 'page goes on'",
      {fetchWith: () => Promise.reject(new Error('offline'))});
    assert.equal(thrower.out, 'page goes on');
    assert.equal(thrower.fetched.length, 1);   // a beacon that throws falls back to fetch
    await new Promise(r => setImmediate(r));
    assert.deepEqual(unhandled, []);
  } finally { process.off('unhandledRejection', onUnhandled); }
});
