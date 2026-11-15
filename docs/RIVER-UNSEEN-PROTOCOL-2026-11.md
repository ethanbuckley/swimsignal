# RIVER-UNSEEN: statement, written before any archive sample is fetched

Written 15 November 2026 against main `6743baf2`. Project 1 of the
[ambition portfolio](https://github.com/ethanbuckley/swimsignal/pull/704) (`docs/AMBITION-PORTFOLIO-2026-11.md` on
that PR). This file fixes the rows, the candidate, the references, the metrics and what each outcome leads to.
**Nothing below the line "Staging result" existed when this was pushed, and no archive sample had been fetched.**
A change after that is an amendment: dated, with both versions kept.

Nothing on the site changes. No forecast, frozen file, active window or the 2027 primary evaluation is touched.

## The question

The river E. coli model was fitted on 2023-26 samples at 20 river bathing waters. The backtest bench (#700) has 60
held-out river rows at 2 sites, so "River candidates cannot be confirmed here". The Environment Agency's Water Quality
Archive holds river E. coli results at points that are not bathing waters, back to 2000. No model here has used them.

**Does a river model fitted only on bathing-water samples from 2023-26 order the samples at river points it never
saw, in 2012-22, and does its 8-in-10 range hold there?**

## What was known when this was written

- On 15 November two requests returned the archive's page cap of 2,500 rows, for 2019 and for 2024 (determinand 2348,
  sampling point type F6). From those two pages I printed counts by sampling point, region, area, purpose, material
  and month. I did not read the result column, and I deleted both files (`docs/ambition-portfolio/request_log.tsv`
  on #704).
- So: at least 2,500 rows a year; about 155 points a page, about 100 of them with 10 or more rows; 72% May to
  September; most rows planned monitoring or planned investigation; the pages lean to Devon, Cornwall, Morecambe Bay
  and East Anglia.
- No result value at any of these points has been read by this work, and none has been joined to rain, exposure or
  any model figure.
- On the bench's seen rows (development evidence): a log10 river model's 8-in-10 range held 79.3% of
  held-out-season samples with no site level, and its within-site Spearman correlation was 0.36 to 0.43
  (`docs/ambition-portfolio/river_bands_range.txt` on #704).

## Stage 1: fetch, count and place (this PR)

Stage 1 reads no result value. It settles whether the set can test the river model at all.

### The fetch

`scripts/river_unseen/fetch.py`. Environment Agency Water Quality Archive, Open Government Licence v3.0.

| What | Request | Sized before the run | Cap | Pace |
|---|---|---|---|---|
| E. coli, determinand 2348, sampling point type F6, calendar years 2012 to 2026 | `POST /data/observation`, CSV, 2,500 rows a page, one year a query | 30 to 135 requests, about 1 MB each (2,500 to 20,000 rows a year; the true count is not known) | 150 requests, 200 MB | 4 s |

- Wall time: at most 35 minutes at about 10 s an answer.
- A refusal (HTTP 401, 403 or 429) stops the run and is not retried. A 502, 503 or 504 is retried after 30 s and
  90 s, and each try counts against the cap.
- Order: 2022 back to 2012, then 2023 to 2026, so a stop costs the least useful years.
- Every request is in `docs/river-unseen/ledger.jsonl`. Raw pages go to `swimsignal-private/river-unseen/raw/`, not
  to git.
- Open-Meteo calls: none.

### Rows kept

- Material "RIVER / RUNNING SURFACE WATER".
- Sample taken in May to September.
- Sampling purpose one of: MS (statutory environmental monitoring), MP (environmental monitoring, GQA and RE), MU
  (monitoring, UK government policy), MN (monitoring, national agency policy), PI (planned investigation, local),
  PN (planned investigation, national).
- Dropped purposes: UI and UF (reactive, pollution incidents), SI and MI (follow-ups to a statutory failure), MA to
  MD (bathing-water abnormal situations and short-term pollution), and any other. Those samples are taken because
  of a bad result or an incident, which selects on the outcome.
- **Held-out rows:** 2012 to 2022. **Development rows:** 2023 to 2026 at the same points. Development rows are not
  part of any read.

### Points kept

A sampling point is kept when all of these hold. Each is decided from positions, names and counts, never a result.

1. **Count.** 30 or more kept held-out rows, in three or more seasons.
2. **On a river.** `transport.locate_pin` with `kind_hint="river"` and no river hint places it in river mode within
   50 m of a link of the river network (`pin.snap.dist_m`), with the site's settings.
3. **The right river.** Where the link it lands on has a name, that name's core (the name without "River", "Afon"
   or "The") appears in the sampling point's label, ignoring case. A point on an unnamed link is kept. This guards
   against a point by a confluence landing on the other river. The points it drops are listed, and a read reports
   them as a sensitivity set.
4. **Overflows upstream.** `transport.upstream_overflows`, with the site's settings, finds one or more monitored
   storm overflows.
5. **Not a bench site.** More than 500 m from every inland bathing water in `data/raw/bathing_waters_inland.json`.

Rule 4 is counted two ways, because the kill rule needs both: points that pass rules 1, 2, 3 and 5 with an overflow
upstream, and those without.

### Kill rule, stated before the fetch

Stop RIVER-UNSEEN as a test of the river model if either holds:

- fewer than 30 points pass all five rules; or
- of the kept held-out rows at points passing rules 1, 2, 3 and 5, more than half are at points with no monitored
  overflow upstream.

Then the rows are kept for the portfolio's rain-only question (ANYWATER) and this record says why.

### What stage 1 commits

- `docs/river-unseen/points.csv`: every sampling point with its label, position, counts of kept rows by span, and
  each rule's outcome. No result.
- `docs/river-unseen/manifest.json`: row counts by year, purpose and material, duplicate checks, the SHA-256 of the
  sealed sample table, and the fingerprints of the shared inputs before and after.
- The sealed sample table (`swimsignal-private/river-unseen/samples.parquet`) holds the results. Stage 1 writes it
  without printing, summarising or joining any result.

## Stage 2: the read (a later PR)

Stage 2 needs rain and exposure for every kept row. That is about 2,900 weighted Open-Meteo calls for the points
alone, more for the overflows' cells, or none with the ERA5-Land bulk download (#702), which waits on a Copernicus
account. Stage 2 does not start until one of those is settled, and any choice it must make that is not fixed here is
an amendment pushed before the join.

- **Candidate.** `river-range-v0`, frozen in `docs/river-unseen/river_range_v0.json` (SHA-256 `bb4d8c10…`), fitted
  by `scripts/river_unseen/freeze_candidate.py` on the bench's 943 seen river rows (`seen.parquet`, SHA-256
  `417648aa…`). A log10 model: rain in 48 and 24 hours, upstream exposure, season. No site level. Spread 0.456 log10.
  The likely reading is its median; the 8-in-10 range is the median times and divided by 3.8.
- **References.** Production's river chance as deployed (without soil moisture in years where none exists; said in
  the record); the month-of-year rate; "more than 10 mm in 48 hours".
- **Rain.** The same source for the candidate and every reference. If ERA5-Land is used where production was fitted
  on Open-Meteo's archive, the record says so and reports the #702 match check beside the result.
- **Primary metric.** Mean over points (15 rows or more) of the within-point Spearman correlation between the likely
  reading and the measured log10 count. **Pass:** the 95% interval, from 2,000 resamples of river-system seasons,
  lies wholly above 0.15.
- **Range check.** The share of held-out samples inside the 8-in-10 range. **Pass:** between 72% and 88%.
- **Reported, deciding nothing.** Brier over 900 against each reference. Seasons to 2016 and from 2017 apart (the
  archive rain most likely changes source at 2017). By purpose. By upstream catchment size. The rule 3 sensitivity
  set. Points with no overflow upstream.

### What each outcome leads to

- **Both pass.** A wording proposal for Ethan: a likely reading and range at river spots in season, on the lake
  range's pattern (#585), and a shadow log beside production for 2027. Nothing shows until he decides.
- **Order passes, range fails.** An order-only line is proposed ("higher or lower than usual here"). The spread is
  diagnosed by stream size.
- **Order fails.** The river estimate stays as it is. The record says the model did not carry to these points and
  shows which kinds of point it failed at. The rows stay as development data.

### Limits known now

- These are not swimming spots. Many are small streams above beaches, sampled to find sources of pollution. A pass
  supports the model at river points with overflows upstream. It does not show the same at a large lowland river
  unless such points are in the set; the read reports catchment size for that reason.
- Investigation points are placed where pollution is suspected. Levels may run higher than at a bathing water. The
  primary metric is order within a point, which a point's level does not move. The range check is exposed to it.
- Hindcasts on archive rain at lead 0, as every bench read. Skill at leads 1 to 4 is not measured.
- The spill model's labels start in 2024. Exposure for 2012-22 comes from that model run on older rain, as the
  bench's lake rows do.

---

## Staging result
