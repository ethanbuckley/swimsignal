# Page-only builds, November 2026

Written 24 November 2026, with the change it describes.

Marks: **[measured]** a time or count from a real run or a command I ran. **[estimated]** arithmetic on measured
parts, not a run. **[not tested]** nothing has run it yet.

## What changed

A push to `main` that changes only what the pages are made from no longer forecasts again. The build job fetches
the site the last build published, writes the pages over it, and deploys that. The data in `data/` is left as it
was, so every page still gives the time that forecast was issued.

A second change skips the tests in the build job when the merge commit holds exactly the files Test Python
already passed on the pull request.

Scheduled, chained and manual builds are as before. They always forecast.

## How a push is judged

Three checks, in this order. Each can only say no, and any no is the full build.

1. `scripts/page_only.py changes <last build's commit> <this commit>`, before anything is installed.
   - Every changed file must be one the pages alone read: `src/dipcast/site/`, `src/dipcast/pages/`, `docs/`,
     the three `scripts/prerender_*.js`. Tests, `README.md`, `.gitignore` and `scripts/preview_redesign.py`
     are read by no build and are ignored.
   - `src/dipcast/site/levels.js` and `scripts/alerts.js` are a full build by choice. They hold the level rules,
     and the alerts Worker sends by them.
   - `scripts/build_site.py` holds the forecast and the page writers in one file, so it is judged by definition.
     A changed function, constant or import counts only if `build()` can reach it without going through the
     steps a page-only build runs again. A name both halves use is a full build.
   - Anything else is a full build: the workflow, any other Python, data, guides, the Lab's files, a new path.
2. The last build's site must download, and its forecast must be under 120 minutes old (`MAX_AGE_MIN`).
3. `build_site.py --pages-only` checks that the state on the runner belongs to that forecast and that no
   `DIPCAST_` setting has changed since. A full build leaves a note for this in the state, `site_build.json`.

If the page-only attempt fails for any reason, the step deletes `site/` and runs the full build.

The base for check 1 is the commit of the newest successful run of this workflow on `main`, not the push's
parent. A push that waited while an earlier one was replaced in the queue is compared with what is live.

## What a page-only build runs again

`alerts.json`, the share cards, every page, the reviews' sections, and the Lab's dates. The Lab's river paths,
which a full build makes from its own network, are the last build's, put back. Nothing else in `data/` is
touched. The state is read and not saved.

## Measured

### Before: the five builds of 24 November 2026, after PR #734

Seconds, from `gh run view <id> --json jobs`. **[measured]**

| Run | Merge | Waited for another build | Tests in the build job | Build step | Build job | Push to live |
|---|---|---|---|---|---|---|
| 45459134074 | #734 | 2 | 267 | 539 | 839 | 857 (14.3 min) |
| 45460548841 | #735 | 386 | skipped | 334 | 366 | 770 (12.8 min) |
| 45462861863 | #736 | 3 | 165 | 423 | 618 | 637 (10.6 min) |
| 45463609471 | #737 | 386 | skipped | 280 | 310 | 740 (12.3 min) |
| 45471777984 | #738 | 3 | 294 | 744 | 1,072 | 1,091 (18.2 min) |

Over the 21 newest runs on `main` (20 to 24 November): the build step took 280 to 748 s, median 548 s. The tests
ran inside the build job in 7 of them, for 165 to 544 s. The deploy job took 8 to 37 s. **[measured]**

### After: the page-only path on a runner

Run 45477900460, a throwaway workflow on a throwaway branch (deleted). It ran the new steps as written in
`site.yml`, against the site that run 45471777984 had published 24 minutes earlier, with `main`'s state restored
read-only. It published nothing. **[measured]**

| Step | Seconds |
|---|---|
| Can this push rebuild the pages only? | 3 |
| Fetch the last build's published site (50 MB) | 3 |
| Build step, page-only | 52 |

The rebuilt site had the same 7,148 files as the published one. Two differed, `lab/refresh.json` and
`reviews/index.json`, each by the time it was written. Every page, card and data file was byte for byte the same.

The build step falls from a median 548 s to 52 s. A whole page-only run should take about 85 s for the build job
and 11 s for the deploy, so about 1.7 minutes from push to live when the tests are skipped too. **[estimated]**
from the measured steps. No page-only run of `site.yml` itself exists yet, because that needs this merged.
**[not tested]**

### How often it applies

Replaying `scripts/page_only.py` over the 20 pushes that built the site from 17 to 24 November: 9 were page-only
by their files. In 7 of those the last forecast was under two hours old, going by the run times. **[measured]**,
with one caveat: for
#735, which changed `build_site.py`, the replay skipped the check that `rebuild_pages()` exists, since it did not
yet.

On 24 November itself it would have applied to one build of five (#735). #734, #737 and #738 changed `site.yml`
and #736 changed the forecast.

### The tests

24 of the last 40 merges had a branch that already held all of `main` (`git merge-base --is-ancestor`), so the
merge commit's files were the pull request head's. **[measured]** For #738 I ran the new step's check against the
API: same tree, and Test Python had passed that head at 19:34. Its build then ran the tests again for 294 s.
With the new rule that build would have gone from 18.2 to about 13.3 minutes. **[estimated]**

Where the branch was behind `main` the tests still run in the build job, as now.

## Limits

- The two-hour limit is my choice. A page-only build keeps the forecast it finds, so a push no longer refreshes
  it. Scheduled builds were a median 4.6 hours apart in October and November, so a page push was often the
  freshest forecast of the afternoon. Under the limit the cost is at most two hours of age. Raise `MAX_AGE_MIN`
  in `scripts/page_only.py` for more page-only builds, lower it for fresher forecasts.
- A change to `site.yml` is always a full build. Three of the five builds on 24 November were that.
- The reading of `build_site.py` follows names. It cannot follow `globals()`, `eval` or `exec`, and refuses a
  file that uses them. It does not look inside other modules: any change to Python under `src/` is a full build.
- The same-files rule for tests does not cover a pull request whose base branch was changed after its last test
  run. GitHub does not record which base a finished run tested.
- After a full build fails late, the state can hold a newer poll than the published site. A page-only build then
  writes `quality.html` from that newer poll. Nothing else reads the state.

## Not done: the forecast step itself

It is still the largest part of a full build. What I measured in it, from the logs, without changing anything:

- The side-arm cache goes stale after most merges: 194 s in #738's build and 89 s in #736's. Its key hashes
  every Python file under `src/dipcast`.
- The Environment Agency's flood-alert requests timed out for 43 to 90 of 133 spots on the first ask in five of
  the six builds I read (2 in the sixth). In run 45206264547 that stage took about 100 s.
- In the same run the EA bathing-water service refused all 38 sample requests (HTTP 429), about 70 s.

I did not re-measure the DuckDB inserts PR #649 named. None of the three above is fixed here.
