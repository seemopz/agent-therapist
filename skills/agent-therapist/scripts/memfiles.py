"""Find Claude Code memory files (CLAUDE.md, AGENTS.md, rules) and when they are loaded."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

SKIP_DIRS = {
    ".git", "node_modules", ".build", "build", "dist", "DerivedData", ".venv",
    "venv", "Pods", ".next", "target", "__pycache__", ".dart_tool",
}
CLAUDE_NAMES = {"CLAUDE.md", "CLAUDE.local.md"}
AGENTS_NAME = "AGENTS.md"
MEMORY_NAMES = CLAUDE_NAMES | {AGENTS_NAME}
_PATHS_FRONTMATTER = re.compile(r"\A---\s*\n.*?^paths\s*:", re.S | re.M)

# "Project instructions" in /config; stored in user settings under the built-in agents-md plugin.
DEFAULT_MODE = "claude-md-or-agents-md"
MODES = {"claude-md-or-agents-md", "claude-md-and-agents-md", "claude-md", "managed-only"}


@dataclass(frozen=True)
class MemFile:
    path: Path
    when: str  # "always", "on demand" or "not loaded"


def instruction_mode(global_dir: Path | None) -> str:
    """Read the "Project instructions" setting from the user settings.json."""
    if global_dir is None:
        return DEFAULT_MODE
    try:
        data = json.loads((global_dir / "settings.json").read_text())
        mode = data["pluginConfigs"]["agents-md@builtin"]["options"]["instructionFiles"]
    except (OSError, ValueError, KeyError, TypeError):
        return DEFAULT_MODE
    return mode if mode in MODES else DEFAULT_MODE


def has_claude_md(d: Path, global_dir: Path | None = None) -> bool:
    """True if d holds one of the three files that make Claude skip AGENTS.md in d."""
    candidates = [d / "CLAUDE.md", d / "CLAUDE.local.md", d / ".claude" / "CLAUDE.md"]
    # ~/.claude/CLAUDE.md is the user file, not a project file, even when $HOME is an ancestor.
    user = {Path.home() / ".claude" / "CLAUDE.md"}
    if global_dir is not None:
        user.add(global_dir / "CLAUDE.md")
    return any(p.is_file() and p not in user for p in candidates)


def _rule_when(path: Path) -> str:
    try:
        head = path.read_text(errors="replace")[:2000]
    except OSError:
        return "always"
    return "on demand" if _PATHS_FRONTMATTER.search(head) else "always"


def _rules(rules_dir: Path, mode: str) -> list[MemFile]:
    if not rules_dir.is_dir():
        return []
    out = []
    for p in sorted(rules_dir.rglob("*.md")):
        when = _rule_when(p)
        # managed-only drops unscoped rules at launch; path-scoped rules still load.
        out.append(MemFile(p, "not loaded" if mode == "managed-only" and when == "always" else when))
    return out


def _agents_when(p: Path, root: Path, mode: str, global_dir: Path | None) -> str:
    if mode in ("claude-md", "managed-only"):
        return "not loaded"
    d = p.parent.parent if p.parent.name == ".claude" else p.parent
    if d == root:
        if mode == "claude-md-and-agents-md":
            return "always"
        blocked = any(has_claude_md(a, global_dir) for a in [root, *root.parents])
        return "not loaded" if blocked else "always"
    if mode == "claude-md-and-agents-md":
        return "on demand"
    return "not loaded" if has_claude_md(d, global_dir) else "on demand"


def _project(root: Path, mode: str, global_dir: Path | None) -> list[MemFile]:
    out: list[MemFile] = []
    top = {root / "CLAUDE.md", root / "CLAUDE.local.md", root / ".claude" / "CLAUDE.md"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if name in CLAUDE_NAMES:
                if mode == "managed-only":
                    out.append(MemFile(p, "on demand" if p not in top else "not loaded"))
                else:
                    out.append(MemFile(p, "always" if p in top else "on demand"))
            elif name == AGENTS_NAME:
                out.append(MemFile(p, _agents_when(p, root, mode, global_dir)))
    out.extend(_rules(root / ".claude" / "rules", mode))
    return out


def _global(g: Path, mode: str) -> list[MemFile]:
    out: list[MemFile] = []
    when = "not loaded" if mode == "managed-only" else "always"
    if (g / "CLAUDE.md").is_file():
        out.append(MemFile(g / "CLAUDE.md", when))
    out.extend(_rules(g / "rules", mode))
    return out


def discover(project_dirs: list[Path], global_dir: Path | None) -> list[MemFile]:
    found: dict[Path, MemFile] = {}
    g = global_dir.resolve() if global_dir is not None and global_dir.is_dir() else None
    mode = instruction_mode(g)
    if g is not None:
        for m in _global(g, mode):
            found.setdefault(m.path, m)
    for d in project_dirs:
        if d.is_dir():
            for m in _project(d.resolve(), mode, g):
                found.setdefault(m.path, m)
    return [found[p] for p in sorted(found)]
