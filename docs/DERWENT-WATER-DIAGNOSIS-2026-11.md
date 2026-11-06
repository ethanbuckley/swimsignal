# Derwent Water's high E. coli results: a diagnosis plan, then the diagnosis

Written 6 November 2026, register row **3 / LAKE-CONC**. This is the next deliverable that #625's evidence supports,
under the workflow's "Develop promising work now" (merged in #628): **a concrete diagnosis**, because the result is
unexplained. Neither the own-rate test (`docs/LAKE-OWN-RATE-TEST-2026-11.md`) nor the line candidates
(`docs/LAKE-LINE-CANDIDATES-2026-11.md`) supports a lake line-chance model. Both turned on one lake. Derwent Water at
Crow Park holds 12 of the 16 lake results over 900 in 2024-26. Its high results came in a summer-long rise that rain
at the lake and modelled spill exposure do not track; 6 of the 12 had 0.6 mm of rain or less in the 48 hours before.
**The plan below is committed and pushed before any spill record, temperature or enterococci value is joined to a
Derwent sample.** Descriptive, on seen samples; it changes no model, verdict, page or log.

## What is already known (seen before this plan)

- Counts, dates, forecast rain at the spot and the modelled exposure of the 59 Derwent samples in the study rows,
  2024-26 (the line-candidates diagnosis, `-derwent.json`). The lake's mean residence time is about 86 days (HydroLAKES,
  `data/raw/lake_residence.csv`); the exposure's die-off window is about three days.
- The three monitored overflows upstream of the bathing water, from the pipeline's own pin and transport (the
  cached overflow table, built on network key b5724303 against the current c259f640; the count matches the study
  rows' 3): **Grange Bridge (UUP00823), Rosthwaite WwTW (UUP01690) and Stonethwaite WwTW (UUP01875)**, all in
  Borrowdale, travel time 23-29 hours. Keswick's overflows discharge to the Greta below the lake and are not upstream.

## Data to join (not yet joined)

- **Recorded spills:** `data/processed/edm_events.parquet`, United Utilities' detailed EDM event records, 2023-2025
  (none for 2026). For each sample, the recorded spill hours at the three overflows in the 1, 3, 7, 30 and 60 days
  before the sample time, and the days since the last recorded spill ended.
- **Water temperature:** `data/research/lake_temperature_obs.v1.json`, the EA reading at the Crow Park point on the
  sample's date.
- **Enterococci:** `data/research/ecoli_evidence.v1.json`, the same sample's enterococci count.
- **Comparison lakes:** the same spill measures at Coniston Water (3 sites, 2 overflows upstream) and Windermere
  (4 sites, 4-6 overflows upstream), so a Derwent-specific pattern can be told from a general one.

Samples: Derwent 2024-25 (40 samples, 9 over 900) for the spill questions, since there are no 2026 records; 2024-26
(59) for temperature.

## Questions and what each answer would mean, fixed now

- **Q1, missed spills.** Spearman rho between recorded spill hours in the 7 days before and log10 E. coli at Derwent,
  2024-25 pooled, with a 95% interval from 2,000 resamples of calendar-month blocks (seed 20261106). Also: how many of
  the 4 dry-day results over 900 in 2024-25 (0.6 mm or less in 48 hours: 30 Jun, 9 Jul, 14 Aug and 22 Aug 2025) had a
  recorded spill in the 7 days before.
- **Q2, accumulation.** The same rho for 30-day and 60-day recorded spill hours. The lake holds water for months, so a
  build-up from spills over weeks would show here and not in the 3-day exposure.
- **Q3, a Derwent pattern or a general one.** Q1 and Q2's rho at Coniston and Windermere, and each lake's recorded
  spill hours in May-September 2024 against 2025.
- **Q4, season and warmth.** Rho of water temperature and of day of season with log10 E. coli at Derwent, 2024-26;
  Derwent's monthly median temperature 2024 vs 2025 vs 2026. Enterococci beside E. coli for the 12 results over 900,
  described only: this file cannot attribute a source.

**What counts as an answer, fixed now:**

- **"Consistent with recorded spills that the rain-driven exposure misses"** if the 30-day or 60-day rho is at least 0.3
  with its interval above zero, **and** Derwent's May-September 2025 recorded spill hours exceed 2024's, **and** at
  least 2 of the 4 dry-day results over 900 had a recorded spill in the 7 days before. **Next deliverable:** a
  development candidate adding recorded-spill accumulation as an input, tested on every lake with held-out folds. Its
  first step is an issue-time check. The detailed EDM files are published the following year, so at issue time only
  the live status feeds exist (United Utilities' is polled; poll history from 18 October 2026).
- **"Not explained by recorded spills at these overflows"** if the 30-day and 60-day rho are under 0.3 or their
  intervals include zero, and fewer than 2 dry-day results had a recorded spill within 7 days. **Next deliverable:** an
  evidence-backed archive of a Derwent line chance from overflow data, naming the other sources these files cannot see
  and which data would test each. No model is built for it.
- **Anything between:** reported as mixed, with the figures. The next deliverable is the data improvement that would
  separate the two, named with who would take it.
- **Q4 cannot establish a cause.** A temperature or season association is reported as such, never as a mechanism.

**Power:** 40 samples with 9 over 900 give a single rho a standard error of about 0.16. One lake and two seasons: any
answer is about these seasons at this site.

---

## Candidate D: a lake-specific seasonal response (protocol, committed before it is fitted or scored)

Added 6 November 2026, after the diagnosis results below were computed and before any fit of D. The diagnosis
found Derwent's counts rise through each summer (May to August medians: 109→260 in 2024, 59→980 in 2025, 63→570 in
2026) and track neither rain, nor modelled exposure, nor recorded spills. The plain model's season terms are shared by
every site, so a lake whose summer rise is steeper than average cannot be represented. **D is the fourth variant tried
on these same seen rows (after A, B and C); any figure below is development, and a selection effect is possible.**

- **D:** `scripts/lake_line_candidates.py`'s B with the slope variable changed: a random slope per bathing water on
  `lake × season`, where `season` is the day of year (recovered from the model's day-of-year terms) standardised on the
  fold's lake fitting rows, with a fixed all-lake mean slope, partially pooled exactly as B. Day of year is known at
  issue time. No other change: same rows, folds, clusters, seed, bootstrap and references as the line candidates.
- **Conditions, main scheme (leave one season out):** (D1) censored log score D − plain above zero, interval above zero;
  (D2) mean within-site rho D − plain above zero, by-site interval above zero. **Guardrail (G):** at unseen lakes
  (leave-one-lake-out), log score D − plain with its interval's lower end above −0.02. Line chance at 900 and 500:
  Brier and skill reported against production, plain and the usual rate with #625's 0.10 margin; **non-inferiority is
  claimed only if an interval excludes harm beyond +0.002 at 900, which 16 events will rarely allow.**
- **Outcomes:** D1, D2 and G hold → D is a supported development candidate for within-lake order. Next: freeze it beside
  plain and B for the 2027 read, computed from `shadow_lake_range_v1`'s logged inputs (it needs no new logger: its only
  new input, the day, is logged). D1 or D2 fails → D is archived with its figures. The Derwent diagnosis stands either
  way.
