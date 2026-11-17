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

## 4. The replay: what was known at the decision time

Added 18 November 2026, for the second version. The page now compares two things at one decision time: the pin's
forecast exactly as issued, and the course's monitors as SwimSignal had received them by then.

### What the archive records about receipt

**Established** [repo: the state release of 17 Nov 2026, `ingest/live.py`]

- `poll_log.parquet` keeps the time of every poll of each company's feed, from 16 September 2026.
- `live_coverage.parquet` keeps, for each overflow and UK day, the half-hour slots in which a poll received a
  known status (spilling or not). So for any poll, the archive says whether a status arrived for each overflow.
- `live_history.parquet` keeps one row for each state of each overflow, with the spill's own start and stop and
  `fetched_at`. That is the **last** poll that saw the state, not the first.
- `issued-YYYY-MM.parquet` keeps each page record as issued, from 31 October 2026. It holds counts (48 of 49
  reporting), not which overflow was missing.
- `forecast_overflows` logs each overflow at each issue, but its `status_known` column is false for all 50 at
  every issue I read, so it says nothing here.

**What follows from that**

- A status at a poll is provable to the half hour. If a later poll falls in the same half hour as the cutoff, the
  replay treats the status as not received.
- A spill is provably received only when its row was last seen at or before the cutoff. A spill last seen later
  may have been received in time, but the archive cannot show it. The replay leaves it out and counts it.
- An overflow with no status at the last poll is "unknown", with the time a status last arrived. It is never
  "not spilling".

- Where a status did arrive at the last poll, its value needs the same proof. "Spilling" needs a row that
  covers the poll and was last seen by the cutoff. "Not spilling" needs no row at all that covers the poll. If the
  only covering row was last seen after the cutoff, the state is "unproven": a status arrived, but the archive
  cannot show what it was. The page puts that under Unknown.

These rules are `replay_at` in `scripts/course_briefing.py`. Five tests hold them: a poll or a spill row after
the cutoff cannot enter; a later poll in the same half hour lends nothing; a monitor with no status stays unknown;
a row last seen after the cutoff cannot make a site "spilling" or "not spilling"; and the state and the list of
spills never disagree about one spill.

**A fault found in review, 18 November 2026.** In the first cut (`d01180f7`) the state at the last poll read
"spilling" from any row whose own start was before the poll, even one last seen after the cutoff. A feed can
backdate a start, so a later record could have set the state. The rule above replaced it. I then compared both
committed replays under the old and the new rule: **no site changes state.** On 14 November, 49 of 50 are "not
spilling", Friday Street is "unknown" and Henley works is "not spilling", as before. On 1 November all 50 and
Henley works are "not spilling", as before. No row covers either last poll, so nothing was ever in doubt there.

### The three dates

| Date and decision time | Kind | The pin, as issued | The course, as received by then |
|---|---|---|---|
| Sat 14 Nov 2026, 07:30 | Same time | Low, index 3, 48 of 49 reporting (`6743baf-20261114T0718Z`) | 49 of 50 gave a status at the 07:13 poll. The one that did not is Friday Street, 0.3 km above the finish, weight 99%. Its last status arrived at 04:12 on 13 Nov, 13 polls earlier. Its 4-minute spill at 02:50 on 13 Nov was received by 04:12 that day. Henley works: not spilling at 07:13 |
| Sun 1 Nov 2026, 08:40 | Same time | Low, index 1, 49 of 49 reporting (`4deeedd-20261101T0832Z`) | 50 of 50 gave a status at the 08:29 poll, none spilling. Henley works: not spilling. Nothing received differs along the course |
| Sat 6 Jul 2024, 13:00 | Historical only | Nothing: the log starts 12 Sep 2026 | Not available. Later records show Henley works spilling 11:45 to 12:45, upstream of section 1 only |

The pin counts 49 and the course 50 because the overflow table has changed since. Both agree that one monitor was
missing on 14 November.

### Does the archive support a fair comparison?

**Partly.** It supports a same-time comparison of the pin against the whole course on 14 November 2026. Every
line in it has receipt evidence from before 07:30. What the course view adds there is which monitor was silent,
where it is, how much it weighs, and that it had spilled the night before.

It does **not** support a same-time case where the evidence differs along the course. Henley works' last
recorded spill began on 26 September 2024, and SwimSignal's polls start in September 2026. On every archived day
its status is "not spilling". The only along-course difference is the July 2024 one, which rests on Environment
Agency files published after the year ended. The page labels that date "Historical view" and the interview guide
keeps it out of the pass count.

**The exact records that would close the gap:**

1. A spill, or a spell with no status, at `TWL00222`, polled by SwimSignal: a `poll_log` row for each poll, the
   `live_coverage` slots for `TWL00222` on that day, and a `live_history` row for the event.
2. The page record issued for `thames-henley` at or just before the chosen decision time.
3. Better still, a first-received time for each state. `live_history` keeps the last. One more column,
   `first_fetched_at`, would make every spill's receipt provable. That is a change to the live poller, so I did not
   make it.

Until the works spills again, or reports nothing, no archived day can show a same-time difference along this
course. That is a fact about the river and the records, not about the tool.

### Later records

Each date also keeps the earlier whole-day view in a fold, labelled "Later records, not available at" the
decision time: the Environment Agency's files for 2024, full-day poll counts, and the exposure index rebuilt from
recorded spills (0 and 6 on 6 July 2024; 1 and 12 on 14 November 2026, where the second figure is the daily model
moving part of one spill onto the next day).

Two dates I looked at and did not use. Monday 26 October 2026: Thames Water's feed gave a status for only 167 of
573 overflows at one poll. Sunday 12 May 2024: Henley works spilled for 16 hours until 02:00, during weeks of
daily spills.

## 5. What was reused, and what is new

- The route, and each overflow on it, beside it or above it: `stretches.route` and a new `stretches.between`, which
  is the outing planner's grouping moved into one function. `stretches.stretches` now calls it. Its tests pass
  unchanged.
- Upstream overflows, travel times and weights: `transport.upstream_overflows`, called as the build calls it.
- The exposure index: `transport.combine_daily`. A recorded spill's days: `forecast_log.observed_spill_days`.
- The limits and "who decides" wording: `briefing.LIMITS` and `briefing.DECIDES`, word for word. A test fails if
  they drift.
- Overflow names and the weight's definition: `levels.js` (`plainName`, `WEIGHT_SAID`).
- A poll's day and half-hour slot: counted as `ingest.live.coverage_rows` counts them.
- The walkthrough's pin-first order, its reveal and its date buttons are Codex's local changes of 17 November,
  carried over unchanged in behaviour. The reveal's content is new.
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
| Each line of the reveal opens with its kind in words: Observation, Modelled connection, Inferred, Later record, Unknown | New. No colour or pill carries it |
| The reveal is three questions as h3 headings, the map after them | New: the answers come before the drawing on a phone |
| Later records under a fold named for what it holds | Already decided: "A row says one sentence and folds the rest" |
| No level and no E. coli figure for a section | New, and deliberate: `docs/PLACE-LEVEL-READ-0-2026-11.md` |
| The caveat reads "A forecast and an evidence map, not a water test. The organiser decides." | New wording. It adds to the kept caveat and does not replace it |

Nothing reverses a recorded decision.

## 7. How to open it and remake it

1. From the repository root: `python3 -m http.server 8793`
2. Open `http://localhost:8793/prototypes/course-briefing/henley-classic/`. You should see the course drawing and
   three date buttons. A date is kept after the `#`, as `#date=gap`.
3. For the walkthrough, add `#mode=walkthrough`. You should see the pin's forecast only, and a button, "Show the
   course evidence".

The likeliest mistake is serving the `site/` folder, as the usual preview does. The page then loads without its
stylesheet, because it reads `src/dipcast/pages/page.css` from the repository.

To remake `course.json`, set scratch `DIPCAST_ROOT` and `DIPCAST_STATE` first, with the state release downloaded
into the state folder. The script refuses a state folder inside a checkout, because it writes the overflow table
there. The command is at the top of `scripts/course_briefing.py`. Without `--openmap` it keeps the drawing already
in the file.

## 8. Limits

- One course. The section rule has been tried on one stream.
- The join positions come from two OS maps, not from a visit. Nobody has walked the bank.
- The 2024 date uses records nobody had on the day. It is a historical view only.
- Receipt is proved to the half hour for a status, and by a spill's last-seen time. A spill received in time but
  seen again later is left out.
- No archived day shows a same-time difference along the course (section 4).
- The counts are from the overflow table of 17 November 2026. The pin's issued records that month count 49.
- The page says nothing about the event's own safety plan, which I have not seen.

## 9. What waits on Ethan

- **Publishing.** The page is outside the site build. Publishing it, or linking it, is his call.
- **Contacting Henley Swim.** Nothing has been sent. The outreach rules in `docs/ORGANISER-PIVOT-2026-10.md` §5
  item 10 apply.
- **Whether to keep a first-received time** in the live poller (section 4, record 3).
- **The three walkthroughs**, with the sheet in `docs/COURSE-BRIEFING-WALKTHROUGH-2026-11.md`. The pass test is
  his: at least two of three organisers name a checkpoint they would add, an extra check, or a change they would
  communicate.
- **The unresolved section.** A walk along the Fawley bank, or a question to Thames Water, would settle it.
  Either is an outside step.
- **Whether to add a join row** for `TWL00222`. Not needed for the forecast today, since the network already
  places it.
