// The Lake District lakes' rules for boats and boards, from the park authority's lakes activities guide (30 Oct 2026),
// in each lake spot's guide under "Paddling here": where they are not allowed, where a permit is needed, and where two
// official pages differ (Derwentwater's islands), said as such rather than one chosen.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const read = id => fs.readFileSync(path.join(__dirname, '../guides', `${id}.toml`), 'utf8');
const SRC = 'source = "https://lakedistrict.gov.uk/explore/things-to-do/on-the-water/lakes-activities-guide/"';

test('no boats or boards where the authority says so', () => {
  assert.match(read('brothers-water'), /topic = "paddle"\ntext = "Canoes, kayaks and paddleboards are not allowed on Brothers Water\."/);
  assert.match(read('rydal-water'), /not allowed on Rydal Water: individual recreational swimming only\./);
});
test('a permit where one is needed', () => {
  for (const id of ['bassenthwaite', 'buttermere', 'crummock-water', 'loweswater']) assert.match(read(id), /permit/, id);
  assert.match(read('loweswater'), /under 4 m are allowed on Loweswater with a permit/);
});
test('Derwentwater says both pages, and that they differ', () => {
  for (const id of ['bw-ukd1101-45800', 'derwent-water-calfclose']) {
    const g = read(id);
    assert.match(g, /says there is no access to the islands in Derwentwater, where the National Trust's page lets you land on St Herbert's and Rampsholme: the two pages differ\./);
    assert.match(g, /You can land on St Herbert's and Rampsholme islands for a picnic/);
  }
});
test('every fact cites the authority\'s page', () => {
  for (const id of ['brothers-water', 'wastwater', 'grasmere', 'osm-windermere-waterhead', 'bw-ukd1230-45750', 'ullswater-glenridding'])
    assert.ok(read(id).includes(SRC), id);
});
