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
