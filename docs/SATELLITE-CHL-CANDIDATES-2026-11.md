# Quality-aware satellite chlorophyll candidates: held-out comparison against the test's baseline (development)

Written 6 November 2026, protocol first, before any band pixel was fetched for it and before any candidate was scored.
Requested by Ethan (relayed by the coordinating session, 6 November): build and compare quality-aware candidate
methods against the existing chlorophyll baseline with the historical data available, on lake- and time-grouped
holdouts, and implement a working research or shadow path when supported. Follows the
[low-signal check](SATELLITE-LOW-SIGNAL-CHLOROPHYLL-2026-11.md) ([#626](https://github.com/ethanbuckley/swimsignal/pull/626)),
whose readout and pre-stated reading ("mixed, not shown") are unchanged, and the
[lab chlorophyll test](LAKE-CHLOROPHYLL-NDCI-TEST-2026-10.md) ([#386](https://github.com/ethanbuckley/swimsignal/pull/386)),
whose verdict ("fails as stated; promising, not validated") is unchanged.

**What this is.** Development on seen data, under the [research workflow](RESEARCH-WORKFLOW.md) (bounded exploration
and, if supported, a running comparison in shadow). The 2021-2026 lab values were scored in #386 and the paired scenes'
signal examined in #626, including how the low-signal rule moved the correlations. Held-out lakes, seasons and years
protect against fitting a candidate's own parameters to the rows it is scored on; they do **not** make the data unseen,
and the candidate list was written after #626. A candidate that does well here is a candidate for prospective
confirmation on pairs made after contract 1.4, not a validated method. Nothing here changes the published readings,
contract 1.4's thresholds or note, any issued forecast, or the frozen 2027 evaluation. Nothing is shown on the site as
a chlorophyll value. A satellite index is not a toxin measurement, an algae forecast or swimming clearance. The lab
outcome is EA acetone-extract chlorophyll (determinand 7887), spectrophotometric, phaeopigment correction not stated.

## 1. The question

The baseline is the lab chlorophyll test's: each lab sample paired with the nearest usable scene within a day, the
median NDCI over the clear core, and an ordinary least-squares line from that reading to log10 chlorophyll. Can a method
that uses each reading's measured signal relate the satellite to lab chlorophyll better at lakes, seasons and years it
was not fitted on, after paying for every sample it can no longer read?

## 2. What was known before the protocol

- #386: 207 pairs at 38 lakes, pooled Spearman 0.502; leave-one-lake-out calibration skill 0.159 [−0.058, 0.325]
  against the lake-mean reference; shallow lakes 0.301 "Better", deeper 0.069 "Too uncertain".
- #626 (seen, and the reason for candidate A): contract 1.4's rule flags 43 of 206 read pairs (21%; deeper lakes 28%,
  shallow 12%); without them the pooled Spearman is 0.580 against 0.501 and the within-lake 0.395 against 0.292, paired
  intervals including zero; #386's four conditions recomputed on the unflagged rows all hold as figures (a post-hoc
  subset). The flagged readings sit low at low-chlorophyll lakes. The inner-core reading changed nothing (+0.004).
- #626's published file holds each paired scene's brightness, pixel IQR and mark, but no pixels. The scratch pixels of
  #626's runs are gone, so candidate D (pixels) and E (more scenes) need a fetch.
- Offline count, no fetch (`prepare`, 6 November): 693 lab samples at the 38 points in seasons with imagery (2021 123,
  2023 143, 2024 137, 2025 148, 2026 142); 207 have a usable scene within a day, 341 within three days; **864 usable
  point-scenes** lie within three days of a sample (139 the same day, 275 at one day, 210 at two, 240 at three), at
  all 38 points. Fingerprint over the 25,234 cached input files `8e2f4b200b05f67fcafc0026ba5a663205fdcbaf9a4ece7797f41daf3675321c`
  (the same as #626's).

## 3. Protocol (fixed before the fetch and before any score)

### Data

- **Populations.** *Paired*: the 207 samples #386 paired (primary). *All*: every one of the 693 samples; a sample a
  method cannot read is predicted by the training reference, so a method is charged for every sample it leaves
  unread. A paired sample whose scene is not read by this fetch is dropped from the paired population for every
  candidate and counted; in the all-sample population an unread scene is absent for every candidate, the baseline
  included.
- **Scenes.** All 864 usable point-scenes within three days of a sample (`scripts/satellite_chl_candidates.py
  prepare`). Order: the 207 paired scenes first, then the rest; within each group points in a seeded order (seed
  20261106) and each point's scenes in a seeded order, one per point in turn. This fetch is a new run under this
  protocol; it includes the one scene #626 left unread.
- **Reads.** B4 and B5 through the existing reader, same scale, offset and mask rules. One run, at most **4,500
  requests and 2.5 GiB** (estimate from #626's measured 4.35 requests and 2.36 MiB a scene: about 3,760 requests and
  2.0 GiB), no account. An HTTP error status, a cap or a mismatch stops the run and nothing is retried. **A dropped
  connection** (no HTTP status) also stops it; written here in advance, unlike #626: one resume (`resume`) is allowed
  over the scenes not yet attempted, on the same ledger so the caps hold over both runs, the failed scene left out. A
  second dropped connection ends the fetch, and the analysis runs on what was read. The heavy-run lock is held for each
  run. SHA-256 over the cached inputs before selection, before and after each run and at the report; the features and
  values files must hash to #386's committed values. Every recomputed core reading must equal a cached one within 1e-6
  wherever the cache has one (the 414 scenes within a day). Pixels stay in scratch; the published file holds values only.

### Per scene

The core reading (#377's rule), contract 1.4's measurements (`signal_quality`: core brightness, pixel IQR) and mark
(`low_signal`), and the **pixel-filtered readings**: the median NDCI over clear core pixels whose own B4 + B5 is at
least a floor, for floors 0.005, 0.010, 0.015 and 0.020, a reading only where at least 9 such pixels have a valid
index (`pixel_filtered`).

### The candidates

Each is fitted on training rows only; any choice it makes is made inside the training rows.
- **B0, baseline.** The paired scene's core reading; OLS of log10 chlorophyll on it (#386's calibration).
- **A, exclude.** As B0, but a reading contract 1.4 marks low-signal is no reading (fitted on unmarked training rows;
  a marked test sample gets the reference). Thresholds are 1.4's, not tuned.
- **B, weight.** Every reading kept. Feasible generalised least squares: OLS, then the log squared residuals regressed
  on a noise score q = ln(IQR + 0.005) − ln(max(brightness, 0.002)), giving each reading an error variance
  exp(c + g q), then weighted least squares; two rounds. A prediction is the inverse-variance blend of the fitted line
  and the training reference (whose variance is its training mean squared error), so a noisy reading moves the
  prediction less (`fgls`, `_weighted`).
- **C, covariates.** OLS of log10 chlorophyll on the reading, log10 brightness (floored at 0.002), pixel IQR and
  reading × log10 brightness; at least 10 training rows. Brightness may carry chlorophyll information of its own
  (green, turbid water is brighter); if C does well, that is part of why.
- **D, pixel filter.** The paired scene's pixel-filtered reading; the floor chosen from the grid inside the training
  rows by an inner holdout of the same kind as the outer one (lakes for the lake holdout, seasons otherwise), least
  mean squared error, unread samples charged the inner reference; ties to the lower floor (`choose_floor`).
- **E, composite.** The median of the core readings of every usable, unmarked scene at the point within three days of
  the sample (both tiles and satellites); no such scene, no reading. OLS as B0.

### Holdouts and measures

- **Lake**: leave one water body out (38 folds; #386's). **Season**: leave one season out (5 folds). **Forward**: fit
  on 2021, 2023 and 2024, test on 2025 and 2026.
- **Reference** for every fold: the mean over training lakes of each lake's mean log10 chlorophyll (#386's), from the
  population's training rows. For seasons and years, the lake's own training mean is reported as context (a strong
  no-satellite reference where the lake is known); it decides nothing.
- **Measures**, per candidate, holdout and population (`measures`): skill = 1 − MSE ÷ MSE(reference); root mean
  squared error on log10 chlorophyll; pooled Spearman of prediction with log10 chlorophyll; within-lake Spearman
  (lake means removed, lakes with two or more rows); **coverage**, the share of the population's samples with a
  reading. Intervals: cluster bootstrap by lake, #386's 2,000 draws (seed 20261026), 2.5th to 97.5th percentiles, with
  out-of-fold predictions held fixed. **Paired differences from B0** for each measure, on the same draws.

### Supported for a shadow log (`support`)

A candidate is supported if, on the paired population:
1. on held-out lakes its skill gain over B0 is at least **+0.03**, and the paired interval's lower end is above
   **−0.05** (#386's harm margin H: no plausible material loss); and
2. on held-out seasons and on the forward years its skill gain is at least 0.

E, whose reason to exist is coverage, may instead meet both conditions on the all-sample population. These are a bar
for logging a candidate beside the baseline before outcomes arrive, not for adoption or display. No significance claim
is made.

### What follows from the result (fixed now)

- **Supported candidates:** `freeze` fits the baseline and each supported candidate once on all rows (D's floor chosen
  by the lake holdout) and writes `data/research/satellite/chl_shadow_model.v1.json`, a versioned research model. The
  refresher and the weekly pilot then log, beside each new reading and from the same windows, the inputs and each
  model's shadow value, in their own run records (not the published lake observation file, not the site). E is formed
  at pairing time from the per-scene values. The 2027 shallow-lake protocol review states how these shadow values are
  compared on pairs made after 1.4.
- **None supported:** no model is written; the record says which condition each candidate failed; the script stays
  runnable.
- Either way: the readout of #626, its pre-stated reading and 1.4's thresholds are unchanged, and the register and
  catalogue entries say this is development on seen data.

### Expected, stated now (guesses)

A gains on the paired population, perhaps by 0.05 to 0.15 in skill, but its coverage falls to about 80%, and it may
lose on the all-sample population where unread samples cost the reference error. B gains a little, less than A, with
full coverage. C may gain the most on held-out lakes, partly through brightness, and is the likeliest to lose on the
forward years. D gains little: in a dark scene few pixels pass, and in a mixed scene the bright pixels may be shore or
cloud edge. E covers more samples (perhaps 300 of 693) and gains most on the all-sample population. I would guess one
or two candidates are supported.

**Not claimed:** that any candidate measures chlorophyll, that a supported one is validated, that a flagged reading is
wrong, anything about algae, toxins or safety, or anything about #386's verdict.

### Amendment 1 (6 November 2026, written during the fetch, before any score)

Main now holds the workflow section "Develop promising work now" (#628, merged as f13f04de). Two of its rules bear on
this protocol and were not fully written above; they are added here before any candidate has been scored. Nothing
above changes.

**The shadow log, if one starts.** The pilot's run record (`data/research/satellite/pilot_runs.json`) is copied to the
public Research Lab by the site build, so shadow values must not go there. If a candidate is supported, its shadow
values and the baseline's go into their own versioned file, `data/research/satellite/chl_shadow_log.v1.json`, which
no page reads and the build does not copy; each row holds the scene's acquisition time, the time it was read, the
model version, every input (reading, brightness, IQR, mark, pixel-filtered reading) and each model's value, plus the
**fallback**: the frozen reference, the value a sample gets when a model has no reading. Inputs are from the scene's
own windows at reading time; no request is added. The refresher writes the same rows into its research root.

**The read of a shadow, fixed now.** Population: lab samples (determinand 7887) at the 38 points with a scene read by
the refresher or the pilot after contract 1.4, within a day, May to September 2027; frozen models, no refit; a model
with no reading is charged the frozen reference. Metric: skill gain over the frozen baseline against the frozen
reference, cluster bootstrap by lake (2,000 draws). A candidate is **not worse** than the baseline if the gain's
interval lower end is above −0.05 (#386's H), and **better** if in addition the gain is at least +0.03 and the lower
end above 0. Too few to judge below 60 pairs at 10 lakes. Read on or after **1 February 2028**, when the season's lab
values should be published; later if the minimum is not met then. A blocker known now: weekly reads at the 38 points
in 2027 need the runner the register already lists as open; the pilot covers five bathing sites, and its pairs with
lab samples will be few.

**What follows for each outcome** (the merged section's list):
- **Supported:** the shadow log above, and the read above.
- **Not supported, and some candidate's gain on held-out lakes is at least +0.03 with its lower end at or below −0.05
  (inconclusive):** no shadow. The deliverable is a **diagnosis**: which lakes, lake types and seasons drive the
  difference between that candidate and the baseline out of fold, and whether low-signal readings carry the
  baseline's largest errors; with the next comparison it implies stated in the record.
- **Not supported, and every candidate's gain is below +0.03 (fail):** the same diagnosis for the best candidate, and
  each variant whose interval excludes a gain of +0.03 archived in the catalogue with what would reopen it.
- **In every case:** if E's composite covers more samples without loss beyond the margin on the all-sample population
  (gain's lower end above −0.05), the composite rule is written into the record as a **coverage improvement** for the
  2027 pairing protocol, whether or not E is supported.

## 4. Results

To be written after the run.
