// The traced river on a spot's map (index.html, decodeLine and drawTrace; build_site.write_traces;
// docs/REVIEW-2026-10-16.md, G6): the page reads the build's encoded polylines, draws them only from
// zoom 10, in the pane under the overflows, and shows the key line while the line is drawn.
// node --test tests/site_trace.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const pageSrc = html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n');
const plain = v => JSON.parse(JSON.stringify(v));   // arrays made in the page's context
const pageDefs = names => names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
  assert.ok(i >= 0, `no ${n} in index.html`);
  let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
  return pageSrc.slice(i, j).join('\n'); }).join('\n');

test('decodeLine reads Google\'s encoded polyline, as src/dipcast/trace.py writes it', () => {
  const ctx = vm.createContext({});
  vm.runInContext(pageDefs(['decodeLine']), ctx);
  // Google's own example (developers.google.com/maps/documentation/utilities/polylinealgorithm); tests/test_trace.py encodes the same.
  assert.deepEqual(plain(vm.runInContext('decodeLine', ctx)('_p~iF~ps|U_ulLnnqC_mqNvxq`@')), [[38.5, -120.2], [40.7, -120.95], [43.252, -126.453]]);
  assert.deepEqual(plain(vm.runInContext('decodeLine', ctx)('')), []);
});

test('drawn from zoom 10 only, under the overflows, and its key shown only while it is drawn', async () => {
  let zoom = 12;
  const added = [], keys = [{ hidden: true }, { hidden: true }], fetched = [];
  const contribLayer = { removeLayer: l => { const i = added.indexOf(l); if (i >= 0) added.splice(i, 1); ctx.onRemove(l); } };
  const L = { polyline: (lines, o) => { const l = { lines, o, addTo: g => { added.push(l); return l; } }; return l; } };
  const handlers = {};
  const map = { getZoom: () => zoom, on: (e, f) => { handlers[e] = f; }, createPane: () => ({ style: {} }) };
  const ctx = vm.createContext({ L, map, contribLayer, current: null, RING: () => '#0f5a61',
    document: { querySelectorAll: q => q === '.trkey' ? keys : [] },
    fetch: async u => { fetched.push(u); return { ok: true, json: async () => ({ id: 'w', lines: ['_p~iF~ps|U_ulLnnqC'] }) }; } });
  vm.runInContext('let current = null;' + pageSrc.slice(pageSrc.findIndex(l => l.startsWith("map.createPane('trace')")),
    pageSrc.findIndex(l => l.startsWith("map.on('layerremove'")) + 1).join('\n') + '\nthis.onRemove = l => handlers.layerremove({ layer: l });', Object.assign(ctx, { handlers }));
  const settle = () => new Promise(r => setTimeout(r, 0));
  vm.runInContext('current = { id: "w", detail_file: "spot/w.json" }', ctx);
  zoom = 9; vm.runInContext('drawTrace()', ctx); await settle();
  assert.equal(added.length, 0); assert.equal(fetched.length, 0); assert.ok(keys.every(k => k.hidden));
  zoom = 11; handlers.zoomend(); await settle();
  assert.deepEqual(plain(fetched), ['data/spot/w-trace.json']);
  assert.equal(added.length, 1);
  assert.deepEqual(plain(added[0].lines), [[[38.5, -120.2], [40.7, -120.95]]]);
  assert.equal(added[0].o.pane, 'trace'); assert.equal(added[0].o.color, '#0f5a61'); assert.equal(added[0].o.interactive, false);
  assert.ok(keys.every(k => !k.hidden));
  zoom = 9; handlers.zoomend(); await settle();
  assert.equal(added.length, 0); assert.ok(keys.every(k => k.hidden));
  zoom = 13; handlers.zoomend(); await settle();
  assert.equal(added.length, 1); assert.equal(fetched.length, 1);   // asked for once a spot
  vm.runInContext('current = null', ctx); handlers.zoomend(); await settle();
  assert.equal(added.length, 0);
});

test('the pane sits under the overlay pane, where the overflows\' circles are drawn, and both keys name the line', () => {
  assert.match(html, /map\.createPane\('trace'\)\.style\.zIndex = 350;/);   // Leaflet's overlayPane is 400
  assert.match(html, /<div class="trkey" hidden><span class="trline"><\/span>The water that reaches this spot<\/div>/);
  assert.match(html, /<p class="t-key trkey" hidden><span class="trline"><\/span>the water that reaches this spot<\/p>/);
  assert.match(html, /\.trline \{[^}]*border-top:2px solid var\(--brand\)/);
});
