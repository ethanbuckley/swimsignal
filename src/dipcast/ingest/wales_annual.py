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

    Amended 4 Oct 2026, after reading the layers' fields and ids and before any count was averaged
    or compared. The averaging above is unchanged; two parts of the uptime plumbing could not work
    as written. (1) The Rivers Trust's 2023 rows number activities in another scheme (seven-digit
    numbers where Dŵr Cymru has 1, 2, 3), so the 2023 uptime join uses the permit reference and
    Dŵr Cymru's asset id (the Rivers Trust's permitReferenceWaSC, Dŵr Cymru's
    Associated_Asset_ID) where that pair names one Rivers Trust row. (2) The Rivers Trust's 2023
    layer holds Dŵr Cymru's uptime in percent and Hafren Dyfrdwy's as fractions, so the
    fraction test is made per company within a layer. Uptime above 100 (one Rivers Trust row in
    2024) is cut to 100.

An overflow is followed across years by its permit reference for Dŵr Cymru (a permit given twice
in one year's layer names no overflow that year: both rows are left out), and by its permit, outlet
grid reference and activity reference for Hafren Dyfrdwy, whose permits cover several outlets.
Its position is the outlet grid reference of its latest return that has one, else the asset's
latitude and longitude. A Dŵr Cymru overflow is matched to the nearest live row whose outlet
(discharge_x_location, discharge_y_location) lies within MATCH_M (50 m); each live row goes to at
most one overflow, nearest pairs first.

The same function, run on the Environment Agency's returns (data/processed/annual_returns.parquet)
over return years 2022 to Y, gives the error of the rule against the EA's own
longterm_average_spill_count_calculated for English overflows (compare_with_ea). Years before
2022 are left out of that comparison so that it sees the same span as Wales.

The other two covariates are the return year's own values, as in the EA returns: spill_hours is
the total duration of all spills in hours (before 12/24 hour counting) and edm_operational_pct the
monitor uptime in percent. model/features.py reads all three under these names.
"""

from __future__ import annotations

import json
import logging

from dipcast import config
from dipcast.arcgis import fetch_all

log = logging.getLogger(__name__)

DC = "https://services3.arcgis.com/KLNF7YxtENPLYVey/arcgis/rest/services"
RT = "https://services3.arcgis.com/Bb8lfThdhugyc4G3/arcgis/rest/services"
DC_LAYERS = {
    2022: f"{DC}/EDM2022_view/FeatureServer/0",
    2023: f"{DC}/EDM_2023_view/FeatureServer/3",          # layer 3: layer 0 answers "Invalid URL"
    2024: f"{DC}/EDM_2024_update_view/FeatureServer/0",   # the resubmitted 2024 return (NRW, 2024 report)
    2025: f"{DC}/EDM_2025/FeatureServer/0",
}
RT_LAYERS = {
    2023: f"{RT}/edm_2023_tidy_final/FeatureServer/0",
    2024: f"{RT}/Storm_Overflow_EDM_Annual_Returns_2024/FeatureServer/0",
    2025: f"{RT}/Event_Duration_Monitoring_Storm_Overflows_2025/FeatureServer/0",
}
LIVE = f"{DC}/Spill_Prod__view/FeatureServer/0"
LIVE_EXTERNAL = f"{DC}/Spill_Prod__External/FeatureServer/0"
LIVE_FIELDS = "GlobalID,asset_name,asset_location,Overflow,Receiving_Water,discharge_x_location,discharge_y_location"
RT_FIELDS = ("waterCompanyName,siteNameEA,siteNameWASC,permitReferenceEA,permitReferenceWaSC,activityReference,"
             "outletDischargeNGRoriginal,recievingWaterName,totalDurationAllSpillsHrs,countedSpills,edmOperationPercent,"
             "longTermAverageSpillCount,Eastings,Northings,Latitude,Longitude,country")
DWR_CYMRU = "Dwr Cymru Welsh Water"      # spelt as the EA's returns and the Rivers Trust spell it
HAFREN_DYFRDWY = "Hafren Dyfrdwy"
RT_WHERE = f"waterCompanyName IN ('{DWR_CYMRU}', '{HAFREN_DYFRDWY}')"
CACHE_DIR = config.CACHE / "wales_annual"
OUT = config.PROCESSED / "wales_annual.parquet"


def _cached(name: str, url: str, refresh: bool, **kw) -> list[dict]:
    """Every row of a layer, from data/cache/wales_annual/<name>.json if it is there and `refresh`
    is false, else read page by page (one request at a time) and saved there."""
    path = CACHE_DIR / f"{name}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())["rows"]
    rows = fetch_all(url, **kw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"source": url, "where": kw.get("where", "1=1"), "rows": rows}, ensure_ascii=False))
    log.info("%s: %d rows from %s", name, len(rows), url)
    return rows


def fetch_raw(refresh: bool = False) -> dict[str, list[dict]]:
    """The raw rows of every source, keyed dc<year>, rt<year>, live and live_external."""
    raw: dict[str, list[dict]] = {}
    for y, url in DC_LAYERS.items():
        raw[f"dc{y}"] = _cached(f"dc{y}", url, refresh, geometry=False)
    for y, url in RT_LAYERS.items():
        raw[f"rt{y}"] = _cached(f"rt{y}", url, refresh, geometry=False, where=RT_WHERE, out_fields=RT_FIELDS)
    raw["live"] = _cached("live", LIVE, refresh, geometry=False, out_fields=LIVE_FIELDS, key="GlobalID")
    raw["live_external"] = _cached("live_external", LIVE_EXTERNAL, refresh, geometry=False,
                                   out_fields="GlobalID,DCWW_ID", key="GlobalID")
    return raw
