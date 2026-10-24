# Dry days before rain, and a longer rain window: the test, stated before any run

Written 24 October 2026. Nothing has been run. No score of any kind has been computed for this test. Results go below
the line at the end. Nothing above it changes after a result is seen.

## Why

Tim Boden (Ambleside Action for a Future) runs his own E. coli model for Waterhead and Lakeside on Windermere. On the
24 October call he described two things SwimSignal's E. coli model does not do.
- **Dry days before rain.** His rural runoff term is the day's rain, above a dry-day threshold, times a multiplier for
  one, two or three dry days before it. Muck builds up on fields and roads in dry weather; the first rain after a
  dry spell washes more of it in.
- **A lag fitted per site.** Waterhead responds best to the sum of the previous two days' rain, Lakeside to one day.

The E. coli model's inputs are rain over 24 and 48 hours to the sample hour, overflow exposure, a lake flag and the
day of the year (`model/ecoli.py`, `FEATURES`). It has no dry-spell term and no window longer than 48 hours.

There are two questions. They are scored on their own and decided on their own.
- **Question 1, dry spell:** does the E. coli model predict exceedances better when it knows how many dry days came
  before the 48-hour window?
- **Question 2, longer window:** does it predict better with rain over 72 hours as well?

A per-site lag cannot be fitted as a model input: the rivers have 16 to 77 samples each. Instead the per-site lag is
reported as a description (below), so it can be set beside Tim's.

Neither Waterhead nor Tim's samples are in this test. Waterhead is not a designated bathing water. The four Windermere
bathing waters are Fellfoot, Lakeside YMCA, Millerground Landing and Rayrigg Meadow. Tim's plate counts, when they
arrive, are a separate check (rank tests first, as with the Fluidion data). They are not used here.

## The inputs

All come from the same hourly lead-0 forecast rain the model is fitted on (`cache/rain/leads_<cell>_<year>.parquet`,
lead 0, read as `scripts/train_ecoli.py`'s `forecast_rain_at_samples` reads it), at the sample's rain cell. The hours
are stamped and windowed as `ecoli.rain_windows` does: a value stamped H is the rain in the hour ending at H, and a
window is missing unless at least `MIN_COVERAGE` (0.9) of its hours carry a value.

**Question 1.** Three 24-hour blocks before the 48-hour window: (t − 72 h, t − 48 h], (t − 96 h, t − 72 h] and
(t − 120 h, t − 96 h], where t is the sample hour. A block is dry when its total is below 1.0 mm (the Met Office's
"wet day" threshold). `dry_run` counts dry blocks back from t − 48 h and stops at the first wet one: 0, 1, 2 or 3. A
missing block stops the count, and if the first block is missing `dry_run` is missing. Two inputs are added:
- `dry3` = `dry_run` / 3;
- `dry3_x_lrain48` = `dry3` × `lrain48`, the model's own log1p of the 48-hour rain.

The product is Tim's multiplier: dry days only matter when it then rains. `dry3` alone keeps the product from
standing in for "a dry week", which already lowers the risk through `lrain48`.

**Question 2.** One input is added: `lrain72` = log1p(rain over (t − 72 h, t]).

All are standardised like the other inputs. Nothing else in the model changes. At forecast time the blocks are known
from the live request's past days (31 past days are already fetched) or forecast, as the 48-hour window is today.

## The evaluation

`scripts/train_ecoli.py`'s own evaluations, run on the same rows three times: today's seven inputs, today's plus
Question 1's two, and today's plus Question 2's one. The rows are the samples it uses today, less any missing a new
input. Rows dropped are counted. Both questions share the reference rows, so a row missing any new input leaves all
three arms.
- **Leave one year out** (LOYO): the Brier score, all, rivers and lakes.
- **Leave one site out** (LOSO): the Brier score.
- **Forward:** fitted to 2024, scored on 2025–26.
- **Interval:** its cluster bootstrap over (site, ISO week) blocks on the LOYO predictions, for the Brier difference,
  with its seed.

### Question 1 passes if all five hold

1. **LOYO Brier, all.** It improves by at least 0.0005, and the 95% interval of the improvement is above zero.
2. **LOSO Brier, all.** No worse than today's by more than 0.0005.
3. **Forward Brier.** No worse than today's by more than 0.0005.
4. **Rivers and lakes apart (LOYO).** Neither is worse by more than 0.0005.
5. **The sign.** In the model fitted on all rows, `dry3_x_lrain48`'s coefficient is above zero: rain after a dry
   spell gives more exceedances than the same rain after wet days. `dry3` has no sign condition.

### Question 2 passes if all five hold

Conditions 1 to 4 as above, with `lrain72` in place of the two. Condition 5: `lrain72`'s coefficient is above zero.
With `lrain48` in the model, that means rain 48 to 72 hours back adds risk.

## The per-site lag, a description only

For each bathing water with at least 30 samples: Spearman's rho between log E. coli and each of rain over 24, 48 and
72 hours, and the window with the highest rho. Reported in a table, with the count of sites picking each window. It
decides nothing. It is the nearest thing in this data to Tim's per-site lags.

## What is expected, stated now

- **Question 1 will most likely fail condition 1.** The samples run from May to September, when dry spells are common
  and the 48-hour rain already separates wet days from dry ones. With about 1,500 rows and few exceedances on lakes,
  a gain of 0.0005 with an interval above zero is a high bar.
- **Question 2 will most likely fail condition 1 too.** Rain over 72 hours shares 48 of its hours with `lrain48`.
- If either passes, it is most likely on rivers, where field runoff reaches the water within a day or two.
- The per-site table will most likely pick 48 hours at most sites, because the model already uses it and it was
  chosen on these sites.

## Running

- The harness is `scripts/dry_spell_eval/`. It is committed after this file and before the run. The statement above
  the line does not change when it is added.
- Everything runs from a `git archive` of the harness commit, in a scratch folder, offline (every outgoing connection
  refused and counted, `scripts/lake_distance_eval/run_offline.py`). No fetch: the lead rain is already cached.
- The chain is the one the die-off test ran (`docs/DIEOFF-WEATHER-TEST-2026-10.md`): `validate_ecoli.py`,
  `replay_ecoli_leads.py`, `train_ecoli.py`, then this test's script. So the reference arm is today's model on
  today's code, and its scores can be set beside the published ones as a face check.
- One run, alone. It starts when no other evaluation, training, build or test runs on this machine.

## What follows

**Question 1 passes.** The two inputs are added in a separate PR. Before it ships, leads 1 to 4 are scored with
them (`train_ecoli`'s by-lead table). If any lead's Brier is worse than today's at that lead by more than 0.0005,
nothing is adopted.

**Question 2 passes.** The same, with `lrain72`.

**Both pass.** Question 1 is added first. Question 2's input is then added to that model and must still meet its
conditions 1 to 4 against it.

**Either fails.** That part changes nothing. This PR stays a record: this file, the results and the harness.

Changing a model input is allowed until the 2027 freeze tag (`docs/PREREGISTRATION-2027.md`). The PR is left for
Ethan to merge.

## What will be reported

Whatever the verdict:
- each condition with its figure and interval;
- every evaluation's table for the three arms, and the coefficients per SD;
- the share of rows at each `dry_run` value, and the correlation of `lrain72` with `lrain48`;
- the per-site lag table;
- rows dropped for a missing input, run time and network attempts.

## Seen before writing

- The published figures: LOYO Brier 0.0919, from the transport fit (`docs/TRANSPORT-FIT-TEST-2026-10.md`), and the
  die-off test's reference run, 0.0921 on its overflow table (`docs/DIEOFF-WEATHER-TEST-2026-10.md`).
- `data/processed/ecoli_validation_rows.parquet` in the main checkout (14 September 2026): 2,165 rows, 1,750 with an
  overflow upstream, from 3 May 2023 to 7 September 2026, 12 lakes and 20 rivers. Only the names, kinds and counts
  were read. No rain, E. coli or risk figure was looked at.
- One lead-rain cache file's columns and span (`leads_50.900_-1.800_2023.parquet`: hourly, leads 0 to 4, all of 2023).
- No score of any kind has been computed for this test.

---

## Results

Not yet run.
