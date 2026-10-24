# Upgraded overflows, option B (each overflow's own record since a start date): the test, stated before any run

**Draft for Ethan's approval; nothing runs until he approves it.** He approves it by merging the PR that carries
this file, or by saying so in writing in that PR. Until then no data is fetched or imported for this test, no
harness is written and no score is computed.

Written 24 October 2026. Results go below the line at the end. Nothing above that line changes after a result is
seen. The record that led here is `docs/UPGRADED-OVERFLOWS-2026-10.md` (PR #298), section 4, option B.

## Why

The spill forecast treats an upgraded overflow as if nothing changed. Its main site input, `lta_spills`, is a
running mean of yearly counts since 2020, and the build reads a copy of the annual returns from 13 Sep 2026
(PR #298, section 1). At Ilkley, the six overflows Yorkshire Water names in its upgrade scheme showed 1 spill day
in April to August 2026 against 23.0 expected (PR #298, section 2).

PR #298 recommended option C now (say so on the spot page, no model change) and a test of option B before the
2027 freeze. Option B: extend layer 2 of the spill model to every company, and fit each overflow's layer 2 only on
its record after a start date. This file is that test.

**What layer 2 is today** (`src/dipcast/model/spill_model.py`, `fit_site_offsets`). For each overflow it adds a
log-odds offset log((n + 15) / (e + 15)), where n is the overflow's observed spill-days, e the spill-days layer 1
expected on the same days, and 15 the prior's pseudo spill-days (`PRIOR_STRENGTH`). Production's 2,271 offsets
are all United Utilities overflows, fitted on 2023 to 2025. Every other company's overflows have an offset of 0.

**Two things change at once under option B**, and the test keeps them apart:
1. **The extension.** Every company's overflows get an offset.
2. **The start date.** Each offset is fitted only on days after the overflow's start date.

PR #251 (`docs/NINE-COMPANY-MODEL-TEST-2026-10.md`) found that offsets fitted on one wet year hurt Anglian and
Thames in the next. So the extension alone is not assumed to help. It is measured (condition 5).

## Seen before writing

What the writer of this file read, and nothing else:
- `docs/UPGRADED-OVERFLOWS-2026-10.md` in full. Its Ilkley figures are therefore seen: the six named overflows'
  and the ten others' expected and observed spill days by season in 2024 to 2026, each overflow's last discharge
  in 2026, the forecast log's lead-0 sums for 14 Sep to 20 Oct 2026, Middleton's `lta_spills` curve, and
  Cromwheel's level changes.
- The first five lines of `docs/UPGRADED-OVERFLOWS-2026-10-silence.csv` (counts of silent Yorkshire Water
  overflows; no ids), and the ids and first two rows of `docs/UPGRADED-OVERFLOWS-2026-10-upstream.csv` (the 16
  overflows upstream of Cromwheel, with weights and 2025 return figures).
- The first 80 lines of `scripts/check_upgraded_overflows.py`.
- Code: `src/dipcast/model/spill_model.py` in full; parts of `src/dipcast/ingest/live.py` (feed fields, record
  stamps, `frozen_records`, `data_states`, `coverage_rows`, `save_live`), `src/dipcast/forecast_log.py` (scoring
  rules, `MAX_GAP_H`, `observed_spill_days`, `observations_from`, `coverage_checks`, the `forecast_overflows`
  columns), `src/dipcast/model/forecast.py` (where `p_raw` and `p_cal` are made), `rainfall.call_weight`, and
  `scripts/train.py`'s use of `fit_site_offsets`.
- The house tests: `docs/LIVE-STATUS-FEATURE-TEST-2026-10.md` (statement and the first lines of its results),
  `docs/LIVE-STATUS-SHADOW-TEST-2026-10.md`, `docs/NINE-COMPANY-MODEL-TEST-2026-10.md`,
  `docs/DIEOFF-WEATHER-TEST-2026-10.md`, `docs/DRY-SPELL-TEST-2026-10.md` (from branch `model/dry-spell-test`),
  `docs/PREREGISTRATION-2027.md` (sections 2, 9 to 12, 15 to 17), and the opening of
  `docs/LEAD-CALIBRATION-B-TEST-2026-10.md`.
- The list of open PRs on GitHub, 24 Oct 2026. None of them fixes the EA import route.

Also seen before this file, by anyone, and so not usable as a fair test:
- The published live scores of production (`verification_live.json`, the Accuracy page), by company, from
  29 Sep 2026. No score of any option B forecast exists.
- PR #251's 2025 scores by company. 2025 is not scored here.

No EA event file, state release, rain file or forecast log was opened for this test. No candidate offset has been
fitted. Whether any of Ilkley's six crosses the change rule below was not worked out before the rule was fixed.

## The arms

All three use production's layer 1 unchanged: `data/processed/spill_model.pkl`, SHA-256 beginning `faa7917e`
(as recorded in `docs/DIEOFF-WEATHER-TEST-2026-10.md`). The harness records the full hash and stops if it differs.
Only the offsets differ.

| Arm | Offsets | Role |
|---|---|---|
| **P** | Production's: United Utilities only, fitted 2023-25; 0 elsewhere | What the site shows. The baseline |
| **B** | Every overflow of the nine companies, fitted on its record from its start date (rule below), with the dead-monitor check | The candidate |
| **B0** | As B, but every start date is the record's start | Reported, and used in condition 6 only. It isolates the start date |

B and B0 replace production's United Utilities offsets too. All offsets use prior strength 15 and recency 1, as
now. Nothing is tuned.

## The record each offset is fitted on

**Days.** Europe/London local days, as the live build and PR #298's hindcast use. (`scripts/train.py` floors UTC
days. This test does not, so the fit matches what the live forecast scores.)

**Spill-days, n.** A local day is a spill-day if an event touches it, by `features.spill_days` on the EA events and
by `forecast_log.observed_spill_days` on the polls.

**Expected, e.** Layer 1's chance for the day (`predict_pooled`, no offset, no lead map), on ERA5-Land archive rain,
with the covariates of the year before's return, as `fit_site_offsets` and PR #298's hindcast do.

**Sources, by date:**

| Days | Source | Which days count |
|---|---|---|
| 1 Jan 2024 to 31 Dec 2025 | EA start/stop files, 2024 and 2025 | PR #251's rule: the overflow-year has an event in the file or 0 spills in that year's return, and EDM operation of at least 50% in that year's return |
| 1 Jan to 31 Aug 2026 | EA start/stop file, 2026 year to August | Overflows that pass the dead-monitor check (below). There is no 2026 return yet to apply PR #251's rule |
| 1 to 27 Sep 2026 | none | Dropped for every overflow. The EA file ends on 31 Aug. The polls start on 11 Sep but carry no observation mask until 28 Sep, so a dry day cannot be confirmed |
| From 28 Sep 2026 | SwimSignal's polls (`live_history.parquet`, `live_coverage.parquet`) | The live labels' rule: a spill-day always counts; a dry day counts only if `forecast_log.covered_site_days` passes it |

United Utilities is read from the EA files, not the Stream feed, so every company comes through one route, as in
PR #251. PR #258's earlier histories (Northumbrian 2020-24, Wessex 2020-23, Thames from Dec 2022) are not used.

**Fits are monthly and look back only.** A fit dated F (the 1st of a month) uses only days up to F − 1. A forecast
issued on day D uses the latest fit dated on or before D. The fits are dated 1 Jan to 1 Nov 2026. So a score for
any day uses no event from that day or later. In production, B would refit on the same rule.

## The start date: a change-point rule, not cited dates

**The choice.** Start dates come from a rule applied to each overflow's own record, not from a file of cited
upgrade dates (option A's file).

**Why:**
- No citable completion date exists for Ilkley today. Yorkshire Water's page was in the future tense on
  21 Oct 2026 ("will all be completed in Summer 2026"; PR #298, section 2).
- A cited file needs a row and a source for every upgrade in England, checked by hand. A rule covers every
  overflow the same way, including ones nobody has written about.
- A rule also catches overflows that get worse. A file of upgrades does not.
- The cost is the dead-monitor risk: a rule reads a silent monitor as an upgrade. The check below answers that.

If option C's dated file (`data/raw/overflow_upgrades.csv`) exists when the test runs, the rule's start dates are
set beside its dates for its rows. That is reported, not used.

**The rule, at each fit dated F**, for overflow i:
1. Group its counted days into calendar months: n_m spill-days and e_m expected.
2. For each month c at which the record could split, take the before part (months before c) and the after part
   (c to the month of F − 1). A split is allowed only if the before part has e ≥ 10 and the after part e ≥ 5.
3. For each allowed split, the Poisson likelihood-ratio statistic for one rate against two:
   G = 2 × [n₁ ln(θ₁/θ) + n₂ ln(θ₂/θ)], where θ₁ = n₁/e₁, θ₂ = n₂/e₂, θ = (n₁ + n₂)/(e₁ + e₂), and 0 × ln 0 = 0.
4. Divide G by the company's dispersion φ at that fit: the Pearson statistic of every overflow-month of that
   company under each overflow's single rate, Σ (n_m − θ̂ e_m)² / (θ̂ e_m) over months with e_m > 0, divided by
   (months − overflows), and at least 1. This allows for spill-days that cluster beyond what layer 1 explains.
5. A split **passes** if G/φ ≥ 15.1 (a one-degree chi-square at 0.0001) and the rate changes at least twofold:
   θ₂/θ₁ ≤ 0.5 or θ₂/θ₁ ≥ 2.
6. If any split passes, the **start date** is the first day of the latest passing month c. Otherwise the start date
   is the start of the record (1 Jan 2024).
7. A start date from a **fall** (θ₂ < θ₁) is kept only if the overflow passes the dead-monitor check. A rise needs
   no check: a dead monitor cannot report spills.

The threshold is strict because the rule scans many splits at about 14,000 overflows. A false start date costs a
shorter record and an offset nearer the prior. A missed change costs a stale offset. Neither number was chosen by
looking at any outcome.

## The dead-monitor check

**The problem** (PR #298, section 2). Of 311 Yorkshire Water overflows with a live feed and a 2025 average of 30
to 45, 17 showed no discharge from before 1 April 2026. A silent monitor is not proof of an upgrade. **A silent
monitor must not lower the forecast.**

**What the repo has to test a monitor.** No feed carries a field that says a sensor works
(`ingest/live.py`: "No layer has a field for a record's validation"). What it does carry:
- the status at each poll: 1, 0, or −1 (offline), and −2/−3 for missing records and feeds that did not answer;
- each record's own stamp, which shows a record that has stopped updating in a feed that has not
  (`frozen_records`; Wessex's WSX10153 and WXW00014 are the named cases);
- per overflow and local day, in `live_coverage.parquet`: polls with a known status (`n_known`), with none
  (`n_unknown`), and known but stale (`n_stale`, which includes frozen records), and the half-hour observation
  mask (`slots`).

The EA files carry no coverage field. They list discharges only. The annual returns' EDM operation figure for
2026 will not exist until the 2026 returns are published (likely late March 2027, inferred in PR #298).

**The check.** An overflow's monitor **is reporting** if, over the reference period, all three hold:
1. at least 80% of its polls gave a known status: n_known / (n_known + n_unknown) ≥ 0.8;
2. at a company that stamps every record (`stamps_every_record`), at most 20% of its known polls were stale;
3. at least 20 of the 28 local days had a known poll.

**The reference period** is 5 Oct to 1 Nov 2026, 28 local days. It starts the day after South West Water's stamps
were first read (4 Oct 2026). It is the earliest stretch with masks and readable stamps at all nine companies.
Every fit in this test reads that one period. In production the check would read the 28 days before each fit.
This is lookahead about the monitor, not about spills: the counts are of polls, not of discharges.

At companies that stamp a record only when it changes (Northumbrian and Southern), condition 2 is not applied,
because a quiet record there is not a frozen one (`ingest/live.py`).

**What the check does in the fit.** For an overflow that is **not reporting**:
- no start date from a fall is kept (rule step 7);
- every counted day after its last recorded spill-day (EA or polls) is dropped from n and e. So its silence adds
  nothing to e, and its offset can only stay or rise against a fit that ignored the silence.

An overflow not reporting that never spilled in its record keeps an offset of 0: layer 1 alone.

B0 gets the same treatment, so B and B0 differ only by start dates.

**What it cannot catch, stated now.** A sensor that is broken but reports 0 with fresh stamps passes the check. So
does a monitor that was dead in spring 2026 and mended by October. The test cannot see either. The 2026 annual
returns' EDM operation figure is reported beside the result if it is out before the decision (below).

## The two scoring windows

**Window E: the EA file, 1 Jan to 31 Aug 2026, lead 0.**
- **Rows.** Overflow-days of the nine English companies' overflows with a position and covariates in the 2025
  return, EDM operation of at least 50% in 2025, finite ERA5-Land rain for the day, and a monitor that passes the
  dead-monitor check. The check is the row filter because the file cannot tell a dry day from a dead monitor.
  So in window E every scored overflow is reporting, and the check never fires there.
- **Forecasts.** A hindcast of every day at lead 0 on ERA5-Land rain: `predict` with each arm's offsets, then the
  lead-0 map (`forecast.calibrate_at_lead`), as PR #298's "expected" was made.
- **Labels.** Spill-day or not, from the 2026 EA file.

**Window L: the live labels, target days 29 Sep to 30 Nov 2026, leads 0 to 4.**
- **Rows.** The scored rows the build publishes (`data/verification_live.csv`), as `forecast_log.verify_live`
  selects them: the latest forecast issued by 08:00 local, overflows with a live feed, the coverage rules, rain
  present. Taken from a `state` release made on or after 2 Dec 2026, so the next-day rule has run for 30 Nov.
- **Forecasts.** P is the logged `p_cal`. B and B0 are made from the same logged row: logit(`p_raw`) − P's offset
  + the arm's offset, with `p_raw` clipped to [0.0001, 0.9999], then the lead map that the row's version stamp
  names (`cal=` part). So all three arms share each row's forecast rain and lead map. If the lead-calibration B
  map (`docs/LEAD-CALIBRATION-B-TEST-2026-10.md`) is adopted inside the window, rows after that date take it in
  every arm.
- **Labels.** The poll-based live labels `verify_live` already gives (PR #253's method).

**Both windows**, rows with no forecast in any arm are dropped from all three and counted.

**Ilkley is not in the deciding scores.** PR #298 published 2026 expected and observed spill days for all 16
overflows upstream of Cromwheel: the six named (YWS00176, YWS00674, YWS00179, YWS00191, YWS00144, YWS00145) and
the ten others in `docs/UPGRADED-OVERFLOWS-2026-10-upstream.csv`. A test set chosen after its outcome was seen is
not a fair one. All 16 are left out of every condition and scored as a described case (below).

The 17 silent Yorkshire Water overflows in PR #298's count stay in. What was seen of them is a count of silence,
not their ids and not any forecast's score.

## The score

**Brier score** on spill-days per overflow-day, for each arm, by company and for the nine together, in each
window. In window L, leads 0 to 4 are pooled for the conditions and reported one by one.

**ECE** as PR #251 defined it (`training.ece`, 10 equal-width bins, weighted by rows).

**The interval.** The 2027 protocol's two-way cluster bootstrap (`docs/PREREGISTRATION-2027.md`, section 10),
applied to the difference in Brier, row by row:
- each draw resamples overflows with replacement and, independently, ISO weeks of the target day with
  replacement; a row counts (times its overflow was drawn) × (times its week was drawn);
- all leads of an overflow-day share both draws;
- 2,000 draws from `numpy.random.default_rng(20261024)`, made once per window, overflows first, then weeks; every
  company, subset and lead in a window uses the same draws;
- the 95% interval runs from the 2.5th to the 97.5th percentile.

*Why two-way, and not the week alone as in PRs #254 and #262.* Option B changes each overflow's level. Its errors
are therefore shared by every day of an overflow, as well as by every overflow in a storm. A week-only interval
would understate the first. The week-only interval is reported beside it, not deciding.

**Unchanged and changed overflows.** An overflow is **changed** in a window if any fit used for that window's
forecasts gave it a start date after 1 Jan 2024. Every other overflow is **unchanged**. At an unchanged overflow,
B equals B0.

## Conditions

B **passes** only if all seven hold.

1. **A gain in window E.** Nine together, B's Brier is lower than P's, and the 95% interval of B − P lies wholly
   below zero.
2. **No loss in window L.** Nine together, the interval of B − P does not lie wholly above zero, and B's Brier is
   no more than 1% above P's.
3. **No company clearly worse.** In each window, at every company with at least 200 spill rows, the interval of
   B − P does not lie wholly above zero.
4. **Reliability, window E.** At each such company, B's ECE is no higher than P's, or it is at most 0.02.
5. **No worse where nothing changed.** In each window, on the unchanged overflows' rows, nine together: the
   interval of B − P does not lie wholly above zero, and B's Brier is no more than 1% above P's. This is the
   extension on its own. PR #251 is the reason to test it.
6. **The start dates earn their place.** In each window, on the changed overflows' rows from each one's first
   start date onward, B's Brier is lower than B0's. At least 30 overflows are changed in window E. The interval
   is reported, not required: the changed set will be small.
7. **The dead-monitor rule fires correctly.** All three hold. They are checked first, and the run stops before any
   score if one fails.
   - (a) **No silence lowers a non-reporting overflow.** At every fit, every overflow that is not reporting has no
     start date from a fall and no counted day after its last spill-day. 0 violations.
   - (b) **Frozen records are caught.** Every overflow at a company that stamps every record, whose own stamp at
     the last poll of the reference period is more than 7 days old, fails the check. This includes WSX10153 and
     WXW00014 if they are still frozen. 100%.
   - (c) **Planted dead monitors are caught.** 200 overflows are drawn with `default_rng(20261024)` from those
     that pass the check and have at least 3 spill-days in 2026. In a copy of the data, their events after
     31 Mar 2026 are deleted and every poll of theirs in the reference period is set to offline (−1). All 200
     must fail the check, and each one's B offset must equal its offset fitted on its days up to its last
     remaining spill-day. 100%.

**Face checks, run before any score** (the run stops on any failure):
- B with every offset set to P's reproduces P to within 1e-12 on every row, in both windows.
- In window L, P's rebuilt forecast (`p_raw` through the row's map) equals the logged `p_cal` to within 1e-6, and
  the logged `p_cal` equals the published `forecast_calibrated` to within 0.0001 (the CSV's rounding).
- In window E, P's hindcast for the six named Ilkley overflows, April to August 2026, sums to 23.0 expected
  spill-days, ±0.1 (PR #298, section 2). This checks the hindcast path against a published figure. It is the only
  use of the Ilkley figures, and it scores nothing.

**Minimum data.** Window E: every company in condition 3 needs its 2026 file (see "Data"). Window L: at least
1,000 spill rows pooled over leads, nine together. Window L is in the past when the test runs, so it cannot be
extended. If it falls short, conditions 2, 3 (for L) and 5 (for L) are inconclusive and B does not pass.

## Reported, not deciding

- Every arm's Brier, difference and both intervals, by company, window and (in L) lead.
- B0 against P, by company and window.
- How many start dates the rule set, by company, fit and direction (fall or rise), and how many falls the
  dead-monitor check refused.
- By company, how many overflows pass and fail the check, and among overflows with no spill in the 6 months before
  the last fit, how many pass. PR #298's 17 of 311 is the comparison.
- **The Ilkley case.** For the six named and the ten others separately: the start date each fit gave (or none),
  the check's verdict, and expected spill-days under P, B and B0 against observed, by window. Cromwheel's level on
  each day of both windows under P and B, as PR #298's section 3 tabulated it. This decides nothing.
- If `data/raw/overflow_upgrades.csv` exists: its dates beside the rule's.
- **If the 2026 annual returns are published before the decision:** window E rescored with the 2026 EDM operation
  figure (at least 50%) added to the row filter. This shows how far a monitor dead in spring could have moved the
  result.

## Data this depends on

- **The EA import route is broken.** On 22 Oct 2026 the per-company files that `scripts/import_ea_events.py`
  downloads returned ResourceNotFound. The EA revised the dataset on 20 Oct, and the data now comes as one zip per
  year through the same signed-link route (PR #298, "Follow-ups"). Another PR is fixing the importer. It was not
  open on GitHub when this was written. **This test waits for it.** All three years (2024, 2025 and 2026 to August)
  are read from the yearly zips as downloaded on one day, with their SHA-256 recorded. PR #251's earlier
  per-company imports are not mixed in, because the 20 Oct revision may have changed them.
- **2026 year to date for all companies: to be confirmed.** PR #298 says the "2026 year to August" zip holds all
  ten companies' files to August. Only Yorkshire Water's was opened. At import, each of the nine English
  companies' 2026 file is checked for events in every month from January to August. Only event counts per month
  are read, and no forecast is compared. A company whose file is missing or lacks a month leaves window E in all
  three arms, and its 2026 EA days leave the fits. It is reported.
- **ERA5-Land rain for 2026.** Every cell of the nine companies' overflows needs 1 Jan to 31 Oct 2026. PR #251
  cached 2024 and 2025 in `data/cache/rain_nine/`; 2026 is cached for United Utilities' cells only (inferred from
  PR #251's "Seen before writing"; to be confirmed). By `rainfall.call_weight`, 304 days of one variable weigh
  about 2.2 calls a cell, so roughly 3,600 calls for about 1,650 cells (inferred; counted exactly before the
  fetch). The fetch needs Ethan's approval, as PR #251's did. It is paced, strict, and not run beside a build or
  another fetch on this machine.
- **The state release.** `live_history.parquet`, `live_coverage.parquet`, `poll_log.parquet` and `dipcast.duckdb`
  from one release made on or after 2 Dec 2026, downloaded read-only, with hashes recorded.
- **The annual returns.** `data/processed/annual_returns.parquet` as on main (last changed 13 Sep 2026). If it is
  refreshed before the run, the run uses the 13 Sep file, so layer 1's inputs match production's in 2026.

## What follows

**All seven pass.** B goes to a live shadow, as PR #262 did for the live-status input:
- B's offsets are fitted on 1 Jan 2027 by the rule above, on the EA files and the polls to 31 Dec 2026, and held
  fixed for the window. The dead-monitor check reads the 28 days before the fit.
- `forecast_overflows` gains one column, `p_offsets`: B's forecast at every lead. Nothing published reads it.
- **The window** opens on the first target day whose 08:00 forecasts carried it at every lead 0 to 4, and runs 28
  target days. With the code merged by mid-January 2027, it runs about late January to late February 2027.
- **Shadow conditions**, on the scored live rows, leads pooled, with this file's bootstrap: (1) nine together, the
  interval of B − P does not lie wholly above zero; (2) no company with at least 200 spill rows has an interval
  wholly above zero; (3) ECE at each such company no higher than P's, or at most 0.02; (4) on unchanged overflows,
  the interval does not lie wholly above zero.
- **If the shadow passes,** adoption is its own PR, Ethan's call, merged by 31 March 2027. That leaves the 2027
  freeze steps their dates: the mid-April decision on refreshing the annual returns, and the tag by 30 April
  2027. If the returns are refreshed, layer 1's inputs change for every overflow, and B's offsets are refitted by
  the same rule before the tag.
- **After the tag.** A monthly refit changes `spill_model.pkl`, which is in `MODEL_PATHS`, so each refit would be
  a candidate under the 2027 protocol (section 12). So either B's offsets are frozen at the tag, or an amendment
  to section 17 makes the refit rule part of the frozen model before 30 April 2027. This is Ethan's decision
  before adoption.

**Any of 1 to 6 fails.** Nothing changes. Option C stays as the page's answer. This file and the results are the
record. If only condition 6 fails, B0 is not adopted either: it was not the stated candidate, and a test of it
needs its own statement.

**Condition 7 fails.** The run stops before any score. The fault is reported. A changed rule needs a new statement.

**Late data.** If the run has not happened by 31 January 2027 (for example, the importer is not fixed), there is no
time for a 28-day shadow before the tag. The test still runs, but nothing is adopted for 2027. A pass then makes a
candidate for after the season (2027 protocol, section 12).

## Expected, stated now (inferred, not conditions)

- **Condition 5 is the main risk.** PR #251's one-year offsets hurt Anglian and Thames. B fits on up to 32 months,
  which should help, but Thames's merged events and Anglian's 2024 event count make those two the likeliest
  failures.
- **Condition 6 may lack data.** At a strict threshold, few overflows will get a start date by 1 Aug 2026. Most
  that do will be falls in spring 2026, and window E leaves them only a few months.
- **The prior slows everything.** With 15 pseudo spill-days, a quiet overflow's offset falls slowly (PR #298
  worked one case: 0.70 after six months). So even where the rule fires, the forecast moves little in 2026.
- **Window L is autumn.** Both 2025 and 2026 over-forecast in autumn (PR #253). That is shared by every arm.

## Not chosen, and why

- **A cited-dates file as the start-date rule.** No date can be cited for Ilkley, and a national file is hand
  work. Reported beside the rule if it exists.
- **A trailing window (`recency` below 1, or the last 12 months only).** It needs no start date, but it forgets an
  overflow's level even when nothing changed, and option B names start dates.
- **A smaller prior.** It would make B move faster, but choosing it would be tuning, and PR #251 found fast offsets
  carry one year's weather into the next.
- **Refitting layer 1.** PR #251's nine-company layer 1 was not adopted. This test changes offsets only.
- **Start dates by day, or several change-points.** Months smooth single storms. The latest change is the one the
  forecast needs.
- **The 2026 annual returns as the dead-monitor check.** They are likely out in late March 2027, too late for a
  shadow before the tag. They are a reported sensitivity.
- **Scoring the Ilkley six.** Their 2026 outcome is published. Any test that counted them would be partly fitted to
  them.

## Order of work, after approval

1. Ethan approves this statement. Nothing below runs before.
2. The importer fix is merged. The yearly zips are imported, and the per-company 2026 coverage check runs.
3. The 2026 ERA5-Land fetch, with its call count first and Ethan's approval.
4. The harness (`scripts/upgraded_overflows_b/`) is committed after this file and before any run. It does not
   change anything above the line.
5. On or after 2 Dec 2026: the state release is downloaded. The run goes from a `git archive` of the harness
   commit, offline (`scripts/lake_distance_eval/run_offline.py`), on a frozen copy of the data folder whose hashes
   go in the results. One run, alone on this machine (`pgrep -fl`, never `pkill`).
6. Condition 7 and the face checks, then the scores. The results go below the line.

---

## Results

Not yet run.
