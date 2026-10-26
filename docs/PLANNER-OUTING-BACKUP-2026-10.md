# Outing and backup, changes with evidence, brief versions (27 Oct 2026)

Three small additions to Plan a swim, Saved and the decision record. All three run on data the page already has. None makes a new request. None sends anything anywhere.

## What existed before

Checked first, so nothing here duplicates it:

- Plan a swim (`plan.js`, `index.html` renderPlan/drawPlan): a day, a start, a distance and a kind. Spots are grouped low / no monitored overflow / moderate or higher / no level. The plan includes an evidence line per row (#269), Compare spots (#299/#300), "Share this plan" as a list link, and the plan kept in `dipcast.plan` (#292). There was no outing time and no backup spot.
- Since you last looked (`since.js`): Saved cards already said "Was low risk when you looked on Friday at 18:20; now moderate risk." The notes are kept in `dipcast.seen`. The line gave no evidence and no issue times, and it said nothing when the data was stale.
- Decision record (`record.html`/`record.js`) and briefings (`scripts/briefing.py`): the record already prints an issue id (`printed.js`, issueId). Briefings are archived by issue id. There was no on-page version check and no read tick.

## 1. Your outing (plan page)

A closed tile, "Your outing", sits at the top of a plan's results. It opens when an outing is set. It has three selects:

- **When:** any time, morning, afternoon, evening, or an hour from 05:00 to 21:00.
- **Spot:** your saved spots first, then the plan's own spots.
- **Backup (optional):** the same choices, minus the spot.

With a spot chosen, the tile shows one line, such as "Tomorrow evening: Port Meadow, or Wolvercote as a backup." Under it, the two spots sit side by side in two equal columns, about 160 px each at 375 px. Each column has:

- the distance and the kind of water
- the day's headline in its level colour
- the row's reasons (`planWhy`)
- the row's evidence line (`planEvidence`)

The tile always ends with the issue time and "A lower forecast level does not mean safe water".

- **Files:** `src/dipcast/site/outing.js` (new). It holds the rules and markup, which Node tests, plus `drawOuting` for the page. The hooks are one line in `drawPlan`, one script tag, some CSS in `index.html`, and `plan.js` readPlan/planHash/planKept.
- **Kept where:** in the plan's address as `when=`, `spot=` and `backup=`. Because `dipcast.plan` stores that address string, it is kept there too. There is no new storage key.
- **Migration:** a plan without an outing reads and writes byte for byte as before. A test pins an old string. Odd values are dropped: an unknown `when`, an id over 100 characters, or a backup equal to the spot. A kept outing time is dropped when the plan's day changes, because the time belonged to that day. The spots are kept.
- **Shared links:** a plan address with an outing opens on it. Older pages ignore the new keys. "Share this plan" (the list link) is unchanged and carries no outing.
- **Spots that have gone:** the tile says "A spot in this outing is no longer listed, so it is left out." It does not drop them silently.
- **Without JS:** the plan page needs JS already, and so does this tile.

## 2. What changed since I checked, with evidence (Saved)

`since.js` keeps its one line. Under it, each card now shows the evidence (`sinceEvidence`):

- Which two forecasts were compared, by issue time: "Forecasts compared: issued Mon 07:00 and Mon 15:30."
- The overflows upstream reported discharging now, against then where both are known: "2 overflows upstream reported discharging now, against 0 then."
- Where the count is not known now, why: "a feed upstream is down or has not updated within six hours." This is the new `gap` field in each note.
- For a spot with no overflow upstream: "No live overflow count for this spot."
- For a rating change: whose rating it is, the EA's yearly classification.
- Which overflows are discharging, and since when, where the spot's forecast lists them (`contributors` with a live event, `spillStart`): "2 overflows upstream reported discharging now, against 0 then: Ben Rhydding storm overflow since Mon 08:40, and 1 more." At most two names; the rest as a count. `contributors` holds the overflows that matter most, so it can name fewer than the count. The names are escaped.
- The outing, when this saved spot is the spot or the backup of the outing kept in `dipcast.plan` and its day has not passed: "This is the spot of your outing tomorrow morning." (`sinceOuting`.)
- For a forecast over 8 h old (the page's own STALE_MIN): "This forecast is N hours old, so the change may be out of date."

**Storage:** `dipcast.seen` as before. Each note gains `gap` (boolean). Notes written before this change have no `gap` and still read and compare. A test covers this. A `gap` that is not a boolean reads as not seen.

## 3. Brief versions and a leader's read tick (decision record, prototype)

Under a decision record, on screen only and never printed, a box shows the version. The version is the issue id plus an 8-hex-digit check of the spot's forecast data. The check is FNV-1a over the spot's `spots.json` entry, the day and the issue time, with keys in a canonical order. It tells two versions apart. It is not a security seal, and the box does not call it one.

The leader can tick "I have read version X". If a later forecast makes a new version, the box says "You ticked an earlier version (…) as read on Sat 31 Oct at 07:05. The brief has changed since: read this version before you tick it." The box says plainly that the tick is kept only in this browser and that nothing is sent anywhere. If storage is blocked, it says the tick lasts only until the page closes.

- **Files:** `src/dipcast/site/brief.js` (new, `BriefAck`). The hooks are one guarded line in `record.js` draw, the script tag and CSS in `record.html`, and `RECORD_SCRIPTS` in `build_site.py`.
- **Storage:** `dipcast.briefacks` holds `[{spot, day, issue, hash, at}]`, at most 30, newest kept, one per spot and day. Odd values read as none.

## What it never claims

- That water is safe or clean. "Safe" appears only in "does not mean safe water". The tests check this for the outing tile and the change lines.
- That a time of day has its own forecast. The tile says "The forecast gives one level for the whole of Monday; it does not change between morning and evening." For today, it also says when the chosen time has passed.
- That a change happened without its evidence. Every since line carries the issue times of both forecasts, and what is known or unknown about the overflows.
- That a tick is a record anyone else can see, or proof of who read what.
- **Official advice is not drawn by this PR.** #379 puts each spot's official advice into `spots.json` and `spots-lite.json` (`official`). It is adding one shared compact indicator for the list, Saved, the planner and the record. This PR builds no second display. It leaves one marked hook (below) to call #379's helper once #379 merges.
- Spill start times are said only for the overflows `contributors` lists. Every other discharging overflow is a count with no time.

## Hook for official advice (#379)

`outing.js` has `outingOfficial(s)`, which returns '' for now. Each outing column draws it under the spot's level. After #379 merges, it should return #379's compact indicator for `s`. That is one call, in that one function. The function's comment marks the place.

For "what changed since you checked", whether official advice appeared or cleared since the last look would be one more field in the `dipcast.seen` note. It would be compared in `sinceEvidence`. This is left until #379's `official` shape is final, and is marked in `since.js` beside sinceEvidence.

#388 and `origin/proto/advisory-finder` merge without conflicts (checked with a merge-tree on 27 Oct). #388 does not touch `eatoday.js`. In `index.html` it adds only CSS, a script tag and one line in drawPlan.

## Storage keys

| Key | What | New? |
|---|---|---|
| `dipcast.plan` | The plan's address string, now with `when`, `spot` and `backup` when set | Extended |
| `dipcast.seen` | One note per saved spot; gains `gap` | Extended |
| `dipcast.briefacks` | Read ticks for decision-record versions | New |

The privacy notice (`pages/privacy.html`) now names the outing in the kept plan and the read tick. Ethan should check that wording.

## Tests

- `tests/site_outing.test.cjs`: address and storage migration, odd values, a kept time dropped on another day, time words, the passed-time note, backup choices, missing spots, and the tile side by side (one spot, none, escaping, the "safe" check). It also checks that the page loads and draws it, and covers the service worker's list.
- `tests/site_since_evidence.test.cjs`: evidence with counts, unknown counts and why, no overflow, rating, stale over 8 h, nothing to compare, old notes without `gap`, which overflows and since when, the outing sentence (spot, backup, hour, today, past day, odd text), and the card escaping an overflow name.
- `tests/site_brief.test.cjs`: version stability and FNV-1a reference values, a tick per version, an older version, storage limits and odd values, the box words, the page with storage and with storage blocked, and script order.
- `tests/test_outing.py`: the build copies outing.js, versions it after plan.js, and the offline copy lists it.
- Updated: `tests/site_since.test.cjs` (the note's `gap`, and the card line now with evidence) and `tests/site_record.test.cjs` (script order).

## Open questions for Ethan

1. **Outing tile placement:** it sits at the top of the results, closed until used. Should it go after the groups, like Compare, or show on a spot's own row ("Make this my spot")?
2. **Times offered:** are morning 06–12, afternoon 12–17 and evening 17–21, plus single hours 05–21, right for swimmers? Or are parts of the day alone enough?
3. **Backup suggestions:** the backup list is Saved first, then the plan's spots. Should it suggest the nearest spot at a lower level, as the spot page's "Lower risk nearby" does? That would be a ranking choice the page makes for the swimmer.
4. **Evidence length on Saved cards:** the evidence adds one to three short sentences per changed card. Keep it as it is, or fold it?
5. **The read tick:** should a version tick also show in the sites view (`sites.html`) and in the briefing email (`briefing.py` could print the same check)? Today only the record page has it. Should the box be dropped before any paid pilot, since a club may read a local tick as a record?
6. **Overflow names on Saved cards:** the Saved page draws from `spots-lite.json`, which has no `contributors`. So the names and spill times show only where the full `spots.json` is loaded; on Saved cards today, the evidence gives the count alone. This was checked in the browser on the fixture. Adding the discharging overflows' names and start times to the lite file would cost a few bytes per spot. Do you want that?
7. **Privacy wording:** the two sentences added to `privacy.html` need your read.

## Browser check (26 Oct 2026, fixture preview)

The fixture is a local `spots.json` from 20 Oct with its dates moved on 6 days, issued 21:40. One edit: Port Meadow is set to moderate, with two listed overflows spilling. The pages were written with `build_site.write_pages`. No pipeline, no network.

- **Phone 375 px (app browser pane):**
  - The tile is closed with no saved plan.
  - Keyboard: Enter opens it, Tab reaches each select, focus ring 2 px, focus kept on the select after each redraw.
  - The two columns are 148 px each. No sideways scroll (scrollWidth 375).
- **Link round trip:** choose the time, spot and backup. Copy the address. Clear storage. Open it in a new tab. The same time, spot and backup appear.
- **Refresh:** bare `/plan/` restores the time, spot and backup from `dipcast.plan`.
- **Day changes:**
  - A kept plan from yesterday opens on today with the time dropped and the spot and backup kept.
  - Picking another day on the strip drops the time and keeps both spots.
  - The one-level-a-day sentence stays in both cases.
- **Past time:** evening chosen at 22:48 today says "That time has already passed today."
- **Blocked storage:** with `localStorage` throwing, a redraw and a backup change ran without errors, and the link kept the backup. This was a redraw under a throwing getter, not a fresh page load with storage blocked.
- **Saved cards:** they show the line, then the issue times, the count against then, an unknown count with its reason, and "This is the spot of your outing tomorrow morning." / "This is the backup for …".
- **Decision record:** Space ticks the box. `dipcast.briefacks` holds exactly `{spot, day, issue, hash, at}`. The box is `.screen-only`.
- **Desktop 1440 px (headless Chrome):** the tile sits in the list column, beside the map.
- **Console:** the only errors were from the fixture:
  - the service worker registration failed with "unknown error when fetching the script". `sw.js` parses (`node --check`), so this looks like a limit of the pane's browser on this port (inferred).
  - 404s for `favicon.ico` and `data/overflows/index.json`, which the fixture does not include.
