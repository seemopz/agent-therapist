---
name: sleepless
description: Run a sustained Codex work session through a user-selected task list or end condition when the user asks for a long autonomous shift.
---

# sleepless for Codex

Run a sustained work session in the user's language. At the start, agree on the task sources and end condition (task list, duration, time, or user stop), unless already specified. Inspect the repository, existing changes, test commands, and available tools. Record a plan and decisions in `SLEEPLESS-REPORT.md` in English. Never overwrite an existing report without inspecting it first.

Work through the chosen tasks, test each meaningful change, fix failures, and update the report with results, decisions, and blockers. Continue to the next task while the session remains active and the end condition is unmet. At the end, summarize completed and outstanding work and validation. Create a branch, commit, push, or open a pull request only when authorized by the user and the active environment; never merge automatically. Preserve unrelated changes.

Claude's sleepless hooks and `.claude/sleepless` state are not active in this Codex workflow. This skill alone cannot enforce command restrictions, keep a turn alive, restart a session, or wake it after a rate limit. Explain these limits before starting and do not promise unattended continuation. If the session stops, the user can resume by asking Codex to continue and pointing it to the report. Respect the user's stop request immediately.
