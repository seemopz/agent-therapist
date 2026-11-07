---
name: sleepless
description: Run a sustained Codex work session through a user-selected task list or end condition when the user asks for a long autonomous shift.
---

# sleepless for Codex

Run a sustained work session in the user's language. At the start, agree on the task sources and end condition (task list, duration, time, or user stop), unless already specified. Inspect the repository, existing changes, test commands, and available tools. Record a plan and decisions in English in a report at `.sleepless/reports/<YYYY-MM-DD>-<label>.md`; add `.sleepless/` to `.git/info/exclude` and never commit the report. Never overwrite an existing report without inspecting it first.

Work through the chosen tasks, test each meaningful change, fix failures, and update the report with results, decisions, and blockers. Continue to the next task while the session remains active and the end condition is unmet. At the end, summarize completed and outstanding work and validation. Create branches, commit, push, or open pull requests only when authorized by the user and the active environment. When authorized, give each task its own branch `type/topic` cut from the starting branch and its own pull request against it; never merge automatically. Preserve unrelated changes.

Claude's sleepless hooks and `.claude/sleepless` state are not active in this Codex workflow. This skill alone cannot enforce command restrictions, keep a turn alive, restart a session, or wake it after a rate limit. Explain these limits before starting and do not promise unattended continuation. If the session stops, the user can resume by asking Codex to continue and pointing it to the report. Respect the user's stop request immediately.
