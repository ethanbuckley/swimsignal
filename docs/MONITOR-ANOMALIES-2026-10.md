# Monitor anomaly flags: a prototype, and how it did on saved polls

Written 26 October 2026. A prototype. Nothing in the build, the site, the forecast or the scorer reads it. No
level, live-feed code path or test window (A8, Option B, live-status shadow) is changed.

Code: `src/dipcast/monitor_anomalies.py` (the rules), `scripts/monitor_anomalies.py` (the offline report and the
failures put in by hand), `tests/test_monitor_anomalies.py`.

Every flag has the overflow (empty for a flag on a whole feed), its company, the rule, the values that set it off
(`evidence`, JSON), when the rule first held (`first_seen`, UTC) and the severity `review`. No rule changes or drops
an input row. A flag is a note for a person, never a correction.

"Read" below means I opened the file or ran the code and saw the value. "Inferred" means a reasonable conclusion I
did not check against a source.

## The data

All read-only copies in a scratch folder. Nothing was fetched.

| File | Version (sha256, first 12) | What it holds |
|---|---|---|
| live_history.parquet | 08a71197f5a8 | 89,825 rows, polls from 11 Sep 20:18 to 25 Oct 14:07 UTC |
| poll_log.parquet | df9411d37301 | 392 polls x 9 companies, 16 Sep 16:42 to 25 Oct 14:07 UTC |
| live_coverage.parquet | 4cded9b09430 | 567,996 overflow-days |
| dipcast.duckdb (forecast log) | 092893b30b9e | forecasts issued 12 Sep to 25 Oct for 1,252 overflows, with lead-0 rain |
| live_latest.parquet | 3d744aa9afdf | the snapshot of 24 Oct 2026 09:41 UTC, 14,202 rows |
| ea_events_<company>.parquet (9 files) | listed in the script's summary | EA start/stop events 2024-2025, 2,952,154 rows |

The first four came from the `state` release as another session downloaded it on 25 Oct (read: the history file is
byte-identical to one in a folder that session named `stateRel`). The snapshot is from a download of 24 Oct 23:10.
The EA files are `data/processed/ea_events_*.parquet` of 16 Oct.

Window evaluated: 17 Sep to 25 Oct 2026 (388 polls, 39 coverage days). Reference year for spill behaviour: 2025.

## 1. What the existing rules catch

| Rule (where) | Catches |
|---|---|
| Feed down, `FEED_DOWN` = -3 (`ingest/live.py` carry_forward; build_health warning) | A company that returns no rows. Its last snapshot is kept, marked feed down. |
| Short read (`is_short`, `SHORT_READ_SHARE` 0.9 of the median of 10 polls; build_health warning) | A read with too few rows. Re-read up to 3 times; missing overflows carried as feed down. |
| Torn read (`arcgis.fetch_all`) | A multi-page read where the layer changed between pages. |
| Repeated ids (`one_row_per_site`, `overflows.duplicate_site_ids`; build_health warning) | An id listed twice. The most recently updated row is kept, and the build warns. |
| Stale feed (`FEED_CURRENT_H` 6 h, `feed_age_hours`; `data_states`, coverage) | A company whose freshest record stamp is over 6 h old, or missing. Its statuses read as stale, not "not discharging". |
| Frozen record (`frozen_records`; quality page list) | One record whose stamp stopped in a company that stamps every record. |
| Stamp-on-change companies (`stamps_every_record`, `feed_on_change`) | Northumbrian and Southern: an old stamp there is a quiet overflow, and the page says a quiet feed cannot be told from a stopped one. |
| Field names in camelCase (`hub_names`) | South West Water's spelling. |
| Event end before start (`live_status.poll_events`; `index.html` `!(a > b)`) | Clipped or ignored where read. Not reported. |
| State release age (`.github/workflows/site.yml`) | State files over a set age in the release. |
| Offline checks by hand: `check_upgraded_overflows.py`, `compare_event_sources.py`, `live_status_shadow_check.py`, `dry_weather.py` | Ilkley's quiet upgraded overflows; two event records of one year; the shadow forecast; dry-weather spills from EA records. None runs on the live feeds. |

What none of them looks at (read from the code):
- the content of a record's times (future, implausibly old);
- whether a record's status agrees with its own event times;
- how long a spill has been running;
- whether a monitor that answers on time is reporting what its neighbours report;
- a feed that answers and is re-stamped, but whose statuses stop changing;
- the share of statuses that are readable (an unreadable status becomes -1, offline: `fetch_live`, `.fillna(-1)`);
- a refresh that slows but stays under 6 h;
- ids that change while the row count holds.

## 2. Candidate gaps: kept and dropped

Kept: the nine rules in section 3.

Dropped, as not real gaps or not workable:
- **Duplicate ids with conflicting status.** Already counted and warned in build_health, and one row kept. A
  synthetic copy with three repeated Anglian ids (the second row discharging) set off the existing warning for all
  three; no new rule is needed.
- **Duplicate positions with conflicting status.** In the 24 Oct snapshot 963 positions carry more than one id, and
  64 of those disagree on status. A hand look at 24 of the 64 (all South West Water) found different named CSOs
  placed at one shared point (Falmouth's Killigrew St, High St, Webber St and Market St CSOs; 14 Plymouth CSOs at
  one point on Stonehouse Creek). Different overflows can disagree. Noise, not a fault.
- **Offline for a long time.** A monitor at -1 already shows as offline (data_states). Nothing to add.
- **"Not discharging" for longer than its own history.** Most overflows are quiet for months; a long quiet spell
  on its own says nothing. quiet_monitor asks the useful form of the question (quiet while its neighbours spilled).
- **Company freeze judged against other companies.** The first form (no change in 24 h while other companies had
  many) fired on 73 hours for Wessex, 15 for Southern, 14 for South West Water and 4 for Thames in the window: rain
is regional, so
  other companies are no guide. Replaced by the rain form (company_freeze).
- **Field-set change.** The saved data keep no field list, so it cannot be evaluated. Its effects are covered
  elsewhere: a missing or renamed Status reads as all offline (known_share_drop); a missing LastUpdated reads as a
  stale feed (existing); missing positions drop rows, which reads as a short read or feed down (existing).

## 3. The rules, and how each did

False alarms are counted over the window on real data. A real-data flag is not proof of a fault; the hand
inspections say what each one looked like.

### future_time: a record time later than the poll that read it
Gap: a clock or time zone slip. The stale test sees a negative age as current, so a stamp an hour ahead passes.
Rule: any record time more than 15 minutes after its poll. Rows carried through an outage are left out.
Real data: 4 records in 86,351 history rows; 0 in the 24 Oct snapshot. All four are United Utilities status
starts, 22 to 47 minutes after the poll that read them (UUP01290 on 18 Sep; UUP00365 and UUP00044 on 22 Oct;
UUP00843 on 23 Oct). Read: later polls kept the same times (UUP00365 and UUP00044 to the second, without the
milliseconds), so the feed wrote a status start ahead of the moment it was read. Conclusion: real small faults in
UU's times, not false alarms, and not worth anyone's time one by one.
Synthetic: Wessex's times moved 1 h ahead set it off on 1,418 records. No existing check fired.

### time_format: most of a company's times before 2015 or a day ahead
Gap: a unit or format change (seconds read as milliseconds gives 1970).
Rule: half or more of a company's records with such a time.
Real data: 0 flags. 12 records in the snapshot carry placeholder status starts (8 South West Water at 1 Jan 2000;
4 Yorkshire Water from 2006 to 2013), too few to fire. Read in the snapshot.
Synthetic: Severn Trent's times as seconds-for-milliseconds set off time_format, and long_run on the 10 overflows
that were discharging (their start became 1970). The existing stale test also fired (the stamps became 1970), so the
site would already show the feed as stale. The new flag names the cause.

### record_contradiction: status and event times disagree
Gap: nothing reports these. Two existing readers clip or ignore an end before a start.
Kinds and counts (24 Oct snapshot; distinct overflows over the window in brackets):
- `event_start_after_end`: 4 United Utilities (21).
- `stopped_with_open_event`, status 0 since after the event started, but no event end: 28 United Utilities (87;
  1 Thames).
- `stopped_before_event_end`, status 0 since more than an hour before the event ended: 33 Anglian, 1 Severn Trent
  (46 Anglian, 3 Severn Trent). Read: Anglian's status starts are Nov-Dec 2025 while their events are Feb-Mar 2026.
- `discharging_with_closed_event`: 0.
Hand look (all 66 in the snapshot): each is a steady quirk of one company's feed, not a monitor fault.
One has an effect. `transport._counted` counts a finished spill only from its `latest_event_end` (read in the code).
In the 24 Oct snapshot, 5 UU spills that stopped 10 to 19 hours before the poll had no event end (UUP02121,
UUP02065, UUP01286, UUP00863, UUP01571; read). Inferred, not measured: the right-now risk does not count them as
recent spills. In the whole history, 76 of 184 such events stopped on a later local day than they started; inferred: the
observed spill-days (`forecast_log.observed_spill_days`, which fills a missing end with the start) miss that day.

### long_run: discharging far longer than it ever has
Gap: a monitor stuck on "discharging" while its record still updates passes every freshness check and counts as a
running spill.
Rule: status 1 for longer than a week, and longer than twice the overflow's longest event in the EA's 2024-2025
records (the week alone where it has none). `first_seen` is when the run passed that limit.
Real data: 7 distinct overflows in the window (8 flags). Hand look, from the history and the 2025 annual return:
- YWS00425, Brecksfield No 2 CSO: discharging since 2 Sep 09:00:00, 53 days; longest on record 12.8 h; went offline
  at least twice and came back with the same start; 55% monitor uptime in 2025. Looks stuck.
- UUP00274, Bolton Road/Astley Street CSO: 17 days; longest on record 0.7 h over 32 events; offline twice, back
  with the same start. Looks stuck.
- YWS02029, Waingate CSO: 12 days; no EA events; 0 spills a year in the 2025 return; offline twice, back with the
  same start. Looks stuck.
- SWS00007, Albion Groyne Brighton CEO: 27 days; no EA events; 0.13 spills a year; record unchanged since 28 Sep.
  Looks stuck (Southern stamps on change, so the old stamp proves nothing either way).
- SWS00803, Spot Lane Bearsted CEO: 12 days; longest 12.25 h; record unchanged since 13 Oct. Unclear.
- YWS02298 (not in the annual returns): 10.8 days to 17 Oct, then gone from the 24 Oct snapshot. Unclear.
- SWS00628, Brewhurst Mill Loxwood CEO: 9.4 days; 243 events on record, longest 81.5 h. Could be a real long spill
  in a wet October. I count it as a probable false alarm.
So: 4 that look stuck, 2 unclear, 1 probable false alarm. None is caught by an existing rule (read: none of the
247 record-level flags of any rule is a frozen record or in a stale feed in the 24 Oct snapshot).
Synthetic: UUP01150 (longest 0.7 h) set to 10 days discharging was flagged. A real long spill, UUP01780 at 12 days
with a 672 h event on record, was not, and set off no other rule.

### quiet_monitor: no spill on days most of its neighbours spilled
Gap: a monitor that reads "not discharging" through storms while its record updates passes every check.
Rule: neighbours are overflows within 5 km. A neighbour storm day for an overflow is one where at least 3, and at
least half, of its neighbours with a known status spilled. Known days come from the coverage file (a live, current
reading that day); spill-days from the history, as the scorer's labels are made. Each overflow's rate on its storm
days comes from the EA's 2025 events, with the same rule (half a spill added over one day). Flag when it spilled on
none of at least 4 storm days, and the chance of that at its 2025 rate is 1% or less. Storms span days, so the chance
is a ranking, not a test.
Real data: 11,512 live storm site-days; 12 flags. Hand look, from the snapshot's latest event and the 2025 return:
- No event at all in the window, last event months back, 36 to 103 spills a year in 2025, monitor uptime 99-100%:
  UUP00625 Deanscales PS (last Nov 2025), UUP00814 Golf Road PS (Apr 2026), SBB00980 Praze an Beeble STW (May 2026),
  SVT00050 Alkborough STW (Aug 2026), UUP01846 Stanwix and Stainton CSO (Jun 2026), YWS00034 Howden STW (no event
  in its live record at all), WXW00505, WXW01014, WXW01078, WXW00490 (Feb-Mar 2026). 10 worth a look. The data
  cannot tell a broken monitor from an upgrade (Ilkley's six, PR #298, are the known case of the second).
- Spilled in the window, just not on storm days: UUP00404 (25 Sep) and YWS00431 (17 Sep). The monitors report.
  2 false alarms.
Ilkley's Middleton CSO (YWS00176) was not flagged: too few storm days in the window (inferred from the count of
flags; not traced).
Synthetic: UUP00623, the overflow with the most storm-day spills in the window, with its spills taken out, was
flagged. No existing check fired.

### company_freeze: no status changes on a wet day
Gap: a feed whose export re-stamps every record while its statuses stop. Seven companies stamped every record in
the 24 Oct snapshot (read: `stamps_every_record`), with feed ages under an hour in the poll log, so their stamps
say the export ran, not that a monitor was read (inferred).
Rule: a company and local day with 5 mm or more of lead-0 forecast rain at half or more of its logged overflows, and
fewer than 5 status changes (status starts and event times). Dry days are not judged.
Real data: 54 wet company-days; 0 flags. The fewest changes on a wet day were 41 (Wessex, 7 Oct), 44 (Thames, 7 Oct)
and 52 (Thames, 20 Oct).
Caveat: the rain is the forecast log's, which covers only overflows upstream of spots: a median of 14 overflows a day
for Northumbrian, 108 to 251 for the others.
Synthetic: Southern's changes removed on its wettest day (7 Oct) were flagged. No existing check fired.

### known_share_drop: the share of readable statuses falls
Gap: a renamed or recoded Status field turns every monitor of a company into -1. The site says "offline" honestly,
but no warning says why.
Rule: share of known statuses 0.10 or more below its median over the 10 polls before.
Real data: 3,490 company-polls with rows; 0 flags. The largest fall was 0.033 (Thames). Known shares ranged from
0.914 (Thames) to 0.999 (Severn Trent, Southern).
Synthetic: Thames all read as -1 was flagged. No existing check fired.

### cadence_change: a slower refresh short of stale
Gap: a feed that goes from minutes to, say, 4 h still counts as live. FEED_CURRENT_H sees it only past 6 h.
Rule: for companies that stamp every record, the median feed age over the last 5 polls above 1 h and above 4 times
its median before. Northumbrian and Southern are left out: their age is the time since any change.
Real data: 2,119 polls of the seven every-record companies with a feed age; 0 flags. The largest recent median was
0.56 h (Yorkshire). In an earlier run over all polls, the same rule on Northumbrian and Southern fired 29 and 42 times,
which is why they are left out.
Synthetic: not put in by hand in the script; the unit test covers it.

### id_turnover: ids change, count holds
Gap: a new id scheme leaves the count unchanged, so no short read; every old id reads as "not in the live feed".
Rule: 5% or more of a company's ids new, or gone while the count held at 90% or more.
Real data: 38 day-pairs x 9 companies from the coverage file; 0 flags. No company changed more than 2% of its ids from
one day to the next.
Synthetic: Wessex's ids renamed was flagged. The existing checks fired only on the 9 Wessex records already frozen in
the clean copy, now under new ids.

## 4. Failures put in by hand

On copies of the 24 Oct snapshot, its poll log, storm-day table and change times. Each line is what fires on the
copy and not on the clean copy.

| Failure | Existing checks | New flags |
|---|---|---|
| One UU record's stamp 3 days old | frozen_record | none |
| Thames' Status recoded (all -1) | none | known_share_drop |
| 3 Anglian ids repeated, second row discharging | duplicate_id x3 | none |
| Wessex's times 1 h ahead | none | future_time x1,418 |
| Severn Trent's times in seconds read as ms | feed_stale | time_format; long_run x10 |
| Southern returns no rows | feed_down | none |
| Wessex's ids renamed | the 9 already-frozen records, under new ids | id_turnover |
| UUP01150 stuck discharging 10 days | none | long_run |
| UUP01780 real long spill, 12 days (672 h on record) | none | **none** (as wanted) |
| UUP00623 reads 0 through every storm | none | quiet_monitor |
| Southern frozen and re-stamped on 7 Oct | none | company_freeze |

## 5. Decisions for Ethan

None of these is wired in. The data-quality page has three lists (two positions, no name or water, records without a
current time). My recommendation, for you to decide:

1. **Add long_run to the quality page** as "Overflows shown discharging for far longer than they ever have". 7 in
   the window, 4 of which look stuck. A stuck "discharging" makes the right-now risk higher than it should be, so it
   matters to swimmers. Not recommended: changing any level from it.
2. **Add quiet_monitor to the quality page**, worded as a question to the company ("no spill recorded on the days its
   neighbours spilled"), not as a fault. 12 in the window, 10 worth a look. It cannot tell an upgrade from a broken
   monitor, so the wording must not say broken.
3. **Put record_contradiction on the page, or only tell United Utilities and Anglian.** 66 records, all steady
   company quirks. A list on the page may read as noise. Separately: the UU spills with no event end are not counted
   as recent spills (inferred from the code, effect not measured). Whether to fill the end from the status start is
   a model change and a decision of its own.
4. **Add known_share_drop, company_freeze, future_time/time_format and id_turnover to build_health's warnings**, not
   to the page: they are about whole feeds, had 0 false alarms in the window (future_time had 4 small real ones),
   and someone needs to see them on the day.
5. **cadence_change: probably not worth wiring in.** It sees only a slowdown between 1 and 6 h, and none happened.

## 6. Limits

- One window of 39 days in autumn. Rare failures (format change, id scheme change, frozen export) did not happen in
  it, so their rules are tested only on failures put in by hand.
- quiet_monitor's reference is 2025; an overflow fixed since then is flagged as quiet. EA 2026 records were not used.
- company_freeze uses forecast rain, not observed rain, and only for overflows near spots.
- long_run's reference covers 2024-2025 EA records: 90% of live ids are in them (read: 12,774 of 14,202).
- The history keeps one row per distinct state, stamped with the last poll that saw it, so a flag's first poll can be
  later than when the condition began. long_run and quiet_monitor give the time the condition held instead.

## How to rerun

```
uv run python scripts/monitor_anomalies.py --state DIR --latest live_latest.parquet \
    --ea-events data/processed --start 2026-09-17 --end 2026-10-25 --out PREFIX --synthetic
```

DIR holds live_history.parquet, poll_log.parquet, live_coverage.parquet and dipcast.duckdb from the `state` release.
It takes about a minute and writes only PREFIX-flags.csv and PREFIX-summary.json.

Contains Environment Agency data (OGL v3.0) and storm overflow status from the English water companies via the
National Storm Overflow Hub (CC BY 4.0).

## 7. Decisions, 26 October 2026

Ethan adopted the recommendations of 26 October ("Adopt all the recommendations as my decisions"). Nothing is wired
in by this PR; each item below is a separate follow-up PR.
- **long_run on the data-quality page:** yes, now. Four monitors look stuck on "discharging".
- **quiet_monitor:** held until a second month of saved polls confirms its flags; it cannot tell a broken monitor from
  an upgraded overflow. When it goes on the page, it is worded as a question to the company, not a fault.
- **Build warnings only (not the page):** company_freeze, known_share_drop, future_time, time_format and id_turnover.
  They had 0 real flags apart from future_time's four, so they cost nothing.
- **record_contradiction:** not on the public page; 158 records is too noisy. A note to United Utilities and Anglian
  Water later (outreach, not done here).
- **cadence_change:** not wired in.
- **United Utilities' missing event ends:** decided separately, in PR #384 (do not fix now; measure again).
