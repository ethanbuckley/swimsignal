// A postcode typed in the search or on Plan a swim is a place, as a town is: its district or sector, from the
// site's own file (plan.js, postcodeIndex, postcodePlace; index.html, offerOnMap, planType). Until 17 Nov 2026
// the page said postcodes did not work.
//   node --test tests/site_postcode_said.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { join } = require('node:path');
const P = require('../src/dipcast/site/plan.js');

const PAGE = fs.readFileSync(join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const index = P.postcodeIndex({ districts: { LS29: [53.92, -1.8], LS2: [53.8, -1.55], SW1A: [51.5, -0.13], L1: [53.4, -2.98], E1W: [51.51, -0.06], ZZ1: [0, 0] },
  sectors: { 'LS29 9': [53.92, -1.83], 'LS2 9': [53.81, -1.55], 'SW1A 1': [51.5, -0.14] } });
const at = t => { const p = P.postcodePlace(index, t); return p && [p.name, p.lat, p.lon]; };

test('a district, a sector and a whole postcode each find a place, however they are spaced or cased', () => {
  assert.deepEqual(at('LS29'), ['LS29', 53.92, -1.8]);
  assert.deepEqual(at(' ls29 '), ['LS29', 53.92, -1.8]);
  assert.deepEqual(at('LS29 9'), ['LS29 9', 53.92, -1.83]);
  assert.deepEqual(at('LS29 9BZ'), ['LS29 9', 53.92, -1.83]);
  assert.deepEqual(at('ls299bz'), ['LS29 9', 53.92, -1.83]);
  assert.deepEqual(at('LS2 9JT'), ['LS2 9', 53.81, -1.55]);       // the space decides between LS2 9 and LS29
  assert.deepEqual(at('SW1A'), ['SW1A', 51.5, -0.13]);            // a district that ends in a letter
  assert.deepEqual(at('SW1A 1AA'), ['SW1A 1', 51.5, -0.14]);
  assert.deepEqual(at('sw1a1aa'), ['SW1A 1', 51.5, -0.14]);
  assert.deepEqual(at('L1'), ['L1', 53.4, -2.98]);                // two characters
});

test('a sector not in the file falls back to its district, and the name is never the whole postcode', () => {
  assert.deepEqual(at('LS29 0AA'), ['LS29', 53.92, -1.8]);
  assert.deepEqual(at('E1W 3SS'), ['E1W', 51.51, -0.06]);
  for (const t of ['LS29 9BZ', 'ls299bz', 'SW1A 1AA']) assert.ok(!/[0-9][A-Z]{2}$/.test(P.postcodePlace(index, t).name), t);
  assert.equal(P.postcodePlace(index, 'LS29 9BZ').postcode, true);
});

test('what is not a postcode in the file finds nothing', () => {
  assert.equal(at('BT1 5GS'), null);                              // Northern Ireland is not in OS Open Names
  assert.equal(at('XX99'), null);
  assert.equal(at('ZZ1'), null);                                  // a position outside Great Britain
  assert.equal(at('Ilkley'), null);
  assert.equal(at(''), null);
  assert.equal(P.postcodePlace(null, 'LS29'), null);              // the file did not come
});

test('the page looks a postcode up and no longer says postcodes do not work', () => {
  assert.ok(!PAGE.includes('Postcodes do not work here yet'));
  assert.ok(PAGE.includes("fetch('data/postcodes.json')"));
  assert.match(PAGE, /for \(const town of postcode \? places : townsNamed\(places, t\)\)/);   // the spots near it, as near a town
  assert.match(PAGE, /No postcode found for “\$\{t\}”: type a town, a village or a river\./);
  assert.match(PAGE, /PLAN\.from = \{ name: pc\.name, lat: pc\.lat, lon: pc\.lon \}/);         // a plan starts from the sector or district
});
