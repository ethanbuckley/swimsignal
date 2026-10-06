// A spot's page follows a swimmer's questions (docs/DESIGN.md, "A swimmer's order"): should I go (the
// answer, the five days, nearby), what is it like at the water (the EA's rating with today's advice, the
// practical guide, then the notes and reviews that mount after it), and why (where the risk comes from,
// the map, the tiles, what the level rests on, the overflows, the day-by-day numbers).
// node --test tests/site_spot_order.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { join } = require('node:path');

const SITE = join(__dirname, '../src/dipcast/site');
const html = fs.readFileSync(join(SITE, 'index.html'), 'utf8');
const render = html.slice(html.indexOf('\nfunction render(d) {'), html.indexOf('\n}\n', html.indexOf('\nfunction render(d) {')));

test('the page puts nearby, then the water, then why, in the order a swimmer asks', () => {
  const at = s => { const i = render.indexOf(s); assert.ok(i >= 0, `render() has no ${s}`); return i; };
  const days = at('Pollution risk, next five days'), near = at('<div id="nearby-host">${nearby(d)}</div>${atWater}');
  const why = at('<div id="sources-host">'), map = at('<span>Upstream</span>'), tiles = at('h += tiles;'), ovs = at('overflowTile(d, total)'), table = at('dayTable(d, total');
  assert.ok(days < near && near < why && why < map && map < tiles && tiles < ovs && ovs < table);
});

test("the EA's rating, with today's advice at its foot, leads the water, and the guide follows it", () => {
  assert.match(render, /atWater = fx\.filter\(o => o\.icon === ICON\.rating\)\.map\(tile\)\.join\(''\)\n\s+\+ \(typeof guideTile === 'function' \? guideTile\(d, serverToday\) : ''\);/);
  assert.match(render, /<div class="tiles">\$\{fx\.filter\(o => o\.icon !== ICON\.rating\)\.map\(tile\)\.join\(''\)\}<\/div>`/);
  // A spot without a forecast keeps the same order: the water before the tiles.
  assert.match(render, /\$\{where\}\$\{atWater\}\$\{tiles\}/);
});

test('the notes and the reviews still find the guide to mount after: it stays a child of the stack', () => {
  for (const f of ['visits.js', 'reviews.js']) assert.match(fs.readFileSync(join(SITE, f), 'utf8'), /#result \.stack > #guide/);
  assert.doesNotMatch(render, /<details class="why"/);   // the guide is never wrapped in a group of its own
});

test('the overflows fold whole, and what their figures mean stays inside the fold', () => {
  const ov = html.slice(html.indexOf('function overflowTile('), html.indexOf('\n}\n', html.indexOf('function overflowTile(')));
  assert.match(ov, /<details class="tile fold" id="overflows"><summary><span class="t-lab">\$\{ICON\.spills\}<span>Overflows that matter most<\/span><\/span><\/summary>/);
  assert.match(ov, /<p class="sub">Live status, and today's modelled chance of a spill/);
  assert.doesNotMatch(ov, /t-more/);   // its corner fold would sit on the fold's own chevron
});
