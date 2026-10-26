# Comprehension test run sheet, Lake District, October to November 2026

The moderator's checklist for one session of the plan in `docs/COMPREHENSION-TEST-2026-10.md`, with the
consent wording and the privacy rules. The record to fill in and the analysis are in
`docs/COMPREHENSION-TEST-2026-10-RECORDS.md`. Written on 26 October 2026, before any session. Nothing here
has been run with a participant.

The tasks, their words, the scoring rubric and the fail lines are the plan's. This sheet adds no criterion.
Where the plan leaves a point open, section 7 names either the default this sheet takes from the plan
(A1 to A7) or the decision Ethan made on 26 October 2026, before any session (D1 to D8). The checklist
uses both, so the moderator never has to stop and decide.

**Before anyone is recruited** (D8): the privacy notice's Research sessions section (PR #380) is merged
and live on https://swimsignal.co.uk/privacy. This sheet does not do that. SwimSignal is registered with
the ICO and the fee paid (confirmed by the operator, 26 Oct 2026).

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
5. Recording: notes only, by default (D7). Offer a recording only when it would help, and make one only
   if the participant agrees to it separately (plan, section 3). Record on your own device, not to a
   video service's cloud.
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
   ⚠ Pull main first, so the picker includes PR #375 (merged 26 October). Why it goes wrong: an older
   checkout counts the lake's missing E. coli estimate when ranking, so on 26 October its five rows were
   all lakes and the rivers with two qualifying gaps were hidden. Since #375 it ranks by the qualifying
   gaps and says how many spots it does not show. The first row may have a high headline, as the River
   Eden spots did on 26 October; that does not change the choice.
4. Open each chosen page and write in the record: the spot, its headline, its "Issued" line as the page
   shows it, and every gap the page shows. The gaps you write here are what you count against in task 3.
   Write every limitation the page itself displays: the picker's gaps, the lake's missing E. coli
   estimate on a lake, and any other limit the page states in words. This list is fixed before the
   session, and it is what task 3 counts (D2). The rule for choosing the spot is unchanged: the lake's
   estimate alone does not qualify a spot (A3).
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
   Count each limitation named that is on the list you wrote that morning, the lake's missing estimate
   included (D2). Write any other valid limit they name separately, in their words; it is recorded, not
   counted. Note if they treat a gap as good news (for example, "no overflow found, so it's clean").
4. **"Save this spot. Now go back to the home page and find it again."** Then, on a phone: **"Close the
   browser, open it again, and find your saved spot."**
   Note which route they take. On an iPhone, note whether they use Safari or the Home Screen app: the two
   keep separate saved lists. Record the two halves separately, each with any prompt or help. On a
   phone, "unaided" for the fail line means both halves done without help (default A4).
5. Group leaders only: **"You are running a session at [a spot they use, or the nearest listed one] on
   Saturday at 10. Prepare what you would send your team or put in your risk assessment."**
   Watch for: whether they find the event page, the sites view or the decision record; whether the limits
   travel with what they prepare; how long it takes; what they say is missing. It counts as a briefing
   if it carries the place, the activity's date and time, dated forecast information and the
   limitations (D3). A plain message or document is enough. Note which of the four it carries.

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

1. Within the hour, while you remember, finish the record: times, help, the other measures, and their
   words from your notes. There is no per-person overall score (D1).
2. Score task 2 on the plan's rubric (section 5 of the plan), from the words you wrote, not from your
   memory of their tone. Mark separately whether they said "tested": that marks a failure of the
   forecast-versus-test message whatever the score.
3. Fill the summary rows at the end of the record. They use the plan's section 6 columns.
4. Save the record in the private folder (section 6). ⚠ Check the file is not inside the swimsignal
   checkout. Why it goes wrong: a record saved next to the docs it was copied from lands in the public
   repository on the next commit.
5. If you recorded, check the notes against the recording and delete it, within 7 days of the session
   (D7).
6. Put the 7- and 14-day follow-up dates in your calendar for anyone who said yes, using their code,
   not their name. Add a reminder 21 days after the session to delete their contact details (D6).
   Delete them sooner when the last follow-up is answered; for anyone who said no to follow-ups, delete
   them at 21 days at the latest.
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
> **What is written down.** Notes of what you do and say, under a code (for example P03), not your name,
> and a note of what you agreed to here. We do not ask for, or write down, your health, your home
> address or where you are. A code is not the same as anonymous: while your contact details are kept,
> the notes can be linked back to you.
>
> **Recording.** None, unless you agree to it separately below. A recording stays on Ethan's computer,
> is used only to check the notes, and is deleted within 7 days.
>
> **Where it is kept.** Only on Ethan's own computer, in a private folder. Never in SwimSignal's public
> code or website, and not shared or sold. Your contact details are kept in a separate list from the
> notes.
>
> **What is published.** A summary of all the sessions together, and the changes made because of it. It
> does not name you. Your words are quoted in it, without your name, only if you agree below.
>
> **How long.** Your contact details are deleted when your last follow-up email is answered, or 21 days
> after today, whichever comes first. The notes, and the note of what you agreed to, are deleted once
> the summary of all the sessions is written, and by 31 January 2027 at the latest, unless you agree to
> them being kept longer.
>
> **Your rights.** Taking part rests on your consent. You can ask to see what is held about you, have it
> corrected or deleted, or withdraw at any time, by emailing hello@swimsignal.co.uk with your code or the
> date of your session. You can also complain to the Information Commissioner's Office (ico.org.uk). The
> privacy notice, swimsignal.co.uk/privacy, says the same under "Research sessions".
>
> **Please do not use today's forecast to decide whether to swim.** It may be out of date.
>
> [Thank-you line, if decided: what it is and when it arrives.]
>
> | | Yes | No |
> |---|---|---|
> | I agree to take part and for notes to be taken | | |
> | I agree, separately, to the screen and our voices being recorded | | |
> | My words may be quoted in the public summary, without my name | | |
> | You may email me twice, at one week and two weeks, to ask whether I used SwimSignal | | |

For a video call, the participant can answer each line aloud; write their answers and the time in the
record. Asking for a signature is not needed for this, and a signed form would hold their name. The
answers are the consent record: they stay with the participant's record and are deleted with it.

## 6. Privacy: what is stored, where, and for how long

From the plan (sections 3, 6 and 7), `docs/SWIMMER_TESTING.md` and Ethan's decisions of 26 October 2026
(section 7). The site's privacy notice says the same under "Research sessions" (PR #380).

**The repository is public.** Nothing that could identify a participant goes into it: no record, no
contact detail, no recording, no picker output with a session date next to a code. This includes
branches, pull request text and issues.

| What | Where | Kept until |
|---|---|---|
| Record, one per participant, under a code, with their consent answers | `~/Documents/GitHub/swimsignal-private/research/2026-10-comprehension/` | The summary is written, and 31 January 2027 at the latest; longer only if the participant agreed (plan, section 6) |
| Contact list: code, name, how to reach them, follow-up answers | A separate file, not in the records folder | The last follow-up is answered, or 21 days after the session, whichever comes first (D6) |
| Recording, only with separate agreement | The moderator's own computer, not a cloud service | The notes are checked against it, within 7 days (D7) |
| Picker output for the day | The private folder, next to the records | With the records |
| Summary table and decisions | A public doc or issue, after the round | Kept; it holds no names and no contact details |

These periods are practice Ethan approved on 26 October 2026, not legal deadlines (D8). The 31 January
2027 end for the notes is the one date in them chosen when the notice was written; Ethan confirms it in
PR #380.

Rules:
- Codes P01 to P10. Never a name in a record.
- A coded record is still personal data while the contact list exists. Never describe the notes as
  anonymous.
- No medical history, home address or precise location (plan, section 3). Do not write the town used in
  task 1; write the distance chosen.
- Follow-up emails go only to those who said yes, and from hello@swimsignal.co.uk.

**Where the private folder is.** What may be promised, and nothing beyond it: the records are kept in a
private folder on the operator's own computer; they are not in the public repository and not published;
that folder is not synced to a cloud service and not backed up (checked 26 October 2026). The privacy
notice says only "a private folder on the operator's own computer", not published and not in the public
source code. The checks behind it, on this Mac on 26 October 2026:
- Finder's iCloud Desktop & Documents setting is off: `defaults read com.apple.finder
  FXICloudDriveDocuments` and `FXICloudDriveDesktop` both return 0, so `~/Documents` is not synced to
  iCloud. OneDrive's folders are separate from `~/Documents` (checked by the coordinating session).
- Time Machine has no destination (`tmutil destinationinfo`), so the folder is not backed up. A lost or
  broken Mac loses the records.
- The folder is not a git repository.
- No encryption is claimed.

## 7. Defaults used, and Ethan's decisions

Numbers in brackets are the questions in this PR's first version (Q1 to Q15), kept so earlier comments
still match.

### Defaults used (from the plan)

Each default comes from the plan section named, and the checklist above uses it. Ethan can override any
of them; the record keeps the raw facts, so an override can be applied afterwards.

- **A1. The one-minute prompt is not help** [Q2]. Plan, section 3: "If they are stuck for a minute, ask
  'What would you try next?'. Help only after two minutes, and record that help was given." Help is
  anything, at or after two minutes, that points to where to go. The record keeps the prompt and the help
  separately, each with its time.
- **A2. Task 1 is read exactly as written**, "half an hour" included [Q3]. Plan, section 4 gives the
  words; section 1 gives the measure, unaided completion and time. The record notes how many places were
  found and how. Done or not done stays the plan's measure; no new definition is added.
- **A3. Task 3 uses a Lake District spot**: the first row of the picker's task 3 list that morning [Q5].
  Plan, section 3 says how to choose; the winter plan runs one area. For choosing the spot, the lake's
  missing E. coli estimate is not one of the plan's four gaps, so it alone does not qualify a spot. (For
  scoring, D2 counts it.) River Thames, Long Bridges, Oxford is used only if no local spot qualifies.
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
- **A7. The picker ranks task 3 by the qualifying gaps** [Q15]. PR #375, merged 26 October 2026, made
  this change and has the table say how many qualifying spots it does not show.

### Ethan's decisions, 26 October 2026, before any session

Ethan approved these on 26 October 2026 ("okay i approve your recommendations"), before any session was
arranged. They are applied in the checklist, the consent wording, the record and the analysis, and in a
dated note in the plan (section 11). They were set before any result existed, so results cannot move
them.

- **D1. No per-person overall score** [Q1]. Tasks 1, 3, 4 and 5 are recorded as direct measures:
  completion, help, time, limits named and misunderstandings. Task 2 keeps the plan's rubric.
- **D2. What task 3 counts** [Q4]. Any genuine limitation the selected page explicitly displays, the
  lake's missing E. coli estimate included. The list is written the morning of the session, before it
  starts. Other valid limits a participant names are recorded separately and not counted. The rule for
  choosing the spot is unchanged (A3).
- **D3. A usable briefing** [Q7] carries the place, the activity's date and time, dated forecast
  information and the limitations. A plain message or document is enough.
- **D4. The repeat-use line** [Q13]: confirmed purposeful returns of at least 3 of 8, or at least 4 of
  9 or 10. The denominator is everyone who completed a session; it is fixed before any follow-up and
  never reduced after outcomes are known. No reply counts as unknown use, not a return. Report follow-up
  consent and how many replied.
- **D5. A safety-guarantee or "water tested" misreading** [Q14]: any one clear case leads to a wording
  fix and a focused retest before the site is promoted more widely. Routine bug fixes may continue.
- **D6. Contact details** [Q10] are deleted when the participant's last follow-up is answered, or 21
  days after their session, whichever comes first. Follow-ups stay at 7 and 14 days.
- **D7. Recording** [Q11]: notes only by default. A recording only with separate agreement, when it is
  useful; the notes are checked against it and it is deleted within 7 days.
- **D8. Privacy** [Q12]: accurate research wording in the privacy notice before recruitment, matching
  what is actually done (PR #380). The retention periods are approved practice, not legal deadlines.
  Coded records may still be personal data. Consent answers stay with the research record for as long
  as it is kept. SwimSignal is registered with the ICO and the fee paid (confirmed by the operator, 26
  Oct 2026).
