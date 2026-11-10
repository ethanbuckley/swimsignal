# Photo candidates from Geograph

`geograph-shortlist.tsv` lists up to 12 Geograph photos for each spot that might show the swim place. It is
a shortlist for a person to check, not a choice. Nothing on the site reads it.
`decisions.tsv` records every candidate that was looked at, whether it was used, and why not; and every spot
left without a photo, with the reason. A photo reaches a spot's
page only as a `[[photo]]` with `status = "historical"` in its guide (`guides/README.md`, "Historical
photos"), after someone has looked at it and checked its place.

## How it was made (10 November 2026)

`scripts/geograph_shortlist.py` read Geograph's free bulk dumps, dated 9 November 2026:

- `gridimage_base.tsv.gz`: title, photographer, date taken.
- `gridimage_geo.tsv.gz`: subject and camera positions, view direction.

It ran against the live site's `data/spots.json` and made no API request. It keeps a photo when:

- its subject is within 300 m of a river spot's pin, or 600 m of a lake spot's (100 m more for a
  six-figure grid reference), and
- its title names the spot's water or place, or a water word (river, beck, falls, beach and so on).

Photos are ranked by name match, distance and how recent they are.

Columns:

- `subject_m_from_pin` and `camera_m_from_pin`: metres on the British National Grid.
- `subject_precision_m`: how exact Geograph's grid reference is (1, 10 or 100 m).
- `flags`: things to look at first. These are a title that says flood, a photo taken before 2010, and no
  camera position.

It covers 121 of the 123 spots. River Duddon at Birks Bridge and the Tame at Dosthill have no candidate
under these rules.

The titles and photographers' names are Geograph's metadata. The dumps are © Geograph Project and
licensed for reuse under [CC BY-SA](https://creativecommons.org/licenses/by-sa/2.0/), and so is this file.

## Geograph's terms, as read on 10 November 2026

- **Key.** The live API (`api.geograph.org.uk`) needs a key. You request it at
  <https://www.geograph.org.uk/get-api-key.php> with a name, an email and what it is for. The API page asks
  AI agents to have their user register. The key belongs to Ethan and is kept outside this repository,
  in `swimsignal-private`.
- **Pace.** The key page implies about one request a second and at most 100 results a request.
- **Bulk use.** Use the dumps, not the live API. Do not scrape photo pages for details. `robots.txt` asks
  the same and disallows `reuse.php`.
- **Hosting.** The dumps page says not to hotlink images on Geograph's servers without permission. The key
  page lists hotlinking large images as a separate permission. So each photo is downloaded once at
  640 px and served from this site (`guides/photos/`).
- **Credit.** Show the photographer's credit with the image, say it is under Creative Commons, and link the
  photo's page (`https://www.geograph.org.uk/photo/<id>`). A changed copy goes out under the same
  licence. The guide's historical-photo line already says all of this (`guide.js`, `guideHistorical`).

## Next, once the key is saved

For each spot, take the first three candidates without a flag, and the rest only if none fit.
`https://api.geograph.org.uk/api/photo/<id>/<key>` gives each one's 640 px image address, title and
photographer. Look at the picture. Check its place against its title, its words, its grid reference and an
official page. Then prepare it with `scripts/guide_photo.py` as `guides/README.md` says, and add it to the
spot's guide with its Geograph id in `source`.

No photo is better than one of the wrong place. A spot whose candidates all fail keeps none, and its row
here records why.

Size: at most about 363 detail requests (3 × 121) and 121 downloads, at one a second. That is about 8
minutes of requests.


## Done, 10 November 2026

Ethan's key was used for 343 requests at one a second: details for 171 candidates and their 640 px copies.
That is within the "about 500" stated when the key was asked for.

- **Rounds.** The first round took the best unflagged candidate for each spot. The second took one or two more for
  the spots whose first was rejected.
- **How each was checked.** Each picture was looked at beside its title, the photographer's words (from the free
  `gridimage_text` dump) and its subject and camera distances from the pin.
- **Rejected:**
  - a photo of something else: a road, a car park, a café, the wrong pond;
  - water in flood or spate;
  - a camera far from the place;
  - recognisable people close up, especially children.
- **Result.** 108 spots now have a historical overview photo in their guide (`guides/<id>.toml`, files
  `guides/photos/geograph-<id>.jpg`). 14 have none, and `decisions.tsv` says why. Cromwheel keeps the three photos
  from 30 October.
- **New guides.** A spot without a guide got a new one holding the photo alone. Its tile says nothing is checked
  yet, and lists every topic as missing.
