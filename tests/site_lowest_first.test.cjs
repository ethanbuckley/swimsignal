// The list's "Lowest risk" order (index.html, lowOrder, lowLastNote, nearCards; 29 Oct 2026): low before moderate
// before high, then spots with no level, and spots with advice against swimming last of all whatever their level; the nearer
// first among equals once a place is given; and, with a place, cards for the lowest-risk spots within 30 miles.
// node --test tests/site_lowest_first.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const { join } = require('node:path');

const SITE = join(__dirname, '../src/dipcast/site');
const DATES = ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30'];
const RISK = { low: 0.01, moderate: 0.2, high: 0.5 };
const spot = (id, name, label, lat = 51.45, lon = -2.59, extra = {}) => ({ id, name, kind: 'river', source: 'osm', lat, lon, area: 'West',
  upstream_summary: { overflows: label ? 2 : 0 }, assumptions: { max_upstream_km: 15 }, location: { mode: 'river' },
  now: { label: label || 'low', discharging_upstream: 0 }, contributors: [],
  days: DATES.map(date => ({ date, risk: RISK[label || 'low'], label: label || 'low', expected_spilling_overflows: 0, rain_48h_mm: 1 })), ...extra });
const ADVICE = { line: 'Environment Agency: advice against bathing', publisher: 'Environment Agency', since: '2026-06-19', checked: '2026-10-26', state: 'checked', restricts: true };

const pageSrc = (() => { const html = fs.readFileSync(join(SITE, 'index.html'), 'utf8');
  return html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n'); })();
function pageDefs(names) {
  return names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
    assert.ok(i >= 0, `no ${n} in index.html`);
    let j = i + 1; while (j < pageSrc.length && /^[\s})\]+:|]/.test(pageSrc[j])) j++;
    return pageSrc.slice(i, j).join('\n'); }).join('\n');
}
const ctx = vm.createContext({ DATA: { generated_at: '2026-10-26T20:00:00Z', spots: [] }, NEAR_N: 3, MILE_KM: 1.609344 });
vm.runInContext(fs.readFileSync(join(SITE, 'experience.js'), 'utf8'), ctx);
vm.runInContext(fs.readFileSync(join(SITE, 'levels.js'), 'utf8') + `\nsetToday("${DATES[0]}");`, ctx);
vm.runInContext(fs.readFileSync(join(SITE, 'eatoday.js'), 'utf8'), ctx);
vm.runInContext(pageDefs(['VIEW', 'mapLevel', 'listRank', 'listAdvised', 'lowRank', 'lowOrder', 'lowLastNote', 'CARDS_KM', 'nearCards']), ctx);
vm.runInContext('var dist = s => s.km; this.VIEW = VIEW;', ctx);
const names = xs => [...xs].sort(vm.runInContext('lowOrder', ctx)).map(s => s.name);
const plain = a => JSON.parse(JSON.stringify(a));   // arrays made in the page's context

test('lowest risk first: low, moderate, high, then spots with no level, then advised spots', () => {
  const xs = [spot('h', 'Hythe', 'high'), spot('m', 'Marlow', 'moderate'), spot('l', 'Lechlade', 'low'),
    spot('a', 'Abbey Mere', 'low', 51, -1, { official: [ADVICE] }), spot('n', 'Nidd', null)];
  assert.deepEqual(names(xs), ['Lechlade', 'Marlow', 'Hythe', 'Nidd', 'Abbey Mere']);
  assert.equal(vm.runInContext('lowLastNote', ctx)(xs), 'Spots with an official notice come last.');
  assert.equal(vm.runInContext('lowLastNote', ctx)(xs.slice(0, 3)), '');
});

test('with a place, the nearer first among equal levels; without one, by name', () => {
  const xs = [Object.assign(spot('b', 'Bath', 'low'), { km: 20 }), Object.assign(spot('a', 'Avon', 'low'), { km: 40 }), Object.assign(spot('c', 'Cam', 'moderate'), { km: 2 })];
  ctx.VIEW.here = null; assert.deepEqual(names(xs), ['Avon', 'Bath', 'Cam']);
  ctx.VIEW.here = [51.45, -2.59]; assert.deepEqual(names(xs), ['Bath', 'Avon', 'Cam']);
});

test('the cards: the lowest-risk spots within 30 miles; with none so near, the three nearest', () => {
  ctx.VIEW.here = [51.45, -2.59];
  const near = [Object.assign(spot('h', 'High Close', 'high'), { km: 3 }), Object.assign(spot('l', 'Low Far', 'low'), { km: 40 }),
    Object.assign(spot('m', 'Mid', 'moderate'), { km: 20 }), Object.assign(spot('x', 'Too Far', 'low'), { km: 60 })];
  ctx.DATA.spots = near;
  const c = vm.runInContext('nearCards', ctx)();
  assert.equal(c.title, 'Lowest risk within 30 miles');
  assert.deepEqual(plain(c.spots.map(s => s.name)), ['Low Far', 'Mid', 'High Close']);   // 40 km is under 30 miles (48.3 km)
  ctx.DATA.spots = near.map(s => Object.assign({}, s, { km: s.km + 100 }));
  const d = vm.runInContext('nearCards', ctx)();
  assert.equal(d.title, 'Near you');
  assert.deepEqual(plain(d.spots.map(s => s.name)), ['High Close', 'Mid', 'Low Far']);
});
