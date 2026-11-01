# Lake E. coli range: a wording proposal and a shadow log

Written 1 November 2026, register row **3 / LAKE-CONC**, after the test in
[LAKE-RANGE-HINDCAST-TEST-2026-11.md](LAKE-RANGE-HINDCAST-TEST-2026-11.md) (#584) passed all three of its stated
conditions. That test's rule for a pass: a wording proposal for Ethan, a shadow log at lake spots, and the 2027 lake
samples as the prospective check. This PR does the second and proposes the first. **It shows nothing new on any page.**

## 1. What the site does at lakes today

Every build computes the over-900 chance at a lake spot, as at a river spot. The page hides it (`ecoliTested` in
`levels.js` excludes lakes; the day table says "n/a", "Not validated on lakes"). That stays: the over-900 chance cannot
be judged at lakes (9 results over 900 in the 962 test rows).

## 2. The shadow log (this PR)

- **Model:** `lake-range-v1`, the tested candidate, frozen in `data/processed/ecoli_lake_range.json` (SHA-256 pinned in
  `src/dipcast/shadow_lake_range.py`; written by `scripts/lake_range_hindcast.py export`). The file holds the reference
  model too: the lake's typical range with no weather, the test's background. The 2027 read never refits either.
- **Where:** every forecast at a lake spot (`pin.mode == "lake"`) that is logged. A spot within 100 m of a lake bathing
  water's position in `spots.csv` uses that bathing water's own level (11 lake bathing waters have one). Any other lake
  uses the average lake's level, `basis` "average lake".
- **What:** one row per day from lead 0: the most likely reading (`median`), the range 8 in 10 samples would fall in
  (`low`, `high`, E. coli per 100 ml), the inputs (`rain_48h`, `rain_24h`, `risk`), `in_season` (May-September),
  `bw_id`, `basis`, the rule, the model hash and the forecast version. Table `shadow_lake_range_v1` in the state database.
- **Cost:** no request. It reads the inputs the spot's E. coli figure already has.
- **Safety:** it returns new arrays, never alters its inputs, and runs inside guards that log and carry on. Without the
  file, or with a file of another hash, it is off. No page, alert, level or published score reads the table.
- **Checked:** `tests/test_shadow_lake_range.py`. The site's code reproduces the research script's medians and ranges
  to one part in a million at two bathing waters and at an unsampled lake. One real forecast (Windermere, Millerground
  Landing, 1 Nov 2026, scratch copy) wrote five rows: most likely about 7 per 100 ml, 8 in 10 between under 10 and
  about 55, each marked out of season.

## 3. The 2027 read, fixed now

- **Rows:** every EA sample with an E. coli count, 1 May to 30 September 2027, at a lake bathing water in the file.
  Each is paired with the shadow row for its day issued last before its sample time (lead 0); lead 1 is reported too.
  A sample with no such row is counted, not filled.
- **Conditions,** as the test's, ISO-week bootstrap, 2,000 resamples, seed 0:
  1. the central 80% range holds 70-90% of results (lead 0);
  2. the log score is above the frozen background's, interval above zero. Both are computed from the frozen file and
     the logged inputs;
  3. each water body (Windermere, Coniston, Derwent Water, Rutland, Frensham) holds at least 60% inside the range.
- **Reported whatever the result:** by site and by month; lead 1; "average lake" rows have no EA samples to judge,
  and are counted only.
- **Read on or after 15 October 2027.** This is a separate, versioned log. It does not touch the 2027 primary
  evaluation.

## 4. Wording: Ethan's decision

**Where and when (recommended A):**

| | Shows the range | Shadow only |
|---|---|---|
| **A (recommended)** | From 1 May 2027, May-September, at the five lake bathing waters the test covered: Windermere ×4, Frensham | Every other lake, until the 2027 read |
| B | Nowhere until the 2027 read | Every lake |
| C | From 1 May 2027 at all 11 lake bathing waters with their own level (adds Coniston ×3, Derwent Water, Rutland ×2, not in the 2012-22 test) | Every other lake |

A shows only what was tested. C adds lakes whose levels come from two or three seasons and were not in the unseen
test. Winter is out in every option: the EA takes no samples from October to April, so the range is untested then.

**Words (proposed, for the tile and the day table):**

- Tile label: **E. coli estimate**. Figure: **about 20** (per 100 ml). No risk band and no colour.
- Line: "A sample today would most likely read **about 20** E. coli per 100 ml. 8 in 10 would read between **under 10**
  and **170**."
- Basis, one line: "From this lake's own Environment Agency samples since 2023, rain at the lake and spills upstream.
  Tested on 2012-2022 samples it never saw: 79% fell inside its 8-in-10 range."
- For comparison, one line: "England rates an inland bathing water Excellent when about 95 in 100 of its samples are
  under 500 per 100 ml, over four seasons."
- Rounding: two significant figures. Anything under 10 reads "under 10", the lab's own limit.
- Day table: the column shows "about 20 (under 10–170)" at a lake where option A or C shows it, and stays "n/a" elsewhere.

**What it does not do (proposed):**

- It does not set the level, the colour or an alert. A lake's level stays the spill risk's.
- No over-900 percentage at lakes.
- The official advice and the water's classification stay above it.
- No "safe" or "clear" wording. A low reading is a likely sample, not a clearance.

## 5. Continuation record

| Field | Content |
|---|---|
| Identity | LAKE-CONC; owner: Claude session "ecoli-estimate-lakes"; this PR; `src/dipcast/shadow_lake_range.py`, `data/processed/ecoli_lake_range.json` |
| Evidence | #584: all three conditions passed on 962 unseen lake rows (Windermere, Frensham); gain from three Windermere sites |
| Stage and claim | Shadow from merge; no display |
| Next deliverable | Ethan's choice of A, B or C and the words; then the display PR, before 1 May 2027 |
| Milestone | 2027 read on or after 15 Oct 2027 (section 3) |
| Release route | Display behind Ethan's choice; fallback is today's "n/a"; removing the file turns the shadow off |
