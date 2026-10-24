# The water body's farm-pollution flag as an E. coli input: the test, stated before any run

Written 24 October 2026. Nothing has been run. No score of any kind has been computed for this test. Results go below
the line at the end. Nothing above it changes after a result is seen.

This is review task D7, part 2 (`docs/REVIEW-2026-10-16.md`, D7 and section 4 item 6). Part 1 gave every listed spot
its Environment Agency water body and that water body's reasons for not achieving good status
(`data/raw/rnags.json`, from the Catchment Data Explorer, Open Government Licence v3.0; `scripts/make_rnags.py`).
The D7 session drafted this test on 18 October in its notes. This file starts from that draft. What changed, and why,
is listed under "Changed from the draft".

## Why

The E. coli model (`model/ecoli.py`, `FEATURES`) is a logistic regression on rain at the spot over 48 and 24 hours,
the overflow exposure index, a lake flag, lake × rain, and the day of the year. The README says what it leaves out:
"the diffuse runoff (farms, roads, urban drainage) that rain washes into rivers regardless of overflows".

The Environment Agency lists, per water body, the sectors and issues that keep it from good status. One of them is
the sector "Agriculture and rural land management" with the issue "Pollution from rural areas". The question:

**Does a flag for that pressure on the sample site's water body improve the E. coli exceedance model?**

## The input

`farm` = 1 where the bathing water's water body lists sector "Agriculture and rural land management" with issue
"Pollution from rural areas", at certainty confirmed or probable. Otherwise 0.

- **Source:** `data/raw/rnags.json` as committed on main (fetched 18 October 2026, SHA-256 of the source CSV
  `553bb49f…`). The bathing water's entry is `spots["bw-" + bw_id]`; its reasons are
  `water_bodies[id]["pressures"]`. This is the rule `build_site.attach_water_body` uses for the page line
  (`FARM_PRESSURE`), so the model and the page would mean the same thing.
- **The join** is part 1's, unchanged. A river bathing water is in the water body whose river line, named for its
  river, is nearest within 500 m; else in the named catchment that holds it. A lake bathing water is in the WFD lake
  the forecast already places it in.
- **Join failures.** Of the 32 bathing waters with an overflow upstream in the frozen rows file (below):
  - Sandy Lane, Chester (river) is placed nowhere. The Welsh Dee is not in England's file.
  - Colwick Country Park (lake) is placed nowhere. Its lake is not a WFD lake.
  - River Avon at Fordingbridge is placed, but its water body lists no reasons at all.

  All three get `farm` = 0. "Not placed" is not the same as "no farm pressure", so a record-only rerun leaves the two
  unplaced sites out (below).
- **It varies only between sites.** One value per bathing water, the same on every sample. It can move a group of
  sites' baseline. It cannot tell one day from another.
- Standardised like the other inputs. Nothing else in the model changes.

## Why leaving a site out decides

A fixed site-level input can fit the sites it was trained on rather than predict. In leave-one-year-out (LOYO) every
site is in the training set, through its other years. The flag splits the sites into two groups, and each group's
fitted baseline is learned partly from the very site being scored. A gain there can be the flag re-describing which
sites run high.

In leave-one-site-out (LOSO) the scored site is never seen. The flag can only help by carrying what the other
flagged sites show to a new one. That is the promise the input makes: a forecast at a spot the model has no samples
for. So LOSO is the primary evaluation, and its interval resamples whole sites, not site-weeks. Site-weeks would
count the weeks at one site as independent evidence about one fixed fact.

A second check guards against luck in which sites are flagged: **placebo flags.** The same number of sites are
flagged at random among the river sites, and the same number among the lake sites, 1,000 times (seed 1). Each
placebo goes through the same LOSO. If any split of the sites into two groups of these sizes gains as much, the flag
has told the model nothing about farms.

## Models compared

- **Reference:** `ecoli.FEATURES`, today's seven inputs, with `train_ecoli.py`'s fitting (`ecoli.fit`, C = 1.0).
- **Candidate:** `FEATURES + ["farm"]`.
- **For the record only** (they decide nothing):
  - `farm_confirmed`: confirmed only, in place of `farm`;
  - `farm` and `farm_x_lrain48` (= `farm` × `lrain48`): runoff that rain washes in;
  - the reference and candidate refitted without the two unplaced sites.

## Data

**England: the rows `train_ecoli.py` fits on,** with its filters, unchanged: bathing-water samples with an overflow
upstream, forecast rain at every lead, and a shown exposure at every lead. On the die-off and dry-spell runs this was
1,502 samples at 31 bathing waters.

The rows come from the chain the dry-spell test ran (`docs/DRY-SPELL-TEST-2026-10.md`): `validate_ecoli.py`,
`replay_ecoli_leads.py`, `train_ecoli.py`, then this test's script, all in one scratch root on a copy of the frozen
data folder the die-off test made on 23 October. The main checkout's overflow table predates the 12 October network
key and is refused (`StaleOverflowTable`).

**Face check:** the reference arm's LOYO, LOSO and forward Brier scores equal those `train_ecoli.py` writes in the
same root. If they do not, the run stops and the write-up says why.

## The evaluations

`train_ecoli.py`'s own functions (`leave_one_out`, `_fit_predict`, `cluster_bootstrap`, 2,000 resamples, seed 1):
- **LOSO:** each bathing water predicted by a model that never saw it. Brier, all rows, rivers and lakes.
- **LOYO:** each year predicted by a model fitted on the others.
- **Forward:** fitted to 2024 and before, scored on 2025–26, with the exposure from the 2023–24 spill model.
- **Intervals:** the gain's 95% interval from `cluster_bootstrap` with whole sites as clusters, on the LOSO
  predictions. The (site, ISO week) interval is reported beside it.
- **Placebo flags:** 1,000 placebo flags as above, each scored by LOSO (all rows) and LOYO (all rows) against the
  same reference.

## What counts as helping: all six must hold

1. **LOSO gain, all rows.** The candidate's LOSO Brier is lower than the reference's by at least 0.0005, and the
   lower end of the whole-site 95% interval of the gain is above zero.
2. **Placebo, LOSO.** Fewer than 5% of the 1,000 placebo flags gain as much or more in LOSO, all rows.
3. **LOYO not worse.** All rows, by no more than 0.0005.
4. **Forward not worse.** All rows, by no more than 0.0005.
5. **Rivers and lakes apart (LOSO).** Neither is worse by more than 0.0005.
6. **The sign.** In the candidate fitted on all rows, `farm`'s coefficient is above zero: a farm pressure on the water
   body goes with more exceedances, not fewer.

The margin, 0.0005, is the one the dry-spell and die-off tests used.

## Does the flag re-describe sites? Stated now, decides nothing

The write-up gives one of three readings, by these rules:
- **Re-describes sites:** the LOYO gain, all rows, is at least 0.0005, and the LOSO gain is below 0.0005.
- **Predicts new sites:** conditions 1 and 2 hold.
- **Neither:** both gains are below 0.0005.

If none of these fits (a LOSO gain of at least 0.0005 that fails its interval or the placebo), the write-up says so
in those words. Beside the reading: where the real flag's LOYO and LOSO gains fall in the placebo distributions. If
random splits of the sites gain as much in LOYO as the real flag, the LOYO gain is the site-mean effect.

## Wales: not run

The brief asks for the flag on W10's Welsh set (185 samples at 11 stations on the Wye near Hay and the Tywi at
Llandeilo; `docs/WALES-PLAN-2026-10.md`), where the estimate averaged 32% against 5.9% observed. The Welsh flag needs
Natural Resources Wales's reasons for not achieving good status. Searched again on 24 October:
- England's file holds no Welsh water body on the Wye above Bredwardine or on the Tywi (part 1, checked by
  operational catchment name).
- DataMapWales publishes NRW's Cycle 3 classifications under the Open Government Licence. That is the status, not
  the reasons.
- An Afonydd Cymru report (November 2025) says NRW keeps a reasons document and that "only the 2022 version is
  currently publicly available". No download of it with a stated licence was found.
- The Environment Agency's retired cycle 2 reasons dataset (2015) holds Welsh Severn water bodies, so the Wye but not
  the Tywi. It is a different cycle from England's file, so the flag would mean different things on each side of the
  border.

So the Welsh arm is not run and Wales is out of the decision. A later test can add it if NRW publishes its reasons
under an open licence; the stations would be placed by part 1's rule on NRW's river lines.

Written now so the result cannot read as a surprise: both Welsh catchments are rural, so the flag would most likely
be 1 there. A positive `farm` coefficient would then raise Welsh predictions that are already too high.

## What is expected, stated now

- **Condition 1 will most likely fail on its interval.** About 31 sites, with the flag splitting them roughly in
  half. A whole-site interval over so few sites can include zero for a real but modest effect. A fail means "not
  shown". It does not mean "no effect".
- **The LOYO gain will most likely exceed the LOSO gain,** for the reason given under "Why leaving a site out
  decides".
- The sign is open. Rural water bodies tend to have fewer overflows upstream, and the exposure index already carries
  that. The flag may end up marking "fewer overflows than the index thinks" as much as "more farm runoff".

## What follows

- **All six hold:** a proposal for Ethan, not a change. The candidate refitted on all rows, used where the flag is
  known. Where it is not (a map click, which has no water body; a spot added since `rnags.json` was made; anywhere in
  Wales) the reference model stays. Before it ships, leads 1 to 4 are scored with it (`train_ecoli`'s by-lead table),
  as the dry-spell test required. The live estimate does not change until he decides.
- **Any fails:** nothing changes. This PR stays a record: this file, its score file and the harness.

Changing a model input is allowed until the 2027 freeze tag (`docs/PREREGISTRATION-2027.md`).

## What will be reported

Whatever the verdict:
- each condition with its figure and interval;
- LOSO, LOYO and forward Brier for the reference, the candidate and the record-only arms, all rows, rivers and lakes,
  with AUC;
- the coefficients per SD;
- the placebo distributions (percentiles) and where the real flag falls in them;
- the flag's split by kind, in sites and rows, after `train_ecoli`'s filters;
- run time and network attempts.

## Running

- The harness is `scripts/farm_pressure_eval/`. It is committed after this file and before the run. The statement
  above the line does not change when it is added.
- Everything runs from a `git archive` of the harness commit, in a scratch folder, offline (every outgoing connection
  refused and counted, `scripts/lake_distance_eval/run_offline.py`). No fetch.
- Main's defaults: no option variables.
- One run, alone, when no other evaluation, training, build or test runs on this machine and at least 35% of memory
  is free.

## Changed from the draft

The D7 session's draft (18 October, not committed) is the base. Changes, made before any run:
- **Primary evaluation.** The draft required gains in both LOYO and LOSO, on rivers. Here LOSO decides, on all rows,
  and LOYO need only not be worse. A LOYO gain is what a site-mean fit produces, so requiring it adds nothing about
  new sites. All rows, because the model is fitted on rivers and lakes together and 31 sites give more power than 20;
  rivers and lakes must each not be worse.
- **Placebo flags,** added: the direct check on whether any split of the sites does as well.
- **The 0.0005 margin,** added, as in the dry-spell and die-off tests.
- **The reference.** The draft checked against main's `ecoli_model_eval.json` within 0.0005. Here the face check is
  against `train_ecoli.py`'s output in the same root, as in the dry-spell test.
- **Wales,** the draft's precondition applied: no openly licensed NRW table was found, so the arm is not run.

## Seen before writing

- The draft and part 1's PR description and notes.
- How the flag splits the 32 bathing waters with an overflow upstream in the frozen `ecoli_validation_rows.parquet`
  (before `train_ecoli`'s filters). Only `bw_id`, `name`, `kind` and `upstream` were read.

  | | flag 1 (confirmed / probable) | flag 0 | not placed |
  |---|---|---|---|
  | Rivers (20) | 9 (2 / 7) | 10 | 1 |
  | Lakes (12) | 7 (3 / 4) | 4 | 1 |

- The published reference figures from the dry-spell run on the same frozen folder: LOYO 0.0921, LOSO 0.0912,
  forward 0.0824, 1,502 rows, 31 sites.
- W10's published results.
- No E. coli value, exceedance or score was looked at against the flag.

---

## Results

(Empty until the run.)
