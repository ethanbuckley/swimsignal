// verification.html's plain figures: the warnings tables at the top and the service record. The page's
// script runs in a sandbox with a fake document and the data a build writes (forecast_log.warning_table,
// forecast_log.service_record).
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/pages/verification.html'), 'utf8');
const src = html.match(/<script>([\s\S]*?)<\/script>/)[1];

const SPILL = {warn_at: 0.4, level: 'high', unit: 'overflow-day forecast', n: 23395, hits: 152, misses: 573, false_alarms: 211,
  quiet_correct: 22459, hit_rate: 152 / 725, warnings_true: 152 / 363, share_correct: 22611 / 23395, always_no_correct: 22670 / 23395,
  base_rate: 725 / 23395, warning_lift: (152 / 363) / (725 / 23395),
  n_overflow_days: 4695, n_spill_overflow_days: 145, n_days: 5, first_day: '2026-09-29', last_day: '2026-10-03', by_lead: []};
const ECOLI = {warn_at: 0.25, level: 'high', unit: 'sample', kind: 'river', n: 15, hits: 0, misses: 1, false_alarms: 2, quiet_correct: 12,
  hit_rate: 0, warnings_true: 0, share_correct: 0.8, always_no_correct: 14 / 15, n_sites: 11, n_lake_samples_left_out: 9,
  base_rate: 1 / 15, warning_lift: 0,
  leads: {0: 15}, first_day: '2026-09-16', last_day: '2026-09-22', too_few_to_judge: true};
const SERVICE = {scheduled_per_day: 48, decision_hour_local: 8,
  runs: {from_day: '2026-09-17', to_day: '2026-10-03', n_days: 17, n: 148, scheduled_per_day: 48, scheduled: 816, share_of_scheduled: 148 / 816,
         per_day_median: 7, per_day_min: 5, per_day_max: 16, days_without_run: [], median_gap_h: 2.6, max_gap_h: 7.71, max_gap_ended: '2026-09-28T17:51+01:00'},
  feeds: {from_day: '2026-09-17', to_day: '2026-10-03', n_polls: 148, n_down: 1,
          companies: [{company: 'Anglian Water', polls: 148, down: 0}, {company: 'Yorkshire Water', polls: 148, down: 1}], down_at: []},
  morning: {from_day: '2026-09-17', to_day: '2026-10-03', n_days: 17, n_with_forecast: 17, days_without: []},
  builds: {since: '2026-10-04T00:16+01:00', n: 2, n_published: 1, by_event: {schedule: 2}, spots_attempted: 105, spots_forecast: 105,
           share_forecast: 1, runs_every_spot: 1, worst: null, not_published: [{at: '2026-10-04T03:00+01:00', why: 'only 3/105 spots got a forecast'}]}};

async function render(data) {
  const els = {};
  const document = {getElementById: id => (els[id] = els[id] || {innerHTML: ''}), querySelectorAll: () => [],
    querySelector: () => ({dataset: {}})};   // <main>, without the build's data-built: the page draws
  vm.runInNewContext(src, {document, location: {hash: ''}, fetch: async () => ({json: async () => data}), console});
  for (let i = 0; i < 5; i++) await new Promise(r => setImmediate(r));
  return els;
}
const OVERALL = {calibrated: {brier: 0.027179383407959886}, climatology_brier: 0.03790110339176735};   // 4 Oct: 28% lower error
const live = (extra = {}) => ({live: {generated_at: '2026-10-04T00:15:52+01:00', n_scored: 0, ...extra}});
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ');

test('the spill figures lead, and the share right sits beside the always-no share in one sentence', async () => {
  const a = text((await render({...live({warning_table: SPILL, overall: OVERALL})})).answer.innerHTML);
  // Short sentences, one idea each.
  assert.match(a, /the spill forecast warned of 21% of spills\. As a yes-or-no warning at the High risk line, it misses most\. When it warned/);
  // Read as a chance: after the tables, against the long-run rate (and the flat forecast where the data has it).
  assert.match(a, /Read as a chance, its error is 28% lower than each overflow's long-run rate\./);
  assert.match(a, /When it warned, a spill followed 42% of the time, against 3\.1% across all forecasts\. A warning made a spill about 14 times as likely\./);
  assert.match(a, /against 96\.9% for saying "no spill" every time\. Spills are rare, so a share right says little on its own\./);
  const sentence = a.split(/(?<=\.) /).find(s => s.includes('96.6%'));
  assert.ok(sentence.includes('96.9%') && sentence.includes('"no spill" every time'), sentence);
  assert.match(a, /That is 5 days of scores between 29 Sept? 2026 and 3 Oct 2026, too few to judge across different weather\./);
  assert.match(a, /152 hits 211 false alarms/);
  assert.match(a, /573 misses 22,459 correct quiet days/);
  assert.match(a, /spill chance of 40% or more/);
  // Wessex's figure is named as a different measure, never set against the share right.
  const wessex = a.split(/(?<=\.) /).filter(s => s.includes('87.8%'));
  assert.equal(wessex.length, 1);
  assert.ok(!/96\.\d%/.test(wessex[0]) && /do not compare/.test(a));
  assert.match(wessex[0], /came true \(42% here\)/);
});

test('a live error no better than the long-run rate is said so, and a rare base rate keeps a decimal', async () => {
  const worse = {calibrated: {brier: 0.05}, climatology_brier: 0.04};
  const rare = {...SPILL, base_rate: 0.004, warning_lift: 1.4};
  const a = text((await render({...live({warning_table: rare, overall: worse})})).answer.innerHTML);
  assert.match(a, /Read as a chance, its error is no lower than each overflow's long-run rate\./);
  assert.match(a, /against 0\.4% across all forecasts\. A warning made a spill 1\.4 times as likely/);
  const none = text((await render({...live({warning_table: {...SPILL, hits: 0, false_alarms: 0, warnings_true: null, warning_lift: null}})})).answer.innerHTML);
  assert.match(none, /It gave no warnings\./);
});

test('too few E. coli samples show counts and say so, with no percentages', async () => {
  const a = text((await render({...live({warning_table: SPILL, ecoli_live: {warning_table: ECOLI}})})).answer.innerHTML);
  const ecoli = a.slice(a.indexOf('The E. coli estimate'));
  assert.match(ecoli, /15 Environment Agency samples at 11 bathing waters, 1 of them over 900/);
  assert.match(ecoli, /warned before 2 samples, none of them over 900\./);
  const one = text((await render({...live({ecoli_live: {warning_table: {...ECOLI, hits: 1, misses: 0, false_alarms: 2}}})})).answer.innerHTML);
  assert.match(one, /warned before 3 samples: 1 over 900 and 2 not\./);
  const quiet = text((await render({...live({ecoli_live: {warning_table: {...ECOLI, false_alarms: 0}}})})).answer.innerHTML);
  assert.match(quiet, /The estimate gave no warnings\. It gave no warning before the one over 900\./);
  assert.match(ecoli, /no warning before the one over 900\. Too few to judge\./);
  assert.match(ecoli, /no new samples come until May/);   // October: out of season
  assert.ok(!/\d%(?! or more)/.test(ecoli.split('A warning is')[0]), ecoli);
  assert.match(ecoli, /9 lake samples are left out/);
});

test('enough E. coli samples get the shares, the always-no share beside the share right', async () => {
  const many = {...ECOLI, n: 300, hits: 12, misses: 18, false_alarms: 30, quiet_correct: 240, hit_rate: 0.4, warnings_true: 12 / 42,
                share_correct: 252 / 300, always_no_correct: 270 / 300, base_rate: 30 / 300, warning_lift: (12 / 42) / (30 / 300), too_few_to_judge: false};
  const a = text((await render({...live({ecoli_live: {warning_table: many}})})).answer.innerHTML);
  assert.match(a, /warned before 40% of those over 900\. When it warned, the sample was over 900 29% of the time, against 10% of all samples\. A warning made a sample over 900 about 3 times as likely\./);
  assert.match(a, /right on 84\.0% of samples, against 90\.0% for never warning/);
  assert.ok(!/Too few/.test(a));
});

test('shares that round alike get a second decimal place', async () => {
  const close = {...SPILL, share_correct: 0.9691, always_no_correct: 0.9694};
  const a = text((await render({...live({warning_table: close})})).answer.innerHTML);
  assert.match(a, /right on 96\.91% of forecasts, against 96\.94%/);
});

test('the held-out ranking is pairs, never a percentage that reads as a share of forecasts right', async () => {
  // The 2025 test as verification.json carries it: AUC 0.93, 33% lower error.
  const ho = {model: 'dipcast', n: 826725, brier: 0.0661, log_loss: 0.24, auc: 0.9312, brier_skill_vs_clim: 0.331};
  const els = await render({...live({warning_table: SPILL, overall: OVERALL}), holdout: [ho]});
  const top = text(els.top.innerHTML), t = text(els.short.innerHTML);
  assert.match(top, /Pairs ranked the right way round 93 in 100 A ranking of spill days above dry days, not a share of forecasts right: United Utilities, 2025, a year the model never saw\./);
  assert.ok(!/93%/.test(top), top);
  assert.match(t, /the error was 33% lower than always forecasting each overflow's long-run rate\. Given one day that spilled and one that did not, it gave the spill the higher chance 93 times in 100\./);
  assert.ok(!/93%/.test(t) && !/ranked above/.test(t), t);
});

test('a data file from before these fields still renders, with no warnings section', async () => {
  const els = await render({...live()});
  assert.equal(els.answer.innerHTML, '');
  assert.ok(els.live.innerHTML.includes('Live scoring of issued forecasts'));
  assert.ok(!els.live.innerHTML.includes('Did the forecast run on time?'));
});

test('the service record: runs against the schedule, the morning forecast, feeds and spots', async () => {
  const t = text((await render({...live(), service: SERVICE})).live.innerHTML);
  assert.match(t, /Did the forecast run on time\?/);
  assert.match(t, /148 in 17 days, a median of 7 a day: 18% of the 816 the schedule asks for/);
  assert.match(t, /Longest wait between runs 7\.7 h/);
  assert.match(t, /Days with a forecast out by 08:00 17 of 17/);
  assert.match(t, /Yorkshire Water in 1 of 148 runs; the other one answered every run/);
  assert.match(t, /105 of 105 \(100%\), over 1 run since/);
  // Nearly all is not all: three failures in 1,470 keep a decimal.
  const most = {...SERVICE, builds: {...SERVICE.builds, spots_attempted: 1470, spots_forecast: 1467, share_forecast: 1467 / 1470}};
  assert.match(text((await render({...live(), service: most})).live.innerHTML), /1,467 of 1,470 \(99\.7%\)/);
  assert.match(t, /Runs that stopped before publishing 1 of 2 since .*only 3\/105 spots got a forecast/);
});

test('model versions are listed in the order they were issued, the unstamped days first', async () => {
  const v = (version, first_day) => ({version, first_day, last_day: first_day, n: 10, base_rate: 0.03, brier_cal: 0.02, climatology_brier: 0.03});
  const overall = {calibrated: {brier: 0.027, auc: 0.84, base_rate: 0.031}, raw: {brier: 0.028, auc: 0.84}, climatology_brier: 0.038};
  const t = text((await render({...live({n_scored: 40, overall, by_version: [v('code=0.1.0+1598635', '2026-09-29'), v('code=0.1.0+6168e76', '2026-10-02'),
    v('code=0.1.0+9f02c3a', '2026-10-01'), v('unstamped (stamps begin 2026-09-28)', '2026-09-25')]})})).live.innerHTML);
  const at = s => t.indexOf(s);
  assert.ok(at('unstamped') < at('1598635') && at('1598635') < at('9f02c3a') && at('9f02c3a') < at('6168e76'), t);
});

// The red-team review of 11 Oct 2026, on the live data of that evening: forecasts were called overflow-days, the
// climatology's AUC was printed as 0.500, a span of days was counted as days, the warnings were mostly one
// company's, and the error was said against the long-run rate alone, which ran high.
const wc = (company, spills, hits, warnings) => ({company, hits, misses: spills - hits, false_alarms: warnings - hits, quiet_correct: 1000});
const OCT11 = {
  n_scored: 48090, generated_at: '2026-10-11T20:15:46+01:00', coverage_from: '2026-09-29',
  scoring_window: {first_scored_day: '2026-09-29', last_scored_day: '2026-10-10', n_scored_days: 10, n_uncovered: 19457,
    days_not_scored: [{day: '2026-10-08', reason: 'min_known_polls', n_candidates: 5000}, {day: '2026-10-09', reason: 'min_known_polls', n_candidates: 5000}]},
  missed_deadline: {n: 5828, share_of_candidates: 0.0436, issue_days: []},
  overall: {calibrated: {brier: 0.024942, auc: 0.835, base_rate: 0.02776}, raw: {brier: 0.025384, auc: 0.834}, climatology_brier: 0.034929,
    climatology_auc: 0.7567, climatology_mean: 0.09717, period_base_rate_brier: 0.02699, mean_forecast: 0.0344},
  warning_table: {...SPILL, n: 48090, hits: 223, misses: 1112, false_alarms: 337, hit_rate: 223 / 1335, n_overflow_days: 9773,
    n_spill_overflow_days: 270, n_days: 10, first_day: '2026-09-29', last_day: '2026-10-10', trained_on: 'United Utilities',
    by_company: [wc('United Utilities', 697, 208, 474), wc('Yorkshire Water', 220, 8, 23), wc('Anglian Water', 127, 0, 8),
      wc('Severn Trent Water', 125, 0, 6), wc('Wessex Water', 95, 7, 22), wc('Northumbrian Water', 23, 0, 0), wc('Thames Water', 20, 0, 9),
      wc('South West Water', 18, 0, 2), wc('Southern Water', 10, 0, 16)]},
  by_company: [['Wessex Water', 0.008366, 0.007742], ['Thames Water', 0.005052, 0.002313], ['Anglian Water', 0.020846, 0.019916],
    ['Yorkshire Water', 0.035069, 0.036045], ['United Utilities', 0.09118, 0.105574], ['Severn Trent Water', 0.023374, 0.02421],
    ['Southern Water', 0.009093, 0.002954], ['Northumbrian Water', 0.04244, 0.04491], ['South West Water', 0.041156, 0.037599]]
    .map(([company, brier_cal, flat_brier]) => ({company, brier_cal, flat_brier, sites: 1, n: 100, base_rate: 0.03, mean_forecast: 0.03, skill: 0.1, auc: 0.8})),
  coverage_sensitivity: {default: {max_gap_h: 8, n: 48090, base_rate: 0.0278, brier_cal: 0.0249, climatology_brier: 0.0349},
    strict: {max_gap_h: 6, n: 18581, base_rate: 0.0159, brier_cal: 0.0156, climatology_brier: 0.0272}},
};

test('11 Oct 2026: forecasts are not overflow-days, and the days are counted, with the missing ones named', async () => {
  const els = await render({live: OCT11});
  const a = text(els.answer.innerHTML), l = text(els.live.innerHTML), s = text(els.short.innerHTML);
  assert.match(a, /That is 10 days of scores between 29 Sept? 2026 and 10 Oct 2026, too few to judge across different weather\. 8 and 9 October are missing: too few runs to observe the overflows six times a day, as the scoring rule needs\./);
  assert.match(a, /The 48,090 forecasts are for 9,773 overflow-days\./);
  assert.match(l, /48,090 forecasts scored, for 9,773 overflow-days on 10 days from 29 Sept? 2026/);
  assert.match(s, /48,090 forecasts scored, for 9,773 overflow-days on 10 days from 29 Sept? 2026/);
  assert.match(s, /10 days are too few to judge/);
  assert.ok(!/48,090 overflow-days|19,457 candidate overflow-days|5,828 overflow-days|12 target days/.test(a + l + s));
  assert.match(l, /5,828 forecasts, 4\.4% of candidates/);
  assert.match(l, /19,457 candidate forecasts were not scored/);
});

test('11 Oct 2026: the climatology row has its own AUC, and the error is said against both baselines', async () => {
  const els = await render({live: OCT11});
  const a = text(els.answer.innerHTML), l = text(els.live.innerHTML), s = text(els.short.innerHTML);
  assert.match(l, /Climatology \(each overflow's long-run rate, averaging 9\.7% a day; spill rate in this period 2\.8%\) 0\.0349 0\.757 0\.00/);
  assert.ok(!/Climatology [^)]*\) 0\.0349 0\.500/.test(l));
  assert.match(a, /Read as a chance, its error is 29% lower than each overflow's long-run rate\. That rate is an easy test here: it averaged 9\.7% a day, against 2\.8% observed\. A flat forecast at the period's own rate, 2\.8% every day, is harder to beat\. Against it the error is 7\.6% lower\./);
  assert.match(a, /At 5 of the 9 companies, that flat forecast scored better than SwimSignal\./);
  assert.match(text(els.top.innerHTML), /Lower error, live 29% Read as a chance, against each overflow's long-run rate, and 7\.6% lower against a flat forecast at this period's own rate\./);
  assert.match(s, /which ran high: 9\.7% a day against 2\.8% observed\. It is 7\.6% lower than a flat forecast at this period's own rate\./);
});

test('11 Oct 2026: the warnings by company, and plainly that outside United Utilities the High line has caught few spills', async () => {
  const els = await render({live: OCT11});
  const a = text(els.answer.innerHTML), s = text(els.short.innerHTML);
  assert.match(a, /208 of the 223 warnings that came true were at United Utilities, the one company the spill model learned from\. At the other 8 companies, 638 forecasts were for a day with a spill, and 15 of them were warnings\. So outside United Utilities, the High risk line has caught few spills so far\. At 5 of them, every warning it gave was a false alarm\./);
  assert.match(a, /Company Spill days Warned of Warnings False alarms United Utilities 697 208 474 266 Yorkshire Water 220 8 23 15 Anglian Water 127 0 8 8/);
  assert.match(a, /Southern Water 10 0 16 16/);
  assert.match(s, /Live warnings, mostly at one company: 208 of the 223 warnings that came true were at United Utilities, where the spill model was trained\. At the other companies, 15 of 638 forecasts for a day with a spill were warnings\./);
  // The summary's one line: shares warned of, and the range among companies with 100 or more spill forecasts.
  assert.match(text(els.top.innerHTML), /By company, it warned of 30% of spills at United Utilities, the one company the spill model learned from, and 2% at the other 8 companies, from 0% at Anglian Water to 4% at Yorkshire Water\./);
  // Without the by-company rows (a file from before 11 Oct 2026) the section renders as before.
  const old = text((await render({live: {...OCT11, warning_table: {...OCT11.warning_table, by_company: undefined}}})).answer.innerHTML);
  assert.ok(!/came true were at/.test(old) && /warned of 17% of spills/.test(old));
});

test('11 Oct 2026: the coverage check reads the right way round', async () => {
  const l = text((await render({live: OCT11})).live.innerHTML);
  assert.match(l, /If the looser rule let unobserved spills through as "no spill", it would show the lower spill rate\. It does not: 2\.8% against 1\.6% under the stricter rule\./);
  const leak = {...OCT11, coverage_sensitivity: {...OCT11.coverage_sensitivity, strict: {...OCT11.coverage_sensitivity.strict, base_rate: 0.05}}};
  assert.match(text((await render({live: leak})).live.innerHTML), /It does: 2\.8% against 5\.0% under the stricter rule, so some spills may be counted as dry days\./);
});

test('11 Oct 2026: the offline counts agree with their tables, and the reanalysis row is not called an upper bound', async () => {
  const ho = {model: 'dipcast (pooled + site offsets)', n: 826725, base_rate: 0.0745, brier: 0.0445, log_loss: 0.15, auc: 0.9296, brier_skill_vs_clim: 0.3347};
  const leads = [{source: 'reanalysis (upper bound)', n: 828550, brier: 0.0447, auc: 0.9287, brier_skill_vs_clim: 0.3317},
                 {source: 'forecast lead 0', n: 828550, brier: 0.0429, auc: 0.9328, brier_skill_vs_clim: 0.3583}];
  const ecoli = {n_samples: 2165, n_sites: 38, period: ['2023-05-03', '2026-09-07'],
                 all_sites: [{predictor: 'rain_48h', n: 1750, sites: 32, spearman_pooled: 0.09, spearman_within_site: 0.35, auc_gt900: 0.65}]};
  const o = text((await render({live: OCT11, holdout: [ho], leads, ecoli})).offline.innerHTML);
  assert.match(o, /tested on 2025 \(826,725 overflow-days, 7\.45% with a discharge\)\. .* The model the site runs was refit on all three years, 2023 to 2025, after this test\./);
  assert.match(o, /It covers 828,550 overflow-days, 1,825 more than the test above\./);
  assert.match(o, /reanalysis \(the weather as it was\) 0\.0447/);
  assert.ok(!/upper bound/.test(o));
  assert.match(o, /\(2,165 samples\)\. The table scores the 1,750 samples at the 32 with a monitored overflow upstream\. The other 6 have none/);
});

// The spot level as the scorer summed it on 24 Oct 2026 (forecast_log.verify_spots on the state release), trimmed.
const rec = (n, hits, misses, false_alarms, auc) => ({n, hits, misses, false_alarms, quiet_correct: n - hits - misses - false_alarms,
  hit_rate: hits / (hits + misses), warnings_true: hits + false_alarms ? hits / (hits + false_alarms) : null,
  base_rate: (hits + misses) / n, auc, n_spots: 67});
const SPOTS = {n_cells: 4800, n_forecast: 4800, n_observed: 2803, n_scored: 2803, first_day: '2026-10-12', last_day: '2026-10-23',
  not_observed: {no_travel_time: 1190, no_overflows: 10, no_live_feed: 414, max_gap: 378, min_known_polls: 5},
  never_observed: [{spot_id: 'bw-ukd6300-40752', name: 'Sandy Lane, Chester'}, {spot_id: 'wye-hereford', name: "River Wye, Bishop's Meadow, Hereford"}],
  overall: {...rec(2803, 96, 101, 80, 0.902), climatology: {...rec(2803, 78, 119, 249, 0.834)}},
  n_spot_days: 691, n_event_spot_days: 45, n_days: 11, first_scored_day: '2026-10-13', last_scored_day: '2026-10-23',
  by_lead: [{lead: 0, ...rec(687, 23, 21, 20, 0.912)}, {lead: 4, ...rec(437, 11, 22, 7, 0.86)}],
  by_water: [{water: 'lake', ...rec(855, 0, 5, 0, 0.86)}, {water: 'river', ...rec(1948, 96, 96, 80, 0.88)}],
  by_company: [{company: 'United Utilities', ...rec(945, 15, 2, 33, 0.97)}, {company: 'unknown', ...rec(10, 0, 0, 0, null)}],
  levels: {bands: ['low', 'moderate', 'high', 'very high'], counts: [[2069, 55, 16, 24], [340, 62, 30, 31], [54, 14, 23, 45], [11, 1, 7, 21]]},
  by_week: [{week: '2026-10-12', n: 1272, mean_forecast: 0.049, mean_observed: 0.039}, {week: '2026-10-19', n: 1531, mean_forecast: 0.154, mean_observed: 0.107}],
  csv: {file: 'verification_spots_live.csv', rows: 4800}};

test('the level itself: its own section, the alert record, ranking, levels table and why days were not checked (review A5)', async () => {
  const els = await render({...live({warning_table: SPILL, overall: OVERALL, spots_live: SPOTS}), credits: {}});
  const L = els.live.innerHTML, t = text(L);
  assert.match(L, /<section id="spot-level"><h2>How the level itself has done<\/h2>/);
  const sec = t.slice(t.indexOf('How the level itself has done'));
  assert.match(sec, /2,803 of the 4,800 spot-day forecasts for days from 12 Oct 2026 could be checked\. The others could not: 1,190 because the forecast was made before travel times were logged; 414 because overflows with no live feed carry over 5% of the spot's weight; 378 because some overflows went unobserved for too long that day; 10 because no monitored overflow was upstream in that forecast; and 5 because there were too few runs/);
  assert.match(sec, /2 spots are never checked, because overflows with no live feed carry over 5% of their weight: Sandy Lane, Chester; River Wye, Bishop's Meadow, Hereford\./);
  assert.match(sec, /Since 13 Oct 2026, on 691 spot-days at 67 spots, the spills that happened would have put the spot at High risk or above on 45\. Of the 197 forecasts for those spot-days, 96 \(49%\) were at High risk or above\. Of the 176 forecasts at High risk or above, 96 \(55%\) were for such a day, against 7\.0% of all forecasts\. 11 days are too few to judge/);
  assert.match(sec, /Forecast High risk or above 96 hits 80 false alarms Forecast lower 101 misses 2,526 correct quiet days/);
  assert.match(sec, /the forecast gave the first the higher score 90 times in 100\. Each overflow's long-run spill rate for the month, combined the same way, did so 83 times in 100, and reached High risk or above on 78 of the 197/);
  // The levels table: each level word with its noun, rows forecast, columns observed.
  assert.match(sec, /Forecast Low risk Moderate risk High risk Very high risk Low risk 2,069 55 16 24 Moderate risk 340 62 30 31/);
  assert.match(sec, /2,175 of 2,803 forecasts had the same level\./);
  assert.match(sec, /Same day, as of 08:00 687 44 23 20 91/);
  assert.match(sec, /Lake spots 855 5 0 0 86 River spots 1,948 192 96 80 88 United Utilities 945 17 15 33 97 Company not known/);
  assert.match(sec, /12 Oct 2026 1,272 4\.9 3\.9/);
  assert.match(L, /<a href="data\/verification_spots_live\.csv" download>Download every spot-day forecast<\/a> \(CSV, 4,800 rows/);
  assert.match(L, /PREREGISTRATION-2027\.md#amendment-1/);
  // The design rules: no level word without its noun, no callout box.
  assert.ok(!/>(Low|Moderate|High|Very high)</.test(L.slice(L.indexOf('id="spot-level"'))), 'a bare level word');
  assert.ok(!/class="notice"/.test(L.slice(L.indexOf('id="spot-level"'))));
  // No link to rows the build did not publish.
  const unpublished = (await render(live({spots_live: {...SPOTS, csv: undefined}}))).live.innerHTML;
  assert.ok(!/verification_spots_live\.csv/.test(unpublished));
});

test('In short says how the level has done, or that nothing is checked yet, and no longer that it is not scored', async () => {
  const s = text((await render(live({warning_table: SPILL, overall: OVERALL, spots_live: SPOTS}))).short.innerHTML);
  assert.match(s, /The level a spot's page shows, against the spills that happened: 49% of forecasts for a spot-day the spills would have put at High risk were at High risk or above\. 55% of forecasts at High risk or above were for such a day\. 11 days are too few to judge\. Details/);
  for (const data of [live(), live({spots_live: {n_cells: 0, n_scored: 0}})]) {
    const els = await render(data), t = text(els.short.innerHTML);
    assert.match(t, /The level a spot's page shows is checked against the spills that happened; nothing has been checked yet\. How it is scored is fixed in the pre-registration ?\./);
    assert.match(els.short.innerHTML, /PREREGISTRATION-2027\.md#amendment-1/);
    assert.ok(!/not yet scored/.test(t));
    assert.ok(!els.live.innerHTML.includes('id="spot-level"'));
  }
});

// The data of 24 Oct 2026, in short: the hits had spread beyond United Utilities, and the scorer had a row for
// overflows with no company. The by-company words follow the data, and that row is not a company.
const OCT24 = {...OCT11, warning_table: {...OCT11.warning_table, n: 117324, hits: 1602, misses: 3902, false_alarms: 2238,
  hit_rate: 1602 / 5504, warnings_true: 1602 / 3840, base_rate: 5504 / 117324,
  by_company: [wc('United Utilities', 1272, 507, 1325), wc('Wessex Water', 1048, 410, 854), wc('Yorkshire Water', 790, 126, 272),
    wc('Anglian Water', 583, 31, 99), wc('Severn Trent Water', 499, 29, 113), wc('Thames Water', 470, 184, 648),
    wc('Southern Water', 381, 169, 288), wc('South West Water', 313, 134, 219), wc('Northumbrian Water', 78, 12, 22), wc('unknown', 70, 0, 0)]}};

test('24 Oct 2026: by company says what the data says, and the row with no company is not counted as one', async () => {
  const els = await render({live: OCT24});
  const top = text(els.top.innerHTML), a = text(els.answer.innerHTML), s = text(els.short.innerHTML);
  assert.match(top, /Spills warned of 29% Since 29 Sept? 2026, 1,602 of 5,504 forecasts for a day with a spill gave a High risk warning\./);
  assert.match(top, /Warnings that came true 42% 1,602 of 3,840 warnings were followed by a spill, against 4\.7% of all forecasts\./);
  assert.match(top, /By company, it warned of 40% of spills at United Utilities, the one company the spill model learned from, and 26% at the other 8 companies, from 5% at Anglian Water to 44% at Southern Water\./);
  assert.match(a, /At the other 8 companies, 4,162 forecasts were for a day with a spill, and 1,095 of them were warnings\./);
  assert.ok(!/caught few spills/.test(a), a);
  assert.match(s, /Live warnings, by company: 507 of the 1,602/);
  assert.ok(!/mostly at one company/.test(s), s);
});

test('a live error above the long-run rate is said as higher, never as a negative lower', async () => {
  const top = text((await render({live: {...OCT11, overall: {...OCT11.overall, calibrated: {...OCT11.overall.calibrated, brier: 0.05}}}})).top.innerHTML);
  assert.match(top, /Higher error, live 43% Read as a chance/);
  assert.ok(!/-\d+%/.test(top), top);
});

// The page as the build writes it: the boxes filled in place, in the page's own order.
test('the four figure tiles come first, before any h2, then the by-company line, then the contents (review C5)', async () => {
  const prerender = require('../scripts/prerender_verification.js').prerender;
  const out = await prerender(html, {live: OCT24, holdout: [{model: 'dipcast', n: 826725, auc: 0.9296, brier_skill_vs_clim: 0.3347}]});
  let page = html;
  for (const id of ['top', 'answer', 'short', 'live', 'offline']) page = page.replace(new RegExp(`<div id="${id}">[\\s\\S]*?</div>`), () => `<div id="${id}">${out[id]}</div>`);
  const body = page.slice(page.indexOf('<main'), page.indexOf('<script>'));
  const firstH2 = body.indexOf('<h2'), tiles = [...body.matchAll(/<div class="stat">/g)].map(m => m.index);
  assert.equal(tiles.length, 4);
  assert.ok(tiles.every(i => i < firstH2), 'a tile after the first h2');
  assert.ok(body.indexOf('<p>By company,') > tiles[3] && body.indexOf('<p>By company,') < firstH2);
  assert.match(body.slice(firstH2), /^<h2 id="toc-h">On this page<\/h2>/);
  // Then everything else in the order it had: the warnings, In short, how to read the numbers, live, offline.
  const at = s => body.indexOf(s);
  assert.ok(at('id="warnings-h"') < at('id="short-h"') && at('id="short-h"') < at('id="reading"') && at('id="reading"') < at('id="live-scoring"')
    && at('id="live-scoring"') < at('id="holdout"'), 'order');
  assert.match(out.top, /<li><a href="#warnings">Warnings, misses and false alarms<\/a><\/li><li><a href="#in-short">In short<\/a><\/li>/);
  assert.ok(out.short.includes('<section class="summary" id="in-short"'));
});

test('the build writes the level section into the page, and the contents list points at it', async () => {
  const prerender = require('../scripts/prerender_verification.js').prerender;
  const out = await prerender(html, {live: {...OCT24, spots_live: SPOTS}, credits: {}});
  assert.match(out.live, /<section id="spot-level"><h2>How the level itself has done<\/h2>/);
  assert.match(out.top, /<li><a href="#spot-level">How the level itself has done<\/a><\/li>/);
  assert.match(out.short, /href="#spot-level">Details<\/a>/);
});
