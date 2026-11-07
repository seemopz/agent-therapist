from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import threading
import time

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
    return (repo / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines().count(".claude/sleepless/")


def run_cli(cwd, *args):
    return subprocess.run([sys.executable, str(SHIFT), *args], cwd=cwd, capture_output=True, text=True)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def add_worktree(repo, name="wt"):
    wt = repo / ".claude" / "worktrees" / name
    git(repo, "worktree", "add", "-q", "--detach", str(wt))
    return wt


def test_start_keeps_branch_and_writes_state_exclude_and_report(git_repo):
    state = shift.start(git_repo, "docs cleanup", "stop", sources=["todo"], start_time=T0)
    assert "branch" not in state
    assert state["version"] == 2
    assert state["base"] == "main"
    assert state["report"] == ".claude/sleepless/reports/2026-09-25-docs-cleanup.md"
    assert state["status"] == "active"
    assert state["end"] == {"kind": "stop", "at": None}
    assert state["idle"] == {"fingerprint": "", "streak": 0}
    assert current_branch(git_repo) == "main"
    assert shift.load(git_repo) == state
    assert exclude_count(git_repo) == 1
    report = (git_repo / state["report"]).read_text(encoding="utf-8")
    assert "docs cleanup" in report and "Base `main`" in report
    assert "{{" not in report
    assert state["session_id"] is None
    porcelain = subprocess.run(["git", "-C", str(git_repo), "status", "--porcelain"],
                               capture_output=True, text=True).stdout
    assert porcelain == ""


def test_start_report_name_gets_suffix_when_taken(git_repo):
    reports = git_repo / ".claude" / "sleepless" / "reports"
    reports.mkdir(parents=True)
    (reports / "2026-09-25-x.md").write_text("old\n", encoding="utf-8")
    state = shift.start(git_repo, "X!", "stop", start_time=T0)
    assert state["report"].endswith("/2026-09-25-x-2.md")
    assert (reports / "2026-09-25-x.md").read_text(encoding="utf-8") == "old\n"


def test_start_refuses_detached_head(git_repo):
    git(git_repo, "switch", "-q", "--detach")
    with pytest.raises(shift.ShiftError, match="detached"):
        shift.start(git_repo, "a", "stop", start_time=T0)


def test_start_refuses_second_shift(git_repo):
    shift.start(git_repo, "a", "stop", start_time=T0)
    with pytest.raises(shift.ShiftError, match="already active"):
        shift.start(git_repo, "b", "stop", start_time=T0)


def test_start_rejects_unknown_source_before_touching_git(git_repo):
    with pytest.raises(shift.ShiftError, match="unknown sources"):
        shift.start(git_repo, "a", "stop", sources=["tracker"], start_time=T0)
    assert current_branch(git_repo) == "main"


def test_branch_name_slug_and_suffix_when_local_or_remote_branch_exists(git_repo):
    assert shift.branch_name(git_repo, "fix", "  Login Crash, Safari!  ") == "fix/login-crash-safari"
    assert len(shift.branch_name(git_repo, "docs", "a" * 80)) == len("docs/") + 40
    git(git_repo, "branch", "feat/dark-mode")
    git(git_repo, "update-ref", "refs/remotes/origin/feat/dark-mode-2", "HEAD")
    assert shift.branch_name(git_repo, "feat", "Dark mode") == "feat/dark-mode-3"


@pytest.mark.parametrize("kind,topic,match", [("feature", "x", "unknown branch type"),
                                              ("fix", "!!", "letters or digits")])
def test_branch_name_rejects_bad_input(git_repo, kind, topic, match):
    with pytest.raises(shift.ShiftError, match=match):
        shift.branch_name(git_repo, kind, topic)


def test_join_from_worktree_switches_branch_and_registers_worker(git_repo):
    shift.start(git_repo, "a", "stop", start_time=T0)
    wt = add_worktree(git_repo)
    r = run_cli(wt, "join", "fix/login")
    assert r.returncode == 0, r.stderr
    assert current_branch(wt) == "fix/login"
    assert current_branch(git_repo) == "main"
    worker = json.loads((git_repo / ".claude/sleepless/workers/fix--login.json").read_text())
    assert worker["branch"] == "fix/login" and worker["status"] == "running"
    assert worker["pr"] is None and worker["note"] == ""
    assert not (wt / ".claude" / "sleepless").exists()
    assert run_cli(wt, "join", "fix/login").returncode == 0  # already on the branch: no-op


def test_join_from_ref(git_repo):
    shift.start(git_repo, "a", "stop", start_time=T0)
    git(git_repo, "branch", "feat/base-task")
    git(git_repo, "commit", "-q", "--allow-empty", "-m", "later on main")
    wt = add_worktree(git_repo)
    shift.join(git_repo, wt, "feat/follow-up", "feat/base-task")
    assert git(wt, "rev-parse", "HEAD") == git(git_repo, "rev-parse", "feat/base-task")


def test_join_switches_to_an_existing_branch_on_restart(git_repo):
    shift.start(git_repo, "a", "stop", start_time=T0)
    git(git_repo, "branch", "fix/x")
    git(git_repo, "commit", "-q", "--allow-empty", "-m", "later on main")
    wt = add_worktree(git_repo)
    shift.join(git_repo, wt, "fix/x")
    assert current_branch(wt) == "fix/x"
    assert git(wt, "rev-parse", "HEAD") != git(git_repo, "rev-parse", "main")


def test_start_refuses_linked_worktree(git_repo):
    wt = add_worktree(git_repo)
    git(wt, "switch", "-q", "-c", "side")
    with pytest.raises(shift.ShiftError, match="main checkout"):
        shift.start(wt, "a", "stop", start_time=T0)
    assert shift.load(wt) is None


def test_join_refuses_main_checkout(git_repo):
    shift.start(git_repo, "a", "stop", start_time=T0)
    with pytest.raises(shift.ShiftError, match="own git worktree"):
        shift.join(git_repo, git_repo, "fix/x")
    assert current_branch(git_repo) == "main"


def test_done_updates_worker(git_repo):
    shift.start(git_repo, "a", "stop", start_time=T0)
    shift.join(git_repo, add_worktree(git_repo), "fix/x")
    r = run_cli(git_repo, "done", "fix/x", "--status", "done", "--pr", "https://example.com/pr/1")
    assert r.returncode == 0, r.stderr
    [worker] = json.loads(run_cli(git_repo, "workers").stdout)
    assert (worker["status"], worker["pr"], worker["note"]) == ("done", "https://example.com/pr/1", "")
    shift.done(git_repo, "fix/x", "blocked", note="needs a decision")
    assert shift.workers(git_repo)[0]["note"] == "needs a decision"
    with pytest.raises(shift.ShiftError, match="no worker"):
        shift.done(git_repo, "fix/other", "done")


def test_wait_returns_immediately_without_running_workers_and_touches_heartbeat(git_repo):
    shift.start(git_repo, "a", "stop", start_time=T0)
    old = time.time() - 3600
    os.utime(str(git_repo / ".claude" / "sleepless" / "heartbeat"), (old, old))
    r = run_cli(git_repo, "wait", "--timeout-minutes", "5")
    assert (r.returncode, json.loads(r.stdout)) == (0, {"reason": "none_running", "workers": []})
    assert shift.heartbeat_age(git_repo) < 5


def test_wait_returns_when_a_running_worker_changes_status(git_repo, monkeypatch):
    monkeypatch.setenv("SLEEPLESS_POLL_SECONDS", "0.05")
    shift.start(git_repo, "a", "stop", start_time=T0)
    shift.join(git_repo, add_worktree(git_repo), "fix/x")
    result = []
    t = threading.Thread(target=lambda: result.append(shift.wait(git_repo, timeout_minutes=1)))
    t.start()
    time.sleep(0.3)
    assert t.is_alive()
    shift.done(git_repo, "fix/x", "done")
    t.join(5)
    assert result[0]["reason"] == "status" and result[0]["workers"][0]["status"] == "done"


def test_wait_counts_only_workers_that_go_stale_during_the_wait(git_repo, monkeypatch):
    monkeypatch.setenv("SLEEPLESS_POLL_SECONDS", "0.05")
    shift.start(git_repo, "a", "stop", start_time=T0)
    shift.join(git_repo, add_worktree(git_repo), "fix/x")
    assert shift.wait(git_repo, timeout_minutes=0.005)["reason"] == "timeout"
    monkeypatch.setattr(shift, "WORKER_STALE_SECONDS", 0.3)
    shift.worker_path(git_repo, "fix/x", ".heartbeat").touch()
    assert shift.wait(git_repo, timeout_minutes=1)["reason"] == "stale"
    assert shift.wait(git_repo, timeout_minutes=0.005)["reason"] == "timeout"  # stale at start


@pytest.mark.parametrize("changes,reason", [
    ({"end": {"kind": "hours", "at": "2000-01-01T00:00:00+00:00"}}, "deadline"),
    ({"status": "ending"}, "shift_inactive"),
])
def test_wait_returns_on_deadline_or_inactive_shift(git_repo, changes, reason):
    shift.start(git_repo, "a", "stop", start_time=T0)
    shift.join(git_repo, add_worktree(git_repo), "fix/x")
    shift.save(git_repo, dict(shift.load(git_repo), **changes))
    assert shift.wait(git_repo, timeout_minutes=1)["reason"] == reason


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


def test_end_then_finish_removes_state_but_keeps_reports(git_repo):
    state = shift.start(git_repo, "a", "stop", start_time=T0)
    shift.join(git_repo, add_worktree(git_repo), "fix/x")
    with pytest.raises(shift.ShiftError, match="end"):
        shift.finish(git_repo)
    assert shift.end(git_repo)["status"] == "ending"
    with pytest.raises(shift.ShiftError, match="still running: fix/x"):
        shift.finish(git_repo)
    shift.done(git_repo, "fix/x", "blocked")
    shift.finish(git_repo)
    assert shift.load(git_repo) is None
    d = git_repo / ".claude" / "sleepless"
    assert sorted(p.name for p in d.iterdir()) == ["reports"]
    assert (git_repo / state["report"]).is_file()


def test_commands_without_shift_fail(git_repo):
    for fn in (shift.end, shift.finish, shift.status):
        with pytest.raises(shift.ShiftError, match="no active shift"):
            fn(git_repo)


def test_fingerprint_changes_with_working_tree(git_repo):
    before = shift.fingerprint(git_repo)
    (git_repo / "new.txt").write_text("x", encoding="utf-8")
    assert shift.fingerprint(git_repo) != before


@pytest.mark.parametrize("name", ["README.md", "new.txt", " spaced ü.txt"])
def test_fingerprint_changes_with_repeated_edits(git_repo, name):
    path = git_repo / name
    path.write_text("first edit", encoding="utf-8")
    before = shift.fingerprint(git_repo)
    path.write_text("second edit", encoding="utf-8")
    assert shift.fingerprint(git_repo) != before


def test_fingerprint_handles_non_utf8_tracked_content(git_repo):
    path = git_repo / "README.md"
    path.write_bytes(b"first \xff edit")
    before = shift.fingerprint(git_repo)
    path.write_bytes(b"second \xff edit")
    assert shift.fingerprint(git_repo) != before


def test_fingerprint_changes_when_a_ref_moves(git_repo):
    before = shift.fingerprint(git_repo)
    git(git_repo, "branch", "fix/x")
    after_branch = shift.fingerprint(git_repo)
    assert after_branch != before
    wt = add_worktree(git_repo)
    git(wt, "switch", "-q", "fix/x")
    git(wt, "commit", "-q", "--allow-empty", "-m", "worker commit")
    assert shift.fingerprint(git_repo) != after_branch


def test_fingerprint_skips_untracked_nested_worktree(git_repo):
    add_worktree(git_repo)
    before = shift.fingerprint(git_repo)
    assert shift.fingerprint(git_repo) == before


def test_fingerprint_changes_with_report_and_worker_files(git_repo):
    state = shift.start(git_repo, "a", "stop", start_time=T0)
    before = shift.fingerprint(git_repo)
    (git_repo / state["report"]).write_text("progress", encoding="utf-8")
    after_report = shift.fingerprint(git_repo)
    assert after_report != before
    shift.join(git_repo, add_worktree(git_repo), "fix/x")
    after_join = shift.fingerprint(git_repo)
    shift.done(git_repo, "fix/x", "done")
    assert len({after_report, after_join, shift.fingerprint(git_repo)}) == 3


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
    (d / "state.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        shift.load(git_repo)


def test_wrap_up_names_base_report_and_steps():
    text = shift.wrap_up({"label": "x", "base": "main", "report": ".claude/sleepless/reports/r.md"})
    assert "against `main`" in text and "`.claude/sleepless/reports/r.md`" in text
    assert "shift.py wait" in text and "shift.py finish" in text
    assert "Never merge" in text and "PushNotification" in text


def test_version_1_state_still_loads_for_status_end_finish(git_repo):
    d = git_repo / ".claude" / "sleepless"
    d.mkdir(parents=True)
    (d / "state.json").write_text(json.dumps({
        "version": 1, "label": "old", "branch": "sleepless/2026-09-25", "base": "main",
        "started": T0.isoformat(), "end": {"kind": "stop", "at": None}, "sources": [],
        "status": "active", "idle": {"fingerprint": "", "streak": 0}, "last_stop": None,
        "session_id": None}), encoding="utf-8")
    assert shift.status(git_repo)["report"] is None
    assert "the shift report" in shift.wrap_up(shift.end(git_repo))
    shift.finish(git_repo)
    assert shift.load(git_repo) is None


def test_cli_round_trip(git_repo):
    r = run_cli(git_repo, "start", "--label", "x", "--end", "hours", "--hours", "2",
                "--sources", "todo,propose")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["sources"] == ["todo", "propose"]
    s = json.loads(run_cli(git_repo, "status").stdout)
    assert s["deadline_passed"] is False
    assert s["heartbeat_minutes"] is not None
    r = run_cli(git_repo, "end")
    assert r.returncode == 0 and "against `main`" in r.stdout
    assert run_cli(git_repo, "finish").returncode == 0
    r = run_cli(git_repo, "status")
    assert r.returncode == 1 and "no active shift" in r.stderr


def test_cli_outside_git_repo(tmp_path):
    r = run_cli(tmp_path, "status")
    assert r.returncode == 1 and "not inside a git repo" in r.stderr
