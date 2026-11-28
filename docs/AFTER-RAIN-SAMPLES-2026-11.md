# Past samples after rain, at lakes with no daily E. coli figure

Written 15 November 2026. A page change, from Ethan's choice the same day. (Not merged as written: rebuilt for the new site on 28 November, `AFTER-RAIN-LAKES-2026-11.md`, #776; the `classic/` tile part below was left out.) Nothing shows until May 2027: the line is
in season only.

## What changes

At a bathing water whose page shows "E. coli in past samples" (no monitored overflow upstream) and whose forecast has
daily rows, the tile adds, from May to September:

> About 14 mm of rain here in the 48 hours to midday today. Past samples here taken after more than 10 mm in 48
> hours: the middle of 12 read 190. After less rain, the middle of 67 read 130. Past samples, not a forecast.

and a fold, "About these samples", saying where the rain figure comes from, why 10 mm, that few samples follow that
much rain, and what bench read 1 found. The old sentence, "Past samples, not a forecast: with no monitored overflow
upstream there is nothing to forecast from", stays everywhere else and out of season. No estimate, comparison word,
colour or level. A picked day uses that day's rain and names it ("to midday on Monday").

Five spots get it, on the live data of 15 November: the Serpentine, Hampstead Heath's Ladies, Mens and Mixed Ponds,
and Colwick Country Park. Cotswold Country Park and Henleaze Lake have past samples too, but they are isolated lakes
with no daily rows, so there is no day's rain to give.

DESIGN.md has the decision ("Past samples after rain").

## Why this and not the "higher / lower than usual" line

Bench read 1 (`docs/BENCH-READ-LAKE-RANGE-2026-11.md`, #700) found that lake-range-v1's likely reading orders the
samples at these lakes, years 2012-22 (within-site rho 0.289 against production's −0.015), and corrected its own
next step: these lakes do not show the lake range, so the existing line could not be added "with the wording
unchanged".

A direction line on its own was checked first, on the 2023-26 (seen) rows. "Usual" uses the same date with the
lake's typical rain, so only rain moves it, and these lakes' typical 48-hour rain is 0.75 to 1.9 mm. With the
direction proposal's fixed thresholds (twice usual, half usual) the line would have said "higher" on 1 of the 348
sample days and "about usual" on the rest: twice usual needs about 57 mm in 48 hours at the Serpentine's inputs, and
"lower" cannot happen. Lowering the thresholds after seeing that would be tuning. Ethan chose this line instead.

## The figures

`data/research/after_rain_samples.v1.json`, written by `scripts/export_after_rain_samples.py`, offline:

- **Samples:** `data/research/ecoli_evidence.v1.json`, the Environment Agency samples (OGL v3) the past-samples tile
  already gives, May to September 2023-26.
- **Rain before each sample:** the backtest bench's frozen seen rows (`rain_48h`, Open-Meteo's archive at the bathing
  water's 0.1-degree cell, the 48 hours before the sample; sha256 `417648aa…`, checked before reading). Joined by
  bathing water and sample time to the minute. 1 to 5 samples a site have no rain figure (mostly 2026 samples from the
  Water Quality Archive, which the bench rows do not hold) and are in neither group.
- **Split:** more than 10 mm in 48 hours, or not. 10 mm is the line of the rain rule on the Accuracy page
  (`docs/SIMPLE-REFERENCES-LIVE-2026-11.md`). A site needs at least 5 samples in each group (`MIN_GROUP`, fixed with
  the split, before the export).
- **Middle result:** `typical.middle`, the past-samples tile's own rule (rank order, a "<10" below every count, the
  lower middle when the count is even, two significant figures).
- **No rain value is in the file.** Only counts and EA results, as BENCH-ECOLI900 keeps Open-Meteo values out of
  published files.

31 of the 38 inland bathing waters have both groups; the build attaches the split only where the page shows past
samples with daily rows, which is the 5 lakes.

| Lake | After more than 10 mm | After less |
|---|---|---|
| Hampstead Heath (Ladies Pond) | 10 samples, middle 360 | 68, middle 91 |
| Hampstead Heath (Mixed Pond) | 8, middle 210 | 60, middle 64 |
| The Serpentine | 12, middle 190 | 67, middle 130 |
| Hampstead Heath (Mens Pond) | 7, middle 73 | 52, middle 55 |
| Colwick Country Park | 10, middle 27 | 54, middle 27 |

These are seen samples, and the wet groups are small: one more wet sample can move a middle a long way. The page says
so in its fold. Colwick shows no difference and the page says what it found there all the same.

## Checks

- `tests/test_after_rain_samples.py`: the split at 10 mm (exactly 10 is "less"), the minimum group, a missing rain
  figure counted, the middle by the tile's rule, where the build attaches it, the schema check, and the committed file
  (no rain value; the Serpentine's figures; the five lakes present).
- `tests/site_after_rain.test.cjs`: the tile's sentence in season; a lab limit reads "under 10"; the old words without
  the split, out of season or with no rain figure; a picked day; the picked day's rows (`water`) with the fold; no
  estimate, safety, risk, exceedance, comparison or colour words.
- Full suites on the branch: 1,144 site tests and 2,438 Python tests passed.
- Rendered from the live `spots.json` of 15 November, built with `write_app_data` and `write_pages`: the build
  attached the split to exactly the five lakes. To see the line in November, one edit was made to a copy of that
  file: `in_validated_season` set true on those five spots' days. The Serpentine's page then read as above (rain
  "about 1 mm" that day), with no sideways scroll at 320, 375 and 1440 px. The unedited copy showed the old sentence.

## Limits and next

- The day's rain is the forecast's 48 hours to midday (part observed, part forecast for later days); the groups'
  rain is the archive's. The two are not the same product (`docs/ERA5-LAND-BULK-RAIN-2026-11.md`, #702).
- After the 2027 season: rebuild the bench rows with 2027 samples (`stage.py`, a new row version) and rerun the export,
  so the groups grow. Nothing is judged: the line reports past results and makes no claim to check.
- Cotswold and Henleaze would need daily rows (rain at the lake each build) to get the line.
