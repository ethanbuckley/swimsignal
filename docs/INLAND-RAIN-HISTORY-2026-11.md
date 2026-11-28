# Past samples by rain at Irish, Welsh and Northern Irish lakes and rivers

Written 28 November 2026. Rank 3 of the [forecast map](FORECAST-MAP-2026-11.md), the part
[ANYWATER-IE](ANYWATER-IE-STATEMENT-2026-11.md) left open: "Inland Irish waters do not get the line yet ... A lake
version needs its own threshold first." Ethan said "Yes, Irish lakes" on 28 November 2026.

## What the site now says

On the coverage page, an inland water's card (lake or river) in the Republic, Wales and Northern Ireland gains the
line the beach cards already have, counted over 900 instead of 500:

> Past samples here by rain, 2014–2026: after 10 mm or more of rain in the 2 days before, the middle of 38 read 96
> (6 over 900); after 2 dry days (under 1 mm), the middle of 54 read 30 (6 over 900). E. coli per 100 ml. Not a
> forecast

(Lilliput, Lough Ennell.) Above each list, after the sentence on what was tested, one sentence: "At lakes and rivers
the lines count results over 900, the inland line, and they were not tested: the test was on the coast." The note
says "each water's own samples" where a list has inland waters.

900 is the inland E. coli line the sample history already uses (`lines` in `sample_history_ireland.v1.json`) and the
"Past samples" line on the same cards (`typical.LINES`): the Bathing Water Directive's "sufficient" line for inland
waters. Same rain rule as the coast: ERA5-Land at the water's 0.1° cell, 48 hours before a sample taken at 12:00
local time where only the date is given, 10 or more samples in a group.

## Which waters

25 inland waters have rain and samples: 20 in the Republic (1,365 samples), 4 in Wales (117), 1 in Northern Ireland
(75). 14 have a group with 10 or more samples, so 14 cards show the line: 9 Irish lakes, 3 Welsh waters and
Northern Ireland's one inland water. The other 11 have too few samples after rain or after dry days. England's inland
bathing waters have spot pages and are not in this file.

## What it rests on

Nothing was tested for inland waters. These are counts of each water's own past samples, the same kind of line as
"Past samples" beside it. ANYWATER-IE reported C1's order on the Irish inland samples (0.205, 0.058 to 0.331; rain
+0.119, +0.023 to +0.237) and said that number decides nothing, because C1 was built for beaches and the statement
fixed that inland waters get the line "with no tested label whatever the inland figure says". The page follows that.

Pooled, for this record only (not on the page): in the Republic's inland waters 4.8% of samples after 10 mm or more
of rain were over 900, against 1.8% after 2 dry days.

## How it was made

`scripts/coastal_c1/export_rain_history.py` now keeps inland waters and writes `line: 900` and `over_900` counts for
them (file version 1.2.0, additive). Every coast entry and every nation's pooled coast figure came out the same as in
the committed 1.1.0 file (checked entry by entry). The nations gain an `inland` block. Offline: the scratch inputs
(C1's fetch and rain, ANYWATER-UK's and ANYWATER-IE's samples and rain) hashed the same before and after. No request.

## How it stands to what is decided

- **Already decided, followed:** the beach cards' rain line and its words (#764, #766); 900 as the inland line in
  every inland past-samples line (`typical.py`); ANYWATER-IE's rule that inland waters carry no tested label.
- **New:** the line at inland waters, and the note's inland sentence.

## Next

A tested version would need inland samples no model has seen, scored against a statement written first. The 2027
Irish, Welsh and Northern Irish inland seasons are the first such rows: a frozen-model read of C1's order on them, at
the 900 line, after the season (owner: research sessions; check on or after 15 October 2027).
