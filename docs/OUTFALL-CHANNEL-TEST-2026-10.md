# Outfalls on a side channel: the test, stated before any result

Written 11 October 2026, before any E. coli score was computed with either option. The options are in
commit 3ae3a51. Before writing this I looked at transport weights only (no rainfall, spill model or
E. coli), and at the published results of the lake test, named under "Seen before writing".

## Why

An Environment Agency bathing water profile cross-check (11 October 2026) found that overflows the EA
names as the closest to a bathing water get 1-2% of the weight. They are snapped onto a short ditch, side
arm or gill with almost no network upstream. The length dilution `(L_ov + L0) / (L_spot + L0)` is then
tiny, though the spill reaches the main river within metres. The first snap also ignores names: it takes
the nearest link, whatever water it is.

Measured on the current overflow table (below), at the bathing water each one reaches:

| overflow | bathing water | snapped onto | network above its link | weight |
|---|---|---|---|---|
| Benson STW | Wallingford Beach | an unnamed link, 288 m | 0 m | 0.006 |
| Sudbury Water Recycling Centre | Friars Meadow, Sudbury | an unnamed link, 109 m | 0 m | 0.022 |
| Sudbury Bailey and Coates CSO | Friars Meadow, Sudbury | an unnamed arm, 104 m (the Stour 173 m) | 0 m | 0.023 |
| Bridge Lane CSO, Ilkley (receiving water Spicey Gill) | Wharfe at Cromwheel | Ewe Croft Beck, 2 m | 2.3 km | 0.022 |
| Ironbridge Dale End SSO (Lyde Brook) | River Severn at Ironbridge | Loamhole Brook, 1 m | 5.4 km | 0.016 |
| Oxford STW (Pottery Stream) | River Thames, Clifton Hampden (a listed spot) | Littlemore Brook, 118 m | 8.5 km | 0.007 |

Three overflows into Caldy Brook at Chester sit 155-252 m away on the Shropshire Union Canal, which is
not joined to the Dee.

## The options

Both are off by default. Neither adds a constant except the 1 km below.

**1. Outfall channel `junction`** (`DIPCAST_OUTFALL_CHANNEL_MODE=junction`, `transport._outfall_junction`).
It is the outfall analogue of `_adopt_main_channel`, with its thresholds:
- It applies to an outfall whose snapped link has under `ADOPT_MIN_M` (5 km) of network upstream.
- From the outfall, its water is followed downstream along the traced path for up to `OUTFALL_JOIN_M`
  (1 km).
- The first node with at least max(`ADOPT_MIN_M`, `ADOPT_RATIO` (5) × its own) upstream is the junction.
- For the length dilution, the outfall then takes the junction's upstream length instead of its own.
- Distance and travel time stay as traced.
- Only the length dilution changes. The `flow` and `urban` dilutions do not use the outfall's own
  length.

Why 1 km:
- At 0.5 m/s it takes about half an hour, 2% of T90 (30 h), so the channel's own die-off is small.
- It is of the order of an outfall's position error: the first snap reaches 750 m.

*Seen in the transport check:* the rule applies to an outfall on a lake link too. Grasmere WwTW is
snapped onto a lake-form link of Grasmere with nothing above it. Under `junction` it takes the
upstream length of the lake's main node:
- Grasmere goes from 0.104 to 0.764;
- Rydal Water from 0.040 to 0.292.

That is the rule as stated, and it is kept. Condition 5 below checks lakes separately.

**2. First snap `named`** (`DIPCAST_OUTFALL_SNAP_MODE=named`, `overflows.prefer_named`).
- An outfall that the first pass snaps onto a link not carrying a distinctive word of its own receiving
  water (`own_water`, which drops "tributary of ...") moves to the nearest link within `SNAP_MAX_M`
  (750 m) that does carry one.
- Otherwise nothing changes.
- Checked joins (`position_source = join`) stay where they are.
- The word must also not be a regional word for a small stream or a place word (`SNAP_EXTRA`: gill,
  sike, clough, lode, rhyne, pill, fleet, bourne and the words `choose_positions` already drops).

*Seen in the transport check:* without `SNAP_EXTRA`, Bridge Lane CSO (receiving water "Spicey Gill")
moved 521 m onto Old Wives Gill, matching only "gill". With it, Bridge Lane moves 526 m onto Spicey
Gill.

What neither option changes:
- Ironbridge Dale End and Oxford STW: their links have more than 5 km of network above them.
- The three Caldy Brook overflows: Caldy Brook is 910-1,640 m from them, beyond the 750 m snap radius.
- The brief counted 258 overflows on another water with their named water within 750 m. This rule moves
  684 of 14,631, because it also moves outfalls snapped onto unnamed links.

## Data

The current overflow table:
- built by `overflows.build_overflows` from the state release's live snapshot (published 11 October
  2026, 18:21 UTC);
- with main's annual returns, positions (#175) and checked joins (#177);
- 14,631 overflows, 13,807 of them on the network.

Two tables are built from the same inputs: first snap `nearest` and `named`. The river network, rain
cache, samples and EDM events are the main checkout's, read only.

## Seen before writing

Transport only, from `scripts/outfall_channel_report.py`. Live spots come from
https://swimsignal.co.uk/data/spots-lite.json (11 October 2026, 20:17), placed as the site build
places them.

| variant | live spots that change (of 105) | raised by over 25% | evaluation sites that change (of 32 with overflows upstream) | raised by over 25% |
|---|---|---|---|---|
| `junction` | 54 | 18 | 24 | 8 |
| `named` | 35 | 4 | 13 | 1 |
| both | 56 | 19 | 24 | 8 |

The evaluation sites raised by over 25%:
- Under `junction` and both:
  - Wharfe at Cromwheel (Ilkley), `uke4100-08901`;
  - Sheep's Green, River Cam, `ukh1201-09801`;
  - Friars Meadow, River Stour, `ukh1401-11051`;
  - Pangbourne Meadow, `ukj1102-11941`;
  - Wallingford Beach, `ukj1403-11947`;
  - River Severn at Ironbridge, `ukg2100-36070`;
  - Coniston Water, Brown Howe, `ukd1230-45725`;
  - River Ribble at Edisford Bridge, `ukd4308-46501`.
- Under `named`: Friars Meadow only.

Unlike the lake test, this one has power: a quarter of the evaluation sites move.

Also seen: the lake test's published results (docs/LAKE-PATH-TEST-2026-10.md). Those include the
full-set scores and the fact that Windermere Lakeside YMCA and Fellfoot had no sample over
900 cfu/100 ml. No per-site E. coli figure was looked at for any other site.

## The evaluation

The chain of #166, the urban test and the lake test, unchanged:
`validate_ecoli.py`, `replay_ecoli_leads.py`, `validate_ecoli_combined.py`, `train_ecoli.py`.
- Run by `scripts/outfall_channel_eval/run_variant.sh`, which is the lake test's wrapper with these
  options. It uses PR #172's `run_offline.py` and `paired.py` (e33eb73) unchanged.
- Four fresh runs on the same inputs:

| run | first snap | outfall channel |
|---|---|---|
| base | `nearest` | `own` |
| junction | `nearest` | `junction` |
| named | `named` | `own` |
| both | `named` | `junction` |

- Lake path is `lake` (the default since #176). Velocity is `fixed`, dilution `length`.
- Each run in its own scratch DIPCAST_ROOT. Rain from the cache only. Every outgoing network connection
  refused. One run at a time.
- The base run will not reproduce #166's 0.0909. The overflow table and the lake rule have changed.
  All comparisons are between these four runs.

Measures, each variant against base. Paired 95% intervals from 2,000 resamples with seed 1:
- LOYO, LOSO and forward Brier of the full model, from the site-week bootstrap
  (`train_ecoli.cluster_bootstrap`).
- LOYO AUC over all sites and over rivers, same bootstrap.
- LOYO Brier over lake samples, same bootstrap.
- Cross-site rho, from a site bootstrap.
- Within-site rho of exposure against log E. coli (not held out), and LOYO within-site rho of rain +
  risk + season. These two are point estimates.
- At each raised site and pooled over them: samples, the share over 900, the mean LOYO prediction, the
  LOYO Brier, the within-site rho and the exposure rank.

`scripts/outfall_channel_eval/judge.py` applies the rule below.

## What counts as passing

For each variant against base, all six must hold:

1. **Brier:** in LOYO, LOSO and forward, the upper end of the interval of the change is at most +0.0005.
2. **AUC:** over all sites and over rivers (LOYO), the lower end of the interval of the change is at
   least -0.005.
3. **Cross-site rho:** the lower end of the interval of the change is at least -0.05.
4. **Within-site rho:** both point changes are at least -0.01.
5. **Lakes:** the upper end of the interval of the LOYO Brier change over lake samples is at most
   +0.0005. Option 1 raises some lake outfalls, Grasmere's among them, so lakes must not get worse.
6. **Raised sites:** the pooled LOYO Brier over the evaluation sites the variant raises by over 25% is
   not higher. This checks that the extra exposure lands where E. coli is high.

Conditions 1-4 are the lake test's, with its margins.

What follows:
- **An option that passes on its own** is made the default in this PR. For option 1 that also needs the
  click-anywhere consistency test to pass in `junction` mode, with `build_any_point` following
  `transport`. Option 2 changes only the overflow table, which click-anywhere already reads.
- **Both options together** become the default only if "both" passes as well as each one alone. If each
  passes alone but "both" fails, the one with the lower LOYO Brier is switched on.
- **1-5 hold and 6 fails:** needs more. Keep it off.
- **Any of 1-5 fails:** keep it off.

If an option is changed after the results are seen, both results are kept and the change is stated.

## What this test cannot show

- Most of the named cases are evaluation sites: Wallingford, Friars Meadow, Ilkley Cromwheel and
  Ironbridge. Clifton Hampden (Oxford STW) and Chester (Caldy Brook) are not changed by either option.
- A pass shows the extra weight does not hurt the E. coli scores and lands where E. coli is high. It
  does not show that 1 km, or the 5 km and 5× thresholds, are right.
- The `named` rule moves 684 outfalls nationally. Only 65 of them change a weight at a live spot or evaluation site.
