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

## 4. Results

To be written after the run.

## 5. Limitations

To be written after the run.

## 6. Next step

To be written after the run.
