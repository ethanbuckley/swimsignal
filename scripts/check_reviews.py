"""Private moderation/storage summary for the operator's Codex heartbeat.

Reads ADMIN_TOKEN from Mac Keychain (or an environment variable on another host). Never writes
the credential, review text, names, ids or photos. State contains only aggregate counts and times.
Repeated unchanged conditions stay quiet; a new review/report, storage threshold or service
failure produces needs_attention=true. This script does not send any email or approve reviews.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import tempfile
from pathlib import Path

import httpx

DEFAULT_URL = "https://swimsignal-reviews.swimsignal-push.workers.dev/"
DEFAULT_STATE = Path(__file__).resolve().parents[1] / "state" / "reviews_monitor.json"


def credential() -> str:
    token = os.environ.get("SWIMSIGNAL_REVIEWS_ADMIN_TOKEN", "").strip()
    if not token:
        saved = subprocess.run(["security", "find-generic-password", "-s", "swimsignal-reviews-admin",
                                "-a", getpass.getuser(), "-w"], capture_output=True, text=True, timeout=15)
        if saved.returncode:
            raise RuntimeError("admin credential unavailable in Mac Keychain")
        token = saved.stdout.strip()
    if not token:
        raise RuntimeError("admin credential is empty")
    return token


def changed(summary: dict, previous: dict) -> tuple[dict, list[str]]:
    storage = summary["storage"]
    for value in (summary["pending"], summary["reported"], storage["cleanup_pending"],
                  storage["bytes"], storage["limit_bytes"]):
        if type(value) is not int or value < 0:
            raise ValueError("invalid aggregate count")
    for key in ("latest_pending_at", "latest_report_at"):
        if summary[key] is not None and not isinstance(summary[key], str):
            raise ValueError("invalid aggregate timestamp")
    if storage["level"] not in ("normal", "warning", "critical", "full"):
        raise ValueError("invalid storage level")
    snapshot = {k: summary[k] for k in ("pending", "reported", "latest_pending_at", "latest_report_at")}
    snapshot.update(storage_level=storage["level"], cleanup_pending=storage["cleanup_pending"], healthy=True)
    notices = []
    for key, when, label in (("pending", "latest_pending_at", "review"), ("reported", "latest_report_at", "report")):
        if snapshot[key] and (snapshot[key] > previous.get(key, 0) or
                              (snapshot[when] or "") > (previous.get(when) or "")):
            notices.append(f"New {label} to check; {snapshot[key]} waiting.")
    levels = {"normal": 0, "warning": 1, "critical": 2, "full": 3}
    if levels[storage["level"]] > levels.get(previous.get("storage_level", "normal"), 0):
        notices.append(f"Photo storage {storage['level']}: {storage['bytes'] / 1e6:.1f} MB of {storage['limit_bytes'] / 1e6:.0f} MB.")
    if storage["cleanup_pending"] > previous.get("cleanup_pending", 0):
        notices.append(f"Photo cleanup needs attention: {storage['cleanup_pending']} batches waiting for retry.")
    if previous.get("healthy") is False:
        notices.append("The review service is responding again.")
    return snapshot, notices


def save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement avoids a truncated checkpoint; mkstemp creates mode 0600.
    fd, name = tempfile.mkstemp(prefix=".reviews-monitor-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(state, out)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def check(url: str, state_path: Path, *, token=credential, get=httpx.get) -> dict:
    if url != DEFAULT_URL:
        raise ValueError("monitor credentials may only be sent to the configured SwimSignal review service")
    try:
        previous = json.loads(state_path.read_text())
        if not isinstance(previous, dict):
            raise ValueError("invalid monitor checkpoint")
    except (FileNotFoundError, ValueError):
        previous = {}
    try:
        response = get(url + "admin/summary", headers={"Authorization": "Bearer " + token()}, timeout=20)
        response.raise_for_status()
        snapshot, notices = changed(response.json(), previous)
    except (httpx.HTTPError, RuntimeError, subprocess.SubprocessError, OSError, KeyError, ValueError, TypeError) as exc:
        # Only a class/status is retained: server bodies and exceptions may contain private data.
        code = f"HTTP {exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
        snapshot = {**previous, "healthy": False, "error": code}
        notices = [f"The review monitor could not check the service ({code})."] if previous.get("healthy") is not False or previous.get("error") != code else []
    save(state_path, snapshot)
    return {"needs_attention": bool(notices), "notices": notices,
            "moderation_url": url + "moderate", "state": snapshot}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.environ.get("DIPCAST_REVIEWS_URL", DEFAULT_URL))
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()
    print(json.dumps(check(args.url, args.state), indent=2))


if __name__ == "__main__":
    main()
