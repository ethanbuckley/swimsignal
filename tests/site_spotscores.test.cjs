// How the forecast has done here (src/dipcast/site/spotscores.js): the tile's words for each case, from
// counts as data/spot_scores.json gives them. node --test tests/site_spotscores.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { join } = require('node:path');
const sc = require('../src/dipcast/site/spotscores.js');

const G = { warn_at: 0.4, min_spills: 10, first_day: '2026-09-29', last_day: '2026-10-05' };
const counts = extra => ({ overflows: 15, scored_overflows: 15, overflow_days: 104, spill_days: 0, forecasts: 520,
  hits: 0, misses: 0, false_alarms: 0, days: 7, first_day: '2026-09-29', last_day: '2026-10-05', ...extra });
const spot = (id, extra = {}) => ({ id, name: id, upstream_summary: { overflows: 15 }, ...extra });
const words = s => sc.scoresWords(s, G).say.join(' ').replace(/<[^>]+>/g, '');
const tile = (d, s) => sc.scoresTile(d, { ...G, spots: s ? { [d.id]: s } : {} });

test('no spill: says so and claims no skill', () => {
  const w = words(counts({ false_alarms: 0 }));
  assert.equal(w, 'Since 29 Sept the forecast has been checked at all 15 overflows upstream: 104 overflow-days, none with a spill. '
    + 'With no spills, there is nothing yet to judge its warnings by. No forecast reached the High risk line.');
  assert.match(words(counts({ false_alarms: 1 })), /It gave 1 false alarm: a forecast at the High risk line on a day with no spill\.$/);
  assert.doesNotMatch(words(counts({ false_alarms: 3 })), /%/, 'no share without a spill');
});

test('below ten spill days: the counts, no share, and the minimum said', () => {
  const w = words(counts({ spill_days: 1, hits: 0, misses: 5, false_alarms: 3 }));
  assert.match(w, /104 overflow-days, 1 with a spill\./);
  assert.match(w, /Too few spills to give a share: that takes 10\. None of the 5 forecasts for it reached the High risk line\. It gave 3 false alarms: forecasts at that line on days with no spill\.$/);
  assert.doesNotMatch(w, /%/);
  assert.match(words(counts({ spill_days: 9, hits: 17, misses: 28 })), /17 of the 45 forecasts for them reached/);
});

test('ten spill days or more: the share, as the Accuracy page words it, with its counts and the days', () => {
  const w = words(counts({ overflows: 65, scored_overflows: 65, overflow_days: 440, spill_days: 50, hits: 65, misses: 185, false_alarms: 69 }));
  assert.match(w, /all 65 overflows upstream: 440 overflow-days, 50 with a spill\./);
  assert.match(w, /It warned of 26% of those spills: 65 of the 250 forecasts for them reached the High risk line\. It gave 69 false alarms/);
  assert.match(w, /That is 7 days so far, too few to judge across different weather\.$/);
  assert.doesNotMatch(words(counts({ spill_days: 10, hits: 1, misses: 49, days: 14 })), /too few to judge/);
  assert.match(words(counts({ spill_days: 19, hits: 0, misses: 95 })), /It warned of 0% of those spills: none of the 95 forecasts/);
});

test('overflows that cannot be scored are counted, and none scored says so', () => {
  assert.match(words(counts({ overflows: 29, scored_overflows: 28 })), /checked at 28 of the 29 overflows upstream:/);
  assert.match(words(counts({ overflows: 2, scored_overflows: 2 })), /checked at both overflows upstream:/);
  assert.match(words(counts({ overflows: 1, scored_overflows: 1 })), /checked at the overflow upstream:/);
  assert.equal(words(counts({ overflows: 14, scored_overflows: 0, overflow_days: 0 })),
    'None of the 14 overflows upstream has been scored yet. They have no live feed, or no day that passed the scoring rules.');
  assert.match(words(counts({ overflows: 1, scored_overflows: 0 })), /^The overflow upstream has not been scored yet\. It has no live feed/);
  assert.match(sc.scoresWords(counts({}), G).more, /no live feed, or with no day that passed the <a href="verification\.html#live-scoring">scoring rules<\/a>, cannot be scored/);
});

test('never "accurate" or "safe", and a level word always has its noun', () => {
  const cases = [counts({}), counts({ false_alarms: 2 }), counts({ spill_days: 3, hits: 2, misses: 13, false_alarms: 1 }),
    counts({ spill_days: 50, hits: 65, misses: 185, false_alarms: 69 }), counts({ scored_overflows: 0 })];
  for (const s of cases) {
    const w = sc.scoresWords(s, G), all = w.say.join(' ') + ' ' + w.more;
    assert.doesNotMatch(all.replaceAll('Accuracy page', ''), /accura|\bsafe/i, 'the page is called Accuracy; nothing else says it');
    for (const m of all.matchAll(/\bHigh\b/g)) assert.equal(all.slice(m.index, m.index + 9), 'High risk');
  }
});

test('the tile: one section after the evidence, with the link and the fold; nothing where there is nothing to score', () => {
  const html = tile(spot('eden-lazonby'), counts({ spill_days: 50, hits: 65, misses: 185 }));
  assert.match(html, /^<section class="tile" id="scores" aria-labelledby="scores-h"><h2 class="t-lab" id="scores-h"><svg class="ic"[^>]*>.*<\/svg><span>How the forecast has done here<\/span><\/h2>/);
  assert.match(html, /<a href="verification\.html#warnings">Every overflow's scores, on the Accuracy page<\/a>/);
  assert.match(html, /<details class="t-more"><summary><span class="sr">How the forecast has done here: what this means<\/span><\/summary><p>An overflow-day is one overflow on one day\./);
  assert.match(html, /A warning is a spill chance of 40% or more/);
  assert.doesNotMatch(html, /class="[^"]*(pill|badge|callout)/);
  assert.equal(tile(spot('a', { error: 'forecast failed: x' }), counts({})), '', 'a failed spot');
  assert.equal(tile(spot('a', { error: 'An isolated lake: no river reaches it' }), counts({})), '', 'an isolated lake');
  assert.equal(tile(spot('a', { unlisted: true }), counts({})), '', 'a point clicked on the map');
  assert.equal(tile(spot('a', { upstream_summary: { overflows: 0 } }), counts({ overflows: 0 })), '', 'nothing upstream');
  assert.equal(tile(spot('a'), null), '', 'not in the file');
  assert.equal(sc.scoresTile(spot('a'), null), '', 'no file');
  assert.equal(sc.scoresHost(spot('a', { error: 'x' })), '');
});

test("no other script of the page defines one of spotscores.js's names, and the page loads it before its own script", () => {
  const site = join(__dirname, '../src/dipcast/site');
  const names = src => new Set([...src.matchAll(/^(?:const|let|var|function|async function|class)\s+([A-Za-z_$][\w$]*)/gm)].map(m => m[1]));
  const mine = names(fs.readFileSync(join(site, 'spotscores.js'), 'utf8'));
  const html = fs.readFileSync(join(site, 'index.html'), 'utf8');
  const others = [html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')),
    ...fs.readdirSync(site).filter(f => f.endsWith('.js') && !['spotscores.js', 'sw.js'].includes(f)).map(f => fs.readFileSync(join(site, f), 'utf8'))];
  assert.deepEqual(others.flatMap(src => [...names(src)].filter(n => mine.has(n))), []);
  assert.ok([...mine].every(n => /^(scores|SCORES)/.test(n)), [...mine].join(' '));
  const at = html.indexOf('src="spotscores.js"');
  assert.ok(at > html.indexOf('src="evidence.js"') && at < html.indexOf('<script>\n'));
  // Right after the evidence tile in render(), so the regroup can move the pair.
  assert.match(html, /evidenceTile\(d, Date\.now\(\), DATA\.generated_at\) : ''\)\n\s+\+ \(typeof scoresHost === 'function' \? scoresHost\(d\) : ''\)/);
});
