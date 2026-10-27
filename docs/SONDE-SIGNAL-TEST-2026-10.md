# EA sonde readings in the river E. coli estimate: the test, stated before any score

Written 27 October 2026. **Not approved and not run.** Ethan approves before any readings fetch or score. No E. coli
value has been read for this test, and no sonde reading has been fetched. Results go below the line at the end.
Nothing above it changes after a result is seen.

**The short version.** On station metadata alone, at most 71 of the 907 river rows, at 4 bathing waters, can have a
turbidity reading from a sonde that counts. The gate below needs 150 rows at 4 sites. So, as stated, the run stops at
its pre-gate, before any readings are fetched, and decides nothing. The statement is complete anyway, so that it can
be run on a larger row set later (see "What follows").

## Request caps, written before any fetch

Committed in 492b737 and pushed at 01:02:08 UTC, before the first request (01:02:15 UTC). Unchanged since.

- **Now (preparation):** at most 150 metadata requests to the EA Hydrology API (`environment.data.gov.uk/hydrology`).
  Metadata means station, measure and reference pages: names, places, dates and counts. No `readings` request is
  made now.
- **Pace:** one request in flight, at least 1.5 s after the previous one ends. Another worker may query the same API
  tonight, so nothing here runs in parallel, and a 403, 429 or 5xx answer is not retried in a loop: at most one retry
  after 10 s, and the request counts twice.
- **Ledger:** every request is logged (URL, status, bytes, start and end time). The count goes in "Seen before
  writing".
- **Scoring time:** the readings fetch is sized below as requests × pace, and capped there, before it runs.

## The question

Does a sonde's reading on the day, as it would have been published before the sample, add to the live river E. coli
estimate? Primary: **turbidity**. Secondary: **ammonium**.

Why it might. Rain and overflow exposure are the live model's day signals, and both are modelled. A turbidity rise is
a measurement of the water itself: runoff and resuspended sediment carry faecal bacteria. Ammonium is a sewage marker
(`docs/OVERFLOW-DATA-SOURCES-2026-10.md`, 2.4). Why it might not. Turbidity rises with any rain, which the model
already has. Most deployments are short and away from bathing waters.

## What was ruled out before, and why this is different

- The review of 16 October ruled out the EA Hydrology **blue-green algae** sensors: "105 measures, zero readings in
  2026" (`docs/REVIEW-2026-10-16.md`, section 4). That is a different property.
- `docs/OVERFLOW-DATA-SOURCES-2026-10.md` (2.4) found the ammonium and oxygen series live (78 ammonium series
  reporting on 25 October) and said "Any model use needs a stated test. Coverage is thin and the stations move." This
  is that test.

## Data and licence

- **Source.** EA Hydrology API, station listings (`/hydrology/id/stations.json?observedProperty=...`) and, at scoring
  time only, readings (`/hydrology/id/measures/{measure}/readings.json`).
- **Licence, read 27 October 2026.** Every JSON answer's `meta` block names `"licenseName": "OGL 3"` and links the
  Open Government Licence v3. The reference page's footer: "All content is available under the Open Government
  Licence v3.0, except where otherwise stated". Credit, if anything is ever shown: "Contains Environment Agency data
  licensed under the Open Government Licence v3.0."
- **A mismatch, not fixed here.** The site's terms page credits its existing Hydrology API uses (flows, water
  temperature) as "All rights reserved". That is stricter than the licence and does no harm, but it is not what the
  API states. Ethan's call.
- **Property names, checked against the API's reference page.** `observedProperty` takes `dissolved-oxygen`, `fdom`,
  `bga`, `turbidity`, `chlorophyll`, `conductivity`, `temperature`, `ammonium`, `nitrate`, `ph` (also `waterFlow`,
  `waterLevel`, `rainfall`, `groundwaterLevel`). The page lists turbidity as "15min instantaneous NTU" and ammonium as
  "15min instantaneous mg/L".
- **The measures used.** In the listings, a sonde's turbidity measure is `<station>-turb-i-subdaily-ntu` (parameter
  `TURBIDITY`, period 900 s) and its ammonium measure `<station>-amm-i-subdaily-mgL` (`AMMONIUM`, 900 s). Only these
  count (`sondes.parse_stations`).
- **Times.** The API writes times without a zone. They are UTC (`src/dipcast/ingest/water_temperature.py`, checked
  3 October 2026 against the flood-monitoring API).

## Which sondes count for a spot (metadata only)

The spots are the 20 river bathing waters with monitored overflows upstream: the river rows of the live model's
validation set. A sonde counts for a sample at a spot when all four hold (`scripts/sonde_signal_eval/sondes.py`):

1. **Same river by name.** The sonde's river, read from its label (`RIVER_PLACE_<team>_<YYYYMM>`) or `riverName` by
   `water_temperature.parse_label`, shares a distinctive word with the spot's watercourse (`names.same_river`). This
   is the site's own rule for its water-temperature line.
2. **Within 15 km in a straight line** (the same rule's `MAX_KM`).
3. **Joined along the river.** `water_temperature.river_relation` on the river network (`river_network.pkl` in the
   run's root) places both on the same side of the tidal limit, with the sonde **upstream at most 20 km along the
   river**, or **downstream at most 2 km**. A downstream sonde reads water that has passed the spot, so only
   one very close to it counts.
4. **Deployed on the sample's day:** `dateOpened` ≤ day ≤ `dateClosed` (or open). A station whose `dateClosed` is
   before its `dateOpened` (E04662A: opened 5 May 2026, "closed" 1 January 1970) is treated as open; its readings
   decide.

**Which one is used.** A sample tries its sondes in this order: upstream before downstream, then the shorter distance
along the river, then station id. The first with a valid feature is used. One sonde per sample.

## The feature

For a sample at time t, the cut is **t\* = t − 6 h** (the publication lag). Only readings stamped at or before t\*
are read. (`scripts/sonde_signal_eval/feature.py`.)

- **Now level:** the median of the readings in (t\* − 2 h, t\*]. At least 4 of the 8 fifteen-minute slots.
- **Baseline:** the median of that sonde's readings in (t\* − 2 h − 30 days, t\* − 2 h]. At least 672 readings (7
  days' worth).
- **Feature:** ln(max(now, floor)) − ln(max(baseline, floor)), clipped to ±3. Floors: 0.1 NTU, 0.01 mg/L.
- **A reading counts** when its value is finite, inside 0 to 4,000 NTU (0 to 100 mg/L for ammonium), and its quality
  is not "Suspect" or "Missing". Duplicate stamps keep the last.
- **Why 6 h.** No publication lag was measured for these series: that needs readings, and none were fetched. The site
  treats a sonde reading up to 24 h old as current (`flows.MAX_READING_AGE_H`). The forecast a swimmer sees at noon comes from a build a few
  hours earlier. 6 h is a guess on the cautious side of "a few hours" [inferred]. **Sensitivity: t\* = t − 24 h**,
  scored and labelled in full, deciding nothing.

## Missing data and the fallback

- A river row with no counting sonde, or no valid feature at any of them, gets **0.0** ("as usual"). Lakes get 0.0.
  The candidate then rests on its other inputs.
- Reported: the share of river rows with a reading (coverage), by property and lag, and the stations used.
- The fallback is part of the candidate. The check on **all river rows** (below) is how it is judged.

## Rows

- **The live river model's rows:** `scripts/train_ecoli_sm.py`'s, from `soil_moisture_eval/diagnostics.rows_q1`: EA
  samples at inland bathing waters with overflows upstream, 2024 to 2026, with forecast rain and exposure at every
  lead. 1,502 rows, 907 river and 595 lake (`ecoli_model_sm.json`, `meta`).
- **Inputs:** today's seven plus `sm`, as `train_ecoli_sm.py` builds them, plus `sonde`.
- **Fitted on all 1,502 rows**, rivers and lakes, as the live river model is. **Scored on river rows only.** The site
  uses this model for rivers only.
- **Root:** the soil-moisture rivers test's frozen data folder (`docs/SOIL-MOISTURE-RIVERS-TEST-2026-11.md`), which
  holds `ecoli_model_sm.json`'s inputs.

## Hold-outs

- **Primary: leave one site out (LOSO).** Each bathing water is predicted by models fitted without it. This matches
  the promise of an estimate at a spot the model never saw.
- **Reported: leave one year out (LOYO).** Most covered rows fall in one year per site, so LOYO mostly tests a site's
  own sonde against other years' fits.
- **Forward in time is not computed.** The covered rows sit in 2024 (Ilkley), 2025 (Knaresborough, Wolvercote) and
  2026 (Fordingbridge). A fit on earlier years would see almost no covered row.

## Reference and candidate

- **Reference:** the production river model's inputs (`FEATURES` + `sm`, `soil_moisture_eval/leads.CAND`), refitted in
  each fold. **Face check:** fitted on all rows, its coefficients equal `ecoli_model_sm.json`'s to 1e-9, or the run
  stops.
- **Candidate:** the same inputs plus `sonde` (turbidity, t − 6 h), refitted in each fold.
- **Secondary candidate:** the same with ammonium in place of turbidity.

## The primary comparison

- **Rows:** river rows with a valid turbidity feature at t − 6 h ("covered rows").
- **Score:** Brier over 900 cfu/100 ml. **Gain** = Brier(reference) − Brier(candidate), both from LOSO.
- **Interval:** 95%, cluster bootstrap over (bathing water, ISO week): `train_ecoli.cluster_bootstrap`, 2,000 draws,
  seed 0.
- **Label:** the near-miss labels of the 26 October addendum to `docs/LAKE-ECOLI-LINE-TEST-2026-10.md`, in its order,
  with its note: "Harm" cannot come first in that order, so "a check labelled harm" means "Possible harm" or "Harm".
  Two cases fit no label in the addendum's order: d > 0 with L ≤ −H and U < B, and d < B with L > 0 and U ≥ B. They are
  reported as "Unlabelled" and are not adopted. (`scripts/sonde_signal_eval/labels.py`.)

### B and H, from predictions alone

**B is the Brier gain if 5% of forecasts each moved one band and the moved forecast were right.**

Working:
- Bands are cut at `ECOLI_CUTS` = 0.10, 0.25, 0.50 (`src/dipcast/site/levels.js`). Their mid-points are 0.05, 0.175,
  0.375 and 0.75.
- For a forecast p, the one-band move p′ is the mid-point of the adjacent band on the side of the nearer cut (the only
  adjacent band for the first and last bands).
- If p′ is the true chance, the expected Brier score of p exceeds that of p′ by (p − p′)². That needs no outcome.
- **B = 0.05 × mean over covered rows of (p − p′)²**, where p is the frozen production model's prediction
  (`ecoli_model_sm.json`, no refit, `sm` held in its range). **B is never below 0.0005**, the margin the soil-moisture
  leads test used. **H = B**, the largest H the addendum allows.
- Illustration, not the margin: if every covered forecast were 0.20, p′ = 0.375 and B = 0.05 × 0.175² = 0.0015. If
  every one were 0.40, p′ = 0.75 and B = 0.05 × 0.35² = 0.0061. If every one sat at 0.10 or 0.11, B would be 0.00015,
  so the floor of 0.0005 applies.
- Why 5%: one forecast in twenty moving one band is the smallest change a regular swimmer at one spot would notice in
  a season of weekly visits (about one visit) [a judgement, not measured].
- B is computed at run time before any comparison, from predictions only, and written to the output before the
  primary gain.

## The placebo

- Each covered sample reads its sondes at a time shifted by a whole number of weeks: k from {2, 3, 4, 5, 6} with a
  random sign. The shifted day must stay in 1 May to 30 September of the same year. Up to 50 tries per sample, else no
  placebo feature (0.0). (`scripts/sonde_signal_eval/placebo.py`.)
- The feature is rebuilt at the shifted time by the same rules, from the same sondes, with the same lag. It keeps each
  sonde's level and season and loses the day.
- 200 draws, `numpy.random.default_rng(draw)`. Each draw: LOSO candidate predictions, Brier gain on the covered rows.
- **rank p** = (1 + number of placebo gains ≥ the real gain) ÷ 201.

## The gate

Checked before any comparison is computed. If it fails, the run writes counts only and stops.

- **Pre-gate, before any readings fetch:** with rule 3 applied to the frozen station listing, the bathing waters'
  upper bounds of covered rows must sum to at least 150, at at least 4 sites. Otherwise nothing is fetched.
- **Gate, after the fetch:** at least **150 covered river rows**, at **4 or more bathing waters**, with **15 or more
  over 900**.
- **Ammonium** has the same gate on its own covered rows. If it fails, the ammonium arm reports counts only.
- **Why these numbers.** 150 is a sixth of the river rows. LOSO needs covered rows at several sites, so that a held-out
  site's coefficient comes from others. 15 events is the floor below which a Brier gain on a few hundred rows is mostly
  noise [a judgement]. No power calculation backs them: no finished test gives a per-cluster spread for a feature like
  this one. The gate is a floor, not a power claim.
- **Disclosed:** the gate numbers were in my working notes before the coverage counts below were made, but they were
  written into files after. Read them as chosen after the counts. Their only effect on this data is to stop the run.

## What decides

The test **passes** if all three hold:
1. The primary comparison is labelled **"Better"**.
2. **Placebo:** rank p ≤ 0.05.
3. **All river rows** (covered and fallback, LOSO): not labelled "Possible harm" or "Harm", with the same B and H.

**"Promising, not shown"** on the primary, with 2 and 3 holding, opens the addendum's forward step: the candidate
frozen by file hash, logged in shadow and not shown, judged only on samples after the shadow starts, with the same B
and H. Its power is computed before the window, as the addendum requires.

Anything else: not adopted. This PR stays a record.

**Reported, deciding nothing:**
- coverage by property and lag; stations used;
- the ammonium arm (if its gate passes), labelled with its own B (same working) and H;
- t − 24 h, labelled;
- LOYO on covered rows, labelled;
- per bathing water: covered rows and both Brier scores;
- on covered rows, for both models: mean forecast against the observed rate, and the miss rate and false-alarm rate
  at the High risk line (0.25);
- AUC and its interval (from `cluster_bootstrap`).

**Before Ethan is asked to adopt (the addendum's list), stated now:**
- *Coverage:* the share of live river spot-days with a counting sonde is reported. The fallback is judged by check 3.
- *Calibration:* on covered rows, the candidate's mean forecast is within 0.02 of the observed rate, or no further from
  it than the reference's.
- *Warning line:* at 0.25, the candidate's miss rate and false-alarm rate are each no more than 0.05 above the
  reference's.
- *Groups:* no bathing water with 14 or more covered rows has a candidate Brier more than 10% above the reference's.
- *Resources:* no Open-Meteo call. Live use would need one Hydrology readings request per build, as the temperature
  line makes now. OGL v3.

## Scoring-time fetch, sized now

- **Station listings:** 2 requests, frozen for the run.
- **Readings:** one request per matched measure and sample year, 1 April to 30 September (the 30-day baseline before
  May, and room for the placebo's shifts), `_limit` 100,000. On the prep counts: 8 sondes cover a sample, each in one
  year, for 2 properties: **16 requests**, about 17,600 rows each, about 281,000 rows in all.
- **Cap: 40 requests** in all, retries included. **Pace:** 1.5 s between requests, one in flight. At up to 10 s per
  answer, 40 requests take at most about 8 minutes.
- If the plan exceeds the cap, nothing is fetched (`fetch.py`).
- Readings are kept outside git and never committed.

## What I expect, stated now

- **The run stops at the pre-gate.** On metadata, the most covered rows possible are 71 at 4 sites: Wharfe at
  Cromwheel 20 (2024), Nidd at Knaresborough 20 (2025), Wolvercote Mill Stream 14 (2025), Avon at Fordingbridge 17
  (2026). The gate needs 150.
- **If it ran on these rows anyway,** I would expect "Too uncertain": a few dozen rows at 4 sites, in single years,
  give an interval far wider than B.
- **On the signal itself** [inferred]: turbidity on the day will mostly repeat rain, which the model has. Any gain
  would come from rain the forecast missed, or from sediment stirred by flow alone. Ammonium near these spots will
  rarely move far from its baseline in summer, except below works.

## The display-only idea (NOT tested here)

A line on a spot page, "Water unusually murky at <sonde> (<place>, <km> upstream)", when a counting sonde's latest
turbidity is well above its own 30-day median. That is an observation beside the forecast, like the temperature line,
never an input. It needs its own decision on wording, thresholds and how stale a reading may be. Nothing in this test
judges it, and its result does not bear on it. A pass here does not make the line right; a fail does not make it
wrong.

## Seen before writing

- The documents named above: the sources note (2.4), the review of 16 October (section 4), `ecoli.py`,
  `train_ecoli_sm.py`, `train_ecoli.py`, the soil-moisture rivers test, and the near-miss addendum with its 26 October
  note.
- **3 requests to the EA Hydrology API, of the 150 allowed,** 01:02:15 to 01:02:40 UTC, all 200: the reference page
  (227 KB), and the turbidity and ammonium station listings (4.8 MB and 5.0 MB). No readings request.
- **From the listings** (metadata only): 1,887 stations with either property. Turbidity: 1,737 stations, 145 marked
  Active. Ammonium: 1,818, 134 Active. Every station has a `dateOpened`; most have a `dateClosed`.
- **Prep, offline** (`prep.py`, `relate.py`; files `SONDE-SIGNAL-TEST-2026-10-candidates.csv` and
  `SONDE-SIGNAL-TEST-2026-10-prep.json`):
  - Rules 1 and 2: 46 turbidity pairs (spot, sonde) at 14 of the 20 spots, 45 for ammonium (Teddington Weir has no
    ammonium measure).
  - Upper bound of covered rows before rule 3: 168 at 7 spots.
  - Rule 3: 21 pairs pass for each property. The seven Thames sondes near Ham and Kingston fail (six on tidal
    water, and Teddington Weir, which the network did not join), as do the Stour sondes below Sudbury (Bures Mill
    10.9 km and Boxted Mill 24.6 km downstream). The prep run of `relate.py` loaded the main checkout's
    `river_network.pkl`: 10 s, 0.75 GB peak.
  - After rule 3: 8 sondes cover a sample day. Covered upper bound: 71 rows at 4 spots, for both properties.
- **Sample days, not values.** To count covered rows I read only the columns `bw_id`, `kind`, `upstream` and
  `sample_time` of `ecoli_validation_rows.parquet` in the main checkout. The `ecoli` column was not read. The May to
  September river rows with overflows upstream number 907, the same as the model's river rows.
- **Choices made after seeing names and distances:** the 20 km upstream cap was written into `sondes.py` after the
  straight-line list and before the network was loaded. One pair falls just outside it: Bulls Ridge on the Frome, 22.2
  km above Farleigh Hungerford, which covers 20 rows (2024). Under a 25 km cap the upper bound would be 91 rows at 5
  sites, still under the gate.
- No E. coli value, no exceedance count, no sonde reading, and no score of any kind.

## Running (only after Ethan approves)

- From a `git archive` of the harness commit: `scripts/sonde_signal_eval/run.sh <frozen root> <soil dir> <out dir>`.
  Steps: station listings (2 requests), prep and rule 3 offline, the pre-gate, the readings fetch (cap 40), then
  `score.py` with every connection refused (`lake_distance_eval/run_offline.py`).
- Synthetic tests: `tests/test_sonde_signal_eval.py` (matching, deployment, no reading after the cut, the anomaly,
  quality and floors, the fallback, sonde order, B and H, labels in order, the placebo, LOSO on synthetic rows, the
  request ledger and the fetch plan).

## What follows

- **As stated, nothing runs past the pre-gate.** Ethan can approve the statement as a record and spend no requests.
- **To make the question answerable,** the rows have to grow. Options, none started, each its own statement:
  1. Wessex Water's river E. coli samples (CC BY 4.0, 2019 to 2025, 99 positions), as held-out rows only. Sonde
     coverage at their positions has not been counted.
  2. The 2027 bathing season, prospectively, with the same rules, at spots whose sondes are live then.
  3. Leave it: the display-only line does not need this test.
- Nothing is adopted or deployed by this PR.

---

## Results

None. Not run.
