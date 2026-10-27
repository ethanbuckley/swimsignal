"""Today's EA advice on a bathing water's page (src/dipcast/site/eatoday.js) is built and stored with the
app, as the other scripts are, and the build itself never asks the EA for it: the reader's browser loads
the EA's own panel when the fold is opened. Its rules are tested in tests/site_eatoday.test.cjs."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_the_page_loads_the_ea_advice_script_from_its_build(tmp_path):
    bs = _build_site()
    spot = {"id": "bw-ukj2310-11945", "name": "Frensham Great Pond", "kind": "lake", "source": "designated", "days": [],
            "classification": {"class": "excellent", "year": 2025,
                               "url": "https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945"}}
    bs.write_pages(tmp_path, [spot], root="https://example.org/")
    stamp = bs.shell_stamp()
    page = (tmp_path / "spot" / "bw-ukj2310-11945" / "index.html").read_text()
    assert f'<script src="eatoday.js?v={stamp}" defer>' in page
    assert (tmp_path / "eatoday.js").read_bytes() == (bs.TEMPLATE.parent / "eatoday.js").read_bytes()
    assert "`eatoday.js?v=${BUILD}`" in (tmp_path / "sw.js").read_text()
    assert bs.TEMPLATE.parent / "eatoday.js" in bs.SHELL_SOURCES
    # The panel is loaded by the reader's browser, never written into a built page.
    assert "bwq/widget" not in page


def test_the_build_never_asks_for_the_panel():
    # No request is added to the build: only the page's script knows the widget's address. The advisory
    # finder, which lists the panel as a source, lives in scripts/ (scripts/advisories.py), outside the
    # package, so this holds for every module of the package.
    for f in [ROOT / "scripts" / "build_site.py", *(ROOT / "src" / "dipcast").rglob("*.py")]:
        assert "bwq/widget" not in f.read_text(), f


def repo_sources(files, root=ROOT):
    """The repo's own Python source among loaded modules' files: under src/ or scripts/, as .py. A
    cached .pyc maps to its source; anything else (an extension module, a .venv inside the checkout,
    a file with no source) is left out, so a binary never reaches the text check."""
    import importlib.util
    out = set()
    for f in files:
        if not f:
            continue
        f = Path(f)
        if f.suffix == ".pyc":
            try:
                f = Path(importlib.util.source_from_cache(str(f)))
            except ValueError:
                continue
        f = f.resolve()
        if f.suffix == ".py" and f.is_file() and any(f.is_relative_to(root / d) for d in ("src", "scripts")):
            out.add(f)
    return sorted(out)


def test_the_build_never_imports_the_advisory_finder():
    # The same contract, from what the build actually loads: import build_site in a fresh interpreter
    # and read every repo source module it brought in. None is the finder, and none names the panel.
    import json
    import subprocess
    code = ("import json, sys; sys.path[:0] = [sys.argv[1] + '/scripts', sys.argv[1] + '/src']; import build_site; "
            "print(json.dumps(sorted({n: getattr(m, '__file__', None) for n, m in list(sys.modules.items())}.items(), "
            "key=lambda x: x[0])))")
    out = subprocess.run([sys.executable, "-c", code, str(ROOT)], capture_output=True, text=True, check=True, cwd=ROOT)
    mods = dict(json.loads(out.stdout.splitlines()[-1]))
    assert "build_site" in mods and "dipcast.official_advice" in mods
    assert "advisories" not in mods and "advisory_finder" not in mods
    ours = repo_sources(mods.values())
    assert ROOT / "scripts" / "build_site.py" in ours and ROOT / "src" / "dipcast" / "official_advice.py" in ours
    assert len(ours) > 5
    for f in ours:
        assert "bwq/widget" not in f.read_text(encoding="utf-8"), f
    assert "bwq/widget" in (ROOT / "scripts" / "advisories.py").read_text(encoding="utf-8")


def test_the_scan_reads_only_source_files(tmp_path):
    # CI checks the repo out with its .venv inside it: binary modules and caches must not break the scan.
    (tmp_path / "src" / "pkg" / "__pycache__").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".venv").mkdir()
    py = tmp_path / "src" / "pkg" / "mod.py"
    py.write_text("x = 1\n")
    pyc = tmp_path / "src" / "pkg" / "__pycache__" / "mod.cpython-312.pyc"
    pyc.write_bytes(b"\x90\xff\x00binary")
    stray = tmp_path / "src" / "pkg" / "_speed.cpython-312-darwin.so"
    stray.write_bytes(b"\x90\xff\x00binary")
    orphan = tmp_path / "src" / "pkg" / "__pycache__" / "gone.cpython-312.pyc"
    orphan.write_bytes(b"\x90")
    venv = tmp_path / ".venv" / "site.py"
    venv.write_text("y = 2\n")
    got = repo_sources([str(py), str(pyc), str(stray), str(orphan), str(venv), None], root=tmp_path.resolve())
    assert got == [py.resolve()]


def test_the_privacy_notice_names_the_panel_on_a_bathing_waters_page():
    notice = (ROOT / "src" / "dipcast" / "pages" / "privacy.html").read_text()
    para = next(p for p in notice.split("<p>") if "environment.data.gov.uk" in p)
    assert "on a bathing water's page" in para and 'Opening "Today\'s EA advice"' in para
    assert "scripts switched off" in para and "does not tell it which page you were on" in para
