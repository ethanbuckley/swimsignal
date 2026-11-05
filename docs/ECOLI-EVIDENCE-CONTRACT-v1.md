# E. coli evidence: the observation contract, version 1

Written 30 October 2026, register row **3 / LAKE-CONC**, route "public research observations"
(`docs/RESEARCH-WORKFLOW.md`). Produced and checked by `scripts/export_ecoli_evidence.py`; file
`data/research/ecoli_evidence.v1.json` (about 30 KB gzipped). The product chat owns where and how it is shown.

## What it may and may not say

- **May say:** what the Environment Agency's lab measured at each inland bathing water and when (E. coli and
  enterococci per 100 ml, with "below" and "above" limits as reported), how many samples passed 900, and how a
  hindsight model estimate compared with each sample.
- **May not say:** that a sample shows the water was safe or unsafe at any other time; that a hindsight estimate was
  the forecast the site issued (the site's own issued forecasts are scored separately on the verification page); that
  a mismatch points to a particular overflow, company or source.
- `claim.public_wording` goes beside the samples. Official advice and the bathing water's EA classification stay
  more prominent than anything here.

## Fields

| Field | Meaning |
|---|---|
| `schema`, `version`, `generated_at` | `"swimsignal.ecoli-evidence"`, `"1.0.0"`, export time |
| `line`, `warn_at` | 900 (the inland "sufficient" line, cfu/100 ml) and 0.25 (the site's river warning line) |
| `hindsight` | what the estimate is: production's form refitted leaving out each year in turn (#466), archived lead-0 forecast rain, replayed exposure; `issued: false` always |
| `sources`, `sample_sources` | input files and SHA-256; `bwq` (the bathing-water service, cached 12 Sep 2026) and `wqa` (the Water Quality Archive, statutory samples the cache lacks) |
| `attribution` | the Environment Agency's Open Government Licence line |
| `claim` | `public_wording`, `not_claimed` |
| `sites` | per bathing water: `spot_id` (the site's id), `bw_id`, `name`, `kind`, `samples`, `summary` |
| `samples` | in time order: `t` (sample time with offset), `ecoli`, `q` (`"<"`, `">"` or null), `ie`, `ie_q` (null from the Archive, which this file reads for E. coli only), `src`, `over` (E. coli over 900), `hindsight` (P(over 900) in hindsight, or null where the sample is outside #466's rows: 2023, and bathing waters with no overflow upstream) |
| `summary` | samples, over 900, below the limit, first and last date, samples with a hindsight estimate, hindsight misses (over 900 with an estimate under 0.25) and false alarms (under 900 with 0.25 or more) |
| `coverage` | sites, samples, samples added from the Archive, samples with a hindsight estimate |

A value with `q: "<"` is the lab's reported limit, not a measurement; a chart must show it as "below 10", never as 10.

## Version 1.1 (31 October 2026): additive, at the product owner's request

- **Correction:** the two reasons listed above for a missing hindsight estimate were incomplete. 101 samples at study
  sites also have none: they are only in the Water Quality Archive, not in the cached bathing-water file the study's
  rows were built from. 89 were taken after that file ended on 7 September 2026; 12, from June to early September,
  were never listed in it.
- `samples[].hindsight_reason`: null when there is an estimate, else `before_2024` (2023: no archived forecast rain),
  `no_overflow_upstream` (the six bathing waters with no monitored overflow upstream: the three Hampstead Heath ponds,
  the Serpentine, Henleaze Lake, Cotswold Country Park) or `archive_only`. Top-level `hindsight_reasons` gives a
  plain sentence for each. As exported: 321, 306 and 101 samples.
- `summary.below_limit_value`: the lab's reported limit behind `below_limit` (10 wherever it occurs), or null.
- `warn_at_note`: 0.25 is the site's river warning line; the summaries count hindsight misses and false alarms at it
  for lakes too, for comparison only (the site gives no E. coli warning at lakes).
