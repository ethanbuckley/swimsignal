// Every Environment Agency E. coli sample at a bathing water (src/dipcast/site/samples.js, the viewer on samples.html):
// what a bathing water's samples say, and only that. Four bathing waters cut whole from the research export, contract
// 1.0 (tests/fixtures/ecoli_evidence_v1_sample.json, docs/ECOLI-EVIDENCE-CONTRACT-v1.md): Derwent Water at Crow Park
// (a "<10" sample, twelve samples over 900 that the hindsight estimate missed, Archive samples with no enterococci),
// Wharfe at Cromwheel (a ">10000" sample, 2023 samples with no estimate, misses and false alarms), Rutland Water
// Whitwell Creek (32 samples below 10, two on one day) and Hampstead Heath Ladies Pond (no hindsight estimate at all).
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const K = require('../src/dipcast/site/samples.js');
const E = require('../src/dipcast/site/evidence.js');

const DOC = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'ecoli_evidence_v1_sample.json'), 'utf8'));
const site = id => DOC.sites.find(x => x.spot_id === id);
const DERWENT = site('bw-ukd1101-45800'), WHARFE = site('bw-uke4100-08901'), RUTLAND = site('bw-ukf2208-09701'), LADIES = site('bw-uki1101-11910');
// The index's entry for a site, as build_site.write_ecoli_evidence writes it: no samples, the EA's page, this build's rating.
const meta = (s, rating = { class: 'poor', year: 2025 }) => ({ ...Object.fromEntries(Object.entries(s).filter(([k]) => k !== 'samples')),
  profile: `https://environment.data.gov.uk/bwq/profiles/profile.html?site=${s.bw_id}`, ...(rating ? { rating } : {}) });
const INDEX = { ...DOC, available: true, sites: DOC.sites.map(s => meta(s)) };
const plain = h => h.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/&quot;/g, '"');
const page = s => plain(K.samplesSite(s, meta(s), DOC, 320));

test('a count given as a limit is said in words, never as the number', () => {
  assert.equal(K.samplesCount(10, '<'), 'below 10');
  assert.equal(K.samplesCount(10000, '>'), 'above 10,000');
  assert.equal(K.samplesCount(1400, null), '1,400');
  const lt = DERWENT.samples.find(s => s.q === '<');
  assert.equal(lt.ecoli, 10);
  const t = plain(K.samplesTable(DERWENT, DOC));
  assert.match(t, new RegExp(`${K.samplesDate(lt.t).replace(/ \d{4}$/, '')}below 10`));
  // The ">10000" at Cromwheel: in words, and over 900.
  assert.match(plain(K.samplesTable(WHARFE, DOC)), /above 10,000, over 900/);
  // Enterococci too: Rutland's "<10" enterococci are "below 10".
  assert.match(plain(K.samplesTable(RUTLAND, DOC)), /below 10below 10/);
});

test('the chart draws a limit as a hollow dot off the scale, in a band labelled in words', () => {
  const svg = K.samplesChart(RUTLAND.samples, 600);
  assert.equal((svg.match(/class="sm-dot-lim"/g) || []).length, RUTLAND.samples.filter(s => s.q).length);
  assert.match(svg, /class="sm-ax">below 10<\/text>/);
  assert.doesNotMatch(svg, />10<\/text>/);   // never a "10" tick for a below-10 count
  assert.match(svg, /<title>[^<]*: below 10 E\. coli per 100 ml<\/title>/);
  // Every below-10 dot sits off the scale (the shaded band of each season's row), so none is drawn at 10.
  const bands = [...svg.matchAll(/<rect x="\d+" y="([\d.]+)" width="\d+" height="([\d.]+)" class="sm-band"/g)].map(m => [+m[1], +m[1] + +m[2]]);
  const lims = [...svg.matchAll(/cy="([\d.]+)" r="3.5" class="sm-dot-lim"/g)].map(m => +m[1]);
  assert.equal(bands.length, 4);
  assert.ok(lims.length === 32 && lims.every(y => bands.every(([a, b]) => y < a || y > b)));
  const wharfe = K.samplesChart(WHARFE.samples, 600);
  assert.match(wharfe, />above<\/text><text[^>]*>10,000<\/text>/);
  assert.match(plain(wharfe), /A hollow dot is a count the lab gave only as a limit: over it, above 10,000\./);
  assert.match(plain(svg), /The hindsight estimates are in the table only\./);
});

test('the hindsight estimate is labelled as worked out afterwards, wherever it appears', () => {
  const t = page(DERWENT);
  assert.match(t, /Model in hindsight, worked out afterwards/);
  assert.match(t, /The last column was worked out afterwards, not shown on the site at the time\./);
  assert.match(t, /It was not shown on the site at the time and is not the forecast the site issued\./);
  assert.doesNotMatch(t, /\bforecast (was|said|showed)\b/i);
});

test('a high sample with a low estimate is a miss, said as a mismatch, never as a source', () => {
  // Derwent, 3 June 2025: 4,200, with an estimate of 1%.
  const s = DERWENT.samples.find(x => x.t.startsWith('2025-06-03'));
  assert.deepEqual([s.ecoli, s.over, s.hindsight], [4200, true, 0.01]);
  assert.equal(K.samplesMatch(s), 'miss');
  assert.ok(plain(K.samplesTable(DERWENT, DOC)).includes('3 Jun4,200, over 9002,8001% (a miss)'));   // date, E. coli, enterococci, estimate
  // And the reverse: under 900 with an estimate of 25% or more.
  const f = WHARFE.samples.find(x => x.t.startsWith('2024-05-15'));
  assert.equal(K.samplesMatch(f), 'false alarm');
  assert.equal(K.samplesMatch({ over: false, hindsight: 0.2 }), null);
  assert.equal(K.samplesMatch({ over: true, hindsight: 0.25 }), null);   // at the warning line, warned
  assert.equal(K.samplesMatch({ over: true, hindsight: null }), null);
  // The counts are the export's own, with its approved sentence beside them.
  const t = page(DERWENT);
  assert.match(t, /12 samples were over 900 with an estimate under 25% \(a miss\); no sample under it had an estimate of 25% or more \(a false alarm\)\./);
  assert.match(page(WHARFE), /8 samples were over 900 with an estimate under 25% \(a miss\); 11 samples were not over 900 with an estimate of 25% or more \(a false alarm\)\./);
  assert.ok(t.includes(DOC.claim.public_wording));
  assert.match(DOC.claim.public_wording, /not evidence about any particular source/);
  // Nothing names a cause: no overflow, company or source is said to explain a sample.
  for (const x of DOC.sites) {
    const body = page(x).replace(DOC.claim.public_wording, '');
    assert.doesNotMatch(body, /\b(overflow|sewage|company|water company|caused?|because|source of)\b/i, x.name);
    assert.doesNotMatch(body, /\b(safe|unsafe|clean|polluted)\b/i, x.name);
  }
});

test('the official rating and the EA page come first, before any sample or estimate', () => {
  const t = page(WHARFE);
  const rating = t.indexOf('Environment Agency rating: Poor (2025).');
  assert.ok(rating >= 0 && rating < t.indexOf('80 samples') && rating < t.indexOf('hindsight'));
  const html = K.samplesSite(WHARFE, meta(WHARFE), DOC, 320);
  assert.match(html, /<a href="https:\/\/environment\.data\.gov\.uk\/bwq\/profiles\/profile\.html\?site=uke4100-08901">the Environment Agency's page for this bathing water<\/a>/);
  assert.match(html, /<a href="spot\/bw-uke4100-08901\/">This spot's page<\/a>/);
  assert.match(plain(K.samplesOfficial(meta(WHARFE, null))), /^No Environment Agency rating yet: this bathing water is too new to have one\./);
});

test('the date range is said first and plainly, over the file and for each bathing water', () => {
  assert.deepEqual(K.samplesRange(INDEX), { first: '2023-05-03', last: '2026-09-24' });
  const s = plain(K.samplesSummary(INDEX));
  assert.equal(s, '3 May 2023 to 24 Sept 2026: 297 samples at 4 bathing waters. A historical record: nothing after 24 Sept 2026 is in it.');
  assert.match(plain(K.samplesSummary({ available: false, why: 'no export in this build' })), /^No samples are published in this update \(no export in this build\)\.$/);
  assert.match(page(DERWENT), /61 samples, 2 May 2024 to 13 Sept 2026\. 12 were over 900 E\. coli per 100 ml\. 1 was given only as below the lab's limit\./);
});

test('no estimate is said as none, and a bathing water without any says why', () => {
  const t = page(LADIES);
  assert.match(t, /No hindsight estimate here: the study it comes from did not cover this bathing water\./);
  assert.match(t, /"None" in the last column: the hindsight study did not cover that sample\./);
  assert.doesNotMatch(t, /\d+%/);
  assert.match(page(DERWENT), /"Not in this file": the samples added from the Water Quality Archive carry E\. coli only\./);
  assert.equal(K.samplesPct(0.004), 'under 1%');
  assert.equal(K.samplesPct(0.996), 'over 99%');
  assert.equal(K.samplesPct(null), '');
});

test('two samples on one day get their times; exactly 900 is not over', () => {
  const t = plain(K.samplesTable(RUTLAND, DOC));
  const two = RUTLAND.samples.filter(s => s.t.startsWith('2023-08-25'));
  assert.equal(two.length, 2);
  for (const s of two) assert.ok(t.includes(`25 Aug, ${s.t.slice(11, 16)}`));
  assert.doesNotMatch(plain(K.samplesTable({ samples: [{ t: '2025-05-31T15:30+01:00', ecoli: 900, q: null, ie: 210, ie_q: null, over: false, hindsight: 0.075 }] }, DOC)), /900, over 900/);
  // The table's year rows count as the export does.
  assert.match(t, /2023: \d+ samples, 0 over 900/);
});

test('the picker lists rivers, then lakes, and keeps the chosen one', () => {
  const html = K.samplesPicker(INDEX, 'bw-uki1101-11910');
  assert.match(html, /Bathing water<select/);
  assert.ok(html.indexOf('label="Rivers"') < html.indexOf('label="Lakes and ponds"'));
  assert.match(html, /value="bw-uki1101-11910" selected/);
});

test("a bathing water's page links its latest lab sample to every sample, once, in the tile only", () => {
  const NOW = Date.parse('2026-10-30T12:00:00Z');
  const d = { id: 'bw-ukd1101-45800', name: 'Derwent Water at Crow Park', kind: 'lake', source: 'designated',
    classification: { class: 'poor', year: 2025, url: 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukd1101-45800' },
    lab_sample: { taken_at: '2026-09-13T12:27+01:00', ecoli: 630 }, sample_history: { first: '2024-05-02', last: '2026-09-13', samples: 61 }, days: [] };
  const tile = E.evidenceTile(d, NOW, '2026-10-30T11:00:00Z');
  assert.equal((tile.match(/samples\.html/g) || []).length, 1);
  assert.match(tile, /630 E\.&nbsp;coli per 100&nbsp;ml, taken 13 Sept: <a href="#about-ecoli">under 900<\/a>\. <a href="samples\.html#spot=bw-ukd1101-45800">Every sample here since May 2024<\/a>\./);
  // The row itself (the evidence map's copy) and the level are unchanged.
  const row = E.evidenceItems(d, NOW, '2026-10-30T11:00:00Z').rows.find(r => r.what === 'Latest lab sample');
  assert.doesNotMatch(row.say, /samples\.html/);
  // Without the field, or with an id that cannot be an address, no link.
  assert.doesNotMatch(E.evidenceTile({ ...d, sample_history: undefined }, NOW, '2026-10-30T11:00:00Z'), /samples\.html/);
  assert.equal(E.evidenceHistory({ ...d, id: 'a"b' }), '');
  assert.equal(E.evidenceHistory({ ...d, sample_history: { first: 'May' } }), '');
});
