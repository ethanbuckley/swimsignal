# LEDGER stage 1: the overflow ledger and the Ilkley audit statement

Written 17 November 2026. LEDGER is the fallback of the six two-year bets Ethan asked for on 17 November 2026,
developed beside PLACE-LEVEL. Owner: Ethan, with a Claude session doing the work. Stage: development (bounded
exploration). **No test was run and there is no new result.** Nothing here changes a forecast, a frozen file, an
issued prediction, an active window or the 2027 primary evaluation.

LEDGER extends two directions already in the register. CATCH-SIM answers "what if this overflow never spilled" at two
spots. RESTORE compares observed with expected after an upgrade. The new parts are a national roll-up per overflow
and a dated audit statement.

## What was built

| Part | Where | State |
|---|---|---|
| The table | `data/research/overflow_ledger.v1.json`, [contract](OVERFLOW-LEDGER-CONTRACT-v1.md), `scripts/export_overflow_ledger.py` | Built |
| A prototype page | `prototypes/research-lab/overflow-ledger/` | Built, left out of the site build, linked from nowhere |
| The audit statement | [RESTORE-ILKLEY-STATEMENT-2026-11.md](RESTORE-ILKLEY-STATEMENT-2026-11.md) | Written. Result: not run |

## The hardest assumption

The ledger adds up the model's weights. It is only as true as the modelled chain from overflow to spot. River
evidence supports that chain weakly: at 59 unseen river points the production estimate ordered a point's days at
0.376, against 0.355 for rain alone ([record](RIVER-UNSEEN-PROTOCOL-2026-11.md)). So every label says the table is an
account of the model, not of measured bacteria. No row says an overflow caused a sample result or broke a permit.

## The table

**How it was made (established).** The weight of each overflow at each spot already exists. Research Lab exhibit 2
exports it at every build (`lab_pollution_paths.export`, which calls `transport.upstream_overflows` with the
production settings). The ledger script reads that export and adds per overflow. It holds no transport code. A test
checks that.

**The run.** 17 November 2026, 18 seconds, offline, nothing fetched. The export was remade in scratch for all 121
listed spots, because the repository's copy of 1 November holds 108 files. A scratch `DIPCAST_ROOT` linked this
worktree's committed files and three caches from the main checkout (`river_network.pkl`, `overflows.parquet`, the OS
Open Rivers geopackage). SHA-256 of the four inputs before and after: unchanged. No file was written into the scratch
root. The hashes are in the file's `inputs`.

**What it holds (established, read from the file).**

- 1,414 overflows traced to 89 of the 121 listed spots, through 2,099 links.
- 29 spots have no monitored overflow within 60 km upstream. 3 sit off the mapped rivers.
- 910 overflows reach one spot only. 380 reach two. One reaches seven.
- 47 overflows have no long-term average in the annual return, so no weighted spills a year.
- 41 groups of spots joined by a shared overflow. The largest is the Thames at 11 spots and 149 overflows.
- The Wharfe group holds 7 spots, 59 overflows and 113 links. At Cromwheel the six overflows of the Ilkley scheme
  carry 4.66 of the spot's summed weight of 6.76.

**Checks.**

- Cromwheel's 16 weights equal the repository's exhibit 2 copy of 1 November 2026, weight for weight (a test).
  That copy was checked against the live site on 1 November.
- Every overflow's roll-up equals the sum of its links, and every spot's total equals the sum over overflows
  (`--check`, and a test).
- The spot list equals `spots.csv` and `spots-osm.csv` (a test).
- Not checked: the weights against a site build of today. The overflow table is the main checkout's cache of
  30 October 2026.

**The season figure.** The brief asked for a season figure such as modelled high-level spot-days. Version 1 gives a
year figure instead: weighted spills a year, the EA's long-term average spill count times the summed weight. The
existing outputs do not hold each overflow's daily chance across a bathing season. The forecast log has them only
from 12 October 2026. A season hindcast is the next deliverable, not a second calculation slipped into this one. The
contract says how the year figure is defined and what it is not.

## The prototype page

`prototypes/research-lab/overflow-ledger/`. The national table (by summed weight, weighted spills or spots reached,
and by company), the same weights by company, and one catchment as a grid of overflows against spots. It opens on
the Wharfe above Ilkley.

- Checked at 1440 × 900 and 375 × 812 in the app's browser: no console error, no sideways page scroll, the tables
  scroll inside their own frames on a phone. Not checked: Safari, a real phone, a screen reader.
- The first screen says "An account of the model, not of measured bacteria. Exploratory. A prototype. Not published."
  The evidence line sits in section 1, above the table.
- `build_site.LAB_UNPUBLISHED` holds the folder, so `write_lab` leaves it out. The research file is not in
  `LAB_DATA`. Tests check both, and that no page or script links it.
- Against [the design reference](DESIGN.md), "The Research Lab": the page uses the Lab's shell, opening order and
  words (already decided there). It is not in the Lab's numbered bar (new: it is unpublished). It has no map and no
  cover (new: a table first; a map is a later choice).

## The audit statement

[RESTORE-ILKLEY-STATEMENT-2026-11.md](RESTORE-ILKLEY-STATEMENT-2026-11.md) fixes the rows, the expectation (rain and
season only, fitted on 2023 and 2024), the references (12 other river bathing waters), the metric, the pass rule with
its interval, and what each result leads to. It is pushed before any 2026 Cromwheel sample or spill record is joined
for it. It does not run before option B's read, on or after 2 December 2026.

Its power is small, and it says so: 17 samples. A fall to about 37% of the expected level is needed for the first
part of the pass rule to hold 8 times in 10. The likely result is "inconclusive".

## What this can and cannot become

- **Supported now:** a table of model accounting, with its limits beside it.
- **Not supported:** any statement that an overflow is to blame for a spot's water. Any ranking of companies.
- **What would strengthen it:** samples that show the chain matters at rivers. PLACE-LEVEL's forecast-timed samples
  and DENSE's four-a-week results are the routes. The Ilkley audit is one small case.

## Needs Ethan (not decided here)

1. Whether the ledger is published at all, or stays a Lab prototype.
2. Whether a public version names overflows nationally, or shows companies and catchments only. The prototype names
   them, as exhibit 2 and each spot page already do for one spot at a time.
3. Whether the by-company table is shown. It follows which spots are listed, so it can be misread as a comparison.
4. Whether the Ilkley audit runs after option B's read, and the two outside contacts it names.
5. Whether the next deliverable is the season hindcast (below) or waits on PLACE-LEVEL.

## Next (register row)

| Field | Content |
|---|---|
| Identity | LEDGER; Claude session for Ethan; this PR; `scripts/export_overflow_ledger.py`, `data/research/overflow_ledger.v1.json`, `prototypes/research-lab/overflow-ledger/` |
| Evidence | None new. Model accounting. The chain's support at rivers is weak (0.376 against 0.355 at 59 unseen points) |
| Stage and claim | Exploration, prototype, not published. Claim: what the model counts, per overflow |
| Next deliverable | A season figure: expected high-level spot-days per overflow for May to September 2025, from the production model on cached archive rain, by CATCH-SIM's removal rule at every spot. Protocol first, with the rain cache's coverage counted in it. Then the Ilkley audit, after option B's read |
| Milestone | Season figure protocol by 15 December 2026. Ilkley audit on or after 2 December 2026, in RESTORE's record due 31 January 2027 |
| Release route | Ethan decides public or Lab-only and naming. Rollback: delete the folder, the file and the build's ignore entry |

## Published as Research Lab exhibit 6 (25 November 2026)

Ethan asked on 25 November 2026 for the Lab's half-done work to be finished, naming this prototype ("The overflow
ledger has a prototype that is not in the build"). That reverses his 19 November decision that the ledger stays an
unpublished prototype. His other decisions of 19 November hold, so the published page differs from the prototype:

- **No national list of overflows.** The national table is by spot: overflows traced, summed weight, largest weight,
  the largest one's share and how many overflows carry half. Overflows are named only in one catchment's grid, as
  exhibit 2 and each spot page name them one place at a time. The opening map draws every traced overflow as an
  unnamed dot.
- **No table by company,** and no company filter.
- **No season figure.** Section 5 says a season count was made and why it is not shown (check 4 failed as stated;
  the per-overflow figure moved between seasons), with a link to its record. The season file is not copied to the
  site.
- The weighted-spills year figure is left off the page. It is in the published file and its contract.

The research file is copied to `lab/data/` as it is (`build_site.LAB_DATA`). It holds every overflow's name and the
by-company roll-up, as exhibit 2's per-spot files already hold the same rows spot by spot. Whether a published file may
hold the by-company roll-up is a question for Ethan; a trimmed public copy is the alternative.

Nothing in the ledger, its contract or its claim changed. Stage unchanged: model accounting, no test.
