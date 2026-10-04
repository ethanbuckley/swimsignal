"""Welsh storm overflow annual returns (EDM), per overflow and year, for the Wales hindcast.

Task W2 of docs/WALES-PLAN-2026-10.md. Off CI and unpublished: Dŵr Cymru Welsh Water's layers
carry no licence, so the output, data/processed/wales_annual.parquet, stays out of git and off the
site until Dŵr Cymru answers question 8.1.7 of the plan.

Sources, read with scripts/fetch_wales_annual.py:

- Dŵr Cymru's own annual-return layers on ArcGIS Online (organisation KLNF7YxtENPLYVey), one per
  return year, 2022 to 2025 (DC_LAYERS). No licence on any of them.
- The Rivers Trust's compilations, "Event Duration Monitoring - Storm Overflows", for 2023 to 2025
  (RT_LAYERS), for Hafren Dyfrdwy's rows. Their item licence text names the Open Government
  Licence. The 2022 compilation has no Hafren Dyfrdwy rows.
- Dŵr Cymru's live layer, Spill_Prod__view, to match each overflow to a live row by outlet
  position, and its twin Spill_Prod__External for the live row's DCWW_ID.

The long-term average rule. Written here on 4 Oct 2026, before the first run, and not to be changed
after the results are seen; a different rule is a new, dated rule beside this one.

    For an overflow and a return year Y, lta_spills is the mean of the overflow's counted spills
    over its return years from FIRST_YEAR (2022) to Y inclusive in which the count is present and
    monitor uptime is at least LTA_MIN_UPTIME (90%). lta_basis is "uptime90" and lta_years the
    number of years averaged.

    If no such year exists, lta_spills is the mean of the counted spills over the years from
    FIRST_YEAR to Y with a count present, whatever their uptime, and lta_basis is "any_uptime".
    If no year has a count, lta_spills is missing and lta_basis is "none".

    A year whose uptime is not known does not reach 90%. Dŵr Cymru's 2023 layer has no uptime
    field, so its 2023 uptime is taken from the Rivers Trust's 2023 compilation where the permit
    reference and activity reference match one row exactly; otherwise it is unknown. Uptime is a
    percentage from 0 to 100; a layer whose uptime column never exceeds 1 holds fractions and is
    multiplied by 100.

The same function, run on the Environment Agency's returns (data/processed/annual_returns.parquet)
over return years 2022 to Y, gives the error of the rule against the EA's own
longterm_average_spill_count_calculated for English overflows (compare_with_ea). Years before
2022 are left out of that comparison so that it sees the same span as Wales.

The other two covariates are the return year's own values, as in the EA returns: spill_hours is
the total duration of all spills in hours (before 12/24 hour counting) and edm_operational_pct the
monitor uptime in percent. model/features.py reads all three under these names.
"""
