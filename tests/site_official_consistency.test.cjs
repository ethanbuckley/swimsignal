// A known official advisory is never shown as a clean "Low" (26 Oct 2026): every surface that shows a spot's
// level, or exports it, carries the compact form of its advice (eatoday.js, eaTodayBrief) or a scoped label,
// and the level itself never changes. Plan a swim's groups, order, suggestions and shared plan (plan.js and
// index.html), the list's counts and the map's tooltips (index.html), the comparison's heads, the embed
// (embed.js), the sites view and briefing (sites.js) and the organisers' page (organisers.js). Fixture items
// only, with the approved Frensham entry's words. node --test tests/site_official_consistency.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const { join } = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const P = require('../src/dipcast/site/plan.js');
const ea = require('../src/dipcast/site/eatoday.js');
const Embed = require('../src/dipcast/site/embed.js');
const S = require('../src/dipcast/site/sites.js');
const O = require('../src/dipcast/site/organisers.js');

const SITE = join(__dirname, '../src/dipcast/site');
const PROFILE = 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945';
const LINE = 'Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026';
const item = (extra = {}) => ({ line: LINE, publisher: 'Environment Agency', link: PROFILE, since: '2026-06-19', checked: '2026-10-26', state: 'checked', ...extra });
const BRIEF = 'EA advice against bathing (harmful algae) · since 19 Jun · checked 26 Oct';
const DATES = ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30'];
const spot = (id, name, extra = {}) => ({ id, name, kind: 'lake', source: 'designated', lat: 51.15, lon: -0.79, area: 'Surrey',
  classification: { class: 'excellent', year: 2025, url: PROFILE }, upstream_summary: { overflows: 2 }, assumptions: { max_upstream_km: 15 },
  location: { mode: 'lake' }, now: { label: 'low', discharging_upstream: 0 }, contributors: [],
  days: DATES.map(date => ({ date, risk: 0.01, label: 'low', expected_spilling_overflows: 0, rain_48h_mm: 1, p_ecoli_gt900: 0.02, in_validated_season: false })), ...extra });
const frensham = (extra = {}) => spot('bw-ukj2310-11945', 'Frensham Great Pond', { official: [item()], ...extra });
const other = (extra = {}) => spot('bw-ukj2310-00001', 'Other Pond', { lat: 51.2, ...extra });
L.setToday(DATES[0]);

test('Plan a swim: a spot with advice keeps its level and group, goes last in it, and is not counted as low where the plan suggests', () => {
  const f = frensham(), o = other();
  assert.equal(P.planAdvised(f), true);
  assert.equal(P.planAdvised(o), false);
  assert.equal(P.planAdvised(frensham({ official: [item({ state: 'approved' })] })), false);   // a state no page shows
  const plan = { day: DATES[0], within: 20, kind: 'all' };
  // Frensham is nearer, but goes after the other low spot; both stay in the low group at "low".
  const r = P.planSpots([o, f], plan, s => s === f ? 1 : 5);
  assert.deepEqual(r.groups[0].map(x => [x.s.id, x.level]), [[o.id, 'low'], [f.id, 'low']]);
  // The areas a plan suggests count it among the spots, not among those at low risk.
  const a = P.planAreas([o, f], plan, () => 1);
  assert.deepEqual([a[0].low, a[0].total], [1, 2]);
  assert.deepEqual(P.planAreas([f], plan, () => 1), []);   // its only spot under advice: not suggested for low risk
});

test('Plan a swim: a better day is never found by counting a spot under advice as low', () => {
  const high = d => ({ ...d, label: 'high', risk: 0.5 });
  // Two plain spots go from high to low tomorrow; with two spots under advice low both days, "two more" still holds.
  const movers = [1, 2].map(i => other({ id: `m${i}`, days: DATES.map((date, j) => j === 0 ? high(other().days[0]) : { ...other().days[j], date }) }));
  const steady = [3, 4].map(i => frensham({ id: `f${i}` }));
  const b = P.betterDay([...movers, ...steady], DATES[0], DATES);
  assert.ok(b, 'a better day');
  assert.deepEqual([b.low, b.was], [2, 0]);   // the advised spots are in neither count
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
function pageContext(names, extra = {}, withAdvice = true) {
  const ctx = vm.createContext({ ...extra });
  vm.runInContext(fs.readFileSync(join(SITE, 'experience.js'), 'utf8'), ctx);
  vm.runInContext(fs.readFileSync(join(SITE, 'levels.js'), 'utf8') + `\nsetToday("${DATES[0]}");`, ctx);
  if (withAdvice) vm.runInContext(fs.readFileSync(join(SITE, 'eatoday.js'), 'utf8'), ctx);
  vm.runInContext(pageDefs(names), ctx);
  return ctx;
}
const BASE = ['esc', 'VIEW', 'issued', 'mapLevel', 'mapWhen', 'listHeadline', 'markerTip', 'overview'];
const EXTRA = { DATA: { generated_at: '2026-10-26T20:00:00Z', spots: [] } };

test('the map tooltip: the level, then the advice on a line of its own; none without advice', () => {
  const ctx = pageContext(BASE, EXTRA), run = (f, ...a) => vm.runInContext(f, ctx)(...a);
  const tip = run('markerTip', frensham());
  assert.ok(tip.startsWith('Frensham Great Pond: Low risk'), tip);
  assert.ok(tip.endsWith(`<br>${BRIEF}`), tip);
  assert.doesNotMatch(run('markerTip', other()), /<br>|advice/);
  const bare = pageContext(BASE, EXTRA, false);
  assert.doesNotMatch(vm.runInContext('markerTip', bare)(frensham()), /advice/);
});

test('the list\'s counts stay the sewage forecast\'s, are named so, and count the spots with advice', () => {
  const ctx = pageContext(BASE, EXTRA), run = (f, ...a) => vm.runInContext(f, ctx)(...a);
  const with_ = run('overview', [frensham(), other()]), without = run('overview', [other(), other({ id: 'x' })]);
  assert.match(with_, /Sewage pollution risk: 2 low · 0 moderate · 0 high or very high/);
  assert.match(with_, / 1 with official advice against swimming: follow it first\.$/);
  assert.match(without, /· Pollution risk: 2 low/);
  assert.doesNotMatch(without, /advice/);
});

test('Plan a swim: the group line says how many have advice, and that it comes first', () => {
  const ctx = pageContext(['planAdviceSub']), sub = vm.runInContext('planAdviceSub', ctx);
  assert.equal(sub(0, 3), '');
  assert.equal(sub(1, 3), '1 of these has official advice against swimming, under its level. Follow it first: the level is SwimSignal\'s sewage forecast only.');
  assert.equal(sub(1, 1), 'This spot has official advice against swimming, under its level. Follow it first: the level is SwimSignal\'s sewage forecast only.');
  assert.match(sub(2, 2), /^All 2 have official advice against swimming, under their level\./);
  // The planner's heading for the low group is scoped when it holds one, and the shared plan leaves it out.
  const src = pageSrc.join('\n');
  assert.match(src, /adv\[0\] \? `Low risk from sewage spills \$\{on\}` : `Low risk \$\{on\}`/);
  assert.match(src, /const out = open\.filter\(o => planAdvised\(o\.s\)\); open = open\.filter\(o => !planAdvised\(o\.s\)\);/);
  assert.match(src, /left out: official advice against swimming\./);
  // The comparison's heads carry the tag under each name.
  assert.match(src, /<span class="k">\$\{esc\(meta\(s\)\)\}<\/span>` : ''\}\$\{typeof eaTodayTag === 'function' \? eaTodayTag\(s\) : ''\}<\/th>/);
});

const DATA = { generated_at: '2026-10-26T20:00:00Z', spots: [frensham(), other()] };
const NOW = Date.parse('2026-10-26T20:30:00Z');

test('the embed and the live sign: the advice under the level, apart from it', () => {
  const card = Embed.card(frensham(), DATA, NOW);
  assert.ok(card.includes(`<p class="o-tag">Official: ${BRIEF}. Follow it first; the level is SwimSignal's sewage forecast only.</p>`), card);
  assert.ok(card.indexOf('class="hl low"') < card.indexOf('o-tag'));
  assert.ok(card.indexOf('o-tag') < card.indexOf('class="act"'));
  assert.doesNotMatch(Embed.card(other(), DATA, NOW), /o-tag|Official/);
  // The level and the five days are the same with or without it; only "could not be checked" goes, as the
  // notice says when it was checked.
  const bare = Embed.card(frensham({ official: [] }), DATA, NOW), part = (h, re) => (h.match(re) || [''])[0];
  for (const re of [/<p class="hl[^]*?<\/p>/, /<ul class="drows"[^]*?<\/ul>/]) assert.equal(part(card, re), part(bare, re));
  assert.match(bare, /could not be checked/);
  assert.doesNotMatch(card, /could not be checked/);
  const html = fs.readFileSync(join(SITE, 'embed.html'), 'utf8');
  assert.match(html, /<script src="levels\.js"><\/script>\s*<script src="eatoday\.js"><\/script>\s*<script src="embed\.js"><\/script>/);
  assert.match(html, /"next days" "official days"/);
});

test('the sites view and its briefing: the advice under the headline, on a day too', () => {
  const row = S.row(frensham());
  const tag = `<p class="o-tag">Official: ${BRIEF}. Follow it first; the level is SwimSignal's sewage forecast only.</p>`;
  assert.ok(row.includes(tag), row);
  assert.match(row.slice(0, row.indexOf(tag)), /<p class="s-head low">Low risk[^<]*<\/p>$/);
  assert.doesNotMatch(S.row(other()), /o-tag/);
  const page = S.view(DATA, { ids: [frensham().id], day: DATES[2] }, NOW);
  assert.match(page, /data-level="low"/);   // the briefing's check reads the level, which is unchanged
  assert.ok(page.includes(BRIEF));
});

test('the organisers\' page: the advice above the day\'s level, inside the forecast and beyond it', () => {
  for (const iso of [DATES[1], '2026-11-05']) {
    const h = O.forecast(frensham(), iso, DATA, NOW);
    assert.ok(h.includes(`<p class="o-tag"><b>Official advice:</b> ${BRIEF}. Not part of the level below; follow it first.</p>`), iso);
    assert.doesNotMatch(O.forecast(other(), iso, DATA, NOW), /o-tag/);
  }
});

test('alerts.json: the level and rank unchanged; what to do is the notice, checked or stale; none without advice', () => {
  const { execFileSync } = require('node:child_process'), os = require('node:os');
  const dir = fs.mkdtempSync(join(os.tmpdir(), 'alerts-')), src = join(dir, 'spots.json'), out = join(dir, 'alerts.json');
  const stale = frensham({ id: 'stale', official: [item({ state: 'unverified', checked: '2026-10-19' })] });
  fs.writeFileSync(src, JSON.stringify({ generated_at: '2026-10-26T20:00:00+00:00', spots: [frensham(), stale, other()] }));
  execFileSync(process.execPath, [join(__dirname, '../scripts/alerts.js'), src, out, 'https://example.org/'], { env: { ...process.env, TZ: 'Europe/London' } });
  const a = JSON.parse(fs.readFileSync(out, 'utf8')), f = a.spots[frensham().id], s = a.spots.stale, o = a.spots[other().id];
  assert.equal(f.level, o.level);
  assert.equal(f.rank, o.rank);
  assert.equal(f.headline, o.headline);
  assert.equal(f.official, BRIEF);
  assert.equal(f.action, `Official: ${BRIEF}. Follow it first; the level is SwimSignal's sewage forecast only.`);
  assert.match(s.action, /^Official: EA advice against bathing \(harmful algae\) · since 19 Jun · not re-checked since 19 Oct\. Follow it first/);
  assert.match(o.action, /^Usual care/);
  assert.equal(o.official, undefined);
  // Each day's action is the notice too, for alerts about a date (push/src/dates.js).
  for (const d of f.days.filter(Boolean)) assert.equal(a.words[d[2]], f.action);
  for (const d of o.days.filter(Boolean)) assert.match(a.words[d[2]], /^Usual care/);
});

test('a list the user picked keeps every spot, with its notice; only Share this plan leaves one out, and says so', () => {
  const Li = require('../src/dipcast/site/lists.js');
  const hash = Li.shareHash('Surrey', [frensham().id, other().id]);
  assert.deepEqual(Li.readShared(hash).spots, [frensham().id, other().id]);
  const src = pageSrc.join('\n');
  // Saved's Share this list and its sites link take the list's spots as they are.
  assert.match(src, /bindShareLink\(b, \$\('share-list-msg'\), new URL\(savedPath\(\), location\.origin\)\.href \+ shareHash\(l\.name, spots\.map\(s => s\.id\)\)/);
  assert.match(src, /bindShareLink\(sl, \$\('sites-link-msg'\), sitesURL\(l, spots\)/);
  // The shared list's view draws each spot as a Saved card, which carries the tag.
  assert.match(src, /spots\.map\(s => savedCard\(s, false, sh\.day, true\)\)/);
  const ctx = pageContext(['esc', 'fmt', 'cls', 'dateLabel', 'glyph', 'ICON', 'tone', 'colour', 'headTone', 'initial', 'VIEW', 'km', 'dist', 'away',
    'PAGE_ID', 'spotPath', 'BOOKMARK', 'untested', 'week', 'rainMeta', 'rainSaid', 'answerParts', 'savedCard'], PAGE_EXTRA);
  assert.ok(vm.runInContext('savedCard', ctx)(frensham(), false, DATES[1], true).includes(`<p class="o-tag">${BRIEF}</p>`));
  // Only the plan's share filters, and its tile names the spot left out.
  const share = src.slice(src.indexOf('function planShare('), src.indexOf('function bindPlan('));
  assert.equal((share.match(/filter\(o => !?planAdvised\(o\.s\)\)/g) || []).length, 2);
  assert.match(src, /left out: official advice against swimming\./);
});

// Second round (integrated review, 26 Oct): Nearby, the comparison's EA row, Saved's grid and best day, the
// action line, and the Not known row.
const X = require('../src/dipcast/site/experience.js');
const PAGE_EXTRA = { ROOT: { pathname: '/' }, DATA: { generated_at: '2026-10-26T20:00:00Z', spots: [] }, PLAN: { day: DATES[0] },
  planWhy: () => '', planEvidence: () => '', milesAway: m => `${m} miles away`, MILE_KM: 1.609344 };

test('"Lower risk nearby" never offers a spot with official advice; a plain "Nearby" tags it', () => {
  const high = d => ({ ...d, label: 'high', risk: 0.5 });
  const here = other({ id: 'here', name: 'River Wey', kind: 'river', days: other().days.map(high), now: { label: 'high', discharging_upstream: 1, monitored_upstream: 2 } });
  const names = ['esc', 'tone', 'km', 'away', 'PAGE_ID', 'spotPath', 'glyph', 'ICON', 'headNote', 'NEAR_KM', 'notHigherAnyDay', 'allFiveDays', 'ratedBetter',
    'joined', 'otherWater', 'unread', 'fewerUnread', 'nearWhy', 'otherAsWell', 'nearby'];
  const f = frensham(), o = other({ id: 'calm', name: 'Calm Pond' });
  const ctx = pageContext(names, { ...PAGE_EXTRA, DATA: { ...PAGE_EXTRA.DATA, spots: [here, f, o] } });
  vm.runInContext('var DAY = null;', ctx);
  const h = vm.runInContext('nearby', ctx)(here);
  assert.match(h, /Lower risk nearby/);
  assert.ok(h.includes('data-id="calm"'), h);
  assert.ok(!h.includes(`data-id="${f.id}"`), 'a spot under advice is not a lower-risk alternative');
  // At a low spot the list is plain "Nearby": Frensham may be in it, with its tag.
  const plain = vm.runInContext('nearby', ctx)(o);
  assert.match(plain, />Nearby</);
  assert.ok(plain.includes(`<span class="o-tag">${BRIEF}</span>`), plain);
});

test('the comparison\'s EA row gives the reviewed notice, not "could not be checked"', () => {
  const said = X.compareAdvice(frensham());
  assert.ok(said.startsWith(`Official: ${BRIEF}. Follow it first.`), said);
  assert.match(said, /<a href="https:\/\/environment\.data\.gov\.uk\/bwq\/profiles\/profile\.html\?site=ukj2310-11945">The Environment Agency's page<\/a> has the latest\./);
  assert.doesNotMatch(said, /could not be checked/);
  assert.match(X.compareAdvice(frensham({ official: [] })), /could not be checked/);
  const row = X.compareRows(frensham(), DATES[0], DATA.generated_at).find(([l]) => l === "Today's EA advice");
  assert.equal(row[1], said);
});

test('Saved: the grid tags the spot, and the best day leaves it out of the count and says so', () => {
  const ctx = pageContext(['esc', 'fmt', 'cls', 'dateLabel', 'tone', 'PAGE_ID', 'spotPath', 'VIEW', 'fiveDays', 'savedGrid', 'bestDayNote'], PAGE_EXTRA);
  const grid = vm.runInContext('savedGrid', ctx)([frensham(), other()]);
  assert.ok(grid.includes(`>Frensham Great Pond</a><span class="o-tag">${BRIEF}</span></span>`), grid);
  assert.equal((grid.match(/o-tag/g) || []).length, 1);
  const note = vm.runInContext('bestDayNote', ctx)([frensham(), other(), other({ id: 'calm', name: 'Calm Pond' })], true);
  assert.match(note, /when 2 of your 2 spots are at low risk \(Frensham Great Pond has official advice against swimming, so is not counted\)\./);
  assert.doesNotMatch(vm.runInContext('bestDayNote', ctx)([other(), other({ id: 'calm', name: 'Calm Pond' })], true), /official/);
});

test('with a notice shown, the level\'s action line points to it, on the spot page and the embed; without one, unchanged', () => {
  assert.equal(ea.eaTodayAct(frensham()), 'Follow the official advice above first.');
  assert.equal(ea.eaTodayAct(other()), '');
  const ctx = pageContext(['esc', 'fmt', 'cls', 'dateLabel', 'glyph', 'ICON', 'tone', 'colour', 'headTone', 'answerParts'], PAGE_EXTRA);
  const parts = vm.runInContext('answerParts', ctx);
  assert.equal(parts(frensham()).act, 'Follow the official advice above first.');
  assert.match(parts(other()).act, /^Usual care/);
  assert.equal(parts(frensham(), DATES[2]).act, 'Follow the official advice above first.');
  const card = Embed.card(frensham(), DATA, NOW);
  assert.ok(card.includes('<p class="act">Follow the official advice above first.</p>'));
  assert.doesNotMatch(card, /Usual care/);
  assert.match(Embed.card(other(), DATA, NOW), /Usual care/);
});

test('the Not known row and the algae tile: the checked date once, in the answer; the tile says what it is beside an algae notice', () => {
  assert.equal(ea.eaTodayLatest(frensham()), 'Open <a href="#ea-today">today\'s EA advice</a> for the latest');
  assert.equal(ea.eaTodayLatest(other({ official: [item()], classification: null })),
    `Open <a href="${PROFILE}">the Environment Agency page</a> for the latest`);
  assert.equal(ea.eaTodayLatest(other()), '');
  const src = pageSrc.join('\n');
  assert.match(src, /rows\.push\(\["Today's EA advice", 'Notice shown above', `\$\{eaTodayLatest\(d\) \|\| 'See the notice above'\}\.`\]\)/);
  assert.match(src, /notice above is about harmful algae; this tile is the sampler's last visual check\./);
});
