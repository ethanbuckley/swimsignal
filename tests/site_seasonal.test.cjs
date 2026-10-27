// Past spills upstream by month (src/dipcast/site/seasonal.js): the fold's words and table for each case,
// from d.seasonal as src/dipcast/seasonal.py gives it. node --test tests/site_seasonal.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { join } = require('node:path');
const se = require('../src/dipcast/site/seasonal.js');

const days = [62, 57, 62, 60, 62, 60, 62, 62, 60, 62, 60, 62];   // 2024 and 2025: a leap February
const spill = [33, 21, 24, 25, 21, 30, 33, 32, 27, 22, 29, 23];
const S = extra => ({ years: [2024, 2025], overflows: 16, covered_min: 15, days, spill, short: { 2021: 0, 2022: 0, 2023: 0 }, ...extra });
const spot = s => ({ id: 'x', name: 'X', seasonal: s });
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');

test('history words: years, the overflows, and the counts behind each share', () => {
  const h = se.seasonalTile(spot(S()));
  assert.match(h, /^<details class="tile fold" id="seasonal"><summary><span class="t-lab"><svg class="ic"[^>]*>.*<\/svg><span>Past spills upstream, by month<\/span><\/span><\/summary>/);
  const t = text(h);
  assert.match(t, /History, not a forecast\. The share of days in each month, 2024 to 2025, when at least one of the 16 monitored overflows upstream reported a spill\./);
  assert.match(t, /July 53% 33 of 62/);
  assert.match(t, /February 37% 21 of 57/);
  assert.match(t, /at least 15 of the 16 had a working monitor \(90% of the year or more\) and a held record\. The rest are left out/);
  assert.match(t, /Not counted: 2021 to 2023, when too few/);
  assert.match(t, /Every overflow counts the same, from one beside the spot to one 60 km upstream/);
  assert.match(h, /<a href="terms\.html#data">Credits and licences<\/a>/);
});

test('an accessible table: caption, column and row headers; the bar is hidden from screen readers', () => {
  const h = se.seasonalTile(spot(S()));
  assert.match(h, /<table class="seasonal"><caption class="sr">Share of days with a spill reported upstream, by month<\/caption>/);
  assert.equal((h.match(/<th scope="row">/g) || []).length, 12);
  assert.equal((h.match(/<th scope="col"/g) || []).length, 3);
  for (const m of h.matchAll(/<span class="s-bar"[^>]*>/g)) assert.match(m[0], /aria-hidden="true"/);
  assert.match(h, /style="width:53%"/);
});

test('one overflow, all covered, one year', () => {
  const t = text(se.seasonalTile(spot(S({ years: [2025], overflows: 1, covered_min: 1, short: {}, spill: Array(12).fill(0), days: [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31] }))));
  assert.match(t, /each month, 2025, when the monitored overflow upstream reported a spill/);
  assert.match(t, /Its monitor worked through each year counted\./);
  assert.match(t, /February 0% 0 of 28/);
  assert.doesNotMatch(t, /Not counted|counts the same/);
});

test('years that are not consecutive are listed', () => {
  assert.equal(se.seasonalYears([2021, 2023, 2024]), '2021, 2023 and 2024');
  assert.equal(se.seasonalYears([2023, 2024, 2025]), '2023 to 2025');
});

test('nothing upstream, records too thin, and nothing to show', () => {
  assert.match(text(se.seasonalTile(spot({ none: true }))), /No monitored storm overflow was found upstream of this spot, so there is no spill history to show\./);
  assert.doesNotMatch(se.seasonalTile(spot({ none: true })), /<table/);
  assert.match(text(se.seasonalTile(spot({ too_few: true, overflows: 38 }))), /Too few of the 38 overflows upstream had a working monitor/);
  assert.equal(se.seasonalTile(spot(undefined)), '');
  assert.equal(se.seasonalTile({ id: 'x', error: 'forecast failed', seasonal: S() }), '');
  assert.equal(se.seasonalTile({ id: 'x', unlisted: true, seasonal: S() }), '');
});

test('never "safe", "clean" or "clear", and no pills or callouts', () => {
  for (const s of [S(), S({ overflows: 1, covered_min: 1 }), { none: true }, { too_few: true, overflows: 3 }]) {
    const h = se.seasonalTile(spot(s));
    assert.doesNotMatch(text(h), /\bsafe|\bclean|\bclear/i);
    assert.doesNotMatch(h, /class="[^"]*(pill|badge|callout)/);
  }
});

test("no other script of the page defines one of seasonal.js's names; the page loads it and draws it after the scores", () => {
  const site = join(__dirname, '../src/dipcast/site');
  const names = src => new Set([...src.matchAll(/^(?:const|let|var|function|async function|class)\s+([A-Za-z_$][\w$]*)/gm)].map(m => m[1]));
  const mine = names(fs.readFileSync(join(site, 'seasonal.js'), 'utf8'));
  const html = fs.readFileSync(join(site, 'index.html'), 'utf8');
  const others = [html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')),
    ...fs.readdirSync(site).filter(f => f.endsWith('.js') && !['seasonal.js', 'sw.js'].includes(f)).map(f => fs.readFileSync(join(site, f), 'utf8'))];
  assert.deepEqual(others.flatMap(src => [...names(src)].filter(n => mine.has(n))), []);
  assert.ok([...mine].every(n => /^(seasonal|SEASONAL)/.test(n)), [...mine].join(' '));
  const at = html.indexOf('src="seasonal.js"');
  assert.ok(at > html.indexOf('src="spotscores.js"') && at < html.indexOf('<script>\n'));
  assert.match(html, /scoresHost\(d\) : ''\)[^\n]*\n\s+\+ \(typeof seasonalTile === 'function' \? seasonalTile\(d\) : ''\);/);
  assert.match(fs.readFileSync(join(site, 'sw.js'), 'utf8'), /`seasonal\.js\?v=\$\{BUILD\}`/);
});
