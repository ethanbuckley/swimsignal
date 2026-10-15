# Residence time at spill-time flow: the test, stated before any flow was fetched or any run

Written 13 October 2026. It follows `docs/LAKE-RESIDENCE-TEST-2026-10.md`: same candidate family, inputs, harness
and conditions. Nothing in this test has been run, and no flow has been fetched. Results go below the line at the
end. Nothing above it changes after a result is seen.

## Why

The first test passed all seven conditions with lake path `residence`. Its section "Which way the errors go" names
three biases, all making a lake remove too much of a spill. One of them can be measured:
- HydroLAKES' residence time is the volume over the long-term **mean** outflow.
- Overflows spill in wet weather, when a lake's inflow is several times its mean. Water then passes through faster.

Ethan asked for this variant on 13 October 2026. Until it is judged, the default is back to lake path `lake`
(commit a46fdd3). So #211 changes nothing the site uses unless this variant passes.

## The variant

`DIPCAST_LAKE_PATH_MODE=residence_spill` (`config.LAKE_PATH_MODE`), off.
- **The rule:** as `residence`, with each lake's τ replaced by τ_spill = τ / max(R, 1). R is the lake's
  spill-time flow ratio.
- **Same formulas:** share alive 1 / (1 + k τ_spill), survivors' hours τ_spill / (1 + k τ_spill),
  k = ln 10 / 30 h.
- **Lakes with no τ** are crossed as in `lake`.
- **The spot's own lake** is unchanged.
- **The times** are read from `data/raw/lake_residence_spill.csv` (`config.LAKE_RESIDENCE_SPILL_FILE`), written by
  `scripts/make_lake_spill_ratio.py` (in this commit).
- **Click-anywhere** follows it, as it follows `residence`. Only the file differs.

### R, the spill-time flow ratio

For each of the 282 WFD lakes with a τ:

**1. Spill days.** The calendar days (UTC) that any part of a discharge event covers, at any United Utilities
overflow:
- upstream of the lake's outlet within the 60 km network cap, or on the lake;
- with the events from `data/processed/edm_events.parquet` (read only). These are United Utilities' event records
  for 2023, 2024 and 2025, the only event records held.
- An event that spans several days counts each day.
- Lakes outside United Utilities' area have no spill days, so they get no R of their own.

**2. Reference gauge.** The rule:
- **Candidates:** stations in the Environment Agency Hydrology API (environment.data.gov.uk/hydrology, OGL v3.0)
  that measure flow and have a daily mean flow measure (`…-flow-m-86400-m3s-qualified`).
- **Placing a station:** snapped to the nearest river link (inland river, tidal river or canal) within 250 m.
  Otherwise it is not used.
- **Which counts:** a station on the lake's outflow (downstream of its outlet node) or on an inflow (its water
  reaches the lake).
- **Distance:** along the network, from the outlet for an outflow station, or to the lake for an inflow station.
  It must be 10 km or less.
- **Choice:** the nearest such station. On a tie, the outflow station.

**3. R.**
- The station's long-term mean flow is the mean of every daily mean in its whole record, as the API returns it
  (one request, up to 100,000 readings).
- R is the median, over the lake's spill days that have a daily mean, of that day's mean over the long-term mean.
- The API's daily date is matched to the UTC spill day.
- At least 30 such days are needed.

**4. Lakes with no R.** A lake with no gauge, no United Utilities overflow upstream, or under 30 days takes the
median R of the lakes that have one.

**5. Requests.**
- EA Hydrology only: one request for the station list, then one per chosen station.
- One process, one request at a time, 2 s apart, with the User-Agent in `config.EA_HEADERS`.
- Each response is cached in the scratchpad.
- No Open-Meteo, NRFA or other source.
- If the EA refuses (403), rate-limits (429) or fails (5xx), the script stops. I report it, and nothing is run.

What the rule cannot capture, stated now:
- A gauge on an inflow sees only that inflow's flow, not the lake's whole inflow.
- R is a median, so the wettest spill days pass more than this.
- The other two biases (full mixing, a low modelled upland mean flow) remain.

## The evaluation

As in `docs/LAKE-RESIDENCE-TEST-2026-10.md`, unchanged but for the mode and the file:
- **Harness:** `scripts/lake_residence_eval/` with `MODE=residence_spill` (`queue.sh`). `run_variant.sh` now gives
  the copied file to both residence settings, so the mode reads it.
- **Inputs:** the same frozen data folder: #205's inputs, overflow table `e6ef0459…`, network `b5724303`, 3,658
  cached rain files.
- **Runs, in a fresh scratch folder:**
  - `lake`: the default, run again;
  - `res`: `residence_spill` with `lake_residence_spill.csv`;
  - `ph01` to `ph20`: `residence_spill` with the R-adjusted times permuted across the same 282 lakes, numpy
    `default_rng(k)` (`make_placebos.py`).
- **Running:** offline (every outgoing connection refused and counted), one run at a time, each waiting for 5 GB
  free plus inactive memory.
- **Check:** `lake` reproduces 1,502 samples and LOYO Brier 0.0938.

## What counts as passing

The seven conditions of the first test, unchanged, with `res` now meaning `residence_spill`. `judge.py` applies
them.
1. **Brier:** LOYO, LOSO and forward; the upper end of the interval of the change is at most +0.0005.
2. **AUC:** all sites and rivers (LOYO); the lower end is at least −0.005.
3. **Cross-site rho:** the lower end is at least −0.05.
4. **Within-site rho:** both point changes are at least −0.01.
5. **Lakes:** the upper end of the lake LOYO Brier change is at most +0.0005.
6. **Placebos:** on each of LOYO Brier, LOYO AUC, LOYO AUC rivers and cross-site rho, at least one of the 20
   placebos is at least as bad as `res`. These are `summary.py`'s rounded figures, as stated before. The unrounded
   counts, from each run's held-out predictions, are reported beside them, as in the first test.
7. **Face check:** `tests/test_lake_residence.py` passes, including its new `residence_spill` test.

Every run must make 0 network attempts.

**What follows:**
- **All seven hold:** `residence_spill` becomes the default in a separate, final commit. Method page, README and
  LICENSE-DATA are updated, and EA Hydrology is credited as the terms page credits it. Left for Ethan to merge.
- **Any fails:** the default stays `lake`. #211 is a record, with `residence` and `residence_spill` as options.

## What will be reported

Whatever the verdict:
- R, its gauge and its number of days for Grasmere, Rydal Water, Windermere (N Basin) and Windermere (S Basin);
- how many of the 282 lakes are gauged with enough days, and the median R;
- Grasmere WwTW's weight at Rydal Water under `lake`, `residence` and `residence_spill`;
- the sum of weights at the Windermere sites (Waterhead, Lakeside YMCA, Fellfoot, Millerground, Rayrigg) under
  the same three;
- the seven conditions, and the record table of the first test.

## Seen before writing

- The first test's results.
- Its quartered-τ sensitivity: Rydal Water 0.0038.
- The coordinator's check (ddba70d) that the 282 rows match HydroSHEDS' own points file.
- No flow, no spill-day count and no R for any lake has been looked at.

---

## Results

Added 14 October 2026, after the runs. Everything above the line is as committed in 21ba2d9 (13 October 2026,
17:53 BST). That commit was pushed before the flow fetch (17:54) and before the first run (22:07). The variant, the
R file and the harness were not changed after any result was seen.

**Verdict: all seven conditions hold. By the rule above, `residence_spill` becomes the default, in the final
commit of #211.** As with `residence`, the samples show no harm and cannot show a gain.

### R (`data/raw/lake_residence_spill.csv`, d635756)

How it was built:
- 11 EA Hydrology requests, none refused, made 13 October 2026 between 17:53 and 17:54 BST.
- 1,102 flow stations have a daily mean measure. 1,079 snap to a river link.

Which lakes got their own R:
- 10 of the 282 lakes are gauged with at least 30 spill days. Their median R is 1.88, which the other 272 lakes take.
- Why the rest have none:
  - 131 have no gauge within 10 km;
  - 71 have no United Utilities overflow upstream;
  - 69 have no lake links in the network;
  - 1 (Derwent Water, Portinscale gauge) has under 30 spill days with a reading.

| lake | United Utilities overflows upstream | spill days 2023-25 | gauge | side, distance | R | τ → τ_spill (days) |
|---|---|---|---|---|---|---|
| Grasmere | 1 | 271 | Rothay at Miller Bridge House | outflow, 5.1 km | 2.24 | 38.9 → 17.4 |
| Rydal Water | 1 | 271 | Rothay at Miller Bridge House | outflow, 2.8 km | 2.24 | 15.9 → 7.1 |
| Windermere (N Basin) | 3 | 289 (268 with a reading) | Trout Beck at Calgarth | inflow, 0.3 km | 2.04 | 187.0 → 91.7 |
| Windermere (S Basin) | 6 | 473 | Leven at Newby Bridge | outflow, 0.4 km | 1.90 | 131.2 → 69.0 |
| Esthwaite Water | 1 | 430 | Eel House Bridge | outflow, 1.4 km | 1.87 | 79.5 → 42.5 |
| Coniston Water | 2 | 498 | Coniston Upstream | inflow, 0.3 km | 1.36 | 281.0 → 206.3 |
| Ullswater | 1 | 154 | Pooley Bridge | outflow, 0.8 km | 1.68 | 379.7 → 225.8 |
| Bassenthwaite Lake | 16 | 624 | Ouse Bridge | outflow, 0.2 km | 1.22 | 64.2 → 52.7 |
| Pennington Flash | 29 | 515 | Little Woolden Hall | outflow, 8.6 km | 1.35 | 16.1 → 11.9 |
| Worthington Reservoir | 7 | 313 | Wigan | outflow, 5.3 km | 1.89 | 3.3 → 1.7 |

Grasmere's only upstream United Utilities overflow is Grasmere WwTW. So its spill days are that works' spill days.

### Transport (spot pins as the site places them)

| place | `lake` | `residence` | `residence_spill` |
|---|---|---|---|
| Rydal Water: Grasmere WwTW | 0.0398 | 0.00098 | 0.00216 |
| Waterhead: Grasmere WwTW | 0.0018 | 0.0000026 | 0.000013 |
| Waterhead, sum of weights | 0.1446 | 0.1428 | 0.1428 |
| Lakeside YMCA, sum | 0.0278 | 0.0267 | 0.0268 |
| Fellfoot, sum | 0.00864 | 0.00830 | 0.00831 |
| Millerground Landing, sum | 0.13374 | 0.13350 | 0.13350 |
| Rayrigg Meadow, sum | 0.14646 | 0.14625 | 0.14625 |

### The runs

- 22 runs, 22:07 to 01:54, one at a time.
- They waited from 17:56 to 22:07 for 5 GB of free plus inactive memory, which other programs held. While memory
  stayed tight, some runs took up to 30 minutes.
- 0 network attempts in all 22. Peak memory 7.7 GB (`replay_ecoli_leads.py`).
- **Check:** `lake` gives 1,502 samples and LOYO Brier 0.0938. Every run kept all 1,502 samples.

### Conditions 1 to 5, `residence_spill` against `lake`, paired

| measure | `lake` | `residence_spill` | change [95% CI] |
|---|---|---|---|
| LOYO Brier | 0.09383 | 0.09381 | −0.00002 [−0.00004, −0.00001] |
| LOYO Brier, rivers (907) | 0.13821 | 0.13817 | −0.00004 [−0.00006, −0.00002] |
| LOSO Brier | 0.09326 | 0.09324 | −0.00001 [−0.00002, −0.000001] |
| Forward Brier (997) | 0.08523 | 0.08521 | −0.00002 [−0.00004, −0.000002] |
| LOYO Brier, lakes (595) | 0.02618 | 0.02618 | −0.000003 [−0.000007, −0.0000002] |
| LOYO AUC | 0.8129 | 0.8129 | +0.0001 [−0.0001, +0.0002] |
| LOYO AUC, rivers | 0.7470 | 0.7470 | +0.0001 [−0.0001, +0.0003] |
| Cross-site rho (31 sites) | 0.7625 | 0.7617 | −0.0008 [−0.0065, 0.0000] |
| Within-site rho, all sites | 0.3139 | 0.3139 | 0.0000 |
| LOYO within-site rho, rain + risk + season | 0.422 | 0.423 | +0.001 |

All five conditions hold, by the same margins as `residence`:
1. Brier: the upper ends are all below 0.
2. AUC: the lower ends are −0.0001 and −0.0001.
3. Cross-site rho: the lower end is −0.0065. Fellfoot and Rutland Whitwell Creek swap 29th and 30th, as under
   `residence`.
4. Within-site rho: the changes are 0.000 and +0.001.
5. Lakes: the upper end is below 0.

### Condition 6: placebos. Holds.

| measure | `residence_spill` | 20 placebos: lowest, median, highest | at least as bad (stated, rounded) | unrounded check: at least as bad / as good |
|---|---|---|---|---|
| LOYO Brier | 0.0938 | 0.0938, 0.0938, 0.0938 | 20 | 6 / 14 |
| LOYO AUC | 0.8129 | 0.8129, 0.8129, 0.8129 | 20 | 10 / 16 |
| LOYO AUC, rivers | 0.7470 | 0.7469, 0.7470, 0.7471 | 13 | 8 / 16 |
| Cross-site rho | 0.76169 | 0.76169, 0.76169, 0.76250 | 18 | 18 / 20 |

As in the first test, the placebos fall on both sides, so the samples cannot tell one lake's time from another's.

### Condition 7: face check. Holds.

`tests/test_lake_residence.py`: 10 passed.

### The sites that move, for the record

LOYO, `lake` → `residence_spill`. The figures match `residence` to the precision shown:

| site | samples | over 900 | mean LOYO prediction | LOYO Brier | mean exposure | rank of 31 |
|---|---|---|---|---|---|---|
| Lakeside YMCA | 57 | 0 | 0.0221 → 0.0218 | 0.00056 → 0.00054 | 0.00206 → 0.00185 | 28 → 28 |
| Fellfoot | 59 | 0 | 0.0201 → 0.0199 | 0.00046 → 0.00045 | 0.00070 → 0.00063 | 29 → 30 |
| Millerground Landing | 59 | 0 | 0.0272 → 0.0272 | 0.00087 → 0.00087 | 0.00805 → 0.00801 | 23 → 23 |
| Rayrigg Meadow | 57 | 0 | 0.0284 → 0.0284 | 0.00094 → 0.00094 | 0.00865 → 0.00862 | 22 → 22 |
| Wolvercote Mill Stream | 55 | 2 | 0.1615 → 0.1608 | 0.0571 → 0.0568 | 0.0261 → 0.0255 | 15 → 15 |

### What this shows

Established:
- `residence_spill` does no harm to any held-out score. It scores the same as `residence` to four decimals.
- It halves the residence times of the four Lake District lakes that matter here. So Grasmere WwTW at Rydal Water
  is 2.2 times what `residence` gives: 0.00216 against 0.00098. That is still 5% of `lake`'s weight.

Inferred, not tested:
- Of the three biases named in the first test, this removes part of the one that could be measured. Full mixing
  and a low modelled upland mean flow remain, both still in the direction of removing too much.
- R is a median over spill days, so the wettest spill days pass more than this.
- Rydal Water and Waterhead still have no samples.
