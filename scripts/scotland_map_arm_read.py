"""Read Scotland's mapped shadow arm, `scotland-map-v1` (docs/SCOTLAND-MAP-SHADOW-ARM-2026-11.md).

    uv run python scripts/scotland_map_arm_read.py --state <copy of the build's state directory> --counts-only
    uv run python scripts/scotland_map_arm_read.py --state <copy> --work <scratch directory> --out <file.json>

Before the read date (dipcast.scottish_shadow_map.READ_NOT_BEFORE) it prints counts only and joins no outcome,
whatever is asked. On or after it, it scores the logged rows by Gate B's rules, and the derived series beside them.
`--state` is a copy: the state directory lives in the Actions cache. Nothing in it is written. The output holds
counts and scores, no Scottish Water row.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--state", type=Path, required=True, help="a copy of the build's state directory")
    ap.add_argument("--work", type=Path, help="scratch directory for the read's copies (needed for scores)")
    ap.add_argument("--out", type=Path, help="write the result here as JSON")
    ap.add_argument("--counts-only", action="store_true", help="rows, issues and checks only: no outcome joined")
    args = ap.parse_args(argv)
    from dipcast import scottish_shadow_map
    out = scottish_shadow_map.read(args.state, args.work, counts_only=args.counts_only)
    text = json.dumps(out, indent=1, default=str)
    if args.out:
        args.out.write_text(text)
    print(text)
    return out


if __name__ == "__main__":
    main()
