# Map clicks on a side arm, fourth try: the 10% floor plus a 2 km limit on the arm (15 October 2026)

Stated before any run. Results go below the line, and nothing above it changes.
Follows `docs/ANYPOINT-SIDE-ARM-FLOOR-2026-10.md`, which failed check 5 on the Little Stour. There,
the arm's head was 3.6 km from the click.

## Said plainly first: this is a weak test

- **The limit was chosen after seeing the data.**
  - The failures it targets are known: the Little Stour (head 3.6 km away), Counter Drain (a 4.6 km
    arm), Dam Dike and Fur Water Drain (heads 1.1 and 2.4 km away).
  - Before writing this, the arm at Queen Elizabeth Gardens was measured at 1,217 m, and at Wolvercote
    Mill Stream at 425 m. So the limit is 2 km, not 1 km.
- **No fresh arms are left.** The two earlier runs used the midpoints of all 13,836 arms. This run
  clicks a quarter of the way along each arm instead. Those are new clicks on the same arms, so they
  are not independent of what was seen.
- So a pass here shows the rule does what it was built to do on the data it was built from. It does
  not show the rule generalises. Ethan should weigh it that way before merging.

## The rule

The third try's rule (#218: the named channel with most network, and the 10% floor), plus one
condition. **No move when the arm is longer than 2 km.**
- The arm's length is measured along its links: from its head, the point `_side_arm_head` finds,
  down to the downstream end of the link clicked.
- It depends only on the arm, so the build can apply it when it writes the page's files
  (`arm_heads`). The page needs no change.
- It applies wherever the side-arm rule does: clicks, the page's files and listed spots.

## Checks, stated before the run

Same inputs and script as the earlier runs. Clicks at 25% along each arm with a move, all of them
(no sampling). Page parity on 200 of those (seed 25).

1. **Queen Elizabeth Gardens:** the click counts the spot's overflows, none on the Nadder or the Wylye.
2. **Page and API agree:** 200 of 200, or misses of #208's or #218's listed kinds only.
3. **Listed spots:** none changes placement or overflow set.
4. **Size:** growth of `data/anypoint/` under 1 MB.
5. **Reach.**
   - **Fails** if any of the ten largest changes moves a click to a channel with under 25% of the
     old channel's network.
   - Also reported: the spread of ratios, how many moves have the head over 1 km from the click, and
     how many arms the limit removes.
6. **Tests:** `pytest -q` and `node --test`, with a synthetic case for the limit.

---

## Results

15 Oct 2026. The statement was pushed at 23:02 BST (d6bcdb6), and the code at eadceca, before the run.
- Same inputs as the earlier runs.
- 0 network requests.
- 2,507 s.

**Outcome: fails check 2 as stated, and stays off.** Every other check passes, including check 5,
which failed the last two tries. One page/API disagreement is caused by this rule. Given the stated
weakness of the test, a pass would not have settled it either.

### Check by check

1. **Queen Elizabeth Gardens: passes.** Its arm is 1,217 m, under the limit. The click counts the
   spot's 18 overflows, none on the Nadder or the Wylye.
2. **The page agrees with the API: 197 of 200, fails.** Three misses:
   - **Allowed kind (#218's):** at 52.7364, 0.9520 one overflow's distance differs by a constant
     202 m, with dilution within 0.002.
   - **Not this rule's, but not a listed kind:** at 50.9506, −0.4842 the page finds no river while
     the API finds the Stor with 3 overflows. With main's rule and main's files (no arms), the page
     still finds nothing and the API still finds the Stor. So this is an existing page/API
     disagreement, found here.
   - **This rule's:** at 52.1579, −0.6306 (Great Ouse) the page counts 53 overflows and the API 52.
     With main's rule both say 52. So the page and API apply this arm's move differently.
3. **Listed spots: pass.** None of the 105 moves.
4. **Size: passes.** +0.85 MB (13.85 to 14.70 MB).
5. **Reach: passes.**
   - The limit removes 308 of the 13,836 arms.
   - At 25% along each of the other 13,528, 12,975 clicks move and 423 change the set of overflows.
   - No move falls under 10% of the old network.
   - The ten largest keep 37% to 100% of the old channel's network, or gain. The lowest is the
     Birket (16.5 to 6.1 km). Two gain over ten times: the Lesser Teise (10 to 109 km) and a Test
     click (18 to 217 km).
   - The Little Stour (#218's third-try failure) and #208's long drains no longer move.
6. **Tests:** `pytest -q` and `node --test` pass, with the synthetic arm-limit case
   (`tests/test_placement.py`).

### What this shows

Established:
- With the floor and the 2 km limit, the reach check passes on clicks the rule was not tuned on
  directly: quarter points rather than midpoints. Those clicks are on the same arms, so this is weak
  evidence, as stated.
- One click shows the page and the API disagree on a move under this rule (52 against 53 overflows).
- A separate page/API disagreement exists on main today. On the Stor at 50.9506, −0.4842, the page
  finds no river.

What would be needed before this could merge:
- Find why the page counts one more overflow at 52.1579, −0.6306, and fix the page or the files.
- Look at the Stor click on main. It is a page fault independent of side arms.
- Then rerun check 2 on a new seed. The rule itself would not change.
