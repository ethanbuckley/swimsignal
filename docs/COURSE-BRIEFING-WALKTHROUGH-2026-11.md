# Course briefing walkthrough: one sheet

For Ethan, with one organiser at a time. About 20 minutes. It is a sheet to use, not a feature. Background:
`docs/COURSE-BRIEFING-HENLEY-2026-11.md`. The interview rules in `docs/ORGANISER-INTERVIEWS-2026-11.md` §3 still
apply: their routine first, no price unless they ask, notes in their words, nothing quoted without asking.

**Pass test.** Across three walkthroughs, at least two organisers name a checkpoint they would add, an extra check
they would make, or a change they would communicate. Count a change only when they can tie it to information the
course view could have shown by the stated decision time. "Interesting" and changes that depend on later records
do not count. This is a test of usefulness, not of forecast skill or readiness to run the service live.

## Before

1. Serve the repository root: `python3 -m http.server 8793`
2. Open `http://localhost:8793/prototypes/course-briefing/henley-classic/#mode=walkthrough`. For each date the page
   shows only the archived pin first. Use **Show the course evidence** after recording the first answer.
3. Say three things: "This is a prototype. Nobody has published it." "These are three past dates, not today."
   "It is a forecast and a map of evidence, not a water test. You decide."
4. You should see the heading "organiser walkthrough", three date buttons and the pin's forecast. If you see a map,
   you are on the full briefing: add `#mode=walkthrough`.

Keep the full briefing closed until the end. Its opening and map give away where the evidence changes. Changing
the date in the walkthrough goes back to the pin for that date.

## For each date

Do them in this order: C, A, then B. C is the one same-time case with something to see. A is the quiet day. B is
history. Read step 1 aloud, then wait.

| | 1. What SwimSignal showed at the pin | 2. Select in the walkthrough | 3. What the reveal shows, as received by the decision time |
|---|---|---|---|
| **C. Saturday 14 November 2026, 07:30** | Low risk. Index 3 of 100. 48 of 49 overflows reporting, none spilling. Issued 07:18. | **Saturday 14 November 2026** | 49 of 50 gave a status at the 07:13 poll. The silent one is Friday Street pumping station, 300 m above the finish, with the largest weight. Its last status arrived at 04:12 the day before. Its 4-minute spill that night was received by 04:12. Henley works: not spilling. All of this was received before 07:30. |
| **A. Sunday 1 November 2026, 08:40** | Low risk. Index 1 of 100. All 49 reporting, none spilling. Issued 08:32. | **Sunday 1 November 2026** | Nothing received differs along the course. 50 of 50 gave a status at 08:29. The map still shows where the works' stream joins. Say so: a quiet day is a true picture. |
| **B. Saturday 6 July 2024, 13:00** | SwimSignal issued nothing in 2024. Ask what they used that day, if anything. | **Saturday 6 July 2024** | A historical view, labelled as one. Later records show Henley works spilling 11:45 to 12:45, upstream of the first 350 m only. Nobody could have read them that day. Outside the pass count. |

After step 1, ask: **"With only that, what would you have checked, decided or told people?"** Write the answer
down before you press the button.

The reveal answers three questions in order: where the evidence changes, what could be checked there, and what
is still unknown. Each line starts with its kind: Observation, Modelled connection, Inferred, Later record or
Unknown. After it, ask, in this order:

1. "Does this change anything you would have done? What?"
2. "Is there a point on the course where you would add a check? Where, and what check?"
3. "Would you tell anyone something different: swimmers, safety crew, the landowner?"
4. "Which line made the difference?" Note its kind.
5. "What here do you not believe, or not need?"

**What counts.** A change counts when the line they point to is an Observation on date A or C, or a Modelled
connection or Inferred line, which hold on any date. A change that rests on a Later record does not count, and
nothing on date B counts. Leave the "Later records" fold closed until they have answered. If they open it, note
what they used from it as feedback.

Be ready for this on date C: the evidence there is the same along the whole course. Friday Street is above the
finish, so it is upstream of every section. The course view adds which monitor was silent and where it is. It does
not show one end differing from the other. Only date B does that, and B is history.

## Record, the same day

One row a date, in `swimsignal-private/interviews/`. No names in this repository.

| Date shown | Would do with the pin alone | Change after the reveal (their words) | Line they used, and its kind | Available by decision time? | Counts towards pass? |
|---|---|---|---|---|---|
| C | | | | | |
| A | | | | | |
| B | | | | No | No |

Then three lines: what they doubted, what they asked for that is not there, and whether this walkthrough counts
towards the pass test (yes or no, and which of the three things they named).

## If they ask

- **"Is the water at the start worse?"** Not known. The page counts which overflows are upstream. It measures
  nothing, and gives no E. coli figure on a river this size.
- **"Why is the middle section unresolved?"** The map shows ditches that may link the works' stream to a second
  mouth. Nobody has checked on the ground.
- **"How do you know what you had at 07:30?"** The archive keeps the time of every poll, and for each overflow
  the half hours in which a status arrived. A spill counts only if its record was last seen before 07:30.
- **"Why is 2024 different?"** SwimSignal kept no archive then. Those spill times were published after the year.
- **"Can I have this for my event?"** It is a prototype for one course. Note the request and the event. Promise
  nothing.
