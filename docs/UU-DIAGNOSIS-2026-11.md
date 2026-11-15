# Why every spill-model candidate fails at United Utilities: a diagnosis, stated before any run

Written 13 November 2026. This is a diagnosis, not a new model and not an adoption test. Nothing here changes a
verdict, a frozen file, an issued forecast, an active window or the 2027 primary evaluation. The hypotheses, the
checks and what each result leads to are fixed above the line at the end. Results go below it. Nothing above the
line changes after a result is seen.

**Every row used here has been seen.** The January to August 2026 rows were scored by #357, #639 and #666, and the
2024 and 2025 rows by many tests. So everything below the line is exploratory development evidence. It can rank
explanations and size them. It cannot confirm a model.

## The three failures to explain

All on January to August 2026, at United Utilities' overflows, against production (`spill_model.pkl`).

| Record | Candidate | Result at United Utilities |
|---|---|---|
| [#357](NINE-COMPANY-MODEL-V2-TEST-2026-11.md) | v2 arm (b): nine-company pooled layer plus two-year offsets | Brier 0.03902 against 0.03774, +3.4%, interval [+0.00007, +0.00261]. The other eight companies: 11% to 23% better |
| [#639](LIVE-STATUS-BACKTEST-2026-11.md) | Live status: the 2024 nine-company model (D2) plus three status inputs | Lead 0: −0.0030 [−0.0057, +0.0003]. Leads 1 to 4: +0.0009 to +0.0015, intervals spanning zero. Forecast rain, lead 4: +0.0081 [+0.0015, +0.0161] on 12,773 rows |
| [#666](COMBINED-CANDIDATE-BACKTEST-2026-11.md) | combined-v1: production at United Utilities plus the status uplift | Lead 0: −0.0043 [−0.0063, −0.0024]. Leads 1 to 4: −0.0003 to +0.0002, intervals spanning zero. Forecast rain, lead 4: +0.0057 [+0.0012, +0.0114] |

[Regional routing](REGIONAL-ROUTING-2026-11.md) keeps United Utilities on production because of the first row.

## Established before this diagnosis (from the records, not rechecked here unless a check says so)

- **Production is a United Utilities model.** Both layers were fitted on United Utilities alone: the pooled layer
  on its 2023 to 2025 Stream event files, the per-overflow offsets on the same rows with recency 0.25, so 2025
  carries 76% of an offset's weight ([provenance](MODEL-PROVENANCE-2026-10.md), which reproduced all 2,271 stored
  offsets exactly).
- **Its lead map is a United Utilities map.** `lead_calibration.json` says `model` "United Utilities 2023-2024;
  verified on 2025", fitted on 2025.
- **v2 and D2 are nine-company models with no company input.** v2: EA start/stop files, 2024 and 2025, offsets at
  recency 1. D2: 2024 only.
- **The hold-out model ties v2 at United Utilities.** `spill_model_holdout_2025.pkl` (United Utilities 2023-24)
  scored 0.03896 on #357's rows, v2 arm (b) 0.03902. So production's edge over both is about 3%.
- **Recency did not decide #357.** Arm (b25), the same model at recency 0.25, scored 0.03900.
- **The two label sources nearly agree.** Spill-days in United Utilities' 2024 Stream file and EA file: 76,958
  shared, 846 only in Stream, 1,333 only in the EA file. 2025: 61,764 shared, none on either side alone
  ([earlier history](EARLIER-SPILL-HISTORY-2026-10.md)).
- **Where #357's loss sits by month.** v2 against production at United Utilities: January +9.8%, February +9.9%,
  March −0.6%, April +4.5%, May +1.8%, June −0.5%, July −4.5%, August −0.4%. In January v2's mean forecast was
  0.094, production's 0.078, observed 0.057.
- **United Utilities' January 2026 was low.** 4,010 spill-days against 10,052 and 8,348 in the two Januaries
  before, with similar rain and no missing day (#357's data check). Cause unknown.
- **Short events rose.** The share of United Utilities' spill-days that come only from events under 15 minutes was
  13.5% in v2's training rows and 18.0% in the 2026 test rows.
- **Rain.** With perfect rain the spill model gained little (#343). Radar at each overflow's own position was no
  better than the cell's radar (#640).
- **The fallback in the backtests.** 21 to 33 rows of 3.26 million took #262's fallback in #639, all in the first
  days of January. The EA file is a complete record, so nothing in it is stale.

## Rows and inputs

**Rows.** #639's rows, United Utilities only, rebuilt by its own code (`scripts/live_status_backtest_2026.py`):
UTC days, 1 January to 31 August 2026; #357's window E (a position and EDM operation of at least 50% in the 2025
return, a monitor that passes option B's dead-monitor check over 5 October to 1 November); ERA5-Land rain; a
spill-day is a UTC day an EA 2026 event touches. #639 counted 2,219 overflows and 539,217 rows there, and 12,773
forecast-rain rows at each lead.

**Training-year rows, for the refitted offsets and the descriptions:** United Utilities' 2023 to 2025 rows as
production saw them (`scripts/check_model_provenance.py`'s rule, Stream labels, UTC days), and its 2024 and 2025
rows by v2's rule (`training.site_years`, EA labels), also on UTC days.

**No row after 31 August 2026 is scored.** The only later input is the poll-count file the dead-monitor check
reads (known, unknown and stale polls per overflow and day, no spill outcome), the same file #666 used. Check C7
also reads poll counts for 5 to 17 October, before lead calibration B's window opens on 18 October. No forecast,
label or score from lead calibration B, the ensemble-rain test, the live-status shadow, A8, regional routing or
option B is read.

**Inputs, read-only, hashed before and after.**

| Input | SHA-256 |
|---|---|
| Production, `data/processed/spill_model.pkl` | `faa7917e2be725a9441b277fc111091c5bdffe45c80ab4fd042682aa9de4210e` |
| Hold-out, `data/processed/spill_model_holdout_2025.pkl` | `882f9d4fb2c9314943fa861d8c6f4c62d8cd1eb57f1aa25059f4eb27d07068dc` |
| v2 arm (b), `data/processed/regional/spill_model_v2_offsets.pkl` | `9e0fc54a9356e4cea528606422dc569691453fc3ab98ea31986f19437ba501f2` |
| v2 arm (a), pooled layer alone (private baselines folder) | `bd8faaaf31031fa3ca8ac763dc7047c9b591ffe37feddb220b7e52d73b1f2dc3` |
| D2 (private baselines folder) | `1603678923ccdd1553830fa67c2069714c0a836c9df7e8c52578aabd729b5bcc` |
| Live-status candidates, leads 0 to 4, `data/processed/live_status/` | as in #639's statement |
| Production's lead map, `data/processed/lead_calibration.json` | `734202bc7f22af38fd72d65c4038bb51828b11f5436ed1de40ffa0f381ad0f09` |
| Annual returns, `data/processed/annual_returns.parquet` | `9f8604f9bbea29b993deadaf70ca92ae9a08050aaa717a731c58e8269db45065` |
| EA 2026 zip (the bytes #357, #639 and #666 used) | `d0dbf32fb8622f98fe072466598d706590e5f8e667619cba7d0639c6555a1a8f` |
| Poll counts, `live_coverage.parquet` (#666's file) | `a5bbf9506a1f0b211364d7eb3dcd7f020d1c6bf1bd57d0e08e62a64c3c1816be` |
| United Utilities' Stream events 2023-25, `edm_events.parquet` (main checkout) | `4ef2c254706f06ce619371a8e8061c1da2a8b5c6f2a39e9b4f5c791c18f31983` |
| United Utilities' EA events 2024-25 (17 Oct import, main checkout) | `c245fb7cd382d3f42c4603f7d8b7f98ce6cf119422f13b4ba6b09f56c5809d9c` |
| United Utilities' EA events 2026 (#666's import of the zip above) | `54aeb21abf61162fc12f911a302d4c6f36a7460f60267d8b972ddfd9f46d0ea1` |

Rain is the main checkout's cache (`data/cache/rain`, `data/cache/rain_nine`), for United Utilities' cells only,
and the cell radar in `data/raw/met_office_radar`, to 31 August 2026 only. Their file listings are hashed before
and after. **No Open-Meteo call and no download.** The run uses a scratch `DIPCAST_ROOT`, `DIPCAST_STATE`, cache
folder of links and output folder. About 540,000 test rows and 2.4 million training rows, one process.

Seen while preparing, and nothing else: file names, column names, date ranges and hashes of the inputs above; the
published tables of the records named. No forecast was computed and no label was joined for this diagnosis.

## The interval

#357's two-way cluster bootstrap, on the United Utilities rows: each draw resamples overflows with replacement
and, independently, ISO weeks of the target day with replacement; 2,000 draws from
`numpy.random.default_rng(20261113)`, made once and shared by every comparison. The 95% interval runs from the
2.5th to the 97.5th percentile. There are about 36 ISO weeks and 2,219 overflows, so the week side is coarse. Intervals
are for sizing. No threshold decides an adoption here.

## The gap, and how a check is read

**G1, the base-model gap:** v2 arm (b) minus production, Brier, on the ERA5-Land rows. #357 measured +0.00128
(0.03902 against 0.03774) on UK local days; these rows are UTC days, so G1 is measured again here and may differ
a little. **G2, the status gap at lead k:** #639's candidate with fallback minus production,
and combined-v1 minus production.

Each check gives a part of a gap with its interval. The labels, fixed now:

- **Main cause:** the part is at least half of the gap and its interval excludes zero.
- **Contributes:** its interval excludes zero and it is under half.
- **Not shown:** its interval includes zero.
- **Ruled out as the main cause:** the upper end of its interval is under a quarter of the gap.
- **Not testable on these rows:** said plainly, with what would test it.

Parts need not add up to the whole. Two explanations can share the same rows.

## Face checks first (C0). The run stops on any failure

1. Every input hash above matches.
2. Production (0.03793), D2 (0.04195), the lead-1 live-status candidate (0.03886) and combined-v1 at lead 1
   (0.03772) reproduce the United Utilities Brier in #639's and #666's committed score tables to within 0.00005,
   and the row and overflow counts match (539,217 and 2,219). v2 arm (b) was never published on these UTC rows;
   it must come within 0.0003 of #357's 0.03902.
3. Production's stored offsets are reproduced exactly from the rebuilt Stream rows at recency 0.25 (the provenance
   check's test), on United Utilities' cells.

## Hypotheses and the check that separates each

### H1. Production's pooled layer is a specialist

*Claim.* A pooled layer fitted on United Utilities alone holds the company's own response to rain and season. A
nine-company layer with no company input holds the average response. An offset moves an overflow's level, not its
response, so two-year offsets cannot repair it.

*Check C1, a swap of layers on the same rows.* Offsets are refitted by `fit_site_offsets` (prior 15) as a
diagnostic. None of these arms is a candidate, and none is saved as a model.

| Arm | Layer 1 | Layer 2 |
|---|---|---|
| P | production's | production's stored offsets (Stream 2023-25, recency 0.25) |
| P-none | production's | none |
| P-EA | production's | refitted: EA labels, 2024 and 2025, v2's overflow-years, recency 1, UTC days |
| P-Stream2 | production's | refitted: Stream labels, the same overflow-years as P-EA, recency 1 |
| P-Stream3 | production's | refitted: production's own rows (Stream 2023-25), recency 1 |
| V | v2's | v2's stored offsets (fitted on UK local days in #357's run) |
| V-none | v2's | none (v2 arm (a)) |
| V-EA | v2's | refitted on exactly P-EA's rows |
| H | hold-out's | hold-out's stored offsets |
| H-EA | hold-out's | refitted on exactly P-EA's rows |

- **The layer-1 part of G1** is V-EA minus P-EA: two layers, the same offset rows, labels and recipe. V-none minus
  P-none is reported beside it. H-EA minus P-EA shows what 2025 adds to a United Utilities layer 1.
- H1 is the main cause if V-EA minus P-EA is at least half of G1 with its interval above zero.

### H2. Production's offsets carry more of the company's own history

*Claim.* Three years, weighted to the newest, on the company's own Stream record give better levels than two
years of EA files.

*Check, from C1's ladder on production's layer:* P-EA to P-Stream2 (label source), P-Stream2 to P-Stream3 (a third
year and production's row rule), P-Stream3 to P (recency 0.25). The offsets part of G1 is P-EA minus P. H2 is the
main cause if that is at least half of G1 with its interval above zero. Reported: how many test overflows have an
offset in P only, in V only, in both and in neither, and G1 within each group.

### H3. The labels differ

*Claim.* United Utilities' Stream record and the EA file count different spills, or the 2026 file counts short
events differently from the training years.

*Checks.* (a) The step P-EA to P-Stream2 above: the same layer, rows and recipe, two label sources. (b) C3: G1
rescored with the 2026 spill-days that come only from events under 15 minutes counted as dry, and the monthly
share of such days in 2024, 2025 and 2026. H3 is the main cause if (a) is at least half of G1, or if (b) removes at
least half of G1. The established 2024 and 2025 agreement (above) makes (a) unlikely.

### H4. United Utilities spilled less in 2026, and the lower forecaster won

*Claim.* The loss is a level effect in one year: fewer overflows spilled per storm in January and February 2026,
both models forecast too high, and v2 was higher.

*Check C2, on the 2026 rows, in hindsight for both P and V.* Each model's log-odds are recalibrated on the scored
rows themselves: (i) one constant; (ii) a constant and a slope; (iii) one constant per calendar month. This
flatters both models equally. Only the change in G1 from step to step is read.
- G1 closes by half or more under (i): a level effect, H4.
- It closes only under (iii): a seasonal shape, which belongs to H1.
- It closes under (ii) and not (i): the response to rain is too steep or too flat, H1.
- It closes under none: the loss is in the order of overflow-days inside a month.

*Check C4, the same question on years with no 2026 in them.* Mean forecast against observed rate by month for
2024 and 2025 at United Utilities, for P, V and both pooled layers alone. Both sets of offsets saw those years, so
this describes shape, not skill. If v2's winter excess over production is there in 2024 and 2025 too, the cause is
structural (H1). If it appears only in 2026, it is that year (H4).

*Check C4b, the mix of overflows.* G1 by thirds of the 2025 return's long-term spill count; by whether the
overflow's January to August spill-day rate fell, held or rose from 2024-25 to 2026 (grouped on the outcome,
labelled so); and the share of G1 carried by the 5% of overflows with the largest contributions, with G1
recomputed without them.

### H5. Rain resolution in upland cells

*Claim.* ERA5-Land smooths rain over 10 km. In the Lake District and the Pennines it is wrong in ways a United
Utilities-only layer has learned to live with and a pooled layer has not.

*Check C5, with the cell radar, 1 December 2025 to 31 August 2026.* An hour counts when radar `coverage` is at
least 0.9 (#343's rule); a day when at least 20 hours count.
- Per United Utilities cell: the mean absolute difference between ERA5-Land's and the radar's daily totals,
  divided by the radar's mean daily total; and the cell's mean ERA5-Land daily rain as a stand-in for upland.
- G1 within thirds of cells by each measure, with intervals.
- A common swap: P and V rescored with rain features built from the radar instead of ERA5-Land, on the rows where
  the radar covers the day and the 30 days before. Neither model was fitted on radar, so only the change in G1
  between the two rain sources, on the same rows, is read.
- H5 is the main cause if G1 in the top third of disagreement is at least twice G1 in the bottom third with
  intervals that do not overlap, or if the radar swap removes at least half of G1. Otherwise not shown or ruled
  out by the rule above.

### H6. The lead map

*Claim.* On forecast rain, production is shown after an isotonic map fitted on United Utilities. The candidates
have no map. So at long leads, where forecast rain is worse, production is pulled toward the base rate and the
candidates are not.

*Check C6, the 12,773 forecast-rain rows at each lead.* Brier and mean forecast against the observed rate for:
#639's candidate; production raw; production mapped; and, as a diagnostic only, #639's candidate passed through
production's lead-k map. H6 is the main cause of the lead-4 forecast-rain loss if the candidate's loss against
mapped production is at least halved against raw production. Few cells carry these rows; the count of cells is
reported and the interval is wide by construction.

### H7. The stale-feed fallback

*Claim.* #262's fallback fires more at United Utilities, so the candidate there is mostly production.

*Check C7.* The count of United Utilities rows that took the fallback at each lead in the rebuilt rows (expected
under 33). That settles it for the three recorded failures, which are all on the EA's complete record. Whether
the fallback fires more at United Utilities on the live polls belongs to the live-status shadow, read on or after
23 November, and is **not read here**. One input-only description is given: the share of polls counted stale or
unknown per company over 5 to 17 October, poll counts only.

### H8. The status adds less at United Utilities

*Claim.* Two parts. (a) At the other eight companies production has no offsets, so "spilled lately" partly stands
in for the overflow's level, which production already holds at United Utilities. (b) United Utilities' spills
are shorter and less persistent from day to day, so yesterday says less about tomorrow.

*Check C8.*
- (a) Per United Utilities overflow: the mean lead-1 uplift (log-odds of the candidate minus log-odds of D2)
  against the overflow's 2026 level error, log of observed over expected spill-days, for D2 and for production.
  Rank correlation across overflows, interval from resampling overflows. Part (a) is supported if the uplift
  tracks D2's level error with an interval above zero and does not track production's.
- (b) The chance of a spill-day given a spill-day the day before, against the chance given none, at United
  Utilities on these rows; and, from #666's committed score table, same-day persistence's Brier skill over the
  company's flat rate at each of the nine companies. Part (b) is supported if United Utilities ranks in the
  bottom three of nine for persistence skill.
- (c) Where the lead-0, lead-1 and lead-4 uplift lands: combined-v1 minus production on rows spilling at issue,
  rows not spilling at issue with a spill-day in the last seven, and dry starts, each with its interval.

### H9, added by this diagnosis. The gap is a few overflows

Covered by C4b's concentration figure. If the 5% of overflows with the largest contributions carry at least half
of G1 and G1 without them has an interval spanning zero, the loss is local, and the next step is to look at those
overflows (upgrades, monitor changes) and not at the model form.

## The ranking

Hypotheses are ranked by the share of the gap their check accounts for, with the label and interval beside each.
Where two checks account for the same rows, both are said to.

## What each result leads to, fixed now

The diagnosis ends in one of two ways.

**Ending A: a named, bounded next candidate for United Utilities.** Taken only if a check finds a specific,
correctable deficit: an arm built only from data before 2026 that beats production on these rows with its
two-way interval wholly below zero, or a status effect at United Utilities that is below zero with its interval
on rows where the label is not already settled at issue time. The candidate is then named and described, not
built here, with the fresh test it would face. A candidate named here was chosen on seen rows, so its test must be
on rows nobody has scored: the EA's September to December 2026 records when published, or the United Utilities
rows of a shadow log whose bar is stated before its read.

**Ending B: production stays at United Utilities.** Taken if no check finds that. The record then says which
explanations are supported, which are ruled out, and what new evidence would reopen the question.

By finding:

| Finding | What follows |
|---|---|
| H1 main cause | Ending B for the base model: a pooled layer with no company input is not expected to beat production there. Reopen with a layer that can hold a company's own response, tested on rows not yet seen, or when United Utilities' behaviour drifts from production's fit |
| H2 main cause | Ending A is possible: v2's layer with production's offset recipe at United Utilities, if that arm's interval is below zero against production; else ending B |
| H3 main cause | A label-alignment note for #357's successors and for the live-status shadow's reading; ending B for the model |
| H4 main cause (one year's level) | Ending B, with the statement that #357's loss is not evidence against v2's form; reopen on the EA's September to December 2026 records |
| H5 main cause | Ending A is possible: a rain-source test at United Utilities' upland cells, under its own statement |
| H6 main cause of the lead-4 loss | A note for the 23 November switch decision: the comparison at long leads is partly the map. Ending A is possible: the candidate with a lead map at United Utilities, tested on the shadow's rows |
| H7 | No effect on the recorded failures; the live question is left to the 23 November read |
| H8 supported | Ending B for leads 1 to 4. For lead 0, ending A only if (c) shows a gain on rows not spilling at issue |
| H9 | A list of the overflows and what to check at each; ending B for the model |
| Nothing reaches "main cause" | Ending B, with the ranked partial explanations and what would separate them |

Inconclusive is a result. If the intervals are too wide to rank two explanations, the record says so and names
the data that would separate them.

## Not done here, and why

- **No refit of any pooled layer.** A new layer 1 would be a new model. Offsets are refitted because the formula
  is closed-form and the arms exist only to hold one layer fixed while the other changes.
- **No rows from the other eight companies are rebuilt.** Where a contrast with them is needed it comes from the
  committed tables of #357, #639 and #666.
- **No poll-based status and no live forecast log.** They sit inside unread windows.
- **No Open-Meteo call.**

## Order of work

1. This statement is pushed before any forecast is computed or any label joined.
2. The script (`scripts/uu_diagnosis.py`) is committed before its run.
3. Inputs are hashed, the face checks run, then every check once.
4. Results go below the line. The register row and the research catalogue entry are added in the same PR.

---

## Results

### Addendum, stated on 13 November after the main run was read and before the addendum was run

The main run (script commit `ffe4d704`) finished and its tables were read. Two of its results need one more
figure each. This is stated and pushed before the addendum script runs. It is chosen after seeing results, so it
is weaker evidence than the checks above the line, and it is labelled so wherever it is used.

**What was seen that prompts it.** C8(c) split combined-v1 minus production by status at leads 0, 1 and 4. On rows
where the overflow was spilling at the issue time, combined-v1 was lower at lead 1 (−0.0364 [−0.0816, −0.0029],
4,133 rows) and at lead 4 (−0.0295 [−0.0644, −0.0024], 4,050 rows). On every other row it was not shown either
way. Leads 2 and 3 were not in the stated split.

**A1.** The same split (spilling at issue, and not) at leads 2 and 3, combined-v1 minus production, with the same
bootstrap draws.

**A2.** The narrow rule as a whole: production's chance, with combined-v1's uplift added only where the overflow
is spilling at the issue time, minus production, on all 539,217 rows at each of leads 1 to 4, with the two-way
interval. On the spilling rows: the observed rate and each mean forecast. On the 12,773 forecast-rain rows at
each lead: the same rule on mapped production, minus mapped production.

**A3.** No new run: from the main run's saved per-overflow sums, the 5% of overflows where v2 gains most, beside
the 5% where it loses most (C4b's concentration figure took only the losing end).

Nothing else is added. The addendum uses the same rows, models and seed.

### The run

Run on 13 November 2026, offline, from a `git archive` of script commit `ffe4d704` (main run) and `9489020d`
(addendum), with a scratch `DIPCAST_ROOT`, `DIPCAST_STATE`, a scratch cache of links to United Utilities' 188 rain
cells and a scratch output folder. Peak memory 1.2 GB, about nine minutes. The statement above the line was pushed
in `b3a8413d` before any forecast was computed. Tables beside this file: `-arms.csv`, `-differences.csv` (every
comparison with its interval), `-monthly.csv`, `-forecast-rain.csv`, `-short-events.csv`, `-addendum.csv`,
`-results.json`.

- **Face checks.** Production 0.0379333, D2 0.0419537, live status at lead 1 0.0388601 and combined-v1 at lead 1
  0.0377208: each equals the committed figure to seven places. 539,217 rows, 2,219 overflows, 36 ISO weeks, 29,282
  spill-days, 12,773 forecast-rain rows at each lead. v2 arm (b) scores 0.03925 on these UTC days (0.03902 on
  #357's local days). All 2,271 of production's stored offsets are reproduced exactly from 2,404,632 Stream rows.
- **A first attempt stopped at face check 3**, as stated, with 2,269 of 2,271 offsets exact. The two others are in
  one cell (55.0, −3.2). Cause, confirmed: `archive_55.000_-3.200_2022.parquet` was added to the shared rain cache on
  1 November, after production was fitted, and `train.load_rain_archive` reads every year it finds, so that cell's
  first days of 2023 gained antecedent rain. The scratch link to that file was removed (the shared file was not
  touched) and the run was repeated from the same commit. Before the stop, only the face-check figures had been
  printed.
- **Shared inputs unchanged.** The fingerprint of the shared event files, model files and the three cache listings
  was `bab324bd…` before the first run and after the addendum. The script's own listings of the files it read
  (rain links, radar files) and the four event and poll files also match before and after.

### The answer

**The candidates fail at United Utilities for one reason with two faces, and a third reason that is an artefact
of the comparison.**

1. **The base model.** The nine-company pooled layer forecasts United Utilities too high, and the per-overflow
   offsets remove only about half of that. Production's pooled layer, fitted on United Utilities alone, does not
   have the excess. This is nearly all of v2's loss, and it is the same deficit that the live-status candidate
   carries in its base (D2).
2. **The status input.** At United Utilities it helps only on rows where the overflow is already spilling at the
   issue time. On the other 99% of rows nothing is shown at any lead. United Utilities' spills are the least
   persistent of the nine companies.
3. **The lead-4 loss on forecast rain is the lead map.** Production is compared after a map fitted on United
   Utilities. The candidates have no map. Against production without the map the loss is not shown.

Labels, rain resolution, the offsets' recipe and the stale-feed fallback are each ruled out as the main cause.

### The ranking

G1, v2 arm (b) minus production on these rows: **+0.00132 [+0.00011, +0.00257]**, 3.5% of production's Brier.

| Rank | Explanation | Part of the gap, with interval | Label by the stated rule |
|---|---|---|---|
| 1 | H1: the pooled layer. Layer swap with the same refitted offsets | +0.00121 [−0.000003, +0.00245], 92% of G1. Pooled layers alone: +0.00236 [+0.00083, +0.00397] | **Not shown, by a hair**: 92% of G1, but the lower end is −0.000003. G1's own lower end is only +0.00011, so no part of it could clear zero by much. The largest part by far |
| 2 | H4: a level effect. One constant fitted in hindsight | Leaves +0.00038 [−0.00042, +0.00134]: 71% of G1 closes. A constant per month leaves +0.00004 [−0.00058, +0.00065] | **Level, yes; one year, no.** The excess is in v2's own training years too (C4). 2026 widened it. No interval was computed for the closed part itself |
| 3 | H2: production's offsets | +0.00010 [+0.00003, +0.00019], 8% of G1 | **Contributes; ruled out as the main cause** (upper end under a quarter of G1) |
| 4 | H9: a few overflows | The 5% where v2 loses most carry 97% of G1; without them +0.00005 [−0.00098, +0.00103] | **Met by the letter, not supported.** The rule trimmed one tail. The 5% where v2 gains most give back 56% of G1, and the middle 90% carry 60% (A3) |
| 5 | H5: rain resolution | Radar in place of ERA5-Land moves G1 by +0.00044 [−0.00030, +0.00133], the wrong way. Thirds of cells by disagreement: +0.00101, +0.00151, +0.00148 | **Ruled out as the main cause.** The gap does sit in the wettest cells (below), which is H1's shape, not a rain error |
| 6 | H3: labels | Label source: +0.00001 [−0.00001, +0.00003]. Without short-only spill-days G1 grows to +0.00187 [+0.00064, +0.00319] | **Ruled out** |

G2, the status gap:

| Explanation | Evidence | Label |
|---|---|---|
| H6: the lead map (forecast rain, lead 4) | Live status minus mapped production +0.00806 [+0.00134, +0.01521]; minus raw production +0.00149 [−0.00340, +0.00648]; passed through the map, −0.00007 [−0.00412, +0.00353] | **Main cause of the lead-4 forecast-rain loss**: 82% of it goes against raw production |
| The base (ERA5-Land, leads 1 to 4) | At lead 1: D2 minus production +0.00402, candidate minus D2 −0.00309, so candidate minus production +0.00093 [−0.00080, +0.00326] | Arithmetic on reproduced figures: the status gain does not cover D2's base deficit |
| H8(b): less persistence | Persistence skill over the flat rate: 0.05 at lead 0 and −0.02 at lead 1, lowest of nine; AUC 0.72 and 0.66 | **Supported** |
| H8(c): where the uplift lands | Lead 0: −0.435 on the 4,171 rows spilling at issue; −0.00094 [−0.00217, +0.00022] on the rest | **The lead-0 gain is all on rows whose label is settled** |
| H8(a): level stand-in | Uplift against 2026 level error: rho 0.64 [0.61, 0.67] for D2, 0.49 [0.45, 0.52] for production | **Not supported as stated**: it tracks production's error too. The check was weak (below) |
| H7: the fallback | 0 United Utilities rows took it at any lead | **No part** in the recorded failures |

### Check by check

**C1, the layer swap** (Brier; mean forecast in brackets; observed rate 0.0543):

| Layer 1 | No offsets | Stored offsets | Offsets refitted on EA 2024-25 |
|---|---|---|---|
| Production's (United Utilities 2023-25) | 0.03901 (0.058) | **0.03793** (0.058) | 0.03803 (0.058) |
| Hold-out's (United Utilities 2023-24) | 0.03978 (0.062) | 0.03914 (0.062) | 0.03842 (0.060) |
| v2's (nine companies 2024-25) | 0.04137 (0.077) | 0.03925 (0.070) | 0.03925 (0.070) |

- With the same refitted offsets, v2's layer is +0.00121 worse than production's and +0.00083 [−0.00048, +0.00218]
  worse than the hold-out's.
- v2's pooled layer alone forecasts 0.077 against an observed 0.054. Its offsets bring that to 0.070. Production's
  pooled layer alone forecasts 0.058.
- What 2025 adds to a United Utilities pooled layer is small: hold-out's layer with the same offsets is +0.00038
  [−0.00009, +0.00086] behind production's. The hold-out's stored deficit (+0.00120 [+0.00056, +0.00187]) was
  mostly its offsets, which had not seen 2025.
- The refit rows: 1,630,829 site-days at 2,270 overflows. EA and Stream labels there: 137,494 spill-days shared,
  1,319 only in the EA file, 839 only in Stream.
- H2's ladder on production's layer: label source +0.00001 [−0.00001, +0.00003]; a third year and production's own
  rows −0.00004 [−0.00022, +0.00015]; recency 0.25 against 1, +0.00014 [−0.00006, +0.00032].
- 2,218 of the 2,219 test overflows have an offset in both production and v2.

**C2, hindsight recalibration on the 2026 rows.** The constant that would have centred each model: −0.09 log-odds
for production, −0.40 for v2. Slopes 0.98 and 0.95. G1 after one constant +0.00038, after a constant and a slope
+0.00033 [−0.00043, +0.00125], after a constant per month +0.00004. These intervals take the fitted constants as
given. **So with the best level correction hindsight can give, month by month, v2 only ties production at United
Utilities.**

**C4, is the excess only 2026?** Mean forecast against the observed rate, at United Utilities' overflows. 2024 and
2025 are years both models' offsets were fitted on, so this is shape, not skill.

| Period | Observed | Production | v2 arm (b) | v2 pooled layer alone |
|---|---|---|---|---|
| 2024, whole year | 0.0959 | 0.0950 (−1%) | 0.1057 (+10%) | 0.1200 (+25%) |
| 2025, whole year | 0.0746 | 0.0772 (+3%) | 0.0832 (+12%) | 0.0923 (+24%) |
| 2024, January to February | 0.1506 | 0.1451 (−4%) | 0.1732 (+15%) | 0.1942 (+29%) |
| 2025, January to February | 0.0794 | 0.0804 (+1%) | 0.1009 (+27%) | 0.1100 (+39%) |
| 2026, January to February | 0.0731 | 0.0878 (+20%) | 0.1170 (+60%) | 0.1275 (+74%) |
| 2024, January to August | 0.0959 | 0.0952 (−1%) | 0.1074 (+12%) | 0.1220 (+27%) |
| 2025, January to August | 0.0446 | 0.0476 (+7%) | 0.0539 (+21%) | 0.0600 (+34%) |
| 2026, January to August | 0.0543 | 0.0578 (+6%) | 0.0703 (+29%) | 0.0774 (+43%) |
| 2024, September to December | 0.0959 | 0.0945 (−1%) | 0.1022 (+7%) | 0.1160 (+21%) |
| 2025, September to December | 0.1343 | 0.1361 (+1%) | 0.1416 (+5%) | 0.1565 (+17%) |

v2 runs high at United Utilities in every period, in its own training years, most from January to April and
least in summer. In January and February 2026 production was 20% too high as well, so that year did widen the
gap. By C4's stated rule the cause is structural, with 2026 on top.

**C4b, which overflows.** By thirds of the long-term spill count: +0.00001, +0.00110, +0.00285 [+0.00030, +0.00545].
The gap is at frequent spillers. Grouped on the outcome: the third of overflows whose spill-day rate fell most
(0.121 in January to August 2024-25, 0.062 in 2026) carry +0.00471 [+0.00200, +0.00756]; the third that rose,
−0.00118 [−0.00288, +0.00041]. Overflows grouped by how far they fell will show regression to the mean, so this
says where the loss is, not why.

**C5, rain.** The radar covers 472,647 rows (88%) for the day and the 30-day window the features read. ERA5-Land
over radar, total rain per cell: median 1.03, middle half 0.93 to 1.17; daily correlation 0.78; the hourly stamps
line up best with no shift. G1 on those rows is +0.00149 with ERA5-Land and +0.00193 with radar. By thirds of cells
on mean rain, though: driest −0.00010 [−0.00128, +0.00096], middle +0.00107 [−0.00018, +0.00250], wettest
**+0.00602 [+0.00214, +0.01029]**. The wettest 63 cells hold 15% of the rows and 69% of G1.

**C3, labels.** 5,295 of the 29,282 spill-days come only from events under 15 minutes. Counting them as dry makes
G1 larger. Their monthly share is seasonal in every year (10% in winter, 20% to 30% in spring and summer;
`-short-events.csv`).

**C6, forecast rain** (12,773 rows at each lead, 53 overflows in 16 cells; observed rate 0.0805). Lead 4:

| Predictor | Mean forecast | Brier |
|---|---|---|
| Production, raw | 0.110 | 0.0699 |
| Production, mapped (what the site shows) | 0.097 | 0.0633 |
| Live status (#639's candidate, no map) | 0.119 | 0.0713 |
| Live status through production's map (diagnostic) | 0.104 | 0.0632 |
| combined-v1 (base is raw production) | 0.097 | 0.0690 |
| combined-v1 with the base mapped (diagnostic) | 0.084 | 0.0645 |

combined-v1 minus mapped production is +0.00571 [+0.00109, +0.01114], as #666 found. Minus raw production it is
−0.00086 [−0.00482, +0.00274]. With its base mapped it is +0.00118 [−0.00173, +0.00439] against mapped production.
At lead 0 the candidates beat production with or without the map (−0.009 to −0.012, intervals below zero).

**C7, the fallback.** No United Utilities row took the fallback at any lead. On the polls of 5 to 17 October
(counts only, the coverage file's own rule for stale): United Utilities 1.3% unknown and 0% stale. Southern is
10% stale, Northumbrian 4%. Nothing in the inputs suggests the fallback fires more at United Utilities. The live
answer is the shadow's, on or after 23 November.

**C8, the status.** A United Utilities overflow that spilled yesterday spills today 37% of the time, against 3.7%
after a dry day. Persistence still has the lowest skill of the nine there, because the rule's chances are fitted
on all nine together and because the ranking is weak (AUC 0.72 at lead 0 against 0.80 to 0.93 at seven others;
Northumbrian is 0.71). Part (a)'s check was weak: the uplift is built from recent spills and the level error from
the same season's spills, so the two are tied for any model. The only informative part is that it tracks D2's
error more than production's.

**Addendum (A1 to A3), chosen after the main run was read.**

| Lead | combined-v1 minus production, rows spilling at issue | The narrow rule minus production, all rows |
|---|---|---|
| 1 | −0.0364 [−0.0816, −0.0029], 4,133 rows | −0.00028 [−0.00060, −0.00002] |
| 2 | −0.0231 [−0.0561, +0.0021], 4,094 rows | −0.00018 [−0.00042, +0.00001] |
| 3 | −0.0132 [−0.0402, +0.0089], 4,097 rows | −0.00010 [−0.00031, +0.00006] |
| 4 | −0.0295 [−0.0644, −0.0024], 4,050 rows | −0.00022 [−0.00051, −0.00002] |

On rows spilling at issue, production forecasts 0.30 for the next day against an observed 0.46 (lead 1). The
uplift moves that to 0.50. The rule as a whole is worth 0.3% to 0.7% of production's Brier. On forecast rain
(about 208 spilling rows a lead) nothing is shown at any lead. A3 is in the ranking table.

### What is established, what is inferred, what was not verified

**Established** (measured here, on seen rows):
- The loss at United Utilities is almost entirely in the pooled layer, and almost entirely a level: v2's pooled
  layer forecasts the company about a quarter too high over a whole training year, and its offsets leave about a
  tenth.
- Labels, the offsets' data and recipe, and ERA5-Land's rain errors each account for under a tenth of the gap or
  none.
- No correction of v2's level or season, even fitted on the test rows, beats production there.
- The live-status and combined candidates' lead-4 loss on forecast rain disappears against production without its
  lead map.
- The status uplift at United Utilities is confined to rows spilling at the issue time.

**Inferred, not tested:**
- *Why the pooled layer runs high.* The other eight companies' overflows spill more for the same rain, season and
  annual-return covariates, most in late winter and spring and in wet cells. No other company's rows were rebuilt
  here, so this rests on #357's company table and on the shape above.
- *Why offsets leave half the excess.* The offset is shrunk toward no change by 15 pseudo spill-days, and it is a
  ratio of counts applied to odds, which under-corrects on wet days. Neither part was measured.
- *Why production is 20% high in early 2026.* Fewer overflows spilled per storm (#357's data check). Cause unknown.

**Not verified:**
- The status here is the EA's complete record. Polled status, with its missed short events, is the shadow's to
  test.
- The forecast-rain results rest on 53 overflows in 16 cells.
- The run used pandas 3.1.0 where #357 used 3.0.5. The face checks reproduce the committed figures exactly.

### Where the run differs from the statement

- The first attempt stopped at face check 3 (above). No code changed between the attempts.
- C5's "day and the 30 days before" was coded as the 30 days ending on the day, which is what the rain features
  read. A cell needed 120 radar days for its disagreement measure; all 188 had them.
- C6 also reports combined-v1, which the statement named under G2 but not under C6.
- H9's and H8(a)'s rules were poor tests, for the reasons given beside them. Their literal results are reported.
- The addendum (A1 to A3) was added after the main run, and pushed before it ran.

### The ending

**Production stays at United Utilities.** regional-v1's fallback is right, and the evidence now says why: the
nine-company pooled layer does not hold United Utilities' level, and no level or seasonal correction of it does
better than tie. Nothing live changes, no frozen file changes, and #357's, #639's and #666's verdicts stand.

By the stated rule there is one finding that names a candidate, and it is narrow:

**`uu-spilling-v1`: at United Utilities, production's chance, with combined-v1's status uplift added only where the
overflow is spilling at the issue time, at leads 1 to 4.** Nothing is fitted; every file it uses is already
frozen. Lead 0 is left out: there the label is all but settled and the page's "right now" level already speaks.
- *Development evidence, on seen rows and chosen after C8(c) was read:* 0.3% to 0.7% of production's Brier, with
  intervals below zero at leads 1 and 4 only.
- *The test it would face:* the addendum script, unchanged, on the EA's September to December 2026 records when
  they are published, under its own statement pushed before that file is imported. Proposed bar, to be fixed
  there: the rule minus production on all United Utilities rows, leads 1 to 4 pooled, with the two-way interval
  wholly below zero; and on the spilling rows a mean forecast no further from the observed rate than production's.
- *What it is not:* a reason to build anything now. The combined-v1 shadow log can describe these rows sooner, but
  28 days will hold too few: eight months here held about 4,100 a lead and cleared zero at two leads of four.
- *Owner and milestone:* the REGIONAL row's owner; the read waits on the EA's file (date not known). If that file
  shows no gain, the candidate is archived.

**What would reopen the base-model question at United Utilities:** a pooled layer that can hold a company's own
level (a company input, or a company-level calibration fitted on the training years), scored on rows nobody has
seen; or evidence that United Utilities' spilling has drifted from production's 2023-25 fit, which the 2027
primary evaluation will show.

### Follow-ups, not done here

1. **For the 23 November switch decision and the combined-v1 shadow.** On forecast rain, a candidate without a
   lead map is compared with production after its map. At United Utilities that alone made lead 4 look "clearly
   worse". The shadow's bar should compare like with like, or say that it does not.
2. **`scripts/check_model_provenance.py` no longer passes against the shared cache**: 2,269 of 2,271, because of
   the 2022 file added on 1 November. `train.load_rain_archive` should read only the years it trains on, or the
   check should. A small fix with its own test.
3. **The combined-v1 logger** should keep the spilling-at-issue flag on each row, so `uu-spilling-v1` can be
   described from its log without a new logger.
