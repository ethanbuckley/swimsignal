# Company calibration (review task A8): the test, stated before any fit

Written 24 October 2026. It is committed and pushed before two things:
- any per-overflow offset is fitted;
- any row of the published scored live forecasts (`data/verification_live.csv`) is read.

Results go below the line at the end. Nothing above that line changes after a result is seen. Review task A8
(`docs/REVIEW-2026-10-16.md`).

## Why

Layer 2 of the spill model (`src/dipcast/model/spill_model.py`, `fit_site_offsets`) gives each overflow a
log-odds offset, log((n + 15) / (e + 15)). Here n is the overflow's observed spill-days, e the spill-days layer 1
expected on the same days, and 15 the prior's pseudo spill-days (`PRIOR_STRENGTH`). Production's offsets are all
United Utilities overflows. Every other company's overflows have an offset of 0, so they get layer 1 alone.

The live record now holds about four weeks of observed spill-days for the other eight companies. The review asked
whether those days, fitted into layer 2 the same way, improve the next four weeks.

## Seen before writing

- **Two failed live corrections** (`docs/LIVE-RECALIBRATION-TEST-2026-10.md`). Company intercepts (its candidate
  B) brought Southern's Brier from 0.0091 to 0.0030 and Thames's from 0.0051 to 0.0023, but made Severn Trent and
  United Utilities slightly worse. Pooled, they missed the 5% bar (4.3%). The lesson taken here: a correction that
  helps the two driest companies can hurt the others, so this test decides company by company.
- **Lead calibration B's secondary check** (`docs/LEAD-CALIBRATION-B-TEST-2026-10.md`), scored live rows 29 Sep to
  16 Oct. Per company: rows, spill rows, observed rate, mean calibrated forecast and Brier of today's forecast.
  The mean forecast was above the observed rate at Severn Trent, South West, Southern, Thames and Wessex, and below
  it at Anglian, Northumbrian and Yorkshire.
- **The task's brief:** on 24 Oct, 26% of spill forecasts outside United Utilities were warned, up from 2% on
  20 Oct after one wet week.
- **Option B's statement** (`docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md`) in full, and lead calibration B's in
  full.
- **Code:** `spill_model.py` in full; in `forecast_log.py` the module notes, `observed_spill_days`,
  `select_decision_forecasts`, `verify_live` and `scored_rows`; `forecast.calibrate_by_lead`, `_apply` and
  `model_version`; `scripts/lead_calibration_b_check.py` in full.
- **The published file's size** from a HEAD request: 9,726,357 bytes, last modified 24 Oct 2026 19:43 UTC.

Not opened: `data/verification_live.csv`, `verification.json`, the forecast log, the `state` release. No offset has
been fitted.

## The candidate

**Model.** Production's layer 1 and lead calibration map, unchanged. Only offsets are added.

**Which overflows.** Every overflow of the eight English companies other than United Utilities that has at least
one fitting row (below). United Utilities' offsets stay production's. An overflow with no fitting row keeps 0.

**Fitting rows.** `data/verification_live.csv` as published when the fit runs, downloaded after this file is pushed,
with its SHA-256 recorded under the line. Of its rows, those with:
- `company` not United Utilities;
- `lead` 0;
- `day` (the target day) on or before 25 Oct 2026. The file cannot hold a later day yet. This rule keeps every
  fitting day before the window.

These are the live labels `forecast_log.verify_live` gives: `observed` is 1 if `observed_spill_days` found a
discharge that touched the local day, and a 0 counts only on a covered day (at least 6 known polls, no gap over
8 hours, the feed current, seen again the next day). Rows with no rain data are already out.

**n and e.** For each overflow, n is the sum of `observed` over its fitting rows. e is the sum of `forecast_raw`
over the same rows, clipped to [0.0001, 0.9999] as `predict_pooled` clips. `forecast_raw` is `SpillModel.predict`,
the model's chance before the lead map. Outside United Utilities it is layer 1 alone, because those overflows have
no offset.

*Why lead 0 only.* Each overflow-day then counts once, so 15 pseudo spill-days mean what they mean in production.
Lead 0 is the forecast made by 08:00 on the day, the closest the log has to the day's real rain.

*Why the logged forecast and not an ERA5 hindcast.* The offset will correct forecasts made from forecast rain. Fitting
on the logged forecast lets it absorb that rain forecast's bias at the overflow too. It also needs no rain fetch. The
cost: an offset fitted this way carries some of these four weeks' rain forecast errors. The prior limits that.

**The prior.** Prior mean ratio 1 (the pooled model), strength 15 pseudo spill-days, recency 1. Exactly as
`fit_site_offsets` does for United Utilities. Nothing is tuned.

**The offset.** ln((n + 15) / (e + 15)), keyed by `overflow_id`.

**Saved as** `docs/COMPANY-CALIBRATION-TEST-2026-11-offsets.json`: the source file's SHA-256 and first and last
fitting day, the prior, and per overflow its company, offset, n, e and fitting days. Its own SHA-256 goes under the
line, with the fitted spill model's version stamp read from the forecast log.

## The forecast to score

For a scored row with `forecast_raw` p, lead k and overflow i:

    candidate = map_k( 1 / (1 + exp(-(logit(clip(p, 0.0001, 0.9999)) + offset_i))) )

`map_k` is the lead map that made that row's `forecast_calibrated`, with the lead clamped to 0 to 4 as
`forecast.calibrate_by_lead` does. It is found per issue day (the local date of `issued_at`): each map on hand is
applied to that day's `forecast_raw`, and the one whose mean absolute difference from `forecast_calibrated` is
smallest is used, if that difference is under 0.001. The maps on hand are `data/processed/lead_calibration.json`
as on main on 24 Oct 2026 (SHA-256 beginning `734202bc7f22af38`) and lead calibration B's map
(`docs/LEAD-CALIBRATION-B-TEST-2026-10-map.json`). So if B is adopted inside the window, rows after that take B's map
in both forecasts. An issue day that no map matches is dropped and counted. If more than 10% of the window's rows are
dropped this way, the check stops and reports.

**Current** is `forecast_calibrated` as published: what the site showed.

**Flat** is, per company, that company's own observed rate over its window rows, given to every row. It is the
Accuracy page's `flat_brier`. It uses hindsight, so it is the strictest constant forecast there is: a forecast that
beats it beats every flat rate.

## The window

- **Target days 26 October to 22 November 2026.** The four whole ISO weeks, Monday to Sunday, after this file's
  commit.
- **Leads 0 to 4,** every scored row of the eight companies.
- **Read on or after 25 November 2026**, from the file published then. A day's label needs a poll on the next day,
  and 25 Nov leaves a day's margin.
- **24 and 25 October** are in neither the fitting rows nor the window.

**If the spill model changes.** The check reads the `spill=` part of each row's version stamp from the forecast log
(the `state` release's `dipcast.duckdb`, downloaded read-only). If any scored row in the window carries a different
`spill=` than the fitting rows, the window ends the day before the first target day with such a row. If that leaves
fewer than 14 days, the check stops: the offsets were fitted for a different layer 1, and a refit needs a new
statement.

**Minimum data.** Every changed company (below) needs at least 50 window rows with `observed` = 1, over all leads.
If any falls short, the window extends by 14 days, once, to 6 December, read on or after 9 December. A company still
short is inconclusive, and the candidate is not adopted.

## Conditions

A company is **changed** if at least one of its window rows has a candidate that differs from `forecast_calibrated`
by more than 0.0001 (the published file's rounding).

The candidate is **adopted only if both hold at every changed company:**

1. **Beats the current forecast.** Brier(candidate) < Brier(current) over the company's window rows, leads pooled.
2. **Beats the flat rate.** Brier(candidate) < Brier(flat) over the same rows.

No in-sample score is computed or reported, at any point. The fitting rows are never scored.

## Reported, not deciding

- Per company and per lead: rows, spill rows, observed rate, mean forecast and Brier for candidate, current and flat.
- Per company, the 95% interval of Brier(candidate) − Brier(current): ISO week of the target day as the cluster,
  every row of a week drawn together, 2,000 draws from `numpy.random.default_rng(20261026)`, one set of draws for
  every company. With four weeks this interval is wide. It is reported so a pass on a hair is read as one.
- A fair flat rate: each company's observed rate on its fitting rows, given to every window row. It uses no
  hindsight.
- How many rows, overflows and spill rows fall in bands of |offset|: under 0.05, 0.05 to 0.2, 0.2 and over.
- United Utilities' window rows: counted, and checked unchanged.

## What follows

**Both conditions hold at every changed company.** Adoption is a separate PR and Ethan's call. It writes the offsets
into the model's `site_offset`, which changes the `spill=` stamp, and the Accuracy page's by-company table gains a
"since" column for the change. It is **not deployed before option B's run** (below). If option B passes, it supersedes
this candidate.

**Either fails at any changed company, or the data is short.** Nothing changes. This file is the record. Its result
is evidence for option B's condition 5.

## Option B and lead calibration B

**Option B** (`docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md`, merged in PR #325) also extends layer 2 to every company.
The two tests differ in four ways:

| | This test (A8) | Option B |
|---|---|---|
| Fitting record | 29 Sep to about 23 Oct 2026, SwimSignal's polls only | EA start/stop files 2024 to Aug 2026, then the polls |
| Expected, e | The logged forecast `forecast_raw`, lead 0 | A layer-1 hindcast on ERA5-Land rain |
| Start dates | None | A change-point rule per overflow, with a dead-monitor check |
| United Utilities | Production's offsets kept | Refitted like every other company |

Both use prior strength 15 and recency 1, and both leave layer 1 alone. This window (26 Oct to 22 Nov) lies inside
option B's window L (29 Sep to 30 Nov).

**They are compatible if this candidate is not deployed before option B runs.** Option B rebuilds its arms from each
logged `p_raw` minus production's offset. Deploying these offsets inside its window L would change `p_raw` mid-window
for every non-United-Utilities overflow. So:
- **This test reads first** (25 Nov). Option B runs on or after 2 Dec.
- **Even if this passes, nothing deploys until option B's result is in.** If option B passes, it supersedes this
  candidate: it fits every company on up to 32 months, not four weeks. If option B fails and this passed, Ethan may
  adopt this.
- This test's frozen offsets could be scored as a reported arm in option B's run. That changes option B's statement,
  so it is Ethan's decision. This file does not assume it.

**Lead calibration B** (`docs/LEAD-CALIBRATION-B-TEST-2026-10.md`) has its live window from 18 Oct to 14 Nov, read on
or after 16 Nov. This test deploys nothing, so it cannot touch production in that window. Its window overlaps this
one. If B's map is adopted inside this window, the per-issue-day map match above keeps both forecasts on the same map.

## Expected, stated now (inferred, not conditions)

- **The offsets will be small.** About 25 lead-0 days per overflow, at mean forecasts of 0.01 to 0.06 outside United
  Utilities, give e of about 0.3 to 1.5. Against 15 pseudo spill-days, an overflow that never spilled gets a ratio of
  about 0.91 to 0.98. Only overflows with several spill-days move much. One with 5 spill-days and e of 1 gets
  (5 + 15) / (1 + 15) = 1.25.
- **So condition 2 will likely fail** at Thames, Southern and Wessex. On 29 Sep to 16 Oct the current forecast's Brier
  there was 0.0066, 0.0138 and 0.0075, against observed rates of 0.0042, 0.0099 and 0.0061, so the flat rate's Brier
  sat 20% to 40% lower. A 2% to 9% cut in the odds cannot close that.
- **Condition 1 is open.** Brier differences will be under 1% at most companies. Their sign will depend on a few
  overflows that spill often, and on whether the window's weather looks like the fitting weeks'.
- **My prediction: not adopted.** The test is still worth its cost, which is small: no rain fetch, no model refit. It
  measures, on four fresh weeks, whether per-overflow offsets help or hurt each company when fitted on the live
  labels. That is the question option B's condition 5 asks.

## Order

1. Push this statement.
2. Commit the harness (`scripts/company_calibration.py`) and its tests (`tests/test_company_calibration.py`).
3. Download `data/verification_live.csv` and the `state` release's `dipcast.duckdb` read-only into scratch. Fit the
   offsets. Commit them with their SHA-256 and the spill model stamp under the line. No score.
4. On or after 25 Nov 2026, run the check once and write the result under the line.

---

## Results

### Step 3: the offsets (24 Oct 2026, after `e534684` and `aae8612` were pushed)

The statement was pushed as `e534684` at 21:26 UTC, and the harness as `aae8612`. Then the data was downloaded and the
offsets fitted. No score of any kind was computed.

- **Command:**

      uv run python scripts/company_calibration.py fit --scored verification_live.csv \
          --db dipcast.duckdb --out docs/COMPANY-CALIBRATION-TEST-2026-11-offsets.json

- **Scored rows:** `data/verification_live.csv` as published 24 Oct 2026 19:43 UTC, 9,726,357 bytes, SHA-256
  `434f910aa0170ec59bba08eaf5f038b423caae0209b4c89ac75891de786eb598`.
- **Forecast log:** the `state` release's `dipcast.duckdb`, asset updated 24 Oct 2026 09:51 UTC, 133,705,728 bytes,
  SHA-256 `8544507fda525c3cb7f3cb3e246d57728e911cbf54dbe6b9e35d519313aed4e7`. Read only for version stamps.
- **Fitting rows:** 20,783 lead-0 rows, target days 29 Sep to 23 Oct 2026, 1,010 overflows. Every one carries the
  spill model stamp `spill=808da63d`. That is the MD5 prefix of the main checkout's `data/processed/spill_model.pkl`,
  checked. The window is checked against this stamp.
- **The frozen offsets:** `docs/COMPANY-CALIBRATION-TEST-2026-11-offsets.json`, SHA-256
  **`2662dcfa592d6e36c7d9e3322a273c3058ea8854dedae414392f022dd5e42e1b`**.

The fit's inputs and the offsets, per company. n and e are what the offsets are made of, not a score. Ratio is
exp(offset), the multiplier on the odds.

| Company | Overflows | Fitting days | n | e | Ratio min | Median | Max | \|offset\| ≥ 0.05 | ≥ 0.2 |
|---|---|---|---|---|---|---|---|---|---|
| Anglian | 159 | 3,266 | 118 | 107.2 | 0.82 | 0.99 | 1.66 | 46 | 7 |
| Northumbrian | 14 | 291 | 16 | 13.2 | 0.93 | 0.99 | 1.28 | 4 | 1 |
| Severn Trent | 111 | 2,431 | 100 | 115.3 | 0.80 | 0.99 | 1.35 | 57 | 4 |
| South West | 29 | 493 | 63 | 62.0 | 0.81 | 0.98 | 1.61 | 16 | 3 |
| Southern | 120 | 1,733 | 77 | 121.0 | 0.86 | 0.98 | 1.33 | 39 | 1 |
| Thames | 194 | 4,228 | 94 | 251.8 | 0.77 | 0.96 | 1.27 | 97 | 3 |
| Wessex | 262 | 5,634 | 209 | 320.2 | 0.73 | 0.98 | 1.23 | 123 | 7 |
| Yorkshire | 120 | 2,691 | 158 | 132.4 | 0.78 | 0.99 | 1.41 | 68 | 7 |
| No company in the file | 1 | 16 | 14 | 0.6 | 1.86 | 1.86 | 1.86 | 1 | 1 |

**Against the expectation stated above.** e per overflow has median 0.91 (quartiles 0.34 and 1.59), close to the
stated 0.3 to 1.5, but with a tail to 5.6 at wet Wessex and Thames overflows. So 602 overflows that never spilled get
ratios down to 0.73, not 0.91. The median ratio at every company is still 0.96 to 0.99.

**Expected moves, from the saved offsets.** The mean forecast, all leads, on the 102,929 non-United-Utilities scored
rows of the fitting days. Today's map matched every issue day (mean absolute difference 0.00003). B's map was never the
closer one, as expected while it is not deployed. No outcome is compared.

| Company | Rows | Mean forecast today | With the offsets | Change |
|---|---|---|---|---|
| Anglian | 16,004 | 0.0274 | 0.0273 | −0.6% |
| Northumbrian | 1,398 | 0.0367 | 0.0367 | 0.0% |
| Severn Trent | 12,055 | 0.0444 | 0.0437 | −1.6% |
| South West | 2,345 | 0.1177 | 0.1168 | −0.8% |
| Southern | 8,635 | 0.0675 | 0.0661 | −2.0% |
| Thames | 20,863 | 0.0553 | 0.0528 | −4.5% |
| Wessex | 28,104 | 0.0538 | 0.0525 | −2.4% |
| Yorkshire | 13,445 | 0.0511 | 0.0508 | −0.6% |

By bin of today's forecast, the offsets lower every bin by 1% to 3% (0.0 bin 0.0165 to 0.0162; 0.4 bin 0.445 to
0.433; 0.7 bin 0.746 to 0.732). The largest move on any one row is 0.11.

So the inference above holds: the offsets move each company's mean by under 5%. Condition 2 is likely to fail
wherever the current forecast sits well above the window's flat rate.

**One overflow has no company in the file:** YWS02298 (a Yorkshire Water id), 16 fitting days, n 14, e 0.60, ratio
1.86. The rule as written fits it, so it is in the frozen file. It belongs to no company's conditions, so the check
counts its rows (`rows_no_company`) and judges them nowhere. Its rows' mean forecast on the fitting days moves from
0.050 to 0.083. If the candidate is adopted, this overflow is left out unless the overflow table gives it a company by
then. The reporting line was added to the harness after the fit and before any score, in the same commit as this
section. Nothing in the fit or the conditions changed.

### Amendment 1 (24 Oct 2026, about 23:10 UTC, before the window opens)

Filed before the window's first target day (26 Oct) and before any window data was read or scored. The
statement above the line is unchanged. The frozen offsets are unchanged: same file, same SHA-256
(`2662dcfa…e42e1b`). Found in review.

1. **Only forecasts issued after the freeze count.** As written, the check took window rows by target day alone.
   But the forecasts for 26 Oct at leads 2 to 4, 27 Oct at leads 3 and 4, and 28 Oct at lead 4 were issued on
   22 to 24 Oct, before the offsets existed. The frozen file was pushed in `2986f6b` at 24 Oct 2026 22:31:41 BST
   (21:31:41 UTC). Scoring the candidate on those rows would apply offsets fitted on labels through 23 Oct to
   forecasts made before then, which a live candidate could never have done. From now:
   - **Cutoff:** a window row counts only if its `issued_at` is after 2026-10-24T21:31:41Z
     (`CANDIDATE_FROZEN_AT`). A row issued at or before it, or with no readable issue time, is left out.
   - **Order:** the cutoff applies first, before the spill-model cut, the minimum-data gate, map matching and every
     score (`available()` in the harness).
   - **Reported:** the check's output gives `issued_before_freeze`: the cutoff, the rows left out, and the count by
     lead.
   - **Tests:** a synthetic window of 2 overflows × 28 days × 5 leads gives 280 rows, of which 12 were issued before
     the freeze (2 at lead 2, 4 at lead 3, 6 at lead 4). Before this amendment the check scored all 280; it now
     scores 268. A boundary test checks that a forecast issued at the freeze to the second is out, and one issued
     a second later is in.
2. **The fitting days, stated once.** The fitting rule says target days on or before 25 Oct, and "The window" says 24
   and 25 Oct are in neither the fitting rows nor the window. They do not conflict in practice: the published file
   held target days only to 23 Oct, so the frozen offsets were fitted on 29 Sep to 23 Oct (`first_day` and
   `last_day` in the offsets file; Step 3 above). So 24 and 25 Oct are in neither, as "The window" says. The
   harness keeps `LAST_FIT_DAY = "2026-10-25"` because it only bounds a fit that has already run. Any refit would
   need a new statement.

Nothing else changes: the window (26 Oct to 22 Nov), the conditions, the minimum data and the read date
(on or after 25 Nov) stand as written.

### Amendment 2, 25 October 2026: noise allowance

Filed on 25 Oct 2026, about 22:00 UTC, before the window's first target day (26 Oct). No window row exists yet, and
none was read. Ethan asked for an audit of the house tests' rules against noise and approved its recommendations;
this amendment applies them here. Its form follows Amendment 1 of `docs/PREREGISTRATION-2027.md`. Every line above
stays as written. The frozen offsets (`2662dcfa…e42e1b`), the window, the changed-company rule, the minimum data,
Amendment 1's cutoff and the read date are unchanged.

**Why.** Conditions 1 and 2 above are point comparisons with no margin. With four weeks of data, a Brier difference
of 0.00001 either way would decide a company, and with it the test. The week interval was reported only. So the
verdict could turn on noise, in either direction.

**The interval.** Option B's two-way cluster bootstrap (`docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md`, "The score"),
applied to the difference in Brier, row by row:
- each draw resamples overflows with replacement and, independently, ISO weeks of the target day with replacement;
  a row counts (times its overflow was drawn) × (times its week was drawn);
- all leads of an overflow-day share both draws;
- 2,000 draws from `numpy.random.default_rng(20261025)`, made once, overflows first, then weeks; the pooled rows and
  every company use the same draws;
- the 95% interval runs from the 2.5th to the 97.5th percentile.

*Why two-way.* The offsets move each overflow's level, so an overflow's errors are shared by all its days, as well
as by every overflow in a wet week. Four weeks alone would give a week-only interval just four clusters. The
statement's week-only interval stays in the output, reported.

**The flat rate in the bootstrap.** Unchanged in definition: each company's own observed rate over its window rows,
given to every row. It is held fixed at that value in every draw.

**The conditions, replacing 1 and 2 as the rule that decides.** "Pooled" means the window rows of all changed
companies together.

- **A. Shown better than the current forecast, pooled.** Brier(candidate) < Brier(current), and the interval of
  candidate − current lies wholly below zero.
- **B. Shown better than the flat rate, pooled.** Brier(candidate) < Brier(flat), and the interval of
  candidate − flat lies wholly below zero.
- **C. No changed company clearly worse than the current forecast.** At each changed company, the interval of
  candidate − current does not lie wholly above zero, and Brier(candidate) is at most 1% above Brier(current).
- **D. No changed company clearly worse than the flat rate.** At each changed company, the interval of
  candidate − flat does not lie wholly above zero, and Brier(candidate) is at most 1% above Brier(flat).

**How they combine.** The candidate is adopted only if A and B hold and C and D hold at every changed company. This
keeps the original's "at every changed company" as a rule that no company may be shown worse, and moves the proof of
help to the pooled rows, where four weeks can show it. It stays all or nothing: there is no adoption at some
companies only. Choosing companies after seeing their scores would be a new candidate, and would need its own
statement.

**Why this rule against the flat rate.**
- *Superiority is kept, and made noise-aware.* The original asked the candidate to beat the flat rate. B asks for that
  to be shown, pooled, not won by a hair. A forecast that cannot be shown better than a constant over the eight
  companies is not worth a model change.
- *Per-company superiority with an interval is not asked.* Northumbrian has 14 overflows, and the minimum data per
  company is 50 spill rows. At that size an interval cannot exclude zero for any forecast this close to the current
  one. Requiring it would make the test fail by design, not by evidence.
- *No company may be shown worse than flat.* D blocks it. A candidate whose interval against flat lies wholly above
  zero at any changed company is not adopted, however well it does elsewhere. So a candidate clearly worse than flat
  cannot be adopted.
- *What is looser than the original.* At a single company, a candidate up to 1% above flat, with an interval that
  spans zero, now passes D. The original would have failed it. That is the noise allowance. B still needs the pooled
  gain to be shown.

**Minimum data.** Unchanged. If a changed company has fewer than 50 spill rows, the window extends once to 6 Dec;
then it is inconclusive and not adopted.

**Reported, not deciding, from now.**
- The statement's conditions 1 and 2 per company, and the verdict they would give (`verdict_original`).
- The week-only intervals against the current forecast and against flat, per company.
- Everything listed under "Reported, not deciding" above.

**Expected under this rule (inferred, not a condition).** On the scored rows of 29 Sep to 16 Oct, from the per-company
figures in `docs/LEAD-CALIBRATION-B-TEST-2026-10.md`, the current forecast's Brier pooled over the eight companies was
about 9% above the flat rate's (summed squared errors about 1,223 against 1,124). Thames was about 57% above,
Southern 41% and Wessex 23%. The offsets move company means by under 5%. So B is likely to fail, and D likely to fail
at Thames, Southern and Wessex. The prediction stays: not adopted.

**Harness.** `scripts/company_calibration.py` computes A to D (`pooled`, `no_worse_than_current`,
`no_worse_than_flat`, `clearly_worse`); its `verdict` is now this amendment's, and `verdict_original` the statement's.
New tests in `tests/test_company_calibration.py`:
- the draws count every overflow and week, and repeat with the seed;
- a constant difference gives a zero-width interval at that constant;
- both rules at their edges (1% slack, interval above zero, gain not shown);
- a gain by a hair is not shown and fails;
- one company clearly worse blocks adoption whatever the pooled gain;
- the case that passed the original passes the amended rules too.

### Step 4: the check

**Read on or after Wednesday 25 November 2026.** Download the published file and the `state` release's
`dipcast.duckdb` the same day, then:

    uv run python scripts/company_calibration.py check --scored verification_live.csv \
        --db dipcast.duckdb --out company-calibration-check.json

It prints the verdict. If it says to extend, rerun with `--end 2026-12-06` on or after 9 December.

Not yet run.
