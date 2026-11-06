# agent-therapist

This repository contains Claude Code skills and hooks under `skills/`, and separate Codex skills under `codex/skills/`.

## Commands
- Tests: `uv run pytest` (single test: `uv run pytest tests/test_scan.py -k <name>`).
- Agent workflow evaluations: follow `tests/scenarios.md`; these require real agent sessions and are separate from pytest.

## Pitfalls
- The user's installed Claude skills may be symlinks into `skills/`; edits can affect live sessions, including sleepless hooks.
- Runtime scripts and hooks support Python 3.9 and use only the standard library. Tests may use the declared development dependencies.
- Tests and examples use generic placeholders, never private repository names or real secrets.
- Changing a check in `skills/agent-therapist/references/checklist.md` requires raising its `<!-- check: id/rev -->` revision; new checks get new IDs.
- Preserve the separation between Claude settings/hooks and Codex configuration. Instruction files alone do not enforce permissions or continuation.
- Put new outstanding tasks in `TODO.md`.
