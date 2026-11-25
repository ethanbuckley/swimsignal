# What SwimSignal could tell people next: a ranked shortlist and one check

Written 24 November 2026 against main `65ed8967`. It asks what the site could next tell a swimmer, a club or an
event organiser that would change a decision, ranks the answers, and reports one feasibility check that was run:
[RIVER-WINTER](RIVER-WINTER-READ-2026-11.md). Nothing on the site, in a frozen file, in an active window or in the
2027 primary evaluation changed.

It builds on the [ambition portfolio](AMBITION-PORTFOLIO-2026-11.md) of 15 November and does not re-propose its
eight projects. Where an idea here touches one, it says so.

Labels:

- **[measured]** a number this session computed. The command or script is named.
- **[read]** a fact I read in a named file, PR or web response on 24 November 2026.
- **[reported]** a fact from one of this session's two research agents, which opened the page. I did not open it.
- **[inferred]** my reading. A named check would settle it.

Each idea is marked **new**, **extension** (of work already here, with new evidence) or **reopened** (set aside
before, with what has changed).

## In short

1. **The check run today passed.** From October to April the site hides its river E. coli estimate as untested.
   On 2,754 winter river samples that no model here had scored, that hidden figure put a monitoring point's days in
   the right order: 0.485 (0.393 to 0.525), and 0.484 (0.354 to 0.531) with the calendar taken out, against a bar of
   0.15 fixed before the read [measured, [RIVER-WINTER](RIVER-WINTER-READ-2026-11.md)]. Summer at the same points
   was 0.39. Rain alone did as well as the model.
2. **So the first pick is a winter river line**, built behind a switch that is off, for Ethan to decide. Every
   reader until May is out of season.
3. **The test to run next** is a rain word for the 15 river spots with no overflow upstream, frozen and scored once
   on the winter samples held in reserve. At such points rain ordered winter days at 0.458 (0.326 to 0.521), while
   production's chance averaged 9% where 46% of results were over 900.
4. **The ambitious bet** is a same-day "sentinel" update: a reading at one site correcting its neighbours. What the
   estimate leaves unexplained is shared between bathing waters under 50 km apart on the same day (rivers 0.21,
   lakes 0.32) and not beyond [measured, seen data]. It needs a same-day measurement source, which is Yorkshire
   Water's project.
5. **With one week:** the winter line's PR, the reserve read for the rain word, a start on logging the Thames
   stream warnings, and a mock-up of "since your sample" for the organiser interviews.

## The check: RIVER-WINTER

Full record: [RIVER-WINTER-READ-2026-11.md](RIVER-WINTER-READ-2026-11.md). Script: `scripts/river_winter/winter_read.py`.

- **Why this check.** It resolved the largest uncertainty that could be settled today with no request and no
  account: whether the estimate hidden for seven months of the year carries any information. The samples were
  already on disk, sealed and unparsed. The model file was frozen before RIVER-UNSEEN's read. So this could be a
  frozen-model backtest on unseen outcomes, not a development figure.
- **What was fixed first.** The figure (production's river chance as deployed, `ecoli_model.json`, SHA-256
  `7daf7c8e…`), two conditions with the bar of 0.15, the interval, the reported figures and what each outcome leads
  to, pushed in commit `bcdb9155` before any winter result was joined. Amendment 1 (`89ba609d`) fixed a clock-change
  bug in the row builder and left out January 2012, also before any score.
- **What was held back.** Half the winters (2,561 rows) stay sealed for one later frozen test.
- **Result.** Both conditions pass: 0.485 (0.393 to 0.525) raw, 0.484 (0.354 to 0.531) with month means removed.
  28 points with 15 or more rows, in 8 river systems, 18 of them in the South West.
- **Established.** At these monitoring points, at lead 0 with reanalysis rain, the hidden figure orders winter days,
  beyond the calendar. Exposure alone, which is what the live winter level is made from, orders them too: 0.471
  (0.367 to 0.530).
- **Not established.** A percentage or level (production said 35.5% on average where 48.3% were over 900); any gain
  from the overflow chain over rain alone (+0.011, −0.022 to +0.032); anything at swim spots, lakes, or days ahead;
  the soil-moisture model the site uses in season.
- **Reproduce.** The commands are at the end of the record. Inputs: the sealed table (`95ca8c9f…`), the ERA5-Land
  cell files for 2012-22, this commit's tracked data. Shared inputs had the same fingerprints before and after.

### What the result changes about the ranking

- Before the read, winter was a question. It is now the first deliverable, because the evidence is of the
  confirming kind and the readers are here now.
- A winter-specific river model drops off the list. The summer model's order carried over without one.
- The rain word for spots with no overflow upstream moves up. Its winter side figure is strong, and it has a clean
  test waiting in the reserve.
- It is the second unseen read in which rain alone matched the model at rivers. Work that refines the overflow
  chain for river E. coli moves down; work that puts a rain reading where there is no overflow data moves up
  (the portfolio's ANYWATER).

## Where things stand (read before ranking)

- **Live.** A daily level at 98 of 133 inland spots from the spill forecast; in season, an E. coli chance, a lake
  reading with a range (11 lakes) and "higher or lower than usual here" at river spots (#709, from May 2027). River
  level, flood alerts, water temperature all year, algae checks, past samples, overflow history, alerts, an
  organisers' page with British Triathlon's checklist.
- **Out of season, which is now.** The E. coli estimate is hidden from October to April (DESIGN, 20 October 2026).
  The level comes from the spill forecast alone. No winter river sample had been scored by any test here before
  today [read: register, RIVER-UNSEEN's row rules].
- **No daily level.** 35 spots have no monitored overflow upstream: 15 rivers and 20 lakes [measured, live
  `spots-lite.json`, 24 November 13:21 UTC]. The 15 rivers are upland becks and gorges (Janet's Foss, Tarr Steps,
  Padley Gorge). They read "No monitored overflow found upstream" every day, in every weather.
- **In development or shadow.** Regional routing, combined-v1, radar to the issue hour, spill durations, lake
  concentration, the Scotland trial, coastal C1 (register).
- **Tested and not adopted.** Die-off weather, dynamic flow, gauge level rise, farm pressure, lake wind, radar at
  each overflow, a neural network, lake own-rate, lake temperature by lake type (register, negative evidence).
- **The portfolio's finding that matters most here.** At 59 river points no model had seen, rain alone ordered a
  point's summer days at 0.355 and production at 0.376. The overflow chain adds little to the order at rivers.

## Area 1: new data

| Feed | What was checked | Usable now? |
|---|---|---|
| EA Water Quality Archive, winter river E. coli | 5,416 October to April results at the 59 RIVER-UNSEEN points, 2012-22, already in the sealed table and never parsed [measured, `winter_read.py counts`]. In 2024 the archive held 927 winter river results at 130 points [reported, one sample query] | **Yes. Used for today's check.** OGL |
| EA River Thames conditions (stream warnings by lock reach) | `gov.uk/api/content/guidance/river-thames-current-river-conditions`: JSON with the reach table as HTML, updated 24 November 11:51. 45 reaches, 43 with no warning, 2 at "Yellow caution: stream increasing" [measured, one request]. OGL. No archive of states [reported]. 11 listed spots are on the Thames [measured]. Join is by lock name, so it needs a 45-row lock table | **Yes**, as a dated observation. New |
| Canal & River Trust strong-stream warnings | An undocumented JSON behind its page: 19 sites on 9 navigations (Severn, Trent, Kennet & Avon), status and a telemetry time. No licence, no coordinates, no history [reported] | No. Needs their permission |
| UKCEH Bloomin' Algae sightings | Public CSV, 5,535 records, refreshed today. 29 of 48 listed lakes have a confirmed or plausible record within 1 km (156 records since 2019, 37 in 2026). 16 of those 29 have no EA algae check on their page [measured, `ba_cover.py` on the CSV]. No licence stated [reported]. The enquiry is drafted and unsent (EXPANSION-2026-10) | Blocked on one email. Reopened: the coverage is now measured |
| Yorkshire Water real-time project | 20 sites, lab samples four times a week, sensors every 15 minutes, open data a stated aim. No data, map or API public yet [reported] | No. This is DENSE; the draft email is unsent |
| Severn Trent bathing-river forecast | A public map layer: 958 points on the Avon, Leam, Sowe and Teme, an E. coli and enterococci class for three days in 4-hour slots. Last edit 31 October. No licence; its history needs a token [reported] | Not for reuse. Worth knowing: a water company now publishes a river forecast by time of day at spots SwimSignal lists |
| Wessex Water, Farleigh Hungerford samples | 114 E. coli results, May 2024 to 3 November 2026, every month including winter. Licence field empty [reported]. The site already holds Wessex's 2021-25 samples under CC BY (#688) | Check the terms of this layer before use. Winter samples at a listed swim spot |
| EA Shropshire daily testing | E. coli by Fluidion sensor at Shrewsbury and Ludlow, in an app only. The open hydrology stations there carry no E. coli and stopped in April and July 2026 [reported] | No |
| RNLI lifeguarded beaches | 254 points, an open licence with attribution. No season dates in the data [reported] | Low value without dates |
| EA and NRW coastal risk predictions | Archives from 2013 (England) and 2015 (Wales), OGL, JSON [reported]. Already used as a reference in COASTAL-BASELINES | Known |
| Emergency overflow reporting | The duty (Water (Special Measures) Act 2025, s4) shows no commencement [reported] | Nothing to ingest |

## Area 2: where the forecast struggles, and methods

| Failure that matters to a swimmer | Evidence | Method that could fix it | Must beat |
|---|---|---|---|
| Winter. The estimate is hidden; the level is spills only | Today: the hidden figure orders winter days at 0.485 (0.393 to 0.525); rain alone 0.473; the level from it is too low (35.5% against 48.3%) [measured]. Published work says winter loads shift from overflows to field runoff (River Leam) [reported] | None needed for the order: the summer model carried over. For a level, a winter refit scored on the reserve | Production as deployed; rain in 48 hours alone |
| Dry-day highs at some rivers | 54 of 199 river results over 900 came on dry days (portfolio, DRY-DAY) | Treated-effluent share of flow. No published model with out-of-sample skill was found [reported] | A site's own dry-day rate |
| Lakes: no skill against the usual rate | Register, LAKE-CONC | Same-day information from a neighbour (below) | The lake's own rate |
| Errors shared across a region on a day | What the estimate leaves unexplained is correlated between bathing waters under 50 km apart sampled the same day: rivers 0.21 (0.13 to 0.29, 403 pairs), lakes 0.32 (0.18 to 0.44, 911 pairs). Beyond 50 km: none (−0.01 and 0.02) [measured, `sentinel_check.py`, seen samples and hindsight estimates, development] | A "sentinel" update: a same-day reading at one site corrects its neighbours. Chicago's version lifted AUC from 0.65 to 0.75 [reported] | The forecast without the update; the last sample |
| A fixed wait after rain | Agencies' 24, 48 and 72 hour waits are conventions; no data was found behind the 48 hours in UK apps [reported] | Already in hand: spill durations and clearing time (DURATION row; next check 1 December) | "Stops now" and the measured still-running curve |

Methods looked at and not ranked: conformal intervals and censored regression have no reported gain against a
baseline for bathing water [reported]. Site-specific rain slopes were tried for lakes (candidate B, #625) and did
not carry to unseen lakes.

## Area 3: other things to forecast or show

| Thing | Supportable as | Evidence |
|---|---|---|
| Whether winter river days can be ordered | **A limited forecast of order**, at lead 0 | Today's check passed |
| A rain word at the 15 river spots with no overflow upstream | **A limited forecast of order.** | At 23 monitoring points with no overflow upstream, rain and season ordered summer days at 0.309 (0.263 to 0.375), rain alone 0.321, on 2,071 samples no model had seen (RIVER-UNSEEN, side set). Winter, today: rain alone 0.458 (0.326 to 0.521) on 1,122 samples at 12 such points |
| Stream warnings on the Thames | **A dated observation.** | The feed above |
| Algae sightings at lakes with no EA check | **A dated observation**, once licensed | 16 lakes, above |
| Whether conditions differ by arrival time | **Needs new measurements.** | One US river varied up to tenfold within a day, peaking 08:00 to 12:30; a Lake Michigan beach fell through the morning, more on sunny days; no UK river measurement was found [reported]. Yorkshire Water's 15-minute sensors could answer it if released |
| How long after rain a place stays raised | **Observation now, forecast in development** | Durations page live; clearing-time wording waits on task 3b and the 1 December check |
| What has changed since an organiser's lab sample | **A dated observation** from data already held | Area 4 |

## Area 4: product

Each is marked against [DESIGN.md](DESIGN.md).

**A. "Since your sample" on the organisers' page.** New. British Triathlon's 2025 guidance asks for lab tests one
month, two weeks and one week before; a result takes 48 hours; over 900 E. coli inland means no swim; for rivers it
says earlier testing has limited value and points to spill notifications and live maps. World Triathlon's matrix
combines the last result with forecast heavy rain [reported, both documents opened by the agent]. So on race day
the organiser's own number is at least a week old, and the rules already name what SwimSignal holds. What would
appear: the organiser enters the sample's date. The page gives, for the days since: rain at the spot, hours of
reported spills upstream, the level SwimSignal issued on the sample day beside the level for race day, and the
river's state. One sentence: "The water on race day is forecast higher / about the same / lower than on the day
you sampled." No pass or fail. Who: organisers and clubs that test. How we would know: in the organiser
interviews (none held yet), whether they can say what they would do differently; then the action counter on the
field. It fits the organisers' page as built; it adds no level or colour.

**B. A rain word where there is no overflow upstream.** Extension. Today 15 river spots say the same thing in a
drought and after a storm. What would appear: under "No monitored overflow found upstream", one line in season:
"More rain than usual here in the last two days. At rivers like this, samples after rain have read higher." It
keeps the teal and sets no level. It needs Ethan's wording decision, because DESIGN's 11 October rule gives these
spots their own words. How we would know: it cannot be judged at these spots (no samples). It rests on the
monitoring points, said on the page.

**C. Stream warnings on Thames spots.** New data, existing place. DESIGN's "River high and flood alerts" (3
October) already gives one line "A separate hazard, not part of the pollution level." A Thames spot would add the
Agency's own board for its reach, dated. How we would know: log the 45 reaches daily for 60 days and compare with
the gauge label the page already shows. If the board never differs from "High water", it adds nothing.

**D. The river line in winter.** Extension, and it reverses one part of a decision. DESIGN's 20 October rule
keeps every E. coli figure out of view from October to April because the estimate was untested then. Its order is
now tested. What would appear at river spots: "That is higher than usual here." (or lower, or about usual), as #709
gives in season; no percentage, no change to the level. Who: every winter river swimmer. How we would know: the
reserve half for any change to the figure; winter samples at a listed spot (Wessex's Farleigh Hungerford layer has
them, terms to check); and the action counter on the tile.

## The ranked shortlist

Ranked by what it would change for a reader, weighed against how soon it can be shown to work.

| Rank | Idea | Decision it improves | Strongest evidence | Smallest credible test | Main dependency | Drop it if |
|---|---|---|---|---|---|---|
| 1 | **River line in winter** (extension, tested today) | Which winter day to swim a river. Every river reader until May | Frozen-model backtest on 2,754 unseen winter samples: 0.485 (0.393 to 0.525), calendar removed 0.484 [measured] | Build the winter cut-points offline and the switch, off. Then one swim-spot check: Farleigh Hungerford's winter samples, if the terms allow | Ethan's decision. Which model file makes the word | Ethan finds an order word with no figure confusing; or at 40 or more winter samples at a listed spot the interval includes zero |
| 2 | **Rain word where no overflow is upstream** (extension) | Whether to swim an upland beck the day after heavy rain. 15 river spots that read the same every day | Rain alone at such points: 0.309 (0.263 to 0.375) in summer, 0.458 (0.326 to 0.521) in winter; production's chance averaged 9% where 46% were over 900 [measured] | Freeze a rain-only word and score it once on the reserve's no-overflow rows (1,028 rows, 10 points with 15 or more) | Ethan's wording, against DESIGN's 11 October rule for these spots | The reserve interval is not wholly above 0.15; or no wording avoids implying a level |
| 3 | **"Since your sample" for organisers** (new) | Whether a week-old lab result still describes race day | British Triathlon's rules: tests a month, two weeks and a week before, 48 hours for a result, and for rivers "limited value" [reported] | A mock-up for one event in the interview pack; three interviews | The organiser interviews, none held yet | Three organisers do not hold a sample date, or would not act on it |
| 4 | **Thames stream warnings** (new data) | Whether to get in on the Thames; an organiser's course call | The Agency's feed: 45 reaches, daily, OGL; 11 listed spots [measured] | A 45-row lock table, then log daily for 60 days beside the page's river state | None | The board never differs from the gauge label the page already shows |
| 5 | **Sentinel update** (new; the ambitious bet) | A level that corrects itself when a neighbour is measured that day | Same-day shared error under 50 km: rivers 0.21 (0.13 to 0.29), lakes 0.32 (0.18 to 0.44), none beyond [measured, seen data]. Chicago: AUC 0.65 to 0.75 [reported] | With Yorkshire Water's samples: leave one site out, add the neighbour's same-day reading, compare with the forecast alone. Before that, a development version across Windermere's four sites | A same-day measurement source. EA results arrive days late and cannot be sentinels | No release by 1 March 2027 (DENSE's date); or the leave-one-out gain's interval includes zero |
| 6 | **Algae sightings at lakes with no EA check** (reopened) | Whether to get in at 16 lakes that show no algae information | 29 of 48 listed lakes have a confirmed or plausible record within 1 km; 16 have no EA check [measured] | None needed; it is an observation | UKCEH's licence. The email is drafted and unsent | They refuse reuse |
| 7 | **Time of day** (needs measurements) | Morning or afternoon | Up to tenfold within a day on one US river; no UK river data [reported] | Add one question to the Yorkshire Water ask: the 15-minute sensor series | That release | The sensors are not released, or show no daily cycle |

### The three picks

- **Improvement to trial soon: 1, the river line in winter.** It is the only item with confirming evidence in hand,
  it serves the people reading now, and it costs one offline build.
- **Forecast or data project to test next: 2, the rain word where no overflow is upstream.** A frozen figure, a
  sealed test set, no request. It also tells us whether a rain reading can stand in for the model anywhere without
  overflow data.
- **Ambitious research bet: 5, the sentinel update.** The shared same-day error is real and local. It is modest
  (0.21 means a neighbour explains about 4% of what is left at a river), so the bet is on dense same-day data, not
  on the EA's samples.

### With one week

1. Days 1 and 2: the winter cut-points file and `river_usual.direction` for October to April, behind a switch that
   is off, with tests and the method-page sentence. One PR. Ethan decides.
2. Day 3: a statement for the rain word, pushed, then the reserve read at the no-overflow points.
3. Day 4: the Thames lock table and a daily log of the 45 reaches, in the build, shown nowhere. This starts the 60
   days.
4. Day 5: the "since your sample" mock-up, added to the organiser interview pack.

Ethan's part, about an hour: decide on the winter line; send the Yorkshire Water email (drafted) with one added
question about the sensor series; send the UKCEH Bloomin' Algae email (drafted).

## What I would not do

- Rebuild any idea in the register's negative-evidence table. None of the above does.
- Show a time-of-day effect. There is no UK river measurement.
- Use the Severn Trent, Canal & River Trust or Bloomin' Algae feeds before their terms are settled.
- Read the reserve half of the winter samples for anything but a frozen winter candidate.

## Sources

Opened by me on 24 November 2026: `https://www.gov.uk/api/content/guidance/river-thames-current-river-conditions`
(one request); `https://swimsignal.co.uk/data/spots-lite.json` (one request); the repository files named above.

Opened by the agents, not by me. Winter and methods: Suslovaite and others 2024, Water Research (River Leam),
https://eprints.whiterose.ac.uk/id/eprint/231879/ ; Kay and others 2008,
https://research.aber.ac.uk/en/publications/faecal-indicator-organism-concentrations-and-catchment-export-coe/ ;
Environment Agency EDGE summary, 2 October 2026 (enterococci decay at 5 to 20 °C); Bowes and others 2026 (UKWIR),
https://nora.nerc.ac.uk/id/eprint/541944/ ; Lucius and others 2019 (Chicago),
https://pmc.ncbi.nlm.nih.gov/articles/PMC6549907 ; Nguyen and others 2022 (Chattahoochee),
https://www.frontiersin.org/articles/10.3389/fmicb.2022.1029176 ; Whitman and others 2004,
https://pmc.ncbi.nlm.nih.gov/articles/PMC444827 ; Ackerman and Weisberg 2003. Organisers: British Triathlon Water
Quality Guidance 2025, https://events.britishtriathlon.org/uploads/content/Water%20Quality%20Guidance.pdf ; World
Triathlon Competition Rules, rules 10.1 and 10.2. Feeds: Canal & River Trust
`canalrivertrust.org.uk/api/scada/strong-stream-warnings`; `bloominalgae.ceh.ac.uk/data/BA_records.csv`; Yorkshire
Water's 22 May 2026 announcement; Severn Trent's `BathingRivers_WarksBW_Points_PROD` layer; Wessex Water's
`farleigh_hungerford_wq_sampling` layer; RNLI `RNLI_Lifeguard_Units`; legislation.gov.uk for s141DA and the 2025
Act's s4.

Scripts for the two small measurements are in `scripts/next_research/`. Both read committed or public files only.
