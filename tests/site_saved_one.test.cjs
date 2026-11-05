// Saved with one spot (30 Oct 2026): its five days once, on its card, then its page and planning there. Two or more keep
// the grid, the comparison and Find a window, which are for choosing between spots.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const app = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');

test('one spot: no grid, no windows, the card with its week, then its page and the planner', () => {
  assert.match(app, /below \+= spots\.length > 1 \? `<div id="grid-host">\$\{savedGrid\(spots\)\}<\/div>` : '<div id="grid-host"><\/div>';/);
  assert.match(app, /savedCard\(s, true, null, false, from, false, one, true\)/);
  assert.match(app, /\$\{unsave && !withWeek \? '' : week\(s\)\}<\/div>`/);
  assert.match(app, /\+ \(one \? savedOneNext\(spots\[0\]\) : ''\)/);
  assert.match(app, /Going\? <a href="\$\{esc\(planPath\(\) \+ planHereHash\(s\)\)\}" data-plan-here>Plan a swim here<\/a>\./);
  assert.match(app, /if \(spots\.length === 1 && typeof planHere === 'function'\) planHere\(spots\[0\]\);/);
});
test('the grid comes back only for two or more', () => {
  assert.match(app, /if \(host\) host\.innerHTML = sp\.length > 1 \? savedGrid\(sp\) : '';/);
});
