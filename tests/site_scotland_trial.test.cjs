// The Scotland trial's label (levels.js, trialWords): said wherever the Wales note is, on trial spots only.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const L = require('../src/dipcast/site/levels.js');

test('a Scotland trial spot says it is a trial, long and short; an English spot says nothing', () => {
  const s = { trial: 'scotland', upstream_summary: {} };
  assert.match(L.trialWords(s), /^Scotland trial: .*2022 to 2025.*Not yet confirmed on live data\.$/);
  assert.equal(L.trialWords(s, true), 'Scotland: trial forecast');
  assert.equal(L.trialWords({ source: 'designated' }), '');
  assert.equal(L.trialWords(null), '');
});
