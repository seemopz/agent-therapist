"""Refusal-only tests for tests/sandbox.sh's safety guard.

Never lets the script reach `rm -rf` on anything we did not create ourselves: every case here
must exit 1 before any write. There is deliberately no positive test that runs the full rsync
(that is covered by manually running `tests/sandbox.sh` against a fresh $TMPDIR path, see
tests/scenarios.md).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from conftest import ROOT

SANDBOX_SH = ROOT / "tests" / "sandbox.sh"


def _run(target: str, **env: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SANDBOX_SH), target],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, **env},
    )


def test_refuses_home_repos():
    result = _run(str(Path.home() / "repos"))
    assert result.returncode == 1, result.stdout + result.stderr


def test_refuses_home_itself():
    result = _run(str(Path.home()))
    assert result.returncode == 1, result.stdout + result.stderr


def test_refuses_case_variant_of_repos():
    # On case-insensitive APFS this resolves to the same directory as ~/repos; on a
    # case-sensitive filesystem its parent (~/Repos) typically does not exist. Either way
    # the guard must refuse before any write.
    result = _run(str(Path.home() / "Repos" / "example-repo"))
    assert result.returncode == 1, result.stdout + result.stderr


def test_refuses_existing_dir_without_marker(tmp_path):
    # tmp_path is under /private/var/folders on macOS, i.e. inside the allowed roots — this
    # exercises the marker check specifically, not the allowlist check.
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("do not delete")
    result = _run(str(tmp_path))
    assert result.returncode == 1, result.stdout + result.stderr
    assert sentinel.is_file()


def test_refuses_nonexistent_parent(tmp_path):
    target = tmp_path / "does-not-exist" / "deeper"
    result = _run(str(target))
    assert result.returncode == 1, result.stdout + result.stderr


def test_refuses_missing_source_repo(tmp_path):
    target = tmp_path / "sandbox"
    result = _run(str(target), SANDBOX_REPO_MESSY=str(tmp_path / "no-such-repo"))
    assert result.returncode == 1, result.stdout + result.stderr
    assert not target.exists()
