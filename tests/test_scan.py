from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import SKILL_DIR
from scan import scan_file

SCRIPT = SKILL_DIR / "scripts" / "scan.py"


def checks(findings, name):
    return [f for f in findings if f.check == name]


def test_length_thresholds(tmp_path):
    p = tmp_path / "CLAUDE.md"
    p.write_text("x\n" * 61)
    assert [f.severity for f in checks(scan_file(p), "length")] == ["low"]
    p.write_text("x\n" * 201)
    assert [f.severity for f in checks(scan_file(p), "length")] == ["high"]
    p.write_text("x\n" * 31)
    assert [f.severity for f in checks(scan_file(p, is_global=True), "length")] == ["medium"]


def test_more_than_one_important(tmp_path):
    p = tmp_path / "CLAUDE.md"
    p.write_text("IMPORTANT: a\nok\nIMPORTANT: b\nIMPORTANT: c\n")
    assert [f.line for f in checks(scan_file(p), "important")] == [3, 4]


def test_secret_credential_pair_is_found_and_masked(tmp_path):
    p = tmp_path / "CLAUDE.md"
    p.write_text("login:\n  `user@test.local` / `abc123XYZ!` was re-registered\n")
    found = checks(scan_file(p), "secret")
    assert [(f.line, f.severity) for f in found] == [(2, "high")]
    assert "abc123XYZ" not in found[0].message
    assert "`a…" in found[0].message or "ab…" in found[0].message


def test_secret_assignments_and_prefixes(tmp_path):
    p = tmp_path / "CLAUDE.md"
    p.write_text(
        "-e POSTGRES_PASSWORD=example\n"
        "token: ghp_abcdefghijklmnopqrstuvwx\n"
        "api_key = sk-abcdefghijklmnopqrstu\n"
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
    )
    assert [f.line for f in checks(scan_file(p), "secret")] == [1, 2, 3, 4]


def test_secret_ignores_placeholders_and_prose(tmp_path):
    p = tmp_path / "CLAUDE.md"
    p.write_text(
        "password: $DB_PASSWORD\n"
        "token=<your token>\n"
        "session/push tokens, the password hash\n"
        "`-vk.debug.login mail:pass` (real login)\n"
        "Passwords: Argon2.\n"
    )
    assert checks(scan_file(p), "secret") == []


def test_diary_markers(tmp_path):
    p = tmp_path / "CLAUDE.md"
    p.write_text(
        "# App\n"
        "## Export my data (20 Sep '26)\n"
        "## State (Jul '26): skeleton stands\n"
        "- old approach, superseded by X\n"
        "- 246 tests, SwiftLint 0\n"
        "## Commands\n"
    )
    assert [f.line for f in checks(scan_file(p), "diary")] == [2, 3, 4, 5]


def test_cli_json(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("x\n" * 201)
    res = subprocess.run([sys.executable, str(SCRIPT), "--json", str(tmp_path)],
                         capture_output=True, text=True, check=True)
    data = json.loads(res.stdout)
    assert data["findings"][0]["check"] == "length"


def test_cli_survives_unreadable_file(tmp_path):
    broken = tmp_path / "CLAUDE.md"
    broken.symlink_to(tmp_path / "does-not-exist.md")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "CLAUDE.md").write_text("x\n" * 201)

    res = subprocess.run([sys.executable, str(SCRIPT), "--json", str(tmp_path)],
                         capture_output=True, text=True)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    lengths = [f for f in data["findings"] if f["check"] == "length"]
    assert any(f["file"].endswith(str(Path("sub") / "CLAUDE.md")) for f in lengths)


def test_diary_message_does_not_leak_secret_on_same_line(tmp_path):
    p = tmp_path / "CLAUDE.md"
    p.write_text("## Login (20 Sep '26) admin@example.com / hunter2secret\n")
    findings = scan_file(p)
    assert checks(findings, "secret"), "expected a secret finding on the same line"
    for f in findings:
        assert "hunter2secret" not in f.message


def test_secret_credential_pair_ignores_two_emails(tmp_path):
    p = tmp_path / "CLAUDE.md"
    p.write_text(
        "login:\n"
        "  `user@test.local` / `abc123XYZ!` was re-registered\n"
        "contact alice@example.com / bob@example.com for access\n"
    )
    found = checks(scan_file(p), "secret")
    assert [f.line for f in found] == [2]


def test_agents_read_in_words_is_flagged_but_import_is_not(tmp_path):
    p = tmp_path / "CLAUDE.md"
    p.write_text("Read AGENTS.md before you start.\n@AGENTS.md\nLies zuerst AGENTS.md.\n")
    assert [f.line for f in checks(scan_file(p), "agents")] == [1, 3]


def test_cli_flags_ignored_agents_md_and_session_start_hook(tmp_path):
    tmp_path = tmp_path.resolve()
    g = tmp_path / "home-claude"
    g.mkdir()
    (g / "settings.json").write_text(json.dumps({"hooks": {"SessionStart": [
        {"hooks": [{"type": "command", "command": "cat AGENTS.md 2>/dev/null"}]}]}}, indent=2))
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "AGENTS.md").write_text("shared\n")
    (proj / "CLAUDE.md").write_text("claude only\n")

    res = subprocess.run([sys.executable, str(SCRIPT), "--json", "--global", str(g), str(proj)],
                         capture_output=True, text=True, check=True)
    found = {(Path(f["file"]).name, f["line"]) for f in json.loads(res.stdout)["findings"]
             if f["check"] == "agents"}
    assert found == {("AGENTS.md", 1), ("settings.json", 8)}

    (proj / "CLAUDE.md").write_text("@AGENTS.md\nclaude only\n")
    res = subprocess.run([sys.executable, str(SCRIPT), "--json", str(proj)],
                         capture_output=True, text=True, check=True)
    assert not [f for f in json.loads(res.stdout)["findings"] if f["check"] == "agents"]
