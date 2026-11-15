# Action counter

**Status, 12 November 2026: on.** Deployed 10 Nov 2026 at `https://swimsignal-actions.swimsignal-push.workers.dev`.
Checked 12 Nov: the secret `READ_TOKEN` is set (`wrangler secret list`), the repository variable `DIPCAST_ACTIONS_URL`
is set (since 10 Nov 01:09 UTC), and the live pages carry `<meta name="swimsignal-actions">`. The deployed version
takes the first five events only; the six added for the redesign are refused with 400 until it is deployed again
(step 4 below).

A Cloudflare Worker that counts eleven things done on swimsignal.co.uk, as daily totals. It answers one question that
Cloudflare Web Analytics (sampled page views) cannot: are people using the site, and is that rising week on week. It
cannot say whether anyone comes back: it keeps nothing that could tell two visitors apart, by design.

## What it counts

| Event    | Sent when                                                                 | Spot id sent |
|----------|---------------------------------------------------------------------------|--------------|
| `spot`   | a spot's page opens (`openSpot`: a link, a marker, a list row, Back to it) | yes |
| `day`    | a day is picked in the five-day strip on a spot's page (not the summary put back) | yes |
| `save`   | Save is pressed and the spot goes into a list (not when it is removed)    | yes |
| `plan`   | Plan a swim shows results for a starting place; once per place per page load, so a new day or distance is the same plan | no |
| `alerts` | alerts are turned on in the Alerts tile, or the email sign-up is accepted | no |
| `dayalert` | on a spot's page, "Alert me if Saturday's forecast changes" is pressed and the alert service accepts it (`mountClear`, kind `date`); not on the press alone, not when stopped | no |
| `lowalert` | on a spot's page, "Tell me when it is back to low risk" is pressed and the alert service accepts it (`mountClear`, kind `low`); not on the press alone, not when stopped | no |
| `logswim` | "Log a swim here" is pressed (`#log-here`, on a phone's spot page on a low-risk day) | no |
| `feed`   | a row of the home page's spill feed is opened (`#home-feed`); the spot it opens counts as `spot` too | no |
| `search` | the phone's search button opens the search field (`#searchbtn`); not when it closes it | no |
| `mapday` | a day is picked in the five-day strip on the phone's full map (`#mapdays`); not the select on Saved and Plan a swim's maps | no |

The last six came with the redesign of 11 Nov 2026 (PRs #673 to #676). None carries a spot's id: per-spot totals stay
for the first three events only, as the privacy notice says.

"Changed my plans" was asked for as a sixth. **No such control exists on the site** (searched 10 Nov 2026: no
button, form or text in `src/dipcast/site/`, `src/dipcast/pages/` or any open PR). The Worker refuses an event of
that name rather than report a total of 0 for a control nobody can press. When the control is built, add
`changed` to `EVENTS` in `src/index.js`, call `countAction('changed')` from it, and add it to the privacy section
(`ACTIONS_PRIVACY` and `ACTIONS_SWAPS` in `scripts/build_site.py`, which say how many; `tests/test_action_counts.py`
checks the number against `EVENTS`).

**Adding an event: deploy the Worker first.** A Worker that does not know a name answers 400. The page never reads
that answer (a beacon), so nothing breaks, but those counts are lost until the Worker is deployed.

## What it keeps, and what it does not

- One KV key a UTC day, `d/YYYY-MM-DD`:
  `{"counts": {"spot": 41, "save": 3}, "spots": {"wharfe-ilkley": {"spot": 5, "day": 2}}, "writes": 12}`.
  `spots` holds per-spot totals for the three spot events, for at most 1,000 distinct spots a day; past that the
  day's totals still count. `writes` is how many times the key was written that day (below).
- No IP address, no user agent, no cookie, no identifier, no referrer, no time finer than the day. The Worker never
  reads a request header except `Origin` (to refuse other sites), `Content-Length` and, for GET, `Authorization`.
- `wrangler.toml` turns on no Workers Logs or other observability setting. Cloudflare's own handling of requests
  to its network is under its privacy policy, as for any request.

The page side (`countAction` in `src/dipcast/site/index.html`) sends nothing where the browser has objected: the
"Don't count my visits" choice on the home page (`dipcast.count`, the same key as the page-view counter), Global
Privacy Control or Do Not Track. It stores nothing on the device. It uses `navigator.sendBeacon` with a text body
(about 50 bytes), so there is no CORS preflight, and falls back to `fetch` with `keepalive` and no credentials.

**Anyone can inflate the totals.** The Worker refuses posts whose `Origin` is not `https://swimsignal.co.uk`, which
stops other web pages, but a script can forge that header. With nothing stored about senders there is no way to
spot repeats. Read the totals as indicators of a trend, not exact counts.

## Writes

Cloudflare's free plan allows 1,000 KV writes a day (Cloudflare's KV limits page, read 10 Nov 2026). The page does
not say whether that is per account or per namespace, so this Worker assumes it is shared with the push Worker (up
to about 230 a day: its README) and the river-shadow logger (24 to 49 a day). Two things keep it inside:

1. **Batching in memory.** Each Worker instance gathers what it is sent for 5 seconds (`FLUSH_MS`), then reads the
   day's key once and writes it once. A visitor who opens a spot, picks a day and saves it in a few seconds costs
   one write, not three. The flush runs under `ctx.waitUntil`, so the instance stays alive until it is written. This
   also keeps writes to the one key under KV's limit of one a second in most cases; a refused write is kept in
   memory and goes with the next flush from that instance.
2. **A daily cap.** The day's record counts its own writes. At `WRITE_CAP` (300) no more are made that UTC day, and
   GET reports the day as `"capped": true`: its totals are then a floor. 300 leaves the other Workers about 700.

Batching alone could not guarantee the limit, since a busy day could spread over many instances; the cap alone
would waste writes on single events. At about 60 visits a day (the strategy review, 6 Nov 2026), expect tens of
writes a day.

What this costs in accuracy: counts gathered in an instance that Cloudflare stops before its flush are lost, and
two instances flushing the same key within a moment can each read the old total, so one batch overwrites the
other. Both undercount slightly; neither overcounts.

## Reading the totals

GET needs the secret `READ_TOKEN`; without it, or without the secret set, GET answers 404. The figures are private:
do not commit them to this repository.

```sh
curl -s -H "Authorization: Bearer $READ_TOKEN" \
  "https://swimsignal-actions.swimsignal-push.workers.dev/?from=2026-11-10&to=2026-11-16"
```

`from` and `to` are UTC days, both included, at most 92 days; without them, the 7 days to today. The answer:

```json
{"events": ["spot", "day", "save", "plan", "alerts", "dayalert", "lowalert", "logswim", "feed", "search", "mapday"],
 "write_cap": 300, "timezone": "UTC",
 "days": [{"date": "2026-11-10", "counts": {"spot": 41, "day": 9, "save": 3, "plan": 2, "alerts": 0, "dayalert": 1,
           "lowalert": 0, "logswim": 2, "feed": 4, "search": 3, "mapday": 5},
           "spots": {"wharfe-ilkley": {"spot": 5, "day": 2}}, "writes": 12, "capped": false}]}
```

A day with nothing counted comes back with zeros and `"writes": 0`.

## Tests

```sh
cd actions
node --test test/*.test.js
```

## Deploying

1. `cd actions`
2. Done on 10 Nov 2026: `npx wrangler kv namespace create COUNTS`, its id is in `wrangler.toml`.
3. (Ethan) `npx wrangler secret put READ_TOKEN`, pasting a long random string (for example from `openssl rand -hex 24`).
   Keep it outside this repository.
4. Done on 10 Nov 2026: `npx wrangler deploy`. Run it again, from `actions/`, whenever `EVENTS` changes, before the
   site that sends the new names goes live. It prints the address, `https://swimsignal-actions.swimsignal-push.workers.dev`.
5. Done on 10 Nov 2026 (read from KV, since GET had no token yet). Check it: post one event and read it back.
   ```sh
   curl -s -X POST -H "Origin: https://swimsignal.co.uk" --data '{"event":"plan"}' https://swimsignal-actions.swimsignal-push.workers.dev/
   ```
   wait 10 seconds, then the GET above. Today's `plan` should be 1. Delete the test count with
   `npx wrangler kv key delete --binding COUNTS --remote d/<today>` **before** step 6, while nothing else is counted.
6. Turn the site side on: `gh variable set DIPCAST_ACTIONS_URL --body "https://swimsignal-actions.swimsignal-push.workers.dev/"`.
   The next build adds the address to the app's pages and the "Action counts" section to the privacy notice.
   Unset the variable to turn it off again; the pages go back exactly as they were.
