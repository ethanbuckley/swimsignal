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
  // The five days are daysTile's, which the build also writes into the spot's own page (prerender_spots.js).
  assert.match(html, /\nconst daysTile = d => `<section class="tile" aria-labelledby="days-h">[^\n]*Pollution risk, next five days/);
  const days = at('<div class="stack"><div class="col-go">${daysTile(d)}'), near = at('<div id="nearby-host">${nearby(d)}</div>${atWater}');
  const why = at('<div id="sources-host">'), map = at('<span>Upstream</span>'), tiles = at('h += tiles + `</div><div class="col-more">${more}`;'), ovs = at('h += overflowTile(d, '), table = at('dayTable(d, total');
  assert.ok(days < render.indexOf('${conditionsSummary(d)}', days) && render.indexOf('${conditionsSummary(d)}', days) < near);
  assert.ok(days < near && near < why && why < map && map < tiles && tiles < ovs && ovs < table);
});

test("the EA's rating, with today's advice at its foot, leads the water, and the guide follows it", () => {
  // Between them, the lab results an organisation sent (measured.js), when there are any.
  assert.match(render, /atWater = fx\.filter\(o => o\.icon === ICON\.rating\)\.map\(tile\)\.join\(''\)\n\s+\+ \(typeof measuredTile === 'function' \? measuredTile\(d, Date\.now\(\)\) : ''\)[^\n]*\n\s+\+ \(typeof guideTile === 'function' \? guideTile\(d, serverToday\) : ''\);/);
  // The other tiles: the open day's forecast, then the latest readings (dayTiles, nowTiles), then a lake spot's one
  // link to its lake's past measured temperatures (lakeTempHost, tests/site_lake_temperatures.test.cjs).
  assert.match(render, /const tiles = dayTiles\(d, DAY\) \+ nowTiles\(d\) \+ lakeTempHost\(d\);/);
  assert.match(html, /const fx = facts\(d, x \? x\.date : null\)\.filter\(o => o\.icon !== ICON\.rating && !o\.live && !IN_CONDITIONS\(o\)\);/);
  // A spot without a forecast keeps the same order: the water before the tiles, which start the
  // desktop's second column.
  assert.match(render, /\$\{where\}\$\{atWater\}<\/div><div class="col-why">\$\{tiles\}<\/div><div class="col-more">\$\{more\}/);
});

test('the notes and the reviews still find the guide to mount after, in the stack or a desktop column', () => {
  for (const f of ['visits.js', 'reviews.js']) assert.match(fs.readFileSync(join(SITE, f), 'utf8'), /#result \.stack #guide/);
  // The guide is in the first column, with the water: the columns hold the stack's order, split once.
  assert.ok(render.indexOf('${atWater}</div><div class="col-why">') > 0);
  assert.doesNotMatch(render, /<details class="why"/);   // the guide is never wrapped in a group of its own
});

test('the overflows fold whole, and what their figures mean stays inside the fold', () => {
  const ov = html.slice(html.indexOf('function overflowTile('), html.indexOf('\n}\n', html.indexOf('function overflowTile(')));
  assert.match(ov, /<details class="tile fold" id="overflows"><summary><span class="t-lab">\$\{ICON\.spills\}<span>Overflows that matter most<\/span><\/span><\/summary>/);
  // The caption says what the order is (11 Oct 2026): it said "the 10 with the most reach" over a list
  // where 80% came above 98%.
  assert.match(ov, /<p class="sub">\$\{total > n \? `The \$\{n\} of the \$\{total\} overflows upstream that matter most this week`/);
  assert.match(ov, /most first: `\n\s+\+ 'one matters more the larger its model weight here, the likelier it is to spill this week, and if it is discharging now\. '/);
  assert.doesNotMatch(ov, /with the most reach of/);
  assert.doesNotMatch(ov, /t-more/);   // its corner fold would sit on the fold's own chevron
});
