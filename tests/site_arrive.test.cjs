// The arrival guide (src/dipcast/site/arrive.js, prototype): the practical guide as a journey, in order; every fact
// with its line of who says so; permission, the way in and the water kept in separate parts; what nobody has checked
// listed; nothing that says or implies "safe"; and the page unchanged without ?arrive=1.
// node --test tests/site_arrive.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const A = require('../src/dipcast/site/arrive.js');
const G = require('../src/dipcast/site/guide.js');

const src = (extra = {}) => ({ status: 'confirmed', source: 'https://www.example.gov.uk/p', source_name: 'Example Council', ...extra });
const guide = (facts, extra = {}) => ({ checked: '2026-10-30', how: 'desk', photos: [], facts, ...extra });
const spot = (g, extra = {}) => ({ id: 'a', name: 'Wharfe at Cromwheel, Ilkley', guide: g, ...extra });
const u0 = () => A.arrivalUnknowns(guide(FACTS));
const plain = h => h.replace(/<[^>]+>/g, ' ').replace(/&#39;/g, "'").replace(/&amp;/g, '&').replace(/\s+/g, ' ');

const FACTS = [
  { topic: 'parking', text: 'Denton Road car park.', ...src() },
  { topic: 'transport', text: 'Trains to Leeds.', ...src({ source: 'https://www.example.co.uk/rail', source_name: 'Rail Co' }) },
  { topic: 'path', text: 'A ramp down to the riverside path.', ...src() },
  { topic: 'entry', text: 'Shingle at low water.', status: 'suggested', from: 'Sam', on: '2026-09-12' },
  { topic: 'hours', text: 'Toilets open 8am to 8pm in summer.', ...src() },
  { topic: 'rules', text: 'Events of more than 20 people need permission.', ...src({ source: 'https://www.example.gov.uk/parks', source_name: 'Parks' }) },
  { topic: 'rules', text: 'A 2020 decision. This is a December 2020 record, not a current check.', ...src({ source: 'https://www.gov.uk/x', source_name: 'Defra', source_date: '2020-12' }) },
];

test('the steps run in the order a first-time visitor meets them, and every guide topic but the rules and the paddling ones has a step', () => {
  assert.deepEqual(A.ARRIVAL_STEPS.map(s => s.key), ['there', 'path', 'entry', 'exit', 'facilities', 'seasons']);
  assert.deepEqual(A.ARRIVAL_STEPS[0].topics, ['transport', 'parking'], 'bus and train before the car');
  const stepped = new Set(A.ARRIVAL_STEPS.flatMap(s => s.topics));
  const left = G.GUIDE_TOPICS.map(([k]) => k).filter(k => !stepped.has(k));
  assert.deepEqual(left, ['rules', 'launch', 'carry', 'paddle'], 'the rules are their own part; boats and boards are the usual guide\'s');
  const html = A.arrivalTile(spot(guide(FACTS)), '2026-10-30');
  const at = s => { const i = html.indexOf(s); assert.ok(i >= 0, s); return i; };
  assert.ok(at('Trains to Leeds.') < at('Denton Road car park.') && at('Denton Road car park.') < at('A ramp down')
    && at('A ramp down') < at('Shingle at low water.') && at('Shingle at low water.') < at('Toilets open 8am'), 'in journey order');
});

test('every fact keeps its own line of who says so: verified, a dated record, or a swimmer\'s word', () => {
  const html = A.arrivalTile(spot(guide(FACTS)), '2026-10-30');
  assert.match(html, /<span class="g-who">Verified<\/span>: <a href="https:\/\/www\.example\.co\.uk\/rail">Rail Co<\/a>\./);
  assert.match(html, /<span class="g-who">Source<\/span>: <a href="https:\/\/www\.gov\.uk\/x">Defra<\/a>, December 2020\./);
  assert.match(html, /<span class="g-who">A swimmer's suggestion<\/span>, from Sam, 12 Sept? 2026\. Not yet checked by SwimSignal\./);
  assert.match(html, /Checked 30 Oct 2026 from the published pages linked below, not on site\./);
  assert.equal(A.arrivalCountsSaid(guide(FACTS)), "In this guide: 5 facts verified, 1 from dated records, 1 a swimmer's word, not checked; 4 published pages in all.");
  assert.deepEqual(A.arrivalCounts(guide(FACTS)), { verified: 5, dated: 1, suggested: 1, pages: 4 });
  // Every fact's words reach the page, and only once.
  for (const f of FACTS) assert.equal(html.split(f.text).length - 1, 1, f.text);
});

test('permission, the way in and the water are separate parts, never one verdict', () => {
  const html = A.arrivalTile(spot(guide(FACTS)), '2026-10-30');
  const way = html.indexOf('id="arr-way-h"'), who = html.indexOf('id="arr-who-h"'), water = html.indexOf('id="arr-water-h"'), unk = html.indexOf('id="arr-unk-h"');
  assert.ok(way > 0 && way < who && who < water && water < unk, 'four parts, in order');
  const part = (a, b) => html.slice(a, b);
  assert.match(part(who, water), /Events of more than 20 people/, 'the rules are under who can swim');
  assert.doesNotMatch(part(way, who), /Events of more than 20 people/, 'and not in the journey');
  assert.match(part(who, water), /A path, a car park or a beach is not permission to swim\./);
  assert.match(part(water, unk), /<a href="#risk-hero">the forecast at the top of this page<\/a>/);
  assert.doesNotMatch(part(water, unk), /low risk|high risk|moderate|E\. coli/i, 'the forecast is linked, not restated');
  // The desk check of access (access.py) joins the rules in its own words; without either, the gap is said.
  const a = { status: 'unconfirmed', checked_at: '2026-10-03', url: 'https://lakedistrict.gov.uk/x', text: 'Access at this point has not been confirmed.' };
  assert.match(A.arrivalPermission({ facts: [] }, { access: a }), /Access at this point has not been confirmed\..*Desk check 2026-10-03; current signs have not been inspected\./s);
  assert.match(A.arrivalPermission({ facts: [] }, {}), /Nothing in this guide says who may swim here\./);
});

test('a step with nothing says so, a step a photo would help says there is none, and both are listed as unchecked', () => {
  const steps = A.arrivalSteps(guide(FACTS));
  assert.deepEqual(steps.filter(s => s.empty).map(s => s.key), ['exit', 'facilities']);
  assert.deepEqual(steps.filter(s => s.noPhoto).map(s => s.key), ['path', 'entry', 'exit']);
  const html = A.arrivalTile(spot(guide(FACTS)), '2026-10-30');
  assert.match(html, /No photo yet of the place to get in\./);
  assert.equal((html.match(/class="arr-none"/g) || []).length, 3, 'getting out, toilets and changing (one line for both), and fees');
  assert.match(html, /<dt>Opening times<\/dt>.*Toilets open 8am.*<dt>Fees and booking<\/dt><dd><p class="arr-none">Nothing in this guide yet\.<\/p>/s, 'the guide\'s own headings');
  assert.ok(u0().includes('Toilets and changing: nothing in this guide.') && u0().includes('Fees and booking: nothing in this guide.'));
  const u = A.arrivalUnknowns(guide(FACTS));
  assert.ok(u.includes('Getting out: nothing in this guide.'));
  assert.ok(u.includes('No photo yet of the path to the water, the place to get in or the place to get out.'));
  for (const q of A.ARRIVAL_ASKED) assert.ok(u.includes(q), q);
  assert.ok(u.includes("1 fact above is a swimmer's word that SwimSignal has not checked."));
  assert.ok(u.includes('No on-site check is recorded for this guide: every verified fact comes from a published page.'));
  assert.ok(!u.some(t => /Nobody/.test(t)));
  const src = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/arrive.js'), 'utf8');
  assert.doesNotMatch(src, /Nobody from SwimSignal/, 'the old wording is gone everywhere');
  // Getting there names whichever way has nothing.
  const carOnly = A.arrivalUnknowns(guide([FACTS[0]]));
  assert.ok(carOnly.includes('Getting there by bus or train: nothing in this guide.'));
  assert.ok(!carOnly.some(t => /by car/.test(t)));
  assert.ok(carOnly.includes('Who can swim here: nothing in this guide.'));
  // A visit: the last line goes.
  assert.ok(!A.arrivalUnknowns(guide(FACTS, { how: 'visit' })).some(t => /No on-site check/.test(t)));
});

// Geograph's, as guides.py passes them: historical, with title, page, licence and changes.
const GEO = { status: 'historical', source: 'https://www.geograph.org.uk/photo/1', source_name: 'Geograph', title: 'Gravel bank',
  licence: 'https://creativecommons.org/licenses/by-sa/2.0/', changes: 'Re-encoded, metadata removed.', w: 640, h: 480, labels: [] };
const pic = (file, topic, extra = {}) => ({ ...GEO, file, topic, caption: `${file}.`, credit: 'Oliver Dixon', taken: '2023-05-16', ...extra });

test('a photo fills only its own step: an overview does not hide the missing path, entry or exit photos', () => {
  const over = guide(FACTS, { photos: [pic('over.jpg', 'overview')] });
  assert.deepEqual(A.arrivalSteps(over).filter(s => s.noPhoto).map(s => s.key), ['path', 'entry', 'exit']);
  const entry = guide(FACTS, { photos: [pic('over.jpg', 'overview'), pic('in.jpg', 'entry')] });
  const steps = A.arrivalSteps(entry);
  assert.deepEqual(steps.filter(s => s.noPhoto).map(s => s.key), ['path', 'exit'], 'the entry photo fills the entry step alone');
  assert.deepEqual(steps.find(s => s.key === 'entry').photos.map(p => p.file), ['in.jpg']);
  const html = A.arrivalTile(spot(entry), '2026-10-30');
  const at = s => html.indexOf(s);
  assert.ok(at('over.jpg') > at('id="arr-way-h"') && at('over.jpg') < at('id="arr-there"'), 'the overview leads the journey');
  assert.ok(at('in.jpg') > at('id="arr-entry"') && at('in.jpg') < at('id="arr-exit"'), 'the entry photo sits in its step');
  assert.match(html, /No photo yet of the path to the water\./);
  assert.match(html, /No photo yet of the place to get out\./);
  assert.doesNotMatch(html, /No photo yet of the place to get in\./);
  assert.ok(A.arrivalUnknowns(entry).includes('No photo yet of the path to the water or the place to get out.'));
});

test('a historical photo says whose it is, when, its licence and changes, and that it shows that day only', () => {
  const g = guide(FACTS, { photos: [pic('in.jpg', 'entry')] });
  const html = A.arrivalTile(spot(g), '2026-10-30');
  assert.match(html, /<span class="g-who">Historical photo<\/span> by Oliver Dixon, taken 16 May 2023: <a href="https:\/\/www\.geograph\.org\.uk\/photo\/1">Gravel bank<\/a> on Geograph\./);
  assert.match(html, /Licensed under <a href="https:\/\/creativecommons\.org\/licenses\/by-sa\/2\.0\/">CC BY-SA 2\.0<\/a>; Re-encoded, metadata removed\. This copy is also under CC BY-SA 2\.0\./);
  assert.match(html, /Not taken by SwimSignal\. It shows that day only, not today's access, permission, water level or conditions\./);
  assert.doesNotMatch(html, /seen on site/, 'never "seen on site"');
  assert.equal(A.arrivalCountsSaid(g), "In this guide: 5 facts verified, 1 from dated records, 1 a swimmer's word, not checked; 4 published pages in all. "
    + 'Photos: 1 historical, by other photographers; none taken by SwimSignal.');
  assert.ok(A.arrivalUnknowns(g).includes('Whether the places in the historical photos look the same today: each shows only the day it was taken.'));
  // A licence the page does not know is neither named nor linked.
  assert.doesNotMatch(G.guideHistorical({ ...pic('x.jpg', 'entry'), licence: 'https://example.org/any' }), /CC BY|Licensed/);
});

test('a sign in a historical photo sits under who can swim, its wording and scope unverified, and is not a rule', () => {
  const sign = pic('sign.jpg', 'rules', { credit: 'Mrs W J Sutherland', taken: '2024-11-13', caption: 'A council sign by the bridge.' });
  const g = guide(FACTS, { photos: [sign] });
  const html = A.arrivalTile(spot(g), '2026-10-30');
  const who = html.indexOf('id="arr-who-h"'), water = html.indexOf('id="arr-water-h"');
  assert.ok(html.indexOf('sign.jpg') > who && html.indexOf('sign.jpg') < water, 'beside the permission part, not in the journey');
  assert.match(html.slice(who, water), /A sign in a historical photo is as it was that day: what it says now, and what stretch it covers, are not verified\./);
  assert.ok(A.arrivalUnknowns(g).includes("What the sign or notice in Mrs W J Sutherland's photo of November 2024 says now, what it covers, and whether it is still there."));
  assert.deepEqual(A.arrivalSteps(g).filter(s => s.noPhoto).map(s => s.key), ['path', 'entry', 'exit'], 'a sign fills no step');
});

test('no guide, a point off the list, or a file that did not arrive', () => {
  const none = A.arrivalTile(spot(null), '2026-10-30');
  assert.match(none, /There is no practical guide for this spot yet: every step below is unknown\./);
  assert.equal((none.match(/class="arr-none"/g) || []).length, 7, 'each of the six steps says nothing yet, once, and so does who can swim');
  assert.equal(A.arrivalTile(spot(guide(FACTS), { unlisted: true }), '2026-10-30'), '');
  assert.equal(A.arrivalTile(spot(guide(FACTS), { detail_missing: true }), '2026-10-30'), '', 'not "no guide" when the file did not arrive');
});

test('nothing in the tile says or implies safe, and a fact\'s words are escaped', () => {
  const bad = '<img src=x onerror=alert(1)>';
  const html = A.arrivalTile(spot(guide([...FACTS, { topic: 'exit', text: bad, status: 'suggested', from: bad, on: '2026-09-12' }])), '2026-10-30');
  assert.doesNotMatch(html, /<img src=x/);
  assert.doesNotMatch(plain(A.arrivalTile(spot(guide(FACTS)), '2026-10-30')), /\bsafe(ly|r|st|ty)?\b|all.clear|good to go|fine to swim/i);
  assert.doesNotMatch(plain(A.arrivalTile(spot(null), '2026-10-30')), /\bsafe(ly|r|st|ty)?\b/i);
});

test('the page is unchanged without ?arrive=1: arrive.js is asked for only then, and the build ships it', () => {
  const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  assert.match(html, /const ARRIVE = new URLSearchParams\(location\.search\)\.get\('arrive'\) === '1';/);
  assert.doesNotMatch(html, /<script src="arrive\.js"/, 'no tag: mountArrival adds it when asked');
  const calls = html.split('\n').filter(l => /mountArrival\(d\)/.test(l) && !/^function/.test(l.trim()));
  assert.ok(calls.length >= 2 && calls.every(l => /if \(ARRIVE\) mountArrival\(d\)/.test(l)), 'every call is behind the flag');
  const build = fs.readFileSync(path.join(__dirname, '../scripts/build_site.py'), 'utf8');
  assert.match(build, /SHELL_SOURCES\.append\(TEMPLATE\.parent \/ "arrive\.js"\)/);
  assert.match(build, /shutil\.copy\(TEMPLATE\.parent \/ "arrive\.js", site \/ "arrive\.js"\)/);
  assert.match(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/sw.js'), 'utf8'), /`arrive\.js\?v=\$\{BUILD\}`/);
});

test('no other script of the page defines one of arrive.js\'s names', () => {
  const SITE = path.join(__dirname, '../src/dipcast/site');
  const names = s => new Set([...s.matchAll(/^(?:const|let|var|function|async function|class)\s+([A-Za-z_$][\w$]*)/gm)].map(m => m[1]));
  const mine = names(fs.readFileSync(path.join(SITE, 'arrive.js'), 'utf8'));
  assert.ok([...mine].every(n => /^(arrival|ARRIVAL)/.test(n)), [...mine].join(', '));
  const html = fs.readFileSync(path.join(SITE, 'index.html'), 'utf8');
  const others = [html, ...fs.readdirSync(SITE).filter(f => f.endsWith('.js') && !['arrive.js', 'sw.js'].includes(f)).map(f => fs.readFileSync(path.join(SITE, f), 'utf8'))];
  const page = names(others.join('\n'));
  assert.deepEqual([...mine].filter(n => page.has(n)), []);
});
