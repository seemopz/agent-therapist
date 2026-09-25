"""State and CLI for a sleepless shift.

Standard library only, Python 3.9. The hooks import this module; Claude runs it as a CLI:

    python3 shift.py start --label L --end stop|time|hours|list [--at HH:MM | --hours N] --sources a,b
    python3 shift.py status | end | finish
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

STATE_DIR = Path(".claude") / "sleepless"
EXCLUDE_LINE = ".claude/sleepless/"
REPORT = "SLEEPLESS-REPORT.md"
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / REPORT
END_KINDS = ("stop", "time", "hours", "list")
SOURCES = ("prompt", "todo", "issues", "propose")


class ShiftError(Exception):
    """A shift command cannot run; the message is shown to Claude."""


def now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def _run_git(root, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def git(root, *args: str) -> str:
    r = _run_git(root, *args)
    if r.returncode != 0:
        raise ShiftError(r.stderr.strip() or "git %s failed" % " ".join(args))
    return r.stdout.strip()


def repo_root(cwd) -> Optional[Path]:
    try:
        r = _run_git(cwd, "rev-parse", "--show-toplevel")
    except OSError:
        return None
    return Path(r.stdout.strip()) if r.returncode == 0 else None


def state_dir(root) -> Path:
    return Path(root) / STATE_DIR


def load(root) -> Optional[dict]:
    """The shift state, or None without a shift. Raises ValueError on a corrupt file."""
    p = state_dir(root) / "state.json"
    if not p.is_file():
        return None
    state = json.loads(p.read_text())
    if not isinstance(state, dict):
        raise ValueError("state.json is not an object")
    return state


def save(root, state: dict) -> None:
    d = state_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(d), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, str(d / "state.json"))


def touch_heartbeat(root) -> None:
    d = state_dir(root)
    if d.is_dir():
        (d / "heartbeat").touch()


def heartbeat_age(root) -> Optional[float]:
    """Seconds since the last heartbeat, or None if there is none."""
    p = state_dir(root) / "heartbeat"
    if not p.exists():
        return None
    return time.time() - p.stat().st_mtime


def compute_deadline(start: dt.datetime, kind: str, at: Optional[str] = None,
                     hours: Optional[float] = None) -> Optional[dt.datetime]:
    if kind == "time":
        m = re.fullmatch(r"(\d{1,2}):(\d{2})", at or "")
        if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
            raise ShiftError("--at needs a time as HH:MM")
        t = start.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        return t if t > start else t + dt.timedelta(days=1)
    if kind == "hours":
        if not hours or hours <= 0:
            raise ShiftError("--hours needs a positive number")
        return start + dt.timedelta(hours=hours)
    return None


def deadline_passed(state: dict, at_time: Optional[dt.datetime] = None) -> bool:
    at = state["end"].get("at")
    return bool(at) and (at_time or now()) >= dt.datetime.fromisoformat(at)


def fingerprint(root) -> str:
    """Changes whenever HEAD or the working tree changes."""
    head = _run_git(root, "rev-parse", "HEAD").stdout
    porcelain = _run_git(root, "status", "--porcelain").stdout
    return hashlib.sha1((head + porcelain).encode()).hexdigest()


def _ref_exists(root, ref: str) -> bool:
    return _run_git(root, "rev-parse", "--verify", "--quiet", ref).returncode == 0


def branch_name(root, day: str) -> str:
    base = name = "sleepless/" + day
    n = 1
    while _ref_exists(root, "refs/heads/" + name) or _ref_exists(root, "refs/remotes/origin/" + name):
        n += 1
        name = "%s-%d" % (base, n)
    return name


def add_exclude(root) -> None:
    p = Path(git(root, "rev-parse", "--git-path", "info/exclude"))
    if not p.is_absolute():
        p = Path(root) / p
    p.parent.mkdir(parents=True, exist_ok=True)
    text = p.read_text() if p.exists() else ""
    if EXCLUDE_LINE in text.splitlines():
        return
    if text and not text.endswith("\n"):
        text += "\n"
    p.write_text(text + EXCLUDE_LINE + "\n")


def _end_text(kind: str, deadline: Optional[dt.datetime]) -> str:
    if kind == "stop":
        return "when the user says stop"
    if kind == "list":
        return "when the task list is done"
    return "at %s" % deadline.strftime("%Y-%m-%d %H:%M")


def start(root, label: str, end_kind: str, at: Optional[str] = None, hours: Optional[float] = None,
          sources=(), start_time: Optional[dt.datetime] = None) -> dict:
    if load(root) is not None:
        raise ShiftError("a shift is already active in this repo; run `shift.py status`")
    if end_kind not in END_KINDS:
        raise ShiftError("--end must be one of: " + ", ".join(END_KINDS))
    unknown = [s for s in sources if s not in SOURCES]
    if unknown:
        raise ShiftError("unknown sources: %s (known: %s)" % (", ".join(unknown), ", ".join(SOURCES)))
    started = start_time or now()
    deadline = compute_deadline(started, end_kind, at, hours)
    base = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if base == "HEAD":
        raise ShiftError("HEAD is detached; check out a branch first")
    branch = branch_name(root, started.date().isoformat())
    git(root, "switch", "-c", branch)
    add_exclude(root)
    state = {
        "version": 1,
        "label": label,
        "branch": branch,
        "base": base,
        "started": started.isoformat(),
        "end": {"kind": end_kind, "at": deadline.isoformat() if deadline else None},
        "sources": list(sources),
        "status": "active",
        "idle": {"fingerprint": "", "streak": 0},
        "last_stop": None,
        "session_id": None,
    }
    save(root, state)
    touch_heartbeat(root)
    report = Path(root) / REPORT
    text = TEMPLATE.read_text()
    for key, value in (("label", label), ("branch", branch), ("base", base),
                       ("started", started.strftime("%Y-%m-%d %H:%M")),
                       ("end", _end_text(end_kind, deadline))):
        text = text.replace("{{%s}}" % key, value)
    report.write_text(text)
    return state


def _require(root) -> dict:
    state = load(root)
    if state is None:
        raise ShiftError("no active shift in this repo")
    return state


def end(root) -> dict:
    state = _require(root)
    state["status"] = "ending"
    save(root, state)
    return state


def finish(root) -> None:
    state = _require(root)
    if state["status"] != "ending":
        raise ShiftError("run `shift.py end` (or have the user say stop) before finish")
    shutil.rmtree(str(state_dir(root)))


def status(root) -> dict:
    state = _require(root)
    age = heartbeat_age(root)
    return dict(state, deadline_passed=deadline_passed(state),
                heartbeat_minutes=None if age is None else round(age / 60, 1))


def wrap_up(state: dict) -> str:
    return (
        "Sleepless shift is ending (%s). Wrap up now: finish or cleanly park the current step, run "
        "the tests, commit and push `%s`. Update SLEEPLESS-REPORT.md (summary with real duration, "
        "done, decisions and questions, blocked, findings, next), commit and push it. Open the PR "
        "with `gh pr create --base %s --head %s --body-file SLEEPLESS-REPORT.md`, or if it exists "
        "`gh pr edit <number> --body-file SLEEPLESS-REPORT.md`. Never merge. Send a "
        "PushNotification with the PR link, run `shift.py finish` (see the sleepless skill), then "
        "write the closing message."
        % (state.get("label") or "no label", state["branch"], state["base"], state["branch"])
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="shift.py", description="sleepless shift state")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("start")
    p.add_argument("--label", required=True)
    p.add_argument("--end", required=True, choices=END_KINDS)
    p.add_argument("--at")
    p.add_argument("--hours", type=float)
    p.add_argument("--sources", default="")
    for name in ("status", "end", "finish"):
        sub.add_parser(name)
    args = parser.parse_args(argv)

    root = repo_root(Path.cwd())
    if root is None:
        print("shift.py: not inside a git repo", file=sys.stderr)
        return 1
    try:
        if args.cmd == "start":
            sources = [s.strip() for s in args.sources.split(",") if s.strip()]
            out = start(root, args.label, args.end, args.at, args.hours, sources)
        elif args.cmd == "status":
            out = status(root)
        elif args.cmd == "end":
            print(wrap_up(end(root)))
            return 0
        else:
            finish(root)
            out = {"finished": True}
    except (ShiftError, ValueError) as e:
        print("shift.py: %s" % e, file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
