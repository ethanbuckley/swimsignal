// Access at each spot of a plan's outing (outing.js, outingAccess): the spot's own practical guide for parking,
// the path, getting in and getting out, in the facts' own words with who says so and the guide's checked line,
// the topics it lacks, and plain states for no guide, a guide still loading and one that did not arrive.
// Nothing is added to a fact. node --test tests/site_outing_access.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { join } = require('node:path');
const O = require('../src/dipcast/site/outing.js');
const G = require('../src/dipcast/site/guide.js');

const SITE = join(__dirname, '../src/dipcast/site');
const TODAY = '2026-10-28';
const NT = 'https://www.nationaltrust.org.uk/visit/peak-district-derbyshire/ilam-park-dovedale-and-the-white-peak';
const PDNPA = 'https://www.peakdistrict.gov.uk/visiting/miles-without-stiles/dovedale';
const fact = (topic, text, extra = {}) => ({ topic, text, status: 'confirmed', source: PDNPA, source_name: 'Peak District National Park Authority', ...extra });
const GUIDE = { checked: '2026-10-03', how: 'desk', facts: [
  fact('parking', 'Dovedale Car Park is reached via Thorpe and the A515 (postcode DE6 2AY, grid ref SK 1465 5095).'),
  fact('parking', 'Parking is free for National Trust members.', { source: NT, source_name: 'National Trust' }),
  fact('path', 'An access-for-all route runs 640 m from Dovedale Car Park to the Stepping Stones.'),
  fact('entry', 'The National Trust says many visitors stop near the stepping stones for a picnic or a paddle.', { source: NT, source_name: 'National Trust' }),
  fact('toilets', 'Dovedale toilets are near the concession stands at the car park.'),
  fact('rules', 'The park authority advises entering open water only as part of a supervised, organised event.'),
] };
const spot = (extra = {}) => ({ id: 'dove-dovedale', name: 'River Dove, Dovedale stepping stones', detail_file: 'spot/dove-dovedale.json', detail_loaded: true, guide: GUIDE, ...extra });

test('the four topics in the facts\' own words, each with who says so, under the guide\'s checked line', () => {
  const h = O.outingAccess(spot(), TODAY);
  assert.ok(h.startsWith(`<p class="g-src">${G.guideChecked(GUIDE, TODAY)}</p>`), h);
  assert.match(h, /Checked 3 Oct 2026 from the published pages linked below, not on site\./);
  for (const f of GUIDE.facts.slice(0, 4)) assert.ok(h.includes(`<p class="g-text">${f.text}</p>`), f.text);
  // Who says so, as the spot page's guide draws it, link and all.
  assert.ok(h.includes(`<a href="${PDNPA}">Peak District National Park Authority</a>`));
  assert.ok(h.includes(`<a href="${NT}">National Trust</a>`));
  assert.equal((h.match(/<span class="g-who">Verified<\/span>/g) || []).length, 4);   // one per run: two parking sources, path, entry
  // In the order a swimmer meets them, under the guide's own headings.
  const at = s => h.indexOf(s);
  assert.ok(at('<dt>Parking</dt>') < at('<dt>Path to the water</dt>') && at('<dt>Path to the water</dt>') < at('<dt>Getting in</dt>'));
  // The topics outside the four are named, not drawn.
  assert.doesNotMatch(h, /toilets are near|supervised, organised event/);
  assert.match(h, /Also in the guide on the spot's page: toilets, who can swim\./);
  // Getting out is missing: said as unknown.
  assert.match(h, /<p class="g-gap">Not in this guide yet: getting out\.<\/p>/);
});

test('a swimmer\'s suggestion says who and when, and that it is not checked', () => {
  const g = { checked: '2026-10-20', how: 'desk', facts: [fact('exit', 'Steps by the weir.', { status: 'suggested', from: 'A swimmer', on: '2026-10-20', source: undefined })] };
  const h = O.outingAccess(spot({ guide: g }), TODAY);
  assert.match(h, /<span class="g-who">A swimmer's suggestion<\/span>, from A swimmer, 20 Oct 2026\. Not yet checked by SwimSignal\./);
  assert.match(h, /Swimmers' suggestions only, gathered up to 20 Oct 2026/);
  assert.match(h, /Not in this guide yet: parking, path to the water, getting in\./);
});

test('no guide, a guide still loading and a guide that did not arrive each say so, and never mix', () => {
  assert.equal(O.outingAccess(spot({ guide: undefined }), TODAY), '<p class="small muted">No access guide for this spot yet.</p>');
  assert.equal(O.outingAccess(spot({ guide: { checked: '2026-10-03', facts: [] } }), TODAY), '<p class="small muted">No access guide for this spot yet.</p>');
  assert.equal(O.outingAccess(spot({ detail_loaded: false, guide: undefined }), TODAY), '<p class="small muted">Loading the access guide…</p>');
  const lost = O.outingAccess(spot({ detail_loaded: false, detail_missing: true, guide: undefined }), TODAY);
  assert.match(lost, /could not be loaded here/);
  assert.doesNotMatch(lost, /No access guide/);
  // A spot whose detail file is not separate (no detail_file) reads its guide as given.
  assert.match(O.outingAccess({ id: 'x', name: 'X', guide: GUIDE }, TODAY), /<dt>Parking<\/dt>/);
  // Only the four topics, none of them present: the checked line and all four gaps.
  const only = O.outingAccess(spot({ guide: { checked: '2026-10-03', how: 'desk', facts: [fact('toilets', 'By the car park.')] } }), TODAY);
  assert.doesNotMatch(only, /<dl/);
  assert.match(only, /Not in this guide yet: parking, path to the water, getting in, getting out\./);
  assert.equal(O.outingAccess(null, TODAY), '');
});

test('the desk check of permission comes first, in its own words, with its date', () => {
  const access = { status: 'restricted_guidance', checked_at: '2026-10-03', text: 'Permission at this point has not been confirmed.' };
  const h = O.outingAccess(spot({ access }), TODAY);
  assert.ok(h.startsWith('<p class="g-text">Permission at this point has not been confirmed.</p><p class="g-src">Desk check 2026-10-03; current signs not inspected.</p>'), h);
  // Before every state, a guide or none.
  assert.ok(O.outingAccess(spot({ access, guide: undefined }), TODAY).startsWith('<p class="g-text">Permission'));
  assert.ok(O.outingAccess(spot({ access, detail_loaded: false, guide: undefined }), TODAY).startsWith('<p class="g-text">Permission'));
});

test('a fact\'s words and a source\'s name are escaped', () => {
  const g = { checked: '2026-10-03', how: 'desk', facts: [fact('entry', 'Steps <b>&</b> a rail.', { source_name: 'A "council" <page>' })] };
  const h = O.outingAccess(spot({ guide: g }), TODAY);
  assert.ok(h.includes('<p class="g-text">Steps &lt;b&gt;&amp;&lt;/b&gt; a rail.</p>'));
  assert.ok(h.includes('A &quot;council&quot; &lt;page&gt;</a>'));
  assert.doesNotMatch(h, /<b>/);
});

test('the outing draws an access block in each column and fills it when the spot\'s file is in', () => {
  const col = (id, name) => ({ id, name, href: `spot/${id}/`, tone: 'low', headline: 'Low risk tomorrow', level: 'low', access: O.outingAccess(spot({ id, name }), TODAY) });
  const h = O.outingSection({ day: '2026-10-29', when: '', spot: 'a', groups: [], backupGroups: [], missing: [], issued: 'x', open: true,
    main: col('a', 'Dovedale'), alt: col('b', 'Other') });
  assert.equal((h.match(/<div class="outing-access" data-outing-access="[ab]"><p class="outing-role">Access<\/p>/g) || []).length, 2);
  assert.ok(h.indexOf('data-outing-access="a"') < h.indexOf('data-outing-access="b"'));
  const src = fs.readFileSync(join(SITE, 'outing.js'), 'utf8');
  assert.match(src, /\n      access: outingAccess\(s, today\(\)\),\n/);   // each column's access, beside its notice and level
  assert.match(src, /spotDetail\(s\)\.then\(\(\) => \{ const el = tile\.querySelector\(`\[data-outing-access="\$\{CSS\.escape\(s\.id\)\}"\]`\);/);
  // guide.js is in the page before outing.js, which reads its names.
  const page = fs.readFileSync(join(SITE, 'index.html'), 'utf8');
  assert.ok(page.indexOf('<script src="guide.js">') < page.indexOf('<script src="outing.js">'));
});

test('with notices and guides together: the notice line above the columns, each column tag first and access last', () => {
  const ea = require('../src/dipcast/site/eatoday.js');
  const notice = { line: 'Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026', publisher: 'Environment Agency',
    link: 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945', since: '2026-06-19', checked: '2026-10-26', state: 'checked', restricts: true };
  const status = { line: 'City of London: swimming status notice (members only this week) since 20 Oct 2026', publisher: 'City of London',
    link: 'https://www.cityoflondon.gov.uk/', since: '2026-10-20', checked: '2026-10-26', state: 'checked', restricts: false };
  const col = (s) => ({ id: s.id, name: s.name, href: `spot/${s.id}/`, tone: 'low', headline: 'Low risk tomorrow', level: 'low',
    official: O.outingOfficial(s), notice: ea.eaTodayBrief(s), advised: ea.eaTodayRestricts(s), access: O.outingAccess(s, TODAY) });
  const a = spot({ id: 'a', name: 'Dovedale', official: [notice] }), b = spot({ id: 'b', name: 'Status Pond', official: [status], guide: undefined });
  const h = O.outingSection({ day: '2026-10-29', when: '', spot: 'a', groups: [], backupGroups: [], missing: [], issued: 'x', open: true, main: col(a), alt: col(b) });
  const at = x => h.indexOf(x);
  assert.ok(at('outing-notices') > 0 && at('outing-notices') < at('outing-pair'));
  // Spot: its notice tag, then its level, then its access; backup likewise, with its no-guide state.
  const spotCol = h.slice(at('data-id="a"'), at('data-id="b"'));
  assert.ok(spotCol.indexOf('o-tag') < spotCol.indexOf('Low risk tomorrow') && spotCol.indexOf('Low risk tomorrow') < spotCol.indexOf('data-outing-access="a"'));
  assert.match(spotCol, /<dt>Parking<\/dt>/);
  assert.match(h.slice(at('data-id="b"')), /No access guide for this spot yet\./);
  // The access block adds no notice words: the guide's facts are about access, not the notice.
  assert.doesNotMatch(h.slice(at('data-outing-access="a"'), at('data-id="b"')), /Official|advice against/);
});
