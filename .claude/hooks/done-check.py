#!/usr/bin/env python3
"""Stop hook: run the tests; if they fail, send Claude back to work. Exit 2 = not done.
Skips the run when the repo is unchanged since the last passing run (e.g. a pure question)."""
import hashlib, json, os, subprocess, sys

TEST_CMD = "uv run pytest -q"  # one shell command line; && and globs work

data = json.load(sys.stdin)
root = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or None


def git(*args):
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                       encoding="utf-8", errors="surrogateescape")
    return r.stdout if r.returncode == 0 else None


stamp = git("rev-parse", "--git-path", "agent-therapist-done-check")
if stamp is not None:
    stamp = os.path.join(root or ".", stamp.strip())
    state = "\0".join(x or "" for x in (TEST_CMD, git("rev-parse", "HEAD"),
                                          git("status", "--porcelain", "--untracked-files=all"),
                                          git("diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD")))
    digest = hashlib.sha256(state.encode("utf-8", errors="surrogateescape"))
    untracked = git("ls-files", "--others", "--exclude-standard", "-z")
    if untracked is None:
        stamp = None
    else:
        try:
            for name in filter(None, untracked.split("\0")):
                content = hashlib.sha256()
                with open(os.path.join(root or ".", name), "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        content.update(chunk)
                digest.update(content.digest())
        except OSError:
            stamp = None  # unreadable files must not authorize a cached pass
    fingerprint = digest.hexdigest()
    try:
        if stamp is not None and open(stamp, encoding="utf-8").read() == fingerprint:
            sys.exit(0)  # nothing changed since the last green run
    except OSError:
        pass

r = subprocess.run(TEST_CMD, shell=True, cwd=root, capture_output=True, text=True, errors="replace")
if r.returncode in (9009, 126, 127):
    print(f"Test command not runnable ({TEST_CMD}): {r.stderr.strip()}. "
          f"Fix TEST_CMD in .claude/hooks/done-check.py.", file=sys.stderr)
    sys.exit(2)
if r.returncode != 0:
    tail = "\n".join((r.stdout + r.stderr).splitlines()[-30:])
    print(f"Tests fail ({TEST_CMD}). Fix them before finishing:\n{tail}", file=sys.stderr)
    sys.exit(2)
if stamp is not None:
    try:
        with open(stamp, "w", encoding="utf-8") as f:
            f.write(fingerprint)
    except OSError:
        pass
sys.exit(0)
