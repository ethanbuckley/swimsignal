# Lakes on the way: the test, stated before any result

Written 11 October 2026, before any E. coli score was computed with this option. The option is in
commit 43bd2fd. Before writing this I looked at transport weights only (no rainfall, spill model or
E. coli), and at one published aggregate, named under "Seen before writing".

## Why

A Lake District water-quality group wrote on 11 October 2026 that the model does not treat lakes as
lakes. Their example: a typical spill into Grasmere has dissipated by the time the water flows out of
Rydal Water, so it does not reach water further down.

What the model does today (main ebdc94a, `transport.upstream_overflows`):
- Travel time is `d_river / v_river + d_lake / v_lake`. Only the spot's own lake counts as `d_lake`.
- A lake between the overflow and the spot is walked as river: at river speed (0.5 m/s), with no
  lake dilution.
- The lake factor `1 / (1 + A / LAKE_A0_KM2)` applies only to the spot's own lake.

So Rydal Water gets Grasmere WwTW at weight 0.068, against 0.104 at Grasmere itself, though the water
first crosses 1.1 km of Grasmere.

## The option

`DIPCAST_LAKE_PATH_MODE=lake` (`config.LAKE_PATH_MODE`). Off by default: `river` is the rule in use.

For each upstream overflow, every WFD lake its water crosses before it reaches the spot (or the spot's
own lake) is treated as the spot's own lake is treated:
- **Time.** The lake's centreline length on the path moves at `LAKE_VELOCITY_MS` (0.05 m/s) instead of
  river speed. With velocity `catchment`, those links' reach-speed seconds are taken out and the same
  lake time is added. A gauge's level index still scales the river part only.
- **Dilution.** Divided by `1 + A / LAKE_A0_KM2` once for each lake crossed, with A the lake's WFD area
  and `LAKE_A0_KM2` = 5 km². This comes after the dilution mode (`length`, `flow` or `urban`) and the
  spot's own lake factor. The low-snap factor comes after it, as before.
- **Distance.** The lake's length moves from `distance_m` to `lake_distance_m`. Their sum, the distance
  along the network, is unchanged. The 60 km cap applies to the same distance as before, so the same
  overflows are traced in both modes.
- An overflow on a lake link crosses the part of that link below it.
- No new constant.

**Which links count as a lake.** A lake-form link (OS Open Rivers `form = lake`) counts only when some
of its length lies inside a WFD lake polygon (`data/processed/lakes.parquet`, 564 polygons). It goes to
the polygon that holds most of its length. The spot's own lake links are left out. Every other
lake-form link stays river, as today.

Why WFD polygons only, not every lake-form link:
1. The lake factor needs an area. Only the WFD polygons give one. A lake-form link outside them could
   be slowed, but it could not get the factor, so it would not be treated as the spot's own lake is.
2. The spot's own lake is found the same way: `_locate` takes the WFD polygon and its area.
3. Outside the polygons, the lake-form links on these paths are short: mill ponds, weir pools and
   channel widenings. For Windermere's south basin there are 23 of them on the traced network, 2.9 km
   in all. Slowing 100 m of weir pool to 0.05 m/s would add 33 minutes. Nothing says such a pond holds
   water back the way a lake does.
4. The WFD set includes small lakes in protected areas (down to 5 ha), for example Priest Pot and Three
   Dubs Tarn. For these the factor is close to 1 and the extra time is short.

Fourteen of the 564 polygons are not valid geometries (nested shells), and GEOS refuses to intersect
them. They are repaired with `shapely.make_valid` before the overlap is measured. The file itself is
not changed.

## Seen before writing

Transport only, from `scripts/lake_path_report.py` and checks in this session. The overflow table and
network are the main checkout's. Live spots are placed from https://swimsignal.co.uk/data/spots-lite.json
(11 October 2026) as the site build places them.

- **Default unchanged.** `upstream_overflows` with `river` gives output identical to main's
  `transport.py` (`DataFrame.equals`) at 143 places: 105 live spots and 38 evaluation bathing waters,
  in all six velocity x dilution pairs. That is 858 traces and 15,942 overflow rows.
- **Live spots.** 20 of 105 change. The sum of transport weights falls by:
  - 41.5% at Rydal Water (0.0680 to 0.0398): Grasmere WwTW's water crosses Grasmere (0.60 km²);
  - 19.5% at Windermere Lakeside YMCA and 19.4% at Fellfoot. Their overflows cross the north basin
    (8.67 km²), Esthwaite Water, Elter Water, Grasmere or Rydal Water;
  - 5.5% at Waterhead;
  - 2.0 to 2.7% at three Thames spots near Oxford: Woodstock and Middle Barton STWs cross Blenheim Lakes
    (0.56 km²) on the Glyme;
  - under 1% at the other 13.
- **Evaluation set.** 38 inland bathing waters, 32 with upstream overflows. 8 change:
  - Lakeside YMCA (0.0346 to 0.0278) and Fellfoot (0.0107 to 0.0086);
  - Wolvercote Mill Stream, -2.6% (Blenheim Lakes);
  - the other five by under 1%: Millerground, Rayrigg Meadow, Ham and Kingston, Colwick, Wallingford.
- **Measured at Lakeside YMCA.** 22.8% of its transport weight comes from overflows whose water crosses
  a WFD lake: 13.0% through the north basin and 9.8% through Esthwaite Water. Ambleside WwTW's water
  crosses 6.45 km of the north basin to reach it.
- **One published aggregate.** The committed `ecoli_validation.json` (September 2026) gives 2.0% of
  samples over 900 cfu/100 ml across the 12 lake bathing waters. No per-site figure was looked at.

So the evaluation has little power for this option. Two sites move by a fifth, one by 2.6%, and the
rest barely. The test below can show that the option does no harm. It cannot show that it helps.

## The evaluation

The chain of PR #166 and the urban test, unchanged: `validate_ecoli.py`, `replay_ecoli_leads.py`,
`validate_ecoli_combined.py`, `train_ecoli.py`.
- Run by `scripts/lake_path_eval/run_variant.sh`. It is PR #172's `run_variant.sh` with the lake path
  option set in place of the dilution option. It uses PR #172's `run_offline.py` and `paired.py`
  (`scripts/urban_diagnosis/`, commit e33eb73), unchanged.
- Two fresh runs on the same inputs: default (`river`) and `lake`. Velocity `fixed` and dilution
  `length`, the production defaults.
- Each run in its own scratch DIPCAST_ROOT. Rain from the cache only. Every outgoing network
  connection refused. One run at a time.
- Check: the fresh default run should reproduce #166's default figures (LOYO Brier 0.0909, cross-site
  rho 0.685). If it does not, the two fresh runs are still compared, and the difference is stated.

Measures, `lake` against default. Paired intervals are 95%, from 2,000 resamples with seed 1.
- Held-out Brier of the full model, in LOYO, LOSO and forward (2025-26). Paired site-week bootstrap
  (`train_ecoli.cluster_bootstrap`, via `paired.py compare`).
- LOYO AUC of the full model, all sites and rivers. Same bootstrap.
- Cross-site rho: Spearman correlation of site-mean exposure with site-mean log E. coli. Paired site
  bootstrap.
- Within-site rho of exposure against log E. coli (not held out, `ecoli_validation.json`), and the LOYO
  within-site rho of rain + risk + season (`ecoli_validation_combined.json`). Point estimates.

**The affected-site look.** For each evaluation site whose weight sum changes by more than 1%
(Lakeside YMCA, Fellfoot, Wolvercote Mill Stream), and for the two south-basin sites pooled, in each
variant:
- samples, and the share over 900 cfu/100 ml;
- the mean LOYO prediction and the LOYO Brier;
- the within-site rho of exposure against log E. coli;
- the site's rank by mean exposure among the 32.

`scripts/lake_path_eval/judge.py` computes all of it and applies the rule below.

## What counts as passing

Non-inferiority on the full set. All four must hold:

1. **Brier.** In LOYO, LOSO and forward, the upper end of the paired interval of the change
   (`lake` minus default) is at most +0.0005. That is about a fifth of the full model's LOYO gain over
   rain alone in #166's fresh run (0.0026).
2. **AUC.** For LOYO, over all sites and over rivers, the lower end of the paired interval of the
   change is at least -0.005. That is about a third of the loss that failed `urban` (-0.013).
3. **Cross-site rho.** The lower end of the paired interval of the change is at least -0.05. That is
   about a sixth of the loss that failed `urban` (-0.29).
4. **Within-site rho.** Both point changes are at least -0.01.

And one check at the sites that move:

5. The pooled LOYO Brier at Lakeside YMCA and Fellfoot is not higher with `lake` (point estimate).

What follows:
- **1 to 5 hold:** recommend `lake` as a candidate to switch on. The switch is Ethan's decision. The case
  for it is physical: the data can only show that it does no harm.
- **1 to 4 hold and 5 fails:** needs more. Keep it off. The two south-basin sites are the only
  evaluation sites with a large change; sampling elsewhere on Windermere would be the next test.
- **Any of 1 to 4 fails:** keep it off.

If the option is changed after the results are seen, both results are kept and the change is stated.

## What this test cannot show

- Rydal Water and Waterhead, the places the note is about, are not designated bathing waters. There
  are no Environment Agency samples there, so their change is not tested at all.
- Both south-basin sites have small weights in both variants (sums under 0.035). The E. coli model
  clips exposure at 0.001 before its logit (`ecoli.features`). *Inferred, not checked:* on many days
  at Fellfoot the exposure is under that floor in both variants, so the change cannot show there.
- The lake factor and lake speed are the ones already used for the spot's own lake. They were not
  fitted to anything, and this test does not fit them.

## Results (added 11 October 2026, after the runs; everything above is unchanged)

The pre-statement above was committed in 5fbd5ac (11 October 2026, 19:24 BST) and pushed before the
first run started (19:25 BST). The option was not changed after the results.

**Verdict: all five conditions hold. By the rule above, `lake` is a candidate to switch on.** The
switch is Ethan's decision. The data show it does no harm; they cannot show it helps (see below).

The runs:
- Two fresh runs on the same inputs, 1,546 model samples each, in the same order.
- 0 network attempts in all 10 script runs.
- The fresh default run reproduces #166's default figures to four decimal places (LOYO Brier 0.0909,
  LOYO AUC 0.8151, cross-site rho 0.685).
- Peak memory 3.9 GB (`replay_ecoli_leads.py` in the `lake` run).

Paired intervals are 95%, from 2,000 resamples. The Brier and AUC intervals resample site-weeks
(1,369 clusters; 923 in the forward test). The cross-site interval resamples the 32 sites.

| measure | default (`river`) | `lake` | change [95% CI] |
|---|---|---|---|
| LOYO Brier, full model | 0.09094 | 0.09091 | -0.00003 [-0.00005, -0.00001] |
| LOYO Brier, rivers | 0.13748 | 0.13743 | -0.00005 [-0.00009, -0.00002] |
| LOSO Brier, full model | 0.09044 | 0.09043 | -0.00002 [-0.00004, +0.00000] |
| Forward (2025-26) Brier | 0.08275 | 0.08273 | -0.00003 [-0.00006, -0.00000] |
| LOYO AUC, full model | 0.8151 | 0.8154 | +0.0002 [+0.0001, +0.0004] |
| LOYO AUC, rivers | 0.7492 | 0.7494 | +0.0003 [+0.0000, +0.0005] |
| LOSO AUC, full model | 0.8077 | 0.8078 | +0.0001 [-0.0001, +0.0004] |
| Forward AUC | 0.8097 | 0.8100 | +0.0003 [-0.0001, +0.0009] |
| Cross-site rho (site-mean exposure vs log E. coli) | 0.685 | 0.685 | 0.000 [0.000, 0.000] |
| Within-site rho, exposure vs log E. coli (not held out) | 0.2885 | 0.2884 | -0.0001 |
| LOYO within-site rho, rain + risk + season | 0.387 | 0.388 | +0.001 |
| Pooled rho, exposure vs log E. coli (not held out) | 0.552 | 0.557 | +0.005 |

Against the conditions:
1. Brier: the upper ends of the change are -0.00001 (LOYO), +0.000005 (LOSO) and -0.000004 (forward),
   all under +0.0005. **Holds.**
2. AUC: the lower ends are +0.0001 (all sites) and +0.00001 (rivers), both above -0.005. **Holds.**
3. Cross-site rho: no site changes rank, so the change is 0 in every resample. **Holds.**
4. Within-site rho: -0.0001 and +0.001, both above -0.01. **Holds.**
5. South basin pooled LOYO Brier: 0.00038 to 0.00034. **Holds.**

The affected-site look, LOYO, default to `lake`:

| site | model samples | share over 900 | mean LOYO prediction | LOYO Brier | within-site rho | exposure rank (of 32) |
|---|---|---|---|---|---|---|
| Windermere, Lakeside YMCA | 57 | 0 | 0.0192 to 0.0182 | 0.00043 to 0.00038 | 0.337 to 0.342 | 29 to 29 |
| Windermere, Fellfoot | 59 | 0 | 0.0170 to 0.0164 | 0.00033 to 0.00030 | 0.120 to 0.129 | 30 to 30 |
| Wolvercote Mill Stream | 55 | 0.036 | 0.162 to 0.161 | 0.0577 to 0.0571 | 0.173 to 0.173 | 21 to 21 |
| South basin pooled | 116 | 0 | 0.0181 to 0.0173 | 0.00038 to 0.00034 | | |

(The within-site rho column uses all of each site's rows with every input: 77, 79 and 75.)

What this shows, and what it does not:
- *Established:* every full-set change is tiny. The largest Brier change is 0.00005, a fiftieth of
  the full model's gain over rain alone. The direction is the same on every held-out measure: slightly
  better.
- *Established:* neither south-basin site had a sample over 900 cfu/100 ml in the model set (0 of 116).
  At a site with no exceedance, the Brier score is the mean of the squared predictions, so any lower
  prediction gives a lower Brier. Condition 5 therefore holds by arithmetic once exposure falls. It is
  consistent with the option, but it is not evidence for it.
- *Established:* the two south-basin sites were already 29th and 30th of 32 by exposure, and stay
  there. So the cross-site ranking cannot move.
- *Inferred, not tested:* the evaluation set cannot test the case the note was about. Rydal Water and
  Waterhead have no Environment Agency samples. Samples below Grasmere and Rydal Water would be the
  test.
- *Inferred, not tested:* for a small lake the existing constants do little dilution. Grasmere
  (0.60 km²) divides the weight by only 1.12. Most of Rydal Water's 41.5% drop comes from the slower
  crossing (5.5 more hours of die-off). Whether that matches the observation that a Grasmere spill has
  dissipated below Rydal Water is not known.
