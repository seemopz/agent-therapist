# agent-therapist

A Claude Code plugin and a separate set of Codex skills with three workflows:

| Skill | What it does |
|---|---|
| [**agent-therapist**](#agent-therapist-1) | builds or tidies up your Claude Code setup: `CLAUDE.md` files, `~/.claude/rules/`, hooks and permissions |
| [**sleepless**](#sleepless) | runs a long autonomous work shift in any git repo, one session and one pull request per task |
| [**preprompt**](#preprompt) | turns a rough idea into a finished prompt for Claude, asking only what is missing |

Made for people who want Claude Code to work well without knowing every detail of it.

The Claude plugin and its hooks live in `skills/`. The Codex versions live in
`codex/skills/` and use Codex instructions and configuration instead of Claude settings.

## Install

### Codex

The current Codex documentation places user skills under `~/.agents/skills`. For example, on macOS or Linux:

```bash
mkdir -p "$HOME/.agents/skills"
ln -s ~/repos/agent-therapist/codex/skills/agent-therapist "$HOME/.agents/skills/agent-therapist"
ln -s ~/repos/agent-therapist/codex/skills/sleepless "$HOME/.agents/skills/sleepless"
ln -s ~/repos/agent-therapist/codex/skills/preprompt "$HOME/.agents/skills/preprompt"
```

On Windows, copy the three directories from `codex/skills/` into `%USERPROFILE%\.agents\skills\`;
update the copies when the repo changes. Older clients may also load `.codex/skills`; use one
installation location to avoid duplicate skills. Codex detects skill changes automatically;
restart it if a skill does not appear. See the [official skill documentation](https://learn.chatgpt.com/docs/build-skills).
Invoke them as `$agent-therapist`, `$sleepless`, and
`$preprompt`, or ask for their workflows in plain language.

Codex's agent-therapist reviews Codex instructions and configuration, with a preview and backup
before changes. A new or rebuilt setup includes a guided global/project interview in small rounds;
existing files provide suggestions to confirm. Optimize asks only about unresolved findings.
Its workflow does not use the Claude-specific scanner or update stamps. Codex's
sleepless runs a sustained session while it is active, but does not install Claude hooks: automatic
continuation, restart, rate-limit recovery, and hook-enforced command guards are not provided.
Resume an interrupted session using its report in `.sleepless/reports/`. The remaining sections describe Claude.

### Claude Code

Requirements: Claude Code, `python3` (3.9 or newer, standard library only), `git`.
`gh` is optional for agent-therapist (used read-only to detect branch protection and pull requests)
and required with write access for sleepless (it opens one pull request per task).

```bash
git clone <repo-url> ~/repos/agent-therapist
ln -s ~/repos/agent-therapist/skills/agent-therapist ~/.claude/skills/agent-therapist
ln -s ~/repos/agent-therapist/skills/sleepless ~/.claude/skills/sleepless
ln -s ~/repos/agent-therapist/skills/preprompt ~/.claude/skills/preprompt
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

Claude works through a task list and then quality work. Each task gets its own branch `type/topic`
from the branch you started on and its own pull request – merged only if you turn on merge mode
at the start. Where possible each task
runs in its own background session with its own git worktree (desktop app session tool or
`claude --bg`), up to 3 at a time; the main session coordinates and keeps a report in
`.claude/sleepless/reports/` that is never committed. At the end you get a push notification and
a closing message with the PR links.

### Use

In the repo you want worked on:

```
/sleepless
```

or in plain words, e.g. "work through the night". One round of at most four questions sets the
end of the shift (when you say stop, at a time, after N hours, or when the list is done) and the
task sources (a list in your prompt, `TODO.md`, GitHub issues, or tasks Claude proposes from the
repo), whether each task runs in its own session, and whether Claude may squash-merge its own
task PRs once CI is green and the review is done (merge mode, off by default). After that Claude decides on its own and writes every decision with its reason into the
report.

| You type | Effect |
|---|---|
| `stop` | Claude wraps up: workers finish or are parked, every task branch pushed with its PR, final report |
| `weiter` or `resume shift` | resumes a shift that paused because nothing changed |

### Hooks

Hooks do the parts that must not depend on Claude:

| Hook | Does |
|---|---|
| Stop | keeps the turn going (lets it end while `shift.py wait` runs in the background for workers); pauses when more than 6 stop attempts in a row bring no repo change (`SLEEPLESS_IDLE_LIMIT`, clamped to 1-6) |
| UserPromptSubmit | `stop` ends the shift, `weiter` or `resume shift` resumes a paused one |
| SessionStart | wakes a restarted session and continues the shift |
| StopFailure | tries to wake the shift 15 minutes after a rate limit, overload or server error (best effort: Claude Code documents StopFailure as notification-only; not verified in a real session) |
| PreToolUse | blocks force push, push to main/master, deleting remote branches, merging, `git merge` into main/master, deleting outside the repo, sending messages – also in worker sessions; records worker heartbeats. In merge mode it allows exactly `gh pr merge <task branch> --squash` for branches the shift created (no `--admin`, `--auto`, `--delete-branch`, `-R`) |

Without an active shift the hooks do nothing. In worker sessions only PreToolUse acts. State and
reports live in `.claude/sleepless/` (git-excluded); `finish` keeps only `reports/`.

### Good to know

- Keeping the machine awake is up to you.
- There is no cost limit; a shift runs until its end condition.
- A second session in the same checkout is ignored by the hooks while the shift session is alive
  (heartbeat younger than 10 minutes). Sessions in other worktrees of the repo count as workers:
  the command guard applies to them during a shift.
- Allowed without asking during a shift: pushing task branches, opening their pull requests,
  starting worker sessions (if you said yes at the start), squash-merging the shift's own PRs (merge
  mode only), deploys as documented in the repo.
- Quality work stays lean: cleanup PRs must not grow non-test code, one theme per PR, and each PR
  states its line delta. Features come only from `TODO.md`, issues or follow-up lists in the docs.
- A worker cleans up after its test runs; `shift.py done --status done` refuses while its worktree
  has stray or uncommitted files.

## preprompt

Turns a rough idea into one finished prompt for Claude.

### Use

```
/preprompt a CLI that sorts photos into folders by date
```

Claude asks only what the idea is missing (0–8 click-to-choose questions, each with a
recommended default), then shows the prompt as one code block, ready to copy. After that it asks
"Run it now?": **Yes** runs it in the same session, **Adjust** rebuilds it with your change,
**No** stops.

The rules the prompt follows – structure in XML tags, a reason for every constraint, no
all-caps, a role line only when it sets a real perspective – are in
`skills/preprompt/references/prompt-rules.md`, with links to Anthropic's docs they come from.

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
  templates/report.md            report skeleton
skills/preprompt/
  SKILL.md                       the flow (steps 1–6)
  references/prompt-rules.md     prompt skeleton, rules, checklist, sources
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

Tests run on Linux and Windows with Python 3.9 and 3.14; POSIX-only tests run on Linux.
The release workflow waits for these checks before running release-please.

Releases come from release-please: Conventional Commits on `main` open a release PR that
bumps the version in `pyproject.toml` and `.claude-plugin/plugin.json` and writes `CHANGELOG.md`.
Never edit these versions by hand.

## Roadmap

1. ✅ agent-therapist: Build new + Optimize + Undo
2. ✅ sleepless: autonomous work shifts with hooks
3. ✅ preprompt: turn a rough idea into a finished prompt
4. agent-therapist: learn from past sessions – find corrections you keep typing and turn them into rules
5. agent-therapist: GitHub steps – protect `main`, set up release-please (only with admin rights, each step confirmed)
6. sleepless: verify the StopFailure retry in a real rate-limited shift

## Background

The writing guide is based on the Claude Code docs ("How Claude remembers your project",
"Best practices") and the sources listed in `references/guide.md`. The sleepless hooks are based on
the Claude Code hooks and plugins docs; design and spike results are in
`docs/superpowers/specs/2026-09-25-sleepless-design.md`.
