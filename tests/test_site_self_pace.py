"""site.yml's self-pacing (job next-build): off unless SELF_PACE is 1, cannot fail the run or pile up, asks
for the next run GAP_MIN minutes after the build started. Read as text: PyYAML is not a dependency."""
import os
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WF = (ROOT / ".github" / "workflows" / "site.yml").read_text()


def _block(text: str, header: str, indent: int) -> str:
    """The lines from `header` (at `indent` spaces) to the next line at that indent or less."""
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln == " " * indent + header)
    out = [lines[start]]
    for ln in lines[start + 1:]:
        if ln.strip() and not ln.startswith(" " * (indent + 1)) and not ln.lstrip().startswith("#"):
            break
        out.append(ln)
    return "\n".join(out)


def _step(job: str, name_start: str) -> str:
    return job.split(f"- name: {name_start}", 1)[1].split("\n      - ", 1)[0]


def _run_script(step: str) -> str:
    body = step.split("run: |\n", 1)[1]
    return textwrap.dedent(body)


JOB = _block(WF, "next-build:", 2)


def test_the_switch_is_off_unless_the_variable_is_1_and_only_on_main():
    cond = re.search(r"^    if: \$\{\{ (.+) \}\}$", JOB, re.M).group(1)
    assert "vars.SELF_PACE == '1'" in cond
    assert "github.ref == 'refs/heads/main'" in cond
    # After a failed build too, but never after a cancel: cancelling is how to stop the chain.
    assert "!cancelled()" in cond and "always()" not in cond
    assert re.search(r"^    needs: build$", JOB, re.M)


def test_the_job_has_only_actions_write_and_runs_no_repository_code():
    perms = _block(JOB, "permissions:", 4)
    assert [ln.split("#")[0].strip() for ln in perms.splitlines()[1:] if ln.split("#")[0].strip()] == ["actions: write"]
    assert "uses:" not in JOB   # no checkout, no actions: only the shell and gh
    # The workflow's own default stays read-only.
    top = WF.split("\njobs:", 1)[0]
    assert re.search(r"^permissions:\n  contents: read$", top, re.M)


def test_the_chain_step_cannot_fail_the_job_or_the_run():
    assert re.search(r"^    continue-on-error: true$", JOB, re.M)        # the job: the run's result
    assert re.search(r"^        continue-on-error: true$", JOB, re.M)    # the step
    assert re.search(r"^    timeout-minutes: (\d+)$", JOB, re.M)
    timeout = int(re.search(r"^    timeout-minutes: (\d+)$", JOB, re.M).group(1))
    gap = int(re.search(r'GAP_MIN: "(\d+)"', JOB).group(1))
    assert gap == 30 and timeout > gap   # the longest wait is the whole gap


def test_the_build_and_deploy_do_not_wait_for_it():
    needs = re.findall(r"^    needs: (.+)$", WF, re.M)
    assert needs == ["build", "build", "build"]   # deploy, deploy-cloudflare, next-build


def test_one_group_one_running_and_the_schedule_stays():
    assert re.search(r"^concurrency:\n  group: site\n  cancel-in-progress: false$", WF, re.M)
    assert "concurrency:" not in JOB   # a job-level group of its own would let chains run beside builds
    assert re.findall(r'cron: "([^"]+)"', WF) == ["*/30 * * * *"]


def test_a_chained_run_says_so_and_is_not_a_manual_run():
    chain = _block(WF, "chain:", 6)
    assert "type: boolean" in chain and "default: false" in chain
    publish = _step(_block(WF, "build:", 2), "Publish state to the rolling release")
    assert re.search(r"^          CHAIN: \$\{\{ inputs\.chain \}\}", publish, re.M)
    assert '[ "$GITHUB_EVENT_NAME" = "workflow_dispatch" ] && [ "$CHAIN" != true ]' in publish
    assert 'if [ "$manual" = true ] || [ -n "$stale" ]; then' in publish
    heartbeat = _step(_block(WF, "build:", 2), "Heartbeat commit")
    assert re.search(r"^        if: github\.event_name == 'schedule' \|\| inputs\.chain$", heartbeat, re.M)


def test_the_build_writes_its_start_time_for_the_wait():
    build = _block(WF, "build:", 2)
    assert "started: ${{ steps.host.outputs.started }}" in build
    assert 'echo "started=$(date -u +%s)" >> "$GITHUB_OUTPUT"' in _step(build, "Choose the host")
    assert "STARTED: ${{ needs.build.outputs.started }}" in JOB


NOW = 1_800_000_000


@pytest.mark.parametrize("started, gh_exit, slept", [
    (str(NOW - 14 * 60), 0, 16 * 60),   # a 14-minute build waits the rest of the 30
    (str(NOW - 40 * 60), 0, None),      # a build over 30 minutes asks at once
    ("", 0, 30 * 60),                   # no start time: the whole gap, never a fast loop
    ("garbage", 0, 30 * 60),
    (str(NOW - 14 * 60), 1, 16 * 60),   # GitHub refuses: a warning, and the step still succeeds
])
def test_the_step_waits_then_asks_for_main_with_chain_true(tmp_path, started, gh_exit, slept):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    log = tmp_path / "log"
    for name, body in {"date": f'echo {NOW}', "sleep": f'echo "sleep $*" >> {log}',
                       "gh": f'echo "gh $*" >> {log}; exit {gh_exit}'}.items():
        (bin_ / name).write_text(f"#!/bin/sh\n{body}\n")
        (bin_ / name).chmod(0o755)
    script = _run_script(_step(JOB, "Wait until GAP_MIN"))
    env = {"PATH": f"{bin_}:{os.environ['PATH']}", "STARTED": started, "GAP_MIN": "30",
           "GITHUB_REPOSITORY": "owner/repo", "GH_TOKEN": "x"}
    # GitHub's default shell for run steps.
    res = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
                         env=env, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    calls = log.read_text().splitlines()
    want = ([f"sleep {slept}"] if slept else []) + ["gh workflow run site.yml -R owner/repo --ref main -f chain=true"]
    assert calls == want
    assert ("::warning title=next-build::" in res.stdout) == bool(gh_exit)
