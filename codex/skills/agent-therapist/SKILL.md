---
name: agent-therapist
description: Set up, audit, or improve Codex instructions and configuration, including AGENTS.md; use when asked to clean up a Codex setup.
---

# agent-therapist for Codex

Help the user build or improve their Codex setup. Talk in their language and explain unfamiliar terms briefly. Write instruction files in English unless asked otherwise.

Read [references/codex-setup.md](references/codex-setup.md) for the Codex-specific discovery checks, setup questions, and writing criteria. Apply these checks in both build and optimize mode. Prefer the user's explicit choices over this skill's defaults.

1. Determine whether the user wants to build, optimize, or undo, and whether the scope is global, project, or both. Ask only for missing choices. Resolve the project using `git rev-parse --show-toplevel`; if there is no git root, ask for the project directory. Never substitute the home directory.
2. Inspect the relevant `AGENTS.md` and `AGENTS.override.md` files, `config.toml`, and project documentation. Check the current official Codex documentation linked in the reference before proposing changes; configuration and supported capabilities can change. If unavailable, report which checks could not be verified and leave uncertain configuration unchanged. Consider instruction precedence and nested directories. Do not treat Claude's `CLAUDE.md` rules or its settings as Codex configuration.
3. For Build new, including rebuilding existing files, complete the selected scope's question plan in [references/codex-setup.md](references/codex-setup.md#build-new-question-plan) before proposing file contents. Existing files supply recommended answers, not permission to skip topics. Ask in small rounds and wait for answers; one autonomy question does not complete global and project setup. For Optimize, ask only about unresolved findings, then find duplication, contradictions, stale details, excessive length and possible secrets. Report secrets masked and never copy them into proposed instructions. Preserve useful existing rules. Suggest concrete changes with reasons, including applicable commands and project-specific exceptions.
4. Show the proposed changes per file and ask for approval before writing. Do not change other repositories, delete files, commit, or modify permissions or hooks without explicit approval. Treat discovered settings as observations, not user preferences.
5. Before writing, save copies of every existing target and a manifest identifying newly created files under `${CODEX_HOME:-~/.codex}/backups/agent-therapist/` in a unique timestamped directory. Protect the backup as it may contain secrets. Write the approved changes, validate changed TOML with a suitable parser and check referenced commands. If validation fails, restore the affected file from the backup and report the error.
6. Report changes, validation, and backup location. For undo, inspect a selected backup manifest, preview restoration, and obtain approval before restoring. Save the current versions first so undo is itself reversible. Remove files created by the original change only with separate explicit approval.

Do not use the Claude-specific scan, token, or stamp scripts to infer Codex instruction loading. Do not promise automatic updates or enforcement that the current Codex environment does not provide.
