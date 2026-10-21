# Ensemble rain for the listed spots: the test, stated before any run

Written 18 October 2026. It is committed and pushed before any code that changes the build's output,
and before any ensemble forecast is logged or scored. Results go below the line at the end. Nothing
above that line changes after a result is seen. Review task D4 (`docs/REVIEW-2026-10-16.md`, section 4
item 3, data source 3).

## Why

Forecast rain is the largest error in the spill forecast. In the neural-net test of 18 October
(PR #239), the boosted model's 2025 Brier score rose from 0.0378 with same-day rain to 0.0492 with
rain forecast four days ahead. The gap between the two models was 0.0011. The page shows one figure
for each of the five days, and nothing says that day 5 is less certain than day 1.

An ensemble is a set of forecasts from the same weather model, each started from slightly different
conditions. Where its members disagree, the weather is less predictable. The question here is
whether that disagreement, carried through the spill model, marks the days when the spill forecast
goes wrong, and whether the members' average is a better forecast than the single one.

## What Open-Meteo keeps: a backtest is not possible

Read on 18 October 2026, then checked with five requests for one point (54.4 N, 2.9 W).

- **The Ensemble API page** (open-meteo.com/en/docs/ensemble-api): "You can retrieve up to three days
  of historical data. Additionally, we store ensemble means and spreads with a longer retention
  period." It lists MOGREPS-UK: "UK", "2 km, 1-hourly", 3 members, "5 days", "Every hour".
- **The Ensemble Mean API page**: "These ensemble means are stored for an extended period, with most
  available since March 2026. Individual ensemble members, however, are only stored for up to three
  days."
- **The Single Runs API page** (single-runs-api): "Most models are archived from 2nd of April 2026."
  It says the ordinary API "stitches the most recent run of each model into a seamless, continuously
  updated time-series", which "discards the individual run structure required for research,
  post-processing, and backtesting workflows". Its model list has no UK ensemble.
- **The Previous Runs API page**: it "supports the same models as the Weather Forecast API". Its
  model list has no UK ensemble either.

Measured with the requests:

| Request | Answer |
|---|---|
| Members, `ukmo_uk_ensemble_2km`, 8 to 17 Oct | Values for 15 to 17 Oct only; 8 to 14 Oct null |
| Members, the same, forecast from 18 Oct | `precipitation`, `precipitation_member01`, `precipitation_member02`; values to 23 Oct 14:00 UTC (126 hours from an 08:00 UTC run) |
| Ensemble mean and spread, `ukmo_uk_ensemble_mean_2km`, 8 to 17 Oct | Values for every hour |
| Previous Runs, `ukmo_uk_ensemble_mean_2km`, `precipitation_previous_day1` and `_day3` | Null for every hour |
| Single Runs, `ukmo_uk_ensemble_2km`, run 2026-10-08T00:00 | "The requested model run is not available." |

So the members are kept for three days only. The means and spreads are kept longer, but as one
stitched series. **Inferred, not measured:** a stitched series holds each hour from the latest run
that covered it, so an archived hour is a short-range forecast, not the forecast made three to five
days before. Neither archive by run nor archive by lead holds the UK ensemble. Days 3 to 5 as they
were forecast cannot be recovered for any past date. **The test therefore needs a live collection
window:** the build logs every member's forecast from the day the code goes live, and the window is
scored once it has passed.

## Seen before writing

- **The live scored rows**, `data/verification_live.csv` as published on 18 Oct 2026, read for their
  size only. 17 scored target days, 29 Sep to 17 Oct. At leads 2 to 4 (days 3 to 5 on the page):
  50,434 rows, 1,412 of them spills (2.8%), 1,145 overflows at nine companies, 420 units of company,
  target day and lead, 242 of them with at least one spill. Every one of the 17 days had a spill
  somewhere. By company: United Utilities 661 spills, Yorkshire 234, Anglian 138, Severn Trent 119,
  Wessex 72, Thames 45, South West 43, Southern 30, Northumbrian 28.
- **The forecast log** in the `state` release, 18 Oct: `dipcast.duckdb`, 99.9 MB, 2,810,935
  overflow rows from 12 Sep, about 110 rows per spot forecast.
- **The Open-Meteo ledger** in the build of 18 Oct 11:28 UTC (run 39123349125): 2,173 calls that UTC
  day after three builds (spots 996, click-anywhere 667, Scotland 300, weather 210). The 17 Oct
  ledger reached 4,013 by 23:15 UTC; it started when PR #243 merged that day. That build made 19
  Open-Meteo requests (spots 7, weather 3, click-anywhere 6, Scotland 3) and retried 5 handshakes.
- **Open-Meteo's weighting**, from its source (open-meteo/open-meteo,
  `ForecastapiController.swift` at `4633aa1250`, `ForecastApiResult.swift` at `cfb443ac67`): a
  request's variables are multiplied by the members of each model it asks for, and then the rule
  in `rainfall.call_weight` applies. One variable from a 3-member model over 6 days weighs
  max(1, 0.3, 0.3 × 6/14) = 1 call per location. The review's "one more call per batch" counted
  requests, not calls.
- **One member forecast**, from the probe above: rain at Windermere's cell from 18 to 23 Oct of
  18.8, 36.1 and 40.4 mm for the three members. No member has been compared with anything that
  happened.

## The candidate (fixed now)

**What the build fetches.**
- The Open-Meteo Ensemble API (`ensemble-api.open-meteo.com/v1/ensemble`), `models=ukmo_uk_ensemble_2km`,
  hourly `precipitation`, `past_days=0`, `forecast_days=6` (one UTC day more than the five local days,
  as `fetch_forecast` asks), in UTC. Three members: the control (`precipitation`) and two perturbed.
  Met Office data: Open-Meteo's licence page lists "Atmospheric forecasts from UK Met Office" under
  CC BY-SA, the same licence and credit as the single forecast for England.
- For the listed spots' rain cells only, the 0.1° cells `prefetch_rain` already collects (332 on
  18 Oct). Not for click-anywhere (1,588 cells) or the Scottish shadow.

**What it costs, and the rules that hold it.**
- 332 cells are 7 requests at 50 a request, and 332 calls a refresh.
- A cell is asked for again only when its cached members are 12 hours old, or no longer reach the end
  of the fifth local day. MOGREPS-UK runs reach 126 hours, so one refresh after local midnight covers
  the whole day. That is about two refreshes a day: 664 calls.
- At most 1,000 ensemble calls in a UTC day (three refreshes), booked as `ensemble` in the ledger.
- In each build the ensemble is asked for after the spots' own forecast, and only from spare calls.
  After the request, what is left of the day's 9,000 must still cover the others' planned use for
  the rest of the UTC day: 8,750 a day (the most the other users ask for at a build every 30
  minutes, `tests/test_open_meteo_ration.py`), spread evenly over the day.
- At that planned ceiling, no ensemble request is made, and none is held from the others. At the
  measured rate (2,173 calls in the first 12 hours of 18 Oct, about three builds), the first request
  of a UTC day usually waits for the second build, and two refreshes take the day to about 5,000.
  Builds have run a median 2.9 hours apart (site.yml), so the ceiling has not been reached.
- **Amended 18 Oct, before any code ran.** The first version of this statement (`e460af5`) kept a
  fixed reserve of 1,500 calls instead. That would have let the ensemble take a ceiling day to about
  9,400 and so hold back about 400 of the spots' and the map's calls in the day's last builds. The
  pace rule replaces it. No condition changed.
- The build log gains `open_meteo_requests`: the requests made by that build, retries included.
  With the ensemble it should be about 26. Over 40 is a build warning.
- An ensemble request that fails, or that the rules hold back, uses the cell's cached members if they
  are under 24 hours old. A day the members do not reach has no band. Never zero rain.

**What the build computes.**
- Each member's hourly rain is the single forecast's rain before the hour that forecast was issued,
  and the member's from that hour on. The past (31 days of rain history) is the same for every member.
- The spill model and the lead calibration run once per member, exactly as for the single forecast.
  This gives each overflow a calibrated spill chance per member and day, and each spot a risk per
  member and day (`transport.combine_daily`, with the same rule for missing rain).
- **The band** for a day is the lowest and the highest of the three members' spot risks. It is
  given only when all three have a risk for that day.
- **Why the range, not the 10th and 90th percentiles the review named.** Three values cannot
  estimate a 10th or 90th percentile. The lowest and highest of three draws fall, on average, near
  the 25th and 75th percentiles of what they are drawn from. So the band is called what it is: the
  range of three forecasts. It is not a 90% interval.
- **The headline does not change.** The level, the bar, the alerts and the scores stay on the single
  rain forecast.

**What the page shows.** A thin line across the bar of days 3, 4 and 5, from the lowest member's
risk to the highest, on the same scale as the bar. It is drawn only where the bar is placed by the
sewage spill risk. Where the E. coli estimate, a poor rating or algae sets the level, the band would
describe something the bar does not show, so it is left off. Where the three agree to within 2% of
the bar's length, there is no line. A screen reader hears the range in words. The data is each day's
`band` in `spots.json`, `{"low", "high"}`, on all five days.
The Method page gains one paragraph saying what the line is and that it is under test.

**What is logged.**
- `forecast_overflows`: `p_cal_members` and `rain_members`, three values each: the calibrated spill
  chance and the day's rain at the overflow's cell for each member.
- `forecast_points`: `risk_members`, the three spot risks, and `ens_issued_at`, when the members were
  fetched.
- Null when the build had no members.

## The questions and the conditions

**Rows.** The scored live rows the build publishes (`data/verification_live.csv`), as
`forecast_log.verify_live` selects them: the latest forecast issued by 08:00 local on the issue day,
overflows with a live feed, the coverage rules, rain data present. Each is joined to its row in
`forecast_overflows` by the same selection, and kept only if it has three finite member chances.
Rows without members are counted and reported. They are left out of both sides of every comparison.
Both sides of every comparison are on the same rows.

**Deciding rows are leads 2, 3 and 4**, the days the band is drawn on (day 1 on the page is lead 0).
Leads 0 and 1 are reported alongside.

**Notation.** For a row: p is the headline's calibrated chance, the forecast the site shows. m1, m2,
m3 are the members' calibrated chances, and y is 1 for a spill, 0 for none. The members' mean is
(m1 + m2 + m3) / 3.

### Question 1: does the members' spread mark the forecasts that go wrong?

Unit: one company, one target day, one lead, with at least 20 rows. In each unit:
- **H**, the forecast count of spills: the sum of p.
- **O**, the observed count: the sum of y.
- **E**, the error: |O − H|.
- **S**, the spread: the highest of the three members' sums of chances minus the lowest.
- **V**, the error the headline itself expects: the sum of p(1 − p).

On wet days H, E and S are all larger, so S would track E even if the members said nothing new. V
grows with H in the same way. So the deciding condition asks whether S tracks E beyond what V does.

- **S1.** Over the units at leads 2 to 4, the Spearman correlation of S with E is above 0, and its
  95% interval is above 0.
- **S2.** The partial Spearman correlation of S with E, given V, is above 0, and its 95% interval
  is above 0. Ranks of S and of E are each regressed on the rank of V by least squares, and the two
  sets of residuals correlated.
- **Intervals**: 2,000 bootstrap draws of target days with replacement (all units of a drawn day
  go in together), seed 20261018, the 2.5th and 97.5th percentiles.

### Question 2: is the members' mean no worse than the single forecast?

- **M1.** Over every row at leads 2 to 4, Brier(mean) ≤ Brier(p).
- **M2.** At each of leads 2, 3 and 4, Brier(mean) ≤ 1.02 × Brier(p).
- **M3.** At every company with at least 50 rows with y = 1 at leads 2 to 4,
  Brier(mean) ≤ 1.02 × Brier(p).

The day-bootstrap interval of Brier(mean) − Brier(p) is reported, not deciding.

### What follows

- **The band.** It is shown from the day the code goes live, and it changes nothing else: no words
  on the page, no alerts, no level.
  - **S1 and S2 pass:** the band stays. The review's "forecast confidence" words ("uncertain: the
    rain forecasts disagree") can then be built as their own task, with Ethan's wording.
  - **S2 fails:** the band comes off the page. A band that tracks error no better than the level
    itself tells a swimmer nothing the level does not. The members stay in the log.
  - **S1 fails:** the same.
- **The headline.** At leads 2 to 4 it switches from p to the members' mean only if M1, M2 and M3
  all pass. Where a build has no members, it stays on p. Otherwise it stays on p.
- **Inconclusive** (minimum data below): no switch. The band stays, still display-only, and Ethan
  decides whether to run a second window.

## The window

- **Opens** on the first target day whose 08:00 forecasts at leads 2, 3 and 4 all carried members:
  four days after the first issue day with members by 08:00. Its date is written under the line
  once the code is live. Deploying is Ethan's decision; nothing is logged before then.
- **Runs** 28 target days. Read on or after the second day after the last, so the next-day
  coverage rule has run.
- **Minimum data.** At least 500 rows with y = 1 at leads 2 to 4 with members, and at least 300
  units for question 1. If either falls short, the window extends by 14 days, once. Then it is
  called inconclusive. The 17 days to 17 Oct had 1,412 spills and 420 units at these leads.
- **If the ensemble changes** (Open-Meteo sends a different number of members for
  `ukmo_uk_ensemble_2km`, or the model is changed in the code), the window ends the day before. If
  that leaves fewer than 14 days, it restarts.
- **If the spill model or the lead calibration changes** (the option B test,
  `docs/LEAD-CALIBRATION-B-TEST-2026-10.md`, may adopt a map after 16 Nov): each row's headline and
  members come from the same model and map, so the comparison stays paired. The date is written
  under the line, and the results are also given before and after it. The window does not stop.
- **Sanity checks**, run first. The joined p must equal the CSV's `forecast_calibrated`, with a mean
  absolute difference under 0.0005 (the log keeps members as 4-byte floats). Rows with members
  should be at least 80% of the scored rows at leads 2 to 4. If either fails, the check stops and
  reports why.

## Reported, not deciding

- **Rain.** Over the overflows' cell-days at leads 2 to 4: the Spearman correlation of the members'
  rain range with |headline rain − ERA5-Land rain|, and the partial correlation given the headline
  rain. ERA5-Land is a reconstruction of the weather as it fell, at 0.1°. It is fetched for the
  window's days from the archive API after the window, about one call per cell.
- How often the headline p falls inside the members' range, and the band's mean width, per lead.
- Questions 1 and 2 at leads 0 and 1, and at each of leads 2, 3 and 4 alone.
- Each member's Brier score beside the headline's.

## Expected, stated now (inferred, not conditions)

- **S1 passes.** Wet days carry larger errors and wider spreads, whatever the members know.
- **S2 is open.** Three members give a noisy spread. MOGREPS-UK at 2 km is the Met Office's
  short-range system, and its members are perturbations of the same system the single forecast
  comes from: the Method page says the rain "for England is the Met Office's". I lean towards a
  fail, with low confidence.
- **M is open.** The mean of three probabilities is smoother than one, which helps a Brier score
  when the members are as good as the single forecast. But MOGREPS-UK members may be less skilful
  than the single forecast at four days, which hurts.

## Not chosen, and why

- **A larger ensemble.** MOGREPS-G (18 members, 20 km, 8 days) would weigh 1.8 calls a location:
  about 600 a refresh. ICON-EU-EPS (40 members) 4.0, about 1,330. ECMWF IFS (51 members, 25 km) 5.1.
  Any of them fits the measured day but not the planned ceiling. MOGREPS-UK is the
  review's choice and the only one at 1 call a location. If S2 fails, a larger ensemble is the
  obvious second test.
- **Building our own members from the stitched mean and spread.** That gives a rain spread, not a
  set of rain series for the spill model, and the archive is not by lead.
- **Lagging.** The Met Office's own MOGREPS-UK combines the last six hourly runs into 18 members.
  Open-Meteo serves the latest three. Keeping each refresh's members and adding the previous
  refresh's would double the members at no cost. It mixes runs of different ages and is a separate
  change.

## Order

1. Push this statement and the check script, `scripts/ensemble_rain_check.py`, with its test.
2. Build the ensemble path behind it, in a draft pull request against main. Nothing is deployed.
3. If Ethan merges it, the first build logs members. The window's dates go under the line.
4. After the window, run the check and apply "What follows".

The check:

    gh release download state -p dipcast.duckdb -D /tmp/ens-state
    curl -sSO https://swimsignal.co.uk/data/verification_live.csv
    uv run python scripts/ensemble_rain_check.py --db /tmp/ens-state/dipcast.duckdb \
        --scored verification_live.csv --start <first day> --end <last day> --out ens-check.json

---

## Results

None yet. The window is open.

### The window's dates (written 21 Oct 2026, before any member was scored)

Read from the forecast log in the `state` release of 21 Oct 2026 10:33 UTC (`forecast_overflows`, opened
read-only). Only whether `p_cal_members` was present in each build was counted. No member was joined to a
scored row or compared with anything that happened.
- **Live.** PR #257 merged 18 Oct 2026 19:18 UTC (`42ab3ea`). The first build to log members was issued at
  19:22 UTC that evening. Every build from then to 21 Oct 10:26 UTC logged `p_cal_members` on every overflow
  row. The builds earlier on 18 Oct logged none.
- **First issue day with members by 08:00 local.** 19 Oct: builds issued at 00:22 and 05:02 UTC (01:22 and
  06:02 BST). The 08:00 forecasts of 20 Oct (00:52 and 05:36 UTC) and 21 Oct (01:13 and 06:14 UTC) carried
  them too.
- **Opens** on target day 23 Oct 2026. Its forecasts at leads 4, 3 and 2 are the 08:00 forecasts of 19, 20
  and 21 Oct, so this date is fixed.
- **Runs** 28 target days, 23 Oct to 19 Nov 2026. **Read** on or after 21 Nov 2026.
- **If the minimum data falls short**, the 14-day extension runs to 3 Dec 2026, read on or after 5 Dec.

### Seen after the statement, before the window (18 Oct 2026)

One local build of this branch (`3f74486`), 14:22 BST. It used the `state` release, an empty rain cache
and the Scottish shadow off. These say what the page will look like on one day's weather. They are not
results: no member has been compared with anything that happened.
- **Requests:** 23 Open-Meteo requests: 16 to the forecast API (spots 7, weather 3, click-anywhere 6)
  and 7 to the ensemble API, with no retries.
- **Calls:** 1,069 in the ledger: spots 332, ensemble 332, weather 105, click-anywhere 300. All 332 cells
  got members, in 2 seconds.
- **Bands:** 80 spots had bands, every spot with an overflow upstream. Of the other 25, 22 have none
  upstream and 3 have no forecast possible.

| Day on the page (lead) | Median width | 90th percentile | Band crosses a level line | Headline inside the range |
|---|---|---|---|---|
| 3 (2) | 0.065 | 0.27 | 41% | 70% |
| 4 (3) | 0.083 | 0.27 | 41% | 70% |
| 5 (4) | 0.115 | 0.32 | 51% | 65% |

- **The log:** 8,830 overflow rows from the build, all with members. All 8,475 live-fed rows have three
  finite values.
