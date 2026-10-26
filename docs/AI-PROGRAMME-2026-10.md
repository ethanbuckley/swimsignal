# AI and data programme, autumn 2026: status map

Started 26 October 2026, after Ethan accepted Codex's assessment of which AI systems are worth building. This is the
one place that says what each piece is, where it stands and what is waiting on a decision. Each piece is a separate
draft PR. None is merged or deployed by this programme, and none changes the live site, the live models, or the A8,
option B or shadow windows.

Last updated: 26 October 2026, evening. Test counts were rerun by the coordinator on each branch.

## The map

| Piece | PR | What it is | Tests | Evidence | Costs and limits used | State |
|---|---|---|---|---|---|---|
| Satellite algae | #377 | statement revised before any run: the CLMS lake product is benchmarked first, with a decision rule; coverage prototype; full harness (stages 1 and 2) | 50 pass | CLMS LWQ 100 m v2 is 10-day composites from Sep 2024, lag up to 4 days, shores not flagged, one granule over Great Britain (in Scotland); inferred: none of our 12 lakes covered. Sentinel-2 C1: scale and offset on all 7,317 items, no C1 items in 2022, Millerground 323 core pixels, Ladies Pond 0. No red or red-edge band read, no check fetched, nothing paired | 522 requests, 113.7 MB (ledger checked: SCL reads only); per-run caps 300 requests and 100 MB, one fired | statement ready for review; stage 1 not run |
| Advisory finder | #379 | dry-run drafts from the EA incident feed and the Irish EPA, plus 4 whitelisted pages; deterministic, no LLM | 33 pass | EA open incidents answered this Mac: 7 open, 1 at a SwimSignal spot (Frensham Great Pond, algae, since 19 Jun); EPA 0 in force (season over) | 11 requests; no account | prototype done |
| Sampling priorities | #381 | ranking of new sample days by information, high-risk list kept apart; simulation stated before it ran | 7 pass | **fails its stated rule**: beats least-sampled-first in 58.5% of 200 runs (60% needed); beats random in 73% | no network; 112 s | prototype done, rule failed |
| Monitoring anomalies | #382 | 9 review-only flags beyond today's feed checks, on 39 days of saved polls plus injected failures | 25 pass | long_run 7 (4 look stuck, 1 probable false alarm); quiet_monitor 12 (10 worth a look); future_time 4 (UU starts 22-47 min ahead of the poll); company_freeze, known_share_drop and future_time caught injected failures no current check fired on | no network | prototype done |
| River rises | #383 | gauge coverage and rise-arrival delays; dated plan against persistence | 21 pass | 66 of 72 river spots have a same-river gauge, 48 an upstream one; 45 of 55 gauges have 15-minute history from before 2015; arrival lag median 1.5 h (308 events, 23 pairs) | 219 EA requests, all 200, 283 MB; no Open-Meteo | scoped, plan not run |
| Moderation help | #378 | a trigger based on queue volume, then Worker rules, a local model, an outside model only after a DPIA | none (no code) | 0 published reviews, 0 notes showing (26 Oct) | none | written |

## Decisions for Ethan

**Satellite algae (#377)**
0. Read and approve the revised statement; nothing is scored before that. Then: whether to make a free Copernicus
   Data Space account, which CLMS downloads need (catalogue search works without one). Without it, CLMS stays
   metadata-only and NDCI on Sentinel-2 is the reading. Stage 1 is estimated (not measured) at about 27,000 requests
   and 2 GB over 7 capped runs.

**Advisory finder (#379)**
1. Who may approve a draft, and where approvals are kept.
2. What counts as a source: council and water-company pages? Closures?
3. Quote council text (copyright, no open licence) or link only.
4. Expiry rules: whether an open EA incident older than 28 days with no expiry is "stale" (Frensham is); whether the
   Irish expected duration becomes a date.
5. The wording of the line, and whether live runs happen off GitHub's runners (the EA service refuses them).

**Sampling priorities (#381)**
6. Whether to pursue it. A plain rule, "least-sampled sites on wetter days", may capture most of the value.
7. Whether to ask a partner about a randomised sampling arm. That is outreach; none was done.

**Monitoring anomalies (#382)**
8. Which flags go on the data-quality page (proposed: long_run, and quiet_monitor worded as a question to the
   company), and which go into build warnings only.
9. **A side finding for the live model, separate from this programme.** `transport._counted` counts a finished
   spill only from its event end (checked in the code). 28 United Utilities records said "not discharging" with no
   event end, 5 of them stopped 10 to 19 h before the poll, so those spills do not count in "right now". The effect
   on forecasts is not measured. Filling the end from the status start would be a model change.

**River rises (#383)**
10. Whether to run the stated plan, no earlier than 2 November 2026. It needs about 1.5 GB of EA history over two or
    three capped runs, and radar rain before about 21 November, while the oldest months are still on AWS.
11. Whether to show an upstream gauge's rise as a plain observation. No model needed; a product call.

**Moderation (#378)**
12. The trigger numbers.

## What was learned

- Upstream gauges give about an hour of warning at most river spots (median arrival 1.5 h, before a 0.5 h median
  publication delay and the build interval). Several hours would need rain.
- An information-based sampling ranking did not clearly beat the simple coverage rule, even in a made-up world built
  to suit it.
- The overflow feeds held up over 39 days for the failures that would hide every spill at once (freezes, recoded
  status, new ids): 0 real flags. The real issues are single monitors: stuck "discharging", quiet through storms, or
  missing event ends.

## Rules every piece follows

- Draft PRs only. No merges, deploys, outreach, purchases, accounts or credential changes.
- Statements are written before any data that could judge them is read. Anything seen first is listed.
- Heavy runs wait for the group's shared `heavy-run.lock`. Public fetches have caps written down first. No piece uses
  Open-Meteo calls.
- Algae blooms are kept apart from toxins and from E. coli. A river-rise figure is not a swimming-safety forecast.
- An advisory is always a draft a person approves, and never changes a level.

## Not in this programme

- A swimmer chatbot, pollution from photos, and camera drowning detection: ruled out on 26 October 2026.
- Between-image bloom forecasting: a separate test, stated later, only if detection works.
