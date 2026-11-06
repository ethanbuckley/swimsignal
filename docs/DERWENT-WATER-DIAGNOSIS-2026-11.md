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

---

## Diagnosis results

Run 6 November 2026 by `scripts/derwent_diagnosis.py` after the plan was pushed (4489eedc). The United Utilities event
file was read from a scratch copy; it and the committed inputs had the same SHA-256 before and after. Figures are in
`DERWENT-WATER-DIAGNOSIS-2026-11.json`. **Seen samples, described; not a test of any model.**

**Answer by the plan's rule: not explained by recorded spills at these overflows.** All three parts point the same
way:

| Plan criterion | Result | |
|---|---|---|
| 30-day or 60-day rho at least 0.3, interval above zero | 30-day 0.28 [−0.19, +0.58]; 60-day 0.17 [−0.30, +0.53] | no |
| May-September 2025 recorded spill hours above 2024's | 172 h in 2025, 220 h in 2024 | no |
| At least 2 of the 4 dry-day results over 900 with a recorded spill in the 7 days before | 1 of 4 (9 July 2025: 0.75 h); the others 8-18 days after the last spill | no |

**Recorded spills by lake** (Spearman rho with log10 E. coli, 2024-25, intervals from calendar-month blocks):

| Lake (samples, over 900) | 1 day | 3 days | 7 days | 30 days | 60 days |
|---|---|---|---|---|---|
| Derwent Water (40, 9) | 0.01 [−0.33, +0.36] | 0.08 [−0.33, +0.44] | 0.20 [−0.23, +0.52] | 0.28 [−0.19, +0.58] | 0.17 [−0.30, +0.53] |
| Coniston Water (120, 3) | **0.53 [+0.17, +0.69]** | **0.48 [+0.19, +0.63]** | **0.48 [+0.27, +0.62]** | **0.33 [+0.08, +0.55]** | 0.08 [−0.26, +0.42] |
| Windermere (160, 0) | 0.30 [−0.05, +0.56] | **0.30 [+0.01, +0.55]** | 0.24 [−0.07, +0.51] | 0.07 [−0.17, +0.32] | −0.04 [−0.29, +0.25] |

May-September recorded spill hours, 2024 / 2025: Derwent 220 / 172 (Grange Bridge 110 / 115, Stonethwaite 88 / 48,
Rosthwaite 22 / 8); Coniston 606 / 605; Windermere 1,058 / 1,261.

- **At Coniston and Windermere, recorded spills track counts over a day to a week; at Derwent they do not.** Derwent's
  overflows spilled less in its worst season than in its best.
- **Exploratory, after the plan, same samples:** at Coniston the modelled exposure (rho 0.42 [+0.24, +0.58]) and
  reanalysis rain at the lake (0.56 [+0.35, +0.67]) track counts about as well as recorded spills, and at Windermere
  (0.23 and 0.36) likewise. Recorded spills would add little there, so no recorded-spill candidate follows. At Derwent
  neither tracks (0.05 and 0.10).
- **Season and warmth (Q4):** water temperature at Crow Park on the sample day ranks Derwent's counts (rho 0.37
  [+0.15, +0.56], 59 samples, 2024-26), as does day of season (0.36 [+0.03, +0.59]). July was warmer in 2025 (20.0 °C)
  and 2026 (20.4 °C) than in 2024 (17.5 °C); the results over 900 had a median of 18.9 °C against 17.3 °C for the rest.
  This is an association; warmth and day of season move together, and the file cannot say which, or either, matters.
- **Enterococci,** described only: 9 of the 12 results over 900 also had enterococci of 750 or more (the other
  samples' median was 91). Three did not (140, 280 and 380), all three on dry days (0.6 mm or less in 48 hours). A source cannot be read from
  this.

**The EA's 2026 bathing water profile for Crow Park** (EA linked-data API, read 6 November 2026, OGL v3) names the upper
catchment's "private discharges ... from private dwellings, hotels and campsites", sheep farming, and runoff "during or
after periods of heavy rainfall". It says improvements were made to sewage discharges at Grange in Borrowdale and
Rosthwaite, and that investigations "will be undertaken during the bathing water season". It gives no source for
dry-weather results.

## Candidate D results

Run 6 November 2026 after its protocol was pushed (d8063382): `LAKE_SLOPE=season uv run python
scripts/lake_line_candidates.py run`, files `LAKE-LINE-CANDIDATES-2026-11-season-scores.json` and `-season-rows.csv`
(their "B" and "C" columns are D and D recalibrated). The same command without `LAKE_SLOPE` reproduced B's committed
scores exactly, apart from timings and a new label field.

| Condition | Result | |
|---|---|---|
| D1. Log score D − plain above zero, interval above zero | −0.003 [−0.018, +0.010] | **fail** |
| D2. Mean within-site rho D − plain, by-site interval above zero | +0.011 [−0.024, +0.050] | **fail** |
| G. Unseen lakes: log score D − plain, lower end above −0.02 | −0.006 [−0.023, +0.004] | **fail** |
| Reported: non-inferior to production at 900 | −0.0005 [−0.0073, +0.0052]: not shown | |
| Reported: skill over the usual rate at 900 | 0.005 | |

The fitted spread of lake seasonal slopes was small (0.06 to 0.11 log10 per standard deviation of day of year, against
about 0.2 for B's wet slopes), so partial pooling shrank Derwent's own season slope nearly to the average (+0.02 to
+0.09). Derwent's within-site rho rose from −0.11 to 0.01 and its Brier at 900 did not improve (0.191 against 0.189).
**D is archived:** with three seasons, a lake-specific season shape cannot be told from noise by this model.

## What it means, and the deliverable chosen

**Chosen deliverable: an evidence-backed archive of a Derwent line chance from the data the model reads, with this
diagnosis.** Why, under "Develop promising work now":

- The mechanism the forecast models, rain-driven spills from the monitored overflows upstream, is contradicted at
  Derwent by the measurements: recorded spills were fewer in the worst season, three of the four dry-day results over 900 in
  2024-25 came 8 to 18 days after the last recorded spill, and rain at the lake does not track counts. Five variants
  (the own rate, A, B, C and D) have now failed on these rows. No further model on these inputs is justified.
- At Coniston and Windermere the opposite holds: rain, modelled exposure and recorded spills track counts.
- **Inferred, not established:** a dry-weather source near Crow Park or in the upper catchment that rises in warm
  summers, consistent with the EA's named private discharges from dwellings, hotels and campsites, which peak with
  tourism, or with wildlife on the shore. These files cannot tell them apart.

**What would test each, and who would take it:**

| Possible source | Data that would test it | Who |
|---|---|---|
| Private discharges, hotels and campsites in the upper catchment | The EA's register of these permits and their locations; occupancy by month | EA register (public, offline read possible); a request is an outside contact (Ethan) |
| A source at the sampling point (boats, landing stages, wildfowl, swimmers) | Paired samples at Crow Park and a second point on the same day; shore bird counts | The EA's in-season investigation the profile names; ask the EA what it found (Ethan) |
| Warm-water persistence | Hourly lake temperature (a buoy) beside samples; the 2027 season | Lake temperature data already held (LAKE-TEMP) if a buoy record exists for Derwent |
| Something the overflow records miss (an unmonitored discharge) | The EA's 2025-26 investigation results for this bathing water | Ethan (outside contact) |

**Reopen the archived Derwent line chance when** one of these supplies a dated input that tracks Derwent's dry-weather
results, judged under its own protocol. The frozen plain and B models (line-candidates record) are unaffected and
keep their 2027 read.
