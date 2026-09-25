"""Deny rules for tool calls during a sleepless shift.

A best-effort guard against mistakes, not a sandbox. Standard library only, Python 3.9.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
from typing import List, Optional

PROTECTED = ("main", "master")
SEPARATORS = {";", ";;", "&&", "||", "|", "|&", "&", "(", ")"}
PREFIXES = {"sudo", "command", "env", "exec", "nohup", "time", "{", "!"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
MCP_DANGER_WORDS = {"send", "post", "reply", "message", "messages", "comment", "comments", "draft", "drafts", "email", "emails", "mail"}
WORD_SPLIT = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")
GH_MESSAGES = {("pr", "comment"), ("pr", "review"), ("issue", "comment"), ("issue", "create")}
GH_GLOBAL_OPTS_WITH_VALUE = {"-R", "--repo"}
MAILERS = {"mail", "mailx", "sendmail", "mutt"}
WEBHOOKS = ("hooks.slack.com", "discord.com/api/webhooks")
PUSH_OPTS_WITH_VALUE = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}

FORCE = "force push is blocked during a sleepless shift"
PROTECTED_MSG = ("pushing to main/master is blocked during a sleepless shift; "
                 "push the shift branch instead")
ALL = "pushing all branches is blocked during a sleepless shift"
DELETE = "deleting remote branches is blocked during a sleepless shift"
OUTSIDE = "deleting outside the repo (%s) is blocked during a sleepless shift"
UNRESOLVED = "cannot resolve the path %r to check that it is inside the repo; use a literal path"
MESSAGE = ("sending messages is blocked during a sleepless shift; "
           "note it in SLEEPLESS-REPORT.md instead")


def segments(command: str) -> List[List[str]]:
    """Split a shell command into simple commands (lists of words)."""
    lex = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        tokens = list(lex)
    except ValueError:
        tokens = command.split()
    out, cur = [], []  # type: List[List[str]], List[str]
    for t in tokens:
        if t in SEPARATORS:
            if cur:
                out.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        out.append(cur)
    return out


def _command_words(seg: List[str]) -> List[str]:
    i = 0
    while i < len(seg) and (seg[i] in PREFIXES or ASSIGNMENT.match(seg[i])):
        i += 1
    return seg[i:]


def _resolve(cwd: str, path: str) -> Optional[str]:
    if "$" in path or "`" in path or (path.startswith("~") and path != "~" and not path.startswith("~/")):
        return None
    return os.path.realpath(os.path.join(cwd, os.path.expanduser(path)))


def _inside(target: str, root: str, allow_root: bool) -> bool:
    root = os.path.realpath(root)
    if target == root:
        return allow_root
    return target.startswith(root.rstrip(os.sep) + os.sep)


def _current_branch(cwd: str) -> str:
    try:
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
                           capture_output=True, text=True)
    except OSError:
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _check_git(words: List[str], cwd: str) -> Optional[str]:
    if os.path.basename(words[0]) != "git":
        return None
    i, gcwd = 1, cwd
    while i < len(words) and words[i].startswith("-"):
        if words[i] == "-C" and i + 1 < len(words):
            gcwd = _resolve(gcwd, words[i + 1]) or gcwd
            i += 2
        elif words[i] in ("-c", "--git-dir", "--work-tree", "--namespace"):
            i += 2
        else:
            i += 1
    if i >= len(words) or words[i] != "push":
        return None
    opts, positional = [], []  # type: List[str], List[str]
    args = words[i + 1:]
    j = 0
    while j < len(args):
        if args[j] in PUSH_OPTS_WITH_VALUE:
            j += 2
            continue
        (opts if args[j].startswith("-") else positional).append(args[j])
        j += 1
    refspecs = positional[1:]
    short = "".join(o[1:] for o in opts if not o.startswith("--"))
    if ("f" in short or "--force" in opts
            or any(o.startswith(("--force-with-lease", "--force-if-includes")) for o in opts)
            or any(r.startswith("+") for r in refspecs)):
        return FORCE
    if "d" in short or "--delete" in opts or any(r.startswith(":") for r in refspecs):
        return DELETE
    if "--all" in opts or "--mirror" in opts or "--branches" in opts:
        return ALL
    for ref in refspecs or ["HEAD"]:
        dst = ref.split(":", 1)[-1]
        if dst == "HEAD":
            dst = _current_branch(gcwd)
        if dst.startswith("refs/heads/"):
            dst = dst[len("refs/heads/"):]
        if dst in PROTECTED:
            return PROTECTED_MSG
    return None


def _check_delete(words: List[str], cwd: str, root: str) -> Optional[str]:
    name = os.path.basename(words[0])
    paths = []  # type: List[str]
    if name in ("rm", "rmdir", "unlink"):
        allow_root, opts_done, skip = False, False, False
        for i, w in enumerate(words[1:], 1):
            if skip:
                skip = False
            elif w.startswith((">", "<")):
                skip = True
            elif not opts_done and w == "--":
                opts_done = True
            elif not opts_done and w.startswith("-"):
                continue
            elif w.isdigit() and i + 1 < len(words) and words[i + 1].startswith((">" , "<")):
                continue
            else:
                paths.append(w)
    elif name == "find" and "-delete" in words:
        allow_root = True
        for w in words[1:]:
            if w.startswith("-") or w in ("!", "("):
                break
            paths.append(w)
        paths = paths or ["."]
    else:
        return None
    for p in paths:
        target = _resolve(cwd, p)
        if target is None:
            return UNRESOLVED % p
        if not _inside(target, root, allow_root):
            return OUTSIDE % p
    return None


def _check_message(words: List[str]) -> Optional[str]:
    name = os.path.basename(words[0])
    if name == "gh":
        i = 1
        while i < len(words):
            w = words[i]
            if w in GH_GLOBAL_OPTS_WITH_VALUE and i + 1 < len(words):
                i += 2
            elif w.startswith("--repo="):
                i += 1
            elif w.startswith("-") and not w.startswith("--"):
                i += 1
            else:
                break
        if i + 1 < len(words) and (words[i], words[i + 1]) in GH_MESSAGES:
            return MESSAGE
    if name in MAILERS:
        return MESSAGE
    if name in ("curl", "wget") and any(h in w for w in words for h in WEBHOOKS):
        return MESSAGE
    return None


def check_bash(command: str, cwd: str, root: str) -> Optional[str]:
    for seg in segments(command):
        words = _command_words(seg)
        if not words:
            continue
        if words[0] == "cd":
            if len(words) > 1:
                cwd = _resolve(cwd, words[1]) or cwd
            continue
        reason = _check_git(words, cwd) or _check_delete(words, cwd, root) or _check_message(words)
        if reason:
            return reason
    return None


def check(tool_name: str, tool_input: dict, cwd: str, root: str) -> Optional[str]:
    """A deny reason for this tool call, or None to let it through."""
    if tool_name == "Bash":
        return check_bash(str(tool_input.get("command", "")), str(cwd), str(root))
    if tool_name.startswith("mcp__"):
        last_segment = tool_name.rsplit("__", 1)[-1]
        words = [m.group(0).lower() for m in WORD_SPLIT.finditer(last_segment)]
        if any(w in MCP_DANGER_WORDS for w in words):
            return MESSAGE
    return None
