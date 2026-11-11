// The day a raised spot is forecast low, and the phone map's five days (11 Nov 2026; docs/DESIGN.md, "The day it is
// forecast low"). A raised spot's page offers alerts for the first of the five days at low risk: the Worker's alerts
// for a date, already on, which say each change of that day's level in the page's own words. It is not a message that
// the water is clear, and nothing new is stored or sent. node --test tests/site_day_alert.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const spots = require('../scripts/prerender_spots.js');

const ROOT = path.join(__dirname, '..');
const PAGE = fs.readFileSync(path.join(ROOT, 'src/dipcast/site/index.html'), 'utf8');
const GEN = '2026-11-11T06:56:11+00:00', NOW = Date.parse(GEN);
const DAYS = ['2026-11-11', '2026-11-12', '2026-11-13', '2026-11-14', '2026-11-15'];
const RISK = {low: 0.03, moderate: 0.2, high: 0.5, 'very high': 0.72};
const spot = (id, labels, extra = {}) => ({id, name: 'River Dart, Dartington Pontoon', kind: 'river', source: 'curated', lat: 50.44, lon: -3.69,
  upstream_summary: {overflows: 20}, location: {mode: 'river'}, contributors: [], assumptions: {max_upstream_km: 60, recent_spill_hours: 48},
  now: {label: 'low', risk: 0, discharging_upstream: 0, recent_upstream: 0, monitored_upstream: 20, monitored_weight: 1, upstream_weight: 1},
  days: DAYS.map((date, i) => ({date, label: labels[i], risk: RISK[labels[i]], expected_spilling_overflows: 0, rain_48h_mm: 1})), ...extra});
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();

function page() {
  const store = {getItem: () => null, setItem() {}, removeItem() {}}, root = 'https://example.org/swim/';
  const ctx = vm.createContext({console, URL, URLSearchParams, Intl, history: {state: null}, location: new URL(root),
    navigator: {onLine: true}, localStorage: store, sessionStorage: store, addEventListener() {}, setTimeout, clearTimeout,
    ROOT: new URL(root), map: null, TOUCH: false, STILL: false});
  ctx.window = ctx;
  vm.runInContext(`Date.now = () => ${NOW};`, ctx);
  for (const f of ['eatoday.js', 'experience.js', 'levels.js', 'lists.js'])
    vm.runInContext(fs.readFileSync(path.join(ROOT, 'src/dipcast/site', f), 'utf8'), ctx);
  vm.runInContext(spots.reached(PAGE, ['clearDay', 'clearAlert'], ['ROOT', 'map', 'TOUCH', 'STILL']), ctx);
  vm.runInContext(`setToday("${DAYS[0]}"); DATA = {generated_at: "${GEN}", spots: []};`, ctx);
  return ctx;
}
const call = (ctx, f, ...a) => vm.runInContext(f, ctx)(...a);

test('the day: the first of the five at low risk after a raised one, and never today', () => {
  const ctx = page();
  assert.equal(call(ctx, 'clearDay', spot('a', ['very high', 'high', 'moderate', 'low', 'low'])), DAYS[3]);
  assert.equal(call(ctx, 'clearDay', spot('b', ['moderate', 'low', 'low', 'low', 'low'])), DAYS[1]);
  assert.equal(call(ctx, 'clearDay', spot('c', ['low', 'moderate', 'low', 'low', 'low'])), DAYS[2], 'raised tomorrow, low the day after');
  assert.equal(call(ctx, 'clearDay', spot('d', ['high', 'high', 'high', 'high', 'high'])), null, 'no low day in the five: nothing to ask about');
  assert.equal(call(ctx, 'clearDay', spot('e', ['low', 'low', 'low', 'low', 'low'])), null, 'never raised');
  assert.equal(call(ctx, 'clearDay', spot('f', ['low', 'low', 'low', 'low', 'low'], {upstream_summary: {overflows: 0}})), null, 'no daily forecast here');
});

test('what the page offers: a button with alerts on in this browser, the way to the Saved page with them off, nothing where notifications cannot be had', () => {
  const ctx = page(), saved = '/swim/saved/';
  const ask = call(ctx, 'clearAlert', {state: 'on', date: DAYS[3], on: false, saved});
  assert.match(ask, /^<button type="button" class="btn" data-clear="add"><svg class="ic"[^>]*>.*<\/svg>Alert me if Saturday's forecast changes<\/button>/);
  assert.match(text(ask), /Forecast low risk on Saturday\. A message each time that day's level here changes, up or down\.$/);
  const on = call(ctx, 'clearAlert', {state: 'on', date: DAYS[3], on: true, saved});
  assert.equal(text(on), "Alerts are on for Saturday 14 November here: a message each time that day's level changes. Stop alerts for Saturday");
  assert.match(on, /<button type="button" class="btn quiet" data-clear="stop">/);
  const off = call(ctx, 'clearAlert', {state: 'off', date: DAYS[3], on: false, saved});
  assert.equal(text(off), "To hear if Saturday's forecast here changes, first turn on alerts in this browser, from the Saved page. Go to alerts");
  assert.match(off, /<a href="\/swim\/saved\/" id="clear-to-alerts">Go to alerts<\/a>/);
  assert.doesNotMatch(off, /<button/, 'nothing is turned on from a spot: the Saved page says what turning alerts on sends');
  assert.match(text(call(ctx, 'clearAlert', {state: 'on', date: DAYS[1], on: false, saved})), /Alert me if Thursday's forecast changes Forecast low risk tomorrow\./);
  for (const state of ['none', 'cannot', 'ios', 'inapp', 'blocked']) assert.equal(call(ctx, 'clearAlert', {state, date: DAYS[3], on: false, saved}), '', state);
  assert.equal(call(ctx, 'clearAlert', {state: 'on', date: null, on: false, saved}), '');
  for (const h of [ask, on, off]) assert.doesNotMatch(text(h), /\b(safe|clean|clear|all clear)\b/i);
});

test('the page: asked only at a raised spot with a page of its own, with the dates already kept, and nothing sent until a button is pressed', () => {
  const mount = PAGE.slice(PAGE.indexOf('async function mountClear(d) {'), PAGE.indexOf('\nfunction actions(d) {'));
  assert.match(mount, /const date = PAGE_ID\.test\(d\.id\) && rank\(level\(d\)\) >= 1 \? clearDay\(d\) : null;/);
  assert.match(mount, /const st = await outingPushState\(\);/, 'the push state the outing reads: no permission is asked');
  assert.match(mount, /D\.keptDates\(localStorage\.getItem\(D\.DATES_KEY\), endpoint, today\(\)\)/);
  assert.match(mount, /const turnOn = b\.dataset\.clear === 'add', next = D\.withDate\(read\(\), d\.id, date, turnOn\);/);
  assert.match(mount, /await D\.sendDates\(DATA\.push\.url, st\.sub, next\); mem = next; D\.storeDates\(st\.sub, next\); paint\(\);/);
  assert.equal((mount.match(/sendDates\(/g) || []).length, 1, 'one send, in the click');
  assert.ok(mount.indexOf('sendDates(') > mount.indexOf("addEventListener('click', async"));
  assert.doesNotMatch(mount, /requestPermission|subscribe\(/);
  assert.match(PAGE, /mountClear\(d\);   \/\/ alerts for the day a raised spot is forecast low/);
});

test('a phone\'s full map over the list has the five days as a strip, each with its count; the select stays elsewhere', () => {
  const ctl = PAGE.slice(PAGE.indexOf('lowCtl.onAdd = () => {'), PAGE.indexOf('lowCtl.addTo(map);'));
  assert.match(ctl, /<fieldset class="day-strip list-days map-days" id="mapdays"><legend class="sr">Day shown on the map<\/legend><\/fieldset>/);
  assert.match(ctl, /<select id="mapday"><option value="">Today and tomorrow<\/option><\/select>/, 'Saved and Plan a swim keep today and tomorrow together');
  assert.match(ctl, /el\.querySelector\('#mapdays'\)\.addEventListener\('change', e => setMapDay\(e\.target\.value\)\);/);
  const fill = PAGE.slice(PAGE.indexOf('function fillMapDays() {'), PAGE.indexOf('function setLowOnly('));
  assert.match(fill, /<input type="radio" name="map-day" value="\$\{iso\}"\$\{VIEW\.day === iso \? ' checked' : ''\}>/);
  assert.match(fill, /<b>\$\{lowOn\(iso\)\}<\/b> <span class="nw">low<\/span>/, "the list strip's own count");
  assert.match(PAGE, /document\.querySelectorAll\('input\[name="list-day"\], input\[name="map-day"\]'\)\.forEach\(r => \{ r\.checked = r\.value === VIEW\.day; \}\);/);
  assert.match(PAGE, /\.low-ctl \.map-days \{ display:none; \}/);
  assert.match(PAGE, /body\.view-list\.map-mode \.low-ctl \.map-days \{ display:grid; width:calc\(100vw - 84px\); max-width:420px;/);
  assert.match(PAGE, /body\.view-list\.map-mode \.low-ctl #mapday \{ display:none; \}/);
});
