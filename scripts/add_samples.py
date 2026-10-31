"""Add an organisation's lab results (samples/README.md): check them, keep every row in the private
folder, and write the ones it agreed to publish into samples/ for the build.

    uv run python scripts/add_samples.py --supplier "Example Swim Club" --received 2026-10-20 results.csv
    uv run python scripts/add_samples.py --supplier "Example Swim Club" --received 2026-10-20 \\
        --spot bw-uke4100-08901 --sampled "2026-10-17 08:30" --ecoli 1200 --enterococci "<10"
    uv run python scripts/add_samples.py --sync

A file is the lab's CSV, or one typed in the format's columns. Its own column names can be mapped
(--column sampled_at="Date and time sampled"); columns it has that the format does not are listed and
ignored. A value in the file wins for its row; a flag fills a blank (--lab, --method, --timezone ...).
Both permissions are off unless given: --publish and --evaluate, each only as the supplier agreed in
writing. Every row is checked before anything is written; one bad row writes nothing.

--sync writes every public file again from the private folder, after a permission is changed there by
hand: a row whose publish is now false leaves samples/ on that run.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from dipcast import samples as sm

ROOT = Path(__file__).resolve().parents[1]
SPOT_FILES = (ROOT / "spots.csv", ROOT / "spots-osm.csv")
# The flags that fill a blank, by column.
FILL = {"supplier": "supplier", "received": "received", "timezone": "timezone", "lab": "lab", "ukas_accredited": "ukas",
        "method": "method", "spot_id": "spot"}


def spot_ids(files=SPOT_FILES) -> set[str]:
    return {r["id"] for f in files if f.exists() for r in csv.DictReader(f.open(newline="", encoding="utf-8"))}


def read_input(path: Path, mapping: dict[str, str]) -> tuple[list[dict], list[str]]:
    """The file's rows with the format's column names, and the columns it ignored."""
    theirs = {v.strip().lower(): k for k, v in mapping.items()}
    with path.open(newline="", encoding="utf-8-sig") as fh:
        r = csv.DictReader(fh)
        names = {}
        for h in r.fieldnames or []:
            low = h.strip().lower()
            names[h] = theirs.get(low) or (low if low in sm.COLUMNS else None)
        rows = [{names[h]: v for h, v in raw.items() if h is not None and names.get(h)} for raw in r]
    return rows, [h for h, c in names.items() if c is None]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", type=Path, help="a CSV of results, one row a sample")
    ap.add_argument("--supplier", help="the organisation that sent them")
    ap.add_argument("--received", help="the day they arrived, 2026-10-20")
    ap.add_argument("--timezone", default="Europe/London", help="the zone the times are in: Europe/London (UK clock time, the default) or UTC")
    ap.add_argument("--spot", help="the spot's id, for one typed sample, or for a file all from one spot")
    ap.add_argument("--sampled", help="for one typed sample: when it was taken, 2026-10-17 08:30")
    ap.add_argument("--ecoli", help="for one typed sample: E. coli per 100 ml, as 1200, <10 or >24196")
    ap.add_argument("--enterococci", help="for one typed sample: intestinal enterococci per 100 ml")
    ap.add_argument("--lab-ref", help="for one typed sample: the lab's reference for it")
    ap.add_argument("--lab", help="the lab's name, as the supplier gives it")
    ap.add_argument("--ukas", choices=["yes", "no"], help="whether the supplier says the lab is UKAS-accredited for the test")
    ap.add_argument("--method", help="the test method, if the supplier gives it")
    ap.add_argument("--publish", action="store_true", help="the supplier agreed in writing to show these on the spot's page")
    ap.add_argument("--evaluate", action="store_true", help="the supplier agreed in writing to their use in testing the forecast")
    ap.add_argument("--column", action="append", default=[], metavar="OURS=THEIRS", help="a column of the file under another name")
    ap.add_argument("--allow-old", action="store_true", help=f"accept samples taken over {sm.MAX_DELAY_DAYS} days before they were received")
    ap.add_argument("--private", help=f"the private folder (default ${sm.PRIVATE_ENV}, else {sm.PRIVATE_DEFAULT})")
    ap.add_argument("--public", type=Path, default=sm.PUBLIC, help="the public folder the build reads (default samples/)")
    ap.add_argument("--sync", action="store_true", help="only write the public files again from the private folder")
    ap.add_argument("--dry-run", action="store_true", help="check, and write nothing")
    a = ap.parse_args(argv)
    try:
        private = sm.private_dir(a.private)
        ids = spot_ids()
        if a.sync:
            counts = sm.sync_public(private, a.public, ids)
            for name, n in counts.items():
                print(f"{name}: {n} row{'' if n == 1 else 's'} may be published")
            return 0
        mapping = {}
        for m in a.column:
            ours, _, theirs = m.partition("=")
            if ours not in sm.COLUMNS or not theirs:
                raise sm.SampleError(f"--column {m!r}: write ours=theirs, ours one of {', '.join(sm.COLUMNS)}")
            mapping[ours] = theirs
        if a.file:
            if a.sampled or a.ecoli or a.enterococci:
                raise sm.SampleError("give a file or one typed sample, not both")
            rows, ignored = read_input(a.file, mapping)
            if ignored:
                print(f"Ignored, not in the format: {', '.join(ignored)}")
        elif a.sampled:
            rows = [{"sampled_at": a.sampled, "ecoli_per_100ml": a.ecoli or "", "enterococci_per_100ml": a.enterococci or "",
                     "lab_ref": a.lab_ref or ""}]
        else:
            ap.error("give a file of results, or --spot, --sampled and a count, or --sync")
        if not rows:
            raise sm.SampleError("no rows")
        flags = vars(a)
        checked, errors = [], []
        for i, raw in enumerate(rows, 1):
            raw = dict(raw)
            for col, flag in FILL.items():
                if not str(raw.get(col) or "").strip() and flags.get(flag):
                    raw[col] = flags[flag]
            for col in ("publish", "evaluate"):
                if not str(raw.get(col) or "").strip():
                    raw[col] = "true" if flags[col] else "false"
            try:
                checked.append(sm.parse_row(raw, ids, allow_old=a.allow_old))
            except sm.SampleError as e:
                errors.append(f"row {i}: {e}")
        names = {sm.slug(r["supplier"]) for r in checked}
        if len(names) > 1:
            errors.append(f"one supplier a run: these rows come from {', '.join(sorted(names))}")
        existing = sm.read_private(private, ids) if private.is_dir() else {}
        name = next(iter(names), None)
        have = {sm.key(r) for r in existing.get(name, [])}
        for i, r in enumerate(checked, 1):
            if sm.key(r) in have:
                errors.append(f"{r['spot_id']} at {r['sampled_at']}: already in {name}.csv")
            have.add(sm.key(r))
        if errors:
            print("Nothing written:", *errors, sep="\n  ", file=sys.stderr)
            return 1
        pub, ev = sum(r["publish"] == "true" for r in checked), sum(r["evaluate"] == "true" for r in checked)
        print(f"{len(checked)} sample{'' if len(checked) == 1 else 's'} from {checked[0]['supplier']}: "
              f"{pub} may be published, {ev} may be used to test the forecast.")
        for r in checked:
            counts = "; ".join(f"{k} {r[c]}" for k, c in (("E. coli", "ecoli_per_100ml"), ("enterococci", "enterococci_per_100ml")) if r[c])
            print(f"  {r['spot_id']}  {r['sampled_at']}  {counts}")
        # What the rows leave unknown (samples.notes): read them with the sender. A note on every row is said once.
        said: dict[str, int] = {}
        for r in checked:
            for n in sm.notes(r):
                said[n] = said.get(n, 0) + 1
        for n, k in said.items():
            print(f"  note: {n}" + (f" ({k} rows)" if k > 1 else ""))
        if a.dry_run:
            print("Dry run: nothing written.")
            return 0
        n = sm.write_supplier(private, a.public, name, existing.get(name, []) + checked)
        print(f"Kept in {private / (name + '.csv')}.")
        if n:
            print(f"{a.public / (name + '.csv')} now has {n} row{'' if n == 1 else 's'}: open a pull request with it to publish them.")
        return 0
    except sm.SampleError as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
