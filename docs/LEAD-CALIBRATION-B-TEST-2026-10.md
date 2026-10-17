# Lead calibration, option B: the test, stated before any run

Written 17 October 2026. It is committed and pushed before two things:
- the map is fitted;
- any live forecast in the window, or any row of the published live scores, is read.

Results go below the line at the end. Nothing above that line changes after a result is seen. Review
task A1 (`docs/REVIEW-2026-10-16.md`, finding 3.1); the record that led here is
`docs/NINE-COMPANY-MODEL-TEST-2026-10.md` (PR #251), section "Lead calibration (A1)".

## Why

The per-lead isotonic map in `data/processed/lead_calibration.json` was fitted for the United
Utilities 2023-24 hold-out model. Production runs the 2023-25 refit (`spill_model.pkl`, `trained_on`
"United Utilities 2023-2025 (refit on all years; verified on 2025 before refit)").

A map for the production model cannot be fitted on United Utilities' 2025: that model has seen
it. It never saw any other company's overflows, so their 2025 rows are out of sample for it.
That is option B.

Ethan, 17 Oct 2026: "Option 3: ship the record only. Then pre-state a test for option B (map
fitted on non-UU rows, cross-fitted by month, with the expected bin moves and a four-week live
check) and run it as its own task." The live four weeks decide adoption.

## Seen before writing

From the 2025 replay in PR #251:
- leads 0 to 4 pooled;
- the eight English companies other than United Utilities;
- overflows in cells with archived lead forecasts;
- labels from the EA start/stop files;
- B's map cross-fitted by month: fitted on odd months and scored on even, then the reverse.

| System, 2025, non-United Utilities rows | Brier |
|---|---|
| Today: production model + the map in use | 0.03941 |
| Production model, no map | 0.03931 |
| **B: production model + a map fitted on these rows, cross-fitted by month** | **0.03818** |

| Company | Rows | Observed | Mean forecast today | Mean forecast B | Brier today | Brier B |
|---|---|---|---|---|---|---|
| Anglian | 458,075 | 0.0363 | 0.0211 | 0.0346 | 0.03041 | 0.03010 |
| Northumbrian | 728,175 | 0.0484 | 0.0276 | 0.0435 | 0.03684 | 0.03548 |
| Severn Trent | 1,275,675 | 0.0451 | 0.0304 | 0.0475 | 0.03280 | 0.03189 |
| South West | 540,200 | 0.0855 | 0.0640 | 0.0903 | 0.05128 | 0.04995 |
| Southern | 279,225 | 0.0466 | 0.0341 | 0.0520 | 0.03143 | 0.03043 |
| Thames | 374,125 | 0.0547 | 0.0381 | 0.0594 | 0.04202 | 0.04186 |
| Wessex | 501,875 | 0.0531 | 0.0379 | 0.0581 | 0.03809 | 0.03748 |
| Yorkshire | 1,408,900 | 0.0704 | 0.0437 | 0.0649 | 0.04647 | 0.04420 |

By bin of today's calibrated forecast (non-United Utilities rows):

| Bin | Rows | Observed | Today | B |
|---|---|---|---|---|
| 0.0-0.1 | 5,009,832 | 0.022 | 0.012 | 0.022 |
| 0.1-0.2 | 270,273 | 0.218 | 0.142 | 0.216 |
| 0.2-0.3 | 122,807 | 0.358 | 0.243 | 0.356 |
| 0.3-0.4 | 61,658 | 0.479 | 0.346 | 0.483 |
| 0.4-0.5 | 33,833 | 0.588 | 0.445 | 0.589 |
| 0.5-0.6 | 24,333 | 0.679 | 0.547 | 0.686 |
| 0.6-0.7 | 18,225 | 0.769 | 0.649 | 0.777 |
| 0.7-0.8 | 14,243 | 0.817 | 0.753 | 0.832 |
| 0.8-0.9 | 10,449 | 0.876 | 0.832 | 0.887 |
| 0.9-1.0 | 597 | 0.856 | 0.931 | 0.924 |

By the forecast rain for the target day: today's mean, then B's, then observed.
- Under 1 mm: 0.009, 0.016, 0.020.
- 1-5 mm: 0.043, 0.070, 0.070.
- 5-10 mm: 0.106, 0.158, 0.149.
- 10 mm or more: 0.244, 0.325, 0.301.

**Also seen:** the live Accuracy page's published summary.
- Forecasts there run high, not low: the 0.4-0.5 bin verifies at 28%.
- Thames and Southern forecast six to eight times their observed rate (review of 16 Oct, section 3).

**Not seen:** I have not opened `data/verification_live.csv` (the scored live rows) or the forecast
log. Their size was read from a HEAD request: 6,555,677 bytes, last modified 17 Oct 2026 10:26 UTC.

## The candidate

- **Model:** unchanged. `data/processed/spill_model.pkl`, SHA-256 beginning `faa7917e2be725a9`.
- **Map:** per lead 0-4, isotonic, as `scripts/verify_leads.py` fits it, from PR #251's commit
  `1a81ca2`:

      uv run python scripts/verify_leads.py 2025 --model spill_model.pkl --exclude "United Utilities"

  - **Rows:** the 2025 site-days of the eight other English companies' overflows in cells with
    archived lead forecasts. That is 3,050 overflows in the replay. They are covered by the EA
    files under the rule in `model/training.site_years`.
  - **Rain:** ERA5-Land, plus the archived forecasts from `data/cache/rain` and
    `data/cache/rain_nine`.
  - **Fit:** the saved map is fitted on all twelve months.
  - **Identity rule:** a lead whose cross-fitted Brier is not below the raw Brier is saved as an
    identity map.
- **Where it is saved:** `docs/LEAD-CALIBRATION-B-TEST-2026-10-map.json`, with its SHA-256 under
  the line. `data/processed/lead_calibration.json` does not change during the test.
- **The map's `model` field** is the production model's `trained_on`. Deployed, it would meet the
  test in `tests/test_training.py` (PR #251).

## Expected moves, stated now

From the replay above. Not yet a property of the saved map; that map's own moves are written under
the line before the window opens.

- **The mean forecast goes up at every one of the eight companies,** by 0.013 (Anglian) to 0.026
  (South West), and in every rain band.
- **The bins go up below 0.9:** by about 0.07 to 0.14 in the 0.1-0.6 bins and 0.01 at 0.0-0.1.
  The 0.9-1.0 bin barely changes.
- **United Utilities:** the same map applies there. Its moves are computed after the fit and
  written under the line before the window opens.
- **My prediction (inferred, not a condition).** The live page shows 2026 forecasts already too
  high, and B raises them. If the 2026 live labels behave as they did up to 16 Oct, B scores
  **worse** live than today in the 0.0-0.4 bins, and the check below fails. 2025's EDM labels and
  2026's live-feed labels disagree in direction. This test finds out which one the map should
  follow.

## The live check

- **Rows.** The scored live forecasts the site publishes: `data/verification_live.csv`, one row
  per overflow, target day and lead, scored by `forecast_log.verify_live` under its coverage
  rules. Columns: `forecast_raw` (the model's probability before the map), `lead`, `company`, `day`
  and `observed`.
- **Paired.** Both maps are applied to the same `forecast_raw`, at lead `min(max(lead, 0), 4)` as
  `forecast.calibrate_by_lead` does:
  - **today:** `lead_calibration.json` as on main on 17 Oct 2026, SHA-256 beginning
    `734202bc7f22af38`;
  - **B:** the saved map.

  Nothing is deployed. The check is prospective because the window is in the future.
- **Window.** Target days 18 October to 14 November 2026, 28 days. Read on or after 16 November.
- **Sanity check.** "Today" recomputed must match the logged `forecast_calibrated`, with a mean
  absolute difference under 0.001. If it does not, the check stops and reports.
- **If the model changes.** If `spill_model.pkl` changes on main inside the window, the window
  ends the day before. If that leaves fewer than 14 days, the check restarts on the new model.
- **Minimum data.** At least 200 scored rows with `observed` = 1 in the window. If there are
  fewer, the window extends by 14 days, once. Then it is called inconclusive.
- **Pass: all three are required.**
  - **L1.** Brier(B) < Brier(today) over every row in the window.
  - **L2.** At every company with at least 50 rows observed = 1 in the window,
    Brier(B) ≤ 1.02 × Brier(today).
  - **L3.** ECE(B) ≤ ECE(today) over every row. ECE is the row-weighted mean |forecast −
    observed| over ten equal-width bins.
- **If it passes:**
  - the map replaces `lead_calibration.json`;
  - the strict xfail mark comes off `tests/test_training.py`;
  - the Method page's "Skill with real forecasts" paragraph says what was done.
- **If it fails:** nothing is deployed, A1 stays open, and this document is the record.
- **Secondary, reported but not deciding.** The same paired comparison on the rows already
  published before 18 October. They have not been read. They are read only after the map is fitted
  and saved.

The check is `scripts/lead_calibration_b_check.py`, committed with this statement.

## Order

1. Push this statement and the check script.
2. Fit the map. Commit it with its SHA-256 and its expected moves, including United Utilities',
   under the line.
3. Run the secondary check on the rows before 18 October and report it.
4. On or after 16 November, run the primary check and adopt B or keep the record.

---

## Results

(Nothing below this line yet.)
