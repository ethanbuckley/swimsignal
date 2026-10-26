# Advisory finder, a dry-run prototype (26 October 2026)

Status: prototype. Drafts only. Nothing is published, sent or read by the site build.

## What it is for

Auckland's Safeswim shows a sourced, dated advisory on a beach, such as an official "do not swim" with
its cause and start date. SwimSignal has no such line. The nearest thing is the EA's own panel, which a
reader can open on a bathing water's page (`src/dipcast/site/eatoday.js`). The site build cannot read
the EA's advice: the bathing-water service has refused GitHub's runners since 28 Sep 2026.

The finder proposes draft advisory lines, such as "EA: open pollution incident at Frensham Great Pond,
harmful algae, since 19 Jun 2026". A person reads each draft and decides. A draft is kept apart from
the forecast levels and never changes them.

## How to run it

```
uv run python scripts/advisory_finder.py --dry-run --fixtures tests/fixtures/advisories --now 2026-10-26T19:00:00+00:00
uv run python scripts/advisory_finder.py --dry-run          # live: one request to each source, one at a time
uv run pytest tests/test_advisory_finder.py -q
```

It writes `data/cache/advisory_drafts.json`, which git ignores, and prints a short table. Without
`--dry-run` it refuses to run. `--previous FILE` compares with an earlier drafts file.

## Sources and licences

Each source below is a fixed entry in `SOURCES` in `src/dipcast/advisories.py`. Any other address is
refused. The licence lines were read from the pages named, on 26 Oct 2026.

| Key | What it is | Licence, as the source states it |
| --- | --- | --- |
| `ea-open` | The EA's open pollution incidents at bathing waters: `https://environment.data.gov.uk/doc/bathing-water-quality/pollution-incident/open.json?_pageSize=100` | [environment.data.gov.uk/bwq](https://environment.data.gov.uk/bwq/): "This dataset is published under the terms of the Open Government Licence". [OGL v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/) asks for an attribution statement and, where possible, a link to the licence. |
| `ea-history` | One water's incidents, open and closed. The address is built in code from a valid EA bathing-water id, never taken from a response. Not read in a live run; the fixture is Ham and Kingston. | As above. |
| `epa-alerts` | The Irish EPA's bathing restrictions: `https://data.epa.ie/bw/api/v1/alerts?page=1&per_page=100` | [data.epa.ie](https://data.epa.ie/api-list/bathing-water-open-data/): "The data provided in the API is licensed under a Creative Commons Attribution 4.0 International License". |
| `ea-widget-frensham` | The EA's own panel for Frensham Great Pond. | OGL. The panel ends "Linked-data from the Environment Agency · OGL". |
| `govuk-lake-district-algae-2018` | An EA press release on GOV.UK, 19 Jul 2018, naming Windermere, Ullswater, Coniston Water and Killington Reservoir. Kept as a real example of an old notice that names shared waters. | GOV.UK footer: "All content is available under the Open Government Licence v3.0, except where otherwise stated". |
| `waverley-frensham` | Waverley Borough Council's news item of 22 Aug 2025 about Frensham Great Pond. | No open licence. Footer: "© Copyright 2026 by Waverley Borough Council". |
| `col-hampstead-swimming` | The City of London's swimming status page for Hampstead Heath. | No open licence. Footer: "© City of London Corporation 2026". |

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
  further notice", flagged stale.
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
gives one; the source's key, publisher, address and licence; the feed record's id and address;
`evidence`, the source's own text, at most 600 characters, with white space made single; `notice_date`;
`status` (new, update, withdrawn or lifted); `advice` and `cause` in the source's words; `expiry` and
`expiry_basis`; `ended`; `fetched_at`; `flags`; `reason`; `duplicates`; `superseded_by`; `draft_line`;
`held`; and `approved`, which is always false.

For a feed, the evidence is the record's fields as `name: value`, with the values exactly as the feed
gave them. A feed has no sentence to quote.

## The defaults, and why

- **Unknown expiry stays unknown.** An expiry is only a date the source gives: the EA's
  `expectedEndOfIncident`, or "until 30 November 2026" on a page. "Until further notice" is recorded
  as the basis, with no date. For the EPA, the expiry is the start plus the EPA's expected duration in
  days, and `expiry_basis` says so. That date is worked out, not stated: it is Ethan's call whether to
  keep it.
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
- **Stale is flagged, not dropped.** A notice older than 28 days with no expiry is flagged `stale`.
  Frensham's EA incident (since 19 Jun) is flagged stale although the EA still lists it as open on
  26 Oct. The reason line says both, so the reviewer sees why.
- **Lifted and withdrawn need the source's words.** A feed's end date makes a draft "lifted". On a
  page, "lifted" or "withdrawn" counts only when the sentence says what was lifted ("the warning has
  been lifted") or says "issued in error". A bare "status=lifted" changes nothing.
- **Gone from a feed is not lifted.** With `--previous`, an incident that has left a feed read whole,
  with no end date read, comes back as "withdrawn" with a reason asking the reviewer to check. From a
  feed not read whole, nothing is inferred.
- **Held** means a reviewer must settle a flag first: unmatched, ambiguous, no_date, conflict or
  superseded.

Inferred, not established: that an open EA incident means the EA advises against bathing. The EA
panel says so for Frensham on 26 Oct. `coastal.py` records the same for Plymouth Hoe on 1 Oct. The
API reference does not say every open incident carries that advice. So a feed draft says "open
pollution incident", not "advice against bathing".

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

For each draft, a person checks the evidence at the source address and decides:

1. Is this the spot? Pick from `candidates` if the draft is unmatched.
2. Is it still in force today? Check stale and no-date drafts at the source.
3. What is the line, word for word, and its start date and expiry?
4. Which of conflicting notices stands?

The finder writes `approved: false` on every draft. It has no function that approves, publishes or
sends.

## What it never does

- It never changes a forecast level or the spot's answer.
- It never publishes, posts, emails or commits drafts. Nothing in the site build imports it.
- It never calls a language model, a paid API or anything that needs an account.
- It never follows a link from a page, and never reads an address that is not on the list.
- It never fills in an expiry, a date or a place the source did not give.
- It never shows Irish restrictions from a kept copy. Each run reads the feed or reports that it could
  not, as `ireland.py` does.

## Decisions still Ethan's

1. **Who may approve a draft**, and where approvals are kept. Nothing records an approval yet.
2. **What counts as a source.** The list has two feeds and four pages. Should council and water
   company pages count, given they are not open-licensed? Should closures ("closed for the winter")
   count, or only advice about the water?
3. **Using council text.** Waverley's and the City of London's pages are copyright. Quote them, link
   only, or ask permission?
4. **Expiry rules.** Should an EPA expected duration become an expiry date? How long may a draft with
   no expiry stand before it lapses (28 days is the stale flag, not a removal)? Should an EA incident
   still in the open list be exempt from stale?
5. **Wording.** "Open pollution incident" versus "advice against bathing", and the form of the line.
   `draft_line` is a suggestion built from fields only.
6. **The EA history feed.** Reading it for all 38 inland bathing waters would be 38 requests a run.
   Is the open list alone enough?
7. **Where it runs.** The EA service refuses GitHub's runners, so a live run has to be from a Mac,
   like the other off-CI scripts.
