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

Not yet run.
