# Map clicks on a side arm, fifth try: the new rule for clicks only (16 October 2026)

Stated before any run on real data. Results go below the line, and nothing above it changes.
Follows `docs/ANYPOINT-SIDE-ARM-LENGTH-2026-10.md`, whose rerun after merging main passed page parity
(200 of 200) but failed the spot check: compared against main's own code, Wolvercote Mill Stream lost
two overflows and Hurley one, and Buscot Weir and Windermere Lakeside moved link.

## What was known before this was written

- Everything in the earlier documents of this series, including the rerun's numbers above.
- The four spots that differed, and the overflows involved: TWL00057 and TWL00723 at Wolvercote,
  TWL00157 at Hurley.
- **Why the earlier spot checks missed it.** They switched off only the click step, so they compared
  the branch with itself. This one compares with main's code, run in a separate process.
- The Lakeside YMCA difference is not explained. It is a lake spot, which the side-arm rule should not
  reach.

## The rule

There are two rules, one for each caller of the side-arm head.

- **Listed spots (`_apply_river_hint`): main's rule, unchanged.** Of the channels near the arm's head
  that carry the spot's river name and have enough network, take the nearest. There is no floor and
  no length limit.
- **Map clicks (`_click_at_head`, and the page's files written by `build_any_point.arm_heads`): the
  fourth try's rule, unchanged.**
  - take the channel with the most network, not the nearest;
  - no move to a channel with under 10% of the old rule's channel's network;
  - no move from an arm longer than 2 km.

So listed spots should be exactly as on main, by construction. The checks test that.

## Checks, stated before the run

The same inputs as the rerun: `river_network.pkl` mended at load, and the overflow table rebuilt from
the snapshot of 13 Oct 03:20 UTC.

1. **Queen Elizabeth Gardens.** The click counts the spot's overflows, and none on the Nadder or the
   Wylye.
2. **The page agrees with the API.** 300 arms with a move, drawn at random (seed 27) and clicked 35%
   of the way along. Of those whose click moves, the first 200.
   - Allowed misses: #208's two kinds, #218's constant offset, and the cap edge (one overflow counted
     on one side only, within 6 m of 60 km).
   - Any other miss fails.
3. **Listed spots match main exactly.** All 105 in `spots.csv` and `spots-osm.csv`, placed and traced
   with main's code (0d81c37) and with this branch, each in its own process, from the same overflow
   table. The link, placement, mode and set of overflows must all match. **Any difference fails,
   Lakeside included.**
4. **Size.** Growth of `data/anypoint/` under 1 MB.
5. **Reach.** 1,000 arms with a move, drawn at random (seed 28), clicked 35% of the way along.
   - Fails if any of the ten largest changes leaves the click with under 25% of the old channel's
     network, as in the fourth try.
   - Also reported: moves to over 10 times the old network.
6. **Tests.** `pytest -q` and `node --test`, with a synthetic case: a listed spot on a side arm whose
   nearest named channel has under 10% of the network is still placed there, while a click is not
   moved.

If every check passes, the PR waits for Ethan to merge it. It changes what map clicks show and nothing
else.

---

## Results

16 October 2026. The statement was pushed at 10:44 BST (83d496a) and the code at 8c9b613, before the run.
Branch includes main 0d81c37. Same snapshot and network (`b5724303`). 0 network requests. 651 s.

**Outcome: checks 1, 2, 4, 5 and 6 pass. Check 3 fails as stated, on one spot, Windermere Lakeside
YMCA, whose link varies on main itself from run to run. With that variation removed, all 105 spots
match main exactly. Whether that is enough is Ethan's decision.**

### Check by check

1. **Queen Elizabeth Gardens: passes.** The click counts the spot's 18 overflows, none on the Nadder
   or the Wylye.
2. **Page against API: passes, 200 of 200** (seed 27, clicks at 35%). No allowed-kind misses were needed.
3. **Listed spots against main: fails as stated, on Lakeside alone.**
   - 104 of 105 match main exactly: link, placement, mode and set of overflows. Among them are
     Wolvercote Mill Stream, Hurley and Buscot Weir, which differed in the rerun.
   - **Windermere Lakeside YMCA** has the same lake, the same 6 overflows and a different link: main
     F1FA1D90, this branch 3E45C8C5.
   - **Seen after the run.** This is main's own nondeterminism, not this rule:
     - Lakeside placed with main's code under `PYTHONHASHSEED` 1, 2 and 3 gives links 3E45C8C5,
       9E639D5A and 9E639D5A;
     - this branch gives the same three under the same seeds;
     - the rerun this morning had main at 9E639D5A.

     Python orders sets of strings by a per-process random seed, and Lakeside's link comes from a tie
     that this order settles. Its lake and its overflows never change.
   - **With `PYTHONHASHSEED=1` in both processes, 0 of 105 spots differ.**
4. **Size: passes.** +0.85 MB.
5. **Reach: passes.**
   - 1,000 arms (seed 28) at 35%: 950 clicks move and 41 change the set of overflows.
   - The ten largest keep 39% to 100% of the old channel's network. The lowest is the Whitewater, 92
     to 36 km. The largest set change is the Idle (166 to 126 km), which loses 11 overflows.
   - No move goes to over 10 times the old network.
6. **Tests: pass.** `pytest -q`: 736 passed, 4 known Pillow failures. `node --test`: 349 passed.
   This includes the new case: a listed spot takes the nearer named channel, a click the bigger.

### Found on the way

Windermere Lakeside YMCA's link differs from one build to the next on main, because of Python's
per-process hashing. Its overflows do not change. Whether anything shown on its page does was not
checked. That is a separate issue from side arms.
