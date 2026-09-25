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
            "question list in SLEEPLESS-REPORT.md and you switch items. Stop attempts without repo "
            "change: %d/%d." % (label(state), state["idle"]["streak"], idle_limit()))


def pause_reason(state: dict) -> str:
    return ("Sleepless: no repo change across %d stop attempts - the shift pauses. Push `%s`, send a "
            "PushNotification that the shift is paused and why, then end the turn. The user resumes "
            "it with \"weiter\"." % (state["idle"]["streak"], state["branch"]))


def wake_message(state: dict) -> str:
    return ("A sleepless shift is active on `%s` (%s). Invoke the sleepless skill, read "
            "SLEEPLESS-REPORT.md, check out the shift branch if needed, and continue with the next "
            "item." % (state["branch"], label(state)))


def find_shift(data: dict):
    """(root, state) of the active shift for this hook call, or None.

    Looks in the git top level of the input cwd first, then in CLAUDE_PROJECT_DIR, so a subagent
    in a git worktree still sees the shift of the main checkout.
    """
    for base in (data.get("cwd"), os.environ.get("CLAUDE_PROJECT_DIR")):
        if not base:
            continue
        root = shift.repo_root(base)
        if root is None:
            continue
        state = shift.load(root)
        if state is not None:
            return root, state
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
    emit({"decision": "block", "reason": continue_reason(state)})
    return 0


def on_prompt(root, state: dict, data: dict) -> int:
    prompt = normalise(str(data.get("prompt", "")))
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
    tool_input = data.get("tool_input")
    reason = guard.check(str(data.get("tool_name", "")),
                         tool_input if isinstance(tool_input, dict) else {},
                         str(data.get("cwd") or root), str(root))
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
    root, state = found
    try:
        return handler(root, state, data)
    except Exception as e:  # noqa: BLE001 - any other failure must not break the session
        emit({"systemMessage": "sleepless: hook error (%s: %s); the sleepless hooks are inactive "
                               "until it is fixed" % (type(e).__name__, e)})
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
