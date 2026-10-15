# Why the urban dilution term failed: the diagnosis, stated before any test

Written 11 October 2026, before any of the tests below was run. It follows
docs/URBAN-DILUTION-TEST-2026-10.md, where `DIPCAST_DILUTION_MODE=urban` failed all three
pre-stated conditions.

Nothing here is a candidate model. Every variant below is a diagnostic. None becomes a default.

## What is already measured

From docs/URBAN-DILUTION-TEST-2026-10.md (LOYO = leave one year out):

| measure | default (`length`) | `flow` | `urban` |
|---|---|---|---|
| LOYO Brier, full model | 0.0909 | 0.0891 | 0.0925 |
| LOYO AUC, all | 0.8151 | 0.8118 | 0.8022 |
| LOYO AUC, rivers | 0.7492 | 0.7376 | 0.7264 |
| Cross-site rho (32 sites) | 0.685 | 0.554 | 0.394 |

`flow` and `urban` use the same formula, `Q_i / (Q_i + Q50_spot)`. In `flow` every overflow has
`Q_i = 0.068 m³/s`. In `urban`, `Q_i = 0.068 × A_i / 0.512`, with `A_i` the overflow's share of a
built-up area, clipped to [0.1, 6.0] km². So **the effect of the spread of A_i is `urban` against
`flow`**. That is the main comparison in every test below. Default is reported for context.

## How every variant is run

- The evaluation chain is unchanged: `validate_ecoli.py`, `replay_ecoli_leads.py`,
  `validate_ecoli_combined.py`, `train_ecoli.py`, on this branch's code
  (claude/urban-dilution-diagnosis, from claude/river-velocity-dilution at d7153fd).
- Each variant runs in its own scratch `DIPCAST_ROOT`, a copy of the main checkout's
  `data/processed` (river network linked, read only). Rain comes from the cache only. Every
  outgoing network connection is refused, and the count of attempts is logged.
- A variant differs from `urban` **only** in the `urban_km2` column of
  `overflow_urban_area.parquet` in its root. The code is the same. `transport.urban_spill_m3s`
  still clips to [0.1, 6.0] km² and divides by 0.512.
- First, `length`, `flow` and `urban` are rerun in this harness. They must reproduce the figures
  above to four decimal places. If they do not, I stop and report.
- Measures per variant: LOYO, LOSO and forward Brier of the full model; LOYO AUC over all sites and
  over rivers; cross-site rho. Paired intervals use the harness of the urban test (2,000 resamples,
  seed 1; site-week clusters for Brier and AUC, sites for cross-site rho).

## H1. Placebo: is it the proxy, or any spread?

**Test.** 20 placebo variants. Each permutes the raw `urban_km2` column at random across all 14,630
overflows (numpy `default_rng(seed)`, seeds 1 to 20). The distribution of values is the same as
in `urban`. Only which overflow gets which value changes.

**Measures.** For each placebo: LOYO Brier, LOYO AUC (all, rivers), cross-site rho. Compare the
real `urban` with the 20 placebos and with `flow`.

**What would confirm or reject.** Let *k* be how many of the 20 placebos are at least as bad as the
real `urban` on a measure (higher Brier, lower AUC, lower rho).
- *k* ≤ 1 on most measures (real `urban` worse than at least 19 of 20 placebos, p ≤ 2/21 ≈ 0.10,
  one-sided): **the proxy carries wrong information.** Built-up share points spill size the
  wrong way at the overflows that matter.
- *k* ≥ 19 on most measures (real `urban` better than at least 19 of 20): **the proxy carries some
  right information**, and spread as such is what hurts.
- Otherwise: **the damage is explained by the formula's sensitivity to any spread of this size.**
  The real A_i is no worse than a random one.
- Separately: if the placebo median is worse than `flow` on a measure, any spread of this size
  hurts on that measure. If it is close to `flow`, a random spread costs nothing on average.

"Most measures" means at least three of the four (LOYO Brier, LOYO AUC all, LOYO AUC rivers,
cross-site rho).

## H2. Proxy validity: does A_i track spill size where there is independent evidence?

**H2a. EDM annual returns.** For each overflow in `annual_returns.parquet` (2021 to 2025, joined on
`site_id`), the mean over years of spill hours and of spill counts, years with a value only.
Spearman rho of A_i (clipped, as used) with each, with a 95% bootstrap interval (2,000 resamples of
overflows, seed 1). Also within network overflows only (`SO on sewer network`).
- Caveat stated now: spill hours and counts measure how long and how often, not how much. Overflows
  are designed and permitted to spill at certain frequencies. So this is a weak test either way.
- Confirmed (A_i tracks spill duration) if the interval's lower end is above 0.1. Rejected if the
  upper end is below 0.1. Otherwise inconclusive.

**H2b. Population equivalent at treatment works.** Source: Defra / Environment Agency, Urban Waste
Water Treatment Regulations Article 15 return, data as at 31 December 2022, file
`UWWTR_Art15_24thOct2024.ods`, table `T_UWWTPS`, field `uwwLoadEnteringUWWTP` (population
equivalent, p.e., entering the works).
https://www.data.gov.uk/dataset/d7e2c57b-110a-462b-97a0-9833e7d26cc2/wastewater-treatment-in-england
Licence as shown on that page: Creative Commons Attribution (CC BY).
- Covers works over 2,000 p.e. (freshwater) or 10,000 p.e. (coastal), so small works are missing.
- Match rule: each overflow whose `asset_type` contains "WwTW" (storm tank or inlet overflow at a
  works) gets the nearest UWWTD works with a load above 0 within 500 m, by great-circle distance
  between the overflow and `uwwLatitude`/`uwwLongitude`. Unmatched overflows are dropped. I report
  how many match.
- Why this is a fair check: a storm overflow at a works passes the flow of the whole sewer catchment
  above the works' treatment capacity. Its spill size should rise with the catchment, and p.e. is
  an independent measure of that catchment's size. (Domain reasoning, not tested here.)
- Measures: Spearman rho of p.e. with A_i (clipped, as used) and with the unsplit built-up area
  `bua_km2`. 95% intervals from 2,000 resamples of works (overflows at one works move together),
  seed 1. Also the paired difference rho(unsplit) − rho(A_i).
- Confirmed (A_i tracks catchment size at works) if rho(p.e., A_i) has a lower end above 0.3.
  Rejected if the upper end is below 0.3. Otherwise inconclusive. If the paired difference
  interval is above 0, **the equal split removes information** the unsplit area had.

**H2c. Works against network overflows.** Expectation from how sewers work (not tested here): an
overflow at a works drains more than an overflow on the network. Measure the median A_i of
overflows at works and of `SO on sewer network` overflows, and the ratio of medians with a bootstrap
interval. If the ratio's interval includes 1 or is below 1, A_i misses that difference.

## H3. Where the damage comes from

**H3a. Per site.** From the chain's own rows (`ecoli_validation_rows.parquet`, rows used by the
cross-site rho), each site's mean exposure in `flow` and in `urban`, its rank among the 32 sites,
the change in rank, and the change in log exposure. Report the sites that move most.

**H3b. Per overflow.** A fast replay of `validate_ecoli.py`'s exposure on the sample days, which
keeps each overflow's daily effect `e_i` (shifted spill probability × weight) apart. It must
reproduce the chain's `risk_model` for `flow` and `urban` to within 1e-9 on every row. If it does
not, H3b is not reported. Each overflow's contribution is its hazard `-ln(1 - e_i)` summed over a
site's sample-day rows (`risk_shares` splits the combined risk this way). For each site, rank
overflows by the change in contribution, `urban` minus `flow`.

**Groups**, fixed now from A_i alone (clipped values):
- `cap`: A_i = 6.0 (raw share ≥ 6.0 km²);
- `large`: A_i ≥ 2.0 km² (includes `cap`; 1,028 of 14,630 overflows, 7.0%; `cap` is 166);
- `floor`: A_i = 0.1 (no built-up area within 1 km, or a share below 0.1 km²; 1,773 overflows);
- `middle`: the rest.

Report each group's share of the summed absolute change in contribution over all 32 sites, and its
share of the overflows upstream of those sites.

**H3c. Counterfactual runs (full chain), diagnostic only.**
- CF-large-median: `large` overflows set to 0.512; the rest keep their A_i.
- CF-floor-median: `floor` overflows set to 0.512; the rest keep their A_i.
- CF-large-only: only `large` overflows keep their A_i; the rest are 0.512.
- CF-floor-only: only `floor` overflows keep their A_i; the rest are 0.512.

What would confirm: a group **drives the damage** if setting it to the median recovers at least half
the `urban` − `flow` gap on at least three of the four measures, *and* keeping only its spread
reproduces at least half the gap on at least three of the four. If neither group does, the damage
is spread across the middle of the distribution too, and I say so.

## H4. The equal split

Diagnostic variants of the apportioning rule, keeping step 1 (nearest built-up area within 1 km)
and the 0.1 km² floor for unassigned overflows:
- `unsplit`: A_i = the whole built-up area `bua_km2` (split exponent 0);
- `sqrt`: A_i = `bua_km2 / sqrt(n_in_bua)` (exponent 0.5);
- `urban` itself is `bua_km2 / n_in_bua` (exponent 1).

So that only the spread changes, each variant is rescaled to the same median as `urban`: raw values
× 0.512 / their median over all 14,630 overflows, then the code clips to [0.1, 6.0].

What would confirm or reject: if `unsplit` or `sqrt` is clearly better than `urban` (on at least three
of the four measures), the equal split is part of the problem. If both are as bad or worse, the split
is not what hurts; the built-up area itself is. This is not a model search: no variant here may be
proposed as a default on these results, because the comparison uses the same samples that judged
`urban`.

## H5. Added test: does the size of the spread matter, for the real proxy?

**Test.** Shrink the real A_i towards the median on a log scale: A_i' = 0.512 × (A_i / 0.512)^γ for
γ = 0.5 (half the spread), applied to the clipped values. Full chain.

**What would confirm or reject.** With H1: if the placebo shows any spread hurts, and γ = 0.5 sits
between `flow` and `urban`, the damage rises with spread size. If γ = 0.5 is better than `flow` on
at least three of the four measures, the proxy carries some right information that full spread
swamps.

## What would settle James Shucksmith's spill-size idea

Not tested here. This diagnosis can show why *this proxy* failed. It cannot show that spill size
does not matter. That needs a spill size measured or modelled per overflow from an independent source.

## Results

Added after the runs, below this line. Nothing above it is changed after any result is seen.

*Results added 11 October 2026, after all runs.*

### The answer

**The built-up-area shares point spill size the wrong way at the overflows that matter.** The real
A_i did worse than all 20 random reshuffles of the same values, on all four measures. Random
reshuffles cost nothing on average against `flow`. So the spread as such is not the problem. Which
overflow gets which value is.

Two independent checks agree that A_i is a poor measure of spill size:
- At treatment works, A_i correlates only 0.35 with the population equivalent entering the works.
  The unsplit built-up area correlates 0.60. The equal split removes information.
- Overflows at works get **half** the A_i of overflows on the sewer network (median 0.29 against
  0.60 km²). A works overflow passes the flow of a whole catchment, so it should get more, not less.

The damage is not concentrated in outer London or the 6 km² cap. Setting the large shares to the
median recovers at most 21% of the gap. The 0.1 km² floor overflows matter more per overflow: they
are 12% of the overflow-site pairs but 31% of the change in exposure, and 60% of them are overflows
at works, mostly small rural ones. Setting them to the median recovers 63% of the cross-site rho
loss, but only 7% to 32% of the other measures. Neither group meets the pre-stated rule for "drives
the damage". The rest comes from the middle of the distribution.

### How the runs were done

- The branch was rebased onto main after PR #166 merged (main 43c41aa). The pre-statement commit
  became 51e3aff (it was 1f4798e). Its text is unchanged (empty diff). On main, the four evaluation
  scripts and `model/transport.py` are as at d7153fd. The changes in between are Scotland code paths.
- The harness of the urban test was lost when the machine restarted. It was rebuilt from the
  repo and the urban test's description: `scripts/urban_diagnosis/` (see Files).
- Every variant ran the full chain, one at a time, in its own scratch root. 30 runs, 5.5 to 6 minutes
  each. One run peaks at 3.7 GB of memory (`replay_ecoli_leads.py`).
- No network connection was attempted in any of the 150 script runs (logged count 0 in each). Rain
  came from the cache.
- Every run kept the same 1,546 samples and 32 sites.

**Reproduction check: passed.** The rebuilt harness reproduces the published table of
docs/URBAN-DILUTION-TEST-2026-10.md exactly, at the published precision:

| measure | default | `flow` | `urban` |
|---|---|---|---|
| LOYO Brier | 0.0909 | 0.0891 | 0.0925 |
| LOSO Brier | 0.0904 | 0.0880 | 0.0913 |
| Forward Brier | 0.0828 | 0.0798 | 0.0838 |
| LOYO AUC, all | 0.8151 | 0.8118 | 0.8022 |
| LOYO AUC, rivers | 0.7492 | 0.7376 | 0.7264 |
| LOSO AUC, all / rivers | 0.8077 / 0.7609 | 0.8106 / 0.7533 | 0.8028 / 0.7418 |
| Forward AUC | 0.8097 | 0.8106 | 0.7938 |
| Cross-site rho | 0.685 | 0.554 | 0.394 |

`urban` against `flow`, paired (the effect of the spread of A_i; change is `urban` minus `flow`):
- LOYO Brier +0.0034 [+0.0016, +0.0054]; LOSO +0.0033 [+0.0014, +0.0054]; forward +0.0040 [+0.0018, +0.0063].
- LOYO AUC −0.0096 [−0.0167, −0.0032]; rivers −0.0111 [−0.0228, −0.0005].
- Cross-site rho −0.160 [−0.342, +0.023].

Brier and AUC values in the tables below are as `train_ecoli.py` writes them (4 decimals). The
"share of the gap" figures use those rounded values. Paired intervals use unrounded predictions.

### H1. Placebo: **confirmed, the proxy carries wrong information**

20 random permutations of A_i (seeds 1 to 20). *k* = placebos at least as bad as the real `urban`.

| measure | `flow` | real `urban` | placebo median | placebo range | *k* |
|---|---|---|---|---|---|
| LOYO Brier | 0.0891 | 0.0925 | 0.0894 | 0.0887 to 0.0904 | 0 of 20 |
| LOYO AUC, all | 0.8118 | 0.8022 | 0.8130 | 0.8104 to 0.8181 | 0 of 20 |
| LOYO AUC, rivers | 0.7376 | 0.7264 | 0.7425 | 0.7377 to 0.7518 | 0 of 20 |
| Cross-site rho | 0.554 | 0.394 | 0.577 | 0.404 to 0.650 | 0 of 20 |

- *k* = 0 on all four measures. The rule needed *k* ≤ 1 on three. One-sided p ≤ 1/21 (0.048) per
  measure.
- A random spread of this size costs nothing on average. The placebo median is within 0.0003 of
  `flow` on LOYO Brier (15 of 20 placebos are slightly worse than `flow`). It is better than `flow`
  on AUC (14 of 20), river AUC (20 of 20) and cross-site rho (14 of 20).

### H2. Proxy validity

**H2a. EDM annual returns: rejected (A_i does not track spill duration).**
Mean annual spill hours and spill counts, 2021 to 2025, joined by `site_id`. Bootstrap over overflows.

| A_i against | overflows | Spearman rho [95% CI] |
|---|---|---|
| spill hours, all | 14,363 | −0.190 [−0.206, −0.174] |
| spill counts, all | 14,363 | −0.168 [−0.184, −0.152] |
| spill hours, `SO on sewer network` | 7,935 | −0.068 [−0.089, −0.044] |
| spill counts, `SO on sewer network` | 7,935 | −0.084 [−0.106, −0.061] |

All upper ends are below 0.1, and below 0. As stated before the run, duration and frequency are not
volume, so this test is weak.

**H2b. Population equivalent at works: inconclusive for A_i; confirmed that the equal split removes information.**
Source: Defra / Environment Agency, UWWTR Article 15 return, data as at 31 December 2022, file
`UWWTR_Art15_24thOct2024.ods` (downloaded 11 October 2026, SHA-256 ba928ea7…a35e54f), table `T_UWWTPS`,
field `uwwLoadEnteringUWWTP`.
https://www.data.gov.uk/dataset/d7e2c57b-110a-462b-97a0-9833e7d26cc2/wastewater-treatment-in-england
Licence on that page: Creative Commons Attribution. Only derived correlations are kept; the file is not
in the repo.

- 1,451 works have a load above 0. 3,083 overflows are at works (`asset_type` contains "WwTW").
  1,322 of them match a works within 500 m, at 1,075 distinct works. 110 of the matched overflows are
  on the 0.1 km² floor.
- Spearman rho with p.e., resampling works:
  - A_i (as used): **0.352 [0.294, 0.409]**. The lower end is below 0.3 and the upper end above, so by
    the pre-stated rule this is inconclusive.
  - Unsplit built-up area: **0.598 [0.545, 0.649]**.
  - Paired difference, unsplit minus A_i: **+0.246 [+0.201, +0.291]**. Above 0: the equal split removes
    information the unsplit area had.
- One row per works (mean A_i): 0.362 [0.306, 0.415] against 0.582 [0.532, 0.631] unsplit; difference
  +0.221 [+0.181, +0.261]. Same conclusion.

**H2c. Works against network overflows: confirmed, A_i misses the difference (it reverses it).**
Median A_i 0.289 km² at works (3,083 overflows) against 0.599 km² on the network (7,944). Ratio
0.48 [0.46, 0.51]. The expectation (works overflows drain more) is domain reasoning, not tested here.

### H3. Where the damage comes from

**Replay check: passed.** The per-overflow replay reproduces the chain's `risk_model` on every row:
largest difference 0 for `urban` and 2.0e-15 for `flow`.

**H3a. Per site** (`flow` → `urban`, rank among 32 sites by mean exposure; E. coli rank is the rank of
the site's mean log E. coli). The sum of |exposure rank − E. coli rank| rose from 224 to 258.

| site | E. coli rank | `flow` rank | `urban` rank | change mostly from |
|---|---|---|---|---|
| Derwent Water at Crow Park | 19 | 17 | 3 | floor overflows (all of it) |
| Sandy Lane, Chester | 21 | 16 | 8 | floor |
| River Teme in Ludlow | 17 | 12 | 4 | floor |
| Wharfe at Cromwheel, Ilkley | 28 | 27 | 20 | floor, then middle |
| Colwick Country Park (West Lake) | 6 | 22 | 30 | middle, then large |
| Ham and Kingston, River Thames | 15 | 2 | 16 | large |
| Wallingford Beach, River Thames | 16 | 10 | 19 | large |
| Pangbourne Meadow, River Thames | 11 | 3 | 10 | large |

- The moves that hurt the ranking: sites with high E. coli fell, and Colwick rose further above its
  E. coli rank. At Derwent Water, Chester, Ludlow and Ilkley the fall comes from floor overflows.
- The three Thames sites, where the large shares act, moved **towards** their E. coli rank. That is
  the opposite of the outer-London speculation in the urban test.

**H3b. Per overflow.** 937 overflow-site pairs (854 distinct overflows) upstream of the 32 sites.
Change = hazard in `urban` minus hazard in `flow`, summed over each site's sample days.

| group | share of pairs | share of summed \|change\| | net change | share of hazard, `flow` → `urban` |
|---|---|---|---|---|
| floor (A_i = 0.1) | 12.0% | 31.5% | −1.29 | 22.1% → 5.7% |
| large (A_i ≥ 2, incl. cap) | 8.3% | 8.0% | +0.33 | 0.8% → 6.8% |
| of which cap (A_i = 6) | 2.3% | 2.4% | | |
| middle | 79.7% | 60.6% | −0.69 | 77.1% → 87.5% |

- 46 pairs make half of the summed |change|; 226 make 90%.
- The largest single changes are floor overflows at small works: Torver WwTW above Coniston Water
  (−0.21), Beamsley STW above Ilkley, Gisburn WwTW above the Ribble at Edisford Bridge.
- Of the floor pairs, 60% are overflows at works (`asset_type` contains "WwTW"), against 29% of
  the middle pairs. *Descriptive; not a pre-stated test.*

**H3c. Counterfactuals (full chain; diagnostic only, not candidate models).** Share of the
`urban` − `flow` gap (Brier +0.0034, AUC −0.0096, river AUC −0.0112, rho −0.160) that each run
recovers or reproduces:

| run | LOYO Brier | LOYO AUC | river AUC | cross-site rho |
|---|---|---|---|---|
| CF-large-median (recovers) | 0.0918 (21%) | 0.8028 (6%) | 0.7274 (9%) | 0.412 (11%) |
| CF-floor-median (recovers) | 0.0914 (32%) | 0.8050 (29%) | 0.7272 (7%) | 0.495 (63%) |
| CF-large-only (reproduces) | 0.0899 (24%) | 0.8099 (20%) | 0.7350 (23%) | 0.570 (−10%) |
| CF-floor-only (reproduces) | 0.0898 (21%) | 0.8076 (44%) | 0.7358 (16%) | 0.552 (2%) |

- **Large: does not drive the damage.** It recovers under half and reproduces under half on all four.
- **Floor: does not drive the damage** by the pre-stated rule. It recovers at least half on one
  measure of four (cross-site rho).
- So the damage is spread. On LOYO Brier the two groups' medians together would recover about
  0.0019 of 0.0034 if their effects add; the rest would sit in the middle group. *Inferred by
  subtraction; a run with both groups at the median was not done.*
- Paired against `urban`: setting the floor to the median lowers LOYO Brier by 0.0011 [0.0004, 0.0019]
  and raises cross-site rho by 0.101 [−0.005, +0.226]. Setting the large shares to the median lowers
  LOYO Brier by 0.0008 [0.0002, 0.0014] and changes rho by +0.017 [−0.079, +0.110].

### H4. The equal split: **inconclusive; no detectable effect on the E. coli scores**

| run | LOYO Brier | LOYO AUC | river AUC | cross-site rho |
|---|---|---|---|---|
| `urban` (split exponent 1) | 0.0925 | 0.8022 | 0.7264 | 0.394 |
| `sqrt` (exponent 0.5) | 0.0924 | 0.8024 | 0.7291 | 0.492 |
| `unsplit` (exponent 0) | 0.0925 | 0.8035 | 0.7319 | 0.530 |

Paired against `urban`, every interval includes 0:
- `unsplit`: LOYO Brier −0.0001 [−0.0014, +0.0013]; AUC +0.0013 [−0.0031, +0.0055];
  river AUC +0.0055 [−0.0019, +0.0134]; rho +0.136 [−0.045, +0.332].
- `sqrt`: LOYO Brier −0.0002 [−0.0009, +0.0006]; AUC +0.0002 [−0.0024, +0.0027];
  river AUC +0.0027 [−0.0014, +0.0071]; rho +0.097 [−0.020, +0.235].

The point estimates favour less splitting on three (`unsplit`) or four (`sqrt`) measures, but none is
clearly better, and both are no better than `urban` on Brier. `unsplit` stays worse than `flow` on
LOYO Brier: +0.0034 [+0.0013, +0.0056]. So the split explains little of the Brier damage, and the
built-up area itself carries most of it. H2b shows the split does remove size information at works.
The two fit together: works overflows matched to a p.e. carry only 12% of the `flow`-mode hazard
upstream of the 32 sites (139 of 854 overflows). *Descriptive.*

### H5. Size of the spread: **confirmed, the damage rises with spread; no sign of right information**

γ = 0.5 (half the log spread): LOYO Brier 0.0905, AUC 0.8057, river AUC 0.7316, rho 0.529. It lies
between `flow` and `urban` on all four measures and is better than `flow` on none. Against `urban`:
LOYO Brier −0.0021 [−0.0032, −0.0010]. Against `flow`: +0.0014 [+0.0005, +0.0023].

### What the tests established, and what they did not

Established:
- The specific assignment of built-up area to overflows hurts. A random assignment of the same values
  does not (H1).
- For this proxy, the damage grows with the size of the spread (H5).
- It is not concentrated in outer London or the cap (H3). The floor overflows contribute most per
  overflow and most of the cross-site loss (H3b, H3c), but not most of the Brier or AUC loss.
- A_i tracks catchment size at works weakly (0.35), less than the unsplit area (0.60). It gives works
  overflows half the share of network overflows. It is negatively associated with spill duration (H2).

Not tested:
- *Why* the floor and small-works overflows matter for E. coli at sites like Derwent Water, Ilkley and
  Ludlow. Possible reasons include spill volume relative to a small receiving stream, treatment at
  small works, or other sources such as farms. None is tested here.
- Whether any per-overflow spill size helps. These tests reject this proxy, not the idea.

### What would make a fair test of spill size per overflow

Not run. A fair test needs:
1. A size measure from a source independent of the built-up area, for the overflows that carry the
   hazard. Works overflows carry 56% of the `flow`-mode hazard upstream of the 32 sites. UWWTD p.e.
   covers only works over 2,000 p.e.: 139 of the 265 works overflows there, 12% of the hazard. Small
   works and network overflows would need another source, for example population served or design
   flows from permit or drainage-plan data, under an open licence (availability not checked).
2. The placebo control used here: the candidate must beat random permutations of its own values, not
   only the default. A random spread of this size scores like `flow`, so beating default alone says
   little.
3. A pre-statement that treats these 32 sites as already seen. A new proxy judged on them is a second
   look at the same samples.

### Files

- `scripts/urban_diagnosis/`: the harness, rebuilt. `run_variant.sh` (one scratch root and the full
  chain, network refused, one script at a time), `queue.sh`, `make_tables.py` (H1, H3c, H4, H5
  tables), `h2.py`, `trace.py` and `decomp.py` (H3a, H3b), `summary.py`, `judge.py` (applies the rules
  above), `paired.py` and `pairs.py` (paired intervals). Outputs go to `$DIAG_DIR`, never to `data/`.
- To rerun: `export DIAG_DIR=<scratch folder>`; `run_variant.sh default length`,
  `run_variant.sh flow flow`, `run_variant.sh urban urban`;
  `make_tables.py data/processed/overflow_urban_area.parquet`; `queue.sh $DIAG_DIR/jobs_diag.txt`;
  `run_trace.sh`; `summary.py`; `judge.py`; `pairs.py`. About three hours on one machine.
  `h2.py` takes its five paths as arguments; the UWWTD table must first be exported from the `.ods`
  to CSV (`T_UWWTPS` sheet).
- The runs here used the same scripts from a scratch folder, with paths written in. The repo copies
  take paths from `DIAG_DIR` and their own location. `pairs.py` was run from the repo copy.
