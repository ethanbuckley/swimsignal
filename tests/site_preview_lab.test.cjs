// The redesign's "Explore the evidence" (docs/RESEARCH-ON-THE-SITE-2026-11.md, item 1; docs/DESIGN.md, "The Research
// Lab, and its manner on the rest of the site", Places): the exhibits that hold a place's own record, each opened on it,
// from the keys in its own file; told so where none does; nothing for a place whose file has not been read.
//   node --test tests/site_preview_lab.test.cjs
process.env.TZ = 'Europe/London';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {prerender} = require(path.join(__dirname, '../scripts/prerender_preview.js'));

const GEN = '2026-11-24T13:21:00+00:00', DAYS = ['2026-11-24', '2026-11-25', '2026-11-26', '2026-11-27', '2026-11-28'];
const place = (id, extra = {}) => ({id, name: `Place ${id}`, kind: 'river', river: 'River Aire', area: 'Yorkshire', source: 'curated', lat: 53.9, lon: -1.8,
  detail_file: `spot/${id}.json`, upstream_summary: {overflows: 3}, location: {mode: 'river'}, assumptions: {max_upstream_km: 60, recent_spill_hours: 48},
  now: {label: 'low', risk: 0.02, discharging_upstream: 0, recent_upstream: 0, monitored_upstream: 3},
  days: DAYS.map(d => ({date: d, label: 'low', risk: 0.05, rain_48h_mm: 2, expected_spilling_overflows: 0.1, in_validated_season: false})), ...extra});

function built(spots, files) {
  const site = fs.mkdtempSync(path.join(os.tmpdir(), 'pv-lab-'));
  try {
    fs.mkdirSync(path.join(site, 'data', 'spot'), {recursive: true}); fs.mkdirSync(path.join(site, 'data', 'upstream')); fs.mkdirSync(path.join(site, 'preview'));
    fs.writeFileSync(path.join(site, 'data', 'spots-lite.json'), JSON.stringify({generated_at: GEN, spots}));
    for (const [id, detail] of Object.entries(files)) fs.writeFileSync(path.join(site, 'data', 'spot', `${id}.json`), JSON.stringify(detail));
    return prerender(site, '');
  } finally { fs.rmSync(site, {recursive: true, force: true}); }
}

test('a place lists the exhibits that hold its record, each opened on it', () => {
  const out = built([place('bw-ukd1203-45625', {kind: 'lake', location: {mode: 'lake'}})],
    {'bw-ukd1203-45625': {id: 'bw-ukd1203-45625', contributors: [], lab: {lake: 'bw-ukd1203-45625', bw: 'ukd1203-45625', ws: 'windermere', lt: true}}});
  const page = out.spots['bw-ukd1203-45625'], sec = page.slice(page.indexOf('id="lab-exhibits"'));
  assert.match(page, /<h2 id="labx-h">Explore the evidence<\/h2>/);
  assert.deepEqual([...sec.matchAll(/<small>Exhibit (\d)<\/small>/g)].map(m => m[1]), ['1', '2', '3', '4', '8']);
  assert.match(sec, /href="lab\/lakes\/"/);
  assert.match(sec, /href="lab\/lake-from-space\/#lake=bw-ukd1203-45625"/);
  assert.match(sec, /href="lab\/pollution\/#spot=bw-ukd1203-45625"/);
  assert.match(sec, /href="lab\/forecasts\/#bw=ukd1203-45625"/);
  assert.match(sec, /href="lab\/workspace\/#c=windermere&amp;spot=bw-ukd1203-45625"/);
  assert.match(sec, /The rivers joining its 3 overflows to it/);
  assert.match(sec, /Not a toxin measurement\./);
  assert.match(sec, /It changes nothing in this forecast\. <a href="lab\/">All eight exhibits<\/a> · <a href="research\.html">Research and data<\/a> · <a href="coverage\.html">Beaches, Wales, Scotland and Ireland<\/a>/);
  assert.ok(page.indexOf('id="lab-exhibits"') > page.indexOf('id="place"'), 'after the rest of the place, never above the answer');
  assert.ok(page.indexOf('id="lab-exhibits"') < page.indexOf('<footer'), 'before the foot');
  // Its id is its own: "evidence" is the record's "What the level rests on" (evidence.js), and a link to one must not land on the other.
  assert.doesNotMatch(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/evidence.js'), 'utf8'), /id="lab-exhibits"/);
  assert.equal(page.split('id="lab-exhibits"').length, 2);
});

test('a place no exhibit holds is told so, and one with no overflow upstream has no exhibit 2', () => {
  const out = built([place('quiet', {upstream_summary: {overflows: 0}, days: []})], {quiet: {id: 'quiet'}});
  assert.match(out.spots.quiet, /No Research Lab exhibit holds a record for this spot yet\./);
  assert.doesNotMatch(out.spots.quiet, /<small>Exhibit/);
});

test('every page carries the site\'s one list of foot links, Research and data among them', () => {
  const out = built([place('a')], {a: {id: 'a'}});
  for (const page of [out.home, out.spots.a]) {
    const line = page.match(/<p class="foot-links">(.*?)<\/p>/s)[1];
    assert.deepEqual([...line.matchAll(/<a [^>]*>([^<]*)<\/a>/g)].map(m => m[1]), ['About SwimSignal', 'How accurate is it?', 'Method', 'Every spot', 'Research and data',
      'Coasts, Wales, Scotland, Ireland and algae', 'For organisations', 'Feedback', 'Request a spot', 'Terms of use', 'Privacy', 'Source code']);
  }
});

test('the opening says where the places listed stop, and links the beaches and the other nations', () => {
  const out = built([place('a')], {a: {id: 'a'}});
  assert.match(out.home, /<p class="meta coverage-line">Beaches, and waters in Wales, Scotland and Ireland that are not listed here: <a href="coverage\.html">their official sources and past samples<\/a>\.<\/p>/);
});
