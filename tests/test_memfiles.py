from __future__ import annotations

import json
from pathlib import Path

from memfiles import MemFile, discover, instruction_mode


def write(p: Path, text: str = "x\n") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def test_project_levels(tmp_path):
    tmp_path = tmp_path.resolve()  # macOS: /var -> /private/var
    root = tmp_path / "proj"
    write(root / "CLAUDE.md")
    write(root / ".claude" / "CLAUDE.md")
    write(root / "ios" / "CLAUDE.md")
    write(root / ".claude" / "rules" / "api.md", "---\npaths:\n  - src/api/**\n---\nrule\n")
    write(root / ".claude" / "rules" / "style.md", "rule\n")
    write(root / "node_modules" / "pkg" / "CLAUDE.md")
    write(root / "README.md")

    found = {m.path.relative_to(root).as_posix(): m.when for m in discover([root], None)}

    assert found == {
        "CLAUDE.md": "always",
        ".claude/CLAUDE.md": "always",
        "ios/CLAUDE.md": "on demand",
        ".claude/rules/api.md": "on demand",
        ".claude/rules/style.md": "always",
    }


def test_global_dir(tmp_path):
    tmp_path = tmp_path.resolve()
    g = tmp_path / "home-claude"
    write(g / "CLAUDE.md")
    write(g / "rules" / "git.md")
    write(g / "projects" / "x" / "memory" / "CLAUDE.md")  # not a memory file

    found = discover([], g)

    assert [m.path.relative_to(g).as_posix() for m in found] == ["CLAUDE.md", "rules/git.md"]
    assert all(m.when == "always" for m in found)


def test_missing_dirs_are_ignored(tmp_path):
    assert discover([tmp_path / "nope"], tmp_path / "also-nope") == []


def test_no_duplicates_when_global_inside_project(tmp_path):
    write(tmp_path / "CLAUDE.md")
    assert len(discover([tmp_path, tmp_path], None)) == 1
    assert isinstance(discover([tmp_path], None)[0], MemFile)


def _set_mode(g: Path, mode: str) -> None:
    write(g / "settings.json", json.dumps(
        {"pluginConfigs": {"agents-md@builtin": {"options": {"instructionFiles": mode}}}}))


def _agents(root: Path, g: Path | None = None) -> dict:
    return {m.path.relative_to(root).as_posix(): m.when for m in discover([root], g)
            if m.path.name == "AGENTS.md"}


def test_agents_md_alone_loads_always(tmp_path):
    root = tmp_path.resolve() / "proj"
    write(root / "AGENTS.md")
    write(root / ".claude" / "AGENTS.md")
    write(root / "pkg" / "AGENTS.md")
    assert _agents(root) == {"AGENTS.md": "always", ".claude/AGENTS.md": "always",
                             "pkg/AGENTS.md": "on demand"}


def test_agents_md_blocked_by_claude_md_in_or_above_project(tmp_path):
    for blocker in ["CLAUDE.md", "CLAUDE.local.md", ".claude/CLAUDE.md", "../CLAUDE.md"]:
        base = tmp_path.resolve() / blocker.replace("/", "_").replace(".", "_")
        root = base / "proj"
        write(root / "AGENTS.md")
        write(root / blocker)
        assert _agents(root) == {"AGENTS.md": "not loaded"}, blocker


def test_user_claude_md_and_rules_do_not_block_agents_md(tmp_path):
    home = tmp_path.resolve()
    g = home / ".claude"
    write(g / "CLAUDE.md")
    write(g / "rules" / "git.md")
    root = home / "proj"
    write(root / "AGENTS.md")
    write(root / ".claude" / "rules" / "style.md")
    assert _agents(root, g) == {"AGENTS.md": "always"}


def test_subdir_agents_md_blocked_only_by_its_own_claude_md(tmp_path):
    root = tmp_path.resolve() / "proj"
    write(root / "CLAUDE.md")
    write(root / "a" / "AGENTS.md")
    write(root / "b" / "AGENTS.md")
    write(root / "b" / "CLAUDE.md")
    assert _agents(root) == {"a/AGENTS.md": "on demand", "b/AGENTS.md": "not loaded"}


def test_instruction_mode_setting(tmp_path):
    tmp_path = tmp_path.resolve()
    g = tmp_path / "home-claude"
    root = tmp_path / "proj"
    write(root / "CLAUDE.md")
    write(root / "AGENTS.md")
    write(root / ".claude" / "rules" / "api.md", "---\npaths:\n  - src/**\n---\nrule\n")
    write(root / ".claude" / "rules" / "style.md")

    assert instruction_mode(g) == "claude-md-or-agents-md"
    _set_mode(g, "claude-md-and-agents-md")
    assert _agents(root, g) == {"AGENTS.md": "always"}
    _set_mode(g, "claude-md")
    assert _agents(root, g) == {"AGENTS.md": "not loaded"}
    _set_mode(g, "managed-only")
    found = {m.path.relative_to(root).as_posix(): m.when for m in discover([root], g)}
    assert found == {"CLAUDE.md": "not loaded", "AGENTS.md": "not loaded",
                     ".claude/rules/api.md": "on demand", ".claude/rules/style.md": "not loaded"}
    _set_mode(g, "bogus")
    assert instruction_mode(g) == "claude-md-or-agents-md"
