const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const PAGE = fs.readFileSync('src/dipcast/site/index.html', 'utf8');

test('the phone map keeps help and area search available after the first-tap hint', () => {
  // In the key since 31 Oct 2026, not as floats of their own over the map's foot.
  const help = PAGE.slice(PAGE.indexOf('const legend = L.control('), PAGE.indexOf('const sayCtl ='));
  assert.match(help, /Forecast for any water/);
  assert.match(help, /Search an area/);
  assert.match(help, /openList\(\); const q = document\.getElementById\('q'\); if \(q\) q\.focus\(\)/);
  assert.match(help, /zoomed out.*zoom in first/s);
  assert.doesNotMatch(PAGE, /const mapHelp =/);
  assert.match(PAGE, /L\.DomUtil\.create\('details', 'map-legend'\); el\.open = !PHONE\.matches/);
  assert.match(PAGE, /<summary>Map key, notices and help<\/summary>/);
});

test('a tap on a dot lists every spot within a fingertip, and a mouse opens a lone one at once', () => {
  const pick = PAGE.slice(PAGE.indexOf('const PICK_PX'), PAGE.indexOf('function styleMarkers('));
  assert.match(pick, /L\.DomEvent\.stopPropagation\(e\)/);
  assert.match(pick, /filter\(\(\[, d\]\) => d <= PICK_PX\)\.sort/);
  assert.match(pick, /spots\.length < 2 && !TOUCH && !PHONE\.matches\) \{ select\(s\.id/);
  assert.match(pick, /spots\.map\(spotItem\)/);
  assert.match(pick, /spots\.length > 3 \? '<button type="button" class="mp-zoom">Zoom in<\/button>'/);
  assert.match(PAGE, /\.on\('click', e => tapSpot\(s, e\)\)/);
  // Gone when the map closes or a spot opens, so it is not waiting on the next visit to the map.
  assert.match(PAGE, /if \(on !== was\) closePick\(\);/);
  assert.match(PAGE, /current = s; DAY = day; closePick\(\);/);
});

test('the list says its risk key once, rain rows keep theirs, and Plan\'s field has room for its words', () => {
  assert.match(PAGE, /<span class="week-label risk" aria-hidden="true">Risk L\/M\/H\/VH<\/span>/);
  assert.match(PAGE, /#spots li:has\(\.week-label\.risk\) ~ li \.week-label\.risk, \.map-pick li:has\(\.week-label\.risk\) ~ li \.week-label\.risk \{ display:none; \}/);
  assert.match(PAGE, /<span class="week-label" aria-hidden="true">Rain mm<\/span>/);
  assert.match(PAGE, /\.plan-go \.plan-from input \{ padding-right:12px; \}/);
  // Every folded tile opens on its name in the display face with the chevron, not the browser's triangle.
  assert.match(PAGE, /details\.sec\.tile > summary \{ font:600 var\(--fs-head\)/);
  assert.match(PAGE, /details\.lists > summary, details\.sec\.tile > summary \{ cursor:pointer; list-style:none;/);
});
