# Practical guides

A spot's practical guide answers what the pollution forecast cannot: where to park, the path to the
water, where to get in and out, toilets, changing, fees and opening times. One file per spot,
`guides/<spot id>.toml`, written by hand. The build (`src/dipcast/guides.py`) checks each file,
attaches it to the spot in `site/data/spots.json`, and copies the photos it uses; the spot's page
draws it as the "Practical guide" tile (`src/dipcast/site/guide.js`). A spot without a file shows a
short tile asking swimmers what they know.

## The one rule: say who says so

Every fact and every photo is one of two kinds, and the page shows which, in words, beside it.

| `status` | Means | Needs | The page says |
| --- | --- | --- | --- |
| `confirmed` | The landowner's, operator's or council's own page says so, or someone from SwimSignal saw it on site | `source` (an https page) and `source_name` (who publishes it), or `seen` (the day), or both | "Confirmed: Example Council" with the page linked, under a first line giving the day it was checked, or "seen on site 20 Aug 2026" |
| `suggested` | A swimmer told us. Not checked | `from` (the name or initials they agreed to) and `on` (the day they told us, or swam) | "A swimmer's suggestion, from Sam, 12 Sept 2026. Not yet checked by SwimSignal." |

Things that are not a source: a wild-swimming directory, a blog, a review site, a map tag, a news
story. A mapped footpath or a swim tag does not establish permission to swim (see `src/dipcast/access.py`).
When a suggestion is checked, change it to `confirmed` with its `source` or `seen`, and drop `from`
and `on`.

`checked` at the top is the day every `confirmed` fact in the file was last checked against its page.
Recheck the whole file when you change any fact; prices and hours change every season. The page
warns readers once a guide is more than a year old. A good time to recheck all of them is May,
before the season.

`how` is `desk` when the confirmed facts come from published pages only, and `visit` when someone
from SwimSignal checked them on site. The page's first line says which: "Checked 3 Oct 2026 from the
published pages linked below, not on site."

## The format

```toml
checked = 2026-10-03     # a bare date, no quotes
how = "desk"             # "desk" or "visit"

[[fact]]
topic = "parking"        # parking, path, entry, exit, toilets, changing, fees, hours, rules
text = "Pay and display car park on Denton Road, a few minutes' walk from the river."
status = "confirmed"
source = "https://www.example.gov.uk/ilkley-bathing"
source_name = "Bradford Council"
lat = 53.9317            # optional: adds an "On a map" link (OpenStreetMap). Only from the source, or seen
lon = -1.8163

[[fact]]
topic = "entry"
text = "Shallow shingle on the south bank, upstream of the stepping stones."
status = "suggested"
from = "Sam R."
on = 2026-09-12
```

Topics and their headings on the page, in this order: `parking` Parking, `path` Path to the water,
`entry` Getting in, `exit` Getting out, `toilets` Toilets, `changing` Changing, `fees` Fees and booking,
`hours` Opening times, `rules` Who can swim. A topic with no fact is listed under "Not in this guide
yet", so a reader takes it as unknown rather than as none. Write "There are no toilets" only when a
source says so.

There is no free text without a source: every sentence on the tile is a fact with its status, or
the page's own words. Keep each fact to one or two plain sentences (400 characters at most). Put prices and hours in the
words the page uses, with the season they apply to.

## Photos

Photos make entry and exit points findable: a numbered label on the picture, the same number in the
list under it.

1. Take the photo on site, or have the swimmer's agreement in writing (the email they sent it with)
   that they took it, that it may be published with their credit, and that anyone recognisable in it
   is happy to be online.
2. Prepare it. This turns it upright, shrinks it to 1600 px on the long side, and removes everything
   else in the file, including where it was taken and the phone's details:

   ```
   uv run --with pillow python scripts/guide_photo.py ~/Downloads/IMG_1234.jpg cromwheel-shingle.jpg
   ```

   It saves `guides/photos/cromwheel-shingle.jpg` and prints the lines to paste, with the size filled in.
3. Paste and fill in:

   ```toml
   [[photo]]
   file = "cromwheel-shingle.jpg"
   width = 1600
   height = 1200
   caption = "The shingle beach from the riverside path, looking upstream."
   credit = "Ethan Buckley"
   taken = 2026-08-20
   status = "confirmed"
   seen = 2026-08-20

   [[photo.label]]
   x = 32        # per cent across the photo, from the left
   y = 70        # per cent down, from the top
   text = "Shingle: the easiest way in"

   [[photo.label]]
   x = 71
   y = 58
   text = "Steps up to the path"
   ```

   A swimmer's photo is `status = "suggested"` with `from` and `on`; the page then says the labels are
   theirs and not checked. Up to six photos a guide and nine labels a photo. To find `x` and `y`,
   open the photo in Preview, hover over the point and read its position against the size.

## Where facts come from

- Swimmers send details and photos from the "Tell us" link on the tile, which opens the feedback form
  set to "Add to or correct a spot's practical guide". It arrives as an email to hello@swimsignal.co.uk.
- Before publishing a swimmer's name, use only what they asked to be credited as. With no answer, use
  "a swimmer" and the day.
- Check a file before a pull request: `uv run pytest -q tests/test_guides.py` lists anything wrong,
  file by file. A file that fails is left out of the published site with a warning, and the forecasts
  still publish.
