# River-rises shadow logger

A Cloudflare Worker that records, once an hour, the river levels and the radar file list that a research
candidate would have had at that hour. The candidate and its scoring are in
[docs/RIVER-RISES-C3-2026-11.md](../docs/RIVER-RISES-C3-2026-11.md), section "The shadow log". The site's builds run
hours apart, so they cannot capture inputs as published at each issue time; this Worker does that on its own cron.

## What it does and does not do

It does:

- run on the hour, every hour (UTC);
- make **two requests** a run, three in the 00:00, 01:00 and 02:00 runs (below), never more;
- keep one KV record a run, `h/<issue hour>`, for an offline evaluation.

It does not:

- make a prediction, or compute anything from the levels or the radar;
- publish anything. Every HTTP request to it gets 404. There is no page, no endpoint, no public text;
- call Open-Meteo;
- touch the site, its builds or the push Worker (`push/`). It has its own KV namespace.

It is not a swimming-safety tool. A record says what the EA and the radar bucket published at an hour, nothing more.

## The requests

1. `GET https://environment.data.gov.uk/flood-monitoring/data/readings?latest&parameter=level`: the latest reading
   of every level measure in England, in one answer (4,111 items, 1.3 MB on 26 Oct 2026). This is the single
   bulk call the EA asks heavy users to make instead of crawling stations one by one (as the C3 document records;
   not re-checked against the EA's page for this README). The Worker keeps only the items whose measure is in
   `src/measures.js`, as `{measure, dateTime, value}`.
2. `GET https://met-office-radar-obs-data.s3.amazonaws.com/?list-type=2&prefix=radar/YYYY/MM/DD/&max-keys=1000`:
   the listing of that UTC day's radar composites (96 a day). It keeps the keys whose time, from the file name, is in
   (issue − 3 h, issue], with `size`, `last_modified` and `etag`. When the issue hour is 00:00, 01:00 or 02:00 UTC
   it lists the day before as well, since the 3-hour window starts on that day.

Rules on every request: https only, to those two hosts only; redirects are not followed and any 3xx counts as a
failure; a 20 s timeout; the EA answer must be at most 8 MB and a listing at most 2 MB (measured on the text);
**no retry, ever**. A failure is written into the hour's record (`status`, `error`), not thrown.

## Which measures

`src/measures.js` and `measures.json` are written by
[scripts/river_rises_eval/shadow_measures.py](../scripts/river_rises_eval/shadow_measures.py), offline, from the scope
CSVs and the coverage run's cached EA answers of 26 Oct 2026. Do not edit them by hand.

- 100 rows: 45 spot gauges, 26 `same` and 29 `trib` upstream gauges; 88 distinct stations.
- `measure` is the flood-monitoring level measure the site itself would read (`flows._level_measures` order, first
  with a reading, as `flows.river_state`). The CSVs' `measure` column is a Hydrology id, a different API.
- The Worker keeps **every** level measure of each listed station (128 ids, `site_order` in `measures.json`), so
  the scorer can apply the site's rule at each hour even if the first measure stops publishing. 91 of the 128 were
  in the 26 Oct answer.
- No station is missing. One has no reading in the 26 Oct answer: L2105 (Knaresborough, Nidd), whose status was
  "Suspended". It stays listed; its hours will most likely be empty.

Do not regenerate these files during the scoring window: the logged set is part of the protocol.

## The stop rule

A run where either request failed adds one to `state/failures` (`{count, recent}`); a run where both succeeded
sets it back to 0. At **6 consecutive failed runs** it writes `state/stopped` = `{at, reason, last_errors}` and
from then on does nothing at all, not even a request, until a person deletes that key (below). The count starts
again from 0.

A run also does nothing when `h/<issue hour>` already exists, so a second fire in the same hour makes no request.
KV can take up to a minute to show a write everywhere, so two fires within seconds of each other could both run;
the cost is two extra requests and the second record replacing the first.

## Cost against the free plan

Limits as the push README records them from Cloudflare's limits page (read 29 Sep 2026): 10 ms of CPU and 50
outgoing requests per run, KV 100,000 reads and 1,000 writes a day. **KV storage of 1 GB and a 25 MiB value limit
are from memory, not verified.**

- **CPU.** The filter on the cached 1.3 MB EA answer (JSON parse and keep 91 of 4,111 items), in Node 26 on a Mac:
  best of 30 runs 1.96 ms, median 2.25 ms, first (cold) call 3.3 to 6.5 ms. Parsing a day's radar listing: 0.14 ms.
  A whole cold run measured in Node took about 17 ms of wall time, of which about 11 ms is Node setting up its web
  streams on first use, which Workers do natively. How Workers count this has not been measured; after deploying,
  check the run's CPU time in the dashboard (Workers, swimsignal-river-shadow, Metrics) or `npx wrangler tail`.
- **Requests.** 2 or 3 a run.
- **KV.** At most 3 reads and 3 writes a run: about 72 reads and 24 to 49 writes a day.
- **Storage.** One record is about 16.5 kB (91 readings and 12 radar keys), so about 0.4 MB a day and about 45 MB
  from mid-November to 28 Feb 2027.

## Records

Key `h/2026-12-01T13:00:00Z`, value:

```json
{"schema": "swimsignal.river-shadow.hour", "version": 1, "issue": "2026-12-01T13:00:00Z",
 "fetched_at": "2026-12-01T13:00:04.120Z", "worker_version": "river-shadow/1", "n_requests": 2,
 "ea": {"status": 200, "bytes": 1307110, "error": null, "n_items_total": 4111,
        "items": [{"measure": "http://environment.data.gov.uk/flood-monitoring/id/measures/F1902-level-stage-i-15_min-m",
                   "dateTime": "2026-12-01T12:45:00Z", "value": 0.412}]},
 "radar": {"status": 200, "bytes": 34512, "error": null,
           "keys": [{"key": "radar/2026/12/01/202612011015_ODIM_ng_radar_rainrate_composite_1km_UK.h5",
                     "size": 402113, "last_modified": "2026-12-01T10:23:40.000Z", "etag": "\"9b2c...\""}],
           "listings": [{"url": "...", "status": 200, "bytes": 34512, "error": null, "n_keys": 96, "truncated": false}]}}
```

## The window

Records start when it is deployed. The shadow scoring uses issue times from 1 Dec 2026 00:00 to 28 Feb 2027 21:00
UTC (from the logger's first full UTC day, if that is later), and is read on or after 8 Mar 2027. Before then,
look only at uptime and missing hours, never at a score.

To copy the records out for the scorer (reads only):

```sh
cd river-shadow
node scripts/export.mjs ~/Documents/GitHub/swimsignal-private/river-rises/shadow-export
```

## Attribution

- This uses Environment Agency flood and river level data from the real-time data API (Beta), under the Open
  Government Licence v3.0.
- Met Office radar: only the bucket listing's metadata (file names, sizes, times, ETags) is stored here. The rain
  values are read later from the files in the AWS Open Data bucket `met-office-radar-obs-data`, licensed CC BY-SA 4.0,
  and checked against these ETags.

## Deploying (Ethan)

1. `cd river-shadow`
2. `node --test test/*.test.js`. You will see `pass 25`, `fail 0`.
3. `npx wrangler kv namespace create SHADOW`. It prints a block with `id = "..."`.
4. Open `wrangler.toml` and replace `REPLACE_WITH_THE_SHADOW_NAMESPACE_ID` with that id.
5. `npx wrangler deploy`. It ends by listing the schedule `0 * * * *`.
6. After the next full hour, plus a minute or two:
   `npx wrangler kv key list --binding SHADOW --remote --prefix h/`
   You should see one name like `h/2026-11-10T14:00:00Z`. Then
   `npx wrangler kv key get --binding SHADOW --remote "h/2026-11-10T14:00:00Z"`
   and check that `ea.error` and `radar.error` are both `null`, `ea.items` has about 90 entries and `radar.keys`
   about 12.
7. If it has stopped (`npx wrangler kv key get --binding SHADOW --remote state/stopped` shows a record), read
   `last_errors`, fix the cause, then restart it with
   `npx wrangler kv key delete --binding SHADOW --remote state/stopped`. The next hour's run asks again.

**The mistake most likely:** leaving out `--remote` on the `kv key` commands. Recent wrangler versions read a local
development copy by default, so `list` answers `[]` and it looks as if the Worker never ran. Every command above
has `--remote` for that reason. Run them from `river-shadow/`, so that wrangler finds this `wrangler.toml` and its
`SHADOW` binding, not the push Worker's.
