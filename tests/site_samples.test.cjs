// Every Environment Agency E. coli sample at a bathing water (src/dipcast/site/samples.js, the viewer on samples.html):
// what a bathing water's samples say, and only that. Four bathing waters cut whole from the research export, contract
// 1.1 (tests/fixtures/ecoli_evidence_v1_sample.json, docs/ECOLI-EVIDENCE-CONTRACT-v1.md): Derwent Water at Crow Park
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
  // At a lake the same two counts are for comparison only (1.1, warn_at_note); a river's page does not say so.
  assert.match(DOC.warn_at_note, /no E\. coli warning at lakes/);
  assert.match(page(DERWENT), /25% is the site's warning line for rivers\. At a lake these two counts are for comparison only: the site gives no E\. coli warning at lakes\./);
  assert.doesNotMatch(page(WHARFE), /for comparison only/);
  assert.ok(t.includes(DOC.claim.public_wording));
  assert.match(DOC.claim.public_wording, /not evidence about any particular source/);
  // Nothing names a cause: no overflow, company or source is said to explain a sample. The reasons a sample has no
  // estimate (1.1) explain a missing estimate, not a count, so they are left out of this check.
  const reasons = [...Object.values(DOC.hindsight_reasons), 'none: no overflow upstream'];
  for (const x of DOC.sites) {
    const body = reasons.reduce((t, r) => t.split(r.replace(/^./, c => c.toLowerCase())).join('').split(r).join(''), page(x).replace(DOC.claim.public_wording, ''));
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
  assert.match(page(DERWENT), /61 samples, 2 May 2024 to 13 Sept 2026\. 12 were over 900 E\. coli per 100 ml\. 1 was given only as below 10\./);   // the export's below_limit_value (1.1)
  assert.match(plain(K.samplesCounts({ summary: { ...DERWENT.summary, below_limit_value: undefined } }, DOC)), /1 was given only as below the lab's limit\./);
});

test('no estimate is said as none, and a bathing water without any says why', () => {
  const t = page(LADIES);
  // Each missing estimate says why, in the export's words (1.1, hindsight_reason and hindsight_reasons).
  assert.ok(t.includes(`No hindsight estimate here: ${DOC.hindsight_reasons.no_overflow_upstream.replace(/^./, c => c.toLowerCase())}`), t);
  assert.ok(t.includes(`Why a sample has no estimate:${DOC.hindsight_reasons.before_2024}${DOC.hindsight_reasons.no_overflow_upstream}`), t);
  assert.match(t, /none: no overflow upstream/);
  assert.doesNotMatch(t, /\d+%/);
  const d = page(DERWENT);
  assert.match(d, /none: only in the Water Quality Archive/);
  assert.ok(d.includes(`Why a sample has no estimate:${DOC.hindsight_reasons.archive_only}`));
  assert.doesNotMatch(d, /added later|2023, no archived rain/);   // Derwent's samples start in 2024
  assert.match(d, /"Not in this file": the samples from the Water Quality Archive carry E\. coli only\./);
  // Every sample without an estimate has a reason, and only those (the export's check).
  for (const x of DOC.sites) for (const smp of x.samples) assert.equal(smp.hindsight === null, smp.hindsight_reason !== null);
  // A 1.0 file without reasons says the study did not cover them.
  const old = { ...LADIES, samples: LADIES.samples.map(({ hindsight_reason, ...r }) => r) };
  assert.match(plain(K.samplesSite(old, meta(old), { ...DOC, hindsight_reasons: undefined }, 320)), /the hindsight study did not cover that sample\./);
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

// ------------------------------------------------------------------ the Republic of Ireland and Wales
// The sample histories (docs/SAMPLE-HISTORY-CONTRACT-v1.md) as the build splits them (build_site.write_sample_histories),
// cut from the committed exports: tests/fixtures/sample_history_split_sample.json holds Ireland's index and four waters
// (Merrion Strand: 159 out-of-season samples and ">" limits; Cahore: plain counts under 10 and a 0, not designated;
// Bundoran: "<1" limits; Lough Muckno: a lake, line 900) and Wales's index and both waters.
const HIST = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'sample_history_split_sample.json'), 'utf8'));
const IE = HIST.ireland, WA = HIST.wales;
const hmeta = (set, id) => set.index.sites.find(x => x.id === id);
const hpage = (set, id) => plain(K.samplesHistorySite(set.sites[id], hmeta(set, id), set.index, 320));

test('the address picks the set and the water; England keeps #spot=', () => {
  assert.deepEqual(K.samplesWhere('#spot=bw-ukd1101-45800'), ['england', 'bw-ukd1101-45800']);
  assert.deepEqual(K.samplesWhere('#ireland=BPNBF070000020002'), ['ireland', 'BPNBF070000020002']);
  assert.deepEqual(K.samplesWhere('#wales'), ['wales', '']);
  assert.deepEqual(K.samplesWhere(''), ['england', '']);
  assert.deepEqual(K.samplesWhere('#ireland=a"b'), ['england', '']);
  assert.equal(K.samplesHash('ireland', 'BPNBF070000020002'), 'ireland=BPNBF070000020002');
  assert.equal(K.samplesHash('england', 'bw-x'), 'spot=bw-x');
  assert.equal(K.samplesHash('wales', ''), 'wales');
  assert.match(K.samplesSetPicker('wales'), /<option value="wales" selected>Wales: Hay-on-Wye and Llandeilo<\/option>/);
});

test('the official body and its page come first; no SwimSignal spot page, estimate or forecast beside the samples', () => {
  for (const [set, id, first] of [[IE, 'IENWBWC020_0000_0100', 'EPA rating: Excellent'], [IE, 'BPNBF330000180001', 'Not a designated bathing water'],
    [WA, 'ukl2400-38620', 'Natural Resources Wales rating: Sufficient (2025).'], [WA, 'ukl1401-37650', 'No Natural Resources Wales rating yet']]) {
    const t = hpage(set, id), at = t.indexOf(first);
    assert.ok(at >= 0 && at < t.indexOf(' samples, '), `${id}: ${t.slice(0, 200)}`);
    const body = t.split(set.index.claim.public_wording).join('').replace(/makes no forecast/g, '');
    assert.doesNotMatch(body, /hindsight|estimate|model|\d+%|forecast/i, id);
    assert.doesNotMatch(t, /\b(safe|unsafe|clean|polluted|overflow|sewage|caused?)\b/i, id);
    const html = K.samplesHistorySite(set.sites[id], hmeta(set, id), set.index, 320);
    assert.doesNotMatch(html, /href="spot\//);
    assert.ok(t.includes(set.index.claim.public_wording));
  }
  assert.match(K.samplesHistorySite(IE.sites.IENWBWC020_0000_0100, hmeta(IE, 'IENWBWC020_0000_0100'), IE.index, 320),
    /<a href="https:\/\/www\.beaches\.ie\/find-a-beach\/#\/beach\/IENWBWC020_0000_0100">this water's page on beaches\.ie<\/a>/);
  assert.match(K.samplesHistorySite(WA.sites['ukl2400-38620'], hmeta(WA, 'ukl2400-38620'), WA.index, 320),
    /<a href="https:\/\/environment\.data\.gov\.uk\/wales\/bathing-waters\/profiles\/profile\.html\?site=ukl2400-38620">Natural Resources Wales's page/);
});

test("Irish limits stay limits: '<1' is below 1, '>2419' is above, a plain 1 is 1, and the scale reaches down to 1", () => {
  const bundoran = IE.sites.IENWBWC020_0000_0100, lt1 = bundoran.samples.find(s => s.q === '<' && s.ecoli === 1);
  assert.ok(lt1);
  assert.ok(plain(K.samplesHistoryTable(bundoran, hmeta(IE, 'IENWBWC020_0000_0100'), IE.index)).includes(`${K.samplesDate(lt1.t).replace(/ \d{4}$/, '')}below 1`));
  const merrion = IE.sites.BPNBF070000020002, gt = merrion.samples.find(s => s.q === '>');
  assert.ok(gt && gt.over === (gt.ecoli >= 500));
  assert.match(plain(K.samplesHistoryTable(merrion, hmeta(IE, 'BPNBF070000020002'), IE.index)), new RegExp(`above ${K.samplesCount(gt.ecoli, null)}`));
  const cahore = IE.sites.BPNBF330000180001, svg = K.samplesChart(cahore.samples, 600, 500, false);
  assert.match(svg, /class="sm-ax">10<\/text>/);                    // a 10 tick: the scale starts at 1
  assert.match(plain(svg), /The scale runs from 1 to 10,000 E\. coli per 100 ml/);
  assert.match(plain(svg), /A count of 0 is drawn at the foot of the scale\./);
  // Bundoran's labs gave "<1" and "<10": the band says both.
  assert.match(K.samplesChart(bundoran.samples, 600, 500, false), /class="sm-ax">below 1 or 10<\/text>/);
  assert.doesNotMatch(plain(svg), /hindsight/);
  // England's charts still start at 10.
  assert.match(plain(K.samplesChart(RUTLAND.samples, 600)), /The scale runs from 10 to/);
});

test("the counts say the EPA's own word, out-of-season samples and the water's own line", () => {
  const t = hpage(IE, 'BPNBF070000020002'), s = hmeta(IE, 'BPNBF070000020002').summary;
  assert.ok(t.includes(`402 samples, 4 Jan 2016 to 4 Nov 2026. ${s.over_line} were over 500 E. coli per 100 ml.`), t.slice(0, 400));
  assert.ok(t.includes(`The EPA assessed ${s.poor} as Poor. 159 were taken out of season: voluntary, and not counted towards a rating.`));
  assert.match(t, /500 per 100 ml is the line of the coastal "sufficient" standard/);
  assert.match(t, /Poor, out of season/);
  assert.match(hpage(IE, 'BPNBF240000030001'), /over 900 E\. coli per 100 ml\.[^]*900 per 100 ml is the line of the inland "sufficient" standard/);
  // How the samples were measured, from the export, with what "below" and "above" mean.
  assert.match(t, /How these samples were measured"Below": Below the lab's lower limit/);
  assert.match(t, /The EPA's data does not name a lab method for each sample\./);
});

test('Wales: the two sources joined, why each sample was taken, and the membrane-filtration method said', () => {
  const t = hpage(WA, 'ukl2400-38620');
  assert.match(t, /^The Warren, Hay-on-WyeRiver, bathing water on the Wye/);
  assert.match(t, /37 samples, 18 Aug 2023 to 7 Sept 2026\. 2 were over 900 E\. coli per 100 ml\. 1 was given only as below the lab's lower limit\. 13 were planned investigation samples, not statutory monitoring\./);
  assert.match(t, /Planned investigation/);
  assert.match(t, /Statutory monitoring/);
  assert.match(t, /counted by membrane filtration/);
  assert.match(hpage(WA, 'ukl1401-37650'), /24 samples, 12 Aug 2023 to 18 Sept 2026\./);
});

test("the list says the file's dates first, and Ireland's picker is by county", () => {
  assert.equal(plain(K.samplesHistorySummary(WA.index)), "12 Aug 2023 to 18 Sept 2026: 61 samples at 2 bathing waters. A historical record: nothing after 18 Sept 2026 is in it. Copied from Natural Resources Wales's published data on 13 Nov 2026, its Water Quality Archive part as published on 4 Oct 2026.");
  assert.equal(plain(K.samplesHistorySummary(IE.index)), "27 May 2014 to 4 Nov 2026: 768 samples at 4 waters. A historical record: nothing after 4 Nov 2026 is in it. Copied from the Environmental Protection Agency's published data on 13 Nov 2026.");
  assert.match(plain(K.samplesHistorySummary({ available: false, why: 'no export in this build' })), /\(no export in this build\)\.$/);
  const html = K.samplesHistoryPicker(IE.index, 'BPNBF070000020002');
  assert.match(html, /^<label class="sm-pick">Water<select/);
  assert.ok(html.indexOf('label="County Donegal"') < html.indexOf('label="County Dublin"') && html.indexOf('label="County Dublin"') < html.indexOf('label="County Wexford"'));
  assert.match(html, /value="BPNBF070000020002" selected>Merrion Strand/);
});
