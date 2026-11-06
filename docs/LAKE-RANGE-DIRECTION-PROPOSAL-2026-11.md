# Proposal for Ethan: say whether a lake's likely E. coli reading is higher or lower than usual

Written 6 November 2026, register row **3 / LAKE-CONC**. This is the next deliverable that
[LAKE-LINE-2012-22-CHECK-2026-11.md](LAKE-LINE-2012-22-CHECK-2026-11.md) named. **It is a product decision for Ethan.
Nothing is built and nothing on the site changes.** If agreed, it adds one line to the lake E. coli tile that #585 put
on the page; it adds no new model, request or log.

## The words (proposed)

On the lake tile, in season (May to September), after the existing sentence "A sample today would most likely read
about 16 E. coli per 100 ml; 8 in 10 would read between under 10 and 150.", one line of three forms:

- "That is **higher than usual** for this lake in early July (usually about 6)."
- "That is **lower than usual** for this lake in early July (usually about 30)."
- "That is **about usual** for this lake in early July."

The day table could carry the same as a word after the figure ("about 22, higher than usual"). The proposal is the tile
line only; the table is an option.

## What "usual" means (fixed in this proposal, so it cannot be tuned on results)

- **Usual:** lake-range-v1's likely reading for the same lake on the same date with that lake's typical inputs: the
  median rain over 48 and 24 hours and the median exposure on its own 2023-26 Environment Agency sample days. It is
  computed from the frozen model file; nothing is refitted.
- **Higher than usual:** today's likely reading is at least twice the usual one. **Lower than usual:** at most half.
  Otherwise **about usual**. Twice is 0.3 on the log scale, under half the lake's own scatter (about 0.70), so the line
  speaks of the estimate, never of the water's measured state.
- Rounded as the tile already rounds: two significant figures, "under 10" below the lab's limit.

## What it rests on

All seen data, labelled as development evidence. The measure is the within-site Spearman correlation between a model's
daily figure and the lab result at the same lake.

| Data | lake-range family median | Production's lake chance | Difference |
|---|---|---|---|
| 2012-22, Windermere ×4 and Frensham, 962 samples (out-of-time; previously examined by #584) | lake-range-v1 0.287; frozen plain 0.279 | 0.123 | plain +0.156 [+0.090, +0.218] |
| 2024-26, 12 lake bathing waters, 637 samples, lake held out of fitting | plain 0.180 | −0.042 | +0.222 [+0.105, +0.332] |
| 2024-26, forward in time | plain 0.222 | −0.078 | +0.300 [+0.132, +0.472] |

**How strong this is, said plainly:** a rank correlation of about 0.25 to 0.3 puts two days at the same lake in the
right order about 58-60% of the time. It is better than production's lake chance, which carries no order within a lake.
It is far from a reliable day-to-day signal. The line is worth showing only as a gentle comparison with the lake's own
usual, never as a warning.

## What it must not imply

- **No safety claim.** "Lower than usual" does not mean safe; "higher than usual" does not mean unsafe. The official
  advice and the bathing water's classification stay above the tile, as now.
- **Not a line chance.** There is no "chance of exceeding 900" at lakes (9 results over 900 in 2012-22, 16 in 2024-26:
  too few to judge). The line must not use "risk", "exceed", "breach", "safe" or "clean".
- **No colour, level or alert.** The lake's level stays the spill risk's, as now.
- **Not a measurement.** It compares two estimates, today's and the usual one.

## Where it would not appear (the fallback)

- **Lakes without their own samples** ("average lake" basis): no line. The ordering was checked only at sampled lakes,
  and "usual" needs the lake's own sample days.
- **Out of season** (October to April): no line. No samples are taken then to check it against.
- **Model file missing or not the frozen one, or an input missing for the day:** no line. The tile says what it says
  today.
- **Colwick Country Park:** no line. The site gives it no lake range, because its pin has no monitored overflow
  upstream (#199).
- **Derwent Water:** no special treatment. Its high results are a summer rise that rain, spills and lake level do not
  track (`docs/DERWENT-WATER-DIAGNOSIS-2026-11.md`), so its line would often read "about usual" on days with results
  over 900. That limitation should sit in the Methods page note if the line is shown.

## How it would be judged (fixed now, before any 2027 sample)

On or after 15 October 2027, with the existing read of `shadow_lake_range_v1` (`docs/LAKE-RANGE-WORDING-2026-11.md`):

1. **Order:** the mean within-site rho of the logged lake-range-v1 median against production's logged lake chance, as
   above, with ISO-week intervals.
2. **The words themselves:** for 2027 samples paired with lead-0 rows, the share of results above the lake's own
   2023-26 median result on "higher than usual" days, minus that share on "lower than usual" days. It must be above
   zero with its interval above zero for the line to stay.

If either fails, the line is removed for 2028 and the record says why.

## The decision needed from Ethan

1. Show the line or not.
2. If shown: the tile line only, or the day table as well.
3. Any change to the words. The "twice" and "half" bands and the definition of usual are fixed here so that 2027 can
   judge them. Changing them after 2027 samples arrive would need a new proposal.
