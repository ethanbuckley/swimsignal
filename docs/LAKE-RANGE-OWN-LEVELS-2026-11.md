# The lake range on the site: own levels at 5 lakes with no overflow upstream, and the row in the redesign

Written 28 November 2026. Follows [bench read 2](BENCH-READ-LAKE-RANGE-COVERAGE-2026-11.md), whose statement said
what a pass leads to. Ethan said "Yes, build it" on 28 November 2026.

## What changes on the site

**One row behind the level, "E. coli estimate at a lake, experimental",** in the redesign (the site's own pages), at
every lake spot that has the lake range:

- In season (May to September): its value is the likely reading ("About 41", or "Under 10"). The lines say "A sample
  today would most likely read about 41 E. coli per 100 ml; 8 in 10 would read between 12 and 290.", the lake's
  higher / lower / about usual line where it has one (the 11 with their own samples, #630), what the figure rests on
  (by basis, below), and "It does not set the level."
- Out of season: "Out of season", and "Tested only for May to September, when the Environment Agency takes samples,
  so no figure is given now." This is what every lake spot with a range shows from today to 30 April 2027.
- No colour, band or level. The level, its words and what to do are unchanged (tested: `site_preview.test.cjs`).

**Where.** The 11 lake bathing waters with their own level, the 20 lake spots with overflows upstream on the
average-lake basis (both had the range only at `classic/`, since #585), and now 5 lake bathing waters with no overflow
upstream: the Serpentine, Hampstead Heath's Ladies, Mens and Mixed Ponds, and Colwick (West Lake). Cotswold Country
Park and Henleaze Lake have their levels in the file but no daily forecast, so they show nothing.

**What each basis says** (`LAKE_RANGE_BASIS` in `levels.js`):

| Basis | Lakes | Says |
|---|---|---|
| tested | Windermere ×4, Frensham | own samples, rain and spills; 79 in 100 inside on 2012-22 samples it never saw (#584) |
| own samples | Coniston ×3, Derwent Water, Rutland ×2 | own samples since 2023, rain and spills; not tested on past seasons here |
| own level, tested here | the 5 above | own samples since 2023, rain and the time of year; 87 in 100 inside on 2012-22 samples it never saw, here and at six lakes like it: a little wide (bench read 2) |
| average lake | 20 spots with overflows upstream | no samples of its own; less certain: at lakes it knew nothing of, more samples fell outside its range than it allows, below at Windermere and Frensham (#584, supplementary) and above at seven others (bench read 2, seen years) |

The lake word's note (#767) changes one sentence: "Its size is not tested, so it gives no figure." becomes "How far
above or below usual is not tested, so the word gives no amount." The range beside it now gives a figure, so the old
sentence would read as if no figure were shown.

## The levels

`data/processed/lake_range_levels.v1.json` (`145d939b…`), written by `scripts/lake_range_levels.py`: for each of the 7,
node weights from the prior plus the summed censored-normal log-likelihood of its 2023-26 samples (the bench's frozen
seen rows), normalised: the candidate bench read 2 passed with (`own_weights`, file hash in the levels file). Tied to
lake-range-v1's hash, which is unchanged. 54 to 79 samples per lake.

`lake_range.ranges(..., own_level=True)` adds them beside the 11, and only `forecast.py`'s branch for a lake with no
overflow upstream asks for that. The range at every lake with overflows, its basis and the `shadow_lake_range_v1`
table are unchanged: no row is logged for the 5 (`if ranges is not None and not ov.empty`). These lakes have no usual
inputs, so no "higher / lower than usual" figure line; the lake word stays their comparison.

The range shows on all 5 days, as at the 11. Bench read 2 tested it at lead 0 (archive rain), the same as #584 for the
11; leads 1 to 4 use forecast rain, unmeasured for both.

## How it stands to what is decided (docs/DESIGN.md)

- **Already decided, followed:** the lake range at lakes with overflows upstream and its words (#585, #630; Ethan, 1
  Nov: "all lakes and bathing waters if possible"); E. coli as a row behind the level, "Out of season" out of season
  (the five reversals, 25 November 2026, item 5).
- **Ported:** the range was only at `classic/` after the switch, and missing from the list of what is only there.
- **Reverses, at these 5 only:** "no E. coli estimate at these spots" (3 and 11 October 2026), already reversed for the
  lake word (#767). Bench read 2 has now tested a figure there.
- **New:** the row's wording in the redesign, the "own level, tested here" basis, and the average-lake basis wording
  (classic said only "below its range"; read 2's seen years found the opposite at seven lakes, so both are said).

## Checked and not checked

**Checked:** `tests/test_lake_range_levels.py` (frozen file, no overlap with the 11, the Serpentine's level above the
average lake's, no range off the list or with another file, the forecast's branch and shadow guard);
`tests/site_preview.test.cjs` (the row in and out of season, no row without a range or at a river, the level
unchanged); a local preview of the live data of 28 November with ranges put on the Serpentine and Windermere by hand,
at 375 and 320 px (no sideways scroll, no console errors). **Not checked:** a range computed by a live build at the 5,
which needs a forecast run; out of season the row will say "Out of season" there from the next build.

## Next

The 2027 read of `shadow_lake_range_v1` continues for the 11 (on or after 15 October 2027). The 5 are not logged; their
2027 check is the bench's rule applied to 2027 samples: coverage of the frozen range, 70% to 90%, read after the season
(owner: research sessions). The average-lake basis at the 20 spots has no test; a check would need samples at lakes
with overflows and no level, which the EA does not take.

## Later the same day

The average-lake basis is no longer shown: [the average-lake check](LAKE-AVERAGE-BASIS-CHECK-2026-11.md) found it held 69% of samples at sampled lakes treated as unknown. Its sentence in the table above is kept in `levels.js` for the record but no spot uses it now.
