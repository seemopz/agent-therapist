from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from conftest import SKILL_DIR
from stamp import checks, diff, level_files, save

SCRIPT = SKILL_DIR / "scripts" / "stamp.py"
T1 = datetime(2026, 9, 25, 10, 0, 0)

CHECKLIST_V1 = """# Checks
## Check 1 – Token cost
<!-- check: tokens/1 -->
text
## Check 2 – Secrets
<!-- check: secrets/1 -->
"""

CHECKLIST_V2 = """# Checks
## Check 1 – Token cost
<!-- check: tokens/1 -->
## Check 2 – Secrets
<!-- check: secrets/2 -->
## Check 3 – AGENTS.md
<!-- check: agents/1 -->
"""


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    g = tmp_path / "home" / ".claude"
    (g / "rules").mkdir(parents=True)
    (g / "CLAUDE.md").write_text("# Me\n")
    (g / "rules" / "git.md").write_text("# Git\n")
    (g / "settings.json").write_text("{}\n")
    p = tmp_path / "proj"
    (p / ".claude").mkdir(parents=True)
    (p / "CLAUDE.md").write_text("# proj\n")
    (p / ".claude" / "settings.json").write_text("{}\n")
    (p / ".claude" / "settings.local.json").write_text("{}\n")
    return g.resolve(), p.resolve()


def test_checks_parses_ids_and_revisions():
    assert checks(CHECKLIST_V2) == {"tokens": 1, "secrets": 2, "agents": 1}


def test_real_checklist_has_an_id_per_check():
    text = (SKILL_DIR / "references" / "checklist.md").read_text()
    found = checks(text)
    assert len(found) == text.count("\n## Check ")
    assert all(rev >= 1 for rev in found.values())


def test_level_files_cover_memory_and_settings_but_not_local_settings(tmp_path):
    g, p = _setup(tmp_path)
    assert level_files(g, None) == sorted([g / "CLAUDE.md", g / "rules" / "git.md", g / "settings.json"])
    assert level_files(g, p) == sorted([p / "CLAUDE.md", p / ".claude" / "settings.json"])


def test_no_stamp_means_not_stamped(tmp_path):
    g, p = _setup(tmp_path)
    assert diff(g, p, checks(CHECKLIST_V1)) == {"stamped": False}


def test_unchanged_level_has_nothing_to_do(tmp_path):
    g, p = _setup(tmp_path)
    save(g, p, checks(CHECKLIST_V1), version="0.2.0", now=T1)
    result = diff(g, p, checks(CHECKLIST_V1))
    assert result == {
        "stamped": True, "version": "0.2.0", "date": "2026-09-25T10:00:00",
        "new_checks": [], "updated_checks": [],
        "changed_files": [], "added_files": [], "removed_files": [],
    }


def test_diff_reports_new_and_updated_checks(tmp_path):
    g, p = _setup(tmp_path)
    save(g, None, checks(CHECKLIST_V1), version="0.2.0", now=T1)
    result = diff(g, None, checks(CHECKLIST_V2))
    assert result["new_checks"] == ["agents"]
    assert result["updated_checks"] == ["secrets"]


def test_diff_reports_changed_added_and_removed_files(tmp_path):
    g, p = _setup(tmp_path)
    save(g, p, checks(CHECKLIST_V1), version="0.2.0", now=T1)
    (p / "CLAUDE.md").write_text("# proj\nnew line\n")
    (p / ".claude" / "settings.json").unlink()
    (p / "sub").mkdir()
    (p / "sub" / "CLAUDE.md").write_text("# sub\n")
    (p / ".claude" / "settings.local.json").write_text('{"x": 1}\n')  # ignored
    result = diff(g, p, checks(CHECKLIST_V1))
    assert result["changed_files"] == [str(p / "CLAUDE.md")]
    assert result["added_files"] == [str(p / "sub" / "CLAUDE.md")]
    assert result["removed_files"] == [str(p / ".claude" / "settings.json")]


def test_levels_are_stamped_separately(tmp_path):
    g, p = _setup(tmp_path)
    save(g, p, checks(CHECKLIST_V1), version="0.2.0", now=T1)
    assert diff(g, None, checks(CHECKLIST_V1)) == {"stamped": False}
    state = json.loads((g / "agent-therapist" / "state.json").read_text())
    assert list(state) == [f"project:{p}"]


def test_cli_save_then_diff(tmp_path):
    g, p = _setup(tmp_path)
    checklist = tmp_path / "checklist.md"
    checklist.write_text(CHECKLIST_V1)
    run = lambda *a: subprocess.run([sys.executable, str(SCRIPT), *a, "--global", str(g),
                                     "--checklist", str(checklist)],
                                    capture_output=True, text=True, check=True)
    run("save", "--level", "global", "--project", str(p), "--level", "project")
    checklist.write_text(CHECKLIST_V2)
    out = json.loads(run("diff", "--project", str(p)).stdout)
    assert set(out) == {"global", "project"}
    assert out["global"]["new_checks"] == ["agents"]
    assert out["project"]["updated_checks"] == ["secrets"]


def test_cli_diff_without_project_only_reports_global(tmp_path):
    g, _ = _setup(tmp_path)
    checklist = tmp_path / "checklist.md"
    checklist.write_text(CHECKLIST_V1)
    out = subprocess.run([sys.executable, str(SCRIPT), "diff", "--global", str(g),
                          "--checklist", str(checklist)],
                         capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == {"global": {"stamped": False}}
