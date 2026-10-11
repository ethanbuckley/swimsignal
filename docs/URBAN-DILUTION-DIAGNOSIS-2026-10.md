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
