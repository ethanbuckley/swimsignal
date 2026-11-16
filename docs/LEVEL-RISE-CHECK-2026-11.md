# Does a recent rise at the river's gauge order E. coli samples beyond rain?

Statement written 16 November 2026 against main `6743baf2`, and pushed before any river-level reading was fetched for
it. **Development evidence only:** every sample used here was already seen. Nothing on the site changes, and no
frozen file, active window or the 2027 primary evaluation is touched. Nothing below the line "Result" existed when
this was pushed.

## Why

The forecast says what it cannot see: runoff from farmland and roads, and treated sewage. A rise at the river's own
gauge shows water arriving from upstream, whatever carried it. The site already reads each spot's gauge for its river
level tile (`src/dipcast/ingest/flows.py`). No test here has used a gauge reading as an input to the E. coli estimate.

Related work, and how this differs:

- Flow as dilution failed (#404, `docs/FLOW-DILUTION-TEST-2026-10.md`). That divided the spill signal by flow. This
  asks whether a rise is a signal of its own.
- River rises (#627) forecasts the rise itself from radar and upstream gauges. It does not use E. coli samples.
- The ambition portfolio (#704) measured that rain and season alone give most of the within-site ordering at rivers.
  So the bar here is rain, not nothing.

## What is fixed

- **Samples.** The backtest bench's seen river rows (`seen.parquet`, SHA-256 `417648aa…`): 943 Environment Agency
  samples at 20 river bathing waters, May to September 2023-26. The bench's held-out file is not opened.
- **Gauges.** Each bathing water's own level gauge, as the river-rises work picked it with the site's rule
  (`flows.station_pick`): `docs/level-rise-check/gauges.csv`. 17 of the 20 have a 15-minute series in the
  Environment Agency's Hydrology archive. The Cam, the Waveney and the Dee at Chester do not, and are left out.
- **Fetch.** One CSV request a gauge, 28 April 2023 to 1 October 2026: 17 requests, capped at 25, 2 seconds apart, a
  refusal or server error stops the run. No Open-Meteo call. Readings the EA marks suspect, rejected or missing are
  dropped. Ledger in `docs/level-rise-check/ledger.jsonl`; series in `swimsignal-private/level-rise/`.
- **Two inputs per sample**, from the gauge alone:
  - `rise24`: the level at the sample time less the lowest level in the 24 hours before, as a share of the gauge's
    usual range (the EA's typical high less typical low).
  - `index`: where the level sits in that range at the sample time.
  A sample needs a reading within 30 minutes and at least 80% of the 24 hours' readings; otherwise it is left out
  of every figure, for every model alike.
- **Models.** Pooled least squares on log10 E. coli, each site predicted from the other sites. Base: rain in 48 and
  24 hours, season, upstream exposure. Candidate: base plus `rise24`.
- **Primary metric.** Mean within-site Spearman correlation with the measured log10 count (sites with 15 or more
  rows): candidate minus base. 95% interval from 4,000 resamples of sites, seed 20261116.
- **Supported** if that interval lies wholly above 0. **Not supported** if it includes 0 or lies below.

## Reported, deciding nothing

Base plus `rise24` and `index`; rain and season with the two gauge inputs against rain and season alone; each gauge
input alone against 48-hour rain alone; the same on dry days (under 2 mm in 48 hours), where rain says nothing; the
share of samples over 900 with and without a rise; each site's correlations.

## What each outcome leads to

- **Supported.** A count of how many of RIVER-UNSEEN's 59 held-out points (#705) have a gauge with a series back to
  2012. If 30 or more: a second candidate for that read, under its own statement, pushed before any join. A live
  version would use the real-time feed the level tile already reads, because the archive lags.
- **Not supported.** Recorded as such for this form of the input. No further gauge variant is tried on these samples.
  If the dry-day figures point somewhere, that is noted for the dry-day project, not acted on here.

## Limits known now

- 17 sites. An interval from 17 sites is wide.
- The Cam is left out, and it is one of the three rivers with the most dry-day results over 900.
- A gauge can sit some way from the sampling point, above or below it.
- The level in the archive is quality-checked after the event. A live gauge reading can differ.

---

## Result
