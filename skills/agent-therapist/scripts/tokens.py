#!/usr/bin/env python3
"""Estimate token cost of Claude Code memory files, optionally against a baseline."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

from memfiles import MemFile, discover

CHARS_PER_TOKEN = 3.5  # rough, slightly pessimistic for mixed German/English markdown
MAX_IMPORT_HOPS = 4  # Claude Code follows nested @path imports at most four hops deep

_FENCE = re.compile(r"^ {0,3}(```|~~~).*?^ {0,3}\1[^\n]*$", re.S | re.M)
_CODE_SPAN = re.compile(r"`+[^`]*`+")
# "@path" not preceded by a word character, so e-mail addresses don't count.
_IMPORT = re.compile(r"(?<![\w@])@([~./\w-][^\s`'\"<>()\[\]]*)")


def estimate(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN) if text else 0


def imports(path: Path, text: str) -> list[Path]:
    """Existing files that `text` (the content of `path`) imports with @path."""
    text = _CODE_SPAN.sub("", _FENCE.sub("", text))
    out = []
    for m in _IMPORT.finditer(text):
        raw = m.group(1).rstrip(".,;:!?")
        target = Path(raw).expanduser()
        if not target.is_absolute():
            target = path.parent / target
        target = Path(os.path.normpath(target))
        if target.is_file() and target not in out:
            out.append(target)
    return out


def _add_imports(rows: list[dict]) -> None:
    """Mark files pulled in by @path imports of always-loaded files as always loaded."""
    by_path = {}
    for r in rows:
        by_path.setdefault(Path(r["path"]).resolve(), r)
    loaded = {Path(r["path"]).resolve() for r in rows if r["when"] == "always"}
    queue = [(Path(r["path"]), 0) for r in rows if r["when"] == "always"]
    while queue:
        src, depth = queue.pop(0)
        if depth >= MAX_IMPORT_HOPS:
            continue
        try:
            text = src.read_text(errors="replace")
        except OSError:
            continue
        for target in imports(src, text):
            key = target.resolve()
            if key in loaded:
                continue
            loaded.add(key)
            row = by_path.get(key)
            if row is None:
                try:
                    content = target.read_text(errors="replace")
                except OSError as e:
                    print(f"warning: cannot read {target}: {e}", file=sys.stderr)
                    continue
                row = {"path": str(target), "tokens": estimate(content),
                       "lines": len(content.splitlines())}
                rows.append(row)
                by_path[key] = row
            row["when"] = "always"
            row["via"] = str(src)
            queue.append((target, depth + 1))


def _always_total(rows: list[dict]) -> int:
    seen, total = set(), 0
    for r in rows:
        key = Path(r["path"]).resolve()
        if r["when"] == "always" and key not in seen:  # a symlinked or imported file counts once
            seen.add(key)
            total += r["tokens"]
    return total


def measure(files: list[MemFile]) -> dict:
    rows = []
    for m in files:
        try:
            text = m.path.read_text(errors="replace")
        except OSError as e:
            print(f"warning: cannot read {m.path}: {e}", file=sys.stderr)
            continue
        rows.append({"path": str(m.path), "tokens": estimate(text),
                     "lines": len(text.splitlines()), "when": m.when})
    _add_imports(rows)
    return {
        "files": rows,
        "always_total": _always_total(rows),
        "total": sum(r["tokens"] for r in rows),
    }


def render(report: dict, baseline: dict | None) -> str:
    old = {r["path"]: r for r in (baseline or {}).get("files", [])}
    lines = [f"{'tokens':>8} {'lines':>6}  {'when':<10} {'change':>7}  file"]
    for r in report["files"]:
        change = ""
        if baseline is not None:
            prev = old.pop(r["path"], None)
            change = "new" if prev is None else f"{r['tokens'] - prev['tokens']:+d}"
        via = f" (imported by {Path(r['via']).name})" if r.get("via") else ""
        lines.append(f"{r['tokens']:>8} {r['lines']:>6}  {r['when']:<10} {change:>7}  {r['path']}{via}")
    for path, prev in old.items():
        lines.append(f"{0:>8} {0:>6}  {prev['when']:<10} {-prev['tokens']:>+7d}  {path} (removed)")
    if baseline is not None:
        lines.append(f"always loaded: ≈ {baseline['always_total']} → ≈ {report['always_total']} tokens")
    else:
        lines.append(f"always loaded: ≈ {report['always_total']} tokens (all files: ≈ {report['total']})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("projects", nargs="*", type=Path)
    ap.add_argument("--global", dest="global_dir", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--baseline", type=Path, help="JSON from an earlier --json run")
    args = ap.parse_args(argv)
    report = measure(discover(args.projects, args.global_dir))
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        baseline = json.loads(args.baseline.read_text()) if args.baseline else None
        print(render(report, baseline))
    return 0


if __name__ == "__main__":
    sys.exit(main())
