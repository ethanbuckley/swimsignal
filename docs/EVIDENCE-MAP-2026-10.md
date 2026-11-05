# Evidence map and live status (prototype map, 30 October 2026)

This PR does two things:

1. **Live status wording, on every page (not behind a flag).** Every surface that shows a spot's level now
   says how many overflows upstream reported a status at the last poll. Where none did, the spot's answer
   leads with "Live sewage spill status unavailable" and labels the level as the modelled forecast. This
   is a correctness fix from the review of PR #463.
2. **The evidence map, behind `?evidence=1`** on a spot's address (`spot/<id>/?evidence=1`). It shows
   where the forecast has evidence upstream and where its knowledge ends. Without the flag the page draws
   no map and asks for no extra file.

The forecast, the levels and the order of the list do not change. A missing status never makes a level,
and a valid modelled forecast is never removed.

Code:
- Live status: `src/dipcast/site/levels.js` (`liveCover`, `liveHead`, `liveLine`, `liveParts`, and
  `headParts` where right now is not known). Used in `index.html` (`answerParts`, `answerWords`,
  `coverWords`, `savedCard`, the share picture), `evidence.js` (`evidenceNowGap`, Plan a swim) and
  `experience.js` (`compareNow`).
- Map: `src/dipcast/site/evmap.js`, with a small hook in `index.html` (`EV_MAP`, `mountEvMap`). `sw.js`
  stores `evmap.js` for offline use.
- Build outputs: `src/dipcast/trace.py` (`cut_ends`, `spot_trace_parts`) and `scripts/build_site.py`.
  The trace file gains `cut_ends`, `data/upstream/<id>.json` gains each overflow's status fields, and
  `river_state` gains `station_lat` and `station_lon`. `src/dipcast/pages/data.html` describes the new
  fields.
- Tests:
  - Node: `tests/site_live_status.test.cjs` (zero, partial and full coverage) and
    `tests/site_evmap.test.cjs`, plus updated wording in `tests/site_honest_headlines.test.cjs`,
    `tests/site_opening.test.cjs`, `tests/site_evidence.test.cjs` and `tests/site_planner.test.cjs`.
  - Python: `tests/test_trace.py`, `tests/test_upstream_files.py`, `tests/test_flows.py` and
    `tests/test_cards.py`.

## User task and success measure

User task: "Before I go, show me where SwimSignal's forecast for this spot has evidence, and where its
knowledge ends."

Success measure: a reader shown the poorly covered spot does not conclude the water is clean because the
page or the map looks empty or calm. In detail:

1. "No live status" looks and reads differently from "the statuses we have show no spill", in words and in
   marks, never by colour alone.
2. Every item tapped (or reached from the keyboard) shows its source, when it was reported and how old that
   is, and how it stands to the spot. For example: "25.7 km upstream along the rivers. Modelled travel time
   to the spot: about 36 h, at the model's assumed 0.2 m/s".
3. Gaps are drawn, not left out:
   - overflows with no live feed;
   - feeds that are down or stale;
   - where the 60 km trace stops a river that goes on;
   - the unmeasured rivers between the marks;
   - no gauge;
   - no lab samples.

## 1. Live status wording (all pages)

A status is what a company's live feed said at the last poll before the update. It is counted as
`forecast.live_counts` counts it, in `now.monitored_upstream`, after the page has aged stale feeds. "None"
means no overflow upstream gave a current status.

| Surface | Before | After |
| --- | --- | --- |
| Spot answer, zero coverage (Wye, Symonds Yat) | "Low risk from sewage spills" / "Forecast only: no overflow upstream reports live" | First, in bold: "Live sewage spill status unavailable: none of the 14 overflows upstream reports live, so whether any is spilling is not known." Then "Modelled forecast", then "Low risk from sewage spills", then "From the rain forecast and each overflow's past spills, not from live readings" |
| Spot answer, partial (Sandy Lane, 1 of 13) | "Low risk from sewage spills" / "Forecast only: the overflows that matter most here do not report live" | First: "Live status from 1 of 13 overflows upstream: none spilling at the last poll; 12 do not report, so could be spilling unseen." Then the level, then "Modelled forecast: most of the model's weight here is on overflows that do not report live" |
| Spot answer, partial or full, right now known (Cromwheel, 13 of 16) | The count sat at the bottom of the answer: "13 of 16 overflows upstream report live, none spilling now; 3 do not, so could be spilling unseen" | The same facts move to the top, before the level: "Live status from 13 of 16 overflows upstream: none spilling at the last poll; 3 do not report, so could be spilling unseen." With all reporting: "Live status from all 45 overflows upstream: none spilling at the last poll." Not repeated at the bottom |
| Compact headline (list rows, map tooltips, embed, sites page, `alerts.json` and so the push alerts and share cards in `cards.py`), zero coverage | "Low risk forecast: no overflow upstream reports live" | "Live sewage spill status unavailable: low risk forecast" |
| Compact headline, partial with right now not known | "Low risk forecast: the overflows that matter most here do not report live" | "Live status from 1 of 13 overflows upstream: low risk forecast" |
| Compact headline, a raised forecast day, zero coverage | "Moderate risk tomorrow: sewage spills" | "Moderate risk tomorrow: sewage spills (modelled, no live status)" |
| Saved card | "Low risk" over "Forecast only: ..." | Line above the level: "Live sewage spill status unavailable" (or the count where right now is not known); unchanged where it is known |
| Share picture, drawn on the device | The headline | For zero coverage, or where right now is not known, the status first, bold, with "Modelled forecast:" when nothing reports. Otherwise the count after the level |
| Plan a swim, the evidence line | "Forecast only: no overflow upstream reports live." | "Live sewage spill status unavailable: forecast only." or "Live status from 1 of 13 overflows upstream: forecast only." |
| Compare table, right now | "Not known here: the overflows that matter most here do not report live." | "Live status from 1 of 13 overflows upstream: right now not known here." |

Notes on the table:
- The prerendered answer (`scripts/prerender_spots.js`) runs the same functions, so it leads the same way.
- Partial coverage where right now is known (most of the model's weight reporting) keeps the compact
  headline as it was, for example "Low risk for the next five days". Its counts are on the spot's answer.
- The compact text keeps its level colour in list rows, as before.

## 2. The evidence map (`?evidence=1`)

A tile, "Where the evidence is", sits under the five days on a phone and in the first column on a
desktop. Top to bottom:

- **The counts first**, with a mark beside them:
  - "Live sewage spill status unavailable." (hollow dashed mark);
  - "Little live evidence: status from 1 of 13 overflows upstream." (hollow struck-through mark), used
    where the reporting overflows carry under half the model's weight;
  - "Live status from 13 of 16 overflows upstream." (filled mark).

  Then what they reported "at the last poll before this update", and how many gave no current status
  "so could be spilling unseen".
- "Statuses as at this update, issued 30 Oct, 17:49 (1 h ago)."
- **The drawing**, built from the build's own files:
  - the traced rivers;
  - a bar wherever the trace stops a river that goes on;
  - the gauge (a diamond) where its station's place is given;
  - every overflow upstream;
  - the spot, ringed, with a square for lab samples.

  The drawing takes keyboard focus, and the arrow keys step through the marks, nearest the spot first.
  A tap does the same for one mark; taps on one place step through overlapping marks.
- **The key**, with "larger mark: more of the model's weight".
- **"Every mark and gap in words (N)"**, folded. It has three lists:
  - "Statuses, readings and records";
  - "Gaps: what is not known here";
  - "How these are counted". This gives the share of the model's weight reporting, with what that weight
    is and is not, and what a status is: the last poll, not a continuous reading, plus the 6-hour stale
    rule.

Marks:

| Mark | Meaning |
| --- | --- |
| filled dot, ringed | spill reported at the last poll, or lately (water still counted) |
| filled dot | not discharging at the last poll, from a current feed |
| hollow, struck through | in a live feed, no current status: offline, stale, feed down, or now over 6 h old where read |
| hollow, dot inside | status not in this update's file (an upstream file from before this change) |
| hollow, dashed | not in any live feed SwimSignal reads |
| bar across a river's end | where the trace stops, from `cut_ends` |
| diamond | river gauge (level only, not part of the pollution level) |
| blue line | river traced; nothing along it measured |
| square beside the spot | lab sample held (filled) or none (dashed) |

### Wording (review item 2)

- **The weight.** An overflow's weight is not called "reach" and is not given as a share of a spill's
  bacteria arriving. It combines the model's travel and dilution assumptions and is not a measured share of
  anything. The share of weight reporting appears only in the notes, and is defined there.
- **Travel times** are "modelled travel time ... at the model's assumed 0.2 m/s".
- **Statuses** are "at the last poll before this update", with the 6-hour stale rule. They are never
  described as continuous observation.
- **No causal claims.** Nothing says a spill caused anything at the spot. Tests check for "safe", "clean",
  "bacteria" and "reach".

### Data from the build (review item 3)

- **Trace cut ends**: `trace.cut_ends` uses the same arithmetic as `transport.traced_lines` (left
  unchanged). It lists the place on each link the 60 km cap shortens, and `write_traces` writes these as
  `cut_ends`.
  - An empty list means every traced river reaches its source within 60 km. The map then draws no bar and
    says so.
  - A file without the field leaves the limit undrawn and says so.
  - I ran `trace.spot_trace_parts` on the main checkout's river network pickle, read only and with no
    forecast. Its lines match the published trace files exactly for Cromwheel, Symonds Yat and Sandy Lane.
    The cut ends were:

    | Spot | Cut ends | What the old page estimate (dead ends at 58.2 km or more) gave |
    | --- | --- | --- |
    | Cromwheel | 0 | 3 bars, none of them a cut |
    | Symonds Yat | 6 | 8 bars |
    | Sandy Lane | 8 | not checked |

    The estimate was wrong in both spots I could compare, which is why it is gone.
- **Per-overflow status**: `write_upstream` now writes `status`, `data_state`, `feed_updated_at` and
  `latest_event_end` for every overflow. That is about 120 bytes an overflow, or about 22 kB more for
  Warleigh Weir's 185.
  - The map takes each overflow's mark from its own fields. It never works one out from the spot's counts:
    `evmapOthers` is removed.
  - A row without `data_state` (any file published before this change) is drawn as "status not in this
    update's file".
- **Gauge position**: `attach_river_levels` writes `station_lat` and `station_lon` from the Environment
  Agency station record its lookup already matched. Without them, the gauge is described in words ("4.5
  km away in a straight line ... Not drawn").

## The spots (live data, 30 Oct 2026, issued 17:49 UTC)

**Well covered: Wharfe at Cromwheel, Ilkley (`bw-uke4100-08901`).**
- 16 overflows, all Yorkshire Water. 13 gave a current status; they carry 74% of the model's weight.
- None was discharging. 2 had spilled lately (Grassington STW, ended 28 Oct 10:32; Kettlewell STW).
- Two Addingham overflows were offline.
- Gauge 1.0 km away. Lab sample 24 Sept. Rated poor.
- No river is cut at 60 km.

**Poorly covered: River Wye, Symonds Yat (`wye-symonds-yat`).** This is the thinnest evidence of the 109
spots:
- None of 14 overflows reports live (all Dŵr Cymru Welsh Water, no feed).
- No lab samples, algae checks or rating.
- Gauge 4.5 km away.
- The trace is cut at 60 km in six places.
- Its answer said "Low risk from sewage spills"; it now leads with "Live sewage spill status unavailable".

**Partial coverage: Sandy Lane, Chester (`bw-ukd6300-40752`).**
- 1 of 13 overflows reports live, carrying 3% of the model's weight. The other 12 have no feed.
- Right now is not known, so the compact headline is "Live status from 1 of 13 overflows upstream: low
  risk forecast".

## 3. An overflow's weight, in words (second review round, 30 Oct 2026)

Every page now calls an overflow's weight a **modelled relative contribution weight**. It comes from the
transport assumptions: travel time and die-off on the way, and dilution. It is neither a measured
bacterial concentration nor a calibrated chance of contamination.

- **Definition.** Given once, in `levels.js` (`WEIGHT_SAID`), and shown on the overflows tile and the
  organisers' table. `profile.py` and `scripts/site_profile.py` carry the same words in Python.
- **Labels.** "22% weight" and "model weight" replace "reach" and "% reach".
- **Methods page.** methods.html now says the index combines the weights "as if they were probabilities, is
  an approximation" (the formula in `transport.combine_daily` is 1 − Π(1 − chance × weight)).
- **Unchanged.** Numbers, thresholds, ordering, file and column names (`weight`, and the organisers' CSV
  column `reach`, whose description now says the column keeps its name) and the model files. The model
  code's own comments (`src/dipcast/model/transport.py`, `forecast.py`) still say "0% reach" and that the
  product "is treated as the probability", because those files are out of bounds here.

### Checked on the build's own writers, with cached records (no forecast, no network)

`scratchpad/evmap-proto/real_writers.py` reads the main checkout's caches. It calls:
- `RiverNetwork.load` on `data/processed/river_network.pkl`;
- `overflows.build_overflows` on `data/processed/live_latest.parquet`, which is from 12 Sep 2026 15:13 UTC;
- for each spot, `trace.spot_trace_parts`, `transport.upstream_overflows` and `with_data_states`, as
  `forecast_point` does;
- the real `build_site.write_traces` (with cuts) and `build_site.write_upstream`.

`readback.cjs` then reads the files back through `evmap.js`, and the page was rendered at 375 px from them.

| Spot | `cut_ends` written | Bars drawn | Per-overflow statuses (12 Sep cache) |
| --- | --- | --- | --- |
| Cromwheel | `[]` | 0 (with the note "Every river traced reaches its source within 60 km") | 15 `live` + 1 `offline`. For example, YWS00176 status 0, `feed_updated_at` 2026-09-12T14:40:27+00:00, `latest_event_end` 2026-03-31T04:18:39+00:00 |
| Symonds Yat | 6, e.g. [52.02173, -2.67037] | 6 | 14 `no_feed`, `feed_updated_at` null |
| Sandy Lane | 8, e.g. [53.12818, -3.22566] | 8 | 12 `no_feed` + 1 `live` (UUP00125, 2026-09-12T14:56:44+00:00) |

Read back an hour after the cached poll, the statuses come out as current. Read back at 30 Oct 18:49, the
same statuses are shown as over 6 hours old.

The gauge position could not be checked on real records. `river_state.station_lat/lon` come from the EA
station that `flows.level_lookup` matches. That lookup needs `data/cache/ea_level_stations.json` and the
EA's latest-readings request, and neither is in the local caches. A build run, or that cache file, would
supply it.

## Not done

- **Upstream statuses are not yet published.** The live files predate this change, so until the next build
  Cromwheel's 6 overflows outside the ten show "status not in this update's file".
- **Station positions are not published yet either**, so the gauge is shown in words only. Drawing it is
  tested with given coordinates.
- **The colour of a list row** still follows the level, so "Live sewage spill status unavailable: low risk
  forecast" shows in the low-risk green.
- **`last_status`** (a spill running when a company's feed last answered) is in the ten listed overflows
  only. It is not added to the upstream file.
- **Lakes** have not been checked on the map.
- **Checked widths**: 320 and 375 px for this round; 1440 px only in the first round.

## A 5-minute check with a real person

Use a phone, someone who swims in rivers, and neither spot's page seen before.

1. Open `spot/wye-symonds-yat/` (no flag) and hand them the phone. Say only: "You're thinking of swimming
   here this weekend."
2. After 30 seconds, ask: "What does SwimSignal know about sewage spills upstream right now?"
   - **Pass**: they say it has no live status, or it is a forecast.
   - **Fail**: "nothing's spilling", "it's clean" or "it's fine".
3. Add `?evidence=1` and ask them to tap the ring nearest the spot and read it out. **Pass**: they can say
   who the status would come from, that there is none, and how far upstream it is.
4. Ask: "Is there anything further up the river this doesn't look at?" **Pass**: they find the bars or the
   "trace stops" label.
5. Open `spot/bw-uke4100-08901/?evidence=1` and ask how it differs. **Pass**: more of it reports, said
   without going by colour.
6. Note their words verbatim. One "it's clean" at step 2 means the lead line is not doing its job.

## Local preview used for the screenshots

No build was run, so no Open-Meteo calls were made.

1. Copy `src/dipcast/site/*` and `src/dipcast/pages/fonts` into a scratch folder.
2. Put the live `data/spots-lite.json` and, for each spot, `data/spot/<id>.json`,
   `data/spot/<id>-trace.json` and `data/upstream/<id>.json` under it.
3. Add the cut ends from `trace.spot_trace_parts` to the copied trace files.
4. Add `<base href="/">` to the copied `index.html`. Built pages carry their own.
5. Serve the folder with `python3 -m http.server`.
6. Take the screenshots with headless Chrome over CDP, with the clock fixed an hour after the issue time.
