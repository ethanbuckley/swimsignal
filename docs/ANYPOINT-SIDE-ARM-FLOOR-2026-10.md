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

15 Oct 2026. The statement was pushed at 21:29 BST (b5d4149), and the code at d03395c, before the run.
- Same inputs as #218.
- 0 network requests.
- 1,019 s.

**Outcome: fails check 5 as stated, and stays off.** Every other check passes, including page parity
at 200 of 200. One of the ten largest changes on fresh clicks lands between the floor and the 25% line.

### Check by check

1. **Queen Elizabeth Gardens: passes.** The click counts the spot's 18 overflows, none on the Nadder
   or the Wylye.
2. **The page agrees with the API: passes, 200 of 200** (seed 15, fresh moved clicks). Neither
   #208's misses nor #218's constant offset came up in this sample.
3. **Listed spots: pass.** None of the 105 moves. Queen Elizabeth Gardens keeps 40% and stays above
   the floor.
4. **Size: passes.** +0.88 MB (13.85 to 14.73 MB).
5. **Reach, on fresh clicks: fails.**
   - #218's run had sampled 8,111 of the 13,836 arms with a move. The other 5,725 are fresh.
   - At their midpoints, 5,363 clicks move, and 271 change the set of overflows counted.
   - Network ratios (new over old), over the 5,363:

| Under 0.10 | 0.10–0.25 | 0.25–0.5 | 0.5–0.9 | 0.9–1.1 | Over 10 |
|---|---|---|---|---|---|
| 0 | 2 | 13 | 270 | 5,069 | 2 |

   - The failing case is in the ten largest:

| Click | Old channel, network | New channel, network | Overflows | Ratio | Head from click |
|---|---|---|---|---|---|
| **51.3240, 1.2561** | **Little Stour, 240 km** | **Little Stour, 37 km** | **34 → 1** | **0.154** | **3.6 km** |

   - The other nine are 0.43 to 1.0. Among them: the Aire (1,209 to 515 km, at 0.43), the Ouse
     (0.78), the Thames at Oxford (0.70), the Colne (0.80), and a Test click gaining 9 overflows
     (13.8 to 182 km).
   - Also reported: 90 of the 5,363 moved clicks have the arm's head over 1 km from the click.
     2 move to over 10 times the old network.
6. **Tests:** `pytest -q` 717 passed, 4 known Pillow failures; `node --test` 342 passed.

### What this shows

Established, from the run:
- The floor removed every move under 10%.
- Parity is clean.
- Fewer than 1 in 300 fresh moves (15 of 5,363) land under 50% of the old network.

The case that failed has the arm's head 3.6 km from the click, as #218's Test case had it 362 m away.
Inferred, not tested: the remaining errors come from **how far the arm runs**, not from which
channel is picked. A click on a long drain or arm is sent to wherever that arm leaves a river, which
can be kilometres away and up a different reach. 90 fresh clicks moved over 1 km.

### What would be needed

A limit on the distance from the click to the arm's head (for example 1 km) is the next candidate.
It is new, and it was seen in this run's data, so it needs its own statement and clicks that no run
has seen. The pool of unseen arms is now empty: #218 sampled 8,111 and this run took the other 5,725.
A fair test would need another way to get fresh cases, for example clicks at other points along
the arms (this run used midpoints only), or a later network release.
