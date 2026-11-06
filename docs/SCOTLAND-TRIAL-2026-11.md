# Scotland trial, 1 November 2026

Ethan's decision on 1 November 2026: launch Scotland as a labelled trial now, on past data, as England launched, once
the model's under-forecast is fixed. Built behind `DIPCAST_SCOTLAND_TRIAL`, off by default. Code:
`src/dipcast/scotland_trial.py`. Contains Scottish Water data licensed under the Open Government Licence v3.0.

## 1. The evidence

| Check | Data | Result |
|---|---|---|
| Gate A ([write-up](SCOTLAND-HINDCAST-2026-11.md)) | 254 overflows, 52,891 spill-days, 2022-25 | PASS: beats each overflow's own history at leads 0-3 (lead 0 BSS 0.18, 0.13 to 0.23). Forecast 72% of the spill-days that happened |
| Calibration map (`scripts/scotland_recalibration.py`) | Fitted 2022-24 (168,095 rows), checked 2025 | PASS, 12 of 12 parts (below). Exploratory: 2025 was seen in aggregate before the rule was written |
| Gate B, live shadow (`scottish_shadow.py`) | 11 Oct to 31 Oct 2026 | Not passed: skill +0.01 to +0.22 in five pieces, every interval crosses zero, 3 to 7 days each |
| Outside review | | None yet |

The map's rule was committed (4e6734b1) before its run. One Platt map on the logit, `p' = 1 / (1 + exp(-(a + b·logit p)))`,
a = 0.449, b = 0.750, for the production spill model (stamp 808da63d) only. On 2025, set G, 233 overflows,
15,604 spill-days, `docs/SCOTLAND-RECALIBRATION-2026-11.json`:

| Lead | Level before | Level after (R1: 0.9-1.1) | Brier gain over unmapped (R2) | BSS vs earlier years (R3) |
|---|---:|---:|---|---|
| 0 | 0.67 | 1.03 | 0.053 (0.026 to 0.077) | 0.23 (0.15 to 0.30) |
| 1 | 0.65 | 1.00 | 0.056 (0.030 to 0.080) | 0.20 (0.12 to 0.27) |
| 2 | 0.62 | 0.98 | 0.062 (0.036 to 0.086) | 0.18 (0.10 to 0.25) |
| 3 | 0.65 | 1.01 | 0.051 (0.023 to 0.077) | 0.15 (0.07 to 0.22) |

At lead 1 the mapped forecast's bands sit within 1 to 5 points of what happened (0.0-0.1: 3.9% forecast, 4.7%
observed; 0.9-1.0: 93.7% forecast, 88.4% observed). England's lead calibration, which the shadow applies, leaves
the level at 0.58 to 0.66.

## 2. What the trial changes, when on

1. **Overflows.** The overflow table gains the 1,485 Scottish Water overflows the shadow forecasts. They are snapped by Scotland's
   marine rule. Emergency overflows, marine outfalls and unsnapped ones are left out. Each carries its live status and data
   state from Scottish Water's API (checked offline on the 4 Oct answer: 1,279 live, 178 offline, 28 stale).
2. **Calibration.** Their spill chances take Scotland's map instead of England's lead calibration, at every lead.
   Leads 4 and 5 were not checked; they use the same map.
3. **Spots.** `spots-scotland.csv` lists SEPA's three inland bathing waters. Upstream counts are from the offline run on 1 Nov:

   | Spot | Overflows upstream | Note |
   |---|---:|---|
   | Dores, Loch Ness | 5 | |
   | Luss Bay, Loch Lomond | 8 | Pin snaps 419 m to the loch's centre line |
   | Loch Morlich | 0 | Page says "No monitored overflow found upstream" |

   SEPA designates all three, the footing England's designated spots have. Each page says "Scotland: trial forecast"
   and, in full, "Scotland trial: Scottish Water's overflows, checked against their 2022 to 2025 records and
   calibrated for Scotland. Not yet confirmed on live data." It shows SEPA's rating and links to SEPA's page.
   SEPA's samples are not republished, because their terms forbid it.
4. **Words.** The home list's opening says "in England, and in Scotland as a trial". The E. coli note at trial
   spots says it is not validated in Scotland. The credits and the footer name Scottish Water.
5. **Unchanged.** The shadow and Gate B are untouched: the shadow keeps England's calibration, so its arm does not change.
   Click-anywhere stays England only (`write_any_point` drops the Scottish rows).

**Added 1 Nov 2026, evening:** nine more spots, on the Scottish Outdoor Access Code and a public body's or
charity's page saying people swim there (`SPOT-ADDITIONS-2026-11.md`): six Loch Lomond bays, Tollie Bay (Loch
Maree), Loch Lubnaig and the River Almond at Almondell. Twelve in all.

## 3. Limits, as known

- **No loch outlines.** No loch outline is loaded for Scotland. Each loch is placed on OS Open Rivers' centre line,
  and travel across it is by that line. The page names the loch from `spots-scotland.csv`, not from the link;
  Dores had snapped to the burn "Allt a' Mhinisteir".
- **Open-Meteo calls.** The three spots add 8 rain cells and 3 weather points: about 123 calls a day at the
  planned worst case, about 90 net of what the shadow already asks for the same cells. After the 28 Oct lakes
  about 41 a day were spare. The build's ration is enforced before each request, and spots ask first. So past
  the cap it is the shadow's and the spare-only requests that are held back. Builds run about every 2.9 hours, not every 30
  minutes, so a real day uses less.
- **Licence.** The live feed names no licence; Scottish Water's page says "an open license for reuse". Turning
  the trial on publishes forecasts built on it. That is the owner's call.
- **Static footers.** The about-line in 13 static pages' footers still says "swim spots in England".

## 4. Switching it on, and off

On: set the repository variable `DIPCAST_SCOTLAND_TRIAL` to `1`. `DIPCAST_SCOTTISH_WATER` has been `1` since 11 Oct.
The next build lists the three lochs. Off: delete the variable; the next build drops them.

The trial also switches itself off if the spill model changes. The map is stamped with the model it was fitted
for, and a new model needs a new map and check.

## 5. Next

| Field | Content |
|---|---|
| Stage | Limited forecast (research workflow): three SEPA lochs, labelled trial |
| Supported claim | On 2022-25 Scottish Water records, the English model with Scottish covariates ranks overflow-days better than their history, and with Scotland's map its level is right on 2025 at leads 0-3 |
| Next deliverables | 1. Gate B from the shadow after its Nov-Jan window. 2. A shadow arm with Scotland's map, so the live check scores what the trial shows. 3. Scottish river spots, each with an authority's own access statement. 4. Click-anywhere in Scotland. 5. Outside review (Stirling invitation, Ethan's) |
| Release route | Owner sets the variable; rollback is deleting it |
