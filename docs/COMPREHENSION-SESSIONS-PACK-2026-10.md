# Comprehension sessions: execution pack, and what is still waiting on a person

Written on 26 October 2026, at about 23:00 UTC. It is an index for running the sessions in the plan, plus a list of
every action across SwimSignal that a person has to take. It adds no rule. The rules are in three files, and this
pack points into them by section:

- **The plan:** `docs/COMPREHENSION-TEST-2026-10.md` (questions, fail lines, tasks, rubric, what results decide).
- **The run sheet:** `docs/COMPREHENSION-TEST-2026-10-RUN-SHEET.md` (checklist, consent wording, privacy rules,
  defaults A1 to A7, Ethan's decisions D1 to D8).
- **The records file:** `docs/COMPREHENSION-TEST-2026-10-RECORDS.md` (blank record, tally, public summary).

Where this pack and those files differ, those files win.

Every statement below is marked. **[read]** means I opened the file, page or log named on 26 October 2026.
**[inferred]** means it comes from notes or reasoning, not from a source I opened, and needs checking.

## 1. Where things stand

- No session has been run. [read: `swimsignal-private/research/2026-10-comprehension/` holds the README, the
  session card, a record sheet and a check-in log with a header line only, and the 24 October dry run. There is no
  P0X record.]
- No one has been recruited, and no recruitment message has been drafted or sent by this work. [inferred: no
  record of one in the repository or the private research folder]
- The privacy notice's "Research sessions" section is live on https://swimsignal.co.uk/privacy. [read: fetched
  26 Oct, about 22:50 UTC; source `src/dipcast/pages/privacy.html`, merged in PR #380]
- SwimSignal is registered with the ICO and the fee is paid. [read: plan section 11, D8; confirmed by Ethan]
- The spot picker is on main: `scripts/pick_test_spots.py`, ranking fix from PR #375. [read]
- UK time is UTC until 28 March 2027 (the clocks went back on 25 October). [read: run sheet section 2, step 5]

## 2. One-off pre-flight, before the first participant is contacted

Each step is Ethan's. Tick it here, or in the private README.

1. **Settle the thank-you** (plan, section 10 item 1). Recommended there: a £10 voucher for swimmers, none for
   leaders, checked against the organiser plan's section 5 first, since money paid may count as trading. Then fill
   the "[Thank-you line, if decided]" in the consent wording (run sheet, section 5), or delete it.
   You will know it worked when the consent text in your private copy has no square brackets left.
2. **Decide which headline wording each participant sees** (plan, section 10 item 2). Recommended there: the live
   wording for the first four, then the scoped headline if its PR is merged by then. [inferred: I could not find
   the headline-scope PR by title search on 26 Oct; check whether it exists before relying on the switch.]
3. **Choose a note-taker, or none** (plan, section 10 item 3). It must be someone who has not seen the site.
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
| Suggested split, swimmer | opening 3, task 1 up to 6, task 2 up to 5, task 3 up to 4, task 4 up to 4, closing 6 | run sheet s3 |
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
2. Read or show the consent wording (run sheet, section 5). Take the four yes/no answers aloud on a call, and write
   them and the time in the record. No signature: a signed form would hold their name.
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

The round is done when all of these are true:

- 8 to 10 sessions completed, with the mix in plan section 2, or a written note of why fewer.
- A record per participant in the private folder, each with its consent answers.
- Day 7 and day 14 follow-ups sent to everyone who said yes, and the answers in the records.
- The tally table filled, with the wording version each participant saw.
- One public summary (records file, section 3) that passed the re-identification check.
- The plan's section 8 decisions taken, each as its own PR or issue.
- Contact details deleted (D6), recordings deleted (D7), and raw notes deleted once the summary is written, by
  31 January 2027 at the latest.

The plan's own limit applies: eight people give direction, not proof. Write that in the summary.

## 9. Outstanding human actions across SwimSignal

Owner "Ethan" means only Ethan can do it, or it needs his yes. "Agent" means a Claude or Codex session can do it
once the decision in the same row is made. Nothing here is drafted or sent. Dates are those in the source.

### 9.1 Comprehension sessions

| # | Action | Owner | Unblocks | Date | Source | Basis |
|---|---|---|---|---|---|---|
| S1 | Decide the participant thank-you, then fill or delete the consent line | Ethan | Recruitment; the consent text | Before recruiting | plan s10 item 1; run sheet s5 | read (decision not found recorded: inferred open) |
| S2 | Decide which headline wording participants see; confirm the headline-scope PR exists | Ethan | Task 2 baseline and comparison | Before session 1 | plan s10 item 2 | read; PR not found (inferred) |
| S3 | Choose a note-taker or none | Ethan | Blind second scoring of task 2 | Before session 1 | plan s10 item 3; records s2.3 | read |
| S4 | **Approve the exact recruitment post(s) and each group or organiser they go to.** None drafted here | Ethan, specific approval | Every session | Week 1, from 26 Oct | plan s2, s9 | read |
| S5 | Book sessions, Wednesday to Friday only | Ethan | Sessions | First slots 28 to 30 Oct | run sheet s1 step 3 | read; slots inferred |
| S6 | Run 8 to 10 sessions as moderator | Ethan | All results | Weeks 1 and 2 | plan s9, s10 item 3 | read |
| S7 | Send day 7 and day 14 follow-ups to those who agreed, from hello@ | Ethan | Repeat-use count (D4) | 7 and 14 days after each session | plan s7; D4 | read |
| S8 | Delete contacts (day 21), recordings (day 7), notes (after summary, by 31 Jan 2027) | Ethan | Keeps to the privacy notice | As stated | D6, D7, plan s6 | read |
| S9 | Analyse and write the public summary, after the re-identification check | Ethan, or an agent with Ethan's review | Plan s8 decisions | After the round | records s2, s3 | read |
| S10 | Three prospective customers try the session workflow for a real activity | Ethan | Pilot evidence | Week 2 | plan s9; `docs/PILOT-SESSIONS.md` | read |
| S11 | Check the private folder is still unsynced and not backed up before session 1 | Ethan | Accuracy of the privacy notice | Before session 1 | run sheet s6 | read |

### 9.2 AI and data programme (draft PRs #377 to #385)

All of these PRs are drafts, by Ethan's decision 16 of 26 October (`docs/AI-PROGRAMME-2026-10.md` on
`docs/ai-programme-status`, PR #378). Merging any of them is Ethan's call. [read: `gh pr list`, 26 Oct about
22:45 UTC, open: #377, #378, #379, #381, #382, #383, #384, #385, all drafts]

| # | Action | Owner | Unblocks | Date | Source | Basis |
|---|---|---|---|---|---|---|
| P1 | Approve, change or decline the algae-incident test statement | Ethan | Its one fetch and score | None | #385, `docs/LAKE-ALGAE-INCIDENT-TEST-2026-10.md` ("waits for Ethan's approval") | read |
| P2 | Frensham Great Pond: approve or decline the advisory draft line, by a PR adding an entry to `data/advisories/approved.json` (empty on 26 Oct). Re-run the finder first: the approval must match the current draft | Ethan only | An EA "advice against bathing (harmful algae)" line, once #379's spot-page block is built and merged | EA incident open since 19 Jun, still open 26 Oct | #379, `docs/ADVISORY-FINDER-2026-10.md` | read |
| P3 | Decide merges of #379 and #382 when the product-brief work on them finishes. #382 needs a real site build and full CI first | Ethan | Advisory block; data-quality page flags | None | AI-PROGRAMME product brief items 1 and 2 | read |
| P4 | River rises: read the evaluation plan; any change by dated amendment before the run | Ethan | The run | Run not before **2 Nov 2026**; if possible before **21 Nov** | #383, `docs/RIVER-RISES-SCOPE-2026-10.md` | read |
| P5 | River rises: run once, alone on the machine, offline from the cache | Agent | The verdict; a shadow-log decision for Ethan if C1 or C2 passes | 2 Nov to 21 Nov | same | read |
| P6 | Missing event ends: measure again; fix only if rule B changes levels at over 1% of spot-builds | Agent; Ethan merges | A fix or a confirmed no-fix | On or after **9 Nov 2026** | #384; AI-PROGRAMME decision 11 | read |
| P7 | Radar: decide whether to keep the raw files (about 34 GB now, 1.4 GB a month) | Ethan | Radar history for spots added later | Before about **20 Nov 2026**, when the oldest month may start to go | `docs/MET-OFFICE-DATA-2026-10.md` s6, s9 | read |
| P8 | Lab-chlorophyll test statement: review before any fetch | Ethan | That test | None | AI-PROGRAMME product brief | read (statement "to come") |
| P9 | Moderation: no action until the trigger fires (over 50 waiting three weeks running, and the other limits) | Ethan | Moderation help | None | #378, decision 15 | read |
| P10 | Practical guide gaps PR: review the sources and merge or not | Ethan | Guides for popular spots | None | AI-PROGRAMME product brief item 3 (sister PR to this one) | inferred: PR not yet open when written |

The radar save itself is done. The cell backfill ran 24 to 25 October [read: `docs/RADAR-RAIN-CHECK-2026-10.md`,
"How it was run"]. The per-overflow save ran 26 October, 00:25 to 07:26 UTC, 704 days from 21 Nov 2024 to 25 Oct
2026, 14,630 overflows, exit 0 [read: `swimsignal-private/radar-per-overflow/run.log`]. `docs/MET-OFFICE-DATA-2026-10.md`
section 9 still lists both as to do; that text is out of date. Only P7 is left before 21 November.

### 9.3 Model windows already running

These read-outs are dated in the repository. Each result is a decision for Ethan; none deploys itself.

| # | Read-out | Read on or after | If data falls short | Source | Basis |
|---|---|---|---|---|---|
| W1 | Lead calibration B (A1 option B), live window 18 Oct to 14 Nov | **16 Nov 2026** | None stated | `docs/LEAD-CALIBRATION-B-TEST-2026-10.md` | read |
| W2 | Ensemble rain (D4), 23 Oct to 19 Nov | **21 Nov 2026** | to 3 Dec, read 5 Dec | `docs/ENSEMBLE-RAIN-TEST-2026-11.md` | read |
| W3 | Live-status shadow, 25 Oct to 21 Nov | **23 Nov 2026** | to 5 Dec, read 7 Dec | `docs/LIVE-STATUS-SHADOW-TEST-2026-10.md` | read |
| W4 | Company calibration (A8), 26 Oct to 22 Nov. Not deployed before option B runs | **25 Nov 2026** | to 6 Dec, read 9 Dec | `docs/COMPANY-CALIBRATION-TEST-2026-11.md` | read |
| W5 | Upgraded overflows option B: approve the 2026 ERA5-Land fetch with its call count; the run uses window L to 30 Nov | Run on or after **2 Dec 2026** | None stated | `docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md`, order of work | read (approved by merging #325; whether import and fetch steps are done: not checked) |

Scheduled tasks are said to read W1 to W4 [inferred: from notes outside the repository; not checked].

### 9.4 Partner and licence contacts

| # | Action | Owner | Unblocks | Date | Source | Basis |
|---|---|---|---|---|---|---|
| C1 | UKCEH Bloomin' Algae: send the licence enquiry, or not. A draft exists and is marked "not sent". It goes from hello@swimsignal.co.uk | Ethan, specific approval | Algae reports on lake pages | None | `docs/EXPANSION-2026-10.md`, "Draft UKCEH enquiry"; `docs/ROADMAP-2026-10.md` item 9 | read |
| C2 | Independent-review invitation to Prof. Richard Quilliam (Stirling): send or not | Ethan, specific approval | Outside review of the algae work | None | `docs/EXPANSION-2026-10.md`, same section | read |
| C3 | Tim Boden: send the model write-up and scripts agreed on 24 Oct | Ethan | The data swap | None | notes outside the repository | inferred |

### 9.5 Carried from notes, not checked tonight

These come from notes kept outside the repository. I did not open a source for them on 26 October, so each needs
checking before anyone acts on it.

- Hosting move to Cloudflare Pages waits on the `CLOUDFLARE_API_TOKEN` secret (`docs/HOSTING-MOVE-2026-10.md`, PR
  #270). `gh secret list` printed nothing on 26 Oct, which may mean no access rather than no secrets. [inferred]
- The push Worker redeploy and `MAIL_WEBHOOK_SECRET` were Ethan's steps on 4 October. [inferred]
- The API is not deployed since the Fly trial ended; API-only fixes reach no one. [inferred]
- An Ilkley overflow note is owed if a source comes back. [inferred]

## 10. What I could not verify

- Whether the thank-you, the headline wording and the note-taker have been decided anywhere outside the repository.
- Whether the headline-scope PR the plan names exists.
- Whether scheduled tasks for W1 to W4 still exist.
- Whether option B's import and 2026 ERA5-Land fetch (W5, steps 2 and 3) have been done.
- The repository's secrets (no output from `gh secret list`).
