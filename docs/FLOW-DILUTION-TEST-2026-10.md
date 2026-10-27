# Dilution scaled by the river's measured flow: the test, stated before any score

Written 27 October 2026. **Approved by Ethan on 27 October 2026** (answers below "Questions for Ethan"); not yet
run. Ethan approved this statement before any run. Nothing below has been
scored. No E. coli value was read in writing it, no flow reading was fetched, and no model was fitted. Results go
below the line at the end. Nothing above the line changes after a result is seen. If anything is changed after a
result is seen, both results are kept and the change is stated.

## The question

Does scaling each overflow's dilution by the river's measured flow on the day improve the river E. coli estimate,
against the production river model as it is now (today's seven inputs plus soil moisture, PR #361)?

## Why

- The production dilution is static. It is `((L_up(overflow) + 5 km) / (L_up(spot) + 5 km)) ** 0.5`, capped at 1
  (`transport.upstream_overflows`, `DILUTION_POWER = 0.5`, fitted in `docs/TRANSPORT-FIT-TEST-2026-10.md`). The
  length ratio stands in for a ratio of flows. It is the same on a dry day and in a spate.
- Dr James Shucksmith's critique of 9 October 2026 asked for flow-based dilution and a speed per river. PR #166 added
  dilution mode `flow`, a spill of fixed size against an *estimated* median flow at the spot. It is also static. The
  critique PDF is private and was not reopened for this. Its points are as PR #166 and the spill-size statement
  record them.
- Three per-overflow size proxies failed on these rows: built-up area (`docs/URBAN-DILUTION-TEST-2026-10.md`), spill
  hours (`docs/SPILL-SIZE-TEST-2026-10.md`) and consented dry weather flow (`docs/PE-SIZE-TEST-2026-10.md`).
  `docs/TRANSPORT-FIT-2-TEST-2026-10.md` ended with "the dilution term is the open question".
- None of those used a measured flow, or a flow that changes from day to day. This test does. A spill into a river at
  summer low flow is diluted less than the same spill into a river in spate.

## The candidate

For each river spot with a flow gauge (next section), on each sample day:

    dilution_i,T = min(1, dilution_i × F_T)
    F_T          = clip((Q_ref / Q_T) ** k, 0.25, 4)

- `dilution_i`: production's dilution for overflow i at that spot, unchanged (length rule, lake factor and all).
- `Q_T`: the gauge's mean flow over the 24 hours published by the issue time (see "Timing").
- `Q_ref`: the same gauge's median daily-mean flow over May to September, 2014 to 2023 (see "Reference flow"). So
  `F_T` is 1 on a day of typical summer flow, above 1 at low flow and below 1 in spate. The spatial pattern stays with
  the length rule, which was fitted. Only the day-to-day change is new.
- **k = 0.5, fixed, not fitted.** It is the exponent the length ratio, a proxy for a flow ratio, was fitted at. So the
  measured flow ratio enters as the estimated one already does. k = 1 (plain dilution: concentration inversely
  proportional to flow) is reported as a secondary arm and decides nothing.
- The clip at 0.25 and 4 is reached only below 1/16 or above 16 times the summer median flow (at k = 0.5).
- The weight is `decay × dilution × other factors`, as now, with only the dilution term changed
  (`flow_protocol.flow_weights`). Speed, die-off, the spill model, the calibration and the transport code are
  unchanged. The exposure is production's lead-0 replay (`replay_ecoli_leads.combine_daily_leads` at k = 0) with
  weights by arrival day (`flow_protocol.exposure_lead0`; a test checks the two agree when the weights do not vary).
- **Fallback.** A spot with no gauge, a gauge without a reference flow, or a day whose window has too few readings
  gets `F_T` missing, and the production weight is used unchanged. The share of river rows with a factor is reported
  and gated.
- **Lakes are not touched.** Lake spots keep production exposure in every arm. Lakes use another model on the site
  (`ecoli_model.json`).

*Inferred, not tested.* At one spot every overflow gets the same `F_T`. When exposures are small,
`risk ≈ F_T × risk_production`, so the candidate adds about `k × ln(Q_ref / Q_T)` to `logit_risk` on that day. That is
close to adding an antecedent-flow term whose sign is fixed: more flow, less exposure.

## Which gauge

Gauges are EA Hydrology flow stations with a daily-mean measure (`...-flow-m-86400-m3s-qualified`) and a 15-minute
measure (`...-flow-i-900-m3s-qualified`), snapped within 250 m of a river link (`make_lake_spill_ratio`'s rule).

**Primary: the spot gauge** (`flow_protocol.choose_spot_gauge`). This is `scripts/glofas_check.py`'s rule from
PR #255, unchanged:
- on the spot's river path, upstream or downstream, within 25 km along the network;
- catchment (from the network's upstream length) within a factor of 2 of the spot's;
- not a part channel (EA label or river words: side, main, flume, fishladder, bypass, intake; relief, navigation,
  carrier, leat);
- the nearest along the network. A "Total" or "Combined" station at the same site goes first.

Why the spot, not each overflow. Dilution at the spot depends on the flow at the spot. A gauge just downstream with a
similar catchment measures it as well as one just upstream. The brief's example rule (a gauge below each overflow and
above the spot) leaves the overflows nearest the spot, which carry the most weight, without a gauge whenever the gauge
is above them. *Inferred from the rule, not counted.*

**Secondary: the per-overflow gauge** (the brief's example, `flow_protocol.choose_overflow_gauge`). For each overflow,
a gauge downstream of the overflow and upstream of the spot, on the spot's river name, with at least half the spot's
catchment, not a part channel: the one nearest the spot. An overflow without one keeps its production weight. It is
reported and decides nothing.

**Real-time or archive.** A gauge counts as on the real-time feed if its `stationReference`, `wiskiID` or `RLOIid`
is in the EA flood-monitoring list of flow stations (`/id/stations?parameter=flow`). This sets its publication lag.

The mapping is computed in the run on the run's network and pins (`score.py map`). The counts in "Seen before
writing" are the expectation from metadata, not the gate.

## Timing: only flow published before the issue time

- **Issue time** (lead 0): 09:00 London time on the sample's London date, or 1 hour before the sample if that is
  earlier (`flow_protocol.issue_time`). EA samples are taken between 10:00 and 14:00.
- **Publication lag:** 1 hour for a gauge on the real-time feed. The river-rises scope (PR #383) measured one snapshot
  on 26 October 2026: median age 0.5 h, 75th percentile 0.75 h. **36 hours** for a gauge only in the Hydrology
  archive. The same work found the Hydrology series "current to within a day". 36 h adds a margin.
  *Replaced before the run, under Ethan's answer 3, by the lag check: 315 h (see "The lag check, result").*
- **Window:** the 24 hours ending at issue time minus lag, `(t − lag − 24 h, t − lag]`. Readings marked Suspect,
  Rejected or Missing are dropped. Unchecked and Estimated are kept. At least 90% of the 96 quarter-hour slots must
  hold a reading, or the row has no factor and falls back (`flow_protocol.flow_at_issue`).
- Nothing after the window's end is read. A test puts a flood after the cut and checks the input does not move.
- **Limitation, stated now.** Archived values are later qualified. The real-time feed at the time may have differed.
  Not checked. A sensitivity arm (`spot_k05_lag1`) gives every gauge a 1 h lag, as if all were on the real-time feed.
  It decides nothing.

## Reference flow

The median of the gauge's daily-mean flows over May to September of 2014 to 2023. That is ten seasons, all before the
first row (2024). A season counts if at least 90% of its 153 days have a value. At least 5 seasons must count, or the
gauge has no reference and its spot falls back (`flow_protocol.reference_flow`). Because the factor is a ratio of the
gauge's own flows, a fixed datum or rating offset cancels. A rating change between 2014 and 2026 would not cancel. Not
checked.

## Rows

The rows the live river model was fitted on: `soil_moisture_eval/diagnostics.rows_q1`, which is `train_ecoli.py`'s
rows and filters. In `ecoli_model_sm.json`: 1,502 samples, 907 river and 595 lake, 31 bathing waters, 2024 to 2026.
Every arm uses the same rows in the same order. Production fits on rivers and lakes together, so every arm does too.
Lake rows keep production exposure in every arm. **Scores are on river rows only.**

## Arms

All are fitted with `train_ecoli` functions and `leads.CAND` (today's seven inputs plus `sm`), refitted in every
training fold. Only `logit_risk` on river rows differs between arms.

| arm | exposure on river rows | role |
|---|---|---|
| `reference` | production (`risk_lead0`) | the comparison |
| `spot_k05` | spot gauge, k = 0.5 | **the candidate** |
| `spot_k1` | spot gauge, k = 1 | reported |
| `overflow_k05` | per-overflow gauge, k = 0.5 | reported |
| `spot_k05_lag1` | spot gauge, k = 0.5, every gauge 1 h lag | reported |

"Production with flow replacing only the dilution term" is `spot_k05`: nothing else changes.

## Hold-outs

- **Leave one site out (LOSO), primary.** `train_ecoli.leave_one_out` by bathing water.
- **Leave one year out (LOYO).** By calendar year: 2024, 2025, 2026.
- **Forward.** Fitted on 2024, scored on 2025 to 2026, with the exposure from the 2023 to 2024 spill model
  (`risk_holdout`), as `train_ecoli.py`'s forward block does. The flow factor is applied to that exposure the same way.

## The primary comparison and its label

- **Score:** Brier on river rows, LOSO predictions. **Gain** = Brier(reference) − Brier(candidate). Positive is better.
- **Interval:** 95%, `train_ecoli.cluster_bootstrap` over site-weeks, 2,000 resamples, seed 1.
- **B and H, from predictions alone** (`flow_protocol.margins`). Stage 1 writes the LOSO predictions and their
  SHA-256 before any score. From the river rows' predictions only:
  - `s = mean((p_candidate − p_reference)²)`. If the candidate's probabilities were the truth, its expected Brier gain
    over the reference would be exactly `s`. If the reference's were, the expected loss would be `s`. So `s` is the
    most the change can be worth on these rows.
  - **B = max(0.001, s / 2).** The candidate must earn at least half of what it could. 0.001 is the floor: PR #248's
    whole refit moved the E. coli Brier by 0.0019.
  - **H = B / 2.**
  - Stage 1 also prints, for the record: the share of river rows whose E. coli band (cuts 0.10, 0.25, 0.50) changes,
    the share crossing the 0.25 warning line, and the mean absolute change.
  - Example working, with made-up numbers: an rms change of 0.05 gives s = 0.0025, B = 0.00125, H = 0.000625.
  - `score.py score` refuses to run unless `run_statement.json` names the predictions file's SHA-256.
- **Labels** (the framework in the addendum to `docs/LAKE-ECOLI-LINE-TEST-2026-10.md`; the first that fits):
  Better, Promising not shown, No useful difference, Possible harm, Harm, Too uncertain. "Possible harm counts as
  harm" (26 October 2026): a secondary check labelled Possible harm or Harm blocks "Promising, not shown".
  Three cases fit no label in that order. Each is labelled "Too uncertain": a positive point estimate with L ≤ −H and
  U < B; L > 0 with d < B ≤ U; and a "Promising" blocked by a secondary with U ≥ B. The tests check every case.
- **Secondary checks** (same B and H): LOSO with whole sites as clusters; LOYO with site-week clusters; LOSO on the
  rows whose gauge is on the real-time feed.

## Placebo

Each gauge's flow series is shifted round its own May to September season, by a shift drawn per gauge per replicate,
uniform on 14 to 139 days (never within 14 days of the true day either way round). 200 replicates, numpy
`default_rng(20261027)`, gauges in sorted order. The shifted issue time reads the shifted window. The reference flow is
unchanged. Only the candidate is refitted. The gain is against the real reference. Shifting within the season keeps
each gauge's flow distribution and seasonal level. It breaks only the link to the day.

## The gate, checked first

On river rows: at least **60%** have a flow factor, at **10 or more** bathing waters, with at least **30** samples
over 900 among them. Below that the result is "too few to judge". Scores are reported as description and the test
cannot pass.

## What counts as passing

All six must hold.
1. **Primary label "Better":** LOSO river gain d ≥ B and its lower end L > 0.
2. **LOYO:** the pooled river gain is above 0, and above 0 in at least 2 of the 3 years.
3. **Forward:** the river gain on 2025 to 2026 is above 0.
4. **Placebo:** the real LOSO river gain is above the 95th percentile of the 200 placebo gains (above the 190th when
   ranked).
5. **No secondary check is labelled Possible harm or Harm.**
6. **The gate holds.**

**Face checks, a stop rule, before any prediction.**
- The `reference` arm's exposure equals `ecoli_exposure_leads.parquet` at lead 0 (production and holdout spill
  models) to 1e-9 on every pair.
- Its fit on all rows equals `ecoli_model_sm.json`'s coefficients to 1e-9.
- Every offline step reports 0 network attempts.

If any fails, the run stops and that is reported first.

## Before Ethan is asked to adopt (reported; each must also hold)

- **Coverage:** the same as production by construction. The fallback gives every row a figure. The share with a
  factor is reported.
- **Calibration:** the candidate's LOSO mean on river rows is within 0.02 of the observed rate, and no further from
  it than the reference by more than 0.01.
- **Misses and false alarms at 0.25:** each no worse than the reference's by more than 0.02.
- **Groups:** none of these is labelled Possible harm or Harm: rows at real-time gauges, rows at archive-only gauges,
  and each water company (`undertaker`) with river rows. A group needs at least 30 rows to be labelled.
- **Live feed:** on the site, only gauges on the real-time flow feed could be used. The others would fall back. The
  site's one latest-readings call asks for levels only (`flows.latest_levels`, `parameter=level`). A flow call would be
  one more EA request per build. No Open-Meteo call.

## What follows

- **Nothing on the live site changes in this PR or because of it.**
- **Pass:** Ethan decides. Any switch is a separate PR: the dilution option in `transport.py`, a real-time flow call,
  and a refit of `ecoli_model_sm.json`.
- **"Promising, not shown":** the frozen candidate runs in shadow over the 2027 season, logged but not shown, scored
  only on samples after the shadow starts, with the same B and H. It is never pooled with these rows.
- **Anything else:** the dilution stays `length`. This PR stays as the record.

## What is expected, stated now

These are guesses.
- **Most likely label: "Possible harm" or "No useful difference". The placebo most likely fails.**
- Flow and E. coli both rise after rain. The candidate lowers exposure on high-flow days, the days when E. coli is
  highest, and its sign cannot flip, because it is tied to `logit_risk`'s positive coefficient. The rain and soil
  inputs already carry the wet-day signal. *Inferred.*
- The spill model gives the chance of a spill, not its size. Big spills come with high flows, so dilution and spill
  size move together. Measured flow corrects one side only.
- Half the gauges are archive-only (see below). Their flow is 36 hours old at issue time.
- Three size proxies have already failed on these rows.
- Overall: it fails.

## Costs and caps

- **EA requests, the run** (`flow_fetch.py flows`): one daily-mean request per gauge (2014 to 2023, about 3,650 rows)
  and one 15-minute request per gauge per season (2024, 2025, 2026; about 14,700 rows each). About 4 requests a
  gauge. 17 spot gauges are expected, plus any per-overflow gauges, so roughly 70 to 190 requests.
- **Caps, written into `flow_fetch.py` and committed (7182abd) before any request:**
  - at most 200 requests a run; cached answers do not count;
  - one request in flight, 1.5 s apart;
  - https to environment.data.gov.uk only, and no Open-Meteo request;
  - stop at the first 403, 429, 5xx, redirect or connection error, with no retry;
  - every answer cached outside git, and every request logged.
  A run stopped at the cap resumes from the cache. The prep's own cap was 150; it used 2.
- **Size:** about 2 to 3 MB of JSON per season series. Roughly 150 MB in all, to scratch, not git.
- **Another worker may query the EA tonight.** So the fetch does not run tonight. It runs after approval, and only when
  `pgrep -fl` shows no other EA fetch running (for example the river-rises fetch, PR #383, not before 2 November).
- **Compute:** `prep` predicts spill probabilities once per site per spill model, as the replay does. It recombines
  them for 5 arms and 200 placebos. `predict` fits about 31 × (5 + 200) LOSO folds and the LOYO and forward folds:
  logistic regressions on 1,502 rows. Under the group's `heavy-run.lock`, alone, with 35% memory free.

## Running

- The harness is `scripts/flow_dilution_eval/`: `flow_protocol.py` (the rules), `flow_fetch.py` (the capped client),
  `score.py` (map, prep, predict, score), `run.sh` and `prep_coverage.py` (the metadata summary below). Its synthetic
  tests are `tests/test_flow_dilution_eval.py`. They cover the gauge rules, the no-leakage lookup and lags, the slot
  rule, the fallback and identity, the exposure against the replay, the reference flow, the placebo shifts and rank
  rule, the margins, every label, the gate, and the client's caps and stops.
- It runs from a `git archive` of the approved commit, in a scratch root (`run.sh prepare`), on a frozen copy of the
  data folder whose hash goes in the results.
- Order: `prepare` (validate, replay and map, offline); `fetch` (EA only); `predict` (exposures, face checks,
  predictions, gate, B and H, offline); then `score` (offline).

## What will be reported

Whatever the verdict:
- the gate counts;
- the mapping: spot gauge per bathing water, side, distance, catchment ratio, real-time or not, and the reason for
  each without one;
- the share of river rows with a factor, by gauge, and the factor's spread;
- B, H and their working;
- the primary gain, interval and label;
- each condition with its figure;
- LOSO, LOYO and forward Brier and AUC for every arm;
- the placebo distribution (lowest, median, 95th percentile, highest);
- the adoption checks and groups;
- the gain by bathing water;
- data hashes, requests made, run time, peak memory and network attempts.

## Seen before writing

- Read on 27 October 2026: the transport-fit, urban-dilution, PE-size and spill-size statements and results;
  `transport.py`; `ecoli.py`; `train_ecoli.py`; `train_ecoli_sm.py`; `replay_ecoli_leads.py`; `flows.py`;
  `glofas_check.py`; the river-rises scope (PR #383, branch `proto/river-rises-scope`); the near-miss addendum.
- E. coli figures already published on these rows were seen, among them `flow` mode against `length` in the
  urban-dilution results table. No new score was computed.
- `ecoli_model_sm.json` meta: 1,502 rows, 907 river, 595 lake, 31 sites, 2024 to 2026, `sm` range 0.052 to 0.494.
- **Two EA requests**, both HTTP 200, at 01:06 UTC on 27 October, through `flow_fetch.py stations`:
  - the Hydrology flow station list: 1,103 stations, 3.0 MB;
  - the real-time flow station list: 351 stations, 0.25 MB.
  Metadata only; no reading.
- **Coverage from metadata** (`prep_coverage.py`). It uses the gauge columns of `docs/GLOFAS-CHECK-2026-11-spots.csv`,
  whose rule is this test's spot rule, run on the network on 18 October. It covers the 20 river bathing waters in
  `data/processed/validation_sites.csv`:
  - **17 have a spot gauge** (9 upstream, 8 downstream, 1.3 to 22.4 km along), on 17 distinct gauges. All 17 have
    both a daily-mean and a 15-minute flow measure.
  - Opening years run from 1883 to 1998, all before the 2014 reference start. Whether each has 5 full reference
    seasons is not known until the run.
  - Status: 15 active. Hunsingore on the Nidd is "Flow Suspended" and Kingston on the Thames "Suspended". Their spots
    may fall back.
  - **8 of the 17 are on the real-time flow feed** (Tadcaster, Reading, Kingston, Farmoor, Sutton Courtenay, Tenbury,
    Buildwas, Montford). The other 9 take the 36 h lag.
  - **No gauge, 3 sites:** Sheep's Green on the Cam and Sandy Lane on the Dee (gauges on the path, catchment too
    different), and Falcon Meadow on the Waveney (no gauge on the path).
  - The GloFAS file also holds flow statistics from PR #255. They were not used.
- Not done: the river network was not loaded and no pin was placed, because another job held the heavy-run lock. So
  the per-overflow rule's coverage is unknown, and the run's counts may differ from these.
- No E. coli value was read. No flow reading was fetched. No model was fitted or scored.

## Questions for Ethan before the run

1. **The gauge rule.** Spot gauge as primary, with the brief's per-overflow rule as a reported arm? Or the reverse?
2. **k.** Fixed at 0.5, or fitted inside training folds over {0.25, 0.5, 0.75, 1}?
3. **Archive-only gauges.** A 36 h lag, as written? Or use only real-time gauges in the candidate (8 of 17 expected,
   which the gate's 60% would likely fail)?
4. **Issue time.** 09:00 London on the sample day?
5. **B and H.** The predictions-only rule above, or fixed values as in the river-rises answers (B = 0.02 skill)?

## Ethan's answers and approval (27 October 2026)

Ethan approved the statement on 27 October 2026 ("okay approved", to Claude's recommendations), with these answers:

1. **Gauge rule:** spot gauge as primary; the per-overflow rule stays a reported arm.
2. **k:** fixed at 0.5; the k = 1 arm stays reported.
3. **Archive-only gauges:** the 36 h lag, after checking it against the gauges' own latest readings (below). If the
   measured lag is longer, the longer one is used.
4. **Issue time:** 09:00 London on the sample day, or 1 h before the sample if earlier, as written.
5. **B and H:** the predictions-only rule, as written.

The run may start before the river-rises fetch (PR #383, after 2 November), so the two EA fetches do not overlap.

### The lag check, stated before its requests

- **Requests:** one per archive-only spot gauge in the metadata coverage (9 gauges), its 15-minute flow measure's
  `readings?latest`, through `flow_fetch.py latest` (the same capped client: one in flight, 1.5 s apart, stop on the
  first 403, 429, 5xx, redirect or connection error). 9 requests; the step's cap is 12.
- **Age:** the request's UTC time minus the end of the latest reading's quarter hour.
- **Left out of the maximum:** a gauge whose status is suspended (Hunsingore, "Flow Suspended"), and a gauge whose
  latest reading is more than 14 days old (not publishing). Each is reported.
- **Lag used:** the larger of 36 h and the largest remaining age, rounded up to the whole hour. It replaces
  `LAG_ARCHIVE_H` in `flow_protocol.py` before the run, in its own commit.
- **Limitation:** one snapshot, on one day. It measures how far behind the archive is now, not on each past sample
  day. No flow value from these requests is used in the test.

### The lag check, result (27 October 2026, 09:54 UTC; recorded before the run)

9 requests, all HTTP 200, 09:54:06 to 09:54:38 UTC (the first answer was cached by a run that then failed on a
time-zone bug in the step, fixed before the other 8; its age is computed at the rerun, about 20 s later).

| Gauge | Status | Latest 15-minute reading (UTC) | Age, h | In the maximum |
|---|---|---|---|---|
| Addingham | Active | 2026-10-14 06:45 | 314.91 | yes |
| Catterick Bridge | Active | 2026-10-14 06:45 | 314.91 | yes |
| Henthorn | Active | 2026-10-14 07:15 | 314.41 | yes |
| East Mills Combined | Active | 2026-10-16 07:15 | 266.41 | yes |
| Taunton Market | Active | 2026-10-27 09:00 | 0.66 | yes |
| Tellisford | Active | 2026-10-27 09:00 | 0.66 | yes |
| Amesbury | Active | 2026-10-27 09:15 | 0.41 | yes |
| Lamarsh | Active | 2026-10-13 07:00 | 338.66 | no: over 14 days |
| Hunsingore | Flow Suspended | 2025-07-14 06:00 | 11,283.66 | no: suspended |

- **Lag used for archive-only gauges: 315 hours** (the largest remaining age, 314.91 h, rounded up; larger than 36 h).
  `LAG_ARCHIVE_H` is 315 in `flow_protocol.py`.
- To keep the look-back inside the fetched data, each season's 15-minute request now starts on 15 April, not 29 April
  (`SEASON_FROM`). Same number of requests; larger answers.
- **What this shows, inferred:** the archive is loaded in batches by area. The Wessex-area gauges were current; the
  northern and eastern ones were last loaded 13 to 16 October. Lamarsh is in the same batch pattern and is left out
  only by the 14-day rule written before the check; with it the lag would be 339 h. The batch interval, and so the
  worst lag, is not known from one snapshot.
- **What it means for the test:** for archive-only gauges the candidate uses flow from about 13 days before issue,
  which can say little about the day. The primary arm is therefore close to a test of the 8 real-time gauges. The
  sensitivity arm `spot_k05_lag1` (every gauge at 1 h) shows what timely flow everywhere would give. It decides
  nothing.

## Run log (written before the score)

- **Code:** `git archive` of 1290013 (approval, answers and lag check), in `swimsignal-private/flow-dilution/`.
- **Data:** the frozen data folder of 23 October 2026 (the one the soil and transport tests used), with the tracked
  `data/` files of 1290013 laid over it; soil from the main checkout's `data/cache/soil`. Hash of `processed` and
  `raw`: `c78b10af0f39ce9273da513fd81795b070d1fcce6517a48d44f8ed5d388c973d`.
- **A first attempt** at 09:57 UTC stopped in `prepare` before any request: the main checkout's own overflow table
  predates the 12 October network, and `load_overflows` refused it. The data folder was rebuilt as above.
- **prepare** 09:58-10:02 UTC, network attempts 0 (validate, replay, map). Map: 20 river bathing waters, 17 with a
  spot gauge, 21 gauges to fetch (spot and per-overflow).
- **fetch** 10:02:45-10:05:34 UTC: **84 requests, all HTTP 200** (cap 200), EA Hydrology only, no Open-Meteo.
- **predict** 10:05-10:07 UTC, network attempts 0. Face checks passed: exposure against the replay, 1,672 pairs, max
  difference 4.4e-16; the reference fit against `ecoli_model_sm.json`, max coefficient difference 4.4e-16.
- **Gate: met.** 765 of 907 river rows have a flow factor (84.3%), at 17 sites, with 156 exceedances.
- **Margins, from predictions alone:** mean squared change 0.000225, so **B = 0.001** (the floor) and **H = 0.0005**.
  Mean absolute change in probability 0.0082; 3.0% of river rows change band, 0.8% change the warning.
- **Predictions SHA-256:** `cd83e65992294e77c13028546552e7d88301823730c092340fcc007678692f80`. No score had been
  computed when this was committed.

---

## Results

Not run.
