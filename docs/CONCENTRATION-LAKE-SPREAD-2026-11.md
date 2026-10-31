# Lake concentrations: an E. coli evidence file, and a lake-specific spread (exploratory)

Written 30 October 2026, register row **3 / LAKE-CONC**, under `docs/RESEARCH-WORKFLOW.md`. Statement committed before
the comparison ran. **Exploratory: every row is 2024-26 data that #466 and earlier tests used.** Nothing here changes
a production model or a shown value.

## Continuation record

| Field | Content |
|---|---|
| Identity | LAKE-CONC; owner: Claude session "SwimSignal pollution event lifecycle"; this PR; code `scripts/concentration_study.py` (`lake` step), `scripts/export_ecoli_evidence.py` |
| Evidence | #466: on rivers the censored site-pooled model ties production's form (Brier 0.1071 vs 0.1069); at lakes it ranks samples within a site better (rho 0.27 vs −0.11 forward) but its central 80% interval held only 65% of lake results (56% at held-out groups): one noise level shared by rivers and lakes |
| Stage and claim | (1) **Public research observation, shipped to a contract:** the E. coli evidence file (below). (2) Development: a lake-specific spread |
| Next deliverable | The evidence file on the Labs page (product owner); the comparison below; then, if the direction holds, a lake statement judged on lake data it never read |
| Milestone and budget | Comparison: this PR, offline, under a minute of fits per fold. Fresh lake data: 2027 lake samples (the 2027 season), or pre-2023 lake seasons, which need archived rain and a hindcast exposure (Open-Meteo archive calls; budget and quota decided before any fetch) |
| Release route | Lake concentrations in guidance need calibration on fresh data; until then the evidence file (measured samples, dated, beside honestly labelled hindsight estimates) is the public output |

## 1. The E. coli evidence file (public research observation)

`scripts/export_ecoli_evidence.py` writes `data/research/ecoli_evidence.v1.json` (contract:
`docs/ECOLI-EVIDENCE-CONTRACT-v1.md`): every EA lab sample at the 38 inland bathing waters, 2023 to 28 September 2026
(2,265 samples), with the lab's qualifier ("<10", ">10000") and enterococci, beside the **hindsight** estimate of
P(E. coli over 900) for the 1,537 samples in #466's rows: production's form refitted leaving out each year in turn,
with archived lead-0 forecast rain and replayed exposure. Not the forecasts the site issued, and labelled so. Each site
gets a summary: samples, over 900, below the limit, hindsight misses and false alarms at 0.25.

## 2. The comparison

- **Models,** on #466's rows and folds (forward in time, leave one year out, connected group and year held out):
  #466's candidate (one noise level), the same model with **its own lake noise level** (one more parameter), and the
  background-only model.
- **Looked at, per scheme and water type:** the share of results inside the central 80% interval (randomised PIT),
  the PIT deciles, the mean log score and its difference from #466's candidate (95% interval, ISO-week bootstrap,
  2,000 resamples, seed 0), Brier over 900, within-site rho.
- **A useful direction** (stated now; a direction, not a verdict): at lakes, the central 80% interval moves into 70%
  to 90% with a log score no worse than #466's candidate (interval not wholly below zero); at rivers, coverage and
  Brier change little. If so, a lake statement for fresh lake data follows. If not, the record says what failed.

---

## Results

Run 30 October 2026 (`concentration_study.py lake`), offline on the main checkout's caches, after the statement was
pushed. Every fit converged. File: `-scores.json`. **Exploratory, reused data.**

**Lakes are much noisier than rivers.** The fitted lake noise level is 0.66-0.76 log10 units in every fold, against
0.36-0.42 for rivers: about a factor of 4.6 against 2.5 in counts. One shared level was too narrow for lakes and too
wide for rivers.

| Scheme | Water | Inside the central 80%: #466 → lake spread | Mean log score: #466 → lake spread | Difference, 95% interval |
|---|---|---|---|---|
| Forward | lakes (407) | 64.4% → **73.2%** | −1.179 → −1.044 | +0.084 to +0.183 |
| Leave one year out | lakes (637) | 64.4% → **77.6%** | −1.133 → −1.024 | +0.067 to +0.149 |
| Group and year held out | lakes (637) | 55.1% → **69.4%** | −1.441 → −1.222 | +0.178 to +0.258 |
| Forward | rivers (616) | 85.1% → 77.3% | −0.658 → −0.693 | −0.094 to +0.014 |
| Leave one year out | rivers (900) | 88.9% → 80.9% | −0.615 → −0.587 | +0.002 to +0.051 |
| Group and year held out | rivers (900) | 89.8% → 84.6% | −0.700 → −0.657 | +0.026 to +0.060 |

- **The stated direction holds, with one shortfall:** lake coverage moves into 70-90% forward and leave-one-year-out,
  and to 69.4% at held-out groups (just under); the lake log score improves in every scheme with the interval above
  zero. Rivers move towards the nominal 80% and their log score improves in two schemes (forward: interval spans zero).
- **Lake PIT deciles** still lean high forward (the top two tenths hold 58 and 71 of 407): some lake results still
  sit above the predicted range; held out by group, both tails are heavy (113 and 82 of 637 in the end tenths).
- **Over-900 Brier** changes little: rivers 0.1051 → 0.1020 forward, 0.1245 → 0.1212 leave one year out; lakes
  0.0312 → 0.0305 forward. Within-site rho at lakes stays about 0.2-0.3.

**What it means.** A lake-specific spread is the better development model: its intervals are much closer to honest at
lakes, with no clear cost at rivers (forward, the river log score is slightly lower, interval spanning zero). It is not a lake forecast. The next step is a lake statement for data it never read: 2027
lake samples (collect from May), or earlier lake seasons once their rain and exposure can be rebuilt within the
Open-Meteo budget. Heavy tails remain; a heavier-tailed lake distribution is the next candidate, judged on those
fresh data, not tuned on these.
