# agent-therapist

A Claude Code plugin with two skills:

| Skill | What it does |
|---|---|
| [**agent-therapist**](#agent-therapist-1) | builds or tidies up your Claude Code setup: `CLAUDE.md` files, `~/.claude/rules/`, hooks and permissions |
| [**sleepless**](#sleepless) | runs a long autonomous work shift in any git repo and ends it with a pull request |

Made for people who want Claude Code to work well without knowing every detail of it.

## Install

Requirements: Claude Code, `python3` (3.9 or newer, standard library only), `git`.
`gh` is optional for agent-therapist (used read-only to detect branch protection and pull requests)
and required with write access for sleepless (it opens the shift's pull request).

```bash
git clone <repo-url> ~/repos/agent-therapist
ln -s ~/repos/agent-therapist/skills/agent-therapist ~/.claude/skills/agent-therapist
ln -s ~/repos/agent-therapist/skills/sleepless ~/.claude/skills/sleepless
```

Symlink only the skills you want. `skills/sleepless` has its own `.claude-plugin/plugin.json`, so
its symlink loads it as plugin `sleepless@skills-dir` including its hooks.

Or load the whole plugin for one session:

```bash
claude --plugin-dir ~/repos/agent-therapist
```

Use either the symlinks or the plugin, not both – otherwise every sleepless hook runs twice.

## agent-therapist

Looks first, asks only what it can't detect, shows a preview of every change, and backs up before
it writes anything.

### Use

In any Claude Code session:

```
/agent-therapist
```

or in plain words, e.g. "clean up my CLAUDE.md setup". The skill asks two questions:
**What?** (Update / Optimize / Build new / Undo) and **Where?** (Global / Project / Both).

### What it does

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

### Safety

- Nothing is written without a preview and your OK.
- Backups go to `~/.claude/backups/agent-therapist/<date>/`; "Undo last change" restores them.
- Which checks ran on which level is kept in `~/.claude/agent-therapist/state.json`, so "Update" knows what is new.
- Lines may be deleted (with a reason); files are never deleted, only suggested.
- `settings.json` is only added to, then validated. New hooks are tried once.
- Secrets found are shown masked and never copied into new files.
- No commits – you get a suggested commit message.
- Other repos are only read, never changed.

## sleepless

Claude works through a task list and then quality work on branch `sleepless/<date>`, commits and
pushes after every step, and ends with `SLEEPLESS-REPORT.md` and a pull request – never a merge.

### Use

In the repo you want worked on:

```
/sleepless
```

or in plain words, e.g. "work through the night". One round of at most four questions sets the
end of the shift (when you say stop, at a time, after N hours, or when the list is done) and the
task sources (a list in your prompt, `TODO.md`, GitHub issues, or tasks Claude proposes from the
repo). After that Claude decides on its own and writes every decision with its reason into the
report.

| You type | Effect |
|---|---|
| `stop` | Claude wraps up: commit, push, final report, pull request |
| `weiter` or `resume shift` | resumes a shift that paused because nothing changed |

### Hooks

Hooks do the parts that must not depend on Claude:

| Hook | Does |
|---|---|
| Stop | keeps the turn going; pauses when more than 6 stop attempts in a row bring no repo change (`SLEEPLESS_IDLE_LIMIT`, clamped to 1-6) |
| UserPromptSubmit | `stop` ends the shift, `weiter` or `resume shift` resumes a paused one |
| SessionStart | wakes a restarted session and continues the shift |
| StopFailure | tries to wake the shift 15 minutes after a rate limit, overload or server error (best effort: Claude Code documents StopFailure as notification-only; not verified in a real session) |
| PreToolUse | blocks force push, push to main/master, deleting remote branches, merging, deleting outside the repo, sending messages |

Without an active shift the hooks do nothing. State lives in `.claude/sleepless/` (git-excluded).

### Good to know

- Keeping the machine awake is up to you.
- There is no cost limit; a shift runs until its end condition.
- A second session in the same checkout is ignored by the hooks while the shift session is alive
  (heartbeat younger than 10 minutes). Use a separate worktree for parallel work.
- Allowed without asking during a shift: pushing the shift branch, opening the pull request,
  deploys as documented in the repo.

## Layout

```
.claude-plugin/plugin.json       plugin metadata
hooks/hooks.json                 sleepless hooks for the plugin install
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
skills/sleepless/
  .claude-plugin/plugin.json     makes the skill folder a plugin (hooks load via symlink)
  SKILL.md                       the shift flow
  hooks/hooks.json, hook.py      hook registration and entry point
  hooks/guard.py                 commands blocked during a shift
  scripts/shift.py               shift state and CLI
  templates/SLEEPLESS-REPORT.md  report skeleton
tests/                           pytest + scenario tests
docs/                            designs, plans, German version of the guide
```

## Development

```bash
uv run pytest
```

Scenario tests run agent-therapist on copies of real repos in a temp folder, never on the originals:

```bash
tests/sandbox.sh
```

Then follow `tests/scenarios.md`. For test runs, `AGENT_THERAPIST_HOME` and `AGENT_THERAPIST_REPOS`
redirect the global folder and the repo collection into the sandbox.

To try sleepless end to end, start a shift in a scratch repo with
`python3 ~/repos/agent-therapist/skills/sleepless/scripts/shift.py start …`, then run
`claude -p "…" --plugin-dir ~/repos/agent-therapist` there.

Releases come from release-please: Conventional Commits on `main` open a release PR that
bumps the version in `pyproject.toml` and `.claude-plugin/plugin.json` and writes `CHANGELOG.md`.
Never edit these versions by hand.

## Roadmap

1. ✅ agent-therapist: Build new + Optimize + Undo
2. ✅ sleepless: autonomous work shifts with hooks
3. agent-therapist: learn from past sessions – find corrections you keep typing and turn them into rules
4. agent-therapist: GitHub steps – protect `main`, set up release-please (only with admin rights, each step confirmed)
5. sleepless: verify the StopFailure retry in a real rate-limited shift

## Background

The writing guide is based on the Claude Code docs ("How Claude remembers your project",
"Best practices") and the sources listed in `references/guide.md`. The sleepless hooks are based on
the Claude Code hooks and plugins docs; design and spike results are in
`docs/superpowers/specs/2026-09-25-sleepless-design.md`.
