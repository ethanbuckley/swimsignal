// The phone's small location map is aria-hidden, so nothing inside it may take keyboard focus
// (axe's aria-hidden-focus), but its credit must stay on the map: OpenStreetMap's licence and the
// tile provider's terms ask for it there.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const page = fs.readFileSync('src/dipcast/site/index.html', 'utf8');
const miniMapSource = page.slice(page.indexOf('function miniMap(s)'), page.indexOf('const fitAll ='));

test('the small map stays hidden from screen readers and keeps its credit', () => {
  assert.match(page, /<div id="loc-map" aria-hidden="true"><\/div>/);
  assert.ok(miniMapSource.includes('MINI.attributionControl.setPrefix(false)'), 'the credit control is kept, only its Leaflet prefix goes');
  assert.ok(!/attributionControl:\s*false/.test(page), 'no map drops its credit');
  // The links exist only once the tile layer is on the map, so the fix runs after it.
  const tilesAt = miniMapSource.indexOf('tiles().addTo(MINI)'), fixAt = miniMapSource.indexOf('keepOutOfTabOrder(el)');
  assert.ok(tilesAt > 0 && fixAt > tilesAt, 'keepOutOfTabOrder runs after the tiles are added');
  // A redraw of the page removes the old map, and its watcher with it.
  assert.ok(miniMapSource.indexOf('MINI_WATCH.disconnect()') < miniMapSource.indexOf('L.map(el'));
});

test('the main map is not aria-hidden: its credit links may take focus', () => {
  assert.match(page, /<div id="map"(?![^>]*aria-hidden)[^>]*>/);
  assert.ok(!/id="spot-map"[^>]*aria-hidden/.test(page), 'the Upstream slot holds the main map and is not hidden');
});

test('keepOutOfTabOrder takes the credit links out of the Tab order, now and after Leaflet redraws them', () => {
  const source = page.slice(page.indexOf('const UNFOCUSABLE'), page.indexOf('let MINI = null'));
  let watcher = null;
  class MutationObserver {
    constructor(cb) { this.cb = cb; watcher = this; }
    observe(el, opts) { this.el = el; this.opts = opts; }
    disconnect() { this.el = null; }
  }
  const ctx = vm.createContext({MutationObserver});
  vm.runInContext(source + ';globalThis.keep = keepOutOfTabOrder; globalThis.SEL = UNFOCUSABLE;', ctx);
  for (const s of ['a[href]', 'button', 'input', '[tabindex]:not([tabindex="-1"])']) assert.ok(ctx.SEL.includes(s), s);

  const link = text => { const attrs = {}; return {text, attrs, setAttribute: (k, v) => { attrs[k] = v; }}; };
  let links = [link('OpenStreetMap'), link('CARTO')];
  const asked = [];
  const el = {querySelectorAll: sel => { asked.push(sel); return links; }};
  const w = ctx.keep(el);
  assert.equal(w, watcher);
  assert.deepEqual(links.map(l => l.attrs.tabindex), ['-1', '-1']);
  assert.equal(asked[0], ctx.SEL);
  assert.equal(watcher.el, el);
  assert.deepEqual({...watcher.opts}, {childList: true, subtree: true});

  // Leaflet rewrites the credit's innerHTML when a layer's attribution changes: new links.
  links = [link('OpenStreetMap'), link('CARTO'), link('Someone new')];
  watcher.cb();
  assert.deepEqual(links.map(l => l.attrs.tabindex), ['-1', '-1', '-1']);
});
