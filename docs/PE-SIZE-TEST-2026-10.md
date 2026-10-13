# Population equivalent as each overflow's spill size: the test, stated before any run

Written 13 October 2026, before any E. coli score was computed for the option below. It is committed
and pushed before the first run. Results go below the line at the end; nothing above it changes after
a result is seen.

## Why

An overflow's weight at a spot is its dilution times its die-off. The default dilution, `length`, is
(network length above the overflow + 5 km) / (network length above the spot + 5 km). So an outfall on
a short ditch beside a big river gets almost nothing, though its spill reaches the river whole (handoff,
section 4A). Three replacements have failed their stated tests: flow dilution and urban area (#166,
#172) and a junction rule (#181). Spill hours as each overflow's size failed too (#197, draft).

#172 said what a fair test of a size needs: a size per overflow that does not come from built-up area,
a placebo control (the same sizes reshuffled), and a statement that treats the sites as already seen.
The handoff's remaining candidate is population equivalent (PE), the size of the population an overflow
serves, from the EA's consents. Ethan allowed offline, test-only use of the consents on 13 Oct 2026.

## The source, and a change of field: PE is not in it

The source is the EA's *Consented Discharges to Controlled Waters with Conditions*, the quarterly
extract on data.gov.uk:

- file `Consented Discharges to Controlled Waters with Conditions.zip`, 57,075,591 bytes, SHA-256
  beginning `6efcacf3`, downloaded 13 Oct 2026 from
  `https://environment.data.gov.uk/api/file/download?fileDataSetId=a54fdea1-7769-4b22-a518-10d51fed6f33&fileName=Consented%20Discharges%20to%20Controlled%20Waters%20with%20Conditions.zip`;
- it holds one Access database (extract of 5 Aug 2026) with tables `consents_active`, `consents_all`,
  `Effluents` and `Determinands`.

**It has no population equivalent.** No column, determinand or unit names population, persons or PE.
Checked by listing every column of the four tables and searching every determinand name and unit.

The nearest field it has is the consented **dry weather flow (DWF)**, in m³/d: the `Effluents` table's
`DWF (m3_d)` and the determinand `FLOW : DRY WEATHER :- {DWF}`. A works' DWF is set from the
population it serves (DWF = P·G + I + E: population times water use per head, plus infiltration and
trade flow), so it is a flow-based measure of the same thing PE measures. This test uses DWF as the
PE measure. The candidate is named `dwf` below. If Ethan wants PE itself, it needs another source
(for example the treatment works' PE in the Urban Waste Water Treatment returns), and a new statement.

**Licence.** The file is under the Environment Agency Conditional Licence: internal or personal use
only, and "you must not publish the Information in any way". It sits in a scratch folder outside the
repo. Nothing from it goes into this repo, a commit, a PR or the site: no per-overflow values, positions,
permit numbers or joined tables. The harness reads it from a path given as an argument. This document
and the PR give aggregates only: the join rate, shares, and the test's measures. The median DWF and
other summaries of the values themselves are left out.

## The option

No model code changes. Mode `urban` reads each overflow's size from `overflow_urban_area.parquet`
(`transport.urban_spill_m3s`). The test writes that file with DWF in place of built-up area
(`scripts/pe_size_eval/make_variants.py`):

- `D_i` = overflow i's DWF in m³/d, from the join below.
- Its size is `a_i = 0.512 × D_i / median(D)`, in the file's km² units, the median taken over the
  overflows given a DWF.
- `transport.urban_spill_m3s` clips `a_i` to [0.1, 6.0] and gives the spill flow
  `Q_i = Q_SPILL_M3S × clip(a_i) / 0.512`. So the median sized overflow spills `Q_SPILL_M3S`, as in
  `flow`, and the others spill in proportion to their DWF, from 0.195 to 11.7 times that.
- The dilution is `Q_i / (Q_i + Q50 at the spot)`, with `Q50 = q50_m3s(catchment_km2(network length
  above the spot))`, as in `flow` and `urban`. The weight is that dilution times the die-off, unchanged.
- An overflow with no DWF is left out of the file and takes the median, `Q_SPILL_M3S`: the `flow` size.

### The join

Fixed now, before any run, and not tuned afterwards.

- **Candidates:** rows of `consents_active` whose effluent type is a water company's sewer storm
  overflow, pumping station overflow, or storm overflow / storm tank at a treatment works. Each is placed
  at its outlet grid reference, or its effluent's if the outlet has none.
- **A candidate's DWF:** its own effluent's DWF (`Effluents`, else the DWF determinand, converted to
  m³/d). If it has none, the largest DWF of any effluent on the same permit. That is how a storm tank
  at a works gets the works' DWF.
- **Matching:** each overflow takes the nearest candidate within 100 m of either of its positions (the
  overflow table's and its latest annual return's grid reference). If another candidate lies within
  10 m of the nearest one's distance and has a different DWF, the overflow is left unjoined.
- **Unjoined overflows,** and joined ones with no DWF, take the median size.

### Placebos

`pd01` to `pd20`: the same DWF sizes permuted across the same sized overflows, numpy `default_rng(k)`.
Unsized overflows stay at the median in every placebo. So a placebo keeps the spread of sizes and moves
only which overflow has which.

Nothing else differs between runs: velocity `fixed`, lake path `lake`, lake near field off (main's
defaults).

## Seen before writing

From the consents, the overflow table and the annual returns only. No E. coli figure for this option,
or for any run on these inputs, was seen.

- **Inputs.** Main `25e735a`. The overflow table is rebuilt on network `b5724303` with
  `load_overflows(net, rebuild=True)`, from the `state` snapshot #205 used (SHA-256 `eaea1f91...`):
  14,631 overflows, SHA-256 beginning `e6ef0459`. Rain is a frozen view of the shared cache: 3,658 files, the
  same set #205 used.
- **Join** (aggregates; the per-overflow table stays in the scratch folder):
  - 13,341 of the 14,631 overflows (91.2%) join a consent outlet. 411 (2.8%) are left unjoined as
    ambiguous, and 879 (6.0%) have no candidate within 100 m.
  - The match is exact for most: the median and the upper quartile of the match distance are 0 m, and
    the 90th percentile is 8.5 m. The annual returns' grid references appear to come from the consents.
  - **3,143 overflows (21.5%) get a DWF**, and so a size of their own. The other 11,488 take the median.
    By company the sized share runs from 5.5% (Dŵr Cymru's English overflows) to 43.7% (Wessex).
  - Of the sized overflows, 19.3% sit at the floor of the clip and 15.5% at the cap.
- The DWF sizes are close to independent of spill hours (Spearman rho 0.087, over the 3,051 sized overflows with spill hours) and of the long-term
  average spill count (0.053), two of the spill model's three inputs. They go with the built-up share
  (rho 0.520), which #172 found pointed the wrong way.

Earlier results on the same samples, all seen: #166 and #172 (`length`, `flow`, `urban` and placebos),
#181 (junction and named snap), #187 (lake near field), #197 (spill hours and placebos), and #205's refit
on this network.

## Reasons to expect little, stated now

- Most overflows get no DWF and sit at the median: in effect this tests the sizes of works storm tanks
  and a few network overflows against one size for the rest. If the overflows upstream of the sampled
  sites are mostly unsized, the test has little power either way.
- A works' DWF says how big the works is, not how much its storm tank spills. A large works may have a
  large tank and spill less often.
- The spread is wide, and a share of the sized overflows sits at each clip.
- The 32 or so sites have been looked at in five tests. A pass here is another look at the same
  samples; the 2027 season would be its real test (docs/PREREGISTRATION-2027.md, section 12).

## The runs

`scripts/pe_size_eval/`, #197's harness with the variant names changed:

- `export_consents.py` turns the Access file into parquet tables, in the scratch folder (it needs the
  `access-parser` package, from a separate environment). `make_variants.py` writes the size tables
  there.
- The E. coli chain: `validate_ecoli.py`, `replay_ecoli_leads.py`, `validate_ecoli_combined.py`,
  `train_ecoli.py`, then `paired.py prep` (held-out predictions per sample).
- Each run in its own scratch `DIPCAST_ROOT`, copied from one data folder; rain from the frozen cache
  only; every outgoing network connection refused and counted; one run at a time.
- 23 runs: `length` (the default), `flow`, `dwf`, and `pd01` to `pd20`.
- Measures per run (`summary.py`): LOYO, LOSO and forward Brier of the full model; LOYO AUC, all and
  rivers; cross-site rho.
- Paired 95% intervals, 2,000 resamples, seed 1 (`paired.py compare`): site-weeks for Brier and AUC,
  sites for cross-site rho. `dwf` against `length`, and `dwf` against `flow`. They pair on the samples
  that both runs keep: a run drops a whole site when more than 0.1 of its weight comes from overflows
  without rain data, and the sizes move that weight (#166's rule, as #197 found it needed).
- **The samples:** the bathing-water E. coli samples of `validate_ecoli.py` (2,165 rows at 38 bathing
  waters in #205), of which `train_ecoli.py` keeps those with rain, a forecast and exposure (1,502 at
  31 sites under `length` in #205).
- **A check before any result is read:** the `length` run must reproduce #205's `train_ecoli` (1,502
  samples; LOYO Brier 0.0938 within 0.001). If it does not, I stop and report.

## What counts as passing

All five must hold, as in #197. `scripts/pe_size_eval/judge.py` applies them.

1. **Information (against its own placebos).** On at least three of four measures (LOYO Brier, LOYO AUC
   all, LOYO AUC rivers, cross-site rho), at most 1 of the 20 placebos is at least as good as `dwf`.
   Each run is measured on its own samples. `common.py` also reports this condition on the samples all
   23 runs keep, beside the stated result; it does not replace it.
2. **Brier against the default.** The upper end of the interval of the change (`dwf` minus `length`) is
   at most +0.0005 for LOYO, LOSO and forward.
3. **AUC against the default.** The lower end of the interval of the change is at least −0.005, over
   all sites and over rivers (LOYO).
4. **Cross-site rho against the default.** The lower end of the interval of the change is at least
   −0.05.
5. **Lakes.** The upper end of the interval of the LOYO Brier change over lake samples is at most
   +0.0005.

The conditions and margins are #197's, unchanged. #197's two harness fixes (pairing on shared samples,
and the placebo count "at least as good") are in from the start.

What follows:
- **All five hold:** DWF becomes a candidate. It stays off. Using it on the site needs a licence
  decision first, since the consents may not be published, and a site built from them would publish
  derived values. Ethan decides. The 2027 season would test it as a candidate.
- **Any fails:** it stays off, and the result is recorded here. `dwf` against `flow` is reported either
  way, as the effect of the sizes alone.

If anything is changed after a result is seen, both results are kept and the change is stated.

---

## Results

Run on 13 October 2026, 13:28 to 15:58 BST, after the statement was pushed (`c262b11`, 12:28 UTC). One
harness change came between the statement and the first run, before any run: `queue.sh` takes an
optional `GATE` command that each run waits on (`c9d52d2`). It waited for free memory; it changes no
measure. Nothing above the line changed.

All 23 runs finished with 0 network attempts, one at a time. The largest single process peaked at 5.6 GB.

**The check held.** The `length` run reproduced #205's `train_ecoli`: 1,502 samples, LOYO Brier 0.0938.

All 23 runs kept the same 1,502 samples at 31 sites (212 over the limit). So the pairing rule and the
common-sample check had nothing to drop, and `common.py` gives the same table as the stated one.

### Verdict: fails. DWF stays off.

Conditions 1 to 4 fail; 5 holds. No model code changes. `judge.py` prints "VERDICT: fails".

### Condition 1: information against its own placebos. Fails.

| measure | `dwf` | `length` | `flow` | 20 placebos: lowest, median, highest | placebos at least as good as `dwf` | holds |
|---|---|---|---|---|---|---|
| LOYO Brier (lower is better) | 0.0934 | 0.0938 | 0.0916 | 0.0904, 0.0922, 0.0941 | 17 | no |
| LOYO AUC, all | 0.8038 | 0.8129 | 0.8075 | 0.8024, 0.8109, 0.8212 | 19 | no |
| LOYO AUC, rivers | 0.7357 | 0.7470 | 0.7384 | 0.7324, 0.7474, 0.7664 | 19 | no |
| cross-site rho | 0.551 | 0.763 | 0.613 | 0.496, 0.667, 0.787 | 18 | no |

Holds on 0 of 4; it needs 3. On every measure, `dwf` is worse than at least 17 of 20 reshuffles of
its own sizes.

### Conditions 2 to 5: `dwf` against `length`, paired

On all 1,502 samples. Change is `dwf` minus `length`, 95% interval.

| condition | measure | `length` | `dwf` | change | bar | holds |
|---|---|---|---|---|---|---|
| 2 | LOYO Brier | 0.0938 | 0.0934 | −0.0004 [−0.0025, +0.0015] | upper ≤ +0.0005 | **no** |
| 2 | LOSO Brier | 0.0933 | 0.0923 | −0.0009 [−0.0031, +0.0011] | upper ≤ +0.0005 | **no** |
| 2 | forward Brier (997 samples) | 0.0852 | 0.0841 | −0.0011 [−0.0048, +0.0024] | upper ≤ +0.0005 | **no** |
| 3 | LOYO AUC, all | 0.8129 | 0.8038 | −0.0091 [−0.0168, −0.0016] | lower ≥ −0.005 | **no** |
| 3 | LOYO AUC, rivers (907) | 0.7470 | 0.7357 | −0.0113 [−0.0235, +0.0005] | lower ≥ −0.005 | **no** |
| 4 | cross-site rho (31 sites) | 0.763 | 0.551 | −0.211 [−0.470, +0.032] | lower ≥ −0.05 | **no** |
| 5 | LOYO Brier, lakes (595) | 0.0262 | 0.0264 | +0.0002 [+0.0000, +0.00048] | upper ≤ +0.0005 | yes |

### `dwf` against `flow`: the sizes alone

On all 1,502 samples. Change is `dwf` minus `flow`.

| measure | `flow` | `dwf` | change |
|---|---|---|---|
| LOYO Brier | 0.0916 | 0.0934 | +0.0019 [+0.0007, +0.0031] |
| LOSO Brier | 0.0905 | 0.0923 | +0.0018 [+0.0005, +0.0031] |
| forward Brier (997) | 0.0819 | 0.0841 | +0.0022 [+0.0006, +0.0039] |
| LOYO Brier, rivers (907) | 0.1344 | 0.1374 | +0.0030 [+0.0010, +0.0051] |
| LOYO AUC, all | 0.8075 | 0.8038 | −0.0037 [−0.0083, +0.0006] |
| LOYO AUC, rivers | 0.7384 | 0.7357 | −0.0027 [−0.0098, +0.0043] |
| forward AUC | 0.8041 | 0.7908 | −0.0133 [−0.0218, −0.0045] |
| LOYO Brier, lakes (595) | 0.0263 | 0.0264 | +0.0001 [−0.0001, +0.0003] |
| cross-site rho (31 sites) | 0.613 | 0.551 | −0.061 [−0.212, +0.079] |

### What this shows

Established, from the tables above:
- DWF fails the stated test on four of five conditions. It stays off, and nothing in the model changes.
- DWF sizes do worse than one size for every overflow (`flow`): Brier is worse on LOYO, LOSO and
  forward, with each interval above zero.
- They also do worse than 17 to 19 of 20 random reshuffles of the same sizes, on every measure. So the
  sizes do carry information, but they point the wrong way: giving the bigger spills to the
  overflows with the bigger consented DWF makes the forecast worse than giving them out at random.
- The join was not the limit. 91% of overflows matched a consent outlet, most at 0 m. The sizes reach
  21.5% of overflows; the rest took the median, as stated.

Inferred, not tested:
- This is the same direction #172 found for built-up area, and the DWF sizes go with built-up share
  (rho 0.52). A big works or a big urban catchment does not mean more E. coli at the sampled spot.
  Possible reasons: big works have bigger storm tanks, and their spills are better diluted or settled
  before they reach a bathing water. None of this was tested.
- The sampled sites see mostly unsized overflows, which could weaken a real effect. It cannot turn one
  into a loss against every placebo, so it does not explain this result.
- Population equivalent itself was not tested, because the source has no such field. A works' PE and
  its DWF both scale with the population it serves, so PE would likely point the same way. That is an
  inference, not a result.

### Files

Outputs are in the run's scratch folder, not in the repo: `summary.csv`, `common.json`,
`paired_length_dwf.json`, `paired_flow_dwf.json`, `judge.json`, and per-run logs. The size tables and
the join table stay there too, since they hold values from the consents. Harness:
`scripts/pe_size_eval/`. Overflow table SHA-256 `e6ef0459…`, network `b5724303`, main `25e735a`. About
six minutes a run, 23 runs one at a time.
