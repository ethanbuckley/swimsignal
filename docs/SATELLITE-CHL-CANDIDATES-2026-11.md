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

### Amendment 2 (6 November 2026, 12:00 UTC, after the first run was stopped, before any score)

The first run (from 11:52:57 UTC) read serially, one range request at a time, and each B4 read took about 30 seconds:
5 of 864 scenes in six minutes, 24 requests, 16,131,802 bytes, a measured rate of about 43 KB/s. At that pace the run
would have held the shared heavy-run lock for about 14 hours. The protocol gave caps but no wall-time estimate, against
Ethan's standing rule (26 October) to size requests × latency first. I stopped it at 11:59 UTC with an interrupt to
its own process; it recorded its run file (fingerprint unchanged) and released the lock. #626's runs were serial too
and read 155 scenes in four minutes, so the slowness is the connection today, not the code.

Changes, before any score:
- **Reads go 16 at a time** through the stage-1 thread pool (`stage1.pmap`), as #377's amendment A1 allows for the two
  public COG buckets; the capped client counts every request under one lock. Paired scenes are still submitted first.
- **A wall-time limit of 60 minutes per run.** Reads in flight finish; nothing new starts; the run is recorded with
  its stop.
- **One continuation** (`continue`) over the scenes not yet read, on the same ledger, so the 4,500-request and 2.5 GiB
  caps hold over every run. The dropped-connection resume of section 3 still applies once, after the continuation.
- **Wall time, estimated:** about 2.0 GiB remain. If the 43 KB/s holds per stream, 16 streams take about 50 minutes;
  if it is the connection's total, the 60-minute limit stops the run after roughly 150 MiB, about 60 scenes.
- **If the limit stops it short:** no second continuation. The analysis runs on what was read, labelled partial. The
  paired population is complete only if all 207 paired scenes were read; the all-sample population and candidate E
  then rest on fewer nearby scenes than selected, and say so. If fewer than all 207 paired scenes are read, the
  paired results are reported on the paired samples read, and the shortfall is a blocker stated in the record.

## 4. Results (6 November 2026)

All figures below are **development on seen data** (section 1). None is fresh confirmation.

### 4.1 The fetch, and what it did not read

Three runs, as the protocol and amendment 2 allow: the first, serial (5 scenes, 24 requests, 16.1 MB, stopped by me
for its pace); the continuation, 16 reads at a time (60 scenes, 267 requests, 142.6 MB, ended by a dropped
connection at 12:07 UTC); the one resume (118 scenes, 512 requests, 280.0 MB, ended by a second dropped connection at
12:15 UTC). Under section 3 the second drop ends the fetch. In all **803 requests and 438,679,528 bytes (418.4 MiB)**,
under the 4,500-request and 2.5 GiB caps; 801 responses 206, two connections dropped with no status, nothing retried.
The fingerprint over the 25,234 cached input files was `8e2f4b20…3675321c` before selection, before and after each run
and at the report. All 183 recomputed core readings equal the cached ones. With 16 streams the rate was about
0.54 MB/s, twelve times the serial run's.

**Read: 183 of the 207 paired scenes, and none of the 657 other scenes within three days.** So:
- the paired population is **183 samples at 38 lakes** (24 paired samples dropped for every candidate, as section 3
  says): 22 were the last 22 in the seeded order and 2 were the scenes whose connections dropped (positions 37 and 166),
  so no outcome chose them;
- **candidate E was not tested.** With no scene other than a sample's own paired scene, every composite is that scene's
  unmarked reading and E's figures equal A's exactly (183 of 183; 148 composites, the same 148 readings as A). The
  rule that marks E "not tested" (`e_tested`) was written **after the first report** showed this, not before any
  score: amendment 2 foresaw E resting "on fewer nearby scenes", not on none. It only removes a support, and the
  published file keeps E's mechanical conditions; `freeze` leaves E out. Amendment 1's coverage clause is **not met**:
  E covers no more samples than A;
- the all-sample population has readings only where the paired scene was read (26% of 693 samples), so its figures
  mostly measure the cost of the reference on unread samples. Its pooled Spearman is negative on the lake holdout for
  that reason (the reference left after removing a high-chlorophyll lake is lower, so the many reference-only rows rank
  backwards); skill and RMSE are the useful measures there.

### 4.2 The candidates on the paired samples

Skill against #386's lake-mean reference, out of fold, with cluster intervals by lake; RMSE in log10 units:

| Candidate | Coverage | Held-out lakes | Held-out seasons | Forward (2025-26) | RMSE, lakes |
|---|---|---|---|---|---|
| B0 baseline | 100% | 0.163 [−0.067, 0.333] | 0.156 [−0.082, 0.337] | 0.221 [0.033, 0.359] | 0.579 |
| A exclude low-signal | 81% | 0.306 [0.117, 0.467] | 0.304 [0.123, 0.461] | 0.348 [0.191, 0.479] | 0.527 |
| B weight by signal | 100% | 0.180 [0.054, 0.278] | 0.198 [0.073, 0.304] | 0.289 [0.154, 0.395] | 0.573 |
| C brightness and spread as covariates | 100% | 0.300 [0.057, 0.484] | 0.290 [0.046, 0.475] | 0.317 [0.025, 0.515] | 0.530 |
| D dark pixels dropped | 93% | 0.197 [−0.130, 0.435] | 0.198 [−0.118, 0.435] | 0.281 [0.006, 0.471] | 0.567 |

Paired skill gain over B0 (the support rule's measure):

| Candidate | Held-out lakes | Held-out seasons | Forward | Supported |
|---|---|---|---|---|
| A | **+0.143 [+0.005, +0.306]** | +0.148 [−0.002, +0.326] | +0.127 [−0.031, +0.299] | yes |
| B | +0.017 [−0.066, +0.139] | +0.042 [−0.045, +0.164] | +0.068 [−0.003, +0.161] | no: gain under +0.03, lower end below −0.05 |
| C | **+0.137 [+0.034, +0.233]** | +0.133 [+0.029, +0.227] | +0.096 [−0.102, +0.230] | yes |
| D | +0.034 [−0.122, +0.178] | +0.041 [−0.116, +0.196] | +0.060 [−0.141, +0.223] | no: lower end −0.122 |
| E | not tested (4.1) | | | no |

On the all-sample population the same ordering holds at a third of the size (A +0.047 [+0.001, +0.103], C +0.045
[+0.010, +0.079] on held-out lakes). D chose the top floor of its grid, 0.020, in 37 of 38 lake folds: the grid's edge,
so a higher floor might have been chosen had it been offered; that was not tested.

The script's words (`words` in the published file): A and C "supported for a shadow log (conditions met on
the paired samples)"; B and D "not supported: fails condition 1"; E "not tested".

**Context that decides nothing but matters for use:** on held-out seasons the lake's own training mean scores skill
0.461 against the same reference, and 0.400 on the forward years. Every satellite candidate here is below that
(A 0.304 and 0.348). These candidates do not use which lake a sample is from; at a lake with a lab history, that
history is a better guess of its chlorophyll level than any of these satellite calibrations.

### 4.3 Diagnosis (amendment 1)

For A, the candidate with the largest held-out-lake gain, out of fold:
- **Where the gain is:** 80% of it is at shallow lakes (mean squared error 0.304 to 0.203); deeper lakes lose a little
  (0.329 to 0.336); lakes with no depth carry 25%. By season, 2024 and 2026 carry most of it; 2021 loses slightly.
- **Lakes most helped:** Filby, Barton and Martham Broads, Groby Pool, Fritton Decoy. **Most hurt:** Wast Water,
  Frensham Great Pond, Ranworth Broad, Ravensthorpe Reservoir, Ormesby Little Broad. At Wast Water, a clear deep lake,
  removing its dark readings leaves the reference, which is far too high for it.
- **Low-signal readings carry the baseline's largest errors:** they are 19% of the paired rows (35 of 183), 29% of the
  baseline's squared error and 37% of its top tenth of errors (baseline mean squared error 0.50 flagged against 0.30
  unflagged).

### 4.4 What this means

1. **Two candidates meet the pre-stated bar for a shadow log: A and C.** Both gain about 0.14 in skill over the
   baseline on held-out lakes, with paired intervals above zero, and keep the direction on held-out seasons and years.
2. **A's support is not independent of #626.** A was proposed because #626 showed, on these same pairs, that the
   unflagged subset agrees better with lab chlorophyll. Holding out lakes and seasons tests the calibration's transfer,
   not that choice. Its thresholds are contract 1.4's, set from shore-margin scenes without reference to lab
   chlorophyll; the decision to try them here was made after #626 had seen these pairs.
3. **C partly uses brightness as a chlorophyll signal**, not only as a quality signal. On the 183 paired samples,
   log10 brightness has a Spearman of 0.387 with log10 chlorophyll and 0.255 with the baseline's residual, but 0.089
   within lakes: brightness mostly separates greener, more turbid lakes from clear ones. In the frozen model C's slope
   on the reading is 5.80 + 2.55 × log10 brightness, about zero at brightness 0.005 and negative below it, so C ignores
   or inverts the darkest readings. Its within-lake Spearman (0.274) is no better than the baseline's (0.280). Its
   forward-year interval reaches −0.10.
4. **B (weighting) is not supported:** its gain (+0.017) is under the +0.03 bar. **D (pixel filtering) is
   inconclusive** in amendment 1's sense: its gain (+0.034) meets the bar but its lower end (−0.122) is beyond the
   −0.05 harm margin, and it chose the edge of its floor grid in 37 of 38 folds, so it is under-explored. Neither gets
   a shadow; neither is archived (amendment 1 archives only when every candidate fails). E is untested.
5. The useful satellite signal is concentrated in shallow lakes, as #386 found, and the low-signal mark identifies the
   readings that carry the baseline's worst errors.

### 4.5 What is built and what runs

- **Frozen model** `data/research/satellite/chl_shadow_model.v1.json` (version 1.0.0): B0, A and C fitted once on the
  183 paired rows, and the fallback (the lake-mean reference, 1.018 in log10 units). Coefficients: B0 1.032 + 1.589 x;
  A 0.878 + 3.514 x on unmarked readings; C on x, log10 brightness, IQR and x × log10 brightness.
- **Shadow log** `data/research/satellite/chl_shadow_log.v1.json` (`scripts/lake_chl_shadow.py`), committed empty with
  the model's SHA-256 and the unit of its values (log10 of the determinand 7887 result). It is committed to the public
  repository by the pilot's bot, like the pilot's other data, but not shown on the site. After each weekly pilot run (`satellite_pilot.run`) and each refresher run
  (`refresh_lake_observations.run`, into its own research root), every new usable reading gets a row: site, scene,
  acquisition time, time read, model version, inputs (reading, brightness, IQR, mark) and the values of B0, A, C and the
  fallback. No request is added. The pilot's workflow commits the file with its other data. A shadow failure is
  printed and never changes a reading or the run record; it is not yet surfaced in the workflow summary, so a failing
  log would be noticed only in the job's output. The file is replaced whole on each write and left alone when nothing
  is new. A local pilot trial with `DIPCAST_PILOT_RUNS` set writes the log beside its scratch run record, never into the
  checkout. The site build does not copy it and no page reads it (checked by `tests/test_lake_chl_shadow.py`).
- **Which rows the 2028 read uses (clarified now, before any row exists):** the log holds every usable reading,
  including some the published file excludes (for example in low sun). The read uses only rows whose scene also passes
  the published file's quality rules (contract 1.1 and later). Refresher rows land in the operator's research root;
  if they are lost, the values can be recomputed from the frozen model and the published reading, brightness, IQR and
  mark, which 1.4 stores for every new reading.
- **Checked against the merged section "Develop promising work now":** inputs exist at reading time (1.4 measures
  them); acquisition and read times are logged; the log is its own versioned file, not the published reading or the
  run record the Lab publishes; the baseline and fallback are logged on the same readings; no request is added; the
  read is fixed in amendment 1 (paired 2027 samples, skill gain over the frozen baseline, not-worse margin −0.05,
  better at +0.03 with lower end above 0, at least 60 pairs at 10 lakes, on or after 1 February 2028).
- **Running:** nothing yet. The log starts with the first weekly pilot run after this PR merges (Mondays about 06:17
  UTC). Run on the existing pilot logs, the logger writes 10 rows for the 10 usable readings, with A and C empty
  because those readings predate 1.4's measurements; that is the expected behaviour.

## 5. Limitations

- **Seen data.** Every lab value was seen in #386 and the signal on these pairs in #626; the candidate list was written
  after #626. Out-of-fold fitting controls the candidates' own parameters, not that history.
- **Partial read** (labelled `partial` in the published file). 183 of 207 paired scenes and none of the 657 other
  nearby scenes. E is untested and the all-sample results rest on paired scenes only.
- **Small, clustered sample.** 183 pairs at 38 lakes; intervals are by lake and wide (A's held-out-lake gain runs from
  +0.005 to +0.306). The season and forward conditions are point estimates by design; their intervals include zero for
  A and, on the forward years, for C.
- **The shadow's pairs depend on reads at the 38 points.** The weekly pilot reads five bathing sites, which are not the
  chlorophyll points; its rows check that the logger works but will add few or no pairs to the 2028 read.
- The lab outcome is EA acetone-extract chlorophyll (determinand 7887), spectrophotometric, phaeopigment correction
  not stated. Nothing here is a chlorophyll measurement, or about algae, toxins or whether water is safe.

## 6. Next steps and blockers

- **Ethan merges #626** (this PR); the shadow log then starts on the next pilot run. Nothing in it is shown anywhere.
- **Blocker, named:** pairs for the 2028 read need refresher runs at the 38 chlorophyll points from May 2027, on a
  runner the register already lists as open. The refresher logs shadow rows into its own research root today; who runs
  it weekly, and where, is a LABS or Ethan decision.
- **Next comparison, development (owner: this session family, Claude):** a candidate that uses the lake's own history (the lake's training mean plus a
  satellite anomaly, A's quality rule kept), against both B0 and the lake-mean reference, on the same holdouts. The
  lake's own mean beat every candidate here on seasons and years, so this is the comparison that says whether the
  satellite adds anything at a lake already sampled.
- **Blocker (amendment 2), data:** the 24 unread paired scenes and the 657 nearby scenes. Earth Search's S3 dropped
  two connections in 13 minutes today with no HTTP status, and the protocol ends a fetch on the second. Testing E,
  and the coverage question, needs a new fetch under a protocol that allows a no-response drop to be retried once per
  request, stated before it runs. Owner: this session family (Claude); no decision of Ethan's is needed.
- **Not archived:** B (not supported) and D (inconclusive) stay open. D's next test is a wider floor grid (above
  0.020) on the same holdouts; B needs a noise model that adds something beyond the low-signal mark.
