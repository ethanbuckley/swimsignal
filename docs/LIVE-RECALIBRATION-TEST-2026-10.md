# Live recalibration test (pre-stated, 11 October 2026)

Written and committed before any correction was fitted or any split of the data was looked at.

## Question

Spill chances look too high above about 10% on the live record, and much too high for some
companies. Would a correction fitted on live scored overflow-days improve forecasts it was not
fitted on?

## What was seen before writing this

Only the aggregate tables in `data/verification.json` from the 19:45 BST build of 11 Oct 2026:
the 10-bin reliability table (forecast 0.444 in the 0.4-0.5 bin against 0.268 observed; 0.757
against 0.405 in 0.7-0.8) and the per-company means (Thames Water 0.022 forecast against 0.002
observed, Southern Water 0.035 against 0.003, United Utilities 0.119 against 0.120). No split by
day, no fitted correction, no held-out score.

## Data

`verification_live.csv` as published by that build: 48,090 overflow-days, target days
29 Sep to 10 Oct 2026 (12 days), 9 companies, leads 0 to 4. SHA-256
`997f12a91a1ebbffcbb769c1bdae5789c1a7f57ce6afdebf34b2a2b9ceaabc91`. Columns used: `company`, `day`, `lead`, `forecast_calibrated` (what the site
uses), `observed` (0/1).

## Candidates (fixed here)

- **A. Isotonic.** Isotonic regression of `observed` on `forecast_calibrated`, pooled over
  companies and leads, clipped to [0.001, 0.999].
- **B. Company intercepts.** Logistic regression of `observed` on logit(`forecast_calibrated`)
  (clipped to [0.001, 0.999]) and one indicator per company: a common slope and an intercept per
  company. scikit-learn `LogisticRegression`, C = 100.

## Method

Leave one target day out: for each of the 12 days, fit each candidate on the other 11 days and
predict the held-out day. Pool the held-out predictions. Also a block check: fit on 29 Sep to
4 Oct and test on 5 to 10 Oct, then the reverse.

## Measures

Brier score (pooled and per company), AUC (pooled), reliability in 10 bins, and on how many of
the 12 held-out days each candidate's Brier is lower than `forecast_calibrated`'s.

## Adoption rule

A candidate passes only if all four hold:

1. Pooled leave-one-day-out Brier at least 5% lower than `forecast_calibrated`'s on the same rows.
2. Lower Brier on at least 8 of the 12 held-out days.
3. Pooled AUC not lower than `forecast_calibrated`'s by more than 0.005.
4. Lower Brier in both directions of the block check.

If both pass, the one with the lower pooled leave-one-day-out Brier is preferred. If neither
passes, nothing changes.

## What passing would and would not mean

Twelve autumn days at mostly dry southern companies are a short, weather-dependent record. A pass
says the correction helps on days like these, not in a wet winter or a summer storm season. The E.
coli estimate takes the calibrated spill chances as an input and was fitted without this
correction, so deploying it is a separate decision: apply it to the spill level only, or refit the
E. coli model.

## Result (run 11 Oct 2026 after the commit above; nothing above was changed)

`scripts/live_recalibration_test.py` on the file named above.

**One departure from the plan, found when run:** the file has scored rows on 10 target days, not
12 (29 Sep to 10 Oct, with 2 days unscored). Leave-one-day-out therefore has 10 folds. Condition 2
was run as "at least 8 of the held-out days". Neither candidate's verdict depends on this, because
both fail condition 1.

| | Brier (held out) | AUC | Mean forecast |
|---|---|---|---|
| Current (`forecast_calibrated`) | 0.02494 | 0.8351 | 0.0344 |
| A, isotonic | 0.02447 (−1.9%) | 0.8186 | 0.0286 |
| B, company intercepts | 0.02406 (−3.5%) | 0.8504 | 0.0277 |

Observed rate 0.0278. Days with lower Brier: A 7 of 10, B 6 of 10. Block check: both lower in both
directions.

- **A fails** conditions 1, 2 and 3.
- **B fails** conditions 1 and 2.
- **Verdict: neither passes. Nothing changes.**

What the run does show:
- The current forecasts are too high above 0.1. Held out, the 0.4–0.5 bin is 0.444 forecast against 0.268 observed.
- B brings Southern Water's Brier from 0.0091 to 0.0030 and Thames Water's from 0.0051 to 0.0023. It makes Severn Trent and United Utilities slightly worse.

So the over-forecasting is real, and it is concentrated at the two driest southern companies over these ten autumn days. A correction fitted on them does not yet beat the bar set above. Re-run with the same rule when more days are scored.

## Rerun 1 (pre-stated, 13 October 2026)

Written and committed before the script was run on the new file. Seen before writing: the file's
hash, its row count, and its rows per day and per company. No forecast or outcome column was read.

**Rule.** The one above, unchanged: candidates A and B, leave one target day out, the block check,
and all four adoption conditions. Same script, `scripts/live_recalibration_test.py`, unchanged.

**Data.** `data/verification_live.csv` as published by the 11:52 BST build of 13 Oct 2026 (site
workflow run 38386135087, commit 25e735a), taken from that run's Pages artifact. 58,274
overflow-days, 9 companies, SHA-256
`2b9fa1709dcfcc92174b58de8a156a0984d666d17de8176a0ff3d7cb49ec0fb8`. Its row count equals
`n_scored` in the same build's `verification.json`. Scored target days: 29 Sep to 12 Oct, with
8 and 9 Oct unscored, so 12 days and 12 folds. The 10 days of the first run have the same row
counts per day as before (48,090 in all); 11 and 12 Oct are new (10,184 rows).

**Condition 2.** With 12 held-out days, "at least 8 of the 12" applies as written. The block check
splits at the middle day: 29 Sep to 4 Oct against 5 to 12 Oct.

**What counts as a change worth acting on.** Only a pass under the rule. If a candidate passes,
the PR says so and stays a draft for Ethan. Deploying it is a separate decision (see "What passing
would and would not mean"), and no model or calibration file changes in this PR. If neither
passes, nothing changes.

**Two checks that are not part of the rule.**
1. The script on the first-run days only (29 Sep to 10 Oct). If it gives the 11 Oct numbers, the
   rows for those days were not rescored since.
2. Mean `forecast_calibrated` against observed rate per company, to update the handoff's "about
   ten times" for Thames Water and Southern Water. Descriptive only.

### Result (run 13 Oct 2026 after the commit above; nothing above was changed)

Run offline on the file named above. No departure from the plan.

| | Brier (held out) | AUC | Mean forecast | 11 Oct run |
|---|---|---|---|---|
| Current (`forecast_calibrated`) | 0.02280 | 0.8287 | 0.0327 | 0.02494, 0.8351 |
| A, isotonic | 0.02215 (−2.8%) | 0.8138 | 0.0254 | −1.9%, 0.8186 |
| B, company intercepts | 0.02182 (−4.3%) | 0.8440 | 0.0248 | −3.5%, 0.8504 |

Observed rate 0.0249. Days with lower Brier: A 8 of 12, B 10 of 12 (11 Oct: 7 and 6 of 10).
Block check: both lower in both directions, as on 11 Oct.

- **A fails** conditions 1 and 3. It passes 2 and 4.
- **B fails** condition 1 only: 4.3% lower against the 5% bar. It passes 2, 3 and 4.
- **Verdict: neither passes. Nothing changes.**

Per company, held-out Brier (current / A / B) and observed rate, all 12 days:

| Company | Current | A | B | Observed | n |
|---|---|---|---|---|---|
| Anglian Water | 0.01910 | 0.01865 | 0.01894 | 0.0187 | 7,598 |
| Northumbrian Water | 0.03304 | 0.03388 | 0.03374 | 0.0366 | 628 |
| Severn Trent Water | 0.01957 | 0.01956 | 0.02067 | 0.0206 | 6,073 |
| South West Water | 0.04865 | 0.04455 | 0.04431 | 0.0440 | 750 |
| Southern Water | 0.00827 | 0.00536 | 0.00278 | 0.0028 | 3,960 |
| Thames Water | 0.00519 | 0.00397 | 0.00287 | 0.0029 | 10,469 |
| United Utilities | 0.08254 | 0.08313 | 0.08255 | 0.1054 | 7,137 |
| Wessex Water | 0.00714 | 0.00650 | 0.00638 | 0.0065 | 14,594 |
| Yorkshire Water | 0.03211 | 0.03184 | 0.03177 | 0.0340 | 7,065 |

Reliability, held out: the current forecast is still too high above 0.1. The 0.4–0.5 bin is 0.443
forecast against 0.259 observed (239 rows); 0.7–0.8 is 0.756 against 0.380 (79 rows).

**Check 1 (first-run days only).** The script on the 48,090 rows for 29 Sep to 10 Oct gives the
11 Oct numbers exactly: Brier 0.02494 / 0.02447 / 0.02406, AUC 0.8351 / 0.8186 / 0.8504, days
7 and 6 of 10. Those days were not rescored. The changes above come from 11 and 12 Oct alone.

**Check 2 (mean forecast against observed rate).**

| Company | Forecast | Observed | Ratio | Spill days | Ratio, first 10 days |
|---|---|---|---|---|---|
| Southern Water | 0.0334 | 0.0028 | 12.0 | 11 | 11.8 |
| Thames Water | 0.0199 | 0.0029 | 6.9 | 30 | 9.3 |
| Wessex Water | 0.0202 | 0.0065 | 3.1 | 95 | 2.7 |
| United Utilities | 0.1112 | 0.1054 | 1.06 | 752 | 0.99 |
| Northumbrian Water | 0.0132 | 0.0366 | 0.36 | 23 | 0.32 |

The other four companies are between 0.66 and 1.10. Southern Water is still about twelve times its
observed rate. Thames Water fell from about nine to about seven times, because 11 and 12 Oct had
10 spill days in 1,844 rows (0.0054) against a mean forecast of 0.0116.

What this shows, and what it does not:
- Measured: B moved from 3.5% to 4.3% below the current Brier with two more days, and now fails on
  condition 1 alone. A moved from 1.9% to 2.8%.
- Inferred, not tested: B's gain still comes from Southern and Thames Water, where its Brier is
  about a third and a half of the current one. These two companies have 41 spill days between them,
  so their correction rests on few events.
- Not settled: whether B would cross 5% with more days. Two days moved it 0.8 points, and both
  were drier than average at most companies. The next run should use a file with more new days.
