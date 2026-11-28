# C1 at issue time: the 2027 shadow on English beaches

Protocol written 28 November 2026 and pushed before any row is logged (the logger writes nothing before 1 May 2027).
The register's next step for C1: "a 2027 shadow protocol with issue-time rain before 1 May 2027". Ethan said "Yes, the
protocol" on 28 November 2026.

## The question

C1 (`docs/COASTAL-C1-PROTOCOL-2026-11.md`, frozen `c1_frozen.v1.json`, SHA-256 `90b390ba…`) beat the same model without
rain on unseen 2012-21 English seasons, using ERA5-Land rain at each sample's time: a reanalysis available only days
later. **Does C1 keep its gain over C0 when its rain is what the build has at issue time, the forecast service's rain
for the 24 and 72 hours to midday, logged before the sample is taken?** A pass is the evidence needed before any
beach-card wording uses C1's figure. Nothing on the site changes from this protocol or its log.

## What is logged (`shadow_coastal_c1_v1`, `src/dipcast/coastal_c1_shadow.py`)

- **When.** May to September 2027 (C1's months). One row per English coastal bathing water per local day: the first
  build of the day at or after 06:00 Europe/London writes it, and no later build that day writes another. Every row
  has `issued_at`, the build's time, and the target day is the issue day.
- **Rain.** Hourly precipitation from the forecast cells the build caches (`rainfall.CACHE/forecast_<cell>.parquet`,
  Open-Meteo's forecast API with 31 past days): the site's own 0.1° cell, else the nearest of the eight around it
  (logged with its distance), fresh by the file's own fetch time (at most 30 hours old, logged as `rain_fetched_at`),
  summed over the 24 and 72 hours to 12:00 local on the target day, each window at least 90% covered. Part of each
  window can be forecast; that is the point of the test.
- **Last sample.** The site's latest statutory sample the build holds (`coastal.latest_samples`), if taken in 2027
  before `issued_at`: `x1 = log10(E. coli) − 1`, else `x2 = 1`, as C1.
- **Site rate.** C1's frozen table: `(k + m·p0) / (n + m)` with every fit year counted; a site not in the table gets
  p0.
- **Figures.** C1's over-500 chance (null when either rain window is not covered), C0's (always), and the month-and-site
  reference R. The rain and every input are logged with the figures, plus the frozen file's hash and the code version.
- **Fetching.** English beaches' cells join the build's existing directory fetch (`build_site.directory_air`) in May to
  September only, with their own budget of 20 cells a build, behind the same Open-Meteo spare-capacity check
  (`rainfall.spare_for`). If the day's ration is short, cells are not fetched and rows go without C1 (logged as such);
  nothing else on the site gives way. No new Worker or scheduler: the site's builds write it.

## How it will be judged (on or after 15 October 2027)

- **Rows.** The EA's 2027 statutory (MS) E. coli samples at English coastal bathing waters, 1 May to 30 September,
  each joined to the log row for its site and local day with `issued_at` before the sample time. A sample with no such
  row, or a row with no C1 figure, is counted as uncovered and reported; it is not scored.
- **Primary.** Brier score for over 500, C1 minus C0, on the covered rows. Interval: 95% percentile, 2,000 bootstrap
  resamples of whole ISO weeks (a storm reaches many beaches at once; one season cannot be resampled by season), seed
  20270501.
- **Pass.** The interval lies wholly below 0.
- **Also reported, deciding nothing:** the within-beach rank correlation of C1 and of C0 with the measured count;
  coverage (covered samples over all samples, by month); C1 against R; the logged forecast rain against ERA5-Land for
  the same windows (one CDS download after the season), to separate a rain-source loss from a model loss.

## What each outcome leads to

| Outcome | What follows |
|---|---|
| Pass | Issue-time C1 is supported on the coast. Next: a wording record for English beach cards in 2028 (an order word, as at rivers and lakes; never a chance: C1's skill over the base rate was 2.9%), under docs/DESIGN.md |
| Fail | Beach cards keep counts only. The record says whether the loss is the rain (forecast against ERA5-Land) or the model. A next candidate (radar for the hours already past, or C1 refitted on forecast rain) gets its own protocol |
| Too few covered rows (under 2,000) | The season could not judge it; the record says so and the log continues into 2028 unchanged |

## Fixed now and not changed later

C1, C0 and R as frozen; the windows ending 12:00; the one-row-a-day rule; the 30-hour freshness and 90% coverage
rules; the join; the metric, interval, seed and pass rule. A change to any of these after 1 May 2027 starts a new
versioned table and protocol; this one is read as written.

## Known limits

- A sample's time is not known in advance; the windows end at 12:00, as the Northern Irish and Irish transfers assumed.
- English beaches whose cell is never fetched in the season give uncovered rows; coverage is reported.
- The live site's English beach cards already show today's rain from a different source (the click-anywhere squares,
  48 hours). This log is separate and does not change them.
