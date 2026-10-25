# A spill model trained on nine companies, second try (v2): the test, stated before any run

Written 25 October 2026 and first pushed in `68f80a9`. Revised the same evening, before any fetch, fit or score, to
make the conditions allow for noise and to fit the approved fetch and run date; "Revision of 25 October" below lists
every change. Results go below the line at the end. Nothing above that line changes after a result is seen.

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

**PR #251's per-company results are known**, and the revised conditions were written knowing them. Against the
hold-out, its candidate's Brier was 1.14% higher at Anglian (0.02722 against 0.02691; 2.6% above production) and 2.33%
higher at United Utilities (0.04561 against 0.04457). Its Welsh pooled Brier was 0.91% higher (0.04206 against
0.04168). Its ECE at Thames was 0.0240. Over the nine it was 3.9% lower than the hold-out. **The margins below are
taken from house rules, not chosen to make that result pass:** the form "interval not wholly above zero, and no more
than 1% above" is option B's conditions 2 and 5, the 1% is PR #334's margin, and the interval is option B's and the
2027 protocol's. Applied to PR #251's point estimates, they would still fail it at Anglian and United Utilities (both
above 1%) and at Thames (ECE). Only the Welsh set would move, from a fail to a pass on its point estimate.

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
  operation of at least 50% in 2025, and a monitor that passes option B's dead-monitor check, with its reference
  period cut short (below): at least 80% of polls with a known status; at most 20% of known polls stale at a company
  that stamps every record (not applied to Northumbrian and Southern); a known poll on at least round(20 × n / 28) of
  the n reference days.
- **The reference period.** From 5 October 2026 to the last complete local day in the `state` release downloaded,
  read-only, just before the run (its newest day, still being polled, is left out). Its hashes and n are recorded.
  Option B reads 5 October to 1 November. The run was approved for now, and 1 November is a week away; the check
  counts polls, not discharges, and the data check's preview on 20 days passed 13,474 of 13,988 overflows. So the
  rows may differ from option B's final window E by a few overflows. The count is reported.
- **Left out:** the 16 overflows upstream of Cromwheel in `docs/UPGRADED-OVERFLOWS-2026-10-upstream.csv` (YWS00176,
  YWS00674, YWS00179, YWS00144, YWS00145, YWS00191, YWS01340, YWS00828, YWS00188, YWS00189, YWS00177, YWS00190,
  YWS00185, YWS01311, YWS00186, YWS00187). PR #298 published their 2026 outcome, so a test that counted them would be
  partly chosen on it. Option B leaves out the same 16.
- **Rain.** ERA5-Land, finite for the day. For 2026: the 200 cells already cached in `data/cache/rain/`
  (`archive_<cell>_2026.parquet`, fetched 6 September or 6 October), and the 1,422 others from the fetch below
  (`data/cache/rain_nine/archive_<cell>_2026a.parquet`). Each cell is read from one file only, and 2026 is cut at
  31 August. ERA5-Land's preliminary days can be revised slightly in the months after; both fetches are after the
  last day used.
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

**Scores**, per company and for the nine together: rows, base rate, Brier, AUC, log loss, Brier skill against each
baseline, a 10-bin reliability table, and ECE (the mean absolute gap between forecast and observed rate over 10
equal-width bins, weighted by rows).

**The interval.** Option B's, which is the 2027 protocol's two-way cluster bootstrap (`docs/PREREGISTRATION-2027.md`,
section 10), applied to the difference in Brier, row by row:
- each draw resamples overflows with replacement and, independently, ISO weeks of the target day with replacement;
  a row counts (times its overflow was drawn) × (times its week was drawn);
- 2,000 draws from `numpy.random.default_rng(20261025)`, made once, overflows first, then weeks; every company, arm
  and subset uses the same draws;
- the 95% interval runs from the 2.5th to the 97.5th percentile.

Two-way because both kinds of shared error are here: v2 changes every overflow's level, so its errors are shared
across an overflow's days, and one storm's are shared across overflows. The week-only interval is reported beside it.
The Welsh set gets its own draws of its overflows and weeks from the same generator, after the English ones.

## Conditions for adopting an arm, all required

Each arm is checked on its own. "Arm − production" is the difference in Brier on the same rows.

1. **A gain over the nine.** Nine together, the arm's Brier is lower than production's, and the 95% interval of
   arm − production lies wholly below zero. (Option B's condition 1.)
2. **No company clearly worse.** At each of the nine companies, the interval of arm − production does not lie wholly
   above zero, and the arm's Brier is no more than 1% above production's. (Option B's conditions 2 and 5.)
3. **Skill against the simple baselines.** At each of the nine, the arm's Brier is lower than both the company flat
   rate and the overflow climatology.
4. **Reliability.** At each of the nine, the arm's ECE is no higher than production's, or it is at most 0.02.
5. **The Welsh set is not clearly worse.** On the Welsh rows, the interval of v2 pooled − production pooled does not
   lie wholly above zero, and v2's pooled Brier is no more than 1% above production's. Neither model has offsets
   there, so this condition is the same for both arms.

**Minimum data.** Each of the nine companies needs at least 200 spill-days in the test rows, and the Welsh set at
least 100. A company short of that makes the test inconclusive, and nothing is adopted.

**Why condition 3 keeps point estimates.** The baselines are a floor. A model that does not beat its company's own
flat rate or each overflow's own history adds nothing at that company, whatever the noise. In PR #251 every company
cleared both by 21% or more (Brier skill).

**Thames and condition 4, decided now: an ECE failure is a rejection, not a recalibration matter.**
- Thames records few, long events, with long gaps between them (median event 60 to 75 minutes against 2 to 20
  elsewhere). *Inferred, not established* (PR #251): it merges activations. But the label is "spilled that day", so
  merging changes event counts far more than spill-days, and it does not explain a forecast that is off at Thames.
- A per-company recalibration fitted after seeing a failure would be a new model component chosen on the test year.
  It would need its own statement and its own test, as option B and A8 are for company-level offsets.
- ECE has noise too, but the 0.02 limit is already an allowance: it passes a company whose forecasts are off by up to
  two percentage points on average, against base rates of 3% to 9% by company in PR #251. ECE's interval is
  reported.
- Arm (b) has an offset for every Thames overflow, fitted on two years. If Thames's forecasts are still off after
  that, the fault is real for the people who read them.

### What changed from PR #251's conditions, and why (written before any result)

- **Noise.** PR #251 compared point estimates. Its losses at Anglian (1.1%) and on the Welsh set (0.9%) were never
  tested against noise. Conditions 1, 2 and 5 now use option B's interval and option B's form. Condition 1 is new: a
  model that is merely not worse anywhere is not worth a change of model.
- **Production replaces the hold-out model** in conditions 2, 4 and 5. PR #251 compared with the United Utilities
  2023-24 hold-out because production had seen United Utilities' 2025, the test year. Production has not seen 2026,
  so it is a fair comparison everywhere, and it is what the site shows. The hold-out is reported.
- **The baselines use January to August of the training years**, not whole years. The test covers January to August,
  so a whole-year rate would mix in the wet autumn months the test does not have.
- **The rows add the dead-monitor check.** There is no 2026 annual return for PR #251's "0 spills in the return"
  rule. The data check shows a January to August silence cannot be judged against a whole-year return.
- **Days are local**, as PR #334 passed.

Conditions 3 and 4 are otherwise PR #251's, with point estimates, as there.

## Reported, not deciding

- **The hold-out model** (`spill_model_holdout_2025.pkl`, SHA-256
  `882f9d4fb2c9314943fa861d8c6f4c62d8cd1eb57f1aa25059f4eb27d07068dc`) on the same rows.
- **Arm (b25):** the same layer 1 with offsets at recency 0.25. It shows what the recency choice does. It cannot be
  adopted.
- **AUC and log loss** per company and nine together, for every predictor.
- **Other intervals,** from the same draws: the week-only interval beside every deciding one; each arm's ECE per
  company; (b) − (a).
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
- Condition 1 passes for (b): PR #251's one-year candidate was already 3.9% better than the hold-out over the nine.
- At United Utilities, production has three years of offsets on the company's own Stream files, and (b) has two
  years of EA files at a different recency. Condition 2 there is close to a coin flip; the 1% point limit is the
  harder half.
- Thames's ECE stays the likeliest failure of condition 4.
- (a) fails condition 2 at United Utilities, where offsets carry a lot.
- The Welsh set should pass condition 5 now: PR #251's 0.9% loss is inside the 1% limit, if its interval allows.

My guess at the verdict: (b) fails on United Utilities or Thames; (a) fails on United Utilities. A pass for (b) would
not surprise me.

## Revision of 25 October, before any fetch, fit or score

Made after `68f80a9` was pushed, at Ethan's request relayed by the parent session, and before any rain was fetched or
any model fitted:
- **Conditions allow for noise.** Point-estimate conditions 1 and 4 of the first version became conditions 2 and 5
  above, with option B's interval and margins. Condition 1 (a gain over the nine) is new.
- **Thames's reliability** decided now: an ECE failure stays a rejection (above).
- **AUC and log loss** are reported for every predictor.
- **"Seen before writing"** now states that PR #251's per-company results were known, and what the new rules would
  have done to them.
- **The run is approved now**, so the dead-monitor reference period ends at the last complete day before the run,
  not on 1 November.
- **The fetch is fetch A** (2,468 calls), not fetch C, to stay under 3,000 calls a day from this Mac.

Nothing else changed: the arms, the training data, the rows' other rules, the predictors and the order of
precedence.

## Data this depends on

**Approval.** Ethan approved the fetch and the run on 25 October, relayed by the parent session ("Monetization
plans remaining work"): he "approves the recommendations, which included approving v2's Open-Meteo fetch and run",
with a limit of 3,000 Open-Meteo calls a day from this Mac, which other sessions share. Nothing is adopted or
deployed, whatever the result.

**The 2026 ERA5-Land fetch: fetch A of the data check.** Fetch C (3,522 calls, which would also have served option B)
is over the daily limit. So:
- 1 January to 31 August 2026, for the 1,422 cells of the 2025 return with no cached 2026 file, into
  `data/cache/rain_nine/archive_<cell>_2026a.parquet`. The tag `2026a` keeps these files apart from a later
  whole-year fetch: `fetch_archive` treats any `archive_<cell>_2026.parquet` as done.
- **Calls:** 1,422 × `rainfall.call_weight(1, 243)` = 1,422 × 1.736 = **2,468**, in 143 requests of up to 10 cells.
  No other Open-Meteo call has been made from this Mac on 25 October (no cache file written that day, no fetch
  process running, checked 21:57 UTC).
- Paced at 3,000 calls an hour, strict (a refusal stops it, with no retry on 429). Every request is logged with its
  time, cells, days, weight and status.
- Option B still needs its own fetch for 2026 to 31 October; these files cover its cells to 31 August.
- The code change: `scripts/fetch_rain_nine.py` gains an `archive 2026a` mode.

**The state release** downloaded just before the run, for the dead-monitor check.

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

1. This statement and the data check are pushed (draft PR #357). Done in `68f80a9`.
2. Ethan approves the fetch and the run. Done on 25 October (above).
3. This revision is pushed before any fetch, fit or score.
4. The fetch (2,468 calls). Its log and request count go under the line.
5. The harness (`scripts/nine_v2_eval.py`) is committed after this file and before any run. It does not change
   anything above the line.
6. Just before the run: the `state` release is downloaded read-only; its hashes, n and the dead-monitor pass list are
   recorded.
7. Inputs frozen as APFS clones, their SHA-256 recorded. One run from a `git archive` of the harness commit, under the
   group's `heavy-run.lock`, alone on this 16 GB Mac (`pgrep -fl`, never `pkill`). `train.py` on United Utilities'
   three years (2.4 million site-days) peaked at 3.9 GB (PR #334). This run trains on about 10 million. The
   dry-weather test's fit on a similar number was estimated at 6 to 9 GB, not measured. The harness logs its peak.
8. Face checks first (the run stops on any failure): production's hash; every predictor has a forecast on every row;
   the test rows' spill-days per company equal a recount from the EA file.
9. The results go below the line, in a record PR. Nothing is adopted or deployed by it.

---

## Results

Not yet run.
