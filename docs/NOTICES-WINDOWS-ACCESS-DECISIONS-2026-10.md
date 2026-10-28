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

## Release batch, 28 October 2026: what it finished

Gap list against the decisions above, and what this batch did about each:

| Item | Before | Now |
|---|---|---|
| Official notices on every surface | Done, with the acceptance matrix (`tests/site_notice_acceptance.test.cjs`) | New surfaces in this batch (Plan's Find a window) use the same helpers; the matrix covers Find a window |
| Find a window | Saved only; no reasons; no area or activity | Also on Plan a swim, for the plan's spots: its area (start and distance) and activity (the kind chip: rivers, lakes, bathing waters). Nearest first by distance, never by level; at most 12, the rest counted. Each other day is named in the page's own headline ("Moderate risk: sewage spills"), the same headline on days in a row as one range; missing days named; notices apart from the levels. Saved shows the same reasons |
| Shareable outing | Spot, backup, access notes, share link | The calendar file also carries each spot's verified parking and getting-in facts from its guide, with the guide's checked date; never a swimmer's suggestion, a meeting point or a put-in the guide does not give |
| Access guides | 53 of 109 spots | Added for Crummock Water and Wastwater, from the park authority's lakes guide and the National Trust's car-park pages (desk-checked 28 Oct); 55 of 109 |
| Spots | | Carding Mill Valley Reservoir, Brothers Water, Loweswater and Bassenthwaite Lake (`docs/SPOT-ADDITIONS-2026-10.md`), 86 Open-Meteo calls a day, about 41 spare |

"Activity" here means the plan's kind chip. SwimSignal has no swim-versus-paddle activity, and none was invented.

## Next-phase queue (short, researched in the repo; none blocks this release)

- **Swim passport** (a personal record of places swum). Nothing exists. The swim journal (`journal.js`, on the device only) is the nearest thing. A passport would extend it, never a server list of where people swim (the Swim Together plan, `docs/SWIM-TOGETHER-2026-10.md` on PR #409, rules that out without the Ofcom check and a DPIA).
- **Swimmer reports.** Visit notes (`visits.js`, quick dated ticks that expire) and reviews are live through the reviews Worker, with moderation by Ethan. More report kinds (paddlers' ticks: launch under water, tree across the river) are #409's stage 3. Moderation load is the limit.
- **Replay** ("what would the forecast have said"). `replay.js` and `data/spot/<id>-replay.json` exist (#390). Next would be replay on the spot page for any past day, which needs the archived inputs per day.
- **Clubs.** `clubs.html` exists (what the levels mean for clubs, the sites view). Stored outings with a list of who is coming are #409's stage 2: pilot-only, after the Ofcom check and a DPIA.
- **SUP and paddling.** No wind is fetched. Its Open-Meteo cost is unchecked against the about 41 calls a day left, and the paddling start and finish points (#409's S4) are not built.

## Still open (not decided here)

- Meeting points and activity type in a shared outing: guide facts have no ids or coordinates, and PR #409's "no
  free text in links" is not yet decided.
- Paddling start and finish points (PR #409, S4).
- Guide topics for carry distance and launch, and a date per fact.
- New listed spots: the D4 read (21 Nov 2026) is a release gate to re-evaluate, not a block on preparing spots (Ethan, 28 Oct).
  The four added here have no bearing on D4 except Bassenthwaite, whose overflows join the live log from its merge.
