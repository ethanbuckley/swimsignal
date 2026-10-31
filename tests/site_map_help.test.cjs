const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const PAGE = fs.readFileSync('src/dipcast/site/index.html', 'utf8');

test('the phone map keeps help and area search available after the first-tap hint', () => {
  const help = PAGE.slice(PAGE.indexOf('const mapHelp ='), PAGE.indexOf('function ovKey('));
  assert.match(help, /Forecast for any water/);
  assert.match(help, /Search an area/);
  assert.match(help, /openList\(\); const q = document\.getElementById\('q'\); if \(q\) q\.focus\(\)/);
  assert.match(help, /zoomed out.*zoom in first/s);
  assert.match(PAGE, /L\.DomUtil\.create\('details', 'map-legend'\); el\.open = !PHONE\.matches/);
  assert.match(PAGE, /<summary>Map key and official notices<\/summary>/);
});
