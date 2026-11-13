# combined-v1 in shadow: the window, the bar and the read date, stated before any row is logged

Written 13 November 2026. Committed and pushed before the logger's code, before any build logged a combined-v1
row, and before any shadow row of any kind was read for it. Results go below the line at the end. Nothing above
that line changes after a row is read, except the window's dates, which are written under the line once the
logger is live, and a plain bug fix, listed under "Changes after this statement" with what it changed.

Register row: "Combined candidate: live status + regional routing" (`docs/RESEARCH-RECOVERY-2026-10.md`). The rule
this follows is "Shadow logging, when it is justified" in `docs/RESEARCH-WORKFLOW.md`.

**This changes no forecast.** The logger writes to its own table. No page, alert, level, card or published score
reads it. **Ethan approves this statement by merging the PR that carries it.** Nothing is logged before that merge.

## Why

`docs/COMBINED-CANDIDATE-BACKTEST-2026-11.md` (#666) scored combined-v1 once on January to August 2026. It passed
its bar at eight companies and failed at United Utilities. That is development evidence: the routing rule and the
combination were chosen after 2026 had been seen. Its status inputs came from the EA's complete record at 00:00
UTC. The live site reads its own polls, which miss short spills and go stale.

The missing piece is a test nothing in combined-v1 has seen, on polled status. The backtest record named a shadow
log as the first source of it. The existing logs cannot give it: they hold the live-status candidate
(`forecast_overflows.p_status`) and the regional-v1 chance (`shadow_regional_v1`), but not D2, so combined-v1 cannot
be rebuilt from them.

## What has been seen, and what has not

- **Seen:** every figure in #666, #639, #357 and #490 (January to August 2026, EA labels). The state release's file
  list and sizes on 13 November (`dipcast.duckdb` 280 MB). The published live scores of production.
- **Not seen:** any row of `shadow_regional_v1`; any `p_status` value; any combined-v1 chance on a live day. No
  shadow table was opened to write this. The live-status read (on or after 23 Nov), the regional read (28 Nov) and
  A8 (25 Nov) had not happened.

## The candidate, frozen

combined-v1 as #666 froze it at commit `4d66d7c7`. Nothing is fitted or changed here. For an overflow of the nine
English companies, a forecast issued at time *T* on local day *D*, and lead *k* (0 to 4):

1. **Base**: regional-v1's raw chance (`shadow_regional.routed`): v2 arm (b) at Anglian, Northumbrian, Severn Trent,
   South West, Southern, Thames, Wessex and Yorkshire; production's raw chance at United Utilities. No lead map.
2. **Status uplift**, where the overflow's status is known at *T*: the base's log-odds plus
   logit(candidate *k*) − logit(D2). Probabilities are clipped to [10⁻⁶, 1 − 10⁻⁶] before a logit.
3. **Fallback**, where the status is not known: the base alone.

Where the day has no rain at the overflow's cell, combined-v1 has no chance (NULL), as production has none.

**The status inputs and when they are known** are the live-status shadow's, unchanged
(`docs/LIVE-STATUS-SHADOW-TEST-2026-10.md`, `model/live_status.py`): the build's own poll for "spilling at issue",
spill-days in the seven local days before *D*, spill hours on the local day before *D*. The status is known only if
the poll gives a current status, the latest current reading is at most **8 hours** before *T*, and no stretch over
8 hours without a current reading falls in the seven-day window. Otherwise it is stale or missing, and the
overflow takes the fallback. **The fallback is part of the candidate. It is logged and scored with it.**

Two differences from #666's rows, both known and both part of what this window measures: the status comes from
polls and local days, where #666 used the EA's complete record at 00:00 UTC; and the issue time is the build's,
where #666's was midnight.

### Frozen files

The logger is off unless every one of these is present with this SHA-256:

| What | File | SHA-256 |
|---|---|---|
| v2 arm (b) | `data/processed/regional/spill_model_v2_offsets.pkl` | `9e0fc54a9356e4cea528606422dc569691453fc3ab98ea31986f19437ba501f2` |
| Candidate, lead 0 | `data/processed/live_status/candidate_lead0.pkl` | `deb5e1e5ee64df0e48e789b9b8eba9bb0be76fba4a23e6745f6a259cec436d00` |
| lead 1 | `candidate_lead1.pkl` | `e0756b1e97485d458bafb868480d73b8c95c502f4136aa05937cb166d3909c3e` |
| lead 2 | `candidate_lead2.pkl` | `ed5bb2b9a39ee222303e3c923b824deffde00e1c63eca89371a3800e51c894da` |
| lead 3 | `candidate_lead3.pkl` | `5180de7086c682fcfebcc9b02e12e197bbd7fb09d5aeb7dfeb940350d8a1360f` |
| lead 4 | `candidate_lead4.pkl` | `ecc835c96d707534d88dbecf6f286c59adb90839f31985926110b85ec4824066` |
| D2, the uplift's reference | `data/processed/combined/spill_model_nine_2024.pkl` | `1603678923ccdd1553830fa67c2069714c0a836c9df7e8c52578aabd729b5bcc` |

These are #666's hashes. All seven were checked against the files on disk on 13 November. D2 (1.55 MB) moves from
`swimsignal-private/baselines/` into the repository in this PR, as the five candidates did in #262 and v2 did in
#490. It was fitted on the EA's 2024 start/stop files, like the candidates. Production's model and lead map are
whatever the build runs; each row carries the build's version stamp.

### United Utilities

United Utilities stays on production. #666 found combined-v1 not better than production there beyond lead 0, so
no result from this window changes what a United Utilities overflow shows. Its rows are still logged with the
frozen formula (production's raw chance plus the uplift), because changing the formula there now would be a new
candidate chosen after seeing #666. They are **reported, not deciding**.

Overflows of any other company (Welsh, Scottish, Irish) and rows with no company are not logged. The candidates
and D2 were fitted on the nine English companies only.

## What is logged

One row per overflow of the nine, target day and lead 0 to 4, in table **`shadow_combined_v1`** of the state
database (`dipcast.duckdb`), which the build already uploads to the `state` release. It is not the issued-forecast
table (`forecast_overflows`). The logger does not write to or read `shadow_regional_v1` or the live-status columns.

| Column | What |
|---|---|
| `issued_at`, `issue_day`, `lat`, `lon` | the forecast's issue time (the same instant the forecast log carries), its local day, the spot |
| `site_id`, `company`, `target_day`, `lead` | the overflow-day |
| `p_combined` | combined-v1's chance. NULL where there was no rain |
| `applied` | `uplift`, `fallback` (status not known, the base alone) or `no_rain` |
| `p_base`, `route` | regional-v1's raw chance, and `v2_offsets` or `production` |
| `p_candidate`, `p_d2` | the two models behind the uplift, on the same row. `p_candidate` NULL where the status was not known |
| `status_known`, `spilling_at_issue`, `spill_hours_24h`, `spill_days_7d` | the status inputs. NULL inputs where not known |
| `status_read_at` | the overflow's latest current reading (the half-hour slot of the poll, so within 15 minutes of it) |
| `rain_issued_at` | when the rain forecast at the overflow's cell was fetched |
| `p_raw`, `p_cal` | **the comparator**: production's raw chance and production's chance after the lead map, from the same forecast |
| `p_shown` | what the site published for that row. Equal to `p_cal` unless the live-status switch is on |
| `rule`, `models`, `version` | `combined-v1`, a stamp of the seven frozen files, production's version stamp |

**Issue-time inputs only.** Every input is one the forecast itself had already read when it ran: the rain the
build fetched, the build's poll, and poll files written before the forecast. The log carries each input's own time
(`status_read_at`, `rain_issued_at`) beside `issued_at`, and the pre-window check counts any row where one is later
than the issue.

**Cost and caps.**
- **Open-Meteo: 0 calls.** All three extra model passes read the site-day frame production has already built. A
  test counts the rain requests with the logger on and off.
- One D2 pass and one candidate pass per lead per spot. No new Worker, scheduler, account or secret.
- **Only forecasts issued by 08:00 local are logged.** The read uses the latest forecast issued by 08:00 on the
  issue day (`forecast_log.DECISION_HOUR`); a later build can never be that forecast. This cuts the rows to about a
  third.
- **Stop rule: the logger writes nothing after issue day 31 January 2027.** Extending or removing it is its own PR.
- Size: inferred, not measured live. About 15,000 to 18,000 rows a logged build (the forecast log's count), two to
  four logged builds a day, so 1 to 2 million rows over the window. The PR states the measured bytes per row.

**Off switch.** Missing or altered frozen file: nothing is computed and nothing is logged. Any error in the shadow is
caught and logged as a warning; the forecast carries on unchanged. To stop it: delete
`data/processed/combined/spill_model_nine_2024.pkl`, or revert the PR.

## The rows, the labels and the comparator

**Rows.** The Accuracy page's scored rows, as `forecast_log.verify_live` selects them: the latest forecast issued
by 08:00 local on the issue day, overflows with a live feed, the coverage rules, rain present. Each is joined to
its `shadow_combined_v1` row by overflow, issue time and target day (the two logs are written by the same
forecast, so the issue time is the same instant). Where several spots share an overflow the rows repeat; the read
takes one. Every predictor is scored on the same rows.

**Labels.** The poll-based live labels `verify_live` gives (PR #253's method): a spill if a poll saw an event
touching the day; a dry day only if the coverage rules hold (at least 6 known polls, no gap over 8 hours, seen
again the next day). A missing or stale status is unknown, never a dry day.

**Comparator.** Production as the site would show it without any switch: `p_cal`, the production model after the
lead map, logged on the same row. If the live-status switch (`DIPCAST_LIVE_STATUS`) is turned on inside the window,
`p_cal` stays production's and `p_shown` records what was published; the date goes under the line and results are
given before and after it. If the lead map or production model changes inside the window (lead calibration B,
A8), the comparison stays paired, since both chances on a row come from the same forecast; the date goes under
the line and results are split at it.

**The two simple rules.** P (same-day persistence) and R (rain over 10 mm in 48 hours), with each side's chance
from the trailing 28 days, exactly as `dipcast.simple_references` computes them for the Accuracy page
(`docs/SIMPLE-REFERENCES-LIVE-2026-11.md`). Comparisons with P or R use the rows where both have a chance.

## The window

- **Opens** on the first target day whose 08:00 forecasts carried combined-v1 at every lead 0 to 4: four days
  after the first issue day with a logged row by 08:00 local. `scripts/combined_shadow_check.py` prints the dates
  from the first logged rows; they are written under the line before any outcome is joined.
- **Runs 28 target days.** Not extended or cut after it starts, except as "Too few" below.
- **Read on or after the second day after the last target day**, so the next-day coverage rule has run.
- If the PR merges on 14 to 17 November, the window is about 19 to 22 November to 16 to 19 December 2026, read
  about 18 to 21 December. That is inferred from the merge date, not fixed here.
- The read harness is due one week before the window ends. It is stated in this document and uses these rules.

It opens no earlier than the merge. It does not touch the live-status read (23 Nov), the regional read (28 Nov),
A8, lead calibration B, ensemble rain, option B or the 2027 primary evaluation.

## The bar

The deciding population is **the eight companies together** (not United Utilities). On the window's scored rows,
combined-v1 **passes** if at **lead 1 and at lead 2**, against each of **production (`p_cal`), P and R**, its
Brier score is lower and the 95% interval of the difference (combined-v1 minus the reference) lies wholly below
zero. Six cells. All six must hold. This is #666's bar, with poll labels and the shown production.

- **Interval.** A two-way bootstrap over overflows and 7-day blocks counted from the window's first day, 2,000
  resamples, `numpy.random.default_rng(20261113)`, one set of draws for every comparison, the 2.5th and 97.5th
  percentiles. P's and R's fitted chances are held fixed within a draw.
- **A caution, stated now.** 28 days is four blocks. A bootstrap over four time blocks is crude: the interval lies
  below zero only when combined-v1 wins in nearly every week. The same interval with the target day as the time
  cluster is reported beside it, not deciding.
- **An interval that includes zero shows nothing either way.** It is "not shown better". It is not "not worse".
  No non-inferiority margin is stated, so no non-inferiority claim will be made from this window.
- **Company guardrail.** Reported for each of the eight with at least 50 spill rows at the lead. A company whose
  Brier is higher than production's with the interval wholly above zero at lead 1 or lead 2 goes back to
  production in any rollout proposal. It does not block the others. A company with fewer than 50 spill rows is
  reported and not judged.
- **Too few.** Under 200 spill rows at the eight companies at lead 1 or at lead 2: the window extends by 14 days,
  once. If still short, it is inconclusive and nothing changes.

**Reported, not deciding:** leads 0, 3 and 4; United Utilities and all nine together; each company; combined-v1
against production's raw chance; against live status alone (`p_candidate` where the status is known, `p_cal` where
not) and against routing alone (`p_base`), both from this table; rows with a known status only; ECE and
reliability tables; warnings at 0.40 as the Accuracy page counts them (hit rate, false-alarm share); the share of
rows that took the fallback, by company; how many 08:00 forecasts carried no shadow.

**Checks run first** (`scripts/combined_shadow_check.py`, on a copy of the state database; it reads only this
table and no outcome): every row has the frozen rule and stamp; the eight are routed to v2 and United Utilities to
production; every fallback row's `p_combined` equals its `p_base`; every uplift row's `p_combined` equals the
formula on its logged parts; no row is issued after 08:00 local or has an input later than its issue. The read
stops if any fails, or if the logged `p_shown` does not match the forecast log's `p_cal` on the joined rows.

## What follows, by outcome

The shadow decides no change to anything shown. Each outcome names the next deliverable.

- **Passes.** The first evidence on data combined-v1 had not seen. Next: a limited-rollout proposal for the eight
  companies in its own PR, with United Utilities and every other site on production, any guardrail company on
  production, a staged switch, monitoring and a rollback, stated against the 2027 tag date (30 April 2027). Ethan
  decides. **If the live-status switch is already on by then**, the proposal also needs combined-v1 lower than
  live status alone at leads 1 and 2 with the interval below zero. #666 did not show that (−0.0008
  [−0.0024, +0.0002]). Without it the simpler model already adopted stays.
- **Fails against production at lead 1 or lead 2.** Not shown better live. Production stays. Next: a diagnosis
  from the logged parts, in the read's PR: base or uplift, known-status share, level or ranking (ECE, AUC), which
  companies. combined-v1 stays a development model.
- **Beats production but not P or not R.** The record says which. No rollout proposal on forecast-skill grounds.
  Next: the same diagnosis, against the rule it lost to.
- **Too few after the extension.** Inconclusive. Next: the EA's September to December 2026 start/stop file, when
  published, scored by #666's harness unchanged. That backtest runs whatever this window shows.

**If the frozen files, the status rule or the formula change inside the window**, the window ends the day before.
Under 14 days left: it restarts with a new statement.

## Not chosen, and why

- **Dropping the uplift at United Utilities.** A new candidate chosen after #666. The frozen one is logged; the
  population that decides leaves United Utilities out.
- **Rebuilding combined-v1 from the other two shadow logs.** D2 is not logged, and the join would read tables
  whose windows have not been read.
- **A lead map on combined-v1.** #666 scored it raw. A map would be a fitted part.
- **Logging every build.** Only a forecast issued by 08:00 can be the decision forecast.
- **A new Worker or schedule.** The site build's cadence is adequate: the read needs one forecast by 08:00 a day.

---

## Results

Not yet run. No row has been logged.

### The window's dates

To be written from `scripts/combined_shadow_check.py` on the first state release that holds logged rows, before any
outcome is joined.
