# Sampling priorities: a synthetic simulation, stated before any run

Written 26 October 2026. No strategy has been run or scored. Results go below the line at the end. Nothing above it
changes after a result is seen.

## Why

SwimSignal's E. coli model learns only from samples someone takes. Today those are the EA's routine samples at 38
inland bathing waters, about 20 per site per season, on days fixed in advance. A partner who samples (for example Tim
Boden's weekly Waterhead series) has a small budget. The question is where and on which days a new sample would teach
the model most.

Two questions are kept apart:
- **Informativeness.** Which sample would most reduce what the model does not know, or best show which of two models is
  right? This is the one tested here.
- **High risk.** Which days is a sample most likely to be over the line? That is a swimmer-protection question. Its list
  is reported separately. It is not judged as a way to learn.

This is a prototype with no fieldwork, no contact with anyone and no spending. A pass here would show only that the
ranking does what it claims in a world built to its own assumptions. It would not show it works on real waters. A fail
in that friendly world would be a reason to stop.

`scripts/sampling_plan_test.py` asked a different question: on days the EA did sample, would keeping the rainiest half
have caught more exceedances? That is high-risk targeting on real rows. It does not ask what a sample teaches. This
test does not repeat it.

## The informativeness score

For a candidate (site, day), the score is the expected information, in bits, that one sample's outcome (over the line
or not) carries about the model. It is BALD: H(mean p) − mean H(p), where H is the Bernoulli entropy and the mean runs
over an ensemble of plausible models. The ensemble is:
- **the fixed part:** `ecoli.fit` (logistic regression on standardised inputs, C = 1) and 20 refits on whole sites
  drawn with replacement;
- **a site offset:** each site's log-odds moves by u ~ N(0, τ²). τ is chosen on a fixed grid by the Laplace marginal
  likelihood on the fitting rows. A site's offset posterior comes from its own rows. A site never sampled keeps the
  full N(0, τ²). The offset is integrated over by 7-point Gauss–Hermite quadrature;
- **two candidate models,** A and B, each with its own fixed part and offsets, weighted ½ each. The score then also
  counts what a sample says about which model is right. That part is the Jensen–Shannon divergence of the two models'
  mean chances.

The fixed part is fitted first and the offsets given it (two stages, not a joint mixed model). This is an approximation.

**The plan.** Greedy. Pick the highest-scoring allowed candidate. Then shrink the picked site's offset variance by one
sample's expected precision, p(1 − p), in each model, and score again. No outcome is used while planning. The picked
site's next visit is worth less, so picks spread without a rule that forces it.

## The synthetic world

One world per replication. Parameters fixed now:
- **Sites:** 40. 28 rivers, 12 lakes. 4 rain regions, sites assigned in turn. 8 rivers and 4 lakes are never sampled
  in history. The other 28 are sampled once a week on their own weekday (one of Monday to Friday).
- **Seasons:** 4, each 140 days (20 weeks). Seasons 0 and 1 are history. Season 2 is the season planned. Season 3 is
  held out for scoring.
- **Rain:** each region has a wet day with chance 0.35, amount gamma (shape 0.8, scale 6 mm). Each site's rain is its
  region's times lognormal(0, 0.3). The 48 h total is that day plus the day before.
- **Soil moisture:** a regional store, s(t) = 0.92 s(t − 1) + 0.08 min(rain / 10, 3), reset to 0.15 at each season's
  start, plus a fixed site offset N(0, 0.5). Standardised on the history seasons to `sm`.
- **Exposure:** logit_risk = site base + 1.0 × (log(1 + rain48) − 1) + N(0, 0.5), clipped to ±6.9. Site base N(−3, 1)
  on rivers, N(−4, 1) on lakes.
- **The true chance:** logit p = −2.2 + 0.8 lr + 0.45 (logit_risk + 3) − 1.6 lake − 0.6 lake × lr + γ (1 − lake) sm + u,
  with lr = log(1 + rain48) and the site's true offset u ~ N(0, 0.7²).
- **Two truths.** γ = 0 in even replications (truth A: soil does nothing). γ = 0.6 in odd ones (truth B: wet soil
  raises the chance on rivers, not lakes).

**The two models,** fitted on the history (about 1,120 rows):
- **A:** `lrain48`, `logit_risk`, `lake`, `lake_x_lrain48`. This mirrors today's model without the season terms.
- **B:** A plus `sm`. This mirrors the soil-moisture variant (`docs/SOIL-MOISTURE-RIVERS-TEST-2026-11.md`). B fits its
  soil term on rivers and lakes alike. So where the truth is B, B is still wrong on lakes on very wet or very dry days.

They disagree in known places: rivers on days whose soil is wetter or drier than their rain suggests, and lakes at
extreme soil values.

## The season planned

- **Budget:** 60 new samples in season 2, 3 a week for 20 weeks.
- **Candidates each week:** every site on Monday to Friday of that week: 200 (site, day) pairs.
- **Limits:** at most 2 samples on one day; at most 1 per site per day.
- **What the planner sees:** 48 h rain times lognormal(0, 0.5), a forecast error. Exposure moves with it. Soil moisture
  is a state known at issue and is not perturbed. The outcome is drawn from the true chance on the true inputs. A
  sampled row enters the data with the true inputs, as reanalysis rain does today.
- **The planning models** are fitted once, on history, at the season's start. They are not refitted during the season.
  The greedy offset shrinkage carries from week to week.

### Strategies

1. **INFO:** the greedy informativeness plan above, with A and B.
2. **COVER, the coverage baseline:** each week, the 3 sites with the fewest samples so far (history plus new), ties
   broken at random. Each on a random weekday within the limits.
3. **RANDOM:** each week, 3 (site, day) pairs drawn at random within the limits.
4. **RISK, reported separately:** each week, the 3 candidates with the highest mean chance (A and B averaged), within
   the limits. It is scored on the same metrics for description. It is not a baseline for the pass rule.

Common random numbers: in a replication, every strategy sees the same world, the same forecast errors, and the same
outcome for the same (site, day). Only the choice of samples differs.

## After the season

For each strategy, the data are history plus its 60 new rows.
- **Model pick.** The models fitted on history (point fits with their offsets) predict the 60 new samples. The model
  with the lower log loss on them is picked. A tie picks A.
- **Refit.** A and B are refitted on history plus the new rows, τ chosen again, with 20 site-bootstrap refits each.

## Metrics, stated now

- **P, primary: site-rate error.** For each of the 40 sites, the true rate R is the mean true chance over season 3's
  weekdays (100 days). The predicted rate R̂ is the mean of the picked model's refitted chance (offset integrated) over
  the same days, with the true inputs. P = mean over sites of (R̂ − R)². Lower is better. Season 3 is never sampled.
- **S1: day-level error.** The mean over the same 4,000 site-days of (p̂ − p)², with p̂ the picked model's chance and p
  the true one. This is the excess Brier score on held-out days.
- **S2: posterior spread of the site rate.** For each site, the variance of R̂ across the picked model's refits and
  offset nodes. The mean over sites.
- **S3: picking the right model.** The share of replications where the picked model is the truth (A when γ = 0, B
  when γ = 0.6). Reported for each truth separately. Under truth A the two models are close, so about half is expected
  for every strategy.
- **S4: exceedances caught.** The number of the 60 new samples over the line. RISK should win this. It is a
  swimmer-protection figure, not a learning one.
- P is also reported split into never-sampled and history-sampled sites.

## Replications and seeds

- 200 replications, r = 0 to 199.
- World: `default_rng(20261026 + r)`. History outcomes: `default_rng(1000000 + r)`. Forecast errors and the season's
  outcome draws (one uniform per site-day): `default_rng(4000000 + r)`, shared by all strategies. RANDOM's draws:
  `default_rng(2000000 + r)`. COVER's tie-breaks and weekdays: `default_rng(3000000 + r)`. Bootstrap refits: seed r.
- One process, no network. Expected to take minutes.

## The pass rule

INFO passes if, against **each** of COVER and RANDOM:
1. INFO's P is lower in at least 60% of the 200 replications; and
2. the mean paired gain (baseline P − INFO P) has a 95% interval with its lower end above 0. The interval is the 2.5th
   to 97.5th percentile of 2,000 bootstrap resamples of the replications, `default_rng(1)`.

Otherwise it fails. The secondary metrics are reported and decide nothing.

## What would make the result uninformative

Each is checked and reported. Any one replaces the verdict with "uninformative".
- **U1, a broken harness.** RANDOM's mean P after the season is not below the mean P of the history-only fit (the same
  procedure with no new rows). Then new samples do not help at all, which points to a fault. I stop and report it.
- **U2, no useful difference.** The means of P under INFO, COVER and RANDOM all lie within 2% of RANDOM's mean P. The
  budget is then too small to matter in this world, whatever the pass rule says.
- **U3, the same picks.** On average more than 80% of INFO's picks share a site and week with a COVER pick. The test
  cannot then tell the two apart.

Beyond these, the whole result is conditional on the world. The truth is a logistic model with normal site offsets,
the same form the score assumes. Real waters break that: counts are not Bernoulli draws on a fixed line, site
differences are not normal, and rain forecasts fail in ways a lognormal error does not copy. So:
- a pass says the ranking is coherent, not that it beats coverage on real waters;
- a fail says the method should not go further in this form.

## Sensitivity runs, stated now, deciding nothing

100 replications each, same seeds as r = 0 to 99:
- **τ = 0:** no true site offsets. Coverage should matter less.
- **Budget 120:** 6 a week.

## Seen before writing

- The code of `ecoli.fit`, `train_ecoli.py`, `sampling_plan_test.py`, and the model files' coefficients.
- The world generator alone was run on 10 seeds to check its base rates, before this file was committed. True mean
  chance: rivers 0.25, lakes 0.03 (the real fit's base rates are 0.216 and 0.025, read from
  `data/processed/ecoli_model.json`). About 1,120 history rows, about 10 lake exceedances in history. 11% of site-days
  have 10 mm or more of rain in 48 h. The soil term (γ = 0.6) moves river chances by 0.06 on average. No strategy, plan,
  score or metric was computed.

---

## Results

Added 26 October 2026, after the run. Everything above the line is as committed in 6e69dfc and pushed before the run.
The harness came after it, in ba1d092. It did not change anything above the line.

**Verdict: fail.** INFO beats RANDOM on both conditions. Against COVER it meets condition 2 but not condition 1: its
site-rate error is lower in 58.5% of replications, against 60% needed. None of U1 to U3 holds, so the verdict stands.
Nothing is adopted. Nothing on the live site, `ecoli_model.json` or any shadow or test window changes.

### How it was run

- `uv run python scripts/sampling_priorities_sim.py --out docs/SAMPLING-PRIORITIES-SIM-2026-10.json`, from ba1d092,
  18:47:58 to 18:49:50 UTC, 112 s, one process. No network call: the harness reads no file and calls no API. The
  heavy-run lock was absent and no other Python job was running.
- The two sensitivity runs followed, 100 s and 77 s. Their files are `-tau0.json` and `-budget120.json`.
- The JSON files were rewritten afterwards to one line per replication. Their content is unchanged (checked by
  reloading and comparing).

**Seen before the run:** a smoke run of 2 replications on seeds outside the stated range (r = 5000, 5001), to check
the harness ran. Nothing was changed in the method after it. Changes after it, before ba1d092: the wording of the
plain-language reasons, a column recording each pick's score, and the test fixture. None of these touches a pick or a
metric. While writing tests I also saw that the fitted τ can fall to the grid's floor (0.01) in a world whose true τ is
0.7 (world seed 7, not in the stated range). The estimator was not changed.

### The pass rule

| Against | INFO lower in | Needed | Mean gain in P (baseline − INFO) | 95% interval | Relative | Result |
|---|---:|---:|---:|---|---:|---|
| COVER | 58.5% | 60% | 0.000189 | 0.000077 to 0.000306 | 6.2% | condition 1 fails |
| RANDOM | 73.0% | 60% | 0.000558 | 0.000429 to 0.000693 | 16.4% | passes |

INFO beat both baselines in the same replication in 51.5% of the 200.

### The checks that would make it uninformative

- U1: RANDOM's mean P after the season, 0.00340, is below the history-only fit's, 0.00408. New samples help. Holds.
- U2: the three means are not within 2% of RANDOM's (INFO is 16% lower). Holds.
- U3: 21% of INFO's picks share a site and week with a COVER pick, against the 80% limit. Holds.

### All metrics, means over 200 replications

| | INFO | COVER | RANDOM | RISK |
|---|---:|---:|---:|---:|
| P, site-rate error | 0.00284 | 0.00303 | 0.00340 | 0.00331 |
| P, never-sampled sites | 0.00496 | 0.00553 | 0.00679 | 0.00671 |
| P, history-sampled sites | 0.00193 | 0.00196 | 0.00195 | 0.00185 |
| S1, day-level error | 0.00395 | 0.00424 | 0.00466 | 0.00448 |
| S2, posterior spread | 0.00306 | 0.00326 | 0.00353 | 0.00362 |
| S3, right model, truth A | 0.53 | 0.54 | 0.53 | 0.49 |
| S3, right model, truth B | 0.77 | 0.67 | 0.65 | 0.80 |
| S4, exceedances in 60 samples | 24.1 | 11.3 | 11.4 | 48.6 |
| Share of samples at never-sampled sites | 0.84 | 1.00 | 0.29 | 0.18 |
| Share at lakes | 0.21 | 0.33 | 0.30 | 0.00 |
| Mean 48 h rain on sampled days (mm) | 10.1 | 3.5 | 3.5 | 15.5 |
| Sites visited | 12.5 | 12.0 | 31.1 | 15.1 |

Read from these figures:
- The whole gain is at never-sampled sites. At history-sampled sites (40 samples each) all four strategies are within
  0.0001 of each other.
- INFO and COVER both go mostly to never-sampled sites. INFO differs mainly in the day: it samples wetter days (10.1 mm
  against 3.5 mm), where the chance is nearer the middle and one result says more. It also spends fewer samples at
  lakes.
- INFO's per-replication gain over COVER is small against the replication-to-replication noise. So the mean gain is
  clear of zero, but INFO loses in 41.5% of single worlds.
- RISK, the swimmer-protection list, catches twice INFO's exceedances and four times the baselines'. As a way to learn
  it is no better than RANDOM (P 0.00331 against 0.00340; RANDOM − RISK interval −0.000044 to 0.000221).
- Picking the right model: under truth A all strategies are near a coin flip, as expected. Under truth B, INFO (0.77)
  and RISK (0.80) pick B more often than COVER (0.67) and RANDOM (0.65). Inferred: both sample wet river days, where
  the soil term matters most.
- The fitted τ in history: median 0.7 (true 0.7), 10th to 90th percentile 0.5 to 0.9. It fell to 0.1 or less in 1% of
  replications.

By truth: INFO beat COVER in 57% of truth-A and 60% of truth-B replications; RANDOM in 71% and 75%.

### Sensitivity runs (decide nothing)

| | INFO lower than COVER | Mean gain, 95% interval | INFO lower than RANDOM | Mean gain, 95% interval |
|---|---:|---|---:|---|
| Main, τ = 0.7, budget 60 | 58.5% | 0.000189 (0.000077 to 0.000306) | 73% | 0.000558 (0.000429 to 0.000693) |
| τ = 0, budget 60 | 66% | 0.000387 (0.000190 to 0.000582) | 62% | 0.000142 (−0.000004 to 0.000296) |
| τ = 0.7, budget 120 | 51% | 0.000060 (−0.000066 to 0.000179) | 78% | 0.000656 (0.000484 to 0.000832) |

- **τ = 0 (all sites alike).** COVER is now the worst strategy (P 0.00088 against RANDOM's 0.00063). It spends every
  sample on sites that are no different. INFO is best (0.00049). But the fitted τ was not 0: median 0.3, and 0.1 or
  less in only 40% of replications. So the planner still believed in site differences that did not exist.
- **Budget 120.** COVER catches up. With 6 samples a week each never-sampled site gets about 10, and where they fall
  matters less. INFO's edge over COVER is gone (51%, interval spanning zero).

### Where it fails, and limits

- **It fails against the simple baseline that matters.** In the world built to its own assumptions, INFO is only a
  little better than "sample the sites with the fewest samples". On a fair reading the method's added value is in
  choosing wet days at never-sampled sites, and that edge is small and inconsistent at this budget. It vanishes at
  budget 120.
- **The world is friendly.** The truth is logistic with normal site offsets, the score's own form. Real counts, real
  site differences and real forecast errors are not. A real test would be harder.
- **The τ estimate is noisy.** With 28 sampled sites it can fall to the floor (the seed-7 world) or stay above zero
  when the truth is zero (τ = 0 run). The never-sampled part of the score is only as good as τ.
- **Greedy and partial.** The plan shrinks only the site offset after a pick. It ignores what a sample teaches the
  fixed part, and it does not refit within the season.
- **No travel or cost.** 12 never-sampled sites may be far apart. The only limits are 2 samples a day and 1 per site a
  day.
- **Selection on inputs.** Sampling wet days does not bias a correctly specified logistic model, because the choice
  depends on inputs, not on the outcome. If the model is wrong in the wet tail, it would. Not checked.

### The prototype on saved rows (an illustration, not a result)

`scripts/sampling_priorities.py --rows <main checkout>/data/processed/ecoli_validation_rows.parquet`, read only. That
file is the older one (14 September 2026, 2,165 rows at 38 sites before filters), not the one behind the published
fit. Model A is today's inputs; model B is train_ecoli.py's "rain + season" variant, with no exposure term. So
"models disagree" marks a site and day where a sample would show whether exposure matters there. Candidates were three
scenario days per site (dry, moderate, wet, mid-July), not dated forecasts. Fitted τ was 1.2, larger than the
synthetic world's 0.7. The top three planned samples were wet scenario days at Falcon Meadow (River Waveney),
Pangbourne Meadow (River Thames) and the River Frome at Farleigh Hungerford. At each, the two models differed (for
example 0.79 with exposure against 0.55 rain only at Farleigh Hungerford). 3 of the 10 planned samples were also on
the high-risk list. These are outputs of a prototype on old rows. They are not a recommendation to sample anywhere.

## What real validation would need

Nothing here was sent, asked for or arranged.

**The data.**
1. **A sampling arm chosen by the ranking.** The only direct test. A partner with a budget samples some weeks on days
   the ranking picks and other weeks on their usual schedule, the week's arm drawn at random in advance. Without it,
   every real dataset was sampled on someone else's schedule, and no strategy can be compared on it.
2. **Tim Boden's Waterhead series** (59 weekly samples, 2025–26, private, none over 900). It is a fixed weekly schedule
   at one lake. It can show whether a site outside the EA set has a level the model gets wrong: the "never sampled"
   case. It cannot test the ranking. What his permission covers was not checked here. Using it for this would need his
   agreement.
3. **The 2027 EA season** at the 38 inland bathing waters (`docs/PREREGISTRATION-2027.md` section 3). The EA picks
   the days, so it cannot test a strategy. It can check one claim of the score, stated in advance: samples with higher
   predicted information should move the model more (larger change in the site's offset, larger log loss). Section 12
   applies: nothing in this prototype may touch the frozen model's paths or constants in the season.

**How it would be judged.** A pre-stated test in this file's style. In real data there is no true rate. So the
primary score would be log loss on later held-out samples not chosen by either arm (for example the next EA season at
the same sites), from models updated with each arm's samples. The pass rule, margins and the near-miss labels of
`docs/LAKE-ECOLI-LINE-TEST-2026-10.md` would be fixed before any sample.

**What Ethan must decide.**
- Whether to take this further at all, given the simulation fails against coverage at this budget. The simple rule
  "sample the least-sampled sites, on wetter days" may give most of the value with no model.
- Which second model defines "disagreement" on real data: the soil-moisture river model, rain only, or none.
- Whether a partner list of high-risk days is offered at all. It is a swimmer-protection list. It biases samples to
  wet days, which this simulation says is no worse for learning than random sampling, but it does not teach more.
- Whether to ask any partner about a randomised sampling arm. That is outreach and is his call.

## Decision, 26 October 2026

Ethan adopted the recommendations of 26 October ("Adopt all the recommendations as my decisions"):
- **Not pursued.** The ranking failed its stated rule against the coverage baseline. This PR is kept as the record of
  that test. It is not wired into anything.
- If a partner asks where to sample, the plain rule of thumb is: the least-sampled sites, on wetter days.
- **No randomised sampling arm now.** It is raised only if a partner (for example Tim Boden at Waterhead) plans 2027
  sampling anyway. No outreach was made.
