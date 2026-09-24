#!/usr/bin/env python3
"""Back up files before agent-therapist writes them, and restore the latest backup."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


def _stored(backup: Path, original: Path) -> Path:
    return backup / "files" / str(original).lstrip("/")


def save(root: Path, files: list[Path], now: datetime | None = None) -> Path:
    stamp = (now or datetime.now()).strftime("%Y-%m-%d_%H%M%S")
    root.mkdir(parents=True, exist_ok=True)
    backup, n = root / stamp, 1
    while backup.exists():
        n += 1
        backup = root / f"{stamp}-{n}"
    backup.mkdir()
    entries = []
    for f in files:
        f = f.resolve()
        existed = f.is_file()
        if existed:
            dest = _stored(backup, f)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        entries.append({"path": str(f), "existed": existed})
    manifest = {"created": (now or datetime.now()).isoformat(timespec="seconds"), "files": entries}
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return backup


def list_backups(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    dirs = [d for d in root.iterdir() if (d / "manifest.json").is_file()]
    return sorted(dirs, key=lambda d: (json.loads((d / "manifest.json").read_text())["created"], d.name),
                  reverse=True)


def restore(backup: Path, dry_run: bool = False, remove_created: bool = False) -> dict:
    manifest = json.loads((backup / "manifest.json").read_text())
    result: dict = {"restored": [], "created": [], "removed": []}
    for e in manifest["files"]:
        target = Path(e["path"])
        if e["existed"]:
            result["restored"].append(e["path"])
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(_stored(backup, target), target)
        elif target.exists():
            result["created"].append(e["path"])
            if remove_created and not dry_run:
                target.unlink()
                result["removed"].append(e["path"])
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("save")
    s.add_argument("--root", type=Path, required=True)
    s.add_argument("files", nargs="+", type=Path)
    ls = sub.add_parser("list")
    ls.add_argument("--root", type=Path, required=True)
    r = sub.add_parser("restore")
    r.add_argument("--root", type=Path, required=True)
    r.add_argument("--id")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--remove-created", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "save":
        print(save(args.root, args.files))
    elif args.cmd == "list":
        for b in list_backups(args.root):
            print(b.name)
    else:
        backups = list_backups(args.root)
        chosen = next((b for b in backups if b.name == args.id), None) if args.id else (backups or [None])[0]
        if chosen is None:
            print("no backup found", file=sys.stderr)
            return 1
        result = {"backup": str(chosen)}
        if not args.dry_run:
            # Restoring overwrites live files; without this, edits made after the backed-up run
            # (or the run itself) would be lost with no way back. Save them first.
            manifest = json.loads((chosen / "manifest.json").read_text())
            current = [Path(e["path"]) for e in manifest["files"]]
            result["safety_backup"] = str(save(args.root, current))
        result.update(restore(chosen, args.dry_run, args.remove_created))
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
