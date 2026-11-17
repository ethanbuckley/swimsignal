// The river tile's "higher or lower than usual here" sentence (docs/RIVER-ORDER-LINE-PROPOSAL-2026-11.md, decided
// 17 November 2026): the build puts `ecoli_usual` on an in-season day at a listed river spot (river_usual.direction);
// the page adds one sentence after the percentage's, and nothing without it. The figure and its band do not change.
// node --test tests/site_river_usual.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const lakeTest = fs.readFileSync(path.join(__dirname, 'site_lake_usual.test.cjs'), 'utf8');
// The same page harness as the lake line's test: its set-up up to its first fixture.
const harness = lakeTest.slice(lakeTest.indexOf('const DATES'), lakeTest.indexOf('const day ='));
const { page, text, DATES } = new Function('require', '__dirname', 'fs', 'path', 'vm', 'assert', harness + '\nreturn { page, text, DATES };')(require, __dirname, fs, path, vm, assert);

const day = (date, usual, p = 0.14, season = true) => ({ date, label: 'low', risk: 0.01, p_ecoli_gt900: p, in_validated_season: season, rain_48h_mm: 2,
  ...(usual ? { ecoli_usual: usual } : {}) });
const river = (usuals, { dates = DATES, season = true } = {}) => ({ id: 'osm-test', name: 'River Test at the bridge', kind: 'river', source: 'osm',
  location: { mode: 'river' }, upstream_summary: { overflows: 4 }, ecoli_scope: { water_body_validated: true },
  now: { label: 'low', risk: 0, discharging_upstream: 0, monitored_upstream: 4 }, contributors: [], assumptions: { max_upstream_km: 60, recent_spill_hours: 48 },
  days: dates.map((d, i) => day(d, usuals[i] === undefined ? usuals[0] : usuals[i], i ? 0.09 : 0.14, season)) });
const tile = (ctx, d) => vm.runInContext('facts', ctx)(d).find(t => /E.&nbsp;coli estimate/.test(t.label)) || {};

test('the three sentences, and nothing for any other word', () => {
  const line = vm.runInContext('riverUsual', page());
  assert.equal(line({ ecoli_usual: 'higher' }), 'That is higher than usual here.');
  assert.equal(line({ ecoli_usual: 'lower' }), 'That is lower than usual here.');
  assert.equal(line({ ecoli_usual: 'about' }), 'That is about usual here.');
  for (const x of [{}, { ecoli_usual: 'sideways' }, { ecoli_usual: null }, null]) assert.equal(line(x), '');
});

test('on the river tile the sentence follows the percentage; the figure and its band are as before', () => {
  const ctx = page();
  const with_ = tile(ctx, river(['higher'])), without = tile(ctx, river([null]));
  assert.match(text(with_.say), /^Chance a water sample would show E\. coli over 900 per 100 ml today; 9% tomorrow\. That is higher than usual here\. This estimate counts/);
  assert.match(text(without.say), /^Chance a water sample would show E\. coli over 900 per 100 ml today; 9% tomorrow\. This estimate counts/);
  assert.doesNotMatch(text(without.say), /usual/);
  for (const k of ['fig', 'word', 'wordTone', 'vis', 'rel']) assert.equal(with_[k], without[k], k);
  assert.match(text(tile(ctx, river(['lower'])).say), /tomorrow\. That is lower than usual here\. This/);
  assert.match(text(tile(ctx, river(['about'])).say), /tomorrow\. That is about usual here\. This/);
  // Today's word only: tomorrow's does not add a second sentence.
  assert.equal((text(tile(ctx, river(['higher', 'lower'])).say).match(/usual/g) || []).length, 1);
});

test('out of season the tile has no figure and no sentence, even if a day carried a word', () => {
  const oct = ['2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08'];
  for (const t of vm.runInContext('facts', page(oct))(river(['higher'], { dates: oct, season: false })))
    assert.doesNotMatch(text(t.say) + text(t.fold), /than usual|about usual/);
});
