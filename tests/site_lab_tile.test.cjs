// "Explore the evidence" on a spot's page (index.html labTile, docs/DESIGN.md "The Research Lab"): only the exhibits
// that hold the spot's own record, each opened on it, and an honest line where none does.
// node --test tests/site_lab_tile.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { join } = require('node:path');

const html = fs.readFileSync(join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const from = html.indexOf('\nconst LAB_COVER = '), to = html.indexOf('\nconst daysTile = ');
const labTile = new Function('PAGE_ID', 'ICON', 'overflows', html.slice(from, to) + '\nreturn labTile;')(
  /^[A-Za-z0-9_-]+$/, { evidence: '' }, d => d.n || 0);
const hrefs = h => [...h.matchAll(/<a href="([^"]+)"/g)].map(m => m[1]);

test('a Windermere bathing water opens all four exhibits on itself', () => {
  const h = labTile({ id: 'bw-ukd1203-45675', n: 3, lab: { lake: 'bw-ukd1203-45675', bw: 'ukd1203-45675', ws: 'windermere' } });
  assert.deepEqual(hrefs(h), ['lab/lake-from-space/#lake=bw-ukd1203-45675', 'lab/pollution/#spot=bw-ukd1203-45675',
    'lab/forecasts/#bw=ukd1203-45675', 'lab/workspace/#c=windermere&spot=bw-ukd1203-45675', 'lab/']);
  assert.match(h, /The rivers joining its 3 overflows to it/);
  assert.match(h, /It changes nothing in this forecast/);
});

test('only what an exhibit holds: no lake, bathing water or catchment is offered that the spot lacks', () => {
  const h = labTile({ id: 'thames-henley', n: 12 });
  assert.deepEqual(hrefs(h), ['lab/pollution/#spot=thames-henley', 'lab/']);
});

test('a spot no exhibit holds is told so, with the way to the rest', () => {
  const h = labTile({ id: 'osm-somewhere', n: 0 });
  assert.match(h, /No Research Lab exhibit holds a record for this spot yet\./);
  assert.deepEqual(hrefs(h), ['lab/']);
  assert.equal(labTile({ id: 'point 54.1,-2.9', n: 2 }), '');   // a clicked point: no tile at all
});
