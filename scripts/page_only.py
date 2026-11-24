"""Whether a push to main can rebuild the pages only (docs/PAGE-ONLY-BUILDS-2026-11.md).

A site build forecasts and then writes the pages. A push that changes only what the pages are made from need not
forecast again: scripts/build_site.py --pages-only writes the pages over the last build's published site and leaves
its data as it is. This script decides whether the commits since that build are such a change. Anything it does not
know to be page-only is a full build: an unknown path, a change to the workflow, a change to scripts/build_site.py
that the forecast half can reach, a file it cannot read.

    python3 scripts/page_only.py changes <base> <head>     # exit 0: pages only; 1: build in full
    python3 scripts/page_only.py age site/data/spots.json  # exit 0: the forecast is young enough to keep

It imports nothing from dipcast, so the workflow runs it before anything is installed.

The paths. PAGE_DIRS and PAGE_FILES are read only by what rebuild_pages runs again (RERUN), bar RULES_FILES, which
are a full build by choice. docs/ is with them: the one file a build reads there is the quality page's
(src/dipcast/quality.py, CASES). NOT_READ is read by no build.
tests/test_page_only.py checks these against the code: which modules read the page sources, and that the forecast
half of build_site.py reaches none of them.

scripts/build_site.py holds both halves, so its changes are read by definition, not by file. Each top-level name
(function, constant, import) whose definition differs between the two commits, comments and docstrings aside, is a
changed name. The forecast half is every name build() can reach by reference without passing through RERUN. If no
changed name is in it, only the pages differ. A name both halves use (site_url, say) is in it, so changing one is a
full build.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

PAGE_DIRS = ("src/dipcast/site/", "src/dipcast/pages/", "docs/")
PAGE_FILES = ("scripts/prerender_spots.js", "scripts/prerender_verification.js", "scripts/prerender_preview.js")
# The level rules. rebuild_pages would apply new ones to alerts.json, the cards and the pages alike, but the alerts
# Worker sends by alerts.json, and new rules over a forecast up to two hours old could send an alert no forecast
# stands behind. A change to the rules is published with a forecast. None of the 9 page-only pushes of 17 to 24 Nov
# 2026 touched either file.
RULES_FILES = ("src/dipcast/site/levels.js", "scripts/alerts.js")
# Read by no build: the tests, and a local preview server (tests/test_page_only.py checks nothing in the build names it).
NOT_READ = ("tests/", ".gitignore", "README.md", "scripts/preview_redesign.py")
BUILD_SCRIPT = "scripts/build_site.py"
FULL_ENTRY, PAGES_ENTRY = "build", "rebuild_pages"
# What rebuild_pages runs again, so what a change may reach without a forecast: the page's rules over spots.json
# (alerts.json, the cards), the pages, the Lab's dates.
RERUN = ("write_alerts", "write_spot_cards", "write_site_pages", "write_cards", "write_lab_refresh")
# With these a name can be reached without being written, so the reading below would miss it.
UNREADABLE = ("globals", "eval", "exec", "__import__")
# A page-only build keeps the forecast it finds, so it is allowed only while that forecast is this young; an older
# one is replaced by a full build, as before. Scheduled builds were a median 4.6 h apart in Oct-Nov 2026 (site.yml).
MAX_AGE_MIN = 120


def _bound(stmt: ast.stmt) -> list[str]:
    """The module-level names a top-level statement binds."""
    if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return [stmt.name]
    if isinstance(stmt, ast.Import | ast.ImportFrom):
        return [(a.asname or a.name).split(".")[0] for a in stmt.names]
    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target] if isinstance(stmt, ast.AnnAssign | ast.AugAssign) else []
    return [n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]


def _dump(stmt: ast.stmt) -> str:
    """The statement without its position, comments or docstrings: two that dump alike run alike."""
    stmt = ast.parse(ast.unparse(stmt)).body[0]   # a copy, so the tree read for references keeps its docstrings
    for node in ast.walk(stmt):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and len(node.body) > 1 \
                and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) \
                and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:]
    return ast.dump(stmt)


def _names(stmt: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(stmt) if isinstance(n, ast.Name)}


class Module:
    """One version of a Python file: what each top-level name is defined by, and what it refers to."""

    def __init__(self, source: str):
        tree = ast.parse(source)
        self.defs: dict[str, list[str]] = {}    # name -> the dumps of the statements that bind it, in order
        self.refs: dict[str, set[str]] = {}     # name -> every name those statements mention
        self.loose: list[tuple[str, set[str]]] = []   # statements that bind nothing: X.append(...), if __name__ ...
        self.unreadable = sorted(_names(tree) & set(UNREADABLE))
        for stmt in tree.body:
            bound, names = _bound(stmt), _names(stmt)
            if not bound:
                self.loose.append((_dump(stmt), names))
                continue
            for name in bound:
                self.defs.setdefault(name, []).append(_dump(stmt))
                self.refs.setdefault(name, set()).update(names - {name})
        # A statement that binds nothing can still change a value (SHELL_SOURCES.append(...)): every name it
        # mentions then depends on the others it mentions.
        for _, names in self.loose:
            for name in names & set(self.defs):
                self.refs[name].update(names - {name})

    def reach(self, start: str, cut: tuple[str, ...] = ()) -> set[str]:
        """Every top-level name `start` can reach by reference, itself included, not passing through `cut`."""
        seen, todo = set(), [start]
        while todo:
            name = todo.pop()
            if name in seen or name not in self.defs or name in cut:
                continue
            seen.add(name)
            todo.extend(self.refs[name])
        return seen


def changed_names(old: Module, new: Module) -> set[str]:
    """The top-level names whose definition differs, was added or was removed; and every name a changed, added
    or removed loose statement mentions."""
    out = {n for n in set(old.defs) | set(new.defs) if old.defs.get(n) != new.defs.get(n)}
    known = set(old.defs) | set(new.defs)
    a, b = Counter(d for d, _ in old.loose), Counter(d for d, _ in new.loose)
    for mod in (old, new):
        for dump, names in mod.loose:
            if a[dump] != b[dump]:
                out |= names & known
    return out


def build_script_verdict(old_source: str, new_source: str) -> tuple[bool, str]:
    """(True, why) if the change to scripts/build_site.py cannot change what the forecast half does."""
    try:
        old, new = Module(old_source), Module(new_source)
    except SyntaxError as e:
        return False, f"{BUILD_SCRIPT} could not be read ({e})"
    for mod in (old, new):
        if mod.unreadable:
            return False, f"{BUILD_SCRIPT} uses {', '.join(mod.unreadable)}, which this cannot follow"
        if FULL_ENTRY not in mod.defs or PAGES_ENTRY not in mod.defs:
            return False, f"{BUILD_SCRIPT} has no {FULL_ENTRY}() or no {PAGES_ENTRY}() at one of the two commits"
        missing = [r for r in RERUN if r not in mod.reach(PAGES_ENTRY)]
        if missing:
            return False, f"{PAGES_ENTRY}() does not run {', '.join(missing)} again"
    changed = changed_names(old, new)
    # In either version: a name the old forecast reached and the new one does not is a change to the forecast too.
    forecast = old.reach(FULL_ENTRY, RERUN) | new.reach(FULL_ENTRY, RERUN)
    hit = sorted(changed & forecast)
    if hit:
        return False, f"{BUILD_SCRIPT}: the forecast half reaches {', '.join(hit[:8])}{' and more' if len(hit) > 8 else ''}"
    return True, f"{BUILD_SCRIPT}: {len(changed)} changed name(s), none the forecast half reaches"


def verdict(paths: list[str], old_build: str | None = None, new_build: str | None = None) -> tuple[bool, list[str]]:
    """(pages only?, the reasons). `paths` are the files that differ between the last build's commit and this one;
    the two sources are scripts/build_site.py at each, needed only if it is among them."""
    if not paths:
        return False, ["no file differs from the last build's commit: nothing says the pages alone changed"]
    reasons, pages = [], True
    for p in sorted(set(paths)):
        if p in RULES_FILES:
            reasons.append(f"{p} holds the level rules, which alerts are sent by")
            pages = False
            continue
        if p.startswith(NOT_READ) or p.startswith(PAGE_DIRS) or p in PAGE_FILES:
            continue
        if p == BUILD_SCRIPT:
            if old_build is None or new_build is None:
                ok, why = False, f"{BUILD_SCRIPT} changed and one of its two versions could not be read"
            else:
                ok, why = build_script_verdict(old_build, new_build)
            reasons.append(why)
            pages = pages and ok
            continue
        reasons.append(f"{p} is not known to be read by the pages alone")
        pages = False
    if pages:
        reasons.insert(0, f"{len(set(paths))} file(s) differ, all read by the pages alone")
    return pages, reasons


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def changes(base: str, head: str) -> tuple[bool, list[str]]:
    """verdict() for two commits in this checkout. Both must be fetched; any git failure is a full build."""
    try:
        paths = [p for p in _git("diff", "--name-only", "--no-renames", base, head).splitlines() if p]
        old = new = None
        if BUILD_SCRIPT in paths:
            old, new = _git("show", f"{base}:{BUILD_SCRIPT}"), _git("show", f"{head}:{BUILD_SCRIPT}")
    except (OSError, subprocess.SubprocessError) as e:
        return False, [f"git could not compare {base} with {head} ({getattr(e, 'stderr', '') or e})".strip()]
    return verdict(paths, old, new)


def young_enough(spots_json: Path, now: datetime | None = None, max_min: float = MAX_AGE_MIN) -> tuple[bool, str]:
    """(True, why) if the published forecast was issued under max_min minutes ago. A file that cannot be read, a
    time without a zone or one in the future is not."""
    try:
        issued = datetime.fromisoformat(json.loads(Path(spots_json).read_text())["generated_at"])
        age = ((now or datetime.now(UTC)) - issued).total_seconds() / 60
    except (OSError, KeyError, TypeError, ValueError) as e:
        return False, f"the published forecast's issue time could not be read ({e})"
    if not 0 <= age < max_min:
        return False, f"the published forecast is {age:.0f} min old (issued {issued.isoformat()}); the limit is {max_min:.0f}"
    return True, f"the published forecast is {age:.0f} min old (issued {issued.isoformat()}), under {max_min:.0f}"


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "changes":
        ok, reasons = changes(argv[1], argv[2])
    elif len(argv) == 2 and argv[0] == "age":
        ok, why = young_enough(Path(argv[1]))
        reasons = [why]
    else:
        print(__doc__, file=sys.stderr)
        return 2
    for r in reasons:
        print(("pages only: " if ok else "full build: ") + r)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
