# Low-signal readings against lab chlorophyll: does contract 1.4's rule change the relationship? (exploratory)

Written 5 November 2026, protocol first, before any band pixel of these scenes was fetched. Follow-up to the
[shore-margin outlier record](SATELLITE-SHORE-OUTLIERS-2026-11.md) ([#623](https://github.com/ethanbuckley/swimsignal/pull/623))
and contract 1.4 ([#624](https://github.com/ethanbuckley/swimsignal/pull/624)), on the pairs of the
[lab chlorophyll test](LAKE-CHLOROPHYLL-NDCI-TEST-2026-10.md) ([#386](https://github.com/ethanbuckley/swimsignal/pull/386)).
Bounded exploration under the [research workflow](RESEARCH-WORKFLOW.md), SAT-OBS. **Exploratory, on seen data:** the
207 pairs and their lab values were examined and scored in #386, and the low-signal thresholds were fixed in #624 on
76 bathing-lake scenes before any lab pair was looked at with them. It changes no reading, no published file, no
forecast and no protocol; the lab chlorophyll test's verdict stands and the 2027 evaluation stays frozen. A satellite
index is not a toxin measurement, an algae forecast or swimming clearance, and nothing here says a flagged or unflagged
reading is accurate. The lab outcome is EA acetone-extract chlorophyll (determinand 7887), spectrophotometric,
phaeopigment correction not stated.

## 1. The question

Contract 1.4 marks a reading *low-signal* when the clear core's median B4 + B5 reflectance is below 0.015 or the
interquartile range (IQR) of pixel NDCI over the clear core is at least 0.10, and shows a note on `/lakes.html`. The
outlier record found such scenes behind the largest shore-margin shifts, and said the test that would settle whether
they are also *worse against lab chlorophyll* belongs to the 2027 protocol review, on readings made after the flags were
fixed. This check asks the narrower, cheaper question now: **on the 207 pairs the lab chlorophyll test already made,
does removing the pairs the rule would flag change the NDCI-to-lab-chlorophyll relationship, and does the inner-core
reading change it?** It cannot replace the 2027 test: the pairs are seen, and the thresholds, though fixed on other
scenes, are being met by lab data for the first time here.

## 2. What was known before the protocol (offline, no fetch)

- **The pairs can be made again.** From the test's read-only caches (`features.parquet`, `values.parquet`, `sizes.json`,
  the chosen points) by the test's own functions (`chl_protocol.prepare_samples`, `protocol.one_per_date`,
  `chl_protocol.pair`): 207 pairs at 38 lakes, pooled Spearman 0.501672568828408, equal to `score.json`'s. Each pair's
  scene is known (207 distinct point-scenes; 108 of them are items two points share, Windermere's two basins mostly).
  Lake types among the pairs: 92 deeper, 89 shallow, 26 with no depth.
- **No band pixel of these scenes is cached.** Only the scene classification windows and the cores were kept.
- **The cost, from the test's own stage-1 ledger** for these 207 point-scenes' B04 and B05 reads (a shared item's cost
  split between its points): **905 requests and 482,287,829 bytes (460 MiB)**, 4.37 requests and 2.22 MiB a scene;
  unshared scenes took 4 to 6 requests (median 4) and 1.25 to 5.67 MiB. The outlier record's 26 scenes cost 4.5
  requests and 2.8 MiB each. So all 207 fit the one-run cap below with about 10% of requests and 23% of bytes to spare.
- **What the second band sample said about the flag's rate:** dark-or-spread marked 10 of 50 bathing-lake scenes
  (20%). The chlorophyll points include deep, clear Cumbrian lakes (Wast Water, Ennerdale, Ullswater, Coniston,
  Windermere), where water is dark, so the share here may be higher, and higher at deeper lakes than shallow ones.
- Nothing else: no brightness, IQR or inner-core reading of any of these scenes has been computed.

## 3. Protocol (fixed before the fetch)

**Scenes.** All 207 point-scenes of the test's pairs (section 2), one fetch of B4 and B5 each through the existing
reader, same scale, offset and mask rules as the test. Read order: points in a seeded order, each point's scenes in a
seeded order, one per point in turn (seed 20261105, `read_order`), so that a run the cap stops early still holds
scenes from every point. No TCI.

**Reads.** `python scripts/satellite_low_signal_chl.py prepare|read|report --out DIR`. One run, at most **1,000
requests and 600 MiB** (estimate 905 and 460 MiB), no account, stop on the first HTTP error, cap or mismatch, no
retry; a partial run stays partial and the analysis is on the pairs read, labelled partial. SHA-256 over every cached
input file (25,234 files: the features, values, score, sizes, cores, items and scene classification windows) before
selection, before the fetch, after it and at the report; the features and values files must also hash to the test's
committed values. Every recomputed core reading must equal the cached one within 1e-6. Pixels stay in scratch; the
published file `data/research/satellite_low_signal_chl_2026_11.json` holds values only.

**Per pair**, from contract 1.4's own code, imported: `refresh_lake_observations.signal_quality` (core brightness,
index IQR, inner-core pixels, inner-core reading) and `export_lake_observations.low_signal` (the rule). Also whether
the dark rule, the spread rule or both fired.

**Variants** (reading, rows):
- A: core reading, every pair (the test's rows; must give its 0.5017);
- B: core reading, unflagged pairs only;
- C: inner-core reading, every pair with one (a core too thin for inner pixels has none; counted);
- D: inner-core reading, unflagged pairs with one.

**Measures**, on each variant (`measures`):
- the **pooled Spearman** of reading with log10 chlorophyll, with the test's cluster bootstrap by lake (2,000 draws,
  seed 20261026, 2.5th to 97.5th percentile): the test's primary statistic, condition 1;
- the **within-lake Spearman**: the same, after each lake's mean reading and mean log10 chlorophyll are taken off, at
  lakes with at least two pairs, so it cannot come from one lake being greener than another; interval from the same
  draws;
- description: the median per-lake Spearman over lakes with at least 3 pairs; the test's four conditions recomputed on
  the variant's rows. They decide nothing: the test is not rerun and its verdict is not re-decided.

**Differences, paired** (`paired_difference`): B minus A (the flag's effect on the core reading), D minus C (its effect
on the inner-core reading) and C minus A on the same pairs (inner-core in place of core). Each cluster-bootstrap draw
over the lakes scores both sides on the same drawn lakes, so the interval is of the difference, not of two overlapping
intervals.

**The share flagged** (`flag_share`): pairs flagged, by rule, by lake type and season; lakes with every pair flagged;
lakes left with at least 3 unflagged pairs.

**Sizes in words**, descriptive, not significance thresholds: a change in a Spearman below **0.03** in absolute value is
"no change", 0.03 to 0.10 "a small change", 0.10 or more "a large change" (the test's interval was 0.37 wide; 0.03 is
about a twelfth of it). A flagged share below **10%** is "rare", above **30%** "frequent".

**The pre-stated reading**, produced by `reading_in_words` from the figures, in this order:
1. If the flagged share is over 30%: the rule as fixed marks a large part of these pairs, so it is too broad to serve
   as an exclusion at these points, whatever the correlations do. Under 10%: rare, its effect bounded. Otherwise:
   common, not frequent.
2. On B minus A: if both the pooled and the within-lake Spearman rise by at least 0.03 and at least one paired interval
   excludes zero, the flagged readings are noise relative to lab chlorophyll on these pairs, and the next step is to
   write the exclusion into the 2027 shallow-lake protocol as a pre-registered rule, judged on 2027 pairs; nothing
   adopted now. If both changes are under 0.03 in absolute value: the flag does not change the relationship; it stays a
   display note and the 2027 review needs no exclusion rule from it. If either falls by 0.03 or more: the flag removes
   pairs that carry information about lab chlorophyll; the thresholds need review before 2027 and the note's wording
   should not call a flagged reading unreliable in general. Anything else: mixed, inconclusive, no next step beyond the
   2027 review.
3. On C minus A: a pooled difference under 0.03 means the margin makes no difference to the relationship on these
   pairs; otherwise its direction is noted for the 2027 margin review, nothing adopted.
4. D minus C is reported in the same size words.
5. Nothing here is a claim about algae, toxins or whether water is safe, and the test's verdict is unchanged.

**Expected, stated now (guesses).** Flagged share 15 to 35%, higher at deeper lakes. Removing flagged pairs may *lower*
the pooled Spearman: dark scenes at clear, low-chlorophyll deep lakes give strongly negative readings that line up with
low chlorophyll by darkness, not by pigment, so they may be helping the pooled rank agreement for the wrong reason;
the within-lake Spearman should rise if the flagged readings are noise. Inner-core against core: no change (the band
samples' median shift was 0.004).

**Not claimed:** that the flag detects algae, that a flagged reading is wrong or an unflagged one right, that the
lab chlorophyll test passes or fails under any variant, or that any threshold is right; the 2027 protocol review
decides what to do with the flag, on 2027 pairs.

### Amendment 1 (5 November 2026, 23:56 UTC, written before the resumed run)

The first run (protocol commit `02c386ff`, 23:47 UTC; fetch from 23:52:28 UTC) stopped after 51 scenes at the 52nd,
the B05 read of `S2A_T30UXD_20260709T112128_L2A` at Swanholme Lakes (AN-SWANHWFD): the server dropped the connection
without a status ("Server disconnected without sending a response"), not an HTTP 429, 5xx or other status. 225
requests, 125,606,991 bytes (119.8 MiB), every completed response 206; fingerprint unchanged
(`8e2f4b20…3675321c`); all 51 recomputed readings equal the cached ones.

The protocol said one run, and that a partial run stays partial. 51 pairs are too few for the within-lake measure as
designed: the seeded order reads one scene per point first, so the 51 pairs sit at 38 lakes with at most two pairs
each, and the within-lake Spearman rests on 26 demeaned pairs (13 lakes) in variant A and 10 pairs in B. The design
was all 207 pairs, and the cost budget is 77% unspent. So this amendment allows **one resumed run** over the 155
scenes the first run never attempted (`resume` step), on the same ledger so the caps of 1,000 requests and 600 MiB
hold over both runs together. The failed scene is left out and counted: no request is retried. The reason is sample
size, not the direction of the partial figures, which are recorded here as they stood and kept in the published file
(`run1_partial`); the pre-stated reading, sizes and measures are unchanged. The amendment commit precedes the resumed run.

The first run's figures (51 pairs, 38 lakes): flagged 14 (27.5%; 9 dark and spread, 5 spread only; 8 of 26 at deeper
lakes, 3 of 18 at shallow, 3 of 7 with no depth). A: pooled 0.385 [0.094, 0.628], within-lake 0.038 [−0.413, 0.548] on
26 pairs. B (37 pairs, 32 lakes): pooled 0.527 [0.157, 0.741], within-lake −0.636 on 10 pairs (59 of 2,000 draws
without value). B − A paired: pooled +0.142 [−0.058, +0.352], within-lake −0.674 [−1.167, +0.405] (65 draws without
value). C − A: pooled −0.002 [−0.028, +0.022]. D − C: pooled +0.136, within-lake −0.674. The pre-stated reading on
these: flagged share common; "removes pairs that carry information" (by the within-lake fall, on 10 pairs); margin
makes no difference.

## 4. Results (6 November 2026)

**Runs.** Two, under amendment 1: 51 scenes (23:52 to 23:53 UTC, 225 requests, 119.8 MiB, stopped by a dropped
connection) and 155 scenes (23:57 to 00:01 UTC, 672 requests, 344.0 MiB). Together **897 requests and 486,293,124 bytes
(463.8 MiB)**, every completed response 206, no retry, under the 1,000-request and 600 MiB caps; the estimate was
905 and 460 MiB. One scene is unread (Swanholme Lakes, sample 10 July 2026), so **206 of the 207 pairs** are in the
results. The SHA-256 over the 25,234 cached input files was `8e2f4b200b05f67fcafc0026ba5a663205fdcbaf9a4ece7797f41daf3675321c`
before selection, before and after each run and at the report; the features and values files hash to the test's
committed values. All 206 recomputed core readings equal the cached ones (largest difference 0). Every pair has an
inner-core reading (the thinnest core has 9 inner pixels). The protocol commit (`02c386ff`, 23:47 UTC) precedes the
first fetch and the amendment commit (`c86bd5d2`, 23:56 UTC) precedes the resumed one; neither is independently
timestamped outside this work session. Per-pair values and every figure below:
[`data/research/satellite_low_signal_chl_2026_11.json`](../data/research/satellite_low_signal_chl_2026_11.json)
(the first run's own figures under `run1_partial`).

### 4.1 The share flagged

**43 of 206 pairs (20.9%)** would carry the low-signal mark: 19 dark and spread, 21 spread only, 3 dark only. By lake
type: deeper 26 of 92 (28%), shallow 11 of 89 (12%), no depth 6 of 25. By season 4 of 19 (2021), 7 of 43, 10 of 41,
9 of 38, 13 of 65 (2026). No lake loses every pair; 25 of 38 lakes keep at least 3 unflagged pairs. Most flagged
pairs are at Windermere's south basin (4 of 9), Wast Water (4 of 5), Wroxham Broad (3 of 8) and Tunstall Reservoir
(3 of 9); 27 lakes have at least one. The flagged readings are lower (median −0.049 against +0.067 unflagged) and
their lab chlorophyll lower too (median log10 0.83 against 1.18, about 7 against 15 µg/l); every one of the 10
readings below −0.2 is flagged. Core brightness over the 206 scenes: quartiles 0.032, 0.052, 0.081.

### 4.2 The measures

| Variant | Pairs (lakes) | Pooled Spearman [95%] | Within-lake Spearman [95%] (pairs) | Per-lake median ρ (lakes ≥ 3 pairs) |
|---|---|---|---|---|
| A: core reading, every pair | 206 (38) | 0.501 [0.298, 0.667] | 0.292 [0.144, 0.430] (203) | 0.43 (30; 24 positive) |
| B: core reading, unflagged | 163 (38) | 0.580 [0.379, 0.729] | 0.395 [0.205, 0.568] (155) | 0.50 (25; 19 positive) |
| C: inner-core reading, every pair | 206 (38) | 0.505 [0.302, 0.666] | 0.289 [0.141, 0.427] (203) | 0.45 (30; 24) |
| D: inner-core reading, unflagged | 163 (38) | 0.581 [0.379, 0.727] | 0.396 [0.206, 0.572] (155) | 0.50 (25; 19) |

A reproduces the test on 206 of its 207 pairs (0.501 against 0.502; the lower end 0.298 against 0.2997).

**Paired differences** (cluster bootstrap of the difference itself):

| Difference | Pooled Spearman | Within-lake Spearman |
|---|---|---|
| B − A: the flag's effect, core reading | **+0.080** [−0.023, +0.176] | **+0.102** [−0.037, +0.255] |
| D − C: the flag's effect, inner-core reading | +0.076 [−0.027, +0.172] | +0.107 [−0.034, +0.262] |
| C − A: inner-core in place of core, same 206 pairs | +0.004 [−0.005, +0.012] | −0.003 [−0.018, +0.012] |

**The pre-stated reading, as the code produced it:**
1. "Flagged share 21%: common, not frequent."
2. "Mixed: pooled +0.080, within-lake +0.102 (a small change and a large change, with no paired interval excluding
   zero): inconclusive on these pairs; no next step beyond the 2027 review."
3. "Inner-core against core reading, same pairs: pooled Spearman differs by +0.004, under 0.03: the margin makes no
   difference to the relationship on these pairs."
4. "With the inner-core reading the flag's effect is pooled +0.076, within-lake +0.107 (a small change, a large change)."
5. "Nothing here is a claim about algae, toxins or whether water is safe, and the lab chlorophyll test's verdict is
   unchanged."

Both measures rose by at least the pre-stated 0.03 when the flagged pairs were removed, in the direction the flag
would predict if those readings are noise, but neither paired interval excludes zero, so under the rule written down
beforehand the result is **mixed, not shown**. The expectation written beforehand (section 3) was wrong in one
respect: removing flagged pairs raised the pooled Spearman rather than lowering it. The flagged readings are low at
low-chlorophyll lakes, so taking them out did not break the between-lake ranking; it tightened it.

**Description, decides nothing:** the test's four conditions recomputed on each variant's rows. On A they reproduce
the test (condition 1 misses by 0.002 on 206 pairs; placebo beaten in all 200 shuffles; calibration skill 0.158
[−0.060, 0.324], "Too uncertain"; shallow lakes "Better", deeper "Too uncertain"). On B, the unflagged pairs, all
four hold as figures: pooled 0.580 with lower end 0.379; placebo 95th percentile 0.539, 0 of 200 at or above 0.580;
leave-one-lake-out calibration skill 0.364 [0.150, 0.539], "Better"; shallow 0.575 [0.370, 0.728] "Better", deeper
0.092 [−0.275, 0.362] "Too uncertain". **This is not a pass.** B is a subset chosen by a rule applied to seen pairs,
after the test was scored; the test's rules say such a subset needs new data (as the shallow-lake subset did on 27
October). It says what to expect on 2027 pairs, and what to pre-state.

### 4.3 What this means for the reading

1. The low-signal mark, fixed on bathing-lake scenes before any lab pair was seen with it, marks about a fifth of the
   lab-paired readings, more at deeper lakes. It does not remove the signal: every measure of agreement with lab
   chlorophyll is higher without the flagged pairs, by 0.08 to 0.10 in Spearman, with intervals that include zero.
2. The flagged readings are not random noise around the right value: they sit low (median −0.05, all ten readings
   below −0.2) at lakes with low chlorophyll. That is the dark-water mechanism of the outlier record, and it is why the
   pooled rank agreement did not fall when they were removed. A low index in a dark scene is not evidence of low
   chlorophyll and must not be read as such; the display note's wording holds.
3. The inner-core reading changes nothing against lab chlorophyll on these pairs (+0.004). The one-pixel margin stays.

## 5. Limitations

- **Seen data.** The pairs, their lab values and the test's score were known before this check; the thresholds were
  fixed on other scenes, but this is the first time they met lab data, and the variants were examined once. Nothing
  here is confirmatory. The recomputed conditions on B are description.
- **One run became two.** The first run stopped on a dropped connection at scene 52; amendment 1, recorded before the
  resume, added a second run over the unattempted scenes and left the failed scene out. The resume was decided on
  sample size (51 pairs at one or two per lake) with the partial figures already seen; they are kept in the record and
  the file so a reader can judge that. One pair of 207 is missing.
- **The paired intervals include zero.** With 43 flagged pairs the paired difference has a 95% interval about 0.2 wide
  in the pooled and 0.3 in the within-lake Spearman. These pairs cannot show a change of 0.08 to 0.10; 2027 pairs at
  the same rate would need to be several times as many to do so, if the effect is real.
- **The within-lake measure** takes each lake's mean off, so it mixes seasons within a lake; the test's placebo keeps
  lake and season. Both are reported.
- **The flagged share** is for scenes within a day of a lab sample in May to September at 38 monitoring points; the
  rate at the bathing-water lakes or out of season is not measured here.
- No pixel of these scenes was inspected by eye; the mechanism statement rests on the outlier record's pictures of
  other scenes and on the brightness figures here.
- The lab outcome is EA acetone-extract chlorophyll (determinand 7887), spectrophotometric, phaeopigment correction
  not stated; nothing here says anything about algae, toxins or whether water is safe.

## 6. Next step

Under the pre-stated reading, no step beyond the 2027 shallow-lake protocol review (before 1 May 2027), which already
tests the flags against lab chlorophyll on readings made after contract 1.4. What this check adds to that review:
- the direction and size to pre-state: removing flagged pairs raised the pooled Spearman by 0.08 and the within-lake
  Spearman by 0.10 on seen 2021-2026 pairs; a 2027 margin of usefulness should be set below that, and the flagged
  share expected is about a fifth (more at deeper lakes);
- the exclusion is a candidate secondary analysis for the 2027 statement, pre-registered there, not a change to the
  display rule or to any reading now;
- the inner-core reading need not be carried as a variant in that review: it made no difference here.

Nothing is adopted, no threshold changes, the note on `/lakes.html` stays as contract 1.4 wrote it, and the lab
chlorophyll test's verdict ("fails as stated; promising, not validated") is unchanged.
