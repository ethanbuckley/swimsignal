"""Compare two event records of the same company and year, counted as spill-days per overflow (any UTC day
an event touches, features.spill_days, the label the spill model trains on), as
docs/NINE-COMPANY-MODEL-TEST-2026-10.md compared United Utilities' Stream and EA files. Off CI:

    uv run python scripts/compare_event_sources.py A.parquet B.parquet --year 2024 [--months 1-12] [--id-a COLUMN]

Both files in the edm_events columns. Prints events and overflows in each, how many overflow ids are
in both, and the spill-days shared, only in A and only in B, first over all ids and then over the ids
in both (so an overflow one file lacks does not count as disagreement on days). --months limits both
to the months one file covers; --id-a reads A's overflow id from another column (rows where it is empty
are dropped), as for the Thames alerts' grid-only ids. No model is run.
"""

from __future__ import annotations

import argparse

import pandas as pd

from dipcast.model.features import spill_days


def days_of(path: str, year: int, months: tuple[int, int], id_col: str = "site_id") -> tuple[pd.DataFrame, pd.DataFrame]:
    ev = pd.read_parquet(path)
    if id_col != "site_id":
        ev = ev.dropna(subset=[id_col]).assign(site_id=lambda d: d[id_col])
    ev = ev[(ev["event_start"].dt.year == year) & ev["event_start"].dt.month.between(*months)]
    d = spill_days(ev)
    d = d[(d["day"].dt.year == year) & d["day"].dt.month.between(*months)]
    return ev, d


def compare(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    m = a.merge(b, on=["site_id", "day"], how="outer", indicator=True)
    n = m["_merge"].value_counts()
    return {"shared": int(n.get("both", 0)), "only_a": int(n.get("left_only", 0)),
            "only_b": int(n.get("right_only", 0))}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--months", default="1-12", help="first-last month, e.g. 1-11")
    p.add_argument("--id-a", default="site_id", help="column of A holding the overflow id")
    args = p.parse_args()
    months = tuple(int(x) for x in args.months.split("-"))
    ev_a, a = days_of(args.a, args.year, months, args.id_a)
    ev_b, b = days_of(args.b, args.year, months)
    ids_a, ids_b = set(ev_a["site_id"]), set(ev_b["site_id"])
    both = ids_a & ids_b
    print(f"A {args.a}: {len(ev_a):,} events, {len(ids_a):,} overflows, {len(a):,} spill-days")
    print(f"B {args.b}: {len(ev_b):,} events, {len(ids_b):,} overflows, {len(b):,} spill-days")
    print(f"overflow ids: {len(both):,} in both, {len(ids_a - ids_b):,} only in A, {len(ids_b - ids_a):,} only in B")
    print("spill-days, all ids:  ", compare(a, b))
    print("spill-days, ids in both:", compare(a[a["site_id"].isin(both)], b[b["site_id"].isin(both)]))


if __name__ == "__main__":
    main()
