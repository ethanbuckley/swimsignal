"""Official advice on a spot's page, from two files and no request: the reviewed advisories
(data/advisories/approved.json, changed only by pull request) and the advisory finder's last weekly
check (data/advisories/last_check.json, written by scripts/advisory_finder.py on a live run and
committed). The site build reads both; it never asks a publisher for anything. The finder itself
lives in scripts/ (scripts/advisories.py), outside this package, so nothing the build imports can
reach it. docs/ADVISORY-FINDER-2026-10.md has the rules.

An advisory is shown at its spot while nothing positive has ended it: the source listing it as
withdrawn or lifted (an end read from the source, for the same draft or the same incident), a stated
expiry passing, or (for a page notice with no stated end) PAGE_TERM_DAYS after review. A check that
failed or is old never hides it, and nor does an incident that left the EA's open list with no end
read (the finder flags that "gone"): it stays, marked "not re-checked since". The advice never changes
a forecast level.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dipcast import config

TZ = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")
APPROVALS_FILE = config.ROOT / "data" / "advisories" / "approved.json"
CHECK_FILE = config.ROOT / "data" / "advisories" / "last_check.json"
PAGE_TERM_DAYS = 14        # a reviewed page notice with no stated end lapses this long after review
RECHECK_DAYS = 8           # a check older than this is shown as "not re-checked since"
ENDED = {"withdrawn", "lifted"}
KINDS = ("feed", "page")
# Who may review an advisory, and on what authority: (reviewer, authority) pairs. The page shows the
# advice; the file says who reviewed it and why they could. Changed only by pull request.
REVIEWERS = (
    ("Ethan Buckley", "Ethan Buckley"),
    ("Codex", "Codex, under Ethan Buckley's delegation of routine decisions, 26 Oct 2026"),
)

_DRAFT_ID = re.compile(r"[0-9a-f]{12}\Z")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_SPOT = re.compile(r"[a-z0-9][a-z0-9-]{1,60}\Z")
# restricts: whether the notice restricts swimming, true or false, set by the reviewer from the notice's own words
# (28 Oct 2026). Required: a notice is never taken to restrict swimming for want of it, and a file without it
# approves nothing. Only true changes which spots the pages leave out of counts, shared plans and suggestions, and
# put first (eatoday.js, eaTodayRestricts); every notice shows either way.
REQUIRED = ("draft_id", "spot_id", "line", "publisher", "link", "kind", "source_url", "start", "fetched_at",
            "reviewer", "authority", "reviewed_at", "restricts")
OPTIONAL = ("incident_id", "expiry")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class ApprovalError(ValueError):
    """The approvals file is not as it must be. Nothing is approved from a file with any error."""


def show_day(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def _plain(text) -> bool:
    """One clean line: no control or invisible characters, no doubled or edge spaces."""
    if not isinstance(text, str) or not text or len(text) > 300:
        return False
    t = unicodedata.normalize("NFKC", text)
    return t == text and not any(unicodedata.category(c) in ("Cc", "Cf") for c in t) and " ".join(t.split()) == t


def _utc(at) -> datetime | None:
    if not isinstance(at, str) or not _UTC.fullmatch(at):
        return None
    try:
        return datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _day(s) -> date | None:
    if not isinstance(s, str) or not _DAY.fullmatch(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def load_approvals(path: Path | None = None, known: set[str] | None = None, now: datetime | None = None) -> dict:
    """The reviewed advisories, by draft id. Each entry has the exact line, the evidence it rests on
    (spot, publisher, link, source address, incident id where there is one, start day, fetch time) and
    who reviewed it on what authority (a pair in REVIEWERS) and when (reviewed_at, UTC, not after
    `now`). `known`, when given, is the set of draft ids the entry must be one of. Any problem raises
    ApprovalError naming each entry: a file with a mistake approves nothing."""
    path = Path(path or APPROVALS_FILE)
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise ApprovalError(f"{path}: cannot be read as JSON ({type(err).__name__})") from None
    entries = body.get("approvals") if isinstance(body, dict) else None
    if not isinstance(entries, list):
        raise ApprovalError(f"{path}: no \"approvals\" list")
    out, problems = {}, []
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            problems.append(f"entry {i}: not an object")
            continue
        did = e.get("draft_id")
        if not isinstance(did, str) or not _DRAFT_ID.fullmatch(did):
            problems.append(f"entry {i}: no valid draft_id")
            continue
        here, before = f"entry {i} ({did})", len(problems)
        if known is not None and did not in known:
            problems.append(f"{here}: unknown draft id, not in this run or the previous one")
        if did in out:
            problems.append(f"{here}: approved twice")
        missing = [k for k in REQUIRED if e.get(k) in (None, "")]
        if missing:
            problems.append(f"{here}: missing {', '.join(missing)}")
        if set(e) - set(REQUIRED) - set(OPTIONAL):
            problems.append(f"{here}: unexpected keys {sorted(set(e) - set(REQUIRED) - set(OPTIONAL))}")
        who, auth = e.get("reviewer"), e.get("authority")
        if who and auth and (who, auth) not in REVIEWERS:
            problems.append(f"{here}: {str(who)[:40]!r} on {str(auth)[:80]!r} may not review "
                            f"(only {'; '.join(a for _, a in REVIEWERS)})")
        when = _utc(e.get("reviewed_at"))
        if e.get("reviewed_at") and not when:
            problems.append(f"{here}: reviewed_at must be a real UTC time as 2026-10-26T19:00:00Z")
        elif when and now and when > now:
            problems.append(f"{here}: reviewed_at is in the future")
        if e.get("fetched_at") and not _utc(e.get("fetched_at")):
            problems.append(f"{here}: fetched_at must be a real UTC time as 2026-10-26T19:00:00Z")
        for k in ("start", "expiry"):
            if e.get(k) is not None and not _day(e.get(k)):
                problems.append(f"{here}: {k} must be a day as 2026-06-19")
        for k in ("line", "publisher"):
            if e.get(k) and not _plain(e[k]):
                problems.append(f"{here}: {k} must be one clean line")
        for k in ("link", "source_url"):
            if e.get(k) and not (isinstance(e[k], str) and e[k].startswith("https://") and _plain(e[k])
                                 and not set('"<> ') & set(e[k])):
                problems.append(f"{here}: {k} must be an https address")
        if e.get("kind") and e["kind"] not in KINDS:
            problems.append(f"{here}: kind must be one of {', '.join(KINDS)}")
        if e.get("spot_id") and not (isinstance(e["spot_id"], str) and _SPOT.fullmatch(e["spot_id"])):
            problems.append(f"{here}: spot_id is not a spot id")
        if e.get("restricts") is not None and not isinstance(e["restricts"], bool):
            problems.append(f"{here}: restricts must be true or false")
        if e.get("incident_id") is not None and not _plain(e.get("incident_id")):
            problems.append(f"{here}: incident_id must be one clean line")
        if len(problems) == before:
            out[did] = {**{k: e.get(k) for k in (*REQUIRED, *OPTIONAL)}, "when": when}
    if problems:
        raise ApprovalError(f"{path}: " + "; ".join(problems))
    return out


def check_record(result: dict, previous: dict | None = None) -> dict:
    """What the page needs from one finder run, to commit as CHECK_FILE: when it ran, each source's
    state, and each draft at a spot with its status, flags, its line as this run wrote it (our own
    words, so the site can tell a reviewed line from a changed one) and when its source last confirmed
    it. No evidence text. An ended draft (withdrawn, lifted)
    in the `previous` record that this run no longer lists is kept, so an ended advisory stays ended
    after it drops out of the finder's drafts, rather than coming back as "not re-checked"."""
    out = _check_record(result)
    for did, d in ((previous or {}).get("drafts") or {}).items():
        if did not in out["drafts"] and isinstance(d, dict) and d.get("status") in ENDED:
            out["drafts"][did] = d
    return out


def _check_record(result: dict) -> dict:
    at = datetime.fromisoformat(result["generated_at"]).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    drafts = {}
    for d in result.get("drafts", []):
        if not d.get("spot_id"):
            continue
        fetched = d.get("fetched_at")
        try:
            fetched = datetime.fromisoformat(fetched).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError):
            fetched = None
        drafts[d["draft_id"]] = {"spot_id": d["spot_id"], "feed_id": d.get("feed_id"), "status": d["status"],
                                 "line": d.get("draft_line"), "flags": list(d.get("flags", [])),
                                 "current": d.get("current"), "fetched_at": fetched,
                                 "superseded_by": d.get("superseded_by"), "source": d["source"]["key"]}
    return {"note": "The advisory finder's last live check (scripts/advisory_finder.py). Written by the "
                    "finder, committed by pull request; the site build reads it and makes no request.",
            "checked_at": at, "mode": result.get("mode"),
            "sources": {s["key"]: s["state"] for s in result.get("sources", []) if s.get("key")},
            "drafts": drafts}


def load_check(path: Path | None = None) -> dict | None:
    """The last check, or None when there is none or it cannot be read (every advisory is then shown
    as not re-checked)."""
    try:
        body = json.loads(Path(path or CHECK_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(body, dict) or not _utc(body.get("checked_at")) or not isinstance(body.get("drafts"), dict):
        return None
    return body


def _local(at: datetime) -> date:
    return at.astimezone(TZ).date()


def shown(approvals: dict, check: dict | None, now: datetime) -> dict[str, list[dict]]:
    """The advisories each spot's page shows, newest first, as {spot_id: [{line, publisher, link,
    since, checked, state}]}. state is "checked" (the last check confirmed it within RECHECK_DAYS),
    "stale" (no check since `checked`), "unverified" (the last check could not read its source),
    "gone" (it left the source's open list and no end was read) or "changed" (the source's line is no
    longer the reviewed one: the new line needs a review, and the reviewed one is not shown as
    current); for the last three, `checked` is when the source last confirmed the reviewed line. Not shown: an advisory its source ended (withdrawn or lifted, read
    from the source, for this draft or any draft of the same incident), one superseded by an ended
    notice, one past its stated expiry, and a page notice PAGE_TERM_DAYS after review when it gives
    no end."""
    today = _local(now)
    drafts = (check or {}).get("drafts", {})
    run_at = _utc((check or {}).get("checked_at"))
    out: dict[str, list[dict]] = {}
    positive = lambda d: isinstance(d, dict) and d.get("status") in ENDED and "gone" not in (d.get("flags") or [])
    ended_incidents = {d.get("feed_id") for d in drafts.values() if positive(d) and d.get("feed_id")}
    for did, a in approvals.items():
        exp = _day(a.get("expiry"))
        if exp and exp < today:
            continue
        if a["kind"] == "page" and not exp and today > _local(a["when"]) + timedelta(days=PAGE_TERM_DAYS):
            continue
        d = drafts.get(did)
        if a.get("incident_id") and a["incident_id"] in ended_incidents:
            continue
        if isinstance(d, dict):
            if positive(d):
                continue
            newer = drafts.get(d.get("superseded_by") or "")
            # Superseded by a notice that ended it: only a positive end read from the source counts, never
            # a synthesized "gone" withdrawal.
            if "superseded" in (d.get("flags") or []) and positive(newer):
                continue
        confirmed = _utc(d.get("fetched_at")) if isinstance(d, dict) else None
        confirmed = max(filter(None, (confirmed, _utc(a["fetched_at"]))))
        if isinstance(d, dict) and "gone" in (d.get("flags") or []):
            state, checked = "gone", confirmed
        elif isinstance(d, dict) and d.get("line") and d["line"] != a["line"]:
            state, checked = "changed", _utc(a["fetched_at"])
        elif isinstance(d, dict) and "unverified" in (d.get("flags") or []):
            state, checked = "unverified", confirmed
        elif isinstance(d, dict) and run_at and (today - _local(run_at)).days <= RECHECK_DAYS:
            state, checked = "checked", run_at
        else:
            state, checked = "stale", max(filter(None, (run_at if isinstance(d, dict) else None, confirmed)))
        out.setdefault(a["spot_id"], []).append({
            "line": a["line"], "publisher": a["publisher"], "link": a["link"], "since": a["start"],
            "checked": _local(checked).isoformat(), "state": state, "_order": (a["start"], a["reviewed_at"]),
            "restricts": a["restricts"]})
    for items in out.values():
        items.sort(key=lambda x: x.pop("_order"), reverse=True)
    return out
