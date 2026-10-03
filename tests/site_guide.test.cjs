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

test('confirmed facts name their page; a suggestion says who, when, and that it is not checked', () => {
  const html = g.guideTile(spot(), '2026-10-04');
  assert.match(html, /Checked 3 Oct 2026 from the published pages linked below, not on site\./);
  assert.match(html, /<span class="g-who">Confirmed<\/span>: <a href="https:\/\/www.example.gov.uk\/p">Example Council<\/a>\./);
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
