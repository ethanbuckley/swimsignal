# Arrival guide (prototype, 30 October 2026)

A spot's practical guide, shown as a journey for someone who has never been there. It is behind an opt-in,
`?arrive=1` on a spot's address (`spot/<id>/?arrive=1`). Without it the page draws nothing new and does not ask
for `arrive.js`. With it, the arrival tile takes the "Practical guide" tile's place (same id, `guide`, so the notes
on a visit and the reviews still mount after it); on a phone the "At the water" fold that holds it opens.

Code: `src/dipcast/site/arrive.js` (the tile, using `guide.js`'s `guideRuns`, `guideChecked` and `guidePhoto`),
a small hook in `src/dipcast/site/index.html` (`ARRIVE`, `mountArrival`, and its CSS after the guide's), one line
each in `scripts/build_site.py` (`SHELL_SOURCES`, `copy_app_files`) and `src/dipcast/site/sw.js` (SHELL), as for
`replay.js`. Test: `tests/site_arrive.test.cjs`. One new guide topic, `transport` ("Bus and train"), in
`src/dipcast/guides.py`, `guide.js` and `guides/README.md`.

## The user task

> I have never been here. Get me from the car park or bus stop to the water, in and out, and tell me what nobody
> has checked.

## Success measure

A first-time visitor can follow the tile in order (arrive, path, entry, exit, seasonal limits) and can name, from
the page alone:

1. which facts are verified, by whom (the linked publisher under each fact) and when (the tile's first line: the
   day every verified fact was last checked, and whether from published pages or on site);
2. which facts come from a dated record rather than a current page ("Source: Defra, December 2020");
3. which facts are a swimmer's word ("A swimmer's suggestion, from Sam, 12 Sept 2026. Not yet checked by
   SwimSignal.");
4. which things are not known at all ("Nothing in this guide yet." at the step, and again under "What nobody has
   checked").

Permission to swim, physical access and water conditions stay in three separate parts ("The way there and back",
"Who can swim here", "The water") and are never joined into one verdict. Nothing in the tile says or implies
"safe"; `tests/site_arrive.test.cjs` fails on the word.

This has not been tested with a first-time visitor. The measure is written so that it can be: give someone the
page at 375 px, ask them to say the route aloud and to sort ten facts into verified, swimmer's word and unknown.

## Which spot, and why

**Wharfe at Cromwheel, Ilkley (`bw-uke4100-08901`).** Chosen over Windermere, Waterhead
(`osm-windermere-waterhead`) because:

- It is a designated bathing water (the Environment Agency's profile; `spots.csv` lists it as `designated`).
  Waterhead is a point from OpenStreetMap, and `access.py` says access and permission at that entry point have not
  been confirmed.
- Its guide has facts on the steps a visitor walks: parking (2), the path (2) and getting in (1). Waterhead's 11
  facts are parking (2), toilets (1), the lake's rules (7) and paddling (1); it has no fact on the path, getting
  in or getting out, so as a journey it would be almost all gaps.
- Ilkley has a railway station in the town and buses from Leeds; both now have a fact from the operator's own
  page (below).

Not checked: how many people visit either spot, on the site or on the water. "Frequently visited" rests on
Cromwheel being a designated bathing water and on Waterhead being the spot used in the social posts, not on
visit counts.

## What the page shows

At 320, 375 and 1440 px (screenshots listed at the end):

1. **Arriving for the first time** (the tile's label, with the guide's signpost icon). The guide's checked line,
   then a count: "In this guide: 9 facts verified, 2 from dated records, none a swimmer's word; 9 published pages
   in all. Photos: 3 historical, by other photographers; none taken by SwimSignal."
2. **The way there and back**: the two overview photos (Geograph 6979159 and 7486475), then the numbered steps:
   1. Getting there: "By bus or train" (2 facts), "By car" (2 facts), then a link to Traveline's journey planner
      for times. The link is not a fact.
   2. From the road to the water (2 facts). "No photo yet of the path to the water."
   3. Getting in (1 fact). "No photo yet of the place to get in." Geograph 7486475 shows gravel upstream of the
      bridge, but no source says that is where people get in, so it is an overview photo, not this step's.
   4. Getting out: "Nothing in this guide yet." "No photo yet of the place to get out."
   5. Toilets and changing: Toilets (2 facts, one a dated record); Changing, nothing yet.
   6. Seasons, opening times and fees: nothing yet. (The toilets' summer and winter hours stay under Toilets,
      where the guide put them: no fact is moved or reworded.)
   A photo sits only in the step of its `topic`: the overview does not fill the path's or the exit's gap.
3. **Who can swim here**: "A path, a car park or a beach is not permission to swim. This part says only what its
   sources say." Then the guide's two `rules` facts (Defra's 2020 decision; Bradford's parks events rule) and,
   where `access.py` has one, the desk check of access in its own words. Then "A sign in a historical photo is as
   it was that day: what it says now, and what stretch it covers, are not verified." and the sign's photo
   (Geograph 7922212).
4. **The water**: a link to the forecast at the top of the page. Nothing about the water is restated.
5. **What nobody has checked**: each step or part with nothing; the photos not taken; four questions the guide's
   format has no place for (depth where you get in, a step-free route, distance on foot from the stop, station and
   car parks, phone signal); any suggestions not checked; what the sign in the November 2024 photo says now, what
   it covers and whether it is still there; whether the places in the historical photos look the same today; and,
   for a desk-checked guide, "No on-site check is recorded for this guide".
6. "Been here? Tell us what you found", to the feedback form set to a guide.

Under every historical photo, on this tile and on the usual one: "Historical photo by Oliver Dixon, taken 16 May
2023: Foot suspension bridge over the River Wharfe [linked] on Geograph. Licensed under CC BY-SA 2.0 [the deed];
Re-encoded as a JPEG at the same size, 640 x 480, with all metadata removed. This copy is also under CC BY-SA 2.0.
Not taken by SwimSignal. It shows that day only, not today's access, permission, water level or conditions." It
never says "Verified" or "seen on site".

## Facts added to the Cromwheel guide

Two facts, topic `transport`, both `confirmed` from the operator's own page, opened on 30 October 2026:

| Fact | Source |
| --- | --- |
| Northern's page for Ilkley station (Station Plaza, LS29 8HF) lists direct trains to Leeds and to Bradford Forster Square, and says there is level access to both platforms. It lists no toilets at the station. The page does not mention the river or the bathing site. | Northern, https://www.northernrailway.co.uk/stations/ilkley |
| First Bus says its X84 runs from Ilkley to Leeds city centre, and gives the usual travel time between them as 1 hour 25 minutes. The page names no stop near the bathing site. | First Bus, https://www.firstbus.co.uk/west-yorkshire/your-services/featured-services/x84 |

The trains to Leeds and Bradford Forster Square are from the page's live departure list, read at about 18:50 on
30 October 2026; "Level access to both platforms", "Toilets No" and the address are in the page's facilities and
accessibility sections.

Because a fact was added, every other confirmed fact was rechecked against its page the same day, and `checked`
moved from 2026-10-20 to 2026-10-30: the Environment Agency profile (path; shingle beach), Bradford Council's
Riverside Gardens leaflet (on-street parking; the ramp at New Brook Street), Bradford Council's car parks page
(Denton Road: 93 spaces, 4 disabled, £1 an hour, £4 over 3 hours, 8am to 6pm every day), Ilkley Town Council's
toilets page (40p, summer 8am to 8pm, winter 9am to 6pm), Defra's 2020 consultation document (toilets at the Lido,
May to early September), Defra's 2020 decision page and Bradford District Parks' event page (more than 20 people,
four weeks' notice). All still say what the guide says.

Not added:

- West Yorkshire Metro's timetable pages (`wymetro.com/buses/timetables/...`) refused automated requests (HTTP
  403). Its Wharfedale frequency PDF (`admin.wymetro.com/media/jdwfj1wb/wharfedale_bus_frequency_0825.pdf`) lists
  the 62 Keighley to Ilkley every 30 minutes and the X84 every 45 minutes in the daytime, but the PDF carries no
  date of its own (only `0825` in its file name and September 2025 in its metadata), so it was left out rather
  than given a guessed `source_date`.
- The Keighley Bus Company's page for the 62 returned 404.
- No source found says how far the station, a bus stop or a car park is from the bathing site, which bank the
  shingle beach is on, or where to get out.

### Effect on the live tile

Adding facts and photos changes Cromwheel's usual tile, as any new fact would: a "Bus and train" row shows after
Parking, and the three historical photos follow the facts, each with its line. With six topics the fold would have
put Toilets and Who can swim behind "Show all", so the usual tile now keeps Who can swim in view wherever it falls
(`guideFacts`), and still folds only when two or more topics would go: Cromwheel's six all show. A guide with ten
topics shows the first four and Who can swim, and folds five. "Bus and train" is not listed under "Not in this
guide yet", so no other guide gains a gap. The rule for Who can swim does change other tiles: run over all 57
guides on 30 October 2026, 19 had Who can swim folded before and show it now (Cromwheel among them). Nine of
those, whose fold would now hide a single topic, show every topic (among them Cromwheel, Grasmere, Dovedale and
Ullswater at Pooley Bridge); the other 10 keep a smaller fold. No guide hides a topic it showed
before. The existing fold tests pass unchanged. Outings (`outing.js`, not edited) will list "bus and train" among
the topics on the spot's page.

## Photos

Decided by Ethan's reviewer on 30 October 2026, after checking Geograph's terms and the CC BY-SA 2.0 deed:
Geograph photos are allowed as a third kind, `status = "historical"` (guides/README.md, "Historical photos";
`src/dipcast/guides.py`). Each carries the photographer (`credit`), its Geograph `title`, its page (`source`), the
day taken as Geograph gives it (`taken`), the deed's exact link (`licence`) and the `changes` made. It has no labels.
Every photo, of any kind, now names the `topic` it shows, or `overview`.

### Used (three)

Downloaded at Geograph's 640 x 480 size (no larger size could be fetched: Geograph's `more.php` refused automated
requests), each into its own new, empty folder, and prepared with `scripts/guide_photo.py` under `python -I`. The
script does not enlarge, so the only change is a re-encode with all metadata removed, which `changes` says.

| File, step | Geograph photo | Photographer, taken | What it shows | Why the place is verified |
| --- | --- | --- | --- | --- |
| `cromwheel-upstream-2021.jpg`, overview | 6979159 "River Wharfe, Ilkley" | Malc McDonald, 14 Jun 2021 | The river looking upstream ("This view looks upstream"), a gravel bank on the left bank, from a raised point. | Camera at SE 1224 4848, the suspension bridge's square (other photos of the bridge are within 10 m); facing WSW, upstream; the EA profile puts the site "upstream of the suspension bridge". |
| `cromwheel-gravel-bridge-2023.jpg`, overview (was Getting in; moved in review because its role is not verified) | 7486475 "Foot suspension bridge over the River Wharfe" | Oliver Dixon, 16 May 2023 | A gravel bank at the water's edge in the foreground, the suspension bridge behind it. | Camera at SE 12224 48476 facing ESE, on the gravel, with the bridge in the picture: the gravel is upstream (west) of the bridge, as the EA profile places the site; the profile describes a "gently sloping shingle beach" exposed when the river is low. |
| `cromwheel-council-sign-2024.jpg`, Who can swim | 7922212 "Warning sign regarding bathing in the River Wharfe" | Mrs W J Sutherland, 13 Nov 2024 | A Bradford Council sign headed "River Wharfe, Suspension Bridge, Ilkley"; at 640 px a line reads "water quality below suspension bridge"; there is a no-swimming pictogram; the rest is not legible. | Camera at SE 1224 4845, beside the bridge; the sign's own heading names the bridge; the Bradford logo is on it. |

What is inferred, not established: that the gravel in 7486475 is where most people get in (the EA profile names a
beach, not a point); that 6979159 was taken from the bridge itself (the grid reference is to 10 m and the view is
raised); which bank the gravel is on (Oliver Dixon's 7486467 says "on the south bank"; nothing official does).
The captions say only what the pictures show.

The sign. No authoritative page was found for it: searches of Bradford Council's, the Environment Agency's and
Defra's pages found the 2020 duty (Bradford provides water-quality information and warning signs in the bathing
season, already a fact in the guide) but no wording or location for a sign at the suspension bridge. So no fact was
added, the photo's caption says its current wording and scope are not verified, the permission part says a sign in
a historical photo is as it was that day, and the field checklist keeps it. Nothing in the tile reads a permission,
a ban or a route from it.

### Other candidates, not used

Found through Geograph's public syndication API (`api.geograph.org.uk`) and each photo page; Geograph's own search
page asked for a bot check, which was not attempted. "What it shows" is from the photographer's title and words and
from looking at the 640 px image; distances are from the spot's pin (53.93189, -1.81618). Not used where the place
or the role could not be checked against an official page: none shows the ramp at New Brook Street, and the path
photos may not be on the leaflet's route.

| Photo | Photographer, date | Camera, facing | What it shows | Use for |
| --- | --- | --- | --- | --- |
| https://www.geograph.org.uk/photo/7486467 "Gravel bank" | Oliver Dixon, 16 May 2023 | SE 12214 48446, NNW | A wide gravel bank, the photographer says on the south bank, running into the river; wooded far bank. | Getting in |
| https://www.geograph.org.uk/photo/7552483 "River Wharfe at Ilkley" | Bill Boaden, 9 Jun 2023 | SE 1221 4843, NNW | The same stony beach in summer, low water. The photographer's words mention swimming and questioned water quality (not usable as text). | Getting in |
| https://www.geograph.org.uk/photo/7486469 "Bend in the River Wharfe" | Oliver Dixon, 16 May 2023 | SE 12241 48507, WSW | The bend "flanked by gravel banks", the beach on the left. | Overview |
| https://www.geograph.org.uk/photo/1336055 "Footpath running between Cemetery & River Wharfe" | Betty Longbottom, 3 Jun 2009 | SE 122 484, SSW | A tree-lined surfaced path with a rail on the river side. Old (2009). | Path |
| https://www.geograph.org.uk/photo/7805201 "Riverside Path, Ilkley" | David Dixon, 31 Mar 2024 | SE 116 480, WNW | The path "along the northern side of the River Wharfe" through Riverside Gardens. | Path, from New Brook Street |
| https://www.geograph.org.uk/photo/1336045 "Riverside Gardens - viewed from New Brook Street" | Betty Longbottom, 3 Jun 2009 | SE 116 481, WNW | The gardens from the street. Old (2009). | Arrival from New Brook Street |

Inferred, not established: from the leaflet (start at New Brook Street, follow the river downstream, cross by the
suspension bridge), the EA profile (the site is upstream of the suspension bridge) and these grid references, the
walk from New Brook Street to the beach looks like roughly 600 m east along the north bank. No source says so, and
the guide does not. Defra's 2020 consultation also says the proposed area ran from Ilkley Main Bridge to Beanlands
Island, the stretch to "Ilkley Swing Bridge" being the more used; whether that swing bridge is the EA's suspension
bridge is not stated, so it was not added.

## Missing field evidence: a checklist for someone on site

Tick each one with the day, and send photos with the agreement in README "Photos" rule 1 (or take them as
SwimSignal, then `scripts/guide_photo.py`).

Photos (with numbered labels):

- [ ] The gap in the fence and the ramp at the north end of the New Brook Street road bridge.
- [ ] The Riverside path between the road bridge and the bathing site, at one or two points.
- [ ] The bathing site from the path: where you leave the path for the beach.
- [ ] The place to get in, at normal level, with the suspension bridge in view (to replace or confirm the 2023
      historical photo).
- [ ] The place to get out, if not the same.
- [ ] The sign by the suspension bridge, close enough to read every line (to replace the 2024 historical photo).
- [ ] The nearest bus stop and the station exit, if a route from them is written up.

Facts to check or find (each needs a source page or `seen` on a visit):

- [ ] Which bank the shingle beach is on, and how you reach it from the Riverside path.
- [ ] How deep the water is at the place to get in, at normal level (say what level the gauge showed that day).
- [ ] Where to get out, and whether it differs when the river is up.
- [ ] Whether there is a step-free route from the road to the water's edge, and where it stops.
- [ ] Walking time from Ilkley station, from the nearest bus stop on Brook Street, from Denton Road car park and
      from New Brook Street to the bathing site.
- [ ] The walk from the Riverside Gardens toilets to the bathing site.
- [ ] Phone signal at the water (network and bars).
- [ ] The Environment Agency or council bathing-water sign at the site: what it says, photographed.
- [ ] The Bradford Council sign by the suspension bridge (Geograph 7922212, November 2024): is it still there,
      its full words, and what stretch of river it says it covers.
- [ ] Whether the gravel in the 2023 photo is where people get in, and which bank it is on.
- [ ] Any other sign about swimming, the landowner or events, with its words.
- [ ] Changing: any place to change, or none (only if seen or a source says so).
- [ ] Seasonal limits other than the toilets' summer and winter hours and the Lido's season: any closures or
      restrictions, with their dates.
- [ ] A rail or bus page that names a stop for the riverside, if one exists (a council's or an operator's).

Unknowns that stay unknown until someone goes:

- [ ] Whether the four questions the page lists for every spot (depth, step-free route, distance on foot, signal)
      should become topics in the guide format. That is a format decision, not a fact.

## How the screenshots were made

No build was run (it calls Open-Meteo). The smallest working route:

1. Copy `src/dipcast/site/*` to a scratch folder, with `src/dipcast/pages/page.css` and `src/dipcast/pages/fonts/`.
2. Put the live `https://swimsignal.co.uk/data/spots-lite.json` at `data/spots-lite.json` and the live
   `data/spot/bw-uke4100-08901.json` at the same path, with its `guide` replaced by this branch's
   `guides/bw-uke4100-08901.toml` parsed by `guides.parse_guide`.
3. Copy `index.html` to `spot/bw-uke4100-08901/index.html` with `<base href="../../">` added after `<head>`. This
   is the one build-time substitution the spot page needs: without the base, relative paths resolve inside
   `spot/<id>/`. The inline script runs as written; `levels.js` has no `?v=` tag, so `arrive.js` loads untagged.
4. Copy the guide's photos to `guides/photos/`.
5. `python3 -m http.server 8793 --bind 127.0.0.1 --directory <folder>`, then headless Chrome over its debugging
   protocol at 320 x 812 and 375 x 812 (2x, touch, an Android user agent) and 1440 x 900, opening
   `/spot/bw-uke4100-08901/?arrive=1` and the same address without it.

Checked on 30 October 2026 with that evening's data, at 320, 375 and 1440 px: no page wider than the screen, every
photo loaded. Keyboard, in headless Chrome: Enter on the focused "Show all" (on `bw-ukd1203-45700`, whose usual tile
folds four topics) shows them, removes the button and moves focus to the first one shown; Enter on the phone's "At
the water" summary opens it, with Who can swim in view; Tab from the arrival tile's first link reaches all 20 of
its links in turn. With `arrive.js` blocked, `?arrive=1` leaves the usual guide in place (`arrive.js` is also in
`sw.js`'s list, so the offline copy holds it). Not checked with a screen reader or in Safari.
