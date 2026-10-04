// verification.html's plain figures: the warnings tables at the top and the service record. The page's
// script runs in a sandbox with a fake document and the data a build writes (forecast_log.warning_table,
// forecast_log.service_record).
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/api/static/verification.html'), 'utf8');
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
  const document = {getElementById: id => (els[id] = els[id] || {innerHTML: ''}), querySelectorAll: () => []};
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
  assert.match(a, /the spill forecast warned of 21% of spills\. As a yes-or-no warning at the High risk line, it misses most\. Read as a chance, it beats each overflow's long-run rate, with 28% lower error\./);
  assert.match(a, /When it warned, a spill followed 42% of the time, against 3% across all forecasts\. A warning made a spill about 14 times as likely\./);
  assert.match(a, /against 96\.9% for saying "no spill" every time\. Spills are rare, so a share right says little on its own\./);
  const sentence = a.split(/(?<=\.) /).find(s => s.includes('96.6%'));
  assert.ok(sentence.includes('96.9%') && sentence.includes('"no spill" every time'), sentence);
  assert.match(a, /5 days so far, too few to judge/);
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
  assert.match(a, /misses most\. Read as a chance, it does no better than each overflow's long-run rate\./);
  assert.match(a, /against 0\.4% across all forecasts\. A warning made a spill 1\.4 times as likely/);
  const none = text((await render({...live({warning_table: {...SPILL, hits: 0, false_alarms: 0, warnings_true: null, warning_lift: null}})})).answer.innerHTML);
  assert.match(none, /It gave no warnings\./);
});

test('too few E. coli samples show counts and say so, with no percentages', async () => {
  const a = text((await render({...live({warning_table: SPILL, ecoli_live: {warning_table: ECOLI}})})).answer.innerHTML);
  const ecoli = a.slice(a.indexOf('The E. coli estimate'));
  assert.match(ecoli, /15 Environment Agency samples at 11 bathing waters, 1 of them over 900/);
  assert.match(ecoli, /warned before 2: 0 were over 900 and 2 were not/);
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
  const t = text((await render({...live({warning_table: SPILL, overall: OVERALL}), holdout: [ho]})).short.innerHTML);
  assert.match(t, /Pairs ranked the right way round 93 in 100 Given one overflow-day that spilled and one that did not, the forecast gave the spill the higher chance 93 times in 100\. A ranking, not a share of forecasts right\./);
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
  assert.match(t, /Runs that stopped before publishing 1 of 2 since .*only 3\/105 spots got a forecast/);
});
