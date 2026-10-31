# Partner water samples: data contract, version 1

Written 31 October 2026. A sampling partner is a group, club, school, event organiser or laboratory that takes water
samples where people swim and sends SwimSignal the results. This contract says what their results must hold.

**It is not a new system.** It is version 2 of the format `samples/` already uses for lab results from organisations
([samples/README.md](../samples/README.md), `src/dipcast/samples.py`, `scripts/add_samples.py`, the spot page's
"Measured" tile in `src/dipcast/site/measured.js`). Version 2 adds 18 optional columns after the existing 13. A
version 1 file still reads unchanged. The same tool adds results, the same two permissions (`publish`, `evaluate`)
decide what is shown and what tests the forecast, and the same private folder holds the full record.

- Template: [`docs/samples-template-v2.csv`](samples-template-v2.csv), the header only. A test keeps it equal to
  `samples.COLUMNS`. (It is not in `samples/`, where every CSV is read as a supplier's file.)
- Checks: `scripts/add_samples.py ... --dry-run FILE.csv` refuses a bad row with its reason, and prints notes for what
  a good row leaves unknown (`samples.notes`). Tests: `tests/test_samples.py`.
- First conforming partner: Ambleside Action for a Future's Waterhead samples,
  [`data/research/partners/aafaf-waterhead.samples.csv`](../data/research/partners/aafaf-waterhead.samples.csv),
  written from the published export by `scripts/export_waterhead_wet.py samples` (below).
- Privacy, retention and moderation: [the partner programme](PARTNER-PROGRAMME-2026-11.md). Register entry: WET in
  [the recovery register](RESEARCH-RECOVERY-2026-10.md).

## The columns

One row per sample (bottle), keyed to a SwimSignal spot. A blank cell means "not stated" and is never a guess.

### Version 1, unchanged

| Column | What |
|---|---|
| `spot_id` | The SwimSignal spot the sample belongs to (`spots.csv`, `spots-osm.csv`) |
| `sampled_at` | When the sample was taken, `2026-10-17 08:30`; the day alone when `time_known` is `no` |
| `timezone` | `Europe/London` or `UTC` |
| `ecoli_per_100ml` | E. coli per 100 ml as reported: `1200`, `<10`, `>2419.6` |
| `enterococci_per_100ml` | Intestinal enterococci per 100 ml, the same way |
| `lab` | The laboratory's name |
| `ukas_accredited` | `yes`, `no` or blank: the sender's word |
| `method` | The named method (`Membrane filtration, BS EN ISO 9308-1`, `Colilert-18 Quanti-Tray/2000`) |
| `lab_ref` | The laboratory's reference. Private |
| `supplier` | The partner |
| `received` | The day SwimSignal received it |
| `publish` | `true` if the partner agreed in writing to publication. Private |
| `evaluate` | `true` if the partner agreed in writing to use in testing the forecast. Private |

### Version 2, added for partners

| Column | Public? | What |
|---|---|---|
| `time_known` | yes | `no` when the sender does not know the time; `sampled_at` is then the day alone. Blank or `yes` means a time is given |
| `site_name` | yes | The sampling point's name as the partner uses it, where it is not simply the spot |
| `site_lat`, `site_lon` | yes | The sampling point, WGS84 decimal degrees, both or neither. Must fall in Great Britain or Ireland |
| `site_confirmed` | yes | `yes` if the partner confirmed the exact point; `no` if it is approximate (a place name we placed) |
| `ecoli_basis`, `enterococci_basis` | yes | `cfu` (colony-forming units, a plate count) or `mpn` (most probable number: Colilert, Enterolert, multiple tube) |
| `ecoli_lower_limit`, `ecoli_upper_limit` | yes | The method's detection or reporting limits for E. coli, per 100 ml |
| `enterococci_lower_limit`, `enterococci_upper_limit` | yes | The same for intestinal enterococci |
| `limits_written` | yes | How the laboratory writes values outside its limits: `qualifier` (`<10`, `>2419.6`) or `zero` (below the lower limit written as 0) |
| `sampler` | no | Who took it, as a role or group (`club volunteer`). Never a private person's name |
| `licence` | yes | `public-domain`, `CC-BY-4.0` or `OGL-3.0`: the licence the results are published under |
| `attribution` | yes | The credit shown beside a result. Needed for `CC-BY-4.0` and `OGL-3.0` |
| `publish_agreed` | no | The day publication was agreed in writing |
| `evaluate_use` | no | `holdout` or `exploratory` (below). Blank with `evaluate` `true` counts as exploratory |
| `evaluate_agreed` | no | The day test use was agreed in writing |

Other determinands (total coliforms, ammonium) are not in the format. A partner who measures them keeps them; the
Waterhead permission names only E. coli and enterococci, so its total coliform column was never exported.

### Values outside a method's limits

- Write a below-limit result as `<` and the limit (`<10`), an above-limit one as `>` and the limit (`>2419.6`).
  Never halve a limit or replace it with 0.
- If the laboratory wrote below-limit results as 0, keep its 0, set `limits_written` to `zero` and give the lower
  limit. The row is refused without it.
- A 0 where `limits_written` is `qualifier` and the lower limit is above 0 is a contradiction: the row is refused.
- A 0 with `limits_written` blank is ambiguous: a true zero count or a below-limit result. The row is accepted with a
  note, and nothing downstream may read it as "no bacteria".
- A plate count and an MPN are different estimates of the same thing. Keep the basis the laboratory used.

## The two permissions, and when they were agreed

`publish` and `evaluate` are version 1's, and work as before: each is `false` until the partner agrees in writing,
each can be taken back, and `--sync` rewrites the public files from the private folder. Version 2 records when each
was agreed, and for `evaluate`, what kind of test use:

- `holdout`: the result may be used in a fair test of a forecast that was fixed before the result existed, and the
  score published. **The agreement must be dated before the sample was taken** (`evaluate_agreed` earlier than the
  sampling day), and the sample must have a time. Either missing, the row is refused.
- `exploratory`: the result may be used to develop and check models, but any comparison is labelled exploratory and
  never presented as a fair test. The right value for any result someone had seen before the agreement.

### Why the test-use agreement comes before the results

A held-out test is fair only if nobody could choose which results go into it after seeing them. If the agreement
comes after the results:

- a partner (or SwimSignal) can include the weeks that make a forecast look good, or bad, and leave out the rest,
  without intending to. A held-out set chosen by its outcomes measures the choice, not the forecast;
- the model's developers may already have looked at the results while changing the model, so the test would be on
  data the model was tuned to.

Both disappear if the rule is fixed first: "every sample we take at these points from this date is test data",
agreed in writing before the first of them is taken. That is why the check compares `evaluate_agreed` with the
sampling day, not with `received`. The forecast being tested must also be frozen before the samples are taken; that
belongs to the test's own protocol ([the research workflow](RESEARCH-WORKFLOW.md)). `scripts/evaluate_samples.py`
leaves out samples with no time, since it pairs each with the forecast live when it was taken.

## What a published result may say

These are the wording rules for any page that shows partner results; the programme document repeats them, and the
Measured tile and the evidence timeline keep them.

- A result is a measurement at one place at the time the sample was taken: not today's water, not the rest of the
  water body, and not a forecast.
- Name the partner and laboratory as the partner gives them. Say that SwimSignal did not take or check the sample.
- A single count is not a bathing water rating, and is not "safe", "clear", "verified" or a pass.
- A result never changes the forecast's level.
- A below-limit value is "below 10" or "under 10", never 0 or "none". A result with no time is said as its day.

## Waterhead: the first conforming partner

`uv run python scripts/export_waterhead_wet.py samples` writes
`data/research/partners/aafaf-waterhead.samples.csv` from `data/research/waterhead_wet.v1.json`
([its contract](WATERHEAD-WET-CONTRACT-v1.md)) alone, so every count is the published one: 59 rows. A test checks
the committed file against the export, count by count, and that every row passes `samples.parse_row`.

| Column | Value | From |
|---|---|---|
| `spot_id` | `osm-windermere-waterhead` | The export's `spots` |
| `sampled_at`, `time_known` | the date, `no` | The sheet has dates only |
| counts | the export's, no `<` or `>` | Unchanged |
| `ecoli_basis`, `enterococci_basis` | `cfu` | The sheet's headings, "cfu/100ml" |
| `method`, limits, `limits_written` | blank | Not stated. So the three 0s (E. coli on 8 and 15 May 2025, enterococci on 18 May 2026) carry a note |
| `lab` | `Simplex Health` for 2025, blank for 2026 | The WET technical report, p. 6; 2026 is an open question |
| `site_name`, `site_lat`, `site_lon`, `site_confirmed` | `Waterhead, Windermere`, the spot's pin, `no` | The exact point is an open question |
| `supplier`, `sampler` | Ambleside Action for a Future; its volunteers (WET project) | The group, not a person |
| `licence`, `attribution` | `public-domain`, the group and project | Tim Boden's email, 25 Oct 2026 |
| `publish`, `publish_agreed` | `true`, 2026-10-25 | The same email |
| `evaluate`, `evaluate_use`, `evaluate_agreed` | `true`, `exploratory`, 2026-10-25 | Permission covers any use, but the seasons were seen before a test was designed |

`add_samples.py --dry-run` on it gives 59 rows, no errors, and these notes: an approximate point and no time on every
row, and the three 0s. They are the WET contract's open questions, carried with each result.

**It is not in `samples/`.** Adding it there (`add_samples.py`, then a pull request) would show its last 30 days in the
Waterhead spot's Measured tile, beside the forecast. The spot page's link to these samples shows no count on purpose
(`index.html`, `localSamplesLine`), so this is Ethan's call, not a side effect of a format change.

## Versioning

A new optional column is a minor change within version 2. Renaming a column or changing what a value means is a new
version, with a new template file. Version 1 files keep reading.

## Changes

- **1.0.0 (31 Oct 2026):** first version, as version 2 of the `samples/` format.
