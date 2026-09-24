# Hook templates

Read this only when a rule is sorted into "Hook" (step 4) or when question 24–26 or 28 is asked.

**Rules advise, hooks enforce.** Propose a hook only for rules that must never be broken.
Everything else stays a line in CLAUDE.md.

## How to install a template

1. Copy the template into `<project>/.claude/hooks/<name>.py` (global: `<global>/hooks/<name>.py`).
2. Replace the single config line at the top (`PROTECTED`, `BRANCHES`, `FORMATTERS`, `TEST_CMD`) with the user's values.
3. Merge the settings snippet into `settings.json` – add, never replace existing hooks.
4. Validate: `python3 -m json.tool <settings.json> > /dev/null`.
5. Try the hook once with a sample payload (shown under each template) and show the user the result.

Hooks use `python3` from the standard library only, so they work with the macOS system Python.
Exit code 2 blocks the action; stderr is shown to Claude.

## protect-files – never edit these files (question 26)

<!-- hook: protect-files -->
```python
#!/usr/bin/env python3
"""Block edits to protected files. Exit 2 = blocked."""
import fnmatch, json, os, sys

PROTECTED = [".env", ".env.*", "*.pem", "*.key"]

data = json.load(sys.stdin)
path = data.get("tool_input", {}).get("file_path", "")
root = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd", "")
rel = os.path.relpath(path, root) if root and os.path.isabs(path) else path
name = os.path.basename(rel)
for pattern in PROTECTED:
    if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(name, pattern):
        print(f"{rel} is protected ({pattern}). Ask the user to change it by hand.", file=sys.stderr)
        sys.exit(2)
sys.exit(0)
```

```json
{"hooks": {"PreToolUse": [{"matcher": "Edit|Write|MultiEdit", "hooks": [
  {"type": "command", "command": "[ ! -f \"$CLAUDE_PROJECT_DIR/.claude/hooks/protect-files.py\" ] || python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/protect-files.py\""}]}]}}
```

The `[ ! -f … ] ||` guard means a missing script is silently skipped instead of blocking every tool call
with exit 2. Global install: put the script under `<global>/hooks/protect-files.py` and replace
`$CLAUDE_PROJECT_DIR/.claude/hooks` with `$HOME/.claude/hooks` (or your resolved global dir, e.g.
`$AGENT_THERAPIST_HOME/hooks`) in both the guard and the command, in the global `settings.json`.

Try: `echo '{"tool_input":{"file_path":".env"}}' | python3 .claude/hooks/protect-files.py; echo $?` → `2`

## no-commit-on-main – only with "Branch + PR" (question 28)

<!-- hook: no-commit-on-main -->
```python
#!/usr/bin/env python3
"""Block `git commit` on protected branches. Exit 2 = blocked."""
import json, os, re, shlex, subprocess, sys

BRANCHES = ["main", "master"]

data = json.load(sys.stdin)
cmd = data.get("tool_input", {}).get("command", "")
payload_cwd = data.get("cwd") or None


def branch_of(path):
    r = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=path,
                       capture_output=True, text=True)
    return r.stdout.strip()


for segment in re.split(r"&&|\|\||;|\||\n", cmd):
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()
    if not tokens or tokens[0] != "git":
        continue
    i, c_path = 1, None
    while i < len(tokens):
        tok = tokens[i]
        if tok == "-C":
            i += 1
            c_path = tokens[i] if i < len(tokens) else None
            i += 1
        elif tok == "-c":
            i += 2
        elif tok.startswith("-"):
            i += 1
        else:
            break
    if i >= len(tokens) or tokens[i] != "commit":
        continue
    cwd = c_path
    if cwd and not os.path.isabs(cwd):
        cwd = os.path.join(payload_cwd or "", cwd)
    branch = branch_of(cwd or payload_cwd)
    if branch in BRANCHES:
        print(f"No commits on {branch}. Create a branch first: git switch -c <type>/<topic>", file=sys.stderr)
        sys.exit(2)
sys.exit(0)
```

```json
{"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
  {"type": "command", "command": "[ ! -f \"$CLAUDE_PROJECT_DIR/.claude/hooks/no-commit-on-main.py\" ] || python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/no-commit-on-main.py\""}]}]}}
```

Global install: same substitution as above (`$HOME/.claude/hooks` or the resolved global dir) in both
the guard and the command, in the global `settings.json`.

Try: `echo '{"tool_input":{"command":"git commit -m x"}}' | python3 .claude/hooks/no-commit-on-main.py; echo $?` → `2` on main.

## format-after-edit – only if a formatter was found (question 25)

Known formatters (use only what the project already has):
`.py` → `["ruff", "format"]` (if `ruff` in pyproject) · `.js/.ts/.tsx/.css/.md` → `["npx", "prettier", "--write"]`
(if prettier in package.json) · `.swift` → `["swiftformat"]` · `.go` → `["gofmt", "-w"]` · `.rs` → `["rustfmt"]`

<!-- hook: format-after-edit -->
```python
#!/usr/bin/env python3
"""Run the project's formatter on the edited file. Never blocks."""
import json, os, subprocess, sys

FORMATTERS = {".py": ["ruff", "format"]}

data = json.load(sys.stdin)
path = data.get("tool_input", {}).get("file_path", "")
cmd = FORMATTERS.get(os.path.splitext(path)[1])
if cmd and os.path.isfile(path):
    try:
        subprocess.run(cmd + [path], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"formatter skipped: {e}", file=sys.stderr)
sys.exit(0)
```

```json
{"hooks": {"PostToolUse": [{"matcher": "Edit|Write|MultiEdit", "hooks": [
  {"type": "command", "command": "[ ! -f \"$CLAUDE_PROJECT_DIR/.claude/hooks/format-after-edit.py\" ] || python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/format-after-edit.py\""}]}]}}
```

Global install: same substitution as above (`$HOME/.claude/hooks` or the resolved global dir) in both
the guard and the command, in the global `settings.json`.

## done-check – tests must pass before Claude says "done" (question 24)

Only if the user chose "check by hook". Set `TEST_CMD` to the exact test command line from question 18,
as one string – it runs through the shell, so `a && b` and globs like `tests/*.test.js` work.
The hook remembers the repo state (inside `.git/`, never committed) after a green run and skips the
tests while nothing changes, so pure questions cost nothing. Measure the test run once
(`time <TEST_CMD>`); if it takes longer than 10 s, say so and recommend against this hook.

<!-- hook: done-check -->
```python
#!/usr/bin/env python3
"""Stop hook: run the tests; if they fail, send Claude back to work. Exit 2 = not done.
Skips the run when the repo is unchanged since the last passing run (e.g. a pure question)."""
import hashlib, json, os, subprocess, sys

TEST_CMD = "npm test"  # one shell command line; && and globs work

data = json.load(sys.stdin)
if data.get("stop_hook_active"):
    sys.exit(0)  # already continued once because of this hook; avoid loops
root = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or None


def git(*args):
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


stamp = git("rev-parse", "--git-path", "agent-therapist-done-check")
if stamp is not None:
    stamp = os.path.join(root or ".", stamp.strip())
    state = "\0".join(x or "" for x in (TEST_CMD, git("rev-parse", "HEAD"),
                                          git("status", "--porcelain", "--untracked-files=all"),
                                          git("diff", "HEAD")))
    fingerprint = hashlib.sha256(state.encode()).hexdigest()
    try:
        if open(stamp).read() == fingerprint:
            sys.exit(0)  # nothing changed since the last green run
    except OSError:
        pass

r = subprocess.run(TEST_CMD, shell=True, cwd=root, capture_output=True, text=True)
if r.returncode in (126, 127):
    print(f"Test command not runnable ({TEST_CMD}): {r.stderr.strip()}. "
          f"Fix TEST_CMD in .claude/hooks/done-check.py.", file=sys.stderr)
    sys.exit(2)
if r.returncode != 0:
    tail = "\n".join((r.stdout + r.stderr).splitlines()[-30:])
    print(f"Tests fail ({TEST_CMD}). Fix them before finishing:\n{tail}", file=sys.stderr)
    sys.exit(2)
if stamp is not None:
    try:
        with open(stamp, "w") as f:
            f.write(fingerprint)
    except OSError:
        pass
sys.exit(0)
```

```json
{"hooks": {"Stop": [{"hooks": [
  {"type": "command", "command": "[ ! -f \"$CLAUDE_PROJECT_DIR/.claude/hooks/done-check.py\" ] || python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/done-check.py\"", "timeout": 300}]}]}}
```

`done-check` is project-only – it runs a project's test command via `$CLAUDE_PROJECT_DIR`, so there is
no global-path variant to install.

Try: `echo '{"stop_hook_active":false}' | python3 .claude/hooks/done-check.py; echo $?` → `0` when tests pass.
