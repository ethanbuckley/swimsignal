# Arrival times against EA ammonium sondes: an exploratory check, stated before any join

Written 13 November 2026. **Exploratory.** It changes no transport setting, no issued forecast and no frozen file.
It is not the sonde signal test of 27 October ([SONDE-SIGNAL-TEST-2026-10.md](SONDE-SIGNAL-TEST-2026-10.md), #403).
That test asks whether a sonde reading improves the E. coli estimate. It stays unrun, with its gate as written. This
check does not run it, relabel it or reuse its name.

Sections 1 to 9 were committed and pushed before the first EA request. Section 10 was added and pushed before the
first readings request. Nothing above the results line changes after a reading is joined to a spill.

## 1. The question

The transport model moves spill water down a river at one speed, 0.2 m/s
(`config.RIVER_VELOCITY_MS`). That speed was fitted on E. coli samples.
[TRANSPORT-FIT-TEST-2026-10.md](TRANSPORT-FIT-TEST-2026-10.md) says it "should not be read as a measured speed".
The river-rises work times gauge rises. A gauge rise is a flood wave, which travels faster than the water itself.

Here: when an overflow with a timed spill start sits upstream of an EA ammonium sonde, how long after the start does
ammonium rise at the sonde? How does that compare with the model's travel time for the same path?

**The model's window.** For an overflow a distance d upstream, the model's travel time is `travel_h` from
`transport.upstream_overflows` (d / 0.2 m/s on a river path). `still_coming` says the water first reaches the point
at start + travel_h. `live_now_risk` counts the water as passing until end + travel_h. So the model's window at the
sonde is **[start + travel_h, end + travel_h]**. The check compares the measured rise time with the start of that
window, and reports how many rises begin before, inside and after it.

## 2. Limits, written before any request

- **EA requests: at most 100 in total**, retries included. One in flight, at least 1.5 s after the previous one ends.
  A 403, 429 or 5xx is retried once after 10 s and counts twice. Planned: 1 station listing, at most 90 readings
  requests, the rest spare.
- **Ledger:** every request is written to `docs/ARRIVAL-TIME-SONDE-CHECK-2026-11-ledger.jsonl` with its URL,
  parameters, status, bytes, start and end time (UTC).
- **No Open-Meteo call.** No rain is used.
- **Spill records:** only the EA start/stop files already built in the main checkout, 2024 and 2025, nine companies
  (`data/processed/ea_events_*.parquet`). The site's own live polls are not read, so no active window is touched.
- **Shared files are read-only.** The run uses a scratch `DIPCAST_ROOT` and `DIPCAST_STATE` holding links to the
  inputs. Their SHA-256 hashes are taken before and after.
- Readings are kept outside git. The ledger, the station table and the event table (times and lags, no raw series)
  are committed.

## 3. Sondes and where they sit

- **Source:** EA Hydrology API, `/hydrology/id/stations.json?observedProperty=ammonium`. OGL v3 (licence read
  27 October for the sonde signal test).
- **A sonde** is a station with a 15-minute ammonium measure, `<station>-amm-i-subdaily-mgL`
  (`scripts/sonde_signal_eval/sondes.parse_stations`).
- **Placed on the river network** by `transport.locate_pin` with the river named in its label, as the site places a
  temperature sensor. A sonde is **out** when it is not placed on a river, when it is on a tidal link (the tide
  reverses the flow), or when it is more than 250 m from the link it is placed on.
- **Overflows upstream** come from `transport.upstream_overflows` with the production settings: the same network
  trace, 60 km cap, distances and `travel_h` the site uses. Distance is along the river network, never a straight
  line.
- **Monitored overflow:** one with at least one event in the EA files. An overflow with no event in a year is either
  unmonitored or did not spill. The files cannot tell these apart.
- **Timing overflow:** a monitored overflow upstream whose path to the sonde is river only (no lake crossed), whose
  position is a high-confidence snap, and whose river distance is **0.5 km to 30 km**. Under 0.5 km the model's travel
  time is under 42 minutes, which is under three sonde readings. Over 30 km the model's travel time is over 41 hours
  and storms overlap.

**Recount of the scoping figure.** The scoping record counted 12 live ammonium stations within 5 km of a spot in a
straight line, 8 on becks around Windermere, on 25 October. The recount reports, from the listing of 13 November:
stations with an ammonium measure; those still open (no `dateClosed`); those within 5 km of a listed spot in a
straight line; and, the count that matters here, those that pass the placement rules with a timing overflow upstream
and a deployment that overlaps 2024 or 2025. "Live" on 25 October meant readings since 15 October. This recount uses
the station's open/closed dates instead, to spend no request on it, and says so beside the figure.

## 4. A rise, defined before any pair is looked at

Readings are 15-minute instantaneous values in mg/L, stamped in UTC.

- **A valid reading:** finite, from 0 to 100 mg/L, quality not "Suspect" or "Missing". Duplicate stamps keep the
  last. Readings sit on the 15-minute grid (slots).
- **Reference time t0:** a spill start (section 5).
- **Baseline:** the valid readings in [t0 − 30 h, t0 − 6 h). At least 48 of its 96 slots must be valid, else the event
  has "no baseline". b = their median. s = 1.4826 × their median absolute deviation. The window ends 6 h before the
  start so that a rise that begins before the recorded start does not lift the baseline. It spans 24 h so that a
  daily cycle below a treatment works is inside s.
- **Threshold:** θ = b + max(0.05 mg/L, 0.5 × b, 3 × s).
- **Rise onset:** the first slot τ in the search window with a reading above θ, where at least 3 of the 4 slots from
  τ to τ + 45 min are valid and above θ.
- **Search window:** [t0 − 6 h, t0 + H]. H is set by distance alone: **H = d / 0.05 m/s, at least 6 h, at most
  72 h.** 0.05 m/s is a quarter of the model's speed. A speed slower than that cannot be seen beyond 13 km, where H
  reaches 72 h.
- **Raised before:** an onset in [t0 − 6 h, t0). The event is counted and left out of timing.
- **Gap:** a run of 4 or more invalid slots (1 h) anywhere from t0 − 6 h to the onset, or to the end of the window
  when there is no onset. The event is counted and left out of timing, because the rise could sit in the gap.
- **No rise:** no onset, no gap.
- **Lag:** L = τ − t0. A reading stamped τ is an instant, so the true crossing lies in (τ − 15 min, τ]. Spill start
  stamps have their own resolution, which the files do not state.
- **Peak lag (secondary):** the time of the highest valid reading in [τ, τ + 24 h], less t0.

**Two other definitions, reported beside the main one and deciding nothing:** looser, θ = b + max(0.03, 0.25 × b,
2 × s); stricter, θ = b + max(0.10, 1.0 × b, 5 × s).

Why ammonium may not answer, stated now: rain that starts a spill also brings runoff and unmonitored sources. Storm
flow dilutes treated effluent, so below a works ammonium can fall in a storm. Sonde ammonium probes drift. Sections
6 and 7 are there to show whether a rise after a spill start is more than background.

## 5. Events

Everything here is per sonde. "Upstream" means every monitored overflow in the model's trace above the sonde, at any
distance, lake paths included.

- **Quiet rule.** A spill start at t0 is an event when no monitored overflow upstream was spilling at any time in
  [t0 − 48 h, t0). The overflow that starts is the **anchor**. Two overflows starting in the same minute: the nearer
  is the anchor.
- **Tier A, one source.** The anchor is a timing overflow, and no other monitored overflow upstream spills in
  [t0, t0 + H]. The anchor's own later spills are allowed. Lag L is set against the anchor's model travel time.
  Implied speed v = d / L.
- **Tier B, first of several.** Other monitored overflows upstream start in [t0, t0 + H]. If every one of them has a
  river-only path, the event's implied speed is the v that solves **min over the overflows of (start + d / v) =
  onset**: the speed at which the first water from any of them reaches the sonde at the measured onset. For one
  overflow this is d / L. Events with a lake-path member are counted and left out.
- **Overlapping spills** are therefore handled by exclusion (the 48 h quiet rule) and by tier. Tier A is the clean
  set. Tier B is secondary.
- **Sensitivity:** a 24 h quiet rule, reported, deciding nothing.
- **Deployment:** an event counts only when t0 − 30 h and t0 + H both fall inside the station's fetched readings.

## 6. The dry reference

A rise can come with no spill. For each sonde, **pseudo-starts** are the times 00:00, 06:00, 12:00 and 18:00 UTC on
which no monitored overflow upstream spilled in [t − 48 h, t + 72 h] and the sonde has a baseline. The same detection
runs on them with each H the sonde's Tier A events use. The share with a rise is the background rate.

**A sonde shows a signal** when its Tier A rise share less its background share has a 95% interval above zero
(bootstrap over ISO weeks, 2,000 draws, seed 0). Otherwise its lags are listed but not read as travel times.

## 7. What is reported

**Per sonde:** river, the timing overflows and their distances, and counts of Tier A events by outcome (rise, no
rise, raised before, gap, no baseline). Then, for rises:

- the lag: every value when there are under 5, else the median, the quartiles and a 95% interval for the median
  (bootstrap over events, 2,000 draws, seed 0);
- the model's travel time for the same overflow, and the ratio of the median lag to it;
- implied speed d / L, the same way;
- the share of rises that begin before, inside and after the model's window (section 1), with 15 minutes' grace at
  each end;
- peak lag, the two other rise definitions, the 24 h quiet rule and Tier B, each labelled secondary.

**Pooled, only if at least 3 sondes on at least 2 rivers show a signal with 5 or more Tier A rises each:** the median
implied speed with a 95% interval (bootstrap over sondes), and a Theil-Sen line of lag on distance. A slope near zero
means the rises do not depend on distance, which points to rain and not to travel.

**Not done:** no fit of a new speed, no E. coli value read, no score of the forecast.

## 8. What I expect, stated now

- Few clean events. Storms start many overflows at once, so Tier A will be common only on becks with one or two
  monitored overflows upstream.
- Where a signal shows, lags shorter than the model's. Water in a storm moves faster than 0.2 m/s, and an onset is
  the leading edge, which runs ahead of the bulk [inferred].
- Several sondes with no signal above background.

## 9. What follows, for each outcome

- **A measured speed, different from the model's:** at least 3 sondes on at least 2 rivers show a signal with 10 or
  more Tier A rises each, and the pooled interval for implied speed excludes 0.2 m/s. Next: a candidate speed test
  under its own protocol, with the candidate taken from this record and judged on what the speed is used for (the
  arrival and clearing times on the page, and the E. coli fit as a guardrail). Nothing changes until that test.
- **A signal, but the interval includes 0.2 m/s or the sondes are too few:** recorded as "consistent with, not
  measured". Next: grow the events from the EA's 2026 start/stop files when they are imported, under this protocol
  unchanged, and say how many events would narrow the interval.
- **No sonde shows a signal, or under 5 Tier A rises anywhere:** the record says why the sondes cannot answer (which
  rule removed the events) and which measurement could: paired monitors above and below an overflow (section 82, not
  yet published), a tracer study, or another sonde property.

Whatever the outcome, the transport settings stay as they are.

---
