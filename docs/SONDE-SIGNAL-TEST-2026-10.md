# EA sonde readings in the river E. coli estimate: the test, stated before any score

Draft, 27 October 2026. Only the request caps are written so far. They are committed before the first request to the
EA Hydrology API. The rest of the statement follows in later commits, before any score.

## Request caps, written before any fetch

- **Now (preparation):** at most 150 metadata requests to the EA Hydrology API (`environment.data.gov.uk/hydrology`).
  Metadata means station, measure and reference pages: names, places, dates and counts. No `readings` request is
  made now.
- **Pace:** one request in flight, at least 1.5 s after the previous one ends. Another worker may query the same API
  tonight, so nothing here runs in parallel, and a 403, 429 or 5xx answer is not retried in a loop: at most one retry
  after 10 s, and the request counts twice.
- **Ledger:** every request is logged (URL, status, bytes, start and end time). The count goes in "Seen before
  writing".
- **Scoring time:** the readings fetch is sized below as requests × pace, and capped there, before it runs.
