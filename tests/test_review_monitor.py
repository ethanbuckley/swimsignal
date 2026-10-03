import importlib.util
import json
import stat
from pathlib import Path

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_reviews.py"
spec = importlib.util.spec_from_file_location("check_reviews", SCRIPT)
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


def summary(pending=0, reported=0, when=None, level="normal", cleanup=0):
    return {"pending": pending, "reported": reported, "latest_pending_at": when,
            "latest_report_at": when if reported else None, "storage": {
                "level": level, "cleanup_pending": cleanup, "bytes": 700_000_000,
                "limit_bytes": 800_000_000}}


def test_new_reviews_reports_and_storage_alert_once_then_stay_quiet(tmp_path):
    path = tmp_path / "state.json"
    data = summary(1, 1, "2026-10-03T19:00:00Z", "warning", 1)
    def get(url, **kwargs):
        assert kwargs["headers"] == {"Authorization": "Bearer secret-test-only"}
        return httpx.Response(200, json=data, request=httpx.Request("GET", url))
    first = monitor.check(monitor.DEFAULT_URL, path, token=lambda: "secret-test-only", get=get)
    assert first["needs_attention"] and len(first["notices"]) == 4
    assert not monitor.check(monitor.DEFAULT_URL, path, token=lambda: "secret-test-only", get=get)["needs_attention"]
    data["latest_pending_at"] = "2026-10-03T19:05:00Z"  # same queue count, different new arrival
    assert len(monitor.check(monitor.DEFAULT_URL, path, token=lambda: "secret-test-only", get=get)["notices"]) == 1
    assert "secret-test-only" not in path.read_text()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_removals_stay_quiet_and_recovered_service_is_announced(tmp_path):
    path = tmp_path / "state.json"
    monitor.save(path, {"pending": 2, "reported": 1, "healthy": True, "storage_level": "warning"})
    def success(url, **kwargs):
        return httpx.Response(200, json=summary(), request=httpx.Request("GET", url))
    assert not monitor.check(monitor.DEFAULT_URL, path, token=lambda: "test", get=success)["needs_attention"]
    def failure(url, **kwargs):
        return httpx.Response(503, text="private server details", request=httpx.Request("GET", url))
    assert monitor.check(monitor.DEFAULT_URL, path, token=lambda: "test", get=failure)["needs_attention"]
    assert not monitor.check(monitor.DEFAULT_URL, path, token=lambda: "test", get=failure)["needs_attention"]
    assert "private server details" not in path.read_text()
    recovered = monitor.check(monitor.DEFAULT_URL, path, token=lambda: "test", get=success)
    assert recovered["notices"] == ["The review service is responding again."]


def test_monitor_does_not_send_credentials_to_another_host(tmp_path):
    def forbidden():
        pytest.fail("credential must not be read")
    with pytest.raises(ValueError):
        monitor.check("https://example.org/", tmp_path / "state.json", token=forbidden)


def test_corrupt_checkpoint_and_invalid_server_summary(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{broken")
    def get(url, **kwargs):
        data = summary()
        data["pending"] = "private invalid value"
        return httpx.Response(200, json=data, request=httpx.Request("GET", url))
    result = monitor.check(monitor.DEFAULT_URL, path, token=lambda: "test", get=get)
    assert result["needs_attention"] and result["state"]["error"] == "ValueError"
    assert "private invalid value" not in path.read_text()
