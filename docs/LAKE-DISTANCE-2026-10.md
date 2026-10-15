# Lake distance through the water: the test, stated before any run

Written 16 October 2026. Nothing in this test has been run through the E. coli evaluation. Results go below the
line at the end. Nothing above it changes after a result is seen.

## Why

Item D of `docs/HANDOFF-2026-10-12.md` section 4, from an outside reviewer.
- For a lake spot, the distance from where an overflow's water enters the spot's lake to the spot is a straight
  line (`transport.upstream_overflows`, lake branch).
- In a lake that bends, the line crosses land. Pooley Bridge, at the foot of Ullswater, has 6.7 of 10.9 km of its
  line from Glenridding WwTW outside the lake.
- That distance moves at `config.LAKE_VELOCITY_MS`, 0.05 m/s. So 1 km is 5.6 hours, and with T90 = 30 h it is a
  factor of 0.65 in die-off.

Lakes crossed on the way to a spot are not part of this. Their metres are already the lengths of their centreline
links, walked link by link.

## The variant

`DIPCAST_LAKE_DISTANCE_MODE=water` (`config.LAKE_DISTANCE_MODE`), off. The default, `line`, is the straight line.

**The rule** (`src/dipcast/model/lake_water.py`, `transport.spot_lake_m`):
- **The water:** the union of the WFD lake polygons that the spot's lake links lie in (`transport._wfd_lake_of`).
  So Windermere's two basins are one water. It is simplified to 10 m (`WATER_SIMPLIFY_M`).
- **The distance:** the shortest path from the entry point to the pin that stays inside the water. A segment may
  use the water widened by 10 m, so the simplification cannot close a channel.
- **Where the straight line stays in the water,** the distance is that line. So only lines that cross land change.
- **A point outside the water** (an entry where a beck's line starts on the bank, a pin on the shore) first goes
  straight to the nearest point of the water. That leg is added.
- **How:** a shortest path in a polygon turns only at reflex corners: where land juts into the water, and the corners
  of islands. Those corners, joined where they see each other, form a graph, solved once per water.
- **Kept as the straight line:** a lake with no WFD polygon (a centreline lake), and two points in parts of the water
  that do not meet. The water distance is never shorter than the straight line.
- **Nothing else changes:** the river distance, the dilution, the lake area factor, the lake path rule
  (`residence_spill`, the default) and the 60 km cap.

**Why not the centreline.** The handoff names two candidates. The other, distance along the lake's own centreline
links, was not chosen:
- It would change every lake distance, including lines that stay in open water. The test would then mix the fault
  reported with a second change.
- Entry points and pins lie off the centreline, so it needs an extra rule for the legs to and from it.

## Seen before writing

Transport only, on the frozen data below, with `scripts/lake_distance_eval/report.py`. No rain, spill model or
E. coli figure was computed or looked at.

**Site spots.** 30 of the site's spots are placed in a lake; 19 have overflows upstream.
- The weights of 17 of the 19 change at all.
- At 8 of the 19 the sum of weights changes by 1% or more:

| spot | overflows | sum of weights, `line` → `water` | change | most metres added |
|---|---|---|---|---|
| Rutland Water Whitwell Creek | 5 | 0.02125 → 0.01465 | −31.1% | 1,652 |
| Ullswater, Pooley Bridge | 1 | 0.000375 → 0.000297 | −20.8% | 547 |
| Rutland Water Sykes Lane | 5 | 0.01267 → 0.01116 | −11.9% | 826 |
| Elter Water | 1 | 0.3970 → 0.3573 | −10.0% | 247 |
| Derwent Water, Calfclose Bay | 3 | 0.1862 → 0.1713 | −8.0% | 195 |
| Ullswater, near Sandwick | 1 | 0.00777 → 0.00745 | −4.2% | 100 |
| Windermere, Lakeside YMCA | 6 | 0.02676 → 0.02593 | −3.1% | 100 |
| Windermere, Fellfoot | 6 | 0.00831 → 0.00811 | −2.5% | 87 |

- Pooley Bridge: Glenridding WwTW's lake distance goes from 10,906 m to 11,453 m. The water path adds 5%, though
  6.7 km of the line is over land. The lake's bends are gentle, so the line is a short cut, not a long one.
- The other 9 that change move by under 1%: Waterhead, Monk Coniston, Millerground Landing, Glenridding, Rydal Water,
  Rayrigg Meadow, Coniston Boating Centre, Coniston Brown Howe, Derwent Water at Crow Park.
- Grasmere and Frensham Great Pond do not change.

**Evaluation bathing waters.** 16 are placed in a lake; 11 have overflows upstream, with 40 rows (pin and overflow).
- 10 change: both Rutland Water sites, the four Windermere sites, the three Coniston sites and Crow Park. Frensham
  does not.
- The ratio of water to line: Rutland 1.02 to 1.37; Windermere 1.0001 to 1.024; Coniston 1.0 to 1.017; Crow Park
  1.0001.

**Also seen:** the results of `docs/LAKE-RESIDENCE-TEST-2026-10.md` and `docs/LAKE-RESIDENCE-SPILL-2026-10.md`.

## The evaluation

As in `docs/LAKE-RESIDENCE-SPILL-2026-10.md`, with the lake distance in place of the lake path.

**Harness:** `scripts/lake_distance_eval/`, in this commit.
- `run_variant.sh` and `queue.sh` are the residence harness's with the lake distance option. The lake path stays at
  its default, `residence_spill`, reading the spill file in the frozen raw folder.
- `paired.py` and `summary.py` are the residence harness's, used unchanged from `scripts/lake_residence_eval/`.
- `judge.py` is the residence harness's with the runs renamed and this test's face check and record sites.
- `run_offline.py` adds the placebo swap described below. It lives in the harness, not in the model code.

**Inputs:** a copy of the frozen data folder both residence tests used, made on 16 October 2026 with every link
followed.
- Overflow table SHA-256 begins `e6ef0459`; the river network is the same `river_network.pkl` (SHA-256 `fc66101d`),
  and `load_overflows` checks the table's network key against it.
- 3,658 cached rain files.
- Raw files: `network_fixes.csv` `7ff7af1a`, `bwq_samples.parquet` `26f5f646`, `lake_residence_spill.csv` `c606c958`
  (the committed file), `wfd_lakes_cycle3.geojson` `c355d810`; `processed/lakes.parquet` `f54113b7`.
- Spots and pins come from this checkout's `spots.csv`, as `eval_pins.bathing_water_pin` reads them.

**Runs**, in a fresh scratch folder:
- `line`: the default, run again;
- `water`: lake distance `water`;
- `ph01` to `ph20`: placebos.

**The placebos.**
- `make_placebos.py` takes the 40 evaluation rows from `report.py`: each pin and overflow, with its ratio of water
  to line.
- Placebo k permutes the 40 ratios with numpy `default_rng(k)`: the same detours, given to other overflows at other
  lakes.
- In a placebo run, `run_offline.py` replaces each lake row's distance with the straight line times its placebo
  ratio. A row the file does not hold keeps the water distance and is counted. The count must be 0.

**Running:** offline (every outgoing connection refused and counted), one run at a time, each waiting for 5 GB free
plus inactive memory.

**Check:** `line` is the configuration of the `res` run of `docs/LAKE-RESIDENCE-SPILL-2026-10.md`. It should give
1,502 samples and LOYO Brier 0.0938. The code has moved on since (#214 to #222), so it may differ.
- If it differs, I report by how much and why, and the test goes on: `line` and `water` share the same code and
  inputs, so the comparison stays paired.

## What counts as passing

The seven conditions of the residence tests, with `line` as the reference and `water` as the candidate. `judge.py`
applies them.
1. **Brier:** LOYO, LOSO and forward; the upper end of the interval of the change is at most +0.0005.
2. **AUC:** all sites and rivers (LOYO); the lower end is at least −0.005.
3. **Cross-site rho:** the lower end is at least −0.05.
4. **Within-site rho:** both point changes are at least −0.01.
5. **Lakes:** the upper end of the lake LOYO Brier change is at most +0.0005.
6. **Placebos:** on each of LOYO Brier, LOYO AUC, LOYO AUC rivers and cross-site rho, at least one of the 20
   placebos is at least as bad as `water`. These are `summary.py`'s rounded figures, as in both residence tests. The
   unrounded counts, from each run's held-out predictions, are reported beside them.
7. **Face check:** `tests/test_lake_distance.py` passes. Among its checks: in an L-shaped lake the water distance
   goes round the inner corner, the weight falls by exactly the die-off of the added metres, a line that stays in
   the water is kept, and the default is `line`.

Every run must make 0 network attempts, and every placebo run 0 placebo misses.

**What is expected, stated now.**
- Most of the evaluation's lake rows change by under 2%. Rutland Water is the exception. So the changes in the
  scores should be small, as in the residence tests.
- None of the Windermere sites had a sample over 900 cfu/100 ml in the residence tests. At a site with no
  exceedance, a lower prediction always lowers the Brier score. So a Brier gain there would be arithmetic, not
  evidence.
- Condition 6 guards against harm only. With changes this small the placebos are expected to fall on both sides.

**What follows:**
- **All seven hold:** `water` is a candidate for the default.
  - It cannot be the default while click-anywhere does not follow it. A map click would then disagree with the spot
    page.
  - So the PR first extends click-anywhere (`scripts/build_any_point.py`, `anypoint.js` and their consistency
    test), then switches the default in a separate, final commit. It is left for Ethan to merge.
  - If click-anywhere is not finished in this session, the PR says so, and the switch stays off.
- **Any fails:** the default stays `line`. The PR is a record, with `water` as an option.

If the option, the placebo files or the harness change after a result is seen, both results are kept and the change
is stated.

## What will be reported

Whatever the verdict:
- the seven conditions, the placebo counts rounded and unrounded, and the network and placebo-miss counts;
- the record table for the ten evaluation sites that change: samples, samples over 900, mean LOYO prediction, LOYO
  Brier, within-site rho, mean exposure and its rank;
- the count of lake spots whose weights change, at all and by 1% or more, as above;
- Pooley Bridge's distance and weight under both.

---

## Results

Not yet run.
