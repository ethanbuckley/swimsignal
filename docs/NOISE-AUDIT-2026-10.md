# Adoption rules without a noise allowance: an audit of the tests, and a rule for new ones

Checked 25 October 2026 on main `63e931e`, plus PR #334's branch for the day-boundary test. A record, not a test.
No verdict below is changed. A test's verdict is what its own conditions said; a fairer rule is for a new test.

## The question

The nine-company model (`docs/NINE-COMPANY-MODEL-TEST-2026-10.md`) was rejected partly on conditions like "no
company worse than today": a point comparison at each of nine companies, with no margin and no interval. A better
model can fail such a rule by chance. If nine companies each carried a 2.5% chance of looking clearly worse by
noise alone, about 20% of runs would show at least one (1 − 0.975⁹). Shared weeks make the true rate lower. Which
other tests decided on rules like that?

## Verdicts that rested partly on a point rule with a small failure

1. **Nine-company model, condition 1.**
   - Anglian: 0.02722 against the hold-out's 0.02691 (+1.1%). Log loss and AUC were better.
   - United Utilities: 0.04561 against 0.04457 (+2.3%). Log loss was worse too, so this loss looks real.
   - No interval was computed. Overall the model was better (0.0362 against 0.0376), and better at 7 of 9 companies.
2. **Nine-company model, condition 4 (the Welsh set).** 0.04206 against 0.04168 (+0.9%). No interval.
3. **Soil moisture in the spill model, arm `add`, condition 3.**
   - Thames ECE 0.0242 against the baseline's 0.0240 (the baseline is itself above 0.02).
   - Its condition 2 also failed on an interval (Anglian +0.00050 [+0.00012, +0.00094]), so the rejection stands on
     that alone.
4. **Lake direction, a pass not adopted.** All seven conditions passed. The default was kept at `any` on
   within-site rho figures without intervals, at about 57 samples per site.

## Verdicts that were clear

These failed on intervals or large losses: the neural challenger, multi-year question 1, covariate-year question 2,
dry-weather spills question 2, urban dilution, population size, die-off question 2, farm pressure, lake wind,
transport fit 2. The map-click checks are deterministic, so noise does not apply.

These already allowed for noise and did not show a gain: dry spell's 72-hour rain (0.00049 against a 0.0005 bar),
live recalibration B (−4.3% against a 5% bar), die-off question 1, spill size, dry-weather question 1, the radar
check, day boundary.

## The rule that recurs: ECE "no higher than the baseline's, or at most 0.02"

About ten tests use it, as a point comparison. A baseline already above 0.02 means any small rise fails.

## Tests not yet read

| Test | Read | Point rules | Action taken |
|---|---|---|---|
| Company calibration (A8) | 25 Nov | "candidate < current" and "< flat" at every changed company | Amendment requested on 25 Oct, before its window opens on 26 Oct |
| Lead calibration B | 16 Nov | L1 and L3 strict, L2 a 2% point margin | None. The window opened on 18 Oct, so the rules stand. The read reports intervals and says if a verdict lies within them |
| Ensemble rain (D4) | 21 Nov | M1 "Brier(mean) ≤ Brier(p)" strict | As for lead calibration B |
| Live-status shadow | 23 Nov | Interval based; ECE point rule | As for lead calibration B |
| Option B | on or after 2 Dec | Mostly intervals with 1% margins; ECE (4) and B < B0 (6) point rules | Reported arm P1 added; the conditions stand as approved |

## Re-tests, each a new statement on data the old test did not see

- **Nine-company model:** v2 is being stated (2024–25 training, 2026 test), with interval-based conditions per company.
- **Soil moisture `add` in the spill model:** a re-test on the 2026 EA files, with interval-based per-company
  conditions and an ECE margin.
- **Lake direction:** on the 2027 samples or Tim Boden's Waterhead counts, with per-site intervals.

## The rule for new statements

1. No condition compares point estimates at every subgroup. Use a pooled gain whose 95% interval lies below zero,
   and per subgroup "not clearly worse": the interval not wholly above zero and the point estimate within a stated
   margin (1% has been the house margin).
2. ECE gets a stated margin (for example +0.005 over the baseline) or an interval, not "no higher".
3. The interval is a cluster bootstrap with a fixed seed: weeks, or overflow × week where the change is per overflow.
4. AUC and log loss are reported beside the Brier score, and decide nothing unless stated.
5. If a statement keeps a strict rule, it says why.
