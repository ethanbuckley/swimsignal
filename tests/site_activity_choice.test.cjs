// What you do on the water (plan.js, readActs and actDefault; index.html, actsChips and paddleFromHere; outing.js,
// outingAccessTopics): optional, kept in this browser, changing what is offered first and never a level.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const P = require('../src/dipcast/site/plan.js');
const O = require('../src/dipcast/site/outing.js');
L.setToday('2026-10-26');
const DATES = ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30'];
const app = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');

test('the choice is read safely and gives a new outing its activity', () => {
  assert.deepEqual(P.readActs('["sup","swim","kite","sup"]'), ['swim', 'sup']);   // known ones, each once, in order
  assert.deepEqual(P.readActs('not json'), []);
  assert.equal(P.actDefault(['swim']), null);
  assert.equal(P.actDefault(['swim', 'sup']), 'sup');
  assert.equal(P.actDefault(['sup', 'paddle']), 'paddle');
  assert.equal(P.ACTS_KEY, 'dipcast.acts');
});

test('a paddler planning from a spot can start with a finish downstream; a swim cannot', () => {
  const s = {id: 'a', name: 'A', lat: 54, lon: -1.9};
  const p = P.readPlan(P.planFromSpot(s, {...P.PLAN_DEFAULT, act: 'paddle'}, DATES[2], 'b'), DATES);
  assert.equal(p.act, 'paddle'); assert.equal(p.finish, 'b'); assert.equal(p.spot, 'a');
  assert.equal('finish' in P.readPlan(P.planFromSpot(s, P.PLAN_DEFAULT, DATES[2], 'b'), DATES), false);
});

test('a paddle outing shows carrying and launching where the guides know them, else the swimmer\'s four', () => {
  const all = new Set(['parking', 'path', 'entry', 'exit', 'launch', 'carry', 'paddle']), old = new Set(['parking', 'path', 'entry', 'exit']);
  assert.deepEqual(O.outingAccessTopics('paddle', all), ['parking', 'path', 'carry', 'launch', 'exit']);
  assert.deepEqual(O.outingAccessTopics('sup', all), ['parking', 'path', 'carry', 'launch', 'exit']);
  assert.deepEqual(O.outingAccessTopics('swim', all), ['parking', 'path', 'entry', 'exit']);
  assert.deepEqual(O.outingAccessTopics('paddle', old), ['parking', 'path', 'entry', 'exit']);   // before #446
});

test('the page says what the choice changes, and that the level and official advice do not', () => {
  assert.match(app, /aria-label="What you do on the water"/);
  assert.match(app, /The level is for the water, the same for everyone in it, and official advice always shows\./);
  assert.match(app, /if \(!actDefault\(acts\(\)\) \|\| !Array\.isArray\(d\.downstream\) \|\| !d\.downstream\.length\) return '';/);
  assert.match(app, /Paddle from here, finishing at /);
  const privacy = fs.readFileSync(path.join(__dirname, '../src/dipcast/pages/privacy.html'), 'utf8');
  assert.ok(privacy.includes('If you choose what you do on the water on the Saved page'));
});
