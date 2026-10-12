# E. coli evaluation pins: the change and its test, stated before any result

Written 12 October 2026, before any E. coli number was computed with the site's pins. Main was at
e52b750. The code change is in the same commit as this file. Results go in a later commit, under
"Results".

**Answer.** Three of the 38 inland bathing waters count different overflows upstream in the E. coli
evaluation than on the site: Colwick West Lake, Queen Elizabeth Gardens (Salisbury) and Wolvercote
Mill Stream. Two more get a different pin but count no overflows either way. The other 33 are the
same. The evaluation should place bathing waters exactly as the site does. This file states the
change and the paired run that measures what it does to the published numbers.

## 1. What differs

**How it was checked.** The river network loaded with the current fixes (topology key `ccc58f6b`).
The overflow table was rebuilt with `load_overflows(net, rebuild=True)` into a scratch
`DIPCAST_STATE`, from the `state` release's live snapshot (uploaded 12 Oct 13:12 UTC): 14,631
overflows, key `ccc58f6b`. For each bathing water, two pins:

- **eval**: `locate_pin(net, lon, lat)` with no hints, at `bwq_samples.parquet`'s position. This is
  what `validate_ecoli.py`, `replay_ecoli_leads.py`, `fetch_rain_leads_upstream.py` and
  `fetch_rain_validation.py` did.
- **site**: `locate_pin` with the spots.csv row's position, kind, river and name, as
  `scripts/build_site.py` passes them.

Then `upstream_overflows` at the default velocity for each. The site pins reproduce the live
`spots.json` (pin mode, overflow count and sum of weights) at all 38. The two positions are at most
0.6 m apart; the site's hints at the eval's position give the same upstream sets as the site's pins.
So the difference comes from the hints, not the positions.

| Bathing water | Eval pin | Site pin | Overflows, eval | Overflows, site | In both | Eval-only share of eval weight |
|---|---|---|---|---|---|---|
| Colwick Country Park (West Lake), ukf1400-09750 | river: River Trent, 199 m | lake: its own centreline, 444 m | 357 | 0 | 0 | 100% |
| River Avon at Queen Elizabeth Gardens, ukk1500-19002 | river: the Avon below the Nadder, 366 m | river: side arm head (#179), 77 m | 32 | 16 | 14 | 60.5% |
| Wolvercote Mill Stream, ukj1402-11946 | river: Thames, 342 m | river: side arm head, 320 m | 29 | 31 | 29 | 0% (the 2 site-only carry 0.1% of the site's weight) |
| Henleaze Lake, ukk1100-36050 | river: River Trym | isolated | 0 | 0 | | |
| Cotswold Country Park and Beach, ukk1302-11760 | river: Cerneywick Brook | isolated | 0 | 0 | | |
| The other 33 | same link | same link | same | same | all | 0% (single weights within 3e-5) |

Details, all established from the run above:

- **Colwick.** The eval traces the Trent and counts 357 Severn Trent overflows, sum of weights 19.3.
  That is the largest sum of the 38; the next is the Nidd at Knaresborough, 10.7. Ten Nottingham
  CSOs (Sneinton, St Ann's, Colwick Road) about 2 km upstream along the network weigh 0.92 each. The site counts none and gives no spill
  forecast (ROADMAP-2026-10 section 2.4). The EA's 2022 profile for West Lake says it "is not
  directly connected to any streams or rivers", and that no sewer overflows discharge into it.
- **Queen Elizabeth Gardens.** The 18 eval-only overflows are all in the Wylye and Nadder catchments
  (Wishford Wilton Road Storm Tank 0.199, Barford St Martin Burcombe Storm Tank 0.140, Barford St
  Martin 0.134, Hanging Langford 0.100, and smaller). The 14 shared ones are on the Avon above Salisbury. They
  weigh about 2.7 times as much at the site's pin (Amesbury Off Church Street Storm Tank 0.139 eval,
  0.372 site): the site's pin is above the Nadder, so less water dilutes them. Sum of weights: eval
  1.099, site 1.170. Two overflows near the 60 km limit (Horton, Coate; 0.003 each) are counted only
  at the site's pin, which is about 1.9 km further up the network. The site's placement is #179's side-arm head rule. I have not re-checked it;
  the 2026 EA profile's text names neither the Nadder nor the Wylye.
- **Wolvercote.** Two overflows near the 60 km limit are counted only at the site's pin (Broadwell
  STW and Stanton Fitzwarren SPS, 0.0006 each). The largest shared one, Cassington STW, weighs 0.846
  at the eval's pin and 0.856 at the site's. Sum of weights: eval 1.152, site 1.168.
- **Henleaze and Cotswold.** Different pins, but no overflows either way, so no number changes.

**This is not new.** The committed `data/processed/validation_sites.csv` (13 Sep 2026) already has
Colwick on the River Trent with 293 overflows, and Queen Elizabeth Gardens with 21.

**Samples.** 2,165 E. coli samples at the 38 sites (May 2023 to 7 Sep 2026). Colwick 65 (2023–26,
none over 900 per 100 ml), Queen Elizabeth Gardens 17 (2026 only, 4 over 900), Wolvercote 75 (3 over
900).

## 2. Why it matters

- `train_ecoli.py` refits `ecoli_model.json`, the E. coli model the site serves, on these rows. The
  site feeds that model the exposure at its own pin. At Colwick the fit sees exposure from 357
  overflows; the site computes none. At Queen Elizabeth Gardens 60% of the fitted exposure comes from
  rivers the site leaves out.
- The Accuracy page (`ecoli_validation.json`, `ecoli_validation_combined.json`,
  `ecoli_model_eval.json`) and the spot pages' water lead skill (`build_site.lead_skill`) describe the
  evaluation's pins, not the site's.
- `train_ecoli.py` and `validate_ecoli_combined.py` keep only samples with overflows upstream. With
  the site's pin, Colwick has none, so its samples leave the fit, as the site shows no estimate there.

## 3. The change (this commit)

- `transport.spot_hints(kind, river)`: the one rule for a spots.csv row's hints. `build_site.py` now
  calls it in `prefetch_rain` and `build`, and `_river_of` comes from it. The site's pins do not
  change: same arguments as before (`tests/test_eval_pins.py` checks `_river_of` on every row).
- `scripts/eval_pins.py`: `bathing_water_pin(net, bw_id, lon, lat)` reads the bathing water's
  spots.csv row (`bw-<id>`) and places it as the site does. A bathing water with no row raises an
  error. `DIPCAST_EVAL_PINS=bare` gives the old rule, for this test and for reproducing old numbers.
- The four evaluation scripts call `bathing_water_pin`. A test fails if any of them calls
  `locate_pin` itself.
- Not changed: `scripts/lake_path_report.py`, whose `eval:` rows imitate the old evaluation for a
  finished test, and `scripts/check_ecoli_wales.py` (Welsh stations, its own hints).

**Merging this makes the next E. coli refit use the site's pins.** It changes no published file by
itself. `ecoli_model.json` and the Accuracy files change only when the chain is rerun and its outputs
committed. That rerun is Ethan's call (section 6).

## 4. The test, stated before running

Two runs of the E. coli chain, one at a time, with every outgoing connection refused:
`validate_ecoli`, `replay_ecoli_leads`, `validate_ecoli_combined`, `train_ecoli`, then `paired.py prep`
(`scripts/eval_pins_test/run_variant.sh`). Run `bare` has `DIPCAST_EVAL_PINS=bare`, run `site` has
`site`. Everything else is the same:

- network `ccc58f6b` and the overflow table above;
- rain: a frozen copy (APFS clone) of the main checkout's `data/cache/rain`, taken at 17:35 BST
  on 12 Oct, after another session added 42 lead and 170 archive files at 17:25. It holds every cell
  the old pins need. The site's pins need two more cells, (51.4, −1.9) and (51.9, −1.7). They carry
  0.53% of Queen Elizabeth Gardens' weight and 0.05% of Wolvercote's. Their 16 files were fetched into
  the copy only. 3,658 files in all;
- every transport option at main's default.

`scripts/eval_pins_test/compare.py` then reports, from the runs' outputs only:

1. **The check.** At the 35 other bathing waters both runs score the same samples, with the same
   upstream count and rain. `risk_model` and the replayed exposures (`risk_prod`, `risk_holdout`,
   `missing_share`) agree within 0.001. Neither run tried the network.
2. **The published measures** of each run: samples and sites; LOYO, LOSO and forward Brier and AUC
   (all, rivers, lakes); the water lead skill at leads 0 to 4; `risk_model`'s Spearman rho (pooled,
   within site) and AUC at 500 and 900 (all, rivers, lakes); the combined file's between-site rho and
   LOYO within-site rho; cross-site rho unrounded; the refitted model's coefficients.
3. **The three changed sites**: samples, samples in the fit, upstream count, mean and maximum
   `risk_model`, within-site rho.
4. **Paired bootstraps** (`paired.py compare`, 2,000 resamples of site-week clusters) on the samples
   both runs keep: LOYO (all, rivers, lakes), LOSO, forward; the change in cross-site rho.

**Decision rule.** The site's pins are recommended whatever the numbers do. A pin is right or wrong by
where the water goes, not by the score it gives; choosing pins by their score would fit the evaluation
to its answer. The run is there so the change is published with its size. Two outcomes stop it and
change the recommendation: the check in step 1 fails (the code does more than this file says), or a
run fails. Either way I stop and report.

**Predictions.** Inferred, written before running. They are not conditions.

- P1. Colwick leaves the fit, so the fitted sample count falls by Colwick's samples in the `bare` fit
  (at most 65).
- P2. Cross-site rho rises. In `bare`, Colwick should have the highest mean exposure of the sites and
  one of the lowest E. coli means.
- P3. Queen Elizabeth Gardens: no prediction of direction. Its shared overflows gain weight while the
  Wylye and Nadder ones leave.
- P4. Wolvercote: mean `risk_model` moves by less than 0.01.

**Seen before writing.** Transport weights and upstream sets for both pins at all 38 (no rain, spill
model or E. coli computed with the site's pins). The committed per-site file of 14 Sep: `rho_model`
at Colwick −0.267 (293 overflows, median E. coli 27), Queen Elizabeth Gardens 0.585 (21), Wolvercote
0.183 (29). Sample and exceedance counts at the five sites in the table. Rain-cache coverage for both
pin sets.

## 5. What a refit would change besides the pins

The published E. coli files are from 16 Sep 2026 (commit 9f49774). Since then the network fixes
(#184), the lake placement (#173), the side-arm head rule (#179), the joins (#175, #177, #188) and the
lake path (#176) have changed many upstream sets. A refit now moves the published numbers for all of
those reasons. The paired run isolates the pins' part: both runs share everything else.

## 6. What stays Ethan's

1. Whether the evaluation uses the site's pins: merging this PR.
2. When to rerun the chain and commit the refitted `ecoli_model.json` and the Accuracy files. The
   rain caches should be complete for the chosen pins first: run `fetch_rain_leads_upstream.py` and
   `fetch_rain_validation.py` after merging (with the site's pins they add the two cells above).

## Results

Run 12 Oct 2026: `bare` 17:44 to 17:50 BST, `site` 17:51 to 17:57, after another session's runs had
finished. Both completed. Neither tried the network. Peak memory stayed under 4.7 GB. Nothing in this
section was known when sections 1 to 6 were written.

**Verdict under the rule above: the recommendation stands.** The check held and both runs completed.
The evaluation should use the site's pins.

### The check holds

At the 35 other bathing waters: 2,008 samples, all paired; upstream counts and rain the same;
`risk_model` within 1.1e-5; the replayed exposures within 1e-4. The change does only what section 1
says.

### The predictions

- **P1 held.** Colwick leaves the fit. `train_ecoli` had kept 44 of its 65 samples in `bare` (it also
  drops samples without forecast rain or a shown figure at every lead). The fit goes from 1,546 samples
  at 32 sites to 1,502 at 31. The paired comparison keeps all 1,502; Colwick is the only site lost.
- **P2 held, for the reason given and no other.** Cross-site rho rises from 0.705 to 0.763. On the 31
  sites both runs keep, it falls from 0.821 to 0.763 (change −0.058, 95% interval −0.207 to 0.000).
  Colwick leaving raises it; Queen Elizabeth Gardens lowers it (next point).
- **P3, no direction stated.** Queen Elizabeth Gardens' mean `risk_model` falls from 0.024 to 0.005
  and its maximum from 0.140 to 0.016. Within-site rho goes from 0.596 to 0.533 (17 samples). Its sum
  of weights rose (1.099 to 1.170), so the dropped Wylye and Nadder overflows carried most of its
  exposure. It now has low exposure and 4 of 17 samples over 900, which is what lowers cross-site rho.
- **P4 held.** Wolvercote's mean `risk_model` moves from 0.0257 to 0.0261.

### The published measures

"Published" is the files on main, made 16 Sep. `bare` is the old pins on today's network and rain;
the gap between those two columns is section 5's other changes, not the pins.

| Measure | Published | bare | site |
|---|---|---|---|
| Samples in the fit (sites) | 1,548 (32) | 1,546 (32) | 1,502 (31) |
| LOYO Brier, all | 0.0908 | 0.0911 | 0.0938 |
| LOYO AUC: all, rivers, lakes | 0.815, 0.749, 0.466 | 0.814, 0.748, 0.472 | 0.813, 0.747, 0.528 |
| LOSO Brier, AUC | 0.0903, 0.808 | 0.0906, 0.806 | 0.0933, 0.807 |
| Forward Brier, AUC (test samples) | 0.0826, 0.810 (1,028) | 0.0830, 0.809 (1,026) | 0.0852, 0.807 (997) |
| Water lead skill shown on spot pages, leads 1 to 4 | 0.752, 0.692, 0.547, 0.547 | 0.745, 0.685, 0.537, 0.537 | 0.759, 0.694, 0.551, 0.551 |
| `risk_model` rho, pooled and within site, all sites | 0.572, 0.293 | 0.564, 0.288 | 0.631, 0.314 |
| `risk_model` AUC over 900, all sites | 0.797 | 0.796 | 0.810 |
| `risk_model` rho pooled, within site, AUC over 900: rivers | 0.477, 0.407, 0.747 | 0.479, 0.403, 0.749 | 0.470, 0.399, 0.744 |
| `risk_model` rho pooled, within site, AUC over 900: lakes | 0.283, 0.213, 0.602 | 0.290, 0.211, 0.606 | 0.342, 0.264, 0.656 |
| Between-site rho (combined file) | 0.684 | 0.705 | 0.763 |
| LOYO within-site rho (combined file) | 0.389 | 0.389 | 0.422 |
| Model coefficients: exposure, lake, intercept | 0.545, −0.467, −2.492 | 0.531, −0.456, −2.486 | 0.589, −0.263, −2.406 |

### Paired, on the 1,502 samples both runs keep

2,000 resamples of site-week clusters. Brier gain is `bare` minus `site`, so positive means the site's
pins do better.

| Split | Brier, bare | Brier, site | Gain (95% interval) | AUC, bare to site (interval of change) |
|---|---|---|---|---|
| LOYO, all | 0.09360 | 0.09383 | −0.00023 (−0.00085 to +0.00029) | 0.813 to 0.813 (−0.003 to +0.003) |
| LOYO, rivers (907) | 0.13781 | 0.13821 | −0.00040 (−0.00146 to +0.00048) | 0.748 to 0.747 (−0.004 to +0.003) |
| LOYO, lakes (595, 16 over 900) | 0.02621 | 0.02618 | +0.00002 (−0.00016 to +0.00026) | 0.504 to 0.528 (+0.001 to +0.048) |
| LOSO, all | 0.09281 | 0.09326 | −0.00045 (−0.00111 to +0.00010) | 0.808 to 0.807 (−0.004 to +0.001) |
| Forward, all (997) | 0.08535 | 0.08523 | +0.00012 (−0.00051 to +0.00069) | 0.807 to 0.807 (−0.004 to +0.004) |

### Reading

Established from the tables above:
- On the samples both runs keep, no Brier change can be told from zero, in any split.
- Most published figures move because Colwick's samples leave, not because forecasts elsewhere change.
  LOYO Brier rises by 0.0027 on the published figure but by 0.0002 on the paired samples.
- The refitted model weighs exposure more (coefficient 0.531 to 0.589) and penalises lakes less (−0.456
  to −0.263).

Inferred:
- LOYO Brier rises on the published figure because Colwick's samples were easy to score: none was over
  900. The validation rho and between-site rho rise because Colwick had the most exposure of any site
  and one of the lowest E. coli means.
- The lake AUC gain rests on 16 exceedances. It is not evidence the model now works on lakes.

**One thing to check, which does not change the rule:** Queen Elizabeth Gardens. With the site's pin
its exposure is a fifth of the evaluation's, yet 4 of its 17 samples were over 900. If #179's placement
is wrong, this is where it would show. Settling it needs the EA's zone-of-influence map. The profile's
image link returned an HTML page, not a map, so I have not seen it.
