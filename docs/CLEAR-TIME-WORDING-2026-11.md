# "When will it clear?": wording prototypes for the conditional clearing time

Written 30 October 2026. A prototype for a person to test, not a change to the site. Nothing here is built.

## What the page says now

The time comes from `transport.clear_time`: the live risk run forward as if every overflow discharging now stopped
now and no new spill started. Two places say it.

- **Right now tile and alerts** (`levels.js`, `clearWords`): "If the overflow discharging upstream stops now, its
  spill should have passed and died off by Saturday 22:47."
- **Where the risk comes from** (`index.html`, `clearSentence`): "If the overflow discharging upstream stops now, the
  model expects low risk from spills by about Saturday evening."

The sentences are accurate. The concern is how they are read.

## Why it may mislead

- **A clock time to the minute reads as a prediction.** "Saturday 22:47" is precise. The condition before it ("if
  ... stops now") is the part a quick reader skips.
- **The condition is usually not met.** In 2024, at a typical hour a spill was running, it was still running 6 hours
  later 61% of the time (`docs/SPILL-DURATION-TEST-2026-11.md`, "Seen before writing"; 2024 only, a description).
  So the time shown is the earliest the risk could clear, and the real time is usually later.
- **What the page does not know:** when the spill will stop. The duration test (same file) found a model can rank
  this better than a lookup table, but its chances are not reliable enough to show.

Not checked: how people actually read the current sentence. That is what the test below is for.

## Three variants

Each keeps the same number from `clear_time`. None needs new data or a new model.

**A. Current** (the control). As above.

**B. Lead with the condition, drop the minute.**
> The overflow upstream is still discharging. If it stopped now, low risk from spills would come back by about
> Saturday evening. It may run for hours yet, and the time moves later for as long as it does.

**C. Hours after it stops, no clock time.**
> The overflow upstream is still discharging. Low risk from spills comes back about 9 hours after it stops.

The 9 is `clears_at` minus the build's issue time, rounded to the hour. The page has the issue time as
`DATA.generated_at`; `clear_time` runs from the forecast's own `now`, set a few minutes earlier in the same build, so
the two differ by minutes. A spot-level issue time in spots.json would make it exact. The time a running
spill holds the risk up after it stops (travel plus die-off) is what the model knows. When the spill stops is what
it does not know, so C does not give a time for it.

**D. C plus a dated description** (only if C alone is misread as "9 hours from now").
> The overflow upstream is still discharging. Low risk from spills comes back about 9 hours after it stops.
> Spills already running are often still running 6 hours later (2024-25 records).

D's second sentence is a description of past records, not a forecast for this spill. It needs the 2024-25 share
by elapsed time, computed once and dated. Not computed for this note.

Where nothing upstream is discharging (spills finished, water still passing), the condition is already true and the
present sentence ("The spill upstream should have passed and died off by …") can stay, though the minute could
still become a part of the day.

## How to test it

Inside the comprehension sessions (`docs/COMPREHENSION-TEST-2026-10.md`). Their protocol is fixed and this pack
does not change it. This is a **proposed amendment for Ethan's decision**, to add after task 3, on a spot whose
upstream overflow is discharging (a printed or static page if none is live on the day):

**Task 3b.** Show one variant (rotate A, B, C across participants; D only if C fails). Ask:
1. "Will the water here be back to low risk by [the time or day shown]?" Correct: "only if the spill stops now", or
   "maybe, it depends when the spill stops". Wrong: "yes".
2. "Has the overflow stopped?" Correct: "no".
3. For C and D only: "When will it be low risk again?" Correct: any answer tied to the spill stopping. Wrong: "in
   about 9 hours" from now.

**Fail line, set now:** a variant fails if 2 or more of the people shown it answer question 1 "yes" without any
condition, or answer question 3 with a time from now. With 8 to 10 people and three variants, each variant is
seen by about three, so this gives direction, not proof (the plan's own caveat).

**What results decide.** If A fails and B or C passes, the passing wording is built in one PR for both places
(`clearWords`, `clearSentence`), with the alert text (`scripts/alerts.js`, `clears`) changed to match. If every
variant fails, the clearing time is taken off the Right now tile and kept only in "Where the risk comes from".

## Open questions for Ethan

- Add task 3b to the sessions, or test it separately?
- If C wins, should alerts keep a clock time? An alert is read later than it is sent, which favours "hours after it
  stops" even more.
