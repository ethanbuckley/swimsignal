# A spill model trained on nine companies, second try (v2): the test, stated before any run

Written 25 October 2026. Nothing for v2 has been fetched, fitted or scored. This file is committed and pushed before
any of that. Results go below the line at the end. Nothing above that line changes after a result is seen.

## Why

The spill model's layer 1 (the pooled classifier on rain, season and annual-return covariates) and its layer 2 (one
offset per overflow) are fitted on United Utilities alone. The radar check of 25 October
(`docs/RADAR-RAIN-CHECK-2026-10.md`) found that the model's knowledge of the other eight companies, not the rain, is
the main limit.

The first try, on 17 October (`docs/NINE-COMPANY-MODEL-TEST-2026-10.md`, PR #251), trained on the EA start/stop files
of nine English companies for 2024 and tested on 2025. It was better over the nine together (Brier 0.0362 against the
hold-out's 0.0376) and at seven of nine companies, but failed three of four conditions:
- Anglian and United Utilities slightly worse (condition 1);
- Thames's reliability, ECE 0.024 (condition 3);
- the Welsh set, 0.04206 against 0.04168 (condition 4).

Its observations pointed at the offsets fitted on one year. Its own pooled layer alone scored 0.0260 at Anglian, below
every row in its table. Two years of EA files now exist for training, and 2026 to August for a test. This file is
that retry.

## Seen before writing

All of `docs/NINE-COMPANY-MODEL-V2-DATA-CHECK-2026-10.md`, written today for this test. In short:
- **The zips.** The EA's yearly zips for 2024, 2025 and 2026 to August, downloaded 25 Oct 2026 (SHA-256 in the data
  check). 2024 and 2025 are unchanged from PR #251's import.
- **2026 events per company:** Anglian 101,557; Northumbrian 81,951; Severn Trent 90,089; South West 202,280;
  Southern 78,153; Thames 13,078; United Utilities 64,672; Wessex 239,943; Yorkshire 111,686. Every company's file
  runs 1 January to 31 August.
- **Spill-days per company and month for 2024, 2025 and 2026** (local days), the counts behind these:
  - January to August 2026 against 2024 and 2025, all nine: 202,537 against 293,240 and 126,427.
  - July 2026 is tiny everywhere (8 at Southern to 446 at Northumbrian). July 2026 was very dry: ERA5-Land 3 to 5 mm
    over five southern and central companies' cells, radar 1 to 3 mm.
  - United Utilities' January 2026: 4,010 against 10,052 and 8,348, with similar rain and no missing day.
- **The live feeds' latest events in January to August:** 77% have an EA event the same local day. The rest are
  mostly short (median 4.5 minutes). South West Water's own file and Thames's alert stream agree with the EA file.
- **Overflows with no event** from January to August: 3,022 of 14,180 in 2026, 3,005 of 14,157 in 2025.
- **Ids in no annual return:** 706 events of 2026, none with a position.
- **The dead-monitor check** (option B's), previewed on 20 of its 28 reference days: 13,474 of 13,988 overflows pass.
- **Dŵr Cymru 2026:** 5,353 events at 112 overflows, January to August; 99 of them in England in the 2025 return.
- **Rain cached:** ERA5-Land 2024 and 2025 for every cell; 2026 for 200 of 1,622 cells.

Also read: PR #251's statement and results in full; `docs/MODEL-PROVENANCE-2026-10.md`; the day-boundary test
(PR #334, branch `claude/day-boundary-a11-a793d8`); option B's statement, its recency note and its addendum P1;
`docs/COMPANY-CALIBRATION-TEST-2026-11.md`; `docs/PREREGISTRATION-2027.md`; the verdicts in `docs/README.md`.

Not seen: any forecast or score on 2026 from any model. No v2 model exists. No production forecast for 2026 rows has
been computed for this test.

## The candidate: one layer 1, two arms

**Training events.** The EA start/stop files of the nine English companies for 2024 and 2025, from the yearly zips
above, read with `edm_events.read_ea_events` (ids mapped by `_id_map`). United Utilities is read from the EA file,
as in PR #251. Dŵr Cymru stays out of training.

**Training rows.** PR #251's rule, unchanged, for each of 2024 and 2025 (`training.site_years`):
- covariates and position from the year before's return (2023 for 2024, 2024 for 2025);
- an overflow-year is kept when the file has an event for it that year, or that year's return gives 0 spills;
- same-year EDM operation of at least 50%;
- finite ERA5-Land rain for the day.

**Days.** UK local days (Europe/London) for rain features, labels and grids. This is PR #334's code (passed on
25 October, not yet merged). If #334 is not on main when the harness is written, the harness branch merges #334's
branch and says so. Local days are what the live forecast, the live scoring and the 2027 scoring use.

**Layer 1.** `SpillModel.fit_pooled` on every kept 2024 and 2025 site-day of the nine companies, with production's
settings: `neg_frac` 0.25, seed 0, `features.ALL_FEATURES`. No company feature, so the pooled layer still applies
where a company has no offsets (Wales, Scotland).

**The two arms:**

| Arm | Layer 2 | Role |
|---|---|---|
| **(a) pooled** | none: layer 1 alone | candidate |
| **(b) offsets** | `fit_site_offsets` on the same rows, prior strength 15, **recency 1** | candidate |

Both arms share one layer 1, fitted once.

**Recency 1 for arm (b), and why.** Production's offsets use 0.25 (`docs/MODEL-PROVENANCE-2026-10.md`): a year one
year older counts a quarter. PR #251 used 1, which had no effect on its one year. Here it decides how much 2024
counts:
- At 0.25, 2025 carries 80% of each offset's weight. That is close to the single-year offsets PR #251 found to be
  its weak part ("an offset fitted on one wet year carries that year into the next"). This retry exists to test two
  years of offsets, so the deciding arm weights them equally.
- Option B's offsets use recency 1, and Ethan kept that on 25 October (addendum P1). With 1 here, arm (b) and option
  B's arm B0 fit offsets the same way, and their window-E results can be read side by side.
- The evidence for 0.25 is one company and one year: 0.0447 against 0.0445 on United Utilities 2025 (README). That
  difference, 0.0002, is smaller than the width of PR #334's 95% interval on those same rows (0.00032).

So arm (b) against production differs in layer 1, events, days, companies and recency together. It answers "should
the site switch", not which part helped. A reported arm (below) shows the recency part.

**Which arm wins, fixed now.** If (b) passes every condition, (b) is adopted. Otherwise, if (a) passes every
condition, (a) is adopted. Otherwise neither. Two candidates give two chances to pass; the conditions are not
adjusted for that. (b) comes first because it is the form production has.

**What would be deployed:** the tested model itself, fitted on 2024 and 2025. Not a refit that adds 2026: that model
would not have been tested, and its lead map would be fitted on its own training data. `trained_on` would read
"Nine English water companies 2024-2025 (EA start/stop files, UK local days); verified on January-August 2026".

## The test rows: window E

The same rows as option B's window E, so the two tests score the same overflow-days.
- **Days.** UK local days, 1 January to 31 August 2026. No month is excluded (the data check gives why).
- **Overflows.** The nine English companies' overflows with a position and covariates in the 2025 return, EDM
  operation of at least 50% in 2025, and a monitor that passes option B's dead-monitor check: over 5 October to
  1 November 2026, at least 80% of polls with a known status; at most 20% of known polls stale at a company that
  stamps every record (not applied to Northumbrian and Southern); a known poll on at least 20 of the 28 days. Read
  from one `state` release made on or after 2 November 2026, downloaded read-only, hashes recorded. If option B's
  harness exists when this harness is written, its function is used.
- **Left out:** the 16 overflows upstream of Cromwheel in `docs/UPGRADED-OVERFLOWS-2026-10-upstream.csv` (YWS00176,
  YWS00674, YWS00179, YWS00144, YWS00145, YWS00191, YWS01340, YWS00828, YWS00188, YWS00189, YWS00177, YWS00190,
  YWS00185, YWS01311, YWS00186, YWS00187). PR #298 published their 2026 outcome, so a test that counted them would be
  partly chosen on it. Option B leaves out the same 16.
- **Rain.** ERA5-Land, finite for the day. 2026 is read from `data/cache/rain_nine/` only (the fetch below), so every
  2026 cell has one fetch date and none is read twice.
- **Labels.** A local day is a spill-day if a 2026 EA event touches it.

**The Welsh test set.** Dŵr Cymru's overflows in England with a position and covariates in the 2025 return and EDM
operation of at least 50% in 2025, 1 January to 31 August 2026, labels from the 2026 zip's Dŵr Cymru workbook
(`read_ea_dcww_events`). SwimSignal polls no Dŵr Cymru feed, so the dead-monitor check cannot be applied there.

## The predictors, all scored on the same rows

| Predictor | What it is |
|---|---|
| (a) | v2 layer 1 alone |
| (b) | v2 layer 1 plus offsets (recency 1) |
| Production | `data/processed/spill_model.pkl` on main, SHA-256 `faa7917e2be725a9441b277fc111091c5bdffe45c80ab4fd042682aa9de4210e` (United Utilities 2023-25, offsets at recency 0.25). Fed local-day features, as the live forecast feeds it. It never saw 2026, so it is out of sample at every company, United Utilities included |
| Company flat rate | the company's spill-day rate over its January to August 2024 and 2025 training rows, one number per company |
| Overflow climatology | the overflow's own spill-day rate over its January to August 2024 and 2025 training rows (`verify.climatology`); an overflow with none takes the company's flat rate |

The harness stops if production's hash differs.

**Scores**, per company and for the nine together: rows, base rate, Brier, AUC, Brier skill against each baseline,
a 10-bin reliability table, and ECE (the mean absolute gap between forecast and observed rate over 10 equal-width
bins, weighted by rows).

## Conditions for adopting an arm, all required

Each arm is checked on its own.

1. **No company worse than production.** At each of the nine companies, the arm's Brier is no higher than
   production's.
2. **Skill against the simple baselines.** At each of the nine, the arm's Brier is lower than both the company flat
   rate and the overflow climatology.
3. **Reliability.** At each of the nine, the arm's ECE is no higher than production's, or it is at most 0.02.
4. **The Welsh set is not worse.** On the Welsh rows, v2's pooled Brier is no higher than production's pooled Brier.
   Neither model has offsets there, so this condition is the same for both arms.

**Minimum data.** Each of the nine companies needs at least 200 spill-days in the test rows, and the Welsh set at
least 100. A company short of that makes the test inconclusive, and nothing is adopted.

### What changed from PR #251's conditions, and why (written before any result)

- **Production replaces the hold-out model** in conditions 1, 3 and 4. PR #251 compared with the United Utilities
  2023-24 hold-out because production had seen United Utilities' 2025, the test year. Production has not seen 2026,
  so it is a fair comparison everywhere, and it is what the site shows. The hold-out is reported.
- **The baselines use January to August of the training years**, not whole years. The test covers January to August,
  so a whole-year rate would mix in the wet autumn months the test does not have.
- **The rows add the dead-monitor check.** There is no 2026 annual return for PR #251's "0 spills in the return"
  rule. The data check shows a January to August silence cannot be judged against a whole-year return.
- **Days are local**, as PR #334 passed.

Conditions 1 to 4 are otherwise PR #251's, with point estimates, as there.

## Reported, not deciding

- **The hold-out model** (`spill_model_holdout_2025.pkl`, SHA-256
  `882f9d4fb2c9314943fa861d8c6f4c62d8cd1eb57f1aa25059f4eb27d07068dc`) on the same rows.
- **Arm (b25):** the same layer 1 with offsets at recency 0.25. It shows what the recency choice does. It cannot be
  adopted.
- **Intervals.** For each arm against production, per company and nine together: a paired bootstrap of the Brier
  difference over ISO weeks of the target day, 2,000 draws, seed 20261025, 2.5th and 97.5th percentiles.
- **Sensitivities**, each rescored with the same models:
  - without United Utilities' January (the data check could not explain its drop);
  - without July;
  - without the dead-monitor check (every overflow with a position and EDM operation of at least 50% in 2025);
  - per month.
- **Event definitions.** Per company: share of the training spill-days that come only from events under 15 minutes,
  and the same in the test rows. Thames merges events; Wessex and South West record many short ones.
- **Mean forecast against observed rate** per company and month, for each predictor.
- **Option B side by side.** If option B has run by then, its window-E Brier for P, B, B0 and P1 beside these, on
  the same rows. Option B's arms use monthly fits that include 2026's earlier months, so this is a description, not a
  fair contest.

## Prediction (inferred, not a condition)

- (b) beats production at most of the eight companies outside United Utilities, where production has no offsets.
- At United Utilities, production has three years of offsets on the company's own Stream files, and (b) has two
  years of EA files at a different recency. Condition 1 there is close to a coin flip.
- Thames's ECE stays the likeliest failure of condition 3, from its merged events.
- (a) fails condition 1 at United Utilities, where offsets carry a lot.
- The Welsh set is unclear: PR #251's layer 1 lost there by 1%.

My guess at the verdict: (b) fails on United Utilities or Thames; (a) fails on United Utilities. A pass for (b) would
not surprise me.

## Data this depends on

**The 2026 ERA5-Land fetch (needs Ethan's approval).** Fetch C of the data check: 1 January to 31 October 2026 for all
1,622 cells, on or after 6 November (when `rainfall.fetch_archive`'s six-day lag reaches 31 October), into
`data/cache/rain_nine/archive_<cell>_2026.parquet`.
- **Calls:** 1,622 × `rainfall.call_weight(1, 304)` = 1,622 × 2.171 = **3,522**.
- It serves option B as well, which needs the same months for the same cells.
- Paced at 3,000 calls an hour, strict (a refusal stops it), in about 70 minutes, under the free limits (5,000 an
  hour, 10,000 a day). Not run beside a build-sized job or another Open-Meteo fetch from this Mac.
- The code change: `scripts/fetch_rain_nine.py` gains an `archive 2026` mode that ignores the 200 partial 2026 files
  in `data/cache/rain/`. It goes in the harness commit.

The smaller choice, if Ethan prefers: fetch A, January to August only for the 1,422 missing cells, 2,468 calls, any
day. It needs an end-date argument, and option B would then fetch its own 2026 later.

**The state release** on or after 2 November, for the dead-monitor check.

**No forecast-lead fetch.** The test uses reanalysis rain only, as PR #251's did.

## How this fits with the other tests and the 2027 freeze

Running this test changes nothing on the site. Deploying a pass would change `spill_model.pkl`, and several live
windows forbid that until they close.

| Test | Window | What a v2 deployment would do to it | So |
|---|---|---|---|
| Lead calibration B (`LEAD-CALIBRATION-B-TEST-2026-10.md`) | 18 Oct to 14 Nov, read on or after 16 Nov | its window ends if `spill_model.pkl` changes | no deployment before 16 Nov |
| Live-status shadow (`LIVE-STATUS-SHADOW-TEST-2026-10.md`) | 25 Oct to 21 Nov (5 Dec if extended) | fallback rows take production's probability, so the baseline would change mid-window | no deployment before 21 Nov (or 5 Dec) |
| Company calibration A8 (`COMPANY-CALIBRATION-TEST-2026-11.md`) | 26 Oct to 22 Nov, read on or after 25 Nov | its window ends at a new `spill=` stamp | no deployment before 25 Nov |
| Option B (`UPGRADED-OVERFLOWS-TEST-B-2026-10.md`) | window L 29 Sep to 30 Nov, run on or after 2 Dec | it rebuilds its arms from logged `p_raw` minus production's offsets; a new layer 1 inside window L breaks that | **no deployment before option B has run** |
| Ensemble rain (`ENSEMBLE-RAIN-TEST-2026-11.md`) | 23 Oct to 19 Nov | stays paired; the date goes under its line | no conflict |
| Day boundary (#334) | none (passed) | v2 is built on its code | #334 merges before or with v2 |

**If v2 passes and option B passes.** They change the same layer in incompatible ways: option B's offsets are fitted
to production's layer 1. v2 goes first, because it changes layer 1, which is the limit the radar check found. Option
B's start-date rule would then need a refit on v2's layer 1, under its own statement, before the freeze or after the
season.

**If v2 passes and option B fails,** v2 goes on alone.

**If v2 fails,** option B and A8 are unaffected, and this file is the record.

**A8's offsets** are fitted to production's layer 1. If v2 is adopted, A8's candidate no longer applies.

### From a pass to the site

1. **A live shadow, 28 target days, as option B's.** v2's forecast at every lead is logged in one new column of
   `forecast_overflows`; nothing published reads it. It opens on the first target day whose 08:00 forecasts carry it
   at every lead 0 to 4. Shadow conditions, on the scored live rows, leads pooled, with option B's bootstrap: (1) nine
   together, the interval of v2 minus production does not lie wholly above zero; (2) no company with at least 200
   spill rows has an interval wholly above zero; (3) ECE at each such company no higher than production's, or at
   most 0.02. **Why a shadow:** the data check found that live labels count short blips the EA file leaves out,
   mostly in dry months. A model fitted and tested on EA spill-days has not met that truth. The shadow does not start
   before option B's run, so it does not touch window L.
2. **The lead map is refitted for v2's model** by whichever recipe lead calibration B's verdict leaves, so the map's
   `model` equals v2's `trained_on`. Its rows are 2026 lead forecasts for the cached lead cells. If more lead cells are
   needed, that fetch has its own count and approval.
3. **The E. coli model** reads spill exposure from the spill model, so `validate_ecoli.py` and `train_ecoli.py` are
   rerun on v2 before deployment.
4. **Adoption** is its own PR, Ethan's call, merged by 31 March 2027.

**The 2027 freeze** (`docs/PREREGISTRATION-2027.md`, section 15). The tag is due by 30 April 2027; any model change
before it is allowed, and the frozen model is whatever is on main at the tag. A new `spill_model.pkl` changes the
stamp's `spill=` part, and a new map its `cal=` part. If the 2026 annual returns are refreshed in mid-April, layer 1's
covariates change for every overflow; that refresh is a model change before the tag, and v2 is not refitted for it.
**If this test has not run by 31 January 2027,** there is no room for a 28-day shadow before the tag. The test still
runs, but nothing is adopted for 2027. A pass is then a candidate for after the season (section 12).

## Not chosen, and why

- **2026 in training.** Then there is no test year. A model on 2024-26 is a later candidate, after this result.
- **Leaving one year out in turn (2024, 2025, 2026).** Two of three folds would train on 2026 data from a file that
  ends in August, and on 2026 rows with no annual return for PR #251's rule.
- **Dropping July or April.** Their low counts follow the rain (the data check). Dropping them would choose the test
  set on its outcome.
- **A company feature in layer 1.** It would make layer 1 unusable where a company has no training rows: Wales,
  Scotland, and any company whose file goes missing.
- **Recency 0.25 as the deciding arm.** Given above; reported as (b25).
- **Fewer pseudo-counts in the prior.** PR #251 named it as a possible retry. Choosing a smaller prior would be
  tuning, and option B kept 15.
- **Live labels as the test.** Option B's window L covers autumn 2026, and a shadow follows a pass. Seven months of EA
  files give far more spill-days than either.

## Order of work

1. This statement and the data check are pushed (draft PR). Nothing below runs before step 2.
2. Ethan approves the fetch's call count, and this statement.
3. The harness (`scripts/nine_v2_eval.py`) and the fetch change are committed after this file and before any run.
   They do not change anything above the line.
4. On or after 2 November: the `state` release is downloaded read-only; its hashes and the dead-monitor pass list are
   recorded.
5. On or after 6 November: the fetch (3,522 calls). Its log and request count go under the line.
6. Inputs frozen as APFS clones, their SHA-256 recorded. One run from a `git archive` of the harness commit, under the
   group's `heavy-run.lock`, alone on this 16 GB Mac (`pgrep -fl`, never `pkill`). `train.py` on United Utilities'
   three years (2.4 million site-days) peaked at 3.9 GB (PR #334). This run trains on about 10 million. The
   dry-weather test's fit on a similar number was estimated at 6 to 9 GB, not measured. The harness logs its peak.
7. Face checks first (the run stops on any failure): production's hash; every predictor has a forecast on every row;
   the test rows' spill-days per company equal a recount from the EA file.
8. The results go below the line.

**The earliest run date is 6 November 2026,** if Ethan approves by then.

---

## Results

Not yet run.
