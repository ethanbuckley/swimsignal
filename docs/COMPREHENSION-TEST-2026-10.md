# Comprehension and repeat-use test, October to November 2026

A plan for eight to ten moderated sessions, written on 20 October 2026 after an outside product
review. It is a plan, not evidence: nothing here has been run yet. It replaces the task list in
`docs/SWIMMER_TESTING.md` for this round and keeps that file's recording rules.

The review's advice, in short: test whether people understand the main answer and come back,
before another redesign. Its sharpest question is whether people read the green headline as a
statement that the water is safe. This plan answers that question first.

## 1. What the sessions must settle

| Question | Measured by | Fails when |
|---|---|---|
| Do people read "Low risk" as "the water is safe"? | Task 2, scored on the rubric in section 5 | 2 or more participants say safe, clean or tested |
| Can people say what the forecast does not know? | Task 3 | 3 or more name no gap |
| Can people find two options for a weekend swim? | Task 1, unaided completion and time | 3 or more need help, or any take over 5 minutes |
| Can people save a spot and find it again? | Task 4, unaided | 2 or more fail |
| Can a group leader prepare a briefing? | Task 5, group leaders only | Any leader cannot produce one in 10 minutes |
| Do people come back unprompted? | Follow-up at 7 and 14 days (section 7) | Fewer than 3 of 8 report a return visit with a purpose |

The fail lines are judgement calls made before the sessions, so the results cannot move them.
Eight people give direction, not proof. A failure by two people is still worth fixing; a pass by
eight does not show the wording works for everyone.

*Clarified 26 October 2026, before any session (section 11):* the repeat-use line is at least 3 of 8, or at
least 4 of 9 or 10, out of everyone who completed a session (D4). Any one clear safety-guarantee or "water
tested" reading leads to a wording fix and a focused retest before wider promotion (D5).

## 2. Who to recruit

- **Six swimmers** who swim in rivers or lakes at least monthly. At least two who do not follow
  sewage news. At least two on an iPhone. Recruit from the Facebook groups SwimSignal already posts in,
  and through local swimming groups' organisers. A post in a group is fine. Do not cold-email sole
  traders or clubs (PECR; see the organiser plan, section 5 item 10).
- **Three or four group leaders**: an activity-centre manager, an event organiser, a club welfare or
  safety officer, a Scout or school leader. These double as buyer conversations: use the
  buyer-interview script in the launch kit after the tasks, not before, so the price talk does not
  colour the comprehension answers.
- Exclude anyone who has helped build or review SwimSignal, and friends who have seen it often.

## 3. Setting up each session

- 30 minutes for a swimmer, 45 for a group leader. A video call with screen sharing, or in person.
  The participant uses their own phone or computer, on the live site.
- Ask permission to take notes. No recording unless they agree; no medical history, home address or
  precise location. Use codes P01 to P10.
- Say at the start, word for word: "This is a test of the website, not of you. Please think aloud.
  The forecast may be out of date, so please do not use today's session to decide whether to swim."
- Do not explain the site, define terms or point at anything. If they are stuck for a minute, ask
  "What would you try next?". Help only after two minutes, and record that help was given.
- Neutral follow-ups only: "What does that tell you?", "What made you say that?". Never "Did you
  notice...?" or "Would it help if...?".
- **Choose the test spots that morning**, since levels change. Task 2 needs a spot at low risk with
  overflows upstream. Task 3 needs a spot with at least one gap: an overflow with no live feed, the E.
  coli estimate out of season, unchecked EA advice, or unconfirmed access. River Thames, Long
  Bridges, Oxford has had all four in October. Note the spot and its level in the record.
  `uv run python scripts/pick_test_spots.py --area "<area heading from spots.html>"` lists that
  morning's candidates for both tasks from the published forecast and spot pages, with each page's
  headline and gaps.

*Clarified 26 October 2026, before any session (section 11):* recording is off by default and needs separate
agreement (D7). Task 3 counts any limitation the chosen page displays, the lake's missing E. coli estimate
included, listed the morning of the session (D2); the rule for choosing the spot is unchanged.

The run sheet for each session, the consent wording and the privacy rules are in
`docs/COMPREHENSION-TEST-2026-10-RUN-SHEET.md`; the blank record and the analysis in
`docs/COMPREHENSION-TEST-2026-10-RECORDS.md`.

## 4. The tasks

Read each task as written. Swimmers do tasks 1 to 4; group leaders do all five.

1. **"You want to swim this Saturday or Sunday somewhere within half an hour of [their town]. Find
   two places you might go."** Watch for: whether they find Plan a swim or the map, whether they
   pick a day, what they compare, what they say makes one better.
2. **"Open [the low-risk spot]. Tell me, in your own words, what this page is telling you about
   swimming there today."** Then: **"What does 'Low risk' mean here?"** Score it on the rubric in
   section 5. Do not prompt for limits; note only what they say unprompted.
3. **"Open [the spot with gaps]. Is there anything this page does not know, or cannot tell you?"**
   Count each gap named. Note if they treat a gap as good news.
4. **"Save this spot. Now go back to the home page and find it again."** Then, on a phone: **"Close
   the browser, open it again, and find your saved spot."** Note which route they take.
5. Group leaders only: **"You are running a session at [a spot they use, or the nearest listed one]
   on Saturday at 10. Prepare what you would send your team or put in your risk assessment."** Watch
   for: whether they find the event page, the sites view or the decision record; whether the limits
   travel with what they prepare; how long it takes; what they say is missing.

Then ask every participant, in this order:
- "What would make you come back before your next swim (or session)?"
- "What did you not trust, and why?"
- "What did you want to know that it did not tell you?"
- Group leaders only: the buyer-interview questions from the launch kit.

*Clarified 26 October 2026, before any session (section 11):* tasks 1, 3, 4 and 5 have no per-person overall
score (D1). A task 5 briefing counts if it carries the place, the activity's date and time, dated forecast
information and the limitations; a plain message is enough (D3).

## 5. Scoring "What does Low risk mean?"

| Score | The answer | Example |
|---|---|---|
| Right | A forecast about sewage from overflows (or "pollution from spills"), and it does not say the water is safe or cover everything | "Not much sewage is expected to reach it, but that's not the whole picture" |
| Partly right | A forecast, but treated as overall water quality or a general green light | "The water's fine today" with no mention of spills |
| Wrong | Says it was tested, measured, safe or clean | "They tested it and it's clean" |

Record the participant's words verbatim. Two "Wrong" answers fail the round (section 1). Any
participant who says "tested" marks a failure of the forecast-versus-test message, whatever their
score.

## 6. Recording

One row per participant per task, as in `docs/SWIMMER_TESTING.md`:

Participant | Swimmer or leader | Device and browser | Task | Done without help? | Time | Words used (verbatim for task 2) | Misunderstanding or friction | Severity (blocks, slows, cosmetic) | Proposed change

Keep raw notes in `swimsignal-private/research/2026-10-comprehension/`, not in this repository.
Put only the summary table and the decisions in a public issue or doc. Delete raw notes once the
summary is written, unless the participant agreed to more.

*Clarified 26 October 2026, before any session (section 11):* contact details are deleted when the last
follow-up is answered or 21 days after the session, whichever comes first (D6); a recording within 7 days
(D7); the notes and consent answers once the summary is written, and by 31 January 2027 at the latest. These
are approved practice, not legal deadlines. Coded notes are treated as personal data for as long as they
are kept, and only genuinely anonymised findings are published (D8).

## 7. Repeat use

Repeat use cannot be measured from the site: the analytics are aggregate only (Cloudflare Web
Analytics, no identifiers), by design. So ask:
- At the end of the session: "May I send you one short email in a week, and one a week later, to ask
  whether you used it?" Record yes or no. Send nothing to anyone who says no.
- At 7 and 14 days, one email each: "Have you opened SwimSignal since we spoke? If yes, what for, and
  did it change anything you did?" Count a return as a visit with a purpose they can name.
- Group leaders: at 14 days, "Did you use it for a real session? If not, what stopped you?"

*Clarified 26 October 2026, before any session (section 11):* follow-ups stay at 7 and 14 days. No reply is
unknown use, not a return, and the denominator is never reduced after the answers are in (D4).

## 8. What the results decide

Agreed now, so the results are not read to fit a plan:
- **Task 2 fails**: change the answer's words before anything else. The headline-scope PR (option A
  or B) is the first candidate. Re-test that one task with three new people.
- **Task 3 fails**: the missing-information grouping on the spot page comes next.
- **Task 1 fails**: look at where people went instead of Plan a swim before changing the planner.
- **Task 4 fails**: fix the save and return route before any new feature.
- **Task 5 fails**: keep briefings done by hand for pilots (already the plan) and record what the
  leader expected to find.
- **Everything passes**: no redesign. Spend the time on pilots.
- A broad visual redesign happens only if a task fails for a reason a specific design change fixes.

*Clarified 26 October 2026, before any session (section 12):* the headline-scope wording (PR #284) has been
live since 20 October. If task 2 fails, a clearer explanatory-wording prototype informed by the observed errors
is evaluated, option A possibly first, with a focused retest before any wider promotion. No wording is rolled
out automatically (H4).

## 9. Order of work for the month

From the review's month plan, with the gate for each step:

| When | Work | Evidence it worked |
|---|---|---|
| Week 1 (from 26 Oct) | Recruit and run four swimmer sessions; merge the E. coli change if Ethan approves it | Participants can explain the answer and its limits |
| Week 2 | Two more swimmers; two group leaders; three prospective customers try the session workflow (`docs/PILOT-SESSIONS.md`, if merged) for a real planned activity | Each uses it for a real session |
| Weeks 3 and 4 | Deliver briefings by hand, keep issued copies, improve their locations; send the 7- and 14-day follow-ups | Recorded use, time saved, support time, willingness to pay |

The milestone the review proposes: one organisation using SwimSignal every week and paying to
continue.

## 10. Decisions for Ethan

1. **A thank-you for participants.** Recommended: a £10 voucher for swimmers, none for leaders
   (their session doubles as a buyer conversation). Money paid by SwimSignal may count as trading;
   check against the organiser plan's section 5 first.
2. **Which headline participants see.** Recommended: run the first four sessions on the live wording
   as it is, so the baseline is known, then the rest on the scoped headline if that PR is merged by
   then. Record which wording each participant saw.
3. **Who runs the sessions.** Ethan, since participants' words matter more than a script. A friend
   who has not seen the site can take notes.

*Clarified 26 October 2026, before any session (section 12):* item 2 is settled. Every participant sees
the live scoped wording; there is no headline comparison (H1). Each record holds the exact headline, URL
and "Issued" line (H3).

## 11. Clarifications, 26 October 2026, before any session

Added on 26 October 2026, before any session was arranged or run, so no result can have shaped them. The
text above is left as written; dated lines in sections 1, 3, 4, 6 and 7 point here. Ethan approved these
the same day ("okay i approve your recommendations"). The details, and how each is applied, are in
`docs/COMPREHENSION-TEST-2026-10-RUN-SHEET.md`, section 7.

- **D1.** No per-person overall score for tasks 1, 3, 4 and 5: direct measures only (completion, help,
  time, limits named, misunderstandings).
- **D2.** Task 3 counts any genuine limitation the chosen page explicitly displays, the lake's missing E.
  coli estimate included, written down before the session. Other valid limits are recorded separately and
  not counted. The rule for choosing the spot (section 3) is unchanged.
- **D3.** A usable task 5 briefing carries the place, the activity's date and time, dated forecast
  information and the limitations. A plain message or document is enough.
- **D4.** Repeat use passes at 3 of 8, or 4 of 9 or 10, confirmed purposeful returns, out of everyone who
  completed a session. No reply is unknown use. The denominator is never reduced after outcomes are known;
  follow-up consent and losses are reported.
- **D5.** Any one clear safety-guarantee or "water tested" reading leads to a wording fix and a focused
  retest before wider promotion. Routine bug fixes may continue.
- **D6.** Contact details are deleted when the last follow-up is answered, or 21 days after the session,
  whichever comes first. Follow-ups stay at 7 and 14 days (section 7).
- **D7.** Notes only by default. A recording only with separate agreement; checked against the notes and
  deleted within 7 days.
- **D8.** The privacy notice describes research sessions before anyone is recruited, matching what is
  done. Retention periods are approved practice, not legal deadlines. Coded records are treated as
  personal data for as long as they are kept. Only genuinely anonymised findings and quotes are published,
  checked for re-identification in the small sample; on withdrawal, anything published that could identify
  the participant is removed or corrected. Consent answers stay with the record while it is kept. SwimSignal is registered with the ICO and
  the fee paid (confirmed by the operator, 26 Oct 2026).

## 12. Clarification, 26 October 2026, before any session: the headline

Added on 26 October 2026, before any participant was recruited and before any session was arranged or run,
so no result can have shaped it. Approved the same day by Codex, under the delegation of routine decisions
Ethan gave on 26 October 2026 (`docs/AI-PROGRAMME-2026-10.md`, "Decisions, 26 October 2026"). The text
above, section 11 included, is left as written; dated lines in sections 8 and 10 point here. How it is
applied is in `docs/COMPREHENSION-TEST-2026-10-RUN-SHEET.md`, section 8.

Why: the scoped headline ("Low risk from sewage spills", PR #284, merged 20 October 2026) has been live since
then; on 26 October the Frensham Great Pond spot page showed it. So the "live wording" and the "scoped
headline" in section 10 item 2 are the same words, and the headline-scope PR named in section 8 is already
merged.

- **H1. One wording.** Every participant uses the current live scoped wording, as the site shows it on the
  day. The earlier bare "Low risk" headline is not restored, and the round makes no comparison between
  headlines, stated or implied.
- **H2. Scoring unchanged.** The tasks, the rubric (section 5) and every fail line (section 1), with D1 to D8,
  stay exactly as written.
- **H3. What each record holds.** For each page used: the exact headline as shown, the page's URL and its
  "Issued" line (the build's issue time).
- **H4. If task 2 fails.** Evaluate a prototype of clearer explanatory wording, informed by the errors
  observed. Option A ("Moderate predicted risk from monitored sewage overflows", `docs/DESIGN.md`) may be the
  first candidate. A focused retest comes before any wider promotion (D5); section 8's retest with three new
  people still applies. No wording is rolled out automatically.
