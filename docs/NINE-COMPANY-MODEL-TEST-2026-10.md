# A spill model trained on nine companies: the test, stated before any run

Written 16 October 2026, before any of the nine companies' event files was opened. It is committed
and pushed before the first training run. Results go below the line at the end. Nothing above that
line changes after a result is seen. Review tasks D1, D2 and A1 (`docs/REVIEW-2026-10-16.md`,
sections 3.1 and 4).

## Why

The spill model's layer 1 (the pooled classifier on rain, season and annual-return covariates) and
its layer 2 (one offset per overflow) were fitted on United Utilities alone. The Accuracy page
shows the cost. 402 of 425 warnings that came true were at United Utilities. Thames and Southern
forecast six to eight times the rate they observed.

The Environment Agency's "Event Duration Monitoring - Storm Overflow - Start/Stop Detailed Data"
(environment.data.gov.uk/dataset/e9677ac1-fd32-4ceb-88a0-2735be5f27c7) gives one row per discharge
for all ten companies that operate in England, for 2024 and 2025. Its licence is the Open
Government Licence v3.0, with the credit "© Environment Agency copyright and/or database right".

A second fault is fixed here too (review finding 3.1, task A1). `lead_calibration.json` was fitted
for the 2023-24 hold-out model, and it is applied to the 2023-25 refit.

## Seen before writing

- **D1, the runner route.** Run 38964387549, 16 Oct 2026 20:44 UTC, on a throwaway branch with
  `contents: read`. The branch was deleted afterwards. The download-url request returned 200, and
  the signed link returned 200 with 914,705 bytes for "Thames 2024 Detailed EDM Data.csv". That file
  begins `PK`, so it is an XLSX workbook despite its `.csv` name. The reader must look at the bytes,
  not the extension.
- **The file list.** There are 23 files. The 20 for England, plus the DSP note, total 191.9 MB
  (HEAD requests on the signed links). All were last modified 21 Sep 2026, except Thames 2026
  (29 Sep). Layouts by name: 2024 files are XLSX for Anglian, Severn Trent and South West, and CSV
  for the rest. 2025 files are XLSX for Southern, Thames, Wessex and Yorkshire, and CSV for the
  rest. Thames 2024 is really XLSX.
- **The DSP note** ("Technical Detail DSP April 2026.docx", read in full). It gives one layout and
  one definition for every company. Column A is the Unique ID, the same id as the annual returns.
  Column B is the site name. Columns C and D are the times the activation started and stopped,
  headed "(GMT)". "Each row holds the data for one EDM activation event." The dataset page adds that
  the data "has not been subject to any formal verification by the Environment Agency". **The note
  gives no company-specific rule.** It does not say whether a company merges activations close
  together, drops short ones, or counts by 12/24-hour blocks (the annual returns do). Whether the
  companies differ is measured in step 1 below, not assumed.
- **Annual returns** (`annual_returns.parquet`). Overflows with a position in the 2023 return,
  which gives the covariates for 2024: Anglian 1,562, Northumbrian 1,565, Severn Trent 2,472,
  South West 1,374, Southern 977, Thames 698, United Utilities 2,264, Wessex 1,295,
  Yorkshire 2,194. They fall in 1,652 rain cells of 0.1°.
- **Rain archive coverage.** ERA5-Land is cached for every United Utilities cell for 2023-26, and
  for 395 of the 1,643 cells of the 2024 return. 1,258 cells have no 2024 or 2025 file. Lead
  forecasts for 2025 cover 394 cells: 2,270 United Utilities overflows and 0 to 715 for each other
  company (0 for Northumbrian and Southern, 3 for South West).
- **Earlier results.** The current model's 2025 hold-out scores, all at United Utilities
  (`verification_2025.csv`). The live Accuracy page's by-company table.

Nothing from the nine companies' event files has been read.

## The candidate (one, fixed now)

- **Events.** The EA files for the nine English companies, 2024 and 2025. United Utilities is
  included and read from the EA file, not the Stream feed, so every company comes through one
  route. Dŵr Cymru Welsh Water's files stay out of training. They are the Welsh test set
  (`dcww_ea_events.parquet`), as now.
- **Ids.** The file's Unique ID is matched to `annual_returns.site_id`, after `_id_map` (old id to
  new id).
- **Which overflow-years count.** The file has no row for an overflow that did not spill, and none
  for an overflow it left out. A site-year is kept when either:
  - the file has at least one event for that overflow in that year, or
  - that year's annual return gives 0 spills.

  A site-year whose return gives spills above 0 but which has no event in the file is dropped as
  missing from the file. So is one whose return gives no count. The existing rule is unchanged: a
  site-year whose same-year EDM operation is under 50% is dropped. The counts dropped by each rule
  are reported per company.
- **Features.** Unchanged (`features.ALL_FEATURES`). There is no company feature. The pooled layer
  stays usable for an overflow of any company, including in Wales and Scotland, and company
  differences go into the per-overflow offsets. Rain is ERA5-Land on the 0.1° grid, days floored
  in UTC as `train.py` does now (review finding 3.9 is out of scope here).
- **Rain.** For the cells that have none, the fetch adds ERA5-Land for 2024 and 2025. It also adds
  1 to 31 December 2023, so January 2024's 7-day and 30-day windows and its antecedent index are
  complete. That file is saved as `archive_<cell>_2023dec.parquet`, so no script mistakes it for a
  whole year. Every new rain file goes to `data/cache/rain_nine/`, not `data/cache/rain/`, because
  `validate_ecoli.py` and the hindcasts read every file in the shared folder, and a new cell there
  would change what they compute (`scripts/fetch_rain_nine.py`). Ethan approved the download and the
  fetch on 16 Oct 2026, with no other Open-Meteo job running from this Mac meanwhile.
- **Fit.** Layer 1 is fitted on every kept 2024 site-day of the nine companies, with the same
  settings as now (`neg_frac` 0.25, seed 0). Layer 2 gives offsets for every overflow with 2024
  site-days, with prior strength 15 and recency 1. Nothing is tuned on 2025.
- **What would be deployed.** This 2024-trained model itself, not a refit on 2024-25. A refit would
  have seen 2025, and the lead calibration below is fitted on 2025. That is the fault in A1.
  `trained_on` will read "Nine English water companies 2024 (EA start/stop files); verified on 2025".

## Verification on 2025, per company

The rows are the 2025 site-days of each company's overflows: a position in the 2024 return, the
coverage rule above, EDM operation of at least 50% in 2025, and finite ERA5 rain for the day. Every
predictor below is scored on the same rows. Each forecast is compared with the label "the overflow
spilled that day".

| Predictor | What it is |
|---|---|
| New | the candidate above |
| Current hold-out | `spill_model_holdout_2025.pkl`, United Utilities 2023-24 (never saw 2025) |
| Current production | `spill_model.pkl`, United Utilities 2023-25. It is in-sample at United Utilities in 2025, so that row is reported but not used in a condition there |
| Company flat rate | the company's 2024 spill-day rate, one number per company |
| Overflow climatology | the overflow's own 2024 spill-day rate (`verify.climatology`). An overflow with no 2024 rows takes the company's flat rate |

Reported per company and for the nine together:
- rows and base rate
- Brier score
- AUC
- Brier skill against overflow climatology and against the flat rate
- a 10-bin reliability table
- ECE, the expected calibration error: the mean absolute gap between forecast and observed rate
  over the 10 equal-width bins, weighted by rows

`verification_2025.csv` gains a `company` column.

The Welsh test set is Dŵr Cymru's overflows in England, with 2025 events from the EA file. They
have no offsets in either model, so pooled predictions are compared.

## Conditions for adopting, all required

1. **No company worse than today.** At each of the nine companies, the new model's 2025 Brier is no
   higher than the current hold-out model's. At the eight companies other than United Utilities,
   it is also no higher than the current production model's.
2. **Skill against the simple baselines.** At each of the nine companies, the new model's Brier is
   lower than both the company flat rate and the overflow climatology.
3. **Reliability.** At each of the nine companies, the new model's ECE is no higher than the
   current hold-out model's, or it is at most 0.02.
4. **The Welsh test set is not worse.** On Dŵr Cymru's English overflows in 2025, the new pooled
   Brier is no higher than the current hold-out model's pooled Brier.

If all four hold, the new model becomes `spill_model.pkl`. The README's Method section gets a
per-company table of Brier, AUC and ECE. The Accuracy page's sentences saying the model learned at
one company are replaced. `assumptions.model` on every spot names the new training set, because it
is the model's `trained_on`.

If any condition fails, the new model is not deployed, and this document is the record.

## Lead calibration (A1), whichever model is deployed

- `scripts/verify_leads.py` fits the per-lead isotonic map **on the model that is deployed**. It
  writes that model's `trained_on` into `lead_calibration.json` as `model`. A test asserts
  `lead_calibration["model"] == SpillModel.load().trained_on`.
- **Rows.** 2025 site-days of every overflow of the nine companies that lies in a cell with
  archived lead forecasts.
- **More lead cells.** Today's 394 cells hold almost no Northumbrian, Southern or South West
  overflows. So 30 more cells are fetched for each of Anglian, Northumbrian, South West, Southern
  and Yorkshire, 150 in all. They are drawn with `numpy.random.default_rng(0)` from that company's
  cells with no lead file, without replacement (all of them where a company has fewer).
- **Cross-fitting.** Each lead's map is scored cross-fitted by month: fitted on odd months and
  scored on even months, then the reverse. The map that is saved is fitted on all twelve months.
- **When a lead gets no map.** If the cross-fitted Brier at a lead is not lower than the raw
  Brier, that lead is saved with an identity map (knots [0, 1] → [0, 1]).
- **The climatology reference.** The hard-coded climatology Brier (0.0669, United Utilities) in
  `verify_leads.py` is replaced by the overflow climatology computed on the same rows.

**If the nine-company model is not adopted**, A1 is closed by its second option. Production becomes
the current hold-out model (United Utilities 2023-24). Its lead map is refitted by the same
procedure, so the map and the model match. The Method page says so. This is a change to the
deployed model, so the PR flags it for Ethan.

**Before deployment, a pre-stated note.** It names the live Accuracy-page `by_rain` and
`reliability` bins expected to move over the four weeks after deployment, and in which direction.
It is written under the results line from the fitted maps, before the change reaches main.

## Order of work

1. Import the files (`scripts/import_ea_events.py`). Report events, overflows, the id match to the
   annual returns, and per company the median event length, the share of events under 15 minutes,
   and the median gap between one event's stop and the next start at the same overflow. These are
   the measured signs of company-specific event definitions.
2. Fetch the missing rain: about 9,800 Open-Meteo calls in all, under the free limits, paced at
   3,000 an hour. The breakdown is 3,289 calls for 2024, 3,280 for 2025, 1,260 for December 2023
   and 1,955 for the lead sample. One variable for a year weighs 2.6 calls a cell (locations ×
   days/14 × variables/10, from Open-Meteo's blog).
3. Train on 2024, verify on 2025, and check conditions 1-4.
4. Fit the lead calibration for the model that will be deployed, and write the pre-stated note.
5. Write the results below the line, then make the change or keep the record.

Evaluations run one at a time on this 16 GB Mac.

---

## Results

Run 17 October 2026 from commit `f0fcf21`, which holds the statement above (first pushed at `4d90a5a`,
16 Oct 21:48 BST). The log is `logs/train_nine_2026-10-17.log` in the main checkout (not committed).
The tables are committed beside this file:
- `-scores.csv`: every predictor, every company
- `-reliability.csv`
- `-coverage.csv`
- `-events.csv`

### Seen before the main run

- **A code test** of the `--nine` path, with United Utilities as the only company (16 Oct, 21:58).
  - A model fitted on United Utilities' 2024 alone scored Brier 0.0454 there in 2025.
  - The hold-out, fitted on 2023-24, scored 0.0446.
  - It showed that condition 1 at United Utilities was at risk. Nothing above the line was changed
    after it.
- **A code test of `verify_leads.py`** on the production model, which is in-sample at United
  Utilities, so its scores mean nothing.

### Step 1: the files and the companies' event definitions

- **Coverage.** 2.95 million events. Every id is in the annual returns, every event has a position,
  and no event lacks a stop.
- **United Utilities against the Stream feed it was trained on,** counted as spill-days:
  - 2025: identical (61,764).
  - 2024: 76,958 shared, 1,333 only in the EA file, 846 only in Stream.
- **Event definitions** (measured; the DSP note gives one definition for all):

| Company | Events 2024 / 2025 | Median event | Under 15 min | Median gap to next start |
|---|---|---|---|---|
| Anglian | 290,172 / 96,034 | 6 min | 61-62% | 2-6 min |
| Northumbrian | 106,346 / 94,698 | 6-15 min | 45-64% | 8-28 min |
| Severn Trent | 223,400 / 91,790 | 14-19 min | 45-52% | 16-35 min |
| South West | 237,036 / 209,707 | 5-6 min | 67-71% | 8-12 min |
| Southern | 73,295 / 52,682 | 7-13 min | 52-62% | 12-15 min |
| Thames | 31,856 / 12,175 | 75 min | 14-16% | 128-165 min |
| United Utilities | 216,376 / 175,356 | 16 min | 48-49% | 26-28 min |
| Wessex | 445,625 / 230,487 | 2 min | 84-85% | 4 min |
| Yorkshire | 213,899 / 151,220 | 15 min | 24% | 22-30 min |

What the table shows:
- **Thames** records far fewer, longer events with long gaps between them. *Inferred:* it merges
  activations close together.
- **Wessex and Anglian** record many very short ones, two to six minutes apart.
- The label is "spilled that day", so these differences change counts much more than labels. But an
  overflow that blips once on a dry day is a spill-day at Wessex and may not be at Thames.

### Overflow-years kept

| | 2024 kept | of | 2025 kept | of |
|---|---|---|---|---|
| Anglian | 1,399 | 1,433 | 1,405 | 1,444 |
| Northumbrian | 1,370 | 1,410 | 1,540 | 1,560 |
| Severn Trent | 2,382 | 2,430 | 2,412 | 2,459 |
| South West | 1,345 | 1,367 | 1,353 | 1,370 |
| Southern | 927 | 976 | 941 | 978 |
| Thames | 577 | 589 | 575 | 590 |
| United Utilities | 2,199 | 2,263 | 2,263 | 2,270 |
| Wessex | 1,291 | 1,294 | 1,281 | 1,295 |
| Yorkshire | 2,108 | 2,187 | 2,140 | 2,191 |

Per company and rule, 0 to 39 overflows were missing from the file and 0 to 58 had EDM under 50%
(`-coverage.csv`). This gives 4,976,868 training site-days in 2024, a base rate of 0.087, and
5,077,150 test site-days in 2025, a base rate of 0.057. 2024 was much the wetter year. The pooled
layer ran its full 300 iterations.

### Verification on 2025, per company

Brier, with ECE in brackets; bold marks the better of new and hold-out. AUC follows for the new model and the hold-out. "Production" is
in-sample at United Utilities.

| Company | New | Current hold-out | Current production | Flat rate | Overflow climatology | AUC new / hold-out |
|---|---|---|---|---|---|---|
| Anglian | 0.0272 (0.011) | **0.0269** (0.008) | 0.0265 (0.010) | 0.0347 | 0.0382 | 0.883 / 0.868 |
| Northumbrian | **0.0332** (0.003) | 0.0353 (0.014) | 0.0341 (0.015) | 0.0483 | 0.0468 | 0.922 / 0.921 |
| Severn Trent | **0.0284** (0.005) | 0.0295 (0.009) | 0.0288 (0.011) | 0.0407 | 0.0418 | 0.928 / 0.924 |
| South West | **0.0519** (0.009) | 0.0547 (0.012) | 0.0536 (0.015) | 0.0854 | 0.0789 | 0.930 / 0.919 |
| Southern | **0.0277** (0.011) | 0.0300 (0.010) | 0.0300 (0.013) | 0.0441 | 0.0445 | 0.946 / 0.938 |
| Thames | **0.0303** (0.024) | 0.0330 (0.010) | 0.0323 (0.012) | 0.0451 | 0.0488 | 0.942 / 0.893 |
| United Utilities | 0.0456 (0.018) | **0.0446** (0.010) | 0.0369 (0.007) | 0.0695 | 0.0656 | 0.929 / 0.930 |
| Wessex | **0.0326** (0.014) | 0.0354 (0.005) | 0.0338 (0.009) | 0.0515 | 0.0511 | 0.944 / 0.924 |
| Yorkshire | **0.0403** (0.005) | 0.0435 (0.022) | 0.0418 (0.022) | 0.0627 | 0.0606 | 0.927 / 0.922 |
| All nine | **0.0362** (0.008) | 0.0376 (0.009) | 0.0356 (0.011) | 0.0547 | 0.0537 | 0.929 / 0.921 |

**The Welsh test set** (Dŵr Cymru's overflows in England, 2025): 44,165 site-days, base rate
0.064. The new pooled model scored 0.04206; the hold-out pooled 0.04168.

### The conditions

1. **No company worse than today: FAIL.**
   - Anglian: new 0.0272 against hold-out 0.0269 and production 0.0265.
   - United Utilities: new 0.0456 against hold-out 0.0446.
2. **Skill against both baselines at every company: PASS.**
3. **Reliability: FAIL** at Thames. ECE 0.0240 against the hold-out's 0.0103, and above 0.02.
4. **The Welsh test set is not worse: FAIL.** 0.04206 against 0.04168.

**The nine-company model is not adopted.** It stays off, and this document is the record. The
candidate is kept off-repo as `spill_model_nine_2024.pkl` (SHA-256 begins `1603678923cc`).

### Observations, not tested and not grounds for any change

- The new model is better than the hold-out at seven companies and over the nine together. It
  loses where the test is hardest for it:
  - United Utilities, where the hold-out has two years of offsets and the candidate one.
  - Anglian.
- **The single-year offsets look like the weak part.** The candidate's own pooled layer, without
  offsets, scores 0.0260 at Anglian (below every row in the table) and 0.0287 at Thames.
  - Anglian logged 290,172 events in 2024 and 96,034 in 2025. Its overflow climatology from 2024
    loses even to the flat rate in 2025.
  - An offset fitted on one wet year carries that year into the next.
  - A next test could state, before running: pooled layer only, or offsets with fewer pseudo-counts
    per year, or two years of offsets once 2026 is in. This needs its own pre-stated test.
- Thames's miscalibration fits its merged events. Inferred, not checked.

### Lead calibration (A1)

**The map fitted by the stated procedure for the model the fallback would deploy.** Model: the
United Utilities 2023-24 hold-out. Rows: 2025, 5,313 overflows of the nine companies in 544
lead cells, 1,939,245 site-days. Climatology Brier 0.0588.

| Lead | Raw Brier | Cross-fitted map | Map kept |
|---|---|---|---|
| 0 | 0.03947 | 0.03921 | yes |
| 1 | 0.04223 | 0.04206 | yes |
| 2 | 0.04394 | 0.04366 | yes |
| 3 | 0.04535 | 0.04502 | yes |
| 4 | 0.04754 | 0.04693 | yes |

**A replay of 2025, leads 0 to 4 pooled, on those rows**, to write the pre-stated note. It found
that the stated fallback is worse than today outside United Utilities, where neither model saw
2025. Brier on non-United Utilities rows:

| System | Brier |
|---|---|
| Today: production model (2023-25) + old map | 0.03941 |
| Production model, no map | 0.03931 |
| Stated fallback: hold-out + its refitted map (map fitted on these same rows) | 0.03966 |
| Hold-out + a map fitted on non-United Utilities rows, cross-fitted by month | 0.03945 |
| Production model + a map fitted on non-United Utilities rows, cross-fitted by month | **0.03818** |

**This corrects the review's guess about direction** (finding 3.1, "inferred: a plausible
contributor to the live over-forecasting"). On 2025, against the EDM files, the old map makes
forecasts too **low**: mean forecast 0.050 against 0.064 observed. Every refitted map raises the
low and middle bins. The live page shows 2026 forecasts too **high**. The two years, or the two
kinds of truth (EDM files and live feed status), disagree.

Which route ships is Ethan's decision (asked 17 Oct 2026):
- the stated fallback;
- the better route found after the run, which is a deviation from the plan above;
- neither.
