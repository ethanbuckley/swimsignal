# Pre-registered evaluation 2027, amendment 4: persistence and a rain rule as secondary references

Version 1, filed 10 November 2026. Amends [the 2027 pre-registration](PREREGISTRATION-2027.md), which allows dated
amendments before 1 May 2027. Amendments 1 to 3 are written in that file's section 17. This one is filed as its own
document so the protocol file, its frozen files and their recorded hashes stay exactly as they are. A later
amendment that changes anything here is a new dated version of this document or a new amendment; version 1 stays as
written.

Asked for by the strategy review of 6 November 2026 (step 5 of its 90-day list: put the simple baselines on the
Accuracy page with intervals and file the pre-registration amendment now). The draft in
[the interim usefulness read](INTERIM-USEFULNESS-2026-10.md) ("Draft amendment") was the starting point; the
differences are listed at the end.

## What does not change

- The four primary outcomes (section 8), their reference (the season/site climatology, section 7), the rule that
  decides them, the data (section 4), the matching rules (section 5), the bootstrap (section 10), the candidates rule
  (section 12) and the freeze steps (section 15).
- Every frozen file. Checked on 10 November 2026 against the latest hash the protocol records for each:

| File | SHA-256 now | As recorded |
|---|---|---|
| `scripts/evaluate_2027.py` | `95176d2086f224122d899aff38cf3dd8f6cbbc8fe0dff760368ee5dbe56c5d40` | yes (amendment 3) |
| `scripts/make_eval2027.py` | `d28ab0c7b998190445ef00716c0fca7d6f19a70c0086aaff17dc49bcf8117912` | yes (amendment 2) |
| `data/eval2027/sites.csv` | `1108747686e456e8e9abd4c7d1c319abae7a6c86da815ae177ad1d4a9ad10713` | yes (section 13) |
| `data/eval2027/climatology.json` | `e2212cf7d57a7c6df82c37f7ff6510ccc70d7cf1b62ab40035751fd9f26934e0` | yes (section 13) |

  `uv run pytest tests/test_evaluate_2027.py` passes (19 tests). `docs/PREREGISTRATION-2027.md` is unchanged by this
  amendment: SHA-256 `a11ff99147c013d6b754363394a42c37f6703bfc0f57f25c0245ae5436ab1f1a`, as on main at `d644dc90`.

## Why

Section 7 compares the spill forecasts with climatology only. A swimmer or an organiser can do without SwimSignal by
looking at the overflow map ("it is spilling, or spilled recently") or at the rain forecast. The interim read of the
live record, 29 September to 23 October 2026, found skill against climatology of about 0.2, but skill against those
two rules near 0.07 in advance with every interval crossing 0, and persistence ahead of the forecast on the same day.
A claim that the forecast is useful needs these rules beside climatology. This amendment adds them as **secondary**
references. Nothing here is a primary outcome.

## The two rules

The same rules, in the same code, as the Accuracy page from 10 November 2026
([SIMPLE-REFERENCES-LIVE-2026-11.md](SIMPLE-REFERENCES-LIVE-2026-11.md), stated before any score):

- **Reference P, same-day persistence.** For a row issued at time T, the overflow is active if its poll record shows
  it spilling at T, or at any moment in the 48 hours (`config.RECENT_SPILL_HOURS`) before T, counting only spill that
  had started by its last current reading at or before T. Spill intervals come from `live_history.parquet` by
  `model.live_status.poll_events`, merged. A current reading is a poll in `poll_log.parquet` whose half-hour slot in
  `live_coverage.parquet` shows a current reading of that overflow. The status is known when those readings cover the
  48 hours before T with no stretch over 8 hours, the stretch to T included. Otherwise the row has no P chance.
- **Reference R, the rain rule.** The logged `rain_mm` for the target day plus that for the day before (from the same
  issue for leads 1 to 4; for lead 0, from the latest logged forecast of that overflow for the day before), over
  10 mm, strictly. A row missing either day has no R chance.
- **Their chances.** For a row with issue day I and lead L, each side's chance is (spills + 0.5) ÷ (rows + 1) over the
  scored live rows of lead L on that side, all companies and all overflows pooled (not only the eligible list), where
  the rule can be applied, with target day from I − 28 to I − 1; none if that side has fewer than 100 such rows. For
  the first four weeks of the season the window reaches back into April 2027. Nothing from day I or later enters.

## Rows

The primary spill analysis's rows (section 4 and `evaluate_2027.evaluate_spills`: eligible overflows in
`data/eval2027/sites.csv`, target days 1 May to 30 September 2027, leads 0 to 4, the frozen model's forecasts after
section 12's version split) on which both P and R have a chance. The reference rows' coverage is reported by company
and by 7-day block: the rows with a known status, with both days' rain, and with both, against the primary rows.

## What is reported

For the strata of section 7 that the rows support: all companies at lead 0, at leads 1 to 4 pooled and at each lead;
each company at lead 0 and at leads 1 to 4; and river, lake and both at lead 0 and at leads 1 to 4.

- Brier score of the forecast and of each reference, on the same rows.
- Skill against P, against R, against the season/site climatology on these rows, and against **the best of the
  three** in each draw (the lowest Brier score of the three in that draw; stricter on the forecast than any one).
- 95% intervals from section 10's bootstrap as written: overflows and 7-day blocks from 1 May 2027, 2,000 draws from
  `default_rng(20270501)`, percentiles 2.5 and 97.5. The references' chances are held fixed within a draw. A draw in
  which a stratum has no weight, or a reference's Brier score is 0, gives no skill for it and is counted.
- The chances each rule used, by lead and side, and the rows they were fitted on.

**Wording, descriptive only.** In a stratum, the forecast "beats" a rule when the lower end of its interval of skill
against that rule is above 0, "does worse than" it when the upper end is below 0, and is "not shown either way"
otherwise. A company or water stratum with fewer than 20 spill rows among its reference rows is reported as too few to
judge. None of this changes section 8's rule, and none of it is a fifth primary outcome.

## The code

- `src/dipcast/simple_references.py` (`score`, with `score_from` and `score_to`) and `scripts/simple_references.py`,
  added on 10 November 2026. The script reads the published `verification_live.csv` and the `state` release's
  `dipcast.duckdb`, `live_history.parquet`, `live_coverage.parquet` and `poll_log.parquet`, read only, and applies
  the primary analysis's selection with `evaluate_2027.read_published`, the site list, the season/site climatology and
  `evaluate_2027.split_versions`. Their SHA-256 at filing are at the end of this document.

- The run uses both files as they are at the tag `eval-2027-model`. Freeze step 4 records their SHA-256 at the tag
  beside the model files. A change to either after the tag makes this secondary analysis a separately labelled one.
- The run, after section 15's step 7, from the same saved files:

      uv run python scripts/simple_references.py --scored verification_live.csv --state <saved state files> \
          --to 2027-09-30 --score-from 2027-05-01 --sites data/eval2027/sites.csv \
          --climatology data/eval2027/climatology.json --repo . --tag eval-2027-model \
          --out results-2027-simple-references.json

- The forecast log and the three poll files are saved, with their SHA-256, at the 31 October 2027 snapshot, as
  section 15 already asks for the log. The poll files are added to that step by this amendment.

**Dry run, not a result.** On 10 November 2026 the script ran in this mode on the live record (state release of
9 November 2026, 21:22 UTC; target days scored from 20 October to 8 November 2026, 200 draws) to check that it reads
the list, the climatology and the version split and writes every stratum. It says nothing about 2027.

## Known weaknesses

- The status rebuild reads event times the feeds published after T and dated back, which flatters P a little (the
  interim read's cross-check: 50 of 812 active rows).
- P needs the pipeline to have run at least every 8 hours in the 48 hours before the issue. In autumn 2026 whole issue
  days failed this when the site ran only a few times a day (27–28 October, 3–4 and 6–7 November). If that recurs in
  2027 the reference rows will be fewer than the primary rows and drawn from days the pipeline ran often.
- R uses forecast rain as logged, not rain as it fell.
- The rules' chances pool all companies, as the forecast's skill is pooled. A company whose spill rate differs from
  the pool gets a poorly pitched rule, which flatters the forecast there; the per-company strata show it.

## Differences from the interim read's draft

- Chances are fitted on the 28 days before each issue, not frozen on 1 May 2027 from the whole autumn and winter, so
  they follow the season and stay a forecast someone could have issued that morning. The draft's second version
  (refitted on the 2027 season itself, flattering the rules) is dropped.
- Only the 10 mm rain rule is a reference. The draft also reported 5 mm; two thresholds invite picking the better one.
- The shadow's logged `spilling_at_issue` does not replace the rebuilt status where it exists. It is logged only from
  20 October 2026 and only for "spilling now", so using it would mix two rules; one rebuilt rule is applied
  throughout, with its weakness stated above.
- The code is a separate module and script rather than a change to `scripts/evaluate_2027.py`, so that file and its
  recorded hash are untouched.

## Hashes at filing
