// "Plan an outing here" on a spot's page (index.html, actions and planHere; plan.js, planFromSpot): the planner as it
// is, on this spot, starting from it. Kept at once unless it would replace an outing still to come, which then waits
// for "Keep this outing" as an outing from a link does, said as a new outing, not one from a link.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const P = require('../src/dipcast/site/plan.js');
const O = require('../src/dipcast/site/outing.js');
L.setToday('2026-10-26');
const DATES = ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30'];
const SPOT = {id: 'wharfe-bolton-abbey', name: 'River Wharfe, Bolton Abbey', lat: 53.984, lon: -1.888};

test('the plan opens on the spot, from the spot, on the day shown, with the kept plan\'s distance and activity', () => {
  const p = P.readPlan(P.planFromSpot(SPOT, {...P.PLAN_DEFAULT, day: DATES[0], within: 10, act: 'paddle'}, DATES[3]), DATES);
  assert.deepEqual(p, {day: DATES[3], from: {name: SPOT.name, lat: 53.984, lon: -1.888}, within: 10, kind: 'all', spot: SPOT.id, act: 'paddle'});
  // No day picked on the page: the plan's own day. Nothing kept: the defaults.
  assert.equal(P.readPlan(P.planFromSpot(SPOT, {...P.PLAN_DEFAULT, day: DATES[1]}), DATES).day, DATES[1]);
  const fresh = P.readPlan(P.planFromSpot(SPOT, P.PLAN_DEFAULT), DATES);
  assert.equal(fresh.within, 20); assert.equal('act' in fresh, false); assert.equal(fresh.day, DATES[0]);
});

test('it replaces nothing silently: an outing still to come keeps it waiting for Keep', () => {
  const kept = P.planKept(`#day=${DATES[4]}&from=Reading&at=51.45,-0.97&within=20&spot=thames-henley`, DATES);
  assert.equal(P.planHasOuting(kept, DATES), true);
  assert.equal(P.planHasOuting(P.planKept('#from=Kendal&at=54.33,-2.75&within=20', DATES), DATES), false);   // a plan, no outing
  assert.equal(P.planHasOuting(P.planKept(`#day=2026-10-20&spot=thames-henley`, DATES), DATES), false);       // its day has gone
  const app = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  assert.match(app, /PLAN_PREVIEW = planInvited\(PLAN, keptNow, location\.hash\.length > 1, PLAN_PREVIEW\) && !\(PLAN_NEW && !planHasOuting\(keptNow, planDates\(\)\)\);/);
  assert.match(app, /e\.preventDefault\(\); PLAN_NEW = true; openPlan\(planHereHash\(d, a\.dataset\.finish \|\| null\)\); \}\)\);/);
  // The page's actions: the plan first, then sharing; and a line under the five days. A spot with no position has neither.
  assert.match(app, /<a class="btn primary" id="plan-here" href="\$\{esc\(planPath\(\) \+ planHereHash\(d\)\)\}" data-plan-here>Plan an outing here<\/a>/);
  assert.match(app, /Going\? <a href="\$\{esc\(planPath\(\) \+ planHereHash\(d\)\)\}" data-plan-here>Plan an outing here<\/a>: a time, a backup, and a link to share\./);
  assert.match(app, /if \(days && canPlanHere\(d\) && !document\.querySelector\('\.plan-here-line'\)\) days\.closest\('section'\)\.insertAdjacentHTML\('beforeend', planHereLine\(d\)\);/);
  assert.match(app, /planHere\(d\); bindShare\(d\);/);
});

test('waiting for Keep, it is a new outing, not one from a link', () => {
  const col = {id: 'a', name: 'Bolton Abbey', href: '', tone: 'low', headline: 'Low', meta: ''};
  const h = O.outingSection({day: DATES[2], spot: 'a', groups: [], backupGroups: [], missing: [], issued: '', open: true, main: col, nowMs: 0,
    preview: {mine: 'your own outing to Henley on Friday', off: null, fresh: true}});
  assert.match(h, /<summary><span>New outing/);
  assert.match(h, /A new outing\. Not kept in this browser until you keep it\./);
  assert.match(h, /Until then, your own outing to Henley on Friday stays as it is\./);
  assert.doesNotMatch(h, /From a link/);
});
