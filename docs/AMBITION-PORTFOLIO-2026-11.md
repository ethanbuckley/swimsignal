# Ambition portfolio, November 2026

Written 15 November 2026 against main `6743baf2`. A ranked list of eight projects that could change what a swimmer
can know or do, each with a first test that could start next week. **A document, not a result.** No model was fitted
for release, no held-out bench row was read, no Open-Meteo request was made, nothing was sent to anyone, and nothing
on the site, in a frozen file or in an active window changed.

Labels used throughout:

- **[measured]** a number this session computed, with the script or request named.
- **[read]** a fact read in a named file, PR or web page on 15 November 2026.
- **[reported]** a fact from one of this session's three research agents that I did not open myself. Each says
  whether the agent read the page or saw a search snippet only.
- **[inferred]** my reading. A named check would settle it.

Every figure computed here uses the backtest bench's **seen** rows (2023-26). Those are development evidence. None
is a confirmation.

## In short

1. **The river forecast can be tested on years it never saw, now.** The Environment Agency's archive holds at least
   2,500 river E. coli results a year at points that are not bathing waters [measured, two requests]. No model here
   has used them. The bench has 60 held-out river rows. This is the largest unused label set found.
2. **Yorkshire Water is taking four lab samples a week at 20 inland sites for two years, and says open data is a
   key aim** [read on its page]. Three of the named sites are listed spots. If the samples are released, the 2027
   season can show in real water whether a high forecast means a high reading, with four times the EA's samples.
3. **About a quarter of river results over 900 came on dry days, and the forecast has no term for them.** 54 of 199
   [measured]. At three rivers the dry-day rate over 900 was 35% where production's form gives 10% [measured]. A
   site's own past rate does not fix it out of season [measured]. A mechanism (treated sewage as a share of river
   flow) is untested here and is used in Berlin's river model [reported].
4. **Most of what orders a river's samples is available from rain and season alone.** Within-site rank correlation
   0.385 from rain and season at sites left out of the fit, 0.427 with the spill chain added; the gain is +0.012 to
   +0.071 [measured]. So the spill chain adds a little at rivers, and a rain-only reading can go where no overflow
   data exists.
5. **A better forecast still reaches almost no one.** Push alerts cannot work in Facebook's browser, which sent 42%
   of visits (6 November figure, dated). Email alerts are built and switched off [read].

The eight projects, ranked, are in "Ranking". The top three come first, each with a drafted statement.

## What was checked before relying on it

| Claim in the brief | Check | Result |
|---|---|---|
| The spill model has no unseen years | `docs/BACKTEST-BENCH-2026-11.md` ("The spill model is not covered"), `docs/EARLIER-SPILL-HISTORY-2026-10.md` lines 21-22 and 53-54 | Holds [read]. Southern and Yorkshire have no open event record before 2024 |
| Recent spill candidates gain 1-3% | Register rows for #694, #697, #640, UU diagnosis | Holds for those rows [read]: 3.3%, 3.2%, 0.9%, 0.3-0.7%. Combined-v1 is larger (0.0307 against 0.0419 at lead 1) but was chosen after 2026 was seen |
| Bench: 2,395 held-out rows, 53 over 900, 60 river rows | `swimsignal-private/bench/ecoli-v1/manifest.json` and the bench record on branch `claude/swimsignal-open-work-7a5300` | Holds [read]. I did not open `heldout.parquet` |
| Read 1: within-site rho 0.29 against −0.015 | `docs/BENCH-READ-LAKE-RANGE-2026-11.md` on that branch | Holds [read]: 0.289 against −0.015, difference +0.304 [+0.197, +0.409] |
| Cached archive rain is most likely IFS, not ERA5-Land | `docs/ERA5-LAND-BULK-RAIN-2026-11.md` on branch `claude/era5land-bulk-rain-a3c198` | Holds as an inference [read]: neighbour pairs agree with the IFS grid 93-96% |
| Coastal samples 2012-26, 32,875 at 404 sites | `docs/COASTAL-BASELINES-2026-11.md`, `data/research/coastal/` | The committed table is 2022-26 (32,868 scored rows at 404 sites) [read]. Samples before 2022 are deliberately unread, for C1's backtest. "2012-26" describes what the archive holds, not what is fetched |
| 417 visits a week, 42% Facebook, 1 push subscriber, 0 interviews | Not in the repository (private strategy review) | Not checked. `docs/ORGANISER-INTERVIEWS-2026-11.md` confirms no interview held [reported, agent read] |

One correction to the source inventory: it says the archive has a "one-year query limit" that "needs API calls" to
confirm. The API answered "Unless querying a single sampling point's observations, the maximum temporal range is 1
year" [measured, request 10 in the log]. The limit is real for queries across points.

## Development checks run for this record

Scripts: `scripts/ambition_portfolio/`. Outputs: `docs/ambition-portfolio/*.txt`. Input: the bench's `seen.parquet`
only (sha256 `417648aa…`, 2,153 rows, 943 at 20 river bathing waters, 1,210 at 18 lake bathing waters). The private
bench files and the Wessex cache had the same SHA-256 before and after. The scripts never open `heldout.parquet`.

| Check | Result (seen rows, 2023-26) | Script |
|---|---|---|
| River results over 900 on dry days (under 2 mm in 48 h) | 54 of 199 (27%). Dry-day samples: 508, of which 10.6% over 900 | `seen_checks.py` |
| Where the dry-day results are | River Tone, River Cam, River Nidd: 31 of 89 dry-day samples over 900 (35%). Production's form, season held out, gives those days a mean chance of 9.6% | `river_site_level.py` |
| Does a site's own past rate fix that? | No. Added to production's form, season held out: Brier 0.1375 against 0.1375, difference [−0.010, +0.011]. Forward to 2025 it is worse (0.180 against 0.127). Site-level error halves (0.10 to 0.05) but does not carry between seasons | `river_site_level.py` |
| Is a river's dry-day level stable between seasons? | Not shown. 12 sites, 2023-24 against 2025-26: Spearman 0.39 [−0.26, +0.86]. At the Cam, 9 of 9 dry-day samples read over 900 in 2024, then 1 of 13 in 2025 and 2 of 10 in 2026 | `dry_day_stability.py` |
| Yield of sampling after rain | After more than 10 mm in 48 h: 79 of 130 river samples over 900 (61%). Otherwise 14.8%. Only 14% of river samples followed that much rain | `seen_checks.py` |
| Chance bands, season held out | Chance 0.4 or more: 55% over 900 (152 samples). Under 0.1: 8% (378 samples) | `river_bands_range.py` |
| Pairs needed to show that gap | 20 pairs give 91% power at one-sided 5% (sign test, simulated). At half the gap, 40 pairs give 66% | `river_bands_range.py` |
| Rain and season alone, sites left out | Rivers: within-site rho 0.385; with exposure 0.427; difference [+0.012, +0.071]. Lakes: 0.318 and 0.308; difference [−0.028, +0.008] | `seen_checks.py` |
| A river likely reading with an 8-in-10 range | Log10 model, season held out: 79.3% inside the range with no site level, 77.3% with one. The range spans a factor of 11 to 14. Within-site rho 0.359 | `river_bands_range.py` |

Limits of these checks. They are hindsight estimates on archive rain, not issued forecasts. The intervals resample
sites (20 rivers). "Production's form" is refitted here on the bench rows without soil moisture, so it is close to
the deployed river model and not the same. No threshold was tuned.

Eleven small web requests went to the Environment Agency's Water Quality Archive and three to public news pages.
Every one is in `docs/ambition-portfolio/request_log.tsv`. Two responses held river E. coli results (2,500 rows each).
I counted rows by point, date, region, purpose and material, did not read the result column, and deleted both files.

---

## Top three

### 1. RIVER-UNSEEN: a decade of river samples the river model never saw

**What a swimmer gets.** A river estimate that has been tested on years it was not fitted on, at river points that
are not bathing waters. If it passes, a likely reading with an 8-in-10 range at river spots, in place of a level
alone. About 65 of the 85 river spots have no EA samples of their own today (85 river spots in #687's count, 20
river bathing waters in the bench).

**New, already tried, or reversing.** New use of a listed source. The inventory lists the archive's bathing-water
samples (`ea-bathing-water-inland`, `ea-coastal-bathing-samples`). `src/dipcast/ingest/wqa.py` fetches determinand
2348 at bathing-water points only [reported, agent read the code]. No file counts river E. coli away from bathing
waters. Extends the backtest bench (#700), whose record says "River candidates cannot be confirmed here". The river
range extends LAKE-CONC (#584, #585), which covers lakes only. The concentration study (#466) tied production on
river Brier (0.1071 against 0.1069); that was a chance over 900, not a range.

**Evidence it could work.**
- Measured: the archive returned 2,500 rows (its page cap) for determinand 2348 at sampling point type "Freshwater -
  rivers" for 2019 and again for 2024. So at least 2,500 a year exist. Each page held about 155 points, about 100 of
  them with 10 or more rows, 72% taken May to September.
- Measured: most rows are planned monitoring or planned investigations (2024 page: 1,683 local investigation, 457
  government-policy monitoring, 265 agency-policy monitoring). 89 of 2,500 were follow-ups to a failure or a
  pollution incident.
- Measured on seen rows: a river range holds 79% of held-out-season samples; within-site rho 0.36 to 0.43.
- Reported (agent read): an Ofwat-funded open model trained on 24 years of this archive reports 81% to 87% accuracy at
  500 cfu, falling to about 74% to 80% on a geographic split, with no sensitivity published. So others have found the
  archive usable.
- Hoped: that enough points sit on the river network with overflows upstream. The 2019 and 2024 pages lean to Devon,
  Cornwall and Morecambe Bay, so many points may be small streams above beaches. Not counted.

**Data.** EA Water Quality Archive, Open Government Licence v3.0 ("All content is available under the Open Government
Licence v3.0, except where otherwise stated" [reported, agent read the page]). API 1.3.1: 2,500 rows a request for
CSV, one year a query across points, filters for determinand, point type, purpose and material [read in the API
description]. The site also offers CSV downloads by area type and year, 2000 to 2026; file sizes are not shown
[reported, agent read]. Missing: the national count, the points' positions against the river network, rain and
exposure for each sample.

**Cost.**
- EA: about 30 to 60 paced API requests for 2012-22 (inferred from 2,500 a year or more), or 11 yearly files.
- Rain at the points: about 2.6 weighted Open-Meteo calls a cell-year (375.4 calls for 144 cell-years, #700). 100
  points over 11 years is about 2,900 weighted calls, before the upstream overflows' cells. That is too much beside
  the live builds. With the ERA5-Land bulk download (#702) it is zero calls.
- Compute: placing points and rebuilding exposure, a few CPU-hours. Money: none. Ethan: 20 minutes for the Copernicus
  account that #702 already waits on.

**First test.** A frozen-model backtest. Statement below.

**Kill rule.** Before any outcome is read: fewer than 30 points pass the placement and count rules, or more than half
the kept rows sit at points with no monitored overflow upstream. Then the set cannot test the river model. Keep the
rows for ANYWATER's rain-only question and record why.

**Ethan's steps.**
1. Create the Copernicus Climate Data Store account (the step #702 waits on).
2. Nothing else until the statement's result.

#### Drafted statement: RIVER-UNSEEN read 1

*Draft. To be pushed, with the candidate's hash, before any archive result is joined to an input.*

- **Question.** Does a river model fitted only on 2023-26 bathing-water samples order the samples at river points it
  never saw, in 2012-22, and does its 8-in-10 range hold there?
- **Rows.** Determinand 2348, sampling point type F6, material "river / running surface water", May to September,
  2012-22. Kept purposes: MS, MP, MU, MN, PI, PN. Dropped: UI, UF, SI, MI and MA to MD, because those samples are
  taken after a bad result or an incident, which selects on the outcome. A point is kept if it lies within 50 m of
  the river network, has 30 or more kept samples in three or more seasons, has at least one monitored overflow
  upstream, and is more than 500 m from a bench bathing water. Rows from 2023-26 at the same points are development
  rows and are not part of the read.
- **Candidate.** `river-range-v0`: a log10 model fitted on the bench's 943 seen river rows (rain in 48 and 24 hours,
  exposure, season), no site level at an unseen point, spread from the seen residuals. Frozen, hash committed.
- **References.** Production's river chance as deployed (without soil moisture where none exists for the year, said
  in the record); the month-of-year rate; "more than 10 mm in 48 hours".
- **Primary metric.** Mean over points of the within-point Spearman correlation between the likely reading and the
  measured log10 count. **Pass:** the 95% interval over river-system seasons lies wholly above 0.15.
- **Range check.** Share of samples inside the 8-in-10 range. **Pass:** between 72% and 88%.
- **Reported, deciding nothing.** Brier over 900 against each reference; seasons to 2016 and from 2017 apart (the
  rain source most likely changes at 2017); by purpose; by upstream catchment size.
- **Both pass.** A wording proposal for Ethan: a likely reading and range at river spots in season, on LAKE-RANGE's
  pattern, and a shadow log beside production for 2027.
- **Order passes, range fails.** An order-only line ("higher or lower than usual here") is proposed; the spread is
  diagnosed by stream size.
- **Order fails.** The river estimate stays as it is. The record says the model did not transfer to these points and
  shows which kinds of point it failed at. The rows stay as development data.
- **Disclosure.** Before this statement, counts by region, purpose, material and month were printed for two pages of
  2,500 rows (2019 and 2024). No result value was read.

### 2. DENSE: four lab samples a week as the forecast's test in real water

**What a swimmer gets.** A dated, public answer to "when this site said high, was the water high?", from lab samples
taken every other day at river spots in 2027. Today that answer rests on about 20 EA samples a site-season.

**New, already tried, or reversing.** New. The repository has no mention of the Yorkshire Water project (grep for
"UnifAI", "four times a week": none). Related and already tried: the EA's daily sensor readings at Shrewsbury and
Ludlow were tested privately on 22 October (`swimsignal-private/ea-westmids-2026-10-21/RESULT-fluidion-rank-2026-10-22.md`):
the forecast ranked Ludlow's sensor days (rho 0.42 [0.10, 0.62]) and not Shrewsbury's (−0.02). The EA then said the
readings were raw and need converting; the follow-up draft is unsent. Extends the sampling planner's field study
(#381, #566), which waits on Ethan's decision, by using samples someone else already takes.

**Evidence it could work.**
- Read on Yorkshire Water's page (22 May 2026): a two-year project with UnifAI Technology, The Rivers Trust and BSI,
  funded by Ofwat. Sensors every 15 minutes at 20 sites. "water samples, taken 4-times per week at each individual
  site" lab-tested for E. coli and enterococci. "more than 7,800 data sets". "A key aim of the project is to make
  data openly available." Sites named include Ilkley, Wetherby and Knaresborough.
- Measured on seen rows: when the chance was 0.4 or more, 55% of river samples read over 900; under 0.1, 8%. Twenty
  high-low pairs would show a gap that size nine times in ten.
- Read: the site has logged its issued `p_ecoli` in `forecast_points` since late September 2026 (WESSEX-RIVER row).
- Hoped: that the samples are released before the project ends, under a licence that allows scoring. The page gives
  no date and no licence. The same project plans its own public predictions, so it is also a competitor.

**Data.** Exists: issued forecasts at Cromwheel (Ilkley), Wilderness Car Park (Wetherby) and the Nidd at the Lido
(Knaresborough). Missing: the samples, their licence, the sampling points' positions and the lab method.

**Cost.** Open-Meteo: none (issued forecasts are already logged). Requests: one file fetch if released. Compute:
minutes. Money: none. Ethan: one email and its follow-up, about an hour.

**First test.** A prospective read on the 2027 season. Statement below. If the 2026 samples are released too, score
them first as a hindcast and label it development: the same seasons were used to fit production, on different days.

**Kill rule.** No release and no reply by 1 March 2027. Then fall back to PAIRS: ask one group that samples a river
anyway to take 20 pairs, one sample on a day the 08:00 forecast gives 0.4 or more and one on a day under 0.1, within
14 days of each other. If no group can move its days either, the 2027 primary evaluation is the only real-water test
and the record says so.

**Ethan's steps.**
1. Send the drafted email to Yorkshire Water's project lead asking whether and when the lab samples will be public.
   Draft: `swimsignal-private/outreach/ambition-2026-11-15/yorkshire-water-samples-DRAFT.txt`.
2. Send the unsent 11 November follow-up to EA West Midlands about converting the sensor readings.
3. If neither gives data by 1 March 2027, decide whether to ask a sampling group for pairs.

#### Drafted statement: DENSE read 1

*Draft. To be pushed before the first 2027 sample from this source is read.*

- **Question.** In May to September 2027, at listed river spots sampled by this project, did samples read higher on
  days when the site's issued chance was higher?
- **Rows.** Every lab E. coli sample from the released file at a sampling point within 500 m of a listed spot on the
  same river, with no overflow between them. One issued forecast per sample: the last issued by 08:00 on the sample
  day (lead 0) and by 08:00 the day before (lead 1), from `forecast_points`. Nothing is rebuilt in hindsight.
- **Primary metric.** Mean within-site Spearman correlation between the lead-1 issued chance and the log10 count.
  **Pass:** the 95% interval over site-weeks lies wholly above 0.
- **Second metric.** Brier over 900 against "more than 10 mm in 48 hours" and the site's month rate. **Pass:** lower
  than both, each interval wholly below 0.
- **Published whatever the result.** The four counts at the 0.25 warning line: warned and high, warned and not,
  not warned and high, not warned and not. Sensitivity and false-alarm share beside them.
- **Pass on both.** The Accuracy page gains a dated section for this test. A proposal to Ethan to say "tested against
  N lab samples in 2027" on those spots' pages.
- **Order passes, Brier fails.** The page says the forecast orders days and is not shown to beat the rain rule.
  Next: a calibration candidate for those sites, tested on the project's second year.
- **Order fails.** Published as a failure on the Accuracy page. Next: diagnose by site and by dry and wet days,
  with DRY-DAY's index.
- **Boundary.** This is a separate record. The 2027 primary evaluation uses EA samples only and is untouched.

### 3. DRY-DAY: what rivers read when it has not rained

**What a swimmer gets.** First, the dated fact: "Past samples here after under 2 mm of rain in 48 hours: the middle
of 32 read 770." Today the Tone's page gives a low level on such a day. Later, if the mechanism holds, a dry-day
level at river spots with no samples, from the treated sewage upstream and the river's flow.

**New, already tried, or reversing.** New as a model input. The four size tests (#166, #172, #197, #210) sized storm
overflows; none tested a works' continuous treated discharge as a dry-weather source. The page already says the
forecast "does not count treated sewage from sewage works" (DESIGN.md, the `levelScope` lines, 11 October). The
dry-weather spills test (#346) failed and is a different question (spills in dry weather). The page line extends the
"Past samples after rain" pattern Ethan chose on 15 November (#703), which today reaches five lakes with no daily
figure. Showing it beside a daily figure at a river is a new decision.

**Evidence it could work.**
- Measured on seen rows: the figures in the table above. 27% of river results over 900 on dry days; 35% over 900 on
  dry days at the Tone, Cam and Nidd against 9.6% from production's form.
- Measured: a site's own rate is not the fix (no Brier gain, worse forward to 2025), and a site's dry-day middle is
  not shown to hold between seasons (rho 0.39, interval through zero).
- Reported (agent read the package's guide): Berlin's river bathing model takes the share of treated wastewater in
  the river as an input. Its Bayesian form gave over 90% true positive rate at three German river sites (Seis and
  others 2024, agent read the abstract record).
- Hoped: that an index built from open data tracks dry-day levels here. The Cam's change after 2024 suggests
  something changed upstream, which a static index would miss.

**Data.**
- Works and their size: the EA's Urban Waste Water Treatment table, population equivalent for works over 2,000 only
  (`docs/PE-SOURCES-2026-10.md`). Its licence line was not read in this session.
- River flow: EA gauges and the National River Flow Archive, already used (`scripts/fit_reach_velocity.py`).
- Which works disinfect their discharge: no open list found [reported, snippet only: a 1998 list of 35 works].
- Bacteria in treated discharge: the archive's filters would show it; not counted.
- Not usable in anything published: the consents register (internal use only).

**Cost.** Open-Meteo: none (the bench rows hold the rain). EA: under 50 requests for flows at 20 sites. Compute:
minutes. Money: none. Ethan: one wording decision; three enquiry emails if he wants the works' details.

**First test.** Two steps.
1. *Page line, no model.* Export the dry and wet split for the river bathing waters from the bench's seen rows by
   #703's script and rule (5 or more in each group). 13 of 20 river sites have both groups at under 2 mm and over 10
   mm [measured]. It makes no claim to test. Ethan decides whether it shows.
2. *Mechanism, bounded exploration then a frozen read.* Statement below.

**Kill rule.** The index does not order dry-day middles at the 20 seen rivers (interval through zero) and is no
better than upstream overflow count alone. Then archive the index, keep the page line, and say what would reopen it:
a list of works with disinfection, or bacteria results for treated discharge.

**Ethan's steps.**
1. Decide whether river bathing waters show the dry and wet past-sample line beside the daily figure.
2. Optional: ask the EA's area teams what their investigations found at the Tone (Taunton), the Cam (Cambridge) and
   the Nidd (Knaresborough). Draft: `swimsignal-private/outreach/ambition-2026-11-15/ea-dry-day-enquiry-DRAFT.txt`.

#### Drafted statement: DRY-DAY read 1

*Draft. The exploration on the 20 seen rivers comes first and is labelled development. The read below is frozen
after it and before RIVER-UNSEEN's dry-day outcomes are joined.*

- **Question.** Across river points the index was not built on, does a treated-sewage index order their dry-day
  E. coli levels?
- **Index.** For each point: the population equivalent of every works discharging upstream within the transport
  window, each reduced by the transport fit's decay to the point, summed, and divided by the river's median summer
  flow at the nearest gauge scaled by catchment area. One number a point. Fixed after the exploration.
- **Rows.** RIVER-UNSEEN's kept points, samples with under 2 mm in the 48 hours before, points with 8 or more such
  samples. The outcome is the point's median log10 count on those days.
- **References.** The number of monitored overflows upstream; catchment area alone.
- **Primary metric.** Spearman correlation across points between the index and the dry-day median. **Pass:** the 95%
  interval over river systems lies wholly above 0, and the index's correlation is higher than each reference's with
  the paired interval above 0.
- **Pass.** A river-range candidate with a dry-day level from the index, for its own bench read. A page proposal that
  names the works upstream as a fact, with no level.
- **Fail.** The index is archived. The page keeps past samples only. The record lists the three rivers' open
  explanations and the measurement that would separate them.
- **Not claimed either way.** That a works causes any sample. That treated discharge breaks a permit.

---

## The other five

### 4. ALERTS-BY-EMAIL: an alert route for the people who cannot have push

**What a swimmer gets.** An email when a saved spot turns high, on any phone, from any browser. Today a reader who
arrives from Facebook cannot be alerted at all.

**New, already tried, or reversing.** Already built, switched off. `push/README.md`, "Email alerts": "built and tested
but **off**" until `MAIL_API_KEY`, `MAIL_HASH_KEY`, `EMAIL_FROM`, `WORKER_URL` and `DIPCAST_EMAIL_URL` are set. It covers rises
only. Not a new surface: the 12 November review's rule ("Nothing should be added to the swimmer's site until
something is removed or folded") is met because the Alerts tile already exists and already explains why push fails.

**Evidence it could work.** Read: push needs the Home Screen app on an iPhone and cannot work in Facebook's or
Instagram's browser (DESIGN.md lines 1443-1449; `push/README.md`, "Email alerts"). Reported from the brief: 42% of visits from Facebook, 1 push
subscriber (6 November, dated). Reported (agent read): Auckland's evaluation found 9% of beach visitors checked its
service before arriving and 54% had not heard of it, so reach, not accuracy, was its limit. Hoped: that readers who
cannot take push will give an email address. Nothing here measures that.

**Data.** None needed. The Worker stores a confirmed address and a hash [read].

**Cost.** Open-Meteo: none. Money: none inside the mail service's free allowance of 100 emails a day [read]; a paid
plan would break the no-spending rule, so the test stops at the allowance. Ethan: about two hours (a mail service
account, the five values, and a read of the privacy notice's email section, which the build adds by itself).

**First test.** Prospective, 28 days from switch-on, stated before it starts. Count confirmed email sign-ups and new
push subscriptions per 100 visits to spot pages, by browser class. **Pass:** 5 or more confirmed addresses and at
least 1 per 100 spot-page visits. Pass leads to date alerts and the weekly note by email (each needs its own consent
words, as the README says). Fail leads to switching it off and recording that alerts are not what readers want from
this site.

**Kill rule.** Fewer than 5 confirmed addresses in 28 days, or the free allowance is reached.

**Ethan's steps.**
1. Decide whether an email address may be held at all before the ICO fee question is settled
   (`docs/PARTNER-PROGRAMME-2026-11.md` leaves it open).
2. If yes: create the mail account, set the five values and deploy the Worker.

### 5. WINDERMERE-100: test the lake chain across one lake

**What a swimmer gets.** On England's most-swum lake, a tested answer to "where on the lake do readings run higher?"
The site gives each Windermere spot its own figure today, and no test has compared places on one lake on one day.

**New, already tried, or reversing.** New source: "Big Windermere" has no hit in the repository. Related: the lake
direction test (#313) passed seven checks and was not adopted; near-field (#187) closed for want of "source/shore
hydrodynamics and paired observations"; lake wind failed. The Waterhead partner samples (WET) are one point.

**Evidence it could work.** Reported (agent read the survey's pages): about 100 locations, 10 surveys from June 2022
to November 2024, "nutrient and bacterial concentrations at independent laboratories". Reported, snippet only: over
1,000 samples, E. coli and intestinal enterococci. Hoped: that the results can be had as a table with positions and
dates, under terms that allow scoring. No licence is stated on the pages read. No lake hydrodynamic model for
Windermere's bacteria was found [reported].

**Data.** Exists: lake-range-v1 and the click-anywhere lake machinery, which can give a figure at any point on the
lake. Missing: the survey table and its terms.

**Cost.** Open-Meteo: 10 survey dates at Windermere's cells, under 30 weighted calls, or none with ERA5-Land. Compute:
minutes. Money: none. Ethan: one email.

**First test.** A frozen-model backtest in space. For each survey, lake-range-v1's likely reading at every sampled
point, computed with no change to the model. Metric: the within-survey Spearman correlation across points between
the likely reading and the measured log10 count, averaged over surveys. Reference: straight-line distance to the
nearer of Ambleside and Bowness. **Pass:** the interval over surveys lies wholly above 0 and the model's correlation
is not below the reference's. Pass leads to a Lab exhibit of the lake by place and a proposal to say the lake figures
were tested across the lake. Fail leads to a "not tested across the lake" line on Windermere's clicked points and
reopens near-field with real pairs. May to September surveys decide; others are reported apart.

**Kill rule.** No table or no permission by 28 February 2027, or fewer than 5 surveys with 50 or more points.

**Ethan's steps.**
1. Send the drafted email to the Freshwater Biological Association.
   Draft: `swimsignal-private/outreach/ambition-2026-11-15/fba-big-windermere-survey-DRAFT.txt`.

### 6. SPILL-UNSEEN: the spill model's first unseen years

**What a swimmer gets.** Nothing visible at first. The Accuracy page could then say the spill forecast was tested on
company-years it never saw, which no line can say today. It also gives the regional and combined candidates a
confirmation that does not wait for a shadow window.

**New, already tried, or reversing.** The sources are listed (`southern-water-event-history` 2017-2025,
`yorkshire-water-event-history` 2021-2026, both "needs permission"). The asks are drafted and unsent:
`docs/EARLIER-SPILL-HISTORY-2026-10.md` (an Environmental Information Regulations request for 2020-23) and
`docs/OVERFLOW-DATA-SOURCES-2026-10.md` step 3 (a licence request). New here: their use as a held-out set under the
6 November backtest rule.

**Evidence it could work.** Read: earlier years at Northumbrian and Wessex were usable once fetched (#258). Read: the
multi-year test found older years did not explain most of the trees' gains, so this is a test set, not more training
data. Hoped: that either company answers, and that monitors before 2024 were reliable enough to score.

**Data.** Exists on the companies' sites with no licence. Covariates from annual returns exist from 2020. Missing:
permission, and rain for those cells and years.

**Cost.** Open-Meteo: about 1,500 weighted calls a company for 2020-23 at 2.6 a cell-year (inferred from about 150 to
200 cells), or none with ERA5-Land. Compute: an hour. Money: none. Ethan: two emails already drafted.

**First test.** A frozen-model backtest. Production's spill model and regional-v1, unchanged, on Southern 2020-23 and
Yorkshire 2021-23, lead 0 on archive rain. References: each overflow's own rate in the other years; "more than 10 mm".
Metric: Brier skill against the own rate, interval by overflow and week. **Pass:** interval wholly above 0 and level
between 0.9 and 1.1. Pass leads to the Accuracy line and to scoring each frozen candidate there. Fail leads to a
diagnosis by year, since a fail could be the monitors and not the model.

**Kill rule.** No permission from either company by 31 January 2027. Reopen with the EA's September to December 2026
file, which is the next unseen label set either way.

**Ethan's steps.**
1. Send the two existing drafts.

### 7. ANYWATER: a rain reading at every sampled bathing water, tested on Ireland and Wales

**What a swimmer gets.** At 240 Irish and 114 Welsh bathing waters, where the site shows a directory card and past
samples, a dated line on what samples there read after rain, and a "higher than usual after rain" reading if the
transfer test passes.

**New, already tried, or reversing.** Extends COASTAL-C1 (#696), which fits rain and season on England's coast and
backtests on 2012-21. It **reverses part of a recorded decision**: `docs/IRELAND-PLAN-2026-10.md` says the site
"cannot forecast … anywhere on the island of Ireland today, and it should not try yet". That was about a forecast
driven by overflows, and Ireland publishes no overflow data. A rain reading needs none. Bench read 1 showed rain and
season order samples at lakes with no overflow input, and the check above shows the same at rivers. It is still not a
sewage forecast and must not be worded as one. ROADMAP's line on the coast ("show it, not compete with it") stands:
this shows past samples by rain and makes no claim against any official forecast.

**Evidence it could work.** Read: on England's coast rain is the only input supported on top of site and month, and
the best Brier skill is 3.4% (COASTAL-BASELINES). That is weak for a chance over a line. Measured on inland seen rows:
rain and season alone give within-site rho 0.385 at rivers and 0.318 at lakes, at sites left out. Reported (agent
read): Scotland's 2012 signs were right or cautious on over 99% of days and showed "poor" on 36% of days that sampled
good; an Irish research system got 77% to 79% of decisions right at one site. Hoped: that order within a site carries
to another country's coast.

**Data.** Exists: 26,929 Irish samples at 240 waters since 2014 (CC BY 4.0) and Welsh samples (OGL v3), both already
shown as histories (#691). Missing: rain at those sample times. Northern Ireland's samples are HTML only.

**Cost.** Open-Meteo: about 6,000 weighted calls for Ireland alone at 2.6 a cell-year (inferred, 200 cells, 12 years),
which is not affordable. With the ERA5-Land bulk box widened to Ireland: none. Compute: minutes. Ethan: the same
Copernicus account.

**First test.** After C1's model is frozen and has passed its own 2012-21 read: score it unchanged on every Irish and
Welsh sample. No model has seen them. Metric: mean within-site Spearman correlation with the measured log10 count.
Reference: site and month. **Pass:** interval over sites and seasons wholly above 0.10. Pass leads to the after-rain
past-sample line on those cards and a wording proposal for a rain reading. Fail leads to the past-sample line only,
which makes no claim.

**Kill rule.** C1 fails its own read. Then no transfer is tried.

**Ethan's steps.** None beyond the Copernicus account. A public rain reading outside England is his decision later.

### 8. SHELLFISH: a coastal label that keeps a week's exposure

**What a swimmer gets.** Indirectly, a test of whether spills reach a stretch of coast at all, which single water
samples cannot give: only 1.5% of coastal samples pass 500.

**New, already tried, or reversing.** New. "Cefas" has no hit in the repository. Extends the coastal row, where
spills were not supported on top of site and month.

**Evidence it could work.** Reported (agent read Cefas's page): E. coli results for each representative monitoring
point download as CSV; "All data is published under the Open Government Licence". Reported, snippet only: 1992 to
2022, about monthly. The data.gov.uk record gives the licence as "Not set", so the two disagree. Hoped: that enough
points sit near bathing waters with spill records. The measure is E. coli in shellfish flesh, not water. It is not a
swimming measure and must never be shown as one.

**Data.** Missing: the count of points within 2 km of a listed coastal bathing water, and the licence conflict.

**Cost.** One request a point for the files. No Open-Meteo. Ethan: none unless the licence needs asking.

**First test.** A count first: points within 2 km of a coastal bathing water with 24 or more results in 2024-25. If
30 or more: does the number of spill hours within 5 km in the 7 days before a result order that point's results?
Reference: rain in those 7 days. **Pass:** spill hours add to rain with the interval above 0. Pass reopens spill
direction for the coast. Fail closes spill-only exposure for the coast until currents are tested.

**Kill rule.** Fewer than 30 points, or the licence is not open.

---

## Ranking

Value is to swimmers if the project works. Ethan's hours are my estimate [inferred]. "Chance it runs" is my judgement
of whether the first test can happen at all, not of whether it passes.

| Rank | Project | What changes for a swimmer | Ethan's hours | Chance the first test runs | Why this rank |
|---|---|---|---|---|---|
| 1 | RIVER-UNSEEN | A tested river estimate and a reading with a range at 85 river spots | 0.5 | High: the rows exist and are open | Largest unused label set, no one's permission, and it removes the bench's stated river limit |
| 2 | DENSE | Proof in real water in 2027, four times the EA's samples | 1 | Medium: rests on a release | One email. A pass or a fail is public either way. PAIRS is the fallback |
| 3 | DRY-DAY | The truth about dry days at rivers that read high without rain | 0.5 | High for the page line; medium for the index | The largest measured gap between page and samples. The first step needs no model |
| 4 | ALERTS-BY-EMAIL | An alert route for readers who cannot have push | 2 | High | Built already. Reach is the limit on everything else. Ranked below the top three because nothing measures demand |
| 5 | WINDERMERE-100 | A tested picture across one lake | 0.5 | Medium: rests on a licence | One email for about 1,000 samples on the lake with the most engaged readers |
| 6 | SPILL-UNSEEN | A spill forecast tested on unseen years | 0.5 | Low to medium: two companies must answer | Drafts exist. No change a swimmer sees at first |
| 7 | ANYWATER | A rain reading at 350 waters outside England | 0.5 | Medium: waits on C1 and ERA5-Land | Wide reach, weak expected signal on the coast |
| 8 | SHELLFISH | A test of spill reach on the coast | 0 | Unknown until counted | Cheap to count, indirect for swimmers |

One step unlocks three projects: the Copernicus account (RIVER-UNSEEN, ANYWATER, and SPILL-UNSEEN's rain). It is
also what #702 waits on.

## What needs Ethan, in one list

1. Create the Copernicus Climate Data Store account (20 minutes; unlocks 1, 6, 7 and #702).
2. Send the Yorkshire Water email (draft written, unsent).
3. Decide whether river bathing waters show dry and wet past samples beside the daily figure.
4. Decide whether an email address may be held before the ICO fee question is settled; if yes, switch email on.
5. Send the Freshwater Biological Association email (draft written, unsent).
6. Send the two existing Southern Water and Yorkshire Water drafts for event records.
7. Send the unsent 11 November follow-up to EA West Midlands.
8. Optional: the EA dry-day enquiry (draft written, unsent).

## Looked at and rejected, so the next session does not repeat it

| Idea | Why not now | What would reopen it |
|---|---|---|
| A site's own rate in the river model | Tested above on seen rows: no Brier gain with the season held out, worse forward to 2025 | A second unseen season, or a reason a site's level should hold between years |
| Illness reports as a label | The form is built and off (DESIGN, "Illness reports"). Published attributable risk is 3% to 5% of bathers above guide values (Wiedenmann 2006, agent read). Telling high-forecast swims from low at that rate needs swims in the thousands; the site has 1 push subscriber. Health data is special category and needs explicit consent and a DPIA (ICO, agent read) | A season with 2,000 or more logged swims, and a university partner for ethics review |
| An illness probability on the page | No service found states one [reported]. The dose-response studies are for other waters and for enterococci at sea or a German trial; applying them to a modelled E. coli estimate would be an unvalidated conversion, which the workflow forbids for guidance | A UK cohort with measured concentrations. None was found |
| The EA's daily sensor readings as labels | Tried privately 22 October: Ludlow ranked, Shrewsbury not; readings are raw and unconverted | The EA's answer on conversion (draft unsent). Ironbridge's 2026 readings |
| Evidence packs for bathing-water applicants | Already built: `scripts/site_profile.py` (MARKETS task T8), with an email to the applicants' support team sent 10 October | An applicant asks for something the profile lacks |
| Buying or borrowing a rapid bacteria sensor | A handheld unit is about £2,785 and £15 a test; a 15-minute kit is £25 a test and reads endotoxin, not E. coli (River Action guide, agent read). No spending until a written commitment | A funder or a partner that owns one |
| Turbidity or ammonium as a live proxy | Two river spots have a sonde upstream (#687). Published fits vary from R² 0.78 to near zero by site and storm [reported]. Section 82 monitors measure no bacteria and are due 2030 to 2035 | Yorkshire Water's sensor data beside its lab samples, which would test the proxy at 20 sites |
| A hydrodynamic model of Windermere | No open model found; lake wind and near-field variants failed or closed. Heavy for one lake | WINDERMERE-100 fails in a way that points to circulation, and a partner has a model |
| A neural or sequence model for spills | Archived with reasons (neural challenger, multi-year). The limit is labels, not model class | A new label source: SPILL-UNSEEN or the EA's late-2026 file |
| Annual returns 2020-23 as an unseen yearly target | Tests yearly level only; the model's covariate comes from the return before, so persistence would explain most of it | A model whose claim is a yearly figure |
| Transfer tests on US, New Zealand or French samples | No UK swimmer benefits soon. Licences and per-sample content unconfirmed [reported, snippets] | ANYWATER passes and a second out-of-country set is wanted |
| Auditing the EA's coastal forecast in public | Already measured on seen data: it caught 45 of 170 at its own sites (COASTAL-BASELINES). Small counts a site, and a public claim needs C1's held-out read first | C1's 2012-21 read |
| Citizen kit results (river trusts, anglers) | Most measure nutrients, not bacteria [reported]. One citizen results site has E. coli with unread terms | Its terms, read |
| A human-marker determinand in the archive | Determinand 5040 ("HH2 genetic marker") exists in the code list; 2025 has no rows [measured]. Other years not checked | SOURCE-ID's record, which could check 2012-24 in 13 requests |
| A satellite lake temperature record | Not confirmed which UK lakes it covers [reported, snippet] | LAKE-TEMP's per-lake offset needs lakes with no EA readings |
| The five directions scoped on 1 November | Not re-proposed. DRY-DAY extends SOURCE-ID with a mechanism. RIVER-UNSEEN extends the bench. Nothing here touches CATCH-SIM, LAKE-ECO or RESTORE | |

## What others do, and what it means here

From the outside survey [reported; "read" where the agent opened the source]:

- Most operating services use regression or a rain threshold. Where skill is published it is high specificity and
  low sensitivity: California's ten beaches had median sensitivity 0.5 against 0 for the old method (read); Chicago's
  model had 93% accuracy with sensitivity 0.11 (read). Accuracy alone hides misses.
- No operator found publishes skill for inland river forecasts that could be copied as a number. The strongest inland
  result is Berlin's (read).
- No service found shows a concentration range or an illness probability. A river reading with a range would be new.
- WHO's advice to the EU says a model used to inform the public should explain 50% to 60% of variance (read). Within-
  site rank correlations of 0.3 to 0.4 are far below that. That is a reason to word any reading as order within a
  site, as the lake line does, and not as a prediction of the count.
- Regulation: from 21 November 2025, bathing seasons can be set by site; 13 new bathing waters opened on 15 May 2026,
  seven on rivers (read). The duty to publish emergency overflow discharges within an hour is law but not in force
  (read).

## What this record does not do

- It runs none of the first tests. Each needs its statement pushed first.
- It does not rank these against the November and December reads, which come first.
- It did not count the archive's river samples nationally, read any Yorkshire Water, Windermere or shellfish result,
  or contact anyone.
- It does not change the register's rows for the projects it extends.

## Sources

Repository: `AGENTS.md`, `docs/RESEARCH-WORKFLOW.md`, `docs/RESEARCH-RECOVERY-2026-10.md`,
`docs/AMBITIOUS-RESEARCH-SCOPING-2026-11.md`, `docs/SOURCE-INVENTORY-2026-11.md`, `docs/COASTAL-BASELINES-2026-11.md`,
`docs/PE-SOURCES-2026-10.md`, `docs/EARLIER-SPILL-HISTORY-2026-10.md`, `push/README.md`; on their branches,
`docs/BACKTEST-BENCH-2026-11.md`, `docs/BENCH-READ-LAKE-RANGE-2026-11.md`, `docs/ERA5-LAND-BULK-RAIN-2026-11.md`,
`docs/AFTER-RAIN-SAMPLES-2026-11.md`. `docs/DESIGN.md`, `docs/ROADMAP-2026-10.md`, `docs/EXPANSION-2026-10.md`,
`docs/MARKETS-2026-10.md` and `docs/ORGANISER-PIVOT-2026-10.md` were read in full by an agent, and I read the DESIGN
sections cited here.

Web pages opened by me on 15 November 2026 (all in the request log):

- Environment Agency Water Quality Archive API, https://environment.data.gov.uk/water-quality/api/swagger
- Yorkshire Water, "Yorkshire Water begins real time AI water quality project", 22 May 2026,
  https://www.yorkshirewater.com/news-media/news-articles/2026/yorkshire-water-begins-real-time-ai-water-quality-project/
- Environment Agency, "Daily bathing water testing expands across Shropshire", 28 August 2025,
  https://www.gov.uk/government/news/daily-bathing-water-testing-expands-across-shropshire

Opened by the agents, not by me: the Berlin, California, Chicago, Sydney, SEPA, WHO, ICO, Cefas and Freshwater
Biological Association pages behind each [reported] line. Their URLs are in the PR description.
