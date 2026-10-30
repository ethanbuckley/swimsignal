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

At 375 and 1440 px (screenshots listed at the end):

1. **Arriving for the first time** (the tile's label, with the guide's signpost icon). The guide's checked line,
   then a count: "In this guide: 9 facts verified, 2 from dated records, none a swimmer's word; 9 published pages
   in all."
2. **The way there and back**, numbered:
   1. Getting there: "By bus or train" (2 facts), "By car" (2 facts), then a link to Traveline's journey planner
      for times. The link is not a fact.
   2. From the road to the water (2 facts). "No photo yet of the path to the water."
   3. Getting in (1 fact). "No photo yet of the place to get in."
   4. Getting out: "Nothing in this guide yet." "No photo yet of the place to get out."
   5. Toilets and changing: Toilets (2 facts, one a dated record); Changing, nothing yet.
   6. Seasons, opening times and fees: nothing yet. (The toilets' summer and winter hours stay under Toilets,
      where the guide put them: no fact is moved or reworded.)
3. **Who can swim here**: "A path, a car park or a beach is not permission to swim. This part says only what its
   sources say." Then the guide's two `rules` facts (Defra's 2020 decision; Bradford's parks events rule) and,
   where `access.py` has one, the desk check of access in its own words.
4. **The water**: a link to the forecast at the top of the page. Nothing about the water is restated.
5. **What nobody has checked**: each step or part with nothing; the photos not taken; four questions the guide's
   format has no place for (depth where you get in, a step-free route, distance on foot from the stop, station and
   car parks, phone signal); any suggestions not checked; and, for a desk-checked guide, "Nobody from SwimSignal
   has been here".
6. "Been here? Tell us what you found", to the feedback form set to a guide.

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

Adding facts changes Cromwheel's usual tile, as any new fact would: a "Bus and train" row now shows after Parking.
With six topics the tile now folds after four, so Toilets and Who can swim move behind "Show all 6 topics"
(before, five topics all showed). No other guide changes: "Bus and train" is not listed under "Not in this guide
yet", so the other 55 tiles are as they were. Outings (`outing.js`, not edited) will list "bus and train" among
the topics on the spot's page.

## Photos: Geograph candidates (a decision for Ethan)

`guides/photos/` does not exist: no guide has a photo. Nothing in `swimsignal-private` shows Cromwheel or
Waterhead (the October social shortlist has an Ambleside to Rydal panorama, not an entry point). The README's
rule 1 allows only photos taken on site by SwimSignal or sent by a swimmer with written agreement, so none was
added.

Geograph's photos are CC BY-SA 2.0: free to use with the photographer's credit and the same licence on the copy.
They would be a third kind of photo, neither "Verified: seen on site" nor a swimmer's. Using them needs a README
rule (status, how the page credits them, how the share-alike licence is shown, and that they show a past day, not
today's river). The candidates below were found through Geograph's public syndication API (`api.geograph.org.uk`)
and each photo page; Geograph's own search page asked for a bot check, which was not attempted. "What it shows" is
from the photographer's title and words and from looking at the 640 px image; distances are from the spot's pin
(53.93189, -1.81618).

| Photo | Photographer, date | Camera, facing | What it shows | Use for |
| --- | --- | --- | --- | --- |
| https://www.geograph.org.uk/photo/7486467 "Gravel bank" | Oliver Dixon, 16 May 2023 | SE 12214 48446, NNW | A wide gravel bank, the photographer says on the south bank, running into the river; wooded far bank. | Getting in |
| https://www.geograph.org.uk/photo/7552483 "River Wharfe at Ilkley" | Bill Boaden, 9 Jun 2023 | SE 1221 4843, NNW | The same stony beach in summer, low water. The photographer's words mention swimming and questioned water quality (not usable as text). | Getting in |
| https://www.geograph.org.uk/photo/7486475 "Foot suspension bridge over the River Wharfe" | Oliver Dixon, 16 May 2023 | SE 12224 48476, ESE | The suspension bridge seen from the gravel bank: shows where the beach sits against the bridge the EA profile names. | Getting in; the landmark |
| https://www.geograph.org.uk/photo/6979159 "River Wharfe, Ilkley" | Malc McDonald, 14 Jun 2021 | SE 1224 4848, WSW, upstream | Looking upstream, apparently from the bridge, with the gravel beach on the left bank. | Overview of the site |
| https://www.geograph.org.uk/photo/7486469 "Bend in the River Wharfe" | Oliver Dixon, 16 May 2023 | SE 12241 48507, WSW | The bend "flanked by gravel banks", the beach on the left. | Overview |
| https://www.geograph.org.uk/photo/1336055 "Footpath running between Cemetery & River Wharfe" | Betty Longbottom, 3 Jun 2009 | SE 122 484, SSW | A tree-lined surfaced path with a rail on the river side. Old (2009). | Path |
| https://www.geograph.org.uk/photo/7805201 "Riverside Path, Ilkley" | David Dixon, 31 Mar 2024 | SE 116 480, WNW | The path "along the northern side of the River Wharfe" through Riverside Gardens. | Path, from New Brook Street |
| https://www.geograph.org.uk/photo/1336045 "Riverside Gardens - viewed from New Brook Street" | Betty Longbottom, 3 Jun 2009 | SE 116 481, WNW | The gardens from the street. Old (2009). | Arrival from New Brook Street |
| https://www.geograph.org.uk/photo/7922212 "Warning sign regarding bathing in the River Wharfe" | Mrs W J Sutherland, 13 Nov 2024 | SE 1224 4845, NE | A Bradford Council sign by the suspension bridge. At 640 px it reads in part "River Wharfe water quality below suspension bridge, Ilkley", with a no-swimming pictogram; the rest is not legible. | Not a guide photo: a lead for a field check (below) |

Inferred, not established: from the leaflet (start at New Brook Street, follow the river downstream, cross by the
suspension bridge), the EA profile (the site is upstream of the suspension bridge) and these grid references, the
walk from New Brook Street to the beach looks like roughly 600 m east along the north bank. No source says so, and
the guide does not.

## Missing field evidence: a checklist for someone on site

Tick each one with the day, and send photos with the agreement in README "Photos" rule 1 (or take them as
SwimSignal, then `scripts/guide_photo.py`).

Photos (with numbered labels):

- [ ] The gap in the fence and the ramp at the north end of the New Brook Street road bridge.
- [ ] The Riverside path between the road bridge and the bathing site, at one or two points.
- [ ] The bathing site from the path: where you leave the path for the beach.
- [ ] The place to get in, at normal level, with the suspension bridge in view.
- [ ] The place to get out, if not the same.
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
      and its full words.
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
4. `python3 -m http.server 8793 --bind 127.0.0.1 --directory <folder>`, then headless Chrome over its debugging
   protocol at 375 x 812 (2x, touch, an Android user agent) and 1440 x 900, opening
   `/spot/bw-uke4100-08901/?arrive=1` and the same address without it.

Checked at 375 and 1440 px only, on 30 October 2026 with the 17:49 UTC data. Not checked at 320 px, with a screen
reader, or in Safari.
