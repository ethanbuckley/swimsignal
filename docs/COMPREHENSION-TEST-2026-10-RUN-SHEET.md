# Comprehension test run sheet, Lake District, October to November 2026

The moderator's checklist for one session of the plan in `docs/COMPREHENSION-TEST-2026-10.md`, with the
consent wording and the privacy rules. The record to fill in and the analysis are in
`docs/COMPREHENSION-TEST-2026-10-RECORDS.md`. Written on 26 October 2026, before any session. Nothing here
has been run with a participant.

The tasks, their words, the scoring rubric and the fail lines are the plan's. This sheet adds no criterion.
Where the plan is unclear, the point is listed under "Questions for Ethan" at the end, and the sheet says
what to record until it is answered.

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
   section 3). If they agree, record on your own device, not to a video service's cloud.
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
3. Task 3 spot: choose from "Task 3: a page with gaps".
   ⚠ The table shows five rows, sorted with the lake's missing E. coli estimate counted as a gap. River
   spots with two other gaps can drop off the list. On 26 October all four river spots were hidden this
   way: River Eden at Armathwaite and at Lazonby, River Lune at Devil's Bridge and River Duddon at
   Birks Bridge, each with "the E. coli estimate is untested this month" and "no access information".
   Their pages may also show a high headline, which can pull attention from the gaps. Open one or two of
   them before you choose. Which spot to prefer is question 5.
4. Open each chosen page and write in the record: the spot, its headline, its "Issued" line as the page
   shows it, and every gap the page shows. The gaps you write here are what you count against in task 3.
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
- Stuck for one minute: ask **"What would you try next?"**. Help only after two minutes, and record that
  help was given and what it was.
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
   Notes: the planner works in miles, not minutes; record a conversion or a question about it as
   friction (question 3). The planner's day is the strip under "Plan a swim"; the map's own day menu
   changes only the map. Do not write their town in the record; write the distance they chose.
2. **"Open [the low-risk spot]. Tell me, in your own words, what this page is telling you about swimming
   there today."** Then: **"What does 'Low risk' mean here?"**
   Write both answers word for word. Score afterwards (section 4), not during.
   ⚠ Do not prompt for limits. Note only what they say unprompted. Why it goes wrong: a pause after the
   answer feels like an invitation to add "Anything else it doesn't cover?", which is a prompt for
   limits. Let the pause sit, then move to task 3.
3. **"Open [the spot with gaps]. Is there anything this page does not know, or cannot tell you?"**
   Count each gap named, against the list you wrote that morning. Note if they treat a gap as good news
   (for example, "no overflow found, so it's clean").
4. **"Save this spot. Now go back to the home page and find it again."** Then, on a phone: **"Close the
   browser, open it again, and find your saved spot."**
   Note which route they take. On an iPhone, note whether they use Safari or the Home Screen app: the two
   keep separate saved lists.
5. Group leaders only: **"You are running a session at [a spot they use, or the nearest listed one] on
   Saturday at 10. Prepare what you would send your team or put in your risk assessment."**
   Watch for: whether they find the event page, the sites view or the decision record; whether the limits
   travel with what they prepare; how long it takes; what they say is missing.

### Closing questions, in this order

1. "What would make you come back before your next swim (or session)?"
2. "What did you not trust, and why?"
3. "What did you want to know that it did not tell you?"
4. Group leaders only: the buyer-interview questions from the launch kit.
5. ⚠ Only now, if they asked something during the tasks that you did not answer, answer it plainly.
   Why it goes wrong: moderators answer mid-task to be kind; this is where the kindness goes instead.
6. Ask: **"May I send you one short email in a week, and one a week later, to ask whether you used
   it?"** Record yes or no. Send nothing to anyone who says no (plan, section 7). Question 8 is about a
   third check-in at four weeks.
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
5. If you recorded, check the notes against the recording, then delete the recording (question 11).
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
> check the notes, and is deleted once they are checked.
>
> **Where it is kept.** On Ethan's computer, in a private folder. Never in SwimSignal's public code or
> website. Your contact details are kept in a separate list from the notes.
>
> **What is published.** A summary of all the sessions together, and the changes made because of it. It
> does not name you. Your words are quoted in it, without your name, only if you agree below.
>
> **How long.** The notes are deleted once the summary is written, unless you agree to more. If you
> agree to the follow-up emails, your contact details are kept until the last one is answered, then
> deleted.
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
| Contact list: code, name, how to reach them, follow-up answer | A separate file from the records, not in the records folder | The last follow-up is answered or given up on (question 10) |
| Recording, only with agreement | The moderator's own computer, not a cloud service | The notes are checked against it (question 11) |
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
what it lists, and it lists no research sessions. Question 12 asks whether to add a section before the
first session. A possible text:

> **Research sessions.** If you take part in a test session, the operator keeps notes of what you did and
> said under a code, not your name, and your contact details separately if you agreed to follow-up
> emails. The basis is your consent. The notes are kept on the operator's computer, not on this website or
> in its source code, and deleted once a summary of all sessions is written; contact details are deleted
> after the last follow-up. You can withdraw at any time by email.

## 7. Questions for Ethan

Each is a point the plan leaves open. Until it is answered, the record keeps the raw facts, so any answer
can be applied afterwards.

1. **Per-task outcome.** The brief for these materials asked for success, partial or fail per task. The
   plan defines a three-way score only for task 2 (right, partly right, wrong). For tasks 1, 3, 4 and 5
   it states the measure and a fail line for the round, not an outcome per person. Do you want a
   per-person outcome for those tasks, and if so, what is "partial"? Until then the record keeps the
   plan's measures and the outcome field is left blank.
2. **Does "What would you try next?" count as help?** The plan prompts at one minute and helps at two.
   Task 1 fails on people who "need help"; task 4 counts "unaided". The record notes the prompt and the
   help separately.
3. **Task 1's words.** "Within half an hour" against a planner in miles; and does finding one place,
   not two, count as done?
4. **What counts as naming a gap in task 3.** Only what the page shows that day (the picker's list), or
   any true limit the participant states (for example "it doesn't cover algae")? Does the lake's missing
   E. coli estimate count? The picker and the private session card say yes; the plan's list of four
   does not name it.
5. **Which task 3 spot in the Lake District.** No spot in the area had an overflow without a live feed
   on 26 October, and none had more than two kinds of gap. The plan's example, Long Bridges in Oxford,
   has had all four but is outside the area. Use the local spot with the most gaps, or Long Bridges? And
   if local: a river (two gaps, a high headline) or a lake (one gap besides the lake estimate, a moderate
   headline)?
6. **Task 4 on a phone.** Is the close-and-reopen step part of "unaided"? A participant can pass the
   first half and fail the second.
7. **Task 5.** What counts as having produced a briefing: anything they would send, or one that
   carries the limits?
8. **Follow-ups at 7 and 14 days, or also 28?** The plan (section 7) says 7 and 14. The private
   session card and check-in log also have 28. The consent wording follows the plan; a third email needs
   its own consent line.
9. **Answering questions about lakes.** The private session card says to say plainly, if asked, that
   lakes are the least tested part. The plan says not to explain the site. This sheet answers only after
   the tasks (section 3, closing step 5). Is that right?
10. **How long to wait for a follow-up reply** before deleting the contact list.
11. **The recording.** The plan says nothing on keeping it. The consent wording says it is deleted once
    the notes are checked against it.
12. **The privacy notice.** Add the research-sessions section before the first session? Whether the
    sessions change anything about the ICO fee was not checked.
13. **The repeat-use fail line** says "fewer than 3 of 8". With 9 or 10 participants, is it still 3?
14. **The older plan's release rule.** `docs/SWIMMER_TESTING.md` treats reading "low" as a safety
    guarantee, or mixing up an annual rating with today's sample, as release-blocking. The new plan keeps
    that file's recording rules but does not say whether this rule still applies. The analysis records
    both kinds of misreading either way.
15. **The picker's task 3 order.** It counts the lake's missing estimate when sorting, so on 26 October
    rivers with two other gaps fell below lakes with one, and off the five-row table. Not changed here.
    Change the sort to ignore that gap, or show more rows?
