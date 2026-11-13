"""Compare two event records of the same company and year, counted as spill-days per overflow (any UTC day
an event touches, features.spill_days, the label the spill model trains on), as
docs/NINE-COMPANY-MODEL-TEST-2026-10.md compared United Utilities' Stream and EA files. Off CI:

    uv run python scripts/compare_event_sources.py A.parquet B.parquet --year 2024 [--months 1-12] [--id-a COLUMN]

Both files in the edm_events columns. Prints the events starting in the window, the overflows with a
spill-day in it, how many overflow ids are in both, and the spill-days shared, only in A and only in
B, first over all ids and then over the ids in both (so an overflow one file lacks does not count as
disagreement on days). --months limits both
to the months one file covers; --id-a reads A's overflow id from another column (rows where it is empty
are dropped), as for the Thames alerts' grid-only ids. --offsets also prints, for A's events at ids in both, how far
the nearest B start at the same overflow lies (within two hours): the share at 0, at +1 hour and at -1 hour shows
whether one record is in local time. No model is run.
"""

from __future__ import annotations

import argparse

import pandas as pd

from dipcast.model.features import spill_days


def days_of(path: str, year: int, months: tuple[int, int], id_col: str = "site_id") -> tuple[pd.DataFrame, pd.DataFrame]:
    ev = pd.read_parquet(path)
    if id_col != "site_id":
        ev = ev.dropna(subset=[id_col]).assign(site_id=lambda d: d[id_col])
    # Days from every event, then the window: an event that runs over New Year starts in December in a
    # continuous record but on 1 January in the EA's calendar-year files.
    d = spill_days(ev)
    d = d[(d["day"].dt.year == year) & d["day"].dt.month.between(*months)]
    ev = ev[(ev["event_start"].dt.year == year) & ev["event_start"].dt.month.between(*months)]
    return ev, d


def compare(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    m = a.merge(b, on=["site_id", "day"], how="outer", indicator=True)
    n = m["_merge"].value_counts()
    return {"shared": int(n.get("both", 0)), "only_a": int(n.get("left_only", 0)),
            "only_b": int(n.get("right_only", 0))}


def start_offsets(a: pd.DataFrame, b: pd.DataFrame) -> pd.Series:
    """For each event of `a`, minutes from its start to the nearest start of `b` at the same overflow (B minus A,
    rounded to the minute), or NaN when none is within two hours."""
    ns = "datetime64[ns, UTC]"   # the files differ in time resolution, which merge_asof refuses
    a = a[["site_id", "event_start"]].astype({"event_start": ns}).sort_values("event_start").reset_index(drop=True)
    b = (b[["site_id", "event_start"]].astype({"event_start": ns}).rename(columns={"event_start": "b_start"})
         .sort_values("b_start"))
    m = pd.merge_asof(a, b, left_on="event_start", right_on="b_start", by="site_id", direction="nearest",
                      tolerance=pd.Timedelta(hours=2))
    return ((m["b_start"] - m["event_start"]).dt.total_seconds() / 60).round()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--months", default="1-12", help="first-last month, e.g. 1-11")
    p.add_argument("--id-a", default="site_id", help="column of A holding the overflow id")
    p.add_argument("--offsets", action="store_true", help="also print where B's nearest start lies")
    args = p.parse_args()
    months = tuple(int(x) for x in args.months.split("-"))
    ev_a, a = days_of(args.a, args.year, months, args.id_a)
    ev_b, b = days_of(args.b, args.year, months)
    ids_a, ids_b = set(a["site_id"]), set(b["site_id"])
    both = ids_a & ids_b
    print(f"A {args.a}: {len(ev_a):,} events, {len(ids_a):,} overflows, {len(a):,} spill-days")
    print(f"B {args.b}: {len(ev_b):,} events, {len(ids_b):,} overflows, {len(b):,} spill-days")
    print(f"overflow ids: {len(both):,} in both, {len(ids_a - ids_b):,} only in A, {len(ids_b - ids_a):,} only in B")
    print("spill-days, all ids:  ", compare(a, b))
    print("spill-days, ids in both:", compare(a[a["site_id"].isin(both)], b[b["site_id"].isin(both)]))
    if args.offsets:
        o = start_offsets(ev_a[ev_a["site_id"].isin(both)], ev_b[ev_b["site_id"].isin(both)])
        n = len(o)
        print(f"A events at ids in both: {n:,}; nearest B start within 2 h: {o.notna().mean():.3f}; "
              f"at 0 min: {(o.abs() <= 1).mean():.3f}; at +60: {((o - 60).abs() <= 1).mean():.3f}; "
              f"at -60: {((o + 60).abs() <= 1).mean():.3f}")


if __name__ == "__main__":
    main()
