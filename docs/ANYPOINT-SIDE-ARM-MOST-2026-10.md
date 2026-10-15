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
