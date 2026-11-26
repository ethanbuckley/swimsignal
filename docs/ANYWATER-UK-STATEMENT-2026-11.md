# ANYWATER-UK: England's frozen coastal model on Welsh and Northern Irish samples

Statement written 25 November 2026, before any Welsh or Northern Irish sample is joined to rain or to any model
figure. Project 7 of the [ambition portfolio](AMBITION-PORTFOLIO-2026-11.md) (ANYWATER), cut to the two UK nations
whose rain is already on disk. The Republic of Ireland waits on a wider rain download (its west lies outside the
8.3° W edge of the bulk ERA5-Land box).

Nothing on the site changes from this statement. No frozen file, issued prediction, active window or the 2027
primary evaluation is touched.

## Gate

The portfolio's kill rule: **C1 must pass its own 2012 to 2021 read** (`docs/COASTAL-C1-PROTOCOL-2026-11.md`,
section 6, verdict "supported on unseen seasons"). If it does not, this test does not run and this file says so.

## What was known when this was written

- Each Welsh and Northern Irish bathing water's summary of its 2023 to 2026 samples (`typical_wales.v1.json`, 112
  sites, 4,588 samples; `typical_northern_ireland.v1.json`, 33 sites, 2,639 samples): counts, medians and ranges.
  No sample time has been joined to rain.
- C1 and C0 frozen on English samples only (`data/research/coastal/c1_frozen.v1.json`, SHA-256 `90b390ba…`).
  No Welsh or Northern Irish row played any part in fitting or choosing them.

## Rows

- **Wales:** NRW's in-season statutory samples (OGL v3), fetched as `scripts/export_typical_readings.py wales` does,
  from 1 May 2023 to 30 September 2026, at the 114 designated bathing waters, coast and estuary kinds only. About
  25 requests, cap 120.
- **Northern Ireland:** DAERA's yearly results tables 2023 to 2026 (OGL v3), as that script's `northern_ireland`
  does, coastal sites only. About 6 requests, cap 10. DAERA gives no qualifier; its lowest value, 10, stands as 10.
- May to September only. A site needs 20 or more rows to count (as `typical.MIN_SAMPLES`).
- Rain: ERA5-Land from the bulk download, converted by `to_cells.py` with C1's cell rule (amendment 1:
  `map_cells`, nearest point with data within 3 steps), window W1 (24 and 72 hours), coverage 90% or more.

## The figures each row gets

Each site is new to the frozen models, so its site rate is the pooled p0 (as a held-out English site in #692).
Within a site, then, C1's chance moves with the month, the last sample and the rain.

- **C1:** the frozen over-500 chance.
- **C0:** the frozen over-500 chance with no rain.
- **Month:** the frozen R (site rate p0 and the month).

## Metric and pass rule

**Primary:** the mean over sites of the within-site Spearman correlation between C1's chance and the measured E. coli
count (a "<" result ranks below every count; ties take the mean rank). Interval: 95% percentile, 2,000 bootstrap
resamples drawing whole sites and whole seasons independently, seed 20261125.

**Pass:** the interval lies wholly above **0.10**, in Wales and Northern Ireland pooled (the portfolio's rule).

**Reported, deciding nothing:** each nation alone; C1 minus C0 (what rain adds within a site) and C1 minus month,
with the same intervals; the Brier score for over 500 for C1, C0 and month; how many results were over 500.

## What each outcome leads to

| Outcome | What follows |
|---|---|
| Pass | The "after rain" past-sample line goes on Welsh and Northern Irish beach cards, labelled as tested this way, and the same rain wording as England's beaches where C1's own result supports it |
| Fail | The past-sample line by rain still goes on those cards (it is a count of past samples, not a claim), with no tested label. No rain wording beyond it |
| Gate shut (C1 not supported) | Nothing here runs. The past-sample line by rain is still allowed: it makes no claim |

## Limits known now

- 2023 to 2026 only: four seasons, and Welsh beaches mostly read low (the typical file's medians are often "<10").
- ERA5-Land is a reanalysis; a live word would use other rain.
- A pass shows that rain orders days within a beach in another nation. It does not show a level or a chance there.

## Amendment 1, 25 November 2026, before any score

The first scoring run stopped while reading times, before any rain was joined or any figure computed: DAERA's tables
give a sample's date and no time. Rule: **a sample with a date and no time counts as taken at 12:00 UK time** that
day (the hour `ecoli.SAMPLE_HOUR` uses for the site's own rain windows). NRW's samples carry their times and are
unchanged. Reported with the result: how many rows took this rule.

---

## Result, 25 November 2026: pass

Gate: C1's own read was "supported on unseen seasons" (`docs/COASTAL-C1-PROTOCOL-2026-11.md`). Scored once by
`scripts/coastal_c1/anywater_uk.py score`; figures in `docs/coastal-c1/anywater_uk.json`. Fetch: NRW's catalogue and
in-season samples and DAERA's layer and 2023-26 tables, 147 sites, 7,227 samples, no refusal.

**Rows.** 7,019 samples at 141 coastal and estuary sites with 20 or more (Wales 4,455 at 109; Northern Ireland 2,564
at 32), 133 over 500. Every rain window covered. All 2,564 Northern Irish rows took amendment 1's 12:00 rule.

| Mean within-site rho with the measured count | Pooled | Wales | Northern Ireland |
|---|---|---|---|
| **C1 (frozen, with rain)** | **0.303 (0.245 to 0.338)** | 0.310 (0.232 to 0.356) | 0.279 (0.221 to 0.341) |
| C0 (no rain) | 0.181 (0.113 to 0.220) | 0.192 | 0.142 |
| Month alone | 0.198 (0.132 to 0.260) | 0.204 | 0.180 |
| C1 minus C0 | +0.122 (+0.092 to +0.162) | +0.118 (+0.078 to +0.162) | +0.137 (+0.083 to +0.217) |

**Pass:** the pooled interval for C1 lies wholly above 0.10. Rain adds to the order within a beach in both nations,
with intervals above zero. Brier for over 500 (reported): C1 0.01795, C0 0.01852, month 0.01854.

**What follows (the statement's table):** the past-samples-by-rain line goes on Welsh and Northern Irish beach cards,
labelled as tested this way. It is not a chance or a level. Limits as stated: four seasons; Northern Irish times are
assumed to be midday.
