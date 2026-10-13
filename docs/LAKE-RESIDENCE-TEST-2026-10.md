# Residence time of lakes on the way: the test, stated before any result

Written 13 October 2026, before any E. coli score was computed with this option. The option is in commit
113e251 on branch `claude/lake-residence-2026-10`, from main 25e735a. Before writing this I looked at transport
weights only (no rainfall, spill model or E. coli), and at earlier published results, named under "Seen before
writing". Results go below the line at the end. Nothing above it changes after a result is seen.

## Why

Handoff 4D (`docs/HANDOFF-2026-10-12.md`). Lakes crossed on the way (#176, lake path `lake`, the default) use the
spot's own lake constants: a drift of 0.05 m/s and a dilution of 1 / (1 + A / 5 km²). Neither is fitted, and
neither knows how long a lake holds its water. So Grasmere still passes most of a spill on to Rydal Water: on the
current overflow table, Grasmere WwTW weighs 0.0398 at Rydal Water. A Lake District water-quality group says a
spill into Grasmere has dissipated by the time the water leaves Rydal Water.

What a lake does to a spill depends on how long it holds water, not on how wide it is. Grasmere holds its water
for weeks; bacteria lose 90% in about 30 hours (`config.T90_HOURS`). Crossing 1.1 km at 0.05 m/s takes 6 hours.

#187 tried a different lake question, the spot's own lake near an inflow, and failed its cross-site condition
at Coniston. This test does not touch the spot's own lake. No wind term is built; that waits for outside data.

## The option

`DIPCAST_LAKE_PATH_MODE=residence` (`config.LAKE_PATH_MODE`). Off by default; `lake` stays the default.

A WFD lake crossed on the way (not the spot's own lake) that has a residence time τ is treated as a well-mixed
lake. Water leaves it at rate 1/τ and bacteria die in it at rate k = ln 10 / T90 = 0.0768 per hour. So:

- **Share that leaves alive:** `lake_pass = 1 / (1 + k τ)`.
- **Time spent in it by the survivors:** `lake_hold_h = τ / (1 + k τ)`, in hours. For any τ over a few days this is
  close to 1/k, 13 hours.
- These replace, for that lake: the crossing time at 0.05 m/s, the die-off over that time, and the area factor
  1 / (1 + A / 5 km²). The die-off of the rest of the journey is as before.
- The lake's metres still count in `lake_distance_m`, and the 60 km cap is unchanged, so the same overflows are
  traced.
- An outfall on the lake mixes into all of it: the whole factor applies.
- A lake with no residence time is crossed as in lake path `lake`.
- The spot's own lake, river spots with no lake on the way, distance and the dilution rule do not change.
- Click-anywhere does not follow it. `build_any_point.py` refuses the mode rather than disagree with the spot
  pages.

No constant is fitted. T90 is the model's own.

### Where the residence times come from

**HydroLAKES v1.0.** Messager, M.L., Lehner, B., Grill, G., Nedeva, I., Schmitt, O. (2016): Estimating the volume
and age of water stored in global lakes using a geo-statistical approach. *Nature Communications* 7: 13603.
Licence CC BY 4.0. It covers lakes of 10 ha or more. Its `Res_time` (days) is the lake's volume over its
long-term mean outflow.

How it was read:
- From a public ArcGIS Online copy (`services5.arcgis.com/caWDr9qv9f34KIAZ/.../HydroLAKES_Polygons/FeatureServer/0`),
  the 2,383 lakes with Country = United Kingdom, on 13 October 2026. Attributes and polygons only.
- The copy was not checked against the HydroSHEDS download (about 800 MB). Downloading it needs Ethan's go.
- `scripts/make_lake_residence.py` writes `data/raw/lake_residence.csv` (SHA-256 begins `d37bb527`).

How each WFD lake gets a time:
- The HydroLAKES lake whose polygon holds a point inside the WFD polygon.
- If the HydroLAKES lake is larger, or holds several WFD lakes, the WFD lake takes the HydroLAKES time times
  min(1, its area / the HydroLAKES lake's area): its share of the volume, emptied by the whole lake's outflow.
  This applies to Windermere, whose two WFD basins are one HydroLAKES lake (north basin 187 days, south 131).
- 282 of the 564 WFD lakes get a time. The rest are mostly under 10 ha. Elter Water (15 ha in the WFD set) is not in
  HydroLAKES, so it keeps the `lake` rule.

What the numbers are:
- **Volume is modelled, not measured,** for 250 of the 282 (`Vol_src` 3: from the lake's area and the slope of the
  land around it). 32 come from a reservoir database (`Vol_src` 2).
- **Outflow is a global model's** (WaterGAP) mean flow.

Checked against the UK Lakes Portal (UKCEH), for plausibility only:

| lake | HydroLAKES volume (Mm³) | UK Lakes Portal volume (Mm³) | Portal mean depth (m) |
|---|---|---|---|
| Grasmere | 3.57 | 4.70 | 7.7 |
| Rydal Water | 1.70 | 1.59 | 5.3 |
| Esthwaite Water | 3.61 | 6.18 | 6.4 |
| Blenheim Lakes | 1.82 | 1.12 | 2.5 |

All four are within a factor of two. The Portal's depth and volume pages state no licence. Only its lake outlines
(Taylor 2021, "Spatial inventory of UK waterbodies", EIDC) are under the Open Government Licence, and they carry no
depth. So the Portal is not used as a source.

Other open sources looked at and not used:
- Wikidata (CC0) has depth for Windermere and Ullswater only, and no residence time for any of these lakes.
- The EA's WFD typology gives only a depth class. Its Catchment Data Explorer returned 503 errors on 13 October.

### Which way the errors go

Three simplifications, all in the same direction: each makes the lake remove more of a spill than it really does.

1. **Well mixed.** A river can run through a lake without mixing into all of it: across the top layer when the lake
   is stratified in summer, or straight through in a flood.
2. **Mean flow.** Overflows spill in wet weather, when inflow is higher and the water is held for less time.
3. **Low flow for wet uplands (inferred, not checked).** HydroLAKES gives Grasmere 1.06 m³/s from 31.6 km², a
   runoff of about 1,060 mm a year. Lake District runoff is probably about twice that.

For a safety tool that is the wrong direction to err in. The sensitivity below quarters every residence time.

## The lakes on the way

From the site's 105 live spots and the 38 evaluation bathing waters, placed as the site places them, 13 WFD lakes
are crossed on the way.

| lake | WFD area (km²) | HydroLAKES depth (m) | outflow (m³/s) | τ (days) | `lake_pass` | `lake_hold_h` |
|---|---|---|---|---|---|---|
| Grasmere | 0.60 | 6.9 | 1.06 | 38.9 | 0.0138 | 12.8 |
| Rydal Water | 0.31 | 6.3 | 1.24 | 15.9 | 0.0330 | 12.6 |
| Elter Water | 0.15 | (not in HydroLAKES: `lake` rule) | | | | |
| Esthwaite Water | 0.94 | 5.1 | 0.53 | 79.5 | 0.0068 | 12.9 |
| Windermere (N Basin) | 8.67 | 15.5 | 8.34 | 187.0 | 0.0029 | 13.0 |
| Ullswater | 8.82 | 18.2 | 4.43 | 379.7 | 0.0014 | 13.0 |
| Blenheim Lakes | 0.56 | 4.4 | 1.09 | 19.3 | 0.0274 | 12.7 |
| Coate Water | 0.27 | 2.2 | 0.11 | 66.0 | 0.0082 | 12.9 |
| Virginia Water | 0.55 | 3.8 | 0.34 | 52.8 | 0.0102 | 12.9 |
| Fleet Pond | 0.28 | 2.5 | 0.08 | 87.3 | 0.0062 | 12.9 |
| Hedgecourt Lake | 0.16 | 2.6 | 0.07 | 57.2 | 0.0094 | 12.9 |
| Ardingly Reservoir | 0.77 | 6.2 | 0.28 | 167.7 | 0.0032 | 13.0 |
| Weir Wood Reservoir | 1.13 | 5.7 | 0.32 | 204.5 | 0.0026 | 13.0 |

## Seen before writing

Transport only. The setup:
- The overflow table and inputs of #205: table SHA-256 begins `e6ef0459`; network `b5724303`; built from the
  `state` release snapshot whose `live_latest.parquet` begins `eaea1f91`.
- Live spots from spots-lite.json (13 October 2026), placed as the site build places them.
- Evaluation bathing waters placed with `eval_pins.bathing_water_pin`.

**The default is unchanged.** `upstream_overflows` with lake path `lake` gives output identical to main's
`transport.py` (`DataFrame.equals`) at all 143 places.

**What `residence` changes**, as the sum of transport weights:

| place | sum, `lake` | sum, `residence` | change |
|---|---|---|---|
| Rydal Water (live, lake) | 0.0398 | 0.00098 | −97.5% |
| Windermere, Lakeside YMCA (live and evaluation) | 0.0278 | 0.0267 | −4.0% |
| Windermere, Fellfoot (live and evaluation) | 0.0086 | 0.0083 | −3.9% |
| River Thames, Port Meadow (live) | 1.102 | 1.085 | −1.6% |
| Wolvercote Mill Stream (live and evaluation) | 1.168 | 1.151 | −1.4% |
| Windermere, Waterhead (live) | 0.1446 | 0.1428 | −1.3% |
| River Thames, Long Bridges (live) | 0.751 | 0.742 | −1.3% |
| Windermere, Millerground Landing (live and evaluation) | 0.1337 | 0.1335 | −0.17% |
| Windermere, Rayrigg Meadow (live and evaluation) | 0.1465 | 0.1463 | −0.14% |
| Ham and Kingston; Wallingford Beach (evaluation) | | | −0.05%; −0.02% |

Nine more live spots change by under 0.7%. Each overflow:
- **Grasmere WwTW at Rydal Water:** 0.0398 to 0.00098. Travel 11.8 h to 18.5 h.
- **Grasmere WwTW at Waterhead:** 0.0018 to 0.0000026.
- **Woodstock STW at Wolvercote**, across Blenheim Lakes: 0.0156 to 0.0011.

Waterhead's total barely moves. Most of its weight comes from overflows that cross no lake (Ambleside WwTW).
Elterwater PS's water crosses Elter Water, which keeps the `lake` rule.

**Sensitivity, every τ quartered:** Rydal Water 0.0038 (−90.5%), Lakeside YMCA −3.6%, Wolvercote −1.1%. The same
conclusion: almost nothing crosses Grasmere and Rydal Water.

**Earlier results, all seen:**
- #176 (lake path `lake`): Lakeside YMCA and Fellfoot had 0 of 116 samples over 900 cfu/100 ml.
- #187 (near field): about 16 lake samples over 900 among 639; all three Coniston sites.
- #197 (spill hours): 595 lake samples after #199.
- #199 and #205: base figures on these inputs. 1,502 samples at 31 sites, LOYO Brier 0.0938, LOYO AUC 0.8129
  (rivers 0.747, lakes 0.528), between-site rho 0.763, LOYO within-site rho 0.422.

No per-site E. coli figure for the Windermere or Thames sites was looked at for this test.

## What the data can and cannot test

- **Rydal Water and Waterhead,** the places the note is about, have no Environment Agency samples.
- **Lakeside YMCA and Fellfoot,** the evaluation sites that move most, move by 4%. In #176 they had no sample
  over 900.
- **Wolvercote** moves by 1.4%.
- So the samples can show whether `residence` does harm. They cannot show that it helps. The case for it is
  physical, as #176's was.
- The ~16 bad lake samples the handoff mentions are at lake bathing waters. Four are at the Coniston sites
  (#187), which have no lake on the way. Where the rest are was not looked at. They enter condition 5 through the
  lake Brier score.

## The evaluation

The setup:
- The chain of #166, #176, #187 and #199, unchanged: `validate_ecoli.py`, `replay_ecoli_leads.py`,
  `validate_ecoli_combined.py`, `train_ecoli.py`, then `paired.py prep`.
- Run by `scripts/lake_residence_eval/queue.sh` and `run_variant.sh`. This is #199's harness, with the lake path
  option and its residence file in place of the pins switch. `run_offline.py` and `paired.py` are #199's,
  unchanged but for their docstrings.
- One frozen data folder, #205's inputs. The overflow table and snapshot as above; rain from a frozen copy of
  #205's 3,658 cached files; the site's pins.
- Each run in its own scratch `DIPCAST_ROOT`, with its residence file copied in.
- Every outgoing network connection is refused and counted. If a run needs rain that is not cached, I stop and
  report.
- One run at a time. Each waits until free plus inactive memory is at least 5 GB.

The 22 runs:
- `lake`: the default.
- `res`: `residence` with `data/raw/lake_residence.csv`.
- `ph01` to `ph20`: `residence` with placebo files. Each is the same 282 residence times, permuted across the same
  WFD lakes with numpy `default_rng(k)` (`make_placebos.py`).

**Check:** the `lake` run should reproduce #205's figures: 1,502 samples, 31 sites, LOYO Brier 0.0938, LOYO AUC
0.8129. If it does not, the runs are still compared, and the difference is stated.

**Measures**, `res` against `lake`:
- Paired 95% intervals from 2,000 resamples, seed 1 (`paired.py compare`), on the samples both runs keep (#166's
  rule, as in #197). Brier and AUC resample site-weeks; cross-site rho resamples sites.
- Held-out Brier of the full model: LOYO, LOSO (leave one site out) and forward (2025-26).
- LOYO AUC, all sites and rivers.
- LOYO Brier over lake samples.
- Cross-site rho: site-mean exposure against site-mean log E. coli.
- Within-site rho (point estimates):
  - exposure against log E. coli, all sites (`ecoli_validation.json`);
  - the LOYO within-site rho of rain + risk + season (`ecoli_validation_combined.json`);
  - lakes, reported only.
- Placebos: each run's own LOYO Brier, LOYO AUC (all and rivers) and cross-site rho (`summary.py`), as in #197.
- **For the record, not a condition:** at the four Windermere sites and Wolvercote, under both runs:
  - samples and samples over 900;
  - mean LOYO prediction and LOYO Brier;
  - within-site rho;
  - mean exposure and its rank among the sites.

`scripts/lake_residence_eval/judge.py` applies conditions 1 to 7 and prints the verdict.

## What counts as passing

All seven must hold.

1. **Brier.** In LOYO, LOSO and forward, the upper end of the interval of the change (`res` minus `lake`) is at
   most +0.0005.
2. **AUC.** Over all sites and over rivers (LOYO), the lower end of the interval of the change is at least −0.005.
3. **Cross-site rho.** The lower end of the interval of the change is at least −0.05.
4. **Within-site rho.** Both point changes are at least −0.01.
5. **Lakes.** The upper end of the interval of the LOYO Brier change over lake samples is at most +0.0005.
6. **Placebos.** On each of the four measures (LOYO Brier, LOYO AUC all, LOYO AUC rivers, cross-site rho), at least
   one of the 20 placebos is at least as bad as `res`.
   - This asks whether the lakes' own residence times point the wrong way, as #172 found the built-up areas did:
     they were worse than all 20 reshuffles.
   - It cannot show that the times point the right way. Most permuted times are also weeks long. With changes this
     small, the placebos are expected to fall on both sides of `res`. How many are at least as good is reported.
7. **Face check.** `tests/test_lake_residence.py` passes. Among its checks, a spill that crosses a lake holding
   water for 39 days keeps under 2% of the weight it has when the lake is walked as river, and the default output
   is unchanged.

Every run must also make 0 network attempts.

Conditions 1 to 5 and their margins are #187's, which are #176's plus the lake condition of #181. Condition 6
follows #172 and #197; it is one-sided, against harm, for the reason given.

What follows:
- **All seven hold:** `residence` becomes a candidate for the default.
  - It cannot be the default while click-anywhere does not follow it: a map click would then disagree with the
    spot page.
  - So the PR first extends click-anywhere (`build_any_point.py`, `anypoint.js` and their consistency test), then
    switches the default. It is left for Ethan to merge.
  - If click-anywhere is not finished in this session, the PR says so, and the switch stays off.
  - The terms page and README get the HydroLAKES credit when it is switched on.
- **Any fails:** it stays off. The PR is a draft record, and nothing the site uses changes.

If the option, the residence file or the harness is changed after a result is seen, both results are kept and the
change is stated.

---

## Results

Added 13 October 2026, after the runs. Everything above the line is as committed in 0cc95e9 (13 October 2026,
13:31 BST), pushed before the first run started (13:33 BST). The option, the residence file and the harness were
not changed after any result was seen.

**Verdict: all seven conditions hold. By the rule above, `residence` is a candidate for the default.** The data
show it does no harm. As stated beforehand, they cannot show that it helps.

The runs:
- 22 runs, 13:33 to 16:00 BST, one at a time, about 6 minutes each, with waits for memory while another session
  ran its own evaluation.
- 0 network attempts in all 22 runs (110 script runs).
- Peak memory 6.6 GB (`replay_ecoli_leads.py`); 4.6 GB in the `lake` run.
- **Check:** the `lake` run reproduces #205's figures: 1,502 samples, 31 sites, LOYO Brier 0.0938, LOYO AUC 0.8129,
  between-site rho 0.763, LOYO within-site rho 0.422.
- Every run kept the same 1,502 samples, so the pairing dropped nothing.
- `res.csv` is `data/raw/lake_residence.csv` read and written again by pandas. Its bytes differ (SHA-256 `5a0e12eb`)
  and its values are equal (`DataFrame.equals`).

### Conditions 1 to 5, `res` against `lake`, paired

Change is `res` minus `lake`, with its 95% interval.

| measure | `lake` | `res` | change [95% CI] |
|---|---|---|---|
| LOYO Brier (1,502) | 0.09383 | 0.09380 | −0.00003 [−0.00004, −0.00001] |
| LOYO Brier, rivers (907) | 0.13821 | 0.13817 | −0.00004 [−0.00006, −0.00002] |
| LOSO Brier | 0.09326 | 0.09324 | −0.00001 [−0.00003, −0.00000] |
| Forward (2025-26) Brier (997) | 0.08523 | 0.08521 | −0.00002 [−0.00004, −0.00000] |
| LOYO Brier, lakes (595) | 0.02618 | 0.02618 | −0.000003 [−0.000007, −0.0000002] |
| LOYO AUC | 0.8129 | 0.8129 | +0.0001 [−0.0001, +0.0002] |
| LOYO AUC, rivers | 0.7470 | 0.7470 | +0.0001 [−0.0001, +0.0003] |
| LOSO AUC | 0.8066 | 0.8068 | +0.0002 [+0.0000, +0.0003] |
| Forward AUC | 0.8070 | 0.8069 | −0.0000 [−0.0003, +0.0002] |
| LOYO AUC, lakes | 0.5278 | 0.5291 | +0.0013 [−0.0004, +0.0038] |
| Cross-site rho (31 sites) | 0.7625 | 0.7617 | −0.0008 [−0.0065, 0.0000] |
| Within-site rho, exposure, all sites (not held out) | 0.3139 | 0.3139 | 0.0000 |
| LOYO within-site rho, rain + risk + season | 0.422 | 0.423 | +0.001 |
| Within-site rho, lakes (reported only) | 0.2642 | 0.2636 | −0.0006 |

Against the conditions:
1. Brier: the upper ends are −0.00001 (LOYO), −0.000001 (LOSO) and −0.000002 (forward), all under +0.0005.
   **Holds.**
2. AUC: the lower ends are −0.0001 (all sites) and −0.0001 (rivers), both above −0.005. **Holds.**
3. Cross-site rho: the lower end is −0.0065, above −0.05. **Holds.**
4. Within-site rho: 0.0000 and +0.001, both above −0.01. **Holds.**
5. Lakes: the upper end of the lake Brier change is −0.0000002, under +0.0005. **Holds.**

### Condition 6: placebos. Holds.

As stated, each run's own figures from `summary.py`:

| measure | `res` | `lake` | 20 placebos: lowest, median, highest | at least as bad as `res` | at least as good |
|---|---|---|---|---|---|
| LOYO Brier | 0.0938 | 0.0938 | 0.0938, 0.0938, 0.0938 | 20 | 20 |
| LOYO AUC | 0.8129 | 0.8129 | 0.8129, 0.8129, 0.8129 | 20 | 20 |
| LOYO AUC, rivers | 0.7470 | 0.7470 | 0.7469, 0.7471, 0.7471 | 6 | 18 |
| Cross-site rho | 0.76169 | 0.76250 | 0.76169, 0.76169, 0.76169 | 20 | 20 |

**A weakness of the statement, found in the results.** `summary.py` reads `train_ecoli`'s figures, which are
rounded to four decimals. At that precision every run ties on three of the four measures, so condition 6 holds
there by ties. #197's statement had the same property; its differences were larger than the rounding.

A check beside the stated rule, not replacing it: the same counts unrounded, from each run's held-out predictions
(`preds_<run>.parquet`) on its own samples:

| measure | `res` | placebos at least as bad as `res` | at least as good |
|---|---|---|---|
| LOYO Brier | 0.0938042 | 6 | 14 |
| LOYO AUC | 0.8129187 | 11 | 16 |
| LOYO AUC, rivers | 0.7470435 | 6 | 16 |
| Cross-site rho | 0.7616935 | 20 | 20 |

So the check gives the same answer. The placebos fall on both sides of `res`, as expected: most permuted
residence times are also weeks long, and they remove almost as much. The samples cannot tell one lake's time from
another's.

### Condition 7: face check. Holds.

`tests/test_lake_residence.py`: 9 passed.

### The sites that move, for the record

LOYO, `lake` → `res`:

| site | samples | over 900 | mean LOYO prediction | LOYO Brier | within-site rho | mean exposure | rank of 31 |
|---|---|---|---|---|---|---|---|
| Windermere, Lakeside YMCA | 57 | 0 | 0.0221 → 0.0218 | 0.00056 → 0.00054 | 0.342 → 0.337 | 0.00206 → 0.00184 | 28 → 28 |
| Windermere, Fellfoot | 59 | 0 | 0.0201 → 0.0199 | 0.00046 → 0.00045 | 0.129 → 0.123 | 0.00070 → 0.00062 | 29 → 30 |
| Windermere, Millerground Landing | 59 | 0 | 0.0272 → 0.0272 | 0.00087 → 0.00087 | 0.492 → 0.493 | 0.00805 → 0.00801 | 23 → 23 |
| Windermere, Rayrigg Meadow | 57 | 0 | 0.0284 → 0.0284 | 0.00094 → 0.00094 | 0.211 → 0.212 | 0.00865 → 0.00862 | 22 → 22 |
| Wolvercote Mill Stream | 55 | 2 | 0.1615 → 0.1607 | 0.0571 → 0.0567 | 0.152 → 0.158 | 0.0261 → 0.0255 | 15 → 15 |

The cross-site change comes from one swap at the bottom of the ranking: Fellfoot goes from 29th to 30th.

### What this shows

Established, from the tables above:
- `residence` does no harm to any held-out score. Every Brier change is a small gain, and its interval stays below 0.
- None of the four Windermere sites had a sample over 900 cfu/100 ml. At a site with no exceedance, a lower
  prediction always gives a lower Brier score. So the lake Brier gain is arithmetic, not evidence.
- The 20 placebos score the same as `res` to four decimals. The samples cannot tell whether a lake's own
  residence time is right.

Inferred, not tested:
- Rydal Water and Waterhead have no Environment Agency samples. So what the reviewer described is not tested
  here: a spill in Grasmere is gone by Rydal Water's outflow. The model now agrees with it (Grasmere WwTW at Rydal
  Water 0.0398 → 0.00098). Samples below Grasmere and Rydal Water would test it.
- The three simplifications under "Which way the errors go" all overstate what a lake removes. The case for
  switching is that a fixed 0.05 m/s drift is further from how lakes hold water than a residence time is. The
  quartered sensitivity reaches the same conclusion at Rydal Water.

### Click-anywhere

Written while the runs were going, in commit 6be6f1a; the E. coli chain does not import it.
- Link records and lake inlets carry `h`: per overflow, the metres of well-mixed lake, the survivors' hours and the
  share alive.
- `anypoint.js` `transportOf` gives travel and die-off as `upstream_overflows` does.
- The cache key holds the residence file's hash and T90 in this mode.
- Lake and river output is unchanged. Their fixture data are identical; only the `lakes.json` note text changed.
- The consistency tests and page fixture cover all three modes, with travel and die-off.
- On the real network, checked against `upstream_overflows`:
  - a click in Rydal Water: Grasmere WwTW, weight 1.053e-3 and 17.62 h in both;
  - the Thames at Port Meadow: 29 overflows, largest weight difference 2e-16, travel equal.

So the condition in "What follows" is met. The default switch is in the next commit, left for Ethan to merge.
