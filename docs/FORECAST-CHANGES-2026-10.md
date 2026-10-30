# Why a forecast changed: prototype (30 Oct 2026)

A prototype. It shows only with `?why=1` in the address, so the live pages are unchanged without it.
Code: `src/dipcast/site/since.js` (section "why it changed"). Tests: `tests/site_forecast_why.test.cjs`,
with two real issues of the live site in `tests/fixtures/forecast_why/`.

## The user task

"My saved spot changed level since I last looked. Did the water change, or did SwimSignal just learn
something new?"

## Success measure

1. Every explanation is built from inputs both forecasts recorded. A fact either forecast lacks is not
   said. Nothing says a fact caused the change.
2. On real issues, the share of level changes that get an explanation from recorded facts, rather than
   "not explained". Target for the prototype: most of them, with the rest said plainly as unexplained.
3. In a 5-minute check with a swimmer (below), they can say for each card whether the water may have
   changed or only SwimSignal's information did.

## What it does

"Since you last looked" already says when a saved spot's level moved: "Was high risk when you looked on
Thursday at 19:05; now moderate risk." The note it keeps in the browser now also keeps, for each of the
five days, the inputs behind the level: its level and what set it, the sewage spill risk (0 to 100, as the
day's sheet shows it), rain here in the 48 hours to midday, the overflows expected to spill, and the
share of rain data missing. It also keeps right now's level and risk, the overflows whose spills ended in
the last 48 hours, the latest sample and algae check, and the model stamp without its code part. These
notes are kept from now on whatever the address, so the explanation has something to compare when it is
switched on.

With `?why=1`, a line about the level gets a "Why:" sentence under it. Each fact is one of four kinds:

| Kind | What it covers | Example from the live site |
| --- | --- | --- |
| Reported | Overflows reported discharging or stopped; a new sample, algae check or rating; an official notice | "Overflows upstream reported discharging: 1 then, 0 now." |
| Forecast | The rain forecast here; the overflows expected to spill that day and the day before | "Overflows upstream expected to spill on Sunday, the day before: 2 then, 1.4 now." |
| Time | Right now falling as spill water moves on and dies off; a day turning into today | "Then this day was tomorrow; today's level also counts right now, from spills upstream." |
| Ours | A feed back or lost; rain data missing or filled in; a new spill model, calibration or E. coli model | "What SwimSignal knows changed, not necessarily the water: A feed upstream was down or late then; every feed is reporting now." |

Reported and forecast facts are grouped under "What changed". Time facts follow under "And time passed",
or "Time passed, with nothing new reported" when they are alone. Facts about SwimSignal's own information
say "not necessarily the water".

Where no fact moved enough, it says so. A move of 5 points or less that crosses a level line is called
small, with the line: "A small change: sewage spill risk 16 of 100 then, 14 now, and moderate risk starts
at 15." A larger one says "None of the inputs kept here moved enough to explain it." The level lines are
the model's own (`transport.SCORE_CUTS`); `tests/test_since.py` checks they agree.

The headline is the worst of right now, today and tomorrow, so it also moves when a day passes. That case
says so: "Then high risk was for Thursday, which has passed. That forecast already had today and tomorrow
at moderate risk."

When an outing is planned at the spot (Plan a swim) and only the outing's day moved, that day gets its own
line: "Sunday, the day of your outing, was low risk when you looked today at 09:05; now high risk."

## Run on real issues

The GitHub Pages artifacts hold 17 issues of the live site, 29 Oct 18:57 to 30 Oct 17:49 UTC (one more
could not be downloaded: HTTP 503). Each pair of successive issues was compared for all 109 spots and five days.

| | Spot-days |
| --- | --- |
| Level moved | 53 |
| Explained by recorded facts | 49 |
| Called small (5 points or less across a line) | 3 |
| Said to be unexplained | 1 |

Facts said: 45 time, 13 reported, 7 forecast, 0 ours. No feed, rain-data or model change happened in those
23 hours. Those kinds are tested on made-up spots only.

Most changes in those 23 hours were time, not new information. Right now fell as earlier spills' water was
modelled to pass, and at midnight 30 Oct became today, so right now started to count towards it.

The one unexplained case: Eden at Armathwaite, 3 November, low to moderate, sewage spill risk 12 to 18,
00:41 to 01:33 on 30 Oct. The spill forecast at the overflows depends on the rain at each overflow, which
the note does not keep (it keeps rain at the spot). Two days before the day may also matter, and the note
compares only the day and the day before.

## What it does not do

- It works only for saved spots, and only for someone who looked before. A note made before 30 Oct 2026 has
  no inputs, so its first change gets no "Why".
- It does not break the risk into the parts each input caused. The model has no such breakdown, so the
  sentence lists facts beside the change, never as its cause.
- The day's `risk_from_later_spills` is not used. It moves from "later" to "today and before" as days
  pass, so comparing it across two issue days would mislead.
- An outing day that moved gets its own line only when the headline did not move.
- Wording is fixed text. An LLM could later edit the wording, given the same facts and told to add none.

## Next steps

1. A "since the last update" line for every visitor: the build keeps the previous issue's inputs in its
   state folder and publishes the facts per spot. Then the line works without saved spots or past notes.
2. Keep the rain at the overflows (the spill model's own input) in the note, which would explain the
   Armathwaite kind of case.

## 5-minute check with a swimmer

Open the Saved page with `?why=1` on a phone with three saved spots and seeded notes (the fixtures here
seed Avon at Warleigh Weir, Medway at Tonbridge and Dart at Dartington). For each card ask:

1. "Has the water at this spot changed since Thursday, or has SwimSignal's information changed?"
2. "Which part of this card is something someone measured, and which is an estimate?"

Pass: they answer both correctly for at least two of the three cards without help. Note any word they
stop at.
