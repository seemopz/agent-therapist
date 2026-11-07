# Sleepless architecture

Claude's sleepless workflow gives every task its own branch `type/topic` and its own pull request
against the shift's base branch, and records decisions in an uncommitted report at
`.claude/sleepless/reports/<date>-<label>.md`. It never merges automatically. Where available, a
coordinator session starts one worker session per task in its own worktree (desktop
`start_session` or `claude --bg`, at most 3 at a time); otherwise it switches branches itself.
The Codex version is instruction-only; it has no Claude hooks or automatic recovery.

## Entry points

- `skills/sleepless/SKILL.md`: task selection, work loop, and wrap-up instructions.
- `scripts/shift.py`: start, status, end, finish, branch, join, done, wait, workers, deadlines,
  and persisted state.
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

Workers are sessions in linked worktrees; hooks find the shift through the main checkout
(`git rev-parse --git-common-dir`). For them only PreToolUse acts: the guard applies with the
worktree as the repo root, and each call refreshes `workers/<slug>.heartbeat`. Workers record
status and PR in `workers/<slug>.json` via `join` and `done`. The coordinator's Stop hook lets the
turn end only while a background `shift.py wait` runs; `wait` returns when a worker changes
status or goes stale. `finish` keeps `reports/` and deletes the rest.

The idle fingerprint includes HEAD, all refs, tracked diffs, untracked file contents (skipping
nested worktrees), the report, and worker files.
Repeated edits count as progress. Stop attempts without progress eventually pause
instead of continuing indefinitely. `start` does not switch branches; each new report gets
a free file name, so earlier reports are never overwritten.

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
