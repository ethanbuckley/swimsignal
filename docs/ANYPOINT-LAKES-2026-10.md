# Map clicks by a lake: what a click means, and the page against the API (16 October 2026)

Written 16 October 2026, before the shore sweep was run again. The fixes below were designed from the
misses found on #225 and from the lake geometry alone. Results go below the line at the end. Nothing above
the line changes after a result is seen.

## What a click by a lake means now

The API (`transport._locate`, `_in_polygon`):

1. A click inside, or within 150 m of, a WFD lake outline is that lake.
   - Its lake centreline is the lake links inside the outline.
   - If no lake link is inside, it is the lake centreline nearest **the click**, within 1.5 km, with every
     lake link joined to it.
   - If there is none within 1.5 km, the WFD lake is passed over.
2. Otherwise the nearest river within 1.5 km, or the nearest lake centreline when it is less than twice as far.

The lakes, counted on main's network and WFD file:
- 564 WFD lakes in England. 362 have a lake centreline inside. **202 have none.**
- Of those 202: 116 have a lake centreline within 1.5 km of the outline, 22 within 150 m.

## The misses found on #225

400 clicks 0 to 250 m from WFD lake outlines (seeds 16 and 17). 58 disagreed for reasons that are not river lines.

| Class | Clicks | Page | API |
|---|---|---|---|
| 1. no lake centreline within 1.5 km of the click | 50 | "isolated lake" | the nearest river (up to 436 overflows, River Don) |
| 2. centreline chosen from the lake's middle | 5 | nearest the lake's middle | nearest the click |
| 3. 15 m lake outlines | 1 | 151.1 m, not in Gorpley Reservoir | 149.1 m, in it |
| 4. same lake, 1 overflow against 0 | 1 | see below | |
| distance just over 6 m | 1 | | |

**Class 4 is class 2.** The click is at 53.87095, −1.55872, by Eccup Reservoir. Eccup has no lake link inside
its outline.
- The build gave it the lake link nearest the lake's middle: an 8 m link on Eccup Beck, 10 m off the outline.
  Alwoodley CSO (YWS00197) reaches it.
- The API took the lake link nearest the click: a 10 m link 1,032 m from the outline, with no overflow upstream.

Checked by running the API on the click, and by reading the build's table for Eccup.

## The fixes (the page and the build follow the API)

**Classes 2 and 4.** The build no longer picks a centreline for a WFD lake with none inside. Such a lake is
written with `lake: -1` in `lakes.json`, now meaning "no lake centreline inside". For a click on it the page
takes the lake link nearest the click, within 1.5 km, from the squares' link index, as the API does. With
none, it says "isolated lake", as before (class 1, below).
- The page now loads the squares for such a click.
- The build adds the squares that any lake link within 1.65 km of such a lake touches, so that link is in the
  index. (1.65 km: the 150 m shore rule plus the 1.5 km search.)

**Class 3.** The page keeps the 15 m outlines in `lakes.json`, which every click fetches. Full outlines would
make it 3.47 MB in place of 0.38 MB (0.79 MB against 0.11 MB gzipped).
- Each polygon now also carries `err`: the largest gap between its 15 m outline and the real one (Hausdorff
  distance), plus 1 m for rounding. Median 14 m, largest 26 m.
- The build writes each lake's real outline to `lake_outlines/<n>.json`, at six decimals (0.1 m).
- When a click is within 150 m ± `err` of a lake, or two lakes are too close to call, the page fetches those
  lakes' real outlines and decides on them.
- Holes (islands) stay out. No island in a WFD lake has a point more than 150 m from its water, so a click
  on one is that lake either way.

## The decision for Ethan: class 1

A click within 150 m of a WFD lake that has no lake centreline within 1.5 km of the click. Nothing in the
network links this lake to a river. Many are reservoirs filled by pumping: Island Barn, King George VI and
Church Wilne take river water this way.

Left as it is in this PR: the page says "isolated lake"; the API traces the nearest river.

| Option | A click on the water | A click on the bank, near a river | Change |
|---|---|---|---|
| A. Isolated lake everywhere | isolated lake | isolated lake: a river's overflows are hidden | API |
| B. As if the lake were not there | the nearest river's overflows, for water that is not the river | the river | page |
| C. Inside the outline: the lake. Outside it: as if the lake were not there | isolated lake | the river | both |
| D. Isolated lake, and name the nearest river's forecast beside it | isolated lake, plus a line on the river | the same | page, more words |

- A matches what a listed lake spot already gets (`_locate_lake`). It hides up to 436 overflows from a click
  on a riverbank 100 m from a reservoir.
- B never hides a river. It gives a click in the middle of a sealed reservoir the forecast of a river it does
  not drain to.
- C uses the outline the swimmer clicked on. The 150 m shore band then works differently for these lakes
  than for lakes with a centreline.
- D says the most, and costs the most words on the card.

My recommendation is C: it keeps "isolated" for the water and never hides a river from someone on its bank.
The sweep below counts how many class 1 clicks are inside the outline and how many outside, to show the size
of each option's effect. Nothing is changed for class 1 until Ethan picks.

**A related question.** The API's rule for a lake with no centreline inside, "the centreline nearest the
click", can take an unrelated pond. At Eccup it took a 10 m pond 1 km away over Eccup Beck's own lake link
10 m from the shore. "Nearest the outline" would pick Eccup Beck. That would change the API too, so it is left
for Ethan with class 1.

## How it is checked

- Scripts: `scripts/anypoint_shore_check/sweep.py` and `parity.cjs`, from #225's sweep, with the misses now
  sorted by these classes.
- Fresh seeds 18 and 19. Per seed: 400 clicks on river lines, 400 up to 200 m off them, and 200 clicks 0 to
  250 m from a random WFD lake outline (400 shore clicks in all).
- Files written from one upstream table with main's 30 m river lines and with full lines (#225), so a
  river-line miss is not counted as a lake miss.
- Agreement as on #225: the same name and set of overflows, distance within 6 m, lake distance within 3 m,
  dilution within 0.001.

### What I expect

On the shore clicks, with full river lines:
- Classes 2 and 4: **0** misses.
- Class 3: **0**, or 1 within 1 m of 150 m.
- Class 1: about one click in eight (35 to 65 of 400), as on #225. Clicks like White Mere's join it: the page
  no longer finds a centreline more than 1.5 km from the click.
- Anything else: at most 2. Any other cause found is reported here, not fixed in this PR.

On the river clicks: the same as #225 (with 30 m lines about 1% in the wrong place; with full lines at most 5
misses in 1,600).

---

## Results

Run on 16 October 2026 from commit a46a40d (this branch) and from main 0f6840a, with the same API answers.

### Shore clicks, full river lines (seeds 18 and 19, 400 clicks)

| | main | this branch |
|---|---|---|
| agree | 348 | **349** |
| 1. isolated lake against a river | 48 | **51** |
| 2 and 4. another lake centreline | 2 | **0** |
| 3. outline | 2 | **0** |
| other | 0 | 0 |

As expected. Classes 2 to 4 are gone, and nothing new appeared. The misses that changed:
- **Fixed (2).** Riding Wood Reservoir: 143.7 m from the real outline, which the page missed (class 3). Avon
  Dam Reservoir: 147.2 m from the 15 m outline but over 150 m from the real one, the other way round (class 3).
- **Moved to class 1 (3).** Snodland Reservoir, twice (class 2 on main): the build gave it a centreline from the
  lake's middle; none is within 1.5 km of either click. By the River Wear: 149.4 m from a lake with no centreline. The 15 m outline
  put the click outside it, so the page agreed with the API by accident.

With main's 30 m river lines this branch also has 1 "other nearest link" and 2 "same link, distances off" on the
shore set. Those are #225's, not lakes.

**Seeds 16 and 17 again**, the clicks #225 found: Church Wilne, Chelker, Island Barn, Gorpley and Eccup now
agree. White Mere and King George VI are now class 1, as stated above. All 400: 54 class 1, 1 distance off by
6.1 m (the one on #225), nothing else.

### Class 1, for the decision (seeds 18 and 19)

51 shore clicks, by 38 lakes. The API traces a river for all 51.

| | clicks | the API's river has no overflow | median overflows | most |
|---|---|---|---|---|
| inside the outline | 16 | 7 | 1 | 35 (River Thames) |
| outside, within 150 m | 35 | 17 | 1 | 202 (River Wear) |

So, of the 51:
- **A** (isolated everywhere) hides a river's overflows on 27 clicks (9 inside, 18 outside).
- **B** (as if no lake) gives 16 clicks on the water a river's forecast, 9 of them with overflows.
- **C** (inside: lake; outside: river) hides overflows on 9 clicks on the water, and gives the river to the 35
  on the bank.

One river click (seed 18, by the River Glem, 3 overflows) is class 1 too: river clicks can land within 150 m of
such a lake.

### River clicks

With full lines, 795 of 797 clicks on the line and 792 of 796 off it agree. The misses: 5 with the same link and
a distance just over 6 m (#225's), and the River Glem click above. One click on the line (seed 18) that main
placed by another lake centreline now agrees.

### Cost

- `lakes.json`: 631,549 bytes to 634,103 (the `err` values).
- `lake_outlines/`: 564 files, 3.84 MB in all. A click fetches one only near 150 m from a lake: 24 of the
  1,993 clicks did.
- No new squares: every square a lake link near such a lake touches already had files. The rule stays, for a
  lake far from any overflow (Quiet Water in the tests).

---

## Option C, built (16 October 2026)

Ethan picked option C for class 1. Written before the sweep below was run.

**The rule.** A click within 150 m of a WFD lake that has no lake centreline within 1.5 km of the click:
- on the lake's water (inside the outline of one of its parts, islands included): that lake, isolated;
- on its shore (outside the outline): placed as if the lake were not there, by the river rule.

**Where it is.**
- API: `transport._locate`, step 1. It applies to points with no lake hint. A listed lake spot still goes to
  `_locate_lake`, as before. All 105 listed spots in `spots.csv` and `spots-osm.csv` were placed with main's
  code and this branch's: none moves.
- Page: `anypoint.js`, `place`. Whether a click is on the water is settled on the real outline when the 15 m
  one is within `err` of it (`outlinesNeeded`).
- Islands: no WFD island has a point more than 150 m from its water, so an island click is always that lake.
- The isolated pin now carries the lake's name and area in the API, as the page shows them.

**Not changed.** The lake with no centreline inside still takes the centreline nearest the click (Eccup).

**What I expect** (seeds 18 and 19 as above, and a fresh seed 20; full river lines):
- Class 1: **0** of the 600 shore clicks.
- The 51 class 1 clicks on seeds 18 and 19: the 16 on the water agree as isolated; the 35 on the shore agree
  as river.
- A new kind of miss is possible: a shore click where the page has no squares near (no overflow anywhere
  near), so it says there is nothing to forecast, while the API names a river with no overflows. Both give no
  forecast. I expect at most 3.
- Agree on seeds 18 and 19: at least 395 of 400 shore clicks (main: 349). Seed 20: at least 196 of 200.
- River clicks: the same as main.

### Results
