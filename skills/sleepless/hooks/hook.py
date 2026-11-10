"""Hook entry point for the sleepless skill.

Usage: hook.py <stop|prompt|session-start|stop-failure|pre-tool-use>, hook JSON on stdin.
Without an active shift every event exits 0 with no output, so normal sessions are untouched.
Standard library only, Python 3.9.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))

import guard  # noqa: E402
import shift  # noqa: E402

STOP_WORDS = {"stop", "stopp", "hör auf", "hoer auf"}
RESUME_WORDS = {"weiter", "resume shift"}
FRESH_HEARTBEAT_SECONDS = 600


def idle_limit() -> int:
    """1..6, the Stop hook cap (8 consecutive blocks without a tool call ends the turn anyway).

    Falls back to 6 for a value that isn't a plain integer, and clamps any other value into range.
    """
    try:
        n = int(os.environ.get("SLEEPLESS_IDLE_LIMIT", "6"))
    except ValueError:
        return 6
    return max(1, min(6, n))


def retry_seconds() -> float:
    return float(os.environ.get("SLEEPLESS_RETRY_SECONDS", "900"))


def emit(obj: dict) -> None:
    print(json.dumps(obj))


def context(event: str, text: str) -> None:
    emit({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}})


def normalise(prompt: str) -> str:
    return prompt.strip().lower().rstrip(".!").strip()


def label(state: dict) -> str:
    return state.get("label") or "no label"


def continue_reason(state: dict) -> str:
    return ("Sleepless shift active (%s). Do not end the turn. Follow the sleepless skill: take the "
            "next item - the chosen task sources first, then quality work. A blocker goes on the "
            "question list in %s and you switch items. Stop attempts without repo change: %d/%d."
            % (label(state), shift.report_name(state), state["idle"]["streak"], idle_limit()))


def wait_reason(state: dict) -> str:
    return ("Sleepless shift active (%s) and task workers are still running. Run `shift.py wait` "
            "(see the sleepless skill) with run_in_background so you wake up when one finishes, "
            "then end the turn. Stop attempts without repo change: %d/%d."
            % (label(state), state["idle"]["streak"], idle_limit()))


def pause_reason(state: dict) -> str:
    return ("Sleepless: no repo change across %d stop attempts - the shift pauses. Push any "
            "unpushed task branch, send a PushNotification that the shift is paused and why, then "
            "end the turn. The user resumes it with \"weiter\"." % state["idle"]["streak"])


def wake_message(state: dict) -> str:
    return ("A sleepless shift is active (%s). Invoke the sleepless skill, read %s and "
            "`shift.py workers`, and continue with the next item." % (label(state),
                                                                       shift.report_name(state)))


def _same(a, b) -> bool:
    return Path(a).resolve() == Path(b).resolve()


def find_shift(data: dict):
    """(root, state, worktree) of the active shift for this hook call, or None.

    Looks in the git top level of the input cwd, the main checkout of that repo, then
    CLAUDE_PROJECT_DIR. worktree is the caller's linked worktree of the shift repo when the caller
    is a task worker, else None.
    """
    cwd = data.get("cwd")
    top = shift.repo_root(cwd) if cwd else None
    main = shift.main_checkout(top) if top else None
    for base in (top, main, os.environ.get("CLAUDE_PROJECT_DIR")):
        if not base:
            continue
        root = shift.repo_root(base)
        if root is None:
            continue
        state = shift.load(root)
        if state is not None:
            worker = main is not None and _same(main, root) and not _same(top, root)
            return root, state, top if worker else None
    return None


def check_session(root, state: dict, data: dict) -> bool:
    """True if this hook call owns the shift.

    A missing session_id in the input is treated as owner. A null state session_id is claimed by
    the caller. A different session_id is foreign while the owner's heartbeat is still fresh
    (another session of the user is left alone); once the heartbeat goes stale, the caller takes
    over. Claiming and taking over persist the new session_id immediately.
    """
    session_id = data.get("session_id")
    if not session_id:
        return True
    owner = state.get("session_id")
    if owner == session_id:
        return True
    if owner is not None:
        age = shift.heartbeat_age(root)
        if age is not None and age < FRESH_HEARTBEAT_SECONDS:
            return False
    state["session_id"] = session_id
    shift.save(root, state)
    return True


def on_stop(root, state: dict, data: dict) -> int:
    if not check_session(root, state, data):
        return 0
    shift.touch_heartbeat(root)
    state["last_stop"] = shift.now().isoformat()
    running = any(t.get("status") == "running" for t in (data.get("background_tasks") or []))
    if state["status"] != "active" or running:
        shift.save(root, state)
        return 0
    if shift.deadline_passed(state):
        state["status"] = "ending"
        shift.save(root, state)
        emit({"decision": "block", "reason": shift.wrap_up(state)})
        return 0
    waiting = any(w.get("status") == "running" for w in shift.workers(root))
    fp = shift.fingerprint(root)
    idle = state["idle"]
    idle["streak"] = idle["streak"] + 1 if fp == idle["fingerprint"] else 1
    idle["fingerprint"] = fp
    if idle["streak"] > idle_limit():
        state["status"] = "paused"
        shift.save(root, state)
        emit({"decision": "block", "reason": pause_reason(state)})
        return 0
    shift.save(root, state)
    emit({"decision": "block", "reason": wait_reason(state) if waiting else continue_reason(state)})
    return 0


def on_prompt(root, state: dict, data: dict) -> int:
    prompt = normalise(str(data.get("prompt", "")))
    if prompt not in STOP_WORDS | RESUME_WORDS or not check_session(root, state, data):
        return 0
    if prompt in STOP_WORDS and state["status"] in ("active", "paused"):
        state["status"] = "ending"
        shift.save(root, state)
        context("UserPromptSubmit", shift.wrap_up(state))
    elif prompt in RESUME_WORDS and state["status"] == "paused":
        state["status"] = "active"
        state["idle"] = {"fingerprint": "", "streak": 0}
        state["session_id"] = data.get("session_id")
        shift.save(root, state)
        context("UserPromptSubmit", "Sleepless shift resumed (%s). Invoke the sleepless skill and "
                                    "take the next item." % label(state))
    return 0


def on_session_start(root, state: dict, data: dict) -> int:
    if state["status"] != "active":
        return 0
    if data.get("source") in ("startup", "resume"):
        age = shift.heartbeat_age(root)
        if age is not None and age < FRESH_HEARTBEAT_SECONDS:
            return 0
    sys.stderr.write(wake_message(state) + "\n")
    return 2


def on_stop_failure(root, state: dict, data: dict) -> int:
    if not check_session(root, state, data):
        return 0
    if state["status"] != "active":
        return 0
    time.sleep(retry_seconds())
    state = shift.load(root)
    if state is None or state["status"] != "active":
        return 0
    sys.stderr.write("Resume the sleepless shift after an API error. " + wake_message(state) + "\n")
    return 2


def on_pre_tool_use(root, state: dict, data: dict) -> int:
    if not check_session(root, state, data):
        return 0
    shift.touch_heartbeat(root)
    reason = guard_reason(data, root, state)
    hso = {"hookEventName": "PreToolUse"}
    if state["status"] == "active" and shift.deadline_passed(state):
        state["status"] = "ending"
        shift.save(root, state)
        hso["additionalContext"] = shift.wrap_up(state)
    if reason:
        hso["permissionDecision"] = "deny"
        hso["permissionDecisionReason"] = "sleepless: " + reason
    if len(hso) > 1:
        emit({"hookSpecificOutput": hso})
    return 0


def guard_reason(data: dict, root, state: dict, worktree=None) -> Optional[str]:
    tool_input = data.get("tool_input")
    merge_branches = shift.task_branches(root, state) if state.get("merge") else None
    return guard.check(str(data.get("tool_name", "")),
                       tool_input if isinstance(tool_input, dict) else {},
                       str(data.get("cwd") or worktree or root), str(worktree or root),
                       merge_branches)


def on_worker_pre_tool_use(root, state: dict, data: dict, worktree) -> int:
    """A task worker: guard rules inside its own worktree, heartbeat for its task branch."""
    branch = shift._run_git(worktree, "branch", "--show-current").stdout.strip()
    if branch and shift.worker_path(root, branch, ".json").is_file():
        shift.worker_path(root, branch, ".heartbeat").touch()
    reason = guard_reason(data, root, state, worktree)
    if reason:
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": "sleepless: " + reason}})
    return 0


HANDLERS = {
    "stop": on_stop,
    "prompt": on_prompt,
    "session-start": on_session_start,
    "stop-failure": on_stop_failure,
    "pre-tool-use": on_pre_tool_use,
}


def main(argv) -> int:
    handler = HANDLERS.get(argv[1] if len(argv) > 1 else "")
    if handler is None:
        return 0
    try:
        data = json.load(sys.stdin)
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    try:
        found = find_shift(data)
    except (ValueError, OSError):
        emit({"systemMessage": "sleepless: the shift state file is unreadable; the sleepless hooks "
                               "are inactive until it is fixed or removed (.claude/sleepless/)."})
        return 0
    except Exception as e:  # noqa: BLE001 - any other failure must not break the session
        emit({"systemMessage": "sleepless: hook error (%s: %s); the sleepless hooks are inactive "
                               "until it is fixed" % (type(e).__name__, e)})
        return 0
    if found is None:
        return 0
    root, state, worktree = found
    try:
        if worktree is not None:  # workers may end their turn; the coordinator follows up
            return on_worker_pre_tool_use(root, state, data, worktree) if handler is on_pre_tool_use else 0
        return handler(root, state, data)
    except Exception as e:  # noqa: BLE001 - any other failure must not break the session
        emit({"systemMessage": "sleepless: hook error (%s: %s); the sleepless hooks are inactive "
                               "until it is fixed" % (type(e).__name__, e)})
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
