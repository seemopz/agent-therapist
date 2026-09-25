# agent-therapist
Claude Code skill that builds or tidies up a user's Claude Code setup: CLAUDE.md files, rules, hooks, permissions.

## Commands
- Tests: `uv run pytest` (single test: `uv run pytest tests/test_scan.py -k <name>`)
- Scenario tests: `tests/sandbox.sh`, then follow `tests/scenarios.md`

## Pitfalls
- `~/.claude/skills/agent-therapist`, `~/.claude/skills/sleepless` and `~/.claude/skills/preprompt` are symlinks into `skills/` – every edit is live in real sessions, including the sleepless hooks.
- Scripts and hooks run with system `python3` 3.9: standard library only, no syntax newer than 3.9.
- Tests and examples use generic placeholders, never real private repo names.
- Changing a check in `references/checklist.md` → raise its `<!-- check: id/rev -->` revision; a new check gets a new id.

## More
- New TODOs → `TODO.md`
