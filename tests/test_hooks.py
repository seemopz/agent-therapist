from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT, SKILL_DIR

HOOKS_MD = SKILL_DIR / "references" / "hooks.md"
BLOCK = re.compile(r"<!-- hook: (\S+) -->\s*```python\n(.*?)```", re.S)


def quote(value):
    return subprocess.list2cmdline([value]) if os.name == "nt" else shlex.quote(value)


def templates() -> dict[str, str]:
    return dict(BLOCK.findall(HOOKS_MD.read_text(encoding="utf-8")))


def install(tmp_path: Path, name: str, config_line: str | None = None) -> Path:
    code = templates()[name]
    if config_line:
        key = config_line.split("=")[0].strip()
        code, n = re.subn(rf"^{key} = .*$", lambda _: config_line, code, count=1, flags=re.M)
        assert n == 1, f"{name}: config line {key} missing"
    p = tmp_path / f"{name}.py"
    p.write_text(code, encoding="utf-8")
    return p


def run(script: Path, payload: dict, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script)], input=json.dumps(payload), text=True,
                          capture_output=True, cwd=cwd, env={**os.environ, "CLAUDE_PROJECT_DIR": str(cwd)})


def test_all_four_templates_present():
    assert set(templates()) == {"protect-files", "no-commit-on-main", "format-after-edit", "done-check"}


def _json_blocks() -> list[str]:
    return re.findall(r"```json\n(.*?)```", HOOKS_MD.read_text(encoding="utf-8"), re.S)


def _commands(node) -> list[str]:
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "command" and isinstance(v, str):
                out.append(v)
            else:
                out.extend(_commands(v))
    elif isinstance(node, list):
        for item in node:
            out.extend(_commands(item))
    return out


def test_hooks_md_json_blocks_parse_and_guard_missing_script():
    blocks = _json_blocks()
    assert blocks, "expected settings.json snippets in hooks.md"
    for raw in blocks:
        data = json.loads(raw)  # every snippet must be valid JSON on its own
        commands = _commands(data)
        assert commands, raw
        for c in commands:
            assert "[ ! -f" in c, c


def test_protect_files(tmp_path):
    s = install(tmp_path, "protect-files", 'PROTECTED = [".env", ".env.*", "migrations/**"]')
    blocked = run(s, {"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / ".env.local")}, "cwd": str(tmp_path)}, tmp_path)
    assert blocked.returncode == 2 and ".env.local" in blocked.stderr
    blocked = run(s, {"tool_name": "Edit", "tool_input": {"file_path": str(tmp_path / "migrations/001.sql")}, "cwd": str(tmp_path)}, tmp_path)
    assert blocked.returncode == 2
    ok = run(s, {"tool_name": "Edit", "tool_input": {"file_path": str(tmp_path / "src/app.py")}, "cwd": str(tmp_path)}, tmp_path)
    assert ok.returncode == 0


def test_no_commit_on_main(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    s = install(tmp_path, "no-commit-on-main")
    payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'x'"}, "cwd": str(tmp_path)}
    r = run(s, payload, tmp_path)
    assert r.returncode == 2 and "main" in r.stderr
    subprocess.run(["git", "-C", str(tmp_path), "symbolic-ref", "HEAD", "refs/heads/feat/x"], check=True)
    assert run(s, payload, tmp_path).returncode == 0
    other = {"tool_name": "Bash", "tool_input": {"command": "git status"}, "cwd": str(tmp_path)}
    assert run(s, other, tmp_path).returncode == 0


def test_no_commit_on_main_parses_git_options(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    s = install(tmp_path, "no-commit-on-main")
    for command in [
        "git -c commit.gpgsign=false commit -m x",
        "git --no-pager commit -m x",
        "cd . && git commit -m x",
    ]:
        r = run(s, {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(tmp_path)}, tmp_path)
        assert r.returncode == 2 and "main" in r.stderr, command
    for command in [
        "git commit-tree HEAD^{tree} -m x",
        'echo "reminder: git commit later"',
    ]:
        r = run(s, {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(tmp_path)}, tmp_path)
        assert r.returncode == 0, command


def test_no_commit_on_main_splits_on_newline(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    s = install(tmp_path, "no-commit-on-main")
    payload = {"tool_name": "Bash", "tool_input": {"command": "git status\ngit commit -m x"}, "cwd": str(tmp_path)}
    r = run(s, payload, tmp_path)
    assert r.returncode == 2 and "main" in r.stderr


def test_no_commit_on_main_respects_dash_c_path(tmp_path):
    main_repo = tmp_path / "main_repo"
    feature_repo = tmp_path / "feature_repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(main_repo)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(feature_repo)], check=True)
    subprocess.run(["git", "-C", str(feature_repo), "symbolic-ref", "HEAD", "refs/heads/feat/x"], check=True)
    s = install(feature_repo, "no-commit-on-main")
    payload = {"tool_name": "Bash", "tool_input": {"command": f"git -C {shlex.quote(main_repo.as_posix())} commit -m x"},
               "cwd": str(feature_repo)}
    r = run(s, payload, feature_repo)
    assert r.returncode == 2 and "main" in r.stderr


def test_format_after_edit_runs_formatter_and_never_blocks(tmp_path):
    marker = tmp_path / "formatted.txt"
    code = f"import sys; open({str(marker)!r}, 'w', encoding='utf-8').write(sys.argv[1])"
    line = "FORMATTERS = " + repr({".py": [sys.executable, "-c", code]})
    s = install(tmp_path, "format-after-edit", line)
    target = tmp_path / "a.py"
    target.write_text("x=1\n", encoding="utf-8")
    r = run(s, {"tool_name": "Write", "tool_input": {"file_path": str(target)}, "cwd": str(tmp_path)}, tmp_path)
    assert r.returncode == 0
    assert marker.read_text(encoding="utf-8") == str(target)
    r = run(s, {"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "b.md")}, "cwd": str(tmp_path)}, tmp_path)
    assert r.returncode == 0


def test_done_check(tmp_path):
    py = quote(sys.executable)
    fail_cmd = py + " -c " + quote('print("2 failed"); raise SystemExit(1)')
    failing = install(tmp_path, "done-check", f"TEST_CMD = {fail_cmd!r}")
    r = run(failing, {"stop_hook_active": False, "cwd": str(tmp_path)}, tmp_path)
    assert r.returncode == 2 and "2 failed" in r.stderr
    assert run(failing, {"stop_hook_active": True, "cwd": str(tmp_path)}, tmp_path).returncode == 2
    passing = install(tmp_path, "done-check", f"TEST_CMD = {py + ' -c pass'!r}")
    assert run(passing, {"stop_hook_active": False, "cwd": str(tmp_path)}, tmp_path).returncode == 0


def test_done_check_missing_test_command(tmp_path):
    s = install(tmp_path, "done-check", 'TEST_CMD = "definitely-not-a-command-xyz"')
    r = run(s, {"stop_hook_active": False, "cwd": str(tmp_path)}, tmp_path)
    assert r.returncode == 2
    assert "definitely-not-a-command-xyz" in r.stderr
    assert "Test command not runnable" in r.stderr or "Tests fail" in r.stderr
    assert run(s, {"stop_hook_active": True, "cwd": str(tmp_path)}, tmp_path).returncode == 2


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell glob expansion")
def test_done_check_runs_compound_commands_and_globs(tmp_path):
    py = quote(sys.executable)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "a.test.txt").write_text("x", encoding="utf-8")
    ok = install(tmp_path, "done-check", f"TEST_CMD = {'ls tests/*.test.txt && ' + py + ' -c pass'!r}")
    assert run(ok, {"stop_hook_active": False, "cwd": str(tmp_path)}, tmp_path).returncode == 0
    second_fails = install(tmp_path, "done-check", f"TEST_CMD = {py + ' -c pass && ' + py + ' -c ' + quote('raise SystemExit(1)')!r}")
    assert run(second_fails, {"stop_hook_active": False, "cwd": str(tmp_path)}, tmp_path).returncode == 2


def _git_repo(path):
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    "commit", "-q", "--allow-empty", "-m", "init"], check=True)


def test_done_check_skips_when_nothing_changed_since_last_pass(tmp_path):
    repo = tmp_path / "repo"
    _git_repo(repo)
    counter = tmp_path / "count.txt"
    cmd = quote(sys.executable) + " -c " + quote(f"open({str(counter)!r}, 'a').write('x')")
    s = install(tmp_path, "done-check", f"TEST_CMD = {cmd!r}")
    payload = {"stop_hook_active": False, "cwd": str(repo)}
    assert run(s, payload, repo).returncode == 0
    assert run(s, payload, repo).returncode == 0
    assert counter.read_text(encoding="utf-8") == "x", "second run with unchanged repo must skip the tests"
    (repo / "a.txt").write_text("changed", encoding="utf-8")
    assert run(s, payload, repo).returncode == 0
    assert counter.read_text(encoding="utf-8") == "xx", "a change must run the tests again"


def test_done_check_never_skips_after_a_failure(tmp_path):
    repo = tmp_path / "repo"
    _git_repo(repo)
    counter = tmp_path / "count.txt"
    code = f"open({str(counter)!r}, 'a').write('x'); raise SystemExit(1)"
    cmd = quote(sys.executable) + " -c " + quote(code)
    s = install(tmp_path, "done-check", f"TEST_CMD = {cmd!r}")
    payload = {"stop_hook_active": False, "cwd": str(repo)}
    assert run(s, payload, repo).returncode == 2
    assert run(s, payload, repo).returncode == 2
    assert counter.read_text(encoding="utf-8") == "xx"


def test_done_check_rechecks_changed_untracked_contents(tmp_path):
    repo = tmp_path / "repo"
    _git_repo(repo)
    source = repo / "new.txt"
    source.write_text("passing", encoding="utf-8")
    code = "from pathlib import Path; raise SystemExit(Path('new.txt').read_text() != 'passing')"
    cmd = quote(sys.executable) + " -c " + quote(code)
    script = install(tmp_path, "done-check", f"TEST_CMD = {cmd!r}")
    payload = {"cwd": str(repo)}
    assert run(script, payload, repo).returncode == 0
    source.write_text("failing", encoding="utf-8")
    assert run(script, payload, repo).returncode == 2
    assert run(script, dict(payload, stop_hook_active=True), repo).returncode == 2


def test_installed_hooks_match_templates():
    for name in ("protect-files", "no-commit-on-main", "done-check"):
        installed = (ROOT / ".claude" / "hooks" / (name + ".py")).read_text(encoding="utf-8")
        if name == "done-check":
            installed = installed.replace('TEST_CMD = "uv run pytest -q"', 'TEST_CMD = "npm test"')
        assert installed == templates()[name]


def test_done_check_blocks_even_if_test_output_is_not_text(tmp_path):
    code = "import sys; sys.stdout.buffer.write(bytes([0xff, 0x81])); raise SystemExit(1)"
    cmd = quote(sys.executable) + " -c " + quote(code)
    script = install(tmp_path, "done-check", f"TEST_CMD = {cmd!r}")
    result = run(script, {"cwd": str(tmp_path)}, tmp_path)
    assert result.returncode == 2
    assert "Tests fail" in result.stderr
