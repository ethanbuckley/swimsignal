# Official notices, Find a window and outing access: decisions (28 October 2026)

Ethan delegated these product calls to Claude and Codex to settle by consensus without waiting for him (28 Oct
2026). This file records what was settled and built on `feat/notice-restricts`. Anything below can be changed by a
later decision; the tests named pin the current behaviour.

## Official notices: three semantics

1. **Each approval says whether its notice restricts swimming.** The `restricts` field in
   `data/advisories/approved.json` is true or false, set by the reviewer from the notice's own words, and it is
   required: an entry without it approves nothing (`src/dipcast/official_advice.py`). The one approval, the EA's
   "advice against bathing (harmful algae)" at Frensham Great Pond, is true.
2. **Only `restricts: true` changes selection.** It decides what Plan a swim, the best-day line, the shared plan and
   Nearby leave out, what the list puts first, and the outing's "neither looks good". Every notice is still
   shown: its tag, the spot page's block, the map's ring and tooltip. The ring is a cue to open the spot and read
   the notice, not a level.
3. **The words follow the kind.** A restricting notice is "Official advice" and asks to "follow it first"; any other
   is an "Official notice" to "read first". Only the notice's own reviewed line may say what it is ("advice
   against bathing"). A notice without the field (a spots.json from before) is neutral and changes no selection.
   Saved's notes and the outing's watch keep the kind, and a reviewer reclassifying the same notice is a change
   only where both notes say true or false.

Pinned by `tests/site_notice_restricts.test.cjs` and `tests/site_notice_acceptance.test.cjs`, plus the loader and
server tests in `tests/test_official_advice.py`, `tests/test_cards.py`, `tests/test_feeds.py` and
`push/test/official.test.js`.

## Find a window: three semantics

1. **A day counts when its displayed SwimSignal forecast is low risk** (`levels.js`, `dayLevel`). Today's level already
   takes in spills right now. A day with no level never counts, and a spot without a day-by-day forecast has no
   window.
2. **Each day is taken on its own.** A low-risk day counts even when a later day is higher; adjacent low-risk days are one
   range. The tile says a later day may be higher.
3. **Days, never hours; no ranking.** One level covers a whole day. Low risk is not a safety check. Spots stay in the
   list's order, and no spot is called safer or best, with or without a notice. A notice shows under the spot's
   name in its own words, and its line follows the kind above.

Pinned by `tests/site_find_window.test.cjs` and `tests/test_find_window.py`.

## Outing access notes

Each column of a plan's outing, and so of a shared outing link, shows the spot's own guide for parking, the path,
getting in and getting out: the facts' own words, who says so, the guide's checked date, and the topics it lacks.
A footpath or common land is never presented as permission; the desk check of permission (`access.py`) comes first
where a spot has one. No fact is added. Pinned by `tests/site_outing_access.test.cjs`.

## Still open (not decided here)

- Meeting points and activity type in a shared outing: guide facts have no ids or coordinates, and PR #409's "no
  free text in links" is not yet decided.
- Paddling start and finish points (PR #409, S4).
- Guide topics for carry distance and launch, and a date per fact.
- New listed spots: none before the D4 read (21 Nov 2026).
