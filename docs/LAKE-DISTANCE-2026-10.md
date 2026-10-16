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

Added 16 October 2026, after the runs. Everything above the line is as committed in 886e6fc (16 October 2026,
00:23 BST), pushed before the first run started (01:00 BST). The option, the placebo files and the harness were not
changed after any result was seen.

**Verdict: all seven conditions hold. By the rule above, `water` becomes the default, in the final commit of this
PR, after click-anywhere follows it (ff92c5d).** As in the residence tests, the samples show no harm and cannot show
a gain.

### How it was run

- The runs used an archive of 886e6fc in a scratch folder, not the working branch. So later commits on the branch
  (click-anywhere, the merge of main) could not reach them.
- One later change touches the rule's code: `lake_water.water_distance` was split so the click-anywhere build can
  share a step (`from_point`), in ff92c5d. On all 109 real rows of `report.py` it gives the same distances as
  886e6fc (largest difference 0.0 m).
- 22 runs, 01:00 to 03:01 BST, one at a time, 5.3 to 6.0 minutes each. They waited from 00:23 to 01:00 for 5 GB of
  free plus inactive memory.
- 0 network attempts in all 22. 0 placebo misses in all 20 placebo runs. Peak memory 6.6 GB
  (`replay_ecoli_leads.py`).
- **Check:** `line` gives 1,502 samples and LOYO Brier 0.093805, as the `res` run of
  `docs/LAKE-RESIDENCE-SPILL-2026-10.md`. Its held-out predictions equal that run's to within 1e-13. So the code
  merged since (#214 to #222) does not move the evaluation.
- Every run kept all 1,502 samples.

### Conditions 1 to 5, `water` against `line`, paired

Change is `water` minus `line`, with its 95% interval.

| measure | `line` | `water` | change [95% CI] |
|---|---|---|---|
| LOYO Brier (1,502) | 0.093805 | 0.093812 | +0.0000064 [+0.0000014, +0.0000115] |
| LOYO Brier, rivers (907) | 0.138169 | 0.138181 | +0.0000124 [+0.0000039, +0.0000207] |
| LOSO Brier | 0.093245 | 0.093242 | −0.0000029 [−0.0000065, +0.0000007] |
| Forward Brier (997) | 0.085211 | 0.085209 | −0.0000028 [−0.0000050, −0.0000007] |
| LOYO Brier, lakes (595) | 0.026179 | 0.026176 | −0.0000027 [−0.0000064, +0.0000005] |
| LOYO AUC | 0.81292 | 0.81290 | −0.00001 [−0.00011, +0.00009] |
| LOYO AUC, rivers | 0.74704 | 0.74696 | −0.00007 [−0.00018, +0.00003] |
| Cross-site rho (31 sites) | 0.7617 | 0.7625 | +0.0008 [0.0000, +0.0065] |
| Within-site rho, exposure, all sites | 0.3139 | 0.3141 | +0.0002 |
| LOYO within-site rho, rain + risk + season | 0.423 | 0.423 | 0.000 |
| Within-site rho, lakes (reported only) | 0.2636 | 0.2650 | +0.0014 |

Against the conditions:
1. Brier: the upper ends are +0.0000115 (LOYO), +0.0000007 (LOSO) and −0.0000007 (forward), all under +0.0005.
   **Holds.**
2. AUC: the lower ends are −0.00011 (all sites) and −0.00018 (rivers), both above −0.005. **Holds.**
3. Cross-site rho: the lower end is 0.0000, above −0.05. **Holds.**
4. Within-site rho: +0.0002 and 0.000, both above −0.01. **Holds.**
5. Lakes: the upper end of the lake Brier change is +0.0000005, under +0.0005. **Holds.**

The LOYO Brier score is worse by 0.0000064, and its interval excludes zero. The worsening is on rivers, whose
exposures do not change. The model is refitted on all sites together, so a change at the lake sites moves its shared
coefficients, and with them the river predictions. The change is 1/80th of the margin.

### Condition 6: placebos. Holds.

As stated, each run's own figures from `summary.py`, rounded:

| measure | `water` | `line` | 20 placebos: lowest, median, highest | at least as bad as `water` | at least as good |
|---|---|---|---|---|---|
| LOYO Brier | 0.0938 | 0.0938 | 0.0938, 0.0938, 0.0938 | 20 | 20 |
| LOYO AUC | 0.8129 | 0.8129 | 0.8126, 0.8129, 0.8131 | 13 | 15 |
| LOYO AUC, rivers | 0.7470 | 0.7470 | 0.7469, 0.7470, 0.7471 | 13 | 17 |
| Cross-site rho | 0.76250 | 0.76169 | 0.76089, 0.76169, 0.77218 | 16 | 7 |

The same counts unrounded, from each run's held-out predictions (reported, not the rule):

| measure | `water` | placebos at least as bad | at least as good |
|---|---|---|---|
| LOYO Brier | 0.0938117 | 4 | 16 |
| LOYO AUC | 0.8129041 | 8 | 12 |
| LOYO AUC, rivers | 0.7469646 | 3 | 17 |
| Cross-site rho | 0.7625000 | 16 | 7 |

The rounded rule holds on all four, and the unrounded counts give the same answer: at least one placebo is as bad on
each. On the Brier score and the river AUC, most placebos do a little better than `water`, by amounts far inside the
margins. The samples cannot tell the real detours from the same detours given to other overflows.

### Condition 7: face check. Holds.

`tests/test_lake_distance.py`: 7 passed.

### The sites that move, for the record

LOYO, `line` → `water`:

| site | samples | over 900 | mean LOYO prediction | LOYO Brier | within-site rho | mean exposure | rank of 31 |
|---|---|---|---|---|---|---|---|
| Rutland Water Whitwell Creek | 52 | 0 | 0.0238 → 0.0233 | 0.00063 → 0.00061 | 0.046 → 0.067 | 0.00065 → 0.00051 | 29 → 30 |
| Rutland Water Sykes Lane | 48 | 0 | 0.0233 → 0.0232 | 0.000615 → 0.000613 | 0.144 → 0.143 | 0.00043 → 0.00041 | 31 → 31 |
| Windermere, Lakeside YMCA | 57 | 0 | 0.0218 → 0.0217 | 0.000544 → 0.000542 | 0.337 → 0.334 | 0.00185 → 0.00178 | 28 → 28 |
| Windermere, Fellfoot | 59 | 0 | 0.0199 → 0.0199 | 0.000454 → 0.000454 | 0.123 → 0.123 | 0.00063 → 0.00061 | 30 → 29 |
| Windermere, Millerground Landing | 59 | 0 | 0.0272 → 0.0272 | 0.000868 → 0.000872 | 0.493 → 0.493 | 0.00801 → 0.00799 | 23 → 23 |
| Windermere, Rayrigg Meadow | 57 | 0 | 0.0284 → 0.0284 | 0.000939 → 0.000944 | 0.212 → 0.212 | 0.00862 → 0.00861 | 22 → 22 |
| Coniston Water, Monk Coniston | 57 | 1 | 0.0331 → 0.0332 | 0.01785 → 0.01785 | 0.580 → 0.580 | 0.01845 → 0.01829 | 17 → 17 |
| Coniston Water, Brown Howe | 57 | 1 | 0.0267 → 0.0268 | 0.01801 → 0.01801 | 0.664 → 0.664 | 0.00737 → 0.00736 | 24 → 24 |
| Coniston Water, Boating Centre | 57 | 2 | 0.0378 → 0.0380 | 0.03216 → 0.03216 | 0.379 → 0.379 | 0.03039 → 0.03039 | 14 → 14 |
| Derwent Water at Crow Park | 58 | 12 | 0.0346 → 0.0347 | 0.19728 → 0.19725 | 0.021 → 0.021 | 0.01568 → 0.01567 | 20 → 20 |

The cross-site change is one swap at the bottom of the ranking: Rutland Water Whitwell Creek and Fellfoot change
places at 29th and 30th. That is the reverse of the swap the residence tests made.

### Spots whose weights change

From `report.py` on the frozen data, as listed under "Seen before writing":
- **Site spots:** 30 placed in a lake, 19 with overflows upstream. The weights change at 17. At 8 the sum of weights
  changes by 1% or more, most at Rutland Water Whitwell Creek (−31%) and Pooley Bridge (−21%).
- **Pooley Bridge:** Glenridding WwTW is 10,906 m by the straight line and 11,453 m through the water. Its weight
  goes from 0.000375 to 0.000297.
- **Evaluation bathing waters:** 16 placed in a lake, 11 with overflows upstream, 10 that change.

### Click-anywhere

Written while the runs were going, in ff92c5d; the E. coli chain does not import it.
- In lake distance `water`, `lakes.json` carries each lake's water: its reflex corners, its outline widened by 10 m,
  and its shore. Each inlet carries where it enters the water and the metres on to every corner.
- `anypoint.js` `waterWay` gives a click the API's way. In lake distance `line` the files carry none of this, and
  nothing changes.
- `tests/test_anypoint_water.py` and its page fixture: an L-shaped lake, with clicks in both arms, round the corner,
  on the shore beyond the end and off the arm by its centreline. The page matches the API within 3 m.
- On real lakes, against `lake_water.water_distance`: Ullswater, Windermere, Rutland Water and Coniston Water,
  1,440 random click and inlet pairs, 983 of them round a bend. Largest difference 1.4 m (0.12%).
- Not done: a full click-anywhere build on the real network in `water` mode. Its lake files are new data the
  site's next build writes.

### What this shows

Established:
- `water` does no harm to any held-out score beyond changes of a few millionths.
- None of the six Rutland and Windermere sites had a sample over 900 cfu/100 ml. So the lake Brier gain there is
  arithmetic, not evidence, as stated beforehand.
- The placebos score about the same as `water`. The samples cannot tell whether the detours are right.

Inferred, not tested:
- The path through the water is closer to where water can go than a line over land. That, not the samples, is the
  case for switching.
- The rule still moves water at one fixed speed along the shortest path. Wind, which decides where river water goes
  in a lake, is not modelled (handoff section 4D).
- Pooley Bridge and Glenridding have no Environment Agency samples, so the change the outside reviewer asked about is
  not tested by data.
