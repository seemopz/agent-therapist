from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from backup import list_backups, restore, save
from conftest import SKILL_DIR

SCRIPT = SKILL_DIR / "scripts" / "backup.py"
T1 = datetime(2026, 9, 22, 10, 0, 0)
T2 = datetime(2026, 9, 22, 11, 0, 0)


def test_save_and_restore_roundtrip(tmp_path):
    tmp_path = tmp_path.resolve()
    root = tmp_path / "backups"
    a = tmp_path / "proj" / "CLAUDE.md"
    a.parent.mkdir()
    a.write_text("old\n")
    new = tmp_path / "proj" / ".claude" / "settings.json"

    b = save(root, [a, new], now=T1)
    assert b.name == "2026-09-22_100000"
    manifest = json.loads((b / "manifest.json").read_text())
    assert manifest["files"] == [{"path": str(a), "existed": True}, {"path": str(new), "existed": False}]

    a.write_text("changed\n")
    new.parent.mkdir()
    new.write_text("{}")

    result = restore(b)
    assert a.read_text() == "old\n"
    assert new.exists(), "created files are never deleted without explicit flag"
    assert result == {"restored": [str(a)], "created": [str(new)], "removed": []}

    result = restore(b, remove_created=True)
    assert not new.exists()
    assert result["removed"] == [str(new)]


def test_dry_run_changes_nothing(tmp_path):
    root = tmp_path / "backups"
    a = tmp_path / "CLAUDE.md"
    a.write_text("old\n")
    b = save(root, [a], now=T1)
    a.write_text("changed\n")
    assert restore(b, dry_run=True)["restored"] == [str(a.resolve())]
    assert a.read_text() == "changed\n"


def test_list_newest_first_and_same_second(tmp_path):
    root = tmp_path / "backups"
    f = tmp_path / "x.md"
    f.write_text("x")
    first = save(root, [f], now=T1)
    second = save(root, [f], now=T1)
    third = save(root, [f], now=T2)
    assert second.name == "2026-09-22_100000-2"
    assert list_backups(root) == [third, second, first]


def test_cli_save_then_restore_latest(tmp_path):
    root = tmp_path / "backups"
    f = tmp_path / "CLAUDE.md"
    f.write_text("old\n")
    out = subprocess.run([sys.executable, str(SCRIPT), "save", "--root", str(root), str(f)],
                         capture_output=True, text=True, check=True).stdout.strip()
    assert (root / out.split("/")[-1] / "manifest.json").exists()
    f.write_text("new\n")
    subprocess.run([sys.executable, str(SCRIPT), "restore", "--root", str(root)], check=True,
                   capture_output=True)
    assert f.read_text() == "old\n"


def test_cli_restore_makes_a_safety_backup_of_current_files_first(tmp_path):
    tmp_path = tmp_path.resolve()
    root = tmp_path / "backups"
    f = tmp_path / "CLAUDE.md"
    f.write_text("old\n")
    subprocess.run([sys.executable, str(SCRIPT), "save", "--root", str(root), str(f)],
                   check=True, capture_output=True)
    f.write_text("edited after the run\n")

    out = subprocess.run([sys.executable, str(SCRIPT), "restore", "--root", str(root)],
                         check=True, capture_output=True, text=True).stdout
    data = json.loads(out)
    assert f.read_text() == "old\n"  # restore still happens

    safety_dir = Path(data["safety_backup"])
    assert safety_dir.is_dir() and safety_dir != Path(data["backup"])
    stored = safety_dir / "files" / str(f).lstrip("/")
    assert stored.read_text() == "edited after the run\n", "pre-restore state must be preserved"


def test_dry_run_restore_makes_no_safety_backup(tmp_path):
    root = tmp_path / "backups"
    f = tmp_path / "CLAUDE.md"
    f.write_text("old\n")
    subprocess.run([sys.executable, str(SCRIPT), "save", "--root", str(root), str(f)],
                   check=True, capture_output=True)
    f.write_text("new\n")
    before = set(root.iterdir())
    out = subprocess.run([sys.executable, str(SCRIPT), "restore", "--root", str(root), "--dry-run"],
                         check=True, capture_output=True, text=True).stdout
    data = json.loads(out)
    assert "safety_backup" not in data
    assert set(root.iterdir()) == before
