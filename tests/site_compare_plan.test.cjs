// From a comparison to a plan without choosing the spot again (index.html, compareTable and compareToPlan).
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const app = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');

test('each column under its name and advice has Plan here, for spots the planner can place', () => {
  assert.match(app, /canPlanHere\(s\) \? `<button type="button" class="linkbtn cmp-plan" data-compare-plan="\$\{esc\(s\.id\)\}" aria-label="Plan an outing at \$\{esc\(s\.name\)\}">Plan here<\/button>` : ''\}<\/th>`/);
  // The advice still comes before it in the head.
  assert.ok(app.indexOf("eaTodayTag(s) : ''}`") < app.indexOf('data-compare-plan="${esc(s.id)}"'));
});
test('on Plan it makes that spot the outing in the plan shown; elsewhere it opens the planner on it', () => {
  const fn = app.slice(app.indexOf('function compareToPlan('), app.indexOf('function drawComparison('));
  assert.match(fn, /if \(onPlanPage\(\)\) \{\n    const next = outingChanged\(PLAN, 'spot'\);/);
  assert.match(fn, /PLAN\.spot = s\.id; if \(PLAN\.backup === s\.id\) delete PLAN\.backup;/);
  assert.match(fn, /PLAN_NEW = true; openPlan\(planFromSpot\(s, planBase\(\), planDates\(\)\.includes\(day\) \? day : null\)\);/);
  assert.match(app, /box\.querySelectorAll\('\[data-compare-plan\]'\)\.forEach\(b => b\.addEventListener\('click', \(\) => compareToPlan\(/);
});
