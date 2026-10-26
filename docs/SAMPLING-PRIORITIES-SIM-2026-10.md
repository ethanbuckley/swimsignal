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

Not yet run.
