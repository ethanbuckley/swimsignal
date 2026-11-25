# RESTORE at Ilkley: did measured E. coli at Cromwheel fall in 2026? The audit, stated before any join

Written 17 November 2026. Part of LEDGER stage 1 and the first case for RESTORE
([scoping](AMBITIOUS-RESEARCH-SCOPING-2026-11.md), section 4). Owner: Ethan, with a Claude session doing the work.

**Result: not run.** Nothing in this file is a finding about 2026 samples. The register starts RESTORE after option
B's read, on or after 2 December 2026. This audit does not run before that read. Results go below the line at the end.
Nothing above that line changes after a result is seen.

## The question

The six overflows Yorkshire Water names in its Ilkley scheme went quiet from April 2026. They showed 1 spill day in
April to August 2026 against 23.0 expected ([record](UPGRADED-OVERFLOWS-2026-10.md), section 2). That is a result
about monitors.

This audit asks about the water. In May to September 2026, was measured E. coli at Wharfe at Cromwheel lower than
rain and season predict from earlier seasons?

## The claim it can support, and the ones it cannot

- **Can support:** "At Cromwheel in the 2026 season, Environment Agency samples read X times what rain and season
  predicted from 2023 and 2024, with this interval. At 12 other river bathing waters the same figure ranged from A to
  B." A description of one site.
- **Cannot support:** that the scheme caused a fall. One site and one season cannot separate the scheme from
  anything else that changed in 2026.
- **Cannot support:** that the water is safe to swim in, or that any overflow caused any sample result.
- **Never:** a confirmation. Ilkley is seen data (next section).

## Seen before writing

**Ilkley is seen data, as the register's RESTORE row requires.**

- The 2026 spill outcome at all 16 overflows above Cromwheel is published in the Ilkley record. The six were chosen
  for this audit because they went quiet.
- The 2026 Cromwheel samples are public on the site's spot page and in `data/research/ecoli_evidence.v1.json`. The
  E. coli model's fits and the bench have used them.
- The writer of this file read, for Cromwheel: the count of samples by year (20 in each of 2023, 2024 and 2025; 17
  bathing-water samples and 3 Water Quality Archive samples in 2026), their dates, and the evidence file's summary of
  80 samples with 22 over 900 across all four years together.
- The writer did not open any 2026 sample value, and did not open any spill record or event file for this audit. The
  "1 against 23.0" figure is quoted from the record.
- For the 13 other river bathing waters named below, the writer read sample counts by season only.

So a pass here is development evidence about one seen site. It is not a held-out test.

## The rows

All samples are Environment Agency bathing-water compliance samples at Cromwheel (`bw_id` `uke4100-08901`), from the
cached `bwq_samples.parquet`, taken from 1 May to 30 September.

| Set | Seasons | Rows in the cached file | Role |
|---|---|---|---|
| Before | 2023, 2024 | 40 | The expectation is fitted on these |
| Transition | 2025 | 20 | Reported apart. Not fitted on, not in the deciding figure |
| After | 2026 | 17 | The deciding rows |

- **Why 2025 is held apart.** The six were already low in April to August 2025: 8 spill days against 21.6 expected
  (the Ilkley record, section 2). Work may have started then. That is inferred: no source gives a date.
- **No row is dropped for its value.** Samples the EA flags as abnormal weather or discountable stay in. A result at
  a lab limit counts at the limit.
- **The 3 Water Quality Archive samples of 2026** are not compliance samples and may have been taken for a reason.
  They are reported apart.
- If the EA's final 2026 set holds more than 17 compliance samples in the season, all of them count.
- **Earlier seasons.** The cached file starts in 2023 (established). Cromwheel was designated before then, so the EA
  should hold 2021 and 2022 (inferred, not checked). If they can be read in at most 2 EA requests, a second fit with
  them in the before set is reported as a sensitivity. It decides nothing.

## The expectation: rain and season only

y is log10 of E. coli (cfu per 100 ml). One least-squares fit on the 40 before rows:

y = a + b·ln(1 + R48) + c·ln(1 + R3to7) + d·sin(2π·day/365.25) + e·cos(2π·day/365.25)

- R48 is the rain in mm in the 48 hours before the sample time. R3to7 is the rain in the 120 hours before that.
- Rain is ERA5-Land archive rain, hourly, at the bathing water's own 0.1° cell (53.9, −1.8), from the rain cache.
- `day` is the day of the year.
- No overflow, spill record, river level, forecast or model output enters. The expectation knows nothing about the
  scheme.
- Five numbers from 40 rows. The fit is made once. No term is added or dropped after the after rows are loaded.

## The metric

D is the mean, over the after rows, of observed y minus expected y. 10^D is the ratio of the 2026 geometric mean to
the expected one. D below 0 means lower than rain and season predict.

**Interval.** 90%, two-sided, by bootstrap: 10,000 draws, seed 20261117. Each draw resamples the before rows with
replacement and refits, and resamples the after rows with replacement. The interval is the 5th to 95th percentile.

This interval covers sampling noise in both sets. It does not cover a shift that touches a whole season for some
other reason, such as low flows in a dry year. The comparison sites are there for that.

## References

1. **Comparison sites.** The river bathing waters with compliance samples in the 2024, 2025 and 2026 seasons, other
   than Cromwheel: 13 in the evidence file. Wharfe at Wilderness Carpark is left out, because the six are upstream of
   it at small weights (the ledger gives 0.02 to 0.10). A site with an overflow marked upgraded in
   `data/raw/overflow_upgrades.csv` at this file's commit is also left out. That leaves at most 12: Ribble at Edisford
   Bridge, Nidd at Knaresborough, Severn at Ironbridge, Teme in Ludlow, Severn in Shrewsbury, Sheep's Green, Friars
   Meadow, Wolvercote Mill Stream, Wallingford Beach, Avon at Fordingbridge, Frome at Farleigh Hungerford, Tone at
   French Weir Park.
2. **S, the same figure with a common before set.** For Cromwheel and each comparison site: the expectation of the
   same form fitted on that site's 2024 and 2025 rows, and the mean 2026 residual. For Cromwheel this before set
   includes the transition season, so its S leans towards showing no fall.
3. **No adjustment.** The 2026 geometric mean against the before geometric mean. Reported, deciding nothing.

## The pass rule

- **Pass:** both of these.
  1. The 90% interval of D is wholly below 0.
  2. Cromwheel's S is the lowest of Cromwheel and the comparison sites. With 12 comparison sites, a site picked at
     random would be lowest 1 time in 13.
- **Fail:** not a pass, and the lower end of D's interval is above −0.30. A fall to half the expected level
  (10^−0.30 = 0.50) is then ruled out.
- **Inconclusive:** anything else. That includes part 1 without part 2.

If fewer than 9 comparison sites remain, part 2 cannot reach 1 in 10 and the result cannot be a pass.

## Power, stated before the run

- There are 17 after rows. A season has about 20 samples.
- Assume the scatter of a river sample round its expectation is about 0.6 in log10. That is inferred from the
  river-level candidate's range, a factor of 5.3 each way for 8 in 10 results
  ([record](RIVER-LEVEL-CANDIDATE-2026-11.md)). The run reports the real scatter.
- Then D has a standard error of about 0.17 to 0.18 if 2026's rain was like the before seasons', and more if not. The 90%
  interval reaches about 0.29 each side.
- For part 1 to hold 8 times in 10, the true fall must be about 0.43 in log10. That is E. coli at about 37% of the
  expected level.
- A fall to 70% of expected would pass part 1 about 1 time in 5. Part 2 is a second hurdle on top.
- So the likely result is "inconclusive" unless the fall is large. That is the honest size of 17 samples.
- Not every high reading at a river comes from an overflow. On the bench's seen rows, 54 of 199 river results over
  900 fell on dry days (the register's DRY-DAY row). A scheme that stops spills leaves those alone.

## Reported, deciding nothing

- D on wet rows (R48 over 10 mm) and on dry rows. If the scheme matters, the fall should sit in the wet rows.
- The transition season's D, with the same expectation.
- The 3 Water Quality Archive samples' residuals.
- The share of 2026 results over 900 against the share the before rows give at the same rain (R48 over 10 mm or not).
- The same analysis for intestinal enterococci.
- The realised scatter, the five fitted numbers, and each comparison site's S.

## What each result leads to

| Result | Next |
|---|---|
| Pass | A case note for Ilkley in RESTORE's January record, with these figures, labelled seen and one site. The ledger's page may say the six were quiet in 2026 and samples read lower than rain and season predicted. No sentence says the scheme caused it. Ethan decides on any spot-page line, and on asking Yorkshire Water or Ilkley Clean River for completion dates |
| Fail | The case note says spill days fell and the samples did not show a fall to half. Next deliverable: a diagnosis from the wet and dry rows, and DRY-DAY's treated-sewage index at Cromwheel. No forecast change |
| Inconclusive | The case note gives D and its interval and says 17 samples cannot settle it. Next deliverable: more samples. Yorkshire Water's four-a-week results (DENSE, waits on Ethan's email) or the 2027 season under a new statement pushed before 1 May 2027 |
| Any | Nothing in the forecast, a frozen file or an issued prediction changes. Option B decides the model question, not this |

The same rows are not scored again with a different form, before set or threshold.

## What this audit does not touch

- Option B: its statement, its windows E and L, its files and its read on or after 2 December 2026.
- `data/eval2027/`, any frozen file, any active window.
- The spill record. The audit reads samples and rain. It opens no event file.

## Order of work, when it runs

1. Commit the script. Record its hash here.
2. Load the before rows and their rain. Fit. Write the five numbers to a file and commit it.
3. Fix the list of comparison sites from the upgrades file, before loading any 2026 value.
4. Load the after rows. Compute D, S, the interval and the reported figures.
5. Write the result below the line, in the same PR.

## Budget

Offline from the cached samples and rain. Shared caches are hashed before and after. The cached 2026 rain file for
Cromwheel's cell was written on 12 September 2026 (established, from the file's date), so September 2026 may be
missing. If it is: one archive request per cell, at most 15, counted against the day's Open-Meteo ledger. At most 2 EA
requests for the 2021 and 2022 seasons. No other fetch.

## Needs Ethan (not decided here)

1. Whether this audit runs at all after option B's read, and who runs it.
2. Whether to ask Yorkshire Water or Ilkley Clean River for completion dates and for their own samples. An outside
   contact.
3. Whether any result is said on Cromwheel's spot page.

---

## Result

Not run.
