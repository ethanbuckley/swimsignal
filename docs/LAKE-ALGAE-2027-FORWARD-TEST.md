# Satellite algae readings in summer 2027: a forward test, stated before the season

Drafted 27 October 2026, at Ethan's request ("draft the 2027 forward statement for the third question without running
anything"). It is a draft for review, not yet approved. Nothing here has been run, and no 2027 data exists. Results go
below the line at the end, after 30 September 2027. Nothing above the line changes once it is approved and frozen.

## Why

The retrospective test (`docs/LAKE-ALGAE-SATELLITE-TEST-2026-10.md`, #377, run 26 October 2026) found that a Sentinel-2
NDCI reading did not add to the month and the last EA check for "algae seen" at English lake bathing waters (AUC
0.60, label "Possible harm"). Two hints came out of the same data, as description only:
- **Objectionable algae** (the EA's top level): raw AUC 0.81 on 20 events, too few to judge.
- **Lake by lake:** the reading ranked "algae seen" well at Frensham Great Pond (0.92) and the Serpentine (0.73), and
  badly at Coniston Water (0.14).

Those hints were found by looking at 2020–2026. Testing them again on the same years would be fishing. The only honest
test is data nobody has seen: summer 2027.

The questions:
- **Q1.** Does the reading rank the EA's *objectionable* algae checks at lake bathing waters in 2027?
- **Q2.** At the *lowland* lake bathing waters (not the Lake District), does it add to the month and the last check
  for *algae seen* in 2027?

What it can never answer, whatever the result: whether algae are toxic (Sentinel-2 has no band for the pigment of
blue-green algae), or whether water is safe.

## A condition that comes first

PR #386 tests whether the same reading tracks EA laboratory chlorophyll (determinand 7887) in English lakes, on
2020–2026 data. It is run after this draft is written. **If #386 is labelled a fail, this statement is withdrawn**
(a dated note below the line, before 1 May 2027), because a reading that does not track measured chlorophyll gives no
reason to expect it to track blooms. If #386 passes or is "too few to judge", this statement goes to review as written.

## Frozen before the season (by 1 May 2027)

- **The reading:** NDCI exactly as #377 states it (Sentinel-2 Collection 1 Level-2A on Earth Search; the water mask,
  connected piece, core pixels, size rule, 80% clear rule, median over clear core pixels). The masks are #377's, made
  from 2020–2026 scene classification, frozen by their hash (`sizes.json` and `cores/` in #377's run folder). No new
  mask is made from 2027 scenes.
- **The sites:** #377's 14 sites past the size rule, on 8 water bodies. **Lowland** for Q2 means every water body
  outside the Lake District: Rutland Water, Colwick Country Park West Lake, Cotswold Country Park lake, the
  Serpentine, Frensham Great Pond (6 sites). Lake District: Windermere, Coniston Water, Derwent Water (8 sites).
- **The outcome:** the EA sampler's visual algae check (determinand 4824), 1 May to 30 September 2027, levels as
  `algae.LEVELS`. Q1: level 3 (objectionable). Q2: level 1 or more (algae seen).
- **Pairing:** the latest usable scene dated 0 to 3 days before the check, as #377.
- **Models and references (Q2):** as #377: R1 the training base rate; R2 month + last check; M2 R2 + the reading;
  logistic, C = 1. Fitted on 2020–2026 paired rows at the lowland sites only, then **frozen** (file hash in the
  amendment). Scored on 2027 rows without refitting.

## The gates

- **Q1:** at least 15 objectionable checks with a reading, at 3 or more water bodies. Below that it is "too few to
  judge" for 2027. Inferred from #377's counts (2, 4, 1, 4 and 9 paired objectionable events in 2021 and 2023–2026),
  one season will most likely be too few. **If so, 2027 and 2028 are pooled** under this same statement, with no score
  looked at after 2027: only the gate counts are reported then.
- **Q2:** at least 30 checks with algae seen, at 3 or more lowland water bodies.

## Pass conditions (two questions, so every interval is 97.5%)

Intervals by cluster bootstrap over water bodies, 2,000 draws, numpy `default_rng(20270501)`.

**Q1 passes if all hold:**
1. Raw AUC of the reading against objectionable at least 0.70, interval lower end above 0.50.
2. Placebo: the readings shuffled within each water body and season, 200 times; the real AUC above the 95th
   percentile.
3. No water body with 3 or more events has an AUC below 0.40 (no single lake carries the result in the wrong
   direction).

**Q2 passes if the primary label is Better and all hold:**
1. Primary: frozen M2 against frozen R2 on 2027 lowland rows, Brier gain, labelled with the near-miss framework
   (`docs/LAKE-ECOLI-LINE-TEST-2026-10.md` addendum; "Possible harm" counts as harm). B and H as #377 for "algae
   seen": B = 0.0036, H = 0.0018.
2. Raw AUC at least 0.65, interval lower end above 0.50.
3. Placebo as in Q1, condition 2.
4. Calibration: mean frozen-M2 forecast within 0.03 of the 2027 lowland rate.

"Promising, not shown" on Q2 is reported and not adopted. A second promising result is not stacked on the first.

## What follows

Nothing on the site changes because of this statement or its result. A pass means Ethan decides whether lake spots
show a dated satellite note ("greener than usual for this lake"), never "toxic", "blue-green" or "safe", and it would
come in its own PR. A fail or too few ends this line of work for those questions.

## Running (after 30 September 2027)

- From a `git archive` of the frozen commit, as #377: stage 1 for 1 May to 30 September 2027 only (about one seventh of
  #377's stage 1: estimated 4,000 requests and 0.7 GB at #377's measured costs; AWS buckets 16 at a time, STAC 1 a
  second; caps written in the amendment before any request), features hash committed, the EA checks fetched once
  (one sampling point a request, #377's A3), scoring offline under the group's heavy-run lock, 0 network attempts.
- No Open-Meteo calls. No daily job during the season is needed: the imagery and the checks stay available.

## What is expected, stated now

These are guesses. Q1 will most likely be too few to judge in 2027 alone. Q2: about one chance in four of a pass;
the lowland hint rests on two lakes.

## Seen before writing

- All of #377's results, including the per-water-body AUCs and the objectionable figures quoted above.
- #386 and #385: statements only; neither had been run when this was written.
- No 2027 data exists.

## Still to do before it can run

1. Ethan reviews this draft (or asks for changes).
2. #386's result is recorded; withdraw this statement if #386 fails.
3. Before 1 May 2027: freeze the Q2 models and the masks' hashes in a dated amendment to section 17 of
   `docs/PREREGISTRATION-2027.md`, and write the stage 1 caps.

---

## Results

None yet. Not before 1 October 2027.
