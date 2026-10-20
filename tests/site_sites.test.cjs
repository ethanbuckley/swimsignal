// The sites view (sites.html, src/dipcast/site/sites.js): several spots on one page, each with its
// headline, its five days and the reason, from levels.js, so a row says what the spot's page says.
// The spots and the name are after the #; an unknown id is listed as not found, never fatal.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const S = require('../src/dipcast/site/sites.js');
const L = require('../src/dipcast/site/levels.js');
const Li = require('../src/dipcast/site/lists.js');

const SITE = path.join(__dirname, '..', 'src', 'dipcast', 'site');
const GEN = '2026-10-04T00:16:57+01:00', NOW = Date.parse(GEN) + 2 * 3600e3;
const day = (date, label, risk, e, extra = {}) => ({date, label, risk, expected_spilling_overflows: e, p_ecoli_gt900: 0.05, in_validated_season: false, rain_48h_mm: 6.2, ...extra});
const DAYS = ['2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08'];
const henley = {id: 'thames-henley', name: 'River Thames, Henley-on-Thames', kind: 'river', source: 'curated', location: {mode: 'river', watercourse: 'River Thames'},
  now: {label: 'low', discharging_upstream: 0}, upstream_summary: {overflows: 51},
  days: [day(DAYS[0], 'low', 0.002, 0.1), day(DAYS[1], 'low', 0.002, 0.1), day(DAYS[2], 'moderate', 0.2, 2.2), day(DAYS[3], 'low', 0.03, 0.4), day(DAYS[4], 'low', 0.02, 0.3)]};
const lazonby = {...henley, id: 'eden-lazonby', name: 'River Eden, Lazonby', location: {mode: 'river', watercourse: 'River Eden'},
  days: [day(DAYS[0], 'low', 0.05, 0.5), day(DAYS[1], 'high', 0.5, 6), day(DAYS[2], 'moderate', 0.3, 3), day(DAYS[3], 'moderate', 0.2, 2), day(DAYS[4], 'very high', 0.8, 9)]};
const lake = {id: 'buttermere', name: 'Buttermere', kind: 'lake', source: 'curated', location: {mode: 'lake'}, now: {label: null}, upstream_summary: {overflows: 0},
  days: DAYS.map((d, i) => ({date: d, risk: null, label: null, rain_48h_mm: i * 4}))};
const DATA = {generated_at: GEN, spots: [henley, lazonby, lake]};
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/\s+/g, ' ');

test('the address holds the spots, in order and each once, and the name; anything unreadable is dropped', () => {
  assert.deepEqual(S.fromHash('#spots=thames-henley,eden-lazonby,thames-henley&name=Club%20launches'), {ids: ['thames-henley', 'eden-lazonby'], name: 'Club launches'});
  assert.deepEqual(S.fromHash('#name=Weekend+swims&spots=a,b'), {ids: ['a', 'b'], name: 'Weekend swims'});   // either order, + as a space
  assert.deepEqual(S.fromHash('#spots=a,%E0%A4%A,b'), {ids: ['a', 'b'], name: ''});   // a broken escape is dropped, not fatal
  assert.deepEqual(S.fromHash(''), {ids: [], name: ''});
  assert.deepEqual(S.fromHash('#spots=' + Array.from({length: 300}, (_, i) => 's' + i).join(',')).ids.length, Li.LINK_SPOTS_MAX);
  assert.equal(S.fromHash('#spots=a&name=' + encodeURIComponent('x'.repeat(80))).name.length, Li.LIST_NAME_MAX);
  // lists.js makes the link the Saved page and the organisers' page copy, and it reads back the same.
  const h = Li.sitesHash('Club & "friends"', ['thames-henley', 'eden-lazonby']);
  assert.equal(h, '#spots=thames-henley,eden-lazonby&name=Club%20%26%20%22friends%22');
  assert.deepEqual(S.fromHash(h), {ids: ['thames-henley', 'eden-lazonby'], name: 'Club & "friends"'});
  assert.equal(Li.sitesHash('', ['a']), '#spots=a');
});

test('unknown or removed ids are listed as not found, and the rest still show', () => {
  const h = S.view(DATA, S.fromHash('#spots=gone-spot,thames-henley,<b>x</b>'), NOW, 'https://swimsignal.co.uk/');
  assert.ok(h.includes('Not found in this forecast: <b>gone-spot</b>, <b>&lt;b&gt;x&lt;/b&gt;</b>.'));
  assert.equal((h.match(/<li class="site">/g) || []).length, 1);
  const none = S.view(DATA, S.fromHash('#spots=gone-spot'), NOW, '');
  assert.ok(none.includes('Not found in this forecast') && !none.includes('<ol') && !none.includes('id="print"'));
  assert.ok(S.view(DATA, S.fromHash(''), NOW, '').includes('This link has no spots in it'));
});

test('a row gives the headline and the five days by levels.js, and the reason in one line', () => {
  L.setToday(DAYS[0]);
  const h = S.view(DATA, S.fromHash('#spots=eden-lazonby,thames-henley,buttermere'), NOW, '');
  // In the link's order.
  assert.ok(h.indexOf('River Eden, Lazonby') < h.indexOf('River Thames') && h.indexOf('River Thames') < h.indexOf('Buttermere'));
  assert.ok(h.includes(`<p class="s-head high">${L.headParts(lazonby)[0]}</p>`));
  assert.equal(L.headParts(lazonby)[0], 'High risk tomorrow');
  // Thursday is very high, worse than the headline's high: said first (11 Oct 2026), where it once said where the level fell.
  assert.equal(L.headParts(lazonby)[2], 'Very high risk on Thursday');
  assert.ok(h.includes('<p class="s-why">Sewage spills. Very high risk on Thursday.</p>'));
  // The five days: a bar a day in its level's colour, read out in words.
  const strip = h.split('River Eden, Lazonby')[1].split('</li>')[0];
  assert.deepEqual([...strip.matchAll(/<i class="([a-z]*)"/g)].map(m => m[1]), ['low', 'high', 'moderate', 'moderate', 'veryhigh']);
  assert.ok(strip.includes('aria-label="Pollution risk, next five days: Sun low risk, Mon high risk, Tue moderate risk, Wed moderate risk, Thu very high risk"'));
  // A low spot whose headline already names the later day: the reason is today's spills, not the headline again.
  assert.equal(L.headParts(henley)[0], 'Low risk now · Moderate risk on Tuesday');
  assert.ok(h.includes('<p class="s-why">Under one spill is expected from the 51 overflows upstream today.</p>'));
  // No overflow upstream: the plain level, the other risks, and the rain as bars.
  assert.ok(h.includes('<p class="s-head clear">No monitored overflow found upstream</p>') && h.includes(L.OTHER_RISKS));
  assert.ok(h.includes('class="week rain"') && h.includes('Rain in the 48 hours to midday: Sun 0 mm'));
  // Each row links its spot and a decision record for today and tomorrow.
  assert.ok(h.includes('href="spot/eden-lazonby/"') && h.includes('href="record.html#spot=eden-lazonby&amp;day=2026-10-05">tomorrow</a>'));
  // Every level word in a headline or reason carries "risk".
  for (const m of text(h).matchAll(/\b(low|moderate|high|very high)\b(?! risk)/gi)) assert.fail(`"${m[0]}" without "risk" in: ${text(h)}`);
});

// A briefing's sheet (scripts/briefing.py, sites_url) is for its session's day, and is kept and read on later
// days: on 20 Oct 2026 a Thursday briefing's sheet said "Very high risk tomorrow", meaning Wednesday.
test('a link with a day gives each spot\'s level that day, named by its date, as the decision record does', () => {
  assert.deepEqual(S.fromHash('#spots=a&day=2026-10-06'), {ids: ['a'], name: '', day: '2026-10-06'});
  assert.deepEqual(S.fromHash('#spots=a&day=tomorrow'), {ids: ['a'], name: ''});   // not a date: no day
  const poor = {...henley, id: 'bw-uke4100-08901', name: 'Wharfe at Cromwheel, Ilkley', source: 'designated', classification: {class: 'Poor', url: ''}};
  const data = {...DATA, spots: [...DATA.spots, poor]};
  const h = S.view(data, S.fromHash(`#spots=eden-lazonby,thames-henley,buttermere,bw-uke4100-08901&day=${DAYS[2]}`), NOW, '');
  const rows = h.split('<li ').slice(1);
  // The level and its cause are dayHeadline's, the day by its date, then that day's overflows as on the record.
  assert.equal(L.dayHeadline(lazonby, DAYS[2]), 'Moderate risk: sewage spills');
  assert.ok(rows[0].includes('<p class="s-head moderate">Moderate risk on Tue 6 Oct</p><p class="s-why">Sewage spills. About 3 of the 51 overflows upstream are expected to spill.</p>'));
  assert.ok(rows[1].includes('<p class="s-head moderate">Moderate risk on Tue 6 Oct</p>'));
  assert.ok(rows[2].includes('<p class="s-head clear">No monitored overflow found upstream</p>'));
  assert.ok(rows[3].includes('<p class="s-head high">High risk on Tue 6 Oct</p><p class="s-why">Rated poor. About 2 of the 51 overflows upstream are expected to spill. EA advice on the day not checked: see the EA&#39;s page.</p>'));
  // Each row says what it drew, for briefing.py to check against alerts.json.
  assert.ok(rows[0].startsWith(`class="site" data-spot="eden-lazonby" data-day="${DAYS[2]}" data-level="moderate">`));
  assert.ok(rows[3].includes('data-level="high"') && L.dayLevel(poor, DAYS[2]) === 'high');
  // That day's letter is marked under the bars, not today's; the record link is for that day.
  assert.deepEqual([...rows[0].matchAll(/<span class="wk( [a-z]+)?">/g)].map(m => m[1] || ''), ['', '', ' on', '', '']);
  assert.ok(rows[0].includes(`href="record.html#spot=eden-lazonby&amp;day=${DAYS[2]}">Tue 6 Oct</a>`));
  // No row says "today" or "tomorrow", and every level word carries "risk".
  const said = text(h.slice(h.indexOf('<ol')));
  assert.ok(!/\b(today|tomorrow)\b/i.test(said), said);
  for (const m of said.matchAll(/\b(low|moderate|high|very high)\b(?! risk)/gi)) assert.fail(`"${m[0]}" without "risk" in: ${said}`);
  // A day outside the forecast's five days: the usual rows, and a line saying so.
  const late = S.view(DATA, S.fromHash('#spots=eden-lazonby&day=2026-10-20'), NOW, '');
  assert.ok(late.includes(`<p class="s-head high">${L.headParts(lazonby)[0]}</p>`) && !late.includes('data-day'));
  assert.ok(late.includes("Tue 20 Oct is not in this forecast's five days, so the levels above are the usual ones, from today."));
  // Without a day the page is as it was, and the next view without one forgets the last day.
  assert.ok(!S.view(DATA, S.fromHash('#spots=eden-lazonby'), NOW, '').includes('data-day'));
});

test('the issue time is said once, with the app\'s stale notice after 8 hours, and nothing says safe', () => {
  const ids = S.fromHash('#spots=eden-lazonby,thames-henley,buttermere');
  const h = S.view(DATA, ids, NOW, '');
  assert.equal((h.match(/Forecast issued/g) || []).length, 1);
  assert.ok(h.includes('Forecast issued Sun 4 Oct, 00:16 (2 h ago).') && !h.includes('Stale'));
  assert.ok(S.view(DATA, ids, Date.parse(GEN) + 9 * 3600e3, '').includes('<b>Stale.</b> This forecast is 9 h old'));
  assert.ok(h.includes('A forecast, not a water test: check the signs at the water before you swim.'));
  assert.ok(!/\bsafe\b/i.test(text(h)) && !/\bclean\b/i.test(text(h)));
});

test('the page, its links from the Saved page and the organisers\' page, and its print layout', () => {
  const page = fs.readFileSync(path.join(SITE, 'sites.html'), 'utf8');
  assert.ok(page.includes('<title>Sites view · SwimSignal</title>') && page.includes('<header class="top">') && page.includes('class="site-foot"'));
  assert.ok(page.includes('@page { size:A4 portrait') && page.includes('break-inside:avoid'));
  assert.ok(/<script src="levels\.js"><\/script>\s*<script src="lists\.js"><\/script>\s*<script src="organisers\.js"><\/script>\s*<script src="sites\.js"><\/script>/.test(page));
  const org = fs.readFileSync(path.join(SITE, 'organisers.html'), 'utf8');
  assert.ok(org.includes('id="sites-maker"') && org.includes('Make a sites link') && org.includes('<script src="sites.js"></script>'));
  const app = fs.readFileSync(path.join(SITE, 'index.html'), 'utf8');
  assert.ok(app.includes("new URL('sites.html', ROOT).href + sitesHash(l.name") && app.includes('id="sites-link">Make a sites link</button>'));
});
