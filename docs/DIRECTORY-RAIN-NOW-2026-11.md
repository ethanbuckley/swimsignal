# Today's rain on Welsh, Northern Irish and Irish cards

Written 28 November 2026. Rank 8 of the [forecast map](FORECAST-MAP-2026-11.md), Wales inland ("Rain word only").
Ethan said "Yes, Wales inland" on 28 November 2026.

## What the site now says

On the coverage page, every card in Wales, Northern Ireland and the Republic that already has "Past samples here by
rain" (#764, #766, #769) gains the line English beach cards have had since #764, under it:

> Rain here in the 2 days to midday on 2026-11-28: 12 mm (forecast service, fetched 28 Nov 06:00). That is as wet as
> the after-rain samples above.

"as dry as the dry-day samples" under 1 mm, nothing extra in between. Where the rain comes from a neighbouring square,
it says "Rain at a point 7 km away". That covers Wales's inland waters with past samples by rain (Llyn Padarn,
Llanishen Reservoir and The Warren at Hay-on-Wye: 3 of 4; Llandeilo Swing Bridge has too few samples after rain or
after dry days) and every Welsh, Northern Irish and Irish beach with them.

## Why this and not the English rain word

The rain word (#763, "more / about / less rain than usual here") was tested on winter samples at English river points
with no overflow upstream. Wales's inland waters have Dŵr Cymru overflows upstream (their data has no licence, so the
site cannot use it), and two are lakes, where the English word was never offered. These cards already carry
something better grounded: what that water's own samples read after rain like today's and after dry days. The
missing piece was today's rain. This line is a count of rain, not a claim, and it says which group today falls in.

## Where the rain comes from

No new request. The build already keeps hourly forecast cells (rain and air temperature) around every directory card
for its water temperature (`build_site.directory_air`, #492): a cell is fetched when no cell within one square of a
card is under 22 hours old, up to 40 a build, inside the Open-Meteo ration. `rain_history.attach_cached` reads those
files: the card's own 0.1 degree square if it has one, otherwise the nearest of the eight around it; fresh by the
file's own fetch time (at most 30 hours old: a restored cache can give an old file a new date); the 48 hours to
midday today at least 90% covered. Because a file can be up to 30 hours old, part of the window can be forecast rather
than recent rain; the line says when its source was fetched.

## How it stands to what is decided (docs/DESIGN.md)

- **Already decided, followed:** the English cards' today's-rain line and its words (#764).
- **New:** the line on Welsh, Northern Irish and Irish cards, the "fetched" time in place of "this build", and "at a
  point N km away" for a neighbouring square (the water temperature line's form).
- ANYWATER-IE's "Limits known now" said Ireland would get no today's-rain line because the English rain squares miss
  it. That limit is lifted by the directory cells, which the build already had.

## Checked and not checked

**Checked:** `tests/test_rain_history.py` (the own square first, a neighbour named by distance, a file too old by its
fetch time, a window under 90% covered, no line without past samples by rain). **Not checked:** how many cards get the
line on a live build; that depends on the CI cache. The build's health records the count per nation
(`rain_now` under `wales`, `ireland`, `northern_ireland`).
