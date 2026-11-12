// A first visit (30 Oct 2026) had a line under the day strip saying what to do ("Open a spot to see why. Save the ones
// you use to keep them at the top."). It went on 12 Nov 2026 (docs/DESIGN.md, "The home page, tightened"): the day's
// count and the spots at very high risk now say what the page is, and the line stood between the controls and them.
// The built page showed it to everyone until the script hid it, so a returning visitor saw it come and go.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const app = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const build = fs.readFileSync(path.join(__dirname, '../scripts/build_site.py'), 'utf8');

test('no hint line under the day strip, in the page or in the built opening', () => {
  for (const s of [app, build]) { assert.doesNotMatch(s, /strip-note/); assert.doesNotMatch(s, /Open a spot to see why/); }
});
test('the day\'s count is not said twice on a first visit', () => {
  assert.match(app, /items\.length && !\(first && !first\.hidden\) \? overview\(items\)/);
});
test('the saved visitor\'s feed is drawn at once, with its heading, and goes only when no saved spot has an overflow', () => {
  assert.match(app, /class="group tile home-feed loading" id="home-feed" aria-labelledby="feed-h">\$\{feedHead\(saved\.length\)\}/);
  assert.match(app, /if \(!have\.length\) \{ host\.innerHTML = ''; host\.hidden = true; return; \}/);
});
