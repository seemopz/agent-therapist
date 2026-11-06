from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "agent-therapist"
SLEEPLESS_DIR = ROOT / "skills" / "sleepless"
PREPROMPT_DIR = ROOT / "skills" / "preprompt"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(SLEEPLESS_DIR / "scripts"))
sys.path.insert(0, str(SLEEPLESS_DIR / "hooks"))


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A throwaway git repo on branch main with one commit."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def g(*args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    g("init", "-q", "-b", "main")
    g("config", "user.name", "Test")
    g("config", "user.email", "test@example.com")
    g("config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("placeholder\n", encoding="utf-8")
    g("add", ".")
    g("commit", "-qm", "init")
    return repo


def make_symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows symlink tests require Developer Mode or administrator rights")
        raise
