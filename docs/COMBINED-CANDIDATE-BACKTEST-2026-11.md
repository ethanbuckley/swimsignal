# One combined spill-forecast candidate on January to August 2026: protocol, stated before any score

Written 10 November 2026, before any forecast from this candidate was computed or any 2026 label was read for it.
Committed and pushed before the run. Results go below the line at the end. Nothing above that line changes after a
result is seen, except a plain bug fix, listed under "Changes after this statement" with what it changed.

The rule this follows is "Backtest instead of waiting" in `docs/RESEARCH-WORKFLOW.md` (Ethan, 6 Nov 2026). Because
parts of this candidate were chosen after 2026 was seen (below), **the result is development evidence, not
confirmation**, whatever it shows.

## Why

On the live record (early November 2026) the spill forecast warns of about 35% of spills, and about half its
warnings come true. No water company passes the promise rule, and same-day persistence beats it. Ethan wants a
forecast good enough to sell to organisations. That needs one candidate that clears a bar stated in advance,
company by company.

Two changes have each been measured on their own on January to August 2026:
- **Live status** (#254, #639): each overflow's own recent spill status as an input. Against production it passed
  all five of #254's conditions at every lead (lead 1 Brier 0.0316 against 0.0419). At United Utilities it was not
  better beyond lead 0.
- **Regional routing** (#357, #490): the nine-company v2 model at eight companies, production at United Utilities.
  v2 was 11-23% better than production at those eight and 3.4% worse at United Utilities.

Neither has been scored together with the other. This test does that, once.

## The candidate: combined-v1

For overflow *i*, target day *d* and lead *k* (issue at 00:00 UTC of day *d*−*k*):

1. **Base** (regional-v1, `scripts/regional_routing.py`, unchanged): v2 arm (b)'s chance at Anglian, Northumbrian,
   Severn Trent, South West, Southern, Thames, Wessex and Yorkshire; production's chance at United Utilities. Raw
   chances, no lead map, as the regional shadow logs them.
2. **Status uplift**: where every status input is known, the base's log-odds plus
   logit(candidate *k*) − logit(D2). Candidate *k* is #254's lead-*k* live-status model; D2 is the same model fitted
   on the same 2024 rows without the status inputs. Their log-odds difference on the same row is what the status
   adds, holding rain, season and site fixed. It is added to the routed base at all nine companies, United
   Utilities included.
3. **Fallback**: where any status input is missing, the base alone.

Probabilities are clipped to [10⁻⁶, 1 − 10⁻⁶] before a logit. **Nothing is fitted.** There is no free parameter.

Why this form. The two pieces cannot both be "used" by swapping models: the live-status candidates replace the
whole model, so the drafted switch (`DIPCAST_LIVE_STATUS`) would leave v2 unused wherever the status is known. The
log-odds uplift keeps each piece doing what it was tested for: v2 or production sets the level from rain and site;
the status moves it. A refit of v2 with the status inputs would be a new model with new choices; it is not tried
here.

### Frozen files

| What | File | SHA-256 |
|---|---|---|
| v2 arm (b), the base at eight companies | `data/processed/regional/spill_model_v2_offsets.pkl` | `9e0fc54a9356e4cea528606422dc569691453fc3ab98ea31986f19437ba501f2` |
| Production, the base at United Utilities | `data/processed/spill_model.pkl` | `faa7917e2be725a9441b277fc111091c5bdffe45c80ab4fd042682aa9de4210e` |
| Live-status candidate, lead 0 | `data/processed/live_status/candidate_lead0.pkl` | `deb5e1e5ee64df0e48e789b9b8eba9bb0be76fba4a23e6745f6a259cec436d00` |
| lead 1 | `candidate_lead1.pkl` | `e0756b1e97485d458bafb868480d73b8c95c502f4136aa05937cb166d3909c3e` |
| lead 2 | `candidate_lead2.pkl` | `ed5bb2b9a39ee222303e3c923b824deffde00e1c63eca89371a3800e51c894da` |
| lead 3 | `candidate_lead3.pkl` | `5180de7086c682fcfebcc9b02e12e197bbd7fb09d5aeb7dfeb940350d8a1360f` |
| lead 4 | `candidate_lead4.pkl` | `ecc835c96d707534d88dbecf6f286c59adb90839f31985926110b85ec4824066` |
| D2, the uplift's reference | `swimsignal-private/baselines/spill_model_nine_2024.pkl` | `1603678923ccdd1553830fa67c2069714c0a836c9df7e8c52578aabd729b5bcc` |
| Production's lead map (comparator only) | `data/processed/lead_calibration.json` | `734202bc7f22af38fd72d65c4038bb51828b11f5436ed1de40ffa0f381ad0f09` |
| The rule and the combination | `scripts/regional_routing.py`; `combine` in `scripts/combined_candidate_backtest_2026.py` | this commit |

All nine hashes were checked on 10 November against the files on disk and against #639's and #490's records. The
harness stops if any differs.

### No A8 arm

The A8 company offsets (#333, read on 25 Nov) correct **production** at the eight companies other than United
Utilities. combined-v1 uses production only at United Utilities, where A8 fits no offset. So there is no coherent
"combined-v1 plus A8" to state. A8 stays out, and its window is not touched.

## Which choices were made on which data

| Choice | Made | On what |
|---|---|---|
| Production model and its lead map | 13 and 15 Sep 2026 | United Utilities 2023-25; before any 2026 EA file was imported |
| D2 and the five live-status candidates | 18 Oct 2026 | EA 2024 rows; settings from 2025 as hold-out (#254) |
| v2 arm (b) | stated before #357's run, fitted on EA 2024-25 | its January to August 2026 score was then read in #357 (25 Oct) |
| regional-v1: United Utilities on production | 30 Oct 2026 (#490) | **after** seeing #357's 2026 scores per company |
| The combination (uplift form, applied at all nine, base without the lead map, fallback to the base) | 10 Nov 2026, here | **after** reading #639's 2026 results, including United Utilities, and #357's |
| P and R, the 10 mm threshold, the 28-day trailing fit | 10 Nov 2026 (#662) | the live poll record, 29 Sep to 23 Oct; no 2026 EA label |
| The pass bar below | 10 Nov 2026, here | knowing #639's and #357's per-company differences against production; nothing against P or R on these rows |

**Already seen of January to August 2026, before this was written:** #357's scores of v2 and production per
company (UK local days); #639's scores of the live-status candidates, D2 and production per company and lead, with
intervals; #490's arithmetic on #357's scores. This session's `count` stage (rows per company and lead, and how many
rows each rule can be applied to); it read no label and computed no forecast.

**Not seen:** any forecast of combined-v1; any score of P or R on these rows.

So the test years were used to choose part of this candidate (the routing rule, and the combination with that
knowledge in hand). By the workflow, the result is **development** (held-out from every model's fit, but seen when
choosing the candidate). It can rank the candidate against the references, size the gain with an interval and check
calibration. It cannot be the confirmation that a limited or main forecast needs. "What follows" names where that
confirmation comes from.

The labels are the EA's 2026 start/stop file, as in #639, not SwimSignal's live polls.

## The rows

Exactly #639's (`docs/LIVE-STATUS-BACKTEST-2026-11.md`, "The period and the rows"), built by its harness imported
unchanged:
- UTC days 1 January to 31 August 2026; window E's 13,426 overflows at the nine English companies;
- ERA5-Land rain: 3,262,518 rows; archived forecast rain: 350,173 rows at each lead, in 206 cells (no Northumbrian
  or Southern rows; South West 482);
- label: an EA event touches the UTC day;
- status rebuilt from the EA events by #254's `Status`, with #639's rule for when it is known.

One input differs from #639: the poll-coverage file for the dead-monitor check. #639's copy (`67731cce…`, state
release of 6 Nov) is no longer on disk. This run uses the state release of 9 Nov (`a5bbf950…`), which holds the same
reference period, 5 Oct to 1 Nov. The `count` stage on 10 Nov gave exactly #639's overflows and rows per company
(13,426; 3,262,518; 350,173 per lead), so window E is the same set by count. The run stops if any count differs.

Other inputs, all checked on 10 Nov: the 2026 zip, downloaded again through `scripts/import_ea_events.py --years 2026`
into a scratch root, is byte-identical to #639's (`d0dbf32f…`, 29,672,650 bytes; 983,409 events); the 2024-25 event
files, annual returns and the ERA5-Land and forecast-rain file listings have #639's hashes.

## The predictors

| Name | ERA5-Land rows | Forecast-rain rows |
|---|---|---|
| **combined-v1** | as above, raw | as above, raw |
| Production | raw (as #357 and #639 scored it) | after the lead-*k* map: what the site shows |
| Live status alone | #639's Q2 predictor: candidate *k*, production raw where the status is unknown | candidate *k*, production mapped where unknown |
| Routing alone | regional-v1, raw | regional-v1, raw |
| P, persistence | trailing-fit chance (below) | the same, fitted on forecast-rain rows |
| R, rain rule | trailing-fit chance (below) | the same, fitted on forecast-rain rows |

## The two simple rules

The accuracy-baselines session published its definitions on 10 November (#662,
`docs/SIMPLE-REFERENCES-LIVE-2026-11.md`). They are used here, moved from polls to the EA's complete record:

- **P, same-day persistence.** Active if an EA event runs at the issue time (00:00 UTC of day *d*−*k*), or a
  spill-day (an event touches the UTC day) falls on day *d*−*k*−1 or *d*−*k*−2: the 48 hours before the issue.
  Known where #254's rule makes all three days known. #662's 8-hour staleness rule is about polls and has no
  counterpart in a complete record.
- **R, the rain rule.** Wet if rain on the target day plus the day before is **over 10 mm** (strictly). On ERA5-Land
  rows that is `rain_d + rain_d1` from ERA5-Land; on forecast-rain rows, #254's lead-*k* `rain_d` and `rain_d1`,
  the same rain every model reads.
- **Each side's chance** (#662's rule): (spills + 0.5) ÷ (rows + 1) over the rows of the same lead, the same side of
  the same rule, all companies pooled, with target day from *I*−28 to *I*−1, where *I* = *d*−*k* is the issue day.
  A side with fewer than 100 such rows gives no chance. Fitted separately on the ERA5-Land and forecast-rain rows.
  No 2025 rows are added, so the first days of January (about *k*+1 target days) have no chance.
- **Common rows**: rows where both P and R have a chance. Every comparison with P or R uses only these.

## The metric

- **Brier score**, by lead 0 to 4, per company and all nine. AUC, log loss, ECE (`training.ece`) and mean forecast
  reported.
- **Warnings, as the Accuracy page counts them** (the counts of `forecast_log.warning_counts`, recomputed in the
  harness): a forecast of 0.40 or more
  (`SPILL_WARN_AT`) is a warning. Reported: warnings, hits, misses, false alarms, **hit rate** (share of spill-days
  warned of) and **false-alarm share** (share of warnings with no spill; 1 − the page's "warnings that came true").
  P and R are also counted as yes/no warnings (active; wet). Reported, not deciding.

## Intervals

#639's `TwoWay`, imported unchanged: a two-way cluster bootstrap by overflow and by ISO week of the target day,
2,000 draws from `numpy.random.default_rng(20261106)`, overflows first then weeks, one set of draws for every
comparison. 95% interval: 2.5th and 97.5th percentiles. Same rows and same seed as #639, so the draws are #639's.
P's and R's fitted chances are held fixed within a draw. The week-only interval is reported beside it.

## The pass bar

On the **ERA5-Land rows**, for a company (and for all nine together), combined-v1 **passes** if at **lead 1 and at
lead 2**, against each of **production, P and R**, its Brier score is lower and the 95% two-way interval of the
difference (combined-v1 minus the reference) lies wholly below zero. Six cells; all six must hold.

- Every company's six cells are reported, pass or not. A company result is about that company only. The pooled
  result is reported with its own line.
- **Why ERA5-Land decides.** It is the only rain source with rows at all nine companies. Forecast rain has none at
  Northumbrian or Southern and 482 rows at South West. On ERA5-Land rows the rain is known exactly at every lead;
  only the status ages. So this tests the status and the base with perfect rain, for every predictor alike.
- **Reported, not deciding:** the same six cells on the forecast-rain rows; leads 0, 3 and 4; combined-v1 against
  live status alone and against routing alone; all metrics and warnings.

## Checks that stop the run

- Any frozen file or the zip differs from the stated hash.
- Rows differ from the count stage per company.
- Any predictor gives a non-finite forecast.
- Routing: a row other than United Utilities goes to production, or a United Utilities row to v2.
- **#639 is reproduced.** "Live status alone vs production", all nine, ERA5-Land, must give #639's Q2 differences to
  four decimals at every lead (−0.0151, −0.0104, −0.0094, −0.0086, −0.0084) with the same intervals. Same rows,
  models and draws, so any gap is a harness fault.

## Expected, stated now (inferred, not conditions)

- Against production: a pass at most of the eight v2 companies at leads 1 and 2. Both pieces were better there on
  their own (#639: −0.0065 to −0.0275 at leads 1-2; #357: 11-23%).
- United Utilities: open. Its base is production, so the uplift alone must carry it. #639's candidate beat D2 there
  at every lead, but its whole model did not beat production.
- Against P: likely at most companies, since P has no rain. Against R with ERA5-Land rain: unknown; R gets the true
  rain, so it is the harder reference.
- combined-v1 against live status alone: lower at the eight v2 companies if v2's base gain survives the uplift.

## What follows, by outcome

Nothing here changes a live switch, threshold, issued forecast or frozen window. The live-status decision stays with
Ethan after the shadow read on or after 23 Nov; this result informs it.

- **A company passes.** Development evidence that combined-v1 beats production and both simple rules at that
  company, at leads 1 and 2, with perfect rain. It is not confirmation. The next deliverable is a **fresh test that
  nothing in this candidate has seen**: combined-v1 is frozen by this commit, so the EA's start/stop records for
  September to December 2026 (the next annual file) are unseen for it, and so are SwimSignal's own poll labels
  after the frozen shadow windows are read. The record names which is first and its date, and what would be needed
  to log combined-v1 in shadow (D2 is not in the repository).
- **A company fails.** Production stays there. The next deliverable is a diagnosis: which reference it loses to,
  whether the base or the uplift drives it (routing alone and live status alone are scored on the same rows), and
  whether it is level or ranking (ECE, AUC).
- **No company passes.** As for a fail, for every company, and the record says whether any variant is worth stating
  (for example, the uplift only at the eight companies) as a new development candidate with its own protocol. It is
  not rerun here with changed settings.

## Network, resources and isolation

- **Open-Meteo: 0 calls.** All rain is cached. The ensemble-rain test D4 (to 21 Nov) is not touched.
- **EA: one zip** (4 HTTPS requests), downloaded on 10 Nov into the scratch root before this was written.
- **No shadow log is read.** Not the live-status shadow (#262, read on or after 23 Nov), not the regional shadow
  (read 28 Nov), not A8 (25 Nov). The 2027 evaluation is untouched.
- **Isolation.** Scratch `DIPCAST_ROOT` and `DIPCAST_STATE`. `DIPCAST_CACHE` points at the main checkout's rain
  cache, read-only. The 2024-25 event files, models, annual returns and rain-cache listings are fingerprinted before
  and after the run (`6cbda499…` before and after the count stage).
- #639's run took 131 s and 4.1 GB. This one adds three model passes per lead and more AUCs; expected under
  15 minutes and about 5 GB.

## Order of work

1. Commit and push this statement and the harness. Open a draft PR against `main`.
2. Check no other heavy run is going (`pgrep -fl`, never `pkill`).
3. `scripts/combined_candidate_backtest_2026.py run`, once, from a `git archive` of the statement's commit.
4. Write the results below the line. Commit the tables beside this file.
5. Update the register row and the catalogue entry.

---

## Results

Not yet run.
