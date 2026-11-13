# CATCH-SIM: what the forecast model says if the rain changes or an overflow goes

First deliverable of CATCH-SIM, the catchment experiment simulator scoped in
[AMBITIOUS-RESEARCH-SCOPING-2026-11.md](AMBITIOUS-RESEARCH-SCOPING-2026-11.md), section 1. Record due 15 Dec 2026.
Owner: Ethan, with a Claude session doing the work. Stage: development (bounded exploration). Not a test of the forecast,
and nothing here changes a forecast, a frozen file, an issued prediction or the 2027 primary evaluation.

**Protocol written and pushed on 13 Nov 2026, before either experiment was run.** The results section is added
afterwards, in the same PR, and does not change anything above it.

## The claim this can support, and the one it cannot

- **Can support:** "Under the production model as fitted, if the rain over these overflows had been X times what it
  was, or if this overflow had not discharged at all, the model's expected spill days and the spot's level would have
  been Y." That is a sensitivity of the model, on days already past.
- **Cannot support:** that a real upgrade, storage tank, wetland or restoration will cut spills or E. coli by any
  amount. That the model is right outside the rain it was trained on. That a wetter or drier climate would look like
  scaled rain.
- **Never:** an upgrade effect made by lowering `lta_spills`. PR #298 found the model's response to that covariate is
  not monotone (Middleton, 2025 inputs: 0 gives 8.1 expected spill days a year, 2 gives 3.3, 10 gives 12.2). Neither
  experiment touches any site covariate.

## Places and overflows

| Place | Spot id | Kind | Upstream overflows | Company |
|---|---|---|---|---|
| Wharfe at Cromwheel, Ilkley | `bw-uke4100-08901` | river | 16 | Yorkshire Water |
| Windermere, Waterhead, Ambleside | `osm-windermere-waterhead` | lake | 4 | United Utilities |

20 overflows in all. The upstream list, each overflow's weight and its travel time are the ones the forecast issued in
its last logged build for each spot (forecast log, see Inputs), checked against `prototypes/research-lab/assets/paths/`.

## Inputs (offline; nothing fetched)

No Open-Meteo call, no EA request, no other fetch. All inputs exist on this Mac already. Shared files are copied into
a scratch `DIPCAST_ROOT` and `DIPCAST_STATE`; the originals are hashed (SHA-256) before and after the run, and the run
fails if any changed. The output file records every hash.

| Input | Where it comes from | Used for |
|---|---|---|
| Spill model `data/processed/spill_model.pkl` (MD5 `808da63d…`) | committed, `origin/main` 5f1ece11 | every chance |
| Lead calibration `data/processed/lead_calibration.json` (MD5 `9b3cc24c…`) | committed | lead-0 calibration |
| Annual returns `data/processed/annual_returns.parquet` | committed | site covariates, the year before |
| ERA5-Land archive rain, 8 cells × 2023-2025 (24 files) | main checkout `data/cache/rain/` (the forecast's cache) | rain features |
| EA start/stop events 2024-25, Yorkshire Water and United Utilities | main checkout `data/processed/ea_events_*.parquet` | observed spill days, for calibration error only |
| Forecast log `dipcast.duckdb` of 5 Nov 2026 12:36 UTC (SHA-256 `3d8e70c9…`) | a copy of the `state` release already on disk in another worktree's replay cache | upstream list, weights, travel times; the reproduction check |

The model's two hashes equal the version stamp on the last logged forecast (`spill=808da63d;cal=9b3cc24c`), so the
hindcast runs the model that issued the latest forecast in the log. **Established** (MD5 of the committed files,
compared with the log's `version` column).

From the forecast log this reads only `forecast_points.risk` and `forecast_overflows.p_cal`, `weight` and `travel_h`:
issued predictions, not outcomes. It does not read `p_status`, the shadow tables, or any spill or sample after
30 Sep 2026. Before writing this protocol I opened the last Waterhead issue in the log to learn its columns; no
experiment had been run.

## The base hindcast

As `scripts/check_upgraded_overflows.py` (PR #298) builds it: every day from 1 Jan 2024 to 31 Dec 2025, local-midnight
days, with the history days the travel times need before each year. Rain features from the archive
(`features.daily_rain_features`), the site covariates of the return year before (`annual_returns`, as `train.py` and
the build use them), the production model's `predict` (pooled trees plus the United Utilities site offsets), lead-0
calibration (`forecast.calibrate_at_lead`), then the spot's risk with `transport.combine_daily` and its level with
`transport.risk_label`. Each overflow's rain cell is `rainfall.grid_cell` of its position in the paths file.

## Experiment 1: scale the rain

Every hourly archive value in every cell is multiplied by s, for s in {0.5, 0.6, …, 1.5} (11 values), before the daily
features are built. Nothing else changes: season, covariates, weights and travel times stay as they were. All ten rain
features (daily total, 1-, 3- and 6-hour maxima, 3-, 7- and 30-day sums, the antecedent index, the two lagged days)
are sums or maxima of hourly rain, so each scales by exactly s.

Reported per overflow and year: expected spill days (the sum of the calibrated daily chances). Per spot and year: days
at each level and the mean risk.

### The monotonicity check (decides whether experiment 1 is shown)

- For each of the 20 overflows and each year (2024, 2025), take expected spill days E(s) on the 11-point grid. An
  overflow is **non-monotone** if, in either year, any step up in rain lowers it: E(s_k+1) < E(s_k) − 0.000001.
- **Monotonicity share** = overflows that are not non-monotone ÷ 20. Also reported, not used for the rule: how many
  overflow-days have a calibrated chance that falls when the rain rises one step, and the largest such fall; and the
  same count for the spot's risk.
- **Stop rule, as scoped and unchanged:** if more than 10% of overflows are non-monotone (3 or more of 20), rain
  scenarios are artefacts. Then the mode keeps "remove an overflow" only, and this record says why.
- **What I expect, inferred and not checked:** zero non-monotone overflows. The model constrains its ten rain features
  to be non-decreasing (`features.MONOTONE`), the lead-0 calibration is isotonic, and the spot's risk only rises when a
  chance rises. The check tests that the whole code path keeps that (the 20-hour day rule, missing hours, float32
  features, the calibration's interpolation). Passing it says the model's answer moves the physical way. It says
  nothing about whether the size of the move is right.

### Outside the rain the model has seen

The trees give a flat answer above their highest split, so a large s mostly repeats the wettest answer. Reported per
place and s: the share of overflow-days whose scaled daily rain is above the largest unscaled daily rain any of the 8
cells had in 2023-2025. That is a proxy for "outside the fitted range", not the training data's own maximum.

### Three storms replayed

Within experiment 1: at each place, the three wettest days of 2024-25 by the mean daily rain over that place's cells,
unscaled, at least 7 days apart. Chosen by this rule before running. Shown: the spot's level on that day and the two
after, at each s and with each overflow removed.

## Experiment 2: remove one overflow

For each upstream overflow, its term leaves the spot's combination: its chance is set to 0 on every day, so
`1 − Π(1 − w·p)` loses that factor. This is defined by the transport rule, not by editing a covariate. It means "if
this overflow had never discharged", which no real upgrade promises: an upgraded overflow can still spill, and the
model has no link between overflows, so it cannot say whether flow held back at one would spill at another.

Reported per overflow and year, at s = 1: days whose level falls, mean and largest risk drop. The mode also lets a
reader combine a removal with a rain scale; those numbers come from the same computation and are not separately
reported here.

## Reproducing the published level (completion check)

The forecast log keeps every issue's calibrated chance per overflow for leads 0 to 4, with the weight and travel time
it used, and the spot's published risk. It does not keep the past days' chances the build used for travel shifts, so
lead L can be rebuilt exactly only when no overflow's travel time reaches before lead 0: leads 3 and 4 at both places
(longest travel 52.0 h at Cromwheel, 65.3 h at Waterhead; `transport.shift_by_travel` needs up to two days and a part
of a third).

- **Check:** for every logged issue (Cromwheel from 13 Sep 2026, Waterhead from 3 Oct 2026, both to 5 Nov 2026), at
  leads 3 and 4, `combine_daily` of the logged chances, weights and travel times gives the logged risk. **Pass:** every
  level equal and the largest risk difference at most 0.000001.
- Then the same removal as experiment 2 on those issued builds: how many issued days at leads 3-4 would have shown a
  lower level without each overflow.
- The rain-scale experiment cannot be run on issued builds: the log keeps a daily rain total per overflow, not the
  hourly forecast the features need.

## Uncertainty, stated beside each number

1. **Year to year.** Every figure is given for 2024 and 2025 separately. The gap between them is the spread. Two
   years is a small sample: this is not an interval.
2. **Calibration error.** At s = 1, the model's expected spill days against the EA's observed spill days at each
   place's overflows (`features.spill_days`, UTC days, as the model trains on), per year: observed ÷ expected. For
   Waterhead's United Utilities overflows the model was fitted on 2023-2025, so that ratio is in-sample and will look
   better than it is. It is stated beside the figures, not used to correct them.
3. **Outside the fitted rain**, as above.

All three are on seen data: 2024-25 rain, spills and the model's own fit. Development evidence, labelled so.

## What follows each outcome

| Outcome | Next |
|---|---|
| 0 to 2 non-monotone overflows | Both experiments in the workspace's what-if mode, labelled as the model's answer, not a prediction |
| 3 or more | Remove-an-overflow only in the mode. Rain scaling kept in this record as the reason. Next deliverable: a diagnosis of which features carry the fall |
| Reproduction fails | Find the cause before showing removal on issued builds. The hindcast part can still be shown, with the failure stated |
| Any outcome | Ethan's two decisions (below). Then the next useful step for CATCH-SIM: replayed historical storms from before 2024, or a third catchment from cached files |

## Where it lives

A what-if mode of the catchment workspace, in `prototypes/research-lab/workspace/whatif/`, made by
`scripts/lab_catch_sim.py`. The build leaves that folder out of the site (`build_site.write_lab`), so it is not
published, and no page links to it. Every view says "the model's answer to a what-if, not a prediction of a real
upgrade".

## Needs Ethan (not decided here)

1. Whether a scenario view is shown publicly at all, or stays a Lab prototype with a "model sensitivity, not a
   prediction" label.
2. Whether "remove an overflow" may name a company's overflow on a public page. The prototype names them, as the
   public workspace already does on its map.

## Budget

Offline. At most 2 CPU-hours and 4 cores. Zero Open-Meteo calls, zero EA requests, zero other fetches.

---

## Results (run 13 Nov 2026, after the protocol was pushed in 6fd1805e)

Development evidence on seen data (2024-25 rain, spills and the model's own fit). `scripts/lab_catch_sim.py`, 24 s on
4 cores. 27 shared inputs copied to scratch and hashed before and after: unchanged. Nothing fetched. Tables:
`docs/CATCH-SIM-2026-12-{summary,removal,expected,storms,issued}.csv`.

### Checks

- **Monotonicity: 0 of 20 overflows non-monotone** (share monotone 1.0). No overflow-day chance fell when rain rose
  one step (116,960 steps at Cromwheel, 29,240 at Waterhead), and no spot-day risk fell (7,310 steps at each). The stop
  rule is not met, so **both experiments stay in the mode**. This shows the model moves the physical way. It does not
  show the size of the move is right.
- **Reproduction: passed at both spots.** 562 of 562 issued levels at leads 3-4 rebuilt exactly from the log (largest
  risk difference 3e-16 Cromwheel, 1e-16 Waterhead), issues 12 Oct to 5 Nov 2026. **Deviation from the protocol:**
  the log has no travel times before 12 Oct 2026 14:10, so 285 earlier Cromwheel issues and 110 Waterhead issues could
  not be rebuilt and are left out, not filled.
- **Calibration error at x1** (observed ÷ expected spill days): Cromwheel 1.25 (2024), 1.22 (2025): the model expects
  fewer spills than the EA recorded. Waterhead 0.81, 0.72: more than recorded, although these United Utilities years are
  in the model's training data. Why Waterhead's in-sample ratio is below 1 is not checked (inferred candidates: UTC vs
  local days, the EA file against the training labels). Bridge Lane CSO has no event in the EA file.
- **Outside the fitted rain:** against all 8 cells (the stated proxy) 0% at Cromwheel even at x1.5, 1.1% at Waterhead.
  Added after the protocol, against each place's own cells: Cromwheel 0.05% at x1.5. A weak proxy at Cromwheel.

### Experiment 1: scaled rain, days at moderate risk or above (2024 / 2025)

| Rain | Cromwheel | Waterhead |
|---|---|---|
| x0.5 | 115 / 108 | 9 / 16 |
| x1.0 (as fitted) | 234 / 175 | 49 / 52 |
| x1.5 | 285 / 197 | 80 / 85 |

Cromwheel's very high days: 5 / 8 at x0.5, 54 / 37 at x1, 108 / 80 at x1.5. Waterhead never reaches high in either
year at any scale. The response is less than proportional above x1 at Cromwheel (half the rain halves moderate-or-above
days; 1.5 times the rain adds about a fifth). Storms: at Cromwheel the storm day itself stays very high at every scale
on 22 May 2024 and 20 Sep 2025; the days after move by one or two levels.

### Experiment 2: take one overflow away (x1, days a level lower, 2024 / 2025)

- **Cromwheel** (234 / 175 days moderate or above): Addingham 3xDWF 56 / 26, Addingham 6xDWF 30 / 24, Rivadale View
  28 / 25, Middleton 20 / 20, Grassington STW 22 / 14; the other eleven 0 to 14. No single removal changes the level on
  any storm day. On issued forecasts (leads 3-4), Middleton or Rivadale View would each lower 65 of 562 levels.
  This agrees with PR #298: one overflow alone moves Cromwheel little, because nearby overflows spill on the same days.
- **Waterhead** (49 / 52 days moderate): Ambleside WwTW 49 / 52, that is every moderate day; Glebe Road PS 20 / 17;
  Elterwater 19 / 20; Grasmere 0 (weight 0.0004). Issued forecasts: Ambleside 55 of 562 lowered. In the model,
  Waterhead's moderate days come from Ambleside WwTW.

Removal never raised a level (checked on every day, scale and overflow).

### Limits

- A model sensitivity on past days. Taking an overflow away means "had it never spilled", not an upgrade.
- Scaled rain is not a climate scenario. Two years is the only spread shown; it is not an interval.
- Weights and travel times are the 5 Nov 2026 build's, used for both years.

### Next (register row)

| Field | Content |
|---|---|
| Identity | CATCH-SIM; Claude session for Ethan; this PR; `scripts/lab_catch_sim.py`, `prototypes/research-lab/workspace/whatif/` |
| Evidence | Monotonicity 0 of 20 (stop rule not met); reproduction 562/562 at leads 3-4. Seen data, development |
| Stage and claim | Exploration, Lab prototype, not published. Claim: the model's answer to two what-ifs |
| Next deliverable | Ethan's two decisions. Then storms from before 2024 (cached rain), or a third catchment |
| Release route | Ethan decides public or Lab-only, and naming overflows. Rollback: delete `whatif/` and the build's ignore entry |
