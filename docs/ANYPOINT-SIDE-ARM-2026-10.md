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
