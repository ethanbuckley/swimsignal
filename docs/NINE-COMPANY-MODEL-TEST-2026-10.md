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
  whole year.
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
2. Fetch the missing rain (two UTC days; about 9,800 Open-Meteo calls in all, under the free
   limits).
3. Train on 2024, verify on 2025, and check conditions 1-4.
4. Fit the lead calibration for the model that will be deployed, and write the pre-stated note.
5. Write the results below the line, then make the change or keep the record.

Evaluations run one at a time on this 16 GB Mac.

---

## Results

(Nothing below this line yet.)
