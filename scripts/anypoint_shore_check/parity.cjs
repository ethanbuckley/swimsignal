// The page's place() on built files against the API's answers (sweep.py), with each miss sorted by cause.
// Run: node parity.cjs <anypoint.js> <files dir> <clicks.json> [outside_england.json]; SHOW=1 lists the misses.
// Clicks are placed as point() places them: the real lake outlines the click needs, then the squares if it needs them.
// Agreement as on #225: the same name and set of overflows, distance within 6 m, lake distance within 3 m,
// dilution within 0.001. Causes for the shore set (docs/ANYPOINT-LAKES-2026-10.md):
//   1 isolated: the page says "isolated lake", the API passes the WFD lake over (no lake centreline within 1.5 km)
//   2 centreline: the same WFD lake, another lake centreline (or one side found none)
//   3 outline: the page and the API place the click by different WFD lakes, or one by none
const fs = require('node:fs'), path = require('node:path');
const A = require(path.resolve(process.argv[2])); const dir = process.argv[3], P = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
const outside = process.argv[5] ? JSON.parse(fs.readFileSync(process.argv[5], 'utf8')) : null;
const cfg = JSON.parse(fs.readFileSync(path.join(dir, 'tiles.json'), 'utf8'));
const lakes = JSON.parse(fs.readFileSync(path.join(dir, 'lakes.json'), 'utf8'));
const memo = {};
const tile = k => memo[k] || (memo[k] = (() => {
  const b = fs.readFileSync(path.join(dir, 'link_index', `${k}.bin`));
  const l = JSON.parse(fs.readFileSync(path.join(dir, 'links', `${k}.json`), 'utf8'));
  return { index: A.decodeIndex(b.buffer.slice(b.byteOffset, b.byteOffset + b.length)), links: l.links };
})());
const outline = i => { const f = path.join(dir, 'lake_outlines', `${i}.json`); return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : null; };
const sets = ['on', 'off', 'shore'];
const res = Object.fromEntries(sets.map(s => [s, { n: 0, agree: 0, outside: 0, causes: {} }])), bad = [];
let fetched = 0;
const class1 = { inside: 0, outside: 0, api_rows: [] };
for (const c of P.clicks) {
  const R = res[c.set];
  if (outside && A.outsideEngland(c.lat, c.lon, outside)) { R.outside++; continue; }
  R.n++;
  const need = A.outlinesNeeded ? A.outlinesNeeded(c.lat, c.lon, lakes, cfg.lake_shore_m) : [];
  fetched += need.length > 0;
  const outlines = Object.fromEntries(need.map(i => [i, outline(i)]));
  const wants = A.needsSquares ? A.needsSquares(c.lat, c.lon, lakes, cfg, outside, outlines) : !A.lakePolygon(c.lat, c.lon, lakes, cfg.lake_shore_m);
  const tiles = Object.fromEntries((wants ? A.squares(c.lat, c.lon, cfg) : []).map(k => [k, tile(k)]));
  const got = A.place(c.lat, c.lon, { cfg, lakes, od: P.od, tiles, outlines });
  const mine = (got.rows || []).map(r => ({ ...r, site_id: P.ids[r.i] })).sort((a, b) => a.site_id.localeCompare(b.site_id));
  const want = [...c.rows].sort((a, b) => a.site_id.localeCompare(b.site_id));
  const why = [];
  if ((got.location?.watercourse ?? null) !== c.watercourse) why.push(`name ${got.location?.watercourse} vs ${c.watercourse}`);
  if (mine.map(r => r.site_id).join() !== want.map(r => r.site_id).join()) why.push(`set ${mine.length} vs ${want.length}`);
  else mine.forEach((r, k) => {
    if (Math.abs(r.dist - want[k].distance_m) > 6) why.push(`${r.site_id} dist ${r.dist} vs ${want[k].distance_m}`);
    if (Math.abs(r.dlake - want[k].lake_distance_m) > 3) why.push(`${r.site_id} lake ${r.dlake} vs ${want[k].lake_distance_m}`);
    if (Math.abs(r.dil - want[k].dilution) > 1e-3) why.push(`${r.site_id} dil ${r.dil} vs ${want[k].dilution}`);
  });
  if (!why.length) { R.agree++; continue; }
  const poly = A.lakePolygon(c.lat, c.lon, lakes, cfg.lake_shore_m, outlines);
  const pageWfd = poly ? poly.poly.wb_id : null, apiIn = c.lake_source === 'polygon';
  const pageLno = got.link ? got.link.lno : null, pmode = got.location?.mode ?? got.mode;
  let cause;
  if (got.mode === 'isolated' && !apiIn && pageWfd === c.wfd) {
    cause = `1 isolated: page isolated lake, API ${c.mode}`;
    class1[poly.d === 0 ? 'inside' : 'outside']++; class1.api_rows.push(c.rows.length);
  } else if (pageWfd !== (apiIn ? c.wfd : null)) cause = `3 outline: page ${pageWfd ? `${poly.d.toFixed(1)} m from ${pageWfd}` : 'no WFD lake'}, API ${apiIn ? `${c.wfd_m.toFixed(1)} m from ${c.wfd}` : c.mode}`;
  else if (apiIn && (got.mode === 'isolated' || (pageLno !== null && pageLno !== c.link_lno))) cause = '2 centreline: same WFD lake, another lake centreline';
  else if (pmode === c.mode && pageLno === c.link_lno) cause = 'same place, rows differ';
  else if (pmode !== c.mode) cause = `mode ${pmode} vs ${c.mode}`;
  else cause = (got.location?.adopted_main_channel || c.adopted) ? 'other link (adopt step)' : 'other nearest link';
  R.causes[cause] = (R.causes[cause] || 0) + 1;
  bad.push({ set: c.set, lat: c.lat, lon: c.lon, cause, page: [pmode, pageLno, pageWfd], api: [c.mode, c.link_lno, c.wfd], why: why.slice(0, 2) });
}
const q = a => { const s = [...a].sort((x, y) => x - y); return s.length ? { n: s.length, zero: s.filter(x => x === 0).length, median: s[Math.floor(s.length / 2)], max: s[s.length - 1] } : {}; };
console.log(JSON.stringify({ dir: path.basename(dir), seed: P.seed, ...res, outlines_fetched: fetched,
  class1: { inside_outline: class1.inside, outside_outline: class1.outside, api_overflows: q(class1.api_rows) } }));
if (process.env.SHOW) for (const b of bad) console.log(JSON.stringify(b));
