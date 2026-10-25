# Soil moisture in the E. coli estimate on rivers only: the test, stated before any score on its data

Written 25 October 2026. Ethan approved this test on 25 October ("yep soil rivers only lets dfefintely do that"),
relayed by the parent session. No sample in the deciding data below has been scored by either estimate. Results go
below the line at the end. Nothing above it changes after a result is seen.

## Why, and why it needs new data

The leads test (`docs/SOIL-MOISTURE-ECOLI-LEADS-TEST-2026-11.md`) failed on one condition. Lakes were 0.00061 worse at
lead 1, against a margin of 0.0005. On rivers the gain was +0.012 to +0.016 at every lead, with intervals above zero.
That suggests a rule: **use soil moisture on rivers, and keep today's model on lakes.** The rule was drawn from those
English rows, so they cannot judge it. This test judges it on river samples the rule was not drawn from.

## The rule under test

- **River points:** the leads test's candidate. That is today's seven inputs plus `sm`, ECMWF IFS
  `soil_moisture_9_to_27cm` (`models=ecmwf_ifs`) at the point's 0.1° cell, at 00:00 UTC of the issue day, held for every
  lead. It is fitted on all 1,502 English rows at lead 0 and held inside their `sm` range (0.059 to 0.489 m³/m³ in the
  leads test).
- **Lakes:** today's model, unchanged.
- **Reference:** today's model everywhere, fitted on the same English rows.
- Nothing is fitted on the deciding data. Every point below is a river, so on the deciding data the rule is the
  candidate and the comparison is candidate against reference.

## The deciding data

### (a) Welsh river samples (NRW, OGL v3)

W10's samples and rules (`scripts/check_ecoli_wales.py`). Its headline set is river points with at least 20 km of
mapped river upstream: 185 samples at 11 stations on 10 October. Inputs as in W10 and the Wales check
(`docs/SOIL-MOISTURE-WALES-CHECK-2026-11.md`): ERA5-Land rain to midday, exposure from W10's trace and Gate A's spill
model (`spill_model_holdout_2025.pkl`), and `sm` from the Wales check's fetch (26 calls, done 25 October).

**Unseen, with one event to record.** The Wales check's run started at 22:18 GMT on 25 October, before this test was
asked for. When the request came, it had finished `validate_ecoli`, `replay_ecoli_leads` and `train_ecoli`. At 22:24:07
it had started `wales.py`. I killed it within about 30 seconds. `wales.py` prints and writes its scores only at its end.
Its log is empty, and no output file exists. The only file it wrote is the station trace (`trace.pkl`): stations,
snaps and upstream overflows, with no E. coli value or estimate. So no Welsh score was seen, and the Welsh rows count
as unseen.

### (b) Wessex Water's river E. coli samples (CC BY 4.0)

- **Source:** "Wessex Water Environmental Water Quality 2019-2025", ArcGIS item 4659ab28caa640c58e725b41ecbba79f,
  layer `Wessex_Water_Environmental_Water_Quality_view/FeatureServer/0`. "Wessex Water Environmental Water Quality ©
  2026 by Wessex Water is licensed under CC BY 4.0." The credit goes in the results and on any page that uses them.
- **Download:** only `Determinand = 'E. coli'`, with all its fields, once, by `scripts/soil_moisture_eval/rivers.py
  fetch`. The raw rows go to the main checkout's `data/cache/wessex_wq/`, outside the repo. No sample row is committed.
- **Samples:**
  - May to September, 2020 to 2025. The model's season is May to September, and the 2027 check is in season too.
  - 2019 is left out: no cached rain covers it (`rain_multi` starts in December 2019).
  - Every row has type "River" and units "E. Coli/ 100 mL".
  - A station is one position (latitude, longitude). The two Warleigh Weir points 50 m apart are two stations.
- **Signs:** W10's rules (`exceeds`, `log_count`). "<" is read from the `Operator` field. A sample whose exceedance is
  unknown is left out of the Brier score and counted.
- **Placement:** W10's rule 4 with the existing transport code. `transport.locate_pin` must place the position in
  "river" mode on an inland river link no more than 250 m away. `upstream_overflows` then traces 60 km upstream at the
  default speed, over the frozen overflow table (key b5724303).
  - The headline set is the points with at least 20 km of mapped river upstream, as in W10.
  - All placed points are reported as a second set and decide nothing.
  - Points that do not place are counted and left out.
- **Inputs:** W10's `predictors`, unchanged.
  - Rain: ERA5-Land to midday at the point's cell, from the main checkout's `rain`, `rain_multi` and `rain_nine`
    caches.
  - Exposure: the production spill model (`spill_model.pkl` in the frozen folder), layer 1, calibrated at lead 0 and
    combined over travel time. This is the model England's bathing waters are validated with. W10 also computes this
    figure for every sample.
  - A cell with less than 99% of its rain hours is a gap. Gaps are fetched within the budget below. Rows still short
    of rain are dropped and counted.
- **`sm`:** Previous Runs lead 0, `models=ecmwf_ifs`, for each cell-quarter holding a sample, 4 cells a request.
  Coverage was checked before writing: values exist in 2019, 2021 and 2022.
- **Budget:** about 95 calls for `sm`, plus any rain gaps. In all, under the 300 Ethan allowed. If rain gaps would pass
  it, those rows are dropped rather than fetched.

### (c) The 2027 bathing-water samples (prospective)

Stated now, run after the 2027 season: the same rule against today's model on the EA's 2027 samples at inland
bathing waters with overflows upstream, at leads 0 to 4 as `train_ecoli.py`'s by-lead table scores them. It uses
conditions 1 and 2 below, with "subgroup" meaning rivers and lakes. It reports in a dated addendum. If the rule has been
adopted by then and 2027 shows it clearly worse, it is withdrawn. It does not decide anything now.

## The conditions, on (a) and (b) together: the headline sets

These follow the noise-aware form of `docs/NOISE-AUDIT-2026-10.md`. "Gain" is Brier(reference) − Brier(rule).
Intervals come from a bootstrap over (region, sampling day) clusters: 2,000 draws with `numpy.random.default_rng(0)`,
every row of a cluster drawn together.

1. **A pooled gain.** On the pooled headline samples whose exceedance is known, the gain is above zero, and its 95%
   interval lies wholly above zero.
2. **No region clearly worse.** For Wales and for Wessex apart, the region is clearly worse if either holds:
   - the interval of the gain lies wholly below zero;
   - the rule's Brier is more than 1% above the reference's.

The test passes if both hold.

**Reported, deciding nothing:**
- AUC over 900 and log loss for both estimates, pooled and by region;
- Spearman's rho with log E. coli, pooled and within station, with intervals;
- per station with at least 14 samples, rho and the mean of each estimate;
- the all-placed sets;
- English rows: leave-one-year-out Brier by lead 0 to 4 for the rule and for today's model (rivers with `sm`, lakes
  without), as the leads test computed them.

## Checks before scoring (the run stops if any fails)

- The reference's coefficients equal `ecoli_model.json` written by `train_ecoli.py` in the same root, to 1e-9.
- In each region, the reference's predictions equal W10's own estimate column for that region's exposure, to 1e-9:
  Gate A's in Wales, production's in Wessex.
- 0 network attempts during scoring.

## What is expected, stated now

- **Wessex: a gain.** Its rivers (the Bristol Avon, the Frome, the Wylye and others) are like the English rivers where
  `sm` helped most, such as the Frome at Farleigh Hungerford (+0.237 within-site rho in the plan's step 2). With about
  2,000 samples, I expect the gain's interval to lie above zero.
- **Wales: worse on Brier.** The estimate is already too high there (mean 0.32 against a rate of 0.06), and wetter
  ground would push it higher. Its interval will most likely include zero, so I expect it not "clearly worse" by the
  interval. The 1% point margin is the risk.
- **Overall:** condition 1 most likely holds, carried by Wessex. Condition 2 is the one at risk, in Wales.
- One more limit, stated now: Wessex samples are at sites near the company's own works and outfalls. Their exceedance
  rate may differ a lot from bathing waters. Calibration, not ranking, is what Brier will mostly measure there.

## Running

- The harness is `scripts/soil_moisture_eval/rivers.py`, plus a `rivers` mode in `run.sh`. It is committed after this
  file and before the Wessex download.
- `rivers.py fetch` downloads Wessex's E. coli rows. `rivers.py prepare` (offline except Open-Meteo) places the points,
  reports rain gaps and fetches `sm` and any rain gaps. Neither reads a Result value against an input or computes a
  score.
- The scoring run is from a `git archive` of the harness commit, offline, under the group's `heavy-run.lock`. It runs
  `validate_ecoli.py`, `replay_ecoli_leads.py`, `train_ecoli.py`, then `wales.py` (the Wales check as stated), then
  `rivers.py run`.

## What follows

**It passes.** An adoption PR for rivers-only `sm` becomes possible: the plan's step 5, with lakes on today's model.
It is Ethan's decision. (c) is its prospective check.

**It fails.** `sm` is not adopted on rivers either. This PR stays a record.

Nothing is adopted or deployed here. The PR is left for Ethan to merge.

## Seen before writing

- The leads test's results, which suggested the rule, and #344's.
- W10's published summary, and the Wales check's statement. Not its result: it was stopped before any score (above).
- Wessex metadata only, from three queries that returned OBJECTID, date, units and position, and no Result:
  - 4,123 E. coli rows from 2019 to 2025;
  - by year, all months: 305, 519, 1,365, 1,362, 335, 110 and 127;
  - May to September: 2,032 at 95 positions in 21 cells;
  - by year, May to September: 2019 71, 2020 51, 2021 913, 2022 836, 2023 49, 2024 53, 2025 59.
- Three Previous Runs requests at (51.35, −2.3): `sm` values exist on 1 October 2019, 1 June 2021 and 1 June 2022.
  Counts only.
- The cached rain files by folder and year.
