# Recalibrating the live spill forecast: a proposed test, not yet approved

Written 26 October 2026. **A draft for Ethan to review. It is not an approval and nothing in it runs.** Ethan approves
it by merging the PR that carries it, or by saying so in writing in that PR. He may change any choice in it before he
approves. After approval, the statement above the line is fixed. Results would go below the line at the end, and
nothing above that line would change after a result is seen. Changes after approval and before the fit are dated
addenda, as in the other tests.

This file runs nothing. No correction is fitted, no score is computed, no data is fetched and no Open-Meteo call is
made. No acceptance rule in any other record changes.

## Why

Two diagnostic reads of the live record, 29 September to 23 October 2026, found the spill forecast's chances run too
high and too spread out:
- `docs/INTERIM-USEFULNESS-2026-10.md` (PR #338): the forecast ranks spill days well but barely beats simple rules on
  the Brier score.
- `docs/CALIBRATION-CHECK-2026-10.md` (PR #340): observed over expected (O/E) 0.74 same day and 0.80 in advance;
  logistic slope 0.74. Uneven by company.

#340 said any recalibration "needs its own stated test on data it was not fitted to". This is a proposal for that
test. It asks one question: does a simple correction, fitted on the live record to early December and frozen, beat
the production forecast on twelve later weeks it never saw?

## Seen before writing

Everything below was read before any choice in this file was made. None of it may be used to judge a candidate. The
October rows may be used to fit one (see "Fitting").

**From #338 and #340, both read in full, every table.** Not opened: their JSON files, `verification_live.csv`, the
forecast log, the `state` release. The figures that shaped this proposal:

| All companies, 29 Sep to 23 Oct | Same day (lead 0) | In advance (leads 1–4) |
|---|---|---|
| Mean forecast, observed rate | 0.063, 0.047 | 0.059, 0.047 |
| O/E (95% interval) | 0.74 (0.65 to 0.87) | 0.80 (0.62 to 0.91) |
| Slope b (95% interval) | 0.74 (0.63 to 0.81) | 0.74 (0.60 to 0.80) |
| Brier | 0.0390 | 0.0397 |
| Reliability (calibration loss), seven bands | 0.0023 | 0.0015 |
| Resolution | 0.0075 | 0.0064 |
| AUC (#338, common rows) | 0.88 | 0.84 |
| Skill against the best simple reference (#338) | −0.05 (−0.19 to 0.12) | 0.07 (−0.05 to 0.12) |

- **By band, same day:** below 0.01 the forecast is slightly too low (0.003 against 0.006). From 0.07 up the observed
  rate is 30% to 38% below the mean forecast in every band (0.249 against 0.154 in 0.15–0.40; 0.527 against 0.363 in
  0.40–0.70; 0.785 against 0.548 at 0.70 or more). High warnings (0.40 and up) came true 388 times in 963 (40%).
- **By company (#340's rule):** too high on average at Thames (O/E 0.38 same day), Wessex (0.66), Southern (0.64) and
  United Utilities (0.66, same day only). Too extreme, not too high, at Anglian (1.12) and Yorkshire (1.14 in
  advance). No clear evidence at Severn Trent and South West. Northumbrian not judged (16 spill overflow-days).
- **By block:** O/E below 1 in all four 7-day blocks, same day (0.87, 0.67, 0.79, 0.71) and in advance. The last block
  (20–23 Oct, four days) holds 54% of the spill overflow-days.
- **By lead:** O/E 0.69 at lead 1, 0.74 at 2, 0.83 at 3, 0.99 at 4. Slope 0.68 to 0.81 at every lead.
- **#338's limits:** persistence and the rain rule were fitted on the rows they were scored on, which flatters them.
  #340 found #338's persistence ("spilling now or in the last 48 hours") is a stronger rule than "spilling now", and
  that hindsight in its rebuild moves a spilling-now reference very little.

**From other records, read for step 1 below:**
- `docs/LIVE-RECALIBRATION-TEST-2026-10.md`: on 12 days (29 Sep to 12 Oct), leave one day out, company intercepts with
  a common slope (its candidate B) cut the held-out Brier by 4.3%, isotonic (A) by 2.8%. Both failed a 5% bar. B helped
  Southern and Thames a lot and made Severn Trent and United Utilities slightly worse.
- `docs/LEAD-CALIBRATION-B-TEST-2026-10.md`: on 2025's EA files every company's forecast was too low. On the live rows
  of 29 Sep to 16 Oct, too high at six of nine. Its secondary check, by company and bin, on those rows.
- `docs/COMPANY-CALIBRATION-TEST-2026-11.md` (A8): the frozen offsets and their per-company inputs (n, e) and mean
  moves (0% to −4.5%), and amendments 1 and 2.
- `docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md` with its addendum P1, `docs/LIVE-STATUS-SHADOW-TEST-2026-10.md`,
  `docs/ENSEMBLE-RAIN-TEST-2026-11.md`, `docs/PREREGISTRATION-2027.md` (sections 1, 2, 7 to 12, 15 to 17 and the
  first lines of amendments 1 to 3), `docs/NOISE-AUDIT-2026-10.md`, and the near-miss addendum at the end of
  `docs/LAKE-ECOLI-LINE-TEST-2026-10.md`.
- **Code:** `model/forecast.py` (`calibrate_by_lead`, and where the calibrated chance `p` feeds `risk` and the E. coli
  features), the head of `model/ecoli.py`, and `forecast_log.SCORED_COLUMNS`.

## Step 1: the plans already running, and how this avoids them

| Plan | What it tests | Rows and window | Read | How this proposal avoids it |
|---|---|---|---|---|
| Lead calibration B (`LEAD-CALIBRATION-B-TEST-2026-10.md`) | A per-lead isotonic map fitted on 2025 EA labels outside United Utilities, replacing `lead_calibration.json` | Scored live rows, target days 18 Oct to 14 Nov 2026; 14-day extension once, to 28 Nov | On or after 16 Nov (about 30 Nov if extended; its file gives no extended read date) | Same layer (after the model), different labels. This proposal deploys nothing before its read, and its window starts after it. If B's map is adopted, this correction is fitted on top of it (see "If production changes before the fit"). |
| Company calibration A8 (`COMPANY-CALIBRATION-TEST-2026-11.md`) | Per-overflow offsets outside United Utilities, fitted on lead-0 live rows to 23 Oct | Target days 26 Oct to 22 Nov, issued after 24 Oct 21:31:41 UTC; extension to 6 Dec | On or after 25 Nov (9 Dec if extended) | A8 corrects each overflow's level. This corrects the chances' spread and the overall level, pooled (R2) or by company (R3), never by overflow. Fitting reads A8's window rows but changes no forecast in it. Window starts after A8's latest read. |
| Live-status shadow (`LIVE-STATUS-SHADOW-TEST-2026-10.md`) | #254's status inputs as a model input, logged as `p_status` | Target days 25 Oct to 21 Nov; extension to 5 Dec | On or after 23 Nov (7 Dec if extended) | Different input. Nothing here touches `p_cal` or `p_status` before its read. If it is switched on at some lead, see "If production changes before the fit". |
| Live recalibration (`LIVE-RECALIBRATION-TEST-2026-10.md`) | Isotonic (A) and company intercepts with a common slope (B), leave one day out | 29 Sep to 12 Oct, retrospective | Done, 11 and 13 Oct: neither passed | This is its prospective successor. R3 is close to its B, refitted per lead on far more days and judged on unseen weeks. Its record is not reopened: it said "re-run with the same rule"; this is a new statement on new data, which the noise audit asks for. |
| Option B and P1 (`UPGRADED-OVERFLOWS-TEST-B-2026-10.md`) | Layer 2 offsets for every company, each from a start date; reported arm P1 | Window E: EA file, 1 Jan to 31 Aug 2026, lead 0. Window L: live rows 29 Sep to 30 Nov 2026 | Runs on or after 2 Dec 2026. If it passes: a 28-day shadow about late January to late February 2027, adoption by 31 Mar 2027 | Window L is over before this window opens, so nothing deployed here can touch it. Option B rebuilds its arms from `p_raw` and the row's map, so a correction after the map would break its pairing if deployed inside window L or its shadow. Neither happens: the earliest switch-on here is 10 Mar 2027. If option B is adopted, it goes first (see "What follows"). |
| 2027 pre-registration and amendments 1–3 (`PREREGISTRATION-2027.md`) | The frozen model's May to September 2027 forecasts against climatology; spot-level scores S1, S2; soil moisture in river E. coli | Season 1 May to 30 Sep 2027; tag by 30 Apr 2027 | 31 Oct 2027 | Any adopted correction must be in the tagged model, so in `MODEL_PATHS` and the version stamp, by an amendment before 30 Apr. Or it stays out and is scored as a labelled secondary. Ethan's choice, below. |
| Noise audit (`NOISE-AUDIT-2026-10.md`) | Which verdicts rested on point rules; the rule for new statements | A record | — | Followed: pooled gain with an interval, per-company "not clearly worse" with a margin, ECE with a margin, cluster bootstrap with a fixed seed, AUC and log loss reported. |
| Near-miss framework (end of `LAKE-ECOLI-LINE-TEST-2026-10.md`) | Labels (better, promising, no useful difference, possible harm, harm, too uncertain), margins B and H, forward step, power | A record | — | Its labels are reported for the primary comparison. B and H are set below, before any data. Its power rule (spread from other data) sets the window's check. |
| Ensemble rain D4 (`ENSEMBLE-RAIN-TEST-2026-11.md`) | Members' spread; whether the members' mean beats the single forecast at leads 2–4 | Target days 23 Oct to 19 Nov; extension to 3 Dec | On or after 21 Nov (5 Dec if extended) | If it passes, the headline at leads 2–4 becomes the members' mean. That would change production before this fit, which is handled below. Nothing here touches the members. |

**The dates this sets.**
- **No correction from this proposal may be deployed before 9 December 2026**, the latest possible read of the
  windows above (A8 extended). Option B's run (on or after 2 Dec) must also be in.
- In practice nothing deploys before this test's own read: **9 March 2027** at the earliest.
- **No switch-on during option B's shadow** if it runs. Its expected dates (late January to late February 2027) end
  before 9 March, so this holds unless option B slips.
- **The window opens on 14 December 2026**, after every read above, extensions included.

Reading the other windows' rows to fit this correction does not touch them. Fitting changes no forecast they score.
Only deployment could, and none happens before their reads.

## The candidates (fixed now)

Each candidate is a fixed transformation of the chance the site already publishes, `forecast_calibrated` (p below).
It sits after the lead map. The spill model and the lead map are unchanged.

With q = logit(clip(p, 0.0001, 0.9999)) and lead k clamped to 0–4, as `calibrate_by_lead` clamps:

- **R1, level only (reported, never adopted).** p' = σ(a_k + q). Five numbers, one per lead.
- **R2, level and spread, pooled (candidate).** p' = σ(a_k + b_k × q). Ten numbers, an intercept and a slope per lead.
- **R3, R2 plus a company term (candidate).** p' = σ(a_k + b_k × q + c_company). Ten numbers plus one per company
  (nine). A row with no company in the file gets c = 0.

**Why these three.**
- *R2 is the pattern October showed most clearly.* The slope was below 1 at every lead and O/E below 1 in every block.
  Most of the calibration loss sits in the upper bands, which a level shift alone cannot fix: the bands from 0.15 up
  are about 95% of #340's same-day reliability term, by the published band table.
- *Per lead,* because O/E rose with lead (0.69 at lead 1 to 0.99 at lead 4). Each lead is fitted on its own rows, so
  no overflow-day counts twice in a fit.
- *R3,* because the bias is uneven by company: Thames O/E 0.38, Anglian 1.12. A pooled shift lowers Anglian's and
  Yorkshire's chances too, where October did not show them too high on average. R3 is close to live recalibration's
  candidate B, the one that came nearest to passing (4.3% against a 5% bar).
- *R1 is reported only.* It shows how much of any gain is the level alone, to read R2 by.

**Not chosen, and why.**
- *Isotonic.* Live recalibration's A lost AUC beyond its 0.005 bar and gained less than B. It also has many more
  free steps than ten numbers.
- *A slope per company.* Northumbrian had 16 spill overflow-days in October and South West 61. A slope needs more.
- *Per-overflow offsets.* A8 and option B test those. Testing them here too would duplicate them.
- *Refitting the spill model.* The nine-company tests and option B own that question.
- *A rolling refit.* The correction would change every week, so no window could judge a fixed candidate, and it
  would break the 2027 freeze. Worth a statement of its own after the 2027 season.
- *Moving the 0.40 High line.* A product decision, not a calibration. See "Warnings" below.

## Fitting

- **Rows.** The published `data/verification_live.csv`, downloaded on the fit date, every scored row with target day
  **29 September to 6 December 2026** (69 days, about ten weeks). Leads 0 to 4. Its SHA-256 goes under the line.
- **Fit date: on or after Thursday 10 December 2026**, after A8's latest possible read. The parameters are committed
  with their SHA-256 and the commit time. That time is the **freeze**.
- **Method.** Maximum-likelihood logistic regression of `observed` on q, per lead, as above.
  - R1 and R2: no penalty. Each lead has some 20,000 rows or more.
  - R3: the same, with a normal prior of standard deviation 1.0 on each company term (an L2 penalty). This only bites
    where a company has few spills, such as Northumbrian. An SD of 1.0 allows odds ratios from about 0.14 to 7.4
    within two SDs, so October's range (Thames to Anglian) is well inside it. Nothing is tuned.
- **If production changes before the fit.** If lead calibration B's map, the live-status inputs, the ensemble mean or
  A8's offsets are adopted before 10 December, every fitting row is first rebuilt as the forecast production would
  then have published. The rebuild uses the logged columns each of those tests' own harness uses (`forecast_raw` and
  the map; `p_status`; `p_cal_members`; the A8 offsets). The exact rebuild is written as a dated addendum before the
  fit, with nothing scored. Rows that cannot be rebuilt are dropped and counted. If more than 25% are dropped, the fit
  waits for a new statement.
- **Before the window: the power check** (see "Margins and power"). Computed on the fitting rows only.
- **No score of any candidate on the fitting rows is reported** except that power check, which is labelled as such.

## The evaluation window

- **Target days Monday 14 December 2026 to Sunday 7 March 2027.** Twelve whole ISO weeks.
- **Read on or after Tuesday 9 March 2027**, from the file published then.
- **Only forecasts issued after the freeze count**, as A8's amendment 1 set: a row whose `issued_at` is at or before
  the freeze is dropped and counted.
- **Rows.** Every scored row of `verification_live.csv` in the window, leads 0 to 4, as `forecast_log.verify_live`
  selects and labels them. Labels are the poll-based live labels (PR #253's method).
- **Production** is `forecast_calibrated` as published. **The candidates** are computed from it, row by row, with the
  frozen parameters. Nothing is deployed. The comparison is paired and prospective because the window is in the
  future.
- **If production changes in the window.** The check reads each row's `spill=` and `cal=` stamp from the forecast
  log. If a row in the window carries a stamp other than the one at the freeze, or the headline rule changes (for
  example the ensemble mean), the window ends the day before. If that leaves fewer than eight weeks, the test stops
  and a new statement is needed.
- **Minimum data.** At least 800 spill overflow-days at lead 0, all companies. If short, the window extends by four
  weeks once, to Sunday 4 April 2027, read on or after 6 April. Still short: description only, nothing adopted.
- **Sanity check, first.** p rebuilt from the log matches the published `forecast_calibrated` (mean absolute
  difference under 0.0001). Otherwise the check stops and reports.

## References

Scored on the same rows as the candidates.
1. **Production, unrefit: the primary comparator.** `forecast_calibrated` as published.
2. **Long-run rate.** The `climatology` column, as the Accuracy page uses it.
3. **Persistence**, as #338 defined it: active if spilling at issue or in the 48 hours before, from the poll files,
   with known status only. Where the shadow logged `spilling_at_issue`, that is used for "spilling at issue", as
   #338's draft amendment proposed. Two versions: fitted on the fitting rows (fair), and fitted on the window rows
   (#338's way, flattering).
4. **The rain rule**, as #338 defined it: 48-hour forecast rain from the log, above 10 mm and above 5 mm. The same two
   versions.

Only the comparison with production decides. The others are reported.

## Metrics

- **Primary: the Brier score**, all window rows, leads 0 to 4 pooled, all companies. The comparison is the relative
  gain g = 1 − Brier(candidate) ÷ Brier(production). Above 0 means the candidate is better.
- **Reported:** g by lead (0, 1–4, and each lead); the Murphy decomposition over #340's seven bands (reliability and
  resolution); O/E and the slope b with intervals, as #340 computed them; log loss (clip 0.0001 to 0.9999); AUC by
  lead and pooled; ECE (`training.ece`, ten equal bins); the warning table at the 0.40 line.
- R1, and R2 where its slope is above 0, change nothing within a lead's ranking, so their AUC by lead equals
  production's. Pooled over leads, and for R3, it can differ. A fitted slope at or below 0 at any lead is reported
  under the line before the window opens, and that candidate is withdrawn.

## Uncertainty

- **Two-way cluster bootstrap**, as the 2027 protocol (section 10), option B and A8's amendment 2: each draw
  resamples overflows and, independently, ISO weeks of the target day, with replacement. A row counts (times its
  overflow was drawn) × (times its week was drawn). All leads of an overflow-day share both draws.
- **2,000 draws from `numpy.random.default_rng(20261214)`**, made once, overflows first, then weeks. Every candidate,
  company, lead and reference uses the same draws. The fitted parameters stay fixed in every draw.
- **Intervals.** The two candidates are judged against production with **97.5% intervals** (1.25th to 98.75th
  percentiles), because two candidates are tested. Everything else, guardrails included, uses 95%.
- The week-only interval is reported beside it. Twelve week clusters are still few. Three times #340's four.

## Margins and power

**Expected effect, from published figures only (inferred, not measured).**
- *Ceiling.* If the window were miscalibrated as October was, a perfect recalibration would remove at most the
  reliability term: 0.0023 of 0.0390 same day (5.9%) and 0.0015 of 0.0397 in advance (3.8%). A correction fitted on
  other weeks removes less.
- *Out-of-sample analogue.* Live recalibration's B, held out by day on 12 autumn days: −4.3%. Its A: −2.8%.
- *So,* if winter keeps autumn's bias, R2 gains about 1% to 4% and R3 a little more. If the bias was autumnal, the gain
  could be nil or negative. 2025's EA labels showed the forecast too low at all nine companies, so the direction is
  not settled. That is what the test measures.

**The margins, set now.**
- **B, the benefit margin: g ≥ 1%.** 1% is the house margin (A8 amendment 2, option B, noise audit). It is between a
  quarter and the whole of the expected gain above. In October's terms it is about 0.0004 of Brier, a sixth of the
  same-day calibration loss.
- **δ, the non-inferiority margin (H in the near-miss framework): 1% of production's Brier.** δ ≤ B, as the framework
  requires. *Why 1%:* it is the largest loss the house tests have accepted as noise, pooled. A candidate that loses
  more than that on Brier is not adopted for any calibration gain.
- **The per-company margin: 2%.** See the guardrails.

**Interval width for twelve weeks (inferred).** The week clusters dominate the width for a pooled correction, because
one storm moves every overflow's error together. Let G be the true mean gain per week and s its spread across weeks,
s = k × G. With 12 week clusters, a 97.5% interval and 80% power, the near-miss framework's rule gives

    weeks needed ≈ ((2.24 + 0.84) × k)² = 9.5 × k²

So twelve weeks show the true gain 80% of the time if k ≤ 1.12: the weekly gains vary by no more than about their own
size. Sixteen weeks allow k ≤ 1.30. The overflow clusters widen this a little more. October's weekly O/E was below 1
in all four blocks, which suggests k near 1, not much below. No finished test gives the weekly spread of a
recalibration gain on live rows, so k is not known now.

**The binding check, at the fit, before the window opens.** On the fitting rows only: fit R2 leaving out one ISO week
at a time, and score each left-out week's gain. Their mean and spread give k. Written under the line before
14 December, with the window's power at 97.5% for a gain equal to that mean. These are fitting rows, not the rows being
judged, as the framework requires.
- If power is at least 80%: the window stays at twelve weeks.
- If below: an addendum before 14 December may lengthen the window to sixteen weeks (to 4 April 2027, read on or
  after 6 April). That leaves no time for the staged switch-on before the 2027 tag, so the result would serve the 2027
  secondary score and later seasons (see "What follows"). Ethan chooses. The window length is never changed after
  14 December.
- If the leave-one-week-out gain is negative on the fitting rows, that is reported, and the test still runs as stated.

## Decision rules (fixed now)

Each candidate, R2 and R3, is judged against production by the same rules. A candidate **qualifies** by route 1 or
route 2, and only if every guardrail holds.

**Route 1: adopt for a clear gain.** g ≥ 1% (B), and g's 97.5% interval lies wholly above 0.

**Route 2: adopt for no harm with a likely gain (non-inferiority).** All three:
- g > 0 (the point estimate favours the candidate);
- g's 97.5% interval lies wholly above −1% (−δ): shown no worse than δ;
- the calibration gain is shown: production's reliability term minus the candidate's, over #340's seven bands, has a
  95% interval wholly above 0.

*Why route 2 exists, and why it is not a back door.* The site shows each overflow's figure as a chance, and the pages
say what a chance means. A forecast whose 50% comes true 36% of the time misleads, even if its Brier score is no
worse. Route 2 adopts a correction only where that is shown to be fixed, at a shown cost below δ, with a positive point
estimate. It is fixed before any window row exists, and it is not a fallback chosen after route 1 fails: both routes
are in the rule from the start. It cannot rescue a candidate that is worse on Brier.

**Otherwise: hold.** Nothing changes. This file is the record.

**Guardrails, all required, for either route.** "Judged companies" are those with at least 50 spill overflow-days at
lead 0 in the window.
- **G1, no company clearly worse.** At each judged company, the 95% interval of Brier(candidate) − Brier(production)
  does not lie wholly above 0, and Brier(candidate) is at most 2% above Brier(production). *Why 2%, not the house 1%:*
  a company cell has roughly a ninth of the rows, so its point estimate is noisier. Over nine companies, small chances
  of a false fail add up (the noise audit's worked example: 2.5% each gives about 20%). The interval part still
  blocks clear harm of any size.
- **G2, calibration by company.** At each judged company, ECE(candidate) ≤ ECE(production) + 0.005, the margin the
  noise audit proposes.
- **G3, ranking.** Pooled AUC, and AUC at each lead, not lower than production's by more than 0.005. Binds R3 only.
- **G4, warnings.** At the 0.40 line, leads pooled: the share of warnings that came true is not clearly lower: the 95%
  interval of candidate minus production does not lie wholly below 0. See "Warnings".

**If both qualify,** R2 is chosen unless R3 beats R2 clearly: the 97.5% interval of 1 − Brier(R3) ÷ Brier(R2) lies
wholly above 0. The simpler candidate wins a tie.

**Labels, reported, not deciding.** For R2 and R3 against production, the near-miss framework's labels with B = 1% and
H = 1%. A "promising, not shown" result is not adopted, and it is not stacked with another window to make a pass.

### Warnings

A correction like October's would lower the chances at the top. **Inferred from #340's published bands, not
measured:** with October's same-day slope (0.74), and an intercept that puts the 0.40–0.70 band's mean forecast
(0.527) on its observed rate (0.363), a forecast of 0.40 becomes about 0.28, and the High line would be crossed only
from about 0.58. Same day, that cuts the High warnings roughly in half, and the share of spill
overflow-days warned from about 35% (388 of 1,105) to perhaps 20% to 25%. The warnings that remain would come true
more often.

That is what a calibrated forecast does at a fixed line, and it is a choice about the product. This draft takes the
view that the 0.40 line means "a 40% chance" and should keep that meaning, so G4 guards only the share of warnings that
come true. The fall in the share of spills warned is reported in full. **Ethan decides this before approving** (see the
list at the end). If he wants the warning count held, the right test is a separate one of the line, not a looser rule
here.

## What follows

**A candidate qualifies.** Three stages, each its own PR and Ethan's call.

1. **Stage A, shadow.** May start any time after the freeze, since it only logs. `forecast_overflows` gains
   `p_recal`, the chosen candidate's chance. Nothing published reads it. It changes no `p_cal`, member or `p_status`,
   so it disturbs no window. Before stage B, on every window row, the logged `p_recal` must equal the harness's value
   within 1e-6. Logging alone judges nothing: the offline window already did.
2. **Stage B, switch-on with a stop rule. 10 March to 6 April 2027 (28 days).** The site shows the corrected chances
   on the map, the spot pages, the API and the Accuracy page. The uncorrected chance is still logged, so the paired
   comparison continues. A script checks each Monday, on the rows since switch-on. **Stop rule:** switch off the same
   day, by a config flag, if any of these holds:
   - the 95% interval of Brier(corrected) − Brier(uncorrected), pooled, lies wholly above 0;
   - a judged company fails G1;
   - a technical fault: a corrected value missing where production had one, or differing from the harness by more
     than 1e-6.

   This is a safety stop, not a second test. Weekly looks raise the chance of a false stop, which is the safe
   direction.
3. **Stage C, kept.** If stage B ends without a stop, the correction stays. Its 2027 status is decided by
   8 April 2027 (below).

**The E. coli estimate keeps the uncorrected input.** `model/forecast.py` feeds the calibrated chance `p` into the
spot's `risk`, and `risk` into the E. coli features. The E. coli models were fitted on the uncorrected chance. So the
switch-on keeps a second, uncorrected `risk` for E. coli. Changing that is a separate test.

**The 2027 season.** The correction is fitted on autumn and judged on winter. It would be used in May to September,
which neither covers. Two options, both scoring both forecasts in 2027, since the correction is a fixed function of
the logged chance:
- **(a) Into the frozen model.** An amendment to section 2 adds the correction file to `MODEL_PATHS` and the stamp,
  merged by 30 April 2027. The uncorrected forecast is scored as a secondary.
- **(b) Out of the frozen model.** The tag carries the uncorrected forecast. An amendment registers the frozen
  correction as a labelled secondary, scored on the 2027 rows. The live site may still show the corrected chances,
  which then is a candidate under section 12. Ethan decides which.

**Option B goes first.** If option B passes its shadow and is adopted (by 31 March 2027), it changes `p_raw` for every
company. This correction was fitted on forecasts before that. It is then not switched on, or is switched off, and a
refit needs a new statement. The same holds if `annual_returns.parquet` is refreshed before the tag (the mid-April
decision in section 15), since that moves layer 1's inputs for every overflow.

**No candidate qualifies.** Nothing changes. The record stands. Any re-test is a new statement on new data.

## What is not tested

- **Summer.** No May to September day is in the fitting rows or the window.
- **Spot levels and alerts.** Only overflow-days are scored. Spot levels move with the corrected chances, and stage A
  counts how many levels and alerts would change. The 2027 S1 and S2 scores cover spot levels.
- **The E. coli estimate.** It keeps the uncorrected input.
- **Why the chances run high.** A correction treats the symptom. The causes (labels against EDM files, autumn rain,
  the model's month factors fitted on May to September) are for other tests.
- **Per overflow.** A8 and option B.
- **The fitting rows' own score.** Never reported, except the labelled power check.

## What would stop the study

- Ethan does not approve before 10 December 2026. The dates then move by addendum before any fit, or the proposal
  lapses.
- A production change in the window leaving fewer than eight weeks.
- More than 25% of fitting rows cannot be rebuilt after a production change.
- The sanity check fails (published and rebuilt production differ).
- Fewer than 800 lead-0 spill overflow-days after the one extension: description only.
- The forecast log or the published file is lost or rewritten for window days: the analysis runs on what exists, says
  where and why, and adopts nothing.
- A change to the live labelling rule (`verify_live`'s coverage rules) inside the window: the window ends the day
  before, with the eight-week minimum as above.

## Order of work, after approval

1. Ethan approves this statement. Nothing below runs before.
2. The harness (`scripts/calibration_test/`, with tests) is committed. It changes nothing above the line.
3. On or after 10 December 2026: download the published file and the `state` release read-only, record their hashes,
   fit R1 to R3, commit the parameters with their SHA-256 (the freeze), and write the power check under the line.
   No Open-Meteo call; one light run under `heavy-run.lock` if other sessions use it.
4. On or after 9 March 2027: run the check once and write the result under the line.
5. If a candidate qualifies: stages A to C, each its own PR.

## Decisions for Ethan before approval

1. **The candidate set:** R2 and R3 judged, R1 reported. Or a single candidate.
2. **δ and B:** both 1% of production's Brier.
3. **The per-company margin:** 2% (this draft) or the house 1%.
4. **The windows:** fitting rows 29 Sep to 6 Dec 2026, fit on or after 10 Dec; window 14 Dec 2026 to 7 Mar 2027,
   read on or after 9 Mar. Sixteen weeks instead, if the power check falls short.
5. **Warnings:** keep the 0.40 line's meaning and accept fewer High warnings (this draft), or hold the warning count,
   which needs a separate test of the line.
6. **The 2027 season:** option (a) or (b) above.
7. **Order with option B and A8:** this draft has option B take precedence, and A8 not deployed inside this window.

---

## Results

Not run. Nothing below this line until the fit.
