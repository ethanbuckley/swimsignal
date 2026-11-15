# Coastal candidate C1: protocol, rain fetch and run sheet

Written 13 November 2026, before any rain for C1 is fetched and before anything is fitted. Main was at `3abdd5b3`.
It is the next deliverable named by [the coastal baselines record](COASTAL-BASELINES-2026-11.md) (PR #692): a
candidate built on rain, frozen, then backtested on the 2012 to 2021 samples, which have not been fetched.

Nothing above the results line changes after a result is seen. A change is a dated amendment with both versions kept.

**Nothing coastal goes on the site, whatever the result.** No frozen file, issued prediction, active window or the
2027 primary evaluation is touched.

## What was known when this was written

- #692's tables and scores on 2022 to 2026 (seen data). Rain (radar, 24 and 72 hours, overflows within 5 km) was the
  only input supported on top of site and month: Brier difference −0.00014 (−0.00028 to −0.00001), whole years.
- The cached Open-Meteo archive files' cell list (which cells and years exist), not their values.
- The build's Open-Meteo ledger for 7 to 13 November (section 3).
- No 2012 to 2021 sample, and no archive rain value for any coastal cell, has been read by this work.

## 1. The question and the decision it supports

**Question.** At English coastal bathing waters, does rain in the hours before a statutory sample raise the chance
that its E. coli is over 500 cfu per 100 ml, once the site, the month and the last sample are known, in seasons that
played no part in building the model?

**Decision.** Whether rain is a confirmed input for a coastal research observation (for example "after rain like
this, past samples here were over the line more often") and for a later coastal shadow forecast. It does not decide
anything a swimmer is told. A pass does not put a coastal forecast on the site.

## 2. The candidate

**Target.** As #692: E. coli over 500. A `<` result never exceeds. A `>` result exceeds when its value is 500 or
more. Statutory samples (`MS`), 1 May to 30 September.

**Rain.** Open-Meteo's archive API, model `era5_land` named in the request, hourly `precipitation`, in UTC. One
series per site: the 0.1° cell of its sampling point (the same snapping as `rainfall.grid_cell`), with Open-Meteo's
default land cell selection. The grid point Open-Meteo used is kept with each file.

- Why ERA5-Land and not radar: radar starts in November 2024. The backtest years need the same source as the fit
  years, so C1 is fitted on archive rain too, not on the radar #692 used.
- Why the model is named: the cached archive files were fetched with the default (`best_match`), which may mix
  sources across years (not checked). Naming one model keeps 2012 and 2026 alike. The cached files are not used to
  fit C1. They are used once, offline, to compare with the new 2024 and 2025 files, and that comparison is reported.
- Why one cell and not a distance rule: #692 averaged radar over overflows within 5 km. A 0.1° cell is about
  11 by 7 km, coarser than that rule, and neighbour cells would add about 2,000 calls. This is a change from #692's
  "What follows" and is made here, before any rain value is read.
- `r_h` is the sum over the `h` hours whose hour-ending label is at or before the sample time (UTC, rounded down to
  the hour). A window counts only when at least 90% of its hours have a value; otherwise the row is not covered.
  Missing rain is never zero.

**Features.**

- `R`: the logit of the site's shrunk exceedance rate and month indicators, exactly as #692 section 4 (site rate
  `(k + m·p0) / (n + m)`, m by the method of moments, a training row's own year left out of k and n).
- Last sample: `x1 = log10(previous result) − 1`, 0 when none; `x2 = 1` when none. Previous statutory E. coli sample
  at the site, same calendar year. As in #692, its result may not have been published by the next sampling day.
- Rain: `log1p` of each window in the chosen pair.

**Window pairs, fixed now.** W1 = (24 h, 72 h), as #692. W2 = (24 h, 120 h). W3 = (48 h, 168 h). W4 = 24 h alone.

**Model.** scikit-learn `LogisticRegression`, `C = 1e6`, on R + last sample + rain.

**Choosing the window, on 2022 to 2026 only.** Leave one year out over the five fit years. Each pair is scored by
its pooled Brier score on the covered rows; the lowest wins. A pair within 0.000005 of the best loses to the one
earlier in this order: W4, W1, W2, W3. The nested estimate (the same choice made inside each outer held-out year)
is reported as development evidence. It decides nothing.

**C0, the same model without rain.** R + last sample, fitted on the same rows as C1.

**Freezing.** C1 and C0 are then fitted on every covered 2022 to 2026 row. One JSON file holds, for each: the
chosen pair, the coefficients, p0, m, the site-rate table (each site's k and n), the month rates, the rain source
and the code commit. Its SHA-256 goes in this record. That commit is pushed **before any 2012 to 2021 sample is
requested**. After that nothing in C1 or C0 changes.

## 3. The rain fetch

**Size, before any call** (`fetch_rain.py --dry-run`):

| | |
|---|---|
| Cells | 185 (the 0.1° cells of the 407 mapped sampling points) |
| Seasons | 15: fit 2026 to 2022 first, then backtest 2021 to 2012 |
| Days a season | 160 (24 April to 30 September; 7 days before 1 May for the 168-hour window) |
| Weight a cell-season | 0.1 × 160 / 14 = 1.143 calls (Open-Meteo's rule, `rainfall.call_weight`) |
| Requests | 285 (19 a season, 10 cells each, the last 5) |
| Weighted calls | 3,171.4: fit seasons 1,057.1, backtest seasons 2,114.3 |
| Daily cap | 1,000 calls, counted from the ledger, retries included |
| Days | 4 at the cap: 87 requests a day at most |
| Pace | 5 s between requests. With about 5 s a request, about 15 minutes a day; 50 minutes in all |

This is 770 calls more than #692's rough 2,400, which assumed cached files would cover 2024 to 2026. They are not
used (section 2), and 2026 needs September for every cell.

**The real daily spare, from the ledger.** The build books every Open-Meteo call in a UTC-day ledger
(`rainfall.calls_today`, logged as `open_meteo` in each build's summary). The last build of each UTC day showed:

| UTC day | Last build (UTC) | Calls | Spare to the 9,000 ration |
|---|---|---|---|
| 7 Nov | 22:07 | 4,484 | 4,516 |
| 8 Nov | 23:18 | 5,850 | 3,150 |
| 9 Nov | 21:11 | 3,423 | 5,577 |
| 10 Nov | 19:16 | 4,400 | 4,600 |
| 11 Nov | 21:39 | 4,908 | 4,092 |
| 12 Nov | 23:46 | 5,314 | 3,686 |
| 13 Nov | 18:12 (day not over) | 3,725 | |

These include the D4 ensemble (389 to 778 a day). None of these days held a request back (`held` was empty).
Builds after the last listed one would add to a day, so the spare is a little smaller than shown.

- **Measured:** the smallest spare in the week was 3,150 calls (8 November).
- **Planned:** the build's ceiling at a build every 30 minutes is 8,750 (`rainfall.PLANNED_DAY_CALLS`). Against the
  9,000 ration that leaves 250; against Open-Meteo's free limit of 10,000 it leaves 1,250.
- **The cap is 1,000.** It fits inside 1,250, so even a day on which the builds reached their planned ceiling would
  stay under Open-Meteo's 10,000 if the two were counted together. On the busiest measured day, the total would have
  been 6,850, under the 9,000 ration.
- Inferred, not checked: Open-Meteo counts by IP address (its terms, as `rainfall.py` quotes them), and this fetch
  runs from the Mac, not from a GitHub runner, so the two may not share a count at all. The cap does not rely on it.
- Hour and minute limits (5,000 and 600): at most 87 requests a day of at most 11.4 calls, 5 s apart, is under 140
  calls a minute.

**Rules** (in `scripts/coastal_c1/fetch_rain.py`, tested offline in `tests/test_coastal_c1_fetch.py`):

- **Not before 22 November 2026 (UTC).** The D4 ensemble test shares the spare budget until its read on 21 November
  ([its record](ENSEMBLE-RAIN-TEST-2026-11.md)). If that read triggers D4's 14-day extension, the fetch does not
  start before 6 December (the register's date). That needs an amendment here and a one-line change to `FIRST_DAY`.
- A request that would take the UTC day over 1,000 is not sent. The run stops; the next UTC day carries on.
- The first HTTP 429, 401 or 403, or a 4xx whose reason names a limit, stops the run and no further request is sent
  that UTC day. Another 4xx stops the run as a fault in the request. Neither is retried.
- A 5xx or a lost connection is tried again after 30 s and 90 s. Every try is ledgered and counted.
- An answer that does not hold every hour of the season for every cell is not saved, and the run stops.
- Every request sent is one line in `<out>/ledger.jsonl`: time, UTC day, season, cells, first cell, weight, try,
  status, bytes, SHA-256 of the body, outcome and, for a refusal or fault, the reason. Each cell-season is
  `<out>/rain/<season>/<cell>.parquet`. One on disk is never asked for again, so the same command resumes.
- The fetch reads no sample. The rain files and ledger are not committed during the fetch. The ledger and
  `complete.json` (counts and a hash of every file) are committed with C1's fit.
- If a refusal happens on two UTC days, the fetch stops for good and the record says so, with what was fetched.

## 4. Run sheet

`<out>` is a folder outside every checkout, so removing a worktree cannot lose it:
`$HOME/dipcast-scratch/coastal-c1-rain`. Run from a checkout of `main` that contains this PR, or this PR's worktree.

**Before the first run (22 November):**

1. Open [the D4 record](ENSEMBLE-RAIN-TEST-2026-11.md) and read its result. If it says the 14-day extension runs,
   stop: the first day is 6 December, and this record needs that amendment first.
2. Check the size, which sends nothing:

```bash
uv run python scripts/coastal_c1/fetch_rain.py --out "$HOME/dipcast-scratch/coastal-c1-rain" --dry-run
```

   It worked when it prints `"requests": 285` and `"calls": 3171.4`.

**Each day from 22 November (any time; the cap is per UTC day):**

```bash
uv run python scripts/coastal_c1/fetch_rain.py --out "$HOME/dipcast-scratch/coastal-c1-rain"
```

How to tell it worked:

- Exit code 0 and a last line like `Cell-seasons on disk: 1295 of 2775. Requests left: 152 ...`. The count of
  cell-seasons rises each day: by about 870 on a full day.
- The line before says `Daily cap reached: 994.3 of 1000 calls used today.` That is the normal end of a day.
- Exit code 2: before 22 November. Nothing was sent.
- Exit code 3: refused. Read the last line of `ledger.jsonl` for the reason. Do not run again that UTC day. Try once
  the next day. A second refusal on another day ends the fetch (section 3).
- Exit code 4: a fault (no answer after three tries, a short answer, or a wrong request). Read the last ledger line.
  The same command resumes; a fault that repeats is a bug to fix before running again.

To see progress at any time, sending nothing:

```bash
uv run python scripts/coastal_c1/fetch_rain.py --out "$HOME/dipcast-scratch/coastal-c1-rain" --status
```

**When it is complete:** the run prints `COMPLETE: every cell-season is on disk.` and writes `complete.json` with
`"cell_seasons": 2775` and `"refusals": 0` (or the count). At the cap that is the fourth day: 25 November if every
day runs. The fit seasons (2026 to 2022) are all on disk after the second day, so fitting may start then.

The mistake most likely: running it a second time on a day that ended with exit 3. The script refuses, but running
it from another folder with a different `--out` would not see the first ledger. Always use the same `--out`.

## 5. The backtest on 2012 to 2021

**Rows.** Statutory E. coli samples (determinand 2348, sampling purpose `MS`), 1 May to 30 September, 2012 to 2021,
at the 407 mapped archive points, mapped to sites as in #692. Enterococci are not fetched; nothing here uses them.
Sites are those in `data/research/coastal/sites.csv`; a site with no 2022 to 2026 history gets the pooled rate, as
in #692. Rows whose rain window is not covered are counted and left out of the rain comparison.

**Fetched how.** `scripts/coastal_baselines/fetch.py`, the E. coli stage, with its years set to 2012 to 2021 in
the backtest PR. Water Quality Archive, about 340 requests (17 groups of 25 points, 10 years, about 2 pages each),
a cap of 430 requests, 3 s apart, a ledger line each. An HTTP 401, 403 or 429 stops it, not retried; a 502, 503 or
504 is retried after 30 s and 90 s. Each paged group must add up to the archive's `totalItems`. From the Mac, not
CI. **Not before** the freeze commit in section 2 is pushed.

**Comparators**, all frozen on 2022 to 2026 and scored on the same backtest rows:

| Name | What |
|---|---|
| B0 | The pooled 2022 to 2026 rate |
| R | Site and month (#692's reference) |
| C0 | R + last sample, no rain |
| C1 | R + last sample + rain |

The EA's forecast was a #692 comparator. Its daily predictions are open from 2022; whether they exist for 2012 to
2021 is not known. After the freeze, one request per year for 15 July, 2012 to 2021 (10 requests, 10 s apart), says
whether they do. Any year with predictions is compared on its rows as a secondary result, after a sized amendment
for the season days. It is not part of the verdict.

**Main metric.** Brier score difference, C1 minus C0, on backtest rows covered by rain. Below zero favours rain.

**Interval.** 95% percentile interval from 2,000 bootstrap resamples that draw whole sites and whole seasons
independently (seed 20261122), the difference paired inside each resample. Ten seasons are enough to resample, so
the interval carries year-to-year spread as well, unlike #692's site-only intervals. The site-only interval is
reported beside it.

**Also reported, deciding nothing:** C1 and C0 against B0 and R; AUC with intervals; calibration in the large and
slope of the frozen C1; each year's Brier difference; the same for 2015 to 2021 alone, because classification under the
revised Bathing Water Directive began in 2015 and earlier sampling may differ; the over-250 target; the comparison of
new ERA5-Land with the cached archive rain on 2024 and 2025.

## 6. Verdicts and what each leads to

The margin is zero: rain must make the Brier score better, and the interval must show it.

| Verdict | Rule | What it leads to |
|---|---|---|
| **Supported on unseen seasons** | The two-way interval is wholly below zero, and the difference is below zero in at least 6 of the 10 seasons | Rain counts as a confirmed coastal input (frozen-model backtest, workflow "Backtest instead of waiting"). Next: a coastal research observation, designed against `docs/DESIGN.md`, saying only what the backtest showed; and a protocol for a 2027 shadow log of C1 with issue-time rain (forecast rain for hours after issue), its comparator C0 and its fallback. Calibration is fixed before any probability is shown, and nothing is shown as a forecast |
| **Mixed** | Point estimate below zero, but the interval includes zero or fewer than 6 seasons agree | Not confirmed, not closed. Next: a diagnosis of which seasons and regions carry it, and whether the 0.1° cell is too coarse (the overflow-cell rain #692 used is the obvious next candidate, if the budget allows) |
| **Not supported** | Point estimate at or above zero | Rain from a 0.1° archive cell does not help on unseen seasons. That closes this rain-only route at this resolution, not the coastal question. Next: outlet positions and spill direction (`docs/OVERFLOW-SEA-OUTFALLS-2026-10.md`), which needs currents (a Copernicus Marine account, Ethan's step) |
| **Too few** | Fewer than 300 exceedances in the covered backtest rows | Say so, with the count. Next: name what extra rows would settle it |

An interval that includes zero shows neither gain nor harm. No verdict changes what the site shows.

## 7. Budget and isolation

- Open-Meteo: 3,171.4 weighted calls in 285 requests over 4 days, from the Mac. No other Open-Meteo call.
- EA: about 340 Water Quality Archive requests and 10 bathing-water probes, after the freeze.
- Fitting: one process, under 30 minutes, outputs to a scratch folder. Fit and backtest code run with explicit
  scratch `DIPCAST_ROOT`, `DIPCAST_STATE` and output folders. Shared caches (`data/cache/rain`,
  `data/cache/rain_nine`) are read only, fingerprinted before and after.

## 8. Order of work, owner, milestones

1. This protocol, the fetch script and its offline tests (this PR). No call made.
2. 22 to 25 November: the rain fetch, one command a day (section 4).
3. From 24 November (fit seasons on disk): fit, choose the window, freeze; push the frozen hash.
4. Then: the 2012 to 2021 sample fetch, the backtest, the verdict, below the line here.

Owner: the research sessions. Ethan's steps: none unless a refusal happens or D4 extends.

## 9. Limits known now

- Archive rain is reanalysis, corrected after the fact. A live version would see radar or forecast rain instead.
  The backtest tests the link between rain and samples, not a live forecast.
- ERA5-Land at 0.1° smooths showers. A storm over one beach may not show.
- Sampling is planned, in working hours, in the season. Samples taken during a short-term pollution warning may be
  disregarded by the EA; the archive's `MS` rows do not say which.
- Laboratory and sampling practice may differ before 2015.
- The last-sample feature assumes the previous result was known by the next sampling day.

---

*Results go below this line.*
