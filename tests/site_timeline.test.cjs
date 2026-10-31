// The evidence timeline (src/dipcast/site/timeline.js): one dated list, newest first, each line a measurement, a report
// or a forecast with its source and who checked it. A swimmer's note is never a verified warning; a satellite index is
// not a toxin measurement or a clearance, and a missing image is not a clear result; a below-limit count is never 0.
// node --test tests/site_timeline.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const { join } = require('path');
const t = require('../src/dipcast/site/timeline.js');

const ROOT = join(__dirname, '..');
const NOW = Date.parse('2026-10-31T12:00:00Z');
const GEN = '2026-10-31T11:40:00+00:00';
const text = html => html.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();
const spot = (extra = {}) => ({ id: 'bw-ukd1101-45800', name: 'Derwent Water at Crow Park', kind: 'lake', days: [{ date: '2026-10-31' }], ...extra });
const kinds = items => items.map(x => `${x.kind} ${x.day}`);

test('one list, newest first, every line labelled and dated, from every source the page has', () => {
  const d = spot({
    official: [{ line: 'Advice against bathing: harmful algae.', publisher: 'Environment Agency', link: 'https://environment.data.gov.uk/bwq/x',
      since: '2026-08-17', checked: '2026-10-30', state: 'checked', restricts: true }],
    algae: { date: '2026-09-13', phrase: 'no algae seen' },
    measured: [{ sampled_at: '2026-10-20T08:30+01:00', ecoli: 1200, enterococci: 10, enterococci_qualifier: '<', supplier: 'Example Club', lab: 'Lab & Co' }],
    sample_history: { first: '2024-05-02' },
  });
  const files = {
    ecoli: { samples: [{ t: '2026-09-13T11:01+01:00', ecoli: 10, q: '<', ie: 20, ie_q: null }, { t: '2024-05-15T16:00+01:00', ecoli: 520, q: null, ie: 510 }] },
    lake: { water_body: 'Derwent Water', series: [{ date: '2026-09-30', datetime: '2026-09-30T11:36Z', ndci: 0.12824, primary: true, season: 'in_season' },
      { date: '2026-09-30', ndci: 0.2, primary: false }, { date: '2026-10-05', ndci: 0.05, primary: true, season: 'out_of_season', experimental: true }] },
    reviews: { visits: [{ id: 'a', spot: d.id, seen_on: '2026-10-30', kinds: ['busy'], until: '2026-10-31' }, { id: 'b', spot: 'elsewhere', seen_on: '2026-10-30', kinds: ['busy'], until: '2026-10-31' }] },
  };
  const items = t.timelineItems(d, files, NOW, GEN);
  assert.deepEqual(kinds(items), ['forecast 2026-10-31', 'report 2026-10-30', 'measurement 2026-10-20', 'measurement 2026-10-05', 'measurement 2026-09-30',
    'measurement 2026-09-13', 'report 2026-09-13', 'report 2026-08-17', 'measurement 2024-05-15']);
  for (const x of items) assert.ok(x.what && x.says && x.source && x.status, JSON.stringify(x));
  const html = t.timelineBody(d, files, NOW, GEN);
  assert.match(text(html), /^Forecast · 31 Oct 2026 Today SwimSignal's five-day forecast\. .*Not a measurement of the water\./);
  assert.match(text(html), /Measurement · 13 Sept 2026 .* Lab sample\. E\. coli below 10 and intestinal enterococci 20, per 100 ml\./);
  assert.match(text(html), /Report · 17 Aug 2026 .* Official advice\. Advice against bathing: harmful algae\./);
  assert.match(html, /Lab &amp; Co/, 'escaped');
  assert.match(html, /<a href="samples\.html#spot=bw-ukd1101-45800">Environment Agency<\/a>/);
  // Words, not a badge: the kind is plain text at the start of the row, in no pill or colour.
  assert.doesNotMatch(html, /class="[^"]*(pill|badge|tag|chip)/);
});

test("a swimmer's note is a report, and suspected pollution stays suspected even when matched to a source", () => {
  const d = spot();
  const reviews = { visits: [{ spot: d.id, seen_on: '2026-10-30', kinds: ['pollution', 'busy'], until: '2026-11-02', text: 'Brown <foam>', photos: [],
    verified: 'Environment Agency incident, 30 Oct' }, { spot: d.id, seen_on: '2026-10-29', kinds: ['algae'], until: '2026-11-05' }] };
  const [matched, plain] = t.timelineVisits(d, reviews, NOW);
  assert.equal(matched.kind, 'report');
  assert.equal(text(matched.says), 'Suspected pollution; Very busy. “Brown &lt;foam&gt;” What one swimmer saw, not a water test. SwimSignal matched it to Environment Agency incident, 30 Oct: follow that source\'s own notice.');
  assert.match(matched.says, /&lt;foam&gt;/);
  assert.match(matched.status, /Read by SwimSignal before it was published; not checked at the water/);
  assert.match(plain.says, /^Suspected algae\. What one swimmer saw, not a water test\.$/);
  assert.match(plain.status, /published as sent; not checked/);
  for (const x of [matched, plain]) assert.doesNotMatch(text(x.says), /^(Pollution|Algae)\b|[Vv]erified/);
  // A note whose ticks have all ended is not listed.
  assert.deepEqual(t.timelineVisits(d, { visits: [{ spot: d.id, seen_on: '2026-10-20', kinds: ['busy'], until: '2026-10-21' }] }, NOW), []);
});

test('a satellite reading is a dated index, never a toxin measurement or a clearance, and missing imagery is said', () => {
  const lake = { water_body: 'Windermere', series: [{ date: '2026-07-01', ndci: -0.031, primary: true, season: 'in_season' }] };
  const [r] = t.timelineSatellite(lake);
  assert.equal(r.kind, 'measurement');
  assert.equal(r.says, '-0.03, from a Sentinel-2 image of the water round a point on Windermere.');
  assert.equal(r.status, 'A research index of green pigment seen from space: not a toxin measurement, and not a sign the water is safe');
  const all = JSON.stringify(t.timelineSatellite(lake));
  for (const word of ['safe to swim', 'clear water', 'no algae', 'toxin-free', 'chlorophyll', 'µg']) assert.ok(!all.includes(word), word);
  const html = text(t.timelineBody(spot(), { lake }, NOW, GEN));
  assert.match(html, /A missing image is not a clear result: it says nothing about algae\./);
  // Without a satellite file the line is not there.
  assert.doesNotMatch(text(t.timelineBody(spot(), {}, NOW, GEN)), /missing image/);
});

test("a partner's samples carry who took them, and a recorded 0 says what is not known about it", () => {
  const link = { href: 'waterhead.html', by: 'Ambleside Action for a Future', data: 'data/research/waterhead_wet.json' };
  const doc = JSON.parse(fs.readFileSync(join(ROOT, 'data/research/waterhead_wet.v1.json'), 'utf8'));
  const rows = t.timelinePartner(link, doc);
  assert.equal(rows.length, 59, 'every published sample');
  const top = t.timelineItems({ id: 'osm-windermere-waterhead', kind: 'lake', days: [{}] }, { partnerLink: link, partner: doc }, NOW, GEN)[1];
  assert.equal(top.day, '2026-10-12');
  const zero = rows.find(x => x.day === '2025-05-08');
  assert.equal(text(zero.says), "E. coli 0 and intestinal enterococci 1, per 100 ml. A recorded 0 may mean below the lab's detection limit, not none.");
  assert.equal(zero.source, '<a href="waterhead.html">Ambleside Action for a Future</a>');
  assert.match(zero.status, /SwimSignal did not take or check the sample/);
  // Every count is the published one.
  for (const s of doc.samples) assert.ok(text(rows.find(x => x.day === s.date).says).startsWith(`E. coli ${s.ecoli} and intestinal enterococci ${s.ie},`));
});

test('below-limit counts are words, never 0; and a sample without a count is left out', () => {
  assert.equal(t.timelineCount(10, '<'), 'below 10');
  assert.equal(t.timelineCount(2419.6, '>'), 'above 2,419.6');
  assert.equal(text(t.timelineCounts(null, null, 10, '<')), 'Intestinal enterococci below 10, per 100 ml.');
  assert.deepEqual(t.timelineAgency(spot({ lab_sample: { taken_at: '2026-09-01T10:00+01:00', ecoli: null } }), null), []);
  const [s] = t.timelineAgency(spot({ lab_sample: { taken_at: '2026-09-01T10:00+01:00', ecoli: 10, qualifier: '<' } }), null);
  assert.equal(text(s.says), 'E. coli below 10, per 100 ml.');
});

test('long lists fold after twelve; an empty one says so; a clicked point has no tile', () => {
  const series = Array.from({ length: 20 }, (_, i) => ({ date: `2026-06-${String(i + 1).padStart(2, '0')}`, ndci: 0.01, primary: true }));
  const html = t.timelineBody(spot({ days: [] }), { lake: { series } }, NOW, GEN);
  assert.equal((html.match(/class="factor"/g) || []).length, 20);
  assert.match(html, /<div class="m-more" hidden>/);
  assert.match(html, /Show all 20/);
  assert.match(t.timelineBody(spot({ days: [] }), {}, NOW, GEN), /Nothing dated is held for this spot yet/);
  assert.equal(t.timelineTile({ id: 'x', unlisted: true }), '');
  assert.match(t.timelineTile(spot()), /^<details class="tile fold" id="timeline" data-spot="bw-ukd1101-45800">/);
});

test('the page loads the script, puts the fold after what the level rests on, and shares no names', () => {
  const site = join(ROOT, 'src/dipcast/site');
  const html = fs.readFileSync(join(site, 'index.html'), 'utf8');
  assert.ok(html.indexOf('src="evidence.js"') < html.indexOf('src="timeline.js"') && html.indexOf('src="timeline.js"') < html.indexOf('<script>\n'));
  const at = html.indexOf("typeof timelineTile === 'function' ? timelineTile(d) : ''");
  assert.ok(at > html.indexOf("typeof evidenceTile === 'function' ? evidenceTile(d, Date.now(), DATA.generated_at) : ''") && at > 0);
  const names = src => new Set([...src.matchAll(/^(?:const|let|var|function|async function|class)\s+([A-Za-z_$][\w$]*)/gm)].map(x => x[1]));
  const mine = names(fs.readFileSync(join(site, 'timeline.js'), 'utf8'));
  const others = [html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')),
    ...fs.readdirSync(site).filter(f => f.endsWith('.js') && !['timeline.js', 'sw.js'].includes(f)).map(f => fs.readFileSync(join(site, f), 'utf8'))];
  assert.deepEqual(others.flatMap(src => [...names(src)].filter(n => mine.has(n))), []);
  assert.ok([...mine].every(n => /^(timeline|TIMELINE)/.test(n)), [...mine].join(', '));
  assert.match(fs.readFileSync(join(site, 'sw.js'), 'utf8'), /`timeline\.js\?v=\$\{BUILD\}`/);
});
