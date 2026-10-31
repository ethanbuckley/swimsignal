# Issued-forecast history and "since the last update" (31 Oct 2026)

A draft. The comparison on a spot's page shows only with `?why=1`, as the inputs sentence of PR #462 does. The
history itself is kept by every build that forecasts.

Code: `src/dipcast/issue_history.py` (writer and reader), `scripts/issue_records.cjs` (the records, by the page's
own rules), `src/dipcast/site/since.js` (section "since the last update"), one step at the end of
`scripts/build_site.py` `build()`, and the state upload in `.github/workflows/site.yml`. Tests:
`tests/test_issue_history.py`, `tests/site_since_last.test.cjs`.

## The user task

"What changed since the last update?", on any spot's page, for anyone, with no saved spot and no earlier visit.

## What existed before, and what this adds

| Already there | What it holds | Why it is not enough here |
| --- | --- | --- |
| The forecast log (`forecast_log.py`, DuckDB `forecast_points`, `forecast_overflows`) | Every issue's risk per point and day, `now_risk`, `rain_48h`, version; each overflow's spill chance, rain and travel time | Keyed by point, not spot. No level as the page shows it, no what-set-it, no live counts or coverage, no rating, sample, algae or official advice. It is built for scoring, and the page never reads it. |
| `build_runs` | Each build: spots forecast, feeds down, whether it failed | Says that a build ran, not what a spot showed |
| Issue ids (`printed.js`, `issueId`) | `<commit>-<UTC minute>`, printed on decision records | An id with no stored record behind it |
| The since-you-looked note (#462) | One record per saved spot, in one browser | Only for saved spots and returning visitors |

This adds one store keyed by spot and issue id, holding what the page showed. It reuses the #462 record shape and
the printed issue id. Nothing in the forecast log, the model files, the 2027 evaluation tables or the research
windows changes.

## The record

`scripts/issue_records.cjs` runs since.js `seenRecord` on the build's own `spots-lite.json`, on the issue's UK day.
Because it uses the page's rules, the record cannot drift from what the page showed. Per spot:

- **Each day:** the level and what set it, the sewage spill risk (0 to 100), rain here in the 48 hours to midday,
  the overflows expected to spill, and the share of the model's weight here with missing rain data.
- **Right now:** level, spill risk and clearing time; overflows reported discharging; spills ended in the last
  48 hours; whether a feed was down or late.
- **Coverage:** how many overflows upstream gave a live status, of how many (`reporting`, `upstream`).
- **The water:** the rating, the latest sample time, the latest algae check, and the official advice in its
  compact words.
- **The model stamp,** without its code part.

Stored as one row per spot per issue: `issue_id`, `issued_at`, `commit`, `source` (always `issued`), `spot`,
`record` (JSON). Rows go in a Parquet file per UTC month, `state/issued-2026-10.parquet`.

## Kept as issued, never rewritten, never reconstructed

- **Rows are only added.** An issue id already kept is left alone on an identical rerun and refused if any record
  differs (`HistoryError`). The file is written to a temporary name and moved into place.
- **Reconstructions are refused.** An issue time more than 6 hours before the clock is refused as a
  reconstruction (`MAX_ISSUE_AGE`). A forecast rebuilt later for a past time would need its own store and its own
  label; none exists, and this one will not take it.
- **Only builds that forecast keep a record.** A rebuild from cached results (`build(refresh=False)`) publishes the
  comparison but keeps nothing.

## The comparison

The build reads the last issue kept before this one, then writes `data/since-last.json`: this issue's id and time,
the previous issue's id and time, and its 109 records. Only after that does it keep this issue. The page builds its
own record from the forecast on screen and compares day by day (`lastParts`), using the same fact functions as #462:

- **Reported or forecast:** overflows reported discharging or stopped; a new sample, algae check or rating; an
  official notice; the rain forecast; the overflows expected to spill that day and the day before.
- **With time:** right now as modelled; a day turning into today.
- **In what SwimSignal knows, not necessarily the water:** how many overflows gave a live status (coverage); a
  feed down or back; rain data missing or filled; a new spill model, calibration or E. coli model.
- **When nothing kept explains it,** it says so: "No other input kept here changed by enough to show", with the
  spill risk then and now. A move of 5 points or less across a level line is called small.

Nothing says an input caused the change.

## Missed builds, failed builds and old records

- **A failed build** keeps nothing.
- **"Previous" is the issue the live site shows while the build runs** (read from its `data/spots-lite.json`, past
  the CDN's ten-minute copy), not merely the last one kept. Added 31 Oct 2026 when #467 was integrated.
- **Builds that did not run** (GitHub's schedule is irregular) show as the gap, which is said in words: "Since the
  update issued Fri 00:41, 52 min before this one". Nothing guesses why there was a gap.
- **A previous issue over 24 hours old** is not compared with: "No earlier update within a day to compare with."
- **No history yet:** "No earlier update on record to compare with yet."
- **A spot new since the last issue:** "this spot was not in that update, so there is nothing to compare."
- **A record missing an input** (an older shape, or a value the build did not have): that input is not compared.
- **Pages and files that do not match:** a page from an older issue than the file says nothing. A file from a
  different issue than the page is ignored.
- **A build that kept its record but then failed to deploy** (a later workflow step, or the deploy job): its issue
  stays in the history as issued, but the next build compares with the issue the site was still showing, so a
  visitor is never told what changed since an update they could not have read.
- **The live issue is not in the history** (the first build after this shipped, or a lost month's file): no
  comparison, "The update shown before this one is not on record, so there is nothing to compare with."
- **The live site could not be read:** the build falls back to the last issue kept, and its health entry says
  `previous_checked: "unverified"` (otherwise `"live"`).
- **A month change:** the reader looks in last month's file too (tested).
- **A cold Actions cache:** the monthly files come back from the rolling state release, uploaded with the other
  state files (`site.yml`). The release is refreshed only when over 12 hours old, so a cold start can lose up to
  about 12 hours of issues; the next build then finds its live issue "not kept" and says so, rather than compare
  with an older one.

## Retention and storage

Measured by replaying 17 real issues (29 Oct 18:57 to 30 Oct 17:49 UTC) through `append()`:

| | Size |
| --- | --- |
| One issue, 109 spots, in the monthly Parquet (zstd) | about 2.9 KB |
| A day at 48 builds | about 140 KB |
| A month | about 4.2 MB |
| A year | about 50 MB, in 12 files |
| `data/since-last.json`, published each build | about 92 KB raw (one issue's records); fetched only with `?why=1` |

Each build rewrites its month's file whole, at most about 4 MB. The rolling release keeps every monthly file.
Nothing is deleted: the store is the record of what was issued, so it is kept for as long as the forecast log is.

## Checks

- **Python** (`tests/test_issue_history.py`, 8 tests):
  - the issue id matches `printed.js`;
  - records come from the page's rules;
  - rows are only added, and a different record under a kept id is refused, leaving the file unchanged;
  - a reconstruction is refused;
  - the previous issue is the last kept, never the issue itself, and never one over a day old;
  - the previous issue is found across a month end;
  - the build step publishes the previous issue, and a rebuild keeps nothing;
  - writer to Parquet to `since-last.json` to since.js `lastSaid` in Node gives the expected sentences.
- **Node** (`tests/site_since_last.test.cjs`, 6 tests): real changes, the cases with nothing to compare, missing
  inputs, coverage, the gap in words, and no word saying safe, clean or caused.
- **Phone previews at 375 px**, from real issues built with `build_site.write_pages`:
  - Informative, 14:33 to 17:34 on 30 Oct, Eden at Armathwaite: Sunday and Monday fell to low risk beside fewer
    overflows expected to spill on Sunday; Tuesday was a small change across the line.
  - Unexplained, 00:41 to 01:33 on 30 Oct, Eden at Armathwaite: Tuesday rose to moderate risk with no kept input
    changing enough to show, and the page says so.

## Not done

- **It is behind `?why=1`.** Turning it on for everyone is a release decision.
- **The rain at each overflow is not kept** (the spill model's own input), which is the likely gap in the
  Armathwaite Tuesday case. That is not tested.
- **The records are not shown anywhere else yet,** such as a public "issued forecasts" archive, or the 2027
  evaluation reading them. Both could read this store; neither does.
- **No real-person check, Safari or screen reader.**
