# `c_baseline.py`: a record, not a test

**Post hoc, exploratory and descriptive, not confirmatory; computed after the results were seen.** It ran on 26
October 2026, after every result of the soil-moisture tests had been seen: #344, the leads test, the Wales check and
the rivers-only test. It decides nothing. The HOLD on PR #361 rests on its pooled figure (amendment 3,
`docs/PREREGISTRATION-2027.md`). Its Wales and Wessex rows are reported, not used. No subgroup is adopted from them.

`c_baseline.py` and `c_baseline.json` are byte-identical to the files that ran (SHA-256 `faf2af90…` and
`52195611…`; copies in `swimsignal-private/soil-361-checks-2026-10-26/`). The JSON holds scores and summaries only,
with no sample rows. Do not rerun it as a test.

## How it ran

26 October 2026, about 00:26 to 00:27 UTC, offline (`run_offline.py`, 0 network attempts). It ran from a
`git archive` of 7ab958e (`<archive>`, which holds the rivers-only harness), in the root that `run.sh rivers` built
for the rivers-only test (`<rivers out>/root`).

    cd <archive>
    DIPCAST_ROOT=<rivers out>/root DIPCAST_STATE=<rivers out>/root/data/processed DIPCAST_CACHE=<frozen>/cache \
    PYTHONPATH=<archive>/src:<archive>/scripts:<archive>/scripts/soil_moisture_eval \
    python <archive>/scripts/lake_distance_eval/run_offline.py c_baseline.py \
      <main data>/cache/soil <main_ecoli_model.json> <rivers out> c_baseline.json \
      <main data>/processed/wales_annual.parquet <main data>/cache/nrw_wqa/Files <main data>/cache/wessex_wq <main data>/cache

## Inputs (SHA-256, first 16 hex digits)

| Input | Hash |
|---|---|
| `<main_ecoli_model.json>`: `data/processed/ecoli_model.json` as on main | `7daf7c8e407a82ba` |
| `<frozen>`: the frozen data folder of the soil tests (overflow key b5724303), 102 files of `processed` and `raw` | `dbded7ac…` (listing) |
| Its overflow table, `overflows.parquet` | `ebc96774…` |
| `<rivers out>/trace.pkl` (Welsh stations' trace) | `c5654b3133ccd43e` |
| `<rivers out>/trace_wessex.pkl` (Wessex points' trace) | `291de2749920e063` |
| `wales_annual.parquet` | `904db5783385eba8` |
| `wessex_wq/ecoli.parquet` (Wessex Water, CC BY 4.0) | `e02f8817cfa350de` |
| NRW archive zips: Carmarthen Bay 2000s, 2010s, 2020s; Wye 2020s | `f5f5ef3836f8b561`, `b7dd7306daa4c0cc`, `60d0114b718be07b`, `a7f2876e655789d7` |
| Soil cache: `q1_*`, `wales_*` and `rivers_*` files, 239 | `ef2cd9c328088a00` (listing) |

## Rows

- **English:** the rivers-only test's 1,502 frozen rows (`train_ecoli.py`'s, via `diagnostics.rows_q1`).
- **Wales and Wessex:** the rivers-only test's headline rows, 185 and 1,304 with known exceedance, as that test
  built them. They come from its saved traces, with the same rain and exposure.
- **Bootstrap:** the test's (region, sampling day) bootstrap, 2,000 draws, `default_rng(0)`.
