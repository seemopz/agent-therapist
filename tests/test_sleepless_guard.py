from __future__ import annotations

import subprocess

import pytest

import guard

DENY = [
    ("git push --force origin sleepless/x", "force"),
    ("git push -f", "force"),
    ("git push -fu origin x", "force"),
    ("git push --force-with-lease origin x", "force"),
    ("git push origin +sleepless/x", "force"),
    ("git push origin main", "main/master"),
    ("git push origin HEAD:master", "main/master"),
    ("git push origin x:refs/heads/main", "main/master"),
    ("git push", "main/master"),
    ("git push origin", "main/master"),
    ("cd sub && git -C .. push origin main", "main/master"),
    ("git push --all", "all branches"),
    ("git push --mirror origin", "all branches"),
    ("git push origin --delete old", "deleting remote"),
    ("git push origin :old", "deleting remote"),
    ("rm -rf /tmp/x", "outside the repo"),
    ("rm -rf ~/x", "outside the repo"),
    ("rm -rf ../other", "outside the repo"),
    ("rm -rf .", "outside the repo"),
    ("FOO=1 sudo rm /etc/hosts", "outside the repo"),
    ("echo hi; rm -r /var/x", "outside the repo"),
    ("find / -name x -delete", "outside the repo"),
    ("rm -rf $HOME/x", "cannot resolve"),
    ("rm -rf $(pwd)/x", "cannot resolve"),
    ("rm -rf `pwd`/x", "cannot resolve"),
    ("rm -rf ~other/x", "cannot resolve"),
    ("rm /42", "outside the repo"),
    ("gh pr comment 3 --body hi", "sending messages"),
    ("gh pr review 3 --approve", "sending messages"),
    ("gh issue comment 4 --body hi", "sending messages"),
    ("gh issue create --title t", "sending messages"),
    ("gh -R owner/repo pr comment 5 --body hi", "sending messages"),
    ("gh --repo owner/repo issue create --title t", "sending messages"),
    ("mail -s hi someone@example.com", "sending messages"),
    ("curl -X POST https://hooks.slack.com/services/T/B/X -d x", "sending messages"),
]

ALLOW = [
    "git status",
    "git push -u origin sleepless/2026-09-25",
    "git push origin HEAD:sleepless/2026-09-25",
    "rm -rf build dist",
    "rm -f 'a file.txt'",
    "rm x > /tmp/log 2>&1",
    "rm x 2>&1",
    "find . -name '*.pyc' -delete",
    "gh pr create --base main --body-file SLEEPLESS-REPORT.md",
    "gh pr edit 3 --body-file SLEEPLESS-REPORT.md",
    "gh -R owner/repo pr create --base main",
    'git commit -m "fix: stop; push to main later"',
    "python3 -m pytest",
    "curl https://example.com",
]


@pytest.mark.parametrize("command,reason", DENY)
def test_bash_denied(git_repo, command, reason):
    result = guard.check("Bash", {"command": command}, str(git_repo), str(git_repo))
    assert result is not None and reason in result


@pytest.mark.parametrize("command", ALLOW)
def test_bash_allowed(git_repo, command):
    assert guard.check("Bash", {"command": command}, str(git_repo), str(git_repo)) is None


def test_bare_push_allowed_on_shift_branch(git_repo):
    subprocess.run(["git", "-C", str(git_repo), "switch", "-qc", "sleepless/2026-09-25"], check=True)
    assert guard.check("Bash", {"command": "git push"}, str(git_repo), str(git_repo)) is None


def test_rm_relative_to_cwd_in_subdir(git_repo):
    sub = git_repo / "sub"
    sub.mkdir()
    assert guard.check("Bash", {"command": "rm -rf ../README.md"}, str(sub), str(git_repo)) is None
    assert "outside" in guard.check("Bash", {"command": "rm -rf ../../x"}, str(sub), str(git_repo))


@pytest.mark.parametrize("tool,denied", [
    ("mcp__chat__send_message", True),
    ("mcp__mail__create_draft", True),
    ("mcp__tracker__add_comment", True),
    ("mcp__x__sendMessage", True),
    ("mcp__x__post-message", True),
    ("mcp__postgres__query", False),
    ("mcp__github__create_pull_request", False),
    ("mcp__x__postprocess", False),
    ("mcp__x__commentary_stats", False),
    ("mcp__x__repost_metrics", False),
    ("PushNotification", False),
    ("Read", False),
])
def test_mcp_and_other_tools(git_repo, tool, denied):
    result = guard.check(tool, {}, str(git_repo), str(git_repo))
    assert (result is not None) == denied


def test_segments_split_on_operators_but_not_inside_quotes():
    assert guard.segments('a "x; y" && b | c; d\ne') == [["a", "x; y"], ["b"], ["c"], ["d"], ["e"]]


def test_gh_with_global_options_denied(git_repo):
    """gh global options (-R, --repo) should be skipped before checking subcommand."""
    assert "sending" in guard.check("Bash", {"command": "gh -R owner/repo pr comment 5 --body hi"}, str(git_repo), str(git_repo))
    assert "sending" in guard.check("Bash", {"command": "gh --repo owner/repo issue create --title t"}, str(git_repo), str(git_repo))


def test_rm_with_fd_prefix_allowed(git_repo):
    """Numeric arguments are only safe if they're file descriptor prefixes (followed by redirect)."""
    # rm x 2>&1 should be allowed (2 is file descriptor redirect)
    assert guard.check("Bash", {"command": "rm x 2>&1"}, str(git_repo), str(git_repo)) is None
    # rm x > /tmp/log 2>&1 should be allowed
    assert guard.check("Bash", {"command": "rm x > /tmp/log 2>&1"}, str(git_repo), str(git_repo)) is None
    # rm /42 should be denied (42 is a path, not a file descriptor)
    assert "outside" in guard.check("Bash", {"command": "rm /42"}, str(git_repo), str(git_repo))
