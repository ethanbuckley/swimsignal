"""Archived editions of Scottish Water's reported-to-SEPA workbook, read into sw_history's rows.

For backtests on years before 2021 (docs/SCOTLAND-2021-BACKTEST-2026-11.md). Off CI's data path; nothing here
reaches the site. The editions are Internet Archive captures of files Scottish Water no longer links. Contains
Scottish Water data licensed under the Open Government Licence v3.0.

The 2020-2024 edition (March 2025) has the layout sw_history reads. The 2017-2021 edition (December 2022) differs
in three ways, each handled here and nowhere else:

- Its 2017 sheet is named "Overflow Events in 2017 ", with a trailing space.
- Its 2017 rows have no Scottish Water measurement point. The edition's guide says the point "has only been
  included on the returns for 2018 onwards"; 2017 has only SEPA's description ("CSO event"). A 2017 row takes the
  single point its Asset ID has in the same edition's later sheets. Where the Asset ID has no point there, or more
  than one, its 2017 rows keep a site id of their own (the Asset ID + UNSPLIT) and join no overflow.
- Its summary has no grid references. Positions come from the other summaries by measurement point, as
  sw_history.assign_sites finds them.

No edition publishes "No. of Days Data" before 2023, so uptime before then is unknown. "No spills" reads as
"no events" (sw_history.status).
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast.ingest import sw_history as sw

UNSPLIT = " (2017, points not split)"
_EVENTS = re.compile(r"Overflow Events in (\d{4})\s*$")
_POINT_HEADER = "SW Measurement Point Description"


def _events_sheet(year: int, header: list[str], rows: list[tuple]) -> pd.DataFrame:
    """sw_history's reading of one event sheet, plus `no_point`: True for a sheet with no Scottish Water
    measurement point column (2017), whose rows are read with a blank point."""
    if sw._col(header, *sw._POINT) is not None:
        return sw._events_sheet(year, header, rows).assign(no_point=False)
    n = len(header)
    padded = [tuple(r[:n]) + (None,) * (n - len(r[:n])) + (None,) for r in rows]
    return sw._events_sheet(year, [*header, _POINT_HEADER], padded).assign(no_point=True)


def read_workbook(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(summary, rows) of one archived edition, as sw_history.read_workbook returns them, with `no_point`."""
    from openpyxl import load_workbook  # dev dependency; only this off-CI path needs it

    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        summary, rows = None, []
        for name in wb.sheetnames:
            if name.startswith("Overflow Summary"):
                summary = sw._summary(*sw._sheet(wb[name]))
            elif m := _EVENTS.match(name):
                rows.append(_events_sheet(int(m.group(1)), *sw._sheet(wb[name])))
    finally:
        wb.close()
    if summary is None or not rows:
        raise ValueError(f"{path.name}: no summary or event sheets")
    return summary, pd.concat(rows, ignore_index=True)


def fill_points(rows: pd.DataFrame) -> pd.DataFrame:
    """Give each no-point row the single measurement point its Asset ID has in the rows that have one, and
    mark `unsplit` the no-point rows whose Asset ID has none or several."""
    rows = rows.copy()
    known = rows[~rows["no_point"] & (rows["key"] != "")]
    keys = known.groupby("asset_id_published")["key"].nunique()
    single = keys[keys == 1].index
    point = known[known["asset_id_published"].isin(single)].drop_duplicates("asset_id_published")
    point = point.set_index("asset_id_published")[["point", "key"]]
    gap = rows["no_point"].to_numpy(dtype=bool)
    hit = gap & rows["asset_id_published"].isin(single).to_numpy()
    rows.loc[hit, "point"] = rows.loc[hit, "asset_id_published"].map(point["point"]).to_numpy()
    rows.loc[hit, "key"] = rows.loc[hit, "asset_id_published"].map(point["key"]).to_numpy()
    rows["unsplit"] = gap & ~hit
    return rows


def load(path: Path, source: str, other_summaries: list[pd.DataFrame],
         years: list[int] | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(events, yearly, rows) of one archived edition, in sw_history.load's form. Asset IDs map to the
    current ones through `other_summaries` (the current editions) first, then the edition's own summary:
    an archived summary still lists works' points under the works' STW id that later became their own CSO
    id. Only sheet `years` are kept (all when None)."""
    summary, rows = read_workbook(path)
    # A summary without grid references transforms to infinity, not to missing.
    for c in ("lat", "lon"):
        summary[c] = summary[c].where(np.isfinite(summary[c]))
    rows = sw.assign_sites(fill_points(rows), [*other_summaries, summary])
    placed = pd.concat([s for s in (summary, *other_summaries)]).dropna(subset=["lat", "lon"])
    by_key, by_id = placed.drop_duplicates("key").set_index("key"), placed.drop_duplicates("asset_id").set_index("asset_id")
    for c in ("lat", "lon"):
        rows[c] = rows[c].fillna(rows["key"].map(by_key[c])).fillna(rows["site_id"].map(by_id[c]))
    u = rows["unsplit"].to_numpy(dtype=bool)
    rows.loc[u, "site_id"] = rows.loc[u, "asset_id_published"].astype(str) + UNSPLIT
    rows.loc[u, ["lat", "lon"]] = np.nan
    if years is not None:
        rows = rows[rows["year"].isin(years)].reset_index(drop=True)
    ev = sw.events(rows, source)
    return ev, sw.yearly(ev, rows, source), rows.assign(source=source)
