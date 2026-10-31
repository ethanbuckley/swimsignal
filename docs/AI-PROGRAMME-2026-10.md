# AI and data programme, autumn 2026: status map

Started 26 October 2026, after Ethan accepted Codex's assessment of which AI systems are worth building. This is the
one place that says what each piece is, where it stands and what is waiting on a decision.

**30 October continuation decision:** the current cross-project status and delivery owners are now in
[RESEARCH-RECOVERY-2026-10.md](RESEARCH-RECOVERY-2026-10.md), under
[RESEARCH-WORKFLOW.md](RESEARCH-WORKFLOW.md). Ethan requested recovery of promising research and a route to public
use. Satellite data/export development, a discoverable observation viewer and fresh-data collection preparation
can proceed now; this supersedes the blanket satellite parking instruction below for those activities. The old
verdicts, existing evaluation windows and restrictions on accounts, external contact and API allocations stand.
The dated snapshots below remain historical records, not current stopping instructions.

**Final snapshot at the close of the 26 October window, 27 October 00:21 UTC** (PR, run and live states read at 00:20-00:21). Merges were
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
| #388 | Planner: outing time + backup; saved changes with evidence and the official notice; local read tick | **merged, live** | fcb7f00 (23:45:54) | Codex fixed a rendering boundary while reviewing (8f384f1). Its own publishing run 40421963614 failed at the test step on the late-night ensemble flake (fixed by #393); live since the 7602610 build |
| #377 | Research: satellite algae (Sentinel-2 NDCI) | **merged (record)** | 41d3afd (23:25) | A fails; B too few; CLMS had no data at the 18 English sites checked in summer 2025. Nothing adopted |
| #381 | Research: sampling priorities simulation | **merged (record)** | c4006ca (23:26) | Fails its stated rule. Nothing adopted |
| #384 | Research: missing event ends | **merged (record)** | c581b9f (23:26) | Do not fix now; re-measure on or after 9 Nov |
| #392 | Official advice, rounds 2-3 (Nearby, compare row, Saved grid, feeds, action line, alerts.json text, weekend-card plain groups; helper keeps the cause) | **merged, live** | 671a319 (00:00:11) | Publishing run 40423520622 succeeded (00:11:52) |
| #394 | Push Worker message text: weekly note, alert email, dated notices and combined push carry the official notice with state-aware leading markers; recipients, triggers, levels, ranks and KV unchanged | **merged** | d661269 (00:08:26), guarded to approved head 62a7c584 (CI green; 123 Worker tests) | **Worker deployed** 00:10:39 UTC by Claude under Codex's delegated authorisation, from a clean `git archive` of main d661269 (`officialMark` checked present), with the existing login (`wrangler whoami` OK, no new access): `swimsignal-push` version **4d73da26-5664-4141-bfd6-1b71c0f8a73f**; schedules unchanged (`*/2`, `*/30`); no secrets, recipients or schedules altered; preflight `OPTIONS /subscribe` 204 at 00:10 |
| #390 | Prototype: catchment replay (`?replay=1` only) | **merged, live (opt-in)** | ea91fae (00:00:21) | Its own publishing run 40423541773 was cancelled by the workflow's concurrency (a newer run replaced it); live since the 7602610 build |
| #395 | Polish: guide "Source: <page>, <month>" for dated historical facts (schema `source_date`); Saved and Plan say what they need without JavaScript | **merged, live** | 7602610 (~00:04) | Five older Defra-sourced facts without "not a current check" still say Verified: recorded as a follow-up |
| #393 | Test only: pin the ensemble spare-calls test to noon | **merged** | 6b5b575 (23:55) | Fixed the late-night flake that also blocked publishing; no production change |
| #383 | Research: river rises scope + evaluation harness | open, draft | 6c3f29d | Fetch and scoring refuse to run before 2 Nov; not reviewed for running yet |
| #385 | Research: NDCI vs EA harmful-algae incidents (statement) | open, draft, **unrun** | 735e882 | Reviewed as a bounded exploratory question; not approved for fetching |
| #386 | Research: NDCI vs EA lab chlorophyll (statement) | open, draft, **unrun** | 61ff324 | 7887 partly verified (acetone extract, phaeopigment correction not stated); not approved for fetching |
| #378 | This status map; moderation trigger | open, draft | this PR | |

## Release (publishing builds of `site.yml` on main)

| Run | Commit | Result | Note |
|---|---|---|---|
| 40420912535 | 9f29521 (#391) | success | live from about 23:45 |
| 40421963614 | fcb7f00 (#388) | failure | test step: late-night ensemble flake (fixed by #393); not deployed |
| 40423520622 | 671a319 (#392) | success (00:11:52) | |
| 40423541773 | ea91fae (#390) | cancelled | replaced by a newer run (concurrency) |
| 40423958498 | 7602610 (#395) | **success (00:19:09)**: final live commit | the newest commit; includes #388, #390, #392, #393, #395 |

Live check, 00:20 UTC: `data/spots.json` build commit **7602610**, generated 00:15:57, 105 spots; Frensham carries the reviewed EA line (state checked, 26 Oct); `outing.js`, `replay.js`, `brief.js`, `eatoday.js` all HTTP 200; live `alerts.json` has Frensham at level low, rank 0 (unchanged) with the official text in `action` and `official`, which the deployed push Worker (version 4d73da26) reads.

## After the snapshot (27 October, 00:23-01:30 UTC)

Ethan approved #386 and #385 as written, asked for the three follow-ups as draft PRs (then "merge them"), and asked
for new feature and research ideas to be built as drafts ("do all except 4"). No live model, level, A8, option B or
shadow window was changed.

| PR | What | State | Head / merge | Notes |
|---|---|---|---|---|
| #386 | Research: NDCI vs EA lab chlorophyll | open, draft, **run: fails as stated** | a03bcb7 | Approval 49bf309; one scoring run, network attempts 0. Pooled ρ 0.502, interval lower end 0.2997 vs 0.3 needed; placebo beaten 200 of 200; calibration "Too uncertain" overall, "Better" in shallow lakes. A near miss in the right direction |
| #385 | Research: NDCI vs EA harmful-algae incidents | open, draft, **run: too few to judge** | d560798 | Approval bac9c34; network attempts 0. Incidents at 3 water bodies; the gate needs 4 |
| #396 | 2027 forward test for satellite algae | open, draft, **withdrawn** | 5538699 | #386 failed by its own rule, so the forward test is withdrawn unless Ethan decides otherwise |
| #397 | Source dates on five Defra facts (Nidd, Wharfe) | **merged, live** | 00:54:50 | Closes the #395 follow-up |
| #398 | Sites view: spot names as h2, no skipped heading levels (P4) | **merged, live** | 00:54:55 | |
| #399 | "Highest risk" puts spots with official advice against swimming first | **merged, live** | 0929fd0 (00:55:00) | Publishing run 40429395084 succeeded (01:12:51) |
| #400 | Water temperature: coverage check and note | open, draft | e5cdac18 | The tile has been live since 3 Oct (1ec864d); 3 of 105 spots have a live same-river sensor. Re-check coverage in May-June 2027 |
| #401 | Past spills upstream by month (history panel) | open, draft | ec06493 | Ethan: "any overflow" count or the forecast's weighted rule; 80% coverage floor; check the fingerprint on the first build |
| #402 | Outing alerts for the planned day, and a calendar file | open, draft | 23d94ef | No `push/` change. Date alerts need the build variable `DIPCAST_PUSH_DATES`, which is not set; setting it also turns on organiser date alerts |
| #403 | Research: sonde readings in the river E. coli estimate (statement) | open, draft, **cannot run** | 7292f73 | 71 covered rows at 4 sites vs a gate of 150; the gate was set after the coverage counts were seen (disclosed). Grow the rows (Wessex CC BY samples, 2027) or drop it |
| #404 | Research: flow-based dilution (statement + harness) | open, draft, **not approved, nothing run** | c0c71e2 | 2 EA metadata requests; 17 of 20 river bathing waters have a spot gauge (8 real-time). Five questions for Ethan at the end of the statement; the run fetch is capped at 200 requests |

#403 flagged the terms page's Hydrology API credit ("All rights reserved") as a mismatch with the API's OGL v3.
Checked 27 Oct: no mismatch. The credit sits under the page's "all under the Open Government Licence v3.0" heading, and
"© Environment Agency copyright and/or database right <year>. All rights reserved." is the EA's own attribution
statement for OGL data (the `attributionStatement` on its dataset records). Nothing to change.

### Ethan's decisions of 27 October, about 09:50 UTC ("okay approved")

| PR | Outcome |
|---|---|
| #405, #400 | **merged** (docs and a coverage script) |
| #401 | **merged, live**: publishing run 40483978433 succeeded (10:03); build health `seasonal`: shown 77, none 22, too few 3, missing 0, **changed 0** (every fingerprint matched); "any overflow" metric and 80% floor kept |
| #402 | **merged** (f44b8c0); `DIPCAST_PUSH_DATES` stays unset until one real-phone test passes (iPhone Home Screen app: alerts on in Saved, ask for an outing, receive one notice); the calendar file works without it |
| #403 | **merged as a record, parked unrun**: revisit after the 2027 season; the 150-row gate stays as written |
| #404 | **approved and run: fails as stated** (c75a1eb, open as a record). Lag check (9 requests): archive-only gauges 11-14 days behind, so 315 h lag; fetch 84 requests; face checks passed; primary +0.00011, Too uncertain; placebo not beaten; real-time-gauge rows Possible harm (−0.0024). Production dilution unchanged |

After #386's near miss: no new satellite test now; a shallow-lake statement, if wanted, in spring 2027 on 2027 data
only. **#386 is classified "promising, not validated"** (27 Oct): the fail stands; the signal is real; no chlorophyll
estimate is shown or used in advice. #386 (a13d88c) and #385 (c8eac36) merged as records; #396 closed unmerged; #404
(a10a643) and #406 merged.

## Open decisions, and whose

- **Codex (delegated):** the stray branch `polish/official-consistency`
  (2 commits, superseded by #392) can be deleted.
- **Ethan (credentials or outside contact):** the push Worker's `GITHUB_DISPATCH_TOKEN` (recommended: not before the
  ensemble-rain read on 21 Nov); recruitment wording and posts for the comprehension sessions; the UKCEH Bloomin'
  Algae licence enquiry; an EA lab question that would settle 7887's definition.
- **Ethan:** the real-phone test, then `DIPCAST_PUSH_DATES`; whether to merge #404 as a record.
- **Follow-ups:** where the replay would live and whether it is cached offline; ("Highest risk" and P4 were fixed in
  #399 and #398.)

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
