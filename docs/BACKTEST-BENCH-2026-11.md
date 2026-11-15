# Backtest bench: E. coli candidates scored on held-out years with one command

Written 15 November 2026. A tool, not a test: no candidate has been scored on the held-out rows, and nothing on the
site changes.

## Why

Each E. coli or lake test so far has rebuilt its own rows: fetched samples, fetched archive rain, rebuilt exposure,
then scored. That took a session and a PR per idea, and it caused at least one error that had to be corrected after
the fact (the 2012-22 lake rows were first built without `lead_calibration.json`; LAKE-LINE-2012-22-CHECK,
"Correction, 6 Nov"). The bench builds the rows once, freezes them with hashes, and scores any candidate against
production and simple references with one command.

It turns the workflow's "Backtest instead of waiting" rule (RESEARCH-WORKFLOW.md, 6 November 2026) into something a
candidate can use in minutes: production's E. coli models were fitted on 2023-26 samples, and the EA has samples
at the same bathing waters back to 2012 that no production model was fitted on.

It is separate from [BENCH RC0](BENCH-ECOLI900-2026-11.md), the open benchmark planned for outside release. That one
scores baselines on seen 2023-26 samples from publishable columns only. This one is internal, scores model candidates,
and its main rows are years production never saw.

## The rows

One row per EA lab sample at the 38 inland bathing waters, May to September, built by `scripts/backtest_bench/stage.py`.
The inputs are the ones production's E. coli models read, rebuilt for the sample's day as a lead-0 hindcast:

- rain in the 48 and 24 hours before the sample, from Open-Meteo's archive at the spot's rain cell;
- exposure: spill chances at every upstream overflow from archive rain, through the spill model, the lead-0
  calibration map and transport, as `validate_ecoli.py`'s hindcast builds it (through `lake_range_hindcast.build_rows`,
  unchanged). A site with no monitored overflow upstream gets exposure 0, as production does;
- `sm` at river rows: soil moisture at 00:00 UTC of the sample day (Previous Runs, `ecmwf_ifs`), as
  `train_ecoli_sm.py` reads it. Lakes have none: production's lake model has no `sm`;
- `prev_over_3d`: whether the previous sample at the site that season, at least 3 days before, was over 900 (a
  reference input; the 3 days is BENCH RC0's lab-turnaround assumption, not a checked one).

| Part | Seasons | Rows | Sites | Water bodies | Results over 900 |
|---|---|---|---|---|---|
| seen (fitted production) | 2023-26 | 2,153 | 38 | 33 | 219 |
| held out, lakes | 2012-22 | 2,335 | 12 | 7 | 41 |
| held out, rivers | 2021-22 | 60 | 2 | 2 | 12 |

104 samples were dropped because their 48-hour rain window was less than 90% covered (`ecoli.MIN_COVERAGE`).
Rivers have few held-out rows because most river bathing waters were designated from 2020 on: the EA lists none of
the 20 river sites before 2021.

**Already read.** 962 of the held-out lake rows (Windermere's four bathing waters and Frensham, 2012-22) were scored
by [#584](LAKE-RANGE-HINDCAST-TEST-2026-11.md) and the [2012-22 lake-line check](LAKE-LINE-2012-22-CHECK-2026-11.md).
Each row carries `prior_reads`, and the bench reports a `not_read_before` subset: 1,433 rows at 9 bathing waters on
7 water bodies (Colwick, Cotswold Country Park, Hampstead Heath's three ponds, Henleaze, the Serpentine, the Wharfe at
Ilkley, Wolvercote Mill Stream). Only the two rivers among them have an overflow upstream, so at those five lakes
production's figure moves with rain and season only.

**Disclosure.** While checking the staged rows on 15 November I printed, for each held-out bathing water, its row
count, its number of results over 900 and its mean exposure. No model figure was computed against a held-out outcome.
A candidate whose design leans on a held-out site's own rate of results over 900 should say so in its statement.

**Where they live.** The rows hold values derived from Open-Meteo, which BENCH RC0 keeps out of published files until
its licence question is settled. So the rows are not in git. They are in `swimsignal-private/bench/ecoli-v1/`
(`seen.parquet`, `heldout.parquet`, `manifest.json`), and the committed
[manifest](backtest-bench/ecoli-v1-manifest.json) holds their SHA-256 hashes. `bench.py` refuses rows whose hash does
not match. Anyone with the repository can rebuild them with `stage.py`; the manifest lists every request.

### What the build cost

| Requests | Count | Weighted Open-Meteo calls |
|---|---|---|
| EA bathing-water listings | 38 | none |
| Open-Meteo archive rain, 2012-22 cell-years (2023-26 were already cached) | 144 cell-years | 375.4 |
| Open-Meteo Previous Runs soil moisture, river cells 2021-22 | 3 | 3.4 |

All in a scratch `DIPCAST_ROOT` (copy-on-write clones of the main checkout's `data/`, with this commit's tracked data
laid over them). The shared `data/raw`, `data/processed` and `data/cache` were fingerprinted (path, size and mtime of
every file) before and after: the same hash, `5031165a…`, both times.

The models the rows were built with are the live site's. The live stamp on 15 November was
`spill=808da63d;cal=9b3cc24c;ecoli=f70c7723`, and the files used hash to the same values.

### Checks that it rebuilds what earlier records built

1. **Row for row against an earlier record.** The 962 rows in `LAKE-LINE-2012-22-CHECK-2026-11-corrected-rows.csv`
   were matched by bathing water and sample time: all 962 found, and the count, both rain windows and the exposure
   agree exactly (largest difference 0.0). Deployed production's mean within-site rank correlation on them is
   0.102, the record's "deployed production" figure.
2. **Self-check candidate.** `candidates/production_refit.py` is production's form refitted on the training rows. In
   `dev` its scores equal the bench's `production_refit` reference exactly on every metric and subset, so a candidate
   is given the same rows the references see.
3. **Tests.** `tests/test_backtest_bench.py`: the AUC matches scikit-learn's with ties, Windermere's and Hampstead's
   sites resample together, `predict` never sees an outcome column, malformed output is refused, the shrunk site
   rate's arithmetic, identical figures differ by exactly zero with a zero interval, and a final read of an
   uncommitted candidate is refused.

## Using it

```bash
uv run python scripts/backtest_bench/bench.py verify
uv run python scripts/backtest_bench/bench.py dev --candidate <your .py>
uv run python scripts/backtest_bench/bench.py final --candidate <committed .py> --statement <committed .md>
```

A candidate is a `.py` file with `fit(rows)` and `predict(model, rows)`. `predict` returns P(over 900), or a dict
with `p900` and optionally `p500` and `rank` (anything that orders a site's samples, such as a predicted median
log10 count). Outcome columns are removed from the rows `predict` sees.

**`dev`** scores by leaving one seen season out, 2023 to 2026. It never opens the held-out file. Run it as often as
you like; its results are development evidence. `production_deployed` is in-sample there (it was fitted on those
rows). It took 2 minutes 43 seconds on this Mac with the self-check candidate.

**`final`** fits on every seen row and scores once on the held-out rows. It refuses unless the candidate and its
statement are committed and unchanged in the working tree. It writes a result file to `docs/backtest-bench/results/`
and appends a line to `docs/backtest-bench/ledger.jsonl` for every run, whatever the result, numbered, so a reader
sees how many times these rows have been read. Commit both.

**What a final read counts as.** A frozen-model backtest under the workflow's rule, when the statement is pushed
before the read and fixes the reference, metric, margin, subset and what each outcome leads to. The bench enforces
the commit; it cannot enforce that nothing about the candidate was chosen after looking at held-out rows. That stays
the author's statement, and the ledger shows every earlier read. Each read of the same rows makes the next one weaker
evidence; a family of variants read one after another should be stated as a family, with its multiple-comparison
rule, before the first read.

**Scores.** For each figure: Brier for over 900 (and over 500 where given); the mean over sites of the within-site
AUC for over 900; the mean over sites (15 rows or more) of the within-site Spearman correlation with the measured
log10 count, which every row informs. Intervals are 95%, from 2,000 resamples (seed 20261115), with the same draws
for every figure, and for each paired difference with the references. Two resampling units are reported side by
side: water bodies (`ci95`; a water body drawn twice counts as two sites), and water bodies within a season
(`ci95_season`; LAKE-LINE-2012-22-CHECK's site × season unit, with a water body's sites kept together). A subset
with few water bodies needs the second: the held-out lakes not read before are 5 water bodies. A statement names
which one decides. Subsets: all, lake, river, not read before, lakes not read before, seasons to 2016, seasons from
2017. (Added 15 November, after the record above was first pushed and before any final read.)

**References.** `production_deployed` (the E. coli models in `data/processed` as deployed, the river model with
`sm` where known); `production_refit` (production's form refitted on the same training rows as the candidate);
`month_rate` (share over the line by calendar month, all sites); `site_rate` (the site's own share in the training
rows, shrunk toward the pooled share with m = 10, LAKE-OWN-RATE-TEST's rule).

## Limits

- **Few results over 900.** 53 held out, 41 at lakes. A test whose main metric is over-900 Brier at lakes will be
  weak; #625 failed partly for this reason (16 events). The rank correlation and the over-500 line use more of the
  rows. Choose the metric in the statement with this in mind.
- **Rivers.** 60 held-out river rows at 2 sites. River candidates cannot be confirmed here; they need the 2027
  season, or another unseen source, under its own statement. Wessex Water's river samples (#688) are not unseen for
  the river model: the soil-moisture rivers test scored the live river rule on them.
- **Rain is archive rain, not a forecast.** The rows are lead-0 hindcasts on Open-Meteo's archive rain, as every
  earlier lake test used. A candidate's skill at leads 1 to 4 is not measured here.
- **The archive rain's source most likely changes at 2017.** The archive is fetched with no `models` parameter
  (`best_match`). The ERA5-Land record (`docs/ERA5-LAND-BULK-RAIN-2026-11.md`, PR #702) measured that the cached
  2020-26 files follow the IFS grid, so they are most likely ECMWF's IFS analysis. That record also says the 2012-16
  rain cannot be IFS, which Open-Meteo's archive starts in 2017, so it comes from ERA5 or ERA5-Land (inferred, not
  measured on these files). Production was fitted on
  the IFS years. Every read reports seasons to 2016 and from 2017 apart.
- **The spill model is not covered.** Its event-level labels start in 2024 (2020 at Northumbrian and Wessex) and
  every year has been used to choose a model. The bench does not change that.
- **Exposure depends on the spill model and calibration map.** If either changes, rebuild the rows as a new
  `row_version`; `bench.py` warns when `lead_calibration.json` differs from the frozen one. The spill model file is
  not in git, so its hash is in the manifest only.

## Next

- The first candidates through `final`, each with its statement pushed first. The lake models already frozen
  (lake-range-v1, LAKE-LINE plain and B) can be read on the `not_read_before` rows, which no earlier test of theirs
  read.
- Coastal samples 2012-21 when COASTAL-C1's rows exist (its own protocol and fetch, 22-25 November).
- ERA5-Land as the bench's rain source once its match check against the cached Open-Meteo files passes (a separate
  record), so a rebuild spends no Open-Meteo calls.
