# Map clicks on a side arm: the river the arm leaves (13 October 2026)

Stated before any run on real data. Results are added below the line, and nothing above it changes.

## The fault

#179 placed a listed spot on a side arm at the river the arm leaves. It finds that river near the arm's head (`transport._adopt_at_head`). A map click still uses the old rule (`_adopt_main_channel`): the river link with the most network within 500 m of the click.

At Queen Elizabeth Gardens, Salisbury, that link is the Avon below the Nadder. Checked on the live click files on 13 Oct 2026 (`anypoint.js` run in Node at 51.06767, −1.80218):
- the click counts 34 overflows;
- the four nearest are on the Wylye and the Nadder (Wishford Wilton Road, Barford St Martin ×2, Hanging Langford);
- the spot's own page leaves both rivers out, as the EA's zone of influence does (#202).

## The rule

A click whose old rule moved it to a main channel then takes the side-arm head rule, as a listed spot does.
- The wanted river is the name of the channel the old rule chose: its own name and OS's alternative.
- With no own name, nothing more happens.
- `_adopt_at_head` itself is unchanged.

A listed spot always has a river name (all 105 in `spots.csv` and `spots-osm.csv` do, or are lakes), so this changes map clicks only.

The page cannot walk the network. The build therefore writes, for each small river link, where a click on it moves to, keyed by the channel the old rule chose. The page looks it up, and the API runs the rule itself.

## Checks, stated before the run

Real data means the current code on `river_network.pkl`, mended at load, and an overflow table rebuilt from the `state` release into a scratch folder.

1. **Queen Elizabeth Gardens.** The click at 51.06767, −1.80218 counts the same set of overflows as the spot does, traced with the same code and inputs. None of them has a receiving water naming the Nadder or the Wylye.
2. **The page agrees with the API.**
   - The synthetic tests (`tests/test_anypoint.py`, `tests/site_anypoint.test.cjs`) gain a side arm across a confluence, and pass.
   - On real data, for 200 clicks drawn at random (seed 13) on links whose answer changes, the page's `place` gives the same overflows as `locate_pin` and `upstream_overflows`, within the existing tolerances (6 m, 1e-3 dilution).
3. **Listed spots do not move.** Every listed spot's placement and overflow set are identical before and after.
4. **Size.** I report the growth of `data/anypoint/`. If it exceeds 1 MB, it goes to Ethan before merging.
5. **Reach.** I report:
   - how many links' answers change;
   - the 10 with the largest change in counted overflows, each looked at on the map;
   - any change that looks wrong. If one does, the rule is stopped and the PR says why.

No accuracy test applies: clicks are not scored.

---

## Results

13 Oct 2026. Inputs:
- the current code on `river_network.pkl`;
- an overflow table rebuilt from the `state` release of 13 Oct 03:20 UTC into a scratch folder (14,631 overflows);
- 0 network requests.

**Outcome: the rule fails check 5 and stays off.** It fixes Queen Elizabeth Gardens, but elsewhere it moves clicks onto small parallel channels that share the river's name. The code stays on this branch as a record. Nothing the site uses changes.

### Check by check

1. **Queen Elizabeth Gardens: passes.**
   - The click counts the same 18 overflows as the spot, on the same link.
   - None of them names the Nadder or the Wylye.
   - The old rule counted 34, and 11 of those named the Nadder or the Wylye.
2. **The page agrees with the API: fails as stated, 198 of 200.**
   - The synthetic tests pass.
   - The two disagreements come from the page's lines, which are simplified to 30 m, not from the rule:
     - one click is called a lake centreline at 19 m when the arm is 11 m away;
     - in the other, the River Lark is nearer than the arm on the simplified line, so the page never sees the arm.
   - For comparison, the old rule on both sides disagreed on 20 of the same 200 clicks. Most of those were distances more than 6 m apart, from projecting the click onto a simplified main channel.
3. **Listed spots: pass.** None of the 105 moves.
4. **Size: passes on the second design.**
   - The first design wrote one row per channel the old rule could choose: 95,135 rows. It added 5.08 MB (+37%) and took 1,432 s to build. Most of the time was pandas `.map` on arrow string columns in `_names_match` and `head_of_arm`.
   - The second design does three things:
     - it groups an arm's channels by where they send a click;
     - it names channels as the index does, using link numbers for the 2,766 arms where a name does not settle it;
     - it replaces the two `.map` calls with lists.
   - Result: +0.90 MB (13.59 to 14.49 MB, +6.6%), 68 s.
   - This design was made after the first run's size was seen and before the rerun. The rule did not change.
5. **Reach: fails.**
   - 13,836 small links have a move. At the midpoint of 9,095 of them (a sample, seed 13: all would have taken over 20 minutes), 8,501 clicks move and 1,196 change the set of overflows counted.
   - The ten largest changes:

| Click | Old: channel, network above | New: channel, network above | Overflows, old → new | Looks |
|---|---|---|---|---|
| 52.8756, −1.2739 (Trent, by Sawley) | River Trent, 3,196 km | River Trent, 2,509 km | 427 → 247 | plausible: above the Derwent and Soar |
| 53.5424, −2.3537 (Irwell; the arm is the Manchester Bolton and Bury Canal) | River Irwell, 395 km | River Irwell, 256 km | 231 → 135 | doubtful: a canal, 1.9 km from its head |
| 52.5105, −1.8655 (Tame, Hawthorn Brook) | River Tame, 43 km | River Tame, 15 km | 76 → 20 | unclear |
| 51.3458, −2.1202 (Semington Brook) | "Semington Brook", 390 km | Semington Brook, 45 km | 101 → 15 | unclear: a name on a larger river's link |
| 51.2278, 0.4206 (Medway) | River Medway, 893 km | River Medway, 370 km | 123 → 37 | plausible |
| 54.0158, −1.2205 (Ouse, Mill Sike) | River Ouse, 2,236 km | River Ouse, 1,820 km | 174 → 100 | plausible: above the Nidd |
| 54.0158, −1.2250 (same) | as above | as above | 174 → 100 | plausible |
| 51.1986, 0.3079 (Medway) | River Medway, 420 km | River Medway, **12 km** | 78 → 7 | **wrong** |
| 53.8774, −1.8467 (Morton Beck, Bingley) | "Morton Beck", 285 km | Morton Beck, 7 km | 70 → 0 | doubtful |
| 52.2898, −0.2196 (Great Ouse) | River Great Ouse, 1,316 km | River Great Ouse, **19 km** | 69 → 1 | **wrong** |

### Why it fails

`head_of_arm` takes the channel nearest the arm's head that carries the river's name and has at least `max(5 km, 5 × the arm's own)` of network above it. Arms with nothing above them are common, and for them that floor is just 5 km. OS draws many braided channels of a big river under the river's name, disconnected above, with a few km of network. The nearest of them wins, and the click loses most of the river. This is the case `_adopt_main_channel` was written for.

At Queen Elizabeth Gardens the nearest named channel happens to be the main Avon above the Nadder, so the rule works there.

### What would be needed

- A rule that, among channels of the river's name near the arm's head, takes the one with the most network, not the nearest. Then check that it still separates the Avon above the Nadder from the Avon below at Queen Elizabeth Gardens.
- Or a floor tied to the channel the old rule chose (for example, at least half its network), so that a click never moves to a channel far smaller than the river it was on.

Either is a new rule, and needs a new statement before it is run.

The same weakness could affect listed spots. Today only Queen Elizabeth Gardens and Wolvercote Mill Stream use the side-arm head, and both were checked by hand (#179, #199).
