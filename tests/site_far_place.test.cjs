// A place the search offers with no listed spot within 25 miles says so, with the nearest (17 Nov 2026).
// node --test tests/site_far_place.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const P = require('../src/dipcast/site/plan.js');

const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const km = (a, b) => { const r = Math.PI / 180, dLat = (b[0] - a[0]) * r, dLon = (b[1] - a[1]) * r;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLon / 2) ** 2; return 12742 * Math.asin(Math.sqrt(h)); };
const miles = (a, b) => km(a, b) / P.MILE_KM;
const SPOTS = [{ name: 'River Wye at Symonds Yat', lat: 51.84, lon: -2.64 }, { name: 'Wharfe at Ilkley', lat: 53.93, lon: -1.82 }, { name: 'No position' }];

test('a place far from every listed spot gets the nearest and its distance; a near one gets nothing', () => {
  const cardiff = P.farFromSpots({ name: 'Cardiff', lat: 51.48, lon: -3.18 }, SPOTS, miles);
  assert.equal(cardiff.name, 'River Wye at Symonds Yat');
  assert.ok(cardiff.miles > 25 && cardiff.miles < 40, String(cardiff.miles));
  assert.match(P.farSaid(cardiff), /^No listed spot within 25 miles\. The nearest is River Wye at Symonds Yat, \d+ miles away\.$/);
  assert.equal(P.farFromSpots({ name: 'Ilkley', lat: 53.925, lon: -1.822 }, SPOTS, miles), null);
  assert.equal(P.farFromSpots({ name: 'Monmouth', lat: 51.81, lon: -2.71 }, SPOTS, miles), null);
  assert.equal(P.farFromSpots({ name: 'Anywhere', lat: 51, lon: -3 }, [], miles), null);   // no spots loaded: nothing to say
});

test('the plan row a far place is offered says it, escaped, in place of what the plan would hold', () => {
  assert.match(html, /const reachMiles = base\.within \|\| FAR_MILES, far = p => farFromSpots\(p, DATA\.spots, \(a, b\) => km\(a, b\) \/ MILE_KM, reachMiles\);/);
  assert.match(html, /<span class="k">\$\{far\(p\) \? esc\(farSaid\(far\(p\), reachMiles\)\) : reach\}<\/span>/);
  // The plan's own reach: 24 miles is near at 25 and far at 20, and the words give the reach used.
  const at24 = { name: 'P', lat: 51.84 - 24 / 69.0, lon: -2.64 };
  assert.equal(P.farFromSpots(at24, SPOTS, miles), null);
  assert.match(P.farSaid(P.farFromSpots(at24, SPOTS, miles, 20), 20), /^No listed spot within 20 miles\. The nearest is River Wye at Symonds Yat, 24 miles away\.$/);
});
