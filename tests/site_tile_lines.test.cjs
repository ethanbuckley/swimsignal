// Every number on a page agrees with the headline, or says why it does not (6 Oct 2026). Wharfe at
// Cromwheel read "High risk" over a spills tile at "Moderate risk", a water tile out of season and five
// days at "High"; its list row said "Rated poor: advice against bathing from 15 May", with no level; the
// list said "E. coli estimate 43%†" with no unit; and "1 of 105 spots have no forecast in this build"
// sat above every spot's name and beside a list summary of "3 without a level".
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const L = require('../src/dipcast/site/levels.js');

const SITE = path.join(__dirname, '../src/dipcast/site/');
const pageSrc = fs.readFileSync(SITE + 'index.html', 'utf8').split('\n');
function pageDefs(names) {
  return names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
    assert.ok(i >= 0, `no ${n} in index.html`);
    let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
    return pageSrc.slice(i, j).join('\n'); }).join('\n');
}
function pageContext(names, extra = {}, today = '2026-10-06') {
  const ctx = vm.createContext({...extra});
  vm.runInContext(fs.readFileSync(SITE + 'experience.js', 'utf8'), ctx);
  vm.runInContext(fs.readFileSync(SITE + 'levels.js', 'utf8') + `\nsetToday("${today}");`, ctx);
  vm.runInContext(pageDefs(names), ctx);
  return ctx;
}
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();

// October: out of the bathing season and of the E. coli estimate's tested months.
const DATES = ['2026-10-06', '2026-10-07', '2026-10-08', '2026-10-09', '2026-10-10'];
const RISK = {low: 0.05, moderate: 0.28, high: 0.5, 'very high': 0.8};
const spot = (labels, extra = {}, p = 0.41, inSeason = false) => ({id: 'x', name: 'X', kind: 'river', source: 'curated',
  upstream_summary: {overflows: 15}, location: {mode: 'river'}, now: {label: 'low', discharging_upstream: 0}, contributors: [],
  assumptions: {max_upstream_km: 60}, ...extra,
  days: labels.map((l, i) => ({date: DATES[i], label: l, risk: RISK[l], p_ecoli_gt900: p, in_validated_season: inSeason}))});
// Wharfe at Cromwheel on 6 Oct 2026: rated poor, spills moderate today, the estimate 41% out of season.
const wharfe = spot(['moderate', 'moderate', 'moderate', 'high', 'moderate'], {source: 'designated',
  classification: {class: 'poor', year: 2025}, algae: {date: '2026-09-24', level: 0, phrase: 'none seen', n_checks: 22, n_seen: 0}});
const lines = s => Object.fromEntries(['spill', 'water', 'rating', 'algae', 'now'].map(k => [k, L.tileLine(s, k)]));

test('a water rated poor: the spills tile says the rating raises it, the rating tile that it sets it', () => {
  L.setToday(DATES[0]);
  assert.equal(L.headline(wharfe), 'High risk: rated poor');
  assert.deepEqual(lines(wharfe), {
    spill: 'On its own: moderate risk. The poor rating raises the level to high risk.',
    water: '',   // out of season: its † note says it does not set the level
    rating: 'This sets the level above.',
    algae: 'Does not raise the level.',
    now: ''});
  // A picked day with high spills: the rating ties, and is named.
  assert.equal(L.dayHeadline(wharfe, DATES[3]), 'High risk: rated poor');
  assert.equal(L.tileLine(wharfe, 'spill', DATES[3]), 'On its own: high risk too.');
  assert.equal(L.tileLine(wharfe, 'rating', DATES[3]), 'This sets the level above.');
});

test('spills that set the level say so; another day or right now is named when it raises it', () => {
  L.setToday(DATES[0]);
  assert.equal(L.tileLine(spot(['moderate', 'low', 'low', 'low', 'low']), 'spill'), 'This sets the level above.');
  assert.equal(L.tileLine(spot(['low', 'high', 'low', 'low', 'low']), 'spill'), "Tomorrow's spill forecast raises the level to high risk.");
  const recent = spot(['low', 'low', 'low', 'low', 'low'], {now: {label: 'moderate', discharging_upstream: 0}});
  assert.equal(L.headline(recent), 'Moderate risk right now: recent sewage spills');
  assert.equal(L.tileLine(recent, 'spill'), 'Recent spills raise the level to moderate risk right now.');
  assert.equal(L.tileLine(recent, 'now'), 'This sets the level above.');
  const running = spot(['moderate', 'low', 'low', 'low', 'low'], {now: {label: 'very high', discharging_upstream: 2}});
  assert.equal(L.tileLine(running, 'spill'), 'Spills right now raise the level to very high risk.');
  // All low: the spills tile says it once; right now adds nothing.
  const low = spot(['low', 'low', 'low', 'low', 'low']);
  assert.equal(L.tileLine(low, 'spill'), 'This sets the level above.');
  assert.equal(L.tileLine(low, 'now'), '');
});

test('in season the water estimate is counted: it sets the level, or says what raises it', () => {
  L.setToday(DATES[0]);
  const wet = spot(['low', 'low', 'low', 'low', 'low'], {}, 0.3, true);
  assert.equal(L.headline(wet), 'High risk today: raised E. coli likely');
  assert.equal(L.tileLine(wet, 'water'), 'This sets the level above.');
  assert.equal(L.tileLine(wet, 'spill'), 'On its own: low risk. The E. coli estimate raises the level to high risk.');
  const dry = spot(['moderate', 'low', 'low', 'low', 'low'], {}, 0.02, true);
  assert.equal(L.tileLine(dry, 'water'), 'On its own: low risk. The spill forecast raises the level to moderate risk.');
});

test('a rating or algae that is not counted says so, and one that sets a plain spot\'s level says that', () => {
  L.setToday(DATES[0]);
  assert.equal(L.tileLine({...spot(['low', 'low', 'low', 'low', 'low']), classification: {class: 'excellent'}}, 'rating'),
    'Not counted in the level: only a poor rating is.');
  const clear = {...spot(['low', 'low', 'low', 'low', 'low']), upstream_summary: {overflows: 0}};
  assert.equal(L.level(clear), L.NO_OVERFLOWS);
  assert.equal(L.tileLine({...clear, classification: {class: 'good'}}, 'rating'), 'Not counted in the level: only a rating of sufficient or poor is.');
  assert.equal(L.tileLine(clear, 'spill'), '');
  const sufficient = {...clear, classification: {class: 'sufficient'}};
  assert.equal(L.headline(sufficient), 'Moderate risk: rated sufficient by the Environment Agency');
  assert.equal(L.tileLine(sufficient, 'rating'), 'This sets the level above.');
  assert.equal(L.tileLine({...clear, algae: {date: '2026-09-01', level: 3, phrase: 'enough to be objectionable'}}, 'algae'),
    'Over two weeks old, so not counted in the level.');
  const failed = {id: 'f', name: 'F', days: undefined, error: 'forecast failed: open-meteo request failed', classification: {class: 'excellent'},
    algae: {date: '2026-10-01', level: 0}};
  assert.deepEqual(Object.values(lines({...failed, days: []})), ['', '', '', '', '']);
});

test('the answer, the list and the picked day lead with the level, then the rating', () => {
  const ctx = pageContext(['esc', 'tone', 'headTone', 'rainSaid', 'answerParts']);
  const run = (f, ...a) => vm.runInContext(f, ctx)(...a);
  const m = run('answerParts', wharfe);
  assert.deepEqual([m.word, m.sub, m.next], ['High', 'Rated poor', 'At least high risk every day']);
  assert.equal(run('answerParts', wharfe, DATES[1]).sub, 'Rated poor');
  const summer = pageContext(['esc', 'tone', 'headTone', 'rainSaid', 'answerParts'], {}, '2026-09-30');
  const june = {...wharfe, days: wharfe.days.map((x, i) => ({...x, date: ['2026-09-30', '2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04'][i]}))};
  assert.equal(vm.runInContext('answerParts', summer)(june).sub, 'Rated poor, advice against bathing');
  // No list row, Saved card or alert reads "Rated poor" without its level any more.
  L.setToday(DATES[0]);
  for (const s of [wharfe, {...wharfe, upstream_summary: {overflows: 0}}]) {
    assert.match(L.headline(s), /^High risk: rated poor$/);
    assert.doesNotMatch(L.headline(s), /from 15 May/);
  }
});

test('a tile puts its line under the figure, before its sentence; a factor row under its value', () => {
  const ctx = pageContext(['tile', 'factorRow', 'tone']);
  const h = vm.runInContext('tile', ctx)({icon: '', label: 'Sewage spills', fig: 28, unit: 'of 100', rel: 'REL', say: 'SAY'});
  assert.match(h, /<p class="t-say">REL<\/p><p class="t-say">SAY<\/p>/);
  assert.doesNotMatch(vm.runInContext('tile', ctx)({icon: '', label: 'Weather', fig: 1, say: 'SAY'}), /t-say">undefined/);
  const r = vm.runInContext('factorRow', ctx)('Sewage spills upstream', 'moderate', 'Moderate risk', 'DETAIL', 'REL');
  assert.match(r, /<div class="f-d">REL<\/div><div class="f-d">DETAIL<\/div>/);
  assert.doesNotMatch(vm.runInContext('factorRow', ctx)('Rain here', null, '3 mm', 'DETAIL'), /f-d"><\/div>/);
});

test('the list counts the spots without a level by why; a spot\'s page notes only its own failure', () => {
  const failed = {id: 'o', name: 'River Great Ouse, Overcote', kind: 'river', error: 'forecast failed: open-meteo request failed'};
  const lake = n => ({id: n, name: n, kind: 'lake', days: [], error: 'An isolated lake with no river connection in the network: storm overflows cannot reach it by water.'});
  const ok = spot(['low', 'low', 'low', 'low', 'low']);
  const ctx = pageContext(['VIEW', 'mapLevel', 'mapWhen', 'listHeadline', 'overview', 'gaps'],
    {issued: () => 'Tue 14:51', DATA: {build: {spots: 4, forecast_failed: 1, no_forecast_possible: 2, today_rain_unavailable: 1}}});
  const run = (f, ...a) => vm.runInContext(f, ctx)(...a);
  assert.equal(run('overview', [ok, failed, lake('Henleaze Lake'), lake('Cotswold Country Park and Beach')]),
    'Updated Tue 14:51 · Pollution risk: 1 low · 0 moderate · 0 high or very high · 3 without a level: 2 no river connection, 1 no forecast in this update. Today and tomorrow.');
  assert.equal(run('overview', [ok]), 'Updated Tue 14:51 · Pollution risk: 1 low · 0 moderate · 0 high or very high · 0 without a level. Today and tomorrow.');
  assert.equal(text(run('gaps', null, true)), '1 spot has no rainfall data for today in this update.');
  assert.equal(run('gaps', null, false), '');   // Saved, a shared list, a plan: their cards say it
  assert.equal(run('gaps', ok), '');
  assert.equal(text(run('gaps', failed)), "This spot's forecast failed in this update, so it has no level.");
  const src = pageSrc.join('\n');
  assert.doesNotMatch(src, /spots have no forecast in this build/);
  assert.doesNotMatch(src, /no rainfall data for today in this build/);
});

test('a list row gives no water figure: out of season it is untested, and it had no unit', () => {
  const ctx = pageContext(['esc', 'fmt', 'tone', 'initial', 'VIEW', 'km', 'dist', 'away', 'PAGE_ID', 'spotPath',
    'week', 'rainMeta', 'mapLevel', 'listHeadline', 'listPath', 'spotItem'], {ROOT: {pathname: '/'}});
  const row = text(vm.runInContext('spotItem', ctx)(wharfe));
  assert.match(row, /High risk: rated poor/);
  assert.doesNotMatch(row, /E\. ?coli|%/);
});

test('the Accuracy page and the scoring rules say South West Water is scored from 5 October', () => {
  const ver = fs.readFileSync(path.join(__dirname, '../src/dipcast/api/static/verification.html'), 'utf8');
  assert.doesNotMatch(ver, /as South West Water's, never counts as current/);
  assert.match(ver, /South West Water's records carry one, lastUpdated, but the site read it only from 4 October 2026, so its overflows are scored from 5 October/);
  const log = fs.readFileSync(path.join(__dirname, '../src/dipcast/forecast_log.py'), 'utf8');
  assert.doesNotMatch(log, /\(South West Water's\) is never current: its overflows are not scored"/);
  assert.match(log, /"unstamped_feed": "a feed with no record stamp is never current: its overflows are not scored that day\. South West Water's lastUpdated stamp was read only from 4 Oct 2026, so its overflows are scored from 5 Oct"/);
});
