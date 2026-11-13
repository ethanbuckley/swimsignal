# River E. coli estimate at three Wessex sampling points: what can be checked, and an exploratory readout

Protocol written 13 November 2026, before any figure below the line was computed. Register row **WESSEX-RIVER**.
Secondary deliverable of the Wessex river samples work (the primary is the observation view,
[WESSEX-RIVER-SAMPLES-CONTRACT-v1.md](WESSEX-RIVER-SAMPLES-CONTRACT-v1.md)). Route: bounded exploration
([RESEARCH-WORKFLOW.md](RESEARCH-WORKFLOW.md)). **Exploratory: these outcomes have been seen before. Nothing here is
a held-out test, and nothing changes on the site.**

## The question

At Warleigh Weir, Farleigh Hungerford and Tellisford Weir, does the river E. coli estimate (the chance a sample is
over 900 per 100 ml) sit at the right level, and does it order the days? Wessex Water's own samples at points beside
these spots are the only measurements at two of them.

## What has already been looked at (stated in full)

1. **Fitting.** No Wessex sample is in any fitted model. Production's river model (`ecoli_model_sm.json`, 1,502 rows)
   and the hindsight models (#466) are fitted on Environment Agency bathing water samples only.
2. **The soil-moisture rivers test, 25 Oct 2026** ([SOIL-MOISTURE-RIVERS-TEST-2026-11.md](SOIL-MOISTURE-RIVERS-TEST-2026-11.md)).
   It scored the then production model ("reference") and the soil-moisture rule ("candidate") against every placed
   Wessex point, May to September 2020-25, with ERA5-Land rain. All three points were in its headline set, with every
   in-season sample: Warleigh Weir 173 (two position strings, 153 and 20), Farleigh's point 91, Tellisford's point 60.
   Its committed JSON publishes, per point: samples, results over 900, mean reference and candidate estimate, and
   within-point Spearman rho for each. **That test's pass was part of the evidence for adopting the candidate on
   rivers (#361, 26 Oct, Ethan's decision).** So in-season Wessex samples helped choose the model now live on rivers.
3. **Counts and positions.** The source inventory and `OVERFLOW-DATA-SOURCES-2026-10.md` give counts and distances at
   these spots. On 13 Nov, building the observation view, I saw every sample at the three points: values, dates,
   counts over 900 by year. I have not paired any of them with a model estimate.
4. **Not looked at:** any estimate for a sample outside May to September; the leave-one-year-out hindsight estimate
   with archived forecast rain (what `/samples.html` shows) at these points; issued forecasts at these spots against
   any Wessex sample.

## What this means for a held-out check

- In-season 2020-25: **not held out.** The outcomes were scored against the live model's own rule and informed its
  adoption. Any figure from them is development evidence. Rebuilding them with another rain input or another fold
  scheme does not make them unseen.
- Out of season (October to April): never scored, but the site shows no E. coli percentage then (`ecoliUntested`,
  DESIGN.md, 20 Oct 2026), and production's soil input for winter months is not cached (a rebuild would need Open-Meteo
  calls this brief does not allow). Not useful for what the site shows, so not run.
- **The genuinely held-out check is prospective:** the site's issued daily estimates are logged
  (`forecast_points.p_ecoli`, issue time and target day) since late September 2026. Wessex samples taken after an
  estimate was issued, joined to that estimate, are unseen. The layer covers 2019-25; it gained 2025 in an edit on
  5 June 2026, so 2026 rows may come in mid-2027 (most of them before the log began) and 2027's in mid-2028.

## The exploratory readout (fixed before computing)

**A. Level and order, from committed figures only.** From `SOIL-MOISTURE-RIVERS-TEST-2026-11.json` `per_station`, for
the three points (Warleigh's two position strings combined by sample-weighted means; rho reported per string):
- observed share over 900 with a Wilson 95% interval (treats samples as independent, so too narrow where samples
  cluster in time);
- mean estimate, reference and candidate (the candidate is the live river rule);
- the gap, observed share minus mean candidate estimate;
- within-point rho as published, with an approximate Fisher-z 95% interval (same independence caveat).

No rerun: the rows are not committed, and rerunning the test is not allowed (`c_baseline.md`: "Do not rerun it as a
test").

**B. Descriptive, from the Wessex export alone.** Share over 900 per point in May to September and in October to
April, 2021-25. At Farleigh Hungerford, the Wessex point's in-season share beside the Environment Agency's bathing water
samples in 2024 and 2025 (`ecoli_evidence.v1.json`): different places 2.3 km apart and different days, so a
description of the river, not a comparison of methods.

**Reading.** A point's level is called "off" if its Wilson interval excludes the mean candidate estimate. This is a
description, not a test: three points, picked because they are swim spots, after their values were seen.

## What each outcome leads to

- **Level off at one or more points:** a diagnosis note in this record and the register: which points, which way,
  and whether the Frome points behave alike. No site change: public wording keeps its full evidence bar, and three
  seen points cannot carry a per-site correction. If the Frome points both read low, the next development step is to
  look for the same in the Environment Agency's own samples at Farleigh (the concentration study's site rows already
  hold them), which would be a check on independent samples.
- **Level within the interval at all three:** recorded as consistent, not as validated.
- **Either way:** the prospective join (issued `p_ecoli` against Wessex samples taken after it was issued) is the next
  held-out step. Owner: the research session that owns WESSEX-RIVER. First check of the layer for 2026 rows on
  **1 July 2027**; a monthly check of its `dataLastEditDate` costs one request.

## Budget

No network calls. Inputs: the committed JSONs named above and `data/research/wessex_river_samples.v1.json`. Script:
`scripts/wessex_river_samples_check.py`, output `docs/WESSEX-RIVER-SAMPLES-CHECK-2026-11.json`.

---

## Results

(Added after the protocol above was committed and pushed.)
