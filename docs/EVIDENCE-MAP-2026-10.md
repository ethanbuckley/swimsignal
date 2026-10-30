# Evidence map (prototype, 30 October 2026)

A spot page can show where its forecast has evidence upstream and where its knowledge ends. It is behind
an opt-in, `?evidence=1` on a spot's address (`spot/<id>/?evidence=1`). Without it the page draws nothing
new and asks for no extra file. The model and the data are unchanged: the map reads files the build
already publishes.

Code: `src/dipcast/site/evmap.js` (view), a small hook in `src/dipcast/site/index.html` (`EV_MAP`,
`mountEvMap`, one host after "Not known here"), two lines in `scripts/build_site.py` (copy the file, add it
to `SHELL_SOURCES` so its `?v=` stamp changes with it), and `evidenceSince` exported from `evidence.js`.
Test: `tests/site_evmap.test.cjs`, on the live files of 30 Oct 2026 trimmed into
`tests/fixtures/evmap_cromwheel.json` and `evmap_symonds_yat.json`.

## User task and success measure

User task: "Before I go, show me where SwimSignal's forecast for this spot has evidence, and where its
knowledge ends."

Success measure: a reader shown the poorly covered spot does not conclude the water is clean because the
map looks empty or calm. In detail:

1. "We have little evidence here" looks and reads differently from "the evidence we have shows no spill",
   in words and in marks, never by colour alone.
2. Every item tapped shows its source, when it was observed and how old that is, and how it stands to the
   spot ("25.7 km upstream, about 36 h at the model's 0.2 m/s").
3. Gaps are drawn, not left out: overflows with no live feed, feeds down or stale, the 60 km trace limit,
   the unmeasured rivers between the marks, no gauge, no lab samples.

## What is shown

A tile, "Where the evidence is", under the five days on a phone (the folds leave it there) and in the first
column on a desktop. Top to bottom:

- **One line that answers the question first**, with a mark beside it:
  - "Little evidence here." (hollow dashed mark) when no overflow upstream reports live, or when those that
    report carry under half the modelled reach. This is the same half-way line where the page stops giving
    a right-now level (`levels.js`, `NOW_WATCHED_SHARE`). It says the level is the model's estimate from
    the rain forecast and past spills, "not a reading", and "A quiet drawing here means not known."
  - "Live evidence for most of the reach." (filled mark) with the count, the share of reach, and what they
    reported at issue ("none discharging, 2 with a spill lately whose water the model still counts").
  - "No overflow evidence here." where nothing monitored is upstream, with "An empty drawing does not mean
    nothing reaches the water".
- "Readings as at this update, issued 30 Oct, 17:49 (1 h ago)."
- **The drawing**: the traced rivers from `data/spot/<id>-trace.json`, the spot ringed, and every overflow
  upstream. The overflows' positions and names come from `data/upstream/<id>.json`. No map tiles are used:
  the drawing shows only what the forecast knows. A scale bar is given in straight-line km.
- **The key**, listing only the marks this spot has.
- **"Every mark and gap in words (N)"**, folded. It has two lists, "Readings and records" and "Gaps: what is
  not known here". Each row has what it is, its age, what it says, where it is from the spot, and whose it
  is. The spot's own items (rain, rating, algae, lab sample, and their gaps) come from `evidence.js`, so the
  two tiles use the same words.
- **A tap** on a mark, the spot or a river shows that row under the drawing. Taps on the same place step
  through the marks there ("1 of 2 here: tap again for the next"), because a town's overflows overlap.

Marks (shape first, colour only repeats it):

| Mark | Meaning |
| --- | --- |
| filled dot, ringed (brick) | reported a spill: running, or lately and still counted |
| filled dot | reported not discharging, from a current feed |
| hollow, struck through | in a live feed, but no current reading: offline, stale, feed down, or a reading now over 6 h old where the page is read |
| hollow, dot inside | in a live feed, but this page's data does not hold its reading (see below) |
| hollow, dashed | not in any live feed SwimSignal reads |
| short bar across a river's end | where the trace stops, about 60 km up the rivers |
| blue line | river traced; nothing along it is measured |
| square beside the spot | lab sample held (filled) or none (dashed) |

## How the gaps are drawn

- **No live feed** (Dŵr Cymru Welsh Water, or an overflow missing from its company's feed): a hollow dashed
  ring at the overflow's place. The row says "No live reading" and that "the model estimates its spills from
  the rain forecast and its past spills". The source given is the Environment Agency's annual returns.
- **No current reading** (offline monitor, stale feed, feed down): a hollow, struck-through ring. The row
  gives the reason the data has. The age is counted where the page is read, so a quiet reading becomes a
  gap once it is over 6 h old (`FEED_CURRENT_H`).
- **Readings this page does not hold**: `spots.json` lists the 10 overflows that matter most this week
  (`KEEP_CONTRIBUTORS`) with their live state. The upstream file has every overflow but no live state. For
  the rest, `evmapOthers` takes the 10's states away from the spot's counts (`now.monitored_upstream`,
  `discharging_upstream`, `recent_upstream`). It gives each one a state only when the counts leave a single
  answer. Otherwise they are drawn hollow with a dot, and the row says, for example, "Of the 6 overflows
  upstream like it, 5 reported live at issue and 1 did not; which is which is not in the data." Cromwheel
  is in that case today.
- **The 60 km limit**: the trace file does not say which line ends were cut at 60 km. `evmapEnds` walks
  the lines as a graph from the spot. It marks a dead end as a cut only when it lies 97% of 60 km or more
  along the rivers (58.2 km), because lines simplified to 25 m measure a little short. The row says it is an
  estimate.
- **The rivers between the marks**: tapping a river gives "Nothing along them is measured: only the
  overflows marked are counted, and farms, wildlife and other sources are not modelled."
- **No gauge, no lab samples**: no lab samples is a dashed square beside the spot and a gap row. No gauge
  within 15 km is a gap row. When there is a gauge, its row gives its distance in a straight line and says
  it is not drawn: the data gives its distance, not its place.

The words keep the site's rules. "Reported upstream" and "modelled to reach" are used, and nothing says a
spill caused anything at the spot. The tile does not use "safe" or "clean"; a test checks this. No level
word appears without its noun.

## The two spots (live data, 30 Oct 2026, issued 17:49 UTC)

**Well covered: Wharfe at Cromwheel, Ilkley (`bw-uke4100-08901`).**
- 16 overflows upstream, all Yorkshire Water. 13 report live, carrying 74% of the modelled reach.
- At issue, none was discharging. 2 had spilled lately (Grassington STW, ended 28 Oct 10:32; Kettlewell
  STW).
- 2 of the listed 10 were offline (the two Addingham overflows, 4.1 km).
- The 6 not listed: 5 reported and 1 did not, and the data cannot say which.
- Gauge at Ilkley, 1.0 km away. Lab sample 24 Sept (380 E. coli per 100 ml). Rated poor (2025).
- Three river ends measure 58.3 to 58.7 km along the rivers and are marked as where the trace stops.

**Poorly covered: River Wye, Symonds Yat (`wye-symonds-yat`).** Chosen because it is the thinnest
evidence of the 109 spots in `spots-lite.json`:
- None of its 14 overflows reports live (0% of the reach). All belong to Dŵr Cymru Welsh Water, which has
  no live feed SwimSignal reads.
- No lab samples, algae checks or rating: it is not a designated bathing water.
- Its gauge (Lydbrook) is 4.5 km away.
- The trace is cut. Eight river ends lie between 58.7 and 59.5 km along the rivers, and the furthest
  counted overflow, Fownhope, is 51.9 km (about 72 h) upstream.
- The page shows "Low risk from sewage spills" over five low days.
- The current Upstream map draws its overflows as light grey "no current reading" dots, which are easy to
  miss on the tiles. That is the calm-looking map this prototype is meant to prevent.

Nearest rivals, set aside:
- Sandy Lane, Chester: 1 of 13 report live, 2.6% of the reach, but it has a lab sample and a gauge 2.9 km
  away.
- River Wye, Hereford: 0 of 14 report live, but its gauge is 0.2 km away and its furthest counted overflow is
  nearer (46 h of travel against Symonds Yat's 72 h).

## Not done

- **Cut ends are estimated**, not known. The build could write them into the trace file, since
  `transport.traced_lines` knows which lines it shortened. Until then, a source near 58 km can be marked
  as a cut, and a cut that simplification shortened below 58.2 km is missed.
- **Per-overflow live state beyond the top 10.** Adding `status`, `data_state` and `feed_updated_at` to
  `UPSTREAM_FIELDS` (`build_site.write_upstream`) would remove the "not in this page's data" case. It
  would add up to about 80 bytes per overflow (measured on one row's JSON; about 15 kB for Warleigh Weir's
  185).
- **The gauge's position** is not in the data, so the gauge is not drawn.
- **Lakes**: the walk starts at the line end nearest the spot. In a lake, the lines that run in may not
  join, so cut ends there may go unmarked. Not checked on a lake spot.
- **The offline copy**: `sw.js` does not store `evmap.js`, so `?evidence=1` does not work offline.
- **Keyboard**: the drawing's marks are not focusable. The folded list is the full text alternative, and
  the drawing's `<title>` points to it.
- **Widths**: checked at 375 and 1440 px only, not at 320.
- **Not rendered through `build_site.write_pages`.** The local preview served the source files with one
  `<base href="/">` added (see below).

## A 5-minute check with a real person

Use a phone, someone who swims in rivers, and neither spot's page seen before.

1. Open `spot/wye-symonds-yat/?evidence=1` and hand them the phone. Say only: "You're thinking of
   swimming here this weekend."
2. After 30 seconds, ask: "What does SwimSignal know about sewage upstream of here right now?" **Pass**: they
   say, in their own words, that it doesn't know or has no live readings. **Fail**: "nothing's spilling",
   "it's clean" or "it's fine".
3. Ask them to tap the ring nearest the spot and read it out. **Pass**: they can say who the reading would
   come from, that there is none, and how far upstream it is.
4. Ask: "Is there anything further up the river this doesn't look at?" **Pass**: they find the bars or the
   "trace stops" label, or say the forecast stops about 60 km up.
5. Open `spot/bw-uke4100-08901/?evidence=1` and ask: "How is this one different?" **Pass**: they say more
   of it is watched or reported, without going by colour. Ask what the hollow marks there are.
6. Note their words verbatim. One "it's clean" or "nothing upstream" at step 2 means the head line and the
   hollow marks are not doing their job.

## Local preview used for the screenshots

No build was run, so no Open-Meteo calls were made.

1. Copy `src/dipcast/site/*` and `src/dipcast/pages/fonts` into a scratch folder.
2. Put these live files under it: `data/spots-lite.json`, `data/spot/<id>.json`,
   `data/spot/<id>-trace.json` and `data/upstream/<id>.json` for the two spots.
3. Add `<base href="/">` after `<head>` in the copied `index.html`. Without it, the page's move to
   `/spot/<id>/` makes every relative fetch 404. Built pages carry their own `<base>`.
4. Serve the folder with `python3 -m http.server`.
5. Open `/?spot=<id>&evidence=1`.

The screenshots were taken in headless Chrome over CDP with the clock fixed an hour after the data's issue
time.
