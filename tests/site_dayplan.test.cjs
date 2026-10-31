// The day plan (dayplan.js): a few options with what is known at each and what is not, and the plan in words and as
// a picture. Only data the page already has; the forecast is for the whole day.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const D = require('../src/dipcast/site/dayplan.js');
const app = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const outing = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/outing.js'), 'utf8');
const TODAY = '2026-10-31', NOW = Date.parse('2026-10-31T19:00:00Z');

const lake = (id, extra = {}) => ({id, name: id, kind: 'lake', lat: 54.4, lon: -3, ...extra});
const row = (s, miles = 1) => ({s, miles, level: 'low'});

test('options: the first few low or nothing-upstream spots, never one an official notice restricts', () => {
  const a = lake('a'), b = lake('b'), c = lake('c'), d = lake('d'), e = lake('e');
  const groups = [[row(a), row(b)], [row(c), row(d)], [row(e)], []];
  assert.deepEqual(D.dpOptions(groups).map(o => o.s.id), ['a', 'b', 'c']);
  assert.deepEqual(D.dpOptions(groups, s => s.id === 'a').map(o => o.s.id), ['b', 'c', 'd']);
  assert.deepEqual(D.dpOptions([[], [], [row(e)], []]), []);   // moderate or higher is never an option
});

test('for a boat or a board, a spot whose guide says they are not allowed is left out; for a swim it stays', () => {
  const no = lake('rydal', {boat_note: {topic: 'paddle', text: 'Canoes, kayaks and paddleboards are not allowed on Rydal Water.', source: 'LDNPA', more: 0}});
  const yes = lake('grasmere', {boat_note: {topic: 'paddle', text: 'Canoes, kayaks and paddleboards are allowed on Grasmere.', source: 'LDNPA', more: 0}});
  const groups = [[row(no), row(yes)], []];
  assert.deepEqual(D.dpOptions(groups, undefined, 'paddle').map(o => o.s.id), ['grasmere']);
  assert.deepEqual(D.dpOptions(groups, undefined, 'sup').map(o => o.s.id), ['grasmere']);
  assert.deepEqual(D.dpOptions(groups, undefined, null).map(o => o.s.id), ['rydal', 'grasmere']);
  assert.equal(D.dpNoBoats(yes), false);
  assert.match(D.dpSection('tomorrow', ['<li></li>'], 'kayaking or canoeing', true), /Spots whose guide says boats and boards are not allowed are left out\./);
});

test('conditions say each value\'s kind and date; the water estimate is for today only', () => {
  const s = lake('w', {water_temp_est: {temp_c: 14, date: TODAY, route: 'lake_off_season'},
    weather: {days: [{date: TODAY, sunrise: '07:11', sunset: '16:38'}, {date: '2026-11-01', sunrise: '07:13', sunset: '16:36'}]},
    access: {status: 'unconfirmed', text: 'Long text.', checked_at: '2026-10-03'}, guide: {checked: '2026-10-20', facts: [{topic: 'parking'}, {topic: 'entry'}]}});
  const today = D.dpConditions(s, TODAY, TODAY, null, new Map(), NOW);
  assert.deepEqual(today.rows.map(r => r[0]), ['Water', 'Daylight', 'Access']);
  assert.equal(today.rows[0][1], 'About 14&nbsp;°C today, a provisional estimate');
  assert.equal(today.rows[1][1], 'Sunrise 07:11, sunset 16:38');
  assert.match(today.rows[2][1], /^Permission at this point not confirmed\. <span class="muted">\(checked from published sources, 3 Oct 2026\)<\/span> Its guide covers parking, getting in/);
  assert.deepEqual(today.missing, ['the path', 'getting out']);
  const sun = D.dpConditions(s, '2026-11-01', TODAY, null, new Map(), NOW);
  assert.equal(sun.rows[0][1], 'About 14&nbsp;°C today, a provisional estimate; none for Sun 1 Nov');
  assert.equal(sun.rows[1][1], 'Sunrise 07:13, sunset 16:36');
  // A stale estimate is never shown as today's; a measured reading says where and how long ago.
  assert.ok(D.dpConditions(lake('x', {water_temp_est: {temp_c: 9, date: '2026-10-30'}}), TODAY, TODAY).missing.includes('water temperature'));
  const m = D.dpConditions(lake('y', {water_temp: {temp_c: 11.4, observed_at: '2026-10-31T17:00:00Z', where: 'at Bowness'}}), TODAY, TODAY, null, new Map(), NOW);
  assert.equal(m.rows[0][1], '11&nbsp;°C, measured at Bowness 2 h ago');
});

test('while the spot\'s own file loads, access says so and nothing is called missing yet', () => {
  const c = D.dpConditions(lake('l', {detail_file: 'spot/l.json'}), TODAY, TODAY);
  assert.match(c.rows.find(r => r[0] === 'Access')[1], /Loading its guide/);
  assert.ok(!c.missing.includes('access'));
  assert.ok(D.dpConditions(lake('n', {detail_file: 'spot/n.json', detail_loaded: true}), TODAY, TODAY).missing.includes('access'));
});

test('for a boat or a board on a river: rules, the river now, finishes; wind is not known', () => {
  const byId = new Map([['b', {id: 'b', name: 'Greenholme'}]]);
  const s = {id: 'a', name: 'Ilkley', kind: 'river', downstream: [['b', 5.5], ['gone', 9]], boat_note: {topic: 'launch', text: 'Launch at the steps.', source: 'Council'},
    river_state: {label: 'normal', station: 'Addingham', level_m: 0.49, age_hours: 1, stale: false}};
  const c = D.dpConditions(s, '2026-11-01', TODAY, 'sup', byId, NOW);
  const rows = Object.fromEntries(c.rows);
  assert.equal(rows.Launching, 'Launch at the steps. <span class="muted">(Council)</span>');
  assert.equal(rows['River level'], 'Usual level at Addingham, read 1 h ago; a reading now, not a forecast');
  assert.equal(rows.Finish, 'Greenholme (5.5 km down)');
  assert.ok(c.missing.includes('wind'));
  // Where none of it is known, it is listed, never left out.
  const bare = D.dpConditions({id: 'z', name: 'Z', kind: 'river'}, TODAY, TODAY, 'paddle', byId, NOW);
  for (const w of ['rules for boats and boards', 'river level', 'a finish downstream', 'wind']) assert.ok(bare.missing.includes(w), w);
  // A swim has none of the boat rows.
  assert.deepEqual(D.dpConditions(s, TODAY, TODAY, null, byId, NOW).rows.map(r => r[0]).filter(k => ['Launching', 'River level', 'Finish'].includes(k)), []);
});

test('an option: the notice first, then the level, the facts, what is not known and the way to plan it', () => {
  const o = row(lake('a', {name: 'Windermere'}));
  const h = D.dpOption(o, {href: '/spot/a/', headline: 'Low risk', tone: 'low', official: '<p class="o-tag">Notice</p>', meta: 'Under a mile away · Lake'},
    {rows: [['Water', 'About 14&nbsp;°C today']], missing: ['wind', 'wind']}, 'Grasmere', 0);
  assert.ok(h.indexOf('o-tag') < h.indexOf('class="hl low"'));
  assert.match(h, /<dl class="dp-facts"><div><dt>Water<\/dt><dd>About 14&nbsp;°C today<\/dd><\/div><\/dl>/);
  assert.match(h, /<p class="dp-gap">Not known here: wind\.<\/p>/);   // each once
  assert.match(h, /<button type="button" class="btn primary" data-dp-go="a">Plan the day here<\/button> <span class="small muted">with Grasmere as backup<\/span>/);
  const chosen = D.dpOption(o, {href: '/', headline: 'Low risk', tone: 'low', meta: '', chosen: true}, {rows: [], missing: []}, null, 0);
  assert.doesNotMatch(chosen, /data-dp-go/);
  assert.match(D.dpSection('on Saturday', [], 'swimming'), /No spot within reach is at low risk from sewage spills on Saturday/);
  assert.match(D.dpSection('tomorrow', [h], 'swimming'), /The forecast is for the whole day, not by the hour\./);
});

test('the plan in words, and the picture\'s map fits the spots', () => {
  assert.equal(D.dpTitle('saturday morning', 'Windermere, Waterhead', 'Rydal Water'), 'Saturday morning at Windermere, Waterhead, with Rydal Water as backup');
  assert.equal(D.dpTitle('today', 'Ilkley', null, 'paddleboarding'), 'Today at Ilkley, paddleboarding');
  const near = [{lat: 54.43, lon: -2.96}, {lat: 54.45, lon: -3.02}], far = [{lat: 54.43, lon: -2.96}, {lat: 53.9, lon: -1.8}];
  assert.ok(D.dpZoom(near) > D.dpZoom(far));
  assert.equal(D.dpZoom([{lat: 54.4, lon: -3}]), 13);
  const [x1] = D.dpWorld(54.43, -2.96, 10), [x2] = D.dpWorld(54.45, -3.02, 10);
  assert.ok(x1 > x2);
});

test('the page draws the options above the outing, and the outing offers the picture', () => {
  assert.match(app, /<script src="dayplan\.js"><\/script>/);
  assert.match(app, /if \(r\.count && typeof dpSection === 'function'\) planOptions\(box, r\.groups\);/);
  assert.ok(app.indexOf("drawOuting(box, r.groups.flat())") < app.indexOf('planOptions(box, r.groups);'));   // afterbegin: the options end up first
  assert.match(outing, /id="outing-picture">Make a picture to send<\/button>/);
  assert.match(app, /if \(!blob\) blob = await dpBlob\(await dpPicture\(\{ \.\.\.p, tiles: null \}\)\);/);   // a map provider that does not allow it
  assert.doesNotMatch(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/dayplan.js'), 'utf8'), /open-meteo|fetch\(/i);   // no new requests
});

test('the picture\'s map is shorter with a third spot, so the blocks and the footer fit', () => {
  assert.equal(D.dpMap(2).h, 500);
  assert.equal(D.dpMap(3).h, 340);
  // Last block's line: map bottom + 80 + (n - 1) steps + 128, above the footer's first line at DP_H - 92 (24 px type).
  for (const [n, step] of [[2, 172], [3, 166]]) { const m = D.dpMap(n); assert.ok(m.y + m.h + 80 + (n - 1) * step + 128 < D.DP_H - 92 - 24, String(n)); }
});
