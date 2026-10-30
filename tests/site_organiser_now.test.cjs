// The organisers' event view says what the overflows upstream were doing at the last update (30 Oct 2026, from an event
// organiser: rain and releases change things quickly). From the live feeds' counts; the silent ones never as dry.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const O = require('../src/dipcast/site/organisers.js');

test('spills at the last update, with the silent ones as unknown', () => {
  assert.equal(O.orgNow({monitored_upstream: 26, discharging_upstream: 0}, 29),
    'None of the 26 that report live was discharging; 3 give no live reading, so could be spilling unseen. A spill\'s water takes hours to days to arrive, so look again the evening before and on the morning.');
  assert.match(O.orgNow({monitored_upstream: 20, discharging_upstream: 2}, 20), /^<b>2<\/b> of the 20 that report live were discharging\. /);
  assert.equal(O.orgNow({monitored_upstream: 0}, 5), 'None of the 5 report live, so whether they are spilling is not known.');
});
test('it is a row of the event view, under the day\'s spill forecast', () => {
  const src = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/organisers.js'), 'utf8');
  assert.match(src, /if \(total\) rows\.push\(row\('Spills at the last update', orgNow\(s\.now \|\| \{\}, total\)\)\);/);
});
