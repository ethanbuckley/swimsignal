# AI and data programme, autumn 2026: status map

Started 26 October 2026, after Ethan accepted Codex's assessment of which AI systems are worth building. This is the
one place that says what each piece is, where it stands and what is waiting on a decision.

**Snapshot during the 26 October window (updated as work lands; final update near 00:30 UTC).** Merges were
made by Codex under Ethan's delegation of routine decisions (from about 22:30 UTC); before that, Ethan approved the
#377 statement (about 19:25 UTC) and adopted the recommendations of 26 October (about 20:15 UTC). No live model,
level, A8, option B or shadow window was changed by any of this.

## Where everything stands

| PR | What | State | Head / merge | Notes |
|---|---|---|---|---|
| #379 | Advisory finder; reviewed official advice on spot pages | **merged, live** | 6b3e544 (23:18) | Frensham: Codex-reviewed EA harmful-algae line (reviewed 22:53:52Z, evidence fetched 22:45:58Z). Publishing run 40418829665 succeeded; Codex checked the live data at 23:25 |
| #382 | Monitor anomalies; long_run list on the data-quality page | **merged, live** | 6688156 (22:45) | Publishing run 40414855047 succeeded; live page 4 comparative + 2 no-baseline rows; 5 feed checks, 0 flags |
| #387 | Comprehension sessions pack; H1-H4 clarification; actions list | **merged** | bf0065a (23:04) | No session run; no recruitment sent |
| #389 | Practical guides, 11 bathing waters | **merged** | 59b60af (23:13) | Private audit `swimsignal-private/guides-audit-2026-10-26/AUDIT.md`, 60 rows; fetch times 22:53:18-22:54:51 and 23:05:51 UTC |
| #391 | Official advice on every surface that shows a level (round 1) | **merged, live** | 9f29521 (23:36) | Publishing run 40420912535 succeeded |
| #388 | Planner: outing time + backup; saved changes with evidence and the official notice; local read tick | **merged** | fcb7f00 (23:45:54) | Codex fixed a rendering boundary while reviewing (8f384f1). Publishing run 40421963614 **failed at its test step** on the late-night ensemble-test flake (1,386 passed, 1 failed), so it was not deployed then; it publishes with the next successful build |
| #377 | Research: satellite algae (Sentinel-2 NDCI) | **merged (record)** | 41d3afd (23:25) | A fails; B too few; CLMS had no data at the 18 English sites checked in summer 2025. Nothing adopted |
| #381 | Research: sampling priorities simulation | **merged (record)** | c4006ca (23:26) | Fails its stated rule. Nothing adopted |
| #384 | Research: missing event ends | **merged (record)** | c581b9f (23:26) | Do not fix now; re-measure on or after 9 Nov |
| #392 | Official advice, rounds 2-3 (Nearby, compare row, Saved grid, feeds, action line, alerts.json text, weekend-card plain groups; helper keeps the cause) | open, draft, **CI green, ready** | 5abb470 | Includes main + #388 + #393. Share-plan exclusion kept with its reason; user-picked lists keep advised spots with the notice. Merge before #394 |
| #394 | Alert/push/email/weekly text and weekend-card groups (text only) | open, draft | 4ee086b, being rebased on #392 | Overlaps #392 (which already covers alerts.json and weekend groups); keeps only what #392 lacks; merge after #392, or close if nothing remains |
| #390 | Prototype: catchment replay (`?replay=1` only) | open, draft, **CI green, ready** | 51aad5f (main incl. #388 and #393 merged; 571 site JS + 124 Python checks pass locally) | Codex added 1685b3e (a lake spot never gets a river arrival). Full CI then failed one existing, clock-dependent ensemble test (not replay code); fixed by pinning the test to noon (3a2e935, also PR #393 for main). Preview http://localhost:8793 |
| #395 | Polish: guide "Source: <page>, <month>" for dated historical facts (schema `source_date`); Saved and Plan say what they need without JavaScript | open, draft, **CI green, ready** | fd5b317 | Includes main + #393; merges cleanly with #390, #392, #394. Not seen rendered with JavaScript off (checked by tests and reading). Five older Defra-sourced facts without "not a current check" still say Verified: for review |
| #393 | Test only: pin the ensemble spare-calls test to noon | **merged** | 6b5b575 (23:55) | Fixed the late-night flake that also blocked publishing; no production change |
| #383 | Research: river rises scope + evaluation harness | open, draft | 6c3f29d | Fetch and scoring refuse to run before 2 Nov; not reviewed for running yet |
| #385 | Research: NDCI vs EA harmful-algae incidents (statement) | open, draft, **unrun** | 735e882 | Reviewed as a bounded exploratory question; not approved for fetching |
| #386 | Research: NDCI vs EA lab chlorophyll (statement) | open, draft, **unrun** | 61ff324 | 7887 partly verified (acetone extract, phaeopigment correction not stated); not approved for fetching |
| #378 | This status map; moderation trigger | open, draft | this PR | |

## Open decisions, and whose

- **Codex (delegated):** review and merge #392, #393 and (if wanted) #390; the stray branch `polish/official-consistency`
  (2 commits, superseded by #392) can be deleted.
- **Ethan (credentials or outside contact):** the push Worker's `GITHUB_DISPATCH_TOKEN` (recommended: not before the
  ensemble-rain read on 21 Nov); recruitment wording and posts for the comprehension sessions; the UKCEH Bloomin'
  Algae licence enquiry; an EA lab question that would settle 7887's definition.
- **Follow-ups:** alert message text (in progress, above); the "Highest risk" sort ranks by the sewage level; sites view heading order (P4);
  where the replay would live and whether it is cached offline.

## Dated next actions

| When | What | Who |
|---|---|---|
| Weekly, in season | Advisory finder run by hand (`docs/ADVISORY-FINDER-RUN-SHEET.md`); without a newer committed check, Frensham shows "Not re-checked since 26 Oct" from 4 Nov | Codex or Ethan |
| After 2 Nov | River rises (#383): review the stated plan, then fetch (about 335 EA requests) and score | Codex review first |
| On or after 9 Nov | Missing event ends: re-measure with `scripts/measure_missing_event_end.py` | agent |
| Before about 20 Nov | Decide whether to keep the 34 GB of raw radar files (the per-overflow save itself is done) | Ethan |
| 21 Nov | Ensemble rain (D4) read; then decide the dispatch token | scheduled task, then Ethan |
| 23 Nov / 25 Nov | Live-status shadow read; A8 read | scheduled tasks |

## Decisions log, 26 October 2026

Ethan adopted every recommendation at about 20:15 UTC ("Adopt all the recommendations as my decisions …"). Later
that evening he delegated routine decisions to Codex. Where a later decision replaced an earlier one, both are shown.

| # | Piece | Decision | Now |
|---|---|---|---|
| 0 | Satellite (#377) | No Copernicus Data Space account | holds: the tile check found no CLMS data at the 18 English sites checked |
| 1 | Advisory | Ethan alone approves | **superseded** by decision 8 of the advisory doc: Codex may be the recorded reviewer under delegation, never attributed to Ethan |
| 2-7 | Advisory | Sources, link-only council text, expiry rules, wording, daily EA history, weekly run by hand | in #379 (merged) |
| 8-9 | Sampling | Not pursued; no randomised arm now | recorded in #381 (merged) |
| 10 | Anomalies | long_run on the page; quiet_monitor later; whole-feed checks as build warnings | live via #382 |
| 11 | Missing ends | Do not fix now; re-measure on or after 9 Nov; fix if rule B moves levels at >1% of spot-builds | recorded in #384 (merged) |
| 12-14 | River rises | Run after 2 Nov; no page line before the test; eight harness answers | in #383 (radar for the test period is already saved) |
| 15 | Moderation | Trigger: >50 waiting three weeks running, >30 min a week four weeks running, any cap hit, or >10 reports a week | this PR |
| 16 | Merging | All stay draft | **superseded**: Codex reviews and merges under delegation |

## Research records merged (26 October 2026, 23:25-23:26 UTC, by Codex; no adoption, no reruns)

Kept separate from adoption: merging a record activates nothing. Each was merged with main at a2353a6..6b3e544 and
checked; the three also merge cleanly with each other, and their tests pass together (67).

| PR | Record | Verdict, unchanged | Head | Checks |
|---|---|---|---|---|
| #377 | Satellite algae (Sentinel-2 NDCI) | A fails (Possible harm, AUC 0.60); B too few to judge; CLMS had no data at the 18 English sites checked in summer 2025 | f291f7a → **merged 41d3afd** | 56 harness tests, ruff, docs checks; CI green |
| #381 | Sampling priorities simulation | fails its stated rule against coverage (58.5% vs 60%) | 456307e → **merged c4006ca** | 10 tests, ruff; CI green |
| #384 | Missing event ends | do not fix now; re-measure on or after 9 Nov | be3a17b → **merged c581b9f** | 7 tests, ruff; CI green |

#383 (river rises) stays a protocol/research draft. #385 and #386 stay unrun and not approved for fetching.

## Build and polling cadence: intended vs observed (checked 26 October 2026, about 23:40 UTC, read-only)

- **Intended.** `site.yml` asks GitHub for a build every 30 minutes (`*/30`), best effort. The push Worker has a
  second cron (`*/30` in `push/wrangler.toml`, `push/src/dispatch.js`) meant to ask GitHub for a build when the last
  one is over 20 minutes old, but only once the Worker secret `GITHUB_DISPATCH_TOKEN` is set; without it, it logs
  "GITHUB_DISPATCH_TOKEN not set; GitHub's own schedule only" and does nothing (`push/README.md`, "Starting the site's
  build"). Each build polls the company feeds, so the poll cadence is the build cadence.
- **Observed** (`gh run list --workflow site.yml`, last 48 h to 23:26 UTC): 33 runs, 12 from the schedule and 21 from
  pushes to main (tonight's merges); **0 `workflow_dispatch` runs in the last 200 runs (back to 12 Oct)**. Scheduled
  runs were a median 4.3 h apart, at most 6.3 h. #390's replay found 23 answered polls per company feed in 48 h on the
  25 Oct state, with gaps of 4, 4 and 16 h.
- **Reading (inferred, not checked):** the Worker's dispatch is not running, most likely because the token is not set
  (or the deployed Worker predates `dispatch.js`). Confirming needs the Worker's logs in Cloudflare, which this session
  does not have.
- **Not a routine code fix.** It is configuration: a fine-grained GitHub token with Actions: write on this repository,
  set as the Worker secret, and the Worker deployed. That is Ethan's (credentials).
- **Timing matters.** Builds every 30 minutes would use the Open-Meteo ration up to its planned ceiling (8,750 of
  9,000 a day), and at that ceiling the ensemble rain test (D4, window 23 Oct to 19 Nov, read 21 Nov) makes no
  ensemble requests (`docs/ENSEMBLE-RAIN-TEST-2026-11.md`). So turning dispatch on now would change a running study
  window. Recommendation: leave it off until D4 is read (21 Nov), then decide.
- **Wording.** User-facing text already describes the schedule as best effort ("at most every 30 minutes" on
  `data.html`; "asks GitHub for a run every 30 minutes … when it has capacity" on `verification.html`). The one
  promise of polls "every 30 minutes" was #390's replay footer, now "when the feeds were polled; events between polls
  can be missed".

## Integrated usability review (26 October 2026, on main 6b3e544, before #388 and #391)

Static preview, no pipeline, no Open-Meteo; real approved and check files; 320, 375 and 1440 px, with and without
JavaScript. The official block itself passed: above the level, the separation sentence, link contrast 7.4:1 and text
14.9:1, in the prerendered page, and in the stale state. Home list, Saved cards, plan rows, a shared plan opened fresh
and the record (incl. print) carry the compact notice. No sideways scroll on any page checked.

| Finding | Severity | Where it is fixed |
|---|---|---|
| B1 "Lower risk nearby" suggests the advised water | blocker | #392 |
| B2 embed / live sign say advice "could not be checked" | blocker | #391 (merged) |
| B3 sites view and printed briefing | blocker | #391 (merged) |
| B4 organisers page has no official line | blocker | #391 (merged) |
| B5 compare tables' EA row says "could not be checked" | blocker | #392 |
| S1 map tooltip, S2 share card and alt text | should-fix | #391 (merged); #392 keeps the cause on the card |
| S3 Atom feeds headline a clean Low | should-fix | #392; alerts.json and push/email delivery are follow-ups |
| S4 Saved day grid untagged, "lowest risk this week" counts the advised spot | should-fix | #392 |
| S5 plan share and low-only filter | should-fix | #391 (merged); share exclusion vs notice still Codex's decision |
| S6 Saved since line reads as good news at an advised water | should-fix | #388 (fixed, cec52a9) |
| S7 "Usual care" under the level at an advised water; algae tile "None seen" beside the notice | should-fix | #392 |
| S8 compact line drops "(harmful algae)"; record line has no link | should-fix | #392 |
| P1 guide label "Verified: Defra" on a fact that says it is not a current check | polish | follow-up: needs a label rule for dated sources |
| P2 "last checked" sentence repeated on the spot page | polish | #392 |
| P3 Saved and Plan stuck on "Loading…" without JavaScript | polish | follow-up |
| P4 sites view heading order skips a level | polish | follow-up |

Not checked: a real phone, iOS Safari, Firefox, screen-reader output, real keyboard focus rings.

## What was learned

- Upstream gauges give about an hour of warning at most river spots (median arrival 1.5 h, before a 0.5 h median
  publication delay and the build interval). Several hours would need rain.
- An information-based sampling ranking did not clearly beat the simple coverage rule, even in a made-up world built
  to suit it.
- The overflow feeds held up over 39 days for the failures that would hide every spill at once (freezes, recoded
  status, new ids): 0 real flags. The real questions are about single monitors: reporting one spill far longer than
  any on record, quiet through storms, or missing event ends.
- A Sentinel-2 chlorophyll index did not add to the month and the last EA check for "algae seen" at English lake
  bathing waters (#377), and the Copernicus lake product had no data at the 18 sites checked.
- Builds, and so feed polls, ran about every 4 hours, not every 30 minutes: the push Worker's dispatch is not
  running, and turning it on would change the ensemble-rain study window.
- An official notice must travel with the level everywhere the level goes (list, plan, share, cards, embed, feeds);
  the integrated review found 13 places where it did not, now fixed or in #392.

## Rules every piece follows

- Codex reviews and merges under Ethan's delegation; workers open draft PRs only. No deploys beyond the normal
  publishing build, no outreach, purchases, accounts or credential changes.
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
