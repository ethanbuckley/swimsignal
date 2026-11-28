# Past samples after rain on the new site (rebuild of #703)

Written 28 November 2026. [#703](AFTER-RAIN-SAMPLES-2026-11.md) (15 November, Ethan's choice that day) built this line
for the earlier page, which is now `classic/`; it was never merged and conflicted with main. Ethan said "Yes, rebuild
it" on 28 November 2026.

## What the site now says

At the Serpentine, Hampstead Heath's Ladies, Mens and Mixed Ponds, and Colwick, May to September only, "The place" gains
an "After rain" fact:

> Past samples here, May to September 2023–2026: after more than 10 mm of rain in the 2 days before, the middle of 12
> read 190; after less, the middle of 67 read 130. E. coli per 100 ml. Rain here in the 2 days to midday today: about
> 14 mm. Past samples, not a forecast.

(The Serpentine's figures; today's rain from the day's forecast row.) No estimate, word, colour or level.

## What was kept from #703, unchanged

The export (`scripts/export_after_rain_samples.py`), its file (`data/research/after_rain_samples.v1.json`, no rain value
in it), the build step (`build_site.attach_after_rain`: only where the page has past samples and daily rows, so these 5
lakes), `typical.middle`, its tests, and its record. The figures and the 10 mm split are #703's, made on 15 November.

## What changed from #703

- **The page.** The line is a place fact on the new site (`afterRainLine` in `levels.js`, `placeFactsHtml` in
  `preview/app.js`), not a sentence in `classic/`'s tile; `classic/` is unchanged, as for the other lake work since the
  switch. Its words follow the beach cards' "by rain" lines ("2 days", "the middle of N read X").
- **What sits beside it.** Since #703 these lakes gained the lake word (#767) and a likely reading with an 8-in-10 range
  on their own level (#771). #703's DESIGN entry said "Not done: a higher / lower than usual line": that was about the
  fixed twice-or-half rule, which #767 replaced with each lake's own thirds. The three now sit together: the range (an
  estimate, tested on unseen years), the word (its order, tested), and this line (counts of past samples).
- **Not carried over:** #703's change of one sentence in `classic/`'s tile.

## Checked

`tests/test_after_rain_samples.py` (#703's), `tests/site_preview.test.cjs` (the line in season with today's rain,
"under 1 mm", no rain figure, out of season, no split, and where the page calls it). A local copy of the live data of
28 November, with the split and the season put on the Serpentine by hand, at 375 px: the fact sits between "Last sample"
and "Algae". **Not checked:** a live build's split (it attaches now; it shows from 1 May 2027).
