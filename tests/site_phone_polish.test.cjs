// The phone pass of 30 Oct 2026 (320 and 375 px): what it measured and changed.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const app = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');

test('a button inside a sentence has a 43 px tap area without moving the line', () => {
  assert.match(app, /\.linkbtn\.small \{ font-size:inherit; padding:10px 0; margin:-10px 0; \}/);
});
test('the stale notice gives the issue time as the rest of the site does', () => {
  assert.match(app, /old \(issued \$\{issued\(\)\}\)\./);
  assert.doesNotMatch(app, /issued \$\{new Date\(DATA\.generated_at\)\.toLocaleString\('en-GB'\)\}/);
});
test('with nothing saved, no activity note comes before the way to save a spot', () => {
  assert.doesNotMatch(app, /actsChips/);   // the choice moved to Plan a swim (31 Oct 2026)
});
