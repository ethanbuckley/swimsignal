const {test} = require('node:test');
const assert = require('node:assert/strict');
const {dayHeadline, dayLevel, setToday} = require('../src/dipcast/site/levels.js');
setToday('2026-09-30');
const spot = {upstream_summary:{overflows:2}, location:{mode:'river'}, now:{label:'low'}, days:[
  {date:'2026-09-30',label:'low',risk:0,p_ecoli_gt900:0.02},
  {date:'2026-10-01',label:'very high',risk:0.9,p_ecoli_gt900:0.02}
]};
test('the chosen day describes its own risk rather than tomorrow’s worse forecast', () => {
  assert.equal(dayHeadline(spot,'2026-09-30'),'Low risk');
  assert.equal(dayLevel(spot,'2026-09-30'),'low');
  assert.equal(dayHeadline(spot,'2026-10-01'),'Very high risk: sewage spills');
});
test('a missing day never becomes low', () => {
  assert.equal(dayHeadline(spot,'2026-10-04'),'No forecast for this day');
  assert.equal(dayLevel(spot,'2026-10-04'),'no forecast');
});
test('standing poor advice survives a low daily prediction', () => {
  const poor = {...spot,classification:{class:'poor'}};
  assert.equal(dayHeadline(poor,'2026-09-30'),'High risk: rated poor, advice against bathing');
  assert.equal(dayLevel(poor,'2026-09-30'),'high');
});
test('out of season the water-quality estimate is shown but does not set the level', () => {
  const {ecoliBand, ecoliLevel, level, headline} = require('../src/dipcast/site/levels.js');
  const day = {date:'2026-09-30', label:'low', risk:0.05, p_ecoli_gt900:0.56, in_validated_season:false};
  const winter = {upstream_summary:{overflows:2}, location:{mode:'river'}, now:{label:'low'}, days:[day, {...day, date:'2026-10-01'}]};
  assert.equal(ecoliBand(winter, day), 'very high');   // its own row and cell keep the band
  assert.equal(ecoliLevel(winter, day), null);          // but it is not in the level
  assert.equal(dayLevel(winter, '2026-09-30'), 'low');
  assert.equal(dayHeadline(winter, '2026-09-30'), 'Low risk');
  assert.equal(level(winter), 'low');
  assert.equal(headline(winter), 'Low risk for the next five days');
  const summer = {...winter, days: winter.days.map(x => ({...x, in_validated_season:true}))};
  assert.equal(dayLevel(summer, '2026-09-30'), 'very high');
  assert.equal(dayHeadline(summer, '2026-09-30'), 'Very high risk: high E.\u00a0coli likely');
  assert.equal(headline(summer), 'Very high risk today: high E.\u00a0coli likely');
  const unmarked = {...winter, days: winter.days.map(({in_validated_season, ...x}) => x)};   // forecasts built before the flag existed
  assert.equal(dayLevel(unmarked, '2026-09-30'), 'very high');
});
test('the lowest-risk day counts low days among spots with a daily forecast, ties to the earlier day', () => {
  const {bestDay} = require('../src/dipcast/site/levels.js');
  const mk = labels => ({upstream_summary:{overflows:1}, location:{mode:'lake'}, now:{label:'low'},
    days: labels.map((l, i) => ({date: ['2026-09-30','2026-10-01','2026-10-02'][i], label: l, risk: l === 'low' ? 0.01 : 0.5}))});
  const spots = [mk(['low','high','low']), mk(['high','low','low']), {days:[], classification:{class:'excellent'}}];
  assert.deepEqual(bestDay(spots, ['2026-09-30','2026-10-01','2026-10-02']), {date:'2026-10-02', low:2, known:2});
  assert.deepEqual(bestDay(spots, ['2026-09-30','2026-10-01']), {date:'2026-09-30', low:1, known:2});
  assert.equal(bestDay([{days:[]}], ['2026-09-30']), null);
  assert.equal(bestDay(spots, ['2026-10-09']), null);   // no spot has a level that day
});
test('standing ratings and missing coverage are not called daily forecasts', () => {
  assert.equal(dayHeadline({days:[],classification:{class:'sufficient'}},'2026-10-01'),'Moderate risk: rated sufficient by the Environment Agency');
  // An excellent or good rating no longer makes such a spot "low": the plain level says what is true there.
  assert.equal(dayHeadline({days:[],classification:{class:'excellent'}},'2026-10-01'),'No monitored overflow found upstream');
  assert.equal(dayHeadline({days:[]},'2026-10-01'),'No monitored overflow found upstream');
});

const {evidenceRows, comparisonIds, compareDays, compareNow, compareAdvice, compareAccess, compareRows} = require('../src/dipcast/site/experience.js');
test('evidence distinguishes missing feeds, dated records, and out-of-season models', () => {
  const days = spot.days.map(x => ({...x, in_validated_season: x.date < '2026-10-01'}));   // as the build marks them
  const s = {...spot, days, now:{monitored_upstream:1},classification:{class:'poor',year:2025,url:'https://example.org'},algae:{date:'2026-09-10',phrase:'none seen'}};
  const facts = Object.fromEntries(evidenceRows(s,'2026-10-01'));
  assert.equal(compareNow(s), '0 discharging. 1 of 2 report live. Not reporting: 1 offline or with no live feed. Missing reports do not mean no spills.');
  assert.match(facts['Environment Agency rating'], /2025.*not today/);
  assert.match(facts['Water samples'], /^No lab sample in this update\. Check the Environment Agency’s page/);   // tests/site_evidence.test.cjs has the rest
  assert.match(facts['Model limits'], /untested/);
  assert.match(facts['Algae observation'], /10 Sept? 2026.*not a current/);
  // The season is the build's mark on the day, as on the page, not the calendar month.
  assert.doesNotMatch(Object.fromEntries(evidenceRows(s,'2026-09-30'))['Model limits'], /untested/);
  const unmarked = {...s, days: spot.days};   // no mark on the day (built before it): the calendar month decides
  assert.match(Object.fromEntries(evidenceRows(unmarked,'2026-10-01'))['Model limits'], /untested/);
  assert.doesNotMatch(Object.fromEntries(evidenceRows(unmarked,'2026-09-30'))['Model limits'], /untested/);
  assert.match(Object.fromEntries(evidenceRows(s,'2026-10-09'))['Model limits'], /untested/);   // a day outside the forecast
});
test('a spot without a forecast is described in the headline’s words', () => {
  const D = ['2026-09-30', '2026-10-01'];
  const lake = {days:[], error:'An isolated lake with no river connection', classification:{class:'excellent', year:2025}};
  assert.equal(compareNow(lake), 'No monitored overflow found upstream.');
  assert.deepEqual(compareDays(lake, D), {same: true, days: D.map(date => ({date, level: 'no river connection', words: 'No monitored overflow found upstream'}))});
  const away = {days:[], error:'No river or lake within 1.5 km of this point.'};
  assert.equal(compareNow(away), 'Not covered by the forecast.');
  assert.equal(compareDays(away, D).days[0].words, 'Not covered by the forecast');
  const failed = {days:[], error:'forecast failed: timeout', upstream_summary:{overflows:4}};
  assert.equal(compareNow(failed), 'No forecast in this update.');
  assert.equal(compareDays(failed, D).days[1].words, 'No forecast in this update');
});
test('missing coverage is not reported as a low risk or current test', () => {
  assert.match(compareNow({days:[]}), /^No monitored overflow found upstream, so no spills to report\. Other pollution sources may still affect this water\.$/);
  assert.match(Object.fromEntries(evidenceRows({days:[]},'2026-09-30'))['Algae observation'], /does not mean algae are absent/);
});

// ------------------------------------------------------------------------------ the comparison
// Saved's "Compare your spots" and the plan's "Compare these spots" (20 Oct 2026): every cell says
// something, and where the data is missing it says it is not known, never a blank that reads as low.
test('the comparison says a day, a live status, advice or access is not known, rather than leave a blank', () => {
  // A day the forecast does not have: no forecast for it, not low.
  assert.deepEqual(compareDays(spot, ['2026-09-30', '2026-10-01', '2026-10-02']).days.map(d => [d.level, d.words]),
    [['low', 'Low risk'], ['very high', 'Very high risk: sewage spills'], ['no forecast', 'No forecast for this day']]);
  assert.equal(compareDays(spot, ['2026-09-30']).same, false);
  // Overflows upstream but no live status in the update; none of them reporting; the ones that matter most not reporting.
  assert.equal(compareNow({...spot, now: {label: 'low'}}), 'Not known: this update has no live status for the 2 overflows upstream.');
  assert.equal(compareNow({...spot, now: {label: 'low', monitored_upstream: 0, discharging_upstream: 0}}),
    'Whether any is discharging is not known. None of 2 report live. Not reporting: 2 offline or with no live feed. Missing reports do not mean no spills.');
  const thin = {...spot, upstream_summary: {overflows: 13}, now: {label: 'low', discharging_upstream: 0, monitored_upstream: 1, monitored_weight: 0.01, upstream_weight: 3,
    no_feed_upstream: 0, stale_upstream: 12, feed_stale: [{company: 'United Utilities', overflows: 12, records: true}]}};
  assert.match(compareNow(thin), /^Not known here: the overflows that matter most here do not report live\. 0 discharging\. 1 of 13 report live\. Not reporting: 12 whose records on United Utilities's feed give no update time\. Missing reports do not mean no spills\.$/);
  assert.equal(compareNow({...spot, now: {label: 'low', monitored_upstream: 2, discharging_upstream: 1}}), '1 of 2 discharging. All 2 report live.');
  // Today's EA advice: never read, so never said to be clear.
  const bw = {source: 'designated', classification: {class: 'good', year: 2025, url: 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj1403-11947'}};
  assert.equal(compareAdvice(bw), 'The Environment Agency&#39;s advice for today could not be checked. '
    + '<a href="https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj1403-11947">The EA\'s page</a> has any advice against bathing there today.');
  assert.match(compareAdvice({id: 'bw-ukj1403-11947', source: 'designated', classification: {class: 'good'}}), /could not be checked\. <a href="https:\/\/environment\.data\.gov\.uk\/bwq\/profiles\/profile\.html\?site=ukj1403-11947">/);
  assert.equal(compareAdvice({source: 'designated'}), 'Not known: this update has no Environment Agency page for this bathing water.');
  assert.equal(compareAdvice({source: 'openstreetmap'}), 'None: not a designated bathing water, so the Environment Agency gives no bathing advice for it.');
  // Access: the desk check's own words and its date, or none.
  assert.equal(compareAccess({}), 'No access information.');
  assert.equal(compareAccess({access: {status: 'unconfirmed', checked_at: '2026-10-03', text: 'Check the <b>signs</b> & the bank.', url: 'https://example.org/a"b'}}),
    'Check the &lt;b&gt;signs&lt;/b&gt; &amp; the bank. Desk check 2026-10-03; current signs not inspected. <a href="https://example.org/a&quot;b">Authority guidance</a>.');
  assert.equal(compareAccess({access: {status: 'restricted_guidance'}}), 'Swimming here is restricted: check the signs. Not known when it was checked.');
  assert.equal(compareAccess({access: {status: 'something new', checked_at: '2026-10-03', url: 'http://not-https.example'}}),
    'Not known whether swimming is allowed at this point. Desk check 2026-10-03; current signs not inspected.');
  // Every row of every column says something, and nothing calls a spot safe or the best.
  for (const s of [spot, {days: []}, {days: [], error: 'forecast failed: x'}, {...bw, ...spot, access: {status: 'unconfirmed'}}]) {
    const rows = compareRows(s, '2026-09-30');
    assert.deepEqual(rows.map(r => r[0]), ['Right now', 'Environment Agency rating', "Today's EA advice", 'Water samples', 'Algae observation', 'Access', 'Local warnings', 'Model limits']);
    for (const [label, html] of rows) {
      assert.ok(typeof html === 'string' && html.trim().length > 10, `${label}: ${html}`);
      assert.doesNotMatch(html, /\b(best|safest|safe to swim|clean)\b/i, label);
    }
  }
});
test('comparison excludes removed spots and duplicates and never exceeds three', () => {
  assert.deepEqual(comparisonIds(['a','a','old','b','c','d'],['a','b','c','d'].map(id=>({id}))),['a','b','c']);
});
const vm = require('node:vm');
const fs = require('node:fs');
const feedback = fs.readFileSync(require('node:path').join(__dirname,'../src/dipcast/pages/feedback.html'),'utf8');
const prepareSource = feedback.slice(feedback.indexOf('function prepareEmail('),feedback.indexOf("$('feedback-form').addEventListener"));
const context = vm.createContext({}); vm.runInContext(prepareSource,context);
test('feedback encodes user content without changing the recipient or adding mail headers', () => {
  const r = context.prepareEmail('spot','A&B','', 'Line 1\n&bcc=other@example.org <script>');
  const url = new URL(r.href);
  assert.equal(url.pathname,'hello@swimsignal.co.uk');
  assert.equal(url.searchParams.get('bcc'),null);
  assert.match(url.searchParams.get('body'), /Line 1\n&bcc=/);
  assert.match(r.text,/Spot request/);
});

// ------------------------------------------------------------------------------ headlines in one form
// A level says "risk" wherever it heads a line, and a later day is named in full (docs/DESIGN.md, Words).
const L = require('../src/dipcast/site/levels.js');
const DATES = ['2026-09-30', '2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04'];
const week = (labels, extra = {}) => ({upstream_summary:{overflows:2}, location:{mode:'river'}, now:{label:'low'}, ...extra,
  days: labels.map((l, i) => ({date: DATES[i], label: l, risk: {low:0.05, moderate:0.2, high:0.5, 'very high':0.8}[l],
    p_ecoli_gt900: 0.02, in_validated_season: false}))});
test('a picked day reads "X risk" at every level, with what set it when raised', () => {
  const s = week(['low', 'moderate', 'high', 'very high', 'low']);
  assert.deepEqual(DATES.slice(0, 4).map(iso => L.dayHeadline(s, iso)),
    ['Low risk', 'Moderate risk: sewage spills', 'High risk: sewage spills', 'Very high risk: sewage spills']);
});
test('a later worse day is named by its full weekday, in the headline and in where the week goes', () => {
  const s = week(['low', 'low', 'low', 'high', 'low']);   // 3 October 2026 is a Saturday
  assert.equal(L.headline(s), 'Low risk now · High risk on Saturday');
  assert.equal(L.weekNext(s), 'High risk on Saturday');
});
test('where the week goes starts at today when the level comes from right now', () => {
  const now = week(['low', 'low', 'low', 'low', 'low'], {now:{label:'moderate'}});
  assert.equal(L.headline(now), 'Moderate risk right now: sewage spills');
  // Today is at least right now since 11 Oct 2026 (levels.js, risk), so today is moderate too and the
  // level falls tomorrow. Until then this read "Low risk later today" over a "Today: Moderate" row.
  assert.equal(L.dayLevel(now, DATES[0]), 'moderate');
  assert.equal(L.weekNext(now), 'Low risk tomorrow');
  assert.equal(L.weekNext(week(['high', 'low', 'low', 'low', 'low'])), 'Low risk tomorrow');
  assert.equal(L.weekNext(week(['high', 'high', 'moderate', 'low', 'low'])), 'Low risk by Saturday');
  assert.equal(L.weekNext(week(['high', 'high', 'high', 'high', 'high'])), 'High risk on all five days');
  assert.equal(L.weekNext(week(['low', 'low', 'low', 'low', 'low'], {classification:{class:'poor'}})),
    'At least high risk every day');
});
test('where the week goes starts after where the level came from, not the first day that shares it', () => {
  // Greenholme on 4 Oct 2026: right now moderate, and Sunday's moderate came after it. The search began
  // after Sunday, found nothing, and the line was blank.
  // Since 11 Oct 2026 a worse later day comes first, in the headline and in where the week goes.
  const greenholme = week(['low', 'low', 'high', 'very high', 'moderate'], {now:{label:'moderate'}});
  assert.equal(L.headline(greenholme), 'Moderate risk right now: sewage spills · Very high risk on Saturday');
  assert.equal(L.weekNext(greenholme), 'Very high risk on Saturday');
  assert.equal(L.weekNext(week(['low', 'low', 'high', 'moderate', 'moderate'], {now:{label:'moderate'}})), 'High risk on Friday');
  // Right now high and Thursday high: today is high too (today is at least right now), and the lowest after it is Friday's moderate.
  assert.equal(L.weekNext(week(['low', 'high', 'moderate', 'high', 'high'], {now:{label:'high'}})), 'Moderate risk by Friday');
  // No lower day: today is high with right now, so the level holds on all five days.
  assert.equal(L.weekNext(week(['moderate', 'high', 'high', 'high', 'high'], {now:{label:'high'}})), 'High risk on all five days');
  assert.equal(L.weekNext(week(['moderate', 'moderate', 'moderate', 'moderate', 'moderate'], {now:{label:'moderate'}})),
    'Moderate risk on all five days');
  // From tomorrow: the search starts after tomorrow even when today has no forecast, and a later day sharing it does not move it.
  assert.equal(L.weekNext(week(['low', 'high', 'moderate', 'high', 'low'])), 'Low risk by Sunday');
  const gap = week(['low', 'high', 'moderate', 'high', 'low']); gap.days[0] = {date: DATES[0], label: 'low', risk: null};
  assert.equal(L.weekNext(gap), 'Low risk by Sunday');
});

// ------------------------------------------------------------------------------ the page's own functions
// Top-level definitions taken from index.html's script and run beside levels.js and experience.js, as
// in the browser: a definition runs from its first line to the next line at the margin that does not
// close it.
const pageSrc = (() => { const html = fs.readFileSync(require('node:path').join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  return html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n'); })();
function pageDefs(names) {
  return names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
    assert.ok(i >= 0, `no ${n} in index.html`);
    let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
    return pageSrc.slice(i, j).join('\n'); }).join('\n');
}
function pageContext(names, extra = {}) {
  const dir = require('node:path').join(__dirname, '../src/dipcast/site/');
  const ctx = vm.createContext({...extra});
  vm.runInContext(fs.readFileSync(dir + 'experience.js', 'utf8'), ctx);
  vm.runInContext(fs.readFileSync(dir + 'levels.js', 'utf8') + '\nsetToday("2026-09-30");', ctx);
  vm.runInContext(pageDefs(names), ctx);
  return ctx;
}
test('the day-by-day table gives each day the level its row in the five days gives', () => {
  const ctx = pageContext(['esc', 'fmt', 'cls', 'dateLabel', 'glyph', 'ICON', 'ecoliCheck', 'dayTable']);
  const poor = week(['low', 'low', 'high', 'low', 'low'], {classification:{class:'poor'}});
  const table = vm.runInContext('d => dayTable(d, 2, false, {})', ctx)(poor);
  const cells = [...table.matchAll(/<span class="badge [\w-]+">([^<]+)<\/span>/g)].map(m => m[1]);
  assert.deepEqual(cells, poor.days.map(x => L.risk(poor, x).level).map(l => l.charAt(0).toUpperCase() + l.slice(1)));
  assert.deepEqual(cells, ['High', 'High', 'High', 'High', 'High']);   // the spills alone said Low on four of them
  assert.doesNotMatch(vm.runInContext('d => dayTable(d, 0, false, {})', ctx)({days: poor.days}), /class="badge/);   // nothing upstream
});
test('stored lists that are not lists, or hold odd entries, read as empty rather than stop the page', () => {
  const {storedList} = require('../src/dipcast/site/experience.js');
  for (const text of [null, '', 'not json', '"abc"', '42', '{"id":"a"}', 'null']) assert.deepEqual(storedList(text), [], String(text));
  assert.deepEqual(storedList('["a", 3, "b"]', x => typeof x === 'string'), ['a', 'b']);
  let stored = '{"id":"a"}';
  const ctx = pageContext([], {localStorage: {getItem: () => stored}});
  // The swim journal (journal.js), which reads the one-tap log's key; that log threw "swims(...).some is not a function" here.
  vm.runInContext(fs.readFileSync(require('node:path').join(__dirname, '../src/dipcast/site/journal.js'), 'utf8'), ctx);
  assert.equal(vm.runInContext('journalNow().length', ctx), 0);
  stored = '[null, 7, {"id":"a","date":"2026-09-30","level":"low"}]';
  assert.equal(vm.runInContext('journalNow().map(e => e.key + " " + e.level).join()', ctx), 'a@2026-09-30 low');
  // The saved spots, read with the lists (lists.js; site_lists.test.cjs has the rest).
  const {readLists} = require('../src/dipcast/site/lists.js');
  assert.deepEqual(readLists(null, '"abc"').lists[0].spots, []);   // a Set of a string was its letters
  assert.deepEqual(readLists(null, '["x", {"y":1}]').lists[0].spots, ['x']);
});
test('a river gauge reading over a day old is named, but not shown as the level now', () => {
  const ctx = pageContext(['esc', 'fmt', 'glyph', 'ICON', 'rangeBar', 'riverTile']);
  const tileOf = vm.runInContext('riverTile', ctx);
  const gauge = {station: 'Salisbury', river: 'River Avon', distance_km: 2.1, same_river: true, rloi: '1234',
    typical_low_m: 0.2, typical_high_m: 1.4, observed_at: '2026-09-02T09:00:00Z'};
  // Before the build marked old readings (no stale field): as it was.
  const now = tileOf({...gauge, level_m: 0.43, label: 'normal'});
  assert.equal(now.fig, '0.43');
  assert.equal(now.word, 'Usual level');
  assert.match(now.say, /^Not part of the pollution level\. Gauge at Salisbury on the River Avon, 2\.1&nbsp;km away, /);
  assert.equal(tileOf({...gauge, level_m: null}), null);   // no reading at all: no tile
  assert.equal(tileOf(null), null);
  // Stale, as attach_river_levels writes it: the value moved to last_level_m, the level cleared.
  const old = tileOf({...gauge, stale: true, age_hours: 708.4, last_level_m: 0.43, level_m: null, index: null, label: 'unknown'});
  assert.equal(old.fig, '–');
  assert.equal(old.word, undefined);
  assert.equal(old.vis, undefined);   // no range bar: there is no level now to place on it
  assert.match(old.say, /^Last reading 30 days ago, not shown as current\. Not part of the pollution level\. Gauge at Salisbury/);
  assert.match(old.more, /check-for-flooding\.service\.gov\.uk\/station\/1234/);
  assert.match(tileOf({...gauge, stale: true, age_hours: 30, level_m: null}).say, /^Last reading 1 day ago,/);
  assert.match(tileOf({...gauge, stale: true, age_hours: 50, level_m: null}).say, /^Last reading 2 days ago,/);
});
test('a water rated poor names the advice against bathing in its season only, by the day shown', () => {
  const poor = week(['low', 'low', 'low', 'low', 'low'], {classification:{class:'poor'}});
  assert.equal(L.inBathingSeason('2026-05-15'), true);
  assert.equal(L.inBathingSeason('2026-09-30'), true);
  assert.equal(L.inBathingSeason('2026-10-01'), false);
  assert.equal(L.inBathingSeason('2026-05-14'), false);
  // Today is 30 September, the season's last day; tomorrow is out of it. The level is high on both.
  // The level and its noun come first, then the reason (6 Oct 2026): "Rated poor" alone left 13 rows
  // with no level, and "from 15 May" read in October as though the advice began on that date.
  assert.equal(L.headline(poor), 'High risk: rated poor, advice against bathing');
  assert.equal(L.dayHeadline(poor, '2026-09-30'), 'High risk: rated poor, advice against bathing');
  assert.equal(L.dayHeadline(poor, '2026-10-01'), 'High risk: rated poor');
  assert.deepEqual(L.headParts(poor), ['High risk', 'rated poor, advice against bathing', '']);
  assert.equal(L.dayLevel(poor, '2026-10-01'), 'high');
  assert.match(L.poorAdvice('2026-09-30'), /^Advice against bathing applies here while the rating is poor/);
  assert.match(L.poorAdvice('2026-10-01'), /^The rating is poor, so the spot stays at high risk or worse; advice against bathing applies 15 May to 30 September\.$/);
  L.setToday('2026-10-02');
  try { assert.equal(L.headline({...poor, days: poor.days.map((x, i) => ({...x, date: ['2026-10-02','2026-10-03','2026-10-04','2026-10-05','2026-10-06'][i]}))}),
    'High risk: rated poor'); }   // what the alerts say, through headline()
  finally { L.setToday('2026-09-30'); }
});
test('the day table’s † note shows only while a cell carries a †', () => {
  const ctx = pageContext(['esc', 'fmt', 'cls', 'dateLabel', 'glyph', 'ICON', 'ecoliCheck', 'dayTable']);
  const off = week(['low', 'low', 'low', 'low', 'low']);   // every day out of season, with a figure
  const river = vm.runInContext('d => dayTable(d, 2, false, {})', ctx)(off);
  // The figures stay in this folded table out of season, marked †, and the note says they are experimental
  // (20 Oct 2026: the main view has none; levels.js, ECOLI_OFF).
  assert.match(river, /<sup>†<\/sup>Out of season: from October to April the Environment Agency takes no samples, so the estimate is untested, experimental and not part of the level\./);
  assert.match(river, /<td class="num">2%<sup>†<\/sup><\/td>/);
  const lake = vm.runInContext('d => dayTable(d, 2, true, {})', ctx)(off);   // the lake's cells read n/a
  assert.doesNotMatch(lake, /†/);
  const blank = vm.runInContext('d => dayTable(d, 2, false, {})', ctx)({days: off.days.map(x => ({...x, p_ecoli_gt900: null}))});
  assert.doesNotMatch(blank, /†/);
});

// ------------------------------------------------------------------------------ the plain levels
// Where the model has nothing to forecast: no monitored overflow within reach upstream, or a lake no
// river flows into. The level says so in words of its own, with one line under it and the rain.
const PAGE = ['esc', 'fmt', 'cls', 'dateLabel', 'glyph', 'ICON', 'tone', 'colour', 'headTone', 'initial', 'VIEW', 'km', 'dist', 'away',
  'PAGE_ID', 'spotPath', 'BOOKMARK', 'untested', 'week', 'rainMeta', 'rainSaid', 'answerParts', 'savedCard', 'mapLevel',
  'listHeadline', 'listPath', 'headNote', 'spotItem', 'markerTip', 'check', 'spilling', 'summary', 'daysSentence', 'ecoliCheck', 'dayTable'];
const plainCtx = () => pageContext(PAGE, {ROOT: {pathname: '/'}});
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
// A river with days but no contributors: the build still computes an E. coli figure for it (35% here).
const clearRiver = {id: 'birks', name: 'River Duddon, Birks Bridge', kind: 'river', source: 'curated', upstream_summary: {overflows: 0},
  location: {mode: 'river'}, now: {label: 'unknown', discharging_upstream: 0}, contributors: [], assumptions: {max_upstream_km: 60},
  days: DATES.map((date, i) => ({date, risk: 0, label: 'low', rain_48h_mm: [12.4, 3, 0, 18, 1][i], p_ecoli_gt900: 0.35, in_validated_season: false}))};
const isolatedLake = {id: 'henleaze', name: 'Henleaze Lake', kind: 'lake', source: 'designated', days: [], contributors: [],
  error: 'An isolated lake with no river connection in the network: storm overflows cannot reach it by water, so the forecast has nothing to say about it.',
  classification: {class: 'excellent', year: 2025, url: 'https://example.org/bw'}, assumptions: {max_upstream_km: 60}};

// Until 11 Oct 2026 "No sewage risk from monitored overflows", which read as no risk at all.
test('a spot with days but nothing upstream reads "No monitored overflow found upstream" on every surface', () => {
  const words = 'No monitored overflow found upstream';
  assert.equal(L.level(clearRiver), L.NO_OVERFLOWS);
  assert.equal(L.headline(clearRiver), words);
  assert.deepEqual(DATES.map(iso => L.dayHeadline(clearRiver, iso)), DATES.map(() => words));   // the list and map on a picked day
  assert.equal(L.dayLevel(clearRiver, DATES[1]), L.NO_OVERFLOWS);
  assert.equal(L.weekNext(clearRiver), '');
  const ctx = plainCtx(), run = (f, ...a) => vm.runInContext(f, ctx)(...a);
  // The answer: the words in the clear teal, the other risks under them, then the rain.
  const m = run('answerParts', clearRiver);
  assert.deepEqual([m.word, m.tone, m.head, m.sub, text(m.next)],
    [null, 'clear', words, 'Other risks apply: algae, wildlife, runoff and bathers. Check the signs at the water.', '12 mm of rain in the last two days']);
  assert.equal(run('colour', L.NO_OVERFLOWS), '#4aa39a');
  // The saved card, the list row and the map's tooltip say the same.
  const card = run('savedCard', clearRiver);
  assert.match(card, /<p class="big-head clear">No monitored overflow found upstream<\/p>/);
  assert.match(text(card), /Other risks apply: algae, wildlife, runoff and bathers\. Check the signs at the water\. 12 mm of rain in the last two days\./);
  assert.match(run('spotItem', clearRiver), /<span class="hl clear">No monitored overflow found upstream<\/span>/);
  assert.equal(run('markerTip', clearRiver), 'River Duddon, Birks Bridge: No monitored overflow found upstream');
  // No E. coli estimate anywhere: the model was fitted on sites with overflows upstream.
  assert.equal(L.ecoliBand(clearRiver, clearRiver.days[0]), null);
  const table = run('dayTable', clearRiver, 0, false, {});
  assert.doesNotMatch(table, /35%/);
  assert.match(table, /E\. coli not shown here<\/b>: estimated only on rivers with monitored overflows upstream/);
  // "Check the signs" once in view: the answer's line has it, so the five days' caveat does not repeat it.
  assert.equal(text(run('check', clearRiver)), 'A forecast, not a water test. This is not a designated bathing water, so the Environment Agency does not test it for bathing.');
  // A clicked point off the list is not checked against the bathing waters, so nothing is said about them.
  assert.equal(text(run('check', {...clearRiver, source: 'unlisted'})), 'A forecast, not a water test.');
  assert.equal(text(run('daysSentence', clearRiver)), 'No storm overflow is monitored within 60 km upstream, so the days show rain instead: rain washes in runoff from farms, roads and wildlife. '
    + 'The wettest day ahead is Saturday, with about 18 mm of rain in the 48 hours to midday.');
  // Today's rain is in the answer already, so the wettest day named is a later one, or none.
  const wetToday = {...clearRiver, days: clearRiver.days.map((x, i) => ({...x, rain_48h_mm: [30, 12, 0, 5, 1][i]}))};
  assert.match(text(run('daysSentence', wetToday)), /The wettest day ahead is tomorrow, with about 12 mm/);
  const dryAfter = {...clearRiver, days: clearRiver.days.map((x, i) => ({...x, rain_48h_mm: [30, 2, 0, 5, 1][i]}))};
  assert.doesNotMatch(text(run('daysSentence', dryAfter)), /wettest/);
});
test('the rain in the last two days is a plain sentence, and absent without a figure', () => {
  const ctx = plainCtx(), said = v => text(vm.runInContext('rainSaid', ctx)({days: [{rain_48h_mm: v}]}));
  assert.equal(said(0), 'No rain in the last two days');
  assert.equal(said(0.3), 'Under 1 mm of rain in the last two days');
  assert.equal(said(1.2), '1 mm of rain in the last two days');
  assert.equal(said(44.7), '45 mm of rain in the last two days');
  assert.equal(said(null), '');
  assert.equal(vm.runInContext('rainSaid', ctx)({days: []}), '');
});
test('a later peak in the sentence over the five days has its noun when today has no count', () => {
  // Greenholme, 11 Oct 2026: "A spill from a nearby overflow upstream is possible today, about 8 on Thursday."
  const ctx = plainCtx(), run = (f, ...a) => vm.runInContext(f, ctx)(...a);
  const peak = week(['moderate', 'low', 'low', 'high', 'low'], {upstream_summary: {overflows: 60}});
  peak.days.forEach((x, i) => { x.expected_spilling_overflows = [0.3, 0.2, 0.1, 8.2, 2][i]; });
  assert.match(text(run('daysSentence', peak)), /^A spill from a nearby overflow upstream is possible today\. About 8 of the 60 are expected to spill on \w+\. Back to low risk tomorrow\.$/);
  // With a count today, "about 8" follows it, as before.
  peak.days[0].expected_spilling_overflows = 3;
  assert.match(text(run('daysSentence', peak)), /^About 3 of the 60 overflows upstream are expected to spill today, about 8 on \w+\. Back to low risk tomorrow\.$/);
});
test('overflows discharging now: the sentence over the five days gives right now\'s level with "risk"', () => {
  // "exposure right now is moderate" left the level word bare (docs/DESIGN.md, Words).
  const ctx = plainCtx(), run = (f, ...a) => vm.runInContext(f, ctx)(...a);
  const two = week(['low', 'low', 'low', 'low', 'low'], {now: {label: 'moderate', discharging_upstream: 2}});
  assert.equal(run('summary', two)[0], '2 upstream overflows are discharging now: moderate risk from them right now.');
  assert.match(text(run('daysSentence', two)), /^2 upstream overflows are discharging now: moderate risk from them right now\. /);
  const one = week(['low', 'low', 'low', 'low', 'low'], {now: {label: 'low', discharging_upstream: 1}});
  assert.equal(run('summary', one)[0], '1 upstream overflow is discharging now: low risk from it right now.');
});
// Since 11 Oct 2026 the same words and the same teal as a spot with no overflow within reach: until then
// only 3 of the 12 lakes with nothing upstream read "No monitored overflow drains into this lake", in grey.
test('an isolated lake reads "No monitored overflow found upstream" in the clear teal, with the same line and no rain', () => {
  const words = 'No monitored overflow found upstream';
  assert.equal(L.level(isolatedLake), L.NO_RIVER);   // its excellent rating made it "low" before
  assert.equal(L.headline(isolatedLake), words);
  assert.equal(L.dayHeadline(isolatedLake, DATES[2]), words);
  assert.equal(L.coverage(isolatedLake), words);   // the page's spills row and the comparison
  const ctx = plainCtx(), run = (f, ...a) => vm.runInContext(f, ctx)(...a);
  const m = run('answerParts', isolatedLake);
  assert.deepEqual([m.word, m.tone, m.head, m.sub, m.next],
    [null, 'clear', words, 'Other risks apply: algae, wildlife, runoff and bathers. Check the signs at the water.', '']);
  assert.equal(run('colour', L.NO_RIVER), '#4aa39a');
  assert.match(run('savedCard', isolatedLake), /<p class="big-head clear">No monitored overflow found upstream<\/p>/);
  assert.match(run('spotItem', isolatedLake), /<span class="hl clear">No monitored overflow found upstream<\/span>/);
  assert.equal(run('markerTip', isolatedLake), `Henleaze Lake: ${words}`);
  // A designated water: the answer says the EA's advice could not be checked (unchecked), not this line.
  assert.equal(text(run('check', isolatedLake)), 'A forecast, not a water test.');
});
test('a rating or an algae check that raises the level still sets it; excellent or good does not', () => {
  const base = {...clearRiver, source: 'designated', location: {mode: 'lake'}};
  assert.equal(L.level({...base, classification: {class: 'good', year: 2025}}), L.NO_OVERFLOWS);
  const sufficient = {...base, classification: {class: 'sufficient', year: 2025}};
  assert.equal(L.level(sufficient), 'moderate');
  assert.equal(L.headline(sufficient), 'Moderate risk: rated sufficient by the Environment Agency');
  const poor = {...base, classification: {class: 'poor', year: 2025}};
  assert.equal(L.level(poor), 'high');
  assert.equal(L.headline(poor), 'High risk: rated poor, advice against bathing');
  const algae = {...base, classification: {class: 'excellent', year: 2025}, algae: {date: '2026-09-20', level: 3, phrase: 'enough to be objectionable'}};
  assert.equal(L.level(algae), 'high');
  assert.equal(L.headline(algae), 'High risk: algae at the last check');
  assert.equal(L.level({...algae, algae: {...algae.algae, date: '2026-09-01'}}), L.NO_OVERFLOWS);   // over 14 days old
  assert.equal(L.level({...isolatedLake, classification: {class: 'poor', year: 2025}}), 'high');
  // A spot with no water within reach (not an isolated lake) keeps the old rule.
  const away = {days: [], error: 'No river or lake within 1.5 km of this point.'};
  assert.equal(L.level(away), L.NOT_COVERED);
  assert.equal(L.level({...away, classification: {class: 'excellent'}}), 'low');
  assert.equal(L.headline(away), 'Not covered by the forecast');
});
test('the plain levels are not low risk: not in the low count, not offered as lower nearby', () => {
  assert.equal(L.rank(L.level(clearRiver)), -1);
  assert.equal(L.rank(L.level(isolatedLake)), -1);
  assert.equal(L.plainLevel(L.NO_OVERFLOWS) && L.plainLevel(L.NO_RIVER), true);
  assert.equal(L.plainLevel('low') || L.plainLevel(L.NO_FORECAST) || L.plainLevel(L.NOT_COVERED), false);
});

// ------------------------------------------------------------------------------ plan a swim
// Each row of a plan says why the spot is there (index.html, planWhy): what the day's level rests on,
// the rating, and what the level leaves out. Which spots, in which order, is plan.js (site_plan).
test('a plan row says what the level rests on, and why a spill expected on a low day does not raise it', () => {
  const now = new Date().toISOString();
  const ctx = pageContext(['esc', 'spilling', 'planWhy'], {DATA: {generated_at: now}}), why = (s, day) => vm.runInContext('planWhy', ctx)(s, day);
  const s = week(['low', 'high', 'low', 'low', 'low'], {upstream_summary: {overflows: 3}});
  s.days[0].expected_spilling_overflows = 1.2;
  s.days[1] = {...s.days[1], expected_spilling_overflows: 2.6, p_ecoli_gt900: 0.3, in_validated_season: true};
  assert.equal(why(s, DATES[0]), 'About 1 of the 3 overflows upstream is expected to spill, but sewage from them is unlikely to reach here.');
  assert.equal(why(s, DATES[1]), 'All 3 overflows upstream are expected to spill. 30% chance a sample would show E.\u00a0coli over 900 per 100\u00a0ml.');   // in season, so the estimate counts
  s.days[2].expected_spilling_overflows = 0.3;
  assert.equal(why(s, DATES[3]), '');   // no spill figure that day, and nothing else to say
  // The rating, unless the headline already gives it; access not confirmed; nothing upstream.
  assert.equal(why({...s, classification: {class: 'excellent', year: 2025}}, DATES[2]), 'Under one spill is expected from the 3 overflows upstream. Rated excellent by the Environment Agency for 2025.');
  assert.doesNotMatch(why({...s, classification: {class: 'poor', year: 2025}}, DATES[2]), /Rated poor/);
  assert.match(why({...s, access: {status: 'unconfirmed'}}, DATES[2]), /Permission to swim at this point is not confirmed\.$/);
  assert.equal(why({...clearRiver}, DATES[2]), 'No monitored storm overflow within 60\u00a0km upstream.');
  // On a plan for today, the river high at its gauge, with the gauge's name escaped.
  const high = {...s, flow_state: 'high', river_state: {station: 'Mill <b>', observed_at: now}};
  assert.match(why(high, DATES[0]), /River high: the gauge at Mill &lt;b&gt; is above its usual range\.$/);
  assert.doesNotMatch(why(high, DATES[1]), /River high/);   // not a forecast: only on a plan for today
});

// ------------------------------------------------------------------------------ the plan's day strip
// planStrip (index.html; 20 Oct 2026): the five days as radio buttons in one strip, the plan's day checked.
test('the day strip offers the five days as one group of radio buttons, the plan\'s day checked', () => {
  const html = vm.runInContext('planStrip', pageContext(['planStrip']))(DATES, DATES[3]);
  assert.match(html, /^<fieldset class="day-strip"><legend class="sr">Day<\/legend>/);
  const radios = [...html.matchAll(/<label><input type="radio" name="plan-day" value="([\d-]+)"( checked)?><span>([^<]+)<span class="dd">([^<]+)<\/span><\/span><\/label>/g)]
    .map(m => [m[1], !!m[2], m[3].trim(), m[4]]);
  assert.deepEqual(radios.map(r => r.slice(0, 3)), [['2026-09-30', false, 'Today'], ['2026-10-01', false, 'Thu'], ['2026-10-02', false, 'Fri'],
    ['2026-10-03', true, 'Sat'], ['2026-10-04', false, 'Sun']]);
  assert.deepEqual(radios.map(r => r[3].split(' ')[0]), ['30', '1', '2', '3', '4']);   // the date under each ("1 Oct"; ICU's month)
  assert.equal((html.match(/ checked/g) || []).length, 1);
});

// ------------------------------------------------------------------------------ right now, after the spills stop
// A spill counts until 48 h after its water has passed, so right now can be raised with nothing upstream
// discharging. Eden at Armathwaite, 4 Oct 2026: "Moderate risk right now: sewage spills" over "0 of 60 discharging".
test('right now raised with nothing discharging says the spills are recent', () => {
  const recent = week(['low', 'low', 'low', 'low', 'low'], {now: {label: 'moderate', discharging_upstream: 0}});
  assert.equal(L.headline(recent), 'Moderate risk right now: recent sewage spills');
  assert.equal(L.headline(week(['low', 'low', 'low', 'low', 'low'], {now: {label: 'moderate', discharging_upstream: 2}})),
    'Moderate risk right now: sewage spills');
  assert.equal(L.headline(week(['moderate', 'low', 'low', 'low', 'low'], {now: {label: 'low', discharging_upstream: 0}})),
    'Moderate risk today: sewage spills');   // a day's forecast is about spills to come, not recent ones
  const m = vm.runInContext('answerParts', plainCtx())(recent);
  assert.equal(m.sub, 'Recent sewage spills');   // a saved card's line, under "Moderate risk"
  // The answer names the spills in its headline (20 Oct 2026), so its line says they are recent, and when.
  assert.deepEqual([m.noun, m.why], ['risk from sewage spills', 'Recent spills, right now']);
  assert.equal(m.next, 'Low risk tomorrow');   // today is at least right now (11 Oct 2026): "later today" before
  assert.equal(L.dayHeadline(recent, DATES[0]), 'Moderate risk: recent sewage spills');
});

// ------------------------------------------------------------------------------ the comparison's table
// compareTable (index.html), run beside levels.js, experience.js, evidence.js and eatoday.js, as in the page.
test('the comparison has a column a spot, the five days first with the day picked shaded, one cell for a level that does not change, and no blank', () => {
  const dir = require('node:path').join(__dirname, '../src/dipcast/site/');
  const ctx = pageContext(['esc', 'tone', 'dateLabel', 'PAGE_ID', 'spotPath', 'ago', 'ageMin', 'issued', 'compareTable'],
    {ROOT: {pathname: '/'}, DATA: {generated_at: '2026-09-30T06:00:00+01:00'}, fiveDays: () => DATES});
  for (const f of ['evidence.js', 'eatoday.js']) vm.runInContext(fs.readFileSync(dir + f, 'utf8'), ctx);
  const a = {...week(['low', 'high', 'low', 'low', 'low']), id: 'a', name: 'River <A>', now: {label: 'low', monitored_upstream: 2, discharging_upstream: 0}};
  const b = {...week(['low', 'low', 'low', 'low']), id: 'b', name: 'B'};   // no fifth day
  const html = vm.runInContext('compareTable', ctx)([a, b, clearRiver], DATES[1], s => `${s.id} away`);
  // Each row's label is a band across the three columns.
  assert.deepEqual([...html.matchAll(/<tr class="lab"><th colspan="3" id="[\w-]+"><span>([^<]+)<\/span><\/th><\/tr>/g)].map(m => m[1]),
    ['Pollution risk, next five days', 'Right now', 'Environment Agency rating', "Today's EA advice", 'Water samples', 'Algae observation', 'Access',
      'Local warnings', 'Model limits']);
  // The five days, each cell naming its day; the day picked (tomorrow here) shaded.
  assert.deepEqual([...html.matchAll(/<tr( class="on" aria-current="true")?><td class="d0" headers="cmp-days cmp-s0"><span class="day">([^<]+)<\/span>/g)].map(m => [m[2], !!m[1]]),
    [['Today', false], ['Tomorrow', true], ['Fri 2 Oct', false], ['Sat 3 Oct', false], ['Sun 4 Oct', false]]);
  assert.match(html, /<span class="day">Tomorrow<\/span><span class="hl high">High risk: sewage spills<\/span>/);
  // B has no fifth day: it says so, in the muted grey, not "Low risk".
  assert.match(html, /<td headers="cmp-days cmp-s1"><span class="day">Sun 4 Oct<\/span><span class="hl na">No forecast for this day<\/span><\/td><\/tr>/);
  // The river with nothing upstream: one cell for the five days, in the plain level's words, never "Low risk".
  assert.equal([...html.matchAll(/rowspan="5"/g)].length, 1);
  assert.match(html, /<td class="same" rowspan="5" headers="cmp-days cmp-s2"><span class="hl clear">No monitored overflow found upstream<\/span>\. The same on every day\.<\/td>/);
  assert.doesNotMatch(html, /<td[^>]*>\s*<\/td>/);
  assert.equal([...html.matchAll(/<td headers="cmp-r\d cmp-s\d">/g)].length, 8 * 3);   // every fact, every spot
  assert.match(html, />River &lt;A&gt;<\/a><span class="k">a away<\/span>/);
  assert.match(html, /^<p class="small muted compare-note">Issued [^<]*\. A lower forecast level does not mean safe water: check the signs at the water\.<\/p>/);
  // The question is which spots to look into further: no column is called the best or the safest.
  assert.doesNotMatch(html + pageDefs(['compareSection', 'compareTable', 'savedCompare', 'planCompare']), /\b(best|safest|safer)\b/i);
});

// Saved's comparison opens as the plan's does (plan.js, planCompareIds): the first three saved spots. Until
// 20 Oct 2026 it took two, and kept what it took first, so one spot saved and then two more compared one.
test('Saved compares the first three saved spots, and saving more fills a comparison of one', () => {
  const ctx = pageContext(['COMPARE', 'savedCompare'], {planCompareIds: require('../src/dipcast/site/plan.js').planCompareIds,
    fiveDays: () => ['2026-09-30'], VIEW: {day: null}});
  const run = vm.runInContext('ids => savedCompare(ids.map(id => ({id}))).ids', ctx), pick = ids => [...run(ids)];   // an array of this realm, for deepEqual
  assert.deepEqual(pick(['a']), ['a']);                               // one saved: the page offers no comparison
  assert.deepEqual(pick(['a', 'b', 'c', 'd']), ['a', 'b', 'c']);      // three more saved: the first three
  vm.runInContext('COMPARE.ids = ["d", "b"]', ctx);                   // two chosen: kept while both are saved
  assert.deepEqual(pick(['a', 'b', 'c', 'd']), ['d', 'b']);
  assert.deepEqual(pick(['a', 'c', 'd']), ['d', 'a', 'c']);           // one of them unsaved: filled from the top
});

// ------------------------------------------------------------------------------ Saved: day by day
// The Saved page's grid (second outside review, 20 Oct 2026): a cell a day at each saved spot, the level with
// its noun, "No forecast" for a missing day, and one cell for a level that does not change from day to day.
test('the day-by-day cells give each day its level with "risk", say "No forecast" for a missing day, and never make a plain level low', () => {
  const {weekCells} = require('../src/dipcast/site/experience.js');
  const four = week(['low', 'moderate', 'high', 'very high']);   // no fifth day
  assert.deepEqual(weekCells(four, DATES).cells.map(c => [c.words, c.rule, c.said]), [
    ['Low risk', true, 'Low risk'], ['Moderate risk', true, 'Moderate risk: sewage spills'], ['High risk', true, 'High risk: sewage spills'],
    ['Very high risk', true, 'Very high risk: sewage spills'], ['No forecast', false, 'No forecast for this day']]);
  assert.equal(weekCells(four, DATES).same, false);
  // Nothing upstream: one cell for the five days, the plain level's words, no level's rule.
  assert.deepEqual(weekCells(clearRiver, DATES), {same: true, level: 'no overflows', rule: false, words: 'No monitored overflow found upstream',
    said: 'No monitored overflow found upstream', cells: []});
  assert.deepEqual(weekCells(isolatedLake, DATES).words, 'No monitored overflow found upstream');
  // A standing rating is a level on every day: one cell, with its rule. A failed forecast is not.
  assert.deepEqual(weekCells({days: [], classification: {class: 'poor'}}, DATES), {same: true, level: 'high', rule: true,
    words: 'High risk: rated poor, advice against bathing', said: 'High risk: rated poor, advice against bathing', cells: []});
  const failed = weekCells({days: [], error: 'forecast failed: x', upstream_summary: {overflows: 3}}, DATES);
  assert.deepEqual([failed.same, failed.rule, failed.words], [true, false, 'No forecast in this update']);
});
test('each day-by-day cell opens the spot on its day, and a spot whose level does not change opens without one', () => {
  const ctx = pageContext(['esc', 'tone', 'dateLabel', 'PAGE_ID', 'spotPath', 'savedGrid'], {ROOT: {pathname: '/'}, fiveDays: () => DATES});
  const a = {...week(['low', 'high', 'low', 'low']), id: 'wharfe-a', name: 'Wharfe <A>'};
  const html = vm.runInContext('savedGrid', ctx)([a, {...clearRiver}]);
  assert.deepEqual([...html.matchAll(/<span role="columnheader">([^<]+)<\/span>/g)].map(m => m[1]), ['Today', 'Thu', 'Fri', 'Sat', 'Sun']);
  const cells = [...html.matchAll(/<a class="([^"]*)" href="([^"]+)" data-id="([^"]+)"(?: data-day="([^"]+)")? aria-label="([^"]+)">([^<]+)<\/a>/g)]
    .map(m => ({cls: m[1], href: m[2], id: m[3], day: m[4], label: m[5], text: m[6]}));
  assert.equal(cells.length, 6);
  assert.deepEqual(cells.slice(0, 5).map(c => [c.href, c.day, c.text, c.cls]), [
    ['/spot/wharfe-a/#day=2026-09-30', '2026-09-30', 'Low risk', 'lv low'], ['/spot/wharfe-a/#day=2026-10-01', '2026-10-01', 'High risk', 'lv high'],
    ['/spot/wharfe-a/#day=2026-10-02', '2026-10-02', 'Low risk', 'lv low'], ['/spot/wharfe-a/#day=2026-10-03', '2026-10-03', 'Low risk', 'lv low'],
    ['/spot/wharfe-a/#day=2026-10-04', '2026-10-04', 'No forecast', 'na']]);
  assert.equal(cells[1].label, 'Wharfe &lt;A&gt;, Tomorrow: High risk: sewage spills');   // the visible words are in the name it is read by
  // The river with nothing upstream: one cell across the five days, to its page with no day, in the plain words.
  assert.deepEqual([cells[5].href, cells[5].day, cells[5].text, cells[5].cls], ['/spot/birks/', undefined, 'No monitored overflow found upstream', 'clear']);
  assert.match(html, /<span class="wg-cell wg-all" role="cell"><a class="clear" href="\/spot\/birks\/"/);
  assert.match(html, /<span class="wg-name" role="rowheader"><a href="\/spot\/wharfe-a\/" data-id="wharfe-a">Wharfe &lt;A&gt;<\/a><\/span>/);
  assert.equal(vm.runInContext('savedGrid', ctx)([]), '');
});
