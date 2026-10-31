// Sampling planner (src/dipcast/site/sampling-planner.js, the cost lines on sampling-planner.html): arithmetic from the
// reader's samples, price and sites, and the simulation run nearest in samples per site, copied from the export
// (data/research/sampling_planner.v1.json). A budget far from any run says the simulation says nothing about it.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const S = require('../src/dipcast/site/sampling-planner.js');

const DOC = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'research', 'sampling_planner.v1.json'), 'utf8'));
const RUNS = DOC.simulation.runs;

test('the default season costs its samples times the price, and is the failed test', () => {
  const l = S.spLines(RUNS, 60, 100, 12);
  assert.equal(l[0], '60 samples at £100 each: £6,000 for the season, before travel and staff time.');
  assert.equal(l[1], 'Over a 20-week season, about 3 a week.');
  assert.equal(l[2], 'Shared equally over 12 sites, about 5 each.');
  assert.match(l[3], /lower error than equal coverage in 58\.5% of 200 made-up worlds/);
  assert.match(l[3], /0\.000189 \(95% interval 0\.000077 to 0\.000306\)\. The interval is above 0\. The test needed 60%, so the policy failed\./);
});

test('ten per site is the budget-120 check, whose interval spans 0; never the sites-alike run', () => {
  const l = S.spLines(RUNS, 120, 85.5, 12);
  assert.equal(l[0], '120 samples at £85.5 each: £10,260 for the season, before travel and staff time.');
  assert.match(l[3], /in 51% of 100 made-up worlds.*−0\.000066 to 0\.000179\)\. The interval includes 0: no clear difference\. This run was a check/);
  assert.equal(S.spNearest(RUNS, 5).run, 'main');
});

test('a budget far from both runs, or fewer samples than sites, is said plainly', () => {
  const few = S.spLines(RUNS, 8, 100, 12);
  assert.equal(few[2], 'Fewer samples than sites: at least 4 of the 12 sites would get none.');
  assert.match(few[3], /says nothing about this budget/);
  assert.match(S.spLines(RUNS, 300, 100, 12)[3], /About 25 per site is outside that/);
  assert.deepEqual(S.spLines(RUNS, 0, 100, 12), ['Enter a number of samples, a price and a number of sites.']);
});
