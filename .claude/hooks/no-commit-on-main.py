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
