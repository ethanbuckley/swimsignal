# AI and data programme, autumn 2026: status map

Started 26 October 2026, after Ethan accepted Codex's assessment of which AI systems are worth building. This is the
one place that says what each piece is, where it stands and what is waiting on a decision. Each piece is a separate
draft PR. None is merged or deployed by this programme, and none changes the live site, the live models, or the A8,
option B or shadow windows.

Last updated: 26 October 2026, about 20:00 UTC. Test counts were rerun by the coordinator on each branch. Ethan approved
the #377 statement at about 19:25 UTC and asked for the rest to be built autonomously.

## The map

| Piece | PR | What it is | Tests | Evidence | Costs and limits used | State |
|---|---|---|---|---|---|---|
| Satellite algae | #377 | statement revised before any run: the CLMS lake product is benchmarked first, with a decision rule; coverage prototype; full harness (stages 1 and 2) | 50 pass | CLMS LWQ 100 m v2 is 10-day composites from Sep 2024, lag up to 4 days, shores not flagged, **checked 26 Oct via its public map tiles: no data at any of the 18 English sites in any dekad of summer 2025** (controls in Scotland, Northern Ireland and Europe had data). Sentinel-2 C1: scale and offset on all 7,317 items, no C1 items in 2022, Millerground 323 core pixels, Ladies Pond 0. No red or red-edge band read, no check fetched, nothing paired | 522 requests, 113.7 MB (ledger checked: SCL reads only); per-run caps 300 requests and 100 MB, one fired | **approved 19:25 UTC; stage 1 running** (from 19:30 UTC, under the heavy-run lock, est. 9-10 h); then the features hash is committed, then stage 2 scores once offline |
| Advisory finder | #379 | dry-run drafts from the EA incident feed and the Irish EPA, plus 4 whitelisted pages; deterministic, no LLM | 33 pass | EA open incidents answered this Mac: 7 open, 1 at a SwimSignal spot (Frensham Great Pond, algae, since 19 Jun); EPA 0 in force (season over) | 11 requests; no account | prototype done |
| Sampling priorities | #381 | ranking of new sample days by information, high-risk list kept apart; simulation stated before it ran | 7 pass | **fails its stated rule**: beats least-sampled-first in 58.5% of 200 runs (60% needed); beats random in 73% | no network; 112 s | prototype done, rule failed |
| Monitoring anomalies | #382 | 9 review-only flags beyond today's feed checks, on 39 days of saved polls plus injected failures | 25 pass | long_run 7 (4 look stuck, 1 probable false alarm); quiet_monitor 12 (10 worth a look); future_time 4 (UU starts 22-47 min ahead of the poll); company_freeze, known_share_drop and future_time caught injected failures no current check fired on | no network | prototype done |
| River rises | #383 | gauge coverage and rise-arrival delays; dated plan against persistence | 21 pass | 66 of 72 river spots have a same-river gauge, 48 an upstream one; 45 of 55 gauges have 15-minute history from before 2015; arrival lag median 1.5 h (308 events, 23 pairs) | 219 EA requests, all 200, 283 MB; no Open-Meteo | scoped; evaluation harness built (53 tests pass), fetch and scoring refuse to run before 2 Nov |
| Missing event ends (live-model side finding) | #384 | replay of the right-now rule with finished UU spills given an end time | 4 pass | replay matched production's level in 99.3% of 7,255 spot-builds; stricter rule: 0 level changes in 9 days; longer window: 2 one-build false Lows at Grasmere | one `gh release download`; 80 s | measured: do not fix now (thresholds stated first) |
| Moderation help | #378 | a trigger based on queue volume, then Worker rules, a local model, an outside model only after a DPIA | none (no code) | 0 published reviews, 0 notes showing (26 Oct) | none | written |

## Decisions, 26 October 2026

Ethan adopted every recommendation on 26 October 2026 (about 20:15 UTC): "Adopt all the recommendations as my
decisions. Record them in the status map and the relevant PRs, apply the ones that need only docs or harness settings,
and keep everything as draft PRs." Earlier the same evening he approved the #377 statement ("approved", about 19:25
UTC). Each decision is recorded in its own PR as well.

| # | Piece | Decision | Applied |
|---|---|---|---|
| 0 | Satellite (#377) | No Copernicus Data Space account. Even full Lake District coverage is 3 water bodies, under the statement's 4; the tile check then found no English site covered at all | recorded in #377 |
| 1 | Advisory (#379) | Ethan alone approves; approvals in a file in the repo, changed by PR | code in #379 |
| 2 | Advisory | Sources: EA, NRW, Irish EPA, council water-quality notices; water companies for their own incidents as "[company] says"; closures are not advisories | code in #379 |
| 3 | Advisory | Council text: link and own summary; verbatim only from openly licensed sources | code in #379 |
| 4 | Advisory | EA incident shows while the EA lists it open, re-checked each run, nothing if the feed fails; no 28-day stale flag for EA items; EPA duration shown as "EPA expects until"; page advisories with no end expire 14 days after approval | code in #379 |
| 5 | Advisory | Wording: "Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026" + link; never changes a level | code in #379 |
| 6 | Advisory | EA history for all 38 waters, once a day | code in #379 |
| 7 | Advisory | Runs by hand on Ethan's Mac, weekly in season; not in Actions or the build | doc in #379 |
| 8 | Sampling (#381) | Not pursued; kept as the record. Rule of thumb: least-sampled sites on wetter days | doc in #381 |
| 9 | Sampling | No randomised arm now; only if a partner plans 2027 sampling | doc in #381 |
| 10 | Anomalies (#382) | long_run on the data-quality page now; quiet_monitor after a second month, worded as a question; whole-feed checks as build warnings only; record_contradiction not public | doc in #382; wiring is a follow-up PR |
| 11 | Missing ends (#384) | Do not fix now; measure again on or after 9 Nov 2026; fix if rule B changes levels at more than 1% of spot-builds; fix map clicks in the same PR | doc in #384 |
| 12 | River rises (#383) | Run the test in early November (after 2 Nov), radar saved before about 21 Nov | doc in #383 |
| 13 | River rises | No upstream-rise line on the page before the test | doc in #383 |
| 14 | River rises | The eight harness questions answered: R1 as built; "Possible harm" counts as harm (note added to the near-miss framework in `docs/LAKE-ECOLI-LINE-TEST-2026-10.md`); B = 0.02 and H = 0.01 Brier skill against persistence, "promising" goes to a winter shadow log; radar at t − 1 h; C2's placebo shifts radar only; datum drop rule (median index outside −0.5 to 1.5); tributary-only gauges included and reported apart; gate pooled with per-gauge figures | harness in #383 |
| 15 | Moderation (#378) | Trigger: over 50 waiting three weeks running, over 30 min a week four weeks running, any cap hit, or over 10 reports a week | this PR |
| 16 | Merging | All of these stay draft PRs for now | all |

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
