// Which official notices restrict swimming (28 Oct 2026): the reviewer marks each approval `restricts` true or false
// (src/dipcast/official_advice.py). Only true changes what the pages select: what Plan a swim, the best-day line,
// the shared plan and Nearby leave out, what the list puts first, and the outing's "neither looks good". Every
// notice still shows: its tag, the spot page's block, the map's ring and tooltip. A notice without the field (a
// spots.json from before it) changes no selection. node --test tests/site_notice_restricts.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const { join } = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const P = require('../src/dipcast/site/plan.js');
const ea = require('../src/dipcast/site/eatoday.js');

const SITE = join(__dirname, '../src/dipcast/site');
const PROFILE = 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945';
const AGAINST = { line: 'Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026', publisher: 'Environment Agency',
  link: PROFILE, since: '2026-06-19', checked: '2026-10-26', state: 'checked' };
const STATUS = { line: 'City of London: swimming status notice (members only this week) since 20 Oct 2026', publisher: 'City of London',
  link: 'https://www.cityoflondon.gov.uk/', since: '2026-10-20', checked: '2026-10-26', state: 'checked' };
const DATES = ['2026-10-28', '2026-10-29', '2026-10-30', '2026-10-31', '2026-11-01'];
L.setToday(DATES[0]);
const spot = (id, name, official = [], extra = {}) => ({ id, name, kind: 'lake', source: 'designated', lat: 51.15, lon: -0.79, area: 'Surrey',
  classification: { class: 'excellent', year: 2025, url: PROFILE }, upstream_summary: { overflows: 2 }, assumptions: { max_upstream_km: 15 },
  location: { mode: 'lake' }, now: { label: 'low', discharging_upstream: 0 }, contributors: [], official,
  days: DATES.map(date => ({ date, risk: 0.01, label: 'low', expected_spilling_overflows: 0, rain_48h_mm: 1, p_ecoli_gt900: 0.02, in_validated_season: false })), ...extra });
const restricting = () => spot('r', 'Restricted Pond', [{ ...AGAINST, restricts: true }]);
const neutral = () => spot('n', 'Status Pond', [{ ...STATUS, restricts: false }]);
const legacy = () => spot('l', 'Legacy Pond', [{ ...AGAINST }]);   // no field: a spots.json from before 28 Oct 2026
const plain = () => spot('p', 'Plain Pond');

test('only a notice marked restricts: true restricts; false, missing or none do not; any one of several does', () => {
  assert.equal(ea.eaTodayRestricts(restricting()), true);
  assert.equal(ea.eaTodayRestricts(neutral()), false);
  assert.equal(ea.eaTodayRestricts(legacy()), false);
  assert.equal(ea.eaTodayRestricts(plain()), false);
  assert.equal(ea.eaTodayRestricts(spot('m', 'Mixed', [{ ...STATUS, restricts: false }, { ...AGAINST, restricts: true }])), true);
  // A restricts: true on a notice the page would not show (an unknown state) does not count either.
  assert.equal(ea.eaTodayRestricts(spot('x', 'X', [{ ...AGAINST, restricts: true, state: 'approved' }])), false);
  assert.equal(ea.eaTodayRestricts(spot('s', 'S', [{ ...AGAINST, restricts: 'true' }])), false);   // only the boolean
});

test('every notice still shows: the compact tag and the spot page\'s block, restricting or not', () => {
  for (const s of [restricting(), neutral(), legacy()]) {
    assert.ok(ea.eaTodayBrief(s), s.name);
    assert.match(ea.eaTodayOfficial(s), /<h2 id="official-h">Official advice<\/h2>/);
    assert.equal(ea.eaTodayAdvice(s).length, 1);
  }
});

test('Plan a swim goes by restricts: a neutral or legacy notice keeps its place and counts as low', () => {
  assert.equal(P.planAdvised(restricting()), true);
  assert.equal(P.planAdvised(neutral()), false);
  assert.equal(P.planAdvised(legacy()), false);
  const plan = { day: DATES[0], within: 20, kind: 'all' };
  // The restricting spot is nearest, but goes last in the low group; the neutral one keeps its distance order.
  const r = restricting(), n = neutral(), p = plain();
  const got = P.planSpots([p, n, r], plan, s => ({ r: 1, n: 2, p: 3 })[s.id]);
  assert.deepEqual(got.groups[0].map(x => x.s.id), ['n', 'p', 'r']);
  const a = P.planAreas([r, n, p], plan, () => 1);
  assert.deepEqual([a[0].low, a[0].total], [2, 3]);   // the restricting spot is not counted low; the neutral one is
});

// The page's own functions, run beside levels.js, plan.js, experience.js and eatoday.js, as in the browser.
const pageSrc = (() => { const html = fs.readFileSync(join(SITE, 'index.html'), 'utf8');
  return html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n'); })();
function pageDefs(names) {
  return names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
    assert.ok(i >= 0, `no ${n} in index.html`);
    let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
    return pageSrc.slice(i, j).join('\n'); }).join('\n');
}
function page(names, extra = {}) {
  const ctx = vm.createContext({ ...extra });
  vm.runInContext(fs.readFileSync(join(SITE, 'experience.js'), 'utf8'), ctx);
  vm.runInContext(fs.readFileSync(join(SITE, 'levels.js'), 'utf8') + `\nsetToday("${DATES[0]}");`, ctx);
  vm.runInContext(fs.readFileSync(join(SITE, 'eatoday.js'), 'utf8'), ctx);
  vm.runInContext(pageDefs(names), ctx);
  return (f, ...a) => vm.runInContext(f, ctx)(...a);
}

test('the list puts first only a spot with a restricting notice, and says so only then', () => {
  const run = page(['ORDER_FIX', 'VIEW', 'mapLevel', 'listRank', 'listAdvised', 'riskOrder', 'riskFirstNote'].filter(n => n !== 'ORDER_FIX'),
    { VIEW: { day: null } });
  assert.equal(run('listAdvised', restricting()), true);
  assert.equal(run('listAdvised', neutral()), false);
  assert.equal(run('listAdvised', legacy()), false);
  assert.equal(run('riskFirstNote', [neutral(), legacy(), plain()]), '');
  assert.notEqual(run('riskFirstNote', [neutral(), restricting()]), '');
  const order = [plain(), neutral(), restricting()].sort((a, b) => run('riskOrder', a, b)).map(s => s.id);
  assert.equal(order[0], 'r');
  assert.deepEqual(order.slice(1), ['p', 'n']);   // the rest by name (Plain, Status): the neutral notice no different from none
});

test('display stays with every notice: the map rings and the tooltip names a neutral notice too', () => {
  const run = page(['VIEW', 'mapLevel', 'mapAdvised'], { VIEW: { day: null } });
  for (const s of [restricting(), neutral(), legacy()]) assert.equal(run('mapAdvised', s), true, s.name);
  assert.equal(run('mapAdvised', plain()), false);
});

test('the selection checks read eaTodayRestricts and the display checks eaTodayAdvice', () => {
  const src = pageSrc.join('\n');
  assert.match(src, /const out = typeof eaTodayRestricts === 'function' \? spots\.filter\(s => eaTodayRestricts\(s\)\) : \[\];/);   // best day
  assert.match(src, /const officialShown = s => typeof eaTodayRestricts === 'function' && eaTodayRestricts\(s\);/);   // Nearby
  assert.match(src, /const mapAdvised = s => typeof eaTodayAdvice === 'function' && eaTodayAdvice\(s\)\.length > 0;/);   // the ring
  const outing = fs.readFileSync(join(SITE, 'outing.js'), 'utf8');
  assert.match(outing, /advised: typeof eaTodayRestricts === 'function' && eaTodayRestricts\(s\),/);
});

test('the action line: "Follow" only for a restricting notice, "Read" for any other, the notice\'s own words shown either way', () => {
  assert.equal(ea.eaTodayAct(restricting()), 'Follow the official advice above first.');
  assert.equal(ea.eaTodayAct(neutral()), 'Read the official notice above first.');
  assert.equal(ea.eaTodayAct(legacy()), 'Read the official notice above first.');
  assert.equal(ea.eaTodayAct(plain()), '');
  // The spot page's block keeps each notice's own line, whichever action goes under the level.
  assert.match(ea.eaTodayOfficial(neutral()), /<p class="o-line">City of London: swimming status notice \(members only this week\) since 20 Oct 2026<\/p>/);
  // The embed takes the same line from eatoday.js.
  const Embed = require('../src/dipcast/site/embed.js');
  const DATA = { generated_at: '2026-10-28T08:00:00Z', spots: [] }, NOW = Date.parse('2026-10-28T08:30:00Z');
  const card = Embed.card(neutral(), DATA, NOW);
  assert.ok(card.includes('<p class="act">Read the official notice above first.</p>'), card);
  assert.ok(card.includes(ea.eaTodayBrief(neutral()).replace(/&/g, '&amp;')));
  assert.ok(Embed.card(restricting(), DATA, NOW).includes('<p class="act">Follow the official advice above first.</p>'));
  // The embed's tag line: "Follow it first" only for a restricting notice, as the spot page's action line.
  assert.ok(card.includes(`<p class="o-tag">Official: ${ea.eaTodayBrief(neutral())}. Read the official notice first; the level is SwimSignal's sewage forecast only.</p>`), card);
  assert.doesNotMatch(card, /Follow/);
  assert.ok(Embed.card(legacy(), DATA, NOW).includes('. Read the official notice first; the level'));
  assert.ok(Embed.card(restricting(), DATA, NOW).includes(`<p class="o-tag">Official: ${ea.eaTodayBrief(restricting())}. Follow it first; the level is SwimSignal's sewage forecast only.</p>`));
});

test('the sites view, the organisers\' page, the record and the comparison: "follow" only for a restricting notice', () => {
  const S = require('../src/dipcast/site/sites.js'), Org = require('../src/dipcast/site/organisers.js');
  const Rec = require('../src/dipcast/site/record.js'), X = require('../src/dipcast/site/experience.js');
  const DATA = { generated_at: '2026-10-28T08:00:00Z', spots: [] }, NOW = Date.parse('2026-10-28T08:30:00Z');
  const tail = "; the level is SwimSignal's sewage forecast only.</p>";
  for (const [s, word] of [[restricting(), 'Follow it first'], [neutral(), 'Read the official notice first'], [legacy(), 'Read the official notice first']]) {
    const b = ea.eaTodayBrief(s);
    assert.ok(S.row(s).includes(`<p class="o-tag">Official: ${b}. ${word}${tail}`), s.name);
    assert.ok(Org.forecast(s, DATES[1], DATA, NOW).includes(`<p class="o-tag"><b>Official advice:</b> ${b}. Not part of the level below; ${word.toLowerCase()}.</p>`), s.name);
    assert.ok(Rec.view(s, DATES[1], DATA, null, 'https://swimsignal.co.uk/', NOW).includes(`. Not part of the level below; ${word.toLowerCase()}.`), s.name);
    assert.ok(X.compareAdvice(s).startsWith(`Official: ${b}. ${word}.`), s.name);
  }
});
