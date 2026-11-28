# Research Lab exhibit 8: a lake the model has never seen

Written 28 November 2026. The pipeline's "bring research onto the site" item; Ethan said "Yes, build them".

## What it shows

`lab/lakes/`, the eighth exhibit. Its question: at a lake it knew nothing about, could the lake model tell which days
would read higher, and how high? Its answer, read from the committed results:

- **The order held.** At the 7 lake bathing waters with no level of their own, 2012 to 2022, the model ordered each
  lake's samples at 0.289 against −0.015 for the earlier lake figure (bench read 1). At Windermere and Frensham, 0.286
  (#584).
- **A typical lake's level did not.** Each sampled lake treated as unknown on 2023 to 2026: 69.4% of samples inside the
  8-in-10 range, 41% at the Serpentine, labelled development (the average-lake check). Windermere and Frensham treated as
  unknown on 2012 to 2022: 75.6%, too high there (#584's supplementary refit).
- **Its own level did.** The 7 lakes on their own levels, 2012 to 2022: 86.9% inside (bench read 2). Windermere and
  Frensham on their own levels: 78.9% (#584).
- What it changed on the site, what it cannot tell you, and three questions with their 2027 reads.

## How it is made

`scripts/lab_lake_reads.py` writes `prototypes/research-lab/lakes/reads.json` from committed files only (#584's two score
files, the two bench result files, the average-lake check, and `spots.csv` for the lakes' positions), with the sources'
hashes; `check` compares the committed file with them. The page types no figure (tested). NaN values in #584's file
(a model it did not score) are left out, as a browser's JSON reader refuses them.

## Also changed

- Every exhibit's bar and the what-if prototype's link to exhibit 8; exhibit 7's "next" goes to it.
- The front page: a card with a drawn cover (the 12 tested lakes, filled where the model had their own level), and its
  credit line.
- `assets/covers/lakes.jpg` (320 px), taken from that drawn cover in the app's browser with the big number hidden, as the
  other covers were; the Research page lists exhibit 8 with it.
- A place page's "Explore the evidence" lists exhibit 8 at the 12 tested lakes (`attach_lab_links`, key `lt`) and says
  "All eight exhibits" in place of "All five".
- `lab/refresh.json` gains `lake-reads` (dated reads, never stale).

## How it stands to what is decided (docs/DESIGN.md)

- **Already decided, followed:** the Lab's shell, bar, pager, front-page covers and the editorial notes (the Research
  Lab, 1 November 2026); exhibits are published on data already read and say what each figure was tested on.
- **New:** the exhibit and its words.

## Checked

`tests/test_lab_lake_reads.py`, `tests/test_lab_build.py` (nine links in every bar, eight covers, the sitemap, the lab
links), `tests/site_preview_lab.test.cjs`. Served from the repository at 1440 and 375 px in the app's browser: every
figure drawn, no sideways scroll; one 404 for `refresh.json`, which exists only in a site build.
