# Comprehension sessions: execution pack, and what is still waiting on a person

Written on 26 October 2026: first version committed at 22:37 UTC (7a805c3), revised after review the same
evening against main at 6688156 (PR #382 merged). It is an index for running the sessions in the plan, plus a list
of every action across SwimSignal that is still open. It adds no rule and changes no protocol. The rules are in
three files, and this pack points into them by section:

- **The plan:** `docs/COMPREHENSION-TEST-2026-10.md` (questions, fail lines, tasks, rubric, what results decide).
- **The run sheet:** `docs/COMPREHENSION-TEST-2026-10-RUN-SHEET.md` (checklist, consent wording, privacy rules,
  defaults A1 to A7, Ethan's decisions D1 to D8).
- **The records file:** `docs/COMPREHENSION-TEST-2026-10-RECORDS.md` (blank record, tally, public summary).

Where this pack and those files differ, those files win. Anything that looks as if it needs a change to them is
listed in section 10 as a proposed amendment for decision, and is not applied here. The one change made so far
is a dated clarification about the headline (H1 to H4), approved on 26 October 2026 before any session and
recorded in the plan (section 12) and the run sheet (section 8), with the original text kept.

Every statement below is marked. **[read]** means I opened the file, page or log named on 26 October 2026.
**[inferred]** means it comes from notes or reasoning, not from a source I opened, and needs checking.

## 1. Where things stand

- No session has been run. [read: `swimsignal-private/research/2026-10-comprehension/` holds the README, the
  session card, a record sheet and a check-in log with a header line only, and the 24 October dry run. There is no
  P0X record.]
- No one has been recruited, and no recruitment message has been drafted or sent by this work. [inferred: no
  record of one in the repository or the private research folder]
- The privacy notice's "Research sessions" section is live on https://swimsignal.co.uk/privacy. [read: fetched
  26 Oct 2026; source `src/dipcast/pages/privacy.html`, merged in PR #380]
- The scoped headline is already live. On https://swimsignal.co.uk/spot/bw-ukj2310-11945/ (Frensham Great Pond),
  checked at 22:49 UTC on 26 Oct 2026, the answer reads "Low risk from sewage spills", issued Mon 22:21. That
  wording is `HEAD_SCOPE` in `levels.js`, from PR #284, merged 20 Oct 2026 at 18:10 UTC (`docs/DESIGN.md`, the
  answer's headline). [read]
- SwimSignal is registered with the ICO and the fee is paid. [read: plan section 11, D8; confirmed by Ethan]
- The spot picker is on main: `scripts/pick_test_spots.py`, ranking fix from PR #375. [read]
- UK time is UTC until 28 March 2027 (the clocks went back on 25 October). [read: run sheet section 2, step 5]

## 2. One-off pre-flight, before the first participant is contacted

Items 1 and 4 to 7 are Ethan's: they spend money, speak for SwimSignal to the public, or happen on his own
computer, where the private folder is. Items 2 and 3 need no decision. Tick them in the private README.

1. **Settle the thank-you** (plan, section 10 item 1). Recommended there: a £10 voucher for swimmers, none for
   leaders, checked against the organiser plan's section 5 first, since money paid may count as trading. Then fill
   the "[Thank-you line, if decided]" in the consent wording (run sheet, section 5), or delete it.
   You will know it worked when the consent text in your private copy has no square brackets left.
2. **Headline wording: settled** (plan, section 12; run sheet, section 8). Every participant uses the live
   scoped wording ("Low risk from sewage spills", PR #284, live since 20 October). The old bare "Low risk" is not
   restored and there is no headline comparison (H1). Scoring and fail lines are unchanged (H2). In each record,
   write the exact headline as shown, the page's URL and its "Issued" line (H3), the day before (run sheet,
   section 1 step 8) and again for the chosen pages that morning (section 2 steps 4 and 5).
3. **A note-taker is optional** (plan, section 10 item 3: "A friend who has not seen the site can take notes").
   With none, there is no second scorer for task 2 (records file, section 2.3). Not a blocker.
4. **Approve the recruitment wording and where it goes, specifically.** Recruitment is a Facebook group post, or a
   request through a group's organiser (plan, section 2). No cold email to sole traders or clubs (PECR). No
   message is drafted here. Each post or request needs Ethan's yes to its exact words and its exact destination.
5. **Make a private copy of the consent wording** (run sheet, section 5) as text you can paste into a call chat, and
   print one copy for in-person sessions.
6. **Check the private folder is still private.** In Terminal:

       defaults read com.apple.finder FXICloudDriveDocuments; defaults read com.apple.finder FXICloudDriveDesktop; tmutil destinationinfo

   It worked if both `defaults` lines print `0`, and `tmutil` prints "No destinations configured." If any of
   these changed since 26 October, the privacy notice's wording on storage needs checking first (run sheet,
   section 6). The likely mistake: turning on iCloud Desktop & Documents later for an unrelated reason. That
   silently syncs `~/Documents`, and the private folder with it.
7. **Have the launch kit's buyer-interview questions to hand** for group leaders (plan, section 2). [inferred: the
   launch kit is a private page, not in this repository.]

## 3. Booking and timings

| What | Rule | Source |
|---|---|---|
| Days to book | Wednesday to Friday only, so "this Saturday or Sunday" is in the planner | run sheet s1 step 3 |
| Swimmer session | 30 minutes, tasks 1 to 4 | plan s3 |
| Group leader session | 45 minutes, tasks 1 to 5, buyer questions last | plan s3, s4 |
| Suggested split, swimmer (the run sheet's suggestion, "not from the plan") | opening 3, task 1 up to 6, task 2 up to 5, task 3 up to 4, task 4 up to 4, closing 6 | run sheet s3 |
| Prompt and help | "What would you try next?" at 1 minute (not help); help only at 2 minutes or later | plan s3, A1 |
| Fail times | task 1 past 5 minutes; task 5 past 10 minutes | plan s1 |
| Reload the chosen pages | within 30 minutes of the start | run sheet s2 step 7 |
| Finish the record | within the hour after | run sheet s4 step 1 |
| Recording, if any | checked and deleted within 7 days | D7 |
| Follow-ups | day 7 and day 14, only if they said yes, from hello@swimsignal.co.uk | plan s7, A5 |
| Contact details | deleted at the last follow-up answer or day 21, whichever is first | D6 |
| Notes and consent answers | deleted once the summary is written, by 31 January 2027 at the latest | plan s6, D8 |

The month plan (plan, section 9): week 1 from 26 October, four swimmers; week 2, two more swimmers and two
leaders; weeks 3 and 4, follow-ups. With Wednesday to Friday bookings, the first possible slots are 28, 29 and 30
October. [inferred: no slot is booked]

Recruits: six swimmers (at least two on an iPhone, at least two who do not follow sewage news) and three or four
group leaders. Exclude anyone who helped build or review SwimSignal (plan, section 2).

## 4. Device and test-spot setup

The day before (run sheet, section 1, steps 6 to 9):

- Video call: check you can see a shared phone screen. Fallback: in person, or the participant reads aloud.
- Open https://swimsignal.co.uk/, one spot page, Plan a swim and Saved. Read a spot page's "Issued" line. More than
  a day old means the build may be stuck: note it, and consider moving the session.
- Copy section 1 of the records file into the private folder as `P0X-2026-MM-DD.md`.

The morning of the session (run sheet, section 2):

1. Pull main in a swimsignal checkout, then run:

       uv run python scripts/pick_test_spots.py --area "Cumbria and the Lake District"

   It worked if it prints two headed lists, "Task 2: low risk with overflows upstream" and "Task 3: a page with
   gaps". When more spots qualify than it lists, it ends with "N more qualify; they are not shown."
   Save the output in the private folder as `picker-2026-MM-DD.md`, never in the checkout.
2. Task 2: the first row of the task 2 table. Check its page headline starts "Low risk".
3. Task 3: the first row of the task 3 table, a Lake District spot (A3). River Thames, Long Bridges, Oxford only
   if no local spot qualifies.
4. On each chosen page, write the headline, the "Issued" line and every limitation the page displays, the lake's
   missing E. coli estimate included. That list is fixed before the session and is what task 3 counts (D2).
5. Leaders: pick the task 5 spot.

The likely mistake here is an old checkout. Before PR #375 the picker ranked lakes first and hid the rivers with
two qualifying gaps (run sheet, section 2, step 3). `git pull` first.

## 5. Consent and data handling, in order

1. Read the opening sentence word for word (run sheet, section 3).
2. Read or show the consent wording (run sheet, section 5). On a video call the participant can answer each line
   aloud; write their answers and the time in the record. A signature is not needed, and a signed form would hold
   their name (run sheet, section 5).
3. Stop if they say no to notes.
4. Code P01 to P10. The name and contact go only in the separate contact list, never in the record.
5. No health, home address or precise location. Write the distance chosen in task 1, not the town.
6. Record nothing unless they agreed separately. Record on your own device, not a call service's cloud.
7. After: calendar the day 7 and day 14 follow-ups under the code, and a day 21 reminder to delete contacts.
8. Withdrawal: delete their record, any recording and their contact details, and correct anything published that
   could identify them (run sheet, section 6).

The public repository holds nothing that could identify a participant. That includes branches, pull request text
and issues (run sheet, section 6). The likely mistake: saving a record next to the docs it was copied from, so it
lands in the next commit. Check the path is under `swimsignal-private/` before saving.

## 6. What to record

Use the record in section 1 of the records file as it is. For each task it asks for time, prompt, help, done
without help, and the participant's words in quotation marks, with your reading kept apart. Task 2 needs both
answers verbatim and a separate "said tested" mark. Task 4 has two halves on a phone (A4). Task 5 checks four
things (D3). Then the summary rows in the plan's section 6 columns.

## 7. How to analyse

After the last session, follow the records file, section 2:

1. Fill the tally table (2.1). Count people, not answers. One count per line.
2. Score task 2 from the quoted words alone, before reading the other tasks. A second scorer, if any, scores blind.
3. Apply D1 to D8 and A1 to A7 as written. Never pick the reading that passes.
4. Repeat use (D4): the denominator is everyone who completed a session, fixed before the first follow-up. No reply
   is unknown use. Report consent to follow-ups and replies at day 7 and day 14.
5. Sort problems into the four kinds in 2.2. Apply the plan's section 8 response to any fail line. Any one clear
   "safe" or "tested" reading leads to a wording fix and a focused retest before wider promotion (D5).
6. Write findings in two parts: what was observed, then what it suggests (2.3).

## 8. What "done" looks like

Gathered from the source files; nothing is added. The round is done when all of these are true:

- 8 to 10 sessions completed, with the mix in plan section 2 (six swimmers, three or four group leaders).
- A record per participant in the private folder, each with its consent answers (run sheet, sections 4 and 6).
- Day 7 and day 14 follow-ups sent to everyone who said yes, and the answers in the records (plan, section 7).
- The tally table filled, with the wording version each participant saw (records file, sections 2.1 and 3).
- One public doc or issue holding the summary (records file, section 3), which passed the re-identification check.
- The decisions under the plan's section 8 taken and listed in that summary (records file, section 3).
- Contact details deleted (D6), recordings deleted (D7), and raw notes deleted once the summary is written, by
  31 January 2027 at the latest (plan, section 6).

The summary says that eight people give direction, not proof (records file, section 2.2).

## 9. Outstanding actions across SwimSignal

**Who decides.** Ethan delegated routine decisions to Codex on the evening of 26 October 2026. Approval records now
name the actual reviewer, not Ethan by default. [read: `docs/AI-PROGRAMME-2026-10.md` on `docs/ai-programme-status`
at 0ea1d4d, "Decisions, 26 October 2026" and "Product brief"] The file does not list the delegation's limits.
[inferred] So this list keeps Ethan only where an action:
- spends money,
- sends a message or post in SwimSignal's name to someone outside,
- or needs his own computer, where the research records are.

Owners:
- **Codex** means Codex decides under that delegation.
- **Agent** means any Claude or Codex session can do the work.
- **Ethan** means only Ethan can do it.

Nothing here is drafted or sent. Dates are the ones in the source.

### 9.1 Comprehension sessions

| # | Action | Owner | Unblocks | Date | Source | Basis |
|---|---|---|---|---|---|---|
| S1 | Decide the participant thank-you, then fill or delete the consent line | Ethan (money; it may count as trading) | Recruitment; the consent text | Before recruiting | plan s10 item 1; run sheet s5 | read; no recorded decision found, so inferred open |
| S2 | Headline wording: **settled** by the 26 Oct clarification (H1 to H4). Every participant sees the live scoped wording; each record holds the exact headline, URL and "Issued" line | Moderator, per session | Task 2 record | Day before and morning of each session | plan s12; run sheet s8 | read: Frensham page checked 22:49 UTC, 26 Oct |
| S3 | Note-taker: optional. With none, there is no blind second scorer | None needed | Second scoring of task 2 only | None | plan s10 item 3; records s2.3 | read |
| S4 | **Approve the exact recruitment post(s), and each group or organiser they go to.** Nothing is drafted here | Ethan, approving each one specifically | Every session | Week 1, from 26 Oct | plan s2, s9 | read |
| S5 | Book sessions, Wednesday to Friday only | Ethan | Sessions | First possible slots 28 to 30 Oct | run sheet s1 step 3 | read; the slot dates are inferred |
| S6 | Run 8 to 10 sessions as moderator | Ethan | All results | Weeks 1 and 2 | plan s9, s10 item 3 | read |
| S7 | Send the day 7 and day 14 follow-ups to those who agreed, from hello@ | Ethan | Repeat-use count (D4) | 7 and 14 days after each session | plan s7; D4 | read |
| S8 | Delete recordings (day 7), contacts (day 21 or earlier) and notes (after the summary, by 31 Jan 2027) | Ethan | Keeping to the privacy notice | As stated | D6, D7, plan s6 | read |
| S9 | Analyse the records and write the public summary, after the re-identification check | Ethan, or an agent working on his computer | Plan s8 decisions | After the round | records s2, s3 | read |
| S10 | Three prospective customers try the session workflow for a real activity | Ethan | Pilot evidence | Week 2 | plan s9; `docs/PILOT-SESSIONS.md` | read |
| S11 | Before session 1, check the private folder is still not synced and not backed up | Ethan | Accuracy of the privacy notice | Before session 1 | run sheet s6 | read |

### 9.2 AI and data programme

State on 26 Oct 2026, read from `gh pr list` and the status map:
- **#382 is merged.** Codex merged it at 22:45 UTC as 6688156, and it is on main.
- **Still drafts:** #377 to #381 and #383 to #386. The two prototypes #388 and #390 are drafts too.
- Under decision 16 these stay drafts "for now". The product brief has Codex coordinating merges.

| # | Action | Owner | Unblocks | Date | Source | Basis |
|---|---|---|---|---|---|---|
| P1 | Algae-incident test statement. Codex reviewed the protocol as a bounded exploratory question. It is kept unrun in this window | Codex | Its one fetch and score | None | #385; AI-PROGRAMME product brief | read |
| P2 | Frensham Great Pond advisory. Codex approves the record from the exact line and its evidence, as the recorded reviewer. It is never attributed to Ethan. Re-run the finder first, so the approval matches the current draft. Merge #379 after #382, which is done | Codex | The EA "advice against bathing (harmful algae)" line on the spot page | EA incident open since 19 Jun, still open 26 Oct | #379; AI-PROGRAMME product brief item 1 | read. The note in `data/advisories/approved.json` on `proto/advisory-finder` still said "Only Ethan Buckley approves" at 22:50 UTC; #379 is in progress |
| P3 | #382 data-quality flags: **done.** Publishing run 40414855047 succeeded. The live quality page shows 4 comparative and 2 no-baseline rows; 105/105 forecasts OK; 5 feed checks run, 0 skipped, 0 flags | Codex | — | Done 26 Oct | AI-PROGRAMME product brief item 2 | run result read (`gh run view`: completed, success, 22:55 UTC); page figures from Codex's check, not re-checked here |
| P4 | River rises: any change to the evaluation plan goes in as a dated amendment, before the run | Codex | The run | Not before **2 Nov 2026**; if possible before **21 Nov** | #383, `docs/RIVER-RISES-SCOPE-2026-10.md`; decision 12 | read |
| P5 | River rises: run it once, alone on the machine, offline from the cache | Agent | The verdict | 2 Nov to 21 Nov | same | read |
| P6 | Missing event ends: measure again. Fix only if rule B changes levels at more than 1% of spot-builds | Agent; Codex merges | A fix, or a confirmed no-fix | On or after **9 Nov 2026** | #384; decision 11 | read |
| P7 | Radar: decide whether to keep the raw files (about 34 GB now, 1.4 GB a month) | Codex; Ethan only if disk space on his computer is the issue | Radar history for spots added later | Before about **20 Nov 2026** | `docs/MET-OFFICE-DATA-2026-10.md` s6, s9 | read |
| P8 | Lab-chlorophyll statement (#386). Kept unrun. First verify EA determinand 7887 from a primary EA source. No 55k-request fetch | Codex | That test | None | AI-PROGRAMME product brief | read |
| P9 | Moderation: nothing until the trigger fires | None now | Moderation help | None | #378, decision 15 | read |
| P10 | Practical guide gaps: review the sources and merge or not | Codex | Guides for popular spots | None | #389 | read |

The radar save itself is done:
- The cell backfill ran 24 to 25 October. [read: `docs/RADAR-RAIN-CHECK-2026-10.md`, "How it was run"]
- The per-overflow save ran on 26 October, from 00:25 to 07:26 UTC. It covered 704 days, from 21 Nov 2024 to 25 Oct 2026, for 14,630 overflows, and exited 0. [read: `swimsignal-private/radar-per-overflow/run.log`]
- Section 9 of `docs/MET-OFFICE-DATA-2026-10.md` still lists both as to do. That text is out of date.
- Only P7 is left before 21 November.

### 9.3 Model windows already running

These read-outs are dated in the repository. None deploys itself.

| # | Read-out | Read on or after | If data falls short | Source | Basis |
|---|---|---|---|---|---|
| W1 | Lead calibration B (A1 option B), live window 18 Oct to 14 Nov | **16 Nov 2026** | None stated | `docs/LEAD-CALIBRATION-B-TEST-2026-10.md` | read |
| W2 | Ensemble rain (D4), 23 Oct to 19 Nov | **21 Nov 2026** | to 3 Dec, read 5 Dec | `docs/ENSEMBLE-RAIN-TEST-2026-11.md` | read |
| W3 | Live-status shadow, 25 Oct to 21 Nov | **23 Nov 2026** | to 5 Dec, read 7 Dec | `docs/LIVE-STATUS-SHADOW-TEST-2026-10.md` | read |
| W4 | Company calibration (A8), 26 Oct to 22 Nov. Not deployed before option B runs | **25 Nov 2026** | to 6 Dec, read 9 Dec | `docs/COMPANY-CALIBRATION-TEST-2026-11.md` | read |
| W5 | Upgraded overflows option B. The 2026 ERA5-Land fetch with its call count needs an approval. The run uses window L to 30 Nov | Run on or after **2 Dec 2026** | None stated | `docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md`, order of work | read. Approved by merging #325. Whether the import and fetch steps are done was not checked |

The read-outs are agent work. Whether adopting a result counts as routine, and so is Codex's decision, is not
written anywhere. [inferred] Scheduled tasks are said to read W1 to W4. [inferred: from notes outside the
repository; not checked]

### 9.4 Partner and licence contacts

| # | Action | Owner | Unblocks | Date | Source | Basis |
|---|---|---|---|---|---|---|
| C1 | UKCEH Bloomin' Algae: send the licence enquiry, or not. A draft exists and is marked "not sent". It would go from hello@swimsignal.co.uk | Ethan, approving it specifically | Algae reports on lake pages | None | `docs/EXPANSION-2026-10.md`, "Draft UKCEH enquiry"; `docs/ROADMAP-2026-10.md` item 9 | read |
| C2 | Independent-review invitation to Prof. Richard Quilliam (Stirling): send it or not | Ethan, approving it specifically | Outside review of the algae work | None | `docs/EXPANSION-2026-10.md`, same section | read |
| C3 | Tim Boden: send the model write-up and scripts agreed on 24 Oct | Ethan | The data swap | None | notes outside the repository | inferred |

### 9.5 Carried from notes, not checked tonight

These come from notes kept outside the repository. I did not open a source for them on 26 October, so each needs
checking before anyone acts on it.

- The hosting move to Cloudflare Pages waits on the `CLOUDFLARE_API_TOKEN` secret (`docs/HOSTING-MOVE-2026-10.md`,
  PR #270). `gh secret list` printed nothing on 26 Oct. That may mean no access rather than no secrets.
  [inferred]
- The push Worker redeploy and `MAIL_WEBHOOK_SECRET` were Ethan's steps on 4 October. [inferred]
- The API has not been deployed since the Fly trial ended, so API-only fixes reach no one. [inferred]
- An Ilkley overflow note is owed if a source comes back. [inferred]

## 10. Proposed amendments: both resolved, 26 October 2026

Two questions about the plan's text were raised here before any session. Both are resolved by the headline
clarification approved on 26 October 2026 by Codex, under the delegation of routine decisions Ethan gave that
day. It is recorded, with the original text kept, in the plan (section 12) and the run sheet (section 8).

1. **Plan, section 10 item 2 (headline baseline).** The plan's "live wording" and "scoped headline" are the same
   words, since PR #284 has been live since 20 October. **Resolved (H1, H3):** every participant uses the live
   scoped wording; the old bare "Low risk" is not restored and there is no headline comparison. Each record
   holds the exact headline, URL and "Issued" line.
2. **Plan, section 8, "Task 2 fails".** Option B (#284) is already live. **Resolved (H4):** if task 2 fails, a
   clearer explanatory-wording prototype informed by the observed errors is evaluated, option A possibly first,
   with a focused retest before any wider promotion. No wording is rolled out automatically. Scoring and fail
   lines stay exactly as written (H2).

## 11. What I could not verify

- Whether the thank-you has been decided anywhere outside the repository.
- Whether scheduled tasks for W1 to W4 still exist.
- Whether option B's import and 2026 ERA5-Land fetch (W5, steps 2 and 3) have been done.
- The live quality page's row counts after #382 (taken from Codex's check).
- The repository's secrets (`gh secret list` printed nothing).
