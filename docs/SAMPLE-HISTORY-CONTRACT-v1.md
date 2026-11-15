# Sample histories for Ireland and Wales: the observation contract, version 1

Written 13 November 2026. Route: public research observations (`docs/RESEARCH-WORKFLOW.md`). Source inventory ranks 7
(`epa-ireland-bathing`) and 8 (`nrw-water-quality-archive`). Register row: "Wales, Scotland, Ireland" in
`docs/RESEARCH-RECOVERY-2026-10.md`.

These are past lab samples, each with its date, from the official body that took it. **No forecast, no model and no
estimate** sits beside them. Nothing here changes an issued prediction, a frozen window or what a swimmer is told.

Labels: **[checked]** read or measured on 13 November 2026; **[inferred]** my reading, not stated by the source.

## What was delivered

| Nation | File | Waters | Samples | Dates | Size |
|---|---|---|---|---|---|
| Republic of Ireland | `data/research/sample_history_ireland.v1.json` | 243 (240 with samples) | 26,929 | 22 May 2014 to 4 Nov 2026 | 898 KB |
| Wales | `data/research/sample_history_wales.v1.json` | 2: The Warren at Hay-on-Wye, Llandeilo Swing Bridge | 61 (37 and 24) | 12 Aug 2023 to 18 Sep 2026 | 21 KB |

Both are under 1 MB. The Irish file is close (898 KB): a second nation's growth or a field more would pass 1 MB, and
the PR flags it for Ethan. The raw EPA pages (9.3 MB) are not in git; their SHA-256s are in the file's `requests`.

The site splits each file into an index and one file a water (`build_site.write_sample_histories`) and shows them on
the existing sample page, `samples.html`, beside England's E. coli evidence. A "Where" picker chooses England, Wales or
the Republic of Ireland. Each Irish card and both Welsh cards on the coverage page link to their water
(`samples.html#ireland=<id>`, `samples.html#wales=<id>`).

## Licences, rechecked on the day [checked]

- **EPA.** The API page says: "The data provided in the API is licensed under a Creative Commons Attribution 4.0
  International License." No rate limit is stated. Credit used: "Contains bathing water data from the Environmental
  Protection Agency (Ireland), Bathing Water Open Data API, licensed under CC BY 4.0", with a note that SwimSignal
  reorders the samples by water and date and that the values are unchanged (CC BY asks for changes to be indicated).
- **NRW.** The Water Quality Archive's record (NRW_DS124903) and the DataMapWales layer both give the Open Government
  Licence and this attribution statement, copied word for word with NRW's own capitals: "Contains Natural Resources
  Wales information © Natural Resources Wales and Database Right. All rights Reserved." The brief gave the same line in
  lower case ("database right", "All rights reserved"); NRW's own capitals are used. The record's next line, about
  Ordnance Survey data, is for the station map, which this work does not use or publish.

## How the data was fetched

Every request is in the file's `requests` with its time, address, status, bytes and SHA-256. The first answer that was
not HTTP 200 would have stopped the run; none came.

| Step | Sized first | Cap | Made | Result |
|---|---|---|---|---|
| EPA licence page, NRW record, DataMapWales page | 3 pages | n/a | 3 | 200 each |
| EPA counts (`per_page=2`) | 2 requests | n/a | 2 | 25,895 in season, 1,034 out of season |
| EPA list of waters and every measurement, 5,000 a page | 8 requests, about 11 MB, 2 s apart, under a minute | 16 | 8 | 200 each, 9.3 MB |
| NRW bathing-water service, one water a request | 2 requests | 6 | 2 (and 2 by hand while sizing) | 200 each, 30 and 16 samples |
| NRW ShareFile folder (the archive's download link) | 1 request | n/a | 2 | 404 both: my guess at its API address was wrong, not a refusal. I stopped and used the archive copy already downloaded |

All requests went from this Mac, off CI, sent with the project's own user agent. NRW's service refuses GitHub's runners
(checked 3 October 2026, `wales.py`); it answered here.

The Water Quality Archive part was not fetched. It is read from the zips already downloaded on 4 October 2026 (Wye
2020s, Carmarthen Bay and the Gower 2020s), copied read-only from the main checkout's cache. Their SHA-256s were the same
before and after. `data/raw/nrw_sample_history/` holds the service's two answers, the archive's 847 rows at the two
stations, the zips' hashes and the ledger: 372 KB, so the Welsh file can be rebuilt without the zips.

Rebuild: `uv run python scripts/export_sample_histories.py export wales --raw data/raw/nrw_sample_history`. Ireland:
`fetch ireland --raw <new dir>`, then `export ireland --raw <that dir>`. A new Irish fetch will differ (see Limits).

## What each source says about its samples

### Republic of Ireland (EPA)

- **Two lists.** In season: 22 May to 15 September, since 2014. Out of season: voluntary samples some councils report,
  which do not count towards a rating. The EPA says the out-of-season list runs from 2021 [checked, API page]; it holds
  rows from January 2016 [checked, the data].
- **The EPA's word for each sample.** Excellent, Good, Sufficient or Poor, which the EPA assesses "using the standards
  set in the Bathing Water Quality Regulations" [checked]. The page counts the Poor ones and shows the word in the table.
- **No lab method is named** for any sample [checked].
- **Lower limits differ by lab.** E. coli values given as "<": 9,844 in all. Most are "<10"; others "<1" (377), "<5" (1),
  "<20" (4) and "<50" (2) [checked]. Plain counts of 1 to 9 appear in every year, 2,493 in all, so some labs count
  below 10 [checked]. *Inferred:* labs use different methods with different limits.
- **Upper limits.** 30 E. coli values are given as ">": ">24196" (9), ">2010" (7), ">2420" (4), ">2419" (3), ">2005" (3)
  and four others [checked]. *Inferred:* 2419.6 is the top count of a most-probable-number tray, and 24196 the same
  diluted ten times. The EPA does not say so.
- **Zeros.** 12 samples read "0" [checked]. Kept as given; the chart draws them at the foot of its scale and says so.
- **Every value parsed.** No row was dropped; no result id repeats; every water with samples is in the EPA's list of
  waters [checked].

### Wales (NRW)

- **E. coli**: "Escherichia coli : Confirmed : MF" (determinand 2348), per 100 ml. MF is membrane filtration: the
  water passes through a filter and the colonies that grow are counted, then confirmed by a further test.
- **Intestinal enterococci**: "Enterococci: Intestinal: Confirmed: MF" (3723), in CFU per 0.1 litre, which is 100 ml.
  The archive also has the presumptive count (3722); the file keeps the confirmed one, which is the one NRW's
  bathing-water service gives [checked: every shared sample matches it].
- **"<10"** is below the lab's lower limit of 10. One E. coli sample at Hay and several enterococci counts read so.
- **Why taken.** "ENVIRONMENTAL MONITORING STATUTORY (EU DIRECTIVES)" becomes "Statutory monitoring";
  "PLANNED INVESTIGATION (NATIONAL AGENCY POLICY)" becomes "Planned investigation". The 2023 samples at both waters, and
  Hay's 2024 samples, are planned investigations [checked]. NRW's service lists Hay's 2024 samples as in-season
  samples all the same [checked].
- **method_name** reads "Low" or "Low Additional". NRW's record does not explain it. The file keeps it; the page does
  not use it.
- **deviating_result**, NRW's flag for a sample that failed the lab's acceptance checks, is empty for every sample here
  [checked].
- **Times** have no offset. *Inferred:* local time in Wales, since both sources agree to the minute and the times fall
  in the working day; `coverage.html` already reads NRW's times as UK time.

### The two Welsh sources agree [checked]

Every sample in both the archive and the service has the same E. coli and enterococci counts and qualifiers. The export
stops if they ever differ. The archive adds 15 planned-investigation samples from 2023 (7 at Hay, 8 at Llandeilo) that
the service lacks. The service adds Llandeilo's samples of 9 and 18 September 2026, which postdate the archive copy.

## Fields

| Field | Meaning |
|---|---|
| `schema`, `version`, `nation` | `"swimsignal.sample-history"`, `"1.0.0"`, `"ireland"` or `"wales"` |
| `generated_at`, `fetched_at`, `period` | Export time; the first request's time; the first and last sample date |
| `source`, `credit`, `claim` | Publisher, licence, the licence wording read on the day; the credit line; `public_wording` and `not_claimed` |
| `qualifiers`, `methods` | What "<" and ">" mean; the source's methods and limits, in sentences the page shows |
| `lines` | 500 (coast, estuary) and 900 (lake, river): the "sufficient" standards' E. coli lines |
| `requests` | The ledger, one entry a request |
| `coverage` | Waters, waters with samples, samples |
| `sites[]` | `id` (the source's id), `name`, `kind`, `line`, `rating`, `page` (the official page), `summary` |
| `summary` | `samples`, `first`, `last`, `over_line`, `below_limit`, `above_limit`, `seasons`; Ireland adds `poor`, `out_of_season`; Wales adds `archive`, `service`, `investigation` |
| Ireland `sites[].in`, `.out` | `[date, E. coli, enterococci, the EPA's word as one letter]`, counts as the EPA gave them ("<10"); `status_letters` decodes the letter |
| Ireland extras | `county`, `designated`, `listed`, `kind_from`, `unrated_year`, `epa_counts`, `dropped` |
| Wales `sites[].samples` | `t`, `ecoli`, `q`, `ie`, `ie_q`, `reason`, `reason_text`, `mechanism`, `method_name`, `deviating`, `src` (`archive`, `service` or both), `over` |
| Wales extras | `river`, `station` (the archive's station number), `archive` (zips and their date), `times` |

A value with `q: "<"` is a limit, not a count: the page says "below 10", never "10". `over` is never true for a "<"
value; a ">" value is over when its limit is at or above the line. Exactly the line is not over. An Irish water's kind is
`ireland.water_kind`'s; a kind with no line would get no line drawn and no over count (none in this export).

## What the page may and may not say

- **May say:** what the official body's lab measured, where and when; how many samples were over the water's line; how
  many were given as a limit; the EPA's own word for each sample; why NRW took each sample.
- **May not say:** that the water was safe or unsafe on any other day or at any other time; anything about today; a
  rating (a rating uses four seasons of scheduled samples by a set method); where any bacteria came from.
- The official rating and the official page come first for every water. The page has no level colours and no link to a
  SwimSignal spot page, since there is none in Wales or Ireland.

## Limits

- **The EPA rewrites past seasons.** Before its December report the EPA keeps only scheduled in-season samples and drops
  investigative ones [checked, API page]. The in-season count fell from 25,978 (31 October) to 25,895 (13 November).
  This file is a dated copy; a later copy can hold fewer samples for the same season.
- **Wales is two waters.** Both have few samples (37 and 24), and the statutory record starts in 2024 at Hay and 2026 at
  Llandeilo. The other 112 Welsh bathing waters are not in this file.
- **The archive copy is from 4 October 2026.** NRW updates the archive monthly; corrections can change past values.
- **No method per Irish sample**, so a reader cannot compare two labs' low counts directly. The page says so.

## Decision record

| Field | Content |
|---|---|
| Identity | Sample histories, Ireland and Wales. Session: irish-welsh-sample-histories (13 Nov 2026). Code: `src/dipcast/sample_history.py`, `scripts/export_sample_histories.py`, `src/dipcast/site/samples.js`. Data: the two files above, `data/raw/nrw_sample_history/` |
| Evidence | Observations only; no test, no score. Checks: every value parsed, counts match the EPA's totals, the two NRW sources agree sample for sample |
| Stage and claim | Public research observations, in [#691](https://github.com/ethanbuckley/swimsignal/pull/691), not merged. Claim: these are the official bodies' published samples, dated |
| Next deliverable | (1) The other 112 Welsh bathing waters from NRW's service, all seasons, one request a water (about 112 requests, about 4 minutes at 2 s); (2) refresh the Welsh archive part when NRW's December update is out, by downloading the two zips by hand; (3) refresh Ireland after the EPA's December report, as a new dated version |
| Milestone and budget | (1) and (2) by 31 Dec 2026, under 130 requests, from this Mac. (3) after the EPA's report, 8 requests |
| Release route | Ethan merges; the next build publishes it. Rollback: delete the two files; the page then says no samples are published for that nation |
