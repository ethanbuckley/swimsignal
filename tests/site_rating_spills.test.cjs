// Where a poor EA rating keeps every day at high risk, the sewage spill forecast and spills right now are said apart
// from it (30 Oct 2026, a swimmer asked why Sheep's Green never changes). No new threshold: the spill forecast's own
// level for each day (the day's `label`) and the live feeds' counts, as the page already had them, further down.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const app = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');

test('each day under a poor rating also shows its own spill forecast', () => {
  assert.match(app, /on && !gone && advisedAgainst\(d\) && hasData\(x\) && x\.label \? `<span class="lsub">spills: \$\{esc\(x\.label\)\}<\/span>` : ''/);
});
test('the five days\' sentence says the spill forecast on its own beside the rating', () => {
  assert.match(app, /The sewage spill forecast on its own is \$\{known\[0\]\.label\} \$\{dayWord\(known\[0\]\.date\)\}, under each day below\. /);
});
test('the line under the level says how many reporting are spilling now, and the silent ones as unknown', () => {
  assert.match(app, /spillNow = mon \? `, \$\{k \? `\$\{k\} spilling now` : 'none spilling now'\}` : ''/);
  assert.match(app, /so could be spilling unseen`\);/);
  assert.match(app, /A monitor reports when it spills, not how much or what is in it\./);
});
