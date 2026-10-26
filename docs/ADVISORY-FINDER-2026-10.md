# Advisory finder, a dry-run prototype (26 October 2026)

Status: prototype. Drafts only. Nothing is published, sent or read by the site build. Ethan's
decisions of 26 Oct 2026 are applied (see "Decisions, 26 October 2026" at the end).

## What it is for

Auckland's Safeswim shows a sourced, dated advisory on a beach, such as an official "do not swim" with
its cause and start date. SwimSignal has no such line. The nearest thing is the EA's own panel, which a
reader can open on a bathing water's page (`src/dipcast/site/eatoday.js`). The site build cannot read
the EA's advice: the bathing-water service has refused GitHub's runners since 28 Sep 2026.

The finder proposes draft advisory lines, such as "Environment Agency: advice against bathing (harmful
algae) since 19 Jun 2026", each with its source link. Ethan reads each draft and decides. A draft is
kept apart from the forecast levels and never changes them.

## How to run it

```
uv run python scripts/advisory_finder.py --dry-run --fixtures tests/fixtures/advisories --now 2026-10-26T19:00:00+00:00
uv run python scripts/advisory_finder.py --dry-run --previous data/cache/advisory_drafts.json   # live, weekly
uv run python scripts/advisory_finder.py --dry-run --previous data/cache/advisory_drafts.json --ea-history
uv run pytest tests/test_advisory_finder.py -q
```

It runs by hand on Ethan's Mac, weekly in season. It does not run in GitHub Actions or in the site
build: the EA's bathing-water service refuses GitHub's runners, and a test checks that no workflow
names the finder. A live run makes one request to each source, one at a time with a pause.

`docs/ADVISORY-FINDER-RUN-SHEET.md` is the step-by-step sheet for the weekly run and for approving.

It writes `data/cache/advisory_drafts.json`, which git ignores, and prints a short table. A run with
`--fixtures` writes `advisory_drafts_fixtures.json` instead, so a check on the saved answers never
replaces the file the next live run compares with. Each table row starts with the draft id and ends
with the whole draft line, the two things an approval needs. Without
`--dry-run` it refuses to run. `--previous FILE` compares with an earlier drafts file; pass last
week's file, because that is how drafts from a feed that could not be read come back as unverified.
`--approvals FILE` (default `data/advisories/approved.json`) is read, never written. If that file has
any mistake, the run stops with exit code 2 and writes nothing.

`--ea-history` also reads the incident history of each of the 38 inland bathing waters: 38 requests,
one at a time, at most once a day (Europe/London). The day is kept in
`data/cache/advisory_ea_history_day.json`, written before the first request. It is live only: not
with `--fixtures` or `--now`.

## Sources and licences

Each source below is a fixed entry in `SOURCES` in `src/dipcast/advisories.py`. Any other address is
refused. The licence lines were read from the pages named, on 26 Oct 2026.

| Key | What it is | Licence, as the source states it |
| --- | --- | --- |
| `ea-open` | The EA's open pollution incidents at bathing waters: `https://environment.data.gov.uk/doc/bathing-water-quality/pollution-incident/open.json?_pageSize=100` | [environment.data.gov.uk/bwq](https://environment.data.gov.uk/bwq/): "This dataset is published under the terms of the Open Government Licence". [OGL v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/) asks for an attribution statement and, where possible, a link to the licence. |
| `ea-history` | One water's incidents, open and closed. The address is built in code from a valid EA bathing-water id, never taken from a response. Read in a live run only with `--ea-history`, for the 38 inland bathing waters; the fixture is Ham and Kingston. | As above. |
| `epa-alerts` | The Irish EPA's bathing restrictions: `https://data.epa.ie/bw/api/v1/alerts?page=1&per_page=100` | [data.epa.ie](https://data.epa.ie/api-list/bathing-water-open-data/): "The data provided in the API is licensed under a Creative Commons Attribution 4.0 International License". |
| `ea-widget-frensham` | The EA's own panel for Frensham Great Pond. | OGL. The panel ends "Linked-data from the Environment Agency · OGL". |
| `govuk-lake-district-algae-2018` | An EA press release on GOV.UK, 19 Jul 2018, naming Windermere, Ullswater, Coniston Water and Killington Reservoir. Kept as a real example of an old notice that names shared waters. | GOV.UK footer: "All content is available under the Open Government Licence v3.0, except where otherwise stated". |
| `waverley-frensham` | Waverley Borough Council's news item of 22 Aug 2025 about Frensham Great Pond. | No open licence. Footer: "© Copyright 2026 by Waverley Borough Council". Copyright only: link and notice date kept, passage not kept. |
| `col-hampstead-swimming` | The City of London's swimming status page for Hampstead Heath. | No open licence. Footer: "© City of London Corporation 2026". Copyright only: link and notice date kept, passage not kept. |

Each entry also has a `role` (regulator, council or water company) and `open_licence` (true for OGL
and CC BY). There is no Natural Resources Wales or water-company entry yet: each needs an address read
and its licence checked first. The code takes them as they are (see decision 2).

What each source said on 26 Oct 2026 (read):

- `ea-open` answered this Mac with 7 open incidents. Frensham Great Pond (harmful algae, since 19 Jun)
  is the only one at a SwimSignal spot. The others are coastal: Blyth South Beach (oil or fuel, since
  11 Aug), Plymouth Hoe East and West (sewage, since 14 Oct), Ryde (sewage, since 24 Oct), and
  Perranuthnoe and Portreath (sewage, since 26 Oct, expected end 26 Oct). The answer has no next page,
  so it was the whole list.
- `ea-history` for Ham and Kingston: two incidents, both ended. Harmful algae from 17 Aug ended 19 Oct.
  Oil or fuel from 10 Sep ended 11 Sep. On 4 Oct the algae incident was still open.
- `epa-alerts`: none. The season is over. The tests also use the EPA's answer of 4 Oct 2026 (two rows).
- The EA panel for Frensham said "Bathing is not advised today due to pollution from harmful algae".
  It gives no date.
- Waverley's page (read live, not kept): one draft for Frensham Great Pond, dated 22 Aug 2025, "until
  further notice", flagged stale. That was before decision 3; the draft now keeps no passage.
- The City of London page (read live, not kept): no draft. It said the Mixed Pond was "closed for the
  winter". That is a closure, not advice about the water, so the finder skips it.

Requests made while building this: 11 in all, one at a time, from this Mac. They were the EA bathing
water landing page and API reference, the open incident list, Ham and Kingston's history, the EPA alerts,
the EPA's open-data page, the OGL v3.0 text, the EA panel for Frensham, and the GOV.UK, Waverley and City of
London pages. None refused. No feed asked for credentials.

Kept as fixtures (`tests/fixtures/advisories/`, `manifest.json` names each address and fetch time):
the two EA answers, the EPA answer and the EA panel byte for byte, and the GOV.UK page cut to its
`<main>` element. The Waverley and City of London pages are not kept, because neither is open-licensed.
Their tests use made-up pages of the same shape.

## The draft record

Each draft has: `spot_id` (or `null`, unmatched) and `candidates`; the official water id where a feed
gives one; the source's key, publisher, kind, role, address, licence and `open_licence`; `link`, the
address a reader opens (the EA profile, the beaches.ie page, or the notice page); the feed record's id
and address; `evidence`, the source's own text, at most 600 characters, with white space made single,
or `null` for a copyright-only source; `evidence_quoted`; `evidence_hash`; `notice_date`; `status` (open,
update, withdrawn or lifted; "open" means in force at the source, not new); `first_seen` (true when
the draft id was not in the `--previous` file, and for every draft without one); `advice`, the line's words for the advice, and `cause`; `expiry` and
`expiry_basis`; `expected_end` and `expected_end_basis` (the EA's or EPA's expectation, never an
expiry); `ended`; `fetched_at`; `flags`; `reason`; `duplicates`; `superseded_by`; `draft_line`; `held`;
`current`; and `approval` (unapproved, approved, changed or lapsed) with `approved`, `approved_by`,
`approved_at` and `approved_line` from the approvals file.

For a feed, the evidence is the record's fields as `name: value`, with the values exactly as the feed
gave them. A feed has no sentence to quote.

## The defaults, and why

- **Unknown expiry stays unknown.** An expiry is only a date the source gives, such as "until 30
  November 2026" on a page. "Until further notice" is recorded as the basis, with no date. A feed
  draft has no expiry: it stands while the feed lists it. The EA's `expectedEndOfIncident` and the
  EPA's start plus expected duration go in `expected_end`, never `expiry`.
- **An ambiguous place stays unmatched.** A passage matches a spot only when it names exactly one: by
  the spot's whole name, by one of three aliases for the Hampstead Heath ponds, or by a water that
  only one spot is on. "Windermere" fits five spots and "Hampstead Heath" three, so both stay
  unmatched, with the candidates listed. "The lake" alone, or "Frensham" alone, matches nothing. A
  feed record matches by its EA id, never by name.
- **A page can be the spot's own.** The EA panel's address names one water, so a passage on it that
  names no place is that water's.
- **No date, held.** A notice with no date keeps `notice_date: null`, is flagged `no_date` and held.
  The EA panel is the real case: it says "today" but gives no time.
- **A newer withdrawal supersedes.** In one thread (one feed incident, or one publisher on one spot),
  the latest notice wins. Older ones are kept, flagged `superseded`, with the id of the newer one. A
  lifting that is older than a notice does not end it.
- **Conflicts are kept.** If current notices from different threads disagree for one spot (one says
  in force, one says lifted), every one is kept and flagged `conflict`.
- **Duplicates collapse.** The same feed id, or the same page, spot and passage, makes one draft. The
  newest feed record wins. `duplicates` counts the rest.
- **Stale is flagged, not dropped.** A page notice older than 28 days with no expiry is flagged
  `stale`. EA feed incidents are never flagged stale: Frensham's (since 19 Jun) is still open on 26 Oct.
- **History is not a conflict.** An ended incident that ended before a current one began does not
  disagree with it. Without this, every water's EA history would flag its current incident.
- **Closures are not advisories.** A passage about a closure for access or the season ("closed for the
  winter", "closed for maintenance", "the pond is closed") makes no draft unless it names a cause in
  the water (algae, sewage, pollution, water quality). "Closed due to blue-green algae" is a draft.
- **Lifted and withdrawn need the source's words.** A feed's end date makes a draft "lifted". On a
  page, "lifted" or "withdrawn" counts only when the sentence says what was lifted ("the warning has
  been lifted") or says "issued in error". A bare "status=lifted" changes nothing.
- **Gone from a feed is not lifted.** With `--previous`, an incident that has left a feed read whole,
  with no end date read, comes back as "withdrawn" with a reason asking the reviewer to check. From a
  feed not read whole, nothing is inferred.
- **Unverified is not current.** If a feed (`ea-open` or `epa-alerts`) cannot be read, or is not read
  whole, its open drafts from `--previous` that were not seen this run come back flagged `unverified`,
  held and `current: false`. This is the rule `ireland.py` uses: a restriction is never shown from a
  kept copy.
- **Held** means a reviewer must settle a flag first: unmatched, ambiguous, no_date, conflict,
  superseded, unverified or company_notice.
- **Current** means the source, as read this run, still has the notice in force: not ended,
  superseded or unverified, and not past an expiry. It is separate from approval.

Inferred, not established: that an open EA incident means the EA advises against bathing. The EA
panel says so for Frensham on 26 Oct. `coastal.py` records the same for Plymouth Hoe on 1 Oct. The
API reference does not say every open incident carries that advice. Ethan adopted "advice against
bathing" as the line's wording for an open EA incident on 26 Oct (decision 5); the inference itself
is unchanged, and a reviewer can check it on the EA panel before approving.

## Source text is treated as hostile

- Scripts, styles, frames, SVG, comments and hidden elements (`hidden`, `aria-hidden`, `display:none`)
  are dropped before any text is read.
- Control characters, zero-width characters and bidi overrides are removed. The review table cleans
  every cell again, so a page cannot write terminal escapes.
- Evidence is plain text, capped at 600 characters.
- No link on a page is ever followed or stored. Requests go only to the fixed addresses, without
  redirects, at most 4 MB each, one at a time with a pause.
- A fixture manifest entry whose address is not on the list is refused, and a fixture file name is
  read as a bare name in the fixtures folder.
- Words such as "ignore previous instructions" stay in the evidence as text. They cannot approve,
  publish or change a draft's status. The tests check this.

## What a reviewer approves

Only Ethan approves. For each draft he checks the evidence, or opens the link where nothing is
quoted, and decides:

1. Is this the spot? Pick from `candidates` if the draft is unmatched.
2. Is it still in force today? Check stale and no-date drafts at the source.
3. Is the line right, word for word?
4. Which of conflicting notices stands? For a water company, is it the company's own incident?

An approval is one entry in `data/advisories/approved.json`, added by pull request:

```
{"draft_id": "1a2b3c4d5e6f", "approver": "Ethan Buckley", "approved_at": "2026-10-26T19:00:00Z",
 "line": "Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026"}
```

The loader refuses the whole file, and the run stops, if any entry has an unknown draft id (not in
this run or `--previous`), a missing or other approver, an `approved_at` that is not UTC in that form
or is in the future, a line that is not one clean line, a repeated id or another key. An approval
holds only for the exact line: if the draft's line changes, the draft is `changed` and needs
approving again. When an advisory has ended and left the drafts, its entry has to be removed by PR.
The finder never writes the file and has no function that publishes or sends.

## What it never does

- It never changes a forecast level or the spot's answer. A test checks that nothing in the package
  imports it, that no workflow runs it, and that no draft carries or names a level.
- It never publishes, posts, emails or commits drafts. Nothing in the site build imports it.
- It never calls a language model, a paid API or anything that needs an account.
- It never follows a link from a page, and never reads an address that is not on the list.
- It never fills in an expiry, a date or a place the source did not give.
- It never treats a feed draft from an earlier run as current. Each run reads the feed or marks the
  earlier drafts unverified, as `ireland.py` does.
- It never keeps a copyright-only source's words.

## Decisions, 26 October 2026

Ethan, 26 Oct 2026: "Adopt all the recommendations as my decisions". What each one is, and what
changed in the code:

1. **Who approves.** Ethan only. Approvals live in `data/advisories/approved.json` (created empty),
   one entry per approved draft: draft id, approver, approved_at (UTC) and the exact line text. The
   file changes only by pull request. Code: `load_approvals` (validation), `apply_approvals`,
   `ALLOWED_APPROVERS`, `--approvals`; the finder marks drafts approved or not and still never
   publishes. Tests reject an unknown draft id, a missing or other approver and a malformed date.
2. **Sources.** The EA, Natural Resources Wales, the Irish EPA and council notices about water
   quality. A water company counts only for its own incidents and is attributed "[company] says".
   Closures for access or the season are not advisories. Code: `Source.role`; `is_closure` drops
   closure passages; a water company's page must have a scope and its drafts are held
   (`company_notice`) for Ethan to confirm the incident is the company's own. No NRW or water-company
   address is on the list yet.
3. **Council text.** Link plus our own short summary. Words are stored only for openly licensed
   sources (OGL, CC BY). For a copyright-only source the draft keeps the link, the notice date and
   `evidence_quoted: false`, not the passage. Code: `Source.open_licence`; `evidence` is null and only
   a hash is kept for Waverley and the City of London; their licence fields say so.
4. **Expiry.** (a) An EA feed incident stands while the EA lists it open, re-checked every run. If
   the feed cannot be read, its earlier drafts are marked `unverified` and are not current. EA feed
   items are no longer flagged stale. (b) The Irish EPA's expected duration is shown as "EPA expects
   until <date>", never as an expiry. (c) A page advisory with no stated end expires 14 days after
   approval unless re-approved. Code: `expected_end` beside `expiry`; `unverified_feeds` in
   `resolve`; `current`; `PAGE_TERM_DAYS`; `approval: lapsed`.
5. **Wording.** "Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026" plus
   the source link. Equivalents: "EPA (Ireland): bathing temporarily prohibited (algal bloom) since
   11 Sep 2026; EPA expects until 18 Sep 2026" (Ballyallia Lake, from the EPA's answer of 4 Oct),
   "Waverley Borough Council: advice against swimming (<cause>) since <date>", and "Thames Water
   says: advice against swimming (sewage) since <date>". The line never changes a risk
   level. Code: `draft_line`, `advice_words`, `link`.
6. **EA history.** Allowed once a day for the 38 inland bathing waters, one request at a time. Code:
   `--ea-history`, `history_ids`, `MAX_HISTORY` (40), the day stamp. It was tested with saved and
   mock answers only; no live request was made while building it.
7. **Where it runs.** By hand on Ethan's Mac, weekly in season. Not in GitHub Actions and not in
   the site build.

## Live dry run, 26 October 2026

One run of `scripts/advisory_finder.py --dry-run` with the real feeds, from this Mac, at 22:06 UTC.
`--previous` was the fixture run of the same day (the 18:37 UTC answers). No `--ea-history`.

Requests (read): 6, one at a time, 22:06:01 to 22:06:08 UTC, all HTTP 200. They were `ea-open`,
`epa-alerts`, `ea-widget-frensham`, `govuk-lake-district-algae-2018`, `waverley-frensham` and
`col-hampstead-swimming`. Nothing downloaded was committed: the EA list and the EA panel were
identical to the fixtures already kept, and the council pages are not open-licensed.

What it found (read):

- 10 drafts, 8 held, 0 approved. All 6 sources `ok`. No feed rows left out.
- One draft at a spot with no flag: `e8b5832d974a`, Frensham Great Pond, "Environment Agency: advice
  against bathing (harmful algae) since 19 Jun 2026".
- Two more for Frensham. The EA panel (`800f5abe3b84`) is held `no_date`. Waverley's notice of
  22 Aug 2025 (`f815928c7a06`) is flagged `stale`, not held, and marked current.
- The 2018 GOV.UK notice (`59099bc9475b`) is held: ambiguous, stale, unmatched (11 spots).
- Six coastal EA incidents are held `unmatched`: Blyth South Beach, Plymouth Hoe East and West, Ryde,
  Perranuthnoe and Portreath. The EA list matched the 18:37 answer exactly.
- EPA: no alerts. City of London: no draft (the closure for winter is skipped, as designed).
- The 9 drafts also in the earlier run kept the same ids.

Unexpected, and what was done:

- The review table cut the draft id and the line off at 64 characters, so an approval could not be
  copied from it. Fixed: each row starts with the id and ends with the whole line; a link where
  nothing is quoted is printed whole. Test: `test_review_table_shows_the_id_and_the_whole_line`.
- A fixture run without `--out` wrote over `data/cache/advisory_drafts.json`, the file the next live
  run compares with. Fixed: a fixture run writes `advisory_drafts_fixtures.json`. Test:
  `test_fixture_run_does_not_overwrite_the_live_drafts_file`.
- The test of the repo's `approved.json` required it to be empty, so Ethan's first approval PR would
  have failed it. Now it checks the file is valid, with the real clock.
- Every draft was `new`, though 9 were in the previous run: `new` meant in force and unchanged, not
  first seen. Fixed the same day: that status is now `open`, and a separate `first_seen` (shown in
  the table) says whether the draft id was in the `--previous` file. Draft ids are unchanged. Test:
  `test_open_is_in_force_and_first_seen_is_separate`.
- A stale page notice is not held and is still marked current. This is as designed (stale is
  flagged, not dropped). The run sheet tells the reviewer to check the page.
