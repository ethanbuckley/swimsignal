# Spot-level scoring: the open points, for Ethan to rule on

**Status: draft. Nothing here is in force.** Pull request #335 builds score S1 of `docs/PREREGISTRATION-2027.md`,
amendment 1: the file `verification_spots_live.csv` (file D) and the Accuracy page's section "How the level itself
has done". Amendment 1 leaves ten points open, and an eleventh came up while the options were being measured.
They are definitions of the score, so they are Ethan's to sign.

For each point: the options, the recommended answer, why, and what it changes. The last part is a draft
amendment 2. It would be needed before `scripts/evaluate_2027.py` gains S1 and S2, because changing that file
changes the SHA-256 that section 13 records.

**Where the figures come from.** The `state` release of 24 October 2026 (09:51 UTC), read only. Target days 12 to
23 October. #335's code at `b79a23d`, with a frozen copy of `overflows.parquet` for companies and the climatology
index. Each option was run by replacing one step of `forecast_log.verify_spots` in a scratch copy, with no change to
the code in git. As built, the window has 80 eligible spots and 4,800 spot-day cells. 2,803 of the cells are
observed, with 96 hits, 101 misses and 80 false alarms at the High line. Eleven days is too few to judge the
forecast. It is enough to show which rules move the counts.

## Summary

| # | Point | Recommended | Code change | Effect on 12–23 Oct |
|---|---|---|---|---|
| 1 | A seen spill on a day that fails the coverage rule | Not an observation, as for the primary scores (as built) | None | None |
| 2 | The unobserved weight, up to 5% | Left out of `o`, as if no spill (as built) | None | At most 6 of 2,803 cells could become events |
| 3 | Bands: raw index or the shown score | The shown score, as the page and alerts use | Yes | Events 197 → 202; 44 forecast cells change level |
| 4 | No forecast by 08:00 | `observed` empty (as built) | None | 0 cells |
| 5 | A forecast with no logged risk | Kept whole, risk empty, not scored (as `b79a23d`) | None | 0 cells |
| 6 | When the eligible spots are frozen | At the tag, by script; the script is due 31 January | Script and test | 80 eligible now |
| 7 | Spots never observed: 8, not 3 | Keep the 95% rule; list them; fix the expected size | Words only | Leaving the rule out would add 240 cells and 81 events |
| 8 | The S1 reference cannot be made from D | Add a `climatology` column to D | Yes | None to the scores |
| 9 | A whole-day travel time | One source day, as `shift_by_travel` (as built) | None | 0 of 23,584 sampled links |
| 10 | Weeks on the page and blocks in the evaluation | Keep both | None | None |
| 11 | Rounding in the published file | Publish 6 decimal places; the build's figures come from the published rows | Yes | The CSV gives 97 hits where the build said 96 |

## 1. A seen spill on a day that fails the coverage rule

Amendment 1 says a spot-day is observed when its overflows each have "a section 5 observation (spill or no spill)"
on every source day. Section 5 sets out a spill rule and a no-spill rule. Its coverage rule is written under "No
spill". But the live scorer it describes applies coverage to every overflow-day, spill or not
(`verify_live` drops uncovered days before it looks for spills).

- **A (as built).** An overflow-day is an observation only when it passes the coverage rule. A spill seen on a
  day that fails it is not used. This is the rule behind `verification_live.csv` and the four primary outcomes.
- **B.** A seen spill counts as `e = 1` even on a day that fails coverage. Only "no spill" needs coverage.

**Recommended: A.** Under B, a poorly observed overflow-day is kept when it spilled and dropped when it did not.
That raises the observed index on exactly the days the data are weakest, the selection effect section 9 warns
about. Under A, a day is kept or dropped for the same reason whatever happened on it. A also keeps S1 on the same
observations as the primary scores.

**What it changes.** Nothing in the code. On 12–23 October, 323 of 12,938 spill overflow-days failed coverage.
Under B, no spot-day changed: none was observed or became an event. This is the measured result. Why there is no
change is inferred: on those days other overflows at the same spots failed coverage too.

## 2. The unobserved weight, up to 5%

A spot-day is observed when overflows carrying at least 95% of its weight are observed. Amendment 1 does not say
what the other 5% or less contributes to `o`.

- **A (as built).** Left out, as if those overflows did not spill. `o` is then a lower bound. `covered` says how
  much weight was seen.
- **B.** Put in their forecast chance.
- **C.** Publish an upper bound as well, with each unobserved overflow-day taken as a spill.

**Recommended: A.** B puts the forecast on both sides of the comparison, which pulls the observation towards the
forecast. C adds a column to answer a small effect: on the 2,803 observed cells, taking every unobserved
overflow-day as a spill raised `o` by at most 0.22, and 6 cells crossed 0.40.

**What it changes.** Nothing in the code. The amendment would state that `o` is a lower bound.

## 3. Bands: the raw index or the score the page shows

Amendment 1 and section 6 band the index at 0.15, 0.40 and 0.70. Section 6 also names `transport.risk_label` as
the place in the code that applies those bands. Since 23 October 2026 (commit `5ba1285`, "label a day by the score
shown"), `risk_label` and `levels.js` take the level from the 0–100 score the page shows. That score is the index
rounded to 3 decimal places, times 100, rounded half up. So 0.3995 shows as 40, reads High risk and sends an alert.
The raw cut puts it at Moderate risk.

- **A (as built).** Raw cuts on the unrounded index.
- **B.** The level rule of `transport.risk_label`, on the forecast and on `o` alike.

**Recommended: B.** The amendment was written to say "how often an alert was right". An alert fires on the level
the page shows, so the score should use that level. Section 6 already points at `risk_label`. B keeps the
protocol pointing at it.

**What it changes.** `verify_spots` and the S1 code band through one function equal to `risk_label`. On the
published rows the High line moves from 97 hits, 100 misses and 80 false alarms (raw) to 99, 103 and 85 (shown).
Events go from 197 to 202. 44 of 4,800 forecast cells change level.

## 4. No forecast by 08:00

Amendment 1 says only that `issued_at`, `forecast` and `version` are empty when no forecast was out by 08:00.

- **A (as built).** `observed` is empty too, with reason `missed_deadline` (a forecast came later that day) or
  `no_forecast` (none that day).
- **B.** Build `o` from the weights of that day's first later forecast.

**Recommended: A.** S1 scores pairs. A cell with no forecast is unscored under either option, so B's `o` would
be a figure nothing uses. It would also rest on a forecast that D does not name.

**What it changes.** Nothing. There were 0 such cells on 12–23 October: every eligible spot had a forecast by 08:00
at every lead.

## 5. A forecast logged with no risk

The forecast logs a NULL risk when too much of the spot's weight comes from cells without rain data.

- **A (as now on #335, `b79a23d`).** The latest forecast by 08:00 is kept as one whole row. A NULL risk stays
  empty: not imputed, not a forecast, not scored, but counted, with its issue time and version.
- **B.** Fall back to the latest forecast by 08:00 that has a risk. This is what `select_decision_forecasts`
  does for overflows, where rows without rain data are dropped before the latest is picked.

**Recommended: A.** At 08:00 the page showed that latest forecast, so the score should too. Section 9 forbids
imputing. B would score a forecast the swimmer did not see. The overflow scorer differs because it scores each
overflow's chance, which needs rain at that one cell. Its rule is registered and unchanged.

**What it changes.** Nothing in the code. #335's first description said the code already did A. It did not:
`groupby().last()` took each column's last non-null value separately, so a later row with no risk carried an
earlier forecast's risk under its own issue time. `b79a23d` fixed it. There were 0 such cells in the window. 225 of
66,790 spot forecasts since 12 October have a NULL risk, but none was the latest by 08:00.

## 6. When the eligible spots are frozen

Amendment 1 calls the list "the spots in `spots.csv` and `spots-osm.csv` at the tag". It also says the list is
"frozen with D", and D is due 31 January. The two dates conflict.

- **A.** The 31 January deliverable is the script that makes the list, with its tests. The list is made from the
  tagged build and recorded in section 17 in the tag's pull request, with the other hashes of section 15, step 4.
- **B.** Freeze the list on 31 January. A spot added or changed later is not evaluated.

**Recommended: A.** A spot's overflows still change between builds. On 12 October the River Rivelin spot lost the
overflows it had before; the River Test at Chilbolton gained some. A January list could score spots the tagged
model sees differently.

The rule, unchanged in substance:

- An eligible spot is in `spots.csv` or `spots-osm.csv` (both list English spots only).
- It has at least one monitored overflow, with or without a live feed, in the tagged build's upstream file.
- Each excluded spot is listed with its reason.

**What it changes.** `scripts/make_eval2027.py` gains a `--spots` mode with a test, by 31 January. The live
file keeps its own rule: a spot whose forecast with travel times had an overflow upstream. That gives 80 spots now,
with 22 left out because they have no overflow upstream.

## 7. Spots never observed: 8, not the 3 the amendment named

Amendment 1 named three spots whose overflows without a live feed carry over 5% of their weight: Sandy Lane
(Chester) and the Wye at Hereford and at Symonds Yat, all Dŵr Cymru's. In the live data there are five more. At
each, overflows of its own English company that are missing from the company's live feed carry the weight:

| Spot | Weight with no live feed | Company |
|---|---:|---|
| River Avon, Warleigh Weir | 6.4% | Wessex Water |
| River Severn at Ironbridge | 5.3% | Severn Trent Water |
| Ham and Kingston, River Thames | 10.2% | Thames Water |
| River Medway, Tonbridge | 18.1% | Southern Water |
| River Wharfe, Greenholme | 7.5% | Yorkshire Water |

- **A.** Keep the 95% rule. List these spots as never observed, and correct the expected size.
- **B.** Leave the overflows with no live feed out of the weight, and score these spots over their live overflows
  only.
- **C.** Report B as a secondary stratum beside A.

**Recommended: A.** The forecast index counts those overflows, and `o` cannot. Under B, a warning driven partly
by an unseen overflow would be scored against an observation that leaves it out. Measured, B adds 240 observed
cells, raises the events from 197 to 278, and the hits from 96 to 157. A shift that large from spots where the two
sides do not count the same overflows is the reason not to mix them in. C reports it, but beside the main figures
it invites the larger counts to be quoted.

**What it changes.** Words only. The expected size becomes about 72 spots (80 less 8) × 153 days × 5 leads =
55,080 cells, against the amendment's 58,905. The list at the tag may differ.

## 8. The S1 reference cannot be made from file D

S1's reference is the same combination with each overflow's primary reference, `c × f`, in place of its chance.
That needs each overflow's weight and travel time, and D carries neither. The build computes the reference
(`live.spots_live.overall.climatology` in `verification.json`), but `evaluate_2027.py`, which reads only published
files, cannot.

- **A.** Add a column `climatology` to D: the reference index for the cell, as the build computes it. This is how
  `verification_live.csv` carries `climatology` for overflows.
- **B.** Publish each forecast's overflows, weights and travel times. That is a second large file.
- **C.** Drop the reference from S1.

**Recommended: A.** One column, the same pattern as the overflow file, and the reference stays.

**What it changes.** `SPOT_COLUMNS` gains `climatology` (after `observed`), and the CSV header says what it is.
The scores do not change. `c` is the published `climatology` of each overflow at build time, as for the primary
reference. `f` is the month factor in `data/eval2027/climatology.json` for the source day's month.

## 9. A whole-day travel time

`shift_by_travel` splits a day between `k = floor(t/24)` days back (share `1 - a`) and `k + 1` (share `a`). When
`t` is a whole number of days, `a = 0`.

- **A (as built).** The second day carries nothing, so it is not a source day and need not be observed.
- **B.** Require it to be observed anyway.

**Recommended: A.** It is what the forecast's own transport does. A day that contributes nothing cannot change
`o`.

**What it changes.** Nothing. 0 of 23,584 sampled links since 20 October had a whole-day travel time.

## 10. Weeks on the page, blocks in the evaluation

The Accuracy page shows the mean forecast against the mean `o` by Monday week, like its other weekly tables.
Amendment 1 asks for the same by 7-day block, and section 10's blocks start on 1 May 2027.

**Recommended: keep both.** The page runs all year. The evaluation runs once, on the season. No change.

## 11. Rounding in the published file (found while measuring)

`verify_spots` writes the CSV at 4 decimal places, but computes the page's figures from unrounded values. A value
just under 0.40 is written as 0.4000. On 12–23 October the published rows give 97 hits and 100 misses, against the
build's 96 and 101. The 2027 script reads the CSV, so it could disagree with the page.

- **A.** Write `forecast`, `observed`, `covered` and `climatology` at 6 decimal places, and compute the build's
  figures from the rows as written.
- **B.** Add level columns computed before rounding.

**Recommended: A.** The page and the 2027 script then read the same numbers, so they cannot disagree. Under
point 3's B, the level comes from the published value by `risk_label`'s rule, in Python and in the script alike.

**What it changes.** `verify_spots` writes at 6 places, then builds `spot_summary` from the rounded rows. Each row
gains two digits in four columns.

---

## Draft amendment 2, not in force until Ethan signs it

*To go in `docs/PREREGISTRATION-2027.md` after amendment 1, in its own pull request, once signed. The text assumes
the recommended answers above. A different ruling changes the matching item.*

### Amendment 2, [date of signing]: the spot-level score made exact, and S1 and S2 in the evaluation script

**Why.** Amendment 1 added two secondary scores for a spot's level, S1 and S2, and file D. Building D (#335) found
eleven points it left open. A score that is not fully defined can be tuned after the fact. So each point is fixed
here, before any season data exist. This amendment also lets `scripts/evaluate_2027.py` gain S1 and S2, which
changes its hash in section 13.

Nothing here changes the four primary outcomes, their data, rules or seed. S1 and S2 stay secondary.

**Definitions for S1** (each numbered as in `docs/SPOT-SCORING-RULINGS-2026-10.md`):

1. An overflow-day has an observation only when it passes section 5's coverage rule, whether it spilled or not.
   This is the rule the primary spill scores use.
2. Overflows without an observation on every source day are left out of `o`, as if they had not spilled. With
   under 5% of the weight unobserved, `o` is a lower bound.
3. A level is the one `transport.risk_label` gives: the index rounded to 3 decimal places, times 100, rounded
   half up, then Low risk under 15, Moderate risk from 15, High risk from 40, Very high risk from 70. It applies to
   the forecast, to `o` and to the reference alike. The event is `o` at High risk or above. A forecast at High risk
   or above is a warning. This replaces the raw cuts of amendment 1 for S1 and S2.
4. Where no forecast was out by 08:00, `observed` is empty too. The reason is `missed_deadline` when a forecast
   came later that issue day, and `no_forecast` when none did.
5. The forecast scored is the latest by 08:00, taken as one whole row. If its risk is empty, the cell has no
   forecast. It is counted, not scored, and never filled from another forecast.
6. A source day that carries no share of the target day (a whole-day travel time) is not a source day.
7. The 95% rule stands. Every spot whose overflows without a live feed carry over 5% of its weight is listed as
   never observed, with that share.

**File D, changed.**

- D gains a column `climatology` after `observed`: the reference index for the cell, with each overflow's
  `clip(c × f, 0.001, 0.95)` in place of its chance. `c` is the overflow's `climatology` as
  `verification_live.csv` publishes it. `f` is the month factor of the source day in
  `data/eval2027/climatology.json`.
- `forecast`, `observed`, `covered` and `climatology` are written at 6 decimal places. Every figure the site shows
  for the spot level is computed from the rows as written.

**Eligible spots, frozen at the tag.** The list `data/eval2027/spots.csv` is made from the tagged build, by
`scripts/make_eval2027.py --spots`, from the build's `spots.json` and upstream files. An eligible spot is in
`spots.csv` or `spots-osm.csv` and has at least one monitored overflow, with or without a live feed, in its
upstream file. Each excluded spot is listed with its reason. The list's SHA-256 is recorded in section 17 in the
pull request of section 15, step 4. The script and its tests are due by 31 January 2027. The list is not.

**Expected size,** inferred and not a promise: about 72 spots × 153 days × 5 leads = 55,080 cells. That is the 80
spots with an overflow upstream on 24 October 2026, less the 8 never observed.

**S1 in `evaluate_2027.py`.**

- New inputs: `--spots`, the published `verification_spots_live.csv`, and `--spot-list`, `data/eval2027/spots.csv`.
- **Cells.** Every listed spot × season day × lead 0 to 4. A cell is scored when it has both a forecast and an
  observation. The rest are counted by reason, by lead and by 7-day block.
- **Frozen-model check.** By `version`, as `split_versions` does for the primary scores.
- **Reported:** amendment 1's list, on the levels of item 3.
  - The alert's record at the High line.
  - The AUC of the forecast index for the event.
  - The four-by-four table of forecast level against observed level.
  - The mean forecast beside the mean `o` by 7-day block.
  - The reference's alert record and AUC beside the forecast's.
- **Strata.** By lead; same day and in advance; river and lake spots; and the company of the overflow with the
  largest weight in the cell's forecast.
- **Intervals.** Amendment 1's bootstrap: spots as the sites, section 10's blocks, 2,000 draws from
  `default_rng(20270502)`.

**S2 in `evaluate_2027.py`.**

- It reads prerequisite B's `exposure` column: the spot's forecast index, the latest issued before the sample, at
  each lead.
- Levels follow item 3.
- Reported for rivers and lakes apart, as amendment 1 says:
  - the AUC for a sample over 900;
  - the share over 900 at each level, with intervals;
  - the alert's record at the High line.
- Same bootstrap as S1, with bathing waters as the sites.
- S2 cannot run before B carries `exposure`.

**Code and hashes.**

- S1 and S2 come in one pull request, with tests and a dry run on autumn 2026 from 12 October, in section 14's
  form.
- That pull request replaces section 13's SHA-256 for `scripts/evaluate_2027.py` with the hash at its merge, and
  `tests/test_evaluate_2027.py` checks the new one.
- The changes to file D (items 3 and 11, and the `climatology` column) come in their own pull request first, with
  their tests.
- Until both are merged, section 13's hashes stand.

**Signed:** ______________________ (Ethan Buckley)  **Date:** ____________
