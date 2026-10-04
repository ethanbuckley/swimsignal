"""Write data/processed/wales_annual.parquet: Welsh storm overflows' annual returns, one row per
overflow and return year, 2022 to 2025, with the long-term average spill count, the position, the
country and the matching live row. Task W2 of docs/WALES-PLAN-2026-10.md; the rule and the
sources are in src/dipcast/ingest/wales_annual.py. Off CI, and never published: Dŵr Cymru's
layers carry no licence, so the parquet and its report stay out of git (data/processed/* is
ignored) until Dŵr Cymru gives terms.

    uv run python scripts/fetch_wales_annual.py             # reads data/cache/wales_annual/ if there
    uv run python scripts/fetch_wales_annual.py --refresh   # reads the layers again (about 20 requests)

It reads one page at a time, never in parallel. It also writes
data/processed/wales_annual_report.json: rows by year, the live match rates and the rule's error
against the EA's long-term averages for English overflows (data/processed/annual_returns.parquet).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

import pandas as pd

from dipcast import config
from dipcast.ingest import wales_annual as wa
from dipcast.ingest.common import write_parquet


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    raw = wa.fetch_raw(refresh="--refresh" in sys.argv)
    table = wa.build(raw)
    write_parquet(table, wa.OUT)
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    rep = {"made": datetime.now(UTC).isoformat(timespec="seconds"), "rule": "see wales_annual.py docstring",
           **wa.report(table, raw), "compare_with_ea": wa.compare_with_ea(ar),
           "dwr_cymru_layers_against_ea_counts": wa.check_against_ea_counts(table, ar)}
    wa.REPORT.write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n")
    print(table.groupby(["company", "year"]).agg(rows=("site_id", "size"), spills=("spills", "count"),
                                                 uptime=("edm_operational_pct", "count"),
                                                 matched=("live_global_id", "count")).to_string())
    for y, r in rep["compare_with_ea"]["years"].items():
        print(y, "all", r["all"], "\n     Dwr Cymru England", r["dwr_cymru_england"])
    print(f"{len(table)} rows -> {wa.OUT}; report -> {wa.REPORT}")


if __name__ == "__main__":
    main()
