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
6. **Cheap to run.** The numpy forward pass for every overflow in `overflows.geojson` for five days
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

(Nothing below this line yet.)
