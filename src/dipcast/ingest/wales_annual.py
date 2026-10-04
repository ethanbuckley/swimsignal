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
import re

import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import shape

from dipcast import config
from dipcast.arcgis import fetch_all

log = logging.getLogger(__name__)

FIRST_YEAR = 2022
LTA_MIN_UPTIME = 90.0
MATCH_M = 50.0

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
REPORT = config.PROCESSED / "wales_annual_report.json"
OUTSIDE_ENGLAND = config.RAW / "outside_england.json"

# Each standard column and the names Dŵr Cymru's layers give it, year by year (first found wins).
DC_FIELDS = {
    "asset_id": ["Associated_Asset_ID"],
    "site_name": ["Permitted_site_name"],
    "permit": ["NRW_permit_reference", "NRW_permit_reference_", "Permit_Number", "Permit_reference_"],
    "asset_type": ["Storm_discharge___Emergency_Ove", "Storm_discharge___Emergency_Overflow_asset_type_"],
    "receiving_water": ["Receiving__waterbody_name", "Receiving__waterbody_name_"],
    "spills": ["No__of_block_counted_spills___a", "Counted_Spills_using_12_24_bloc",
               "No__of_block_counted_spills___annual__no___"],
    "spill_hours": ["Duration_of_all_spills___annual", "Total_Duration_hours_in_decimal",
                    "Duration_of_all_spills___annual__hrs__"],
    "edm_operational_pct": ["Percentage_complete_data___annu", "Percentage_complete_data___annual_____"],
    "outlet_ngr": ["Outlet_discharge_NGR"],
    "asset_lat": ["Latitude"],
    "asset_lon": ["Longitude"],
}
RT_COLUMNS = {
    "waterCompanyName": "company", "siteNameEA": "site_name", "permitReferenceEA": "permit",
    "permitReferenceWaSC": "asset_id", "activityReference": "activity",
    "outletDischargeNGRoriginal": "outlet_ngr", "recievingWaterName": "receiving_water",
    "countedSpills": "spills", "totalDurationAllSpillsHrs": "spill_hours",
    "edmOperationPercent": "edm_operational_pct", "Eastings": "outlet_e", "Northings": "outlet_n",
    "Latitude": "asset_lat", "Longitude": "asset_lon",
}
YEAR_COLUMNS = ["site_name", "permit", "asset_type", "receiving_water", "spills", "spill_hours",
                "edm_operational_pct", "uptime_source", "source"]
SITE_COLUMNS = ["lat", "lon", "easting", "northing", "pos_source", "outlet_asset_m", "country", "emergency",
                "live_global_id", "live_dcww_id", "live_name", "live_dist_m"]
# What the hindcast (task W4) reads: the names and units model/features.site_static_features expects.
MODEL_COLUMNS = ["site_id", "lat", "lon", "company", "lta_spills", "spill_hours", "edm_operational_pct"]

_TO_BNG = Transformer.from_crs(4326, 27700, always_xy=True)
_TO_WGS = Transformer.from_crs(27700, 4326, always_xy=True)
_GRID = "ABCDEFGHJKLMNOPQRSTUVWXYZ"    # the OS grid's letters: no I
_NGR = re.compile(r"([A-HJ-Z]{2})(\d*)")


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


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def ngr_to_bng(ref) -> tuple[float, float]:
    """Easting and northing in metres of an OS grid reference such as "SO 27675 01786" or
    "SO2767501786": the south-west corner of the square it names, to the metre for ten digits.
    (nan, nan) when it does not parse."""
    if not isinstance(ref, str):
        return np.nan, np.nan
    m = _NGR.fullmatch(re.sub(r"\s+", "", ref).upper())
    if not m or len(m.group(2)) % 2 or not 2 <= len(m.group(2)) <= 10:
        return np.nan, np.nan
    l1, l2 = (_GRID.index(c) for c in m.group(1))
    e100, n100 = ((l1 - 2) % 5) * 5 + l2 % 5, (19 - (l1 // 5) * 5) - l2 // 5
    if not (0 <= e100 <= 6 and 0 <= n100 <= 12):
        return np.nan, np.nan
    d = m.group(2)
    h = len(d) // 2
    scale = 10 ** (5 - h)
    return float(e100 * 100_000 + int(d[:h]) * scale), float(n100 * 100_000 + int(d[h:]) * scale)


def _num(s: pd.Series) -> pd.Series:
    """Numbers from a column that may hold text ("143.75", "N/A", "1,204")."""
    if s.dtype.kind in "iuf":
        return s.astype(float)
    txt = s.astype("string").str.replace(",", "", regex=False).str.strip()
    return pd.to_numeric(txt, errors="coerce").astype("float64")


def _ref(s: pd.Series) -> pd.Series:
    """A reference upper-cased with its spaces removed; empty, "TBC" and "N/A" become missing."""
    out = s.astype("string").str.upper().str.replace(r"\s+", "", regex=True)
    return out.mask(out.isin(["", "TBC", "N/A", "#N/A", "NAN", "NONE"]))


def _activity(s: pd.Series) -> pd.Series:
    """An activity reference as text: 31232090.0 -> "31232090"; missing or "TBC" -> ""."""
    num = pd.to_numeric(s, errors="coerce")
    txt = _ref(s).fillna("")
    return txt.where(num.isna(), num.round().astype("Int64").astype("string")).fillna("")


def uptime_pct(uptime: pd.Series, company: pd.Series) -> pd.Series:
    """Monitor uptime in percent, 0 to 100. Within one layer, a company whose uptime never exceeds
    1 reports fractions, which are multiplied by 100 (the Rivers Trust's 2023 layer holds Hafren
    Dyfrdwy's that way beside Dŵr Cymru's percentages). Values above 100 are cut to 100."""
    u = _num(uptime)
    for c in company.dropna().unique():
        rows = company == c
        if u[rows].notna().any() and u[rows].max() <= 1:
            u[rows] = u[rows] * 100
    return u.clip(0, 100)


def _pick(df: pd.DataFrame, names: list[str]) -> pd.Series:
    for n in names:
        if n in df:
            return df[n]
    return pd.Series(pd.NA, index=df.index, dtype="object")


def _drop_repeats(df: pd.DataFrame, what: str) -> pd.DataFrame:
    """Rows whose site_id is missing or given twice in one layer name no overflow: drop them all."""
    bad = df["site_id"].isna() | df["site_id"].duplicated(keep=False)
    if bad.any():
        log.info("%s: %d rows left out (id missing or repeated)", what, int(bad.sum()))
    return df[~bad]


def parse_dc(rows: list[dict], year: int, source: str = "") -> pd.DataFrame:
    """One Dŵr Cymru annual-return layer as standard columns, one row per overflow."""
    df = pd.DataFrame(rows)
    out = pd.DataFrame({k: _pick(df, v) for k, v in DC_FIELDS.items()}, index=df.index)
    out["company"] = DWR_CYMRU
    out["year"] = year
    out["permit"] = _ref(out["permit"])
    for c in ["spills", "spill_hours", "asset_lat", "asset_lon"]:
        out[c] = _num(out[c])
    out["asset_id"] = _num(out["asset_id"]).round().astype("Int64")
    out["edm_operational_pct"] = uptime_pct(out["edm_operational_pct"], out["company"])
    out["uptime_source"] = np.where(out["edm_operational_pct"].notna(), "layer", None)
    en = [ngr_to_bng(r) for r in out["outlet_ngr"]]
    out["outlet_e"] = [e for e, _ in en]
    out["outlet_n"] = [n for _, n in en]
    out["site_id"] = "DCWW-" + out["permit"]
    out["source"] = source
    return _drop_repeats(out, f"Dwr Cymru {year}")


def parse_rt(rows: list[dict], year: int, company: str = HAFREN_DYFRDWY, source: str = "") -> pd.DataFrame:
    """One company's rows of a Rivers Trust compilation as standard columns. Uptime is put in
    percent across the whole layer read (see uptime_pct) before the company is picked."""
    df = pd.DataFrame(rows)
    out = pd.DataFrame({new: _pick(df, [old]) for old, new in RT_COLUMNS.items()}, index=df.index)
    out["edm_operational_pct"] = uptime_pct(out["edm_operational_pct"], out["company"])
    out = out[out["company"] == company].copy()
    out["year"] = year
    out["asset_type"] = pd.NA
    out["permit"] = _ref(out["permit"])
    out["activity"] = _activity(out["activity"])
    out["outlet_ngr"] = _ref(out["outlet_ngr"])
    for c in ["spills", "spill_hours", "asset_lat", "asset_lon", "outlet_e", "outlet_n"]:
        out[c] = _num(out[c])
    out["asset_id"] = _num(out["asset_id"]).round().astype("Int64")
    en = [ngr_to_bng(r) for r in out["outlet_ngr"]]
    out["outlet_e"] = out["outlet_e"].fillna(pd.Series([e for e, _ in en], index=out.index))
    out["outlet_n"] = out["outlet_n"].fillna(pd.Series([n for _, n in en], index=out.index))
    out["uptime_source"] = np.where(out["edm_operational_pct"].notna(), "rivers_trust", None)
    prefix = "HD" if company == HAFREN_DYFRDWY else "RT"
    parts = pd.concat([out["permit"].fillna("").str.replace("/", "", regex=False),
                       out["outlet_ngr"].fillna(""), out["activity"]], axis=1)
    sid = parts.apply(lambda r: "-".join(p for p in r if p), axis=1)
    out["site_id"] = (prefix + "-" + sid).where(out["outlet_ngr"].notna() | out["permit"].notna())
    out["source"] = source
    return _drop_repeats(out, f"{company} {year} (Rivers Trust)")


def fill_uptime_2023(dc23: pd.DataFrame, rt23_rows: list[dict]) -> pd.DataFrame:
    """Dŵr Cymru's 2023 layer has no uptime. Take it from the Rivers Trust's 2023 compilation
    where the permit reference and Dŵr Cymru's asset id name exactly one Rivers Trust row."""
    df = pd.DataFrame(rt23_rows)
    r = pd.DataFrame({new: _pick(df, [old]) for old, new in RT_COLUMNS.items()}, index=df.index)
    r["edm_operational_pct"] = uptime_pct(r["edm_operational_pct"], r["company"])
    r = r[r["company"] == DWR_CYMRU]
    r = pd.DataFrame({"permit": _ref(r["permit"]), "asset_id": _num(r["asset_id"]).round().astype("Int64"),
                      "rt_pct": r["edm_operational_pct"]})
    r = r.dropna(subset=["permit", "asset_id"])
    r = r[~r.duplicated(["permit", "asset_id"], keep=False)]
    out = dc23.merge(r, on=["permit", "asset_id"], how="left")
    out.index = dc23.index
    fill = out["edm_operational_pct"].isna() & out["rt_pct"].notna()
    out.loc[fill, "edm_operational_pct"] = out.loc[fill, "rt_pct"]
    out.loc[fill, "uptime_source"] = "rivers_trust_2023"
    log.info("Dwr Cymru 2023: uptime from the Rivers Trust for %d of %d rows", int(fill.sum()), len(out))
    return out.drop(columns="rt_pct")


def parse_live(rows: list[dict], external: list[dict]) -> pd.DataFrame:
    """Dŵr Cymru's live rows: id, DCWW_ID from the twin layer, name, overflow kind and outlet (BNG)."""
    df = pd.DataFrame(rows)
    ext = pd.DataFrame(external, columns=["GlobalID", "DCWW_ID"]).drop_duplicates("GlobalID")
    df = df.merge(ext, on="GlobalID", how="left")
    return pd.DataFrame({"global_id": df["GlobalID"], "dcww_id": df["DCWW_ID"], "name": df.get("asset_name"),
                         "overflow": df.get("Overflow"), "easting": _num(df["discharge_x_location"]),
                         "northing": _num(df["discharge_y_location"])})


# ---------------------------------------------------------------------------
# The long-term average (the rule in the module docstring)
# ---------------------------------------------------------------------------

def long_term_average(df: pd.DataFrame, first_year: int = FIRST_YEAR,
                      min_uptime: float = LTA_MIN_UPTIME) -> pd.DataFrame:
    """`df` with one row per (site_id, year) and columns spills and edm_operational_pct. Returns
    its rows from `first_year` on, with lta_spills, lta_years and lta_basis as the module
    docstring's rule defines them: for year Y, the mean count over years first_year..Y with a
    count and uptime >= min_uptime ("uptime90"); else over the years with a count ("any_uptime");
    else missing ("none"). Raises on a repeated (site_id, year)."""
    if df.duplicated(["site_id", "year"]).any():
        raise ValueError("long_term_average needs one row per site_id and year")
    d = df[df["year"] >= first_year].sort_values(["site_id", "year"]).copy()
    has = d["spills"].notna()
    good = has & (d["edm_operational_pct"] >= min_uptime)      # unknown uptime is never >= 90
    g = d["site_id"]
    sum_good = d["spills"].where(good, 0.0).groupby(g).cumsum()
    n_good = good.astype(int).groupby(g).cumsum()
    sum_all = d["spills"].where(has, 0.0).groupby(g).cumsum()
    n_all = has.astype(int).groupby(g).cumsum()
    d["lta_spills"] = np.where(n_good > 0, sum_good / n_good.where(n_good > 0, 1),
                               np.where(n_all > 0, sum_all / n_all.where(n_all > 0, 1), np.nan))
    d["lta_years"] = np.where(n_good > 0, n_good, n_all).astype(int)
    d["lta_basis"] = np.select([n_good > 0, n_all > 0], ["uptime90", "any_uptime"], "none")
    return d


# ---------------------------------------------------------------------------
# Positions, country and the live match
# ---------------------------------------------------------------------------

def site_positions(long: pd.DataFrame) -> pd.DataFrame:
    """One position per site_id: the outlet of its latest return that has one, else the asset's
    latitude and longitude in its latest return. Columns site_id, easting, northing, lat, lon,
    pos_source ("outlet" or "asset") and outlet_asset_m, the distance from the outlet to the asset's
    latitude and longitude (a large one hints at a mistyped grid reference)."""
    d = long.sort_values("year")
    out = d.dropna(subset=["outlet_e", "outlet_n"]).groupby("site_id")[["outlet_e", "outlet_n"]].last()
    out = out.rename(columns={"outlet_e": "easting", "outlet_n": "northing"}).assign(pos_source="outlet")
    asset = d.dropna(subset=["asset_lat", "asset_lon"]).groupby("site_id")[["asset_lat", "asset_lon"]].last()
    ae, an = _TO_BNG.transform(asset["asset_lon"].to_numpy(), asset["asset_lat"].to_numpy())
    asset = pd.DataFrame({"easting": ae, "northing": an, "pos_source": "asset"}, index=asset.index)
    out = pd.concat([out, asset[~asset.index.isin(out.index)]])
    a = asset.reindex(out.index)
    out["outlet_asset_m"] = np.where(out["pos_source"] == "outlet",
                                     np.hypot(out["easting"] - a["easting"], out["northing"] - a["northing"]), np.nan)
    lon, lat = _TO_WGS.transform(out["easting"].to_numpy(), out["northing"].to_numpy())
    out["lat"], out["lon"] = lat, lon
    return out.rename_axis("site_id").reset_index()


def wales_shape():
    """Wales (with Scotland) from data/raw/outside_england.json, without the island of Ireland."""
    g = json.loads(OUTSIDE_ENGLAND.read_text())
    polys = list(shape(g["geometry"]).geoms)
    return shapely.union_all([p for p, part in zip(polys, g["parts"], strict=True) if part == "wales_scotland"])


def country_of(lat: np.ndarray, lon: np.ndarray, wales=None) -> np.ndarray:
    """ "Wales" inside the outside-England shape south of 54.5° N, else "England"."""
    wales = wales_shape() if wales is None else wales
    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    inside = shapely.contains_xy(wales, lon, lat) & (lat < 54.5)
    return np.where(np.isnan(lat), None, np.where(inside, "Wales", "England"))


def match_live(sites: pd.DataFrame, live: pd.DataFrame, max_m: float = MATCH_M) -> pd.DataFrame:
    """Each site (site_id, easting, northing) to the nearest live row (global_id, easting,
    northing) within max_m, one to one, nearest pairs first. Returns site_id, live_global_id,
    live_dist_m for the matched sites."""
    s = sites.dropna(subset=["easting", "northing"]).reset_index(drop=True)
    lv = live.dropna(subset=["easting", "northing"]).reset_index(drop=True)
    cols = ["site_id", "live_global_id", "live_dist_m"]
    if s.empty or lv.empty:
        return pd.DataFrame(columns=cols)
    a, b = cKDTree(s[["easting", "northing"]].to_numpy()), cKDTree(lv[["easting", "northing"]].to_numpy())
    pairs = a.sparse_distance_matrix(b, max_m, output_type="ndarray")
    pairs = pd.DataFrame({"i": pairs["i"], "j": pairs["j"], "d": pairs["v"]}).sort_values(["d", "i", "j"])
    used_i, used_j, out = set(), set(), []
    for i, j, d in pairs.itertuples(index=False):
        if i in used_i or j in used_j:
            continue
        used_i.add(i)
        used_j.add(j)
        out.append((s.at[i, "site_id"], lv.at[j, "global_id"], float(d)))
    return pd.DataFrame(out, columns=cols)


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------

def build(raw: dict[str, list[dict]], wales=None) -> pd.DataFrame:
    """The per-overflow, per-year table from the raw rows (see fetch_raw): Dŵr Cymru's layers and
    Hafren Dyfrdwy's Rivers Trust rows, with the long-term average, one position per overflow,
    its country and its live row."""
    frames = []
    for y in sorted(DC_LAYERS):
        if f"dc{y}" not in raw:
            continue
        d = parse_dc(raw[f"dc{y}"], y, DC_LAYERS[y])
        if y == 2023 and "rt2023" in raw:
            d = fill_uptime_2023(d, raw["rt2023"])
        frames.append(d)
    for y in sorted(RT_LAYERS):
        if f"rt{y}" in raw:
            frames.append(parse_rt(raw[f"rt{y}"], y, HAFREN_DYFRDWY, RT_LAYERS[y]))
    long = pd.concat(frames, ignore_index=True)
    long["uptime_source"] = long["uptime_source"].fillna("none")
    lta = long_term_average(long)
    pos = site_positions(long)
    pos["country"] = country_of(pos["lat"].to_numpy(), pos["lon"].to_numpy(), wales)
    asset_type = long.sort_values("year").groupby("site_id")["asset_type"].last()
    pos["emergency"] = pos["site_id"].map(asset_type).astype("string").str.contains(
        r"\bEO\b|Emergency", case=False, regex=True).fillna(False).astype(bool)
    live = parse_live(raw.get("live", []), raw.get("live_external", [])) if raw.get("live") else None
    if live is not None:
        m = match_live(pos[pos["site_id"].str.startswith("DCWW-")], live)
        m = m.merge(live.rename(columns={"global_id": "live_global_id", "dcww_id": "live_dcww_id",
                                         "name": "live_name"})[["live_global_id", "live_dcww_id", "live_name"]],
                    on="live_global_id", how="left")
        pos = pos.merge(m, on="site_id", how="left")
    for c in ["live_global_id", "live_dcww_id", "live_name", "live_dist_m"]:
        if c not in pos:
            pos[c] = np.nan if c == "live_dist_m" else None
    out = lta[["site_id", "company", "year", *YEAR_COLUMNS, "lta_spills", "lta_years", "lta_basis"]]
    out = out.merge(pos[["site_id", *SITE_COLUMNS]], on="site_id", how="left")
    out["year"] = out["year"].astype(int)
    return out.sort_values(["company", "site_id", "year"]).reset_index(drop=True)


def covariates(wa: pd.DataFrame, year: int) -> pd.DataFrame:
    """The covariates of return year `year`, in MODEL_COLUMNS plus country, emergency and the live
    row. A hindcast of year Y reads year Y - 1, as scripts/train.py does with the EA returns."""
    d = wa[wa["year"] == year]
    return d[[*MODEL_COLUMNS, "country", "emergency", "live_global_id", "live_dcww_id", "lta_basis"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Checks: the rule against the EA's values, and the report
# ---------------------------------------------------------------------------

def _errors(ours: pd.Series, theirs: pd.Series) -> dict:
    ok = ours.notna() & theirs.notna()
    a, b = ours[ok].astype(float), theirs[ok].astype(float)
    if not len(a):
        return {"n": 0}
    err = a - b
    return {
        "n": len(a),
        "mean_abs_error": round(float(err.abs().mean()), 3),
        "median_abs_error": round(float(err.abs().median()), 3),
        "median_error": round(float(err.median()), 3),
        "share_within_0_5": round(float((err.abs() <= 0.5).mean()), 4),
        "share_within_10pct": round(float((err.abs() <= np.maximum(0.5, 0.1 * b.abs())).mean()), 4),
        "mean_abs_error_log1p": round(float((np.log1p(a.clip(lower=0)) - np.log1p(b.clip(lower=0))).abs().mean()), 4),
        "spearman": round(float(a.corr(b, method="spearman")), 4) if len(a) > 2 else None,
    }


def compare_with_ea(ar: pd.DataFrame, years=(2022, 2023, 2024, 2025)) -> dict:
    """The rule run on the EA's returns from 2022, against the EA's own long-term average in the
    same return year. Rows with no site_id, or whose (site_id, year) repeats, are left out first:
    they name no single overflow. Returns, per return year, the errors over all overflows with
    both values, by the rule's basis, and for Dŵr Cymru's English overflows."""
    a = ar.dropna(subset=["site_id", "year"]).copy()
    a["year"] = a["year"].astype(int)
    rep = a.duplicated(["site_id", "year"], keep=False)
    a = a[~rep]
    lta = long_term_average(a[["site_id", "year", "company", "spills", "edm_operational_pct", "lta_spills"]]
                            .rename(columns={"lta_spills": "ea_lta"}))
    out = {"left_out_repeated_rows": int(rep.sum()), "years": {}}
    for y in years:
        d = lta[lta["year"] == y]
        row = {"all": _errors(d["lta_spills"], d["ea_lta"]),
               "dwr_cymru_england": _errors(d.loc[d["company"] == DWR_CYMRU, "lta_spills"],
                                            d.loc[d["company"] == DWR_CYMRU, "ea_lta"])}
        for basis in ("uptime90", "any_uptime"):
            sel = d["lta_basis"] == basis
            row[basis] = _errors(d.loc[sel, "lta_spills"], d.loc[sel, "ea_lta"])
        row["by_years_averaged"] = {str(k): _errors(g["lta_spills"], g["ea_lta"]) for k, g in d.groupby("lta_years")}
        # A reference, not the rule: the return year's own count taken as the long-term average.
        row["reference_this_year_count"] = _errors(d["spills"], d["ea_lta"])
        row["ea_lta_missing"] = int(d["ea_lta"].isna().sum())
        out["years"][str(y)] = row
    return out


def check_against_ea_counts(wa_table: pd.DataFrame, ar: pd.DataFrame, max_m: float = MATCH_M) -> dict:
    """Dŵr Cymru's own layers against the EA's returns for the same English overflows: each
    Dŵr Cymru site in England is paired with the nearest EA Dŵr Cymru overflow within max_m (one to
    one), and their counts and hours compared year by year. Says whether the two publish the same
    numbers, so whether the Welsh layers count spills as the EA's returns do."""
    ea = ar[(ar["company"] == DWR_CYMRU) & ar["site_id"].notna()].dropna(subset=["ngr_easting", "ngr_northing"])
    ea_sites = ea.drop_duplicates("site_id")[["site_id", "ngr_easting", "ngr_northing"]].rename(
        columns={"site_id": "global_id", "ngr_easting": "easting", "ngr_northing": "northing"})
    dc = wa_table[(wa_table["company"] == DWR_CYMRU) & (wa_table["country"] == "England")]
    m = match_live(dc.drop_duplicates("site_id")[["site_id", "easting", "northing"]], ea_sites, max_m)
    m = m.rename(columns={"live_global_id": "ea_site_id"})
    pairs = dc.merge(m[["site_id", "ea_site_id"]], on="site_id").merge(
        ea[["site_id", "year", "spills", "spill_hours"]].astype({"year": int}).rename(
            columns={"site_id": "ea_site_id", "spills": "ea_spills", "spill_hours": "ea_hours"}),
        on=["ea_site_id", "year"])
    out = {"dc_sites_in_england": int(dc["site_id"].nunique()), "paired_with_ea": len(m), "years": {}}
    for y, g in pairs.groupby("year"):
        ok = g["spills"].notna() & g["ea_spills"].notna()
        okh = g["spill_hours"].notna() & g["ea_hours"].notna()
        out["years"][str(y)] = {
            "pairs_with_both_counts": int(ok.sum()),
            "counts_equal": int((g.loc[ok, "spills"] == g.loc[ok, "ea_spills"]).sum()),
            "counts_within_1": int(((g.loc[ok, "spills"] - g.loc[ok, "ea_spills"]).abs() <= 1).sum()),
            "hours_within_1": int(((g.loc[okh, "spill_hours"] - g.loc[okh, "ea_hours"]).abs() <= 1).sum()),
            "pairs_with_both_hours": int(okh.sum()),
        }
    return out


def report(wa: pd.DataFrame, raw: dict[str, list[dict]] | None = None) -> dict:
    """Rows by company and year, data coverage, the live match rates and the lta basis."""
    rep: dict = {}
    by = wa.groupby(["company", "year"])
    rep["rows"] = {f"{c} {y}": int(n) for (c, y), n in by.size().items()}
    rep["with_spills"] = {f"{c} {y}": int(n) for (c, y), n in by["spills"].count().items()}
    rep["with_uptime"] = {f"{c} {y}": int(n) for (c, y), n in by["edm_operational_pct"].count().items()}
    rep["uptime_ge_90"] = {f"{c} {y}": int(n) for (c, y), n in
                           by["edm_operational_pct"].apply(lambda s: int((s >= LTA_MIN_UPTIME).sum())).items()}
    rep["uptime_source"] = {f"{c} {y} {s}": int(n) for (c, y, s), n in
                            wa.groupby(["company", "year", "uptime_source"]).size().items()}
    rep["lta_basis"] = {f"{c} {y} {b}": int(n) for (c, y, b), n in
                        wa.groupby(["company", "year", "lta_basis"]).size().items()}
    sites = wa.drop_duplicates("site_id")
    rep["sites"] = {c: int(n) for c, n in sites.groupby("company").size().items()}
    rep["sites_by_country"] = {f"{c} {k}": int(n) for (c, k), n in sites.groupby(["company", "country"]).size().items()}
    rep["sites_by_position"] = {f"{c} {k}": int(n) for (c, k), n in sites.groupby(["company", "pos_source"]).size().items()}
    rep["emergency_sites"] = int(sites["emergency"].sum())
    rep["sites_outlet_over_5km_from_asset"] = int((sites["outlet_asset_m"] > 5000).sum())
    rep["lta_years"] = {f"{c} {y} {k}": int(n) for (c, y, k), n in
                        wa.groupby(["company", "year", "lta_years"]).size().items()}
    dc = wa[wa["company"] == DWR_CYMRU]
    # Overflows whose id is last seen in 2023 next to one first seen in 2024: a renumbered permit
    # starts its average again (inferred; the layers do not link old and new references).
    span = dc.groupby("site_id")["year"].agg(["min", "max"])
    old = sites.set_index("site_id").loc[span.index[span["max"] <= 2023], ["easting", "northing"]].dropna()
    new = sites.set_index("site_id").loc[span.index[span["min"] >= 2024], ["easting", "northing"]].dropna()
    near = (cKDTree(new.to_numpy()).query(old.to_numpy())[0] <= 10).sum() if len(old) and len(new) else 0
    rep["dc_ids_ending_2023_starting_2024"] = {"last_seen_2023": len(old), "first_seen_2024": len(new),
                                              "last_seen_2023_with_new_id_within_10m": int(near)}
    rep["dc_rows_matched_to_live"] = {str(y): [int(g["live_global_id"].notna().sum()), len(g)]
                                      for y, g in dc.groupby("year")}
    dcs = sites[sites["company"] == DWR_CYMRU]
    rep["dc_sites_matched_to_live"] = [int(dcs["live_global_id"].notna().sum()), len(dcs)]
    if raw and raw.get("live"):
        live = parse_live(raw["live"], raw.get("live_external", []))
        rep["live_rows"] = len(live)
        rep["live_rows_matched"] = int(live["global_id"].isin(dcs["live_global_id"]).sum())
        # Nearest-outlet distances without the one-to-one step, for comparison with the plan's 2.2.
        latest = parse_dc(raw["dc2025"], 2025) if raw.get("dc2025") else None
        if latest is not None:
            pts = latest.dropna(subset=["outlet_e", "outlet_n"])[["outlet_e", "outlet_n"]].to_numpy()
            lv = live.dropna(subset=["easting", "northing"])
            dist, _ = cKDTree(pts).query(lv[["easting", "northing"]].to_numpy())
            rep["live_rows_with_2025_outlet_within"] = {f"{m} m": int((dist <= m).sum()) for m in (10, 50, 200)}
        mm = live.merge(dcs[["live_global_id", "country", "emergency"]], left_on="global_id",
                        right_on="live_global_id", how="left")
        rep["live_rows_matched_by_kind"] = {str(k): [int(g["live_global_id"].notna().sum()), len(g)]
                                            for k, g in mm.groupby("overflow")}
    return rep
