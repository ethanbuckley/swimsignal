# E. coli refit on the site's pins (October 2026)

Written and committed on 12 Oct 2026, before the cache top-up and the run below. Results are added
in a later commit, under "Results".

## Why

#199 made the E. coli evaluation place each bathing water as the site does. Its stated test
(`docs/EVAL-PINS-TEST-2026-10.md`) measured the effect and recommended the change. #201 regenerated
the Accuracy files 32 seconds before #199 merged, so they describe the old pins. The E. coli model
the site serves (`ecoli_model.json`, `ecoli_model_eval.json`) dates from 16 Sep. On 12 Oct Ethan
asked for the cache to be topped up for the site's pins and for the chain to be rerun on main,
with the refitted model and the Accuracy files committed together.

## Steps

1. **Cache top-up.** Run `fetch_rain_leads_upstream.py` and `fetch_rain_validation.py` on main
   `66e2d81` (site pins) in a scratch `DIPCAST_ROOT`, writing into the shared `data/cache/rain`. The
   overflow table is the one #201's runs used. It was rebuilt on network `ccc58f6b` from the `state`
   release's snapshot uploaded at 13:12 UTC on 12 Oct, the same snapshot #199 used. Expected: 16
   new files, lead and archive rain for cells (51.4, -1.9) and (51.9, -1.7), 2023–2026. That
   would make 3,658 files.
2. **One run of the chain** on main `66e2d81`, offline and alone: `validate_ecoli`,
   `replay_ecoli_leads`, `validate_ecoli_combined`, then `train_ecoli`. The scratch root is built
   as for #201:
   - the main checkout's untracked `bwq_samples.parquet`, `edm_events.parquet` and
     `river_network.pkl`;
   - copies of main's tracked raw and processed files;
   - the overflow table above;
   - rain from a fixed view of the shared cache after step 1.

## What I expect

#199's `site` run used the same pins, network and snapshot, and the same 3,658 rain files (in its
own copy). Its `validate_ecoli.py` was main `e52b750`'s, before #200. So the run should reproduce
that column of its results table:

- **`train_ecoli`:** samples in the fit 1,502 (31 sites); LOYO Brier 0.0938; LOYO AUC 0.813, 0.747
  and 0.528 (all, rivers, lakes); coefficients 0.589, -0.263 and -2.406 (exposure, lake,
  intercept); water lead skill 0.759, 0.694, 0.551 and 0.551. All equal at the precision #199
  reported.
- **`validate_ecoli_combined`:** between-site rho 0.763 and LOYO within-site rho 0.422, equal.
  It already drops rows without `rain_48h`, so #200 cannot change it.
- **`validate_ecoli`:** the `risk_model` measures (all sites rho pooled 0.631, within site 0.314,
  AUC over 900 0.810) within 0.003. #200 removes the Derwent Water sample of 7 Sep 2026, where the
  archive ends. That row has no `rain_48h` but did have a `risk_model`. Colwick's 7 Sep row has no
  overflows upstream with the site's pin.

If a `train_ecoli` or combined figure differs at #199's precision, or a `validate_ecoli` figure
differs by more than 0.003, I stop. I report it before committing anything.

## What gets committed

- `data/processed/ecoli_model.json` and `ecoli_model_eval.json`: the refitted model and its
  evaluation. They change the spot pages' E. coli estimates and water lead skill.
- `data/processed/ecoli_validation.json`, `ecoli_validation_combined.json` and
  `ecoli_validation_per_site.csv`: the Accuracy files.
- `data/processed/validation_sites.csv`: written by `fetch_rain_validation.py` in step 1. It is the
  per-site upstream summary, last made on 13 Sep, and now uses the site's pins.

Nothing else is committed. The exposure and rows parquets are git-ignored. No spill model is
refitted. Nothing merges without Ethan's go.
