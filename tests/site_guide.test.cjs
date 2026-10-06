// A spot's practical guide (src/dipcast/site/guide.js): who says so under every fact, gaps named,
// labelled photos, nothing unsafe written into the page.
// node --test tests/site_guide.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const g = require('../src/dipcast/site/guide.js');

const guide = (extra = {}) => ({ checked: '2026-10-03', how: 'desk', photos: [], facts: [
  { topic: 'entry', text: 'Steps by the jetty.', status: 'suggested', from: 'Sam', on: '2026-09-12' },
  { topic: 'parking', text: 'Pay and display on Denton Road.', status: 'confirmed', source: 'https://www.example.gov.uk/p', source_name: 'Example Council', lat: 53.93, lon: -1.82 },
], ...extra });
const spot = (extra = {}) => ({ id: 'a', name: 'Wharfe at Cromwheel, Ilkley', guide: guide(), ...extra });

test('verified facts name their page; a suggestion says who, when, and that it is not checked', () => {
  const html = g.guideTile(spot(), '2026-10-04');
  assert.match(html, /Checked 3 Oct 2026 from the published pages linked below, not on site\./);
  assert.match(html, /<span class="g-who">Verified<\/span>: <a href="https:\/\/www.example.gov.uk\/p">Example Council<\/a>\./);
  assert.doesNotMatch(html, /Confirmed|confirmed/, 'one word for checked against an official source, as on the notes on a visit');
  assert.match(html, /<span class="g-who">A swimmer's suggestion<\/span>, from Sam, 12 Sept? 2026\. Not yet checked by SwimSignal\./);
  assert.ok(html.indexOf('Parking') < html.indexOf('Getting in'), 'topics in the order a swimmer meets them');
  assert.match(html, /openstreetmap\.org\/\?mlat=53\.93&amp;mlon=-1\.82/);
  assert.match(html, /Not in this guide yet: path to the water, getting out, toilets, changing, fees and booking, opening times, who can swim\./);
  assert.match(html, /feedback\.html\?type=guide&amp;spot=Wharfe%20at%20Cromwheel%2C%20Ilkley/);
});

test('a site visit, a guide of suggestions only, and an old guide each say so', () => {
  assert.equal(g.guideChecked(guide({ how: 'visit' }), '2026-10-04'), 'Checked on site 3 Oct 2026.');
  const onlySuggested = guide({ facts: [guide().facts[0]] });
  assert.match(g.guideChecked(onlySuggested, '2026-10-04'), /^Swimmers' suggestions only, gathered up to 3 Oct 2026: nothing here has been checked/);
  assert.doesNotMatch(g.guideChecked(guide(), '2027-10-03'), /over a year/);
  assert.match(g.guideChecked(guide(), '2027-10-04'), /over a year ago: fees, opening times and paths may have changed/);
});

test('a spot without a guide asks for one; a point clicked on the map shows nothing', () => {
  const html = g.guideTile(spot({ guide: undefined }), '2026-10-04');
  assert.match(html, /No guide for this spot yet/);
  assert.match(html, /type=guide/);
  assert.equal(g.guideTile(spot({ unlisted: true }), '2026-10-04'), '');
});

test('a spot whose own file did not arrive says nothing about a guide, rather than "no guide yet"', () => {
  // The guide is in data/spot/<id>.json, not spots-lite.json; offline without a stored copy it is unknown.
  assert.equal(g.guideTile(spot({ guide: undefined, detail_missing: true }), '2026-10-04'), '');
});

test('a photo carries numbered labels on it, the same numbers in its key, and its credit', () => {
  const photo = { file: 'steps.jpg', w: 1600, h: 1200, caption: 'The steps from the path.', credit: 'Ethan Buckley', taken: '2026-08-20',
    status: 'confirmed', seen: '2026-08-20', labels: [{ x: 30, y: 72.2, text: 'Steps in' }, { x: 64, y: 40, text: 'Way out' }] };
  const html = g.guideTile(spot({ guide: guide({ photos: [photo] }) }), '2026-10-04');
  assert.match(html, /<div class="g-pic" style="aspect-ratio:1600 \/ 1200"><img src="guides\/photos\/steps\.jpg" width="1600" height="1200"/);
  assert.match(html, /style="left:30%;top:72.2%" aria-hidden="true">1</);
  assert.match(html, /style="left:64%;top:40%" aria-hidden="true">2</);
  assert.match(html, /<ol class="g-key"><li>Steps in<\/li><li>Way out<\/li><\/ol>/);
  assert.match(html, /alt="The steps from the path\. Labelled: 1, Steps in; 2, Way out\."/);
  assert.match(html, /Photo: Ethan Buckley, 20 Aug 2026\./);
  assert.match(html, /seen on site 20 Aug 2026/);
  const theirs = g.guidePhoto({ ...photo, status: 'suggested', from: 'Priya', on: '2026-08-21' }, 0, guide());
  assert.match(theirs, /A swimmer's photo, from Priya; the labels are theirs and not yet checked\./);
});

test('nothing in a guide can write markup, a script link or a path into the page', () => {
  const bad = '<img src=x onerror="alert(1)">';
  const html = g.guideTile(spot({ name: bad, guide: guide({ facts: [
    { topic: 'parking', text: bad, status: 'confirmed', source: 'javascript:alert(1)', source_name: bad, lat: '1;x', lon: 2 },
    { topic: 'entry', text: 'ok', status: 'suggested', from: bad, on: '2026-09-12' }],
  photos: [{ file: '../../etc.jpg', w: 1, h: 1, caption: bad, credit: bad, taken: '2026-08-20', status: 'confirmed', seen: '2026-08-20', labels: [] },
    { file: 'ok.jpg', w: '1" onload="x', h: 3, caption: bad, credit: bad, taken: '2026-08-20', status: 'confirmed', seen: '2026-08-20',
      labels: [{ x: '5%;background:red', y: 1, text: bad }] }] }) }), '2026-10-04');
  assert.ok(!html.includes('<img src=x') && !html.includes('javascript:') && !html.includes('../'));
  assert.ok(!html.includes('onload=') && !html.includes('background:red') && !html.includes('mlat=1;x'));
  assert.ok(html.includes('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;'));
});

// A fact on each of the first n topics, each from its own page.
const topics = n => g.GUIDE_TOPICS.slice(0, n).map(([k], i) => ({ topic: k, text: `Fact ${i + 1}.`, status: 'confirmed',
  source: `https://www.example.gov.uk/${k}`, source_name: 'Example Council' }));
const hiddenRows = html => (html.match(/<div class="g-row" hidden>/g) || []).length;

test('past five topics the first four show and a button opens the rest; at five or fewer all show', () => {
  for (const n of [1, 4, 5]) {
    const html = g.guideTile(spot({ guide: guide({ facts: topics(n) }) }), '2026-10-04');
    assert.equal(hiddenRows(html), 0, `${n} topics: none folded`);
    assert.doesNotMatch(html, /Show all/, `${n} topics: no button, so it never hides a single topic`);
  }
  for (const n of [6, 9]) {
    const photo = { file: 'steps.jpg', w: 4, h: 3, caption: 'Steps.', credit: 'E', taken: '2026-08-20', status: 'confirmed', seen: '2026-08-20', labels: [] };
    const html = g.guideTile(spot({ guide: guide({ facts: topics(n), photos: [photo] }) }), '2026-10-04');
    assert.equal(hiddenRows(html), n - 4, `${n} topics: all but four folded`);
    assert.equal((html.match(/<div class="g-row">/g) || []).length, 4);
    assert.ok(html.indexOf('<dt>Parking</dt>') < html.indexOf(' hidden>'), 'the first topics in order show');
    assert.ok(html.includes(`<button type="button" class="btn quiet" id="g-all" aria-expanded="false">Show all ${n} topics</button>`));
    const btn = html.indexOf('id="g-all"');
    assert.ok(html.indexOf('</dl>') < btn && btn < html.indexOf('class="g-photo"') && btn < html.indexOf('class="g-ask"'), 'the button under the list; the photos keep their place');
    if (n < 9) assert.ok(btn < html.indexOf('class="g-gap"'), '"Not in this guide yet" keeps its place, after the list');
  }
  // The count is of topics with facts, not of facts.
  const many = [...topics(6), { ...topics(1)[0], text: 'Another parking fact.' }];
  assert.match(g.guideTile(spot({ guide: guide({ facts: many }) }), '2026-10-04'), /Show all 6 topics/);
});

test('"Show all" shows the folded topics and goes, as the reviews\' and the notes\' do', () => {
  const rows = [{ hidden: true }, { hidden: true }];
  let removed = false, asked = '';
  const tile = { querySelectorAll: q => { asked = q; return rows; } };
  const button = { closest: q => (q === '#g-all' ? button : q === '#guide' ? tile : null), remove: () => { removed = true; } };
  g.guideClick({ target: button });
  assert.equal(asked, '.g-row[hidden]');
  assert.ok(rows.every(r => r.hidden === false) && removed);
  g.guideClick({ target: { closest: () => null } });   // a click elsewhere on the page does nothing
  g.guideClick({ target: null });
});

test('after "Show all", focus moves to the first row shown, as the button that had it is gone', () => {
  let focused = null;
  const rows = [0, 1].map(i => ({ hidden: true, focus() { focused = i; } }));
  g.showRest(rows, { remove() {} });
  assert.equal(focused, 0);
  assert.equal(rows[0].tabIndex, -1);
  assert.equal(rows[1].tabIndex, undefined);
});

test('facts in a row from the same source share one line, after the last of them', () => {
  const src = { status: 'confirmed', source: 'https://www.cityoflondon.gov.uk/ponds', source_name: 'City of London Corporation' };
  const html = g.guideFacts(guide({ facts: [
    { topic: 'rules', text: 'Women and girls only.', ...src },
    { topic: 'rules', text: 'Ages 8 and over.', ...src },
    { topic: 'rules', text: 'Under 15s with an adult.', ...src }] }));
  assert.equal((html.match(/class="g-src"/g) || []).length, 1);
  assert.match(html, /<dd><p class="g-text">Women and girls only\.<\/p><p class="g-text">Ages 8 and over\.<\/p><p class="g-text">Under 15s with an adult\.<\/p><p class="g-src"><span class="g-who">Verified<\/span>: <a href="https:\/\/www.cityoflondon.gov.uk\/ponds">City of London Corporation<\/a>\.<\/p><\/dd>/);
  assert.equal(g.guideRuns([{ text: 'a', ...src }, { text: 'b', ...src }]).length, 1);
});

test('a different page, day, name or kind of source starts a new line; so does a new topic', () => {
  const src = { status: 'confirmed', source: 'https://www.example.gov.uk/a', source_name: 'Example Council' };
  const lines = facts => (g.guideFacts(guide({ facts })).match(/class="g-src"/g) || []).length;
  const runs = facts => g.guideRuns(facts).map(r => r.texts);
  assert.deepEqual(runs([{ text: 'a', ...src }, { text: 'b', ...src, source: 'https://www.example.gov.uk/b' }]), [['a'], ['b']], 'another page of the same publisher');
  assert.deepEqual(runs([{ text: 'a', ...src }, { text: 'b', ...src, source_name: 'Example Parish' }]), [['a'], ['b']], 'another publisher name');
  assert.deepEqual(runs([{ text: 'a', ...src, seen: '2026-08-20' }, { text: 'b', ...src, seen: '2026-08-21' }]), [['a'], ['b']], 'another day seen');
  assert.deepEqual(runs([{ text: 'a', ...src }, { text: 'b', ...src, seen: '2026-08-20' }]), [['a'], ['b']], 'a page, and a page seen on site');
  const sam = { status: 'suggested', from: 'Sam', on: '2026-09-12' };
  assert.deepEqual(runs([{ text: 'a', ...src }, { text: 'b', ...sam }, { text: 'c', ...sam }, { text: 'd', ...sam, on: '2026-09-13' }]), [['a'], ['b', 'c'], ['d']],
    'a suggestion never joins a verified fact; the same swimmer on the same day shares one line');
  assert.deepEqual(runs([{ text: 'a', ...src }, { text: 'b', ...src, source: 'https://www.example.gov.uk/b' }, { text: 'c', ...src }]), [['a'], ['b'], ['c']],
    'only facts next to each other share: each still ends with its own line');
  assert.equal(lines([{ topic: 'parking', text: 'a', ...src }, { topic: 'fees', text: 'b', ...src }]), 2, 'never across topics');
  const html = g.guideFacts(guide({ facts: [{ topic: 'entry', text: 'a', ...src, lat: 53.93, lon: -1.82 }, { topic: 'entry', text: 'b', ...src, lat: 53.94, lon: -1.82 }] }));
  assert.equal((html.match(/On a map/g) || []).length, 2, 'two places on a map keep a link each');
});
