# Sleepless architecture

Claude's sleepless workflow runs on a dedicated branch, records decisions in
`SLEEPLESS-REPORT.md`, and ends with a pull request. It never merges automatically.
The Codex version is instruction-only; it has no Claude hooks or automatic recovery.

## Entry points

- `skills/sleepless/SKILL.md`: task selection, work loop, and wrap-up instructions.
- `scripts/shift.py`: start, status, end, finish, deadlines, and persisted state.
- `hooks/hook.py`: Stop, UserPromptSubmit, SessionStart, StopFailure, and PreToolUse.
- `hooks/guard.py`: best-effort command checks during a shift; this is not a sandbox.

Paths above are relative to `skills/sleepless/`.

## Installation

Use either the root plugin or the symlinked skill directory with its own plugin
manifest. Both load the same hook implementation. Installing both runs hooks twice.
The root and skill-level `hooks.json` registrations are kept equivalent by tests.

## State and ownership

State lives in `<git-root>/.claude/sleepless/`, excluded through Git's info/exclude.
`state.json` is replaced atomically; a heartbeat identifies recent owner activity.
Other sessions are ignored while the owner's heartbeat is fresh. Ordinary prompts
must not claim a shift. Explicit resume may take over a paused shift.

The idle fingerprint includes HEAD, tracked diffs, and untracked file contents.
Repeated edits count as progress. Stop attempts without progress eventually pause
instead of continuing indefinitely. An unsaved existing report blocks a new shift
before branch or state changes; committed reports remain recoverable through Git.

## Recovery and limits

SessionStart uses `asyncRewake`; exit code 2 asks Claude Code to wake the agent.
StopFailure waits before attempting the same recovery. Recovery from a real rate
limit has not been verified and remains best effort. Machine sleep, client shutdown,
and the host's continuation limits can interrupt a shift. No spending cap is provided.

Historical spikes on 2026-09-25 observed SessionStart wake-up and continued Stop
blocks when tool calls occurred between them. Those observations do not establish
current end-to-end behavior. Current verification cases are in `tests/scenarios.md`.

## Validation and sources

`tests/test_sleepless_*.py` checks state, command guards, hook payloads, and packaging.
Real agent behavior requires separate runs with tool traces and file-diff evidence.

- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Claude Code hooks](https://code.claude.com/docs/en/hooks)
- [Claude Code plugins](https://code.claude.com/docs/en/plugins)
