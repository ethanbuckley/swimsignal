# Partner water samples: data contract, version 1

Written 31 October 2026. A partner is a group, club, school, event organiser or laboratory that takes water samples
at a place people swim and sends SwimSignal the results. This contract says what one file of results must hold, how
values outside a method's limits are written, and the two permissions each result carries.

- Template: [`docs/partner-samples-template-v1.csv`](partner-samples-template-v1.csv), the header row only.
- Checker: `uv run python scripts/partner_samples.py check FILE.csv`. It prints every error and warning, and exits 1
  on any error. Tests: `tests/test_partner_samples.py`.
- First conforming partner: Ambleside Action for a Future's Waterhead samples,
  [`data/research/partners/aafaf-waterhead.partner-v1.csv`](../data/research/partners/aafaf-waterhead.partner-v1.csv),
  written from the published export by `scripts/partner_samples.py waterhead` (below).
- Privacy, retention and moderation: [the partner programme](PARTNER-PROGRAMME-2026-11.md). Register entry: WET in
  [the recovery register](RESEARCH-RECOVERY-2026-10.md).

## How this relates to `samples/`

`samples/` (its README, `scripts/add_samples.py`, `src/dipcast/samples.py`) already takes lab results from an
organisation and shows the last 30 days on a spot's page. It keys a result to a SwimSignal spot id and holds one row
per bottle, with E. coli and enterococci side by side. That suits an organiser who tests at one of our spots.

This contract is for a partner who samples at its own points, which may not be one of our spots, and whose results
may be used to test forecasts. So it holds the sampling point's own position, one row per determinand, the method's
detection limits and how out-of-limit values are written, and the date each permission was given. A file in this
format can be turned into `samples/` rows where a point matches a spot; nothing does that automatically yet.

## One row per result

One row is one determinand measured in one sample. A sample tested for E. coli and enterococci is two rows with the
same `sample_id`. Columns may come in any order; every column below must be present, and no others. A blank cell is
allowed only where the table says so. `not_stated` means the partner has not told us; it is never a guess.

| Column | Blank allowed | What |
|---|---|---|
| `partner_id` | no | Short id for the partner, lower case letters, digits and hyphens (`aafaf`). One partner per file |
| `sample_id` | no | The partner's own id for the sample (bottle). Same for every row from one sample |
| `site_name` | no | The sampling point's name as the partner uses it (`Waterhead, Windermere`) |
| `site_lat`, `site_lon` | no | The sampling point, WGS84 decimal degrees. Must fall within Great Britain and Ireland |
| `site_confirmed` | no | `yes` if the partner has confirmed this is the exact point; `no` if it is approximate (a place name we placed) |
| `sampled_on` | no | The day the sample was taken, `YYYY-MM-DD` |
| `sampled_time` | yes | The time it was taken, `HH:MM`. Blank if not known |
| `timezone` | only when `sampled_time` is blank | `Europe/London` (UK clock time) or `UTC` |
| `determinand` | no | `ecoli`, `intestinal_enterococci`, `total_coliforms`, or `other:<name>` (`other:ammonium`) |
| `result` | no | The value as the laboratory reported it, a number of 0 or more. For a value outside the limits, see below |
| `qualifier` | yes | Blank for a counted value; `<` for below the lower limit; `>` for above the upper limit |
| `unit` | no | `cfu/100ml` (colony-forming units, a plate count) or `mpn/100ml` (most probable number) for the three bacteria; any unit for `other:` |
| `method_type` | no | `plate_count` (membrane filtration or spread plate), `mpn` (Colilert or Enterolert with Quanti-Tray, multiple tube), `other`, or `not_stated` |
| `method` | yes | The named method and standard if the laboratory gives one (`Membrane filtration, BS EN ISO 9308-1`, `Colilert-18 Quanti-Tray/2000`) |
| `lower_limit` | yes | The method's lower detection or reporting limit in `unit`. Blank if not stated |
| `upper_limit` | yes | The method's upper limit in `unit` (2,419.6 for an undiluted Quanti-Tray/2000). Blank if none or not stated |
| `limits_written` | no | How the laboratory writes a value outside the limits: `qualifier` (as `<10` or `>2419.6`), `zero` (below the lower limit written as 0), or `not_stated` |
| `lab` | no | The laboratory's name, or `not_stated` |
| `lab_accredited` | no | `yes`, `no` or `not_stated`: whether the partner says the laboratory is UKAS-accredited for this test. Their word, not ours |
| `sampler` | no | Who took the sample, as a role or group (`AAFAF volunteer`, `club coach`). Not a private person's name |
| `licence` | no | The licence the partner publishes under: `public-domain`, `CC-BY-4.0`, `OGL-3.0`, or `none` |
| `attribution` | yes | The credit to show beside a published result. Needed when `licence` is not `public-domain` or `none` |
| `publish_consent` | no | `yes` if the partner agreed in writing that SwimSignal may show this result and include it in its open data files; else `no` |
| `publish_consent_on` | only when `publish_consent` is `no` | The day that agreement was given |
| `test_use` | no | `holdout`, `exploratory` or `none` (next section) |
| `test_consent_on` | only when `test_use` is `none` | The day the test-use agreement was given |
| `consent_ref` | only when both permissions are `no`/`none` | Where the written agreement is kept (`email 25 Oct 2026, swimsignal-private/...`). A pointer, never the email itself |
| `received_on` | no | The day SwimSignal received this result |
| `notes` | yes | Anything else about this result, in the partner's words or ours, labelled as which |

### Values outside a method's limits

A laboratory cannot count below its lower limit or above its upper limit. How it writes those values decides what
the number means, so the contract asks for both the limits and the convention.

- Write a below-limit result as `qualifier` `<` and `result` equal to the limit (`<`, `10`), and an above-limit
  result as `>` and the upper limit (`>`, `2419.6`). Never halve a limit or replace it with 0.
- If the laboratory wrote below-limit results as 0, keep its 0, set `limits_written` to `zero`, and give the
  `lower_limit`. The checker then reads every 0 as "below the limit".
- If nobody knows, set `limits_written` to `not_stated`. A 0 is then ambiguous: it could be a true zero count on the
  plate or a below-limit result. The checker warns, and nothing downstream may read it as "no bacteria".
- A plate count and an MPN are different estimates of the same thing. Keep the unit the laboratory used; do not
  convert one into the other.

## The two permissions

Each result carries two separate permissions. Either can be given without the other, and either can be taken back
(the programme document says how).

**Publication** (`licence`, `attribution`, `publish_consent`, `publish_consent_on`): whether SwimSignal may show the
result on its pages and include it in open data files that others may download and reuse. `publish_consent` `yes`
needs a licence other than `none`.

**Use as test data** (`test_use`, `test_consent_on`):

- `holdout`: the result may be used to test a forecast that was fixed before the result existed, and the score may be
  published. **The agreement must be dated before the sample was taken** (`test_consent_on` earlier than
  `sampled_on`). The checker refuses a `holdout` row agreed on or after its sampling day.
- `exploratory`: the result may be used to develop and check models, but any comparison is labelled exploratory and
  is never presented as a fair test. This is the right value for any result someone had seen before the agreement.
- `none`: not used for testing at all.

### Why the test-use agreement comes before the results

A held-out test is fair only if nobody could choose which results go into it after seeing them. If the agreement
comes after the results:

- a partner (or SwimSignal) can include the weeks that make a forecast look good, or bad, and leave out the rest,
  without intending to. A held-out set chosen by its outcomes measures the choice, not the forecast;
- the model's developers may already have looked at the results while changing the model, so the test would be on
  data the model was tuned to.

Both problems disappear if the rule is fixed first: "every sample we take at these points from this date is test
data", agreed in writing before the first of them is taken. That is why the checker compares `test_consent_on` with
`sampled_on`, not with `received_on`. The forecast being tested must also be frozen before the samples are taken;
that belongs to the test's own protocol ([the research workflow](RESEARCH-WORKFLOW.md)), not to this file.

The same reasoning is why the Waterhead seasons below are `exploratory`: they were sent, and seen, before any
Waterhead test was designed.

## What a published result may say

These are the wording rules for any page that shows partner results. The programme document repeats them.

- A result is a measurement at one place at the time the sample was taken: not today's water, not the rest of the
  water body, and not a forecast.
- Name the partner and laboratory as the partner gives them. Say that SwimSignal did not take or check the sample.
- A single count is not a bathing water rating, and is not "safe", "clear", "verified" or a pass.
- A result never changes the forecast's level.
- A below-limit value is said as "below 10", never as 0 or "none". An ambiguous 0 (`limits_written` `not_stated`) is
  shown as the partner recorded it, with the warning that it may be below a limit.

## The checker

`scripts/partner_samples.py check FILE.csv` reads one or more files and reports, per row:

Errors (the file is refused):
- a missing or unknown column, a blank required cell, or more than one `partner_id`;
- a date that is not real, a `received_on` in the future, or a sample taken after it was received;
- a time that is not `HH:MM`, or a time with no `timezone`;
- a position outside Great Britain and Ireland;
- an unknown determinand, a bacteria row in a unit other than `cfu/100ml` or `mpn/100ml`, or `method_type` `mpn`
  with `cfu/100ml` (or `plate_count` with `mpn/100ml`);
- a negative or non-numeric result, or a qualifier other than blank, `<` or `>`;
- `publish_consent` `yes` with `licence` `none` or no `publish_consent_on`, or a licence that needs a credit with no
  `attribution`;
- `test_use` `holdout` with `test_consent_on` on or after `sampled_on`;
- a consent date in the future. A publication consent given after the result arrived is fine: only `holdout`
  depends on when it was agreed;
- the same `sample_id` and `determinand` twice, or one `sample_id` with two sites, days or times.

Warnings (the file is accepted, and the warning travels with it):
- a 0 where `limits_written` is `not_stated`: it may be a below-limit result;
- a `<` or `>` value that differs from the stated limit;
- `site_confirmed` `no`;
- no `sampled_time`: the sample cannot be matched to a forecast issue time, only to a day.

## Waterhead: the first conforming partner

`uv run python scripts/partner_samples.py waterhead` writes
`data/research/partners/aafaf-waterhead.partner-v1.csv` from `data/research/waterhead_wet.v1.json`
([its contract](WATERHEAD-WET-CONTRACT-v1.md)). It reads only the published export, so every value comes from it
unchanged: 59 samples, two rows each (E. coli and intestinal enterococci), 118 rows. `scripts/partner_samples.py
check-waterhead` writes it again in memory and fails if the committed file differs, or if any result differs from
the export.

How each column is filled, and why:

| Column | Value | From |
|---|---|---|
| `partner_id`, `sample_id` | `aafaf`, `wet-<date>` | One sample a day in the sheet |
| `site_name`, `site_lat`, `site_lon` | `Waterhead, Windermere`, 54.41897, -2.96235 | The SwimSignal spot `osm-windermere-waterhead` (OpenStreetMap). The sheet has no site column |
| `site_confirmed` | `no` | The exact point is an open question in the WET contract |
| `sampled_time`, `timezone` | blank, blank | Not in the sheet. 2025 was "mostly Thursday mornings" (the report); no clock time |
| `result`, `qualifier` | the export's count, blank | Unchanged. No count in the sheet carries a `<` or `>` |
| `unit` | `cfu/100ml` | The sheet's column headings |
| `method_type`, `method` | `not_stated`, blank | Neither season's method is stated. cfu suggests a plate count; that is an inference, so it is not written |
| `lower_limit`, `upper_limit`, `limits_written` | blank, blank, `not_stated` | Unknown. So the three 0s (E. coli on 8 and 15 May 2025, enterococci on 18 May 2026) are flagged as possibly below a limit |
| `lab` | `Simplex Health` for 2025, `not_stated` for 2026 | The WET technical report, p. 6; 2026 is an open question |
| `lab_accredited` | `not_stated` | Not said |
| `sampler` | `Ambleside Action for a Future (WET project)` | The group, not a person |
| `licence`, `attribution` | `public-domain`, the export's attribution | Tim Boden's email, 25 Oct 2026: public domain, credit the group |
| `publish_consent`, `publish_consent_on` | `yes`, 2026-10-25 | The same email |
| `test_use`, `test_consent_on` | `exploratory`, 2026-10-25 | Permission covers any use, but the seasons were seen before a test was designed, so they cannot be held out |
| `consent_ref` | `Tim Boden email 25 Oct 2026 (swimsignal-private/tim-boden-aafaf/)` | A pointer, not the email |
| `received_on` | 2026-10-25 | The export's `sources.received` |

Running the checker on it gives no errors and these warnings: the three 0s, an unconfirmed site and no sampling time
on each row. They are the WET contract's open questions, now carried with each result. When Tim answers them, the
WET export moves to 1.2 and the partner file is written again from it.

## Versioning

A new optional column, a new determinand or a new `method_type` is a minor version (1.1). Removing or renaming a
column, or changing what a value means, is a major version (2.0) and a new template file. The checker reads
`docs/partner-samples-template-v1.csv` for its columns, so the template and the checker cannot drift apart.

## Changes

- **1.0.0 (31 Oct 2026):** first version.
