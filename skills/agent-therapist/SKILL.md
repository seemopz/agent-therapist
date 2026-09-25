---
name: agent-therapist
description: Use when the user wants to set up, rebuild, clean up, audit or shorten their Claude Code setup – CLAUDE.md files, ~/.claude/rules, hooks or permissions – or asks why Claude ignores their CLAUDE.md, or types /agent-therapist.
---

# agent-therapist

Builds a new Claude Code setup from a short questionnaire, or optimizes an existing one with a
fixed set of checks. Result: short, consistent files; must-rules as hooks; details in `docs/`.

Talk to the user in their language. Keep messages short. Explain terms (hook, permission) in one
line the first time, the user may not be technical.

## Paths

- `$SKILL` – this skill's directory.
- `$G` – global dir: `${AGENT_THERAPIST_HOME:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}`. Resolve once with Bash.
- `$P` – project dir: the git root of the current directory (`git rev-parse --show-toplevel`) – nothing
  else. If that fails (no git root) and scope includes Project, ask the user for the project folder;
  never fall back to the current directory or to `$HOME` as `$P`. For scope Global, `$P` is unused –
  omit it from every `tokens.py`/`scan.py` call below.
- `$REPOS` – other repos, read-only: `${AGENT_THERAPIST_REPOS:-$HOME/repos}`.
- `$BACKUP` – created in step 6 under `$G/backups/agent-therapist/`.

Bash calls don't share shell state with each other: resolve `$SKILL`, `$G` and `$P` once, then
substitute their absolute paths literally into every command below instead of writing the variable
name again. Likewise, capture the backup path printed by `backup.py save` and use it literally
wherever `$BACKUP` appears next.

## Principles

1. **Detected ≠ wanted.** Show what you found. Propose a change only with a reason; otherwise "Keep as is" is preselected.
2. **Rules advise, hooks enforce.** A hook only for rules that must never be broken.
3. **Keep it short.** Test for every line: "Would Claude make mistakes without this line?" CLAUDE.md links, `docs/` holds details. Background: `references/guide.md`.
4. **Global = default, project = deviation**, stated explicitly ("in this repo: commit directly to main").
5. **Memory files are always in English.** Every line written into a CLAUDE.md file or `rules/*.md`
   is always in English, no matter what language the chat is in – unless the user explicitly asks
   for another language. Rules about the chat language are written in English too, e.g.
   "Reply in German. Be brief, result first." Reason: fewer tokens, matches code and commands.
6. **Every question gets a recommendation** – every single one, in every step, with a one-line
   reason in its description. Single choice: exactly one option first, marked "(Recommended)".
   Multi-select: mark every recommended option "(Recommended)" and preselect all of them – usually
   several. Free text: offer a concrete draft (from the findings) as the recommended answer. No clear winner → recommend the option matching the findings or the
   safest one, and say so.

## Safety – always

- No write without a preview and the user's OK.
- Back up before writing (step 6). Offer "Undo last change" in the start menu.
- Delete lines only with a reason; never delete files – only suggest it. Exception: "Undo last change"
  with `--remove-created` deletes files, but only ones agent-therapist itself created, and only after a
  second explicit OK.
- `settings.json`: only add, then validate with `python3 -m json.tool`.
- Never copy a found secret into any file, message or preview; show it masked. Exception: backups
  under `$G/backups/agent-therapist` may contain secrets copied from the original files – expected, and
  stays local only, never shown or copied anywhere else.
- Other repos: read only. Only touch `$G` and `$P`.
- never commit. At the end suggest a commit message only.
- Out of scope: writing skills, `CLAUDE.local.md`, path-scoped rules. Mention them only if the user asks.

## Step 1 – Start

First run `python3 $SKILL/scripts/stamp.py diff --global $G --project $P` (omit `--project $P` if there
is no git root). It reports per level whether agent-therapist ran there before (`stamped`) and what is
new since: `new_checks`, `updated_checks`, `changed_files`, `added_files`, `removed_files`.

Ask **What?** (Update / Optimize / Build new / Undo last change) and **Where?** (Both (Recommended
inside a git repo, else Global) / Global / Project) in one call (question tool, clickable) – except when "What?" is already known
to be "Undo last change": Undo has no scope, so never ask "Where?" for it.
- **Update** – only if a level is stamped; then it is first and (Recommended), with what is new in the
  label, e.g. "Update (2 new checks, 1 changed file since 2026-09-25)". If nothing is new on any stamped
  level, say "up to date since <date>" instead and drop the option.
- **Optimize** – (Recommended) if files exist and Update is not offered.
- **Build new** – (Recommended) if no files exist.

If neither `$G/CLAUDE.md`, `$G/rules/` nor any CLAUDE.md or AGENTS.md in `$P` exists, skip "What?" – it is "Build new".
If the user's first message already answers these, don't ask again.

**Decide the mode per level, not once for both.** For scope Both: if `$G/CLAUDE.md` and `$G/rules/`
don't exist, the global level always runs as **Build new** (questions.md blocks 0–3, only the open
questions) even if the user picked Optimize; the project level runs as the user picked (Optimize if
`$P` has CLAUDE.md files, else Build new). Say this to the user in one line, e.g. "Global is still
empty, so I'll build it fresh; the project gets optimized." Patterns found in other repos (checklist.md
Check 2) may be used as **preselected** answers in that questionnaire that the user still confirms –
never write them straight into `$G` without going through the questionnaire.

**Undo last change:** `python3 $SKILL/scripts/backup.py restore --root $G/backups/agent-therapist --dry-run`,
show the list, ask for OK, then run it without `--dry-run`. Before overwriting anything, this itself
saves a fresh "safety backup" of the current files (printed as `safety_backup` in the JSON output) –
so the undo can be undone too. Files created by agent-therapist are listed separately; remove them only
after a second explicit OK (`--remove-created`). Then stop.

## Step 2 – Look

Collect silently, then show a short summary (5–8 lines):

- Memory files and cost (omit `$P` for scope Global): `python3 $SKILL/scripts/tokens.py --global $G $P`
- `settings.json` / `settings.local.json` in `$G` and `$P/.claude`: hooks, permissions
- Project files: `package.json`, `pyproject.toml`, `Makefile`, `Cargo.toml`, `project.yml`, README
- Git: `git log -50 --format=%s`, branches, and the detection in `references/git.md` (for block 3)

The summary ends with one line per failed command, always, in this form:
"Failed: <command> – <what it means>" (e.g. "Failed: `gh api …/protection` – 404, no branch
protection set up, so the way to main comes from the PR history"). No failures → no such line.

## Step 3 – Main part

**Build new:** read `references/questions.md` and ask the questions from `questions.md` → Question plan,
max 4 per call. Existing files stay as backup. If old files exist, first run
`python3 $SKILL/scripts/scan.py --global $G $P` (omit `$P` for scope Global), then list their rules
and ask which good ones to keep (multi-select, rules that pass the line test preselected). Never
offer or copy a line the scan flagged `secret` – drop it from the list entirely, it never gets copied
into a new file.

**AGENTS.md in `$P`:** Claude Code already reads it, and a new `$P/CLAUDE.md` would stop that
(`references/guide.md` → "AGENTS.md"). Never create `$P/CLAUDE.md` without asking first (question tool):
- **Keep AGENTS.md only** (Recommended if it covers the project): project answers go into a preview of
  `AGENTS.md` changes instead – no CLAUDE.md.
- **CLAUDE.md with `@AGENTS.md`**: first line `@AGENTS.md`, below only Claude-specific lines.

**Optimize:** read `references/checklist.md` and run checks 1–8 (deterministic part, omit `$P` for
scope Global: `python3 $SKILL/scripts/scan.py --global $G $P`). Collect findings, each with
file:line, what, proposal, reason. Do not ask per finding yet – that happens in step 5.
Then ask the questions `questions.md` → Question plan lists for "Project, Optimize" (deviations,
hooks, permissions).

**Update:** Optimize, narrowed per level with the `stamp.py diff` result from step 1:
- checks in `new_checks` + `updated_checks` → run on all files of that level;
- files in `changed_files` + `added_files` → run all checks 1–8 on just these files;
- `removed_files` → mention in the summary only.
Skip the questions for deviations, hooks and permissions unless a finding needs one. A level in scope
without a stamp runs as Optimize – say so in one line. If nothing is new on a stamped level, say
"<level>: up to date since <date>" and leave it out.

If scope Both ended up with different modes per level (see Step 1), run both procedures: Build new
for the empty level, Optimize for the other – each scoped to just that level's files.

## Step 4 – Sort

Put every rule (answer, kept rule, finding) into exactly one target, with a short reason:

| Target | For |
|---|---|
| `$G/CLAUDE.md` | how the user works: language, style, machine, tools |
| `$G/rules/token.md` | block 0 |
| `$G/rules/git.md` | git habits – template in `references/git.md` |
| `$P/CLAUDE.md` | project: one-liner, commands, deviations, pitfalls, boundaries, knowledge files |
| hook | must always / never happen – templates in `references/hooks.md` |
| permission | allow / deny – `references/permissions.md` |
| delete | fails the line test, outdated, diary |
| `docs/` | correct but too long – link it from CLAUDE.md |

Use the templates in `references/guide.md` ("Template: global", "Template: repo") for structure.

Every reason must be checkable against the files or the preview: only use the reason "deviates from the global default"
when the global files – existing, or planned within this run – actually contain that default;
otherwise say what goes wrong without the line instead (e.g. "explicit, so Claude doesn't create
branches on its own").

**Deviations from the global default** (only for the current project – never for other repos): when
`$P` works differently from a global default (e.g. commits directly to main, no release-please), ask
once per deviation with the question tool:
- **Record exception** (preselected – the repo works this way today): add "In this repo: …" to `$P/CLAUDE.md`.
- **Align repo with the default**: no exception line. Only real setup work goes into `TODO.md`
  (e.g. "Set up release-please"); a pure working-rule change such as "use branches" takes effect
  through the global rule and needs no TODO. Stage 1 only notes setup work – it does not set up
  release-please or change GitHub settings.
  When the repo is aligned to Branch + PR, offer `no-commit-on-main` (question 28) right away.

## Step 5 – Preview

Per file, show the planned result as a list:

- ✂ delete – line, reason
- → move – line, target, reason
- ✓ keep
- \+ new – line, reason

The proposed CLAUDE.md/`rules/*.md` line itself is always in English (Principle 5); the reason next
to it stays in the user's language.

Then ask: apply all (Recommended) / choose one by one / nothing. "One by one" goes through each file with
apply / skip. Nothing is written before this answer.

## Step 6 – Save

1. Backup of every file that will be written or created:
   `python3 $SKILL/scripts/backup.py save --root $G/backups/agent-therapist <files…>` → prints `$BACKUP`.
   Also save the token baseline (omit `$P` for scope Global, run before writing):
   `python3 $SKILL/scripts/tokens.py --global $G --json $P > $BACKUP/tokens-before.json`.
2. Write the files.
3. Validate every changed `settings.json`: `python3 -m json.tool <file> > /dev/null`. On error, restore that file from `$BACKUP` and tell the user.
4. Try every new hook once with its sample payload from `references/hooks.md` and show the exit code.
   For `done-check`, show how long the test run took; if it is longer than 10 s, say that every
   changed answer will wait that long and offer to remove the hook.
5. Check that every command written into a CLAUDE.md exists (`which` / script present).
6. Stamp every level that ran (Build new, Optimize or Update), so "Update" later knows what is new:
   `python3 $SKILL/scripts/stamp.py save --global $G --level global --level project --project $P`
   (pass only the levels that ran). Also do this when the user answered "nothing" in step 5 – declined
   findings then don't come back through Update, only through Optimize. The stamp lives in
   `$G/agent-therapist/state.json`; it is internal state, not a user file, so it needs no preview.

## Step 7 – Finish

Show in ≤ 10 lines:

- what changed (files, number of lines deleted / moved / new)
- tokens before → after (omit `$P` for scope Global): `python3 $SKILL/scripts/tokens.py --global $G --baseline $BACKUP/tokens-before.json $P`
- where the backup is, and that "Undo last change" in `/agent-therapist` restores it
- that "Update" in `/agent-therapist` later checks only what is new since today
- if any rule moved to or was added in global because it was found in other repos (Check 2): list
  where it still appears there (repo/file:line + a short quote), with the note "agent-therapist does not
  edit other repos; remove these with `/agent-therapist` → Optimize in that repo."
- a suggested commit message for the project repo (Conventional Commits if the repo uses them) – do not commit.
