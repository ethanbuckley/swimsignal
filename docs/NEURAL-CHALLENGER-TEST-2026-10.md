# A neural-net challenger to the spill model: the test, stated before any run

Written 16 October 2026, before any neural net was trained and before any result of the
nine-company model was seen (its results section was empty when this was written). Results go
below the line at the end. Nothing above that line changes after a result is seen.

## Why

On 16 Oct 2026 Ethan asked whether a neural net could give better spill forecasts than the
gradient-boosted model.

The boosted model sees ten summaries of the rain (`features.RAIN_FEATURES`): daily totals, rolling
totals, an antecedent index and the heaviest 1, 3 and 6 hours of the day. A neural net can read the
hourly rain itself, so it can see when in the day a storm fell and what shape it had. That is the
only thing tested here. On table-shaped data like ours, boosted trees usually match or beat neural
nets, so the expected result is no gain. The test is cheap enough to be worth running anyway.

This depends on the nine-company model (`docs/NINE-COMPANY-MODEL-TEST-2026-10.md`, review task D2).
It uses that model's events, rain cache, rows and coverage rules. Its candidate is the baseline here,
**whether or not it is adopted**. If D2 is abandoned before it produces a candidate, this test does
not run.

What this does not test: the transport step (travel time, die-off, dilution) and the E. coli column.
Both are unchanged.

## The challenger (one, fixed now)

- **Inputs for overflow *i* on day *d*.** Everything comes from the overflow's 0.1° ERA5-Land cell
  and its annual-return row, the same sources as the boosted model:
  - the hourly rain for the 72 hours from 00:00 UTC on *d*−2 to 23:00 UTC on *d*, as log(1 + mm);
  - the daily totals for *d*−30 to *d*−3 (28 values), as log(1 + mm);
  - `doy_sin`, `doy_cos`, `log_lta_spills`, `log_spill_hours`, `edm_pct` (`features.py`).

  There is no company feature and no per-overflow embedding, as in D2. Days are floored in UTC, as
  `train.py` does. A row whose 72-hour window has fewer than 90% finite hours is dropped from every
  predictor's scoring, and the count is reported. Missing hours inside a kept window are set to 0 and
  flagged by a second input channel (1 where the hour was missing).
- **Network.** About 10,000 weights:
  - a one-layer GRU (a recurrent network that reads a sequence step by step), hidden size 32, over
    the 72 hourly steps (2 channels: rain and missing flag); its last state is kept;
  - a dense layer of 16 over the 28 daily totals;
  - the GRU state, the daily layer and the 5 static inputs concatenated, then a dense layer of 32
    with ReLU, then one output, the log odds of a spill.
- **Monotone in rain.** Not built into the network. It is measured (condition 5).
- **Layer 2.** The same per-overflow offsets as D2 (`SpillModel.fit_site_offsets`, prior strength
  15, recency 1), fitted on the challenger's own 2024 predictions. So layer 1 is compared with
  layer 1, and both get the same layer 2.
- **Training rows.** Exactly D2's 2024 layer-1 rows, with the same subsample: dry days kept with
  `numpy.random.default_rng(0)` at `neg_frac` 0.25 and weighted 1/0.25, as `fit_pooled` does.
- **Fit.** Weighted binary cross-entropy. Adam, learning rate 0.001, batch 1,024, at most 20 epochs.
  Early stopping on an inner hold-out within 2024: every fourth ISO week (weeks 4, 8, 12 …) is held
  out from training and used only to stop, with patience 3. Three seeds (0, 1, 2). The prediction is
  the mean of the three networks' probabilities. **Nothing is tuned on 2025.** If any setting above
  is changed after a 2025 score is seen, the run is void and the change is recorded below the line.
- **Software.** PyTorch, in a new optional dependency group `nn` in `pyproject.toml`, used only to
  train. The build does not install it. If adopted, the weights are written to JSON and the forward
  pass runs in numpy in `src/dipcast/model/` (a GRU forward pass is about 30 lines). A test checks
  that the numpy and PyTorch outputs agree within 1e-5 on 1,000 rows.

## Verification on 2025

The rows are D2's 2025 verification rows (its section "Verification on 2025, per company"), less
any dropped by the 90% rule above. Every predictor is scored on the same rows.

| Predictor | What it is |
|---|---|
| Challenger | the network above, with its layer 2 |
| Boosted | D2's candidate, with its layer 2 |
| Current hold-out | `spill_model_holdout_2025.pkl`, United Utilities 2023-24 |
| Company flat rate | the company's 2024 spill-day rate |

Reported per company and for the nine together: rows, base rate, Brier score, AUC, a 10-bin
reliability table and ECE (D2's definition).

**With forecast rain.** On D2's lead rows (2025 site-days in cells with archived lead forecasts),
both models are fed the hourly forecast rain issued 0 to 4 days ahead, in place of ERA5-Land, with no
isotonic map. Brier and AUC are reported per lead. The site runs on forecast rain, and a model that
leans on the hour a storm falls may suffer more from a forecast that gets the hour wrong.

**Uncertainty.** Paired differences in Brier (challenger minus boosted) get 95% intervals from a
cluster bootstrap by calendar week: 2,000 resamples, seed 0, every row of a week drawn together.
One storm hits many overflows at once, so weeks are the honest unit. This is the grouping the
E. coli tests found most demanding (README, Method).

## Conditions for adopting, all required

1. **A real gain overall.** Over the nine companies together, the challenger's Brier is lower than
   the boosted model's, and the 95% interval of the difference lies wholly below zero.
2. **No company clearly worse.** At no company is the challenger's Brier higher than the boosted
   model's with the 95% interval of that difference lying wholly above zero.
3. **Not worse with forecast rain.** At every lead from 0 to 4, the challenger's Brier on the lead
   rows is no higher than the boosted model's.
4. **Reliability.** At each company, the challenger's ECE is no higher than the boosted model's,
   or it is at most 0.02.
5. **More rain does not lower the risk.** On the 2025 rows, adding 1 mm to every hour of the 72-hour
   window lowers the challenger's probability on fewer than 0.5% of rows, and by no more than 0.01
   on any row. The same holds for doubling every hour of the window.
6. **Cheap to run.** The numpy forward pass for every overflow in the built site's `data/overflows.geojson` for five days
   takes under 60 seconds on this Mac (an Apple M3 with 16 GB).

If all six hold, the challenger replaces layer 1 in production. The lead map is refitted for it by
D2's A1 procedure, `trained_on` names it, and the README's Method table gains its row.

If any fails, nothing is deployed and this document is the record. A fail on condition 1 alone
answers Ethan's question: on this data, the network gives no measurable gain over the boosted trees.

## Order of work

1. Wait until D2 has written its results, so its rows and candidate exist. Run nothing while D2 or
   any other evaluation or build is running on this Mac.
2. Add the `nn` group and `scripts/train_nn.py`. The sequences are cut on the fly from one array per
   cell: 1,652 cells × 8,784 hours × 4 bytes is about 58 MB, so memory is not the limit.
3. Time one epoch of one seed. If one seed would take more than 2 hours, stop and write the timing
   below the line. Any smaller network is then stated here as a new candidate, before 2025 is scored.
4. Train the three seeds, fit layer 2, and score 2025 with ERA5-Land rain, then with lead forecasts.
5. Check conditions 1 to 6, write the results below the line, then deploy or keep the record.

---

## Results

### Choices the statement leaves open, fixed before any training

Written 18 October 2026, before any network was trained and before any 2025 score of the challenger
was computed. The code is `scripts/train_nn.py`. D2's 2025 scores for the boosted model were already
published in its own Results.

- **The baseline.** D2's candidate, `spill_model_nine_2024.pkl`, SHA-256 `1603678923ccdd15…`. It was
  untracked in the D2 worktree. A copy is kept off-repo in `swimsignal-private/baselines/`.
- **Rows.** D2's rows, built by D2's own code (`train._frame`). The script stops unless it gets
  D2's counts: 4,976,868 training site-days, 1,569,401 in the subsample, and 5,077,150 for 2025.
- **The 90% rule.** At least 65 of the 72 hours must be finite. It drops rows from scoring only.
  Training rows are D2's rows as stated, so none is dropped there. How many would fall under the
  rule is reported.
- **The daily layer has no activation.** The statement gives ReLU to the dense layer of 32 only.
- **Static inputs are standardized.** Each of the five is shifted and scaled by its mean and
  standard deviation over the 2024 training rows (inner hold-out excluded). The rain inputs are
  log(1 + mm) as stated, with no scaling.
- **Daily totals.** D2's `rain_d` for each day. A day with fewer than 20 finite hours has an unknown
  total. It enters as 0, which matches the boosted model's 7-day and 30-day totals, since they skip
  such a day.
- **Fit details.**
  - The batch loss is the mean of weight × cross-entropy.
  - The inner hold-out loss is Σ(weight × cross-entropy) / Σ weight, over the subsampled rows of
    ISO weeks 4, 8, …, 52 of 2024 (ISO week of the UTC day).
  - Training stops after 3 epochs without a strictly lower hold-out loss, and the best epoch's
    weights are kept.
  - Each seed sets `torch.manual_seed(seed)` for the starting weights and `default_rng(seed)` for
    the shuffle. Training runs on the CPU.
- **Ensemble and layer 2.** The mean of the three probabilities is clipped to [0.0001, 0.9999], as
  `SpillModel.predict_pooled` clips. `SpillModel.fit_site_offsets` (prior 15, recency 1) is then fitted
  on it over all 4,976,868 rows of 2024, as D2 fitted its own.
- **Forecast rain, both models fed the same way.**
  - For lead *k*, the hours of days *d*, *d*−1 and *d*−2 come from the forecasts issued *k*, *k*−1
    and *k*−2 days ahead (floored at 0). This is `verify_leads.py`'s split.
  - Every earlier day comes from ERA5-Land.
  - The boosted model's ten rain features are computed from that same series. So its 3-, 7- and
    30-day totals and its antecedent index include the forecast days.
  - This differs from `verify_leads.py`. That script keeps the 7-day, 30-day and antecedent-index
    features on ERA5-Land. Here, that would give the boosted model the observed rain of *d*, *d*−1
    and *d*−2, which the challenger never sees. Production computes every feature from one forecast
    series, as is done here.
  - A missing feature becomes 0 for the boosted model, as in `verify_leads.py`. There is no
    isotonic map.
- **Lead rows.** D2's lead rows less the 90% rule on the ERA5-Land window. Then, at each lead, rows
  whose day-*d* forecast total is known (`verify_leads.py`'s rule) and whose 72-hour forecast
  window passes the 90% rule. Both models are scored on the same rows at each lead.
- **Bootstrap.** Weeks are ISO (year, week) of the UTC day. One set of 2,000 draws of weeks, from
  `default_rng(0)`, serves every company and every lead. The interval is the 2.5th to 97.5th
  percentile.
- **Condition 5.** Only finite hours are changed; a missing hour stays missing. "Lowers" means any
  decrease in the challenger's final probability, with its layer 2.
- **Condition 6.**
  - The file is the live site's `data/overflows.geojson` (swimsignal.co.uk, last modified 18 Oct
    2026 06:22 GMT).
  - The inputs have that shape, drawn from 2025 rows.
  - The timing covers the three networks' forward passes and their mean. Cutting the windows is not
    timed.
- **Size.** The stated layers have 5,681 weights, not "about 10,000". That number was an estimate.
  The layers are as stated.
- **Software.** `uv` resolved `torch>=2.4` to PyTorch 2.14.1.

### The run

Run 18 October 2026 on this Mac, from commit `aec0d23`, which holds the choices above. The script
did not change after that commit. The training log was pushed (`7feb90b`) before 2025 was scored.
The logs are in `logs/train_nn_*_2026-10-18.log` in the worktree (not committed). Nothing else was
running. The tables are committed beside this file:
- `-scores.csv`: every predictor, every company
- `-differences.csv`: challenger minus boosted, with the bootstrap intervals
- `-reliability.csv`
- `-leads.csv`
- `-training.csv`: every epoch of every seed
- `-checks.json`: the 90% rule, conditions 5 and 6, and a check of the forecast-feature code

**Timing (step 3).** One epoch of one seed took 49 s to train (1,158 batches) and 5 s to score the
inner hold-out. Twenty epochs would take 18 minutes, well under the 2-hour limit, so no smaller
network was needed.

**Training.**
- Rows: 1,185,403 training rows and 383,998 inner hold-out rows. None of the subsampled 2024 rows
  falls under the 90% rule.
- In every seed the inner hold-out loss was lowest after the first epoch:
  - seed 0: 0.17804
  - seed 1: 0.17709
  - seed 2: 0.17674

  After that, the hold-out loss rose while the training loss kept falling. Early stopping kept
  epoch 1 each time and stopped after epoch 4. All three seeds took 10 minutes.
- The networks are kept off-repo in `swimsignal-private/baselines/nn_challenger/`. Their SHA-256
  begins `2a9b45bf52da`, `89b3aebd9b2f` and `75c7f33952cf` (seeds 0, 1, 2).

**Rows and checks.**
- The 90% rule dropped none of the 5,077,150 rows of 2025. Every predictor is scored on all of them.
- The boosted model gives D2's published scores on these rows: 0.0362 for the nine together,
  0.0272 at Anglian and 0.0456 at United Utilities. The hold-out gives 0.0376.
- Lead rows: 1,939,245 site-days for 5,313 overflows in 544 cells, the same as D2. At each lead,
  10,626 rows were dropped and 1,928,619 scored. 10,626 is 2 × 5,313. *Inferred:* these are 1 and 2
  January, whose window reaches into 2024, and the lead files start on 1 January 2025.
- The forecast-feature code was fed ERA5-Land on 200,000 lead rows. It gave back the rows' own ten
  rain features to within 0.00003 mm.

### Verification on 2025, ERA5-Land rain

Brier, with ECE in brackets. Bold marks the better of challenger and boosted. The difference is
challenger minus boosted, with its 95% week-cluster interval.

| Company | Challenger | Boosted (D2) | Current hold-out | Flat rate | AUC challenger / boosted | Difference [95%] |
|---|---|---|---|---|---|---|
| Anglian | 0.0297 (0.025) | **0.0272** (0.011) | 0.0269 (0.008) | 0.0347 | 0.885 / 0.883 | +0.0024 [+0.0016, +0.0035] |
| Northumbrian | **0.0331** (0.009) | 0.0332 (0.003) | 0.0353 (0.014) | 0.0483 | 0.922 / 0.922 | −0.0001 [−0.0011, +0.0008] |
| Severn Trent | 0.0291 (0.014) | **0.0284** (0.005) | 0.0295 (0.009) | 0.0407 | 0.924 / 0.928 | +0.0007 [−0.0002, +0.0016] |
| South West | 0.0526 (0.021) | **0.0519** (0.009) | 0.0547 (0.012) | 0.0854 | 0.931 / 0.929 | +0.0007 [−0.0009, +0.0024] |
| Southern | 0.0286 (0.022) | **0.0277** (0.011) | 0.0300 (0.010) | 0.0441 | 0.946 / 0.945 | +0.0009 [−0.0001, +0.0020] |
| Thames | 0.0343 (0.038) | **0.0303** (0.024) | 0.0330 (0.010) | 0.0451 | 0.939 / 0.942 | +0.0040 [+0.0020, +0.0062] |
| United Utilities | 0.0469 (0.021) | **0.0456** (0.018) | 0.0446 (0.010) | 0.0695 | 0.924 / 0.929 | +0.0013 [+0.0005, +0.0022] |
| Wessex | 0.0345 (0.025) | **0.0326** (0.014) | 0.0354 (0.005) | 0.0515 | 0.940 / 0.944 | +0.0020 [+0.0002, +0.0038] |
| Yorkshire | 0.0405 (0.006) | **0.0403** (0.005) | 0.0435 (0.022) | 0.0627 | 0.924 / 0.927 | +0.0002 [−0.0008, +0.0011] |
| All nine | 0.0372 (0.017) | **0.0362** (0.008) | 0.0376 (0.009) | 0.0547 | 0.927 / 0.929 | +0.0011 [+0.0005, +0.0017] |

All nine rows: 5,077,150, base rate 0.057.

### With forecast rain

All nine companies, on the lead rows (base rate 0.063, 1,928,619 rows at each lead).

| Lead | Challenger | Boosted | Difference [95%] | AUC challenger / boosted |
|---|---|---|---|---|
| 0 | 0.03905 | **0.03784** | +0.0012 [+0.0007, +0.0018] | 0.926 / 0.932 |
| 1 | 0.04200 | **0.04153** | +0.0005 [−0.0002, +0.0011] | 0.908 / 0.911 |
| 2 | 0.04466 | **0.04376** | +0.0009 [+0.0001, +0.0017] | 0.904 / 0.907 |
| 3 | 0.04666 | **0.04578** | +0.0009 [−0.0001, +0.0021] | 0.891 / 0.890 |
| 4 | 0.05006 | **0.04919** | +0.0009 [−0.0004, +0.0023] | 0.879 / 0.879 |

These boosted scores cannot be compared with D2's lead table. That table scored a different model
(the hold-out), and it fed the 7-day, 30-day and antecedent-index features from ERA5-Land.

### The conditions

1. **A real gain overall: FAIL.** The challenger's Brier is higher, not lower: 0.0372 against
   0.0362. The difference is +0.0011, with an interval of +0.0005 to +0.0017, wholly above zero.
2. **No company clearly worse: FAIL.** At four companies the interval lies wholly above zero:
   Anglian, Thames, United Utilities and Wessex.
3. **Not worse with forecast rain: FAIL.** The challenger's Brier is higher at all five leads.
4. **Reliability: FAIL** at six companies. In each, the challenger's ECE is above both the boosted
   model's and 0.02:

   | Company | Challenger ECE | Boosted ECE |
   |---|---|---|
   | Anglian | 0.025 | 0.011 |
   | South West | 0.021 | 0.009 |
   | Southern | 0.022 | 0.011 |
   | Thames | 0.038 | 0.024 |
   | United Utilities | 0.021 | 0.018 |
   | Wessex | 0.025 | 0.014 |

   It passes at Northumbrian, Severn Trent and Yorkshire.
5. **More rain does not lower the risk: PASS.**
   - Adding 1 mm to every hour lowered the probability on 1 row of 5,077,150, by 0.0003.
   - Doubling every hour lowered it on none.
6. **Cheap to run: PASS.** The numpy forward pass of the three networks took 5.7 s for 73,150 rows
   (14,630 overflows × 5 days). Its logits agree with PyTorch's within 0.000002 on 1,000 rows.

**The challenger is not adopted.** Nothing is deployed, and this document is the record. Condition 1
alone answers Ethan's question. On this data, a network reading the hourly rain gives no gain over
the boosted trees. It does measurably worse: its Brier over the nine companies is 3% higher, and
the 95% interval of the difference lies wholly above zero.

### Observations, not tested and not grounds for any change

- **Layer 1 alone, the network also loses.**
  - Over the nine together: 0.0372 against the boosted layer 1's 0.0364.
  - No single seed beat the boosted layer 1 overall. The best, seed 1, scored 0.0369.
  - The network's layer 1 is a little better at Northumbrian (0.03325 against 0.03362) and level at
    Yorkshire (0.04080 against 0.04083).
- **Layer 2 hurts the network where it hurt the boosted model in D2.**
  - Anglian: 0.0269 for layer 1 alone, 0.0297 with offsets.
  - Thames: 0.0310 for layer 1 alone, 0.0343 with offsets.
  - This fits D2's observation that offsets fitted on one wet year carry that year into the next.
- **The network forecasts too high in the middle of the range.**
  - Over the nine, forecasts of 0.1 to 0.2 averaged 0.142, and 9.9% of those site-days spilled. The
    boosted model's 0.142 came true 12.9% of the time.
  - At Thames, the challenger's forecasts of 0.4 to 0.5 came true 26.8% of the time.
- **Storm timing was not the weak point with forecast rain.** The stated worry was that a model
  leaning on the hour a storm falls would lose more when the forecast gets the hour wrong. The gap
  is largest at lead 0 (+0.0012) and no larger at lead 4 (+0.0009).
- **Every seed stopped learning usefully after one pass.** *Inferred, not checked:* after one epoch,
  the network begins to fit the particular storms of the 2024 weeks it trains on. A different
  setting might close the gap. But 2025 has now been seen, so any new setting needs its own
  pre-stated test, scored on a year no network has yet been scored on (2026, once its files are out).

### What was not done

- There is no numpy forward pass in `src/dipcast/model/`, and no test of it. Both were for adoption
  only. The forward pass used for condition 6 is in `scripts/train_nn.py`.
- `spill_model.pkl` and `lead_calibration.json` are unchanged.
