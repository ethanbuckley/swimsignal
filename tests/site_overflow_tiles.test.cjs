// The map's overflow layer by tile (docs/REVIEW-2026-10-16.md, C4): index.html's loadOverflows asks
// for the tiles of data/overflows/ in view (build_site.write_overflow_tiles), keeps the last OV_KEEP,
// and draws the overflows inside the view, as it drew them from the whole file before.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const block = page.slice(page.indexOf('let ovCall = 0;'), page.indexOf("map.on('moveend', () => loadOverflows()"));

// The same points as tests/test_site_pages.py's test of build_site.overflow_tile, so the page and the
// build put an overflow in the same tile.
const TILES = [[51.5074, -0.1278, 511, 340], [54.05, -1.95, 506, 328], [50.1188, -5.5376, 496, 346], [55.7, -2.0, 506, 320], [52.0, 0.0, 512, 338]];

// A map showing [south, west, north, east] at zoom z, and files answering fetch: {path: features}.
function page_(files, view, z = 12) {
  const asked = [], drawn = [];
  const [s, w, n, e] = view;
  const ctx = vm.createContext({
    asked, drawn, Promise, Map, Set, Math, Error,
    PHONE: { matches: false }, mapMode: () => true, current: null, ovKey: () => {},
    map: { getZoom: () => z, getBounds: () => ({ getNorth: () => n, getSouth: () => s, getWest: () => w, getEast: () => e,
      contains: ([lat, lon]) => lat >= s && lat <= n && lon >= w && lon <= e }) },
    ovLayer: { clearLayers: () => { drawn.length = 0; } },
    L: { geoJSON: fc => ({ addTo: () => { drawn.push(...fc.features.map(f => f.properties.site_id)); } }) },
    fetch: async url => { asked.push(url); const body = files[url];
      return body === undefined ? { ok: false, status: 404 } : { ok: true, json: async () => body }; },
  });
  vm.runInContext(block + '\nthis.load = loadOverflows; this.ovTile = ovTile; this.ovFetch = ovFetch; this.keep = OV_KEEP;'
    + '\nthis.cache = () => [...OV_TILES.keys()];', ctx);
  return ctx;
}
const ov = (id, lat, lon) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] }, properties: { site_id: id } });

test('a point is in the same zoom 10 tile as the build puts it', () => {
  const ctx = page_({}, [0, 0, 0, 0]);
  for (const [lat, lon, x, y] of TILES) assert.deepEqual([...ctx.ovTile(lat, lon, 10)], [x, y], `${lat},${lon}`);
});

test('only the tiles in view that have overflows are asked for, and only the overflows in view are drawn', async () => {
  // Near Burnsall: a view across tiles 505-328 and 506-328, whose shared edge is at lon -2.109.
  const files = { 'data/overflows/index.json': { z: 10, tiles: ['505-328', '506-328', '507-328', '511-340'] },
    'data/overflows/505-328.json': { features: [ov('W1', 54.06, -2.15), ov('far-W', 54.06, -2.4)] },
    'data/overflows/506-328.json': { features: [ov('E1', 54.04, -1.93)] } };
  const ctx = page_(files, [54.0, -2.2, 54.1, -1.9]);
  await ctx.load();
  assert.deepEqual(ctx.asked.sort(), ['data/overflows/505-328.json', 'data/overflows/506-328.json', 'data/overflows/index.json']);
  assert.deepEqual(ctx.drawn.sort(), ['E1', 'W1']);   // far-W is in a fetched tile but out of view
  await ctx.load();   // a move within the same tiles: nothing asked for again
  assert.equal(ctx.asked.length, 3);
});

test('a tile that failed is asked for again on the next move; the rest are kept', async () => {
  const files = { 'data/overflows/index.json': { z: 10, tiles: ['505-328', '506-328'] },
    'data/overflows/505-328.json': { features: [ov('W1', 54.06, -2.15)] } };   // 506-328 answers 404
  const ctx = page_(files, [54.0, -2.2, 54.1, -1.9]);
  await assert.rejects(ctx.load());
  assert.deepEqual(ctx.cache(), ['505-328']);
  files['data/overflows/506-328.json'] = { features: [ov('E1', 54.04, -1.93)] };
  await ctx.load();
  assert.deepEqual(ctx.drawn.sort(), ['E1', 'W1']);
  assert.equal(ctx.asked.filter(u => u.endsWith('505-328.json')).length, 1);
  assert.equal(ctx.asked.filter(u => u.endsWith('506-328.json')).length, 2);
});

test('below zoom 9 nothing is asked for', async () => {
  const ctx = page_({}, [50, -6, 56, 2], 8);
  await ctx.load();
  assert.deepEqual(ctx.asked, []);
});

test('the cache keeps the most recently used OV_KEEP tiles', () => {
  const ctx = page_({}, [0, 0, 0, 0]);
  for (let i = 0; i < ctx.keep; i++) ctx.ovFetch(`t${i}`).catch(() => {});
  ctx.ovFetch('t0').catch(() => {});   // used again: now the most recent
  ctx.ovFetch('new').catch(() => {});   // one over: the least recently used, t1, goes
  const kept = ctx.cache();
  assert.equal(kept.length, ctx.keep);
  assert.ok(kept.includes('t0') && kept.includes('new') && !kept.includes('t1'));
  assert.ok(ctx.keep >= 96, `OV_KEEP ${ctx.keep}: a zoom 9 view on a wide screen needs about 100 tiles`);
});
