# ANYWATER-IE: England's frozen coastal model on the Republic of Ireland's samples

Statement written 27 November 2026, before any Irish sample is joined to rain or to any model figure. Rank 3 of the
[forecast map](FORECAST-MAP-2026-11.md): the same transfer test as [ANYWATER-UK](ANYWATER-UK-STATEMENT-2026-11.md),
on the EPA's samples. Ethan chose to start it on 27 November 2026.

Nothing on the site changes from this statement. No frozen file, issued prediction, active window or the 2027
primary evaluation is touched.

## Gate

C1's own 2012 to 2021 read was "supported on unseen seasons" (`docs/COASTAL-C1-PROTOCOL-2026-11.md`), and
ANYWATER-UK passed. Both are met. The score script still checks C1's verdict and the frozen file's hash, and refuses
if either differs.

## What was known when this was written

- The EPA's samples by water, 2014 to 2026, as committed in `data/research/sample_history_ireland.v1.json` (CC BY
  4.0, read 13 November 2026). Its page shows each sample, so counts and dates are known. Counted for this
  statement, from that file and nothing else: 223 coast and estuary waters, 24,530 in-season samples, 210 waters
  with 20 or more, 535 results over 500.
- No Irish sample time has been joined to rain. The rain for Ireland west of 8.3° W was not on disk until this
  statement's download (below).
- C1 and C0 frozen on English samples only (`data/research/coastal/c1_frozen.v1.json`, SHA-256 `90b390ba…`).
  No Irish row played any part in fitting or choosing them.

## Rows

- **Samples:** the committed sample history's in-season rows (`in`), E. coli with its qualifier. No new sample
  request. A water's kind is the file's (`ireland.water_kind`): coast and estuary only for the pass rule.
- **Time:** the EPA gives a date and no time. A sample counts as taken at **12:00 Irish time** that day, the rule
  ANYWATER-UK's amendment 1 set for Northern Ireland.
- May to September only. A water needs 20 or more rows to count.
- **Positions:** the EPA's list of waters (one request to `data.epa.ie/bw/api/v1/locations`), Irish Grid easting
  and northing converted by `ireland.position`.
- **Rain:** ERA5-Land hourly total precipitation from the Copernicus CDS, a new download over Ireland only (55.5 N,
  10.7 W, 51.3 S, 5.9 E), May to September 2014 to 2026, converted by `scripts/era5land/to_cells.py` with C1's cell
  rule (nearest point with data within 3 steps, 0.1 mm). The whole island comes from this one download, so the
  border does not split sources. Window W1 (24 and 72 hours), coverage 90% or more.

## The figures each row gets

As ANYWATER-UK: each water is new to the frozen models, so its site rate is the pooled p0. C1 is the frozen
over-500 chance; C0 the same with no rain; Month the frozen R.

## Metric and pass rule

**Primary:** the mean over waters of the within-water Spearman correlation between C1's chance and the measured
E. coli count ("<" ranks below every count, ">" above; ties take the mean rank). Interval: 95% percentile, 2,000
bootstrap resamples drawing whole waters and whole seasons independently, **seed 20261127**.

**Pass:** the interval lies wholly above **0.10** (ANYWATER-UK's bar).

**Reported, deciding nothing:** C1 minus C0 and C1 minus month with the same intervals; the Brier score for over 500
for C1, C0 and month; how many results were over 500; seasons 2014 to 2021 and 2022 to 2026 apart; the inland
waters (lakes and the one river, line 900) scored the same way, since C1 was never built for them.

## What each outcome leads to

| Outcome | What follows |
|---|---|
| Pass | The past-samples-by-rain line goes on Irish coast and estuary cards, labelled as tested this way |
| Fail | The past-samples-by-rain line still goes on (a count of past samples, not a claim), with no tested label |

Inland Irish waters get the line with no tested label whatever the inland figure says: it was not the test.

## Limits known now

- Sample times are assumed, not read.
- A pass shows rain orders days within a beach in another country. It does not show a level or a chance there.
- No today's-rain line for Ireland: the site's rain squares are made for England's tap-anywhere map and none
  falls on an Irish beach.

## How the rain was converted, 27 November 2026, before the score

The download is May to September only, and `to_cells.py` converted only years that start in January. It gained
`--first-month` (default 1, so earlier conversions are unchanged; test in `tests/test_era5land.py`). With 5, each
year runs from 1 May 00:00 UTC, and its first hour is unknown because April is not on disk. The rain rule is the
same. All 65 months downloaded; 158 cells (73 with their own data, 85 from the nearest point with data within 3
steps), 3,672 hours a year, no step below −0.05 mm.

---

## Result, 27 November 2026: pass

Scored once at 10:30 UTC by `scripts/coastal_c1/anywater_ie.py score`; figures in `docs/coastal-c1/anywater_ie.json`.
One EPA request (the list of waters, all 243 with a position). Every rain window covered.

**Rows.** 24,413 samples at 210 coast and estuary waters with 20 or more, 532 over 500. All took the 12:00 rule.

| Mean within-water rho with the measured count | Coast and estuary, 2014 to 2026 |
|---|---|
| **C1 (frozen, with rain)** | **0.320 (0.274 to 0.356)** |
| C0 (no rain) | 0.237 (0.194 to 0.266) |
| Month alone | 0.214 (0.175 to 0.259) |
| C1 minus C0 | +0.083 (+0.057 to +0.111) |
| C1 minus month | +0.105 (+0.067 to +0.130) |

**Pass:** the interval for C1 lies wholly above 0.10. Rain adds to the order within a beach, with an interval above
zero.

**Reported, deciding nothing.** Brier for over 500: C1 0.02076, C0 0.02111, month 0.02129. Seasons 2014 to 2021: C1
0.341 (0.284 to 0.394), rain +0.094. Seasons 2022 to 2026: C1 0.281 (0.207 to 0.330), rain +0.085. Inland waters
(18 lakes and the river, 1,331 samples): C1 0.205 (0.058 to 0.331), rain +0.119 (+0.023 to +0.237). C1 was not
built for them, and this was not the test.

**What follows (the statement's table):** the past-samples-by-rain line goes on Irish coast and estuary cards,
labelled as tested this way. It is not a chance or a level.

**One change from the table.** Inland Irish waters do not get the line yet. The line counts results over 500, and an
inland water's line is 900 in the sample history (`lines` in `sample_history_ireland.v1.json`), so the same words would mislead there. A lake
version needs its own threshold first.
