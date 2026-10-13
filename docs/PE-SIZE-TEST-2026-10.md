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

Not yet run.
