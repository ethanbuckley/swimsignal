# Screen audit and proposed hierarchy (#549)

Live site, 31 Oct 2026, forecast issued 12:47 UTC. Phone at 375 × 812, measured in headless Chrome with
`tools/measure.js`. "Screens" is page height ÷ 812. "Grey blocks" counts visible paragraphs, list items and labels
drawn in the muted text colour. Full-length screenshots are in `before/`.

| Screen | Example | Screens | Words | Words on first screen | Grey blocks | Folds |
|---|---|---|---|---|---|---|
| Explore, 3 saved | home | 17.3 | 2,952 | 127 | 34 | 4 |
| Spot, normal | River Eden, Lazonby | 3.8 | 578 | 72 | 57 | 9 |
| Spot, official advice | Frensham Great Pond | 3.7 | 539 | 151 | 67 | 9 |
| Spot, stale gauge | River Dove, Dovedale | 3.5 | 490 | 57 | 71 | 9 |
| Spot, an overflow's feed stale | River Cam, Grantchester | 3.1 | 478 | 73 | 55 | 9 |
| Spot, no river drawn in, no gauge | Loughrigg Tarn | 3.7 | 510 | 66 | 13 | 0 |
| Spot, no overflow upstream | Wastwater | 3.4 | 461 | 69 | 46 | 7 |
| Plan, with an outing | Grasmere, backup Rydal Water | 10.0 | 1,679 | 70 | 67 | 8 |
| Research | research.html | 5.2 | 854 | 194 | 0 | 0 |
| Satellite viewer | lakes.html | 3.2 | 623 | 158 | 1 | 0 |

## What gets in the way of the four tasks

**1. Find my water and see temperature and current information.**
- Explore opens on a heading, the search and a five-day count strip. The saved spots start below the middle of
  the first screen, and each card is about 220 px tall, so three saved spots fill a whole screen.
- No card shows water temperature. On a spot page it is in "Water conditions", the third tile, after the five
  days: about 1.5 screens down.
- A spot page opens with a grey sentence about overflow polling, above the answer.
- The temperature line repeats itself: "12°C, provisional estimate. About 12 °C (provisional estimate, not yet
  checked in these months)."

**2. Understand an official warning, stale data or a missing estimate.**
- Official advice is in the right place: first, in its own box. But the page says three times that it is separate
  from the level: "Follow this advice first. It is not SwimSignal's…"; "This level is SwimSignal's forecast. The
  official advice above is separate."; and "The Environment Agency's notice above was last checked…".
- Frensham's first screen also says "Live sewage spill status unavailable…" in bold, then "Modelled forecast",
  then the level. Four statements come before the answer.
- A stale river gauge (Dove) and a stale overflow feed (Cam) are mentioned only in grey paragraphs inside folds.
  Nothing next to the value says "stale".
- Missing values are said twice, far apart. On Loughrigg Tarn, "Lake level: No gauge reading available here" is
  in Water conditions, and the temperature appears again lower down as "Forecast for today". The reason there is
  no five-day strip (no river or beck is drawn into the tarn) is a grey paragraph under the heading.

**3. Pick a date and time, compare an alternative, save the plan.**
- Plan is 10 screens long. The outing editor is the second tile, inside a fold that starts closed. Separate tiles
  follow: the 22 suggested spots under "Low risk tomorrow", "No monitored overflow found upstream" and "Moderate
  risk or higher", then Share, Find a window and Compare.
- "Keep this outing" sits above the choices it would keep. "What would change this plan" is long prose.
- Each suggestion has its own explanatory sentence, often repeated word for word ("A spill from the overflow
  upstream is possible, not expected.").

**4. Find Research and open a viewer on a phone.**
- The More tab (#546) fixed reaching Research on phones, except on iOS before 17, which #552 fixes.
- Research's first screen is 194 words of prose. The four viewers are text links in a list. Nothing says what you
  can look at or how fresh it is.
- The satellite viewer is a table and a chart of an index. It has no map of where the reading is taken, no
  picture, and no way to step through dates. "Latest" means the latest in the dataset; the weekly check's result
  is one line further down.

## Proposed hierarchy

Every spot page, card and plan column follows the same order: what to do first, the answer, then the
conditions. Each value carries its own kind and age.

1. **Official advice**, when there is any, as one compact block: who said it, what it says, since when, when it
   was last checked, and a link. One sentence says it comes first and is separate from SwimSignal's level. That is
   said once.
2. **The answer**: the level with its noun ("Moderate risk from sewage spills"), the day, and when it changes
   ("Low by Tuesday"), plus one line of reason in plain numbers. Where nothing upstream is monitored, the answer
   says so and says why in that one line.
3. **Conditions**, in a compact grid. Each value is labelled with its kind (Measured, Estimated, Forecast,
   Observed) and its time. A stale or missing value is stated where the value would be ("No reading since
   15 Oct"), not in a fold.
4. **The five days**, as now but smaller.
5. **One primary action**, "Choose a swim time", and one secondary, "Compare another spot".
6. **Alternatives**: at most two, each with its level that day, its distance and whether it is on the same
   river.
7. **Details on demand**: "Why this level", "What this forecast cannot see" and "Methods and sources" as named
   disclosures. The methods prose moves into these, so it stays in the product.

Explore leads with **My waters**: one compact row per saved spot, showing the level, the temperature, and a flag
for official advice or stale data. The search comes next, then a route to the map and the full list.

Plan becomes one flow: **When**, then **Where** (spot, then backup), then **Your plan** side by side, then
**Save**.

Research leads with four entry cards. Each says what its viewer lets you do and how fresh the data is. The
satellite explorer (#550) is the first.

## What stays

- The words for levels, the official-advice rules (eatoday.js), "provisional estimate" and the claim limits in
  the lake contract. The prototype changes where these are said and how often, not what is claimed.
- Saved spots, lists and plans stay in the browser. No account, analytics or new service.
