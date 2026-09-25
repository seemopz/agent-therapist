# agent-therapist

A Claude Code skill that builds or tidies up your Claude Code setup: `CLAUDE.md` files,
`~/.claude/rules/`, hooks and permissions. It looks first, asks only what it can't detect,
shows a preview of every change, and backs up before it writes anything.

Made for people who want a clean setup without knowing every Claude Code detail.

## What it does

| Mode | When | Result |
|---|---|---|
| **Build new** | nothing there yet, or you want a fresh start | short questionnaire (clickable, max 4 questions at a time) → new files |
| **Update** | you ran agent-therapist here before | runs only the checks added since then, and all checks on files that changed since then |
| **Optimize** | files already exist | fixed checks → findings with a proposal and a reason each |
| **Undo last change** | you don't like the result | restores the latest backup (and backs up the current state first) |

It decides per level: if your global setup is still empty but the project has files, the global
part is built new and the project part is optimized.

### What gets checked when optimizing

1. Token cost per file, before and after, including `@path` imports (estimated, shown with ≈)
2. The same rule repeated across your repos → move it to global
3. Contradictions between global, project and subfolder files
4. Diary entries, counters, outdated notes → delete or move to `docs/`
5. Files that are too long (over 200 lines, target under 60) → split into `docs/`
6. Passwords and secrets → reported masked, never copied
7. The checklist from `references/guide.md` (e.g. at most one `IMPORTANT` line)
8. `AGENTS.md`: not loaded because a CLAUDE.md blocks it, or outdated workarounds (hook, "read AGENTS.md")

### Where things end up

| Target | For |
|---|---|
| `~/.claude/CLAUDE.md` | how you work: language, style, machine, tools |
| `~/.claude/rules/token.md`, `git.md` | token hygiene, git habits |
| `<project>/CLAUDE.md` | commands, deviations from global, pitfalls, boundaries |
| hook | rules that must never be broken (templates: protect files, no commits on main, format after edit, tests before "done") |
| permission | commands that may run without asking, or never |
| `docs/` | knowledge that is correct but too long for `CLAUDE.md` |

Memory files are always written in English (fewer tokens, matches code and commands).
The conversation stays in your language.

## Safety

- Nothing is written without a preview and your OK.
- Backups go to `~/.claude/backups/agent-therapist/<date>/`; "Undo last change" restores them.
- Which checks ran on which level is kept in `~/.claude/agent-therapist/state.json`, so "Update" knows what is new.
- Lines may be deleted (with a reason); files are never deleted, only suggested.
- `settings.json` is only added to, then validated. New hooks are tried once.
- Secrets found are shown masked and never copied into new files.
- No commits – you get a suggested commit message.
- Other repos are only read, never changed.

## Install

Requirements: Claude Code, `python3` (3.9 or newer, standard library only), `git`. `gh` is optional
(used read-only to detect branch protection and pull requests).

```bash
git clone <repo-url> ~/repos/agent-therapist
ln -s ~/repos/agent-therapist/skills/agent-therapist ~/.claude/skills/agent-therapist
```

Or load it as a plugin for one session:

```bash
claude --plugin-dir ~/repos/agent-therapist
```

## Use

In any Claude Code session:

```
/agent-therapist
```

or in plain words, e.g. "clean up my CLAUDE.md setup". The skill asks two questions:
**What?** (Optimize / Build new / Undo) and **Where?** (Global / Project / Both).

## Layout

```
.claude-plugin/plugin.json       plugin metadata
skills/agent-therapist/
  SKILL.md                       the flow (steps 1–7)
  references/                    read only when a step needs them
    guide.md                     how to write a good CLAUDE.md
    questions.md                 question catalogue
    checklist.md                 checks for "Optimize"
    git.md                       git detection and rules template
    hooks.md                     hook templates
    permissions.md               safe allow/deny lists
  scripts/
    memfiles.py                  finds memory files (incl. AGENTS.md) and when they load
    tokens.py                    token cost per file, before/after
    scan.py                      length, IMPORTANT, secrets, diary entries, AGENTS.md
    backup.py                    backup and undo
    stamp.py                     remembers which checks ran, reports what is new ("Update")
tests/                           pytest + scenario tests
docs/                            design, plan, German version of the guide
```

## Development

```bash
uv run pytest
```

Scenario tests run the skill on copies of real repos in a temp folder, never on the originals:

```bash
tests/sandbox.sh
```

Then follow `tests/scenarios.md`. For test runs, `AGENT_THERAPIST_HOME` and `AGENT_THERAPIST_REPOS`
redirect the global folder and the repo collection into the sandbox.

Releases come from release-please: Conventional Commits on `main` open a release PR that
bumps the version in `pyproject.toml` and `.claude-plugin/plugin.json` and writes `CHANGELOG.md`.
Never edit these versions by hand.

## Roadmap

1. ✅ Build new + Optimize + Undo
2. Learn from past sessions: find corrections you keep typing and turn them into rules
3. GitHub steps: protect `main`, set up release-please (only with admin rights, each step confirmed)

## Background

The writing guide is based on the Claude Code docs ("How Claude remembers your project",
"Best practices") and the sources listed in `references/guide.md`.
