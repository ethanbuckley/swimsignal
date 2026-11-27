# What SwimSignal could forecast, and where: 25 November 2026

One page. Counts are from files in the repository on 25 November 2026 (main `7b704b8e`), named in each row.
"Places" means places a swimmer could look up. Ranked by places added, then by how soon it could be on the site.

## Today

- **England inland:** 133 spots. A daily level at 98 (spill forecast). 35 have no monitored overflow upstream
  (15 rivers, 20 lakes) and read the same every day. In season: an E. coli chance at rivers, a likely reading with
  a range at 11 lake bathing waters. Winter river word on at 69 river spots since 25 Nov. Tap-anywhere on English
  rivers and lakes.
- **Scotland:** 12 trial spots behind `DIPCAST_SCOTLAND_TRIAL`.
- **Everywhere else:** directory cards with past samples only. England's coast 404 of 426, Wales 112 of 114,
  Northern Ireland 33 of 33, Republic of Ireland 210 of 243 (`data/research/typical_*.v1.json`).

## The map

| Rank | Water | Places added | What we could honestly say | What is tested | What stands in the way | On the site |
|---|---|---|---|---|---|---|
| 1 | **England's coast** | 404 bathing waters with samples | A rain word ("heavy rain here in the last 3 days") with the beach's own past samples after rain like that. A "higher than usual after rain" word only if the frozen test passes. Never a chance or a level: best skill on seen years is 3.4% | **Passed 25 Nov on 2012-21, unseen:** rain improved the over-500 chance (Brier −0.00041, interval below zero, 9 of 10 seasons; AUC 0.786 against 0.665) | Nothing for the card lines. A chance would need calibration and a 2027 shadow | **Live 26 Nov** (#764) |
| 2 | **Wales and Northern Ireland coast** | 112 + 33 | The same lines, from England's frozen model | **Passed 25 Nov:** on 7,019 Welsh and NI samples it never saw, within-beach order 0.303 (0.245 to 0.338); rain adds +0.122 | C1 must pass first. Per-sample Welsh results need one NRW archive fetch (answers this Mac, OGL). NI samples are held. Rain is on disk (box reaches 8.3° W) | **Live 26 Nov** (#764) |
| 3 | **Republic of Ireland coast and lakes** | 210 | As rank 2 | **Passed 27 Nov:** on 24,413 Irish samples 2014-26 it never saw, within-beach order 0.320 (0.274 to 0.356); rain adds +0.083 | Done: one CDS download over Ireland (65 months). Lakes need a 900 line first | **On the site with the ANYWATER-IE PR** (coast and estuary) |
| 4 | **Scotland's coast** | 90 | Rain word and a link to SEPA's own sign. No past samples | Nothing | SEPA's terms forbid republishing its samples (Ethan's contact). SEPA runs its own predictions at 30 beaches | When SEPA answers |
| 5 | **England rivers with no overflow upstream** | 15 spots (they read "nothing upstream" every day now) | A rain word, all year | Rain ordered winter days at such points at 0.458 (0.326 to 0.521), seen rows; a sealed reserve read exists | Passed 25 Nov: 0.415 (0.287 to 0.495) on reserve winters | **Live 26 Nov** (#763) |
| 6 | **England lakes without their own samples** | 7 bathing lakes (bench read 1 passed for the likely reading's order) + 20 lake spots with no daily level | "Higher or lower than usual for this lake", order only | 0.289 against −0.015 on 2012-22, unseen (bench read 1) | Ethan's choice of what to show (register, BACKTEST-BENCH row) | When decided |
| 7 | **Scotland inland** | 12 now, more with access statements | The trial forecast | 2021 frozen backtest passed at lead 0; live shadow not yet | A switch (Ethan's), and Gate B in February | Already built |
| 8 | **Wales inland** | 4 bathing waters, plus rivers | Rain word only | Nothing | Dŵr Cymru's overflow data has no licence | Rain word: after rank 5 |

## What I am building first

Rank 1: run C1 as its protocol says, with one amendment made before any rain value is read: the rain comes from
the CDS ERA5-Land download instead of Open-Meteo's `era5_land` copy of the same dataset, and a sampling point whose
0.1° cell is sea takes the nearest land cell. Fit and freeze on 2022-26, fetch the unread 2012-21 samples, score
once. A pass puts a labelled coastal observation on each English beach's page. A fail says so and closes this route
at this resolution, not the coast.

## Result, 25 November 2026

C1 passed: "supported on unseen seasons" (`docs/COASTAL-C1-PROTOCOL-2026-11.md`, results). Rank 2 (Wales and
Northern Ireland) is now open to test.
Wales and Northern Ireland passed too (`docs/ANYWATER-UK-STATEMENT-2026-11.md`).

## On the site, 26 November 2026

- 545 beach cards in England, Wales and Northern Ireland: past samples by rain, and today's rain on English cards (#764).
- 15 river spots with no overflow upstream: a rain word, "more / about the usual / less rain than usual here" (#763).
- Research Lab exhibits 6 (overflow ledger, #757) and 7 (a river's bad days, #761); exhibit fixes (#758).
- The redesign links the Lab, Research and the coverage page (#756); each place's page and the method page say what
  each figure was tested on (#759); the home page's research line is back (#762).

## 27 November 2026

The Republic of Ireland passed the same transfer test (`docs/ANYWATER-IE-STATEMENT-2026-11.md`): 220 Irish coast and
estuary cards get past samples by rain. Next, by places added: lakes without their own samples (your choice from
bench read 1), then Irish lakes with a 900 line.
