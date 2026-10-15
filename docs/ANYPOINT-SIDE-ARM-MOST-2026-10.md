# Map clicks on a side arm, retry: the named channel with the most network (15 October 2026)

Stated before any run on real data. Results are added below the line, and nothing above it changes.
Follows `docs/ANYPOINT-SIDE-ARM-2026-10.md` (#208), whose rule failed its check 5 and stayed off.
This branch is #208's with main merged in (5d68a03).

## What #208 found

#208 sent a map click on a side arm to the river the arm leaves, as a listed spot is sent
(`head_of_arm`). Of the channels near the arm's head that carry the river's name and have at least
`max(5 km, 5 × the arm's own)` network above them, it took the **nearest**. OS draws many braided
channels of a big river under the river's name, disconnected above, with a few km of network. The
nearest of those often won, and the click lost most of the river: on the Medway a click went from
420 km of network to 12 km, and on the Great Ouse from 1,316 km to 19 km.

## What was looked at before this was written

- **Queen Elizabeth Gardens.** With main's code on the same network, the arm under the click
  (51.06767, −1.80218) has no network above it. Within 500 m of its head, exactly one channel
  carries "Avon": the Avon above the Nadder, 77 m away, with 130.4 km of network. The old rule's
  channel, the Avon below the Nadder (324.0 km), is not within 500 m of the head. So a rule that
  takes the most network among those candidates still sends this click above the Nadder.
- A second rule was considered: a floor of half the old rule's channel's network. It was dropped
  because it fails here (130.4 / 324.0 = 0.40) before any run.
- Nothing else was run.

## The rule

`head_of_arm` is unchanged except for the last step. Among the candidates it already keeps (river
forms, within `ADOPT_RADIUS_M` (500 m) of the arm's head, carrying the wanted name, with at least
`max(ADOPT_MIN_M, ADOPT_RATIO × own)` network), it takes the one with the **most network above
it**, not the nearest. Ties go to the nearer. Everything else in #208 stays:
- the click path (`_click_at_head`);
- the files the build writes;
- the page.

Listed spots use the same function. So their placements are checked too (check 3).

## Checks, stated before the run

The same inputs as #208's run, so the two compare:
- `river_network.pkl`, mended at load;
- the overflow table rebuilt from the `state` release of 13 Oct 03:20 UTC (`live_latest.parquet`,
  MD5 5877fc61…) into a scratch folder;
- #208's run script, with only the rule changed.

1. **Queen Elizabeth Gardens.** The click counts the same overflows as the spot, and none has a
   receiving water naming the Nadder or the Wylye.
2. **The page agrees with the API.** For 200 clicks drawn at random (seed 13) among those that move,
   the page's `place` gives the same overflows as Python, within #208's tolerances (6 m,
   1e-3 dilution). #208 got 198 of 200, with both misses from the page's 30 m line simplification.
   The same two causes are allowed and listed. Any other cause fails this check.
3. **Listed spots.** Every listed spot's placement and overflow set are the same as on main.
4. **Size.** The growth of `data/anypoint/` over main is reported. Over 1 MB goes to Ethan before merging.
5. **Reach.** Reported as #208 did: links with a move, midpoint clicks moved, and clicks whose
   overflow set changes, with the ten largest changes.
   - **Fails** if any of the ten moves a click to a channel with under 10% of the network of the
     channel the old rule chose. #208's two wrong cases were 2.9% (Medway) and 1.4% (Great Ouse).
   - Also reported: how many of all moved midpoint clicks fall under 10%.
   - Also reported: where #208's ten clicks go under this rule.

No accuracy test applies: clicks are not scored. If every check passes, the PR still waits for
Ethan to merge it; if any fails, it stays a record, as #208 did.

---

## Results

15 Oct 2026. Run after b44d8a0 was pushed (19:57 BST). Inputs:
- #208's run script, with only the rule changed and three reports added;
- `river_network.pkl` mended at load, and the overflow table rebuilt from the same snapshot (14,631
  overflows);
- branch code with main merged;
- 0 network requests;
- 1,302 s.

**Outcome: the rule fails check 5 as stated and stays off.** It removes #208's braided-channel
losses: none of #208's ten moves a click to a small channel now. But one new case in the ten does:
on the Test, the river itself is not within 500 m of the arm's head. Check 2 also has two misses
of a kind not in #208's list.

### Check by check

1. **Queen Elizabeth Gardens: passes.** The click counts the same 18 overflows as the spot, on the
   same link (the Avon above the Nadder). None names the Nadder or the Wylye. The old rule counted
   34, 11 of them on those rivers.
2. **The page agrees with the API: 198 of 200, and the two misses are a new kind.**
   - In both, the page and Python count the same overflows under the same name. Every distance is
     off by one constant: 182 m on an arm at 51.2252, −1.7861 (Avon), and 132 m at 51.0471, −1.3157
     (Itchen). One dilution moves by 0.002.
   - #208's two misses were a different kind: a lake centreline, and a river the simplified line
     put nearer than the arm.
   - Inferred, not checked: a constant offset along the river looks like the head being placed on
     the page's simplified line of a long, winding link, a third effect of the 30 m simplification.
     As stated, only #208's two causes were allowed, so this check is not passed.
3. **Listed spots: pass.** None of the 105 moves.
4. **Size: passes.** +0.88 MB (13.85 to 14.73 MB, +6.3%), under the 1 MB limit.
5. **Reach: fails.**
   - 13,836 small links have a move. At the midpoint of a sample of 8,111 (seed 13; the script
     samples when the full set would take over 20 minutes), 7,591 clicks move. 408 change the set of
     overflows counted; #208 changed 1,196 of its 9,095.
   - Moves to a channel with under 10% of the old channel's network: **2 of 7,591**.
   - The ten largest changes:

| Click | Arm; click to its head | Old channel, network | New channel, network | Overflows | Ratio |
|---|---|---|---|---|---|
| 52.8756, −1.2739 | unnamed, 39 m; 274 m | Trent, 3,196 km | Trent, 2,511 km | 429 → 245 | 0.79 |
| 54.0158, −1.2205 | Mill Sike; 415 m | Ouse, 2,236 km | Ouse, 1,820 km | 175 → 101 | 0.81 |
| 54.0158, −1.2250 | Mill Sike; 124 m | Ouse, 2,236 km | Ouse, 1,820 km | 175 → 101 | 0.81 |
| 52.4346, 0.1403 | Counter Drain, 4.6 km; 3.2 km | Old Bedford River, 13 km | Hundred Foot Drain (New Bedford River), 3,192 km | 1 → 44 | 249 |
| 52.9484, −1.0691 | unnamed, 1.2 km; 642 m | Trent, 3,421 km | the same link, nearer its head | 324 → 356 | 1.00 |
| **50.9379, −1.4865** | unnamed, 752 m; 362 m | **Test, 391 km** | **Test, 9 km** | **22 → 1** | **0.023** |
| 52.7384, −1.7609 | unnamed, 946 m; 459 m | Trent, 320 km | Trent, 303 km | 51 → 51 | 0.95 |
| 53.7019, −1.0023 | Dam Dike, 2.2 km; 1.1 km | Aire, 1,284 km | Aire (Lady Gime Reach), 1,282 km | 154 → 173 | 1.00 |
| 53.5661, −1.0842 | Fur Water Drain; 2.4 km | Don, 736 km | Don (Flood Drain), 728 km | 360 → 378 | 0.99 |
| 53.6634, −1.7551 | unnamed, 864 m; 422 m | Colne, 170 km | Colne, 136 km | 108 → 92 | 0.80 |

   - **Where #208's ten go now.** Medway (420 km), Great Ouse (1,316 km), Morton Beck, Semington
     Brook, the Tame and the Medway at 893 km all keep the old channel's network (ratio 0.96 to
     1.00). The Irwell keeps 390 of 395 km. The Trent and the Ouse move as #208 had them (0.79,
     0.81: above the Derwent and Soar, and above the Nidd).

### Why it fails

The rule chooses only among channels within 500 m of the arm's head. On the Test at 50.9379,
−1.4865, the head of a 752 m unnamed arm is 362 m from the click. Near that head the only Test
channel with enough network has 9 km above it. The 391 km Test the old rule chose is near the
click, not near the head.

Inferred, from the network's names and lengths only, not looked at on a map:
- **Hundred Foot Drain.** Its ratio of 249 is the other way round: from the Old Bedford River to the
  New Bedford, two parallel channels of the Ouse Washes. Both carry "Bedford", so the name allows
  it. Whether a click on Counter Drain should count the Great Ouse's 44 overflows is not settled.
- **Dam Dike and Fur Water Drain** are drains whose heads lie 1.1 and 2.4 km from the click. That is
  a long way to move a click, though the river and its overflows barely change.

### What would be needed

A rule that never moves a click to a channel with far less network than the old rule's would
stop the Test case. For example, the most network as here, but no move when the result is under
10% of the old channel's. Queen Elizabeth Gardens (40%) would still move.

That threshold was chosen after seeing this run. A test of it would need a statement saying so, and
clicks this run did not see: the arms outside this sample, or another seed.

The page's constant offsets (check 2) need a look at how the page places a head on a long link
before any rule is merged.
