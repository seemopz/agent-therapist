from __future__ import annotations

import json

from conftest import ROOT, SKILL_DIR


def test_plugin_manifest_is_valid_json():
    data = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert data["name"] == "agent-therapist"
    assert data["skills"] == "./skills/"


def test_guide_is_present_and_has_checklist():
    text = (SKILL_DIR / "references" / "guide.md").read_text()
    assert "## Checklist" in text
    assert "## Checkliste" not in text
    assert "IMPORTANT" in text


def test_guide_is_english_only():
    text = (SKILL_DIR / "references" / "guide.md").read_text()
    import re
    assert not re.search(r"[äöüÄÖÜß]", text)


def test_german_guide_copy_is_preserved_for_docs():
    text = (ROOT / "docs" / "claude-md-guide.de.md").read_text()
    assert "## Checkliste" in text


REF = SKILL_DIR / "references"


def test_questions_has_all_blocks_and_28_questions():
    text = (REF / "questions.md").read_text()
    for n in range(6):
        assert f"## Block {n}" in text
    assert "## Which blocks" in text
    import re
    numbers = [int(m) for m in re.findall(r"^(\d+)\. \*\*", text, re.M)]
    assert numbers == list(range(1, 29))


def test_checklist_has_eight_checks_and_uses_scripts():
    text = (REF / "checklist.md").read_text()
    for n in range(1, 9):
        assert f"## Check {n}" in text
    assert "scripts/tokens.py" in text and "scripts/scan.py" in text


def test_checklist_asks_for_restraint_on_already_good_files():
    text = (REF / "checklist.md").read_text()
    assert "roughly 5 findings or fewer" in text


def test_checklist_check2_requires_naming_repos_exactly():
    text = (REF / "checklist.md").read_text()
    assert "name them with file:line" in text
    assert '"3+"' in text
    assert "personal rule, belongs in global" in text


def test_git_has_fixed_rules_and_detection():
    text = (REF / "git.md").read_text()
    for phrase in ["force-push", "--no-verify", "Co-Authored-By", "release-please",
                   "gh api", "gh pr list --state merged", "## Detection", "## Template: rules/git.md"]:
        assert phrase in text, phrase


def test_permissions_sections():
    text = (REF / "permissions.md").read_text()
    for h in ["## Allow", "## Deny", "## Never allow"]:
        assert h in text
    assert "Read(./.env)" in text


import re as _re

SKILL_MD = SKILL_DIR / "SKILL.md"


def _frontmatter(text: str) -> dict:
    m = _re.match(r"\A---\n(.*?)\n---\n", text, _re.S)
    assert m, "missing frontmatter"
    out = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip()
    return out


def test_skill_frontmatter():
    fm = _frontmatter(SKILL_MD.read_text())
    assert fm["name"] == "agent-therapist"
    assert fm["description"].startswith("Use when")
    assert len(fm["description"]) <= 1024


def test_skill_links_resolve():
    text = SKILL_MD.read_text()
    refs = set(_re.findall(r"(references/[\w.-]+\.md|scripts/[\w.-]+\.py)", text))
    assert refs, "SKILL.md should point to references and scripts"
    for r in refs:
        assert (SKILL_DIR / r).is_file(), r
    for required in ["references/questions.md", "references/checklist.md", "references/hooks.md",
                     "references/git.md", "references/permissions.md", "references/guide.md",
                     "scripts/tokens.py", "scripts/scan.py", "scripts/backup.py"]:
        assert required in refs, required


def test_skill_stays_short_and_has_safety_rules():
    text = SKILL_MD.read_text()
    assert len(text.splitlines()) < 250
    for phrase in ["AGENT_THERAPIST_HOME", "backups/agent-therapist", "never commit", "Keep as is",
                   "never delete", "json.tool"]:
        assert phrase in text, phrase
    assert "corrections.py" not in text  # stage 2


def test_skill_never_uses_home_as_project_dir():
    text = SKILL_MD.read_text()
    assert "never fall back to the current directory or to `$HOME` as `$P`" in text
    assert "ask the user for the project folder" in text


def test_skill_scopes_scripts_to_global_only_when_scope_is_global():
    text = SKILL_MD.read_text()
    assert text.count("omit `$P` for scope Global") >= 4


def test_skill_undo_has_no_scope_question():
    text = SKILL_MD.read_text()
    assert "Undo has no scope" in text


def test_skill_build_new_runs_scan_and_excludes_secrets():
    text = SKILL_MD.read_text()
    build_new = text.split("**Build new:**")[1].split("**Optimize:**")[0]
    assert "scripts/scan.py" in build_new
    assert "secret" in build_new


def test_skill_safety_names_exceptions():
    text = SKILL_MD.read_text()
    assert "Exception" in text
    assert "--remove-created" in text
    assert "second explicit OK" in text
    collapsed = " ".join(text.split())
    assert "backups under `$G/backups/agent-therapist` may contain secrets" in collapsed


def test_skill_mentions_safety_backup_on_undo():
    text = SKILL_MD.read_text()
    assert "safety_backup" in text
    assert "safety backup" in text


def test_skill_pins_memory_files_always_english():
    text = SKILL_MD.read_text()
    assert "always in English" in text
    assert "Reply in German. Be brief, result first." in text


def test_questions_language_question_excludes_memory_files():
    text = (REF / "questions.md").read_text()
    assert "not memory files" in text
    assert "always English" in text


def test_skill_decides_mode_per_level_for_empty_global():
    text = SKILL_MD.read_text()
    assert "Decide the mode per level, not once for both" in text
    assert "the global level always runs as **Build new**" in text
    assert "preselected" in text


def test_skill_requires_reasons_to_be_checkable():
    text = SKILL_MD.read_text()
    assert "Every reason must be checkable against the files or the preview" in text
    assert "deviates from the global default" in text


def test_skill_step7_lists_followups_for_repo_sourced_rules():
    text = SKILL_MD.read_text()
    assert "agent-therapist does not" in text
    assert "edit other repos" in text
    step7 = text.split("## Step 7")[1]
    assert "repo/file:line" in step7


def test_skill_asks_how_to_handle_project_deviations():
    text = SKILL_MD.read_text()
    assert "Record exception" in text and "Align repo with the default" in text
    assert "only for the current project" in text
    git = (REF / "git.md").read_text()
    assert "Record exception" in git


def test_feedback_round_3_rules():
    text = SKILL_MD.read_text()
    # 1. failed detection commands are explained in one sentence
    assert "Failed: <command> – <what it means>" in text
    # 2. rule-only switches need no TODO
    assert "Only real setup work goes into `TODO.md`" in text
    # 3. aligning to Branch + PR offers the commit hook right away
    assert "offer `no-commit-on-main` (question 28) right away" in text
    q = (REF / "questions.md").read_text()
    # optional questions are still asked, auto answers are still confirmed
    assert "Optional means the user may skip the answer – still ask the question." in q


def test_question_plan_is_fixed_and_reported():
    q = (REF / "questions.md").read_text()
    assert "## Question plan" in q
    for row in ["Global, Build new", "Project, Build new", "Project, Optimize", "Global, Optimize"]:
        assert row in q, row
    assert "Asked: " in q  # coverage line after the last round
    assert "Do you also work on other machines" in q
    text = SKILL_MD.read_text()
    assert "questions.md` → Question plan" in text
    c = (REF / "checklist.md").read_text()
    assert "version numbers" in c


def test_feedback_round_5_rules():
    text = SKILL_MD.read_text()
    assert "Failed: <command> – <what it means>" in text
    assert "longer than 10 s" in text
    c = (REF / "checklist.md").read_text()
    assert "only if the global version covers everything this one says" in c


def test_agents_md_is_documented_and_protected_in_build_new():
    guide = (REF / "guide.md").read_text()
    assert "### AGENTS.md" in guide and "claude-md-or-agents-md" in guide and "claudeMdExcludes" in guide
    skill = (SKILL_DIR / "SKILL.md").read_text()
    assert "Never create `$P/CLAUDE.md` without asking first" in skill
    assert "## Check 8 – AGENTS.md" in (REF / "checklist.md").read_text()


def test_every_question_has_a_recommendation():
    import re
    skill = SKILL_MD.read_text()
    assert "Every question gets a recommendation" in skill
    questions = (REF / "questions.md").read_text()
    for line in re.findall(r"^\d+\. \*\*.*$", questions, re.M):
        assert "Recommended" in line, line
    assert "Where?**\n(Global / Project / Both" not in skill
    assert "apply all (Recommended)" in skill
    assert "mark every recommended option" in skill


def test_skill_offers_update_and_stamps_after_saving():
    text = SKILL_MD.read_text()
    assert "scripts/stamp.py diff" in text
    assert "scripts/stamp.py save" in text
    assert "**Update:**" in text
