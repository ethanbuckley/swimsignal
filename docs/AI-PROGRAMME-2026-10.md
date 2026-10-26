# AI and data programme, autumn 2026: status map

Started 26 October 2026, after Ethan accepted Codex's assessment of which AI systems are worth building. This is the
one place that says what each piece is, where it stands and what is waiting on a decision. Each piece is a separate
draft PR. None is merged or deployed by this programme, and none changes the live site, the live models, or the A8,
option B or shadow windows.

Last updated: 26 October 2026, about 21:50 UTC. Test counts were rerun by the coordinator on each branch. Ethan approved
the #377 statement at about 19:25 UTC and asked for the rest to be built autonomously.

## The map

| Piece | PR | What it is | Tests | Evidence | Costs and limits used | State |
|---|---|---|---|---|---|---|
| Satellite algae | #377 | approved statement, run once (26 Oct): Sentinel-2 NDCI at 14 lake sites vs 1,358 EA algae checks, 2020-26 | 56 pass | **A (algae seen) fails**: adds nothing to month + last check (Brier gain −0.0047, 97.5% interval −0.023 to +0.002, "Possible harm"; AUC 0.60). **B (objectionable) too few to judge** (20 events; AUC 0.81 description only). 404 of 1,358 checks paired (30%). CLMS lake product: no data at any English site | stage 1 28,317 requests / 5.18 GB after A1 (parallel bucket reads); A2 byte cap 5 GiB (8.2 MB overshoot disclosed); A3 EA fetch per point; scoring offline, 0 network attempts | **done: lakes keep the EA check only** |
| Advisory finder | #379 | dry-run drafts from the EA incident feed and the Irish EPA, plus 4 whitelisted pages; deterministic, no LLM | 33 pass | EA open incidents answered this Mac: 7 open, 1 at a SwimSignal spot (Frensham Great Pond, algae, since 19 Jun); EPA 0 in force (season over) | 11 requests; no account | prototype done |
| Sampling priorities | #381 | ranking of new sample days by information, high-risk list kept apart; simulation stated before it ran | 7 pass | **fails its stated rule**: beats least-sampled-first in 58.5% of 200 runs (60% needed); beats random in 73% | no network; 112 s | prototype done, rule failed |
| Monitoring anomalies | #382 | 9 review-only flags beyond today's feed checks, on 39 days of saved polls plus injected failures | 25 pass | long_run 7 (4 look stuck, 1 probable false alarm); quiet_monitor 12 (10 worth a look); future_time 4 (UU starts 22-47 min ahead of the poll); company_freeze, known_share_drop and future_time caught injected failures no current check fired on | no network | prototype done |
| River rises | #383 | gauge coverage and rise-arrival delays; dated plan against persistence | 21 pass | 66 of 72 river spots have a same-river gauge, 48 an upstream one; 45 of 55 gauges have 15-minute history from before 2015; arrival lag median 1.5 h (308 events, 23 pairs) | 219 EA requests, all 200, 283 MB; no Open-Meteo | scoped; evaluation harness built (53 tests pass), fetch and scoring refuse to run before 2 Nov |
| Missing event ends (live-model side finding) | #384 | replay of the right-now rule with finished UU spills given an end time | 4 pass | replay matched production's level in 99.3% of 7,255 spot-builds; stricter rule: 0 level changes in 9 days; longer window: 2 one-build false Lows at Grasmere | one `gh release download`; 80 s | measured: do not fix now (thresholds stated first) |
| Moderation help | #378 | a trigger based on queue volume, then Worker rules, a local model, an outside model only after a DPIA | none (no code) | 0 published reviews, 0 notes showing (26 Oct) | none | written |

## Decisions, 26 October 2026

Ethan adopted every recommendation on 26 October 2026 (about 20:15 UTC): "Adopt all the recommendations as my
decisions. Record them in the status map and the relevant PRs, apply the ones that need only docs or harness settings,
and keep everything as draft PRs." Later that evening Ethan delegated routine decisions to Codex; approval records now name the actual reviewer and
authority rather than Ethan by default (#379). Earlier the same evening he approved the #377 statement ("approved", about 19:25
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

## Product brief, 26 October 2026, 22:30 to 00:30 UTC

Ethan approved the next development direction, with Codex coordinating. Order: priorities first, then improvements.
Research records stay separate from live adoption: #377 and #381 keep their failed outcomes, no live satellite or
sampler, #383 keeps its dates, and the lab-chlorophyll and incident tests are not fetched or scored until their
protocols are reviewed.

| # | Item | PR | State |
|---|---|---|---|
| 1 | #379: CI guard fixed (finder moved to `scripts/advisories.py`; build reads files only via `official_advice.py`); official-advice block above the level, stale/unread sources keep warnings visible as "Not re-checked since". Decisions (Codex, delegated): Codex may be the recorded reviewer, never attributed to Ethan; a 6-request live finder run creates `last_check.json`; Codex approves the Frensham record from the exact line and evidence. Merges main after #382 | #379 | **final head 5a3991d, CI green (1,308 passed; site interactions passed); ready for Codex review/merge.** Approved Frensham entry committed (a2353a6: reviewer Codex, delegated, reviewed 22:53:52Z). Pre-merge fixes done: reworded EA-today line; invalid approvals stop publication; disappeared incidents kept as not re-checked; exact-line guard on the site; one compact indicator on list, Saved, plan rows and record. Follow-ups: embed, share card, map tooltips, alerts; the "Not known here" tile still lists Today's EA advice as not checked |
| 2 | #382: question wording, no-baseline monitors in their own group, unknown when stale or unchecked, no file paths on the page; full CI green on 5a2a90d. A local real build needs about 394 Open-Meteo calls (`--no-refresh` still fetches rain and soil); Codex chose not to spend them: **Codex merged #382 at 22:45 UTC (6688156)**; publishing run 40414855047 **succeeded**; Codex verified the live quality page: 4 comparative + 2 no-baseline rows; 105/105 forecasts OK; 5 feed checks run, 0 skipped, 0 flags | #382 | **merged and live** |
| 3 | Practical guides for popular spots from verifiable sources (#389: 17 facts at 11 bathing waters, Defra consultations and Anglian Water pages; 16 + 13 tests). Codex review: word-overlap checks don't justify new checked dates; consultation facts dated as historical; Whitwell toilet fact out unless the site is named; postcode/owner lines don't fill access gaps. Revised b7e1cc2: every kept fact (61) read next to its source passage 22:55-23:20 UTC, so the 26 Oct date is earned; address/owner lines removed from path; Wetherby ramp and Whitwell toilets removed; Defra items worded as "…listing, not a current check"; Sykes Lane swim rule corrected to the FAQ's words; 16 + 13 tests; merges clean; **final head 639d7c3, ready for Codex merge**: private audit at swimsignal-private/guides-audit-2026-10-26/AUDIT.md (60 rows: 49 supports, 9 with caveat, 2 reworded; 34 saved sources; audit.py regenerates it identically from the PR head); dated Anglian Water low-water notice in the Sykes Lane entry guide in place of the dogs and toilet-count facts; Whitwell evening swims reworded; fetch times 22:53:18-22:54:51 and 23:05:51 UTC); sessions execution pack (#387, 5dd54e7: real timestamps, owners by delegation, S2 already live via #284, protocol kept as written, two proposed amendments listed unapplied; Codex approved a clarification before the first participant: everyone sees the current live scoped wording, no A/B or restored "Low risk", thresholds unchanged, a failed task 2 leads to a focused retest of a clearer wording, no automatic rollout; recorded as H1-H4, additions only, in the plan s12 and run sheet s8; #387 **merged bf0065a at 23:04 UTC** by Codex, CI green); outstanding human actions | #389, #387 (pack) | review fixes in progress: real timestamps, delegation and #382 status, S2 checked against the live heading, protocol kept as stated |
| 4 | Catchment replay prototype: last 48 h of reported spills (observed), modelled arrival (estimate, from travel_h), Open-Meteo model rain over the overflow cells, latest gauge reading only; gaps drawn as gaps; opt-in `?replay=1`; no new API calls; 1.8-6.6 kB per spot. Found: Yorkshire Water's latest event is only the tail of a spill (handled). Codex decisions: 48 h; current gauge with time only; rain labelled as overflow-cell mean; details folded; no arrival bars through lakes; open-ended arrivals kept; stamped script; 320 px; stable preview for QA | #390 | prototype, changes in progress; extra review: polls described as polls with gaps and coverage shown, history unavailable marked, ends across gaps given as ranges, payload bound enforced or relabelled |
| 5 | Planner (#388): outing time and backup spot; what changed since I checked, with evidence (extending the existing `since.js`, not duplicating it); club brief versions and leader acknowledgement (local only) | #388 | **0a8bedb**: browser-checked (link round trip, backup on refresh, day change, past time, keyboard, 375/1440 px) and fresh page loads with localStorage blocked (plan, Saved, record: no errors); Saved shows counts, issue times, gaps and a link to the spot's overflows, no names; 173 node tests. Official indicator: placeholder now, to be wired for real after #379 merges |
| - | Lab-chlorophyll test statement (no fetch): EA determinand 7887 at 40 lakes chosen by metadata only; pass needs Spearman ≥ 0.5 (lower end > 0.3), within-lake placebo, LOLO calibration Better (B 0.10, H 0.05), no lake type harmed; stage 1 sized at ~55,200 requests / 3.2 GB | #386 | **kept unrun**. 7887 **partly verified** (61ff324): the EA lab's only accredited chlorophyll test (UKAS 0754) is acetone extraction + spectrophotometry per the SCA 1980 chlorophyll a method, uncorrected by default; no EA page ties code 7887 to it, and phaeopigment correction is not stated. Results must say "EA acetone-extract chlorophyll (7887), correction not stated"; if unresolved, the inference stays explicit and nothing claims lab chlorophyll-a validation. No 55k-request fetch |
| - | Algae incident test statement (no fetch) | #385 | protocol reviewed by Codex as a bounded exploratory question; **kept unrun in this window** |

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
- Caps are sized before they are written: requests × (pause + latency) = run time, stated with the caps. Rate-limited
  APIs (EA, Open-Meteo, the CLMS map tiles, STAC search) go one request at a time with a pause; object stores such as
  the AWS Sentinel-2 buckets are read in parallel (16 at a time) with no pause. Learned on 26 October 2026: #377's
  stage 1 was first paced at 1 request a second for every host, about 9.5 hours for under 1 GB; Amendment A1 fixed it.
- Algae blooms are kept apart from toxins and from E. coli. A river-rise figure is not a swimming-safety forecast.
- An advisory is always a draft a person approves, and never changes a level.

## Not in this programme

- A swimmer chatbot, pollution from photos, and camera drowning detection: ruled out on 26 October 2026.
- Between-image bloom forecasting: a separate test, stated later, only if detection works.
