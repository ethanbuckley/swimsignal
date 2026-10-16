# Map clicks: the page's lines are the API's lines (16 October 2026)

## The fault

A map click at 50.9506, −0.4842, on the River Stor in West Sussex, got two answers on main:
- **API** (`transport.locate_pin`, `upstream_overflows`): the River Stor, link E165DA0C, 3 overflows.
- **Page** (`anypoint.js`, `place`): an unnamed lake centreline, no watercourse, 0 overflows.

It was found on 15 Oct 2026 while testing the side-arm rule (#218). It happens with main's rule and main's files, so it is not caused by side arms.

## The cause

The build simplified every river line to 30 m before writing `link_index/` (`SIMPLIFY_M`). The page measures a click against those lines. The API measures it against the network's own lines.

At this click:
- The click is 0.001 m from a short unnamed link (140 m long). Its simplified line is 24.5 m away.
- A lake centreline is 35.2 m away, in both.
- The rule (`_locate`): take the lake when its distance × 0.5 is under the river's.
  - API: 17.6 m against 0.001 m. River. The link has little network above it, so the Stor 170 m away is adopted (`_adopt_main_channel`).
  - Page: 17.6 m against 24.5 m. Lake. The lake has no overflow above it.

Checked by running both on this click: Python on `river_network.pkl`, and Node on files built from the same table.

## The fix

The build writes every vertex of every line (`scripts/build_any_point.py`, `write_files`). No change to the page.

Size, with the same table and inputs:

| | 30 m lines (main) | full lines |
|---|---|---|
| `data/anypoint/` | 13.85 MB | 19.51 MB |
| `link_index/` | 5.84 MB | 11.50 MB |
| one square, average | 17 KB | 34 KB |
| one square, largest | 48 KB | 82 KB |

A click fetches the squares within 1.6 km of it: one to four.

Smaller tolerances were measured too. 10 m saves 1.3 MB and still has wrong places. 5 m saves 0.04 MB. So the lines are not simplified at all.

## How common it was

Method:
- Run on 16 Oct 2026 on main at ae6e79c (before #223 and #224).
- One upstream table, built from main's code into a scratch state folder. Files written from it with 30 m lines and with full lines.
- Clicks on river links that have an overflow upstream, chosen in proportion to length. Two seeds (16, 17), 400 clicks each per set:
  - **on**: on the line;
  - **off**: 0 to 200 m off it, in a random direction.
- Each click traced by the API (main's rule), then placed by `anypoint.js` on the files.
- Agreement as in the side-arm checks: the same name and set of overflows, distance within 6 m, lake distance within 3 m, dilution within 0.001.
- 12 clicks outside England were left out.

### Main (30 m lines)

| | on | off |
|---|---|---|
| clicks | 793 | 795 |
| agree | 383 | 318 |
| **wrong place**: another nearest link | 1 | 8 |
| **wrong place**: lake centreline, not river (the Stor's kind) | 1 | 2 |
| **wrong place**: another main channel adopted | 0 | 4 |
| same link, distances off | 408 | 463 |

- **Wrong place: 16 of 1,588 clicks (1%).** The page counts another river's overflows, or none. Full lines fix 15 of them. The 16th is the adopt radius (below).
- **Same link: the page's distances are off.** The page reads its place along the simplified line, which is shorter than the real one.
  - 731 differ in distance only, 136 in distance and dilution, and 4 in the set of overflows. With full lines all 871 agree.
  - Over all same-link clicks the distance error is 6.8 m at the median, 28 m at the 90th percentile and 482 m at most. Dilution is off by at most 0.014.

### Full lines

| | on | off |
|---|---|---|
| clicks | 793 | 795 |
| agree | **793** | **791** |
| another main channel adopted | 0 | 1 |
| distance off by 6.5 to 7.2 m | 0 | 3 |

Distance errors on the same link: 3.8 m at the median, 7.2 m at most. Dilution: at most 0.0001.

The four misses left are not about lines:
- **Adopt radius (1).** On the Teise at 51.1649, 0.4541, a link is 499.7 m from the click. The API looks for main channels inside a 500 m buffer, which shapely draws as a 32-sided polygon. That polygon falls up to 2.4 m short of 500 m between its corners. So the API leaves the link out and the page takes it.
- **Distance just over 6 m (3).** Base distances are stored in tens of metres, so up to 5 m off. The page's flat local frame adds about 3 m on a 19 km straight drain (the Old Bedford River).

## Not fixed here: clicks near lake shores

Also run: 400 clicks 0 to 250 m from the outlines of WFD lakes (same seeds). Full lines change nothing here.
- **50 of 400: the page says "isolated lake", the API traces a river.** The WFD lake has no lake centreline. The page then treats the click as that lake, which has no river connection. The API falls through to the nearest river. This is the page's design (the API does the same only for a listed lake spot). But within 150 m of the shore it can hide a river's overflows: up to 436 on the Don.
- **5: a WFD lake with no centreline inside it.** The build gives it the centreline lake nearest the lake's middle, if within 1.5 km. The API takes the one nearest the click, if within 1.5 km.
  - Church Wilne, Chelker and Island Barn: one is 1.42 to 1.44 km from the click but over 1.6 km from the middle. The page says isolated; the API says lake.
  - White Mere and King George VI: one is 1.3 km from the middle but over 1.5 km from the click. The page says lake; the API traces a river.
- **1: the 15 m lake outlines.** Gorpley Reservoir: the click is 149.1 m from the real outline and 151.1 m from the simplified one, against the 150 m shore rule.
- **1: not yet classified.** Both say the same WFD lake, but the page counts 1 overflow and the API 0.
- **1: a distance off by 6.1 m**, as above.

These need a decision on what a click by a lake should mean, so they are left for another PR.
