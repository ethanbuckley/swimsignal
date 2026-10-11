# The near field of a lake: the test, stated before any result

Written 12 October 2026, before any E. coli score was computed with this option. The option is in the
commit just before this one on branch `claude/lake-near-field`, rebased onto main 7d1924a. Before
writing this I looked at transport weights only (no rainfall, spill model or E. coli), and at earlier
published results, named under "Seen before writing".

## Why

A site review on 11 October 2026 (the 20:17 build) found that on 16 of the 19 lake spots with
overflows, the index can never rise above Low (0.15), even with every overflow discharging. The cause:
- A lake spot's dilution is the length ratio `(L_ov + L0) / (L_spot + L0)`, and its spot length is the
  network above the lake's outlet, so the whole lake's catchment.
- The lake-area term `1 / (1 + A / 5 km²)` then divides that.

Coniston Boating Centre's page showed Coniston WwTW 0.2 km away, spilling with a 45% chance that day,
but the spot's highest possible index was 0.09.

Physically, an inflow's plume near where it enters a lake is diluted by the inflow's own river, not
yet by the whole lake. It mixes into the lake with distance.

## The option

`DIPCAST_LAKE_NEAR_MODE=blend` (`config.LAKE_NEAR_MODE`). Off by default until this test passes.

For a lake spot, each overflow's dilution blends from its near value to today's lake value with the
straight-line distance d across the spot's lake, from where its water enters to the spot:

    dilution = near × f + lake × (1 - f),   f = exp(-d / LAKE_NEAR_M),   LAKE_NEAR_M = 1 km

- **lake:** today's dilution: the length ratio to the lake's outlet, divided by `1 + A / 5 km²` (no
  area term for a lake known only from its centreline).
- **near:** the inflow's own river dilution at its mouth. It is the same length ratio, with the spot
  length taken as the network of that inflow alone: the links into the entry node from outside the
  lake (`transport._inflow_length`). The water the lake's centreline brings to the same node from
  further up the lake is not the inflow's.
  - For an outfall on the lake itself, near is 1.
  - With dilution `flow` or `urban`, the same rule uses the inflow's network for the spot's flow.
- A WFD lake crossed before the spot's lake (lake path `lake`, #176) still multiplies the result by its
  factor.
- Distance, travel time and die-off do not change.
- River spots do not change.
- Click-anywhere follows the same rule:
  - `build_any_point` publishes each inlet's own dilution (`n`) and `near_m` in `lakes.json`;
  - `anypoint.js` blends in the same way;
  - the consistency test passes under this rule as well.

**Why 1 km.**
- Nekouee (2010, NOAA Technical Memorandum GLERL-151, summary) studied the Grand River plume in Lake
  Michigan and found bacterial reductions due to dilution "generally small (less than 10:1) up to
  4.5 km from the river mouth".
- For an exponential blend, that is an e-folding distance of at least 4.5 km / ln 10, about 2 km, for
  a large river.
- The same report separates a near field, where mixing is driven by the inflow's own momentum and
  buoyancy, from a far field, driven by the lake's turbulence.
- Inflows to English lakes are far smaller than the Grand River, so their near field ends sooner.
  1 km, half the large-river bound, is a judgment from that literature. It was fixed before any run
  and is not fitted to our samples.

## Seen before writing

Transport only, from `scripts/lake_near_report.py`. The setup:
- the current overflow table, from the state release's live snapshot (11 October 2026, 18:21 UTC), as
  in the outfall-channel test;
- live spots from spots-lite.json (11 October 2026, 20:17), placed as the site build places them.

The ceiling is the index with every upstream overflow discharging, `1 - prod(1 - w)`.

| lake spot | overflows | ceiling now | ceiling with `blend` | the overflow that moves most |
|---|---|---|---|---|
| Coniston Water, Boating Centre | 2 | 0.089 Low | 0.803 Very high | Coniston WwTW, 84 m across |
| Grasmere | 1 | 0.104 Low | 0.688 High | Grasmere WwTW, 290 m |
| Elter Water | 1 | 0.397 Moderate | 0.605 High | Elterwater PS, 479 m |
| Ullswater, Glenridding | 1 | 0.034 Low | 0.561 High | Glenridding WwTW, 354 m |
| Frensham Great Pond | 1 | 0.483 High | 0.522 High | Churt SPS, 495 m |
| Windermere, Waterhead | 4 | 0.139 Low | 0.384 Moderate | Ambleside WwTW, 434 m |
| Derwent Water, Calfclose Bay | 3 | 0.176 Moderate | 0.199 Moderate | Grange Bridge, 2.5 km |
| Coniston Water, Monk Coniston | 2 | 0.055 Low | 0.194 Moderate | Coniston WwTW, 1.2 km |
| Windermere, Rayrigg Meadow | 4 | 0.144 Low | 0.169 Moderate | Glebe Road PS, 2.3 km |
| Windermere, Millerground Landing | 4 | 0.132 Low | 0.148 Low | Glebe Road PS, 2.6 km |
| Derwent Water at Crow Park | 3 | 0.120 Low | 0.126 Low | Grange Bridge, 3.5 km |
| Coniston Water, Brown Howe | 2 | 0.027 Low | 0.063 Low | Torver WwTW, 1.1 km |
| Rydal Water | 1 | 0.040 Low | 0.042 Low | Grasmere WwTW, across Grasmere and 0.9 km of Rydal Water |
| Windermere, Lakeside YMCA | 6 | 0.028 Low | 0.031 Low | Glebe Road PS, 6.7 km |
| Rutland Water, Whitwell Creek | 5 | 0.021 Low | 0.024 Low | Oakham STW, 4.4 km |
| Rutland Water, Sykes Lane | 5 | 0.013 Low | 0.013 Low | Oakham STW, 5.6 km |
| Ullswater, near Sandwick | 1 | 0.008 Low | 0.012 Low | Glenridding WwTW, 3.8 km |
| Windermere, Fellfoot | 6 | 0.009 Low | 0.009 Low | Glebe Road PS, 9.4 km |
| Ullswater, Pooley Bridge | 1 | 0.000 Low | 0.000 Low | Glenridding WwTW, 10.9 km |

- Lake spots with overflows whose ceiling is under 0.15: 16 of 19 now, 10 with `blend`.
- The ones that stay are far from every overflow they have.
- The other 14 lake spots have no overflow upstream, and nothing changes there.
- Default (`off`) output is identical to main's `transport.py` at 143 places (105 live spots and
  38 evaluation bathing waters) in all six velocity × dilution pairs.

**The evaluation set.** Of its 12 lake bathing waters with overflows upstream:
- `blend` moves three a lot, all on Coniston Water. Ceilings:
  - Boating Centre: 0.089 → 0.80;
  - Monk Coniston: 0.055 → 0.19;
  - Brown Howe: 0.027 → 0.06.
- Three move a little: the two north-basin Windermere sites and Frensham.
- The rest barely move.
- River sites do not change.

**Already published, seen before writing:**
- `ecoli_validation.json` (September 2026) has about 16 exceedances of 900 cfu/100 ml among about 800
  lake samples (2.0%).
- The lake test found no exceedance at Windermere Lakeside YMCA and Fellfoot.
- The outfall-channel test's lake LOYO Brier was 0.0249 over 639 lake samples.

No per-site E. coli figure was looked at for the Coniston sites.

## What the data can and cannot test

- About 16 lake exceedances in all, and three sites that move much. So the data can show whether
  `blend` makes the held-out E. coli scores worse, on the full set and on lakes. They cannot show that
  it makes lake forecasts better.
- The sites the near field matters most for (Grasmere, Glenridding, Waterhead, Elter Water) have no
  Environment Agency samples.
- The face check below tests what the review asked for: a nearby spill can raise the level.

## The evaluation

The setup:
- The chain of #166 and the lake test, unchanged: `validate_ecoli.py`, `replay_ecoli_leads.py`,
  `validate_ecoli_combined.py`, `train_ecoli.py`.
- Run by `scripts/lake_near_eval/run_variant.sh`. It is the lake test's wrapper with this option, and
  uses PR #172's `run_offline.py` and `paired.py` (e33eb73) unchanged.
- Two fresh runs on the same inputs (the current overflow table, as above): base (`off`) and `blend`.
  Lake path is `lake`, velocity `fixed`, dilution `length`.
- Each run in its own scratch DIPCAST_ROOT. Rain from the cache only. Every outgoing network connection
  refused. One run at a time.

Measures, `blend` against base. Paired 95% intervals from 2,000 resamples with seed 1:
- LOYO, LOSO and forward Brier of the full model, from the site-week bootstrap.
- LOYO AUC over all sites and over rivers.
- LOYO Brier and AUC over lake samples.
- Cross-site rho, from a site bootstrap.
- Within-site rho of exposure against log E. coli (all sites and lakes), and the LOYO within-site rho
  of rain + risk + season.
- At the three Coniston sites: samples, exceedances, the mean LOYO prediction, the LOYO Brier and the
  within-site rho. These are for the record and are not a pass condition. With so few exceedances,
  one site's Brier mostly says whether it ever exceeded.

`scripts/lake_near_eval/judge.py` applies conditions 1-5. Condition 6 is `tests/test_lake_near.py`.

## What counts as passing

All six must hold:

1. **Brier:** in LOYO, LOSO and forward, the upper end of the interval of the change is at most +0.0005.
2. **AUC:** over all sites and over rivers (LOYO), the lower end of the interval of the change is at
   least -0.005.
3. **Cross-site rho:** the lower end of the interval of the change is at least -0.05.
4. **Within-site rho:** both point changes are at least -0.01.
5. **Lakes:** the upper end of the interval of the LOYO Brier change over lake samples is at most
   +0.0005.
6. **Face check:** with `blend`, an overflow 200 m from a lake spot, alone on a 300 m beck with nothing
   above it, reads High or above when it spills (`tests/test_lake_near.py`). The same overflow reads
   Low with `off`.

Conditions 1-4 and their margins are the lake test's. Condition 5 is the outfall-channel test's.

What follows:
- **All six hold:** `blend` becomes the default in this PR, as Ethan has asked for this change if it
  passes. Click-anywhere already follows it.
- **Any fails:** it stays off, and the failure is reported.

If the option or its constant is changed after the results are seen, both results are kept and the
change is stated.

## Results (added 12 October 2026, after the runs; everything above is unchanged)

The pre-statement above was committed in 01234e8 (12 October 2026, 00:07:18 BST) and pushed before the
first run started (00:07:34). The branch was rebased onto main 7d1924a before the pre-statement, so
the runs used the rebased code. Neither the option nor its constant was changed after the results.

**Verdict: `blend` fails condition 3, the cross-site ranking. By the rule above it stays off.**
Conditions 1, 2, 4, 5 and 6 hold.

The runs:
- Two fresh runs on the same 1,546 model samples.
- 0 network attempts in 10 script runs.
- Peak memory 4.0 GB.

Paired 95% intervals from 2,000 resamples. Brier and AUC resample site-weeks; the cross-site interval
resamples the 32 sites.

| measure | base (`off`) | `blend` | change [95% CI] |
|---|---|---|---|
| LOYO Brier | 0.09106 | 0.09106 | -0.00000 [-0.00022, +0.00021] |
| LOYO Brier, rivers | 0.13768 | 0.13778 | +0.00009 [-0.00023, +0.00043] |
| LOSO Brier | 0.09056 | 0.09039 | -0.00017 [-0.00037, +0.00001] |
| Forward (2025-26) Brier | 0.08291 | 0.08265 | -0.00026 [-0.00050, -0.00003] |
| LOYO AUC | 0.8145 | 0.8148 | +0.0003 [-0.0019, +0.0028] |
| LOYO AUC, rivers | 0.7478 | 0.7479 | +0.0000 [-0.0014, +0.0014] |
| LOYO Brier, lakes (639 samples, 16 over 900) | 0.02487 | 0.02474 | -0.00013 [-0.00041, +0.00009] |
| LOYO AUC, lakes | 0.472 | 0.454 | -0.018 [-0.054, +0.019] |
| Cross-site rho | 0.687 | 0.602 | -0.085 [-0.237, +0.006] |
| Within-site rho, exposure (not held out) | 0.2866 | 0.2987 | +0.012 |
| Within-site rho, lakes | 0.212 | 0.225 | +0.012 |
| LOYO within-site rho, rain + risk + season | 0.387 | 0.387 | 0.000 |
| Pooled rho, exposure (not held out) | 0.561 | 0.513 | -0.048 |

Against the conditions:
1. Brier: the upper ends are +0.00021 (LOYO), +0.00001 (LOSO) and -0.00003 (forward). **Holds.**
2. AUC: the lower ends are -0.0019 (all sites) and -0.0014 (rivers). **Holds.**
3. Cross-site rho: the lower end is -0.237, under -0.05. **Fails.**
4. Within-site rho: +0.012 and 0.000. **Holds.**
5. Lakes: the upper end of the LOYO Brier change is +0.00009. **Holds.**
6. Face check: `tests/test_lake_near.py` passes. The overflow 200 m off reads High with `blend` and Low
   with `off`. **Holds.**

The Coniston sites, LOYO, base → `blend` (for the record, not a condition):

| site | samples | over 900 | mean prediction | Brier | within-site rho | mean exposure |
|---|---|---|---|---|---|---|
| Boating Centre | 57 | 2 | 0.030 → 0.048 | 0.0327 → 0.0324 | 0.379 → 0.374 | 0.030 → 0.276 |
| Monk Coniston | 57 | 1 | 0.027 → 0.031 | 0.0175 → 0.0177 | 0.580 → 0.577 | 0.018 → 0.066 |
| Brown Howe | 57 | 1 | 0.022 → 0.022 | 0.0178 → 0.0178 | 0.664 → 0.645 | 0.007 → 0.016 |

**After the results, not pre-stated:** what drives the cross-site loss.
- Coniston Boating Centre goes from 15th to 1st of 32 sites by mean exposure. Its mean E. coli ranks
  20th.
- Without the three Coniston sites, the cross-site rho is 0.678 under base and 0.676 under `blend`.
- So the whole loss is the near field putting Coniston WwTW's spills, 84 m away, at nearly full
  strength at a site whose samples are middling.

What this shows:
- *Established:* `blend` does no harm to the held-out probability scores. Forward Brier is slightly
  better, and the lake Brier is better on the point estimate.
- *Established:* it lifts the ceiling at lake spots near an overflow, as asked: 16 of 19 lake spots
  with overflows were under Low, and 10 are with `blend`.
- *Established:* at the one evaluation site it changes most, its exposure rank and the samples
  disagree.
- *Checked after the results:* the outfall is where the model puts it. Coniston WwTW (UUP00534,
  receiving water Church Beck) is 112 m from the Boating Centre by both its live position and its
  annual-return outlet. It spills often: 168 spills and 1,765 hours a year on the long-term average.
- *Inferred, not tested:* the gap must be in the near field itself or in the sampling, for example:
  - the beck's plume runs along the shore away from the sampling point;
  - Church Beck in spate dilutes a storm spill more than its network length suggests;
  - samples rarely fall on spill days.

  A plume or dye survey at the Church Beck mouth would settle it. The samples here cannot.
