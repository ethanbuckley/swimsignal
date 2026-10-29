// Your places on Explore: saved cards say what has changed since you last looked, as on Saved, now that Explore opens
// on today; the look is noted there; and what you do on the water sits at the foot of the saved spots.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const app = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');

test('a saved card gives the change since your last look for no day or today, never for another day', () => {
  assert.match(app, /\$\{\(!iso \|\| iso === today\(\)\) && typeof sinceSaid === 'function' \? sinceSaid\(s, DATA\.generated_at\) : ''\}<\/li>`;/);
  assert.match(app, /if \(!savedGroup\.hidden && \(!VIEW\.day \|\| VIEW\.day === today\(\)\) && typeof lookedAt === 'function'\) lookedAt\(/);
});

test('Explore\'s saved spots end with the activity choice, bound as on Saved', () => {
  assert.match(app, /id="saved-list">\$\{saved\.map\(s => savedCard\(s, false, VIEW\.day\)\)\.join\(''\)\}<\/ul>\$\{actsChips\(undefined, true\)\}<\/section>`/);
  assert.match(app, /if \(saved\.length\) \{ bindItems\(document\.getElementById\('saved-list'\)\); bindActs\(\); \}/);
});

test('Explore says it in one line; Saved in full', () => {
  assert.match(app, /What you do on the water, if you like: a boat or a board gets launching, carrying and places to finish\. The level is the same for everyone\./);
  assert.match(app, /The level is for the water, the same for everyone in it, and official advice always shows\./);
});
