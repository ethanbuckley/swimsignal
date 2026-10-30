# Regional routing of the nine-company v2 spill model: candidate, seen-data description and shadow plan

Written 30 October 2026 under `docs/RESEARCH-WORKFLOW.md`, register row **2 / REGIONAL**
(`docs/RESEARCH-RECOVERY-2026-10.md`). This is development, not an adoption. It changes no production model, no
displayed level, no alert and no active window (lead calibration B, ensemble rain D4, live-status shadow, A8,
option B, winter recalibration, the 2027 primary evaluation).

## Continuation record

| Field | Content |
|---|---|
| Identity | REGIONAL; owner: Claude session "SwimSignal pollution event lifecycle"; this PR; code `scripts/regional_routing.py`, `scripts/regional_routing_rebuild.py`; models in `swimsignal-private/baselines/regional-routing/` |
| Evidence | v2 (#357) arm (b), trained on 2024-25, scored on January-August 2026: all nine Brier 0.03654 against production 0.04204; better at eight companies by 11-23%; **United Utilities worse**, 0.03902 against 0.03774 (+3.4%, interval wholly above zero). The historical verdict stands: not adopted. Every January-August 2026 row has been seen |
| Stage and claim | Development: a frozen routing candidate and a prospective shadow plan. No claim of improvement until the shadow reads |
| Next deliverable | **Built in this PR** (section 4): `src/dipcast/shadow_regional.py`, hooked into the forecast behind guards, writing table `shadow_regional_v1`; `scripts/regional_shadow_check.py`. Next: the read harness (labels and scores), before the window ends |
| Milestone and budget | Logger built 30 October 2026 (due 6 November). The window opens on the first full UK day after the first build that logs shadow rows once this merges, runs 28 days, and is read the next day (about early December). Read harness due one week before the window ends. No fetch, no Open-Meteo call, no new account; one extra model prediction per overflow-day in the build; the v2 file adds 1.1 MB to the repository |
| Release route | If the shadow is useful (section 5), a limited-rollout proposal for the eight companies with United Utilities and every other site on production, staged after the frozen windows close and stated against the 2027 tag date. Rollback: the routing table falls back to production for every company |

## 1. The candidate's files (recovered and verified)

The v2 run's arm (b) file had not survived on disk; only arm (a) remained in a scratch folder. It was rebuilt on
30 October from the run's own tagged code (`record/nine-company-v2-run`), in a scratch root with the 2024-25 inputs
linked read only, with the run's library versions (scikit-learn 1.9.1, pandas 3.0.5, numpy 2.5.3):
`scripts/regional_routing_rebuild.py`. **All three files match the recorded SHA-256 byte for byte:**

| File | SHA-256 |
|---|---|
| `spill_model_v2_offsets.pkl` (arm b, the candidate) | `9e0fc54a9356e4cea528606422dc569691453fc3ab98ea31986f19437ba501f2` |
| `spill_model_v2_pooled.pkl` (arm a) | `bd8faaaf31031fa3ca8ac763dc7047c9b591ffe37feddb220b7e52d73b1f2dc3` |
| `spill_model_v2_offsets_r025.pkl` | `ab2e7ba834bab881…` (not kept) |

The shared inputs (annual returns and the nine companies' 2024-25 event files) hashed to `df2ce1501c254996` before
and after; nothing was written to the scratch root or to any shared cache. The two kept files and a SHA256SUMS are in
`swimsignal-private/baselines/regional-routing/`. Production is `data/processed/spill_model.pkl`, SHA-256 `faa7917e…`
on main, the model v2 was compared with.

## 2. The routing rule, frozen

`regional-v1` (`scripts/regional_routing.py`, three tests):
- the eight companies other than United Utilities → v2 arm (b);
- United Utilities, any other company (Welsh, Scottish, Irish sites), and a row with no company → production.

Both models take the same 15 inputs, so one frame serves both. A site with no v2 offset gets v2's pooled layer, the
model's own rule. The rule was **chosen after seeing** v2's per-company results, so it is a development hypothesis;
the whole rule, fallback included, is what the shadow judges.

## 3. What the seen rows say (a description, not evidence)

From v2's committed per-company scores (`docs/NINE-COMPANY-MODEL-V2-TEST-2026-11-scores.csv`), weighting each
company's Brier by its rows, January-August 2026, ERA5-Land rain, lead 0:

| | All nine, Brier |
|---|---|
| Production | 0.04204 |
| v2 arm (b) everywhere | 0.03654 |
| **regional-v1** (v2 at eight, production at United Utilities) | **0.03633** (13.6% below production) |
| Overflow climatology / company flat rate | 0.05261 / 0.05608 |

This is the rows that chose the rule, scored with reanalysis rain, without the lead-calibration map the live site
applies. It says the rule is worth a prospective look. It does not say how it will do live.

## 4. The shadow plan (draft for review before the logger merges)

- **What runs (built).** In each site build, for every overflow-day and lead 0 or later that a spot's forecast
  computes, the routed raw chance (`regional-v1`; the rule and the v2 file's hash on every row; production's version
  stamp too) beside production's raw and shown (lead-calibrated) chance. Both models read production's own site-day
  frame, so the shadow makes no rain request. Written to its **own table, `shadow_regional_v1`,** in the state
  database (`dipcast.duckdb`, which the build already uploads to the `state` release): not the issued-forecast table
  (`forecast_overflows`, whose history the product chat owns), and never into any displayed value, alert, score or
  level. The module returns new arrays, never alters its inputs, runs only behind guards that log and carry on, and
  is off when the committed v2 file (`data/processed/regional/`) is missing or has another hash. Rows repeat where
  several spots share an overflow, as the issued table's do; the read takes one per build, overflow, day and lead.
- **Checked on 30 October** (offline, archived rain passed in, no Open-Meteo call): 16 real overflows at four
  companies; the four United Utilities overflows identical to production; the twelve others from v2 (mean absolute
  difference 0.013); every value finite where production's is; production's arrays and frame unaltered; shared
  inputs hashed the same before and after.
- **Check before the window opens** (`scripts/regional_shadow_check.py` on a copy of the state database): every
  production-routed row carries production's raw chance; the eight companies, and only they, are routed to v2; the
  rule and model stamp are the frozen ones. It prints the window the first logged build implies.
- **Labels.** Spill-days from SwimSignal's own polls, with the live-status shadow's rule for a known status (no gap
  between current readings over 8 hours). A missing or stale status is unknown, never a dry day.
- **Window.** 28 UK days from the first full day after the first logged build. Not extended or cut after it starts.
- **Primary measure (lead 0, the eight companies):** Brier of the routed probability against production as shown,
  difference with a 95% interval from a two-way bootstrap over overflows and 7-day blocks (2,000 resamples, seed
  20261106). **Proposed useful margin:** an improvement of at least 5% of production's Brier with the interval below
  zero. Why 5%: the seen gain (13.6%) came from the rows that chose the rule, with reanalysis rain; live winter poll
  labels and forecast rain will shrink it; 5% is about the gain worth carrying a second model and its monitoring.
  To settle in review, before the window opens.
- **Guardrails.** Reported per company, with the same interval: a company whose routed Brier is worse than
  production's by more than 5% with the interval wholly above zero goes to the fallback in any rollout proposal,
  rather than blocking the others. United Utilities is production by construction.
- **Secondary, reported:** leads 1-4; routed against production's raw probability; reliability tables; the two simple
  references (company flat rate, overflow climatology, from 2024-25); coverage (rows with a known label).
- **Not decided by the shadow:** any change to the shown level. A useful result earns a limited-rollout proposal of
  its own (staging, fallback, monitoring, and its effect on the 2027 tag on 30 April 2027).

## 5. What would end or change this

- **Useful:** limited-rollout proposal for the eight companies, United Utilities and all other sites on production.
- **Not useful:** the record says by how much; v2 stays a development model. Reopen with a new input or a new
  population, not by rerunning this window.
- **Too few known labels** (under 10,000 known overflow-days at the eight companies): extend by one further
  28-day window, stated now, then read.

## Settled before the window opened (30 October 2026, 22:57 UTC)

Recorded before the first possible window day (31 October, UK time), with no shadow row read:
- **Useful margin: 5%,** as proposed in section 4: the routed lead-0 Brier at the eight companies at least 5% below
  production's as shown, with the 95% interval of the difference below zero.
- **Guardrail: 5%,** as proposed: a company worse than production by more than 5% with its interval wholly above zero
  goes to the fallback in any rollout proposal.
- **First logged build (inferred, to be confirmed):** the publishing build of the merge, run 41140069210 (forecasts
  22:48-22:55 UTC on 30 October, 109 spots, no shadow warning in its log). Its state stays in the build cache until
  the release copy is next published (when it is over 12 hours old, after about 07:45 UTC on 31 October). The window
  is whatever `scripts/regional_shadow_check.py` reports from the first logged rows: if that is this build, 31
  October to 27 November, read on 28 November.
