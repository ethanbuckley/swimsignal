// A spot's back link names the list it returns to (26 October 2026). A spot opened from a shared
// list (saved/#list=Windermere&spots=...) or from one of several named lists said "Saved spots",
// though Back returned to that list. openSpot now keeps the list's name (and a shared list's address)
// in the history state, backTo turns the state into the link's words and address, and bindBack still
// goes back in the history, as before.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const lists = require('../src/dipcast/site/lists.js');
const page = fs.readFileSync('src/dipcast/site/index.html', 'utf8');
const between = (a, b) => { const i = page.indexOf(a), j = page.indexOf(b, i); assert.ok(i >= 0 && j > i, `${a} .. ${b}`); return page.slice(i, j); };
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'})[c]);
const SHARED = '#list=Windermere%20%3Cb%3Eswims%3C%2Fb%3E&spots=osm-windermere-waterhead,bw-ukd1203-45650';

// openSpot, run on its own, with the page around it stood in for: where it is (shown, the address)
// and the lists of my own. Returns the state it pushed.
function open({shown = 'saved', hash = '', many = false, fromMap = false} = {}) {
  const pushed = [];
  const own = many ? [{id: 'l1', name: 'My spots', spots: []}, {id: 'l2', name: 'Weekend', spots: []}] : [{id: 'l1', name: 'Saved spots', spots: []}];
  const noop = () => {};
  const ctx = vm.createContext({
    shown, current: null, DAY: null, location: {hash},
    history: {state: null, pushState(st, t, url) { pushed.push({st, url}); location.hash = ''; }, replaceState: noop},
    readShared: lists.readShared, planDates: () => ['2026-10-26'], manyLists: () => many, listNow: () => own[many ? 1 : 0],
    keepPlace: noop, mapMode: () => fromMap, setMapMode: noop, map: {getCenter: () => ({lat: 0, lng: 0}), getZoom: () => 9, fitBounds: noop},
    spotPath: id => `/spot/${id}/`, render: noop, selLayer: {clearLayers: noop}, RING: noop, MOTION: () => ({}), scrollTop: noop, focusHeading: noop,
    L: {circleMarker: () => ({addTo: noop}), latLngBounds: x => x}});
  const location = ctx.location;
  vm.runInContext(between('function openSpot(', 'const focusHeading') + ';this.openSpot = openSpot;', ctx);
  ctx.openSpot({id: 'osm-windermere-waterhead', lat: 54.4, lon: -2.9, contributors: []}, true, true, null);
  assert.equal(pushed.length, 1);
  return JSON.parse(JSON.stringify(pushed[0].st));   // a plain object of this realm, for deepEqual
}

const ctx = vm.createContext({readShared: lists.readShared, savedPath: () => '/swim/saved/', planPath: () => '/swim/plan/', ROOT: {pathname: '/swim/'}});
vm.runInContext(between('function backTo(', '// The top of a spot') + ';this.backTo = backTo;', ctx);
const backTo = st => ({...ctx.backTo(st)});   // a plain object of this realm, for deepEqual
// The link as spotTop writes it: its own template, run on backTo's answer.
const template = between('<a href="${esc(back.href)}" class="back"', '${saveButton(d)}');
const link = st => vm.runInNewContext('`' + template + '`', {back: ctx.backTo(st), esc});

test("from a shared list the back link is the list's name, escaped, and goes to the list", () => {
  const st = open({hash: SHARED});
  assert.equal(st.from, 'saved');
  assert.equal(st.back, 'Windermere <b>swims</b>');
  assert.equal(st.backHash, SHARED);   // read before the address became the spot's
  assert.equal(link(st), `<a href="/swim/saved/${SHARED.replace('&', '&amp;')}" class="back" id="back"><span class="bn">Windermere &lt;b&gt;swims&lt;/b&gt;</span></a>`);
  // A link from before lists (#spots=a,b) has no name: "Shared list", as its page says.
  assert.equal(backTo(open({hash: '#spots=grasmere'})).label, 'Shared list');
});

test('from one of several lists of my own it is that list, with the plain Saved address', () => {
  const st = open({many: true});
  assert.equal(st.back, 'Weekend');
  assert.equal(st.backHash, undefined);
  assert.deepEqual(backTo(st), {label: 'Weekend', named: true, href: '/swim/saved/'});
});

test('from a single list, a plan, the list or the map it is as before', () => {
  const one = open();
  assert.deepEqual(one, {spot: 'osm-windermere-waterhead', from: 'saved'});
  assert.deepEqual(backTo(one), {label: 'Saved spots', named: false, href: '/swim/saved/'});
  assert.equal(link(one), '<a href="/swim/saved/" class="back" id="back">Saved spots</a>');   // no span: only a list's own name has one
  assert.deepEqual(open({shown: 'plan', hash: SHARED, many: true}), {spot: 'osm-windermere-waterhead', from: 'plan'});
  assert.deepEqual(backTo({from: 'plan'}), {label: 'Plan a swim', href: '/swim/plan/'});
  assert.deepEqual(open({shown: 'list', many: true}), {spot: 'osm-windermere-waterhead', from: 'list'});
  assert.deepEqual(backTo({from: 'list'}), {label: 'All spots', href: '/swim/'});
  assert.equal(open({fromMap: true, many: true}).from, 'map');   // a marker on the full map, whatever list Saved shows
  assert.deepEqual(backTo({from: 'map'}), {label: 'Map', href: '/swim/'});
  assert.deepEqual(backTo(null), {label: 'All spots', href: '/swim/'});   // a direct visit: no state
});

test('only a list address goes into the link', () => {
  assert.equal(backTo({from: 'saved', back: 'X', backHash: '#about'}).href, '/swim/saved/');
  assert.equal(backTo({from: 'saved', back: 'X', backHash: 'spots=a'}).href, '/swim/saved/');   // not after a #: no path of its own
  assert.equal(backTo({from: 'saved', back: 'X', backHash: {}}).href, '/swim/saved/');
  assert.equal(link({from: 'saved', back: 'X', backHash: '#list=a"onclick=x&spots=b'}), '<a href="/swim/saved/#list=a&quot;onclick=x&amp;spots=b" class="back" id="back"><span class="bn">X</span></a>');
});

test('spotTop writes the link from backTo, escaped, and bindBack still goes back in the history', () => {
  assert.match(between('function spotTop(', '// What Save did'), /const back = backTo\(history\.state\);\n\s*let h = `<div class="top-row"><a href="\$\{esc\(back\.href\)\}" class="back" id="back">\$\{back\.named \? `<span class="bn">\$\{esc\(back\.label\)\}<\/span>` : esc\(back\.label\)\}<\/a>\$\{saveButton\(d\)\}<\/div>`;/);
  // A list's name is up to 40 characters: it gives way to Save on a 320 px phone, on one line.
  assert.match(page, /\.top-row \.back:has\(\.bn\) \{ flex:0 1 auto; min-width:0; \}/);
  assert.match(page, /\.back \.bn \{ min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; \}/);
  for (const state of [{spot: 's', from: 'saved', back: 'Windermere', backHash: SHARED}, {spot: 's', from: 'saved', back: 'Weekend'}, {spot: 's', from: 'saved'}]) {
    let backs = 0, pushes = 0, clicked = null;
    const b = {addEventListener: (k, f) => { clicked = f; }};
    const c = vm.createContext({document: {getElementById: id => (id === 'back' ? b : null)}, plainClick: () => true,
      history: {state, back: () => { backs++; }, pushState: () => { pushes++; }}, keepPlace() {}, renderList() {}, scrollTop() {}, ROOT: {pathname: '/swim/'}});
    vm.runInContext(between('function bindBack(', '\n\n') + ';this.bindBack = bindBack;', c);
    c.bindBack();
    let prevented = false;
    clicked({preventDefault() { prevented = true; }});
    assert.deepEqual([backs, pushes, prevented], [1, 0, true]);
  }
});
