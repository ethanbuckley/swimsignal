"""site.yml's time limits. On 24 Nov 2026 the build that followed a merge was cancelled seconds from the end, with
nothing published (run 45426174017): the tests and the build shared one limit of 25 minutes, the tests took 9.2 of
them and the build needed about 15.9. Each long step now has its own limit and the job's is their sum and a
margin, so a slow test run cannot use up the build's time. Read as text: PyYAML is not a dependency."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = (ROOT / ".github" / "workflows" / "site.yml").read_text()
BUILD = WF.split("\n  build:\n", 1)[1].split("\n  deploy:\n", 1)[0]

TESTS_STEP = "Tests (the build does not run if these fail)"
BUILD_STEP = "Build forecasts and site"


def _limit(step_name: str) -> int | None:
    """timeout-minutes of the named step of the build job, or None where it has none."""
    step = BUILD.split(f"      - name: {step_name}\n", 1)[1].split("\n      - ", 1)[0]
    m = re.search(r"^        timeout-minutes: (\d+)\b", step, re.M)
    return int(m.group(1)) if m else None


def _job_limit() -> int:
    return int(re.search(r"^    timeout-minutes: (\d+)$", BUILD, re.M).group(1))


def test_the_tests_and_the_build_each_have_their_own_limit():
    assert _limit(TESTS_STEP) is not None
    assert _limit(BUILD_STEP) is not None


def test_the_job_allows_both_steps_their_whole_limit_and_the_rest_of_the_job():
    # Under the sum, a tests step inside its own limit could still stop the build before the build's limit.
    # The rest (checkout, install, state, artifact) took 88 s at most in the 169 runs that finished, 31 Oct to 24 Nov 2026.
    assert _job_limit() >= _limit(TESTS_STEP) + _limit(BUILD_STEP) + 3


def test_the_limits_cover_the_slowest_runs_seen():
    # 200 runs, 31 Oct to 24 Nov 2026: tests at most 10.3 min; the build at most 13.9 where it finished, and
    # about 15.9 on 24 Nov had it not been cancelled. Test Python's own job limit is 10.
    assert _limit(TESTS_STEP) >= 15
    assert _limit(BUILD_STEP) >= 25


def test_no_other_step_of_the_build_job_runs_the_tests_or_the_build():
    # The limits are found by step name; a second step doing either would have none.
    assert BUILD.count("uv run pytest") == 1
    assert BUILD.count("scripts/build_site.py") == 1


def test_a_push_build_also_asks_whether_test_python_passed_its_commit():
    # The second attempt of 24 Nov 2026 was a push run, so it did not ask and ran the tests for 9 minutes, 36 minutes
    # after Test Python had passed that commit. Any run on main asks; the tests run here unless the answer is yes.
    ask = BUILD.split("      - name: Did Test Python already pass this commit on main?\n", 1)[1].split("\n      - ", 1)[0]
    assert re.search(r"^        if: github\.ref == 'refs/heads/main'$", ask, re.M)
    assert "event_name" not in ask.split("run: |", 1)[0]
    # Only a successful run of this exact commit, pushed to main, counts.
    assert "head_sha=$GITHUB_SHA&branch=main&event=push&status=success" in ask
    tests = BUILD.split(f"      - name: {TESTS_STEP}\n", 1)[1].split("\n      - ", 1)[0]
    assert re.search(r"^        if: steps\.tested\.outputs\.passed != 'true'$", tests, re.M)


def test_a_suite_too_slow_for_the_build_fails_on_the_pull_request_first():
    # Test Python runs the same pytest command on every pull request, under a shorter limit than the build's
    # tests step: a suite that would stop the build is stopped there, before the merge.
    py = (ROOT / ".github" / "workflows" / "python-tests.yml").read_text()
    assert int(re.search(r"^    timeout-minutes: (\d+)$", py, re.M).group(1)) < _limit(TESTS_STEP)
    cmd = re.search(r"^        run: (uv run pytest .+?)(?:\s+#.*)?$", py, re.M).group(1)
    assert f"run: {cmd}\n" in BUILD + "\n"
