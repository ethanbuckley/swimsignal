// When location is blocked, the line names the control that was pressed so it can be pressed again (index.html,
// locate): the pin at the end of the search box (NEAR_PIN), or "Near me" among the sorts. On 29 Oct 2026 the pin
// replaced the "Show spots near me" button and the line still named the button. node --test tests/site_near_me_words.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const locate = html.slice(html.indexOf('function locate('), html.indexOf('\n}\n', html.indexOf('function locate(')));

test('the blocked-location line names a control the page has', () => {
  assert.match(locate, /then press \$\{at === 'cta' \? 'the location pin in the search box' : 'Near me'\} again\./);
  assert.doesNotMatch(locate, /Show spots near me/);   // no such button since the pin
  // The two it names: the pin in the search (data-near-cta, which calls locate('cta')) and the Near me sort.
  assert.match(html, /const NEAR_PIN = '<button type="button" class="search-loc" data-near-cta aria-label="Spots near me">/);
  assert.match(html, /\$\{'geolocation' in navigator \? NEAR_PIN : ''\}<\/div>/);
  assert.match(html, /nearCta\.addEventListener\('click', \(\) => locate\('cta'\)\)/);
  assert.match(html, /const SORTS = \{[^}]*near: 'Near me'/);
});
