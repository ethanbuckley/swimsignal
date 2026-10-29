// The day a spot opens on from Explore (index.html, openDay): the list's day unless it is today. The list opens on
// today since 29 Oct 2026, so passing its day opened every spot tapped from Explore with today picked and its
// detail open, in place of the spot's own answer. Taps on rows and cards, the map's dots, and the cards' links.
// node --test tests/site_open_day.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const def = n => { const i = html.indexOf(`const ${n} = `); return html.slice(i, html.indexOf('\n', i)); };

test('today opens a spot on its own answer; another day opens on that day', () => {
  const ctx = vm.createContext({ VIEW: { day: null }, today: () => '2026-10-29' });
  vm.runInContext(def('openDay') + '\nthis.openDay = openDay;', ctx);
  for (const [day, want] of [[null, null], ['2026-10-29', null], ['2026-11-01', '2026-11-01']]) {
    ctx.VIEW.day = day; assert.equal(ctx.openDay(), want, String(day));
  }
});

test('rows, cards and the map\'s dots open through it, and the cards\' links follow the same rule', () => {
  assert.match(html, /e\.preventDefault\(\); select\(a\.dataset\.id, true, true, openDay\(\)\); \}\)\);/);   // bindItems: rows and cards
  assert.match(html, /\.on\('click', \(\) => select\(s\.id, false, true, openDay\(\)\)\)/);   // the map's dots
  assert.match(html, /href="\$\{esc\(iso && iso !== today\(\) && daily\(s\) \? spotPath\(s\.id\) \+ '#day=' \+ iso : spotPath\(s\.id\)\)\}"/);   // savedCard
  assert.match(def('listPath'), /openDay\(\) && daily\(s\) \? '#day=' \+ openDay\(\)/);
  assert.doesNotMatch(html, /select\([^)]*VIEW\.day\)/);
});
