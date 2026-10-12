# Missing rain in the E. coli validation (October 2026)

Written and committed on 12 Oct 2026, before any of the runs below. Their results are added in a
later commit, under "Results".

## What was found

The E. coli scripts read rain from the cache only (`data/cache/rain`). On 12 Oct 2026 the cache
lacked cells that today's upstream sets need:

- **Lead rain** (`leads_*`, read by `replay_ecoli_leads.py`) lacked 10 cells: 67 overflows at six
  sites. All 67 are upstream only since the network repairs of #184 (11 Oct). On the network as it
  loaded before #184 (`RiverNetwork(fix=False)`), none is upstream. The files were written 12–16 Sep.
  The replay counts these overflows as missing (`missing_share`, as production does). This is the
  side finding of `docs/SPILL-SIZE-TEST-2026-10.md` (PR #197).
- **Archive rain** (`archive_*`, read by `validate_ecoli.py`) lacked 43 cells (170 cell-years) that
  `fetch_rain_validation.py` asks for today. This touched 307 of 1,750 samples at seven sites. The
  share of transport weight from overflows with no rain in the sample year was: Sheep's Green
  0.705, Wolvercote Mill Stream 0.209, River Avon at Queen Elizabeth Gardens 0.067 (2026), Ham and
  Kingston 0.027 (2026), Wallingford Beach 0.025, Colwick Country Park (West Lake) 0.010 and River
  Severn in Shrewsbury 0.002 (2026). Why 33 of the 43 cells were missing before #184 is not
  established.
- **`validate_ecoli.py` filled missing rain with 0.** So an overflow whose cell the cache lacked
  counted as a dry day, and nothing said so. Its `risk_model` feeds `validate_ecoli_combined.py`,
  the published `ecoli_validation*.json`, and PR #197's cross-site rho.
- **The live forecast is not affected.** It fetches rain for every upstream cell at each build. In
  the published `spots.json` of 12 Oct, `rain_missing_share` is 0 at all six sites.

## The refresh (12 Oct 2026, about 17:30 BST)

Both fetch scripts were run in a scratch `DIPCAST_ROOT` with an overflow table rebuilt on the
current network (key `ccc58f6b`): `fetch_rain_leads_upstream.py` added 42 lead files and
`fetch_rain_validation.py` added 170 archive files, with no failed request. Afterwards no cell-year
that either script asks for is missing. The two extra lead files are 2023 for cells 51.3,-0.4 and
51.3,-0.5, which already had 2024–2026.

## The change

`validate_ecoli.py` now treats an overflow-day with no rain data as unknown, as production
(`forecast.spill_probabilities`), the replay and `check_ecoli_wales.py` do:

- its spill chance is NaN, so it adds nothing to `risk_model`;
- `missing_share` (`transport.missing_share`) is written for every sample;
- a sample day over `forecast.MAX_MISSING_SHARE` (0.1) gets no `risk_model`, because the site would
  have shown no figure. The downstream scripts already drop rows without `risk_model`;
- a warning lists the sites with missing rain, and `ecoli_validation.json` gains
  `samples_without_figure`.

## Runs, stated before running

Each run is offline (every outgoing connection refused) and runs alone. Each uses its own scratch
`DIPCAST_ROOT`, built as in PR #197's `setup_root.sh`:

- the main checkout's untracked data (`bwq_samples.parquet`, `edm_events.parquet`,
  `river_network.pkl`);
- this branch's tracked raw files, and copies of its tracked processed files;
- `live_latest.parquet` from the `state` release;
- the overflow table rebuilt on the current network (key `ccc58f6b`).

Rain comes from one of two fixed views of `data/cache/rain`, made of symlinks:

- "refreshed": the 3,642 files there after the refresh;
- "before": the 3,430 files listed just before it.

| run | `validate_ecoli.py` | rain |
|---|---|---|
| R1 | main `e52b750` | refreshed |
| R2 | this branch | refreshed |
| R3 | this branch | before |
| R4 | main `e52b750` | before |

Each run is `validate_ecoli.py` and then `validate_ecoli_combined.py`. No model is refitted. No
tracked output from these runs is committed.

What I expect, and what will be reported:

1. **Neutral on a complete cache (R1 against R2).** `risk_model` is equal within 1e-9 on every row
   whose `missing_share` in R2 is 0. Rows with `missing_share` above 0 in R2 are listed (site, day,
   share). I expect them only where the archive itself ends: the 2026 files fetched before 12 Oct
   stop at 6 Sep 23:00 UTC, and the samples run to 7 Sep 2026. If any other row differs, the change
   is not neutral, and I say why before going on.
2. **The guard works (R3).** It warns at the seven sites above. Their `missing_share` on sample days
   matches the shares above within 0.002. Beyond those, only the 7 Sep 2026 rows of point 1 may
   show a share. The samples over 0.1, which I expect to be Sheep's Green's 58 and Wolvercote's 75,
   get no `risk_model`.
3. **What the gap did to the published numbers (R4 against R1).** I will report, with no
   prediction:
   - `risk_model`'s pooled and within-site Spearman, and its AUC over 900 and over 500, for all
     sites;
   - the per-site rho at the seven sites;
   - `validate_ecoli_combined.py`'s measures.

   Whether to regenerate the published validation files (`data/processed/ecoli_validation*.json`
   and `.csv`) on the refreshed cache is Ethan's decision. This PR does not regenerate them. PR
   #197's runs are not redone here.

## Results (12 Oct 2026, 17:31–17:43 BST, after the statement above was committed in 243cebe)

All four runs were offline and logged 0 network attempts. They ran one at a time, with a peak of
3.7 GB each. Every expectation held as stated.

### 1. Neutral on a complete cache: holds

R1 and R2 have the same 2,165 rows. On the 2,163 rows where R2's `missing_share` is 0, the largest
difference in `risk_model` is 6.7e-16. Two rows have `missing_share` above 0. Both are on 7 Sep
2026, where the archive ends, and both already had no `rain_48h`:

| site | day | `missing_share` | R2 `risk_model` | R1 `risk_model` |
|---|---|---|---|---|
| Derwent Water at Crow Park | 7 Sep 2026 | 0.103 | none | 0.016 |
| Colwick Country Park (West Lake) | 7 Sep 2026 | 0.814 | none | 0.177 |

### 2. The guard works: holds

R3 warns at the seven sites, and their shares match the ones stated above within 0.002:

| site | `missing_share` on sample days | stated |
|---|---|---|
| Sheep's Green, River Cam | 0.7048 | 0.705 |
| Wolvercote Mill Stream | 0.2088 | 0.209 |
| River Avon at Queen Elizabeth Gardens | 0.0675 | 0.067 |
| Ham and Kingston, River Thames | 0.0265 | 0.027 |
| Wallingford Beach, River Thames | 0.0246 | 0.025 |
| Colwick Country Park (West Lake) | 0.0102 | 0.010 |
| River Severn in Shrewsbury | 0.0018 | 0.002 |

The only other shares are the two 7 Sep 2026 rows of point 1. 135 samples are over 0.1: Sheep's
Green's 58, Wolvercote's 75, and those two rows. None of the 135 has a `risk_model`.

### 3. What the gap did to the numbers (R4 against R1, both main's code)

These are `risk_model` measures. R4 used the cache as it was; R1 used the refreshed one.

| measure | R4 (stale cache) | R1 (refreshed) | change |
|---|---|---|---|
| all sites: Spearman pooled | 0.563 | 0.564 | +0.001 |
| all sites: Spearman within site | 0.286 | 0.288 | +0.002 |
| all sites: AUC over 900 | 0.793 | 0.796 | +0.004 |
| all sites: AUC over 500 | 0.789 | 0.791 | +0.002 |
| rivers: AUC over 900 | 0.744 | 0.749 | +0.004 |
| lakes: AUC over 900 | 0.606 | 0.606 | 0 |
| combined: between-site rho (risk) | 0.684 | 0.705 | +0.021 |
| combined: within site, spill risk only, rho | 0.357 | 0.361 | +0.004 |
| combined: rivers, spill risk only, rho | 0.500 | 0.509 | +0.009 |
| combined: within site, rain + risk + season, AUC over 900 | 0.866 | 0.868 | +0.002 |

At site level the gap mattered most at Sheep's Green. There, `risk_model` rises by 0.023 on
average and by up to 0.216, and the site's rho goes from 0.320 to 0.346. Wolvercote's rho goes from
0.165 to 0.152, and River Avon at Queen Elizabeth Gardens' from 0.584 to 0.596. The other four
sites move by 0.005 or less.

The gap biased these measures down a little. The largest effect is on between-site rho (+0.021).
The published `ecoli_validation.json` and `ecoli_validation_combined.json` were last regenerated on
14 Sep (c11d8f0), on an older network and older code, so they match neither run. Regenerating them
is Ethan's decision, and this PR does not do it.
