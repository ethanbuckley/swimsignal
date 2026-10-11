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
