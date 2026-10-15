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
