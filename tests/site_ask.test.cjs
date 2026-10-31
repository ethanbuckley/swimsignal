const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ask = require('../src/dipcast/site/ask.js');

// The Worker's reply for "Paddleboarding within 20 miles of Leeds tomorrow morning?" (ask/test/http.test.js), cut down.
const answer = {
  question: 'q', day: '2026-11-01', day_words: 'Sunday 1 November', issued_at: '2026-10-31T18:14:16+00:00',
  summary: 'Two spots on the Wharfe are at low risk of sewage pollution tomorrow.', assumptions: ['Tomorrow read as Sunday 1 November'],
  spots: [{ id: 'osm-wharfe-greenholme', name: 'River Wharfe, Greenholme', kind: 'river', area: 'Yorkshire', miles: 11.7, fit: 'Low risk tomorrow',
    url: 'https://swimsignal.co.uk/spot/osm-wharfe-greenholme/#day=2026-11-01', restricts: false, unknown: ['Wind: not known.'],
    facts: [{ topic: 'official', text: 'Official advice: none in SwimSignal\'s data for this spot.', source: "SwimSignal's data", date: '2026-10-31T18:14:16+00:00', link: null },
      { topic: 'forecast', text: 'Sunday 1 November: Low risk.', source: "SwimSignal's forecast", date: '2026-10-31T18:13:26+00:00', link: null },
      { topic: 'guide', text: 'Parking: <b>on the road</b>', source: 'Bradford Council', date: '2026-10-30', link: 'https://www.bradford.gov.uk/x' },
      { topic: 'rating', text: 'Bathing water rating: poor (2025).', source: 'Environment Agency', date: '2025', link: 'javascript:alert(1)' }] }],
  unknown: ['Wind on Sunday'], notes: ['Other risks apply.'], plan_url: 'https://swimsignal.co.uk/plan/#day=2026-11-01',
};

test('the tile is there only when spots.json names an https Worker', () => {
  assert.equal(ask.askBox({}), '');
  assert.equal(ask.askBox({ ask: { url: 'http://x.example/' } }), '');
  const html = ask.askBox({ ask: { url: 'https://swimsignal-ask.example.workers.dev/' } });
  assert.match(html, /<form id="ask-form"/);
  assert.match(html, /maxlength="300"/);
  assert.match(html, /href="privacy.html#ask"/);
});

test('the answer: the model\'s words first, then each spot\'s lines with source and date, official advice first', () => {
  const html = ask.askAnswerHtml(answer);
  assert.ok(html.indexOf('ask-summary') < html.indexOf('ask-spots'));
  assert.ok(html.indexOf('Official advice') < html.indexOf('Low risk.'));
  assert.match(html, /<a href="https:\/\/swimsignal\.co\.uk\/spot\/osm-wharfe-greenholme\/#day=2026-11-01">River Wharfe, Greenholme<\/a>/);
  assert.match(html, /11\.7 miles · river · Yorkshire/);
  assert.match(html, /<a href="https:\/\/www\.bradford\.gov\.uk\/x">Bradford Council<\/a>, 30 Oct 2026/);
  assert.match(html, /Environment Agency, 2025/);
  assert.ok(!html.includes('javascript:'));
  assert.match(html, /Read as: Tomorrow read as Sunday 1 November\./);
  assert.match(html, /<h3 class="ask-sub">Not known<\/h3>/);
  assert.match(html, /Open in Plan a swim/);
  assert.match(html, /Written by an AI model/);
});

test('everything from the Worker is escaped', () => {
  const html = ask.askAnswerHtml({ ...answer, summary: '<script>x</script>' });
  assert.ok(!html.includes('<script>') && html.includes('&lt;script&gt;'));
  assert.ok(!html.includes('<b>on the road</b>'));
});

test('dates as the reader reads them', () => {
  assert.equal(ask.askWhen('2025'), '2025');
  assert.equal(ask.askWhen('2026-10-26'), '26 Oct 2026');
  assert.equal(ask.askWhen('2026-10-31T18:13:26+00:00'), '31 Oct, 18:13');
  assert.equal(ask.askWhen(null), '');
});

test('index.html draws the tile on Plan a swim only through askBox, and loads ask.js after plan.js', () => {
  const page = fs.readFileSync('src/dipcast/site/index.html', 'utf8');
  assert.match(page, /cols\(\(typeof askBox === 'function' \? askBox\(DATA\) : ''\) \+ '<div id="plan-results"><\/div>'\)/);
  assert.ok(page.indexOf('<script src="plan.js">') < page.indexOf('<script src="ask.js">'));
});
