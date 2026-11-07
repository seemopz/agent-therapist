"""State and CLI for a sleepless shift.

Standard library only, Python 3.9. The hooks import this module; Claude runs it as a CLI:

    python3 shift.py start --label L --end stop|time|hours|list [--at HH:MM | --hours N] --sources a,b
    python3 shift.py branch <type> <topic>
    python3 shift.py join <branch> [--from <ref>]
    python3 shift.py done <branch> --status done|blocked [--pr URL] [--note TEXT]
    python3 shift.py wait [--timeout-minutes 50]
    python3 shift.py workers | status | end | finish
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
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "report.md"
END_KINDS = ("stop", "time", "hours", "list")
SOURCES = ("prompt", "todo", "issues", "propose")
BRANCH_TYPES = ("feat", "fix", "docs", "refactor", "test", "chore", "perf", "build", "ci", "style")
WORKER_END = ("done", "blocked")
WORKER_STALE_SECONDS = 20 * 60


class ShiftError(Exception):
    """A shift command cannot run; the message is shown to Claude."""


def now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def _run_git(root, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          encoding="utf-8")


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


def main_checkout(cwd) -> Optional[Path]:
    """The main checkout of the repo at cwd (differs from repo_root in a linked worktree)."""
    try:
        r = _run_git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    except OSError:
        return None
    common = Path(r.stdout.strip())
    return common.parent if r.returncode == 0 and common.name == ".git" else None


def shift_root(top) -> Path:
    """The checkout holding the shift: top itself, or the main checkout when top is a worktree."""
    if load(top) is None:
        main = main_checkout(top)
        if main is not None and load(main) is not None:
            return main
    return Path(top)


def state_dir(root) -> Path:
    return Path(root) / STATE_DIR


def load(root) -> Optional[dict]:
    """The shift state, or None without a shift. Raises ValueError on a corrupt file."""
    p = state_dir(root) / "state.json"
    if not p.is_file():
        return None
    state = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise ValueError("state.json is not an object")
    state.setdefault("report", None)  # version 1 kept the report in the repo root
    return state


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, str(path))


def save(root, state: dict) -> None:
    _write_json(state_dir(root) / "state.json", state)


def worker_path(root, branch: str, suffix: str) -> Path:
    return state_dir(root) / "workers" / (branch.replace("/", "--") + suffix)


def workers(root) -> list:
    d = state_dir(root) / "workers"
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))]


def worker_age(root, branch: str) -> float:
    """Seconds since the worker's last tool call (or its join, before the first heartbeat)."""
    paths = [worker_path(root, branch, suffix) for suffix in (".heartbeat", ".json")]
    paths = [p for p in paths if p.exists()]
    return time.time() - max((p.stat().st_mtime for p in paths), default=0)


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
    """Changes whenever HEAD, any ref, the working tree, the report or a worker file changes."""
    head = _run_git(root, "rev-parse", "HEAD").stdout + _run_git(root, "for-each-ref").stdout
    porcelain = _run_git(root, "status", "--porcelain", "--untracked-files=all").stdout
    diff = subprocess.run(["git", "-C", str(root), "diff", "--no-ext-diff", "--no-textconv",
                           "--binary", "HEAD"], capture_output=True, check=True).stdout
    digest = hashlib.sha256((head + porcelain).encode("utf-8") + diff)
    for name in _run_git(root, "ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0"):
        if name:
            path = Path(root) / name
            if path.is_symlink():
                content = os.readlink(path).encode("utf-8")
            elif path.is_dir():  # a nested repo or worktree, listed as "dir/"
                continue
            else:
                content = path.read_bytes()
            digest.update(name.encode("utf-8") + b"\0" + content + b"\0")
    d = state_dir(root)
    for path in sorted(list(d.glob("reports/*.md")) + list(d.glob("workers/*.json"))):
        digest.update(path.name.encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def _ref_exists(root, ref: str) -> bool:
    return _run_git(root, "rev-parse", "--verify", "--quiet", ref).returncode == 0


def slugify(text: str, limit: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit].strip("-")


def branch_name(root, kind: str, topic: str) -> str:
    if kind not in BRANCH_TYPES:
        raise ShiftError("unknown branch type %r (known: %s)" % (kind, ", ".join(BRANCH_TYPES)))
    slug = slugify(topic)
    if not slug:
        raise ShiftError("the topic needs letters or digits")
    base = name = "%s/%s" % (kind, slug)
    n = 1
    while _ref_exists(root, "refs/heads/" + name) or _ref_exists(root, "refs/remotes/origin/" + name):
        n += 1
        name = "%s-%d" % (base, n)
    return name


def report_path(root, day: str, label: str) -> str:
    """Repo-relative path of a free report file for a shift starting on day."""
    stem = name = "%s-%s" % (day, slugify(label) or "shift")
    n = 1
    while (state_dir(root) / "reports" / (name + ".md")).exists():
        n += 1
        name = "%s-%d" % (stem, n)
    return (STATE_DIR / "reports" / (name + ".md")).as_posix()


def add_exclude(root) -> None:
    p = Path(git(root, "rev-parse", "--git-path", "info/exclude"))
    if not p.is_absolute():
        p = Path(root) / p
    p.parent.mkdir(parents=True, exist_ok=True)
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    if EXCLUDE_LINE in text.splitlines():
        return
    if text and not text.endswith("\n"):
        text += "\n"
    p.write_text(text + EXCLUDE_LINE + "\n", encoding="utf-8")


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
    main = main_checkout(root)
    if main is not None and main.resolve() != Path(root).resolve():
        raise ShiftError("this is a linked worktree; start the shift in the main checkout (%s)" % main)
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
    report = report_path(root, started.date().isoformat(), label)
    add_exclude(root)
    state = {
        "version": 2,
        "label": label,
        "base": base,
        "report": report,
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
    text = TEMPLATE.read_text(encoding="utf-8")
    for key, value in (("label", label), ("base", base),
                       ("started", started.strftime("%Y-%m-%d %H:%M")),
                       ("end", _end_text(end_kind, deadline))):
        text = text.replace("{{%s}}" % key, value)
    (state_dir(root) / "reports").mkdir(exist_ok=True)
    (Path(root) / report).write_text(text, encoding="utf-8")
    return state


def _require(root) -> dict:
    state = load(root)
    if state is None:
        raise ShiftError("no active shift in this repo")
    return state


def join(root, worktree, branch: str, from_ref: Optional[str] = None) -> dict:
    """Put the worktree on its task branch (cut from from_ref or the base); mark it running."""
    state = _require(root)
    if Path(worktree).resolve() == Path(root).resolve():
        raise ShiftError("run join inside the worker's own git worktree, not the main checkout")
    if git(worktree, "branch", "--show-current") != branch:
        if _ref_exists(worktree, "refs/heads/" + branch):  # a restarted worker keeps its commits
            git(worktree, "switch", branch)
        else:
            git(worktree, "switch", "-c", branch, from_ref or state["base"])
    worker = {"branch": branch, "status": "running", "started": now().isoformat(), "pr": None,
              "note": ""}
    _write_json(worker_path(root, branch, ".json"), worker)
    return worker


def done(root, branch: str, status: str, pr: Optional[str] = None,
         note: Optional[str] = None) -> dict:
    _require(root)
    if status not in WORKER_END:
        raise ShiftError("--status must be one of: " + ", ".join(WORKER_END))
    p = worker_path(root, branch, ".json")
    if not p.is_file():
        raise ShiftError("no worker for branch %s; see `shift.py workers`" % branch)
    worker = json.loads(p.read_text(encoding="utf-8"))
    worker["status"] = status
    if pr:
        worker["pr"] = pr
    if note:
        worker["note"] = note
    _write_json(p, worker)
    return worker


def poll_seconds() -> float:
    return float(os.environ.get("SLEEPLESS_POLL_SECONDS", "20"))


def _wait_reason(root, running: set, stale_before: set, timeout_at: float) -> Optional[str]:
    state = load(root)
    if state is None or state["status"] != "active":
        return "shift_inactive"
    if deadline_passed(state):
        return "deadline"
    if not running:
        return "none_running"
    by_branch = {w["branch"]: w for w in workers(root)}
    if any(by_branch.get(b, {}).get("status") != "running" for b in running):
        return "status"
    if any(worker_age(root, b) > WORKER_STALE_SECONDS for b in running - stale_before):
        return "stale"
    return "timeout" if time.time() >= timeout_at else None


def wait(root, timeout_minutes: float = 50) -> dict:
    """Block until a running worker changes status or goes silent, the shift deadline passes, the
    shift stops being active, or the timeout. Keeps the coordinator's heartbeat fresh meanwhile."""
    _require(root)
    timeout_at = time.time() + timeout_minutes * 60
    running = {w["branch"] for w in workers(root) if w.get("status") == "running"}
    # a worker already stale at the start was reported before; it must not end every later wait
    stale_before = {b for b in running if worker_age(root, b) > WORKER_STALE_SECONDS}
    while True:
        touch_heartbeat(root)
        reason = _wait_reason(root, running, stale_before, timeout_at)
        if reason:
            return {"reason": reason, "workers": workers(root)}
        time.sleep(max(0.0, min(poll_seconds(), timeout_at - time.time())))


def end(root) -> dict:
    state = _require(root)
    state["status"] = "ending"
    save(root, state)
    return state


def finish(root) -> None:
    state = _require(root)
    if state["status"] != "ending":
        raise ShiftError("run `shift.py end` (or have the user say stop) before finish")
    running = [w["branch"] for w in workers(root) if w.get("status") == "running"]
    if running:
        raise ShiftError("workers still running: %s; stop their sessions, then mark each with "
                         "`shift.py done <branch> --status done|blocked`" % ", ".join(running))
    for p in state_dir(root).iterdir():
        if p.name == "reports":
            continue
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(str(p))
        else:
            p.unlink()


def status(root) -> dict:
    state = _require(root)
    age = heartbeat_age(root)
    return dict(state, deadline_passed=deadline_passed(state),
                heartbeat_minutes=None if age is None else round(age / 60, 1))


def report_name(state: dict) -> str:
    return "`%s`" % state["report"] if state.get("report") else "the shift report"


def wrap_up(state: dict) -> str:
    return (
        "Sleepless shift is ending (%s). Wrap up now: wait for running task workers (`shift.py "
        "wait`) or park them (`shift.py done <branch> --status blocked`), and finish or cleanly "
        "park your own current step. Make sure every task branch is pushed and has its own PR "
        "against `%s` (or the branch it depends on). Never merge. Finalize the report at %s "
        "(summary with real duration, done with branches and PR links, decisions and questions, "
        "blocked, findings, next); it is never committed. Send a PushNotification with the PR "
        "links, run `shift.py finish` (see the sleepless skill), then write the closing message "
        "with the summary and the PR links."
        % (state.get("label") or "no label", state["base"], report_name(state))
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
    p = sub.add_parser("branch")
    p.add_argument("type", choices=BRANCH_TYPES)
    p.add_argument("topic")
    p = sub.add_parser("join")
    p.add_argument("branch")
    p.add_argument("--from", dest="from_ref")
    p = sub.add_parser("done")
    p.add_argument("branch")
    p.add_argument("--status", required=True, choices=WORKER_END)
    p.add_argument("--pr")
    p.add_argument("--note")
    sub.add_parser("wait").add_argument("--timeout-minutes", type=float, default=50)
    for name in ("workers", "status", "end", "finish"):
        sub.add_parser(name)
    args = parser.parse_args(argv)

    top = repo_root(Path.cwd())
    if top is None:
        print("shift.py: not inside a git repo", file=sys.stderr)
        return 1
    try:
        root = top if args.cmd in ("start", "branch") else shift_root(top)
        if args.cmd == "start":
            sources = [s.strip() for s in args.sources.split(",") if s.strip()]
            out = start(root, args.label, args.end, args.at, args.hours, sources)
        elif args.cmd == "branch":
            print(branch_name(root, args.type, args.topic))
            return 0
        elif args.cmd == "join":
            out = join(root, top, args.branch, args.from_ref)
        elif args.cmd == "done":
            out = done(root, args.branch, args.status, args.pr, args.note)
        elif args.cmd == "wait":
            out = wait(root, args.timeout_minutes)
        elif args.cmd == "workers":
            out = workers(root)
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
