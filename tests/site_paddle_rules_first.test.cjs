// A lake's rules for boats and boards before someone plans (30 Oct 2026): first in a paddle outing's Access, and on a
// spot's page for someone who said they paddle, in the guide's own words with who says so.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const O = require('../src/dipcast/site/outing.js');
const app = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');

test('a paddle outing\'s Access starts with the rules for boats and boards', () => {
  const all = new Set(['parking', 'path', 'entry', 'exit', 'launch', 'carry', 'paddle']);
  assert.equal(O.outingAccessTopics('paddle', all)[0], 'paddle');
  assert.ok(!O.outingAccessTopics('swim', all).includes('paddle'));   // a swim's Access is as before
});
test('a paddler sees the first rule beside Plan a swim here, from the guide, with its source', () => {
  assert.match(app, /\+ paddleRules\(d\) \+ paddleFromHere\(d\);/);
  assert.match(app, /x\.topic === 'paddle' && x\.status === 'confirmed'/);
  assert.match(app, /<b>Paddling here:<\/b> \$\{esc\(f\.text\)\} <span class="muted">\(\$\{esc\(f\.source_name \|\| 'the guide'\)\}/);
  assert.match(app, /const f = actDefault\(acts\(\)\) && d\.guide/);   // only for a paddle or a board
});
