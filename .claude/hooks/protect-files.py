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
