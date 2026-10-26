# AI and data programme, autumn 2026: status map

Started 26 October 2026, after Ethan accepted Codex's assessment of which AI systems are worth building. This is the
one place that says what each piece is, where it stands and what is waiting on a decision. Each piece is a separate
draft PR. None is merged or deployed by this programme, and none changes the live site, the live models, or the A8,
option B or shadow windows.

Last updated: 26 October 2026, programme start.

## The map

| Piece | Deliverable | PR | Tests | Evidence so far | Costs and limits | State | Next decision (Ethan) |
|---|---|---|---|---|---|---|---|
| Satellite algae | #377 statement revised: existing CLMS product benchmarked before custom Sentinel-2 processing; coverage prototype; harness with synthetic tests | #377 (draft) | synthetic only | none yet | download caps written before any fetch; no account | in progress | read and approve the statement before any scoring |
| Advisory finder | dry-run drafts from official feeds, then a small whitelist | to come | fixtures | none yet | no LLM, no account, about 20 requests | in progress | who approves, what counts as a source, expiry, wording |
| Sampling priorities | offline ranking; synthetic simulation stated before it is run | to come | synthetic | none yet | no network | in progress | whether to use it with partner sampling |
| Monitoring anomalies | review-only flags beyond today's health rules, judged on saved data | to come | synthetic failures | none yet | no network | in progress | which flags go on the data-quality page |
| River rises | coverage and arrival-delay prototype; dated plan against persistence | to come | synthetic hydrographs | none yet | EA request caps; no Open-Meteo calls | in progress | whether to run the stated evaluation |
| Moderation help | a trigger based on queue volume | this PR | none (no code) | 0 published reviews, 0 notes showing (26 Oct) | none | written | the trigger numbers |

## Rules every piece follows

- Draft PRs only. No merges, deploys, outreach, purchases, accounts or credential changes.
- Statements are written before any data that could judge them is read. Anything seen first is listed in the
  statement.
- Heavy runs wait for the group's shared `heavy-run.lock`. Public fetches have caps written down before they start.
  No piece uses Open-Meteo calls.
- Algae blooms are kept apart from toxins and from E. coli. A river-rise figure is not a swimming-safety forecast.
- An advisory is always a draft a person approves, and never changes a level.

## Not in this programme

- A swimmer chatbot, pollution from photos, and camera drowning detection: ruled out on 26 October 2026.
- Between-image bloom forecasting: a separate test, stated later, only if detection works.
