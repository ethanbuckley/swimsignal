# Lab results from organisations

An organisation that pays for lab tests of the water (an event organiser, an activity centre, a club)
can send SwimSignal its results. Each result is kept with the spot, the time the sample was taken and
who sent it. With the sender's agreement it shows on the spot's page, in a tile of its own, set apart
from the forecast; with a separate agreement it is used to test the forecast. It never changes the
level.

This folder holds only the results that may be published. Every result, with both permissions, is
kept outside this repository.

## Where things are

| What | Where | Public? |
| --- | --- | --- |
| Every result, both permissions, the lab's reference | `~/Documents/GitHub/swimsignal-private/samples/<supplier>.csv` (or the folder in `DIPCAST_SAMPLES_PRIVATE`) | No |
| The results that may be published, without the lab's reference or the permissions | `samples/<supplier>.csv`, here | Yes, once merged |
| Results paired with the forecasts live when they were taken | `<private folder>/evaluation/pairs.csv` | No |

One file per supplier, named from its name: "Example Swim Club" is `example-swim-club.csv`. Never edit
a file in this folder by hand. `scripts/add_samples.py` writes it whole from the private file each
time, so the private file is the record and this one follows it.

## The two permissions

Each is `false` until the sender agrees to it in writing (an email is enough). Keep that email.

- `publish`: the result may appear on the spot's page and in the site's open data files (spots.json,
  `spot/<id>.json`), with the sender's name and its lab's. The data page offers those files for reuse,
  so the agreement has to cover that too.
- `evaluate`: the result may be used to test the forecast, and to report how it did. Results used
  this way are not shown unless `publish` is also true.

A sender's name appears on the site only beside a result it agreed to publish.

## The format

One row per sample. Columns, in this order:

| Column | Needed | What |
| --- | --- | --- |
| `spot_id` | yes | The spot's id, as in `spots.csv` or `spots-osm.csv` (`bw-uke4100-08901`) |
| `sampled_at` | yes | When the sample was taken: `2026-10-17 08:30` or `17/10/2026 08:30`. Stored with its offset, `2026-10-17T08:30+01:00` |
| `timezone` | yes | The zone that time is in: `Europe/London` (UK clock time) or `UTC` (some lab systems record GMT all year) |
| `ecoli_per_100ml` | one of these two | E. coli per 100 ml: `1200`, or a limit, `<10` or `>24196`, as the lab reports it |
| `enterococci_per_100ml` | one of these two | Intestinal enterococci per 100 ml, the same way |
| `lab` | no | The lab's name, as the sender gives it |
| `ukas_accredited` | no | `yes` or `no` if the sender says whether the lab is UKAS-accredited for the test; blank if it does not say. This is the sender's word, and the page says so. Do not fill it in from anything else |
| `method` | no | The test method, if given (`membrane filtration`, `Colilert-18`) |
| `lab_ref` | no | The lab's reference for the sample, to find it in the report again. Private only |
| `supplier` | yes | The organisation that sent it |
| `received` | yes | The day it arrived, `2026-10-20` |
| `publish` | yes | `true` or `false` (above) |
| `evaluate` | yes | `true` or `false` (above) |

The public file has the same columns less `lab_ref`, `publish` and `evaluate`.

Checks, on adding and on every build:

- The spot id must be one of the site's spots.
- The time must have happened. In the hour the clocks go back a UK time happens twice: write the
  offset (`2026-10-25 01:30+01:00` for the first, `+00:00` for the second). In the hour they go
  forward it never happens, and is refused.
- `received` is not before the sample was taken and not in the future. A sample taken more than 120
  days before it arrived is refused unless `--allow-old` is given: a lab reports within days, so a gap
  of months is more often a wrong year, or a day and a month swapped.
- A count is a number per 100 ml, at most 10,000,000. Convert any other unit before adding it.
- The same spot, time and sender twice is one sample entered twice, and is refused.

A sample with no time cannot be added: ask the sender. The time places it against the forecast that
was live when it was taken.

## Adding results

1. Save the lab's CSV from the email, or type the values.
2. Check without writing anything:

   ```
   uv run python scripts/add_samples.py --supplier "Example Swim Club" --received 2026-10-20 \
       --publish --evaluate --dry-run results.csv
   ```

   Leave out `--publish` or `--evaluate` unless the sender agreed to it. If the lab's columns have
   other names, map each one: `--column sampled_at="Date/time sampled" --column ecoli_per_100ml="E. coli"`.
   Columns the format does not have are listed and ignored. A flag fills a blank cell (`--lab`,
   `--method`, `--ukas yes`, `--spot` for a file all from one spot); a value in the file wins.
   For one result typed by hand:

   ```
   uv run python scripts/add_samples.py --supplier "Example Swim Club" --received 2026-10-20 --publish \
       --spot bw-uke4100-08901 --sampled "2026-10-17 08:30" --ecoli 1200 --enterococci "<10" --lab "Example Water Lab"
   ```

3. Run it again without `--dry-run`. It prints each sample, then where it kept them. Any bad row means
   nothing is written, and it says which row and why.
4. If it says `samples/<supplier>.csv now has N rows`, open a pull request with that file. The
   results show on the spot's page from the first build after it merges.

The mistake most likely here is passing `--publish` for a batch where the sender agreed to some
results and not others (a test for its own records, say). Add those as two runs, or set `publish`
per row in the file: a value in the file wins over the flag.

## Changing a permission

Edit `publish` or `evaluate` in the private file, then:

```
uv run python scripts/add_samples.py --sync
```

It writes every public file again from the private folder. A result whose `publish` is now `false`
leaves `samples/`; commit the change in a pull request, and it leaves the page with the next build.
A supplier with nothing left to publish loses its public file.

## On the page

The build (`src/dipcast/samples.py`, `attach_measured`) puts each spot's published results from the
last 30 days, newest first and at most 10, in spots.json as `measured`. Thirty days, because a count
is for the moment the sample was taken and can change within hours after rain, so an old one says
little about the water now (an Environment Agency sample counts in the level for 14 days only); but a
monthly schedule's latest result, as British Triathlon's guidance suggests before an event, should
stay shown until the next one.

The spot's page draws them in the tile "Measured: lab results sent to SwimSignal"
(`src/dipcast/site/measured.js`): when each sample was taken and how long ago, the counts, who sent it
and when, the lab and method as the sender gives them, and that SwimSignal did not take or check the
samples and that they do not change the forecast. An E. coli count is set against 900 per 100 ml, the
line the E. coli estimate uses, with what that line is. Nothing on the page calls a result verified,
safe or a pass.

## Testing the forecast

```
gh release download state -p dipcast.duckdb -D ~/tmp/state
uv run python scripts/evaluate_samples.py --db ~/tmp/state/dipcast.duckdb
```

For each result with `evaluate = true` it finds the forecasts logged for its spot before the sample
was taken, for the sample's day: one for each lead, 0 (issued that day) to 4 (four days ahead), and
marks the newest as the one live when the sample was taken. It writes them to the private folder's
`evaluation/pairs.csv`, with whether the E. coli count is over 900, and counts the results with no
forecast before them. It needs the forecast log, which is on the build runner and in the "state"
release; a local `data/processed/dipcast.duckdb` is only as new as its last local build. It scores
nothing: with a handful of results a score would mean little, and the test belongs in a
pre-registration first (`docs/PREREGISTRATION-2027.md`).
