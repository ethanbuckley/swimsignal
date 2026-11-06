// A town typed in the list's search lists the spots near it, under the spots named for it (plan.js, townsNamed,
// spotsNear, nearSaid, milesFrom; index.html, offerOnMap). Until 6 Nov 2026 "Ambleside" listed one spot, Windermere
// at Waterhead; Rydal Water, Loughrigg Tarn, Grasmere and Elter Water came only after tapping "From Ambleside".
//   node --test tests/site_town_search.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const { join } = require('node:path');
const P = require('../src/dipcast/site/plan.js');

const SITE = join(__dirname, '../src/dipcast/site');
const PAGE = fs.readFileSync(join(SITE, 'index.html'), 'utf8');
// Straight-line miles, as the page's km() / MILE_KM.
const miles = (a, b) => { const r = Math.PI / 180, dLat = (b[0] - a[0]) * r, dLon = (b[1] - a[1]) * r;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLon / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(h)) / P.MILE_KM; };

// In the file's order, biggest first, as data/places.json.
const index = P.placeIndex({ places: [['Henley-in-Arden', 52.29, -1.78], ['Henley-on-Thames', 51.54, -0.9], ['Keswick', 54.6, -3.13],
  ['Ambleside', 54.43, -2.96], ['Amble', 55.33, -1.58], ['Thames Ditton', 51.39, -0.33], ['Keswick, South Norfolk', 52.6, 1.26], ['Henley', 52.1, 1.15]] });
const named = t => P.townsNamed(P.placeMatches(index, t, 2), t).map(p => p.name);

test('a town is the place offered that what is typed names in full, never part of a word', () => {
  assert.deepEqual(named('Ambleside'), ['Ambleside']);
  assert.deepEqual(named(' ambleside '), ['Ambleside']);                        // case and spaces do not count
  assert.deepEqual(named('Ambles'), []);                                        // still typing
  assert.deepEqual(named('Amble'), ['Amble']);                                  // a town of its own; Ambleside is not "Amble ..."
  assert.deepEqual(named('Keswick'), ['Keswick', 'Keswick, South Norfolk']);    // two of that name: both, as the plan offers both
  assert.deepEqual(named('Henley'), ['Henley-in-Arden', 'Henley-on-Thames']);   // the first word of each name
  assert.deepEqual(named('Thames'), ['Thames Ditton']);
  assert.deepEqual(named(''), []);
  assert.deepEqual(P.townsNamed([], 'Ambleside'), []);                          // the list of places did not come
});

// The live positions of 6 Nov 2026 (spots-lite.json, places.json).
const AMBLESIDE = { name: 'Ambleside', lat: 54.43, lon: -2.96 };
const LAKES = [['osm-windermere-waterhead', 'Windermere, Waterhead, Ambleside', 54.41897, -2.96235], ['rydal-water', 'Rydal Water', 54.447, -2.989],
  ['loughrigg-tarn', 'Loughrigg Tarn', 54.4306, -3.0117], ['grasmere', 'Grasmere (lake)', 54.45, -3.02], ['elter-water', 'Elter Water', 54.43, -3.033],
  ['bw-ukd1203-45650', 'Windermere, Millerground Landing', 54.38071, -2.92254], ['bw-ukd1203-45675', 'Windermere, Rayrigg Meadow', 54.37816, -2.9225],
  ['bw-ukd1101-45800', 'Derwent Water at Crow Park', 54.59499, -3.14218]].map(([id, name, lat, lon]) => ({ id, name, kind: 'lake', lat, lon }));

test('the spots near a town: within 10 miles, nearest first, five at most, leaving out those already listed', () => {
  const n = P.spotsNear(LAKES, AMBLESIDE, miles, new Set(['osm-windermere-waterhead']));
  assert.deepEqual(n.rows.map(x => x.s.name), ['Rydal Water', 'Loughrigg Tarn', 'Grasmere (lake)', 'Elter Water', 'Windermere, Millerground Landing']);
  assert.deepEqual(n.rows.map(x => P.milesFrom(x.miles, 'Ambleside')),
    ['1.7 miles from Ambleside', '2.1 miles from Ambleside', '2.8 miles from Ambleside', '2.9 miles from Ambleside', '3.7 miles from Ambleside']);
  assert.equal(n.total, 6);                                                     // Rayrigg Meadow at 3.9 is within reach; Crow Park at 13.5 is not
  assert.equal(P.nearSaid(n.rows.length, n.total), 'the 5 nearest of 6 within 10 miles');
  // Nothing skipped: the spot named for the town is nearest.
  assert.equal(P.spotsNear(LAKES, AMBLESIDE, miles).rows[0].s.name, 'Windermere, Waterhead, Ambleside');
  // A town with nothing in reach has no group.
  assert.deepEqual(P.spotsNear(LAKES, { name: 'Amble', lat: 55.33, lon: -1.58 }, miles), { rows: [], total: 0 });
});

test('the line beside the heading, and the distance in the miles wording of the rest of the site', () => {
  assert.equal(P.nearSaid(1, 1), '1 spot within 10 miles');
  assert.equal(P.nearSaid(3, 3), '3 spots within 10 miles, nearest first');
  assert.equal(P.nearSaid(5, 12), 'the 5 nearest of 12 within 10 miles');
  assert.equal(P.milesFrom(0.4, 'Keswick'), 'under a mile from Keswick');
  assert.equal(P.milesFrom(1, 'Settle'), '1 mile from Settle');
  assert.equal(P.milesFrom(12.4, 'Ambleside'), '12 miles from Ambleside');
  assert.equal(P.milesAway(1.74), '1.7 miles away');                            // unchanged for the list's own distances
});

// ------------------------------------------------------------------------------ the rows are the list's rows
const pageSrc = PAGE.slice(PAGE.indexOf('<script>\n') + 9, PAGE.lastIndexOf('</script>')).split('\n');
function pageDefs(names) {
  return names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
    assert.ok(i >= 0, `no ${n} in index.html`);
    let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
    return pageSrc.slice(i, j).join('\n'); }).join('\n');
}
const DATES = ['2026-11-06', '2026-11-07', '2026-11-08', '2026-11-09', '2026-11-10'];
function rowContext() {
  const ctx = vm.createContext({ ROOT: { pathname: '/' } });
  vm.runInContext(fs.readFileSync(join(SITE, 'experience.js'), 'utf8'), ctx);
  vm.runInContext(fs.readFileSync(join(SITE, 'levels.js'), 'utf8') + `\nsetToday("${DATES[0]}");`, ctx);
  vm.runInContext(fs.readFileSync(join(SITE, 'plan.js'), 'utf8'), ctx);
  vm.runInContext(pageDefs(['esc', 'fmt', 'cls', 'dateLabel', 'glyph', 'ICON', 'tone', 'colour', 'headTone', 'initial', 'VIEW', 'km', 'dist', 'away',
    'PAGE_ID', 'spotPath', 'week', 'rainMeta', 'mapLevel', 'listHeadline', 'openDay', 'listPath', 'headNote', 'spotItem', 'spotRow']), ctx);
  return ctx;
}
const days = (label, extra = {}) => DATES.map(date => ({ date, risk: label === 'low' ? 0.01 : 0.5, label, rain_48h_mm: 1, ...extra }));
const rydal = { id: 'rydal-water', name: 'Rydal Water', kind: 'lake', source: 'curated', upstream_summary: { overflows: 3 }, location: { mode: 'lake' },
  now: { label: 'low', discharging_upstream: 0 }, contributors: [], assumptions: { max_upstream_km: 60 }, days: days('low') };
const crowPark = { ...rydal, id: 'bw-ukd1101-45800', name: 'Derwent Water at Crow Park', source: 'designated', classification: { class: 'poor', year: 2025 } };
const brothers = { id: 'brothers-water', name: 'Brothers Water', kind: 'lake', source: 'curated', upstream_summary: { overflows: 0 }, location: { mode: 'lake' },
  now: { label: 'unknown', discharging_upstream: 0 }, contributors: [], assumptions: { max_upstream_km: 60 }, days: days('low') };
const loughrigg = { id: 'loughrigg-tarn', name: 'Loughrigg Tarn', kind: 'lake', source: 'curated', days: [], contributors: [], assumptions: { max_upstream_km: 60 },
  error: 'An isolated lake with no river connection in the network: storm overflows cannot reach it by water, so the forecast has nothing to say about it.' };

test('a spot near the town is the list\'s own row, its level and words unchanged, with the distance from the town', () => {
  const ctx = rowContext(), run = (f, ...a) => vm.runInContext(f, ctx)(...a);
  for (const s of [rydal, crowPark, brothers, loughrigg]) {
    const near = run('spotRow', s, run('milesFrom', 1.7, 'Ambleside')), listed = run('spotItem', s);
    assert.ok(near.includes(' · 1.7 miles from Ambleside'), near);
    assert.equal(near.replace(' · 1.7 miles from Ambleside', ''), listed, s.name);   // nothing else differs
  }
  const head = s => (run('spotRow', s, '2 miles from Ambleside').match(/<span class="hl ([\w-]+)">([^<]*)<\/span>/) || []).slice(1);
  assert.deepEqual(head(rydal), ['low', 'Low risk for the next five days']);
  assert.equal(head(crowPark)[0], 'high');                                      // rated poor: high, as on the list
  // No monitored overflow upstream is never said as low risk, in words or in colour.
  for (const s of [brothers, loughrigg]) {
    const [tone, words] = head(s);
    assert.equal(tone, 'clear', s.name);
    assert.doesNotMatch(words, /low risk/i, s.name);
  }
  assert.equal(head(brothers)[1], 'No monitored overflow found upstream');
});

test('the page lists the town\'s spots first among the offers, with the list\'s filters, and opens them as list rows do', () => {
  const offers = PAGE.slice(PAGE.indexOf('async function offerOnMap('), PAGE.indexOf('const WATER_ZOOM'));
  // Each file on its own: the places still come when the rivers do not (the smoke fixture has no rivers file).
  assert.match(offers, /Promise\.allSettled\(\[loadWaters\(\)/);
  assert.match(offers, /for \(const town of townsNamed\(places, t\)\)/);
  assert.match(offers, /spotsNear\(DATA\.spots\.filter\(listKept\), town, \(a, b\) => km\(a, b\) \/ MILE_KM, listed\)/);
  assert.match(offers, /const listed = new Set\(LISTED\.map\(s => s\.id\)\)/);       // never a spot twice
  assert.match(offers, /<li class="area-head"><h3>Near \$\{esc\(n\.town\.name\)\} <span>· \$\{nearSaid\(n\.rows\.length, n\.total\)\}<\/span><\/h3><\/li>/);
  assert.match(offers, /spotRow\(x\.s, milesFrom\(x\.miles, esc\(n\.town\.name\)\)\)/);
  assert.match(offers, /box\.innerHTML = nearRows \+ plans \+/);
  assert.match(offers, /bindItems\(box\);/);
  // The count and the tally take the town's spots in.
  assert.match(offers, /overview\(all\)\.replace/);
  assert.match(offers, /Showing \$\{all\.length\} of \$\{DATA\.spots\.length\} spots: \$\{LISTED\.length\} matching the search, \$\{more\.length\} near /);
  // The name matches are drawn as before, and remembered for the offers.
  const draw = PAGE.slice(PAGE.indexOf('function drawSpots('), PAGE.indexOf('// ------------------------------------------------------------------------------ the Saved page'));
  assert.match(draw, /const keep = s => found\(s\) && listKept\(s\);/);
  assert.match(draw, /LISTED = items;/);
  assert.match(PAGE, /function spotItem\(s\) \{ const d = dist\(s\); return spotRow\(s, d !== null \? away\(d\) : null\); \}/);
});
