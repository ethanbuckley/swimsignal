// The list's "Highest risk" order (index.html, riskOrder and riskFirstNote): a spot whose row shows official
// advice against swimming (eatoday.js, eaTodayAdvice) comes first, whatever its sewage level, by level then name
// among such spots; the rest keep the order they had. A notice not re-checked still shows, so still comes first;
// one in a state no page shows (ended, withdrawn) does not. No level or count changes. Fixture items only, with
// the approved Frensham entry's words. node --test tests/site_risk_order.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const { join } = require('node:path');

const SITE = join(__dirname, '../src/dipcast/site');
const PROFILE = 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945';
const LINE = 'Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026';
const item = (extra = {}) => ({ line: LINE, publisher: 'Environment Agency', link: PROFILE, since: '2026-06-19', checked: '2026-10-26', state: 'checked', ...extra });
const DATES = ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30'];
const RISK = { low: 0.01, moderate: 0.2, high: 0.5 };
const spot = (id, name, label = 'low', extra = {}) => ({ id, name, kind: 'lake', source: 'designated', lat: 51.15, lon: -0.79, area: 'Surrey',
  classification: { class: 'excellent', year: 2025, url: PROFILE }, upstream_summary: { overflows: 2 }, assumptions: { max_upstream_km: 15 },
  location: { mode: 'lake' }, now: { label, discharging_upstream: 0 }, contributors: [],
  days: DATES.map(date => ({ date, risk: RISK[label], label, expected_spilling_overflows: 0, rain_48h_mm: 1, p_ecoli_gt900: 0.02, in_validated_season: false })), ...extra });

// The page's own functions, run beside levels.js, experience.js and eatoday.js, as in the browser.
const pageSrc = (() => { const html = fs.readFileSync(join(SITE, 'index.html'), 'utf8');
  return html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n'); })();
function pageDefs(names) {
  return names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
    assert.ok(i >= 0, `no ${n} in index.html`);
    let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
    return pageSrc.slice(i, j).join('\n'); }).join('\n');
}
function pageContext(withAdvice = true) {
  const ctx = vm.createContext({ DATA: { generated_at: '2026-10-26T20:00:00Z', spots: [] } });
  vm.runInContext(fs.readFileSync(join(SITE, 'experience.js'), 'utf8'), ctx);
  vm.runInContext(fs.readFileSync(join(SITE, 'levels.js'), 'utf8') + `\nsetToday("${DATES[0]}");`, ctx);
  if (withAdvice) vm.runInContext(fs.readFileSync(join(SITE, 'eatoday.js'), 'utf8'), ctx);
  vm.runInContext(pageDefs(['esc', 'VIEW', 'issued', 'mapLevel', 'mapWhen', 'listHeadline', 'overview',
    'listRank', 'listAdvised', 'riskOrder', 'riskFirstNote']), ctx);
  return ctx;
}
const ctx = pageContext(), run = (f, ...a) => vm.runInContext(f, ctx)(...a);
const order = (spots, c = ctx) => [...spots].sort(vm.runInContext('riskOrder', c)).map(s => s.name);
const levels = (spots, c = ctx) => spots.map(s => [s.name, vm.runInContext('mapLevel', c)(s)]);

const frensham = (extra = {}) => spot('bw-ukj2310-11945', 'Frensham Great Pond', 'low', { official: [item()], ...extra });
const others = () => [spot('a', 'Ashford Weir', 'high'), spot('b', 'Bray Lock', 'moderate'), spot('c', 'Cotswold Lake', 'low'), spot('d', 'Dart Reach', 'high')];

test('without an advised spot the order is the sewage level, then name, and no line shows', () => {
  const xs = others();
  assert.deepEqual(order(xs), ['Ashford Weir', 'Dart Reach', 'Bray Lock', 'Cotswold Lake']);
  assert.equal(run('riskFirstNote', xs), '');
});

test('a spot with advice against swimming comes first, its level unchanged, and the line says why', () => {
  const xs = [...others(), frensham()];
  // Before this change Frensham (low) sat last but for name: after Cotswold Lake. Now it leads.
  assert.deepEqual(order(xs), ['Frensham Great Pond', 'Ashford Weir', 'Dart Reach', 'Bray Lock', 'Cotswold Lake']);
  assert.equal(run('riskFirstNote', xs), 'Spots with official advice against swimming come first.');
  // Levels and counts are the same as without the advice, and as before the sort.
  const bare = [...others(), frensham({ official: [] })];
  assert.deepEqual(levels(xs), levels(bare));
  assert.equal(run('mapLevel', frensham()), 'low');
  assert.equal(run('overview', xs).replace('Sewage pollution risk', 'Pollution risk').replace(/ 1 with official advice against swimming: follow it first\.$/, ''),
    run('overview', bare));
  assert.match(run('overview', xs), /Sewage pollution risk: 2 low · 1 moderate · 2 high or very high/);
});

test('advised spots among themselves: by sewage level, then name', () => {
  const ham = spot('bw-ham', 'Ham and Kingston', 'high', { official: [item()] });
  const abbey = spot('bw-abbey', 'Abbey Mere', 'low', { official: [item()] });
  assert.deepEqual(order([...others(), frensham(), abbey, ham]),
    ['Ham and Kingston', 'Abbey Mere', 'Frensham Great Pond', 'Ashford Weir', 'Dart Reach', 'Bray Lock', 'Cotswold Lake']);
});

test('a notice not re-checked still shows, so still comes first; an ended or withdrawn one does not', () => {
  for (const state of ['stale', 'unverified', 'gone', 'changed']) {
    const xs = [...others(), frensham({ official: [item({ state })] })];
    assert.equal(order(xs)[0], 'Frensham Great Pond', state);
    assert.notEqual(run('riskFirstNote', xs), '', state);
  }
  for (const state of ['ended', 'withdrawn']) {
    const xs = [...others(), frensham({ official: [item({ state })] })];
    assert.deepEqual(order(xs), ['Ashford Weir', 'Dart Reach', 'Bray Lock', 'Cotswold Lake', 'Frensham Great Pond'], state);
    assert.equal(run('riskFirstNote', xs), '', state);
  }
});

test('without eatoday.js the order is the sewage level alone', () => {
  const bare = pageContext(false), xs = [...others(), frensham()];
  assert.deepEqual(order(xs, bare), ['Ashford Weir', 'Dart Reach', 'Bray Lock', 'Cotswold Lake', 'Frensham Great Pond']);
  assert.equal(vm.runInContext('riskFirstNote', bare)(xs), '');
});

test('the list uses the order only where it shows Highest risk, and the line only with it', () => {
  const src = pageSrc.join('\n'), draw = src.slice(src.indexOf('function drawSpots() {'), src.indexOf('\n}\n', src.indexOf('function drawSpots() {')));
  assert.match(draw, /const byRisk = VIEW\.sort !== 'name' && !\(VIEW\.sort === 'near' && VIEW\.here\);/);
  assert.match(draw, /: byRisk \? riskOrder\(a, b\) : a\.name\.localeCompare\(b\.name\)\);/);
  assert.match(draw, /firstNote = byRisk \? riskFirstNote\(items\) : ''/);
  assert.match(src, /<p class="overview" id="overview"><\/p><p class="overview" id="risk-first" hidden><\/p><ul class="spots" id="spots">/);
});
