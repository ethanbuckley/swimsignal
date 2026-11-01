# SwimSignal design system

Written 1 October 2026, when the site was redrawn to look like one product rather than a set of
generated pages, and revised on 2 October 2026 for the fifth round, "a field guide, not a
dashboard", and the seventh, "the sky and the glass" (both below). This file is the reference for
anyone changing how the site looks: what was wrong, what was decided, and the rules that keep the
pages consistent. The stylesheet that carries the system is `src/dipcast/pages/page.css`; the
app page, `src/dipcast/site/index.html`, repeats the tokens and the header inline so that it paints
before any stylesheet arrives and works offline on its own. A token changed in one must be changed
in the other: `tests/test_design_tokens.py` fails the build when the two sets differ, or when a rule
in either writes a colour, a font size or a radius instead of using a token.

## What was wrong

Seen on 1 October 2026, at 375 px and 1440 px, light and dark:

- **No typeface had been chosen.** Everything was the system font stack, so the site inherited
  whatever the device had. Headlines were 800 weight with tight tracking, under small uppercase
  tracked labels ("PLAN YOUR NEXT SWIM", "POLLUTION RISK", "SEWAGE SPILLS UPSTREAM"). That stack,
  eyebrow + heavy headline + muted lede, is the signature of generated interfaces.
- **Rounded, floating surfaces.** Cards at 16 px radius with two-layer drop shadows, pill buttons
  at 999 px, a gradient-tinted intro card, hero cards washed in the level's pastel. Eight different
  corner radii were in use (8, 10, 11, 12, 14, 16, 20 and 999 px).
- **Two sites.** The app had a teal bar, cards and a grey page; the prose pages (About, Accuracy,
  Terms, Privacy, Testing, Feedback) had a white page, a plain text nav, smaller type and their own
  heading sizes. Their navs disagreed on names ("Map" and "Explore" for the same page) and the
  page titles put the brand on different sides ("SwimSignal · About", "Feedback · SwimSignal").
- **The accuracy page read as a notebook dump:** a callout box, then a wall of small grey
  paragraphs and bare tables in a monospaced font, with no way to see the four numbers that matter.
- **Text glyphs as icons:** ★ and ☆ on the Save button, ← on back links, + and – on folds, ✓ on
  the swim log, and a 64 px "404".
- **Caveats repeated** under every control, so the honest ones were lost among the decorative ones.

## Decisions

### Type

Two typefaces, both by Adobe under the SIL Open Font License, served from this site (`fonts/`, with
the licence beside them) so that no third party receives a request:

- **Source Serif 4** for the wordmark, page headings and spot names. A serif at
  600 weight, never heavier. Variable optical size, so it is sturdy at 18 px and fine at
  34 px. The file is Google Fonts' own for weight 600 alone (52 kB, against 122 kB for weights 200
  to 900, 6 October 2026), and both stylesheets declare 600 only: a serif at another weight would
  be drawn from the 600 file, or thickened by the browser. A trimmed file of our own would be a
  Modified Version under the OFL and could not keep the Reserved Font Name "Source".
- **Source Sans 3** for everything else: body, labels, controls, tables. Weights 400 and 600, and
  700 for headlines and level words; 300 (Light) for a tile's figure (seventh round). The file
  carries weights 200 to 900, and both stylesheets declare all of them.
  Risk levels, operational card headings and numerical results use the sans: they need to read
  quickly, while the serif gives places and reports their character. Tables and headline figures
  explicitly use tabular numerals.
- The monospaced stack is kept for one thing: model version strings.

Six sizes, in pixels, as tokens (`--fs-*`) in both stylesheets, and no other size anywhere: 13
meta (used sparingly: a row's kind, the week's letters, a tile's label, the foot), 15 notes (notes,
controls, a row's headline, a tile's sentence), 17 body (the app and the prose pages alike), 20
section headings (and the wordmark, a prose page's lede and h2, a saved spot's level), 30 a figure
(a tile's, a headline without a level), 36 the spot's name, page titles and the answer's level, 30
on phones (800 px wide or less, where the app's phone layout begins, and the same step on the prose
pages; until 2 October the prose pages dropped it at 540 px). A prose page's h3 is the body size in the
serif. Line height 1.5 for text (both files; `page.css` had 1.55), 1.1 to 1.25 for headings. No
letter-spacing except −0.01em on the 36 px headings (`--fs-title`: page titles, the spot's name, the
answer's level, the Accuracy figures), and no uppercase labels anywhere. (Until 2 October the
wordmark and every h1 to h3 had −0.005em and the 30 px figures −0.01em, below what the eye can see at
those sizes; they were taken off to keep the rule simple.)

### Colour

- A warm paper page `#f6f4ee`, one white surface `#fff`, ink `#1b2328`, muted `#5a6166` (5.7:1 on
  the paper), hairlines `#e0dbd0`. Light only (fifth round): nothing is hard-coded in a rule.
- Brand teal `#0f5a61` (the icon's), the one accent: the mark, links, the primary button, a chosen
  filter, focus rings. The low-risk filter uses the moss text shade `#326a43` with white text.
  White on a fill (the bar, the brand, a chosen control) is `--on-fill`; the veil over the map
  that says "two fingers to move" is `--scrim`.
- The mark in every header is the icon's teal too. It was a lighter `#1a6871` from 1 October,
  chosen to stand off the teal bar of the time; on the slate bar both shades are about 1.1:1 to it
  (`#1a6871` 1.14, `#0f5a61` 1.07), so the lighter one no longer bought anything and the two marks
  were unified on 2 October. The mark reads by its river, dot and ring, not by its square.
- `--faint` (`#676b6e`, the week's letters, a placeholder) is 4.9:1 on the paper and 5.4:1 on
  white, but 4.25:1 on the bare sky, under AA. It is for tiles, fields and the paper only: checked on
  2 October at 375 and 1440 px, every piece of faint text on the list, a spot and the Saved page
  sits on a tile.
- The header is a slate bar, `#3d5b5d` (`--bar`, seventh round), a darker shade of the picture's
  nearest fells: white on it is 7.4:1, and the links' 86% white (`--bar-ink`) 5.6:1.
- The four levels keep their meaning and are the only strong colours on a page, in one natural
  palette: moss, ochre, rust and brick. Marks (map, day strips, bars, rules): low `#3b7d4f`,
  moderate `#b7791f`, high `#c2552a`, very high `#a32d2d`. Text (headlines, values): `#326a43`,
  `#855817`, `#a04623`, `#992a2a`, which pass 4.5:1 on the paper and on white (5.6:1 or more on the
  paper). The ochre and rust marks are too light for text (3.3:1 and 4.1:1 on the paper), hence
  the two sets. A spot with no monitored overflow upstream is teal `#4aa39a`, not grey: it is a
  calm answer, not a missing one. Grey `#98a2aa` means no level. An isolated lake, which the river
  network links to no monitored overflow, is teal too since 11 October 2026: it has the same words.
  An overflow discharging now is
  the very-high brick. An overflow with no current reading is the light grey, and the map keys call it
  that, "no current reading" (4 October 2026; they said "offline" and "offline or no feed"): a monitor
  offline, no live feed, or a feed that has not updated within six hours, whose "not discharging" may
  be out of date (`drawnStatus`). The same dot in a picked day's list of overflows.
- The map: OpenStreetMap's tiles with the land in grey and the water (sea, lakes, rivers) in a
  muted blue, `#bccfd8`, about as light as the grey it replaced (L* 82 against 83; chroma 8). Its
  hue (235°) is 48° from the teal marker's, which keeps a paper ring, and the open spot's dark
  teal ring has 4.9:1 against it. CSS filters change every colour alike, so the tiles go through
  an SVG filter in `index.html` (`#tiles`) that finds OpenStreetMap's water by its colour. That
  blue is not a token: the filter's numbers cannot read one.
- A level colours the answer's big word, a day's bar and the dot on a scale. The written level
  carries the meaning even when colour is hard to see; the marks are a supporting cue. It never fills
  a surface: the washed-tint card was the dashboard look, and five of them in a column were a wall
  of pastel. A level word in a table or the swim journal is the word in its text colour, not a filled
  label.

### Shape and surface

- One corner radius, 8 px (`--radius`), for the hero, inputs, buttons, a chosen chip, the maps,
  and the controls, tooltips and credit on the map. Count badges and dots are round, because they
  are circles. Nothing else is a pill. Two small radii are tokens of their own and used for nothing
  else: the mark's 6 px corner (`--radius-mark`) and the 4 px of a focus ring round a text link
  (`--radius-ring`). A header link's hover, the map's credit, its tooltips and its "Map" button had
  6 px until 2 October; they are 8 now. Bars are square, on the Accuracy page as in the app.
- The answer has no box (seventh round): its words sit on the sky. Everything after it is a tile,
  frosted where the picture is behind it and near white on the paper below, with no border; inside
  a tile, hairlines. No shadows and no gradients, except a 1 px lift under the controls that sit on
  the map, which need to read against tiles. Notices (stale, offline) keep their box: they are
  exceptions to read first.
- The five days are rows, as Apple's ten days: the day, its level, and a bar of four bands filled
  into the day's band. The open day is shown by a shaded row with a rule at its left, not a glow.
- The forecast issue time is the answer's last line, before the five days, so freshness is
  visible at the point of deciding.

### Words

- Labels are sentences or phrases in normal case: "Sewage spills upstream", "Water quality",
  "Saved spots", "All spots".
- A level says "risk" wherever it heads a line (seventh round): "Very high risk today: sewage
  spills", "Low risk by Tuesday", "High risk" in the answer and on a saved card, the map's
  tooltips, a picked day's rows. A bare "Very high" read as very high what. The word stands alone
  only under a heading that names it: the five days ("Pollution risk, next five days"), the
  day-by-day table's "Risk" column, the map's key.
- The answer's headline names what it covers where the spills set the level (20 October 2026, after an
  outside review read "Moderate risk" at Long Bridges as a verdict on the water): "Moderate risk from sewage
  spills", every word at the title's size, and the line under it says when ("Tomorrow", "Right now"), not
  the cause again; recent spills say "Recent spills, right now". A low level reads "Low risk from sewage
  spills" over its days. A poor rating, algae, a lab sample and the E. coli estimate are not forecasts of
  spills: "High risk" over "Rated poor", as before. The shared picture says the same. The list, the map's
  tooltips, Nearby, the comparison, a saved card, the embed and the alerts keep the short form, whose raised
  rows name the cause after a colon ("Moderate risk tomorrow: sewage spills"). The words are `HEAD_SCOPE` in
  `levels.js`; the reviewer's own, "Moderate predicted risk from monitored sewage overflows", were option A.
- Right now raised with no overflow upstream discharging (4 October 2026): a spill counts until 48 h
  after its water has passed, so the reason is "recent sewage spills" ("Moderate risk right now: recent
  sewage spills"; the answer's line under the level is "Recent sewage spills"). "Sewage spills right now"
  over a Right now tile saying "0 of 60 discharging" read as a contradiction (`nowBecause` in `levels.js`).
- A level set by the Environment Agency's rating leads with the level, then the reason (6 October
  2026): "High risk: rated poor", and in the bathing season "High risk: rated poor, advice against
  bathing". "Rated poor" alone left 13 rows on the list with no level, and in October "advice against
  bathing from 15 May" read as though the advice began on that date. The rating's tile gives the dates.
- Every tile the level rests on says in one line, under its figure, how it stands to the level above
  (6 October 2026, `tileLine` in `levels.js`): "This sets the level above.", "On its own: moderate
  risk. The poor rating raises the level to high risk.", "Tomorrow's spill forecast raises the level to
  high risk.", "Not counted in the level: only a poor rating is.", "Does not raise the level." A picked
  day's rows do the same for that day. An E. coli estimate out of season has no line: its tile says so. Wharfe at
  Cromwheel read "High risk" over a spills tile at "Moderate risk" and five days at "High", with
  nothing to join them up.
- Where the model has nothing to forecast, the level is a plain one that says what is true there
  (3 October 2026), in the answer, on a saved card, in the list row, the map's tooltip and key,
  and the alerts (the key lists it in the teal):
  - **"No monitored overflow found upstream"**, in the clear teal, where the trace finds no
    monitored overflow within 60 km upstream, and for an isolated lake (the forecast's `error` begins
    "An isolated lake"), whose spills row says why in plain words (levels.js, `ISOLATED_WHY`). Until
    11 October 2026 these were "No sewage risk from monitored overflows", which read as no risk at
    all, and "No monitored overflow drains into this lake", in grey, which only 3 of the 12 lakes with
    nothing upstream got. Before that the lake's was "No river connection: overflows cannot reach this
    lake", false at a fell tarn with becks in and out that the river network does not draw (Loughrigg
    Tarn). The levels' keys, `no overflows` and `no river connection`, stay: the alerts, the journal and
    the push Worker store them.
  - Under either, one line kept in view: "Other risks apply: algae, wildlife, runoff and bathers.
    Check the signs at the water." That line is the view's one "check the signs", so the caveat
    in the tile under the answer drops its own. Then, where the forecast has it, the rain in the 48 hours
    to midday today as a sentence: "12 mm of rain in the last two days".
  - No E. coli estimate on these spots, in a tile, a day's cell or the table: the model was fitted
    on sites with overflows upstream. The EA rating, the algae check and the river level stay as
    tiles.
  - A rating of sufficient or poor, or algae at the last check, still sets the level where it
    raises it ("High risk: rated poor"). An excellent or good rating no longer makes
    such a spot "low": that was the same word as a forecast that had looked and found nothing.
  - Before this the page said "No monitored overflows upstream" or "Not covered by the
    forecast", which a swimmer read as "no information".
- Units (4 October 2026): a distance a swimmer travels is in miles ("7.7 miles away", "under a mile
  away"), in the list, "Nearby" and Plan a swim; a distance the water travels, or to a gauge or a
  sensor, is in km ("2.1 km upstream", "Gauge at Addingham, 3.4 km away"), as the model counts it.
- The weekend (4 October 2026, Ethan's choices): while the five days reach a Saturday or a Sunday,
  the best-day line on the list and the Saved page first says how the weekend looks, so Show stays
  last, beside the week's best day: "Best this weekend: Saturday, 64 spots at low risk. Lowest
  pollution risk this week: tomorrow". Both days are words, as in any sentence: a later day by its
  full weekday, "today" and "tomorrow" in lower case (until then the best day took the day picker's
  "Tomorrow" or "Fri 9 Oct"). Only the better weekend day is named. On a Tuesday Saturday is alone,
  so there is no "best": "This weekend: 64 spots at low risk on Saturday." Equal days are said
  together. Nothing is added on a Sunday, when the weekend is today and the list shows it, or when
  the week's best day is itself a weekend day, which the line then names once.
- The list's two opening lines (20 October 2026, Ethan's pick, option B): the answer names the
  weekend's better day while the five days reach one, "Saturday: 19 of 105 spots at low risk · Show".
  When another of the five days has more spots at low risk, the line under it says so in the same
  form, the day in bold: "Today: 43 of 105, the most this week · Show". Until then the second line was
  "Lowest pollution risk this week: today", with no count, and read as contradicting the first, which
  never says it is the weekend's day. The Saved page keeps its own best-day line, above.
- One caveat per view, in the place it is read: the intro says "Forecasts, not water tests" once;
  the hero's last line says to check the signs at the water. The rest of the explanation lives
  under "About these forecasts" and on the About and Accuracy pages.
- A row says one sentence and folds the rest (fifth round): the hero's rows keep the sentence with
  the figures in view and put the rest under a fold named for its tile, "<label>: what this means"
  (one name per fold, so a screen reader's list of them tells them apart; until 2 October every
  one was "What this means"), word for word. What the strip's
  cells show folds into the water row, or the spills row where there is no water estimate. The EA rating keeps its
  advice in view and folds how it is rated and the years before. A section's note under the answer
  does the same: River level keeps "Not part of the pollution level." in view, and the definition
  of reach under the overflows folds whole.
- "About these forecasts" is in full on the list only. A spot's page and the Saved page give it one
  line, "About these forecasts · How accurate is it?", which opens it in place; so does any link to
  a part of it (the levels, what E. coli counts, your data).
- Kept in view, once per view, whatever else folds: "A forecast, not a water test: check the signs
  at the water before you swim", every Environment Agency advice sentence, the issue time, the
  data credits in the foot, and every sentence of the terms and the privacy notice. Consent text
  (the alerts) folds under what it is about, before the button, and keeps every sentence.
- Names agree everywhere: the home page is **Explore**, the verification page is **Accuracy**.
  Page titles are "Page · SwimSignal", where the page's name leaves out the brand its heading may
  carry: "About SwimSignal" is "About · SwimSignal", "Testing SwimSignal this winter" is "Testing
  this winter · SwimSignal". A spot's page is "Name: pollution risk forecast · SwimSignal". One
  exception, kept for search: the home page is "SwimSignal · pollution risk forecasts for swim
  spots", so a search result starts with the name.
- One name for each thing (2 October 2026). Before this the product went by four descriptions, the
  E. coli figure by six names and the spill score by four.
  - The product is a **pollution risk forecast**, in titles, descriptions, the manifest, the foot
    and the About page. Not "sewage-spill forecast" or "sewage-overflow risk": the level also
    takes in water quality and the bathing-water rating, and the strip already says "Pollution
    risk". "Sewage" stays where a sentence is about the overflows themselves.
  - The spill score is the **exposure index**, defined where it is explained (About, Accuracy,
    Testing, a spot's page) as "a 0–100 score for sewage from upstream reaching the spot", then
    "It is a score, not a probability." Not "spill risk", "overflow exposure" or "the modelled
    chance", and not called a probability. Until 11 October 2026 the definition said "how likely
    sewage from upstream is to reach the spot", which read as a probability beside the Method
    page's "not a probability". An overflow's **weight** (30 October 2026; until then "reach", "the share of
    a spill's bacteria the model expects to arrive") is a modelled relative contribution weight, from the
    transport assumptions (travel time and die-off, and dilution): neither a measured bacterial
    concentration nor a calibrated chance of contamination. Pages say "22% weight" or "model weight", define it
    once in `levels.js` (`WEIGHT_SAID`), and never call it reach or a chance. File and column names
    (`weight`, `reach` in the organisers' CSV) are kept.
    Its tile and rows keep their labels, "Sewage spills" and "Sewage spills upstream".
  - The E. coli figure is the **E. coli estimate** in prose, and its tile is **Water quality**.
    Not "E. coli chance", "E. coli risk", "E. coli > 900" or "water-quality estimate".
  - **Dŵr Cymru Welsh Water**, with the circumflex, in prose.
- Abbreviations are spelled out where a reader meets them: "Environment Agency" in full before
  "EA" on any page; "WwTW", "STW", "CSO" and "SPS" in overflow names are explained on the About
  page; "lead calibration" is defined under the live table on Accuracy. "cfu" is not used: the
  threshold is "900 E. coli per 100 ml".
- Overflow names (6 October 2026, markets plan B1): a plain name first, made from the company's
  (`plainName` in `levels.js`): "Addingham sewage works overflow" for "Addingham/NO 1 SPS/Preliminary
  Treatment-STW/6Xdwf Overflow", "Rivadale View storm overflow" for "RIVADALE VIEW/CSO". The company's
  name, in normal case, sits beside it, smaller and muted, because it is the name to look the overflow
  up by: first in the overflows tile's meta line, under the name in the organisers' table, in brackets
  in a picked day's rows, on its own line in the map's popup. The organisers' CSV keeps `site_name`
  and adds `plain_name`. A sentence ("Where the risk comes from", the clearing time) and a map tooltip
  give the plain name alone. A name with no code, or with nothing left once the codes are out, is
  shown as `nameCase` sets it, never with a guessed place: on 6 October 2026 that was 1,686 of the
  14,374 named overflows, 1,078 of them Wessex Water's, whose names carry no code.
- A part that cannot be used yet is not shown: Compare appears on the Saved page once two spots
  are saved. A picked day's details begin with its rows, because the hero's headline already
  gives that day's level and why.
- One date on a spot's page (22 October 2026). A picked day moves every forecast tile with it:
  Sewage spills, the E. coli estimate, Rain here and Weather sit under "Forecast for Saturday 24
  October" (or "Forecast for today"). The readings, Right now, River level, Water temperature and the
  algae check, sit apart under "Latest readings", which says they do not change with the day. An
  outside review had picked Saturday at Long Bridges and found the tiles below still on today.
- The live status before the level (30 October 2026, review of PR #463; docs/EVIDENCE-MAP-2026-10.md). A
  spot's answer opens, on today's view, with how many overflows upstream gave a status at the last poll, in
  ink: "Live status from 13 of 16 overflows upstream: none spilling at the last poll; 3 do not report, so
  could be spilling unseen." Where none did, it leads in bold with "Live sewage spill status unavailable",
  and the level under it is labelled "Modelled forecast" with its inputs. The compact headline leads with
  the status where right now is not known ("Live sewage spill status unavailable: low risk forecast"), and
  a raised day with nothing reporting says "(modelled, no live status)". The words are `liveHead` and
  `liveLine` in `levels.js`. "Forecast only: no overflow upstream reports live", under a big green "Low
  risk", was read as an observation at the Wye at Symonds Yat.

### Icons

One stroke set, 1.75 px, round caps: search, map, bookmark (Save and Saved), chevron (back links
and folds), and since the seventh round one for each tile's label (`ICON`: the
days, spills, water, right now, river level, rain, sun, rating, algae, map, nearby, the table, and a
question in a circle for Not known here).
The chevrons drawn in CSS (back links, folds, a tile's corner) and a select's arrow (`--arrow`) use
the same 1.75 px. The search icon (`SEARCH_ICON`) was still 2.2 on 2 October.
Inline SVG, so they inherit `currentColor` and need no file. The brand mark is inlined in every
header for the same reason: it needs no path to resolve at any depth.

From the fifth round to the seventh the one decorative element was the river line, the mark's
river turned to run across, under the list's heading and on the empty states. Ethan had it taken
off the pages on 2 October 2026: the picture of the fells is the motif now. The link-preview card
(`icons/og.png`, drawn by `scripts/make_share_image.py`) still draws it under the name, on the
paper, as the site's first screen looked in the fifth round.

### Layout

- **Header**, shared by every page: the slate bar (seventh round), the mark, the serif wordmark and
  the main links (Explore, Accuracy, About, Feedback; the app adds Saved) in white. The current page
  is underlined in white.
- **App, desktop:** every view is a page under the header from 1,100 px (20 Oct 2026). A spot opens as
  a page: the map moves into the spot's own tile, 400 px tall; the opening spans the page over the
  wide sky (`icons/fells-wide.webp`, `make_sky_image.py --wide`), and under it two columns, 5 to 7,
  1,180 px at most: the five days, nearby and the water on the left, the map and why on the right.
  Before, a spot was 3,803 px tall in the 460 px column at 1,440 x 900, beside a map already used to
  pick it. The list, Saved and Plan a swim match it (`cols`, `col-list`, `col-map`): the opening
  (`.lead`) centred over the wide sky, 760 px at most, the back link at the left edge as on a spot;
  on the list the search and "Show spots near me" share a row, as do the day and "Low risk only";
  under it the view on the left (5) and the full map on the right (7), in a glass tile labelled Map
  that is sticky under the header, the screen's height less the header and two 24 px gaps, never
  under 480 px. It keeps its controls, its legend (wrapped to the tile, above the credit) and
  click-anywhere. The page scrolls as one, in the panel, so the list keeps its place and the map its
  view when a spot is opened and closed. At 1,440 x 900 the map is 646 x 735 (880 x 836 beside the
  560 px column before); the list's opening ends 425 px down, so 427 px of the 788 px tile show on the
  first screen, and a river picked from the search scrolls the page until the whole tile is in view
  (`mapInView`). In the tile the map takes quarter steps of zoom (`snapMap`) and fits all the spots
  close to their own bounds, clear of the legend (`fitAll`): zoom 6.5 there, where a whole step left
  England under half the tile. A phone's map and the desktop's column keep whole steps and their fits. About and the foot share the 1,180 px
  frame, About's text at 720 px.
  From 801 to 1,099 px a spot is one 720 px column, and the list, Saved and Plan keep the old layout:
  map left, a 460 px column right. One 720 px column would put the map between the opening and the
  first spot: the opening ended about 520 px down at 1,440 before it was shortened, so with a 320 px map tile (a spot's at
  this width) the first spot would start near the foot of a 900 px screen (an estimate, not built).
  Two columns would leave the list 380 px wide, a phone's. A row's five days carry their short names ("Tue") over bars 32 px wide from
  1,200 px. On the list the day and "Low risk only" are the opening's alone; the map shows its own
  pair only on Saved and Plan, which have none.
  Saved since the second outside review (20 Oct 2026: "give the saved forecasts more width and make
  the map secondary... the nationwide map currently dominates even the empty Saved page"): the
  forecasts take the wide column and the map the narrow one, 7 to 5 (`cols(v, 'wide-list')`; 674 and
  482 px at 1,440), the map's tile 480 px tall, still sticky. With nothing saved there is no map at all
  from 1,100 px: the page is one 720 px column (`solo`). This turns round part of the layout of 20 Oct
  2026 for Saved alone: the list and Plan a swim keep 5 to 7. From 801 to 1,099 px Saved keeps the map
  on the left.
  **App, phone:** list first, the map one tap away in the bar at the bottom, a spot's page with its
  own small map. Unchanged: the two columns are `display:contents` there, so the order is the one
  stack it was.
- **Prose pages:** one 720 px column, serif headings, 17 px text, a summary box where a page has an
  answer in a few lines, and the shared foot: one line about what the site is, then the small links.
- **Accuracy page:** since 24 October 2026 (review C5), a one-screen summary opens it, under the lede: four
  figures in the ruled definition list, one sentence each (spills warned of, warnings that came true, pairs ranked
  the right way round, lower error live), then the warnings by company in one line, computed from the scorer's rows
  (the share warned of at the company the model learned from, the other companies together, and the range among
  those with 100 spill forecasts or more), then the contents list, which now starts with the warnings and In short.
  Every figure comes from `verification.json`; none is written in. The held-out year's lower error and the count of
  lab samples, tiles until then, are in In short. The rest below keeps its order. Before that the page opened with
  the forecasts as warnings (4 October 2026): a plain sentence with the figures, the
  share right always beside what saying "no" every time gets right, then a two-by-two table of hits, misses,
  false alarms and correct quiet days, each count over its name so it fits a 320 px phone. Under it (11 October
  2026) the warnings by company, a sentence and a table, since most hits were at the one company the model
  learned from, then the error read as a chance against both the long-run rate and a flat forecast at the
  period's own rate. Then the same for the E. coli estimate. A scored row is a forecast (one overflow, day and
  lead), never called an overflow-day, and days are counted, never spanned. Then the four numbers that matter
  in a ruled definition list, a short "in short" list,
  a contents list, then sections in the same order as before, with "Did the forecast run on time?" last of the
  live ones. The held-out ranking (an AUC) is said as pairs, "93 in 100", over "Pairs ranked the right way round"
  and a line saying it is a ranking, not a share of forecasts right (4 October 2026): as "93%" under "warned of 21% of
  spills" it read as accuracy, and 93% is also NSW Beachwatch's headline figure, a different measure. The opening
  paragraph is short sentences, one idea each. Tables share one style; the three
  reliability tables draw forecast against observed as bars. A table wider than the screen scrolls
  sideways in its own box, between two hairlines, and the bar column keeps at least 120 px. The
  scoring rules fold away under "How the live scoring works", so the page opens on results.

#### Head of every page

Each prose page's `<head>` carries, in this order:

- the title, "Page · SwimSignal", and a meta description (Terms and Privacy have none);
- `theme-color`, the header's slate, `#3d5b5d`, so the browser's own bar runs on from it (one
  value: the site is light only);
- the icon, `icons/icon.svg`, and the Home Screen icon, `icons/apple-touch-icon.png`;
- the stylesheet, `page.css`;
- preloads for the two faces every page uses, `SourceSans3-latin.woff2` and
  `SourceSerif4-latin.woff2`, so that text swaps into them sooner. The italic is rarely used and
  is not preloaded.

The pages were written for an API server (removed 20 Oct 2026), so these links start `/static/`;
`scripts/build_site.py` rewrites each one for the static site (`REWRITES`), and the icons are the
site's own, `src/dipcast/site/icons/`. The 404 page, which the build writes, has the same head with
absolute links, `noindex` and no description. The app page's head is its own, in `index.html`: it
adds the manifest and the Home Screen tags, and asks for `data/spots-lite.json` (`FORECAST`, which
`main()` awaits) and preloads the picture, `icons/fells.webp`. Every view's largest paint is the
picture behind its opening words, and those wait for the forecast: asked for later, the forecast
waited for the scripts at the foot of the page and the picture for the forecast (5 October 2026). A spot's page asks for the spot's own file there too, `data/spot/<id>.json` (`DETAIL`): its overflows and guide, which `spots-lite.json` leaves out (6 October 2026). The Home Screen app's status bar is
`black-translucent`: the page draws under it, its white text sits on the slate, and the header's
top padding takes in the safe area. (From the fifth round to the seventh it was `default`, dark
text, over the paper header.) Nothing in any head is fetched from another site: the app's map
library is this site's own (below). The API server's `/` sends a visitor to the site
(`DIPCAST_SITE_URL`, else swimsignal.co.uk); its own map page, `static/index.html`, which had the
system font, uppercase pill badges and a palette of its own, was removed on 2 October.

#### The map library and the offline copy

Leaflet 1.9.4 is served from this site, `vendor/leaflet/` (from `src/dipcast/site/vendor/leaflet/`,
which the build copies), with its BSD 2-Clause licence and a `VERSION.txt` beside it, for the same
reason as the fonts: no third party receives a request when a page opens. Until 2 October it came
from unpkg.com, which the privacy notice then had to list. The page still pins both files by hash
(`integrity`), and a test checks the hashes against the files; an upgrade replaces the files and
the two hashes together.

The offline copy (`sw.js`) stores only this site's files. Its cache is named `dipcast-<stamp>`,
where the stamp is a hash of the files it stores or that decide what it stores (`SHELL_SOURCES` in
`scripts/build_site.py`: the page, the worker, the scripts, the stylesheet, the icons, the picture,
the fonts, `vendor/`). The build writes the stamp into the worker, so a changed file changes
`sw.js`, browsers install the new worker, and it fills a new cache from the server (`no-cache`),
deleting the old one when it takes over. A hash of the files, not the commit, so a commit that
touches neither (the model, the tests) does not make every visitor download the shell again. The
page asks for `levels.js` and `experience.js` at `?v=<stamp>`, so a page and its level rules always
come from one build, even when one of them loses the 4 s race to the network. A file added to the
worker's `SHELL` belongs in `SHELL_SOURCES` too. The `dipcast-` prefix stays: the worker and the
page's "Turn off the offline copy" clear caches by it.

### What a swimmer wants first (second round, 1 October 2026)

The question a swimmer brings is one of three: is my spot all right today or this weekend; where
near me is low on Saturday; why is it high, and when does it ease. So the home page opens on the
answer. First the heading, one line and the search. Then one row of controls, the day picker and
Low risk, with one muted line under it holding the caveat ("Forecasts, not water tests.") and the
week's best day. Then the saved spots, or one line on how to save one. The kinds of water (rivers,
lakes, bathing waters) are a second row under All spots, because they narrow that list only. The
list carries no colour key: each row says its level in words, and the bars are explained once at
the foot of the list. On a 375 px phone the first saved spot is now above the fold; before, the
first screen was controls alone.

On a spot's page the issue time and today's weather share one muted line between the answer and
the five days, so freshness is read at the point of deciding. While the forecast loads, the home
page shows the list's shape in hairline grey rather than a line of text. Leaflet's own controls
(zoom, attribution, popups, tooltips) use the tokens, the one radius and the map lift, so the map
no longer carries a second visual language. A control keeps its own corner when focused. Fold
summaries and stand-alone text buttons are 44 px targets. (Since 2 October.) Every map's credit is
OpenStreetMap's alone; the terms credit Leaflet. On a map too narrow for the legend and the credit
side by side, the legend sits above the credit's line. A phone's Upstream map shows neither the
legend nor the list's controls, which covered the ringed spot. The phone's small map under a spot's
name is hidden from screen readers (`aria-hidden`), so its credit's links leave the Tab order
(`tabindex="-1"`): the credit stays on the map, a tap still opens its links, and "Open map" beside it
is the way in for a keyboard or a screen reader. (Since 7 October.)

### Where instead (third round, 1 October 2026)

A spot that reads moderate or worse on the day shown, or is rated poor, carries a "Lower risk
nearby" card after its answer: up to three spots within 40 km that are lower that day, nearest
first, each opening on the same day, with one line under them saying a lower level is not clean
water. A spot without a level is never offered, and nor is a water rated poor, because advice
against bathing applies there whatever the level of the spot beside it. In the hero's rows the
sentence with the figures stays in view and the explanation folds under "<label>: what this means"; the
EA advice and "A forecast, not a water test" stay visible. The list's counts begin with the issue
time. On the Saved page the cards come first and Compare below them. A redrawn view rises 4 px
into place over 0.22 s, as a picked day does, and not at all for anyone who asked for less motion.
The desktop legend is the title, the six levels in two wrapping lines and the overflows' key: about
half its old height. A spot's four actions are a two-by-two grid. The brand link is a 44 px target
(padding inside a negative margin, so nothing moves) and the mark's corner is 6 px, the small
radius.

### The way back (fourth round, 1 October 2026)

Back returns to the place it left. The list and the Saved page keep their scroll, and the row that
had the focus, whenever they are left (for a spot, for each other, by Back or Forward) or covered
by the full map, and get both back once on the way back: a reader at row 60 of 89 is not sent to
row 1, and the next Tab carries on from the row they opened. Explore and a fresh load still start
at the top. On a phone, a spot opened from a marker on the full map goes back to the map at the
view it had; its back link reads "Map", and closing the map forgets it. Every spot with a forecast
has a "Nearby" card: the three nearest spots within 40 km, whatever their level, each row giving
its headline. A spot that reads moderate or worse that day, or is rated poor, keeps "Lower risk
nearby", with only lower spots and the line that a lower level is not clean water. On a desktop,
"/" puts the focus in the search and Escape empties it.

Two wording rules came out of this round. A level word stands beside the thing at risk, never
beside the thing measured: the water-quality row says "Very high risk", and a list row "E. coli
risk 63%", because beside "Water quality" a bare "Very high" read as very good water. The
Environment Agency's classification words (excellent, good, sufficient, poor) are used only for
the Agency's own rating. And a button says what happens: the feedback form's button is "Send by
email", which opens the reader's email app with the message, with the copy of the text beneath
as the fallback; it was "Prepare email" followed by a second step.

### A field guide, not a dashboard (fifth round, 2 October 2026)

After four rounds the site still read as generated, and the reasons were specific (they are listed
in `docs/DESIGN-HANDOFF.md`): every block a bordered white card in a column, a saturated teal bar
the loudest thing on every page, a page grey so close to white that only borders separated
anything, seventeen type sizes, a Leaflet-demo map, and no motif. So:

- **One white surface per page.** The hero is the only card. Right now, River level, Nearby,
  Overflows, Day by day, the Saved page's sections and the About section are unboxed: a hairline,
  a serif heading, the content. The list and the Nearby rows lost their container and kept their
  dividers. The Saved page's spots are entries between hairlines, the name in the serif, then the
  headline and the strip. A list someone shared keeps a box while it is on offer.
- **A warm paper page** (`#f6f4ee`), so the white hero lifts without a border and the map reads
  as a different material.
- **A light header**: the paper, the mark and the wordmark in teal, ink links, a hairline. The
  phone's bar at the bottom is unchanged.
- **Six type sizes** (13, 15, 17, 20, 30, 36) as tokens, the spot's name and page titles at 36 (30
  on phones), the headline level at 30, then a real drop to the 17 px body. 40 px from the answer
  to the first section, 32 between sections, 8 and 12 within them.
- **Natural level colours**, moss, ochre, rust and brick, with darker text shades that pass AA on
  the paper and on white.
- **A grey map, then blue water**: the tiles in greyscale, so the markers are the only strong
  colours on it; markers a size larger with a 2 px paper ring; the legend the six keys in one
  line, with the overflows' key below it only while overflows are on the map. Still
  OpenStreetMap, which the privacy notice names. The same day the water came back as a muted blue
  (Colour, above): grey, the lakes had matched the woods and the fells around them, and at street
  level Derwent Water could hardly be told from the land. Faded OpenStreetMap colours were tried
  and dropped, because they bring back the green parks and the coloured roads that competed with
  the markers; so was a paper-coloured land, which turns the fells brown.
- **The river line** from the mark as the one decorative element.
- **Quieter controls**: the chips and the sort control lost their borders (words in the text's
  weight, the chosen one filled); the day strip lost its outer box.
- **Light only.** The dark theme was the light one with inverted tokens, not a design; the site is
  read outdoors, where the light theme's contrast is what counts; and keeping two palettes in step
  had cost each round effort. A dark theme, if wanted later, is a deliberate toggle with its own
  palette.

### The sky and the glass (seventh round, 2 October 2026)

Ethan asked for the cleanness of Apple Weather, and chose the closest of four mock-ups (a paper
version, Apple's order without boxes, Apple's tiles on paper, and this) over the recommended one.
What makes Apple's page clean, and what was taken from it:

- **One answer, first.** The level and "risk" at one size, the title's (36 px, 30 on phones), in
  semibold sans and the level's colour: "High risk", since a bare "High" read as high what. Under
  it, what set it and when ("Sewage spills today"), where the five days go ("Low risk by Tuesday",
  Apple's high and low) and the issue time. Centred, with no box. The first build set the level
  alone at 72 px Light with a small "risk" beside it, as Apple sets "19°"; Ethan found it goofy and
  too large, and picked this from three settings (Regular at 44, this, Bold at 30).
- **A sentence over the days**, as Apple's over its hours, saying something the headline does not:
  "About 13 of the 60 overflows upstream are expected to spill today, fewer each day after."
- **Data drawn.** The five days are rows with a bar of four bands, filled into the day's band and
  placed in it by what set the level (the exposure index, the E. coli estimate where it counts, the
  foot of high for a water rated poor), so the bar always agrees with the word beside it. Drawn
  from the spills alone, a water rated poor showed "High" beside an almost empty bar. The tiles draw
  the exposure index and the E. coli estimate on stepped scales, the river's level on its usual range, every
  overflow upstream as a dot, the rain as columns and the sun's path over the day.
- **One anatomy.** Every tile is a label with its icon, one figure, one drawing, one sentence, and
  the rest of the explanation behind a chevron in its corner: Sewage spills, Water quality, Right
  now, River level, Rain, Weather, the EA rating and the algae where they apply, then Nearby, the
  Upstream map, the overflows that matter most and the day-by-day numbers.
- **A background that is the place.** A picture of fells over a lake (`icons/fells.webp`, 8 KB,
  drawn by `scripts/make_sky_image.py`, so it needs no licence and no request to anyone else) hangs
  behind the opening of each view: its sky ends at the bottom of the answer's words, its fells fill a
  128 px band below them (48 px on a phone since 6 October 2026: see "The first screen"; the list's
  band is 48 px on a wider screen and 28 px on a phone since 14–15 October 2026), and it is
  the paper about 300 px further down. Its top rows are the
  `--sky` colour that runs on up to the header, so it has no edge. The weather data has only the
  day's high, sunrise and sunset, so the picture cannot follow the weather, as Apple's does. A
  photograph would be a separate job, with sourcing and licences. The picture is 500 CSS px wide; from
  2 October a view wider than that (a screen 501 to 800 px wide: a phone on its side, a small tablet) stretches it
  sideways to both edges at the same 600 px height, where before its sides showed as hard vertical edges.
- **Glass, light.** The tiles are frosted (`--glass`, a blur and 76% white). Measured on 2 October
  2026 over the darkest fell: the grey text and the level colours pass 4.5:1 at 76% and fail at
  64% (4.1 to 4.2), so the panes are three-quarters white and the picture shows through them only
  faintly. On the built pages (8,492 text runs, nine views at 320, 375 and 1440 px) every one passes
  AA, against the darkest pixel behind it: the closest are 4.70:1 on the sky and 4.82:1 on the
  glass. Nothing below the
  answer's words sits on the picture without a tile: on the list the saved spots, the hint and all
  the spots are tiles, and so is the empty Saved page. Plain white where a browser draws no blur, or
  the reader has asked for less transparency.
- **Saved as Apple's places**: each spot's name, its level with "risk" (20 px bold), what set it
  and where the week goes, and the week as small bars. The list shows the same cards on one tile.
- **Day by day on Saved** (second outside review, 20 Oct 2026: aligned, the weeks "would improve
  scanning"): a tile above the cards with every saved spot's five days in line (`savedGrid`; the
  cells are `weekCells` in `experience.js`). The names down the left, the days across the top
  ("Today", "Wed"), each cell the day's level with its noun ("Moderate risk") in the level's text
  colour under its 4 px rule, a link to the spot on that day. A day the forecast does not have says
  "No forecast", in grey with no rule. A spot whose level is the same every day has one cell across
  the five in its headline's words, with a rule only if that is a level: "No monitored overflow
  found upstream" in the plain teal, no rule. The Saved page's own cards no longer draw the week:
  the grid gives it once, in line, and the cards keep the answer and why. On a phone each name has
  its own line over its five days, so the days keep the width: 61 px each at 375 px ("Moderate" is
  53 px); the grid is never under 280 px, so a 320 px phone scrolls it sideways by about 20 px.
- **A slate bar on top.** Shown the old teal bar, a sky with no bar and a slate bar beside the
  paper header, Ethan chose the slate: a darker shade of the picture's nearest fells, so it frames
  the sky and echoes the fells under the answer, where the old teal swallowed the mark's teal
  square and competed with the level colours. The river line came off the pages at the same time
  (Icons).

What it reverses, knowingly: one white surface per page (round five) becomes tiles, as Apple's page
is; the level's headline grows from 30 px bold to the title's size, semibold; the light header
(round five) becomes a dark bar again, slate rather than teal. Uppercase labels, borders, shadows
and gradients stay out: a tile's label is normal case, and a bar's bands are steps. Overflow names
that arrive in capitals ("LITTLE SALKELD WwTW") are set in normal case (`nameCase`). The daily E.
coli figures left the five days for the water tile (today and tomorrow) and the day-by-day table.
The prose pages keep the paper.

### What the level counts (11 October 2026)

A Lake District water-quality group wrote that a "Low risk" at Waterhead on Windermere read as "the water
is fine", while rain washes in runoff from grazing land and roads whatever the overflows do, and the wind
decides whether an overflow's water reaches the shore. Nothing near the headline said what the level
counts. So a spot with a daily level has one more line in the answer, after what to do and before the
river line and the issue time (`levelScope` in `levels.js`, `.scope` in `index.html`): ink, the notes' size,
centred as the answer is, no box, no bold lead. Once a page, never in a tile. (20 October 2026: under the
five days, in their tile, after what to do; see "A tighter opening".)

- Every spot with a daily level: "This forecast counts sewage from the monitored storm overflows upstream,
  and the rain that makes them spill. It does not count treated sewage from sewage works, runoff from
  farmland and roads, wildlife or other bathers."
- On a river from May to September, where the E. coli estimate counts that day, the second sentence is
  "It counts treated sewage from sewage works, runoff, wildlife and other bathers only as an average. That
  average comes from the rain here and the time of year."
- Treated sewage, which a works lets out every day, was added to both on 11 October 2026, and to the Method
  page's limits and About's "What it cannot see": it is a source of its own, apart from the storm spills.
- A lake adds "In a lake, the wind decides where river water goes. The forecast does not use wind."
- A plain level keeps its own line, "Other risks apply: ...", which says the same in its place.
- "This forecast", not "the level": at a bathing water the level also takes in the Environment Agency's
  rating and the algae check, which are not forecasts. The words do not rename the level: whether to call
  it a sewage risk is Ethan's decision.

The Method page's "What the forecast does not count" (`methods.html#limits`) is the one place for each
limit and what a swimmer can do instead: runoff, treated sewage from sewage works, wildlife and bathers,
wind and mixing on a lake, spills in dry weather. The page for groups says the same under its levels, and
About's "What it cannot see" (which the decision record copies word for word) adds wildlife, bathers and
the wind. A record shows the lines that apply to its spot (`cannotSee` in `record.js`, 11 October 2026):
Dŵr Cymru's only where its overflows are upstream, and the E. coli estimate's sentence only where the spot
shows the estimate.

### A tighter opening (20 October 2026)

A second outside review: "Its long, centred introduction pushes the five-day forecast down", and "make
the important missing input visible without searching through the page". On a 375 x 812 phone the five
days began 739 px down at Long Bridges and 802 px down at Ludlow, below the screen. So:

- **The answer is one block:** the place, the level, why and when, where the week goes, a long spill that
  may be a fault, the river's separate hazard, one line on what the forecast could read, and the issue
  time. The five days follow at once.
- **What the forecast could read** (`coverLine`, `.cover`): ink, the notes' size, centred, just above the
  issue time. Clauses, each only where it applies: how many overflows upstream report live ("44 of 45
  overflows upstream report live; 1 does not", and "All 45 ..." too, so the line is there every time; on
  today's view only, and not where the line under the level already says "Forecast only: no overflow
  upstream reports live"); the days of the five with no forecast; "Overflows in Wales not counted (12% of
  the river above)"; "Today's EA advice not checked: open it before you swim", linked. A missing input is
  said as missing, never as low. The Wales and EA sentences that sat beside the level since 11 October are
  these clauses now, shorter, in the same place.
- **Under the five days**, in their tile (`answerAfter`, `.after`): what to do, at the sentence's size after
  a hairline, then what the level counts, at the notes' size. A picked day fills it again.
- **Kept:** the sky picture and its glass (seventh round), the 48 px and 128 px bands, the level's size,
  every word of what to do and what the level counts. The answer stays the same element, so the largest
  paint is still the picture behind it.
- Measured on the live data of 20 October 2026, the top of the five days' rows, before and after: Long
  Bridges 739 to 576 px at 375 x 812 and 684 to 543 px at 1440 x 900; River Dart, Spitchwick (low) 669 to
  529 and 677 to 558; Ludlow 802 to 600 and 740 to 585.
- **29 October 2026:** the sentence over the five days had grown again where an overflow too far away
  to count is named ("Grasmere sewage works overflow is upstream too, but too little of its water would
  reach here to count"), and with a flood alert the rows fell below the bottom bar at Waterhead (777 px at
  375 x 812, the bar at 748). That clause now ends what the level counts, under the five days
  (`answerAfter`), word for word. On the live data of 29 October, spots whose first day row did not
  clear the bar went from 7 to 3: Waterhead 777 to 706, Tonbridge 749 to 701, the three Windermere
  bathing waters 716 to 669. Still below it: Frensham Great Pond (the EA's advice against bathing comes
  first, on purpose), River Dart at Spitchwick (two overflows discharging now, 734) and Waterhead by 4 px.
- **Later on 29 October 2026 (the v2 mock-up, Ethan: "Build all of it"):** the spot's name comes first
  and the place (kind, water, size, `.kind`) moves under the issue time; why and when share a line
  ("Right now · Low risk tomorrow", `.wn`), as do what the forecast could read and the issue time
  (`.ci`). Words unchanged. On a phone the page is then the answer, the five days and "Lower risk
  nearby"; everything else goes in three folds named for the question each answers (`phoneFolds`):
  *Why this level* (where the risk comes from, the Upstream map, the day's tiles), *At the water*
  (readings now, the phone's small map, the rating, the practical guide, then reviews, visit notes
  and illness reports), *What this forecast cannot see* ("Not known here", what the level counts,
  the water-test line, the folded detail). Waterhead at 375 x 812 went from 8.7 screens to 3.3, Henley
  from 5.8 to 2.9. A desktop keeps its columns; crossing 800 px draws the page again. The Upstream map
  is closed by default on a phone: the trade-off Ethan accepted for a short page.

### River high and flood alerts (3 October 2026)

A high river and a flood are a different hazard from pollution, so they never set or colour the
level. They get one line in the answer, after where the five days go and before the issue time, on
every day's view (`flowLine` in `index.html`; the facts and their words are `flowFacts` and
`flowSentence` in `experience.js`). The line is in ink, centred as the answer is, its lead in bold,
and it always ends "A separate hazard, not part of the pollution level." The leads:

- "**River high**: the gauge at Addingham is above its usual range."
- "**River rising fast**: the gauge at Addingham rose 0.40 m between 08:45 and 14:30." (more than a
  fifth of the gauge's usual range in six hours).
- "**Flood alert in force here** (Environment Agency): Upper River Wharfe.", the area linked to its
  page, with "and 1 more" where there are others. "Flood warning" or "Severe flood warning" leads
  instead when that is the most severe. "Here", not "nearby": an alert is named only when the EA's
  outline of its area covers the spot's point on its water, or reaches its lake (26 Oct 2026: "nearby"
  had named the River Ure at Burnsall on the Wharfe, 16.7 km away). An alert for the spot's own river or
  lake whose area does not cover it, or one with no outline, is a quiet row of Not known here: "A flood
  alert or warning is in force that could not be matched to this spot." with the EA's flood map linked
  (`floodUnmatched`); never "nearby", since such an area can be 11.6 km away (Lower River Ure at Aysgarth). Alerts for other water are counted in the data, never named.

A failed check never reads as none in force, and it is not a hazard either, so it gets no bold line
in the answer (16 Oct 2026: in bold above the five days on 48 of 105 pages, it read like one).
Instead a quiet line, in the muted meta size, sits under the River or Lake level tile, or under
Weather at a spot with no gauge: "Flood warnings not checked for this forecast. See the Environment
Agency." (`floodUnchecked` and `floodUncheckedLine` in `experience.js`; `.t-note` in `index.html`).
The build asks a failed request once more, 20 s later, before it gives up
(`build_site.attach_flow_state`).

Nothing is said that may have stopped being true. A river word needs a gauge on the spot's own river
and a reading under a day old, and a rise needs its last reading under six hours old; a build over a
day old shows no line at all. Lakes get no river word, because the gauge matched to a lake can be on
a beck or river that shares its name (`build_site.attach_flow_state`); flood alerts apply to lakes as
to rivers. The same sentences go in a plan for today, and the flood ones, with the quiet "not checked" line,
in the Compare table's "Local warnings" row. The River level tile keeps its own words in ink too ("High water", "Usual
level"): "High" in a level's colour read as a pollution level.

### What to do (4 October 2026)

NSW Beachwatch gives an action with each of its levels; SwimSignal gave a level and why, and left the
decision to the reader. The answer now has one line on what to do, after where the five days go and
before the river line and the issue time (`levelAction` and `dayAction` in `levels.js`, `.act` in
`index.html`). Since 20 October 2026 it follows the five days instead, in their tile (see "A tighter
opening"); a spot with no five days keeps it in the answer. It is a sentence in ink, centred as the answer is: never a level's colour, a box or a
bold lead, so it reads as following from the level rather than as a second one. A picked day gets that
day's line, and very high names its day: "Avoid swimming here tomorrow: choose a lower day or spot." A
water rated poor, algae at the last check and the spots without a level have lines of their own. No
line says a spot is safe. The embed card and `alerts.json` carry the same line, and so does a push
notification for one spot, after its headline (4 October 2026: "Very high risk right now: sewage spills. Avoid
swimming here right now: choose a lower day or spot."); the saved cards and the list leave it out, since they are
for comparing spots. Each line and its sources are on the Method
page (`methods.html#actions`), which `tests/site_actions.test.cjs` checks word for word.

### Water on its way (4 October 2026)

Right now's level holds each spill in full until its water has passed the spot, its end plus its travel
time, and counts it for 48 hours after that (`transport.live_now_risk`). Before, a spill died off from
its end, so the headline eased while water from far upstream was still arriving, and before "should
clear by" did. A spill whose water has not reached the spot yet counts from its start: Ethan chose that
over also waiting for the water, which would have dropped headlines to "Low risk" with sewage minutes
away. So the level never waits; one line says when the water gets there.

- In "Where the risk comes from", after right now's sources and before the clearing time, when spills
  whose water has not arrived hold at least half of right now's risk (`now.arriving`): "Water from a
  spill 3.1 km upstream reaches here in about 20 minutes." The tile's other sentences' ink, no bold.
- The time is counted when the page is read: "in a few minutes" under ten, to the nearest ten minutes
  under the hour, "in about an hour", whole hours under twelve, then the part of the day as the clearing
  time says it ("by about Sunday evening"). Moderate or worse only, today only, and nothing once the time
  has passed.
- The Right now tile says "3 stopped lately: a spill counts until 48 h after its water has passed here."
  It said "3 finished in the last 48 h", which a spill far upstream now outlasts. "None stopped lately"
  where there are none.

### Water temperature (3 October 2026)

The Water temperature tile (`waterTile` in `index.html`; the reading is
`build_site.attach_water_temperature`'s) has the tiles' anatomy, after "Rain here" and before
"Weather", with a thermometer from the stroke set. Its figure is the reading in whole degrees, "14°"
with "C", in ink: a temperature is not a level. It has no drawing. Its sentence says where and how old,
counted when the page is read, not when it was built: "Measured at Bures Mill on the Stour, 10.9 km
downstream, 2 h ago." The fold says it is the nearest Environment Agency sensor on the spot's own river,
within 15 km, that has reported in the last day, upstream if there is one; that the water where you swim can be warmer or
colder; and that it is not part of the pollution level, with a link to the sensor's page. Rivers only:
a river sensor is not a lake's water. Where there is no such sensor there is no tile, since the
temperature is never estimated.

### Swimmers' reviews (3 October 2026)

Reviews (`reviews.js`; the service is `reviews/`) are one more tile with the same anatomy, the last of
the part about the water, after the guide and the notes (see "A swimmer's order"). Its figure
is the share who would swim there again, "75% would swim here again", shown from three reviews
(fewer would make a percentage of one or two people), drawn as a bar in ink: a score is not a level,
so it never takes a level's colour, and no tomato, star or thumb stands in for the words. Under the
figure, one sentence ("3 of 4 swimmers would swim here again"), then the reviews between hairlines,
newest swim first: the yes or no in bold as the row's headline, then who and when ("Priya · swam 21
Sept 2026"), the text, photos as 72 px squares that open full size over the page, and Report (Delete
on your own review) in the meta size. The first three show; "Show all" opens the rest. The score is
also a link at the end of the line over the spot's name, the place's own facts, in the meta size,
never in the answer. Writing one opens a form in place of the button: a question to each field, in
the order a swimmer answers them, the yes or no as two buttons that fill when chosen, as a chosen
chip does.

### Practical guides (3 October 2026)

The practical guide (`guide.js`; the facts are hand-written in `guides/`, whose README has the
format) is one more tile with the same anatomy, in the part about the water, after the EA's rating and
before the notes and the reviews: facts first, then opinion. Its label is "Practical guide" with a signpost icon from the stroke set.
Its first line says how far to trust the whole tile: "Checked 3 Oct 2026 from the published pages
linked below, not on site", or "Checked on site", and past a year that fees, opening times and paths
may have changed. Then the facts as a ruled list, a topic's name over its facts, in the order a
swimmer meets them: parking, the path, getting in, getting out, toilets, changing, fees, opening
times, who can swim. Under each fact, in the meta size, who says so, in words: "**Verified**:
City of London Corporation" (the page linked) or "**A swimmer's suggestion**, from Sam, 12 Sept 2026.
Not yet checked by SwimSignal." No colour tells them apart, since colour on the page means a level,
and no badge or pill. Topics with no fact are named in one line, "Not in this guide yet: toilets,
changing", so a gap reads as unknown rather than as none. A photo runs the tile's width in the one
radius, its labels as numbered round markers (ink, with a white ring, as a dot has) and the same
numbers in a list under it, then the caption, the credit and the day. The tile ends with one line
and a link to the feedback form set to a guide. A spot without a guide gets a short tile asking for
one; a point clicked on the map gets none.

Since 4 October 2026:

- **One word.** "Verified" is the notes' word for checked against an official source, so the guide
  uses it too. Before that the tile said "Confirmed". The notes keep "confirm" for a swimmer saying
  something is still so. The files keep `status = "confirmed"`.
- **A dated record says "Source".** A fact from a record of a past date, such as a Defra designation
  consultation, says it is "a February 2026 listing, not a current check". Under it, "Verified"
  would contradict it, so its line is "**Source**: Defra, February 2026." (the page linked), from the
  file's `source_date` (since 27 October 2026).
- **One line for a run.** Facts next to each other under one topic, with the same line of who says
  so, share it. It shows once, after the last of them. Facts in a run sit 4 px apart, closer than the
  10 px between runs, so the line reads as theirs. A new topic, page, day or swimmer starts a new
  line, and a suggestion never shares a verified fact's line.
- **Fold after four topics.** Past five topics, the first four show and "Show all 7 topics" opens
  the rest, as the reviews and the notes do. At five or fewer all show, so the button never hides a
  single topic. "Not in this guide yet" and the photos stay below it. Farleigh Hungerford's tile was
  2,136 px tall on a 320 px phone; folded it is 789 px.
- **Bus and train** (30 October 2026), after Parking, from an operator's or a council's own page. Not
  listed under "Not in this guide yet", as the guides written before it would all gain the same gap.
- **The arrival guide** (prototype, `?arrive=1` only, `arrive.js`; docs/ARRIVAL-GUIDE-2026-10.md). The
  same facts and lines of who says so, in the guide tile's place, as a journey: getting there (by bus or
  train, by car), the path, getting in, getting out, toilets and changing, seasons and fees, each step
  numbered in the sans with its facts as the guide's rows. Then "Who can swim here", "The water" (a
  link to the forecast, nothing restated) and "What nobody has checked", each under a serif heading at
  the body size over a hairline, so that permission, the way in and the water read as three separate
  things. A step with no fact says "Nothing in this guide yet."; a step a photo would make findable
  says "No photo yet of the place to get in." beside a camera from the stroke set, muted, not boxed.
  A photo sits in the step of its `topic` and no other; an overview leads the journey; a sign's photo
  sits under "Who can swim here", after a line saying its wording now and its scope are not verified.
- **Historical photos** (30 October 2026): Geograph's, under CC BY-SA 2.0. The line under one says
  "**Historical photo** by Oliver Dixon, taken 16 May 2023", the title linked to its page, the licence
  linked to its deed, the changes, that this copy is under the same licence, and that it is not
  SwimSignal's and shows that day only, not today's access, permission, water level or conditions. No
  labels on it, and no "Photo:" credit in the caption, which the line already gives.
- **Who can swim stays in view** (30 October 2026). Past the fold, the first four topics and Who can
  swim show, wherever it falls; the fold still opens only when two or more topics would go.

### Notes on a visit (3 October 2026)

A review describes the place; a note describes a day. The notes (`visits.js`; the service is the
reviews Worker in `reviews/`) are one more tile, "Recent visits", with a flag from the stroke set.
The order in the part about the water is the guide, the notes, the reviews. The tile is there only
while reviews are on, and never on a point clicked on the map.

- A note is ticks from a fixed list ("Entry steps or path damaged", "Car park closed", "Very busy",
  "Water looked clear"), a few words and one photo. The ticks, joined by " · ", are the row's headline
  in bold, as a review's yes or no is. Then the meta line ("Seen yesterday · shown until 1 Nov unless
  confirmed again"), the words, and the photo as a 72 px square.
- Each tick ends by itself (`VISIT_KINDS`, which must match `reviews/src/rules.js`): a day for how
  busy it was, a full car park and good news; two for rough water; three for pollution; seven for
  algae; 14 for a closed car park or way in; 30 for damage and a new sign.
- Worst first: suspected pollution or algae, then hazards, then the rest, then good news. Four show,
  and "Show all 6" opens the rest. A good note never sits above a warning. Where the forecast or a
  note warns, a muted line above the first good note says the good one changes nothing, such as "A
  good visit does not change the forecast above."
- Two words are kept apart. **Confirm**: another swimmer says damage, a closure or a sign is still
  there, with "Still like this"; the meta line then says "confirmed by 1 more swimmer, the last today",
  and the tick's days start again. **Verify**: the operator names an official source for a note of
  pollution or algae. Until then the tick reads "Suspected pollution" or "Suspected algae" over "Not
  verified: what one swimmer saw, not a water test."; once verified it reads "Pollution" or "Algae"
  over "Verified: <the source>." Only those two can be verified, and only damage, closures and signs
  confirmed.
- No level colour and no badge on a note: a note is not a level.
- A note of ticks alone is published at the next build without being read first
  (`PUBLISH_TICKS_AT_ONCE` in `reviews/src/rules.js`; kept on 4 October 2026). A note about today is
  worth little two days later, the words are the site's own and it names no one. Words and photos
  are read first. Against a false tick: ten notes a day per connection, "Not verified" on pollution
  and algae, Report, and Delete on `/moderate`.
- The form opens in place of "Say what it's like today". "When were you here?" is Today or Yesterday
  as two chips; the ticks are chips two to a row. Ticking pollution or algae shows the Environment
  Agency's and Natural Resources Wales's incident phone numbers.

### Illness after swimming (4 October 2026, off until Ethan switches it on)

One more tile after the reviews (`illness.js`; the service is the reviews Worker, `reviews/README.md`,
"Illness reports"), there only while reports are on. Its label is "Illness after swimming" with a
thermometer from the stroke set. No report is ever shown, only counts, from five.

- The figure is a count in ink, never a level colour: "6 reports in the last 30 days", or, when the
  30 days have fewer than five, the 12 months' count. Then one sentence, "6 swimmers reported being ill
  after swimming here in the last 30 days, and 11 in the last 12 months.", and "Unverified: what
  swimmers told the site, not a test of the water or a diagnosis." A spot without a count says "No
  count to show: fewer than 5 swimmers have reported being ill after swimming here in the last 12
  months."
- "I got ill after swimming here" is a plain button, not filled: the tile is not an invitation. The
  line on getting help, "Unwell now? Call 111 or go to 111.nhs.uk ...", sits outside the part the form
  replaces, so it stays in view while the form is open.
- The form is the reviews' form: the day of the swim from a list of the last 15 days, the symptoms and
  the onset as the notes' chips, two to a row, the doctor question as two chips, and the consent as its
  own tick with the words "information about my health". An onset that would fall after today is
  shown but cannot be chosen.

### The E. coli estimate out of season, and Not known here (20 October 2026)

An outside reviewer looked at the Thames at Long Bridges, Oxford, on 20 October 2026: "Moderate risk" in the
answer, and under it an E. coli tile whose figure was "56%", labelled "Untested in October". They read two
answers to reconcile, and wrote that publishing a precise number gives it authority whatever the text beside it
says. They asked for observations, missing information and experimental estimates to sit apart.

- **No percentage in view out of season.** From October to April (`ecoliUntested`) no E. coli percentage is in
  a tile's figure, a picked day's row, the shared picture, the organisers' page or the decision record. The tile
  is named "Experimental E. coli estimate"; its figure is "Out of season" (`ECOLI_OFF` in `levels.js`), with no
  band and no scale, whose dot was the figure; its sentence is the one that said what the level counts instead.
  The daily figures fold under "Experimental estimate", with the live record and the Welsh test. The tile goes
  last, after the tiles of what is observed. A picked day's row does the same. The shared picture gives the rain
  under each day unless all five are in season. The organisers' page and the record give `ECOLI_OFF_SAID` in the
  row's place. The day-by-day numbers keep the figures, marked †, since a reader opens that table for the
  numbers; its note says they are experimental. In season nothing changes. On 11 October the band had already
  gone ("Very high risk" under a "Low risk" answer read as a contradiction).
- **Not known here.** One tile straight after the five days, a row for each thing the page could not see, as a
  picked day's rows: the label, two or three words on the right ("1 of 45 not reporting", "Not checked", "Not
  counted", "Not confirmed"), then the sentence it had before. The rows: live readings missing (the overflows
  that could be spilling unseen, a feed down or stale), overflows in Wales, today's EA advice at a bathing water,
  access (the desk check; it was a paragraph under the five days), flood warnings not checked (a note under River
  level since 16 October). No tile where there is no gap. The Right now tile keeps its count and "44 of 45 report
  live."; which do not, and why, moved to the tile.
- **Kept beside the answer as well:** the lines for today's EA advice and Wales (11 October: beside the level,
  where "Low risk" and "Usual care" had stood in for them). Their rows repeat them, so the tile is whole. A long
  spill that may be a monitor fault stays in the answer only: it is a reading, not a gap.
- **Not done:** headings over the tiles ("Forecast", "Observed", "Experimental"), which would put words between
  tiles; proposed in the pull request with a mock, to wait for user testing.

### What the level rests on (4 October 2026)

One tile (`evidence.js`) after the forecast's tiles, folded whole as the day-by-day numbers are (6 October
2026: its figures are on the tiles above it). It lists the
evidence the level rests on, each item with how old it is and whose it is, and then says what there is
none of here. Its figures are already on the tiles above it. This is the one place where their ages and
sources sit together, and the only place with the latest lab sample.

- The rows are a picked day's rows (`.factor`): the item on the left, its age on the right, what it says
  in ink, then whose it is at the meta size. They sit 8 px apart, not 12. Measured at 375 px on the data of
  4 October: five rows (Wharfe at Cromwheel) make a 554 px tile, two rows and a gap (the Eden at
  Armathwaite) 306 px.
- The items, in this order: the overflows upstream (discharging, stopped lately, and how many report
  live, with why the others do not: offline, a feed that is down, a stale feed with its last update, or no
  live feed); the rain; the Environment Agency rating and its year; the algae at the last check; the latest
  lab sample. These are what the forecast takes in, not what it gives out: the exposure index and the
  E. coli estimate stay in their tiles. The river level and the water temperature are left out: they are
  not part of the level, and their tiles date them.
- Ages are counted when the page is read, in UK time: "1 h 30 min ago" within a day, as the issue time
  says it, then "Yesterday", "10 days ago", then whole months.
- The lab sample is one sentence: the count, the day, and whether the count is over 900, the line the
  E. coli estimate is about: "380 E. coli per 100 ml, taken 24 Sept: under 900." A fact about the number,
  not advice. 900 is the inland "sufficient" standard's (Bathing Water Regulations 2013, schedule 5), on a
  90-percentile evaluation over four seasons, so one sample sets no rating; the comparison links to the
  About section's E. coli entry, which says so. A count of exactly 900 is "not over 900". A count given as
  a limit is compared only where the limit settles it ("Under 10 …: under 900"; "Under 1,000 …" is not
  compared). The Compare table on the Saved page gives the sample in the same words (`evidenceSample`).
- The gaps come last, under a hairline, a sentence each, in ink: "No lab samples, algae checks or rating
  here." (the facts only: the line under the five days already says it is not a designated bathing
  water), "No monitored overflow within 60 km upstream, so no spills to go on; farms, wildlife and
  unmonitored sources are not modelled.", "No rain forecast arrived for Thursday.", "No lab sample here
  this season." A sample missing because the build had no samples file says that instead, and links the
  Environment Agency's page.
- Runoff from farms (18 October 2026, review task D7). Where the Environment Agency's Catchment Data
  Explorer lists agriculture and rural land management as a confirmed or probable reason the spot's water
  body does not reach good status, under "Pollution from rural areas", the gaps say so in its words and
  with its certainty, "Environment Agency" linking to its page for the water body: "Runoff from farms here
  is not modelled. The Environment Agency lists agriculture and rural land management as a probable
  reason this stretch of river does not reach good status." A lake is "this lake". Under the no-overflow
  gap, which already says farms are not modelled, only the second sentence. It is a gap, not a row: the
  level does not take it in. The Agency's reasons are about the water body's plants, animals and
  chemistry, not bacteria, so the line says nothing about today's water. "Good status" is left as the
  Agency says it; its page, one tap away, explains it. On the data of 18 October 2026, 36 of the 105
  spots carry the line (23 rivers, 13 lakes), the two Wye spots among them, both "probable".
- No level colour anywhere in it: the rating's word is in ink here, since its tile already colours it.
- Not on a point clicked on the map, nor on a spot without a forecast, whose answer says why.

### How the forecast has done here (6 October 2026, draft)

One tile (`spotscores.js`) right after "What the level rests on", from `data/spot_scores.json`
(`src/dipcast/spot_scores.py`). The live scores are per overflow, so the tile gives the plain sums of the
spot's upstream overflows' rows in `data/verification_live.csv`, under the Accuracy page's rules and its
High risk line (a 40% spill chance at the overflow). Nothing is weighted by reach, so each count can be
found in the CSV.

- Two short paragraphs, then a link to the Accuracy page, then the tile's fold for the definitions.
- First: since when, at how many of the overflows upstream, how many overflow-days, how many with a spill.
- Then one of three: no spill ("nothing yet to judge its warnings by"); under 10 spill days (the counts
  and "Too few spills to give a share: that takes 10"); or 10 or more (the share, worded as the Accuracy
  page words it, "It warned of 26% of those spills", with its counts, and the Accuracy page's "too few to
  judge across different weather" while under 14 days). False alarms are counted as forecasts, as hits are.
- None scored: says so, and why an overflow cannot be scored (no live feed, or no day that passed the
  scoring rules).
- Never "accurate" or "safe". No level colour.
- Not on a point clicked on the map, a failed forecast, an isolated lake, a spot with no monitored overflow
  upstream (What the level rests on already says so), or when the file is missing.

### Today's EA advice (4 October 2026)

The Environment Agency's short-term advice against bathing, after a pollution incident or an algal
bloom, cannot reach the forecast: its service refuses the build's machines, and its API does not answer
other sites' pages. On a designated bathing water's page the rating tile now ends in a fold, "Today's EA
advice" (`eatoday.js`), as each English coastal site on the coverage page has (#116).

- It sits under a hairline at the foot of the tile, after the rating's sentence and its "what this
  means". The summary is in the notes' size at 600, with the folds' chevron. One per page: a picked
  day's rating row has none.
- Opening it loads the EA's embeddable panel for the site, once per page view, from the reader's
  browser, in a frame sandboxed with scripts off that sends no referrer. Nothing is stored. The panel
  keeps the EA's design, since a page cannot style another site's frame, at most 343 px wide as on the
  coverage page. A page cannot read the frame's height either, so it is fixed: 280 px, as on the coverage
  page, and 340 px for a site with no rating yet, whose panel adds two lines saying so; under 375 px wide,
  330 and 400. Measured on the 38 panels on 4 October 2026 (`index.html` has the figures), 280 px alone
  cut the EA's credit line off six panels at every width and seven on a 320 px phone.
- Under it, muted, in the notes' size: "The Environment Agency's own panel, loaded 4 Oct 2026, 16:45. It
  shows no issue time, and browsers may keep it for up to an hour. No warning is not a water test."
- The line under the five days points to it, and its link opens the fold: "Open Today's EA advice, below,
  for the Environment Agency's own panel. It shows any advice against bathing there today, which this
  forecast does not include." (6 October 2026: it said the fold "shows" the advice, but the fold shows
  nothing until it is opened, and the page may not open it for the reader, since the privacy notice says
  the EA is asked only when you choose to.) The rating's sentence no longer says the page lacks the advice.
- The line under the panel ends "If the panel does not show, open the EA's page.", linked (6 October 2026).
  The closed fold's link to the EA's page was replaced by the frame, so a panel that did not load (offline,
  or a frame the browser blocks) left no way to the advice.
- Out of season the panel still shows an open incident: on 6 October 2026 Frensham Great Pond's read
  "Bathing is not advised today due to pollution from harmful algae", Hampstead Heath (Mixed Pond)'s
  "Pollution forecasts will resume when the season starts", and Wharfe at Cromwheel's, rated poor,
  "Bathing is not advised".
- It never sets the level, since the page cannot read the frame. It is not in the embed, the organisers'
  sign or the alerts.

### The swim journal (4 October 2026)

A swimmer's own record of swims (`journal.js`), on the device only. It replaced the one-tap log, "I
swam here today", and reads its entries.

- **On the Saved page, not a page of its own.** A phone's bar at the bottom has three tabs and its header
  one link; a `journal/` page would have needed a fourth tab, or been reachable only from Saved. Saved is
  already the page about what this device keeps, and the one-tap log was there. The journal is its last
  tile.
- **"Log a swim"** takes the log's place in a spot's four actions and opens a form in a tile under them,
  the reviews' form: the day and the time side by side (one above the other at 360 px and under), the
  minutes in the water, a note of 280 characters, up to three photos, then "Kept with the swim", what will
  be kept, in the journal's words. The day and the time are filled in, so logging is two taps where it
  was one. No health questions: the illness reports are separate.
- **"Only on this device."** in bold leads the form's line and the journal's: reviews and notes on a visit,
  further up the same page, are public.
- **What is kept** is what the page showed when the swim was logged: the level and what set it, in a picked
  day's words ("Moderate risk: sewage spills"; right now's spills where they are worse), with the forecast's
  issue time; the rain in the last two days; how many overflows upstream were discharging; the river level
  and the water temperature where the page showed a figure. Only for a swim on the day it is logged, at or
  after the forecast's issue time: the page has no forecast for the days before, and one issued after the
  swim was not there when they swam (a swim with no time keeps none, since that cannot be told). The form
  says which of these it is, under "Kept with the swim".
- **A row** is a review's: the day and time in bold, the spot (linked while it is listed) and the minutes,
  the level in its text colour with "in the forecast issued Sun 4 Oct, 15:29", the figures in the meta
  size, the note, the photos as 72 px squares that open full size, then Delete. No link that sends anything,
  since the journal is private (Ethan, 4 October 2026: the one-tap log's "How was it?" went). Five show,
  newest first; "Show all" opens the rest. A one-tap log entry shows its level "in the day's forecast".
- **A copy**: "Save a copy" makes a file of the swims, notes and photos (a phone offers its share sheet);
  "Add swims from a copy" reads one back, leaving out swims already there. It is how the journal moves to
  another phone, or between Safari and the Home Screen app on an iPhone, which keep separate storage.

### A point off the list (3 October 2026)

A click on the map away from the listed spots (`anypoint.js`) gives a forecast for that point, worked
out in the browser from the files in `data/anypoint/`. On a phone only the full map takes the click.
The card is a listed spot's card (`render` in `index.html`) with these differences:

- The line over the name begins "Unlisted point: not hand-checked".
- No Save. The spot's four actions (the link, the picture, Log a swim, the feedback link) give way
  to one button, "Request this as a spot", which opens a request on GitHub with the point's position
  filled in.
- No E. coli estimate: the Water quality tile reads "not estimated" and says the estimate needs a rain
  forecast for the spot itself, which only listed spots get.
- No practical guide, no notes on a visit, no reviews and no river or flood line.
- The map rings the point with the open spot's teal ring; the point has no marker of its own.
- A click in Wales or Scotland, or on their estuaries, reads "Not covered by the forecast" and "SwimSignal
  has overflow data for England only, so it has no forecast here.", with no request button. The overflow
  data covers England only, so "No sewage risk" there would be false (`outside_england.json`).
- A click anywhere on the island of Ireland, or on its sea loughs, reads the same, ending "no forecast in
  Northern Ireland." or "no forecast in the Republic of Ireland." (4 October 2026). Before, it read "No river
  or lake near this point has a monitored storm overflow within 60 km upstream", which SwimSignal had no
  basis for: its river map has no link there and it reads no Irish overflow data.
- Outside England the card's sentence "This is not a designated bathing water, so the Environment Agency
  does not test it for bathing" gives way to the official source there, after "A forecast, not a water
  test: check the signs at the water before you swim.": DAERA's Bathing Water Quality Dashboard in Northern
  Ireland, the Environmental Protection Agency's beaches.ie in the Republic, and in Wales and Scotland the
  coverage page, which links to Natural Resources Wales and the Scottish Environment Protection Agency.
  The words say who publishes what, and nothing about the water.

### The list's order: lowest risk first (29 October 2026)

The list opens lowest risk first, the question a swimmer asks ("where can I go?"), in place of A–Z by area.
Four sorts: Lowest risk, Highest risk, A–Z, Near me (`SORTS`; Ethan: "surely we want to be able to sort for
lowest risk, and even lowest risk near me?"). The order (`lowOrder`): low, moderate, high, very high, then
spots with no level, then spots whose official notice restricts swimming, last of all whatever their level
(the reverse of Highest risk, where they lead); the nearer first among equals once a place is given; then the
name. A line over the list says "Spots with an official notice come last." while one is in it. A–Z keeps the
areas; the other sorts are one list. Once a place is given, the cards over the list are the lowest-risk spots
within 30 miles in that order (`nearCards`, "Lowest risk within 30 miles"); with none so near, the three
nearest ("Near you"). Before, the three nearest of any level put River Avon, Warleigh Weir (high, 13 miles)
above the Wye at Symonds Yat (low, 27 miles) for a Bristol location. The trade-off: a close moderate spot is
not among the cards when low ones lie within 30 miles; the list, nearest first under Near me, still has it.

### A swimmer's order (6 October 2026)

A spot's page had grown to 7,087 px at 375 px wide (Wharfe at Cromwheel, about nine screens), and its
order followed when each part was built: ten tiles of readings came before the practical guide, the notes
and the reviews, and the Upstream map was near the bottom. The page now follows a swimmer's questions, in
three parts, with no heading of their own (each tile keeps its label, and no eyebrow is added):

- **Should I go**: the answer, the five days, the phone's small map, Nearby or Lower risk nearby.
- **At the water**: the Environment Agency rating, with Today's EA advice at its foot, then the practical
  guide, the notes on a visit and the reviews (and the illness counts, when on). The rating leads because
  it carries the Agency's advice, which stays in view, and because Today's EA advice is the box the line
  under the five days sends the reader to.
- **Why**: "Where the risk comes from" in words, the Upstream map (phones), the tiles of readings, What the
  level rests on, the overflows that matter most and the day-by-day numbers. The last three fold whole,
  with the tile's label as the summary, since their figures are on the tiles above or on the map. The
  overflows' explanation, in a tile's corner fold elsewhere, sits under the rows once the tile is open,
  because the corner would sit on the fold's own chevron.

The order is the DOM's, not CSS `order`, so the keyboard and a screen reader meet the parts in the same
order: after a spot opens the focus is on its name, and the next Tab stops are the five days, the EA
advice link, the map button, Nearby, the rating, the guide, the notes and the reviews. The notes and the
reviews still mount after `#guide`, which stays a child of `.stack`. A tile added after What the level rests
on falls inside Why without any change here. Nothing was removed.

Measured at 375 px on the data of 6 October 2026 (Wharfe at Cromwheel; y is from the top of the page): the
page is 6,079 px, from 7,087; the part about the water starts at 1,642 px, where the practical guide was
at 3,685 and the reviews at 4,839; Why starts at 3,289. At 1,440 px the panel is 5,030 px, from 5,929. A
spot with no overflows (Semerwater) is 3,644 px, from 3,866; a point off the list, 3,755 from 4,177.

Two other orders were shown to Ethan with this one: the same order with nothing folded (7,087 px, the
same as before), and the whole of Why under one fold (4,193 px), which hides the readings' tiles and the
map he chose in the seventh round.

### Why each nearby spot (20 October 2026)

An outside review found the Nearby card around Oxford offering other places on the Thames, which can
share pollution sources, with nothing to say so: Long Bridges, at moderate risk, offered "Lower risk
nearby: River Thames, Hurley", 87 km of river downstream. Each row now has one more line under its meta
line, in the planner rows' `.why` style (the note size, ink): why it is there, from how its water is joined
to this spot's (the build's `catchment` and `linked`, `src/dipcast/spot_links.py`).

- "Same river, shares overflows with this spot." ("Shares overflows with this spot." between a river and a
  lake, or rivers of two names): at least one monitored overflow counts at both.
- "Same river, further downstream." ("Downstream of this spot." otherwise; upstream likewise), then "The
  forecast counts none of the same overflows." where both have overflows upstream: joined by the river,
  but further apart along it than the 60 km the forecast traces. Hurley's row on Long Bridges says this.
- "Same catchment, another branch.": neither's water reaches the other before the tide.
- "Different catchment.": they reach tidal water apart. A plain fact in ink, never a level's colour or a
  reassuring word, since a different catchment has overflows and runoff of its own. Where one is shown
  under "Lower risk nearby", the note under the rows adds: "A different catchment or branch has overflows
  and runoff of its own."
- "Fewer missing upstream readings.": fewer of its overflows upstream give no current reading, and no
  smaller a share of their weight reports.
- No reason where either spot has no place on the network (an isolated lake).

The rows keep every earlier rule: lower on the same days, never a plain level, never a water rated poor,
a known now, within 40 km, nearest first. One rule is added: where none of the nearest three is known to
be on other water, the third gives way to the nearest that is, if one is within 40 km. On the data of
20 October 2026 this changed 8 of the 73 cards: Greenholme offers the Ribble at Stainforth Force in place
of the Wharfe at Burnsall, and Hurley the Wey at Waverley in place of Wallingford. "Lower predicted spill
influence" is not a row's reason: under "Lower risk nearby" every row is lower by the card's own rule,
and the note under the rows says so.

### Four picks from mock-ups (29 October 2026)

A review that day (Vercel's interface guidelines and the "taste" skill's rules, each finding checked)
left four layout questions. Each was mocked up beside the current page, and Ethan picked:

- **The counts go under the list.** Over the list: "Updated Thu 15:42." and any official notice
  (`overviewTop`); the full counts (`overview`, less its issue time) follow the last row
  (`#overview-foot`). The day's answer line above already gives the overall picture. At 375 x 812 the
  first spot moved from 732 to 664 px down, clear of the bottom bar at 748; at 320 x 640 from 843 to 753,
  still below the bar (576), where no option fitted. Rejected: three counts kept above (687 px).
- **The opening on the left edge from 1,100 px.** The spot's answer and the list's, Saved's and Plan's
  openings line up with the tiles below instead of centring over them, which gave a wide screen four
  left edges. Phones keep the centred answer. Rejected: left on phones too.
- **The prose pages take the app's links:** Plan a swim, Saved, Accuracy, About, Feedback. Explore
  went (the wordmark goes home, as in the app). On a phone Feedback leaves the header row, so four fit,
  and stays in every page's foot. Rejected: Explore added to every page, the app included.
- **The Method page's opening:** the lead paragraph in ink, and "In short" on the paper under a hairline
  instead of a white box (Rules for changes, 3). `p.lead` and `.summary` are shared, so every prose
  page's opening is ink and every summary unboxed. From 1,100 px "On this page" sits beside the text
  and stays in view while reading (Method only). Rejected: the same without the contents beside.

### The list's choices in one sheet (29 October 2026)

The sorts, the kinds of water and Low risk only were nine controls between the opening and the first spot
(Hick's law: the more choices in view, the longer each decision). They are now behind one Filter button
beside "All spots", in a sheet that rises from the foot of a phone's screen and sits centred on a wider one
(`#filter-sheet`, a `<dialog>`; Escape or a tap on the backdrop closes it). Inside: Sort, Water, Risk, as
labels in the sans, then "Show 13 spots", the count the list will show. The button carries a count of the
choices that differ from how the list opens ("Filter, 2 on"). The day picker stays in the opening: it
changes every level on the page, not just the list. "Low risk only" left the opening (and the build's copy
of it, `home_lead`); the note under the opening that explains it still shows while it is on.

### What was kept on purpose

The information architecture (list → spot → day), every word of the terms and privacy notice, the
accessibility work (focus rings, `aria-pressed`, 16 px inputs so iOS does not zoom, 44 px targets),
the phone's bottom bar, offline behaviour, and the level rules in `levels.js`. The redesign changed
how things look, not what the site says.

## Rules for changes

1. Add a colour, size or radius only as a token in `page.css`, and mirror it in `index.html`. A
   font size is one of the six `--fs-*` tokens, or it is a seventh size. The two sets must stay
   equal (`tests/test_design_tokens.py`); only the app's layout and filter tokens (`--tile-filter`,
   `--header-h`, `--nav-h`) live in `index.html` alone. The Research Lab's editorial variant (a warmer paper,
   the deep frontispiece, the selected rust, the gap hatching) lives in `lab.css` alone, over `page.css`
   ("The Research Lab", below); a Lab token never redefines the site's radius, ink, brand or type sizes.
2. Place names, page titles and section headings in the serif, 600; risk levels, a row's headline,
   controls and numbers in the sans. No uppercase labels, no tracking.
3. No new radius, shadow or gradient. In the app the answer is unboxed and everything after it is a
   tile (seventh round); within a tile, and on the prose pages, separate with a hairline and
   whitespace, not a box. No words on the picture below the answer's own without a tile under them.
4. Icons are inline SVG from the one stroke set; never a text glyph.
5. A level may colour text, a day's bar and a dot on a scale. It may not fill a surface.
6. Check a change at 320, 375 and 1440 px before opening a pull request. The local preview is
   `.claude/launch.json` (`python3 -m http.server 8766 --directory site`) after
   `scripts/build_site.py` has written `site/`, or after writing the pages alone with
   `build_site.write_pages` over a downloaded `site/data/spots.json`.
7. In `page.css`, the prose defaults for paragraph and list spacing are written as
   `:where(main.doc) p`, with no specificity, so that a component's class sets its own spacing.
   Written as `main.doc p`, a default outranks a single class such as `.note`, and the
   component's spacing is silently lost.
8. Nothing is fetched from another site but the map's tiles (and, when it is on, the page-view
   counter). The exceptions each start with something the reader does, and the privacy notice
   names each: alerts, while they are on (the push Worker); sending, reporting, confirming or
   deleting a review or a note on a visit, and asking about one of yours that is waiting (the
   reviews Worker); opening the Welsh list on the coverage page (Natural Resources Wales's
   data service); and opening "Today's EA advice" on the coverage page or a bathing water's page
   (the Environment Agency's own panel, in a frame with scripts off); and pressing Ask in Ask SwimSignal, while
   it is on (the Ask Worker, and Anthropic behind it). A library is copied into `src/dipcast/site/vendor/` with its licence and pinned
   by hash.

## Review refinements

The PR review kept the editorial identity but made the decision easier to scan: stronger sans-serif
risk headlines, readable day cells with aligned levels, plain place metadata instead of decorative
chips, a visible issue time, and 44 px controls. Secondary text and keyboard focus use shades that
stay legible on the page. The accuracy figures sit on the page between rules, rather than in four
more cards; their numbers use tabular sans-serif digits. Reliability bars draw the forecast in the link shade and the
observed in the muted grey (until 2 October the observed bar was the high level's rust, a level colour on something that is not a
level; then briefly ink, which beside the teal read as two near-black strips). Teal and grey differ in hue more than
in lightness (1.26:1; ink was 2.02:1), so the order, forecast above observed, and the key carry the difference too;
the grey is 4.45:1 on the empty track. On phones the prose header
gives all four navigation links a single full-width row.

## Plan a swim (3 October 2026)

- `plan/` is a view of the app, as Saved is, reached from "Plan a swim" in the header. On a phone it
  was the header's one link until 29 October 2026; it is now "Plan" in the bar at the bottom, which has
  four places: Explore, Map, Plan, Saved, home on the left and yours on the right, each icon over its
  label, as phone apps have them (Jakob's law: people expect an app to work like the ones they know).
  A phone's header is the wordmark alone, and Map's "Back" over the full map. Its choices sit on the sky as the list's do: the day and the distance side by side,
  the starting place as a field with the pin icon where the search has the glass, the kinds of water
  as the list's chips. The distances read "20 miles", not "Within 20 miles", which did not fit a
  320 px phone; the count under the chips says "within".
- The day is a strip of the five days (`planStrip`; second outside review, 20 October 2026), in place
  of a select: each day its short name over its date ("Thu", "23 Oct") in a 44 px target, the day
  chosen filled as a chosen chip is, in a field's box. Radio buttons under it, hidden but focusable,
  so the arrow keys move along the strip and a screen reader reads "Day" and each day. Under 600 px
  the distance is under the strip, full width (the first spot 58 px lower at 375 px than with the
  select); from 600 px beside it, 3 to 1. The address keeps `day=`. The list's and the map's "Today and
  tomorrow" is not offered: a plan has always been for one day (`readPlan`).
- The spots come in up to four tiles, each the list's rows between hairlines with one more line in
  ink, why the spot is there: "Low risk on Saturday", "No monitored overflow found upstream" (a plain
  level), "Moderate risk or higher on Saturday", "No level". Until 20 October 2026 the first two were
  one tile, "Nothing flagged on Saturday", which an outside review read as one answer: a forecast that
  looked and found the risk low, and a spot with nothing upstream to forecast from. The plain tile says
  so in one line under its heading, with the other risks; the foot keeps the view's one "check the
  signs". "Share this plan" holds both tiles' spots and counts each ("14 at low risk on Saturday and 6
  with no monitored overflow found upstream").
- Under each row with a daily forecast, one line on how much evidence sits behind its level, apart
  from the reasons above it (20 October 2026; the outside review asked for the pollution signals and the
  evidence coverage as two things). Muted, the meta size, outside the row's link (`.ev-line`,
  `evidenceCoverage` in `evidence.js`):
  - on a plan for today, a low row whose right now is not known (no overflow upstream reports live, or
    those that matter most do not, a stale feed included): "Forecast only: ...", the words a saved card
    uses. Until 20 October 2026 this was in the why line;
  - whose overflows these are, by reach, and the share of spills the live warnings caught at that
    company, or at the companies the model did not learn from: "United Utilities' overflows, whose
    spills the model learned from. Since 29 Sept it has warned of 37% of their spills." / "Yorkshire
    Water's overflows. The model learned from United Utilities'; since 29 Sept it has warned of 2% of
    other companies' spills." The share links to the Accuracy page's warning table
    (verification.html#warnings) and comes from its file (verification.json, `live.warning_table`,
    `by_company`), fetched once when the plan opens; until it arrives, or if it fails, the rows have no
    such sentence. "Mostly" when the companies named hold under nine tenths of the reach. The counts are
    left to the Accuracy page: every row in a place says much the same, so the line is kept short.
  - Said once where rows share it (22 October 2026: an outside review found the same sentence under all
    eight Oxford rows, which made them harder to compare). The company sentence most rows share, if two
    or more do, is the line under the count instead (`#plan-basis`; `planShared` and `planSharedWho` in
    `plan.js`): "All 8 spots: Thames Water's overflows. ...", "9 of the 12 spots with a forecast:
    Yorkshire Water's overflows. ...". Counted among the spots with a forecast where some have none, so
    the reader is not left to work out which ones are meant. A row keeps its own company sentence only
    where it differs (Skipton's three United Utilities rows), and its "Forecast only" part always.
  - The list and the planner load spots-lite.json, which has no contributors; the build gives each spot
    `reach_by_company` there for this line.
  - Not on a plain level or a row with no level: the first has its heading's line, the second its own.
  - Not on the spot page's answer: the answer is drawn into the built page before any script runs, the
    figure is in a file the spot page does not load, and the line would arrive after the answer and push
    it down. The spot's own scores are in "How the forecast has done here".
- A row's distance leads its meta line ("7.7 miles away · Lake · bathing water"). Miles: travel is
  planned in miles, and Ethan's own example was "within 20 miles". Since 4 October 2026 every
  distance a swimmer travels is in miles, the list's and "Nearby" too; distances the water travels,
  and to a gauge or sensor, stay in km, as the model counts them.
- Before a starting place is chosen, a tile asks for one, with "Use my location" as its button, so no
  words sit on the picture below the band.
- Under that tile since 24 October 2026 (review C6, "the page is empty until a place is typed"): "Most spots at
  low risk today", the three areas with the most spots of the chosen kind at low risk on the day, each a row
  that starts the plan from the middle of the area's spots, at the distance that reaches them all (50 miles at
  most): "Cumbria and the Lake District / 8 of 25 spots at low risk today, within 30 miles" (`planAreas` in
  `plan.js`). Where "Near me" on the list has already taken your position on this page, the plan starts from
  it at once, as before. The page never asks for a position to fill this, and the position is still kept in no
  storage: the privacy notice says it "is not stored, and it is gone when you close the page", so a new page
  load suggests areas instead.
- "Compare these spots" (20 October 2026; the outside review asked "which of these places should I
  look into further for Saturday?" without leaving the plan): a fold under the groups and before "Share
  this plan", as Compare is under the cards on the Saved page. Three selects, offered in the plan's own
  groups, start on the first three spots shown. While it is open it is in the address
  (`&compare=<id>,<id>,<id>`, `plan.js`), so a shared link opens on it, and the page moves to it. A spot
  that leaves the plan (a shorter distance, another kind) drops out, and the first spots shown fill it
  back to three.
  - Found from the count (22 October 2026: an outside review found it worked once opened but was easy to
    miss under the results). The count line ends "Compare spots", which opens the fold and goes to it,
    and reads "Go to the comparison" while it is open. The fold stays under the groups: open, it is about
    2,800 px tall on a 375 px phone, and above the groups it pushed them almost three screens down.
  - While it is open each row has a "Compare" tick at the right of its name (`.cmp-pick`, outside the row's
    link), the first three ticked. A tick adds or removes that spot and the selects follow; with three
    ticked, the others are greyed until one is unticked. Shut, the ticks are hidden.
- Saved's "Compare your spots" and the plan's are one table (`compareTable`; the cells in
  `experience.js`, `compareDays` and `compareRows`). A column a spot, at least 150 px, so two sit side by
  side on a 375 px phone and three in the 1,440 px desktop's list column; a third on a phone scrolls
  sideways. Each row's label is a band across the table, its words kept in view as it scrolls. Until 20
  October 2026 a column of labels took a third of a phone's width and Saved compared one day at a time,
  picked in a select of its own; now both give the five days first, each cell naming its day over the
  level in its colour, the plan's day (or the map's on Saved, else today) shaded with a rule at its left.
  A spot whose level is the same every day has one cell for the five. Then: Right now (what the overflows
  upstream are doing, how many report live and why the others do not, the words of "What the level rests
  on"), the Environment Agency rating, Today's EA advice (never read, so "could not be checked" with the
  EA's page linked, or "None: not a designated bathing water"), water samples, algae, access (the desk
  check's words and date, or "No access information"), local warnings and model limits. Each cell says
  what is not known rather than stay blank. The note above the table: "A lower forecast level does not
  mean safe water: check the signs at the water." No column is called the best.

## The home page's opening, shorter (29 October 2026)

The v2 mock-up's opening, built (Ethan: "Build all of it"). Before it a phone met 14 controls before the
first spot's answer; the first row began 732 px down a 375 x 812 screen, under the tab bar at 748.

- **Near me is a pin at the end of the search field** (`NEAR_PIN`, `.search-loc`, "Spots near me"), as a
  maps app has it, in place of a full-width button. It stays once a place is given.
- **"Or check the river or lake where you are" went**, with `hereForecast`: the map's tap on any river or
  lake does the same. The trade-off Ethan accepted.
- **The five days are a strip**, Plan's (`list-days`), each day with how many spots are at low risk that
  day (`lowOn`, the same count Low risk only gives), and a line under it: "Under each day: the spots at
  low risk, of 109." It replaced the select ("Today and tomorrow" first) and the line under it ("This
  weekend, Sunday: 66 of 109 spots at low risk · Show", `answerLines`, removed). The list opens on today,
  not today and tomorrow together (the other trade-off accepted); the map's own picker keeps both. A
  link from the list carries `#day=` only for a day that is not today, so a spot opens on its own answer.
- The build's copy (`home_lead`) has the pin and the strip, today checked, the counts waiting for the
  forecast.

At 375 x 812 the first spot now begins 544 px down (320 x 640: 555, the bar at 576).

## Your outing, back on Explore (29 October 2026)

An outing made on Plan a swim (a spot, a backup, a time, what for) was kept in this browser (`dipcast.plan`),
but found again only by opening Plan. Explore now shows it above Saved spots, "Your outing", while its day is
one of the five days, its spot is still listed and it has a starting place (`planOuting` in plan.js; without
a starting place Plan draws no outing, so its link would open an empty plan). Under the heading, the plan's
own words for when and what for and the backup by name (`outingResumeSaid`), then the spot as a saved card
for the outing's day (`savedCard`: official advice first, then that day's level), then, where the spot has
official advice, the spot page's line "This level is SwimSignal's forecast. The official advice above is
separate." With paddling or paddleboarding, the plan's note "The level is for the water, the same whatever
you do on it." "Open your plan" opens Plan a swim on the kept plan. Hidden while the list is narrowed, as
Saved spots is. Nothing new is stored, and a day gone by takes it away.

## How an outing's backup is joined to its spot (30 October 2026)

A backup on the same water as the spot can be hit by the same spill, and the outing tile did not say so.
The spot page's Nearby card already works out how two spots are joined (`joined`, `nearWhy`, from
`src/dipcast/spot_links.py`), so the tile now says it in the card's words, in one plain line over the two
columns (`outingJoin` in outing.js): "Backup: shares overflows with your spot." (with "same river" where
both are on a river of one name), "same river, further downstream" or "upstream", "same catchment, another
branch", or "different catchment". The line sits over the columns, not under them: each column runs on
through its access guide, so under them it would be two phone screens from the names. A different catchment
or branch gets a plain fact, never a reassuring word: "It has overflows and runoff of its own." Nothing is
said where either spot has no catchment, or while a shared overflow cannot yet be ruled out (same catchment,
neither spot's own file in). In the backup's list, a spot in another catchment than the spot's carries
", different catchment" after its name; a long name loses the end of it in a closed select on a phone, and
the line says it in full.

## Since you last looked (4 October 2026)

- A saved spot's card says what changed since this browser last showed it, in one line under the
  card's own (`since.js`): "Was low risk when you looked on Friday at 18:20; now moderate risk." In the
  muted grey at the notes' size, since it is history, and never in a level's colour. The same cards on
  the list's Saved spots tile carry it too, while no day is picked.
- One change a card, the first of: the level ("risk" on both sides, as everywhere), a new Environment
  Agency rating ("Was rated good for 2025 ...; now rated excellent for 2026."), and an overflow upstream
  starting or stopping ("No overflow upstream was discharging when you looked on Friday at 18:20; now 2
  are."). A stop is said only while every feed upstream is current, since a feed that is down drops its
  overflows from the count. The day is `levels.js`'s `dayWord` within the week before the forecast's
  day, and the date further back.
- Nothing on a first look, when nothing changed, or when the forecast is the one already seen.
- A spot counts as looked at when its level is on screen with no day picked: its card on the Saved page
  or the list, or its own page. The lines compare with the notes as they were when the page opened, so
  they stay for the visit and are gone on the next unless something changes again.
- Not on a spot's own page: its answer already fills a 320 px phone's first screen (River Eden at
  Armathwaite, 4 October 2026: the five days' heading at 590 px of 640), and one more line would sit
  between what to do and the issue time.

## Named lists and shared links (4 October 2026)

- Saved spots can be kept in named lists (`lists.js`; "Weekend", "Club"). With one list the Saved page
  looks as before. With more, the lists are chips under the heading, as the list's filters are, the one
  shown filled, and the lede names it: "The next five days at the 3 spots in Weekend". The cards, Compare
  and "Share this list" are the list shown; the alerts, the badge and the list's "Saved spots" group are
  every list together.
- "Your lists" folds under the cards, as Compare does: move or copy a spot (a spot, from any list, and a
  list to put it in), rename the list shown, make a new list, and delete the list shown, which asks first
  and says how many spots would no longer be saved. Forms between hairlines; no new colour or radius.
- Save on a spot's page adds to the list shown. With more than one list it says which, "Save to Weekend"
  and "Saved in Weekend"; a long name ends in an ellipsis, and the back link keeps to one line.
- A shared list opens as a page of its own, read only: the list's name as the title, one sentence saying
  someone shared it and that it is not kept until added, one button, "Add to my lists", then the cards as
  tiles without the bookmark. This replaces the fifth round's box offering a shared list. A list already
  added says so, with "Show it". A plan's link opens the cards on the plan's day.
- A spot's back link names the list it returns to (26 October 2026): a shared list's name ("Windermere"),
  or the list shown when there are several of my own ("Weekend"); with one list it stays "Saved spots".
  It said "Saved spots" from a shared list too, though Back went to the shared list. A click still goes
  back in the history; the link's address is the list's, for a new tab. A long name ends in an ellipsis,
  as Save's does, so the row keeps to one line at 320 px.
- Someone with nothing saved who adds a shared list gets that one list (26 October 2026): it takes the
  place of the empty "My spots" a first visit makes (lists.js, `addSharedList`), so there is no chip for
  an empty list beside it. With anything saved, another list, or "My spots" renamed, it is added beside them.
- "Open a list from a link" (26 October 2026, a phone-journey audit): the Home Screen app on an iPhone
  has no address bar and keeps its own storage, so a list sent to someone, or saved in Safari, could not
  be opened in it. A text box on the Saved page takes a pasted link and opens it as the shared-list page
  above, with its own "Add to my lists" and "It is in your lists already"; nothing new is drawn after the
  paste. Only a link to this site's `saved/` with a list in it is taken (`pastedList` in `lists.js`); else
  one muted line says why. Nothing is read from the clipboard. The form sits in "Your lists"; with nothing
  saved, when "Your lists" is not shown, it is a tile of its own under the empty tile, whose Home Screen
  sentence points to it.
- The next step after saving (25 October 2026, a 375 px walk through the Facebook post's link). Save on a
  spot's page says what it did in a muted line straight under the button (`#save-msg`, empty and without
  room until then), with Saved as a link and, where the site has alerts, "There you can also set up alerts
  for them." It said it at the foot of the page, about 6,700 px below a phone's first screen. Where the
  site has alerts, a shared list's lede adds "Once added, it stays under Saved, where you can set up alerts for
  its spots.", and the note after "Add to my lists" ends "To hear when one of its spots reaches high or
  very high risk: Go to alerts", which brings the Alerts tile (about two screens down) into view.
- Facebook's and Instagram's own browsers (`IN_APP`, by their user agents), where a tapped link opens: a
  shared list says, before its button, that a list added there stays in that app and that alerts cannot be
  turned on there, and to open the page in Safari (or the reader's own browser) from the app's menu. The
  Alerts tile there says the same, then, on an iPhone, the Home Screen steps. "Tap Share, then Add to Home
  Screen" was wrong inside the app, which has no Add to Home Screen.
- What a link holds is said beside its button, once: "It holds the list's name, Weekend, and which spots
  are in it, nothing else." A plan's adds the day and "not where you start from".

## The embed and the data page (3 October 2026)

- **The embed**, `embed.html?spot=<id>` (`src/dipcast/site/embed.html` and `embed.js`), is one spot's
  card for a club's or a council's page, in an iframe. It is a white tile with a hairline and the one
  radius on a transparent page, so whatever is behind the frame shows round it. In order: the place
  name in the serif; the headline as a saved spot's card sets its level (20 px bold, in the level's
  text shade, "risk" in it as everywhere); where the week goes; the five days as the spot's page's
  rows under "Pollution risk, next five days"; the caveat; the issue time with the link back; the
  data credits at the meta size. The credits name each source and licence in short, and give the
  Ordnance Survey and Copernicus notices word for word, as `data_credits` in `scripts/build_site.py`
  does. It uses page.css's tokens and typefaces, and
  `tests/test_design_tokens.py` checks its styles as it checks the app's.
- Its rows are 32 px, not 46, since nothing in them is a button. A day's bar fills the day's band (a
  quarter for low, all four for very high) rather than being placed within it: that rule is
  `levelPlace` in `index.html`, and the card does not keep a second copy of it.
- Every link opens a new tab: inside a frame, a link that opened in place would leave the site
  squeezed into someone else's page. It has no map, no page-view counter, and stores nothing.
- It fits a column from 320 px. Measured in Chrome on 4 October 2026 over all 105 spots, with the
  full credits, the tallest card was 783 px at 320 px wide, 681 at 375 and 578 at 480, and none
  overflowed sideways. The snippet on About asks for 800. With the shorter credits that came first, the
  tallest was 637, 553 and 487 on the same data. A stale forecast's notice adds about 90 px, and that
  card scrolls inside its frame.
- **The data page**, `data.html`, is a prose page. A file's fields are a ruled list (`dl.fields`), the
  name over what it holds: in a two-column table the long field names squeezed the words into a
  column a few words wide on a phone.

## Organisers, signs and the live sign (4 October 2026)

- **The organisers' page**, `organisers.html` (`organisers.js`), is a prose page, linked from the app's
  foot ("For event organisers"), from one line under every spot's actions and from About. A spot and a
  day are chosen at the top and kept after the #. Within the five days the day's level is set as a saved
  card sets it (20 px bold, the level's text shade), with a 4 px rule in the level's mark colour at its
  left; the day detail's rows follow as a ruled list (`dl.fields`), in the spot page's words (`spilling`
  and `howSure` are copies, and a test checks `index.html` still has them). Beyond the five days it says
  when the day's forecast first appears (four days before, as the last of its five) and what is known
  now. Always: the overflows upstream as a table, which on a phone becomes a block per overflow, the
  name over its figures two to a line, each with its label; a CSV with the credits; and the checklist,
  which is in the page so that it prints without a script. Printed: A4, no controls.
- **The event week** (6 October 2026). Beyond the five days the page adds "Dates to plan for", a ruled list
  (`dl.fields`): the three laboratory tests British Triathlon's guidance suggests (about a month, two weeks
  and a week before; a month before is the same day of the month before, or its last day), the day the
  forecast first covers the event, and the event. A test date that has passed says so. Dates in another
  year carry the year. Under it, "Add these dates to your calendar" makes an .ics file in the browser, with
  the dates still to come as all-day events. Inside the five days the day view is as it was. Where the build
  says the alert service takes dates (`push.dates` in `spots.json`), "Alert me about this date" follows, in
  either view, only in a browser that has alerts on: its consent folds under "What asking sends", before the
  button, as the Saved page's does.
- The overflows are every one upstream, ordered by reach, which does not change with the weather, since
  an event can be weeks away. `spots.json` keeps ten (`KEEP_CONTRIBUTORS`); where a spot has more, the page
  loads `data/upstream/<id>.json` (4 October 2026; before, 42 of 105 spots' tables were partial) and shows the
  ten until it arrives, saying so, or if it cannot. A tiny reach is "<1%" in the table. The number headers wrap,
  and a feed's name may break after its "_", "/" or "&", so the table fits the 720 px column: measured at 1440 px
  over all 81 spots with overflows, none is wider than its column (14 were before, the widest by 93 px).
- **The sign**, `spot/<id>/sign/`, is a white sheet, centred: the mark and wordmark, the name in the
  serif, one line on what the forecast is, the QR code (black on white, made at build time by
  `src/dipcast/signs.py`), the short address, the caveat in bold under a hairline, and one line of
  credit. It gives no level: printed, a level is out of date within hours. It has no script, and asks
  search engines to leave it out.
- **The live sign**, `embed.html?spot=<id>&screen`, is the embed's card in two columns on the paper: the
  answer and the caveat on the left, the five days on the right, the QR code and address at the bottom
  left, when it last checked at the bottom right. It asks for the forecast every 20 minutes and redraws
  every minute; the 8 h stale notice says whether the build or the screen's connection is behind.
- Both signs are read from metres away, where 36 px is small. Each is laid out in the six sizes at a
  fixed size and zoomed whole: the sign at A6, printed at twice that on A4; the live sign at 960 by 540,
  zoomed to the screen (twice at 1920 by 1080). The steps between the sizes stay the system's.
- None of the three is stored ahead in the offline copy: they are used with a connection, at a desk or
  on a screen, and the live sign must show the newest forecast. A page once visited is kept, as any is.

## The sites view and the decision record (6 October 2026)

- **The sites view**, `sites.html#spots=a,b,c&name=…` (`sites.js`), is a prose page for a centre, a club or a
  council: the name as the title, the issue time once with the app's stale notice, then one row a spot
  between hairlines. A row is the name in the serif with its kind under it, the headline in the level's
  text shade (`headParts`, so "High risk", "High risk tomorrow", the plain levels), the reason in one line,
  links to a decision record for today and tomorrow, and the five days as the list's bars (`.week`, read
  out in words). Where the headline already names the later day, the reason is today's spills in the spot
  page's words. On a phone the name goes above, the bars stay beside the headline. An id not in the
  forecast is named under the rows as not found. The issue line carries the issue id and the site's
  address, and the data credits for the listed spots close the page. Printed: A4, the meta and notes sizes,
  margins 9 by 11 mm, rows 4 px apart, no site foot, since the issue line says what it said. Nine rows and
  the credits fit one page; ten rows did before the credits (5 October 2026), and now carry the credits' end
  to a second page for 13 of 41 lists of ten (live data of 20 October 2026).
  Headings (27 October 2026): the name is the h1, each spot's name an h2 and "Data credits" an h2, so no
  level is skipped and a screen reader steps from spot to spot. Both h2s keep the look they had: the name's
  h2 (`.s-h`) takes no size or margins of its own, and the credits' heading is set at the notes size.
- The link comes from "Make a sites link": under "Share this list" on the Saved page, for the list shown
  (`lists.js`, `sitesHash`), and in a fold on the organisers' page, where several spots are ticked in a box
  that scrolls on its own, in the order they were picked.
- **The decision record**, `record.html#spot=<id>&day=YYYY-MM-DD` (`record.js`), is up to two A4 pages: first what
  it is and is not, with the live warning-table figures; the spot, the day, the level with the 4 px rule
  the organisers' page uses, and why; every input with its time, its age and its source as a ruled list;
  the About page's "What it cannot see", word for word; then labelled lines to write on; then the data
  credits. Printed, the
  rows are two columns and the limits two columns, at reading size: Ethan chose two pages over one page
  zoomed to 0.8, about 8 pt (6 Oct 2026). The decision lines are kept together on one page. Outside the five days it
  says when the day's forecast first appears and gives no record. Linked from the organisers' page for
  the picked day, from each row of the sites view, and as "Print a decision record" under a spot's day.
- **For paid pilots** (20 October 2026, `docs/ORGANISER-PIVOT-2026-10.md`, OP2 to OP4; the wording waits for
  Ethan's approval, then a solicitor's). The record's opening says it is one input to the organisation's own
  risk assessment, beside lab tests, checks at the water, the EA's advice and the water companies' alerts;
  names what it does not cover (algae, leptospirosis, farm and road runoff, outfalls no one monitors,
  physical dangers); says missing data never means low risk; and leaves the decision to the organisation.
  `&org=<name>` in the address names the organisation in the opening and on the first decision line.
- **The issue id** (`printed.js`, both pages) is the build's commit and the forecast's issue time in UTC to
  the minute, `3ed1b5a-20261020T1216Z`: under the record's day and in its printed foot, and in the sites
  view's issue line. spots.json carries the commit as `commit`; every logged forecast's model version has
  the same one.
- **The data credits** (`printed.js`, both pages) are the build's (`data_credits`: `sources`, `companies`),
  one source a line with its licence and what SwimSignal changed, for the sources the page's spots use:
  the companies upstream by name (`upstream_summary.companies`), the EA, OS, Open-Meteo and the Met Office
  where there is rain, Copernicus where there is a model, HydroLAKES where sewage crosses a lake, the EA's
  flood API where the record shows a gauge or flood alerts, OpenStreetMap with its address written out for
  an OpenStreetMap spot. Then the licences written out, since a printed link cannot be followed. On screen a
  list at the meta size; printed, run-on text in two columns at the meta size, line height 1.3, under a
  run-in "Data credits." (a list's items left the foot of each column short).
- The record printed: margins 7 by 10 mm, labels 136 px, writing lines 27 px, the decision beside the
  signature. No `break-after:avoid` on the rows' labels: a label shares its grid row with its text, so the
  rule forbade every break in the list and left a third of page 1 empty. Measured on all 105 spots, today
  and tomorrow, on the live data of 20 October 2026: every record on two pages, the fullest with about 66 px
  to spare (about 107 px before the credits).
- Neither is in the offline copy; both are in the sitemap, as the organisers' page is.

## The coverage page (3 October 2026)

- `coverage.html` is a prose page, linked from the app's foot as "Coasts, Wales, Scotland, Ireland
  and algae" (Ireland added 4 October 2026). It sends a reader to the official services for the
  English coast, Wales, Scotland, the Republic of Ireland and Northern Ireland, and to the UK Centre
  for Ecology & Hydrology's algae map. SwimSignal forecasts none of these.
- Each directory (the English coast, `coastal.py`; Wales, `wales.py`; Scotland, `scotland.py`; the
  Republic, `ireland.py`; Northern Ireland, `northern_ireland.py`) is
  written into the page by `scripts/build_site.py` and folds under its own summary, "Search the
  English coastal directory" and the like, so the page opens on the links and what they are for. The
  lists are in the page, so they work without JavaScript.
- Inside, a search field filters by name, with a count kept up to date ("<n> of <total> sites").
  Accents and apostrophes do not count, so "Tra Mor" finds "Trá Mór". The
  list is rows with a hairline under each, in a box at most 32rem tall that scrolls on its own
  (`page.css`).
- A row is the water's name, linked to its official page, over one small paragraph: its kind and its
  rating with the year ("2025 rating: Excellent"), then, where the source has them, the advice and the
  latest sample, each with its date. The advice names its agency ("At snapshot: EA: increased
  pollution risk"). Advice past its expiry is replaced in the browser by "This EA advice has expired;
  check the official profile". A Scottish row has the rating alone and sends the reader to the
  Scottish Environment Protection Agency's page for the rest. An Irish row shows a restriction in
  force, or DAERA's advice against bathing, in semibold before the sample, in the source's own words
  with its date; nothing on the page is coloured by a SwimSignal level. A sample more than 30 days old says so.
- Opening the Welsh list asks Natural Resources Wales's data service for current samples and
  forecasts, from the reader's browser, and the privacy notice names it. Rule 8 under Rules for
  changes does not yet list this request.
- Each list ends with its credit and licence, and says the agency does not endorse SwimSignal.

## Overflow history and the page for groups (6 October 2026)

- **Overflow history**, `spot/<id>/profile/` (`src/dipcast/profile.py`, template `src/dipcast/site/profile.html`,
  written by `write_profiles` in `scripts/build_site.py`), is a prose page with no script, one per spot with a
  page. In order: the title, links back to the spot and the organisers' page, the caveat in a plain paragraph,
  "In short" as a summary box, each year 2021 to 2025 as a table, then every overflow upstream by reach, then
  the sources. Tables are the Accuracy page's (`.tw`, numbers right in tabular figures); the number headers
  wrap. On a phone (540 px or less) the overflows' ten columns become a block per overflow, the name over its
  figures two to a line, each with its label, as on the organisers' page. A spot with nothing upstream, an
  isolated lake or no forecast gets the caveat and one paragraph saying so. Linked from the spot's
  "Overflows that matter most" tile and under the organisers' table as "Overflow history, 2021 to 2025".
  In the sitemap; not on the data page (it is HTML, not data) and not in the offline copy. Printed: A4, no nav.
- **For clubs, centres and leaders**, `clubs.html`, is a prose page like About, linked from About and the
  app's foot beside "For event organisers". Its limits come first, in a summary box. Its action lines are
  `levels.js`'s word for word (a test checks), each quote is word for word from a page opened on the date
  given in the page's comment, and level words carry "risk".

## Each overflow's record (31 October 2026)

- **`overflow/<id>/`** (`src/dipcast/overflow_record.py`, template `src/dipcast/site/overflow.html`, written by
  `write_overflow_pages` in `scripts/build_site.py`) is a prose page with no script, one for every overflow with an
  annual-returns id upstream of a spot with a page. In order: the plain name, then the company, its own name and the id
  as the dateline; the caveat (not a water test; a spill count is not a finding that a permit was broken); the record
  as label-and-value rows (stacked on a phone); the spots downstream, each linked to its page and its overflow history;
  spills each year as the Accuracy page's table; recent spills; improvements recorded; spills in dry weather only where
  the spot page's rule notes them, labelled as SwimSignal's inference with the method linked; "Send this record"; the
  sources.
- Every figure is a source's, credited on the page. What a licence does not allow is named with its reason ("not
  published here"): the consents register (internal use only), Southern's and Yorkshire's own event files and the
  companies' plan layers (no licence), Water UK's plan (its terms forbid reuse).
- Words: neutral and factual. Never "breach", "illegal" or "safe"; a WINEP date is "the date the action should be
  delivered, a deadline, not a record that it was".
- "Send this record" is the one filled button (`.btn.primary`). It is a `mailto:` with no address: the draft names the
  company, the overflow, its last two years' counts, the improvement entry and the WINEP date, asks one question and
  links the page. The company's own contact page and UK Parliament's "Find your MP" are ordinary links. The draft is
  also shown in a fold for anyone without a mail app. SwimSignal sends nothing.
- Linked from each overflow's name in the spot page's "Overflows that matter most" and on its overflow history. In
  the sitemap; not in the offline copy or on the data page. Printed: no nav, no send section.

## The first screen (6 October 2026)

- **The first saved spot fits on a 375 x 812 phone.** Before, the Saved tile began behind the bar at
  the bottom. Three changes, from three options shown to Ethan (the PR lists them): the caveat and the
  line for groups are one line ("For swimming and water sports. Forecasts, not water tests.", then the
  link to the clubs page; two short sentences, since one sentence joining the caveat to the list of
  activities read oddly); the week's best day follows it on its own line; and on
  a phone the fells' band under the opening is 48 px, not 128, so the first tile starts on the fells,
  which show through its glass. Wider screens keep 128.
- **15 October 2026: the list's band on a wider screen is 48 px.** At 128 it was an empty band of fells
  between the opening and the list, and on a 1440 x 900 screen only the first spot showed, at the
  foot. A spot's page keeps 128 on a wider screen.
- **15 October 2026: the list's answer line** (option B of the 13 October mock-ups): "Sunday: 67 of
  105 spots at low risk · Show", in the display face at the heading size (the body size on a phone,
  so it stays one line at 375 px), the count in the low colour. It names the weekend's better day
  while the five days reach one, and otherwise the week's best. The best-day line follows only when
  the week's best is another day with more spots at low risk.
- **"Low risk only"**, not "Low risk", on the list's switch: it hides every spot that is not low risk,
  as the map's switch of the same name does. Under 375 px it takes two lines ("Low risk", "only") so
  that "Today and tomorrow" still fits beside it.
- **The opening is in the built page.** The home page carries the list's opening down to the caveat's
  line (`home_lead` in `scripts/build_site.py`, word for word the script's, which a test checks), and a
  spot's page its name and description under the sky, each with the first tile's shape in grey below.
  So the picture, the largest thing on the first screen, paints without waiting for the forecast:
  measured on 6 October 2026 at 375 px on slow 4G, the largest paint moved from 4.4 to 2.4 s on the
  home page and from 4.3 to 2.4 s on a spot's page. What depends on the forecast (the best day, the
  build's notices) comes after the caveat's line, so the opening never grows above it and the
  picture never paints again, larger, when the script draws the real one. Words typed into the search
  before then carry over.

## Near you first (14 October 2026)

Ethan chose this from three mock-ups (near you first, an answer line with the list by area, a trim
only), shown at 375 and 1440 px on the day's data.

- **Near me under the search.** One full-width button, "Show spots near me", the way most people come
  in. It is in the built page too (`NEAR_CTA`, word for word the script's), so the picture still paints
  before the forecast. Once a place is given, the button goes and the three nearest spots show as cards
  ("Near you") above the list, each with how far it is; the list sorts by distance. The cards hide while
  the list is narrowed by a search, a kind of water or Low risk only. The place stays in the page, as
  before.
- **A–Z until then.** The list no longer opens on the highest risk, so a first look is not a stack of
  red rows. A refused or failed location says so under the button that asked, and the list keeps its order.
- **Less before the first spot.** The line for groups moved to the foot of the list. The line on how to
  save a spot shows only once a spot has been opened in this visit (nothing is stored for it). On a
  phone the fells' band under the list's opening is 28 px; a spot's page keeps 48.
- **Not changed:** the counts line keeps "Pollution risk:", since a level word needs its noun.

## Cards to share (11 October 2026, draft)

Pictures of the forecast for Instagram and Facebook groups, drawn by `src/dipcast/cards.py` at
1080 x 1350 and 1080 x 1080, with a caption to paste beside each. The build writes them to
`site/cards/`, with a page at `cards/index.html` (noindex, in no sitemap, linked from no page) that
shows them with their download links; `scripts/make_cards.py --out <dir>` makes the same from the
live site's data.

- **Two kinds.** A weekend card per area (`AREAS`: an area's spots and the short name each gets on
  the card): the coming Saturday and Sunday, or today and tomorrow when run on a Saturday or a Sunday;
  none on a Monday or a Tuesday, when the five days do not reach Sunday. A storm card: the spots with
  monitored overflows upstream discharging now, most first, at most eight; none at all when no
  overflow is discharging, never an "all clear" card.
- **The page's words, not new ones.** A day's level is `alerts.json`'s, which `levels.js` writes, so a
  card says what the spot's page says on that day. The cells sit under a column headed "Pollution
  risk"; a spot with no daily level goes in a line under the table in its headline's words ("No sewage
  risk from monitored overflows at Buttermere and Wastwater."); a water rated poor gets the rating's
  sentence. The storm card's clearing time is the "Right now" tile's (`clearSentence`, `partOfDay`),
  and its count is in the very-high brick, the colour of an overflow discharging now.
- **The site's look.** The slate header with the mark and the address, the paper, Source Serif 4 for
  the area and the spots, Source Sans 3 for the rest, hairlines between rows, dots in the level marks
  and level words in the text shades. No text under 28 px, since the card is seen at about a third of
  its size; every text colour is 4.5:1 or more on its ground (a test checks). The foot gives the issue
  time and "A forecast, not a water test."; the storm card adds the overflow data's CC BY 4.0 credit.

## The map's dots, the list's key and the folds (31 October 2026)

From a walk through the live site at 375 px. What was measured, and what changed:

- **A tap lists the spots under it.** At the zoom a phone opens on, 100 of the 109 dots overlapped
  another (each 18 px across, the nearest a median 4 px away), and a tap opened whichever was drawn
  last. Now every dot within 20 px of the tap is listed in a card at the map's foot, as the list's own
  rows; a row opens its spot, and past three, "Zoom in" fits the map to them (the Lakes went from one
  pile to a median 19 px apart). On a phone even a lone dot gives a card, so you see what you hit
  before the map goes; with a mouse, which can hover for the name, a lone dot opens at once. The dots
  are not grouped under a count: a cluster's one colour would hide a high level among lows.
- **One float at the map's foot.** "Forecast for any water" and "Search an area" moved into the key,
  now "Map key, notices and help". A returning visitor's phone map had three floats there, a first
  visit four (with the first-tap line); now one, or two.
- **The list's key once.** "Risk L/M/H/VH" (#519) is on the first row with risk bars, in the list and
  in the map's card; rain rows keep "Rain mm", the exception. Every row's letters and its full
  description for screen readers stay. The bars sit at the row's edge, so they line up without the key.
  Six rows fit on a 375 px screen where five did.
- **Every folded tile alike.** Saved's "Activity preferences and swim journal" and "Learn about water
  conditions" had the browser's triangle in the text face, beside "Open a shared list" in the display
  face with the chevron. Every `details.sec.tile` now opens on its name in the display face with the
  chevron.
- **Plan's place field** kept 52 px on its right for the location pin it does not have, and read
  "Starting fror" at 375 px.

## Ask SwimSignal (31 October 2026, off until Ethan deploys it)

A question in plain words on Plan a swim, answered from SwimSignal's own data (`ask/README.md`). One tile, "Ask
SwimSignal", above the plan's groups, only while spots.json has `ask` (`DIPCAST_ASK_URL`): a field and an Ask
button on one row, and one muted line saying an AI model answers from SwimSignal's data, that the question goes to
SwimSignal and Anthropic, and to leave out personal details, with a link to the privacy section.

- **The model's words apart from the data's.** The day as a small heading, the model's summary, then "Read as:"
  with how it read the question, muted. Then the spots, one a row between hairlines: the name (a link to the
  spot's page, on the day), distance, kind and area muted, the model's phrase on why it fits, then SwimSignal's lines
  for the day, each with its source and date muted under it. The official advice line is first and in 600 weight;
  the rest are regular. Then "Not known", a list, and the notes, muted. The last line says when the data was issued,
  that an AI model wrote the answer, and links to Plan a swim with the same day, place and distance.
- **No box for the answer**, no pill, no eyebrow, no callout: it is the tile's content, as the plan's groups are.
- **Never "safe" or "clean"**, as everywhere on the site. The Worker refuses an answer whose words use them,
  judge a spot for children, or name a condition or a number its data did not give.


## The Research Lab, and its manner on the rest of the site (1 November 2026)

Ethan chose the Research Lab's look as the reference for the deeper evidence: real satellite plates, drawn
catchments, ink on paper, serif headings, numbered figures with captions, and gaps drawn as gaps. This pass made the
Lab part of the same product and carried a restrained share of that manner into the forecast pages. The forecast
answer, the five days and official advice keep their place and their look.

**One shell.** Every Lab page loads `page.css` and then `prototypes/research-lab/lab.css`. The build puts the site's
own header (`build_site.site_header`, with Research Lab as the current page) and the phone bar in place of the
stand-in a repository preview shows. So the fonts, header, phone bar, fields, select arrows, tables and type sizes
are the site's, written once. `lab.css` resets the few prose-page defaults that would otherwise reach its controls
(labels, check boxes, range sliders, `.note`), each with `:where(.lab)` so any Lab class still wins.

**The Lab's editorial variant.** These tokens differ from the site's on purpose, in `lab.css` alone:
- a warmer paper (`--paper`, `--paper-2`) with its grain, and a warmer `--card`, `--line` and `--rule`;
- the deep frontispiece (`--deep-2`, `--deep-ink`, `--deep-muted`; `--deep` itself is a shared token, since the
  covers on the forecast pages sit on it while they load);
- `--pick`, the selected state's rust, and `--gap`, the hatching for missing data;
- `--fs-title` 44 px (32 on phones), an exhibit's one large line.

Radius, ink, brand, bar and the six type sizes are the site's. The Lab's old 6 px radius and its 21 px heading
size are gone.

**Navigation.** The header's desktop links gained "Research Lab" (`lab/`) and renamed "Research" to "Research &amp;
data" (`research.html`, now titled "Research and data"). The phone's More menu has both. The four primary phone
destinations are unchanged. Under the header each Lab page has its own bar: "Research Lab", then the four exhibits
numbered. The page you are on is in white with a rule under it, so colour is not the only sign. On a phone the bar
scrolls sideways, and the current one is scrolled into view. Each exhibit ends with the previous and next exhibit by
name, the overview at either end, and "Back to the forecasts".

**An exhibit's opening.** The order is the title, the question, then the answer in a sentence or two. "The figures
behind it" are folded under the answer. Then one scope line (exploratory, the outcome cutoff), then "Data as of": the
dates in one line, with how each part is refreshed and when the page was built inside the fold. A part past its
refresh limit is said outside the fold, in amber, never hidden. A file that fails to load replaces the answer with a
plain sentence. The repository-only advice ("serve the repository root") is in the README, not on the site.

**Places.** A spot's page has "Explore the evidence" after its detail tiles, never above the answer. It lists only
the exhibits that hold that spot's own record, each opened on it: its lake (`#lake=`), its overflows (`#spot=`), its
bathing water (`#bw=`), and its workspace catchment with the spot in focus (`#c=…&spot=`). The keys come from
`build_site.attach_lab_links`, in the spot's own file. A spot no exhibit holds is told so, with a link to all four.
Each exhibit links back to "Today's forecast for" the place it shows. A link to a lake, bathing water, catchment or
spot an exhibit lacks says so in a status line and names what is shown instead. It never swaps one in quietly. In
exhibit 1 the wide picture follows the selected lake. Where that lake has no wide picture, the line under the
pictures says which lake the picture is.

**Covers.** The four exhibit covers are pictures (`prototypes/research-lab/assets/covers/*.jpg`, 320 px), taken from
the Lab front page's own drawn covers. They appear on the Research page, on Accuracy (exhibit 3), in the spot page's
tile and in the home page's invitation. On the Lab's front page each card is one link. Its cover is drawn inert
(`drawMap({inert: true})`: no focusable points, `aria-hidden`), with `pointer-events: none` inside, so nothing in a
card is a control of its own.

**The manner on the forecast pages:**
- **Routes** (`.routes`, in `page.css`, repeated in `index.html` as the tokens are): the cover in the plate's ink
  hairline, "Exhibit n" in the monospaced face of a figure label, the name in the serif, one line, between hairlines.
  There is no card.
- **The home page:** one compact "Research Lab" block after the list and its footnotes, below the task of finding a
  spot. It shows the four routes, two columns from 541 px.
- **A spot's Upstream map:** a figure in the Lab's manner. The map is square-cornered in an ink hairline with the
  plate's corner ticks, and its caption opens with its name in the serif ("Upstream of …"). Only this map: the small
  phone map and the full map are unchanged.
- **Accuracy:** one route to exhibit 3 under the lede, in place of a link in the lede's last sentence.

**Words.** The Lab's pages say "exploratory" and keep their distinctions: a satellite index is not a toxin
measurement; a hindsight estimate "would have flagged", it did not warn; the model's weight is a factor from 0 to 1,
not a share arriving; the lake coverage is pooled over five sites. The spot page's tile says the Lab changes nothing
in the forecast.
