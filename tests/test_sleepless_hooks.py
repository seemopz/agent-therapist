from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import pytest

import shift
from conftest import SLEEPLESS_DIR

HOOK = SLEEPLESS_DIR / "hooks" / "hook.py"
EVENTS = ["stop", "prompt", "session-start", "stop-failure", "pre-tool-use"]


def run_hook(repo, event, payload=None, project_dir=None, **env):
    data = {"cwd": str(repo)}
    data.update(payload or {})
    e = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", ""),
         "CLAUDE_PROJECT_DIR": str(project_dir or repo), "SLEEPLESS_RETRY_SECONDS": "0"}
    e.update(env)
    return subprocess.run([sys.executable, str(HOOK), event], input=json.dumps(data),
                          capture_output=True, text=True, cwd=str(repo), env=e)


def out(r):
    return json.loads(r.stdout) if r.stdout.strip() else None


def set_state(repo, **changes):
    state = shift.load(repo)
    state.update(changes)
    shift.save(repo, state)


def age_heartbeat(repo, seconds=3600):
    p = repo / ".claude" / "sleepless" / "heartbeat"
    old = time.time() - seconds
    os.utime(str(p), (old, old))


@pytest.fixture
def shift_repo(git_repo):
    shift.start(git_repo, "night work", "stop", sources=["todo"])
    return git_repo


@pytest.mark.parametrize("event", EVENTS)
def test_no_shift_is_silent(git_repo, event):
    r = run_hook(git_repo, event, {"prompt": "stop", "tool_name": "Bash",
                                   "tool_input": {"command": "git push -f"}})
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_outside_git_repo_is_silent(tmp_path):
    r = run_hook(tmp_path, "stop")
    assert (r.returncode, r.stdout) == (0, "")


def test_unknown_event_is_silent(shift_repo):
    assert run_hook(shift_repo, "bogus").stdout == ""


def test_corrupt_state_reports_and_allows(git_repo):
    d = git_repo / ".claude" / "sleepless"
    d.mkdir(parents=True)
    (d / "state.json").write_text("{broken")
    r = run_hook(git_repo, "stop")
    assert r.returncode == 0
    assert "unreadable" in out(r)["systemMessage"]


def test_stop_blocks_while_active(shift_repo):
    r = run_hook(shift_repo, "stop")
    o = out(r)
    assert o["decision"] == "block" and "night work" in o["reason"]
    state = shift.load(shift_repo)
    assert state["last_stop"] and state["idle"]["streak"] == 1


@pytest.mark.parametrize("status", ["paused", "ending"])
def test_stop_passes_when_not_active(shift_repo, status):
    set_state(shift_repo, status=status)
    assert out(run_hook(shift_repo, "stop")) is None


def test_stop_passes_with_background_tasks(shift_repo):
    r = run_hook(shift_repo, "stop", {"background_tasks": [{"id": "t1", "type": "shell"}]})
    assert out(r) is None
    assert shift.load(shift_repo)["idle"]["streak"] == 0


def test_stop_after_deadline_starts_wrap_up(shift_repo):
    set_state(shift_repo, end={"kind": "hours", "at": "2000-01-01T00:00:00+00:00"})
    o = out(run_hook(shift_repo, "stop"))
    assert o["decision"] == "block" and "gh pr create" in o["reason"]
    assert shift.load(shift_repo)["status"] == "ending"


def test_stop_idle_pauses_after_limit(shift_repo):
    for _ in range(2):
        assert "next item" in out(run_hook(shift_repo, "stop", SLEEPLESS_IDLE_LIMIT="2"))["reason"]
    o = out(run_hook(shift_repo, "stop", SLEEPLESS_IDLE_LIMIT="2"))
    assert o["decision"] == "block" and "PushNotification" in o["reason"]
    assert shift.load(shift_repo)["status"] == "paused"
    assert out(run_hook(shift_repo, "stop", SLEEPLESS_IDLE_LIMIT="2")) is None


def test_stop_progress_resets_streak(shift_repo):
    run_hook(shift_repo, "stop")
    run_hook(shift_repo, "stop")
    assert shift.load(shift_repo)["idle"]["streak"] == 2
    (shift_repo / "work.txt").write_text("progress")
    run_hook(shift_repo, "stop")
    assert shift.load(shift_repo)["idle"]["streak"] == 1


@pytest.mark.parametrize("prompt", ["stop", "Stopp!", "  STOP. ", "hör auf", "hoer auf"])
def test_prompt_stop_starts_wrap_up(shift_repo, prompt):
    o = out(run_hook(shift_repo, "prompt", {"prompt": prompt}))
    assert "gh pr create" in o["hookSpecificOutput"]["additionalContext"]
    assert o["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert shift.load(shift_repo)["status"] == "ending"


@pytest.mark.parametrize("prompt", ["don't stop", "stop the build first", "weiter"])
def test_prompt_other_text_changes_nothing_while_active(shift_repo, prompt):
    assert out(run_hook(shift_repo, "prompt", {"prompt": prompt})) is None
    assert shift.load(shift_repo)["status"] == "active"


def test_prompt_resume_from_pause(shift_repo):
    set_state(shift_repo, status="paused", idle={"fingerprint": "abc", "streak": 7})
    o = out(run_hook(shift_repo, "prompt", {"prompt": "weiter"}))
    assert "resumed" in o["hookSpecificOutput"]["additionalContext"]
    state = shift.load(shift_repo)
    assert state["status"] == "active" and state["idle"]["streak"] == 0


def test_prompt_stop_while_paused_starts_wrap_up(shift_repo):
    set_state(shift_repo, status="paused")
    run_hook(shift_repo, "prompt", {"prompt": "stop"})
    assert shift.load(shift_repo)["status"] == "ending"


@pytest.mark.parametrize("source", ["startup", "resume"])
def test_session_start_wakes_with_old_heartbeat(shift_repo, source):
    age_heartbeat(shift_repo)
    r = run_hook(shift_repo, "session-start", {"source": source})
    assert r.returncode == 2 and "sleepless/" in r.stderr and "night work" in r.stderr


def test_session_start_skips_fresh_heartbeat(shift_repo):
    r = run_hook(shift_repo, "session-start", {"source": "startup"})
    assert (r.returncode, r.stderr) == (0, "")


def test_session_start_compact_wakes_even_with_fresh_heartbeat(shift_repo):
    assert run_hook(shift_repo, "session-start", {"source": "compact"}).returncode == 2


@pytest.mark.parametrize("status", ["paused", "ending"])
def test_session_start_silent_when_not_active(shift_repo, status):
    set_state(shift_repo, status=status)
    age_heartbeat(shift_repo)
    assert run_hook(shift_repo, "session-start", {"source": "startup"}).returncode == 0


def test_stop_failure_rewakes(shift_repo):
    r = run_hook(shift_repo, "stop-failure", {"error": "rate_limit"})
    assert r.returncode == 2 and "API error" in r.stderr


def test_stop_failure_silent_when_paused(shift_repo):
    set_state(shift_repo, status="paused")
    assert run_hook(shift_repo, "stop-failure", {"error": "rate_limit"}).returncode == 0


def test_pre_tool_use_denies_and_touches_heartbeat(shift_repo):
    age_heartbeat(shift_repo)
    r = run_hook(shift_repo, "pre-tool-use",
                 {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}})
    hso = out(r)["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "deny"
    assert "main/master" in hso["permissionDecisionReason"]
    assert shift.heartbeat_age(shift_repo) < 60


def test_pre_tool_use_allows_safe_command(shift_repo):
    r = run_hook(shift_repo, "pre-tool-use", {"tool_name": "Bash", "tool_input": {"command": "git status"}})
    assert out(r) is None


def test_worktree_cwd_falls_back_to_project_dir(shift_repo, tmp_path):
    other = tmp_path / "worktree"
    other.mkdir()
    subprocess.run(["git", "-C", str(other), "init", "-q"], check=True)
    r = run_hook(other, "stop", project_dir=shift_repo)
    assert out(r)["decision"] == "block"
