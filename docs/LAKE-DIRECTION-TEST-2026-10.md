# Which way across a lake: the test, stated before any run

Written 23 October 2026. Nothing in this test has been run through the E. coli evaluation. Results go below the
line at the end. Nothing above it changes after a result is seen.

## Why

A review of the live site before a call with a Lake District water-quality group, 23 October 2026.
- At a lake spot, an overflow whose water enters the spot's own lake counts whichever way the water must go to reach
  the spot (`transport.upstream_overflows`, lake branch). Only the distance through the water and the area cut apply.
- So Glebe Road PS, which enters Windermere at Bowness, counts at Waterhead, 7.1 km up the lake from it, at a weight
  of 0.10, and is listed there as "upstream". Windermere drains south, out of the south basin at Newby Bridge.
- Between lakes the model already follows the flow: water entering the south basin never counts in the north basin.
  Within one lake it does not.
- Ethan's decision, 23 October 2026: build a direction rule for overflows down the lake, with the test written first.

## The variant

`DIPCAST_LAKE_DIRECTION_MODE=down` (`config.LAKE_DIRECTION_MODE`), off. The default, `any`, is the rule now.

**The rule** (`transport.down_lake_m`, `transport.lake_outlet_xy`):
- **The outlet:** where water leaves the spot's lake, `transport._lake_outlet` of the spot's lake links (the node with
  the most network upstream among those that leave the lake). Checked on the map before writing: for Waterhead it is
  the north basin's outlet at the narrows south of Bowness (54.338 N, 2.944 W), since in the river network the two
  basins are two lakes; Lakeside YMCA's is Newby Bridge, Monk Coniston's the foot of Coniston Water, Glenridding's
  Pooley Bridge.
- **Down the lake:** for each overflow, the spot's distance to the outlet less the entry point's, each the shortest
  path through the lake's water (`lake_water.water_distance`, as the lake distance has used since 16 October), or the
  straight line where the lake has no WFD polygon or no path is found.
- **Left out:** an overflow whose entry is more than `LAKE_DOWN_MARGIN_M` = 1,000 m nearer the outlet than the spot.
  It is dropped from the spot's list, as an overflow on another branch is: it is not upstream.
- **Kept, unchanged:** every other overflow, with the same distance, travel time, die-off, dilution and weight.
- **Nothing else changes:** river spots, lakes crossed on the way (`residence_spill`), the lake distance (`water`),
  the 60 km cap.

**The margin, and when it was set.** It was first written as 250 m, a tolerance for shoreline geometry only. The
transport-only report below then showed that 250 m would drop overflows entering 280 to 460 m from the spot at three
small waters: Churt SPS at Frensham Great Pond (284 m), Glenridding WwTW at Glenridding (303 m) and Elterwater PS at
Elter Water (455 m). Near where it enters, a spill spreads in every direction by wind and mixing before any
through-flow carries it away. So the margin was set at 1,000 m. That is a judgement, not a fitted figure. It was set
before any rain, spill model or E. coli figure was computed for this test.

**Wind, stated now.** The lake group's own point is that in a lake the wind decides where river water goes. This rule
does not use the wind either. It assumes the through-flow carries a spill towards the outlet, and that beyond 1 km
up the lake nothing carries it back.
- Windermere and Coniston Water run roughly north to south and drain south. The commonest winds in the Lake District
  come from the south-west and west (inferred from general UK climate, not checked against a station here). A
  south-westerly pushes surface water north-east: up these lakes. So the rule removes a pathway that the commonest
  wind can create. It may be wrong on exactly the days a swimmer at the head of a lake would care about.
- The rule `any` it replaces is not right either: it carries every spill up the lake on every day, at a fixed drift,
  whatever the wind.
- Neither is measured. The test can show only whether the samples are hurt.

## Seen before writing

Transport only, on the frozen data below, with `scripts/lake_direction_eval/report.py`. No rain, spill model or
E. coli figure was computed or looked at.

**Site spots.** 19 of the site's lake spots have overflows upstream. At 1,000 m, 5 lose an overflow and 1 loses all:

| spot | overflow left out | metres down the lake | weight under `any` | sum of weights, `any` → `down` |
|---|---|---|---|---|
| Windermere, Waterhead | Glebe Road PS | 6,867 | 0.101 | 0.377 → 0.276 |
| Windermere, Millerground Landing | Glebe Road PS | 2,571 | 0.227 | 0.344 → 0.117 |
| Windermere, Rayrigg Meadow | Glebe Road PS | 2,298 | 0.238 | 0.351 → 0.113 |
| Coniston Water, Boating Centre | Torver WwTW | 4,948 | 0.050 | 0.260 → 0.210 |
| Coniston Water, Monk Coniston | Coniston WwTW | 1,132 | 0.170 | 0.212 → 0 |
| | Torver WwTW | 5,997 | 0.042 | |

- Unchanged: Grasmere, Rydal Water, Lakeside YMCA, Fellfoot, Brown Howe, Crow Park, Calfclose Bay, Elter Water,
  Glenridding, Pooley Bridge, near Sandwick, both Rutland Water sites, Frensham Great Pond.
- Monk Coniston would read "No monitored overflow found upstream". Coniston WwTW enters 1.25 km from it through the
  water, 1.13 km nearer the outlet.

**Evaluation bathing waters.** 11 are placed in a lake with overflows upstream, with 24 rows (pin and entry point).
The same 4 change: Millerground Landing, Rayrigg Meadow, Coniston Boating Centre and Monk Coniston, 5 rows.

**Also seen:** the results of the three lake tests before (`docs/LAKE-PATH-TEST-2026-10.md`,
`docs/LAKE-RESIDENCE-SPILL-2026-10.md`, `docs/LAKE-DISTANCE-2026-10.md`) and of `docs/DIEOFF-WEATHER-TEST-2026-10.md`
(#303), whose frozen data folder this test reuses.

## The evaluation

As in `docs/LAKE-DISTANCE-2026-10.md`, with the lake direction in place of the lake distance.

**Harness:** `scripts/lake_direction_eval/`, in this commit.
- `run_variant.sh` and `queue.sh` are the distance harness's with the lake direction option; lake path and lake
  distance stay at their defaults (`residence_spill`, `water`).
- `paired.py` and `summary.py` are used unchanged from `scripts/lake_residence_eval/`.
- `judge.py` is the distance harness's with the runs renamed, 10 placebos and this test's face check.
- `run_offline.py` adds the placebo swap below.

**Inputs:** a copy, made 23 October 2026, of the frozen folder `docs/DIEOFF-WEATHER-TEST-2026-10.md` ran on:
overflow table `ebc96774` (built 22 October on network `b5724303`), `river_network.pkl` `fc66101d`,
`bwq_samples.parquet` `26f5f646`, 3,658 rain files. `lake_residence_spill.csv`, `lake_residence.csv` and
`network_fixes.csv` are byte-identical to main bfe47f2's. Spots and pins come from this checkout.

**Runs**, one at a time, offline, from an archive of the commit that adds this file:
- `any`: the default, run again;
- `down`: lake direction `down`;
- `ph01` to `ph10`: placebos.

**The placebos.** `make_placebos.py` takes the 24 evaluation rows and the candidate's flags (5 left out). Placebo k
permutes the flags across the 24 rows with numpy `default_rng(k)`: as many rows left out, at other lakes or other
overflows. In a placebo run, `run_offline.py` replaces `down_lake_m` with the placebo's flags. A row the file does not
hold keeps the rule's own value and is counted; the count must be 0.

There are 10 placebos, not the 20 of the earlier tests, so the runs finish before the call on 24 October. With 10,
condition 6 is easier to pass by chance. That is a weaker guard, stated now.

**Samples that leave.** A site that loses every overflow leaves the scored set, as every site with none does. Under
`down` that is Monk Coniston. The comparison is paired on the samples both runs keep (`paired.py`), and the samples
that leave are reported.

**Check:** `any` should give `train_ecoli`'s figures of the die-off test's reference arm on the same folder: 1,502
samples, LOYO Brier 0.0921. If it differs, I report by how much and why, and the test goes on.

## What counts as passing

The seven conditions of the lake tests, with `any` as the reference and `down` as the candidate. `judge.py` applies
them.
1. **Brier:** LOYO, LOSO and forward; the upper end of the interval of the change is at most +0.0005.
2. **AUC:** all sites and rivers (LOYO); the lower end is at least −0.005.
3. **Cross-site rho:** the lower end is at least −0.05.
4. **Within-site rho:** both point changes are at least −0.01.
5. **Lakes:** the upper end of the lake LOYO Brier change is at most +0.0005.
6. **Placebos:** on each of LOYO Brier, LOYO AUC, LOYO AUC rivers and cross-site rho, at least one of the 10 placebos
   is at least as bad as `down` (`summary.py`'s rounded figures; unrounded counts reported beside them).
7. **Face check:** `tests/test_lake_direction.py` passes: the default is `any`; water entering down the lake beyond
   the margin is left out and what is kept is unchanged; the metres go through the water; an entry inside the margin
   still counts; a spot at the outlet loses nothing.

Every run must make 0 network attempts, and every placebo run 0 placebo misses.

**What is expected, stated now.**
- In the earlier lake tests no Windermere site had a sample over 900. At a site with no exceedance a lower prediction
  always lowers the Brier score, so a Brier gain there is arithmetic, not evidence.
- Monk Coniston leaving the scored set changes the cross-site rho's set of sites. That is reported with it.
- The changes in the scores should be small.

**What follows:**
- **All seven hold:** `down` becomes the default in a final commit of this PR, after click-anywhere follows it
  (`scripts/build_any_point.py`, `site/anypoint.js` and their consistency test), and the Method page says so. If
  click-anywhere cannot follow it in this PR, the default stays `any` and the PR says why.
- **Any fails:** the default stays `any`. The PR is a record, with `down` as an option.

If the option, the placebo files or the harness change after a result is seen, both results are kept and the change
is stated.

## What will be reported

Whatever the verdict:
- the seven conditions, the placebo counts rounded and unrounded, and the network and placebo-miss counts;
- the record table for the lake bathing waters: samples, samples over 900, mean LOYO prediction, LOYO Brier,
  within-site rho, mean exposure and its rank;
- the samples that leave the scored set;
- the lake spots whose weights change, as above.

---

## Results

Not yet run.
