from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import SKILL_DIR
from memfiles import MemFile
from tokens import estimate, imports, measure, render

SCRIPT = SKILL_DIR / "scripts" / "tokens.py"


def test_estimate():
    assert estimate("") == 0
    assert estimate("abcdefg") == 2  # 7 / 3.5
    assert estimate("a") == 1


def test_measure_totals(tmp_path):
    a = tmp_path / "CLAUDE.md"
    a.write_text("x" * 35 + "\n" + "y" * 34 + "\n")  # 71 chars -> 21 tokens, 2 lines
    b = tmp_path / "sub" / "CLAUDE.md"
    b.parent.mkdir()
    b.write_text("z" * 7)
    report = measure([MemFile(a, "always"), MemFile(b, "on demand")])
    assert report["files"][0] == {"path": str(a), "tokens": 21, "lines": 2, "when": "always"}
    assert report["always_total"] == 21
    assert report["total"] == 23


def test_measure_skips_unreadable_file(tmp_path, capsys):
    broken = tmp_path / "CLAUDE.md"
    broken.symlink_to(tmp_path / "does-not-exist.md")
    ok = tmp_path / "sub" / "CLAUDE.md"
    ok.parent.mkdir()
    ok.write_text("hello")

    report = measure([MemFile(broken, "always"), MemFile(ok, "always")])

    assert report["files"] == [{"path": str(ok), "tokens": estimate("hello"), "lines": 1, "when": "always"}]
    assert "cannot read" in capsys.readouterr().err


def test_cli_survives_unreadable_file(tmp_path):
    broken = tmp_path / "CLAUDE.md"
    broken.symlink_to(tmp_path / "does-not-exist.md")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "CLAUDE.md").write_text("hello")

    res = subprocess.run([sys.executable, str(SCRIPT), "--json", str(tmp_path)],
                         capture_output=True, text=True)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert any(f["path"].endswith(str(Path("sub") / "CLAUDE.md")) for f in data["files"])


def test_render_with_baseline_shows_delta_and_removed(tmp_path):
    before = {"files": [{"path": "/p/CLAUDE.md", "tokens": 100, "lines": 10, "when": "always"},
                        {"path": "/p/old.md", "tokens": 40, "lines": 4, "when": "always"}],
              "always_total": 140, "total": 140}
    after = {"files": [{"path": "/p/CLAUDE.md", "tokens": 60, "lines": 6, "when": "always"}],
             "always_total": 60, "total": 60}
    out = render(after, before)
    assert "-40" in out
    assert "/p/old.md" in out and "removed" in out
    assert "140 → ≈ 60" in out


def test_cli_json(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("hello world\n")
    res = subprocess.run([sys.executable, str(SCRIPT), "--json", str(tmp_path)],
                         capture_output=True, text=True, check=True)
    data = json.loads(res.stdout)
    assert data["always_total"] == estimate("hello world\n")


def test_imports_resolve_relative_to_importing_file_and_skip_code(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("a")
    (tmp_path / "docs" / "b.md").write_text("b")
    (tmp_path / "AGENTS.md").write_text("agents")
    src = tmp_path / "docs" / "x.md"
    text = ("@a.md and @../AGENTS.md.\n"
            "mail me at user@example.com, missing @nope.md\n"
            "`@b.md` stays literal\n```\n@b.md\n```\n")
    assert imports(src, text) == [tmp_path / "docs" / "a.md", tmp_path / "AGENTS.md"]


def test_measure_counts_imports_as_always_up_to_four_hops(tmp_path):
    for i in range(1, 7):
        nxt = f"@f{i + 1}.md" if i < 6 else ""
        (tmp_path / f"f{i}.md").write_text(f"file {i} {nxt}\n")
    claude = tmp_path / "CLAUDE.md"
    claude.write_text("@f1.md\n@f1.md\n")  # imported twice, counted once

    report = measure([MemFile(claude, "always")])

    names = {Path(r["path"]).name: r.get("via") for r in report["files"]}
    assert set(names) == {"CLAUDE.md", "f1.md", "f2.md", "f3.md", "f4.md"}
    assert Path(names["f1.md"]).name == "CLAUDE.md" and Path(names["f4.md"]).name == "f3.md"
    assert report["always_total"] == sum(r["tokens"] for r in report["files"])
    assert "(imported by f3.md)" in render(report, None)


def test_import_turns_unloaded_agents_md_into_always_and_symlink_counts_once(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text("shared instructions\n")
    claude = tmp_path / "CLAUDE.md"
    claude.write_text("@AGENTS.md\nclaude only\n")
    report = measure([MemFile(agents, "not loaded"), MemFile(claude, "always")])
    assert [r["when"] for r in report["files"]] == ["always", "always"]
    assert report["always_total"] == estimate("shared instructions\n") + estimate("@AGENTS.md\nclaude only\n")

    claude.unlink()
    claude.symlink_to(agents)
    report = measure([MemFile(agents, "always"), MemFile(claude, "always")])
    assert report["always_total"] == estimate("shared instructions\n")
