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
| 1 | **England's coast** | 404 bathing waters with samples | A rain word ("heavy rain here in the last 3 days") with the beach's own past samples after rain like that. A "higher than usual after rain" word only if the frozen test passes. Never a chance or a level: best skill on seen years is 3.4% | Seen years only: rain is the one input that helped, 2022-26 (COASTAL-BASELINES) | C1 had not run: its rain fetch was waiting on Open-Meteo budget. **ERA5-Land rain for 2012 to Aug 2026 is now on disk** (CDS, 176 monthly files), so the test needs no Open-Meteo call | Days, if C1 passes on 2012-21 |
| 2 | **Wales and Northern Ireland coast** | 112 + 33 | The same word, from England's frozen model, scored on Welsh and NI samples it never saw (ANYWATER) | Nothing yet | C1 must pass first. Per-sample Welsh results need one NRW archive fetch (answers this Mac, OGL). NI samples are held. Rain is on disk (box reaches 8.3° W) | A week after rank 1 |
| 3 | **Republic of Ireland coast and lakes** | 210 | As rank 2 | Nothing | Outside the UK. Rain box stops at 8.3° W: one more CDS download, free | After rank 2, optional |
| 4 | **Scotland's coast** | 90 | Rain word and a link to SEPA's own sign. No past samples | Nothing | SEPA's terms forbid republishing its samples (Ethan's contact). SEPA runs its own predictions at 30 beaches | When SEPA answers |
| 5 | **England rivers with no overflow upstream** | 15 spots (they read "nothing upstream" every day now) | A rain word, all year | Rain ordered winter days at such points at 0.458 (0.326 to 0.521), seen rows; a sealed reserve read exists | One read of the reserve, then wording | Days |
| 6 | **England lakes without their own samples** | 7 bathing lakes (bench read 1 passed for the likely reading's order) + 20 lake spots with no daily level | "Higher or lower than usual for this lake", order only | 0.289 against −0.015 on 2012-22, unseen (bench read 1) | Ethan's choice of what to show (register, BACKTEST-BENCH row) | When decided |
| 7 | **Scotland inland** | 12 now, more with access statements | The trial forecast | 2021 frozen backtest passed at lead 0; live shadow not yet | A switch (Ethan's), and Gate B in February | Already built |
| 8 | **Wales inland** | 4 bathing waters, plus rivers | Rain word only | Nothing | Dŵr Cymru's overflow data has no licence | Rain word: after rank 5 |

## What I am building first

Rank 1: run C1 as its protocol says, with one amendment made before any rain value is read: the rain comes from
the CDS ERA5-Land download instead of Open-Meteo's `era5_land` copy of the same dataset, and a sampling point whose
0.1° cell is sea takes the nearest land cell. Fit and freeze on 2022-26, fetch the unread 2012-21 samples, score
once. A pass puts a labelled coastal observation on each English beach's page. A fail says so and closes this route
at this resolution, not the coast.
