// Reviewed official advice in its compact form (src/dipcast/site/eatoday.js, eaTodayBrief and eaTodayTag),
// on the surfaces where a spot is one row among many: the list, Saved and Plan a swim's rows (index.html,
// spotItem, savedCard, planItem). One helper, so every surface says the same; it sits beside the level,
// never in it. Fixture items only: no real approval. node --test tests/site_official_tags.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const { join } = require('node:path');
const ea = require('../src/dipcast/site/eatoday.js');

const SITE = join(__dirname, '../src/dipcast/site');
const PROFILE = 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945';
const LINE = 'Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026';
const item = (extra = {}) => ({ line: LINE, publisher: 'Environment Agency', link: PROFILE, since: '2026-06-19', checked: '2026-10-26', state: 'checked', ...extra });
const BRIEF = 'EA advice against bathing (harmful algae) · since 19 Jun · checked 26 Oct';

test('the compact form: who, what, since when, and when it was checked', () => {
  assert.equal(ea.eaTodayBrief({ official: [item()] }), BRIEF);
  assert.equal(ea.eaTodayBrief({ official: [item({ state: 'stale' })] }), 'EA advice against bathing (harmful algae) · since 19 Jun · not re-checked since 26 Oct');
  assert.equal(ea.eaTodayBrief({ official: [item({ state: 'gone' })] }), 'EA advice against bathing (harmful algae) · since 19 Jun · not re-checked since 26 Oct');
  assert.equal(ea.eaTodayBrief({ official: [item(), item({ since: '2026-01-01' })] }), BRIEF + ' · 1 more');
  assert.equal(ea.eaTodayBrief({ official: [item({ publisher: 'Waverley Borough Council',
    line: 'Waverley Borough Council: advice against swimming (blue-green algae) since 22 Aug 2025', since: '2025-08-22' })] }),
  'Waverley Borough Council advice against swimming (blue-green algae) · since 22 Aug · checked 26 Oct');
  assert.equal(ea.eaTodayTag({ official: [item()] }), `<span class="o-tag">${BRIEF}</span>`);
  assert.equal(ea.eaTodayTag({ official: [item()] }, 'p'), `<p class="o-tag">${BRIEF}</p>`);
  assert.match(ea.eaTodayTag({ official: [item({ publisher: '<b>x</b>', line: '<b>x</b>: <i>y</i> since 1 Jan 2026' })] }), /&lt;b&gt;x&lt;\/b&gt; &lt;i&gt;y&lt;\/i&gt;/);
  for (const d of [{}, { official: [] }, null, { official: [item({ state: 'approved' })] }]) {
    assert.equal(ea.eaTodayBrief(d), '');
    assert.equal(ea.eaTodayTag(d), '');
  }
});

// The page's own row functions, run beside levels.js, experience.js and eatoday.js, as in the browser.
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
  vm.runInContext(fs.readFileSync(join(SITE, 'levels.js'), 'utf8') + '\nsetToday("2026-10-26");', ctx);
  if (withAdvice) vm.runInContext(fs.readFileSync(join(SITE, 'eatoday.js'), 'utf8'), ctx);
  vm.runInContext(pageDefs(names), ctx);
  return ctx;
}
const NAMES = ['esc', 'fmt', 'cls', 'dateLabel', 'glyph', 'ICON', 'tone', 'colour', 'headTone', 'initial', 'VIEW', 'km', 'dist', 'away',
  'PAGE_ID', 'spotPath', 'BOOKMARK', 'untested', 'week', 'rainMeta', 'rainSaid', 'answerParts', 'savedCard', 'mapLevel',
  'listHeadline', 'listPath', 'headNote', 'spotItem', 'planItem'];
const EXTRA = { ROOT: { pathname: '/' }, DATA: { generated_at: '2026-10-26T20:00:00Z' }, PLAN: { day: '2026-10-26' },
  planWhy: () => '', planEvidence: () => '', milesAway: m => `${m} miles away` };
const DATES = ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30'];
const frensham = (extra = {}) => ({ id: 'bw-ukj2310-11945', name: 'Frensham Great Pond', kind: 'lake', source: 'designated',
  classification: { class: 'excellent', year: 2025, url: PROFILE }, upstream_summary: { overflows: 2 }, assumptions: { max_upstream_km: 15 },
  location: { mode: 'lake' }, now: { label: 'low', discharging_upstream: 0 }, contributors: [],
  days: DATES.map(date => ({ date, risk: 0.01, label: 'low', rain_48h_mm: 1 })), ...extra });

test('the list, Saved and Plan a swim show the compact form beside the level, and change nothing else', () => {
  const ctx = pageContext(NAMES, EXTRA), run = (f, ...a) => vm.runInContext(f, ctx)(...a);
  const on = frensham({ official: [item()] }), off = frensham();
  const tag = `<span class="o-tag">${BRIEF}</span>`;
  const row = run('spotItem', on);
  assert.ok(row.includes(`<span class="hl low">Low risk for the next five days</span>${tag}<span class="k">`), row);
  assert.equal(row.replace(tag, ''), run('spotItem', off));   // the level and the rest are the same
  const card = run('savedCard', on);
  assert.ok(card.includes(`<p class="o-tag">${BRIEF}</p>`), card);
  assert.ok(card.indexOf('class="big low">Low risk') < card.indexOf('o-tag'));
  assert.equal(card.replace(`<p class="o-tag">${BRIEF}</p>`, ''), run('savedCard', off));
  const plan = run('planItem', { s: on, miles: 3, level: 'low' });
  assert.ok(plan.includes(`</span>${tag}<span class="k">`), plan);
  assert.equal(plan.replace(tag, ''), run('planItem', { s: off, miles: 3, level: 'low' }));
  for (const f of ['spotItem', 'savedCard']) assert.doesNotMatch(run(f, off), /o-tag/);
});

test('without eatoday.js the rows draw as before', () => {
  const ctx = pageContext(NAMES, EXTRA, false), run = (f, ...a) => vm.runInContext(f, ctx)(...a);
  for (const f of ['spotItem', 'savedCard']) assert.doesNotMatch(run(f, frensham({ official: [item()] })), /o-tag|advice against/);
});

// The spot page's "Not known here" tile says the same as the answer's line when a reviewed notice shows.
test('the "Not known here" row follows the reviewed notice, and says "Not checked" only without one', () => {
  const names = ['esc', 'fmt', 'cls', 'dateLabel', 'glyph', 'ICON', 'overflows', 'liveSay', 'noFeedSaid', 'accessSaid', 'eaSaid', 'unknowns'];
  const have = names.filter(n => pageSrc.some(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`)));
  const ctx = pageContext(have, EXTRA), run = (f, ...a) => vm.runInContext(f, ctx)(...a);
  const row = d => JSON.parse(JSON.stringify(run('unknowns', d).find(r => r[0] === "Today's EA advice")));   // out of the page's realm
  assert.deepEqual(row(frensham({ official: [item()] })), ["Today's EA advice", 'Notice shown above',
    'Open <a href="#ea-today">today\'s EA advice</a> for the latest.']);   // when it was checked is said once, in the answer (coverLine)
  assert.deepEqual(row(frensham({ official: [item({ state: 'unverified', checked: '2026-10-19' })] })).slice(0, 2), ["Today's EA advice", 'Notice shown above']);
  assert.equal(row(frensham())[1], 'Not checked');
});

