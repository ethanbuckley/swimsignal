const {test} = require('node:test');
const assert = require('node:assert/strict');
const O = require('../src/dipcast/site/outing.js');

test('past-time warning uses the swim spot time, including summer time', () => {
  assert.doesNotMatch(O.outingTimeNote('2026-07-01', '07', Date.parse('2026-07-01T06:59:00Z')).join(' '), /passed/);
  assert.match(O.outingTimeNote('2026-07-01', '07', Date.parse('2026-07-01T07:00:00Z')).join(' '), /passed/);
});
