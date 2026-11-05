// A plan's outing kept for offline use (src/dipcast/site/outingpack.js, with sw.js): what a pack holds, that a new
// build's worker leaves it alone, the order the worker answers in without a connection (network, the build's cache,
// the pack), the words, and the pack's end: "Stop keeping it", and the day after the outing.
process.env.TZ = 'Europe/London';   // the words are on the device's clock
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const L = require('../src/dipcast/site/levels.js');
const P = require('../src/dipcast/site/outingpack.js');
const read = f => fs.readFileSync(path.join(__dirname, '..', f), 'utf8');

const SCOPE = 'https://example.org/swim/';
const DAY = '2026-10-31';   // a Saturday, after the clocks went back: London is on UTC
L.setToday('2026-10-29');
const at = s => Date.parse(s);
const META = {v: 1, day: DAY, spot: 'frensham', backup: 'wey', names: ['Frensham Great Pond', 'River Wey at Waverley'],
  keptAt: at('2026-10-29T07:12:00Z'), issuedAt: '2026-10-29T06:00:00Z'};

// The browser's caches, by name, as the page and the worker both see them.
function cachesWorld() {
  const byName = new Map();
  const key = k => typeof k === 'string' ? k : k.url;
  const one = name => { if (!byName.has(name)) byName.set(name, new Map()); const m = byName.get(name);
    return {match: async k => m.get(key(k))?.clone(), put: async (k, r) => { m.set(key(k), r); }, add: async req => { m.set(key(req), new Response('shell file')); },
      keys: async () => [...m.keys()]}; };
  return {byName,
    open: async name => one(name), keys: async () => [...byName.keys()], delete: async name => byName.delete(name), has: async name => byName.has(name),
    match: async (k, o = {}) => { for (const n of o.cacheName ? [o.cacheName] : [...byName.keys()]) { const m = byName.get(n); if (m && m.has(key(k))) return m.get(key(k)).clone(); } return undefined; }};
}
const storage = (init = {}) => { const m = new Map(Object.entries(init)); return {m, getItem: k => m.has(k) ? m.get(k) : null, setItem: (k, v) => { m.set(k, String(v)); }, removeItem: k => { m.delete(k); }}; };

// The worker at a build, on a clock, with the network given.
function worker(fetch, cs, {build = 'dev', now = at('2026-10-31T08:00:00Z')} = {}) {
  const handlers = {};
  class Clock extends Date { constructor(...a) { super(...(a.length ? a : [now])); } static now() { return now; } }
  class ScopedRequest extends Request { constructor(u, init) { super(typeof u === 'string' ? new URL(u, SCOPE).href : u, init); } }
  const context = vm.createContext({fetch, URL, Response, Request: ScopedRequest, Date: Clock, caches: cs,
    self: {registration: {scope: SCOPE}, location: new URL(SCOPE), skipWaiting: async () => {}, clients: {claim: async () => {}},
      addEventListener(type, h) { handlers[type] = h; }},
    setTimeout() {}});
  vm.runInContext(read('src/dipcast/site/sw.js').replace("const BUILD = 'dev';", `const BUILD = '${build}';`), context);
  const event = async (type, e = {}) => { let p; handlers[type]({...e, waitUntil(x) { p = x; }}); await p; };
  const ask = () => new Promise(ok => handlers.message({data: {outingPack: 'shell'}, ports: [{postMessage: ok}]}));
  return {context, handlers, event, ask};
}
const offline = async () => { throw new Error('offline'); };
// A pack as the page stores it: its files and its note.
async function packWith(cs, files, meta = META) {
  const c = await cs.open(P.CACHE);
  for (const [u, body] of Object.entries(files)) await c.put(SCOPE + u, new Response(body));
  await c.put(SCOPE + P.META, new Response(JSON.stringify(meta)));
}

// ------------------------------------------------------------------------------ what a pack holds
test('a pack holds the plan, the spot\'s and the backup\'s pages and files, the forecast, then what may be there', () => {
  const l = P.files({shell: ['./', 'app.js?v=abc', 'data/spots-lite.json', 'outingpack.js?v=abc'],
    spots: [{id: 'frensham', page: true, file: 'spot/frensham.json'}, {id: 'odd id', page: false, file: 'spot/odd.json'}]});
  assert.deepEqual(l.need, ['plan/', 'data/spots-lite.json', 'spot/frensham/', 'data/spot/frensham.json', 'data/spot/odd.json']);
  assert.deepEqual(l.may, ['data/spot/frensham-trace.json', 'data/spot/odd-trace.json', ...P.EXTRAS, './', 'app.js?v=abc', 'outingpack.js?v=abc']);   // each file once
  // A spot with no file of its own (no detail_file) brings its page only.
  assert.deepEqual(P.files({shell: [], spots: [{id: 'tarn', page: true, file: null}]}).need, ['plan/', 'data/spots-lite.json', 'spot/tarn/']);
});

test('the pack takes every file the offline copy holds for its build, from the worker itself', async () => {
  const w = worker(offline, cachesWorld(), {build: 'b2'});
  const answer = await w.ask();
  assert.equal(answer.build, 'b2');
  assert.ok(answer.shell.includes('outingpack.js?v=b2') && answer.shell.includes('levels.js?v=b2') && answer.shell.includes('./'), answer.shell.join(' '));
  const l = P.files({shell: answer.shell, spots: []});
  for (const f of answer.shell) assert.ok(l.need.includes(f) || l.may.includes(f), f);
});

// ------------------------------------------------------------------------------ the worker
test('the pack\'s cache is the one the page fills, and a new build\'s worker leaves it alone', async () => {
  assert.match(read('src/dipcast/site/sw.js'), new RegExp(`const PACK = '${P.CACHE}', PACK_META = '${P.META}';`));
  assert.ok(!P.CACHE.startsWith('dipcast-'));
  const cs = cachesWorld();
  await (await cs.open('dipcast-old')).put(SCOPE + 'plan/', new Response('old build'));
  await packWith(cs, {'plan/': 'kept plan'});
  const w = worker(offline, cs, {build: 'new'});
  await w.event('install');
  await w.event('activate');
  assert.deepEqual((await cs.keys()).sort(), ['dipcast-new', P.CACHE].sort());
  assert.equal(await (await w.context.networkFirst({url: SCOPE + 'plan/', mode: 'navigate'})).text(), 'kept plan');
});

test('without a connection: the network first, then this build\'s cache, then the pack, each marked as stored', async () => {
  const cs = cachesWorld();
  await (await cs.open('dipcast-dev')).put(SCOPE + 'data/spots-lite.json', new Response('build copy'));
  await packWith(cs, {'data/spots-lite.json': 'pack copy', 'data/spot/frensham.json': 'pack spot', 'spot/frensham/': 'pack page'});
  const online = worker(async () => new Response('network'), cs);
  const fresh = await online.context.networkFirst(new Request(SCOPE + 'data/spots-lite.json'));
  assert.equal(await fresh.text(), 'network');
  assert.equal(fresh.headers.get('X-SwimSignal-Stored'), null);
  const cs2 = cachesWorld();   // a fresh world: the network's answer above was stored in the first
  await (await cs2.open('dipcast-dev')).put(SCOPE + 'data/spots-lite.json', new Response('build copy'));
  await packWith(cs2, {'data/spots-lite.json': 'pack copy', 'data/spot/frensham.json': 'pack spot', 'spot/frensham/': 'pack page'});
  const off = worker(offline, cs2);
  const build = await off.context.networkFirst(new Request(SCOPE + 'data/spots-lite.json'));
  assert.equal(await build.text(), 'build copy');
  assert.equal(build.headers.get('X-SwimSignal-Stored'), '1');
  const pack = await off.context.networkFirst(new Request(SCOPE + 'data/spot/frensham.json'));
  assert.equal(await pack.text(), 'pack spot');
  assert.equal(pack.headers.get('X-SwimSignal-Stored'), '1');
  // A spot's page asked for with a query is the page kept under its address.
  assert.equal(await (await off.context.networkFirst({url: SCOPE + 'spot/frensham/?source=plan', mode: 'navigate'})).text(), 'pack page');
  // Stored-first files (fonts, icons, the map library): this build's copy, the network, then the pack.
  await (await cs2.open(P.CACHE)).put(SCOPE + 'fonts/a.woff2', new Response('pack font'));
  assert.equal(await (await off.context.storedFirst(new Request(SCOPE + 'fonts/a.woff2'))).text(), 'pack font');
});

test('after the outing\'s day the worker deletes the pack rather than answer from it', async () => {
  const cs = cachesWorld();
  await packWith(cs, {'spot/frensham/': 'pack page'});
  const lastMinute = worker(offline, cs, {now: at('2026-10-31T23:59:00Z')});
  assert.equal(await (await lastMinute.context.networkFirst({url: SCOPE + 'spot/frensham/', mode: 'navigate'})).text(), 'pack page');
  const after = worker(offline, cs, {now: at('2026-11-01T00:01:00Z')});
  await assert.rejects(after.context.networkFirst({url: SCOPE + 'spot/frensham/', mode: 'navigate'}), /offline/);
  assert.equal(await cs.has(P.CACHE), false);
  // A pack without its note is not answered from either.
  const bare = cachesWorld();
  await (await bare.open(P.CACHE)).put(SCOPE + 'plan/', new Response('no note'));
  await assert.rejects(worker(offline, bare).context.networkFirst({url: SCOPE + 'plan/', mode: 'navigate'}), /offline/);
});

// ------------------------------------------------------------------------------ the words
test('the tile says when it was kept and when its forecast was issued, and to check again', () => {
  const kept = now => P.tile({state: 'kept', meta: META, want: {day: DAY}, names: META.names, nowMs: at(now)});
  assert.match(kept('2026-10-31T09:00:00Z'), /<b>Kept for offline use at 07:12 on Thursday\.<\/b> The forecast in it was issued at 06:00\. Check again before you leave if you have signal\./);
  assert.match(kept('2026-10-30T09:00:00Z'), /Kept for offline use at 07:12 yesterday\./);
  assert.match(kept('2026-10-29T09:00:00Z'), /Kept for offline use at 07:12 today\./);
  // A forecast issued the evening before it was kept says its day.
  assert.match(P.tile({state: 'kept', meta: {...META, issuedAt: '2026-10-28T21:40:00Z'}, want: {day: DAY}, nowMs: at('2026-10-29T09:00:00Z')}),
    /The forecast in it was issued at 21:40 yesterday\./);
  const h = kept('2026-10-29T09:00:00Z');
  assert.match(h, /It stays on this device until the end of Saturday, then it is deleted\./);
  assert.match(h, /data-outing-pack="stop">Stop keeping it</);
  assert.ok(!/iPhone/.test(h) && !/Keep it again/.test(h));
  // On iPhone and iPad, what cannot be promised; in an app's own browser, where it stays.
  const ios = P.tile({state: 'kept', meta: META, want: {day: DAY}, nowMs: at('2026-10-29T09:00:00Z'), ios: true, app: 'Facebook'});
  assert.match(ios, /Safari can delete it sooner if the phone is short of space\. Safari and the Home Screen app each keep their own copy/);
  assert.match(ios, /In the Facebook app's browser, it stays in that app/);
  // A later forecast than the kept one is offered.
  const newer = P.tile({state: 'kept', meta: META, want: {day: DAY}, newer: '2026-10-29T12:00:00Z', nowMs: at('2026-10-29T13:00:00Z')});
  assert.match(newer, /A newer forecast was issued at 12:00 today\. Keep the outing again to store it\./);
  assert.match(newer, /data-outing-pack="keep">Keep it again</);
  assert.ok(!/A newer/.test(P.tile({state: 'kept', meta: META, want: {day: DAY}, newer: META.issuedAt, nowMs: at('2026-10-29T13:00:00Z')})));
});

test('before keeping, the tile says what is kept, until when, and that nothing is sent; another outing kept is named', () => {
  const ready = P.tile({state: 'ready', want: {day: DAY}, names: ['Frensham Great Pond', 'River Wey at Waverley']});
  assert.match(ready, /data-outing-pack="keep">Keep this outing for offline use</);
  assert.match(ready, /This keeps the plan and the pages of Frensham Great Pond and River Wey at Waverley on this device, so you can open them without signal, until the end of Saturday\. Nothing is sent\./);
  const other = P.tile({state: 'other', meta: {...META, spot: 'x', names: ['Semerwater'], backup: null, day: '2026-10-30'}, want: {day: DAY}, names: ['Frensham Great Pond']});
  assert.match(other, /A different outing is kept for offline use: Semerwater, for tomorrow\. Keeping this one replaces it\./);
  assert.match(other, /Stop keeping that one/);
  assert.match(P.tile({state: 'off', want: {day: DAY}}), /needs the offline copy, which is turned off in this browser/);
  assert.match(P.tile({state: 'none', want: {day: DAY}}), /This browser cannot keep the outing for offline use\./);
  for (const s of ['ready', 'other', 'kept', 'off', 'none']) {
    const h = P.tile({state: s, meta: META, want: {day: DAY}, names: META.names, nowMs: at('2026-10-29T09:00:00Z'), ios: true});
    assert.ok(!/\b(safe|clean|clear)\b/i.test(h.replace(/<[^>]+>/g, '')), s);
  }
});

test('names and an app are escaped', () => {
  const bad = '<img src=x onerror=alert(1)>';
  const h = P.tile({state: 'other', meta: {...META, names: [bad, `"${bad}"`]}, want: {day: DAY}, names: [bad]})
    + P.tile({state: 'kept', meta: META, want: {day: DAY}, nowMs: at('2026-10-29T09:00:00Z'), app: bad});
  assert.ok(!h.includes('<img') && h.includes('&lt;img src=x onerror=alert(1)&gt;') && h.includes('&quot;'));
  assert.ok(!P.line({meta: META, rel: 'plan/', offline: true, nowMs: at('2026-10-29T09:00:00Z'), issued: bad}).includes('<img'));
});

test('a kept page read from a stored copy says so and how old the copy is; other pages, and fresh ones, say nothing', () => {
  const now = at('2026-10-29T09:20:00Z');
  const plan = P.line({meta: META, rel: 'plan/', offline: true, nowMs: now});
  assert.equal(plan, '<p class="issued">Showing the copy kept on this device. Your outing was kept for offline use at 07:12 today, 2 h 8 min ago.</p>');
  assert.ok(P.line({meta: META, rel: 'spot/wey', offline: true, nowMs: now}));   // the backup's page, with or without its slash
  assert.match(P.line({meta: META, rel: 'spot/frensham/', offline: true, nowMs: now, issued: 'Thu 06:00'}), /The forecast shown was issued Thu 06:00\./);
  assert.equal(P.line({meta: META, rel: 'spot/other/', offline: true, nowMs: now}), '');
  assert.equal(P.line({meta: META, rel: '', offline: true, nowMs: now}), '');   // the list
  assert.equal(P.line({meta: META, rel: 'plan/', offline: false, nowMs: now}), '');
  assert.equal(P.line({meta: META, rel: 'plan/', offline: true, nowMs: at('2026-11-01T08:00:00Z')}), '');   // past its day
  assert.equal(P.line({meta: null, rel: 'plan/', offline: true, nowMs: now}), '');
});

// ------------------------------------------------------------------------------ the note, and the pack's end
test('the note is read only when whole, and belongs to one day, spot and backup', () => {
  assert.deepEqual(P.read(JSON.stringify(META)), META);
  for (const bad of [null, '', '{', '[]', JSON.stringify({...META, day: 'Saturday'}), JSON.stringify({...META, keptAt: 'now'}), JSON.stringify({...META, spot: 3})]) assert.equal(P.read(bad), null, String(bad));
  assert.ok(P.same(META, {day: DAY, spot: 'frensham', backup: 'wey'}));
  assert.ok(!P.same(META, {day: DAY, spot: 'frensham', backup: null}));
  assert.ok(!P.same(META, {day: '2026-10-30', spot: 'frensham', backup: 'wey'}));
  assert.ok(P.same({...META, backup: null}, {day: DAY, spot: 'frensham'}));
  assert.ok(!P.expired(META, at('2026-10-31T23:59:59Z')) && P.expired(META, at('2026-11-01T00:00:01Z')) && P.expired(null, 0));
});

test('"Stop keeping it" deletes the pack and its note; a page opened after the day does the same, and an orphan pack goes', async () => {
  const cs = cachesWorld(), st = storage({[P.KEY]: JSON.stringify(META)});
  await packWith(cs, {'plan/': 'x'});
  await P.drop(cs, st);
  assert.equal(await cs.has(P.CACHE), false);
  assert.equal(st.getItem(P.KEY), null);
  // Within its day a page leaves it; after, the page deletes it.
  const cs2 = cachesWorld(), st2 = storage({[P.KEY]: JSON.stringify(META)});
  await packWith(cs2, {'plan/': 'x'});
  assert.equal(await P.tidy(at('2026-10-31T20:00:00Z'), cs2, st2), false);
  assert.equal(await cs2.has(P.CACHE), true);
  assert.equal(await P.tidy(at('2026-11-01T07:00:00Z'), cs2, st2), true);
  assert.equal(await cs2.has(P.CACHE), false);
  assert.equal(st2.getItem(P.KEY), null);
  // A pack whose note this browser lost.
  const cs3 = cachesWorld();
  await packWith(cs3, {'plan/': 'x'});
  assert.equal(await P.tidy(at('2026-10-29T07:00:00Z'), cs3, storage()), true);
  assert.equal(await cs3.has(P.CACHE), false);
  // Nothing kept: nothing done, and no cache made.
  const cs4 = cachesWorld();
  assert.equal(await P.tidy(at('2026-10-29T07:00:00Z'), cs4, storage()), false);
  assert.deepEqual(await cs4.keys(), []);
});

test('keeping stores every file at its address with the note, the issue time read from the kept forecast', async () => {
  const cs = cachesWorld(), st = storage();
  const asked = [];
  const get = async p => { asked.push(p);
    if (p === 'data/spots-lite.json') return new Response(JSON.stringify({generated_at: '2026-10-29T06:00:00Z', spots: []}), {headers: {'Content-Type': 'application/json'}});
    if (p.endsWith('-trace.json') || p === 'reviews/index.json') return new Response('', {status: 404});
    return new Response(`body of ${p}`, {headers: {'Content-Type': p.endsWith('/') ? 'text/html' : 'text/plain'}}); };
  const list = P.files({shell: ['./', 'app.js?v=abc'], spots: [{id: 'frensham', page: true, file: 'spot/frensham.json'}]});
  const note = await P.store(list, get, SCOPE, {v: 1, day: DAY, spot: 'frensham', backup: null, keptAt: META.keptAt, issuedAt: 'stale'}, cs, st);
  assert.equal(note.issuedAt, '2026-10-29T06:00:00Z');
  assert.deepEqual(P.read(st.getItem(P.KEY)), note);
  const kept = await (await cs.open(P.CACHE)).keys();
  assert.deepEqual(kept.sort(), [SCOPE, SCOPE + 'app.js?v=abc', SCOPE + 'data/spot/frensham.json', SCOPE + 'data/spot_scores.json', SCOPE + 'data/spots-lite.json',
    SCOPE + 'data/verification.json', SCOPE + P.META, SCOPE + 'plan/', SCOPE + 'spot/frensham/'].sort());   // no trace, no reviews: they were not there
  const page = await cs.match(SCOPE + 'spot/frensham/', {cacheName: P.CACHE});
  assert.equal(await page.text(), 'body of spot/frensham/');
  assert.equal(page.headers.get('Content-Type'), 'text/html');
  assert.equal(JSON.parse(await (await cs.match(SCOPE + P.META, {cacheName: P.CACHE})).text()).day, DAY);
  assert.ok(asked.every(p => !/^https?:/.test(p)), 'only the site\'s own files, by their addresses under its root');
});

test('a needed file that cannot be had keeps nothing new and leaves the pack that was there', async () => {
  const cs = cachesWorld(), st = storage({[P.KEY]: JSON.stringify(META)});
  await packWith(cs, {'plan/': 'the earlier outing'});
  const list = P.files({shell: [], spots: [{id: 'frensham', page: true, file: 'spot/frensham.json'}]});
  await assert.rejects(P.store(list, async p => p === 'spot/frensham/' ? new Response('', {status: 404}) : new Response('{}'), SCOPE, {v: 1, day: DAY, spot: 'frensham', keptAt: 1}, cs, st),
    /spot\/frensham\/ answered 404/);
  assert.equal(await (await cs.match(SCOPE + 'plan/', {cacheName: P.CACHE})).text(), 'the earlier outing');
  assert.deepEqual(P.read(st.getItem(P.KEY)), META);
});

test('a browser that will not keep the note keeps no pack', async () => {
  const cs = cachesWorld(), st = {getItem: () => null, setItem() { throw new Error('denied'); }, removeItem() {}};
  const list = P.files({shell: [], spots: []});
  await assert.rejects(P.store(list, async () => new Response('{}'), SCOPE, {v: 1, day: DAY, spot: 'a', keptAt: 1}, cs, st), /not keeping site data/);
  assert.equal(await cs.has(P.CACHE), false);
});

// ------------------------------------------------------------------------------ in the page
test('the page loads outingpack.js after outing.js, the offline copy keeps it, and the outing tile calls it once', () => {
  const html = read('src/dipcast/site/index.html'), outing = read('src/dipcast/site/outing.js');
  assert.ok(html.indexOf('<script src="outingpack.js"></script>') > html.indexOf('<script src="outing.js"></script>'));
  assert.ok(read('src/dipcast/site/sw.js').includes('`outingpack.js?v=${BUILD}`'));
  assert.equal(outing.match(/OutingPack\./g).length, 1);
  // The freshness line, the stored-copy mark and turning the offline copy off all reach it.
  assert.ok(html.includes('h += OutingPack.notice();') && html.includes('OutingPack.seen(res);') && html.includes('await OutingPack.drop()'));
  // Nothing beyond the site's own files: no other host is named.
  assert.ok(!/https?:\/\//.test(read('src/dipcast/site/outingpack.js').replace(/^\s*\/\/.*$/gm, '')));
});

test('the privacy notice says what a kept outing stores, that nothing is sent, and when it goes', () => {
  const p = read('src/dipcast/pages/privacy.html');
  assert.match(p, /"Keep this outing for offline use", on an outing on Plan a swim, stores/);
  assert.match(p, /keeping them sends nothing to SwimSignal or anyone else/);
  assert.match(p, /deleted after the outing's day, when you press "Stop keeping it", when you turn off the offline copy/);
});
