# Option B and layer 2's recency weight: a note for Ethan before any run

Written 25 October 2026. A note, not an amendment. `docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md` (the statement) is
not changed by it. Nothing for option B has been fetched, imported, written or scored.

## What is wrong in the statement

The statement says, under "The arms": "All offsets use prior strength 15 and recency 1, as now."

"As now" is not true of production. `docs/MODEL-PROVENANCE-2026-10.md` (PR #348) shows that main's
`spill_model.pkl` was fitted with layer-2 recency **0.25**: a year k years older than the newest counts 0.25^k. Every
one of its 2,271 United Utilities offsets is reproduced exactly at 0.25, and at no other value tried. `train.py`'s
default was 1.0 and the file did not record the setting, so the statement repeated `train.py`'s default.

## Why it matters for option B

- **Arm P** is production: United Utilities offsets at recency 0.25, 0 elsewhere.
- **Arms B and B0** refit United Utilities too, on 2024 to 2026 records, at recency 1.
- So B − P mixes three changes at United Utilities: the start-date rule, the dead-monitor rule, and a move from
  recency 0.25 to 1. At the other eight companies P has no offsets, so there it mixes only the first two with the
  extension.
- **Condition 5** ("No worse where nothing changed ... This is the extension on its own") is affected most. On
  unchanged United Utilities overflows, B differs from P by the recency weight alone, so condition 5 there measures
  the recency change, not the extension.
- **Condition 6** (B against B0) is not affected: both arms use the same recency.
- **"Not chosen, and why"** turns down "a trailing window (`recency` below 1 ...)" because it "forgets an
  overflow's level even when nothing changed". Production already does that at United Utilities.

## The choices

Each would be a dated addendum below the statement, written before the harness or any data, as the statement
allows for its own order of work. None is made here.

1. **B and B0 at recency 0.25, production's setting (recommended).** B − P then measures the start-date rule, the
   dead-monitor rule and the extension to eight companies, with layer 2 fitted the way production fits it. B0 still
   isolates the start dates. No arm is added. The addendum must say how `fit_site_offsets` counts a year's age in a
   monthly refit: it uses the calendar year, so a fit dated 1 March 2026 weights 2026's two months at 1, 2025 at 0.25
   and 2024 at 0.0625. The cost: B inherits production's down-weighting of older years. This is the behaviour the
   statement turned down as an alternative to start dates, but it is what the site does today.
2. **Keep recency 1, add an arm P1.** P1 is production's layer 1 with United Utilities offsets refitted at
   recency 1 on the same records and monthly look-back fits, and 0 elsewhere. Decide on B − P1 (start dates and
   extension) and report P1 − P (the recency change). The decision to deploy then rests on two comparisons, and the
   run grows by one arm.
3. **Keep the statement as it is.** Add only a sentence saying B − P includes the move from 0.25 to 1 at United
   Utilities. The conditions then judge the whole package. The result cannot say which part helped or hurt, and
   condition 5 at United Utilities becomes a recency test.

## Approval

The statement says Ethan approves it by merging the PR that carries it. PR #325 was merged on 24 October 2026 at
18:50 UTC, with ten other PRs. So by its own wording it is approved. Its "Order of work, after approval" has not
started: no import, fetch, harness or score. An addendum made now still comes before any data, which is what the
house rule needs.

## Also noted

- PR #333 (company calibration) says its recency 1 is "Exactly as `fit_site_offsets` does for United Utilities".
  Production used 0.25. It does not change #333: its offsets are fitted on one four-week window, inside one year,
  so the recency weight has no effect there, and production's United Utilities offsets are kept.
