// Your places on Explore: saved cards say what has changed since you last looked, as on Saved, now that Explore opens
// on today; the look is noted there. What you do on the water is chosen on Plan a swim, not here (31 Oct 2026).
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const app = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');

test('a saved card gives the change since your last look for no day or today, never for another day', () => {
  assert.match(app, /\$\{\(!iso \|\| iso === today\(\)\) && typeof sinceSaid === 'function' \? sinceSaid\(s, DATA\.generated_at\) : ''\}`/);
  assert.match(app, /if \(!savedGroup\.hidden && \(!VIEW\.day \|\| VIEW\.day === today\(\)\) && typeof lookedAt === 'function'\) lookedAt\(/);
});

test('Explore\'s saved spots end with the cards: no activity choice, which changed nothing on them (31 Oct 2026)', () => {
  assert.match(app, /id="saved-list">\$\{saved\.map\(s => savedCard\(s, false, VIEW\.day\)\)\.join\(''\)\}<\/ul><\/div>` : ''\);/);
  assert.match(app, /if \(saved\.length\) bindItems\(document\.getElementById\('saved-list'\)\);/);
  assert.doesNotMatch(app, /data-act="|aria-label="What you do on the water"/);
});

test('the next outing and the saved spots are one tile, Your places, hidden with both its parts', () => {
  assert.match(app, /<section class="group tile" id="places-group" aria-labelledby="places-h"><h2 class="group-head" id="places-h">Your places<\/h2>\$\{places\}<\/section>`/);
  assert.match(app, /<div class="places-part" id="outing-group" data-day="\$\{esc\(o\.day\)\}"><h3 class="places-sub" id="outing-h">Next outing<\/h3>`/);
  assert.match(app, /<div class="places-part" id="saved-group"><h3 class="places-sub" id="saved-h">Saved spots<\/h3>/);
  assert.match(app, /if \(placesGroup\) placesGroup\.hidden = \[outingGroup, savedGroup\]\.every\(g => !g \|\| g\.hidden\);/);
  // Nothing saved or planned: the hint, after a spot has been opened, never on a first look.
  assert.match(app, /: OPENED \? `<p class="save-hint tile">\$\{BOOKMARK\}<span>Open a spot and press Save to keep it here\.<\/span><\/p>` : '';/);
});
