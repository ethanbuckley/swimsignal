"""Scotland hindcast, Stage A (task S3 of docs/SCOTLAND-PLAN-2026-10.md, section 6). Off CI; publishes nothing.

A hindcast is a forecast made after the fact with the rain that fell, scored against what the
overflows did. This script applies the English spill model, unchanged, to Scottish Water's
overflows, and writes a summary of scores (no rows) to data/processed/scotland_hindcast.json.
Contains Scottish Water data licensed under the Open Government Licence v3.0.

    DIPCAST_ROOT=<main checkout> uv run python scripts/hindcast_scotland.py --dry-run
    DIPCAST_ROOT=<main checkout> uv run python scripts/hindcast_scotland.py

It reads S1's events (sw_events.parquet), S2's covariates (sw_covariates.parquet) and rain cells
(scotland_rain_cells.csv), and rain only from the cache: ERA5-Land archive_*.parquet and archived
forecasts leads_*.parquet. It never calls Open-Meteo, except with --fetch-leads (see "Rain").

GATE A
======

Written 11 October 2026, before any run that scores a forecast against a Scottish label, and
committed on its own before the script's code. It is not to be changed after any result is seen.
A different rule would be a new, dated rule beside this one, and the write-up would report both.
Before writing it I had looked at: the number of Scottish overflow-years with a count, by year; the
rain cell-years cached so far; and the durations of United Utilities' training events (below). No
Scottish forecast had been made or scored.

Model. Layer 1 (the pooled model) of data/processed/spill_model_holdout_2025.pkl: trained by
scripts/train.py on United Utilities' discharges of 2023 and 2024, and not refitted. The
production model (spill_model.pkl, refitted on 2023 to 2025) is scored beside it as a check and has
no part in the gate.

Rain. ERA5-Land hourly rain per 0.1 degree cell, days in UTC, features from
model/features.daily_rain_features, as train.py builds them. A year's features come from its own
cell-year and, for January's antecedent windows, the cell-year before, where that is 2021 or later
(the archive starts in 2021). Rows whose day has no rain total are dropped, as in train.py. "Lead 0"
means this rain, the rain that fell. "Leads 1, 2 and 3" mean Open-Meteo's archived forecasts for
2025, built as scripts/verify_leads.py builds them (the target day and the two days before from the
forecast, longer windows from ERA5-Land).

Overflows and labels. Scottish Water's event history (task S1) and the covariates of task S2
(ingest/sw_covariates.py). A label is a spill-day: a UTC day touched by an event that
sw_covariates.counted_events keeps (longer than 15 min 30 s, or of unknown duration), in every year
and both files. A day record (no end time; its start is local midnight) labels its local date. An
overflow-year is "counted" when its S2 status is "events" or "no events". Left out: emergency
overflows (EO in the API's overflow type, or "EO" or "Emergency" in the measurement point's name;
plan 5.2: they do not spill because of rain); overflows with no position; and an overflow-year
whose own uptime (edm_operational_pct) is below 50%, as train.py does. Unknown uptime is kept.

Sets.

- G, the gated set: overflow-years of 2022 to 2025 counted in that year and in the year before.
- N, reported only: overflow-years of 2022 to 2025 counted in that year but not the year before.
  Most are the overflows whose first published year is 2025.

Arms, on G.

- "Scottish covariates", the arm the gate is about, named before the run: lta_spills, spill_hours
  and edm_operational_pct from S2's return of the year before (sw_covariates.covariates_for). A
  missing value takes the median of that year's G overflows, then the model's default, as
  features.site_static_features does with company "Scottish Water".
- "Default covariates": all three missing, so site_static_features gives 20 spills, 100 hours and
  90%. This is what Scotland would get with no new code.
- "Calibration layer": the Scottish-covariates arm plus SpillModel.fit_site_offsets (prior 15
  spill-days, recency 1, as train.py), fitted for each test year only on the overflow's counted
  years before it, each with its own year-before covariates.
- "Production model, Scottish covariates": a check.

On N: "default covariates" only (N has no year before to take covariates from).

Baselines.

- "Earlier years", the gate's baseline: the overflow's spill-day rate over its counted years
  before the test year (the same uptime rule): spill-days divided by days in those years. Where
  it has none, the spill-day rate of all counted Scottish overflow-years before the test year in the
  same calendar month. Clipped to 0.001 to 0.95.
- "Flat": the test set's own spill-day rate on every row. It uses the answer, so it is a hard
  baseline, as the accuracy page shows it.

Scores. Brier score; Brier skill score (BSS) = 1 - Brier(model) / Brier(baseline); log loss; AUC;
reliability by tenths; the level, sum of forecasts / spill-days; wet days (rain_d + rain_d1 > 10 mm)
and dry days apart; by year; by overflow type (CSO, SSSO, CSO/SSSO, not in the API); by local
authority (the API's LOCAL_AUTHORITY_NAME). Intervals: a cluster bootstrap that resamples
overflows and ISO weeks together (rows weighted by the product of the overflow's and the week's
draw counts), 2,000 draws, seed 0, 95% percentile intervals.

Pass rule.

- G1. G at lead 0, the four test years pooled: the lower end of the 95% interval of BSS (Scottish
  covariates against earlier years) is above zero.
- G2, G3, G4. G's 2025 rows at leads 1, 2 and 3, each lead separately: the same, on the rows whose
  cell has archived forecasts. A lead test runs only if those rows hold at least LEAD_MIN_SITES
  (20) overflows and LEAD_MIN_SPILL_DAYS (200) spill-days; otherwise it is untested.
- G with fewer than MIN_SITES (10) overflows or MIN_SPILL_DAYS (100) spill-days at lead 0 is
  untested.

Verdict: FAIL if any tested part fails. PASS if all four parts are tested and pass. NOT COMPLETE if
no tested part fails and some part is untested; that is not a pass, and the Scottish forecast does
not go ahead on it. On FAIL, the next step is a short write-up in the accuracy page's terms, and
Scotland's spill forecast stops (plan, task S3).

The other arms, set N, the groups and the level are reported, not gated. The gated arm is not
re-chosen from them after the fact.

The 15 min 30 s cut and the training labels (the plan's open check, section 6). Checked on 11
October 2026 in the code and in the training file: neither ingest/edm_events.py nor train.py cuts
short events, and in data/processed/edm_events.parquet 52.1%, 48.4% and 49.8% of United Utilities'
2023, 2024 and 2025 events last 15 min 30 s or less. Leaving those out removes 13.9% of UU's
spill-days (14.1%, 13.3% and 14.2% by year). So the model learned from labels that include short
events, and here it is scored on labels without them. Inferred, not measured: if short events are
as common in Scotland, the model forecasts about 1 / 0.86 = 1.16 times too many spill-days. The
earlier-years baseline is built from the same cut labels, so the mismatch can only lower the
model's skill against it. The rule stays as the plan states it, the gate is not eased for it, and
the level is reported. A second mismatch pushes the other way (inferred, not measured): S2 counts
lta_spills after the cut, while the EA returns the model learned from count every event, so a
Scottish overflow reads as quieter than an English one with the same discharges.

Rain needed, and the refusal. The script scores only when every archive cell-year that G's scored
rows need (the test year and the year before) is cached, and every 2025 archived-forecast file
for the cells of G's 2025 rows. Otherwise it stops with the count missing and scores nothing.
`--without-leads` drops the second condition; G2 to G4 are then untested, so the verdict cannot be
PASS. The calibration arm (its fitting years need more cell-years) and set N each run only if all
their cell-years are cached; otherwise the result says "not run" and how many are missing.
`--fetch-leads --max-calls N` asks Open-Meteo's previous-runs API for the missing 2025 forecast
files of G's cells, paced, stopping at the first refusal or before N calls; it scores nothing.
"""

from __future__ import annotations

MIN_EDM_PCT = 50.0
WET_MM = 10.0
BASE_CLIP = (0.001, 0.95)
N_BOOT = 2000
SEED = 0
MIN_SITES, MIN_SPILL_DAYS = 10, 100
LEAD_MIN_SITES, LEAD_MIN_SPILL_DAYS = 20, 200
GATE_LEADS = [1, 2, 3]
TEST_YEARS = [2022, 2023, 2024, 2025]
LEAD_YEAR = 2025
FIRST_RAIN_YEAR = 2021
