# Advisory finder: weekly run sheet

For Ethan, by hand, on your Mac, once a week in season. The rules and reasons are in
`docs/ADVISORY-FINDER-2026-10.md`. This sheet is only what you do.

**The site does not show advisories yet.** Nothing in the site build reads the drafts or
`data/advisories/approved.json`. Showing approved lines on spot pages is a later PR, and it needs your
go-ahead. Until then, an approval is a record of your decision and nothing more.

## What never happens

- Nothing is published, posted, sent or emailed. The finder has no code that does any of these.
- The finder never writes `approved.json`. Only you change it, by pull request.
- It never changes a risk level or a spot's answer.
- It does not run in GitHub Actions or in the site build. A test fails if a workflow names it.
- A weekly run makes 6 requests, one at a time with a 1 second pause: the EA open-incident list, the
  EPA alerts, and four whitelisted pages. `--ea-history` adds 38 more.

## Before PR #379 merges

The finder lives only on the branch `proto/advisory-finder` (draft PR #379). Run it from its own
worktree, so it does not disturb your main checkout or other sessions' worktrees.

1. Go to your repository.

   ```bash
   cd ~/Documents/GitHub/dipcast
   ```

2. Fetch the branch.

   ```bash
   git fetch origin
   ```

3. Make a worktree for the finder (once).

   ```bash
   git worktree add ~/Documents/GitHub/swimsignal-advisories origin/proto/advisory-finder
   ```

   You will know it worked: the last line starts `HEAD is now at`.

Approvals cannot be made before #379 merges. `approved.json` is not on `main`, and PRs go against
`main`. You can still run the finder and read the table.

After #379 merges, use the same worktree on `main` instead (step 3 of the weekly run says how). Your
drafts file stays where it is, in that worktree's `data/cache/`.

## Once: check it works without the network

1. Go to the worktree.

   ```bash
   cd ~/Documents/GitHub/swimsignal-advisories
   ```

2. Run it on the saved answers. This makes no requests.

   ```bash
   uv run python scripts/advisory_finder.py --dry-run --fixtures tests/fixtures/advisories --now 2026-10-26T19:00:00+00:00
   ```

   You will know it worked: the last two lines are `11 draft(s), 11 first seen, 8 held, 0 approved. Dry run: ...`
   and `Drafts written to .../advisory_drafts_fixtures.json`.

## Weekly: the dry run

1. Go to the worktree.

   ```bash
   cd ~/Documents/GitHub/swimsignal-advisories
   ```

2. Fetch.

   ```bash
   git fetch origin
   ```

3. Move the worktree to the newest code. Before #379 merges:

   ```bash
   git switch --detach origin/proto/advisory-finder
   ```

   After #379 merges:

   ```bash
   git switch --detach origin/main
   ```

   You will know it worked: a line starting `HEAD is now at`.

4. The first time only, run it without a previous file.

   ```bash
   uv run python scripts/advisory_finder.py --dry-run
   ```

5. Every week after that, compare with last week.

   ```bash
   uv run python scripts/advisory_finder.py --dry-run --previous data/cache/advisory_drafts.json
   ```

   You will know it worked: one `source <key>: ok` line for each of the 6 sources, then
   `N draft(s), N first seen, N held, N approved. Dry run: nothing published or sent ...`, then
   `Drafts written to .../data/cache/advisory_drafts.json`.

The mistake you are most likely to make: leaving out `--previous`. The run still works, so nothing
looks wrong. But without last week's file, a feed that failed this week cannot mark its old drafts
`unverified`, and an incident that left the EA list cannot come back as `withdrawn`. You lose the
week-to-week comparison silently. The command writes to the same file it reads, after reading it, so
the same command works every week.

If a line says `source ea-open: error (...)` or `source epa-alerts: error (...)`, that feed was not
read. Run step 5 again later that day. Do not approve anything from that run.

If the run stops with `Approvals refused, nothing written`, the exit code is 2 and no drafts file is
written. The message names each bad entry. Fix `approved.json` by PR (see "When an approved advisory
ends" below for the usual cause).

## Reading the review table

One row per draft. The columns:

- `id`: the draft id. You copy it into an approval.
- `status`: `open`, `update`, `lifted` or `withdrawn` (below).
- `first_seen`: `yes` if this draft id was not in the previous drafts file, `no` if it was. On a run
  without `--previous`, every row says `yes`. This is the column to scan for what is new this week.
- `approval`: `unapproved`, `approved`, `changed` or `lapsed` (below).
- `spot`: the spot id. `?` and ids means more than one spot fits. `-` means no SwimSignal spot (most
  EA incidents are on the coast).
- `notice`: the date the source gives. `-` means none.
- `expiry`: a date the source states, or 14 days after you approved a page notice. Usually `-`.
- `source`: which whitelisted source.
- `flags`: what needs settling (below). `-` means none.
- `line | evidence`: the exact line you would approve, then the source's own words (cut short), or
  `not quoted: open <link>` for a source whose words we may not keep.

Statuses:

- `open`: in force at the source, and not changed since the previous run. A standing incident shows
  `open` every week; `first_seen` tells you whether it is new this week.
- `update`: in force, and its words, expiry or expected end changed since the previous run.
- `lifted`: the source gives an end date.
- `withdrawn`: the page says it was withdrawn, or the incident left the EA list with no end date
  read. For the second kind, check the EA profile before treating it as over.

Flags, and what to do:

- `held`: not a flag but a count in the last line. A draft is held when it has any of `unmatched`,
  `ambiguous`, `no_date`, `conflict`, `superseded`, `unverified` or `company_notice`. Settle the flag
  before you approve. `stale` alone does not hold a draft.
- `unmatched`: no single spot. For an EA coastal incident, ignore it. An approval has no spot field
  (read from the code: the only keys are draft id, approver, time and line), so you cannot assign a
  spot by approving.
- `ambiguous`: the source names a water several spots share, such as Windermere. Ignore it, or ask for
  a narrower source.
- `no_date`: the source gives no date. The EA panel for Frensham is the usual one. Approve the dated
  `ea-open` row for the same spot instead.
- `unverified`: a feed could not be read this run, so this row is last week's copy and is not current.
  Do not approve it. Run again later.
- `conflict`: two sources disagree for one spot (one in force, one ended). Open each link. Approve at
  most the one that stands today.
- `stale`: a page notice older than 28 days with no stated end. The drafts file still marks it current,
  because the page has not said otherwise. Open the link and check the page still says it today. The Waverley
  notice of 22 Aug 2025 is stale.
- `superseded`: an older notice in the same thread as a newer one. Do nothing.
- `company_notice`: a water company's page. There is no water-company source yet.

Approval states:

- `approved`: your entry matches this draft's line exactly.
- `changed`: you approved a different line for this draft id. The source changed. Read the new line,
  and approve again by PR if it is right.
- `lapsed`: a page notice with no stated end, approved more than 14 days ago. Check the page. If it
  still says so, re-approve by PR with today's `approved_at`. If not, remove the entry by PR.

## Approving a draft

Only after #379 merges. Only you approve.

1. Decide from the table. Check four things: it is the right spot; it is in force today (open the
   link for `stale` or `not quoted` rows); the line is right word for word; no other row for the spot
   says the opposite.

2. Make a branch from `main` in the worktree.

   ```bash
   git switch -c advisories/approve-2026-11-02 origin/main
   ```

   Put the real date in the branch name. You will know it worked: `Switched to a new branch`.

3. Get the time in UTC, in the form the file needs.

   ```bash
   date -u +%Y-%m-%dT%H:%M:%SZ
   ```

4. Open `data/advisories/approved.json` and add one entry to the `approvals` list. Copy the id and the
   line from the table, not by retyping:

   ```json
   {"draft_id": "e8b5832d974a", "approver": "Ethan Buckley", "approved_at": "2026-11-02T19:00:00Z",
    "line": "Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026"}
   ```

   The line is the text in the last column, up to and not including ` | `.

5. Check the file is valid.

   ```bash
   uv run pytest tests/test_advisory_finder.py -q
   ```

   You will know it worked: `passed`, and no `failed`.

6. Run the weekly command again (6 requests).

   ```bash
   uv run python scripts/advisory_finder.py --dry-run --previous data/cache/advisory_drafts.json
   ```

   You will know it worked: that row's `approval` column says `approved`, and the last line says
   `1 approved` (or one more than before).

7. Commit the file.

   ```bash
   git add data/advisories/approved.json
   ```

   ```bash
   git commit -m "Advisories: approve e8b5832d974a (Frensham Great Pond)"
   ```

8. Push and open the PR.

   ```bash
   git push -u origin HEAD
   ```

   ```bash
   gh pr create --fill
   ```

   You will know it worked: `gh` prints the PR's address. Merge it when you are happy.

The mistake you are most likely to make: retyping the line, or letting an editor change it (curly
quotes, a double space, a line break). The finder compares the line character for character. A line
that differs by one character shows `changed`, not `approved`. Copy it from the table.

## When an approved advisory ends

When a draft you approved shows `lifted` or `withdrawn`, remove its entry from `approved.json` by PR
that week. If you leave it, the run after next stops with exit code 2 and the message
`unknown draft id, not in this run or the previous one`. This is read from the code: an ended draft
stays in the next run's previous file for one more week, then drops out. It has not happened in a
real run yet.

## Once a day at most: EA history

`--ea-history` also reads the EA incident history of each of the 38 inland bathing waters: 38 more
requests, one at a time with a 1 second pause. It finds incidents that opened and ended between two weekly
runs, which the open list no longer shows. Use it when you want that, not every week.

1. Run the weekly command with the option.

   ```bash
   uv run python scripts/advisory_finder.py --dry-run --previous data/cache/advisory_drafts.json --ea-history
   ```

   You will know it worked: a line `source ea-history: ok, N candidate(s)`. Ended incidents show as
   `lifted` rows from `ea-history`.

2. A second try the same day (Europe/London) makes no history requests. It prints
   `source ea-history: skipped (already read on <date>: once a day at most)`.

The mistake you are most likely to make: running it again after a failure part way. The day is
recorded in `data/cache/advisory_ea_history_day.json` before the first request, so a run that stopped
part way still counts. That is deliberate. Wait until tomorrow. Do not delete the file to get round
it: the limit is there to keep the EA's service from seeing us as a burden.
