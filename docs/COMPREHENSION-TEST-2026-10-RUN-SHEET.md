# Comprehension test run sheet, Lake District, October to November 2026

The moderator's checklist for one session of the plan in `docs/COMPREHENSION-TEST-2026-10.md`, with the
consent wording and the privacy rules. The record to fill in and the analysis are in
`docs/COMPREHENSION-TEST-2026-10-RECORDS.md`. Written on 26 October 2026, before any session. Nothing here
has been run with a participant.

The tasks, their words, the scoring rubric and the fail lines are the plan's. This sheet adds no criterion.
Where the plan leaves a point open, section 7 either names the default this sheet uses, taken from the
plan, or lists it as a decision only Ethan can make, with what the record does until then. The checklist
already uses the defaults, so the moderator never has to stop and decide.

**Before session 1:** decisions D6, D7 and D8 in section 7 (privacy) must be settled. They block the
first session.

**⚠ marks the steps where a moderator most often goes wrong, with the reason.**

The winter plan runs every session in one area: "Cumbria and the Lake District", the area heading on
swimsignal.co.uk/spots.html.

## 1. The day before

1. Give the participant a code, P01 to P10, in order of sessions. Write the code and their contact
   details in the contact list (section 6), never in the record.
2. Note whether they are a swimmer (30 minutes, tasks 1 to 4) or a group leader (45 minutes, tasks 1
   to 5), and what device they will use. The plan wants at least two on an iPhone and at least two who
   do not follow sewage news (plan, section 2).
3. ⚠ **Book Wednesday to Friday.** Task 1 asks about "this Saturday or Sunday", and Plan a swim offers
   today and the next four days. From a Monday, Saturday is not offered; from a Tuesday, Sunday is not.
   Why it goes wrong: the task reads fine on any day, and the missing weekend day only shows mid-task.
   (Found in the 24 October dry run.)
4. Consent: have the consent wording in section 5 ready, printed for a session in person, or as text you
   can paste into the call's chat. Have the thank-you settled first if there is one (plan, section 10
   item 1); the wording has a line for it.
5. Recording: the default is notes only. Record only if the participant agrees at the start (plan,
   section 3), and only once Ethan has decided how long a recording is kept (D7). If they agree, record
   on your own device, not to a video service's cloud.
   ⚠ Why it goes wrong: video call services can save a recording to their own cloud, and the record
   button does not always say where it saves. A cloud recording sits on their servers, outside the
   private folder.
6. Device and call:
   - Video call: check you can see a shared phone screen. On an iPhone the participant starts screen
     sharing from the call app; on a laptop they share the browser window. Have a fallback ready: a
     session in person, or the participant reading aloud what they see.
   - In person: sit beside them. Do not touch their device.
   - Your own device charged; a timer you can start silently.
7. Check the site loads: open https://swimsignal.co.uk/, one spot page, Plan a swim and Saved. On a
   spot page, read the "Issued" line (for example "Issued Mon 17:44"). If it is more than a day old,
   the build may be stuck; write that in the record and consider moving the session.
8. Check which headline wording is live, the current one or the scoped headline, and note it for the
   record (plan, section 10 item 2).
9. Copy the blank record (`COMPREHENSION-TEST-2026-10-RECORDS.md`, section 1) into the private folder as
   `P0X-2026-MM-DD.md`. Never into this repository.
10. Group leaders: have the buyer-interview questions from the launch kit open. They come after the
    tasks and the three closing questions, never before (plan, section 2).

## 2. The morning of the session

1. From a swimsignal checkout, run:

       uv run python scripts/pick_test_spots.py --area "Cumbria and the Lake District"

   It reads the published forecast and spot pages and writes nothing. Save its output in the private
   folder as `picker-2026-MM-DD.md`.
2. Task 2 spot: take the first row of "Task 2: low risk with overflows upstream". Open its page and
   check the headline starts "Low risk".
3. Task 3 spot: take the first row of "Task 3: a page with gaps". Use a Lake District spot; use River
   Thames, Long Bridges, Oxford (the plan's example) only if the area has none that qualifies (default
   A3).
   ⚠ Use the picker from PR #375 or later. Why it goes wrong: before #375 the list counted the lake's
   missing E. coli estimate when ranking, so on 26 October the five rows shown were all lakes and the
   rivers with two qualifying gaps were hidden. #375 ranks by the qualifying gaps and says how many
   spots it does not show. Until #375 is merged, run the picker from its branch,
   `fix/picker-task3-order`. The first row may have a high headline, as the River Eden spots did on 26
   October; that does not change the choice.
4. Open each chosen page and write in the record: the spot, its headline, its "Issued" line as the page
   shows it, and every gap the page shows. The gaps you write here are what you count against in task 3.
   Mark which are among the plan's four (an overflow with no live feed, the E. coli estimate out of
   season, unchecked EA advice, unconfirmed access) and which is the lake's missing E. coli estimate,
   which is not one of the four.
5. Write the picker's "Forecast issued" time too. It comes from spots.json and can differ by a few
   minutes from the page's "Issued" line (17:37 against 17:44 UTC on 26 October). The page's line is
   what the participant sees. UK time is UTC until 28 March 2027.
6. Note anything on the task 2 page a participant may ask about. Example from the dry run: Rydal Water
   was "Low risk" while its one overflow upstream was discharging.
7. ⚠ **Within 30 minutes of the session, reload both pages.** If the task 2 spot no longer says "Low
   risk", or the task 3 spot has lost its gaps, run the picker again and choose again. Why it goes wrong:
   the site rebuilds through the day, and a spot picked at 8:00 can be "Moderate" by an afternoon
   session.
8. Group leaders: decide the task 5 spot, one they use, or the nearest listed one.

## 3. During the session

### Opening, word for word

1. Say: **"This is a test of the website, not of you. Please think aloud. The forecast may be out of
   date, so please do not use today's session to decide whether to swim."**
2. Read the consent wording (section 5) or give it to them to read. Ask: "May I take notes?" and, only
   if you want to record, "May I record the screen and our voices?". Tick their answers in the record.
   Stop if they say no to notes.

### Rules for every task

- Read each task as written. Do not paraphrase it.
- Start the timer when you finish reading the task. Stop it when they say they are done or give up.
- Do not explain the site, define terms or point at anything.
- Stuck for one minute: ask **"What would you try next?"**. That prompt is not help. Help is anything,
  at or after two minutes, that points to where to go (default A1). Record both, each with its time,
  and what the help was.
- Neutral follow-ups only: **"What does that tell you?"**, **"What made you say that?"**.
- ⚠ Never **"Did you notice...?"** or **"Would it help if...?"**. Why it goes wrong: both slip out when a
  participant is near the thing you hope they find. Either one turns an unprompted finding into a
  prompted one, and the task 2 and task 3 counts then mean nothing.
- ⚠ When a participant asks you a question about the site ("What does moderate mean?", "Is that
  live?"), do not answer it. Say "What do you think?" or "What does that tell you?", and note the
  question; it is a finding. Why it goes wrong: answering is the polite reflex, and one answer during
  task 2 gives away the thing being tested.
- Write their words in quotation marks, as said. Write your own reading separately (the record has two
  fields for this).
- Do not ask them to clear the site's data, even if they have used SwimSignal before. It would delete
  their own saved spots. Note in the record if they already had saved spots.

### The tasks

Swimmers do tasks 1 to 4; group leaders do all five. Suggested time per task, not from the plan, so that
a swimmer's session fits 30 minutes: opening 3, task 1 up to 6, task 2 up to 5, task 3 up to 4, task 4
up to 4, closing questions 6. The plan's own times: a prompt at 1 minute, help at 2, task 1 fails for a
participant past 5 minutes, task 5 fails past 10.

1. **"You want to swim this Saturday or Sunday somewhere within half an hour of [their town]. Find two
   places you might go."**
   Watch for: whether they find Plan a swim or the map, whether they pick a day, what they compare, what
   they say makes one better.
   Read it exactly as written, "half an hour" included (default A2). The planner works in miles, not
   minutes; if they convert or ask, do not answer, and note it as friction. Record how many places they
   found and how. Done or not done is the plan's measure: completed without help, and the time taken.
   The planner's day is the strip under "Plan a swim"; the map's own day menu changes only the map. Do
   not write their town in the record; write the distance they chose.
2. **"Open [the low-risk spot]. Tell me, in your own words, what this page is telling you about swimming
   there today."** Then: **"What does 'Low risk' mean here?"**
   Write both answers word for word. Score afterwards (section 4), not during.
   ⚠ Do not prompt for limits. Note only what they say unprompted. Why it goes wrong: a pause after the
   answer feels like an invitation to add "Anything else it doesn't cover?", which is a prompt for
   limits. Let the pause sit, then move to task 3.
3. **"Open [the spot with gaps]. Is there anything this page does not know, or cannot tell you?"**
   Count each gap named, against the list you wrote that morning. Write every limit they name, with
   their words, and mark it as one of the plan's four gaps, the lake's missing estimate, or another
   limit; what counts is Ethan's decision D2, and the record keeps all three. Note if they treat a gap
   as good news (for example, "no overflow found, so it's clean").
4. **"Save this spot. Now go back to the home page and find it again."** Then, on a phone: **"Close the
   browser, open it again, and find your saved spot."**
   Note which route they take. On an iPhone, note whether they use Safari or the Home Screen app: the two
   keep separate saved lists. Record the two halves separately, each with any prompt or help. On a
   phone, "unaided" for the fail line means both halves done without help (default A4).
5. Group leaders only: **"You are running a session at [a spot they use, or the nearest listed one] on
   Saturday at 10. Prepare what you would send your team or put in your risk assessment."**
   Watch for: whether they find the event page, the sites view or the decision record; whether the limits
   travel with what they prepare; how long it takes; what they say is missing. Record what they produced
   and whether it carries the limits; what counts as a briefing is Ethan's decision D3.

### Closing questions, in this order

1. "What would make you come back before your next swim (or session)?"
2. "What did you not trust, and why?"
3. "What did you want to know that it did not tell you?"
4. Group leaders only: the buyer-interview questions from the launch kit.
5. ⚠ Only now, if they asked something during the tasks that you did not answer, answer it plainly.
   That includes questions about lakes: say plainly that lakes are the least tested part of the forecast
   (default A6). Why it goes wrong: moderators answer mid-task to be kind; this is where the kindness
   goes instead.
6. Ask: **"May I send you one short email in a week, and one a week later, to ask whether you used
   it?"** Record yes or no. Send nothing to anyone who says no (plan, section 7). Follow-ups are at 7
   and 14 days only (default A5).
7. Thank them. If there is a thank-you (plan, section 10 item 1), say how and when it arrives.

## 4. After the session

1. Within the hour, while you remember, finish the record: times, the outcome fields, and their words
   from your notes.
2. Score task 2 on the plan's rubric (section 5 of the plan), from the words you wrote, not from your
   memory of their tone. Mark separately whether they said "tested": that marks a failure of the
   forecast-versus-test message whatever the score.
3. Fill the summary rows at the end of the record. They use the plan's section 6 columns.
4. Save the record in the private folder (section 6). ⚠ Check the file is not inside the swimsignal
   checkout. Why it goes wrong: a record saved next to the docs it was copied from lands in the public
   repository on the next commit.
5. If you recorded, check the notes against the recording, then keep or delete it as decided under D7.
6. Put the 7- and 14-day follow-up dates in your calendar for anyone who said yes, using their code,
   not their name.
7. Paper notes: type them into the record, then shred them.
8. Publish nothing yet. The public summary is written once, after the round (records file, section 3).

## 5. Consent wording

Read aloud or give to read before the first task. Plain language, so it can be read in two minutes.

> **Helping test SwimSignal**
>
> SwimSignal is a free website that forecasts the risk of sewage spills at swimming spots. It is run by
> one person, Ethan Buckley. This session tests the website, not you.
>
> **What happens.** You use the website on your own phone or computer and think aloud while you do a
> few small tasks. It takes about 30 minutes (45 for group leaders). You can skip any task or stop at
> any time, without giving a reason.
>
> **What is written down.** Notes of what you do and say, under a code (for example P03), not your name.
> We do not ask for, or write down, your health, your home address or where you are.
>
> **Recording.** Only if you agree below. A recording stays on the moderator's computer, is used only to
> check the notes, and is deleted [when, per decision D7].
>
> **Where it is kept.** On Ethan's computer, in a private folder. Never in SwimSignal's public code or
> website. Your contact details are kept in a separate list from the notes.
>
> **What is published.** A summary of all the sessions together, and the changes made because of it. It
> does not name you. Your words are quoted in it, without your name, only if you agree below.
>
> **How long.** The notes are deleted once the summary is written, unless you agree to more. If you
> agree to the follow-up emails, your contact details are kept until the last one is answered [or for
> the wait set by decision D6], then deleted.
>
> **Your rights.** You can ask to see what is held about you, have it corrected or deleted, or withdraw
> at any time, by emailing hello@swimsignal.co.uk with your code or the date of your session. You can
> also complain to the Information Commissioner's Office (ico.org.uk).
>
> **Please do not use today's forecast to decide whether to swim.** It may be out of date.
>
> [Thank-you line, if decided: what it is and when it arrives.]
>
> | | Yes | No |
> |---|---|---|
> | I agree to take part and for notes to be taken | | |
> | I agree to the screen and our voices being recorded | | |
> | My words may be quoted in the public summary, without my name | | |
> | You may email me twice, at one week and two weeks, to ask whether I used SwimSignal | | |

For a video call, the participant can answer each line aloud; write their answers and the time in the
record. Asking for a signature is not needed for this, and a signed form would hold their name.

## 6. Privacy: what is stored, where, and for how long

From the plan (sections 3, 6 and 7) and `docs/SWIMMER_TESTING.md`, and in line with the site's privacy
notice, which promises no personal data beyond what it lists.

**The repository is public.** Nothing that could identify a participant goes into it: no record, no
contact detail, no recording, no picker output with a session date next to a code. This includes
branches, pull request text and issues.

| What | Where | Kept until |
|---|---|---|
| Records, one per participant, under a code | `swimsignal-private/research/2026-10-comprehension/`, outside the repository | The summary is written; longer only if the participant agreed (plan, section 6) |
| Contact list: code, name, how to reach them, follow-up answer | A separate file from the records, not in the records folder | The last follow-up is answered, or the wait set by D6 runs out |
| Recording, only with agreement | The moderator's own computer, not a cloud service | As decided under D7 |
| Picker output for the day | The private folder, next to the records | With the records |
| Summary table and decisions | A public doc or issue, after the round | Kept; it holds no names and no contact details |

Rules:
- Codes P01 to P10. Never a name in a record.
- No medical history, home address or precise location (plan, section 3). Do not write the town used in
  task 1; write the distance chosen.
- The private folder's README says it is not in git and not backed up. Whether this Mac syncs
  `~/Documents` to a cloud service was not checked.
- Follow-up emails go only to those who said yes, and from hello@swimsignal.co.uk.

**The site's privacy notice does not cover this yet.** It says SwimSignal holds no personal data beyond
what it lists, and it lists no research sessions. Decision D8 is whether to add a section before the
first session. This PR does not change the notice. A possible text:

> **Research sessions.** If you take part in a test session, the operator keeps notes of what you did and
> said under a code, not your name, and your contact details separately if you agreed to follow-up
> emails. The basis is your consent. The notes are kept on the operator's computer, not on this website or
> in its source code, and deleted once a summary of all sessions is written; contact details are deleted
> after the last follow-up. You can withdraw at any time by email.

## 7. Defaults used, and decisions only Ethan can make

Numbers in brackets are the questions in this PR's first version (Q1 to Q15), kept so earlier comments
still match.

### Defaults used (from the plan)

Each default comes from the plan section named, and the checklist above already uses it. Ethan can
override any of them; the record keeps the raw facts, so an override can be applied afterwards.

- **A1. The one-minute prompt is not help** [Q2]. Plan, section 3: "If they are stuck for a minute, ask
  'What would you try next?'. Help only after two minutes, and record that help was given." Help is
  anything, at or after two minutes, that points to where to go. The record keeps the prompt and the help
  separately, each with its time.
- **A2. Task 1 is read exactly as written**, "half an hour" included [Q3]. Plan, section 4 gives the
  words; section 1 gives the measure, unaided completion and time. The record notes how many places were
  found and how. Done or not done stays the plan's measure; no new definition is added.
- **A3. Task 3 uses a Lake District spot**: the first row of the picker's task 3 list that morning [Q5].
  Plan, section 3 says how to choose; the winter plan runs one area. The lake's missing E. coli estimate
  is not one of the plan's four gaps. River Thames, Long Bridges, Oxford is used only if no local spot
  qualifies.
- **A4. Task 4's two halves are recorded separately** [Q6]. "Unaided" for the fail line means both
  halves done without help: plan, section 1 asks "Can people save a spot and find it again?", and
  section 4 adds the close-and-reopen step on a phone.
- **A5. Follow-ups at 7 and 14 days only** [Q8]. Plan, section 7. The private kit
  (`session-card.md` and `checkin-log.csv`, 24 October) adds a 28-day check-in; it is not used, and
  the consent wording asks for two follow-ups. The plan wins.
- **A6. No explaining during the tasks**; questions about lakes are answered plainly after the tasks,
  in the closing [Q9]. Plan, section 3: "Do not explain the site, define terms or point at anything."
  The private session card says to tell a participant, if asked, that lakes are the least tested part;
  the plan wins on timing, and the card's words are used in the closing.
- **A7. The picker ranks task 3 by the qualifying gaps** [Q15]. Fixed by PR #375, which also says how
  many qualifying spots the table does not show. Until it is merged, run the picker from its branch,
  `fix/picker-task3-order`.

### Decisions only Ethan can make

Each says what the record does until it is decided. D6 to D8 block session 1.

- **D1. A per-person outcome for tasks 1, 3, 4 and 5** [Q1]. The plan scores task 2 as right, partly
  right or wrong, and for the others gives a measure and a fail line for the round, not an outcome per
  person. Until decided: the record keeps the plan's measures and leaves the outcome field blank; the
  round's fail lines are tallied from the measures.
- **D2. What counts as naming a gap in task 3** [Q4]. Is any true limit enough (for example "it doesn't
  cover algae"), or only the gaps the page shows? Does the lake's missing estimate count? Until decided:
  the record marks each limit named as one of the plan's four gaps, the lake's estimate, or another
  limit, and the analysis tallies "named no gap" each way.
- **D3. What counts as a task 5 briefing** [Q7]: anything the leader would send, or only one that
  carries the limits? Until decided: the record keeps what they produced, whether the limits travelled
  with it, and the time, and the analysis tallies both readings.
- **D4. The repeat-use fail line with 9 or 10 participants** [Q13]. The plan says "fewer than 3 of 8".
  Until decided: the analysis reports the count of returns and how many were asked, and applies 3 as
  written.
- **D5. Whether the older plan's release rule still applies** [Q14]. `docs/SWIMMER_TESTING.md` treats
  reading "low" as a safety guarantee, or mixing up an annual rating with today's sample, as
  release-blocking. Until decided: the record notes both kinds of misreading.
- **D6. How long to wait for a follow-up reply before deleting the contact list** [Q10]. **Blocks
  session 1.** The consent wording has a placeholder for it.
- **D7. Keeping a recording** [Q11]: whether recording is offered at all, and when a recording is
  deleted. **Blocks session 1.** The consent wording has a placeholder; until decided, take notes only.
- **D8. The privacy notice and the ICO fee** [Q12]. Whether the research-sessions section (section 6)
  goes into the site's privacy notice before session 1, and whether the sessions change the ICO fee
  position (not checked). **Blocks session 1.**
