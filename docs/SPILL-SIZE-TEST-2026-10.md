# Spill hours as each overflow's spill size: the test, stated before any run

Written 12 October 2026, before any E. coli score was computed for the option below. It is committed
and pushed before the first run. Results go below the line at the end; nothing above it changes after
a result is seen.

## Why

An overflow's weight at a spot is its dilution times its die-off. The default dilution, `length`, is
(network length above the overflow + 5 km) / (network length above the spot + 5 km). So an outfall on
a short ditch beside a big river gets almost nothing, though its spill reaches the river whole: Culham
STW had 0.005 before its join was checked by hand (#177), Benson STW has 0.006, Oxford STW 0.007. A
reviewer from Sheffield said the rule has "no logic" (handoff, section 4A).

The logical form is the spill's flow against the river's: `Q_i / (Q_i + Q50 at the spot)`. Mode `flow`
uses it with one spill size for every overflow. Mode `urban` gave each overflow a size from its share
of built-up area; it failed its test (#166), and #172 found the built-up shares point size the wrong
way (worse than all 20 random reshuffles of the same values). #172 also said what a fair test of a
size needs: a measure independent of built-up area, a placebo control, and a statement that treats
the sites as already seen.

The handoff names the next candidate: spill hours from the annual returns. Ethan asked for it to be
run (12 October 2026), after being told the reasons below to expect little from it.

## The option

No model code changes. Mode `urban` reads each overflow's size from `overflow_urban_area.parquet`
(`transport.urban_spill_m3s`). The test writes that file with spill hours in place of built-up area:

- `S_i` = the overflow's mean annual spill hours over 2021 to 2025, years with a value, from
  `annual_returns.parquet`.
- Its size is `0.512 x S_i / median(S)`, in the file's km² units. So the median overflow spills
  `Q_SPILL_M3S`, as in `flow`, and an overflow spills in proportion to its spill hours.
- `urban_spill_m3s` clips the size to [0.1, 6.0] km², as for the built-up areas: 0.195 to 11.7 times
  the median overflow's spill.
- An overflow with no spill hours is left out of the file and takes the median.
- `scripts/spill_size_eval/make_variants.py` writes it (`sh.parquet`) and 20 placebos
  (`ph01` to `ph20`): the same sizes permuted across the same overflows, numpy `default_rng(k)`.

Nothing else differs between runs: velocity `fixed`, lake path `lake`, lake near field off (main's
defaults).

## Seen before writing

From the annual returns and the overflow table only; no E. coli figure for this option was seen.

- The overflow table: built on main `204d2a1` from the `state` release's live snapshot (11 October
  2026, 18:16 UTC), 14,631 overflows, network key `ccc58f6b`, 10 checked joins. SHA-256 begins
  `f3c7ed7b`. `sh.parquet` begins `7d33d7bd`.
- 14,363 overflows (98.2%) have spill hours. The median is 42.1 hours a year; quartiles 4.8 and 195.2;
  712 have none.
- Under the clip, 29.3% of them sit at the floor and 11.7% at the cap.
- Spearman rho of `S_i` with the built-up share: −0.188 (#172 found −0.190 on its table).
- Spearman rho of `S_i` with `lta_spills`, one of the spill model's three inputs (`features.COVARIATES`:
  `lta_spills`, `spill_hours`, `edm_operational_pct`): 0.872.

Earlier results on the same samples, all seen: #166 and #172 (`length`, `flow`, `urban` and placebos,
on an older main), #181 (junction and named snap), #187 (lake near field, base LOYO Brier 0.09106).

## Reasons to expect little, stated now

- Spill hours measure how long an overflow spills, not how much. #172 said this of the same field.
- The spill model already takes spill hours and spill counts as inputs. An overflow that spills often
  already has a higher chance. Weighting it again by size counts the same information twice in part.
- The spread is wide and 41% of overflows sit at a clip.
- The 32 sites have been looked at in four tests. A pass here is a second look at the same samples;
  the 2027 season would be its real test (docs/PREREGISTRATION-2027.md, section 12, candidates).

## The runs

`scripts/spill_size_eval/` (run_variant.sh, queue.sh), PR #172's harness unchanged in method:

- The E. coli chain: `validate_ecoli.py`, `replay_ecoli_leads.py`, `validate_ecoli_combined.py`,
  `train_ecoli.py`, then `paired.py prep` (held-out predictions per sample).
- Each run in its own scratch `DIPCAST_ROOT`, copied from one data folder; rain from the cache only;
  every outgoing network connection refused and counted; one run at a time.
- 23 runs: `length` (the default), `flow`, `sh`, and `ph01` to `ph20`.
- Measures per run (`summary.py`): LOYO, LOSO and forward Brier of the full model; LOYO AUC, all and
  rivers; cross-site rho.
- Paired 95% intervals, 2,000 resamples, seed 1 (`paired.py compare`): site-weeks for Brier and AUC,
  sites for cross-site rho. `sh` against `length`, and `sh` against `flow`.

## What counts as passing

All five must hold. `scripts/spill_size_eval/judge.py` applies them.

1. **Information (against its own placebos).** On at least three of four measures (LOYO Brier, LOYO AUC
   all, LOYO AUC rivers, cross-site rho), at most 1 of the 20 placebos is at least as good as `sh`.
   This asks whether spill hours put the sizes on the right overflows, not only whether a spread helps.
2. **Brier against the default.** The upper end of the interval of the change (`sh` minus `length`) is
   at most +0.0005 for LOYO, LOSO and forward.
3. **AUC against the default.** The lower end of the interval of the change is at least −0.005, over
   all sites and over rivers (LOYO).
4. **Cross-site rho against the default.** The lower end of the interval of the change is at least
   −0.05.
5. **Lakes.** The upper end of the interval of the LOYO Brier change over lake samples is at most
   +0.0005.

Conditions 2 to 5 and their margins are the lake tests' (#176, #187). Condition 1 is #172's rule.

What follows:
- **All five hold:** spill hours become a candidate. A mode of its own is written, off by default, and
  Ethan decides whether it becomes the default. The 2027 season would test it as a candidate.
- **Any fails:** it stays off, and the result is recorded here. `sh` against `flow` is reported either
  way, as the effect of the sizes alone.

If anything is changed after a result is seen, both results are kept and the change is stated.

---

## Results

### Changes made after the per-run measures were seen, before any paired result

All 23 runs finished on 12 October 2026 (14:11 to 16:39 local), each with 0 network attempts. The paired
step then stopped: `paired.py` checks that both runs kept the same samples, and they did not. Before
running it again, three changes, committed before any paired result was computed:

1. **Pairing.** The runs keep different samples. A run leaves out a whole site when more than
   `MAX_MISSING_SHARE` (0.1) of its weight comes from overflows without rain data, and the sizes move
   that weight. Colwick Country Park (West Lake) is at 0.010 under `length` and 0.114 under `sh`, so `sh`
   leaves out its 44 samples (none over the limit). The placebos leave out up to three of River Avon at
   Queen Elizabeth Gardens (17 samples), River Severn in Shrewsbury (57), Wolvercote Mill Stream (55) and
   Colwick. `paired.py compare` now pairs on the samples that both runs keep. This is the rule of the
   #166 statement that this harness comes from; #172's runs all kept the same 1,546 samples, so its
   check was stricter than the rule.
2. **A bug in `judge.py`, fixed to match the statement.** Its condition 1 count was the wrong way
   round: it counted placebos at least as *bad* as `sh`. The statement, and the code's own comment, say
   at least as *good*. #172's judge counted "at least as bad" and said so; it is not affected.
3. **A check on condition 1, added (`common.py`).** Condition 1 as stated compares each run's measures
   on its own samples, which now differ. `common.py` recomputes condition 1 on the samples that all
   23 runs keep. Cross-site rho uses every site in every run, so it is unchanged. This check is
   reported beside the stated result; it does not replace it.

Seen before these changes: `summary.csv`, the per-run measures on each run's own samples.

### Verdict: fails. Spill hours stay off.

Conditions 1 and 4 fail; 2, 3 and 5 hold. No model code changes. `judge.py` prints "VERDICT: fails".

### Condition 1: information against its own placebos. Fails.

As stated, each run on its own samples (`length` 1,546, `flow` 1,529, `sh` 1,502, placebos 1,417 to 1,546):

| measure | `sh` | `length` | `flow` | 20 placebos: lowest, median, highest | placebos at least as good as `sh` | holds |
|---|---|---|---|---|---|---|
| LOYO Brier (lower is better) | 0.0917 | 0.0911 | 0.0880 | 0.0867, 0.0890, 0.0912 | 20 | no |
| LOYO AUC, all | 0.8197 | 0.8145 | 0.8142 | 0.8087, 0.8160, 0.8258 | 3 | no |
| LOYO AUC, rivers | 0.7621 | 0.7476 | 0.7403 | 0.7342, 0.7454, 0.7661 | 1 | yes |
| cross-site rho | 0.649 | 0.684 | 0.558 | 0.408, 0.583, 0.729 | 8 | no |

Holds on 1 of 4; it needs 3.

The check (`common.py`), on the 1,373 samples that all 23 runs keep (28 sites, 196 over the limit;
the four sites above left out):

| measure | `sh` | `length` | `flow` | 20 placebos: lowest, median, highest | placebos at least as good as `sh` | holds |
|---|---|---|---|---|---|---|
| LOYO Brier | 0.0908 | 0.0929 | 0.0905 | 0.0894, 0.0918, 0.0926 | 5 | no |
| LOYO AUC, all | 0.8252 | 0.8195 | 0.8149 | 0.8092, 0.8167, 0.8270 | 1 | yes |
| LOYO AUC, rivers | 0.7590 | 0.7449 | 0.7357 | 0.7342, 0.7414, 0.7617 | 1 | yes |
| cross-site rho | 0.649 | 0.684 | 0.558 | 0.408, 0.583, 0.729 | 8 | no |

Holds on 2 of 4. It fails either way. Each run's measures recomputed on its own samples equal
`summary.csv`'s, which checks the recomputation.

### Conditions 2 to 5: `sh` against `length`, paired

On the 1,502 samples both keep (Colwick's 44 left out). Change is `sh` minus `length`, 95% interval.

| condition | measure | `length` | `sh` | change | bar | holds |
|---|---|---|---|---|---|---|
| 2 | LOYO Brier | 0.0936 | 0.0917 | −0.0019 [−0.0042, +0.0003] | upper ≤ +0.0005 | yes |
| 2 | LOSO Brier | 0.0928 | 0.0906 | −0.0022 [−0.0046, +0.0001] | upper ≤ +0.0005 | yes |
| 2 | forward Brier (997 samples) | 0.0853 | 0.0821 | −0.0032 [−0.0072, +0.0004] | upper ≤ +0.0005 | yes |
| 3 | LOYO AUC, all | 0.8130 | 0.8197 | +0.0067 [−0.0017, +0.0151] | lower ≥ −0.005 | yes |
| 3 | LOYO AUC, rivers (907) | 0.7476 | 0.7621 | +0.0145 [+0.0002, +0.0299] | lower ≥ −0.005 | yes |
| 4 | cross-site rho (32 sites) | 0.684 | 0.649 | −0.036 [−0.299, +0.226] | lower ≥ −0.05 | **no** |
| 5 | LOYO Brier, lakes (595) | 0.0262 | 0.0263 | +0.0001 [−0.0004, +0.0004] | upper ≤ +0.0005 | yes |

### `sh` against `flow`: the sizes alone

On the 1,485 samples both keep (Colwick and Queen Elizabeth Gardens left out). Change is `sh` minus
`flow`.

| measure | `flow` | `sh` | change |
|---|---|---|---|
| LOYO Brier | 0.0905 | 0.0911 | +0.0006 [−0.0006, +0.0016] |
| LOSO Brier | 0.0894 | 0.0900 | +0.0006 [−0.0006, +0.0017] |
| forward Brier (980) | 0.0804 | 0.0811 | +0.0007 [−0.0007, +0.0021] |
| LOYO AUC, all | 0.8095 | 0.8196 | +0.0101 [+0.0031, +0.0179] |
| LOYO AUC, rivers (890) | 0.7403 | 0.7617 | +0.0214 [+0.0081, +0.0354] |
| LOYO Brier, lakes (595) | 0.0263 | 0.0263 | +0.0000 [−0.0002, +0.0002] |
| cross-site rho (32 sites) | 0.558 | 0.649 | +0.091 [−0.052, +0.260] |

### What this shows

Established, from the tables above:
- Spill hours fail the stated test. They stay off, and nothing in the model changes.
- On probability accuracy (Brier), spill hours do no better than random reshuffles of the same sizes:
  all 20 placebos are at least as good on each run's own samples, and 5 of 20 on the common samples.
  Against a single size for every overflow (`flow`), Brier is no better either.
- On ranking samples (AUC), spill hours do better than a single size (+0.010 over all sites, +0.021
  over rivers, both intervals above 0) and better than most reshuffles.
- On ranking the 32 sites (cross-site rho), the result is too uncertain to read: against `length` the
  interval runs from −0.30 to +0.23. Condition 4 fails because a loss of that size cannot be ruled out,
  not because a loss was shown.

Inferred, not tested:
- The AUC gain may mean spill hours carry some information on which days are worse. It did not carry
  over to probabilities or to sites, and it was found on the same samples that judged the four earlier
  tests. It is not a candidate under this rule.
- The reasons stated beforehand fit: spill hours measure duration, and the spill model already uses
  them.

A side finding, not part of the test. At six of the 38 sites the replay covers, a fixed share of the weight under
`length` comes from overflows with no rain data on any sample day in these runs: River Avon at Queen
Elizabeth Gardens 5.4%, Colwick 1.0%, River Severn in Shrewsbury 0.18%, Ham and Kingston 0.13%,
Wolvercote Mill Stream 0.09%, Wallingford Beach 0.06%. Those overflows count as not spilling, as in
production (`replay_ecoli_leads.py`, `transport.missing_share`). Why they have no rain data, and
whether the live forecast has the same gap, was not checked.

### Files

Outputs are in the run's scratch folder, not in the repo: `summary.csv`, `common.json`,
`paired_length_sh.json`, `paired_flow_sh.json`, `judge.json`, and per-run logs. Harness:
`scripts/spill_size_eval/`. Overflow table SHA-256 `f3c7ed7b…`, `sh.parquet` `7d33d7bd…`, main
`204d2a1`. About six minutes a run, 23 runs one at a time.
