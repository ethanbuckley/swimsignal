# The lake word at the 7 English lake spots whose range is withheld

Written 28 November 2026. Follows [the average-lake check](LAKE-AVERAGE-BASIS-CHECK-2026-11.md), which withheld the
average-lake range at 15 spots because it did not hold when sampled lakes were treated as unknown. Ethan said "Yes,
lake word" on 28 November 2026.

## What the site now says

At Ullswater (Glenridding, Pooley Bridge, near Sandwick), Bassenthwaite Lake, Grasmere, Rydal Water and Elter Water,
on today's day only and May to September only, one sentence after the level's reasons, the same words as at the 5
lakes with no overflow upstream (#767):

- "Today E. coli is estimated higher than usual for this lake." (or "about usual", "lower than usual")

and, among the notes, what it rests on:

> Higher or lower than usual comes from the rain here, spills at the overflows upstream and the time of year. Only its
> order is tested: on past summer samples kept back to test it at Windermere and Frensham Great Pond, days it put
> higher tended to read higher. This lake has no samples, so it was not tested here. How far above or below usual is
> not tested, so the word gives no amount. This is not a level.

No figure, colour or level; the level and what to do are unchanged (tested). The E. coli row still says "Not given
here". `classic/` is unchanged.

## Why order and not the range

The range failed at unknown lakes because the model cannot place an unknown lake's level. The word compares today's
likely reading with the same spot's own figures, so the level drops out: only the order of days within a lake matters,
and a lake's level shifts every day by the same amount. That order was tested where spills drive it: lake-range-v1's
likely reading ordered each lake's own samples at Windermere's four bathing waters and Frensham, 2012 to 2022, years
it never saw, at a mean within-site rho of 0.286, against 0.132 for production's form refitted and 0.102 as deployed (`LAKE-LINE-2012-22-CHECK-2026-11.md`,
corrected rows; #584). Bench read 1 found 0.289 at the 7 lake bathing waters with no overflow upstream, from rain and
the date alone.

What is not known: whether the order holds at these 7 lakes, which have no samples; and how well 1 overflow upstream
(6 of the 7; Bassenthwaite has 16) moves the figure there. Nothing can check these until someone samples them.

## Usual

The middle third of each spot's own figures on every May to September day of 2023 to 2026: lake-range-v1's likely
reading on the average-lake basis (the figure the forecast computes and logs there), from archive rain at the spot
(48 and 24 hours to midday) and spill exposure hindcast at lead 0 from the overflows upstream (`validate_ecoli.hindcast`,
as #584 and the bench built it). Higher is above two thirds, lower below one third, compared on log10 at 3 decimal
places, as at the other lakes. Frozen in `data/processed/lake_order_overflow.v1.json` (`0fd17fea…`), tied to
lake-range-v1's hash; 588 to 590 days per spot, a third each way (`scripts/lake_order_overflow.py`).

**Requests.** 4 Open-Meteo archive requests for the 10 cell-years not already cached (one cell for 2023 to 2025,
seven cells for 2026), into a scratch cache: about 26 weighted calls by the hindcast's own weighting. The other 38
cell-years came from copies of the cache. The shared `data/raw`, `data/processed` and `data/cache` had no file or
directory with a status change during the run. (The first fingerprint of them was computed from unsorted `find`
output, so it could not be compared; the status-time check replaced it.)

## The 8 Scottish loch spots

Loch Ness (Dores) and Loch Lomond ×7 keep "Not given here" and get no word. The order was tested at English lakes, and
their overflows come from the Scottish trial's data, which is behind `DIPCAST_SCOTLAND_TRIAL`. A word there would need
its own reason; none is built.

## How it stands to what is decided (docs/DESIGN.md)

- **Already decided, followed:** the lake word's form, place and words (#767), a spot's own thirds (the river order
  line, 17 November 2026), today only where the test was at lead 0.
- **New:** the word at lakes with overflows upstream, and its note.

## How it will be judged

There is no sample here to judge it with. The order it rests on is judged again by the 2027 read of
`shadow_lake_range_v1` at Windermere and Frensham (on or after 15 October 2027). If that read finds the order no
better than production's, the word comes off these 7 too.

## Files

`data/processed/lake_order_overflow.v1.json`, `scripts/lake_order_overflow.py`, `src/dipcast/lake_order.py` (both
files merged in `cuts`), `src/dipcast/model/forecast.py` (the word where the range is withheld),
`src/dipcast/site/levels.js` (`LAKE_ORDER_UP_SAID`), `src/dipcast/site/preview/model.js` (`answer`),
`tests/test_lake_order_overflow.py`, `tests/test_lake_order.py`, `tests/site_preview.test.cjs`.
