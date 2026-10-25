# Why train.py did not rebuild main's spill model: layer 2 was fitted at recency 0.25

Checked 25 October 2026. A record of a finding, not a test. No model file changes.

## The question

On 25 October the day-boundary test (PR #334) found that `scripts/train.py` at main does not reproduce main's
model files. Layer 1 (the pooled model) came out the same; the site offsets (layer 2) did not. The hold-out file
scores 0.04451 on 2025, the rebuild 0.04472. Recency 0.5 and 0.7 were tried there and did not match.

## The answer

**Main's `spill_model.pkl` and `spill_model_holdout_2025.pkl` were fitted with layer-2 recency 0.25.**
`train.py`'s default is 1.0, and the setting is not stored in the files. The data, the code and the randomness
are not the cause.

## The evidence

- **The files.** Both were committed once, in 8ac835f (13 September 2026, 18:42 BST), and never refitted.
- **The code.** `SpillModel.fit_site_offsets` and `fit_pooled` are the same at 8ac835f and at main, apart from
  comments. `train.py`'s defaults were the same then as now: `--neg-frac 0.25`, `--recency 1.0`, prior 15.
- **Layer 1 is identical.** The rebuilt hold-out model's layer 1 and main's give the same probability, to the last
  bit, on 5,000 random inputs. `fit_pooled` trains on every spill day and a seeded quarter of the dry days, so an
  identical layer 1 needs the same rows, in the same order, with the same labels and features.
- **The rows are identical.** Rebuilt with current code and the main checkout's data, the rows per overflow equal
  each file's `site_n` at every overflow (2,241 in the hold-out file, 2,271 in production).
- **The offsets, recomputed.** `scripts/check_model_provenance.py` takes each file's own layer 1, rebuilds
  `train.py`'s rows, and recomputes the offsets with `fit_site_offsets`' formula at several recency weights:

| Recency | Hold-out: offsets matched exactly | Production: offsets matched exactly |
|---|---|---|
| 1.0 (`train.py`'s default) | 336 of 2,241 | 30 of 2,271 |
| 0.5 | 336 of 2,241 | 30 of 2,271 |
| 0.3 | 336 of 2,241 | 30 of 2,271 |
| **0.25** | **2,241 of 2,241** (largest difference 0.0) | **2,271 of 2,271** (largest difference 0.0) |
| 0.2 | 336 of 2,241 | 30 of 2,271 |

  Twelve values from 1.0 to 0.1 were tried; only 0.25 matches. The overflows that match at every value have rows
  in one year only, where the weight cancels.
- **The README agrees, without the number.** Its model section says the first run of 12 September scored 0.0447,
  and that "recency-weighting the site calibration improves it only slightly (0.0445)". The 13 September table
  shows 0.0445. So the files were the recency-weighted run. The value 0.25 was recorded nowhere until now.

## What this changes

- **`train.py`'s production path now defaults to recency 0.25**, so a rebuild gives production's offsets. The
  nine-company path keeps 1, as its test stated. `SpillModel` now records `site_recency` and `site_prior` when
  offsets are fitted. Older files load with both as `None`.
- **Earlier tests are not affected in their own terms.** The tests that refit layer 2 (nine-company, neural
  challenger, multi-year, covariate year, live-status feature, Scotland hindcast) stated "recency 1" and compared
  arms fitted the same way. Where a doc says "recency 1, as `train.py`", that was true of `train.py`. It was not
  true of production.

## Where this matters next

- **Day boundary (#334).** Its first run fitted both arms at recency 1, so its "old" arm was not production. It was
  rerun on 25 October with both arms at 0.25, after a dated addendum and with the same conditions and frozen
  inputs. The old arm then reproduced main's files exactly (every offset and layer 1 to 0.0), and the test passed
  again: N1 ΔBrier +0.000066 (interval −0.000090 to +0.000219, limit 0.000445), N2 at leads 0 to 4 within their
  limits. A pass is not a deployment: the lead maps, the live windows and the 2027 stamp still come first (#334).
- **Option B (`docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md`, merged, not yet approved).** It says its offsets use
  "recency 1, as now". Production is 0.25. Arm B also refits United Utilities over several years, so B against
  production would mix the start-date rule with a change of recency. This is for Ethan to settle before approving
  it.
- **Company calibration (#333).** Its statement says recency 1 is "exactly as `fit_site_offsets` does for United
  Utilities". That is not what production did. It does not matter there: its offsets are fitted on one four-week
  window, where recency has no effect, and production's United Utilities offsets are kept.

## The check after a change of day boundary

`features.py` cuts days for new models. PR #334 moves it to UK local days, and its `build_site_days` refuses a UTC
grid. The check must still rebuild the rows the 13 September files saw, which were UTC days. So
`check_model_provenance.py` no longer calls `features.daily_rain_features`, `spill_days` or `build_site_days`. It
uses frozen copies in `scripts/legacy_utc_days.py`: the three functions as they stood when every offset was
reproduced, with their constants fixed. Switching the check to local days instead would compare the old files with
rows they were never fitted on.

Checked on 25 October:
- On #334's branch with the old check (`da2b383`): `build_site_days: days in different zones {'days': 'UTC',
  'rain': 'Europe/London', 'labels': 'Europe/London'}`, before anything was checked.
- On #334's branch merged with this one: the check rebuilds the same rows as on main (1,577,907 hold-out, 2,404,632
  production), reproduces every stored offset at 0.25 and exits 0. The full suite passes there (1,024 passed).
- `tests/test_model_provenance_legacy.py`: the copies give UTC days, checked against values worked out by hand
  around a BST midnight; the check's rows do not touch `features.py`'s day functions; while `features.py` still cuts
  UTC days, the copies equal it frame for frame.

## How to rerun

```bash
DIPCAST_ROOT=<a data folder with edm_events.parquet and the rain cache> PYTHONPATH=scripts:src uv run python scripts/check_model_provenance.py --holdout data/processed/spill_model_holdout_2025.pkl --prod data/processed/spill_model.pkl
```

It reads only. It needs about 4 GB and 30 seconds. Exit 0 means each file is reproduced by some recency and,
where the file records one, by that one. The run of 25 October used the main checkout's data folder.
