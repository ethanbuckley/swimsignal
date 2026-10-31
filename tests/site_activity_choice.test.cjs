// What you do on the water (plan.js, readActs and actDefault; index.html, planActRow and paddleFromHere; outing.js,
// outingAccessTopics and outingActLine): optional, chosen on Plan a swim, kept in this browser, never changing a level.
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
  assert.deepEqual(O.outingAccessTopics('paddle', all), ['paddle', 'parking', 'path', 'carry', 'launch', 'exit']);   // the rules first
  assert.deepEqual(O.outingAccessTopics('sup', all), ['paddle', 'parking', 'path', 'carry', 'launch', 'exit']);
  assert.deepEqual(O.outingAccessTopics('swim', all), ['parking', 'path', 'entry', 'exit']);
  assert.deepEqual(O.outingAccessTopics('paddle', old), ['parking', 'path', 'entry', 'exit']);   // before #446
});

test('the choice is made on Plan a swim, not on the saved cards, and the page says the level does not change', () => {
  assert.doesNotMatch(app, /actsChips|bindActs|data-act="/);   // gone from Explore and Saved (31 Oct 2026)
  assert.match(app, /<div class="plan-row">\$\{planStrip\(planDates\(\), PLAN\.day\)\}<\/div>\$\{planActRow\(PLAN\.act\)\}<div class="plan-go">/);
  assert.match(app, /const PLAN_ACTS = \[\['', 'Swim'\], \['paddle', OUTING_ACT_WORDS\.paddle\[0\]\], \['sup', OUTING_ACT_WORDS\.sup\[0\]\]\];/);
  assert.match(app, /The levels are the same: they are for the water, whoever is in it\./);
  assert.match(app, /\$\{ev\}\$\{planActLine\(s\)\}<\/li>`;/);   // each row of the plan
  // A choice kept from the Saved page is still read: the planner starts as it, but never over a link's own.
  assert.match(app, /if \(location\.hash\.length <= 1 && !PLAN\.act && actDefault\(acts\(\)\)\) PLAN\.act = actDefault\(acts\(\)\);/);
  assert.match(app, /let ACTS = typeof readActs === 'function' \? readActs\(stored\('dipcast\.acts'\)\) : \[\];/);
  assert.match(app, /From here by boat or board, finishing at /);
  const privacy = fs.readFileSync(path.join(__dirname, '../src/dipcast/pages/privacy.html'), 'utf8');
  assert.ok(privacy.includes('If you choose what you do on the water on Plan a swim'));
  assert.ok(privacy.includes('A choice made on the Saved page before 31 October 2026 is read the same way.'));
});

test('"Paddle" is said "Kayak/canoe"; the key in links and in this browser stays paddle', () => {
  assert.deepEqual(O.OUTING_ACT_WORDS.paddle, ['Kayak/canoe', 'kayaking or canoeing']);
  assert.deepEqual(O.OUTING_ACT_WORDS.sup, ['Paddleboard', 'paddleboarding']);
  assert.equal(O.outingVerb('paddle'), 'Kayak/canoe');
  assert.deepEqual(P.OUTING_ACTS, ['swim', 'paddle', 'sup']);
  assert.equal(P.readPlan('#act=paddle', DATES).act, 'paddle');
  for (const f of ['index.html', 'outing.js']) {
    const src = fs.readFileSync(path.join(__dirname, '../src/dipcast/site', f), 'utf8');
    assert.doesNotMatch(src, />Paddle<|'Paddle'|Paddle from here/, f);
  }
});

// The plan's row for a boat or a board (outing.js, outingActLine): what is known, and "not known" where nothing is.
const byId = new Map([['wharfe-greenholme', {id: 'wharfe-greenholme', name: 'Greenholme'}], ['wharfe-otley', {id: 'wharfe-otley', name: 'Otley'}]]);
const href = (s, fin) => `/plan/#spot=${s.id}&finish=${fin}`;

test('a swim adds nothing to a plan row', () => {
  const s = {id: 'wharfe-ilkley', downstream: [['wharfe-greenholme', 5.5]], boat_note: {topic: 'launch', text: 'Launch here.', source: 'X', more: 0}};
  assert.equal(O.outingActLine(s, null, byId, href), '');
  assert.equal(O.outingActLine(s, 'swim', byId, href), '');
});

test('a boat or a board gets the guide\'s first fact with its source, and finishes downstream as links', () => {
  const s = {id: 'wharfe-ilkley', downstream: [['wharfe-greenholme', 5.5], ['gone', 9], ['wharfe-otley', 14.2]],
    boat_note: {topic: 'launch', text: 'You can launch from the <south> end.', source: 'National Trust', more: 2}};
  for (const act of ['paddle', 'sup']) {
    const h = O.outingActLine(s, act, byId, href);
    assert.match(h, /<p class="act-line"><b>Launching a boat or board:<\/b> You can launch from the &lt;south&gt; end\. <span class="muted">\(National Trust; 2 more on its page\)<\/span><\/p>/);
    assert.match(h, /<b>Finish downstream:<\/b> <a href="\/plan\/#spot=wharfe-ilkley&amp;finish=wharfe-greenholme" data-plan-start="wharfe-ilkley" data-plan-finish="wharfe-greenholme">Greenholme<\/a> \(5\.5 km\), <a [^>]*>Otley<\/a> \(14 km\)\./);
    assert.doesNotMatch(h, /gone/);   // a spot no longer listed is left out
  }
  const rules = O.outingActLine({id: 'a', boat_note: {topic: 'paddle', text: 'Allowed.', source: null, more: 0}}, 'paddle', byId, href);
  assert.match(rules, /<b>Paddling here:<\/b> Allowed\. <span class="muted">\(its guide\)<\/span>/);
});

test('where SwimSignal knows neither, the row says "not known", never "none"', () => {
  const h = O.outingActLine({id: 'henleaze-lake'}, 'sup', byId, href);
  assert.equal(h, '<p class="act-line"><b>Launching and rules for boats and boards:</b> not known.</p><p class="act-line"><b>Finish downstream:</b> not known.</p>');
  assert.match(O.outingActLine({id: 'a', downstream: [['gone', 3]]}, 'paddle', byId, href), /<b>Finish downstream:<\/b> not known\./);
});
