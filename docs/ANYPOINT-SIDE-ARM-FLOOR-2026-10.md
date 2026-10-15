# Map clicks on a side arm, third try: most network, with a 10% floor (15 October 2026)

Stated before any run. Results go below the line, and nothing above it changes.
Follows `docs/ANYPOINT-SIDE-ARM-MOST-2026-10.md` (#218), whose rule failed its check 5 on one click
on the Test.

## Said plainly first: this threshold was chosen after seeing data

#218's results named this floor as the fix, after its run had shown the Test case (2.3%) and
Queen Elizabeth Gardens (40%). So 10% is tuned to the cases already seen. To keep the test fair:
- the reach check runs only on clicks #218 did not see (below);
- the threshold is not changed after this run, whatever it shows.

## The rule

The same as #218 (of the named channels near the arm's head with enough network, the one with
most), plus one condition. **No move when that channel has under 10% of the network above the
channel the old rule chose** (`_adopt_main_channel`'s pick, the river the click was on before).
The click then stays where the old rule put it. The condition applies wherever the side-arm head
rule does:
- a map click (`_click_at_head`);
- the files the page reads (`build_any_point.arm_heads`, keyed by the old rule's channel);
- a listed spot whose pin the old rule moved (`_apply_river_hint`).

## Checks, stated before the run

The same inputs and script as #218: `river_network.pkl` mended at load, and the overflow table
rebuilt from the snapshot of 13 Oct 03:20 UTC (MD5 5877fc61…). No network requests.

1. **Queen Elizabeth Gardens.** The click counts the same overflows as the spot, none naming the
   Nadder or the Wylye.
2. **The page agrees with the API** on 200 moved clicks drawn from the fresh set (seed 15).
   Allowed misses, each listed:
   - #208's two causes (a lake centreline; a river nearer on the simplified line);
   - #218's constant offset. That is the same overflows under the same name, every distance off by
     one constant (within 1 m), and dilution within 0.005.

   Any other miss fails this check.
3. **Listed spots.** Every listed spot's placement and overflow set are the same as on main.
4. **Size.** The growth of `data/anypoint/` over main. Over 1 MB goes to Ethan before merging.
5. **Reach, on fresh clicks only.** The arms with a move under this rule, minus the 8,111 that
   #218's run sampled (seed 13 over its 13,836). One click at each arm's midpoint, old rule against
   new. Reported: clicks moved, clicks whose overflow set changes, the ten largest changes, and the
   spread of network ratios (new over old).
   - **Fails** if any of the ten largest changes moves a click to a channel with under 25% of the
     old channel's network. The floor stops anything under 10%; the band from 10% to 25% is where a
     braided channel could still slip through. Queen Elizabeth Gardens is 40%.
   - Also reported, not judged: moves where the new channel has over 10 times the old's network
     (#218's Hundred Foot Drain case), and moves whose arm head is over 1 km from the click.
6. **Tests.** `pytest -q` and `node --test`, with a synthetic case for the floor.

If every check passes, the PR still waits for Ethan to merge it, as a change to what map clicks show.

---

## Results
