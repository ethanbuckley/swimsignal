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

The wrong recency is one of several ways arm P differs from arms B and B0 at United Utilities. None of the others
was in doubt; this note lists them so that no comparison is read as isolating one thing. From the statement's "The
arms" and "The record each offset is fitted on", and from `scripts/train.py` and `config.EDM_EVENT_FEEDS`:

| At United Utilities | P (production) | B and B0 |
|---|---|---|
| Events | United Utilities' own files on Stream, 2023 to 2025 (`edm_events.parquet`) | The EA's start/stop files, 2024 and 2025 and 2026 to August, then SwimSignal's polls from 28 Sep 2026 |
| Days | UTC days (`train.py` floors UTC) | Europe/London local days |
| Rows that count | `train.py`'s rule: same-year EDM operation of at least 50%, rain present | PR #251's rule for 2024 and 2025, the dead-monitor check for 2026, the live labels' coverage rule for the polls |
| Fitting | Once, on all three years | Monthly, each fit using only earlier days, 1 Jan to 1 Nov 2026 |
| Recency | 0.25 | 1 |
| Start dates | None | B: the change-point rule; B0: none |

So:
- **B − P** at United Utilities mixes all six rows of that table. At the other eight companies, P has no offsets,
  so B − P there is the whole extension: offsets where there were none, fitted B's way.
- **Condition 5** ("No worse where nothing changed ... This is the extension on its own") is not the extension on its
  own at United Utilities. On an unchanged United Utilities overflow, B differs from P in source, days, rows,
  fitting and recency. It is the extension on its own only at the other eight companies, where P is zero.
- **Condition 6** (B against B0) differs only in the start dates, since both arms share every other row of the table.
  It is the one comparison in the statement that isolates a single mechanism.
- **"Not chosen, and why"** turns down "a trailing window (`recency` below 1 ...)" because it "forgets an
  overflow's level even when nothing changed". Production already does that at United Utilities.

## The choices

Each would be a dated addendum below the statement, written before the harness or any data, as the statement
allows for its own order of work. None is made here, and none changes the arms without Ethan choosing it.

1. **Keep the statement as it is, and say what B − P is.** Add only a sentence: B − P is the whole change the site
   would make, including a different source, days, rows, fitting and recency at United Utilities; condition 5 at
   United Utilities measures that package, not the extension. The deciding question, "should the site switch to B",
   is answered as stated. Which part helped or hurt is not.
2. **B and B0 at recency 0.25, production's setting.** This removes one row of the table. B − P still differs in
   source, days, rows and fitting, so it still does not isolate the start-date rule, the dead-monitor rule or the
   extension. It mainly makes B closer to how production weights old years. The monthly refit counts a year's age by
   calendar year: a fit dated 1 March 2026 would weight 2026's two months at 1, 2025 at 0.25 and 2024 at 0.0625.
3. **Keep recency 1, add a reported arm P1.** P1 is B0's own offsets at United Utilities (same events, days,
   rows, monthly look-back, recency and dead-monitor check, no start dates) and 0 elsewhere. B − P1 at United
   Utilities then differs only in the start dates, as B − B0 does; at the other eight companies it is the extension.
   P1 − P would show what the record change alone does at United Utilities. This adds an arm to an approved test,
   so it needs Ethan's explicit choice; the deciding comparison stays B − P.

No recommendation is made between them here. Choice 1 changes least and answers the deployment question. Choice 3
is the only one that holds the record dimensions equal at United Utilities.

## Approval

The statement says Ethan approves it by merging the PR that carries it. PR #325 was merged on 24 October 2026 at
18:50 UTC, with ten other PRs. So by its own wording it is approved. Its "Order of work, after approval" has not
started: no import, fetch, harness or score. An addendum made now still comes before any data, which is what the
house rule needs.

## Also noted

- PR #333 (company calibration) says its recency 1 is "Exactly as `fit_site_offsets` does for United Utilities".
  Production used 0.25. It does not change #333: its offsets are fitted on one four-week window, inside one year,
  so the recency weight has no effect there, and production's United Utilities offsets are kept.
