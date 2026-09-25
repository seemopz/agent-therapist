from __future__ import annotations

import re

from conftest import PREPROMPT_DIR

RULES = PREPROMPT_DIR / "references" / "prompt-rules.md"
SKELETON_TAGS = ("context", "task", "requirements", "constraints", "examples",
                 "output_format", "success_criteria")


def test_rules_has_all_sections():
    text = RULES.read_text()
    for heading in ("## Skeleton", "## Rules", "## Checklist", "## Sources"):
        assert heading in text, heading


def test_rules_skeleton_has_every_tag():
    text = RULES.read_text()
    for tag in SKELETON_TAGS:
        assert "<%s>" % tag in text and "</%s>" % tag in text, tag


def test_rules_cover_key_points_from_docs():
    text = RULES.read_text()
    for needle in ("reason", "positive", "all-caps", "15 years", "3–5", "last",
                   "explain its reasoning", "platform.claude.com"):
        assert needle in text, needle


def test_rules_are_english_only():
    assert not re.search(r"[äöüÄÖÜß]", RULES.read_text())


SKILL = PREPROMPT_DIR / "SKILL.md"


def test_skill_frontmatter():
    text = SKILL.read_text()
    assert text.startswith("---\nname: preprompt\ndescription: Use when ")
    assert "\nargument-hint: <idea>\n" in text.split("\n---\n", 1)[0] + "\n"


def test_skill_flow_key_steps():
    text = SKILL.read_text()
    for needle in ("references/prompt-rules.md", "AskUserQuestion", "at most 8",
                   "one code block", "Run it now?", "Yes", "Adjust", "No",
                   "What is it about?"):
        assert needle in text, needle


def test_skill_is_english_only_and_short():
    text = SKILL.read_text()
    assert not re.search(r"[äöüÄÖÜß]", text)
    assert len(text.splitlines()) <= 90
