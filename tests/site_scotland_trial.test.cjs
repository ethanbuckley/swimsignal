// The Scotland trial's label (levels.js, trialWords): said wherever the Wales note is, on trial spots only.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const L = require('../src/dipcast/site/levels.js');

test('a Scotland trial spot says it is a trial, long and short; an English spot says nothing', () => {
  const s = { trial: 'scotland', upstream_summary: {} };
  assert.match(L.trialWords(s), /^Scotland trial: .*2022 to 2025.*Not yet confirmed on live data\.$/);
  assert.equal(L.trialWords(s, true), 'Scotland: trial forecast');
  // Emergency overflows, alone or in a mixed type, are never forecast (scottish_shadow.py), so not counted:
  // three of them discharge into Loch Lomond under 1 km from Duck Bay and Balloch (docs/NEW-SPOTS-AUDIT-2026-11.md).
  assert.match(L.trialWords(s), /Emergency overflows are not counted, nor outfalls that are both storm and emergency overflows\./);
  assert.equal(L.trialWords({ source: 'designated' }), '');
  assert.equal(L.trialWords(null), '');
});
