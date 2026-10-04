"""A level word always carries "risk" where it says how a spot is (docs/DESIGN.md, Words): "reaches
high or very high risk", never "turns high"; "High risk today", never "High today". Ethan flagged a
bare level word twice (4 October 2026), so this reads every text the site, the alert Worker and the
feedback form show, and fails on the bare forms.

What it leaves alone: a list that names the scale ("A day's level (low, moderate, high or very
high)"), the levels' key and the map's key, and the five days' rows under "Pollution risk, next five
days". None of those follows a verb or a day. Code comments are not read."""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Everything that writes words a visitor, a subscriber or a feedback form shows. build_site.py is
# read for its strings only (the privacy notice's alerts sections, the page descriptions).
SHIPPED = [
    *sorted((ROOT / "src/dipcast/site").glob("*.js")),
    *sorted((ROOT / "src/dipcast/site").glob("*.html")),
    *sorted((ROOT / "src/dipcast/api/static").glob("*.html")),
    *sorted((ROOT / "push/src").glob("*.js")),
    *sorted((ROOT / "reviews/src").glob("*.js")),
    ROOT / "scripts/alerts.js",
    *sorted((ROOT / ".github/ISSUE_TEMPLATE").glob("*.yml")),
]

LEVEL = r"(?:very\s+high|high|moderate|low)"
# A level after "risk" ("...or very high risk"), or after "or worse" + "risk", is not bare.
CARRIES_RISK = r"(?!\s+(?:or\s+(?:very\s+high|high|moderate|low)\s+)?risk)"
VERB = (r"(?:turns?|turned|turning|reach(?:es|ed|ing)?|rises?|rising|rose|risen|goes|going|went|gone|"
        r"becomes?|became|becoming|stays?|stayed|staying|falls?|fell|falling|drops?|dropped|"
        r"is|are|was|were|be|been|being|makes?|made|making|puts?|keeps?|kept|leaves?|left)")
BARE = [
    # A spot's state after a verb: "turns high", "is moderate", "makes it high", "stays at least high".
    re.compile(rf"\b{VERB}\s+(?:(?:it|them|the\s+level|the\s+spot|at\s+least|back|to|at|on)\s+)*{LEVEL}\b{CARRIES_RISK}", re.IGNORECASE),
    # A level heading a line with its day: "High today", "Very high on Saturday", "Low again".
    re.compile(rf"\b{LEVEL}\s+(?:today|tomorrow|tonight|right\s+now|now|again|by|until|from|this|"
               r"on\s+(?:mon|tues|wednes|thurs|fri|satur|sun)day)\b", re.IGNORECASE),
]
# Kept on purpose, each with why. A phrase here must still be found, so a stale entry fails too.
ALLOWED = {
    # The exposure index is a 0-100 score: a low score is a number, not a spot's level.
    "when the exposure index is low": "src/dipcast/site/index.html",
    # The operator's log line in `wrangler tail` (push/README.md), never shown to a visitor.
    "spots rose to high": "push/src/index.js",
}
# A level after the subject "risk" carries it already: "right now's risk is moderate or worse".
AFTER_RISK = re.compile(r"\brisk(?:'s)?\s+(?:\w+\s+){0,2}$", re.IGNORECASE)


def _strings(path: Path) -> str:
    """build_site.py's string constants, docstrings left out, one a line."""
    tree = ast.parse(path.read_text())
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    return "\n".join(n.value for n in ast.walk(tree)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs)


def _text(path: Path) -> str:
    """The file without its comments: HTML's, and JavaScript's whole-line and trailing ones."""
    s = re.sub(r"<!--.*?-->", "", path.read_text(), flags=re.DOTALL)
    lines = []
    for line in s.splitlines():
        if re.match(r"\s*(//|/\*|\*)", line):
            continue
        lines.append(re.sub(r"\s//\s.*$", "", line))
    return "\n".join(lines)


def _bare(name: str, text: str) -> list[str]:
    found = []
    for pattern in BARE:
        for m in pattern.finditer(text):
            if AFTER_RISK.search(text[max(0, m.start() - 40):m.start()]):
                continue
            around = " ".join(text[max(0, m.start() - 40):m.end() + 20].split())
            if any(phrase in around and where == name for phrase, where in ALLOWED.items()):
                continue
            found.append(f"{name}: ...{around}...")
    return found


def test_shipped_texts_never_leave_a_level_word_without_risk():
    found = []
    for path in SHIPPED:
        if "vendor" not in path.parts:
            found += _bare(str(path.relative_to(ROOT)), _text(path))
    found += _bare("scripts/build_site.py", _strings(ROOT / "scripts/build_site.py"))
    assert not found, "a level word without \"risk\" (docs/DESIGN.md, Words):\n" + "\n".join(found)


def test_the_allowed_phrases_are_still_there():
    for phrase, where in ALLOWED.items():
        assert phrase in " ".join((ROOT / where).read_text().split()), (phrase, where)


def test_the_check_finds_the_forms_it_is_for():
    caught = ["A notification when one of your saved spots turns high or very high, at most once a day.",
              "It uses them only to send a notification when one of those spots' forecast turns high and",
              "The rating is poor, so the level stays at least high; advice",
              "2 upstream overflows are discharging now; exposure right now is moderate.",
              "a rating of sufficient makes the level moderate and poor makes it high",
              "High today. Very high on Saturday.",
              "When ${which} goes very high"]
    kept = ["A notification when one of your saved spots reaches high or very high risk, at most once a day.",
            "A day's level (low, moderate, high or very high) is the worst of these",
            "The rating is poor, so the spot stays at high risk or worse; advice",
            "Very high risk today: sewage spills. Low risk by Tuesday.",
            "While right now's risk is moderate or worse, or an overflow upstream is discharging",
            "Pollution risk: 30 low · 20 moderate · 5 high or very high",
            "A high river runs faster and colder. Daytime high about 14°C. Too high to swim."]
    for words in caught:
        assert _bare("t", words), words
    for words in kept:
        assert not _bare("t", words), words
