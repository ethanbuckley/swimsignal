"""Welsh annual returns (ingest/wales_annual.py), on synthetic rows with the field names of Dŵr
Cymru's layers, the Rivers Trust's compilations and the live layer. No real Dŵr Cymru row is kept
here: its data carries no licence."""

import math

import numpy as np
import pandas as pd
import pytest

from dipcast.ingest import wales_annual as wa

# Field names as each Dŵr Cymru layer spells them (read from the layers on 4 Oct 2026).
NAMES = {
    2022: {"permit": "NRW_permit_reference", "spills": "No__of_block_counted_spills___a",
           "hours": "Duration_of_all_spills___annual", "pct": "Percentage_complete_data___annu"},
    2023: {"permit": "Permit_Number", "spills": "Counted_Spills_using_12_24_bloc",
           "hours": "Total_Duration_hours_in_decimal", "pct": None},
    2024: {"permit": "NRW_permit_reference_", "spills": "No__of_block_counted_spills___a",
           "hours": "Duration_of_all_spills___annual", "pct": "Percentage_complete_data___annu"},
    2025: {"permit": "Permit_reference_", "spills": "No__of_block_counted_spills___annual__no___",
           "hours": "Duration_of_all_spills___annual__hrs__", "pct": "Percentage_complete_data___annual_____"},
}


def dc_row(year, permit, spills, hours, pct=None, asset=1001, outlet="SO 30000 20000", kind="CSO on sewer network",
           lat=51.8, lon=-3.0):
    n = NAMES[year]
    row = {"Associated_Asset_ID": asset, "Permitted_site_name": f"Test site {permit}", n["permit"]: permit,
           n["spills"]: spills, n["hours"]: hours, "Latitude": lat, "Longitude": lon,
           "Receiving__waterbody_name_": "Afon Test"}
    if n["pct"]:
        row[n["pct"]] = pct
    if year != 2023:
        row["Outlet_discharge_NGR"] = outlet
        row["Storm_discharge___Emergency_Overflow_asset_type_" if year == 2025 else "Storm_discharge___Emergency_Ove"] = kind
    return row


def rt_row(company, permit, spills, pct, asset=None, activity=None, ngr="SJ1000010000", e=310000, n=310000):
    return {"waterCompanyName": company, "siteNameEA": f"RT {permit}", "permitReferenceEA": permit,
            "permitReferenceWaSC": asset, "activityReference": activity, "outletDischargeNGRoriginal": ngr,
            "countedSpills": spills, "totalDurationAllSpillsHrs": 10.0 * (spills or 0), "edmOperationPercent": pct,
            "Eastings": e, "Northings": n, "Latitude": 52.7, "Longitude": -3.3}


def test_grid_references_parse_with_and_without_spaces():
    assert wa.ngr_to_bng("SO 27675 01786") == (327675.0, 201786.0)
    assert wa.ngr_to_bng("SO2767501786") == (327675.0, 201786.0)
    assert wa.ngr_to_bng("SJ1280725592") == (312807.0, 325592.0)
    assert wa.ngr_to_bng("ST 3003 9591") == (330030.0, 195910.0)
    assert wa.ngr_to_bng("SM8109805719") == (181098.0, 205719.0)
    for bad in (None, "", "SO123", "IO1234", "not a ref", 12.5):
        assert all(math.isnan(v) for v in wa.ngr_to_bng(bad))


def test_rule_averages_years_with_uptime_of_90_and_counts_unknown_uptime_as_below():
    df = pd.DataFrame([
        # A: 2023's uptime is unknown and 2024's is 50%, so neither counts.
        ("A", 2021, 99, 100.0), ("A", 2022, 10, 95.0), ("A", 2023, 20, np.nan), ("A", 2024, 30, 50.0),
        ("A", 2025, 40, 92.0),
        # B: no year reaches 90%, so every year with a count is averaged.
        ("B", 2022, 5, 40.0), ("B", 2023, 15, 80.0), ("B", 2024, np.nan, 99.0),
        # C: no count at all.
        ("C", 2024, np.nan, 100.0),
        # D: a later good year replaces the low-uptime fallback.
        ("D", 2022, 2, 10.0), ("D", 2023, 8, 90.0),
    ], columns=["site_id", "year", "spills", "edm_operational_pct"])
    out = wa.long_term_average(df).set_index(["site_id", "year"])
    assert 2021 not in out.loc["A"].index
    assert out.loc[("A", 2022), "lta_spills"] == 10 and out.loc[("A", 2022), "lta_basis"] == "uptime90"
    assert out.loc[("A", 2023), "lta_spills"] == 10 and out.loc[("A", 2024), "lta_spills"] == 10
    assert out.loc[("A", 2025), "lta_spills"] == 25 and out.loc[("A", 2025), "lta_years"] == 2
    assert out.loc[("B", 2022), "lta_spills"] == 5 and out.loc[("B", 2022), "lta_basis"] == "any_uptime"
    assert out.loc[("B", 2023), "lta_spills"] == 10 and out.loc[("B", 2024), "lta_spills"] == 10
    assert out.loc[("B", 2024), "lta_years"] == 2
    assert math.isnan(out.loc[("C", 2024), "lta_spills"]) and out.loc[("C", 2024), "lta_basis"] == "none"
    assert out.loc[("D", 2022), "lta_basis"] == "any_uptime" and out.loc[("D", 2023), "lta_spills"] == 8
    with pytest.raises(ValueError):
        wa.long_term_average(pd.concat([df, df.head(1)]))


def test_uptime_fractions_are_found_per_company_and_capped():
    u = pd.Series([99.0, 45.5, 0.998, 0.5, 119.4])
    c = pd.Series([wa.DWR_CYMRU, wa.DWR_CYMRU, wa.HAFREN_DYFRDWY, wa.HAFREN_DYFRDWY, "Other"])
    assert wa.uptime_pct(u, c).round(1).tolist() == [99.0, 45.5, 99.8, 50.0, 100.0]


def test_dc_layer_reads_text_numbers_and_drops_a_permit_given_twice():
    rows = [dc_row(2022, "aa 0009401", "40", "143.75", 100), dc_row(2022, "AA0009701", "N/A", "1,204.5", 99.4),
            dc_row(2022, "BB3690ZP", "3", "2", 90), dc_row(2022, "bb3690zp", "3", "2", 90)]
    d = wa.parse_dc(rows, 2022)
    assert d["site_id"].tolist() == ["DCWW-AA0009401", "DCWW-AA0009701"]
    assert d["spills"].tolist()[0] == 40 and math.isnan(d["spills"].tolist()[1])
    assert d["spill_hours"].tolist() == [143.75, 1204.5]
    assert d[["outlet_e", "outlet_n"]].iloc[0].tolist() == [330000.0, 220000.0]


def test_2023_uptime_comes_from_the_rivers_trust_by_permit_and_asset_id():
    dc23 = wa.parse_dc([dc_row(2023, "AA0009401", 46, 89.75, asset=72282), dc_row(2023, "AA0009701", 56, 175.5, asset=32155),
                        dc_row(2023, "AA0010901", 3, 1.0, asset=32135)], 2023)
    rt = [rt_row(wa.DWR_CYMRU, "AA0009401", 46, 99.67, asset=72282, activity=5630104),
          rt_row(wa.DWR_CYMRU, "AA0009701", 56, 99.2, asset=99999),                      # asset id differs
          rt_row(wa.DWR_CYMRU, "AA0010901", 3, 80.0, asset=32135), rt_row(wa.DWR_CYMRU, "AA0010901", 3, 70.0, asset=32135),
          rt_row(wa.HAFREN_DYFRDWY, "S/01/1/O", 5, 0.9)]
    out = wa.fill_uptime_2023(dc23, rt).set_index("permit")
    assert out.loc["AA0009401", "edm_operational_pct"] == 99.67
    assert out.loc["AA0009401", "uptime_source"] == "rivers_trust_2023"
    assert math.isnan(out.loc["AA0009701", "edm_operational_pct"])          # no match
    assert math.isnan(out.loc["AA0010901", "edm_operational_pct"])          # two Rivers Trust rows: ambiguous


def test_hafren_dyfrdwy_rows_keep_one_id_across_years_and_percent_uptime():
    y23 = [rt_row(wa.HAFREN_DYFRDWY, "S/01/07393/O", 23, 0.95, activity="TBC", ngr="SJ2301907647"),
           rt_row(wa.HAFREN_DYFRDWY, "S/01/07393/O", 15, 1.0, activity="33060100", ngr="SJ2301907647"),
           rt_row(wa.DWR_CYMRU, "AA1", 4, 97.0)]
    y25 = [rt_row(wa.HAFREN_DYFRDWY, "S/01/07393/O", 12, 99.0, activity=None, ngr="SJ 23019 07647"),
           rt_row(wa.HAFREN_DYFRDWY, "S/01/07393/O", 13, 98.0, activity=33060100.0, ngr="SJ2301907647")]
    a, b = wa.parse_rt(y23, 2023), wa.parse_rt(y25, 2025)
    assert len(a) == 2 and set(a["site_id"]) == set(b["site_id"])
    assert "HD-S0107393O-SJ2301907647-33060100" in set(a["site_id"])
    assert a["edm_operational_pct"].tolist() == [95.0, 100.0]


def test_live_match_is_one_to_one_nearest_first_within_50_m():
    sites = pd.DataFrame({"site_id": ["a", "b", "c", "d"], "easting": [0.0, 10.0, 500.0, np.nan],
                          "northing": [0.0, 0.0, 0.0, 0.0]})
    live = pd.DataFrame({"global_id": ["L1", "L2", "L3"], "easting": [12.0, 549.0, 1000.0], "northing": [0.0, 0.0, 0.0]})
    m = wa.match_live(sites, live).set_index("site_id")
    assert m.loc["b", "live_global_id"] == "L1" and m.loc["b", "live_dist_m"] == 2.0
    assert "a" not in m.index                     # L1 went to the nearer overflow
    assert m.loc["c", "live_global_id"] == "L2"   # 49 m
    assert "d" not in m.index


def fixture_raw():
    """Three Dŵr Cymru overflows over four years, one Hafren Dyfrdwy overflow, and three live rows."""
    welsh, english = "SO 10000 20000", "SO 50000 40000"       # near Brecon; near Hereford
    raw = {
        "dc2022": [dc_row(2022, "AA1", "10", "50", 95, asset=1, outlet=welsh), dc_row(2022, "AA2", "60", "300", 99, asset=2,
                   outlet=english, lat=52.06, lon=-2.72), dc_row(2022, "AA3", "1", "0.5", 20, asset=3, outlet="SO 10100 20000",
                   kind="EO at pumping station")],
        "dc2023": [dc_row(2023, "AA1", 20, 80, asset=1), dc_row(2023, "AA2", 70, 320, asset=2)],
        "dc2024": [dc_row(2024, "AA1", "30", "90", 50, asset=1, outlet=welsh), dc_row(2024, "AA2", "80", "400", 98,
                   asset=2, outlet=english), dc_row(2024, "AA3", "2", "1", 30, asset=3, outlet="SO 10100 20000",
                   kind="EO at pumping station")],
        "dc2025": [dc_row(2025, "AA1", 40, 120.5, 92, asset=11, outlet=welsh), dc_row(2025, "AA2", 90, 410, 97, asset=12,
                   outlet=english)],
        "rt2023": [rt_row(wa.DWR_CYMRU, "AA1", 20, 99.0, asset=1), rt_row(wa.DWR_CYMRU, "AA2", 70, 60.0, asset=2),
                   rt_row(wa.HAFREN_DYFRDWY, "S/01/1/O", 8, 0.97, activity=5, ngr="SJ1280725592")],
        "rt2024": [rt_row(wa.HAFREN_DYFRDWY, "S/01/1/O", 12, 99.0, activity=5, ngr="SJ1280725592", e=312807, n=325592)],
        "rt2025": [rt_row(wa.HAFREN_DYFRDWY, "S/01/1/O", 16, 85.0, activity=5, ngr="SJ1280725592", e=312807, n=325592)],
        "live": [{"GlobalID": "g1", "asset_name": "Live 1", "Overflow": "Storm", "discharge_x_location": 310005,
                  "discharge_y_location": 220000},
                 {"GlobalID": "g2", "asset_name": "Live 2", "Overflow": "Storm", "discharge_x_location": 350000,
                  "discharge_y_location": 240030},
                 {"GlobalID": "g3", "asset_name": "Live 3", "Overflow": "Emergency", "discharge_x_location": 300000,
                  "discharge_y_location": 300000}],
        "live_external": [{"GlobalID": "g1", "DCWW_ID": "DCWW1"}, {"GlobalID": "g2", "DCWW_ID": "DCWW2"}],
    }
    return raw


def test_build_gives_the_model_columns_lta_country_and_live_row():
    t = wa.build(fixture_raw())
    assert set(wa.MODEL_COLUMNS) <= set(t.columns)
    assert t.groupby("company").size().to_dict() == {wa.DWR_CYMRU: 10, wa.HAFREN_DYFRDWY: 3}
    a1 = t[t["site_id"] == "DCWW-AA1"].set_index("year")
    # 2022 10 at 95%; 2023 20 at 99% (from the Rivers Trust); 2024 30 at 50%; 2025 40 at 92%.
    assert a1["lta_spills"].tolist() == [10.0, 15.0, 15.0, (10 + 20 + 40) / 3]
    assert a1.loc[2023, "uptime_source"] == "rivers_trust_2023"
    assert a1.loc[2025, "spill_hours"] == 120.5 and a1.loc[2025, "edm_operational_pct"] == 92
    assert (a1["live_global_id"] == "g1").all() and (a1["live_dcww_id"] == "DCWW1").all()
    assert (a1["country"] == "Wales").all() and (a1["pos_source"] == "outlet").all()
    a2 = t[t["site_id"] == "DCWW-AA2"].iloc[0]
    assert a2["country"] == "England" and a2["live_global_id"] == "g2" and a2["live_dist_m"] == 30.0
    a3 = t[t["site_id"] == "DCWW-AA3"]
    assert a3["emergency"].all() and a3["live_global_id"].isna().all()   # g1 went to AA1, 5 m away
    assert a3["lta_basis"].tolist() == ["any_uptime", "any_uptime"] and a3["lta_spills"].tolist() == [1.0, 1.5]
    hd = t[t["company"] == wa.HAFREN_DYFRDWY].set_index("year")
    assert hd["edm_operational_pct"].tolist() == [97.0, 99.0, 85.0]
    assert hd["lta_spills"].tolist() == [8.0, 10.0, 10.0]
    assert hd["live_global_id"].isna().all() and (hd["country"] == "Wales").all()
    cov = wa.covariates(t, 2024)
    assert cov.columns[:7].tolist() == wa.MODEL_COLUMNS and len(cov) == 4
    rep = wa.report(t, fixture_raw())
    assert rep["dc_sites_matched_to_live"] == [2, 3] and rep["live_rows_matched"] == 2


def test_compare_with_ea_leaves_out_repeated_rows_and_scores_the_rule():
    ar = pd.DataFrame([
        ("X", wa.DWR_CYMRU, 2022, 10, 95.0, 10.0), ("X", wa.DWR_CYMRU, 2023, 20, 95.0, 15.0),
        ("Y", "Thames Water", 2022, 4, 99.0, 6.0), ("Y", "Thames Water", 2023, 8, 99.0, 9.0),
        ("Z", "Thames Water", 2023, 1, 99.0, 1.0), ("Z", "Thames Water", 2023, 2, 99.0, 1.0),
        (None, "Thames Water", 2023, 3, 99.0, 3.0), ("Y", "Thames Water", 2021, 100, 99.0, None),
    ], columns=["site_id", "company", "year", "spills", "edm_operational_pct", "lta_spills"])
    out = wa.compare_with_ea(ar, years=(2023,))
    assert out["left_out_repeated_rows"] == 2
    y = out["years"]["2023"]
    # X: 15 vs 15. Y: 6 vs 9 (2021 is not used).
    assert y["all"]["n"] == 2 and y["all"]["mean_abs_error"] == 1.5 and y["all"]["share_within_0_5"] == 0.5
    assert y["dwr_cymru_england"]["n"] == 1 and y["dwr_cymru_england"]["mean_abs_error"] == 0.0
