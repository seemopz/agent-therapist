# sleepless Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second skill `sleepless` to this plugin: a long autonomous work shift in any git repo, with hooks that keep the turn going, end/resume on "stop"/"weiter", wake a restarted session, and block dangerous commands.

**Architecture:** `skills/sleepless/` is itself a skills-dir plugin (own `.claude-plugin/plugin.json` + `hooks/hooks.json`), so a symlink into `~/.claude/skills/` loads the hooks in every session. One hook entry point `hooks/hook.py <event>` dispatches to handlers; `scripts/shift.py` owns the state file and a CLI; `hooks/guard.py` holds the PreToolUse deny rules. A root `hooks/hooks.json` mirrors the registration for the repo-level plugin install.

**Tech Stack:** Python 3.9 standard library, pytest (via `uv run pytest`), git, Claude Code hooks (Stop, UserPromptSubmit, SessionStart with `asyncRewake`, StopFailure with `asyncRewake`, PreToolUse).

**Spec:** `docs/superpowers/specs/2026-09-25-sleepless-design.md`

## Global Constraints

- Scripts and hooks: Python 3.9, standard library only, no syntax newer than 3.9 (`from __future__ import annotations`, `Optional[...]`, no `match`, no `X | Y` at runtime).
- All files, code, comments and commits in English.
- Tests and examples use generic placeholders, never real private repo or person names.
- Commits: `type(scope): what`, no Co-Authored-By line. Never edit `CHANGELOG.md`, versions or `.release-please-manifest.json`.
- No `rm -rf` in commands (denied by project settings); tests use `tmp_path`.
- Work on branch `feat/sleepless`. Do not push or open a PR without asking the user.
- State path `<repo>/.claude/sleepless/`, excluded via `.git/info/exclude` line `.claude/sleepless/`.
- Env knobs: `SLEEPLESS_IDLE_LIMIT` (default 6), `SLEEPLESS_RETRY_SECONDS` (default 900).

## Deviation from the spec (decided while planning)

- Hooks look for the shift first in the git top level of the input `cwd`, then in `CLAUDE_PROJECT_DIR`. Reason: a subagent working in a git worktree has a different top level without the (untracked) state dir; without the fallback the guard would be off there.
- `find … -delete` may target the repo root itself (it deletes matches inside); `rm` on the repo root is denied.
- Redirect targets (`> file`) are not treated as paths to delete.

## File map

| File | Responsibility |
|---|---|
| `skills/sleepless/scripts/shift.py` | state file, heartbeat, deadline maths, idle fingerprint, branch naming, report creation, CLI `start/status/end/finish`, wrap-up text |
| `skills/sleepless/hooks/guard.py` | pure deny rules for Bash and MCP tool calls |
| `skills/sleepless/hooks/hook.py` | hook entry point, finds the shift, one handler per event |
| `skills/sleepless/hooks/hooks.json` | registration for the skills-dir plugin |
| `skills/sleepless/.claude-plugin/plugin.json` | makes the skill folder a plugin |
| `skills/sleepless/templates/SLEEPLESS-REPORT.md` | report skeleton |
| `skills/sleepless/SKILL.md` | the shift flow for Claude |
| `hooks/hooks.json` | same registration for the repo-level plugin |
| `tests/conftest.py` | + `SLEEPLESS_DIR`, sys.path, `git_repo` fixture |
| `tests/test_sleepless_state.py`, `test_sleepless_guard.py`, `test_sleepless_hooks.py`, `test_sleepless_files.py` | tests |
| `README.md`, `CLAUDE.md` | install and layout docs |

---

### Task 1: State library and CLI (`shift.py`) + report template

**Files:**
- Modify: `tests/conftest.py`
- Create: `skills/sleepless/scripts/shift.py`
- Create: `skills/sleepless/templates/SLEEPLESS-REPORT.md`
- Test: `tests/test_sleepless_state.py`

**Interfaces:**
- Produces (module `shift`):
  - `class ShiftError(Exception)`
  - `now() -> datetime` (aware, local)
  - `repo_root(cwd) -> Optional[Path]`
  - `load(root) -> Optional[dict]` (raises `ValueError` on corrupt JSON), `save(root, state) -> None`
  - `touch_heartbeat(root) -> None`, `heartbeat_age(root) -> Optional[float]` (seconds)
  - `compute_deadline(start, kind, at=None, hours=None) -> Optional[datetime]`
  - `deadline_passed(state, at_time=None) -> bool`
  - `fingerprint(root) -> str`, `branch_name(root, day: str) -> str`, `add_exclude(root) -> None`
  - `start(root, label, end_kind, at=None, hours=None, sources=(), start_time=None) -> dict`
  - `end(root) -> dict`, `finish(root) -> None`, `status(root) -> dict`
  - `wrap_up(state) -> str`
  - state keys: `version, label, branch, base, started, end{kind,at}, sources, status, idle{fingerprint,streak}, last_stop`
- Produces (conftest): `SLEEPLESS_DIR`, fixture `git_repo` (temp repo on branch `main` with one commit)

- [ ] **Step 1: Extend conftest**

Replace `tests/conftest.py` with:

```python
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "agent-therapist"
SLEEPLESS_DIR = ROOT / "skills" / "sleepless"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(SLEEPLESS_DIR / "scripts"))
sys.path.insert(0, str(SLEEPLESS_DIR / "hooks"))


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A throwaway git repo on branch main with one commit."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def g(*args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    g("init", "-q", "-b", "main")
    g("config", "user.name", "Test")
    g("config", "user.email", "test@example.com")
    g("config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("placeholder\n")
    g("add", ".")
    g("commit", "-qm", "init")
    return repo
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_sleepless_state.py`:

```python
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
    porcelain = subprocess.run(["git", "-C", str(git_repo), "status", "--porcelain"],
                               capture_output=True, text=True).stdout
    assert ".claude" not in porcelain


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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_sleepless_state.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'shift'`.

- [ ] **Step 4: Write the report template**

Create `skills/sleepless/templates/SLEEPLESS-REPORT.md`:

```markdown
# Sleepless shift: {{label}}

Branch `{{branch}}` from `{{base}}` · started {{started}} · ends {{end}}

## Summary

_Written at the end of the shift: what changed, real duration including restarts and pauses._

## Plan

_Task list in the order it will be worked on._

## Done

| Item | Commits |
|---|---|

## Decisions and questions

_Each entry: the decision taken and why, or the open question and what was tried._

## Blocked

## Findings

## Next
```

- [ ] **Step 5: Write `shift.py`**

Create `skills/sleepless/scripts/shift.py`:

```python
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
    }
    save(root, state)
    touch_heartbeat(root)
    report = Path(root) / REPORT
    if not report.exists():
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_sleepless_state.py -q`
Expected: all pass. Then `uv run pytest -q` – the existing suite still passes.

- [ ] **Step 7: Commit**

```bash
git add tests/conftest.py tests/test_sleepless_state.py skills/sleepless/scripts/shift.py skills/sleepless/templates/SLEEPLESS-REPORT.md
git commit -m "feat(sleepless): add shift state library and CLI"
```

---

### Task 2: Command guard (`guard.py`)

**Files:**
- Create: `skills/sleepless/hooks/guard.py`
- Test: `tests/test_sleepless_guard.py`

**Interfaces:**
- Consumes: fixture `git_repo` from Task 1.
- Produces (module `guard`): `check(tool_name: str, tool_input: dict, cwd: str, root: str) -> Optional[str]` – a deny reason or `None`; `segments(command: str) -> List[List[str]]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sleepless_guard.py`:

```python
from __future__ import annotations

import subprocess

import pytest

import guard

DENY = [
    ("git push --force origin sleepless/x", "force"),
    ("git push -f", "force"),
    ("git push -fu origin x", "force"),
    ("git push --force-with-lease origin x", "force"),
    ("git push origin +sleepless/x", "force"),
    ("git push origin main", "main/master"),
    ("git push origin HEAD:master", "main/master"),
    ("git push origin x:refs/heads/main", "main/master"),
    ("git push", "main/master"),
    ("git push origin", "main/master"),
    ("cd sub && git -C .. push origin main", "main/master"),
    ("git push --all", "all branches"),
    ("git push --mirror origin", "all branches"),
    ("git push origin --delete old", "deleting remote"),
    ("git push origin :old", "deleting remote"),
    ("rm -rf /tmp/x", "outside the repo"),
    ("rm -rf ~/x", "outside the repo"),
    ("rm -rf ../other", "outside the repo"),
    ("rm -rf .", "outside the repo"),
    ("FOO=1 sudo rm /etc/hosts", "outside the repo"),
    ("echo hi; rm -r /var/x", "outside the repo"),
    ("find / -name x -delete", "outside the repo"),
    ("rm -rf $HOME/x", "cannot resolve"),
    ("rm -rf $(pwd)/x", "cannot resolve"),
    ("rm -rf `pwd`/x", "cannot resolve"),
    ("rm -rf ~other/x", "cannot resolve"),
    ("gh pr comment 3 --body hi", "sending messages"),
    ("gh pr review 3 --approve", "sending messages"),
    ("gh issue comment 4 --body hi", "sending messages"),
    ("gh issue create --title t", "sending messages"),
    ("mail -s hi someone@example.com", "sending messages"),
    ("curl -X POST https://hooks.slack.com/services/T/B/X -d x", "sending messages"),
]

ALLOW = [
    "git status",
    "git push -u origin sleepless/2026-09-25",
    "git push origin HEAD:sleepless/2026-09-25",
    "rm -rf build dist",
    "rm -f 'a file.txt'",
    "rm x > /tmp/log 2>&1",
    "find . -name '*.pyc' -delete",
    "gh pr create --base main --body-file SLEEPLESS-REPORT.md",
    "gh pr edit 3 --body-file SLEEPLESS-REPORT.md",
    'git commit -m "fix: stop; push to main later"',
    "python3 -m pytest",
    "curl https://example.com",
]


@pytest.mark.parametrize("command,reason", DENY)
def test_bash_denied(git_repo, command, reason):
    result = guard.check("Bash", {"command": command}, str(git_repo), str(git_repo))
    assert result is not None and reason in result


@pytest.mark.parametrize("command", ALLOW)
def test_bash_allowed(git_repo, command):
    assert guard.check("Bash", {"command": command}, str(git_repo), str(git_repo)) is None


def test_bare_push_allowed_on_shift_branch(git_repo):
    subprocess.run(["git", "-C", str(git_repo), "switch", "-qc", "sleepless/2026-09-25"], check=True)
    assert guard.check("Bash", {"command": "git push"}, str(git_repo), str(git_repo)) is None


def test_rm_relative_to_cwd_in_subdir(git_repo):
    sub = git_repo / "sub"
    sub.mkdir()
    assert guard.check("Bash", {"command": "rm -rf ../README.md"}, str(sub), str(git_repo)) is None
    assert "outside" in guard.check("Bash", {"command": "rm -rf ../../x"}, str(sub), str(git_repo))


@pytest.mark.parametrize("tool,denied", [
    ("mcp__chat__send_message", True),
    ("mcp__mail__create_draft", True),
    ("mcp__tracker__add_comment", True),
    ("mcp__postgres__query", False),
    ("mcp__github__create_pull_request", False),
    ("PushNotification", False),
    ("Read", False),
])
def test_mcp_and_other_tools(git_repo, tool, denied):
    result = guard.check(tool, {}, str(git_repo), str(git_repo))
    assert (result is not None) == denied


def test_segments_split_on_operators_but_not_inside_quotes():
    assert guard.segments('a "x; y" && b | c; d\ne') == [["a", "x; y"], ["b"], ["c"], ["d"], ["e"]]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sleepless_guard.py -q`
Expected: collection error `No module named 'guard'`.

- [ ] **Step 3: Write `guard.py`**

Create `skills/sleepless/hooks/guard.py`:

```python
"""Deny rules for tool calls during a sleepless shift.

A best-effort guard against mistakes, not a sandbox. Standard library only, Python 3.9.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
from typing import List, Optional

PROTECTED = ("main", "master")
SEPARATORS = {";", ";;", "&&", "||", "|", "|&", "&", "(", ")"}
PREFIXES = {"sudo", "command", "env", "exec", "nohup", "time", "{", "!"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
MCP_WORDS = re.compile(r"send|post|reply|message|comment|draft|email", re.I)
GH_MESSAGES = {("pr", "comment"), ("pr", "review"), ("issue", "comment"), ("issue", "create")}
MAILERS = {"mail", "mailx", "sendmail", "mutt"}
WEBHOOKS = ("hooks.slack.com", "discord.com/api/webhooks")
PUSH_OPTS_WITH_VALUE = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}

FORCE = "force push is blocked during a sleepless shift"
PROTECTED_MSG = ("pushing to main/master is blocked during a sleepless shift; "
                 "push the shift branch instead")
ALL = "pushing all branches is blocked during a sleepless shift"
DELETE = "deleting remote branches is blocked during a sleepless shift"
OUTSIDE = "deleting outside the repo (%s) is blocked during a sleepless shift"
UNRESOLVED = "cannot resolve the path %r to check that it is inside the repo; use a literal path"
MESSAGE = ("sending messages is blocked during a sleepless shift; "
           "note it in SLEEPLESS-REPORT.md instead")


def segments(command: str) -> List[List[str]]:
    """Split a shell command into simple commands (lists of words)."""
    lex = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        tokens = list(lex)
    except ValueError:
        tokens = command.split()
    out, cur = [], []  # type: List[List[str]], List[str]
    for t in tokens:
        if t in SEPARATORS:
            if cur:
                out.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        out.append(cur)
    return out


def _command_words(seg: List[str]) -> List[str]:
    i = 0
    while i < len(seg) and (seg[i] in PREFIXES or ASSIGNMENT.match(seg[i])):
        i += 1
    return seg[i:]


def _resolve(cwd: str, path: str) -> Optional[str]:
    if "$" in path or "`" in path or (path.startswith("~") and path != "~" and not path.startswith("~/")):
        return None
    return os.path.realpath(os.path.join(cwd, os.path.expanduser(path)))


def _inside(target: str, root: str, allow_root: bool) -> bool:
    root = os.path.realpath(root)
    if target == root:
        return allow_root
    return target.startswith(root.rstrip(os.sep) + os.sep)


def _current_branch(cwd: str) -> str:
    try:
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
                           capture_output=True, text=True)
    except OSError:
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _check_git(words: List[str], cwd: str) -> Optional[str]:
    if os.path.basename(words[0]) != "git":
        return None
    i, gcwd = 1, cwd
    while i < len(words) and words[i].startswith("-"):
        if words[i] == "-C" and i + 1 < len(words):
            gcwd = _resolve(gcwd, words[i + 1]) or gcwd
            i += 2
        elif words[i] in ("-c", "--git-dir", "--work-tree", "--namespace"):
            i += 2
        else:
            i += 1
    if i >= len(words) or words[i] != "push":
        return None
    opts, positional = [], []  # type: List[str], List[str]
    args = words[i + 1:]
    j = 0
    while j < len(args):
        if args[j] in PUSH_OPTS_WITH_VALUE:
            j += 2
            continue
        (opts if args[j].startswith("-") else positional).append(args[j])
        j += 1
    refspecs = positional[1:]
    short = "".join(o[1:] for o in opts if not o.startswith("--"))
    if ("f" in short or "--force" in opts
            or any(o.startswith(("--force-with-lease", "--force-if-includes")) for o in opts)
            or any(r.startswith("+") for r in refspecs)):
        return FORCE
    if "d" in short or "--delete" in opts or any(r.startswith(":") for r in refspecs):
        return DELETE
    if "--all" in opts or "--mirror" in opts or "--branches" in opts:
        return ALL
    for ref in refspecs or ["HEAD"]:
        dst = ref.split(":", 1)[-1]
        if dst == "HEAD":
            dst = _current_branch(gcwd)
        if dst.startswith("refs/heads/"):
            dst = dst[len("refs/heads/"):]
        if dst in PROTECTED:
            return PROTECTED_MSG
    return None


def _check_delete(words: List[str], cwd: str, root: str) -> Optional[str]:
    name = os.path.basename(words[0])
    paths = []  # type: List[str]
    if name in ("rm", "rmdir", "unlink"):
        allow_root, opts_done, skip = False, False, False
        for w in words[1:]:
            if skip:
                skip = False
            elif w.startswith((">", "<")):
                skip = True
            elif not opts_done and w == "--":
                opts_done = True
            elif not opts_done and w.startswith("-"):
                continue
            elif not w.isdigit():
                paths.append(w)
    elif name == "find" and "-delete" in words:
        allow_root = True
        for w in words[1:]:
            if w.startswith("-") or w in ("!", "("):
                break
            paths.append(w)
        paths = paths or ["."]
    else:
        return None
    for p in paths:
        target = _resolve(cwd, p)
        if target is None:
            return UNRESOLVED % p
        if not _inside(target, root, allow_root):
            return OUTSIDE % p
    return None


def _check_message(words: List[str]) -> Optional[str]:
    name = os.path.basename(words[0])
    if name == "gh" and len(words) >= 3 and (words[1], words[2]) in GH_MESSAGES:
        return MESSAGE
    if name in MAILERS:
        return MESSAGE
    if name in ("curl", "wget") and any(h in w for w in words for h in WEBHOOKS):
        return MESSAGE
    return None


def check_bash(command: str, cwd: str, root: str) -> Optional[str]:
    for seg in segments(command):
        words = _command_words(seg)
        if not words:
            continue
        if words[0] == "cd":
            if len(words) > 1:
                cwd = _resolve(cwd, words[1]) or cwd
            continue
        reason = _check_git(words, cwd) or _check_delete(words, cwd, root) or _check_message(words)
        if reason:
            return reason
    return None


def check(tool_name: str, tool_input: dict, cwd: str, root: str) -> Optional[str]:
    """A deny reason for this tool call, or None to let it through."""
    if tool_name == "Bash":
        return check_bash(str(tool_input.get("command", "")), str(cwd), str(root))
    if tool_name.startswith("mcp__") and MCP_WORDS.search(tool_name.rsplit("__", 1)[-1]):
        return MESSAGE
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_sleepless_guard.py -q`
Expected: all pass. If a DENY/ALLOW case fails, print `guard.segments(command)` for it and fix the rule, not the test (the tables are the spec).

- [ ] **Step 5: Commit**

```bash
git add skills/sleepless/hooks/guard.py tests/test_sleepless_guard.py
git commit -m "feat(sleepless): add command guard for shifts"
```

---

### Task 3: Hook entry point (`hook.py`)

**Files:**
- Create: `skills/sleepless/hooks/hook.py`
- Test: `tests/test_sleepless_hooks.py`

**Interfaces:**
- Consumes: `shift.*` (Task 1), `guard.check` (Task 2).
- Produces: CLI `python3 hook.py <stop|prompt|session-start|stop-failure|pre-tool-use>` reading hook JSON on stdin; stdout JSON per Claude Code hook schema; `session-start` and `stop-failure` exit 2 with the wake message on stderr.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sleepless_hooks.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sleepless_hooks.py -q`
Expected: most tests FAIL (hook.py missing → python exits 2 with "can't open file").

- [ ] **Step 3: Write `hook.py`**

Create `skills/sleepless/hooks/hook.py`:

```python
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
RESUME_WORDS = {"weiter", "continue", "resume"}
FRESH_HEARTBEAT_SECONDS = 600


def idle_limit() -> int:
    return int(os.environ.get("SLEEPLESS_IDLE_LIMIT", "6"))


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
            "it with \"weiter\"." % (idle_limit(), state["branch"]))


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


def on_stop(root, state: dict, data: dict) -> int:
    shift.touch_heartbeat(root)
    state["last_stop"] = shift.now().isoformat()
    if state["status"] != "active" or data.get("background_tasks"):
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
        shift.save(root, state)
        context("UserPromptSubmit", "Sleepless shift resumed (%s). Take the next item per the "
                                    "sleepless skill." % label(state))
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
    if state["status"] != "active":
        return 0
    time.sleep(retry_seconds())
    state = shift.load(root)
    if state is None or state["status"] != "active":
        return 0
    sys.stderr.write("Resume the sleepless shift after an API error. " + wake_message(state) + "\n")
    return 2


def on_pre_tool_use(root, state: dict, data: dict) -> int:
    shift.touch_heartbeat(root)
    tool_input = data.get("tool_input")
    reason = guard.check(str(data.get("tool_name", "")),
                         tool_input if isinstance(tool_input, dict) else {},
                         str(data.get("cwd") or root), str(root))
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
    if found is None:
        return 0
    root, state = found
    try:
        return handler(root, state, data)
    except (KeyError, TypeError, AttributeError):
        emit({"systemMessage": "sleepless: the shift state file is incomplete; the sleepless hooks "
                               "are inactive until it is fixed or removed (.claude/sleepless/)."})
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_sleepless_hooks.py -q`
Expected: all pass. Then `uv run pytest -q`: full suite green.

- [ ] **Step 5: Commit**

```bash
git add skills/sleepless/hooks/hook.py tests/test_sleepless_hooks.py
git commit -m "feat(sleepless): add hook entry point for shift events"
```

---

### Task 4: Hook registration and plugin manifests

**Files:**
- Create: `skills/sleepless/.claude-plugin/plugin.json`
- Create: `skills/sleepless/hooks/hooks.json`
- Create: `hooks/hooks.json`
- Test: `tests/test_sleepless_files.py`

**Interfaces:**
- Consumes: `hook.py` event names from Task 3.
- Produces: both registrations; test helpers reused by Task 5 (`SLEEPLESS_DIR` only).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sleepless_files.py`:

```python
from __future__ import annotations

import ast
import json

from conftest import ROOT, SLEEPLESS_DIR

SKILL_HOOKS = SLEEPLESS_DIR / "hooks" / "hooks.json"
ROOT_HOOKS = ROOT / "hooks" / "hooks.json"
EVENTS = {"Stop": "stop", "UserPromptSubmit": "prompt", "SessionStart": "session-start",
          "StopFailure": "stop-failure", "PreToolUse": "pre-tool-use"}
SCRIPTS = [SLEEPLESS_DIR / "scripts" / "shift.py", SLEEPLESS_DIR / "hooks" / "hook.py",
           SLEEPLESS_DIR / "hooks" / "guard.py"]


def test_skill_hooks_cover_every_event_and_call_hook_py():
    hooks = json.loads(SKILL_HOOKS.read_text())["hooks"]
    assert set(hooks) == set(EVENTS)
    for event, arg in EVENTS.items():
        [group] = hooks[event]
        [handler] = group["hooks"]
        assert handler["type"] == "command"
        assert handler["command"] == 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/hook.py" ' + arg
    assert hooks["SessionStart"][0]["matcher"] == "startup|resume|compact"
    assert hooks["SessionStart"][0]["hooks"][0]["asyncRewake"] is True
    assert hooks["StopFailure"][0]["hooks"][0]["asyncRewake"] is True
    assert hooks["StopFailure"][0]["hooks"][0]["timeout"] >= 1000
    assert hooks["PreToolUse"][0]["matcher"] == "Bash|mcp__.*"


def test_root_hooks_mirror_skill_hooks():
    mirrored = SKILL_HOOKS.read_text().replace("${CLAUDE_PLUGIN_ROOT}/hooks/",
                                               "${CLAUDE_PLUGIN_ROOT}/skills/sleepless/hooks/")
    assert json.loads(ROOT_HOOKS.read_text()) == json.loads(mirrored)


def test_sleepless_plugin_manifest():
    data = json.loads((SLEEPLESS_DIR / ".claude-plugin" / "plugin.json").read_text())
    assert data["name"] == "sleepless"
    assert "version" not in data


def test_sleepless_scripts_parse_as_python_39():
    for p in SCRIPTS:
        ast.parse(p.read_text(), filename=str(p), feature_version=(3, 9))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sleepless_files.py -q`
Expected: 3 FAIL (`FileNotFoundError` for the JSON files), the 3.9 parse test passes.

- [ ] **Step 3: Write the manifests**

Create `skills/sleepless/.claude-plugin/plugin.json`:

```json
{
  "name": "sleepless",
  "description": "Long autonomous work shifts in any git repo: keeps working until you say stop, resumes after restarts, blocks dangerous commands.",
  "author": {
    "name": "Simon"
  },
  "license": "MIT"
}
```

Create `skills/sleepless/hooks/hooks.json`:

```json
{
  "hooks": {
    "Stop": [
      {"hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/hook.py\" stop", "timeout": 30}]}
    ],
    "UserPromptSubmit": [
      {"hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/hook.py\" prompt", "timeout": 10}]}
    ],
    "SessionStart": [
      {"matcher": "startup|resume|compact", "hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/hook.py\" session-start", "asyncRewake": true, "timeout": 30}]}
    ],
    "StopFailure": [
      {"hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/hook.py\" stop-failure", "asyncRewake": true, "timeout": 1200}]}
    ],
    "PreToolUse": [
      {"matcher": "Bash|mcp__.*", "hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/hook.py\" pre-tool-use", "timeout": 10}]}
    ]
  }
}
```

Create `hooks/hooks.json` with the same content, every `${CLAUDE_PLUGIN_ROOT}/hooks/hook.py` replaced by `${CLAUDE_PLUGIN_ROOT}/skills/sleepless/hooks/hook.py`:

```json
{
  "hooks": {
    "Stop": [
      {"hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/sleepless/hooks/hook.py\" stop", "timeout": 30}]}
    ],
    "UserPromptSubmit": [
      {"hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/sleepless/hooks/hook.py\" prompt", "timeout": 10}]}
    ],
    "SessionStart": [
      {"matcher": "startup|resume|compact", "hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/sleepless/hooks/hook.py\" session-start", "asyncRewake": true, "timeout": 30}]}
    ],
    "StopFailure": [
      {"hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/sleepless/hooks/hook.py\" stop-failure", "asyncRewake": true, "timeout": 1200}]}
    ],
    "PreToolUse": [
      {"matcher": "Bash|mcp__.*", "hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/sleepless/hooks/hook.py\" pre-tool-use", "timeout": 10}]}
    ]
  }
}
```

- [ ] **Step 4: Run tests and validate the plugins**

Run: `uv run pytest -q`
Expected: all pass.

Run: `claude plugin validate . && claude plugin validate skills/sleepless`
Expected: both print `Validation passed`. If the repo-level validation complains about the nested `.claude-plugin` inside `skills/sleepless/`, stop and report to the user (it decides whether the dual install route survives).

- [ ] **Step 5: Commit**

```bash
git add skills/sleepless/.claude-plugin/plugin.json skills/sleepless/hooks/hooks.json hooks/hooks.json tests/test_sleepless_files.py
git commit -m "feat(sleepless): register shift hooks for skills-dir and plugin installs"
```

---

### Task 5: The skill (`SKILL.md`)

**Files:**
- Create: `skills/sleepless/SKILL.md`
- Modify: `tests/test_sleepless_files.py` (append tests)

**Interfaces:**
- Consumes: CLI from Task 1 (`start/status/end/finish` and their flags), hook messages from Task 3 ("next item", "pauses", "A sleepless shift is active", "weiter").

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sleepless_files.py`:

```python
def test_skill_md_frontmatter_and_key_steps():
    text = (SLEEPLESS_DIR / "SKILL.md").read_text()
    assert text.startswith("---\nname: sleepless\ndescription: Use when ")
    for needle in ('scripts/shift.py" start', 'scripts/shift.py" status', 'scripts/shift.py" end',
                   'scripts/shift.py" finish', "AskUserQuestion", "PushNotification",
                   "SLEEPLESS-REPORT.md", "Never merge", "caffeinate", "weiter"):
        assert needle in text, needle


def test_report_template_placeholders():
    text = (SLEEPLESS_DIR / "templates" / "SLEEPLESS-REPORT.md").read_text()
    for key in ("label", "branch", "base", "started", "end"):
        assert "{{%s}}" % key in text
    for heading in ("## Summary", "## Done", "## Decisions and questions", "## Blocked",
                    "## Findings", "## Next"):
        assert heading in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sleepless_files.py -q`
Expected: `test_skill_md_frontmatter_and_key_steps` FAILS with `FileNotFoundError`.

- [ ] **Step 3: Write `SKILL.md`**

Create `skills/sleepless/SKILL.md`:

````markdown
---
name: sleepless
description: Use when the user starts a long autonomous work shift in a repo – overnight or while away ("sleepless", "work through the night", "keep going until I say stop", "Nachtschicht") – and whenever a sleepless hook message says a shift is active.
---

# sleepless

A shift is a long unattended work session on its own branch. It ends only the way the user chose
at the start: **stop** in chat, a time, a number of hours, or the task list being done. While
`.claude/sleepless/state.json` exists, this plugin's hooks enforce the mechanics: the Stop hook
keeps the turn going, "stop" and "weiter" in chat end or resume the shift, a new session after a
restart is woken automatically, and dangerous commands are blocked. This skill says what to do with
the time.

`$SHIFT` below stands for `python3 "${CLAUDE_SKILL_DIR}/scripts/shift.py"`, run inside the repo.

Talk to the user in their language. Everything written to files, commits and the PR is in English.

## Start (once)

1. `python3 "${CLAUDE_SKILL_DIR}/scripts/shift.py" status`. If a shift is active, you are resuming:
   go to **After a restart**.
2. Detect what is there: a task list in the user's prompt, `TODO.md`, open issues
   (`gh issue list --limit 20`, only if `gh` works), how tests run (CLAUDE.md, README, package
   files), how deploys run.
3. One `AskUserQuestion` round, at most 4 questions. Detected options first, marked "(detected)":
   - **End of shift**: "When I say stop" / "At a time" / "After N hours" / "When the list is done".
     The user types the time or hours via "Other"; if not, use a second question in the same round.
   - **Task sources** (multi-select): "List in my prompt" / "TODO.md" / "GitHub issues" /
     "Propose tasks" (you derive tasks from the repo and write them into the report's plan first).
   Never ask about cost – there is no cost limit. Never ask about keeping the machine awake – that
   is the user's job; never start `caffeinate` or anything similar.
4. `python3 "${CLAUDE_SKILL_DIR}/scripts/shift.py" start --label "<short topic>" --end <stop|time|hours|list> [--at HH:MM | --hours N] --sources <prompt,todo,issues,propose>`.
   It creates branch `sleepless/<date>`, the state, and `SLEEPLESS-REPORT.md`.
5. Write the plan (the task list in order) into the report, commit `docs(sleepless): start shift`,
   `git push -u origin <branch>`.
6. Tell the user in 2–3 lines: branch, end condition, first task. Start the first task in the same
   turn.

## The loop

For every item:

1. Do the work. Independent items may run in parallel subagents; give each a self-contained prompt
   and never let two touch the same files.
2. Run the tests. Red → fix. If you can't, revert or park the change and note it.
3. Review by a subagent: hand it the diff and the item. Fix real findings, note the rest under
   Findings.
4. Commit (`type(scope): what`), push.
5. Update `SLEEPLESS-REPORT.md` (Done: item → commit hashes; can go into the item's commit), push.
6. Take the next item **in the same turn**.

| Order | Source | Done means |
|---|---|---|
| 1 | the chosen sources: prompt list → `TODO.md` → issues → proposed tasks | every item done or on the question list |
| 2 | quality work | failing or missing tests, stale docs, TODO/FIXME in code, lint and type warnings, small refactors that make code clearer |

End condition "when the list is done": after row 1, run
`python3 "${CLAUDE_SKILL_DIR}/scripts/shift.py" end` and follow the wrap-up it prints. Every other end condition: quality work runs until the shift ends.

## Decisions and blockers

- Decide yourself. Write every decision with its reason under "Decisions and questions" in the
  report. When unsure, pick the option that is easiest to undo.
- Blocked: write the question and what you tried, switch to the next item, come back when
  something changes. Nothing waits for the user.

## Allowed without asking

Pushing the shift branch, opening or updating the shift PR, and deploys as the repo documents them
(CLAUDE.md, README, scripts). Session-hygiene rules ("suggest a new session") are waived during a
shift; compaction is expected and the report carries the state.

## Blocked by the hooks

Force push, push to main/master, deleting remote branches, deleting outside the repo, sending
messages (PR/issue comments, new issues, mail, chat webhooks, MCP send tools). A denied command is
not an error: note it if it mattered and do something else. Never work around the guard.

## Push notifications

Send `PushNotification` (load it with ToolSearch if it is deferred) only for: the idle pause, the
end of the shift (with the PR link), and important findings (security issue, broken main, risk of
data loss). The user is asleep.

## Pause

When the Stop hook says the shift pauses (no repo change across several stop attempts): push,
`PushNotification` with the reason, end the turn. The shift stays active; the user resumes it with
"weiter".

## End

On the wrap-up instruction (from "stop" in chat, a passed deadline, or `$SHIFT end`):

1. Finish or cleanly park the current step; tests; commit; push.
2. Final report: summary with real duration (including restarts and pauses), done, decisions and
   questions, blocked, findings, next. Commit, push.
3. `gh pr create --base <base> --head <branch> --title "sleepless: <label>" --body-file SLEEPLESS-REPORT.md`,
   or `gh pr edit <number> --body-file SLEEPLESS-REPORT.md` if the PR exists. Never merge.
4. `PushNotification` with the PR link.
5. `python3 "${CLAUDE_SKILL_DIR}/scripts/shift.py" finish`.
6. Closing message: what was done, the PR link, open questions.

## After a restart

A hook wakes the new session with "A sleepless shift is active". Then: `$SHIFT status`,
`git switch <branch>` if needed, read `SLEEPLESS-REPORT.md` and `git log --oneline <base>..HEAD`,
note the restart time in the report, continue with the next item.

## Red flags – all of these mean: take the next item

| Thought | Reality |
|---|---|
| "The list is done." | Quality work starts now (unless the end condition is "list done"). |
| "The next step needs the user." | Decide, note it with the reason, build. |
| "Good stopping point, I'll summarise." | The summary is the report. The turn goes on. |
| "The context is very long." | Compaction handles it; the report is the memory. |
| "I'm blocked." | Question list, next item. |
| The Stop hook blocked the stop | Not an error. Read its reason and continue. |

## Common mistakes

- Ending a message with "next step needs you" while the shift is active.
- Waiting on a background build instead of starting the next independent item.
- `sleep` loops to pass time: the idle guard pauses the shift; real work does not.
- Committing `.claude/sleepless/` – it is excluded via `.git/info/exclude`; never force-add it.
````

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add skills/sleepless/SKILL.md tests/test_sleepless_files.py
git commit -m "feat(sleepless): add shift skill"
```

---

### Task 6: Docs and end-to-end check

**Files:**
- Modify: `README.md` (sections Install, Use, Layout)
- Modify: `CLAUDE.md` (Pitfalls)

- [ ] **Step 1: README**

In `README.md`, after the "## Use" section add:

````markdown
## sleepless

A second skill: a long autonomous work shift in any git repo. Claude works through a task list and
then quality work on branch `sleepless/<date>`, commits and pushes after every step, and ends with
`SLEEPLESS-REPORT.md` and a pull request (never a merge). Start it with `/sleepless` or "work
through the night".

Hooks do the parts that must not depend on Claude:

| Hook | Does |
|---|---|
| Stop | keeps the turn going; pauses after 6 stop attempts without a repo change |
| UserPromptSubmit | `stop` ends the shift, `weiter` resumes a paused one |
| SessionStart | wakes a restarted session and continues the shift |
| StopFailure | retries 15 minutes after an API error |
| PreToolUse | blocks force push, push to main/master, deleting outside the repo, sending messages |

Without an active shift the hooks do nothing. State lives in `.claude/sleepless/` (git-excluded).
Keeping the machine awake is up to you.
````

In "## Install", replace the symlink block with:

````markdown
```bash
git clone <repo-url> ~/repos/agent-therapist
ln -s ~/repos/agent-therapist/skills/agent-therapist ~/.claude/skills/agent-therapist
ln -s ~/repos/agent-therapist/skills/sleepless ~/.claude/skills/sleepless
```

`skills/sleepless` has its own `.claude-plugin/plugin.json`, so the symlink loads it as plugin
`sleepless@skills-dir` including its hooks. Use either the symlinks or the plugin install below,
not both – otherwise every sleepless hook runs twice.
````

In "## Layout", add under `skills/agent-therapist/…`:

```
skills/sleepless/
  .claude-plugin/plugin.json     makes the skill folder a plugin (hooks load via symlink)
  SKILL.md                       the shift flow
  hooks/hooks.json, hook.py      hook registration and entry point
  hooks/guard.py                 commands blocked during a shift
  scripts/shift.py               shift state and CLI
  templates/SLEEPLESS-REPORT.md  report skeleton
hooks/hooks.json                 sleepless hooks for the plugin install
```

- [ ] **Step 2: CLAUDE.md**

Replace the first Pitfalls line in `CLAUDE.md` with:

```markdown
- `~/.claude/skills/agent-therapist` and `~/.claude/skills/sleepless` are symlinks into `skills/` – every edit is live in real sessions, including the sleepless hooks.
```

- [ ] **Step 3: Full test run**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 4: End-to-end check with a real session (scratch repo, `--plugin-dir`)**

In a scratch directory (session scratchpad, not the repo):

```bash
git init -q e2e && cd e2e && git commit -q --allow-empty -m init
python3 <repo>/skills/sleepless/scripts/shift.py start --label e2e --end stop --sources propose
SLEEPLESS_IDLE_LIMIT=2 claude -p "Reply with OK." --model haiku --plugin-dir <repo> < /dev/null
python3 <repo>/skills/sleepless/scripts/shift.py status
```

Expected: the `-p` run ends after the pause block (status shows `"status": "paused"`); a
`git push origin main` attempt inside such a run is denied. Record the result in the task report.
No cleanup with `rm -rf` – the scratchpad is discarded with the session.

- [ ] **Step 5: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs(sleepless): document install, hooks and layout"
```

- [ ] **Step 6: Hand back to the user**

Ask before: pushing `feat/sleepless`, opening the PR, and creating the symlink
`~/.claude/skills/sleepless` (outside the repo).
