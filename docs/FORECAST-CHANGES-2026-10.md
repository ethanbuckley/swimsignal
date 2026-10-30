# What changed in a forecast's inputs: prototype (30 Oct 2026)

A prototype. It shows only with `?why=1` in the address, so the live pages are unchanged without it.
Code: `src/dipcast/site/since.js` (section "what changed in the inputs"). Tests:
`tests/site_forecast_why.test.cjs`, with two real issues of the live site in `tests/fixtures/forecast_why/`.

Revised 30 Oct 2026 after review: the sentence is labelled "What changed in the inputs", not "Why". The
model has no breakdown of a level by input, so these facts sit beside the change. They do not prove what
caused it.

## The user task

"My saved spot changed level since I last looked. Did the water change, or did SwimSignal just learn
something new?"

## Success measure

1. Every fact said is one both forecasts recorded. A fact either forecast lacks is not said. Nothing says a
   fact caused the change.
2. Coverage: the share of level changes where at least one recorded input changed beside them. Cases with
   none are said plainly.
3. In a 5-minute check with a swimmer (below), they can say for each card whether the water may have
   changed or only SwimSignal's information did.

Measure 2 is coverage, not accuracy. Whether the listed inputs are the ones that moved the level is not
tested here, and the model cannot say.

## What it does

"Since you last looked" already says when a saved spot's level moved: "Was high risk when you looked on
Thursday at 19:05; now moderate risk." The note it keeps in the browser now also keeps, for each of the
five days:

- the day's level and what set it;
- the sewage spill risk, 0 to 100, as the day's sheet shows it;
- the rain here in the 48 hours to midday;
- the overflows expected to spill;
- the share of the model's weight here whose rain data was missing.

It also keeps right now's level and risk, the overflows whose spills ended in the last 48 hours, the latest
sample and algae check, and the model stamp without its code part. These notes are kept from now on
whatever the address, so there is something to compare when the sentence is switched on.

With `?why=1`, a line about the level gets a sentence under it, "What changed in the inputs: ...". Each fact
is one of four kinds:

| Kind | What it covers | Example from the live site |
| --- | --- | --- |
| Reported | Overflows reported discharging or stopped; a new sample, algae check or rating; an official notice | "Overflows upstream reported discharging: 1 then, 0 now." |
| Forecast | The rain forecast here; the overflows expected to spill that day and the day before | "Overflows upstream expected to spill on Sunday, the day before: 2 then, 1.4 now." |
| Time | Right now, as modelled from spills upstream; a day turning into today | "Then this day was tomorrow; today's level also counts right now, from spills upstream." |
| SwimSignal's information | A feed back or lost; rain data missing or filled in; a new spill model, calibration or E. coli model | "In what SwimSignal knows, not necessarily the water: A feed upstream was down or late then; every feed is reporting now." |

Where no kept input changed by enough to show, it says so. A move of 5 points or less across a level line is
called small, with the line: "A small change: sewage spill risk 16 of 100 then, 14 now, and moderate risk
starts at 15." A larger one says "No other input kept here changed by enough to show." The level lines are
the model's own (`transport.SCORE_CUTS`); `tests/test_since.py` checks they agree.

The headline is the worst of right now, today and tomorrow, so it also moves when a day passes. That case
says so: "Then high risk was for Thursday, which has passed. That forecast already had today and tomorrow
at moderate risk."

When an outing is planned at the spot (Plan a swim) and only the outing's day moved, that day gets its own
line: "Sunday, the day of your outing, was low risk when you looked today at 09:05; now high risk."

## Replay on real issues

The GitHub Pages artifacts held 17 issues of the live site, from 29 Oct 18:57 to 30 Oct 17:49 UTC (one more
could not be downloaded: HTTP 503). Each issue was compared with the next, for all 109 spots and five days:
16 pairs over about 23 hours.

| | Spot-days |
| --- | --- |
| Level moved | 53 |
| At least one kept input changed beside it | 49 |
| Called small (5 points or less across a line) | 3 |
| No kept input changed by enough to show | 1 |

Facts said: 45 time, 13 reported, 7 forecast, 0 SwimSignal's information.

What this replay does and does not establish:

- It shows the sentence can be built for most changes in one short, quiet stretch. It does not show the
  facts are the right ones; nothing here tests that.
- No feed outage, rain-data gap or model change happened in those 23 hours. Those kinds are tested on
  made-up spots only.
- Time facts were the most common: right now's modelled risk changed, or a day became today. Both follow
  from the model's rules, with nothing new reported.

The case with no kept input: Eden at Armathwaite, 3 November, low to moderate risk, sewage spill risk 12 to
18, between the 00:41 and 01:33 issues on 30 Oct. The note keeps rain at the spot, not at each overflow, and
compares only the day and the day before. Either may be why nothing showed. That is not checked.

## What it does not do

- It works only for saved spots, and only for someone who looked before. A note made before 30 Oct 2026 has
  no inputs, so its first change gets no sentence.
- It does not split the risk into parts caused by each input; the model has no such breakdown.
- The day's `risk_from_later_spills` is not used. It moves from "later" to "today and before" as days pass,
  so comparing it across two issue days would mislead.
- An outing day that moved gets its own line only when the headline did not move.
- Wording is fixed text. An LLM could later edit the wording, given the same facts and told to add none.

## Next steps

1. A "since the last update" line for every visitor: the build keeps the previous issue's inputs in its
   state folder and publishes the facts per spot. Then it works without saved spots or past notes.
2. Keep the rain at the overflows (the spill model's own input) in the note.
3. Before relying on the sentences, test them: over a longer replay, check how often the inputs listed are
   ones whose change moves the model's risk in the same direction when the model is rerun with only that
   input changed.

## 5-minute check with a swimmer

Open the Saved page with `?why=1` on a phone with three saved spots and seeded notes (the fixtures here
seed Avon at Warleigh Weir, Medway at Tonbridge and Dart at Dartington). For each card ask:

1. "Has the water at this spot changed since Thursday, or has SwimSignal's information changed?"
2. "Which part of this card is something someone measured, and which is an estimate?"

Pass: they answer both correctly for at least two of the three cards without help. Note any word they
stop at.
