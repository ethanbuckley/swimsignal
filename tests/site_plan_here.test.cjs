// "Plan a swim here" on a spot's page (index.html, actions and planHere; plan.js, planFromSpot): the planner as it
// is, on this spot, starting from it. Kept at once unless it would replace an outing still to come, which then waits
// for "Keep this outing" as an outing from a link does, said as a new outing, not one from a link.
const {test} = require('node:test');
const vm = require('node:vm');
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
  assert.match(app, /e\.preventDefault\(\); PLAN_NEW = true; openPlan\(planHereHash\(d, a\.dataset\.finish \|\| null\)\); \}\); \}\);/);
  assert.match(app, /else if \(a\.hasAttribute\('data-plan-here'\) && typeof planHereHash === 'function'\) \{ e\.preventDefault\(\); PLAN_NEW = true; openPlan\(planHereHash\(d\)\); \}/);   // the card's (bindAct)
  // The page's actions: the plan first, then sharing; and a button under the five days. A spot with no position has neither.
  assert.match(app, /<a class="btn primary" id="plan-here" href="\$\{esc\(planPath\(\) \+ planHereHash\(d\)\)\}" data-plan-here>\$\{planHereWords\(\)\}<\/a>/);
  assert.match(app, /<p class="plan-here-line"><a class="btn primary" href="\$\{esc\(planPath\(\) \+ planHereHash\(d\)\)\}" data-plan-here>\$\{planHereWords\(\)\}<\/a><\/p>/);
  assert.match(app, /if \(days && canPlanHere\(d\) && !document\.querySelector\('\.plan-here-line'\)\) days\.closest\('section'\)\.insertAdjacentHTML\('beforeend', planHereLine\(d\)\);/);
  assert.match(app, /planHere\(d\); bindAct\(d\); bindShare\(d\);/);
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

// The button's words and its link, from the page's own planBase, planHereHash and planHereWords, with this browser's
// storage stubbed. 17 Nov 2026, outside design audit: "Plan a swim here" carried act=paddle and opened Kayak/canoe for
// someone who had chosen it before. The words now follow what the link opens; the day and the place carry as before.
const APP = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8').split('\n');
const def = n => { const i = APP.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`let ${n} =`));
  assert.ok(i >= 0, `no ${n} in index.html`);
  let j = i + 1; while (j < APP.length && /^\s/.test(APP[j])) j++;
  return APP.slice(i, j).join('\n'); };
const planHere = (store, day = DATES[3]) => {
  const ctx = vm.createContext({URLSearchParams, URL});
  for (const f of ['levels.js', 'plan.js', 'outing.js']) vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site', f), 'utf8'), ctx);
  vm.runInContext(`setToday('${DATES[0]}'); const store = ${JSON.stringify(store)}; const stored = k => store[k] ?? null;
    const planDates = () => ${JSON.stringify(DATES)}; const PLAN = null; let DAY = '${day}';\n`
    + ['PLAN_KEY', 'PLAN_READ', 'ACTS', 'acts', 'planBase', 'planHereHash', 'planHereWords'].map(def).join('\n'), ctx);
  return {words: vm.runInContext('planHereWords()', ctx), plan: P.readPlan(vm.runInContext(`planHereHash(${JSON.stringify(SPOT)})`, ctx), DATES)};
};

test('a first visit: "Plan a swim here" opens a swim, on the day shown, from the spot', () => {
  const {words, plan} = planHere({});
  assert.equal(words, 'Plan a swim here');
  assert.equal('act' in plan, false);                                       // the planner's Swim
  assert.equal(plan.day, DATES[3]);
  assert.equal(plan.spot, SPOT.id);
  assert.deepEqual(plan.from, {name: SPOT.name, lat: 53.984, lon: -1.888});
});

test('a remembered activity: the words say what the link opens, and the day and the place still carry', () => {
  const paddle = planHere({'dipcast.acts': '["paddle"]'});
  assert.equal(paddle.words, 'Plan kayaking or canoeing here');
  assert.equal(paddle.plan.act, 'paddle');
  assert.equal(paddle.plan.day, DATES[3]);
  assert.equal(paddle.plan.spot, SPOT.id);
  const sup = planHere({'dipcast.acts': '["sup"]'});
  assert.equal(sup.words, 'Plan paddleboarding here');
  assert.equal(sup.plan.act, 'sup');
  // An activity kept with the last plan (act=, no choice in dipcast.acts) is carried too, and said.
  const kept = planHere({'dipcast.plan': `#day=${DATES[1]}&within=10&act=paddle`});
  assert.equal(kept.words, 'Plan kayaking or canoeing here');
  assert.equal(kept.plan.act, 'paddle');
  assert.equal(kept.plan.within, 10);
  // Swim chosen: unchanged.
  const swim = planHere({'dipcast.acts': '["swim"]'});
  assert.equal(swim.words, 'Plan a swim here');
  assert.equal('act' in swim.plan, false);
});
