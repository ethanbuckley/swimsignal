// A first visit (30 Oct 2026): what to do here, said in the strip's own note, only before anything is saved, planned
// or opened; once a spot is saved, Your places takes over.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const app = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');

test('the strip note says what to do, on a first visit only', () => {
  assert.match(app, /!SAVED\.size && !OPENED && !\(typeof planOuting === 'function' && planOuting\(stored\(PLAN_KEY\), planDates\(\)/);
  assert.match(app, /' Open a spot to see why\. Save the ones you use to keep them at the top\.' : ''\}<\/p>`/);
});
