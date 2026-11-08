# River rises: evaluation result

Scored 2026-11-05T23:54:04+00:00. Predictions SHA-256 `a1f304431d49a6a7c398665de446bb31f769bfaace6c93546c0853a187b4f8e3`; statement SHA-256 `cb5c060332ac45440bafab9c59e265cb5016b1047aa7edb7296f72f44f5864d0`.

## Gate (checked before any score)

- Spot gauges with a pair: 26 (needs 25).
- Share of hourly issue times with a label: training 0.947, test 0.954 (needs 0.8 in both).
- Label-1 episodes in P, test period: 596 at 25 gauges in 10 river systems (needs 150, 15, 6).
- **Met.**

Each gauge's share of hourly issue times with a label (reported; the gate uses the pooled share above):

| Spot gauge | Training | Test |
|---|---|---|
| 022009 | 1.000 | 1.000 |
| 055807_TG 320 | 0.712 | 0.991 |
| 0569TH | 1.000 | 1.000 |
| 1100TH | 1.000 | 0.998 |
| 1800TH | 1.000 | 1.000 |
| 2077 | 1.000 | 1.000 |
| 2134 | 1.000 | 1.000 |
| 2200TH | 0.999 | 1.000 |
| 2320 | 1.000 | 0.949 |
| 2625 | 1.000 | 1.000 |
| 3040TH | 0.998 | 1.000 |
| 3404TH | 1.000 | 0.975 |
| 4197 | 0.464 | 0.893 |
| 43123 | 1.000 | 1.000 |
| 46122 | 1.000 | 1.000 |
| 52111 | 1.000 | 1.000 |
| 53120 | 1.000 | 1.000 |
| 53129 | 1.000 | 1.000 |
| 710301 | 0.379 | 0.742 |
| 722421 | 1.000 | 1.000 |
| 724629 | 0.999 | 1.000 |
| 760502 | 1.000 | 0.991 |
| 762505 | 1.000 | 1.000 |
| E22678 | 0.701 | 1.000 |
| F1902 | 1.000 | 1.000 |
| F1903 | 1.000 | 1.000 |
| F1906 | 1.000 | 1.000 |
| F2004 | 1.000 | 1.000 |
| F3505 | 1.000 | 0.974 |
| L2009 | 1.000 | 1.000 |
| L2105 | 1.000 | 0.336 |
| L2208 | 1.000 | 1.000 |
| L2307 | 1.000 | 0.637 |

## Datum rule (stage 1, before any prediction)

A spot or upstream gauge whose training-period index median lies outside -0.5 to 1.5 is dropped.

| Gauge | Role | Spot gauge | Median | 5th pct | 95th pct | Issue times | Why |
|---|---|---|---|---|---|---|---|
| 1090TH | trib | 1100TH | 1.536 | 0.877 | 2.230 | 1354 | training-period index median outside the rule |

## C1 against R3 (population P, 3 h, d = 1 h)

- 1. Brier skill 0.0199, 95% interval -0.1849 to 0.0723 (13 river systems): fails.
- 2. Skill above 0 in 6 of 9 river systems with 5+ episodes (needs 6): holds.
- 3. At 0.5: hit rate 0.106, false-alarm ratio 0.608: fails.
- 4. Median lead gained 1.00 h on 100 of 677 onsets caught: holds.
- 5. With d = 3 h, skill -0.0617: fails.
- 6. Placebo: real gain 0.00012, 95th percentile of 200 shifts 0.00002: holds.

**Verdict: Fails.** Near-miss label (B 0.0200, H 0.0100): **Too uncertain**.

Secondary comparisons (own bootstrap, same B and H): P3d3 skill -0.0617 [-0.1459, -0.0059], Possible harm; A3d1 skill 0.0436 [-0.0553, 0.0800], Too uncertain. At 6 h: skill 0.0651 [-0.0516, 0.1108].

## C2 against C1 (population P, 3 h, d = 1 h)

- 1. Brier skill 0.0415, 95% interval 0.0017 to 0.0826 (13 river systems): fails.
- 2. Skill above 0 in 7 of 9 river systems with 5+ episodes (needs 6): holds.
- 3. At 0.5: hit rate 0.115, false-alarm ratio 0.578: fails.
- 4. Median lead gained 1.00 h on 99 of 677 onsets caught: holds.
- 5. With d = 3 h, skill 0.0308: holds.
- 6. Placebo: real gain 0.00024, 95th percentile of 200 shifts 0.00001: holds.

**Verdict: Fails.** Near-miss label (B 0.0200, H 0.0100): **Better**.

Secondary comparisons (own bootstrap, same B and H): P3d3 skill 0.0308 [-0.0053, 0.0853], Promising, not shown; A3d1 skill 0.0292 [-0.0031, 0.0641], Promising, not shown. At 6 h: skill 0.0335 [-0.0008, 0.0643].

## By upstream gauge kind (reported apart; the conditions above are pooled)

| Kind | Spot gauges | Rows with a label | Events | C1 skill vs R3 | C2 skill vs C1 |
|---|---|---|---|---|---|
| same river | 26 | 225304 | 1173 | -0.0087 | 0.0434 |
| tributary only | 7 | 59544 | 494 | 0.0906 | 0.0363 |

## Pooled scores

| Config | Model | Brier | Skill vs R3 | Skill vs R1 | AUC | Hit rate | False-alarm ratio |
|---|---|---|---|---|---|---|---|
| P3d1 | R1 | 0.00567 | 0.0350 | 0.0000 | 0.815 | 0.000 | n/a |
| P3d1 | R3 | 0.00588 | 0.0000 | -0.0363 | 0.574 | 0.001 | 0.970 |
| P3d1 | C1 | 0.00576 | 0.0199 | -0.0156 | 0.637 | 0.106 | 0.608 |
| P3d1 | C2 | 0.00552 | 0.0606 | 0.0266 | 0.682 | 0.115 | 0.578 |
| P6d1 | R1 | 0.01367 | 0.0505 | 0.0000 | 0.787 | 0.000 | n/a |
| P6d1 | R3 | 0.01440 | 0.0000 | -0.0532 | 0.577 | 0.002 | 0.905 |
| P6d1 | C1 | 0.01346 | 0.0651 | 0.0154 | 0.656 | 0.118 | 0.507 |
| P6d1 | C2 | 0.01301 | 0.0964 | 0.0483 | 0.717 | 0.147 | 0.515 |
| P3d3 | R1 | 0.00590 | 0.0299 | 0.0000 | 0.810 | 0.000 | n/a |
| P3d3 | R3 | 0.00608 | 0.0000 | -0.0308 | 0.480 | 0.001 | 0.875 |
| P3d3 | C1 | 0.00646 | -0.0617 | -0.0944 | 0.566 | 0.029 | 0.833 |
| P3d3 | C2 | 0.00626 | -0.0290 | -0.0608 | 0.687 | 0.051 | 0.789 |
| A3d1 | R1 | 0.00588 | 0.0527 | 0.0000 | 0.801 | 0.000 | n/a |
| A3d1 | R2 | 0.00602 | 0.0302 | -0.0238 | 0.403 | 0.000 | n/a |
| A3d1 | R3 | 0.00621 | 0.0000 | -0.0557 | 0.546 | 0.004 | 0.927 |
| A3d1 | C1 | 0.00594 | 0.0436 | -0.0097 | 0.646 | 0.089 | 0.626 |
| A3d1 | C2 | 0.00577 | 0.0715 | 0.0198 | 0.694 | 0.099 | 0.591 |

By river system, by spot gauge and reliability: result.json.

Whatever the result, nothing on the site changes because of this test.
