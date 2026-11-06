# Sampling planner: data contract, version 1

Written 31 October 2026, for issue #482 (register row "Sampling priorities #381"). The file is
`data/research/sampling_planner.v1.json`, schema `swimsignal.sampling-planner`, made by
`scripts/export_sampling_planner.py`. The site shows it on `sampling-planner.html` (`build_site.write_sampling_planner`),
linked from the Research page. Route: public research observations plus a planning aid (`docs/RESEARCH-WORKFLOW.md`).

## What it is for

A planning aid for a conversation with a sampler: where the samples behind the E. coli model are thin, and what the
#381 simulation found for simple ways of spending a sampling budget, with a cost the reader sets. It is not a sampling
plan. It allocates no sample, sends nothing to anyone, and makes no efficiency claim.

## Sources

All already in the repository, read only. No fetch, no model fit, no simulation run. Each file's SHA-256 is in
`sources`.

| Input | What it gives |
|---|---|
| `data/research/ecoli_evidence.v1.json` | Every EA E. coli sample at the 38 inland bathing waters, 2023-26: counts by year and month |
| `docs/CONCENTRATION-STUDY-2026-11-atlas-rows.csv` | The concentration study's 1,537 rows (2024-26, 32 bathing waters with an overflow upstream) and their archived lead-0 forecast rain in 48 hours |
| `spots.csv`, `spots-osm.csv` | SwimSignal's 109 spots, their kind and area |
| `data/research/waterhead_wet.v1.json` | `spots`: the one spot with a local group's samples |
| `docs/SAMPLING-PRIORITIES-SIM-2026-10*.json` | The simulation's three runs: main (200 replications), τ = 0 and budget 120 (100 each) |

## What the file holds

| Field | Content |
|---|---|
| `claim` | `public_wording`, the page's lead, and `not_claimed` |
| `field_validation` | `false`. Stays false until a field study (below) passes |
| `coverage` | `samples`, `years`, `months` (May to September), `by_month`, `outside_months` (0); `wet`: rows with rain, rows over 10 mm in 48 hours, sites with rain; `spots`: totals, those with EA or local samples, those with none by kind and by area; `sites`: per bathing water, samples by year and month, `rain_rows` and `wet_rows` (null for the six with no overflow upstream) |
| `policies` | The four simulated policies in the page's order, with their rule in words. RISK is named "Wettest, riskiest days": a pure wet-day rule was not simulated |
| `simulation` | The record's path, the copied verdict (`fail`), the pass rule and metric in words, the world, and per run: replications, τ, budget, samples per never-sampled site, history-only error, each strategy's metrics, and the information policy against equal coverage and random (share of worlds with lower error, mean gain, 95% interval) |
| `cost` | The form's starting values (60 samples, £100, 12 sites) and a note that they are assumptions, not a quote |
| `field_study` | A link to the section below |
| `attribution`, `sources` | The EA's OGL line; each input's and the script's SHA-256 |

Figures are copied from the simulation's files, rounded to six decimal places. The verdict is copied, never
recomputed. "Wet" is more than 10 mm in 48 hours, the concentration study's line; the simulation used 10 mm or more.

## What it may say

- **May say:** how many EA samples each bathing water has, by year and month, and how many came after rain; which
  spots have none; what the simulation found, with its failed verdict beside it; what a season costs at the reader's
  price.
- **May not say:** that any policy finds more pollution or teaches the model more in real water; that the information
  policy passed; that the page is a sampling plan for any site or day; what a real programme costs; that a spot with no
  samples is clean or polluted.
- The page keeps "Suggested priorities, not a plan" apart from the simulation and the cost. The priorities follow the
  rule of thumb Ethan recorded on 26 October 2026 (least-sampled sites, on wetter days) and are listed as things to
  discuss.

## The field study an efficiency claim would need

Nothing here was arranged, asked for or costed with anyone. Asking a partner is outreach and Ethan's call.

**Design.** A partner who samples anyway (for example a local group planning a 2027 season) splits the season by week.
Before the season, each week is assigned at random, with a fixed seed written down, to one of two arms:
- **Rule arm:** the sites and days the stated rule picks: the least-sampled sites, on the wettest forecast day of the
  week within the partner's limits. The information policy could be a third arm only if it is frozen first.
- **Usual arm:** the partner's normal fixed schedule.

Both arms take the same number of samples at the same laboratory with the same method. Sites must include places the EA
does not sample, since the simulation's whole gain was at never-sampled sites.

**Primary measure.** The model is updated twice, once with each arm's samples. Each version is scored by log loss on
later samples neither arm chose: the next season's EA samples where they exist, and a fixed-schedule set at the
partner's sites. Secondary: the share of results over 900, reported apart as a swimmer-protection figure, never as
learning.

**Size.** It cannot be set from what is known. The simulation's gain was small (about 6% of equal coverage's error) and
was lost in 41.5% of single worlds; a real world is harder. So one season of 60 samples per arm would most likely be
inconclusive. The first season is therefore a pilot, stated as such: at least 60 samples per arm at no fewer than 6
sites, to estimate the spread of the difference. The confirmatory size is then computed from that spread, for a stated
margin, and written down before the second season. Pilot results never count towards the confirmation.

**What would count as success.** Fixed before the first sample: the rule arm's mean log loss lower than the usual
arm's by at least a stated margin, with the 95% interval of the paired difference (resampled by site and week) above
zero, and no subgroup (rivers, lakes) worse by more than a stated harm margin. Anything else is reported as "not shown",
with its estimate and interval. Only a pass changes `field_validation` to true, in a new minor version.

**What would not count.** A rerun of the simulation, a reanalysis of past EA samples (taken on the EA's schedule, so no
policy can be compared on them), or a high-risk list catching more exceedances.

## Changes

- **1.0.0 (31 Oct 2026):** first version.

## Also read by

The Research Lab's exhibit 5, sampling gaps (`docs/SAMPLING-GAPS-EXHIBIT-2026-11.md`), reads this file as it is from
`lab/data/`, beside its own `gaps.json`. It shows the same verdict and limits.

## Use in tests

`tests/test_sampling_planner_page.py` checks the committed file against `check`, the page's figures and its failed
verdict, and that a file of another schema is not shown. `tests/site_sampling_planner.test.cjs` checks the cost lines.
