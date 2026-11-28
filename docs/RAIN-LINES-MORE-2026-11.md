# Today's rain lines: a 10 km cap, the English beaches the squares missed, and Scotland

Written 28 November 2026. Three items from the pipeline that needed no decision; Ethan said "Yes, build them".

## 1. A 10 km cap

Live on 28 November, Llanishen Reservoir's line took its rain from a square 17 km away. A card's own 0.1 degree square
still counts as "here", as on English beach cards since #764. A neighbouring square now gives a line only if its centre
is within 10 km of the water (`rain_history.MAX_KM`); beyond that the card shows no rain line. The coastal C1 shadow
(#775) is unchanged: it logs each row's distance and its protocol's cell rule is fixed.

## 2. English beaches the squares missed

On 28 November, 344 to 362 of the 407 English beach cards with past samples by rain had today's rain, depending on the
build, from the click-anywhere squares the build already writes. The other 45 to 63 now join the
directory fetch (`build_site.directory_air`, the same 40-cell budget a build, behind the Open-Meteo spare-capacity
check), and their cards take today's rain from those cells (`attach_cached(..., only_missing=True)`). A beach that
already has a square's figure keeps it. The build's health counts them (`coastal.rain_now_cached`).

## 3. Scotland

Each Scottish card gains "Rain here in the 2 days to midday on <date>: <mm> mm (forecast service, fetched <time>)." from
the cells the build already caches for its water temperature, with no comparison: SEPA's conditions of use keep past
samples off the page, so there are no groups to compare it with (`now_line(..., groups=False)`). The card's link to
SEPA's page for its signs, samples and advice stays as it was.

## Checked

`tests/test_rain_history.py`: a neighbour at 12 km gives nothing and one at 7 km is named by distance; a Scottish card
with no past samples needs `require_history` off and shows rain with no groups; a missing English card is filled and a
square's figure is kept. **Not checked:** live counts, which depend on the CI cache; the build's health records them.
