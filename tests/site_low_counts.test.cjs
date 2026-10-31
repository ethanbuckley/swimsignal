// One rule for every "at low risk" count that helps choose a place (index.html, lowOn and lowToChoose; plan.js,
// planAreas): low on the day shown, and no official advice restricting swimming. On 31 Oct 2026 the day strip said
// 54 and the area lines and the list summary 55, because Frensham Great Pond (low for sewage, EA advice against
// bathing for harmful algae) was counted in some and not others. The summary keeps the forecast's own tally and says
// how many of its low spots are under such advice. node --test tests/site_low_counts.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const { join } = require('node:path');

const SITE = join(__dirname, '../src/dipcast/site');
const DATES = ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30'];
const RISK = { low: 0.01, moderate: 0.2, high: 0.5 };
const PROFILE = 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945';
const notice = { line: 'Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026', publisher: 'Environment Agency',
  link: PROFILE, since: '2026-06-19', checked: '2026-10-26', state: 'checked', restricts: true };
const spot = (id, name, area, label, extra = {}) => ({ id, name, area, kind: 'lake', source: 'curated', lat: 51 + id.length / 10, lon: -1,
  upstream_summary: { overflows: 2 }, assumptions: { max_upstream_km: 15 }, location: { mode: 'lake' }, now: { label, discharging_upstream: 0 },
  contributors: [], days: DATES.map(date => ({ date, risk: RISK[label], label, expected_spilling_overflows: 0, rain_48h_mm: 1 })), ...extra });
const SPOTS = [
  spot('a', 'Ashford', 'Surrey', 'low'), spot('bb', 'Bray', 'Surrey', 'moderate'),
  spot('ccc', 'Frensham Great Pond', 'Surrey', 'low', { source: 'designated', classification: { class: 'excellent', year: 2025, url: PROFILE }, official: [notice] }),
  spot('dddd', 'Dart', 'Devon', 'low'), spot('eeeee', 'Exe', 'Devon', 'high'),
];

const src = (() => { const html = fs.readFileSync(join(SITE, 'index.html'), 'utf8');
  return html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n'); })();
const defs = names => names.map(n => { const i = src.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
  assert.ok(i >= 0, `no ${n} in index.html`);
  let j = i + 1; while (j < src.length && /^[\s})\]+]/.test(src[j])) j++;
  return src.slice(i, j).join('\n'); }).join('\n');
const ctx = vm.createContext({ DATA: { generated_at: '2026-10-26T20:00:00Z', spots: SPOTS } });
for (const f of ['experience.js', 'levels.js']) vm.runInContext(fs.readFileSync(join(SITE, f), 'utf8'), ctx);
vm.runInContext(`setToday("${DATES[0]}");`, ctx);
vm.runInContext(fs.readFileSync(join(SITE, 'eatoday.js'), 'utf8'), ctx);
vm.runInContext(defs(['esc', 'VIEW', 'issued', 'mapLevel', 'mapWhen', 'listHeadline', 'noticeVerb', 'overview',
  'lowEligible', 'lowOn', 'lowToChoose', 'areaHead', 'areaFold']), ctx);
vm.runInContext(`VIEW.day = "${DATES[0]}";`, ctx);
const run = (f, ...a) => vm.runInContext(f, ctx)(...a);

test('the day strip, the area lines and the plan\'s areas give one count, leaving out the spot under advice', () => {
  const strip = run('lowOn', DATES[0]);
  assert.equal(strip, 2);   // Ashford and Dart; Frensham is low for sewage but under advice against bathing
  assert.equal(run('lowToChoose', SPOTS), strip);
  const areaCount = a => Number(run('areaFold', a, SPOTS.filter(s => s.area === a), () => '').match(/<span>(\d+) of \d+ at low risk<\/span>/)[1]);
  assert.equal(areaCount('Surrey') + areaCount('Devon'), strip);
  assert.match(run('areaHead', 'Surrey', SPOTS.filter(s => s.area === 'Surrey')), /, 1 at low risk</);
  // The planner's area suggestions (plan.js) count the same way.
  const P = require(join(SITE, 'plan.js'));
  const areas = P.planAreas(SPOTS, { day: DATES[0], kind: 'all' }, () => 1, 5);
  assert.equal(areas.reduce((t, a) => t + a.low, 0), strip);
});

test('the summary keeps the forecast\'s tally and says how many of its low spots are under advice', () => {
  const said = run('overview', SPOTS);
  assert.match(said, /: 3 low \(1 of them under official advice restricting swimming\) · 1 moderate · 1 high or very high/);
  // 3 low in the forecast's tally, less the 1 under advice: the strip's 2.
  assert.equal(3 - 1, run('lowOn', DATES[0]));
  // With no such spot, the summary says nothing of it.
  const plain = SPOTS.filter(s => !s.official);
  assert.doesNotMatch(run('overview', plain), /under official advice/);
});
