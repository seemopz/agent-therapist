from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys

import pytest

import shift
from conftest import SLEEPLESS_DIR

SHIFT = SLEEPLESS_DIR / "scripts" / "shift.py"
TZ = dt.timezone(dt.timedelta(hours=2))
T0 = dt.datetime(2026, 9, 25, 22, 10, tzinfo=TZ)


def current_branch(repo) -> str:
    return subprocess.run(["git", "-C", str(repo), "branch", "--show-current"],
                          capture_output=True, text=True).stdout.strip()


def exclude_count(repo) -> int:
    return (repo / ".git" / "info" / "exclude").read_text().splitlines().count(".claude/sleepless/")


def run_cli(cwd, *args):
    return subprocess.run([sys.executable, str(SHIFT), *args], cwd=cwd, capture_output=True, text=True)


def test_start_creates_branch_state_exclude_and_report(git_repo):
    state = shift.start(git_repo, "docs cleanup", "stop", sources=["todo"], start_time=T0)
    assert state["branch"] == "sleepless/2026-09-25"
    assert state["base"] == "main"
    assert state["status"] == "active"
    assert state["end"] == {"kind": "stop", "at": None}
    assert state["idle"] == {"fingerprint": "", "streak": 0}
    assert current_branch(git_repo) == "sleepless/2026-09-25"
    assert shift.load(git_repo) == state
    assert exclude_count(git_repo) == 1
    report = (git_repo / "SLEEPLESS-REPORT.md").read_text()
    assert "docs cleanup" in report and "sleepless/2026-09-25" in report
    assert "{{" not in report
    assert state["session_id"] is None
    porcelain = subprocess.run(["git", "-C", str(git_repo), "status", "--porcelain"],
                               capture_output=True, text=True).stdout
    assert ".claude" not in porcelain


def test_start_overwrites_existing_report(git_repo):
    (git_repo / "SLEEPLESS-REPORT.md").write_text("old label\n")
    subprocess.run(["git", "-C", str(git_repo), "add", "SLEEPLESS-REPORT.md"], check=True)
    subprocess.run(["git", "-C", str(git_repo), "commit", "-qm", "old report"], check=True)
    shift.start(git_repo, "new label", "stop", start_time=T0)
    report = (git_repo / "SLEEPLESS-REPORT.md").read_text()
    assert "new label" in report
    assert "old label" not in report


def test_start_refuses_second_shift(git_repo):
    shift.start(git_repo, "a", "stop", start_time=T0)
    with pytest.raises(shift.ShiftError, match="already active"):
        shift.start(git_repo, "b", "stop", start_time=T0)


def test_start_rejects_unknown_source_before_touching_git(git_repo):
    with pytest.raises(shift.ShiftError, match="unknown sources"):
        shift.start(git_repo, "a", "stop", sources=["tracker"], start_time=T0)
    assert current_branch(git_repo) == "main"


def test_branch_suffix_when_local_or_remote_branch_exists(git_repo):
    subprocess.run(["git", "-C", str(git_repo), "branch", "sleepless/2026-09-25"], check=True)
    subprocess.run(["git", "-C", str(git_repo), "update-ref",
                    "refs/remotes/origin/sleepless/2026-09-25-2", "HEAD"], check=True)
    assert shift.branch_name(git_repo, "2026-09-25") == "sleepless/2026-09-25-3"


def test_exclude_line_added_once(git_repo):
    shift.add_exclude(git_repo)
    shift.add_exclude(git_repo)
    assert exclude_count(git_repo) == 1


@pytest.mark.parametrize("at,expected", [
    ("23:30", dt.datetime(2026, 9, 25, 23, 30, tzinfo=TZ)),
    ("07:00", dt.datetime(2026, 9, 26, 7, 0, tzinfo=TZ)),
])
def test_deadline_at_time_is_next_occurrence(at, expected):
    assert shift.compute_deadline(T0, "time", at=at) == expected


def test_deadline_hours():
    assert shift.compute_deadline(T0, "hours", hours=1.5) == T0 + dt.timedelta(minutes=90)


def test_deadline_none_for_stop_and_list():
    assert shift.compute_deadline(T0, "stop") is None
    assert shift.compute_deadline(T0, "list") is None


@pytest.mark.parametrize("at", ["7", "25:00", "07:61", None])
def test_deadline_rejects_bad_time(at):
    with pytest.raises(shift.ShiftError, match="HH:MM"):
        shift.compute_deadline(T0, "time", at=at)


@pytest.mark.parametrize("hours", [0, -1, None])
def test_deadline_rejects_non_positive_hours(hours):
    with pytest.raises(shift.ShiftError, match="positive"):
        shift.compute_deadline(T0, "hours", hours=hours)


def test_deadline_passed():
    state = {"end": {"kind": "hours", "at": (T0 + dt.timedelta(hours=1)).isoformat()}}
    assert not shift.deadline_passed(state, T0)
    assert shift.deadline_passed(state, T0 + dt.timedelta(hours=1))
    assert not shift.deadline_passed({"end": {"kind": "stop", "at": None}}, T0)


def test_end_then_finish_removes_state(git_repo):
    shift.start(git_repo, "a", "stop", start_time=T0)
    with pytest.raises(shift.ShiftError, match="end"):
        shift.finish(git_repo)
    assert shift.end(git_repo)["status"] == "ending"
    shift.finish(git_repo)
    assert shift.load(git_repo) is None
    assert not (git_repo / ".claude" / "sleepless").exists()


def test_commands_without_shift_fail(git_repo):
    for fn in (shift.end, shift.finish, shift.status):
        with pytest.raises(shift.ShiftError, match="no active shift"):
            fn(git_repo)


def test_fingerprint_changes_with_working_tree(git_repo):
    before = shift.fingerprint(git_repo)
    (git_repo / "new.txt").write_text("x")
    assert shift.fingerprint(git_repo) != before


def test_fingerprint_ignores_state_dir(git_repo):
    shift.start(git_repo, "a", "stop", start_time=T0)
    before = shift.fingerprint(git_repo)
    shift.touch_heartbeat(git_repo)
    shift.save(git_repo, dict(shift.load(git_repo), last_stop="x"))
    assert shift.fingerprint(git_repo) == before


def test_heartbeat_age(git_repo):
    assert shift.heartbeat_age(git_repo) is None
    shift.start(git_repo, "a", "stop", start_time=T0)
    assert 0 <= shift.heartbeat_age(git_repo) < 5


def test_load_raises_on_corrupt_state(git_repo):
    d = git_repo / ".claude" / "sleepless"
    d.mkdir(parents=True)
    (d / "state.json").write_text("{not json")
    with pytest.raises(ValueError):
        shift.load(git_repo)


def test_wrap_up_names_branch_base_and_pr():
    text = shift.wrap_up({"label": "x", "branch": "sleepless/2026-09-25", "base": "main"})
    assert "gh pr create --base main --head sleepless/2026-09-25" in text
    assert "Never merge" in text and "PushNotification" in text


def test_cli_round_trip(git_repo):
    r = run_cli(git_repo, "start", "--label", "x", "--end", "hours", "--hours", "2",
                "--sources", "todo,propose")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["sources"] == ["todo", "propose"]
    s = json.loads(run_cli(git_repo, "status").stdout)
    assert s["deadline_passed"] is False
    assert s["heartbeat_minutes"] is not None
    r = run_cli(git_repo, "end")
    assert r.returncode == 0 and "gh pr create --base main" in r.stdout
    assert run_cli(git_repo, "finish").returncode == 0
    r = run_cli(git_repo, "status")
    assert r.returncode == 1 and "no active shift" in r.stderr


def test_cli_outside_git_repo(tmp_path):
    r = run_cli(tmp_path, "status")
    assert r.returncode == 1 and "not inside a git repo" in r.stderr
