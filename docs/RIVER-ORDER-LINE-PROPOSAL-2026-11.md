# Proposal for Ethan: say whether E. coli is likely higher or lower than usual at a river spot

Written 16 November 2026, register row **RIVER-UNSEEN**. This is the deliverable the
[read](RIVER-UNSEEN-PROTOCOL-2026-11.md) named for its outcome (order passes, range fails). **It is a product
decision for Ethan. Nothing is built and nothing on the site changes.** It follows the pattern of the lake line
(`LAKE-RANGE-DIRECTION-PROPOSAL-2026-11.md`, `usualLine` in `index.html`).

Mock-up at 375 px, made from the page's own styles: [river-order-line/mockup-375.png](river-order-line/mockup-375.png).
It has not been checked at 320 or 1440 px, in dark mode, or in the real page.

## Decided by Ethan, 17 November 2026

**Keep the percentage and add the sentence, at every river spot that carries the estimate (57 on the build of 30
September 2026).** The level rule does not change. So nothing in the design reference is reversed: the first
proposal below, words in place of the percentage at the 37 spots that are not bathing waters, is not taken, and
decision 3 falls away. The mock-up shows the decided form. Its sentence is in bold only to show where it sits; on
the page it is plain, as the lake's is.

The sentence, after "Chance a water sample would show E. coli over 900 per 100 ml today; 9% tomorrow.":

- "That is higher than usual here."
- "That is lower than usual here."
- "That is about usual here."

Nothing is built yet. What the build still needs is at the end.

## The words (as first proposed; superseded by the decision above)

In season (May to September), on the E. coli tile of a river spot.

**At the 37 river spots that are not bathing waters**, the figure becomes words and the percentage leaves the tile:

- "Higher than usual here" / "Lower than usual here" / "About usual here"
- Under it: "More E. coli is likely today than is usual at this spot. It compares today with this spot's own usual,
  from the rain here and the spills upstream. No samples are taken here, so it gives no reading and no chance."
- On a lower day, after the first sentence: "That is not a clearance: this spot's usual level is not known."
- The test, in the tile or its corner fold: "In a test on 6,322 Environment Agency river samples at 59 places it had
  never seen, samples on its higher days read about two and a half times those on its lower days."

**At the 20 river bathing waters**, the percentage stays as it is and one sentence is added after it: "That is
higher than usual here." (or lower, or about usual).

Counts are from the built `spots.json` of 16 November 2026: 57 river spots carry the estimate.

## How each part stands to what is already decided

| Part | Status |
|---|---|
| A "higher or lower than usual" sentence beside an estimate | Already decided for lakes (`LAKE-RANGE-DIRECTION-PROPOSAL-2026-11.md`); new at rivers |
| A figure in words at the heading's size (`t-fig-words`) | Already decided (DESIGN.md, tile figures, 31 October 2026) |
| No colour, band or scale on the words | Follows rule 5 and the lake tile ("Never a level, band or colour") |
| Taking the percentage off the tile at spots that are not bathing waters | **Reverses** the in-season river tile (DESIGN.md, "The E. coli estimate out of season": "In season nothing changes"). Reason below |
| The estimate no longer setting the level at those 37 spots | **Reverses** `levels.js` ("A day's level is the worse of two forecasts and one record"). A separate decision, 3 below |

## What "usual" means (fixed here, so it cannot be tuned on results)

- **The figure compared** is the one the site already makes each day: production's chance of a sample over 900.
  No new model. On the read's rows it ordered a place's days as well as the candidate did (0.376 against 0.360).
- **Usual** is the middle third of the spot's own figures on May to September days of 2023 to 2026, hindcast at
  lead 0. **Higher** is above the upper cut-point, **lower** below the lower one. The cut-points are frozen per
  spot before 1 May 2027.
- Not checked: what the build needs to make each spot's 2023-26 figures, or what it costs.

## What it rests on

| Evidence | Figure | Class |
|---|---|---|
| The read: order within a place, 6,322 unseen samples, 59 points | 0.360 (0.314 to 0.394), bar 0.15 | Confirmation, at those points |
| Thirds of a point's own figures, all seasons | Samples on higher days read 2.9 times those on lower days (typical point); higher above lower at 58 of 59 points | After the read, development |
| Cut-points from seasons to 2016, applied from 2017 | 2.6 times; 33 of 35 points | After the read, development |
| The percentage at those points | It averaged 20% where 48% of samples were over 900. Where it said under 10%, 35% were over | After the read, development |
| The percentage's range form at bathing-water rivers | 80.6% inside its 8-in-10 range, in sample | Development |

**How strong this is, said plainly.** A rank correlation of 0.36 puts two days at the same place in the right order
about 62% of the time. On a third of days the tile would say "about usual". It is a gentle comparison, not a warning.

**Why the percentage goes at spots that are not bathing waters.** It was fitted and tested on bathing waters. At
the only other river places with samples to test it on, it read far too low. Those places are Environment Agency
investigation and monitoring points, dirtier than a swim spot is likely to be, so this does not show the percentage
is wrong at the 37 spots. It shows it is untested there, and that it failed where it could be tested away from
bathing waters.

## What it must not imply

- **No safety claim.** "Lower than usual" is not clean. The usual level at an unsampled spot is not known, and the
  tile says so on a lower day.
- **Not a reading and not a chance.** No number at spots that are not bathing waters.
- **No colour, level or alert** from the words.
- The words avoid "safe", "clean", "exceed" and "breach".

## Where it would not appear

- Out of season: the tile says "Out of season", as now.
- Lakes: they have their own line.
- Spots with no monitored overflow upstream: no estimate there, as now. The read's side set (23 points, 0.309) is
  not used to extend it.
- A spot whose 2023-26 figures cannot be made, or a day with an input missing: the tile as it is today.

## How it would be judged (fixed now, before any 2027 sample)

On or after 15 October 2027, at river bathing waters, which have samples: the geometric mean of samples taken on
"higher" days over that on "lower" days, pooled within site, with an interval from site-weeks. It must be above 1
with its interval above 1 for the line to stay in 2028.

At the 37 spots that are not bathing waters there are no samples, so nothing there can judge it. It would rest on
the read and on the bathing waters' result. That is a limit of the proposal.

## The decisions needed from Ethan

1. Show the line or not.
2. At the 37 spots that are not bathing waters: words in place of the percentage (proposed), or the percentage
   kept with the sentence added, as at bathing waters.
3. If the percentage goes there: whether the estimate still sets the level at those spots. Proposed: not counted,
   as at lakes, since a number judged unfit to show should not set a level unseen. Levels there would come from
   spills alone and could only fall, which is the less cautious direction. **The count, below, is large: over half
   of spot-days.** That changes the recommendation: see the count.
4. Any change to the words. The thirds and the definition of usual are fixed here so that 2027 can judge them.

## The count for decision 3 (17 November 2026)

How many spot-days would show a lower level if the estimate stopped setting it at river spots that are not bathing
waters. Levels as `levels.js` cuts them: spills at 15, 40 and 70 on the exposure index; the estimate at 10%, 25%
and 50%.

**One real in-season day.** The local build of 30 September 2026, all 37 spots: 36 would have shown a lower level.
21 went from high to low, 11 from moderate to low, 2 from very high to moderate, 1 from very high to high, 1 from
very high to low. One stayed at very high.

**The 2025 season, hindcast.** Every day from 1 May to 30 September 2025, lead 0, ERA5-Land rain, production's
figure without soil moisture. 27 of the 37 spots, 4,131 spot-days. The other 10 spots were dropped: the pin this
hindcast places at their position finds no overflow upstream where the site's own pin does. That difference was
not traced.

| | Low | Moderate | High | Very high |
|---|---|---|---|---|
| Level as now | 39.4% | 27.2% | 22.3% | 11.1% |
| From spills alone | 82.2% | 11.5% | 3.7% | 2.7% |

**2,373 of 4,131 spot-days (57.4%) would show a lower level.** 1,112 go from moderate to low and 644 from high to
low. 21 of the 27 spots are raised on more than half of season days now; from spills alone, 2 are.

**What this means for decision 3.** Dropping the estimate from the level would turn most of the season at these
spots to "Low risk from sewage spills". The read found E. coli at places that are not bathing waters running
higher than the estimate says, not lower. So the change would lower the stated level where the evidence points
the other way. **Revised recommendation: leave the level rule as it is.** Show the words in place of the
percentage (decision 2), and let the tile's line say how it stands to the level, as it does now ("This sets the
level above."). The mock-up's "Not counted in the level." would then be wrong and should be changed before
anything is built.

That leaves a level set by a figure the tile no longer prints. The honest form of that is the tile saying so. The
alternative, which keeps everything in view, is decision 2's second option: keep the percentage and add the
sentence, at all 57 river spots.

## What the build still needs (17 November 2026; nothing built)

1. **Each spot's cut-points.** The two figures that split its May to September days of 2023 to 2026 into thirds.
   Made once by a script and committed as a frozen file before 1 May 2027; the site build only reads it.
2. **Which rain makes them. Open.** The site's daily figure comes from Open-Meteo forecast rain. The rain on disk
   for 2023 to 2026 is ERA5-Land, which failed the match check against Open-Meteo's archive (12.1% lower, daily
   correlation 0.879). Cut-points made on ERA5-Land would sit low beside the site's figures, so more days would
   read "higher". Either the cut-points come from Open-Meteo archive rain (calls to be sized against the ration
   first), or the 2026 season's own logged figures set them, which leaves no line until those exist. Not settled.
3. **The site's own pin.** The hindcast for the count placed its own pin and lost 10 of the 37 spots. The script
   must use the pin the build uses.
4. **Soil moisture.** The hindcast figure left it out. The cut-points must come from the figure as deployed.
5. **The page.** One sentence in the in-season river tile (`index.html`), the day's direction in `spots.json`,
   the fallback (no sentence when a spot has no cut-points or an input is missing), tests, an entry in DESIGN.md,
   and the test sentence in the tile's corner fold. Checked at 320, 375 and 1440 px.
6. **The 2027 judgement**, as fixed above, logged from the first in-season build.

Nothing shows before May 2027 whatever is built, since the sentence is in season only.
