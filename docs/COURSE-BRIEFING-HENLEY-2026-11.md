# A course briefing for the Henley Classic: route facts and prototype, November 2026

Written 17 November 2026. The site treats Henley as one pin near the bridge. This is a first try at evidence for a
stretch of river: one real course, cut into sections where the water-quality evidence changes.

Marks: **[checked]** I opened the source on 17 Nov 2026. **[repo]** read from this repository or its state
release on 17 Nov 2026. **[inferred]** my reasoning, not a fact.

Nothing here is published. The page is a prototype in `prototypes/course-briefing/`, which the site build does
not copy. Nobody at Henley Swim, Thames Water or anywhere else has been contacted. No organiser has seen it.

## The answer

The evidence changes once, near the start. The storm overflow at Henley sewage works (`TWL00222`) reaches the
Thames in the first 350 m of the swim. Whether it also reaches the next 510 m is unresolved. The last 1.25 km to
the finish is above it. The same 50 monitored overflows are upstream of every section.

The lead held. `TWL00222` is not counted at the `thames-henley` pin, and its water does join the Thames on the
course. It joins close to the start, not halfway.

## 1. The course

**Established**

- The organiser's page says "2.1km upstream", "The Henley Classic starts with a short walk to the official regatta
  start", and "a unique, straight line, point-to point-swim (ie no turns)". Next held Sunday 27 June 2027, 4am. It
  gives no coordinates [checked: henleyswim.com/henley-classic].
- Henley Royal Regatta says its Straight Course "runs straight from below the Berkshire side of Temple Island" to
  "finish at Poplar Point", 1 mile 550 yards, which is 2,112 m [checked: hrr.co.uk/about/regatta-course].
- OS OpenMap Local (October 2026 release) draws Temple Island as an island 204 m long. Its downstream tip is at
  easting 477140, northing 184915. Historic England's list puts the Temple (entry 1319072) at 477097, 184748, near
  the island's upstream end [checked: both, open licence].
- Henley Bridge is list entries 1369131 and 1117419, at about 476358, 182643 [checked].

**Inferred**

- The start is the island's downstream tip, moved onto the OS Open Rivers line. That is my reading of "below the
  Berkshire side of Temple Island". I did not find the start pontoons on any open map. I put it at about 60 m
  either way.
- The finish is 2,112 m upstream of that along the OS Open Rivers line, at 476377, 182953. That is 311 m
  downstream of the bridge. No open dataset I used places Poplar Point. I put it at about 100 m either way.
- The route tool measures 2.11 km between the two ends, which is the check that they agree with each other. It is
  not a check that they are right.

One correction to my own first reading: Wikipedia's regatta article says both "the downstream end" and "the upstream
end" of the island for the start. I used the regatta's own page, not that article.

## 2. The overflows

All from `transport.upstream_overflows`, the site build's own trace, on the overflow table built in scratch from
the state release of 17 Nov 2026 [repo].

**Established**

- 50 monitored storm overflows are within 60 km upstream of the finish. All are Thames Water's.
- None sits on the Thames between the finish and the start.
- The nearest is Friday Street (Henley) pumping station (`TWL00191`), 0.3 km above the finish and 35 m above the
  `thames-henley` pin. Its model weight at the finish is 99%, the largest of the 50. So it is upstream of the whole
  course. Its monitor has been offline since 13 November 2026 [repo: `live_history.parquet`].
- At the start the count is 48: 47 of the 50, plus Henley sewage works. Three of the 50 are past the forecast's
  60 km limit once the point moves 2.1 km down.
- Henley sewage works (`TWL00222`): Thames Water gives its receiving water as "Fawley Court Stream". The site's
  network places the outfall 25 m from an unnamed OS Open Rivers stream, which meets the Thames at 477028, 184587.
  That is 0.35 km upstream of the start. The route tool lists it as a side-stream overflow joining there.
- No row for it exists in `data/raw/overflow_joins.csv`, and none was needed. I added none.
- OS OpenMap Local draws that stream's lower end as open water joined to the river, with four mouths: 0.35 km,
  0.24 km and 0.13 km upstream of the start, and one 0.11 km below it. The joins have gaps of 3 m or less on the map.
- Its annual returns: 9 spills in 2021, 0 in 2022, 1 in 2023, 86 in 2024 (950 hours), 0 in 2025. Its last recorded
  spill began on 26 September 2024 [repo: `annual_returns.parquet`, EA start and stop files, the live feed].
- Its model weight at the start is 7%.

**Inferred, or unresolved**

- **Unresolved: 0.35 to 0.86 km from the start.** The same map shows ditches between the stream's channels and
  the Fawley Court canal, which meets the river 0.86 km from the start. They join only across gaps of up to 10 m. I
  cannot tell whether water crosses those gaps, or which way it runs. The page marks this section "unresolved" and
  counts it as neither above nor below the works.
- Between OS OpenMap Local's last drawn water by the works and the meadow channels there is a gap that OS Open
  Rivers bridges with one line. I take that as a culvert or a narrow ditch [inferred].
- Why the works spilled 86 times in 2024 and not once in 2025 is not known. I did not look for a cause.
- A 7% weight assumes the stream's water is mixed across the Thames. The mouths are all on the Buckinghamshire
  bank. How far the water spreads before the start line is not known, and nothing here measures it.
- Where the works' treated effluent enters was not checked. The Environment Agency's consents register would say,
  but its licence does not allow publishing from it.

## 3. What can be observed, by section

| Observation | Section 1, start to 0.35 km | Section 2, to 0.86 km | Section 3, to the finish |
|---|---|---|---|
| Live status, Thames Water's feed | The 50 and Henley works | The 50; the works unresolved | The 50 |
| EA start and stop files, 2024 and 2025 | Same overflows, after the year ends | Same | Same |
| EA laboratory samples | None | None | None |
| River level | Hambleden Lock, below the start | Same gauge | Same gauge |
| Issued forecast | None | None | None: the pin is 226 m above the finish |

The nearest designated bathing waters upstream are Pangbourne Meadow (25.8 km above the finish by river,
designated 2026) and Wallingford Beach (42.4 km, designated 2024) [repo: route tool]. The build's polls of Thames
Water's feed in the 30 days to 17 November: 304 polls, half the gaps under 1.1 hours, 38 gaps over 6 hours, the
longest 15.6 hours [repo: `poll_log.parquet`].

## 4. The three dates

| Date | Why | Issued at the pin | What the course view adds |
|---|---|---|---|
| Sun 1 Nov 2026, 08:40 | Routine | Low, index 1, 49 of 49 reporting (`4deeedd-20261101T0832Z`) | Nothing changes along the course. Henley works reporting, not spilling |
| Sat 6 Jul 2024, 13:00 | The evidence differs | Nothing: the log starts 12 Sep 2026 | Henley works recorded spilling 11:45 to 12:45, upstream of section 1 only. 14 other spills far upstream |
| Sat 14 Nov 2026, 07:30 | A feed gap | Low, index 3, 48 of 49 reporting (`6743baf-20261114T0718Z`) | The one missing is Friday Street, 0.3 km above the finish, weight 99%. It spilled for 4 minutes at 02:50 the day before, then gave no reading at any of 6 polls |

Only the "issued" column is as issued, from the kept page records. Everything else on the page is laid out now
from records and is labelled "Reconstruction". For 6 July 2024 that means the Environment Agency's files, which
were published after the year ended. Nobody could have read them on the day.

The page also gives, in a fold, the exposure index rebuilt from recorded spills at each end. It is the site's
`combine_daily` with spill days in place of spill chances. It reads 0 and 6 on 6 July 2024, and 1 and 12 on 14
November 2026. The second pair is the daily model moving part of one spill onto the next day at the start. It is
not a second source, and the fold says so.

Two dates I looked at and did not use. Monday 26 October 2026: Thames Water's feed gave a status for only 167 of
573 overflows at one poll. It is a clearer company-wide gap, but it says less about this course. Sunday 12 May
2024: Henley works spilled for 16 hours until 02:00, during weeks of daily spills. It is closer to a dawn swim but
harder to read, because much else was spilling.

## 5. What was reused, and what is new

- The route, and each overflow on it, beside it or above it: `stretches.route` and a new `stretches.between`, which
  is the outing planner's grouping moved into one function. `stretches.stretches` now calls it. Its tests pass
  unchanged.
- Upstream overflows, travel times and weights: `transport.upstream_overflows`, called as the build calls it.
- The exposure index: `transport.combine_daily`. A recorded spill's days: `forecast_log.observed_spill_days`.
- The limits and "who decides" wording: `briefing.LIMITS` and `briefing.DECIDES`, word for word. A test fails if
  they drift.
- Overflow names and the weight's definition: `levels.js` (`plainName`, `WEIGHT_SAID`).
- New: `scripts/course_briefing.py`, the page (`prototypes/course-briefing/`), and the rule that cuts a course into
  sections (`sections`). The rule: an overflow counts for the stretch from the start up to the furthest join the
  network or a mapped mouth gives. A "possible" mouth beyond that makes the stretch between unresolved.

## 6. Design choices

Checked against `docs/DESIGN.md`.

| Choice | Status |
|---|---|
| A prose page on `page.css`, numbered h2 steps, the drawn part under a hairline | Already decided: "The organisers' worked example" |
| The issued level in its text colour with a 4 px rule, never a filled surface | Already decided: "Organisers, signs and the live sign"; Rules for changes, 5 |
| Plain overflow names with the company's name beside them, weight as a percentage with its definition | Already decided: "Words", overflow names and weight |
| "Missing data never means low risk" beside every monitor with no reading | Already decided: the briefing's limits |
| The course drawing as a square-cornered figure in an ink hairline, caption opening with its name | Already decided for a spot's Upstream map: "The Research Lab" |
| Detail under "The figures behind it" | Already decided: "An exhibit's opening" |
| Distances along the water in km | Already decided: "Units" |
| Sections in the order a swimmer meets them, each with a rule at its left: heavy, dashed or hairline | New |
| "Reconstruction" as a label with a rule at its left, on everything not issued | New. It follows the planner's value tags |
| No level and no E. coli figure for a section | New, and deliberate: `docs/PLACE-LEVEL-READ-0-2026-11.md` |
| The caveat reads "A forecast and an evidence map, not a water test. The organiser decides." | New wording. It adds to the kept caveat and does not replace it |

Nothing reverses a recorded decision.

## 7. How to open it and remake it

1. From the repository root: `python3 -m http.server 8793`
2. Open `http://localhost:8793/prototypes/course-briefing/henley-classic/`. You should see the course drawing and
   three date buttons. A date is kept after the `#`, as `#date=gap`.

The likeliest mistake is serving the `site/` folder, as the usual preview does. The page then loads without its
stylesheet, because it reads `src/dipcast/pages/page.css` from the repository.

To remake `course.json`, set scratch `DIPCAST_ROOT` and `DIPCAST_STATE` first, with the state release downloaded
into the state folder. The script refuses a state folder inside a checkout, because it writes the overflow table
there. The command is at the top of `scripts/course_briefing.py`. Without `--openmap` it keeps the drawing already
in the file.

## 8. Limits

- One course. The section rule has been tried on one stream.
- The join positions come from two OS maps, not from a visit. Nobody has walked the bank.
- The 2024 date uses records nobody had on the day.
- The counts are from the overflow table of 17 November 2026. The pin's issued records that month count 49.
- The page says nothing about the event's own safety plan, which I have not seen.

## 9. What waits on Ethan

- **Publishing.** The page is outside the site build. Publishing it, or linking it, is his call.
- **Contacting Henley Swim.** Nothing has been sent. The outreach rules in `docs/ORGANISER-PIVOT-2026-10.md` §5
  item 10 apply.
- **The three walkthroughs**, with the sheet in `docs/COURSE-BRIEFING-WALKTHROUGH-2026-11.md`. The pass test is
  his: at least two of three organisers name a checkpoint they would add, an extra check, or a change they would
  communicate.
- **The unresolved section.** A walk along the Fawley bank, or a question to Thames Water, would settle it.
  Either is an outside step.
- **Whether to add a join row** for `TWL00222`. Not needed for the forecast today, since the network already
  places it.
