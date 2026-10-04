# Pre-registered evaluation: May to September 2027

This file fixes, before the season starts, how SwimSignal's forecasts for May to September 2027
will be scored. It follows the plan in `docs/EXPANSION-2026-10.md` ("Prospective May–September
2027 evaluation"). The registration is the merge of the pull request that adds this file: its merge
commit on main is the record, and the hashes in section 13 tie the analysis to it.

Changes before 1 May 2027 are allowed as dated amendments in section 17, with new hashes. Nothing
here changes after 1 May 2027. Where this file says how the code works, it was read from main at
`be1c85e` on 4 October 2026, with file and line. Where it infers, it says so.

## 1. What is tested

Two forecasts the site issues, each against an observation SwimSignal does not control.

| | Forecast | Observation | Unit scored |
|---|---|---|---|
| Spills | `forecast_calibrated`: one monitored overflow's chance of discharging on a target day, after the correction for each day ahead (`forecast.calibrate_by_lead`), as the map uses it | The water company's live feed, polled by the site's scheduled build (every 30 minutes asked; `site.yml` line 7) | One overflow, one target day, one lead |
| E. coli | `p_ecoli_gt900`: the chance an Environment Agency sample would show more than 900 E. coli per 100 ml | EA statutory samples at the inland designated bathing waters | One sample, one lead |

The season is target days 1 May to 30 September 2027, as Europe/London dates.

The E. coli unit is the EA's count per 100 ml from membrane filtration: determinand 2348,
"Escherichia coli : Confirmed : MF" (`ingest/wqa.py` line 24). Membrane filtration counts colonies,
so the unit is colony-forming units (cfu) per 100 ml, as the model's own target says:
"E. coli > 900 cfu/100 ml" (`data/processed/ecoli_model.json`, `meta.target`, line 31). A sample
scores 1 when its count is over 900 (`forecast_log.py` line 827). A count of exactly 900 scores 0.
A count published as "<10" or ">10000" is read as 10 or 10000 (`ingest/wqa._count`).

Not tested here: a spot's exposure index and its level (no observation of it exists; its die-off
and dilution steps are physical estimates), "right now", the action lines, coastal, Welsh and
Scottish waters, algae and access.

The spill warning line is applied to each overflow's chance, as the Accuracy page has done since
#96. 40% is the chance at which a spot right beside one overflow (reach 100%) reads High risk. A spot
further downstream reads High only at a higher chance, or from several overflows at once
(`forecast_log.py` lines 87–95).

## 2. The frozen model

The model is frozen by a git tag, `eval-2027-model`, on a commit of main that Ethan chooses and
pushes before 1 May 2027 (section 15). Everything in git at that commit is the frozen model. Two
inputs are outside git:

- the river network, `river_network.pkl`, which the build downloads from the release `data-v1`
  when it is not cached (`site.yml` line 79). Its SHA-256 is recorded at the tag;
- the rain forecast, Open-Meteo's, fetched live. It is part of the forecast, not of the model.

**The version stamp.** Every logged forecast carries a stamp (`forecast.model_version`, `forecast.py`
lines 117–138):

    spill=<8>;cal=<8>;ecoli=<8>;code=<version>+<commit>;rain=open-meteo-forecast

Each `<8>` is the first 8 hex digits of the MD5 of the spill model, the calibration map and the E.
coli model. On 4 October 2026 the live stamp was
`spill=808da63d;cal=9b3cc24c;ecoli=55b5d280;code=0.1.0+be1c85e;rain=open-meteo-forecast` (the
15:29 BST build's `spots.json`, `assumptions.version`). The three MD5 prefixes match the files on main.

The `code` part changes with every merge, including changes to pages only, so it is not compared as
text. A forecast counts as the frozen model's when both hold:

1. its stamp's `spill`, `cal` and `ecoli` parts equal those of the files at the tag, and its `rain`
   part is `open-meteo-forecast` (`evaluate_2027.frozen_hashes`); and
2. between the tag and its `code` commit, no file in `MODEL_PATHS` changed and none of the model's
   constants in `src/dipcast/config.py` changed (`evaluate_2027.code_changes`).

`MODEL_PATHS` (in `scripts/evaluate_2027.py`): the spill model, calibration map and E. coli model;
`annual_returns.parquet`, `id_lookup.parquet` and `lakes.parquet` in `data/processed/`;
`src/dipcast/model/` and `src/dipcast/network/`; `overflows.py`, `ids.py`; and in
`src/dipcast/ingest/`, `rainfall.py`, `flows.py`, `lakes.py` and `annual_returns.py`.

The model's constants in `config.py`: `SNAP_MAX_M`, `RIVER_VELOCITY_MS`, `LAKE_VELOCITY_MS`,
`T90_HOURS`, `RECENT_SPILL_HOURS`, `MAX_UPSTREAM_KM`, `RAIN_GRID_DEG`, `FORECAST_DAYS` and
`FORECAST_PAST_DAYS`. The rest of `config.py`, such as a feed's address, is not the model.

Watched files: a change after the tag to `forecast_log.py`, `ingest/live.py`, `ingest/wqa.py`,
`ingest/bwq.py`, `spill_day_ratio.json`, `bathing_waters_inland.json`, `spots.csv` or
`scripts/build_site.py` does not change a forecast but may change how it is scored or published.
Each is listed in the output with its commit. Its rows are kept.

## 3. Eligible sites: `data/eval2027/sites.csv`

`scripts/make_eval2027.py` made the list on 4 October 2026 from the 15:29 BST build's `spots.json`
and its 81 `data/upstream/<spot id>.json` files, and from `data/raw/bathing_waters_inland.json`. No
data API was called. The upstream files were downloaded once from the published site.

**Overflows (1,089).** Every overflow marked `has_live` in any listed spot's upstream file. Those
are the overflows whose water can reach one of the 105 listed spots within 60 km along the river
network (`transport.upstream_overflows`), at a company that publishes their status live.

| Company | Eligible | Scored at least once, 29 Sep to 3 Oct 2026 |
|---|---:|---:|
| Anglian Water | 139 | 123 |
| Northumbrian Water | 14 | 8 |
| Severn Trent Water | 103 | 101 |
| South West Water | 29 | 0 |
| Southern Water | 117 | 111 |
| Thames Water | 185 | 172 |
| United Utilities | 133 | 116 |
| Wessex Water | 248 | 245 |
| Yorkshire Water | 121 | 119 |
| **All** | **1,089** | **995** |

`water` says which kind of spot an overflow reaches: river only (1,071), lake only (17) or both (1).
South West Water's overflows are eligible but were never scored: its feed carries no record times,
so it never counts as current (`forecast_log.py` lines 24–33). If that changes, they score. The 65
upstream overflows with no live feed are left out: they are forecast but cannot be scored. 24 of
the 105 spots have no upstream file: nothing monitored within 60 km, or an isolated lake.

**Bathing waters (38).** The 38 inland designated bathing waters in
`data/raw/bathing_waters_inland.json` (20 river, 18 lake), the set the live E. coli scorer reads
(`forecast_log._bathing_sites`). Each is a listed spot, `bw-<EA id>`. `company` is the EA's named
sewerage undertaker. On 4 October 2026 every river one had overflows upstream and an E. coli
estimate; 16 lakes had an estimate; 2 isolated lakes (Cotswold Country Park and Beach, Henleaze
Lake) get none, because `forecast_point` returns before logging for an isolated lake. Their samples
count as not scored.

**The rule.** The list is fixed now. An overflow or bathing water not on it is not evaluated: a spot
added later, or an id a company renames. Its rows are counted and reported (`rows_outside_list`).
An eligible overflow that leaves its company's feed stays in the count as not scored.

## 4. The data the evaluation reads

Only published files, taken once: the copies at `https://swimsignal.co.uk/data/` from the first
successful build on or after **31 October 2027, 00:00 UK time**. Each is saved with its SHA-256
before the script runs. The wait lets late samples reach the EA's Water Quality Archive, whose
latest sample trailed the bathing-water service's by 3 to 7 days at 15 sites and 15 days at one in
September 2026 (`ingest/wqa.py`, module notes).

| File | State on 4 Oct 2026 | Columns the script needs |
|---|---|---|
| `verification_live.csv` | Published | `overflow_id, company, day, lead, issued_at, forecast_raw, forecast_calibrated, climatology, observed`; and `version` (A) |
| `verification_ecoli_live.csv` | **Not published** (B) | `bathing_water, sample_time, day, ecoli, lead, issued_at, forecast`; optional `kind, observed, version` |
| `verification_live_unscored.csv` | **Not published** (C, recommended) | `overflow_id, day, lead, reason` |
| `verification.json` | Published | None: the script does not read it. Its service record (runs, gaps, feeds down) is quoted beside the results |

Three changes to what the site publishes are needed before the tag. Each is a small pipeline change
in its own pull request; none is made here.

- **A. A `version` column in `verification_live.csv`**: the scored forecast's stamp. `verify_live`
  already carries it (`forecast_log.py` line 477) but `scored_rows` does not write it (lines
  609–632). Without it the script cannot tell the frozen model's rows from a candidate's. It runs,
  and says "frozen-model check: not made".
- **B. `verification_ecoli_live.csv`**: one row per EA sample at an eligible bathing water in the
  season, for each lead 0 to 4: `bathing_water` (EA id), `kind`, `sample_time` (ISO 8601 with
  offset), `day` (the sample's local date), `ecoli` (count per 100 ml), `observed` (1 if over 900),
  `lead`, `issued_at`, `forecast` (the estimate), `version`. Where no forecast at that lead was issued
  before the sample, `lead` is filled and `issued_at`, `forecast` and `version` are empty. A sample
  must have rows even when nothing forecast it. `verify_ecoli` makes these pairs today
  (`forecast_log.py` lines 789–858) but publishes only counts and the 30 latest. Without B, the E.
  coli half cannot be run from published files.
- **C. `verification_live_unscored.csv`** (recommended): one row per overflow-day forecast the live
  scorer did not score, with its reason: one of `UNCOVERED_REASONS` (line 319), `missed_deadline` or
  `no_rain_data`. Without C, the not-scored cells are counted but not explained.

**Size.** `verification_live.csv` held 23,395 rows in 1.94 MB for 5 target days on 4 October 2026.
At that rate it reaches about 140 MB by October 2027 (inferred: 367 days at 0.39 MB a day). If the
pipeline splits it, the evaluation joins the parts (one header, rows in day order) and records each
part's SHA-256.

## 5. Matching rules

As the live scorer applies them on 4 October 2026. `tests/test_evaluate_2027.py` checks the
constants, so a change to one fails the tests until this file is amended.

**Spill forecasts** (`forecast_log.py`):

- **Decision time.** For each overflow, issue day and target day, the forecast scored is the latest
  one issued by 08:00 Europe/London on the issue day (`DECISION_HOUR`, line 72;
  `select_decision_forecasts`, lines 208–229). Lead is the target day minus the issue day, 0 to 4.
- **Same day and in advance.** Lead 0, issued by 08:00 on the target day, is the same-day forecast.
  Leads 1 to 4 are in advance. Each lead is reported, and leads 1 to 4 pooled.
- **Exact site and date.** The forecast's overflow id equals the feed's, and its target day equals
  the observed local day.
- **Spill (1).** A poll saw an event touching that local day: from the latest event's start to its
  end, or to the poll time while it was still discharging; or a poll saw the overflow discharging
  with no event times, which counts on that poll's local day (`observed_spill_days`, lines 176–205).
- **No spill (0)**, only when the overflow was seen with a known status at least 6 times that day
  from a feed updated within 6 hours, with no unobserved stretch over 8 hours counting the day's
  edges, and seen again the next day (`MIN_KNOWN_POLLS` line 73, `MAX_GAP_H` line 81,
  `covered_site_days` lines 302–313). A feed with no record times is never current
  (`unstamped_feed_days`, line 322).
- **Not scored**: no forecast by 08:00 (line 411); a forecast made without rain data at the
  overflow's cell, or for an overflow with no live feed (line 221); or an observation that fails the
  rule above, under the first rule it breaks (`UNCOVERED_REASONS`, line 319).

**The E. coli estimate** (`forecast_log.py`):

- A logged spot forecast belongs to a bathing water when its coordinates round to the bathing
  water's at 4 decimal places, about 10 m (`match_points_to_sites`, lines 782–786).
- A pair is the same bathing water, the forecast's target day equal to the sample's local date, and
  the forecast issued strictly before the sample time (line 822). For each sample and lead, the
  latest such forecast (line 824).
- Samples from the Water Quality Archive are statutory monitoring only, sampling purpose MS
  (`ingest/wqa.py` line 34), the set the bathing-water service lists. Follow-ups after a failure are
  taken because a result was bad, so they are left out. A sample listed by both EA services is
  counted once (`refresh_ecoli_samples`).
- The warning table takes one row per sample: the latest forecast issued before it, whatever its
  lead (`ecoli_warning_table`, lines 551–565), on rivers only (line 557).

## 6. Bands and warning lines

| | Low | Moderate | High | Very high | Where in the code |
|---|---|---|---|---|---|
| Spill chance | under 0.15 | 0.15 to under 0.40 | 0.40 to under 0.70 | 0.70 or more | `site/levels.js` line 67 (`SPILL_CUTS`); `model/transport.py` line 511 (`LOW_CUT`) and lines 615–622 (`risk_label`) |
| E. coli estimate | under 0.10 | 0.10 to under 0.25 | 0.25 to under 0.50 | 0.50 or more | `site/levels.js` line 67 (`ECOLI_CUTS`), line 68 (`ECOLI_BANDS`), line 80 (the band is the first with p below its cut) |

A value on a cut belongs to the band above it, in both places. The E. coli cuts have no Python copy:
only `ECOLI_WARN_AT` (`forecast_log.py` line 98) and `compare_prf.WARN_AT` (line 57) repeat 0.25.

**Warning lines.** A forecast at or above the line is a warning (`warning_counts`,
`forecast_log.py` line 525).

- Spills: 0.40 (`SPILL_WARN_AT`, line 95).
- E. coli: 0.25, rivers only (`ECOLI_WARN_AT`, line 98). The site shows the estimate and lets it
  set a level only on rivers with overflows upstream, from May to September (`levels.js` lines 76–82).

Both are the site's High risk line. A saved spot that reaches High risk sends a push alert
(`push/src/shared.js` line 11, `HIGH = 2`).

## 7. What is reported

For each forecast and each stratum, by `scripts/evaluate_2027.py`:

- **Counts**: rows, sites, events, the observed rate and the mean forecast.
- **Brier score**: the mean of (forecast − outcome)², the outcome being 1 or 0. Lower is better.
- **Skill**: 1 − Brier ÷ the reference's Brier. 0 is no better than the reference, 1 is perfect,
  below 0 is worse.
- **References**, from data before 2027 only (`data/eval2027/climatology.json`):
  - Spills, **primary: the season/site climatology**, clip(c × f, 0.001, 0.95). c is the published
    `climatology` column: each overflow's long-run daily spill rate, its EA annual-return spill count
    × 1.004 ÷ 365, clipped to 0.001–0.95 (`forecast_log._site_climatology`, lines 875–886). f is the
    target day's month factor from United Utilities' event history 2023–2025, the spill model's
    training data: May 0.51, June 0.72, July 1.00, August 0.68, September 1.29. A factor is that
    month's share of spill-days over its share of calendar days.
  - Spills, secondary: c alone, as the Accuracy page uses it.
  - E. coli, **primary: each bathing water's share of samples over 900** in 2023–2026, all taken
    in May to September, as (over + 0.5) ÷ (samples + 1), so a site with none over still gets a
    chance above 0. 16 to 80 samples a site. A site without samples would take its type's rate.
  - E. coli, secondary: the rate by type, river 0.2161 and lake 0.025
    (`ecoli_model.json`, `meta.base_rate_by_type`), as the live scorer uses (line 833).
- **Reliability by band**: in each of the four bands, the number of forecasts, their mean and the
  share that happened, with an interval.
- **Discrimination (AUC)**, in plain words: given one forecast whose event happened and one whose
  event did not, how often the forecast gave the event the higher chance, a tie counting half. 0.5
  is chance and 1 is perfect. It is a ranking, not a share of forecasts right.
- **The warning table** at the line, on the same rows as the Brier score: hits, misses, false
  alarms and correct quiet ones; the share of events warned of; the share of warnings that came
  true; and the share right, beside the share that saying "no" every time gets right. For E. coli,
  one row per river sample, with the samples that had no forecast counted beside it, so the
  denominator is every river sample. Under 100 river samples with a forecast, or 10 of them over
  900, it is reported as too few to judge (`forecast_log.py` lines 101–102).
- **Coverage** (section 9), and for spills the Brier score before the lead correction.

**Strata.** Lead (each of 0 to 4, same day, in advance). Company: for spills the list's company; for
E. coli the undertaker, rivers only. Water: for spills, overflows reaching river spots only, lake
spots only, or both; for E. coli, river and lake. Coverage also by 7-day block. All strata are
descriptive.

## 8. Primary outcomes

Four, each the skill against the season/site climatology with its 95% interval:

1. Spill forecasts, same day.
2. Spill forecasts, in advance (leads 1 to 4 pooled).
3. The E. coli estimate on rivers, same day.
4. The E. coli estimate on rivers, in advance.

A primary outcome shows skill when the lower end of its interval is above 0. There is no adjustment
for having four. All four are reported together, whatever they show. Everything else is
descriptive. `docs/EXPANSION-2026-10.md` sets what the result is for: region and coastal releases
need positive held-out skill with uncertainty, and an external review.

**Expected sizes**, inferred from earlier seasons and not a promise:

- Spills: 1,089 overflows × 153 days × 5 leads = 833,085 cells. At the dry run's 85.9% scored,
  about 716,000 rows.
- E. coli: about 340 river samples. The rivers had 290 samples in 2024, 281 in 2025 and 336 in 2026
  to 7 September, with 102, 51 and 43 of them over 900. Its intervals will be wide.

## 9. Missing data, failed feeds and abstentions

Kept and reported. Never imputed, never dropped from a count.

- Every eligible overflow × season day × lead is a cell: 833,085 of them. A cell is scored or not.
  The share scored is reported overall, by lead, company, water and 7-day block.
- A cell with no row covers every reason a forecast was not scored, including days on which no
  forecast was made at all. The live scorer cannot count those: it only sees forecasts that exist.
- With file C, the not-scored cells are split by reason.
- For E. coli, every eligible sample × lead is a cell. Samples with no forecast, and pairs whose
  forecast was issued after the sample, are counted.
- Failed builds and feed outages: the service record in `verification.json` at the snapshot
  (runs against the 48 a day asked, the longest gap, feeds down by company), quoted beside the results.

The scores themselves are on scored cells only. If scoring fails more on wet days, the scores
describe drier ones. So each 7-day block also shows the observed rate and mean forecast on its
scored cells, where such a bias would show.

## 10. Uncertainty

A two-way bootstrap, fixed now:

- Each draw resamples the sites (overflows for spills, bathing waters for E. coli) with replacement
  and, independently, the 7-day blocks with replacement. A row counts (times its site was drawn) ×
  (times its block was drawn). All leads of a site and day share both draws.
- Blocks are 7 days from 1 May 2027: 1–7 May, 8–14 May and so on. The season has 22, the last
  (25–30 September) of 6 days.
- 2,000 draws, from numpy's `default_rng(20270501)`. The draws are made once for each forecast, in
  a fixed order (sites, then blocks), and every stratum uses the same draws.
- 95% intervals: the 2.5th and 97.5th percentiles, numpy's default interpolation.
- A draw with no event, or none of a stratum's rows, has no AUC or skill. It is left out of that
  interval and counted.

Why two ways: one storm raises many overflows and samples in the same days, which the blocks
capture; one overflow or bathing water resembles itself all season, which the sites capture.

## 11. No early stopping

The analysis runs once, on the snapshot of 31 October 2027, over the whole season. The Accuracy page
keeps updating during the season, as now; no decision about this evaluation is taken from it. If the
season is cut short, by a lost forecast log or a model change forced by a fault, the analysis runs
on what exists and says where and why it ends. The scores do not choose the cut.

## 12. Candidates

A change after the tag to `MODEL_PATHS` or a model constant makes a candidate. Its forecasts carry
their own stamp or commit. The script leaves them out of the frozen model's analysis and counts them
by label.

A candidate gets its own prospective evaluation: the same script, list and rules, from its first
forecast day (`--from`), reported separately and labelled as a candidate. It never replaces the
frozen model's result.

The pipeline logs one model at a time. There is no shadow run. So a candidate put live in the
season ends the frozen model's record on that day. The commitment: no change to the model paths or
constants between 1 May and 30 September 2027 unless a fault forces it, and any such change is
reported with its date and reason.

## 13. Frozen files and their hashes

| File | SHA-256 |
|---|---|
| `scripts/evaluate_2027.py` | `a92dca7a86377421354614d0aeeec1cf389840ede03aa9779fbcb57ef1ca4d6e` |
| `scripts/make_eval2027.py` | `9d123c6345aaf24c36d83aba0f04da60a432dc56489e65f8eec9e7958c7dfb3e` |
| `data/eval2027/sites.csv` | `1108747686e456e8e9abd4c7d1c319abae7a6c86da815ae177ad1d4a9ad10713` |
| `data/eval2027/climatology.json` | `e2212cf7d57a7c6df82c37f7ff6510ccc70d7cf1b62ab40035751fd9f26934e0` |

To check: `shasum -a 256 scripts/evaluate_2027.py scripts/make_eval2027.py data/eval2027/sites.csv
data/eval2027/climatology.json`. `uv run pytest tests/test_evaluate_2027.py` reads this table and
fails if a file differs. The script also compares itself, the list and the climatology with this
table when it runs, and labels its output "NOT the registered analysis" if any differs.

Inputs the list and climatology were made from (SHA-256):

- `spots.json`, generated 2026-10-04T15:29:52 BST: `df9dd7a40a50d4bc3f4f4bd2fbf1af3db3e876053b05e6d27be7a455cc7e0181`
- the 81 upstream files of the same build, combined as in `make_eval2027.dir_sha256`:
  `b3771e3576efa30a94c7e8cb08850341cdad01d06a92f0dd4f72fcd169a8c60a`
- `data/raw/bathing_waters_inland.json` (in git): `bbad4ae370fcb24b8664401c3bd57de0a97c20ecb68551816aaead5cb3472e64`
- United Utilities' events 2023–2025, `data/processed/edm_events.parquet` of a training checkout
  (not in git; made by the training pipeline from Stream's EDM layers):
  `4ef2c254706f06ce619371a8e8061c1da2a8b5c6f2a39e9b4f5c791c18f31983`
- EA samples 2023–2026, `data/processed/ecoli_validation_rows.parquet` of a training checkout (not in
  git; made by `scripts/validate_ecoli.py`): `ec8c60b39ca30c433d2ca64ceab33cee06c43e5429c05fdeeaf756091425db1a`
- `data/processed/ecoli_model.json` (in git): `4b457f7dd77ede8e6eb1d833a251ad91e04efe03308cd9da62569bc34e2bb38c`

The model files on main on 4 October 2026, for comparison with the tag (SHA-256):
`spill_model.pkl` `faa7917e2be725a9441b277fc111091c5bdffe45c80ab4fd042682aa9de4210e`,
`lead_calibration.json` `734202bc7f22af38fd72d65c4038bb51828b11f5436ed1de40ffa0f381ad0f09`,
`ecoli_model.json` as above.

## 14. Dry run on autumn 2026: not a result

The script was run on `verification_live.csv` as published at 15:30 BST on 4 October 2026
(SHA-256 `487a254c9e6dc5da20f769fdacc40862b40ee9cfb02691a4f7d1e9509a911ca6`), over target days 29
September to 3 October 2026, with the registered 2,000 draws and seed. It checks that the script
runs and reads the files right. It says nothing about 2027: five October days of a dry spell.

    uv run python scripts/evaluate_2027.py --spills verification_live.csv --from 2026-09-29 --to 2026-10-03

| | Same day | In advance |
|---|---:|---:|
| Overflow-day forecasts scored | 4,695 | 18,700 |
| Spills among them | 145 | 580 |
| Brier score | 0.0245 | 0.0278 |
| Skill, season/site climatology | 0.44 [0.37, 0.58] | 0.36 [0.29, 0.44] |
| Skill, site rate alone | 0.35 [0.28, 0.52] | 0.27 [0.21, 0.36] |
| AUC | 0.87 [0.81, 0.98] | 0.83 [0.79, 0.91] |
| Warnings at 40%: hits, misses, false alarms | 39, 106, 45 | 113, 467, 166 |

Cells scored: 23,395 of 27,225 (85.9%). South West Water 0%, Northumbrian Water 57%, Southern Water
56%, the rest 84% to 98%. The E. coli half was not run: file B does not exist.

What the dry run showed about the method:

- The script reproduces the live page's own figures from the same rows: same-day Brier 0.0245,
  in-advance AUC 0.829, all-leads skill against the site rate 0.28, and the same-day warning counts
  39, 106, 45 and 4,505.
- The five days fall in two blocks, so the intervals here carry almost no week-to-week spread. A
  full season has 22.
- In this dry spell the September and October month factors (1.29, 1.12) made the season/site
  reference worse than the site rate alone (Brier 0.0436 against 0.0379), so skill against it
  reads higher. In May, June and August the factors are below 1, which lowers the reference: in a
  dry spell that makes it harder to beat than the site rate. The primary
  reference was set by `docs/EXPANSION-2026-10.md` on 3 October, before this run; both are always
  reported.
- Without the `version` column the frozen-model check could not be made.
- A full season of 716,493 synthetic rows (these rows repeated over May to September) took 2 minutes.

## 15. Freeze steps

Dated, for Ethan. Also in the pull request.

1. **When this is merged** (October 2026): the merge commit registers the protocol.
2. **By 31 January 2027**: prerequisites A and B merged (C recommended), each with its tests, so
   the files are published for three months before the season. B can only be tried on real samples
   once the season's first samples arrive in May; until then its tests carry it.
3. **By mid-April 2027**: if the EA has published the 2026 annual returns (it published the 2024
   ones in March 2025: inferred from past years, not checked here), decide whether to refresh
   `annual_returns.parquet` before the tag. After the tag a refresh makes a candidate.
4. **By 30 April 2027**: choose the commit. Any model change before it is allowed. Then:
   - `git tag -a eval-2027-model <commit> -m "Frozen model for the 2027 evaluation"` and
     `git push origin eval-2027-model`;
   - record in section 17, in a pull request merged by 30 April: the commit, the date, the stamp
     the tagged build writes (`spots.json`, `assumptions.version`), the SHA-256 of the three model
     files at the tag, and the SHA-256 of `river_network.pkl` from release `data-v1`
     (`gh release download data-v1 -p river_network.pkl -D /tmp/net && shasum -a 256 /tmp/net/river_network.pkl`);
   - save a dated copy of the forecast log (`dipcast.duckdb` from the `state` release).
5. **1 May to 30 September 2027**: no change to the model paths or constants. Any change after the
   tag makes a separately labelled candidate (section 12).
6. **Early June 2027**: check that `verification_live.csv` has `version` and that
   `verification_ecoli_live.csv` has the first samples.
7. **31 October 2027**: save the published files and their SHA-256, run
   `uv run python scripts/evaluate_2027.py --spills verification_live.csv --ecoli verification_ecoli_live.csv --repo . --tag eval-2027-model --out results-2027.json`,
   check the `river_network.pkl` hash again, and publish the results in full.

## 16. Weaknesses known now

- The observations are the companies' own monitors. A gap is a missing day, not a dry one, but a
  monitor that is wrong is not caught.
- The spill reference's month factors come from one company over three years. Other companies'
  seasons may differ.
- The E. coli site rates rest on 16 to 80 samples a site.
- Issue times are recorded by the pipeline itself, and its log lives in a rolling release that a
  later run replaces (`site.yml` lines 101–141). Nothing outside it dates the forecasts. The dated
  copies in section 15 are the check.
- Scores are on scored cells only (section 9).
- About 340 river samples will give wide E. coli intervals.

## 17. Amendments

None yet.
