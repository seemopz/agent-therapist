#!/usr/bin/env python3
"""Deterministic checks on Claude Code memory files: length, IMPORTANT, secrets, diary, AGENTS.md."""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from memfiles import AGENTS_NAME, discover
from tokens import measure


@dataclass
class Finding:
    file: str
    line: int
    check: str
    severity: str  # high | medium | low
    message: str


EMAIL = r"[\w.+-]+@[\w-]+\.[\w.-]+"
SECRET_PATTERNS = [
    ("credential pair", re.compile(r"`?" + EMAIL + r"`?\s*/\s*`?([^\s`]{6,})`?")),
    ("assignment", re.compile(
        r"(?i)(?:password|passwort|pwd|secret|token|api[_-]?key)\s*[:=]\s*[`'\"]?([^\s`'\"]{4,})")),
    ("key", re.compile(
        r"\b(sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_\w{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[\w-]{10,})")),
    ("private key", re.compile(r"(-----BEGIN [A-Z ]*PRIVATE KEY-----)")),
]
PLACEHOLDER = re.compile(r"(?i)^(\$|<|…|\.\.\.|\*{3}|x{3}|your[-_])")

DIARY_PATTERNS = [
    ("dated heading", re.compile(
        r"^#{1,6} .*(\(\d{1,2} \w{3} '\d{2}\)|\d{4}-\d{2}-\d{2}|\b[A-Z][a-z]{2} '\d{2}\b)")),
    ("outdated marker", re.compile(r"(?i)\b(superseded|obsolete|veraltet|überholt|no longer)\b")),
    ("counter", re.compile(r"(?i)\b\d+ (tests|commits)\b")),
]

# A sentence that points Claude at AGENTS.md in words instead of importing it with @AGENTS.md.
READ_AGENTS = re.compile(
    r"(?i)\b(read|follow|see|check|load|use|consult|refer|lies|liest|siehe|beachte|befolge)\b.*AGENTS\.md")


def _mask(value: str) -> str:
    return value[:2] + "…"


def scan_file(path: Path, is_global: bool = False) -> list[Finding]:
    f = str(path)
    lines = path.read_text(errors="replace").splitlines()
    out: list[Finding] = []

    n = len(lines)
    if is_global and n > 30:
        out.append(Finding(f, 1, "length", "medium", f"{n} lines; global file should stay under 30"))
    elif n > 200:
        out.append(Finding(f, 1, "length", "high", f"{n} lines; over 200, target under 60"))
    elif n > 60:
        out.append(Finding(f, 1, "length", "low", f"{n} lines; target under 60"))

    important = [i for i, l in enumerate(lines, 1) if re.search(r"\bIMPORTANT\b", l)]
    for i in important[1:]:
        out.append(Finding(f, i, "important", "medium", "more than one IMPORTANT line"))

    for i, line in enumerate(lines, 1):
        secret_found = False
        for kind, rx in SECRET_PATTERNS:
            m = rx.search(line)
            if m:
                value = m.group(1) if m.groups() else m.group(0)
                if PLACEHOLDER.match(value):
                    continue
                if kind == "credential pair" and "@" in value:
                    continue
                out.append(Finding(f, i, "secret", "high", f"possible secret ({kind}): {_mask(value)}"))
                secret_found = True
                break
        if path.name != AGENTS_NAME and READ_AGENTS.search(line) and "@AGENTS.md" not in line:
            out.append(Finding(f, i, "agents", "medium",
                               "tells Claude in words to read AGENTS.md; replace with an @AGENTS.md import"))
        for kind, rx in DIARY_PATTERNS:
            if rx.search(line):
                # Never echo the raw line text when this line also carries a secret finding.
                detail = "line contains a secret" if secret_found else line.strip()[:80]
                out.append(Finding(f, i, "diary", "low", f"{kind}: {detail}"))
                break
    return out


def scan_agents_setup(report: dict) -> list[Finding]:
    """AGENTS.md files that never load, from a tokens.measure() report."""
    loaded = {Path(r["path"]).resolve() for r in report["files"] if r["when"] == "always"}
    out = []
    for r in report["files"]:
        p = Path(r["path"])
        if p.name == AGENTS_NAME and r["when"] == "not loaded" and p.resolve() not in loaded:
            out.append(Finding(str(p), 1, "agents", "medium",
                               "AGENTS.md is not loaded: a CLAUDE.md or CLAUDE.local.md takes precedence "
                               "(or Project instructions excludes it); add @AGENTS.md to that CLAUDE.md"))
    return out


def scan_settings(path: Path) -> list[Finding]:
    """SessionStart hooks that print AGENTS.md – a leftover from before Claude Code read it natively."""
    try:
        raw = path.read_text(errors="replace")
        hooks = json.loads(raw).get("hooks", {}).get("SessionStart", [])
    except (OSError, ValueError, AttributeError):
        return []
    out = []
    for group in hooks if isinstance(hooks, list) else []:
        for h in group.get("hooks", []) if isinstance(group, dict) else []:
            cmd = h.get("command", "") if isinstance(h, dict) else ""
            if AGENTS_NAME in cmd:
                line = next((i for i, l in enumerate(raw.splitlines(), 1) if AGENTS_NAME in l), 1)
                out.append(Finding(str(path), line, "agents", "medium",
                                   "SessionStart hook prints AGENTS.md; Claude Code reads it itself, "
                                   "so this adds a second copy – remove the hook"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("projects", nargs="*", type=Path)
    ap.add_argument("--global", dest="global_dir", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    gdir = args.global_dir.resolve() if args.global_dir else None
    findings: list[Finding] = []
    files = discover(args.projects, args.global_dir)
    for m in files:
        try:
            findings.extend(scan_file(m.path, is_global=gdir is not None and gdir in m.path.parents))
        except OSError as e:
            print(f"warning: cannot read {m.path}: {e}", file=sys.stderr)
            continue
    findings.extend(scan_agents_setup(measure(files)))
    settings = [gdir / "settings.json", gdir / "settings.local.json"] if gdir else []
    for d in args.projects:
        settings += [d / ".claude" / "settings.json", d / ".claude" / "settings.local.json"]
    for sp in settings:
        findings.extend(scan_settings(sp))
    if args.json:
        print(json.dumps({"findings": [asdict(x) for x in findings]}, indent=2, ensure_ascii=False))
    else:
        for x in findings:
            print(f"{x.file}:{x.line} [{x.check}/{x.severity}] {x.message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
