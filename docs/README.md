# docs

Every file in this folder, grouped by kind. A test file states its conditions before the run and adds its
results below a line at the end. The verdict given here is a short form of that results section; the file
itself is the record. CSV and JSON files are the result tables of the test they are listed under.

## Plans and reviews

- [ROADMAP-2026-10.md](ROADMAP-2026-10.md): the roadmap of 3 October 2026. More spots, what makes the app useful,
  and PR-sized tasks.
- [REVIEW-2026-10-16.md](REVIEW-2026-10-16.md): a review of the live site, the pipeline, the model and open data
  not yet used, with tasks an agent can take alone.
- [EXPANSION-2026-10.md](EXPANSION-2026-10.md): the coastal, Welsh and Scottish directories, the scientific review
  package, and the plan for a May to September 2027 evaluation.
- [MARKETS-2026-10.md](MARKETS-2026-10.md): five groups besides swimmers, what to build for each, and the paid
  pilots (section 6a).
- [ORGANISER-PIVOT-2026-10.md](ORGANISER-PIVOT-2026-10.md): how SwimSignal starts charging activity centres and
  event organisers while swimmers stay free.
- [PILOT-SESSIONS.md](PILOT-SESSIONS.md): how to run a paid pilot's briefings by hand with `scripts/briefing.py`.
- [HOSTING-MOVE-2026-10.md](HOSTING-MOVE-2026-10.md): moving the site from GitHub Pages to Cloudflare Pages.
  Limits, the workflow change, checks after the switch, rollback.
- [IRELAND-PLAN-2026-10.md](IRELAND-PLAN-2026-10.md), [SCOTLAND-PLAN-2026-10.md](SCOTLAND-PLAN-2026-10.md),
  [WALES-PLAN-2026-10.md](WALES-PLAN-2026-10.md): one plan per nation. What the sources publish, measured
  coverage, how a forecast would be validated, draft emails and tasks. Plans only.
- [COMPREHENSION-TEST-2026-10.md](COMPREHENSION-TEST-2026-10.md): a plan for 8 to 10 moderated swimmer sessions,
  October to November 2026. Not yet run.
- [SWIMMER_TESTING.md](SWIMMER_TESTING.md): the earlier swimmer test plan. The comprehension test replaces its
  tasks and keeps its recording rules.
- [SWIMSIGNAL_REVIEW.md](SWIMSIGNAL_REVIEW.md): review notes for the SwimSignal rebrand: scope, compatibility,
  evidence limits, checks.

## Tests stated before the run

### The spill model

- [NINE-COMPANY-MODEL-TEST-2026-10.md](NINE-COMPANY-MODEL-TEST-2026-10.md): a spill model trained on nine
  companies. **Not adopted:** conditions 1, 3 and 4 fail. Tables: `-coverage.csv`, `-events.csv`,
  `-reliability.csv`, `-scores.csv`.
- [NEURAL-CHALLENGER-TEST-2026-10.md](NEURAL-CHALLENGER-TEST-2026-10.md): a neural net against the boosted
  trees. **Not adopted:** conditions 1 to 4 fail (Brier 0.0372 against 0.0362). Tables: `-checks.json`,
  `-differences.csv`, `-leads.csv`, `-reliability.csv`, `-scores.csv`, `-training.csv`.
- [MULTI-YEAR-TEST-2026-10.md](MULTI-YEAR-TEST-2026-10.md): more years of training data. **Question 1 no** (the
  network does not beat the trees). **Question 2 yes** (the trees beat the single-year model), but most of the
  gain comes without the extra years. Tables: `-checks.json`, `-covariates-filled.csv`, `-coverage.csv`,
  `-differences.csv`, `-reliability.csv`, `-scores.csv`, `-training.csv`.
- [COVARIATE-YEAR-TEST-2026-10.md](COVARIATE-YEAR-TEST-2026-10.md): whether the site covariates carry their
  return year's wetness. **Question 1 no, question 2 no.** The 2026 confirmation waits for the 2026 files. Tables:
  `-checks.json`, `-differences.csv`, `-rain.csv`, `-reliability.csv`, `-scores.csv`, `-shifts.csv`,
  `-training.csv`.
- [LIVE-STATUS-FEATURE-TEST-2026-10.md](LIVE-STATUS-FEATURE-TEST-2026-10.md): the overflow's own spill status as
  an input. **All five conditions pass at leads 0 to 4 on 2025.** Not deployed: it needs a confirmation on
  SwimSignal's own polls. Tables: `-checks.json`, `-differences.csv`, `-leads.csv`, `-persistence-2024.csv`,
  `-reliability.csv`, `-scores.csv`, `-spells-2024.csv`, `-subsets.csv`.
- [LIVE-STATUS-SHADOW-TEST-2026-10.md](LIVE-STATUS-SHADOW-TEST-2026-10.md): those candidates run in shadow on
  the polls, with a fallback where status is missing. **No result yet:** a 28-day live window.
- [LEAD-CALIBRATION-B-TEST-2026-10.md](LEAD-CALIBRATION-B-TEST-2026-10.md): lead calibration, option B. **No
  result yet:** the map is fitted; the live window is 18 October to 14 November 2026, read on or after
  16 November. The map: `-map.json`.
- [LIVE-RECALIBRATION-TEST-2026-10.md](LIVE-RECALIBRATION-TEST-2026-10.md): two corrections for live
  over-forecasting. **Neither passes,** in the first run and the rerun.
- [DRY-WEATHER-SPILLS-TEST-2026-10.md](DRY-WEATHER-SPILLS-TEST-2026-10.md): overflows that spill in dry weather, and
  whether that history predicts what the spill model misses. **Question 1 no** (the 2024 rate loses to production and
  the flat rate); **Question 2 fails all four conditions.** Top-overflows table and a page-note proposal. Tables:
  `-checks.json`, `-companies.csv`, `-overflows.csv`, `-q1-differences.csv`, `-q1-scores.csv`, `-q2-differences.csv`,
  `-q2-leads.csv`, `-q2-reliability.csv`, `-q2-scores.csv`, `-q2-subsets.csv`, `-top.csv`, `-y2026.csv`.
- [ENSEMBLE-RAIN-TEST-2026-11.md](ENSEMBLE-RAIN-TEST-2026-11.md): ensemble rain for the listed spots. **No
  result yet:** the window runs 23 October to 19 November 2026, read on or after 21 November.

### Transport and the E. coli estimate

- [TRANSPORT-FIT-TEST-2026-10.md](TRANSPORT-FIT-TEST-2026-10.md): river speed, T90 and the dilution exponent
  fitted to E. coli samples. **All four conditions hold:** 0.2 m/s, 72 h and 0.5, the defaults now.
- [TRANSPORT-FIT-2-TEST-2026-10.md](TRANSPORT-FIT-2-TEST-2026-10.md): a wider grid past that fit's corner.
  **Conditions 1 and 2 fail;** the settings stay.
- [URBAN-DILUTION-TEST-2026-10.md](URBAN-DILUTION-TEST-2026-10.md): dilution by urban area per overflow.
  **Fails all three conditions;** the default stays `length`.
- [URBAN-DILUTION-DIAGNOSIS-2026-10.md](URBAN-DILUTION-DIAGNOSIS-2026-10.md): why it failed, as hypotheses
  stated first. **Answer:** the built-up-area shares point spill size the wrong way at the overflows that matter.
- [SPILL-SIZE-TEST-2026-10.md](SPILL-SIZE-TEST-2026-10.md): spill hours as each overflow's size. **Fails**
  (conditions 1 and 4); stays off.
- [PE-SIZE-TEST-2026-10.md](PE-SIZE-TEST-2026-10.md): consented dry weather flow as each overflow's size
  (population equivalent is not in the source). **Fails** (conditions 1 to 4); stays off.
- [DIEOFF-WEATHER-TEST-2026-10.md](DIEOFF-WEATHER-TEST-2026-10.md): sunlight and temperature in die-off. **Both
  questions fail;** nothing adopted.
- [FARM-PRESSURE-TEST-2026-10.md](FARM-PRESSURE-TEST-2026-10.md): the Environment Agency's farm-pollution flag
  per water body as an E. coli input. **Fails conditions 1, 2, 5 and 6;** nothing adopted. Scores: `-score.json`.
- [LAKE-PATH-TEST-2026-10.md](LAKE-PATH-TEST-2026-10.md): a lake on the way at lake speed, with lake dilution.
  **All five conditions hold;** switched on, then replaced by `residence_spill`.
- [LAKE-RESIDENCE-TEST-2026-10.md](LAKE-RESIDENCE-TEST-2026-10.md): a lake on the way as a well-mixed lake with
  a residence time. **All seven conditions hold;** a candidate for the default.
- [LAKE-RESIDENCE-SPILL-2026-10.md](LAKE-RESIDENCE-SPILL-2026-10.md): the same at spill-time flow. **All seven
  conditions hold;** the default.
- [LAKE-DISTANCE-2026-10.md](LAKE-DISTANCE-2026-10.md): distance within a lake spot's own lake measured through
  the water. **All seven conditions hold;** `water` is the default.
- [LAKE-DIRECTION-TEST-2026-10.md](LAKE-DIRECTION-TEST-2026-10.md): leaving out water that enters a lake below
  the spot. **All seven conditions hold, but the default stays `any`:** at every sampled lake it changes, the
  within-site match fell.
- [EVAL-PINS-TEST-2026-10.md](EVAL-PINS-TEST-2026-10.md): the E. coli evaluation placing spots as the site does.
  **The recommendation stands:** the evaluation uses the site's pins.
- [ECOLI-REFIT-SITE-PINS-2026-10.md](ECOLI-REFIT-SITE-PINS-2026-10.md): the E. coli model refitted on the site's
  pins, and rerun after a network fix. **Every stated check holds.**
- [MISSING-RAIN-CHECK-2026-10.md](MISSING-RAIN-CHECK-2026-10.md): rain cells missing from the E. coli validation
  cache, the refresh and the reruns. **Every expectation held.**
- [GLOFAS-CHECK-2026-11.md](GLOFAS-CHECK-2026-11.md): GloFAS river flow against EA gauges. **Passes narrowly:**
  fit for the two model tests it names, not as a flow in m³/s. Tables: `-cells.csv`, `-gauges.csv`, `-spots.csv`.

### Map clicks

- [ANYPOINT-SIDE-ARM-2026-10.md](ANYPOINT-SIDE-ARM-2026-10.md): a click on a side arm takes the river the arm
  leaves, first try. **Fails check 5;** stays off.
- [ANYPOINT-SIDE-ARM-MOST-2026-10.md](ANYPOINT-SIDE-ARM-MOST-2026-10.md): second try, the named channel with the
  most network. **Fails check 5;** stays off.
- [ANYPOINT-SIDE-ARM-FLOOR-2026-10.md](ANYPOINT-SIDE-ARM-FLOOR-2026-10.md): third try, with a 10% floor. **Fails
  check 5;** stays off.
- [ANYPOINT-SIDE-ARM-LENGTH-2026-10.md](ANYPOINT-SIDE-ARM-LENGTH-2026-10.md): fourth try, with a 2 km limit on the
  arm. **Fails check 2;** on the rerun check 2 passes and check 3 fails. Stays off.
- [ANYPOINT-SIDE-ARM-CLICKS-2026-10.md](ANYPOINT-SIDE-ARM-CLICKS-2026-10.md): fifth try, the new rule for clicks
  only. **Checks 1, 2, 4, 5 and 6 pass; check 3 fails** on one spot whose link varies from run to run. The rule
  is in `transport.head_of_arm`.
- [ANYPOINT-LAKES-2026-10.md](ANYPOINT-LAKES-2026-10.md): what a click by a lake means, page against API.
  **Option C built:** all 600 shore clicks agree.

### Overflow positions

- [OVERFLOW-POSITIONS-2026-10.md](OVERFLOW-POSITIONS-2026-10.md): checked joins and a rule for overflows whose
  two positions disagree. **3 joins added; 37 of 166 conflicts settled,** 128 open; no listed spot changes.
  Cases: `-cases.csv`.
- [OVERFLOW-SEA-OUTFALLS-2026-10.md](OVERFLOW-SEA-OUTFALLS-2026-10.md): seven sea outfalls against the EA's
  bathing-water features. **3 of 7 settled,** 4 open. Cases: `-cases.csv`.
- [OVERFLOW-SPOT-CONFLICTS-2026-10.md](OVERFLOW-SPOT-CONFLICTS-2026-10.md): the three open conflicts that change a
  listed spot. **1 of 3 settled** (South Lane, Ash stays at its live position); nothing moves.

### The coast

- [SEA-CURRENTS-SCOPING-2026-10.md](SEA-CURRENTS-SCOPING-2026-10.md): whether sea currents carrying an overflow's
  water towards a beach can be tested. **Not yet:** 32,874 coastal samples exist, but there is no coastal model to
  add currents to. A staged plan, if the coast becomes a priority.
- [UKMCAS-ORDER-DRAFT-2026-10.md](UKMCAS-ORDER-DRAFT-2026-10.md): the Met Office marine data order form and email,
  drafted for Ethan. **Not sent;** wait unless the coast becomes a priority.

### The 2027 season

- [PREREGISTRATION-2027.md](PREREGISTRATION-2027.md): how the May to September 2027 forecasts will be scored,
  fixed before the season. **No result until after the season.**

## Checks and records

- [MODEL-PROVENANCE-2026-10.md](MODEL-PROVENANCE-2026-10.md): why `train.py` did not rebuild main's spill model. Layer 2
  was fitted at recency 0.25, shown by reproducing every stored offset exactly; `train.py`'s default now matches.
- [ANYPOINT-LINES-2026-10.md](ANYPOINT-LINES-2026-10.md): map clicks answered differently by page and API because
  the page used lines simplified to 30 m. The build now writes full lines.
- [LIVE-VS-EDM-LABELS-2026-10.md](LIVE-VS-EDM-LABELS-2026-10.md): live spill labels against the EA's start/stop
  files. No day is in both sources yet; three indirect checks say the labels are not the main cause.
- [UPGRADED-OVERFLOWS-2026-10.md](UPGRADED-OVERFLOWS-2026-10.md): Ilkley's upgraded storm overflows in the
  forecast. Recommends a note on the spot page now and a stated test before the 2027 freeze. Tables:
  `-levels.csv`, `-log.csv`, `-lta-curve.csv`, `-observed.csv`, `-silence.csv`, `-since-last.csv`,
  `-upstream.csv`, `-week.csv`.

## Data sources

- [EARLIER-SPILL-HISTORY-2026-10.md](EARLIER-SPILL-HISTORY-2026-10.md): event-level spill records before 2024.
  Northumbrian and Wessex from 2020, Thames from December 2022; none found for five other companies.
- [SOURCE-SCOTTISH-WATER-2026-10.md](SOURCE-SCOTTISH-WATER-2026-10.md): licence and terms of Scottish Water's
  overflow data. The annual files are OGL v3.0; the live API's licence has no name.
- [PE-SOURCES-2026-10.md](PE-SOURCES-2026-10.md): sources looked for a population equivalent per overflow, and
  why that work is parked.

## Design

- [DESIGN.md](DESIGN.md): the design system. Type, colour, words, layout, and the decisions behind each part of
  the pages.
- [DESIGN-HANDOFF.md](DESIGN-HANDOFF.md): a design handoff of 2 October 2026. Why the site read as generated,
  and the "field guide" direction.

## Handoffs

- [HANDOFF-2026-10-04.md](HANDOFF-2026-10-04.md): state of main on 4 October 2026, checks to run first, next
  tasks.
- [HANDOFF-2026-10-12.md](HANDOFF-2026-10-12.md): state of main on 12 October 2026, the fixes of 11 and 12
  October to check, and how to improve each.
