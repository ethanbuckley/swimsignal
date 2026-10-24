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

Added 24 October 2026, after the run. Everything above the line is as committed in eb63bc5 (24 October 2026, 18:36
BST) and pushed before the run. The harness came in 4e4c1e8 (18:38). It changed nothing above the line.

**Verdict: both questions fail. Nothing is adopted.** Question 1 fails conditions 1, 3 and 5. Question 2 fails
condition 1 only, narrowly: its gain is 0.00049 against a margin of 0.0005, and the interval includes zero. This PR is
a record: this file, `DRY-SPELL-TEST-2026-10-score.json` and the harness.

### How it was run

- From a `git archive` of 4e4c1e8, offline, with `scripts/dry_spell_eval/run.sh`. Zero network attempts in each of
  the four steps.
- The data folder was the frozen copy the die-off test ran on (23 October). A first try on the main checkout's data
  folder stopped at `validate_ecoli.py`: its overflow table predates the 12 October network key and the code refuses
  it (`StaleOverflowTable`). Nothing was scored in that try. The frozen copy's overflow table carries key b5724303.
  SHA-256 of its processed and raw files (river network excepted): `6e13bee2…2070545`.
- Main's defaults: velocity 0.2 m/s, T90 72 h, dilution power 0.5, lake path `residence_spill`.
- Run time: `validate_ecoli` 172 s, `replay_ecoli_leads` 99 s, `train_ecoli` 100 s, `score.py` 21 s. Peak memory
  3.1 GB.

### Face check. Holds.

The reference arm's scores equal those `train_ecoli.py` wrote in the same root: LOYO 0.0921, LOSO 0.0912, forward
0.0824, 1,502 rows. No row was dropped for a missing new input. 212 of the 1,502 are over 900; 31 sites.

### The inputs

| `dry_run` | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| All rows | 35.9% | 14.2% | 6.5% | 43.4% |
| Rivers | 28.2% | 12.3% | 6.6% | 52.8% |

Correlation of `lrain72` with `lrain48`: 0.909. Of `dry3` with `lrain48`: −0.434.

### Brier scores

| Evaluation | Reference | Q1 dry spell | Q2 72 h |
|---|---|---|---|
| LOYO, all | 0.09215 | 0.09239 | 0.09165 |
| LOYO, rivers | 0.13537 | 0.13578 | 0.13448 |
| LOYO, lakes | 0.02625 | 0.02624 | 0.02636 |
| LOSO, all | 0.09119 | 0.09107 | 0.09100 |
| Forward (997 rows), all | 0.08240 | 0.08629 | 0.08207 |
| LOYO AUC | 0.8164 | 0.8144 | 0.8174 |

LOYO gain over the reference, (site, ISO week) cluster bootstrap, 1,325 clusters:

| | Gain | 95% interval |
|---|---|---|
| Q1, all | −0.00024 | −0.00136 to +0.00080 |
| Q1, rivers | −0.00040 | −0.00219 to +0.00133 |
| Q2, all | +0.00049 | −0.00014 to +0.00113 |
| Q2, rivers | +0.00089 | −0.00016 to +0.00196 |

### Question 1: dry spell. Fails conditions 1, 3 and 5.

1. LOYO gain −0.00024. Fails.
2. LOSO 0.00012 better. Holds.
3. Forward 0.00389 worse. Fails.
4. Rivers 0.00041 worse, lakes 0.00001 better: both inside the margin. Holds.
5. `dry3_x_lrain48` is −0.212 per SD. Fails. In these samples, rain after a dry spell gives *fewer* exceedances than the
   same rain after wet days, not more. `dry3` alone is +0.049.

### Question 2: 72-hour rain. Fails condition 1.

1. LOYO gain +0.00049, below the 0.0005 margin, and the interval includes zero. Fails.
2. LOSO 0.00019 better. Holds.
3. Forward 0.00033 better. Holds.
4. Rivers 0.00089 better; lakes 0.00011 worse, inside the margin. Holds.
5. `lrain72` is +0.334 per SD, and `lrain48` falls from 0.651 to 0.418. Holds.

### The per-site lag (description only)

25 bathing waters have 30 or more samples. The window with the highest Spearman rho against log E. coli:

| Window | Sites | Rivers (14) | Lakes (11) |
|---|---|---|---|
| 24 h | 6 | 1 | 5 |
| 48 h | 6 | 3 | 3 |
| 72 h | 13 | 10 | 3 |

The statement expected 48 hours at most sites. That was wrong: 10 of the 14 rivers rank best on 72 hours. Two
examples: Severn at Ironbridge 0.114 (24 h), 0.555 (48 h), 0.597 (72 h); Wharfe at Wilderness Carpark 0.445, 0.532,
0.659. At the Windermere sites the picks scatter: Lakeside YMCA 72 h (0.045, 0.256, 0.340), Millerground 24 h (0.538,
0.534, 0.517), Rayrigg 24 h, Fellfoot 72 h with all three near zero. The full table is in the JSON.

### What this shows

- **Tim's dry-day multiplier does not carry over to this model.** The sign is the opposite of his. One reading: after
  a dry spell, soil soaks up the first rain, so less runs off; after wet days, the same rain runs straight in. Another:
  `dry3` and `lrain48` are correlated (−0.43), so the product partly re-describes rain the model already has. This
  test cannot tell which. His multiplier was fitted to Waterhead's small streams, which are not in these samples.
- **A longer window helps rivers, by a little, but not enough to clear the bar.** The 72-hour arm improved every
  evaluation except lakes, and 10 of 14 rivers prefer it. But the gain is inside the noise for all rows, so by the
  rule stated above nothing changes.
- The per-site table was read after the run. Any rule built from it, such as "72 hours on rivers only", would be fitted
  to these samples. It needs its own statement and data this test has not seen: the 2027 season's EA samples, or
  Tim's Waterhead and Lakeside counts.

### What follows

Nothing is adopted. The harness stays for the next test of the same kind.
