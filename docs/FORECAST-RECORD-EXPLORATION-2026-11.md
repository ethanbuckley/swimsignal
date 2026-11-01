# How good are the forecasts? Exploration and Research Lab exhibit 3

Written 1 November 2026. Bounded exploration under [the research workflow](RESEARCH-WORKFLOW.md), for Research Lab
exhibit 3. **Exploratory, on outcomes already read.** It changes no verdict, model, threshold or the live forecast.

## What was asked

Build a forecast-against-observation explorer: choose a place and period, see what the model predicted, what was
found and where it missed, beside simple baselines, with false alarms shown as plainly as misses.

## Inputs, cutoff and budget

- Committed files only: `data/research/ecoli_evidence.v1.json` (1.1.0); `data/processed/verification_2025.csv`,
  `verification_leads_2025.csv`, `reliability_2025.csv`; `data/processed/prf_comparison.json`.
- **Cutoff 30 September 2026.** Every outcome used is from before the earliest active evaluation window (lead
  calibration B opened 18 October). No shadow log, state database or issued-history file is read. Nothing from the
  live-status, A8, D4, regional or option B windows is scored.
- No download, no dipcast import. Input hashes checked before and after (unchanged). It runs in seconds.
- Code: `scripts/forecast_record_explore.py`. Output: `prototypes/research-lab/forecasts/exploration.json`. Bootstrap
  over bathing waters, 2,000 draws, seed 20261102, fixed before any figure was computed.

## The E. coli estimates and what they are

The estimates are the concentration study's hindsight estimates (`docs/CONCENTRATION-STUDY-2026-11.md`): the
production model's form refitted leaving out each year, with archived lead-0 forecast rain. **They are not what the
site issued.** 1,537 samples at 32 bathing waters, 2024-2026. The model's form was chosen with these years in view, so
this is a description of fit to held-out years, not an independent test.

Simple alternatives, each leave-one-year-out:
- **usual rate:** the over-900 rate for rivers, or for lakes, in the other years;
- **this water's own rate:** the site's over-900 rate in the other years (5 samples or more, else the usual rate);
- **last sample:** the other years' over-900 rate after an over-900 sample, or after one under it, using the
  previous sample at the site within 30 days.

## Results

| | Rivers (900 samples, 20 sites, 192 over 900) | Lakes (637 samples, 12 sites, 16 over 900) |
|---|---|---|
| Brier, estimate | 0.123 | 0.025 |
| Brier, usual / own rate / last sample | 0.178 / 0.171 / 0.166 | 0.025 / 0.024 / 0.024 |
| Estimate minus last sample (95%, by site) | −0.043 (−0.062 to −0.024) | +0.001 (−0.001 to +0.005) |
| AUC, estimate / own rate | 0.829 / 0.637 | 0.468 / 0.813 |
| At the 25% line: caught / missed / false alarms | 121 / 71 / 125 | 0 / 16 / 0 |
| Last-sample rule at 25%: caught / missed / false alarms | 84 / 108 / 111 | 1 / 15 / 6 |

- **Rivers: the estimate beat every simple alternative,** with intervals clear of zero. It caught 37 more samples over 900
  than the last-sample rule, for 14 more false alarms: about one false alarm per sample caught.
- **Lakes: no better than the usual rate.** It ranked lake samples no better than chance (AUC 0.47); each lake's own
  past rate ranked them well (0.81). The site already gives no E. coli warning at lakes. This is consistent with that
  choice and with the lake work under way in PRs #584/#585, which tests a range, not this warning.
- **Confident misses:** 17 of the 71 river misses had an estimate under 10%; the median miss was 15.5%.
- **By year** (all sites): the estimate beat the usual rate in 2024, 2025 and 2026 (0.104 vs 0.153, 0.078 vs 0.100,
  0.066 vs 0.091). Fewer samples went over 900 each year, so compare within a year.

Spill forecasts and the EA comparison are shown from their existing records, unchanged:
- **2025 held-out year, United Utilities overflows only** (828,550 overflow-days, 7.4% spilled): skill against the
  usual rate 36% on the day, 30%, 28%, 25%, 20% at one to four days ahead. Above about 30% forecasts ran high (top band
  93% forecast, 85% observed). The winter recalibration test already covers this; nothing new is proposed.
- **Beside the EA's daily risk prediction** (`prf_comparison.json`): 30 samples both covered, 16-28 September 2026;
  the record's own verdict is "Too few samples to judge either forecast."

## Established and inferred

- **Established (this run, already-read outcomes):** the figures above.
- **Not established:** how the issued forecasts perform. Hindsight uses archived forecast rain and refitted models; the
  issued record adds feed failures, timing and the model actually deployed. Only 30 issued estimates have been scored.
- **Inferred:** the lake result says the model's lake inputs carry little sample-level information at these 12 lakes;
  it does not say lakes cannot be forecast.

## Wording correction after review (1 November 2026)

An outside review found that the exhibit's opening said the estimate "warned before" 121 river samples. These estimates
were rebuilt afterwards, so nothing was warned before any sample. The opening, the dot ledger's caption and playback,
the per-site facts and note 3 now say the estimate "would have flagged" a sample, and the opening says "rebuilt
afterwards, not issued at the time". The one comparison of forecasts issued at the time (against the Environment
Agency, 16 to 28 September 2026) keeps "warned", since those were real issued forecasts. No numbers changed.

## Proposed next questions (not started)

1. **How far apart are hindsight and the issued record?** Report issued against hindsight on the same 2027 samples, from
   the 2027 primary evaluation already registered. Unconvincing: no comparison on shared samples.
2. **Why does a lake's own history beat the model?** A lake model starting from the lake's own rate, judged on unseen
   lake seasons, within LAKE-CONC. Unconvincing: a gain only at the best-sampled lakes, or one that vanishes out of sample.
3. **What do confident misses share?** A checklist fixed before opening the 17 river cases, counted on correct days too.
4. **Which catch/false-alarm balance do swimmers want?** Show the whole trade-off curve and ask; never move the line on
   these samples to improve a figure.

## The prototype

`prototypes/research-lab/forecasts/`, with the Lab front page at `prototypes/research-lab/` and the shared stylesheet
`prototypes/research-lab/lab.css` (moved from exhibit 1). Checked at 1440 × 900 and 375 × 812: no horizontal scroll, no
console errors, site picker, season rows, sample selection by mouse and keyboard, deep links `#bw=…&t=…`. Not checked:
Safari, real phone, screen reader.

## Readout

| Field | Content |
|---|---|
| Identity | Research Lab exhibit 3; "forecast-record-explore 0.1.0"; PR #586 |
| Evidence | Already-read outcomes to 30 Sep 2026; rivers −0.043 (−0.062 to −0.024) against the best simple alternative; lakes no difference |
| Stage and claim | Exploration. Supports "at rivers, hindsight estimates beat simple alternatives"; not "the site's issued forecasts were this good" |
| Next deliverable | Ethan's review of exhibits 1 and 3; question 2 goes to LAKE-CONC |
| Budget | None spent: offline, committed files |
| Release route | Product owner (LABS) decides what moves to the Accuracy page; rollback is not linking it |
