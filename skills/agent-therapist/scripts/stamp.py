#!/usr/bin/env python3
"""Remember which checks ran on a setup level, and report what is new since then."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from memfiles import discover

HERE = Path(__file__).resolve().parent
DEFAULT_CHECKLIST = HERE.parent / "references" / "checklist.md"
PLUGIN_JSON = HERE.parents[2] / ".claude-plugin" / "plugin.json"
_CHECK_ID = re.compile(r"^<!-- check: ([\w-]+)/(\d+) -->$", re.M)


def checks(checklist_text: str) -> dict[str, int]:
    """Check id → revision, from the `<!-- check: id/rev -->` markers in checklist.md."""
    return {m.group(1): int(m.group(2)) for m in _CHECK_ID.finditer(checklist_text)}


def plugin_version() -> str | None:
    try:
        return json.loads(PLUGIN_JSON.read_text())["version"]
    except (OSError, ValueError, KeyError):
        return None


def _state_file(g: Path) -> Path:
    return g / "agent-therapist" / "state.json"


def _key(p: Path | None) -> str:
    return "global" if p is None else f"project:{p.resolve()}"


def level_files(g: Path, p: Path | None) -> list[Path]:
    """Files agent-therapist manages on one level. settings.local.json is left out on purpose:
    it changes whenever the user approves a permission prompt."""
    if p is None:
        files = [m.path for m in discover([], g)]
        settings = g / "settings.json"
    else:
        root = p.resolve()
        files = [m.path for m in discover([root], g) if root in m.path.parents]
        settings = root / ".claude" / "settings.json"
    if settings.is_file():
        files.append(settings.resolve())
    return sorted(set(files))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(g: Path) -> dict:
    try:
        return json.loads(_state_file(g).read_text())
    except (OSError, ValueError):
        return {}


def save(g: Path, p: Path | None, current: dict[str, int], version: str | None = None,
         now: datetime | None = None) -> dict:
    state = _load(g)
    entry = {
        "version": version,
        "date": (now or datetime.now()).isoformat(timespec="seconds"),
        "checks": current,
        "files": {str(f): _sha(f) for f in level_files(g, p)},
    }
    state[_key(p)] = entry
    target = _state_file(g)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state, indent=2) + "\n")
    return entry


def diff(g: Path, p: Path | None, current: dict[str, int]) -> dict:
    entry = _load(g).get(_key(p))
    if entry is None:
        return {"stamped": False}
    old_checks: dict = entry.get("checks", {})
    old_files: dict = entry.get("files", {})
    now_files = {str(f): _sha(f) for f in level_files(g, p)}
    return {
        "stamped": True,
        "version": entry.get("version"),
        "date": entry.get("date"),
        "new_checks": sorted(c for c in current if c not in old_checks),
        "updated_checks": sorted(c for c, rev in current.items()
                                 if c in old_checks and rev > old_checks[c]),
        "changed_files": sorted(f for f in now_files if f in old_files and now_files[f] != old_files[f]),
        "added_files": sorted(f for f in now_files if f not in old_files),
        "removed_files": sorted(f for f in old_files if f not in now_files),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["save", "diff"])
    ap.add_argument("--global", dest="global_dir", type=Path, required=True)
    ap.add_argument("--project", type=Path)
    ap.add_argument("--level", action="append", choices=["global", "project"],
                    help="save: levels to stamp (repeatable). diff: default is global, plus project if given")
    ap.add_argument("--checklist", type=Path, default=DEFAULT_CHECKLIST)
    args = ap.parse_args(argv)

    g = args.global_dir.expanduser().resolve()
    levels = args.level or (["global", "project"] if args.project else ["global"])
    if "project" in levels and args.project is None:
        ap.error("--level project needs --project")
    current = checks(args.checklist.read_text())
    out = {}
    for level in levels:
        p = args.project.expanduser().resolve() if level == "project" else None
        if args.command == "save":
            out[level] = save(g, p, current, version=plugin_version())
        else:
            out[level] = diff(g, p, current)
    if args.command == "save":
        out = {level: {"saved": True, "files": len(e["files"])} for level, e in out.items()}
    json.dump(out, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
