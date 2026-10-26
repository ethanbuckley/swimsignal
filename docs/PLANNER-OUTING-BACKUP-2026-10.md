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
- **Today's EA advice is not part of the evidence.** It is not in `spots.json`. The EA panel loads only when its fold opens (`eatoday.js`). The line cannot say "EA advice appeared" without a new request, so it says nothing about it.
- **Spill start times ("spilling since 09:10") are not said.** `spots.json` has counts, not start times.

## Storage keys

| Key | What | New? |
|---|---|---|
| `dipcast.plan` | The plan's address string, now with `when`, `spot` and `backup` when set | Extended |
| `dipcast.seen` | One note per saved spot; gains `gap` | Extended |
| `dipcast.briefacks` | Read ticks for decision-record versions | New |

The privacy notice (`pages/privacy.html`) now names the outing in the kept plan and the read tick. Ethan should check that wording.

## Tests

- `tests/site_outing.test.cjs`: address and storage migration, odd values, a kept time dropped on another day, time words, the passed-time note, backup choices, missing spots, and the tile side by side (one spot, none, escaping, the "safe" check). It also checks that the page loads and draws it, and covers the service worker's list.
- `tests/site_since_evidence.test.cjs`: evidence with counts, unknown counts and why, no overflow, rating, stale over 8 h, nothing to compare, and old notes without `gap`.
- `tests/site_brief.test.cjs`: version stability and FNV-1a reference values, a tick per version, an older version, storage limits and odd values, the box words, the page with storage and with storage blocked, and script order.
- `tests/test_outing.py`: the build copies outing.js, versions it after plan.js, and the offline copy lists it.
- Updated: `tests/site_since.test.cjs` (the note's `gap`, and the card line now with evidence) and `tests/site_record.test.cjs` (script order).

## Open questions for Ethan

1. **Outing tile placement:** it sits at the top of the results, closed until used. Should it go after the groups, like Compare, or show on a spot's own row ("Make this my spot")?
2. **Times offered:** are morning 06–12, afternoon 12–17 and evening 17–21, plus single hours 05–21, right for swimmers? Or are parts of the day alone enough?
3. **Backup suggestions:** the backup list is Saved first, then the plan's spots. Should it suggest the nearest spot at a lower level, as the spot page's "Lower risk nearby" does? That would be a ranking choice the page makes for the swimmer.
4. **Evidence length on Saved cards:** the evidence adds one to three short sentences per changed card. Keep it as it is, or fold it?
5. **The read tick:** should a version tick also show in the sites view (`sites.html`) and in the briefing email (`briefing.py` could print the same check)? Today only the record page has it. Should the box be dropped before any paid pilot, since a club may read a local tick as a record?
6. **Privacy wording:** the two sentences added to `privacy.html` need your read.
