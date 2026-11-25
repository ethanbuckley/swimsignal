# Research on the site: what each page says about evidence (25 November 2026)

Ethan, 25 November 2026: "The new design has no link to the Lab at all, and results live in docs a swimmer never sees.
Propose and build how a place's page, the home page and the method pages should carry what we have learned: what is
tested, on what, and what is not known."

The redesign has been the site since 24 November 2026 (`DIPCAST_REDESIGN=1`, #738). Checked on the source of main
`7b704b8e`:

- Its header has Map, Plan a swim, Saved, Accuracy, About and "Earlier version". Its foot has four links: Method and
  limits, How accurate it has been, Privacy, Terms. Nothing links the Research Lab, Research and data, the model
  scorecard or the research catalogue.
- A place's page shows the level, the sewage spill risk with each overflow's chance of a spill, the E. coli estimate
  (a percentage in season at rivers, "Out of season" otherwise, with the winter word at rivers today), the water
  temperature estimate, and the model weight of each overflow upstream. None of them says what it was tested on. The
  only links are "How the forecast is made" and "How accurate it has been", under Behind the level.
- The earlier version's "Explore the evidence" (the Lab's exhibits that hold the place's own record) and the home
  page's research line were not ported, and neither is among the five reversals Ethan decided on 25 November.

Each recommendation is marked **new**, **already decided** (with the DESIGN.md section) or **reversing** (with why).
Everything here can be built now from files already in the repository. Nothing changes a level, a figure or a test.

## The place's page

1. **"Explore the evidence"**, the Lab's exhibits that hold this place's own record, each opened on it, after the
   rest of the page. **Already decided** ("The Research Lab, and its manner on the rest of the site", Places, 1 November
   2026): the same exhibits, keys (`lab` in the place's own file, from `build_site.attach_lab_links`), words and
   covers as the earlier page's tile, and "It changes nothing in this forecast". **New:** its place, last before the
   foot, as the 1 November desktop order put it last; a point tapped on the map has none, as before. **New:** its last line
   also links Research and data and the coverage page ("Beaches, Wales, Scotland and Ireland").
2. **"What each figure was tested on"**, a section after Behind the level, Upstream and Elsewhere, before The record
   here. One row for each figure the page shows for that place and day: what it was tested on (years, places), the
   result in one plain line, what is not known, and a link to the test. **New.** Named so, not "What this rests on",
   because "What the level rests on" (4 October 2026) is already the name of the inputs-and-ages tile in The record
   here, and the two would read as one.
   - Each row carries one of four fixed labels, chosen by the data, never written per row: "Tested on data it never
     saw", "Development result, on data already seen", "Checked against samples: no gain shown", "Not tested". So an
     untested figure cannot read as tested, and a development result always says so (the wording rules, fixed).
   - Missing data is said as not known, never as a negative. A satellite index, if one is ever listed, says it is not
     a toxin measurement (the file's check refuses a satellite row without those words).
   - Measurements (the overflows' monitors, gauges, the Environment Agency's samples, ratings and algae checks) are not
     models: one line says each names its source where it is shown. They get no row.
3. **One data file drives it.** The rows are a new `figures` list in `data/research/research_catalogue.v1.json`
   (minor version 1.1.0; its contract gains the field). Each row names the figure key the page draws, the kinds of
   water it applies to, its basis, its three lines, its links, the catalogue entries and scorecard models it rests on,
   and verbatim quotes from its records. The build writes the small public file `data/research/figures.json` from it
   (`build_site.write_figures`). The check holds every number in a row's lines to its quotes, so a figure cannot drift
   from its record. A new result is a changed row; a new figure is a row plus the key where the page draws it. **New.**
   - **A coastal entry later** is one row with `"kinds": ["coast"]` and its own figure key, which the PR that draws
     the coastal figure adds to `figuresShown` in `model.js`. Nothing else changes.
   - **The lake range** has its row now, though the redesign does not draw it (reversal 5, "E. coli as a row", is to be
     looked at again in May 2027). It shows on the method page today and on a lake's page once the page draws it.

## The home page

4. **The research line**, after the list: how many candidate models are being scored beside the live forecast,
   without changing it, and the date the next test is read, with links to the model scorecard and the Research Lab;
   "Research: a model is tested before it changes a forecast." when the scorecard cannot be read. **Already decided**
   ("After the review: near me, the record, the research, a shorter phone page", 12 November 2026), words and rule
   (`researchNow`) unchanged. It was dropped when the redesign became the site, and is not among the five reversals.
5. Nothing else on the home page. A count of tests passed or a tile of results would answer a question no swimmer
   brings to the first screen ("Tried and removed: the poster home page", 20 November 2026).

6. **Where the listed places stop**: one line under the areas, and under a search that found nothing, "Beaches, and
   waters in Wales, Scotland and Ireland that are not listed here: their official sources and past samples", linked to
   the coverage page (`coverage.html`), the only page with England's coastal directory and the Wales, Scotland and
   Ireland directories. The redesign linked it from nowhere. **New.** "Not listed here" rather than "not forecast",
   since the Scotland trial lists some Scottish places.

## The header and the foot

7. **The foot takes the site's one list of links** (`build_site.FOOT_LINKS`, less Data credits, which the foot's own
   credits fold gives, as the app's foot does). That brings Research and data, Method and Every spot to every
   redesign page. **Already decided** ("One foot, one opening", 12 November 2026). The redesign's own first sentence
   and its two folds stay.
8. **The header stays without the Lab.** **Already decided** ("One product in the bar, one entry for organisations",
   6 November 2026): the Lab is reached from Research and data, About, Accuracy and each place's page. Putting it back
   in the header would reverse that, and nothing found here argues for it.

## The method pages

9. **Method** (`methods.html`) gains a section, "What each figure was tested on", written by the build from the same
   file: every row, for every kind of place, each with its own anchor. A place's rows are the same words, so the two
   cannot disagree. **New.**
10. **Research and data** gains one line under "Tests and their results" pointing to that section. **New.**
11. **Accuracy** is unchanged. It already opens on the live record, links the scorecard and routes to exhibit 3
    ("The answer first on Accuracy, Research and For organisations", 17 November 2026).

## Not proposed

- Badges, pills or coloured labels for "tested" or "not tested": the label is words in the muted colour; colour on
  the page means a level.
- Any change to a level, a figure, a test, a window or a verdict. The rows restate what the records say, with their
  numbers; where the register and a record differ, the catalogue's `register_note` already says so.
- A Lab link in the header (8 above).

## Pull requests

One per piece, each from main: (a) the foot, "Explore the evidence" and the coverage line; (b) the figures, the place's section, the
method page's section and the Research line; (c) the home page's research line.
