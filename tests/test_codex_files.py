"""Check that the independently installed Codex skills remain usable packages."""
import re

import pytest

from conftest import ROOT


@pytest.mark.parametrize("name", ["agent-therapist", "preprompt", "sleepless"])
def test_codex_skill_package(name):
    directory = ROOT / "codex" / "skills" / name
    text = (directory / "SKILL.md").read_text(encoding="utf-8")
    frontmatter, body = text.split("\n---\n", 1)
    assert frontmatter.startswith("---\nname: " + name + "\n")
    assert re.search(r"^description: \S.+", frontmatter, re.M)
    assert body.strip()
    for target in re.findall(r"\]\(([^)]+)\)", body):
        if "://" not in target and not target.startswith("#"):
            assert (directory / target.split("#", 1)[0]).is_file(), target


def test_both_agents_share_repository_instructions():
    assert (ROOT / "AGENTS.md").is_file()
    assert "@AGENTS.md" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
