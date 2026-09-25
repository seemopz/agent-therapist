# sleepless – design

A second skill in the agent-therapist plugin. It runs a long autonomous work shift in any git
repo: Claude keeps working through a task list and then quality work until the shift ends, commits
and pushes after every step to a shift branch, and ends with a report and a pull request. Hooks
enforce the parts that must not depend on Claude's judgement.

Modelled on a project-specific "night shift" skill; nothing here is tied to one project.

## Goals

- Work continues until the user says **stop**, a deadline passes, or the task list is done –
  whichever end the user picked at the start.
- A shift survives session restarts, API errors and context compaction.
- Idle shifts pause instead of burning tokens, and tell the user.
- Destructive or outward-facing commands are blocked mechanically during a shift.
- The morning reader gets one report file that is also the PR description.

## Non-goals

- Keeping the machine awake. That is the user's job; the skill never starts `caffeinate` or similar.
- Cost limits. No token or money brake.
- Merging. The shift opens a PR and never merges it.
- Project-specific setup (VMs, simulators, progress-file formats).

## Facts from the docs and a spike (Claude Code 2.1.281, 2026-09-25)

| Fact | Source |
|---|---|
| A folder under `~/.claude/skills/` with `.claude-plugin/plugin.json` loads as plugin `<name>@skills-dir` in every session, in place (edits are live); its root `SKILL.md` stays a plain skill `/<name>` | docs: plugins/create, plugins/loading |
| Plugin hooks (`hooks/hooks.json`, `${CLAUDE_PLUGIN_ROOT}`) run whenever the plugin is enabled | docs: hooks, "Where you define a hook" |
| Skill-frontmatter hooks register only when the skill is invoked → useless after a restart | docs: hooks, "Hooks in skills and agents" |
| Stop hook: Claude Code ends the turn after 8 consecutive blocks – but only blocks with **no tool call in between** count. With real work between blocks, 19 blocks in a row went through | docs + spike |
| `asyncRewake: true`: the hook runs in the background; exit code 2 wakes Claude even when the session is idle, stderr becomes a system reminder | docs + spike (Stop hook in `-p`, SessionStart in a fresh interactive session with no input: woke after ~3 s) |
| SessionStart `additionalContext` alone never starts a turn in interactive mode | docs |

## Layout

```
skills/sleepless/
  .claude-plugin/plugin.json   name "sleepless" – makes the symlinked folder a skills-dir plugin
  SKILL.md                     the shift flow
  hooks/hooks.json             hook registration for the skills-dir plugin
  hooks/hook.py                one entry point: hook.py <event>, reads the hook JSON on stdin
  scripts/shift.py             state library + CLI (start, status, end, finish)
hooks/hooks.json               same hooks for the repo-level plugin install (--plugin-dir / marketplace)
tests/test_sleepless_*.py
```

Both `hooks.json` files point at the same `hook.py` through `${CLAUDE_PLUGIN_ROOT}`. The README
says to use exactly one install route (symlink **or** plugin); with both, every hook runs twice.

All Python is 3.9, standard library only. `hook.py` imports `shift.py` by path.

## State

`<repo>/.claude/sleepless/` – `<repo>` is the git top level of the hook's `cwd`. On `start` the
path `.claude/sleepless/` is appended to `.git/info/exclude` (once), so it never shows in
`git status` and never changes the idle fingerprint.

`state.json` (written atomically: temp file + `os.replace`):

```json
{
  "version": 1,
  "label": "short topic of the shift",
  "branch": "sleepless/2026-09-25",
  "base": "main",
  "started": "2026-09-25T22:10:00+02:00",
  "end": {"kind": "stop | time | hours | list", "at": "2026-09-26T07:00:00+02:00 or null"},
  "sources": ["prompt", "todo", "issues", "propose"],
  "status": "active | paused | ending",
  "idle": {"fingerprint": "sha1", "streak": 0},
  "last_stop": "iso timestamp"
}
```

`heartbeat` – an empty file whose mtime `hook.py` touches on every PreToolUse and Stop call. Kept
apart from `state.json` so parallel subagents never race on the JSON.

No `state.json` → every hook exits 0 immediately with no output. Normal sessions are untouched.
A corrupt `state.json` → hooks exit 0 and print a one-line `systemMessage`; they never block on
broken state.

## `shift.py` CLI

Called by Claude from the skill (`python3 "${CLAUDE_SKILL_DIR}/scripts/shift.py" …`).

| Command | Does |
|---|---|
| `start --label L --end stop\|time\|hours\|list [--at HH:MM \| --hours N] --sources a,b` | refuses if a shift is active; creates branch `sleepless/<date>` from the current HEAD (suffix `-2`, `-3` … if taken), records the current branch as `base`, writes state, adds the exclude line, creates `SLEEPLESS-REPORT.md` from the template |
| `status` | prints state as JSON plus `deadline_passed` and minutes since heartbeat |
| `end` | sets status `ending` (used when "list done" is the end condition, or the user asks to wrap up) |
| `finish` | deletes `.claude/sleepless/`; refuses unless status is `ending` |

`--at HH:MM` means the next occurrence of that local time. Times are stored with UTC offset.

## Hooks

### Stop (sync)

In order:

1. No state, status `paused` or `ending` → exit 0 (only touch heartbeat / `last_stop`).
2. `background_tasks` in the input is non-empty → exit 0. The task notification wakes Claude;
   blocking would force idle busy-work. Streak unchanged.
3. Deadline passed (`time`/`hours`) → status `ending`, block with the wrap-up instruction.
4. Idle check: fingerprint = sha1 of `git rev-parse HEAD` + `git status --porcelain`. Same as last
   → streak + 1, else streak = 1. Streak > `SLEEPLESS_IDLE_LIMIT` (default 6) → status `paused`,
   block once with: "No repo change across N stop attempts. Push the branch, send a
   PushNotification saying the shift is paused and why, then end the turn." The next stop passes
   (rule 1).
5. Otherwise block: "Shift active (<label>). Do not end the turn. Take the next item per the
   sleepless skill …" plus the streak counter.

The idle limit stays below the 8-block cap, so pure text replies reach the pause first.

### UserPromptSubmit (sync)

The prompt is normalised (trimmed, lower-case, trailing `.!` removed) and compared as a whole:

| Prompt | State | Effect |
|---|---|---|
| `stop`, `stopp`, `hör auf`, `hoer auf` | active / paused | status `ending`; `additionalContext`: wrap-up instruction |
| `weiter`, `continue`, `resume` | paused | status `active`, streak 0; `additionalContext`: "shift resumed, take the next item" |
| anything else | any | nothing |

Only whole-prompt matches count, so "don't stop" or a pasted log never ends a shift.

Wrap-up instruction (used by Stop rule 3, `stop`, and `end`): finish or park the current step,
tests, commit, push, final report update, `gh pr create --base <base> --body-file
SLEEPLESS-REPORT.md` (or update the existing PR), PushNotification, `shift.py finish`, closing
message.

### SessionStart (`asyncRewake`, matcher `startup|resume|compact`)

1. No state or status not `active` → exit 0.
2. `startup`/`resume` and heartbeat younger than 10 minutes → exit 0. Another session is probably
   still running the shift; waking this one would run two shifts in parallel.
3. Otherwise exit 2 with stderr: "A sleepless shift is active on <branch> (<label>). Invoke the
   sleepless skill, read SLEEPLESS-REPORT.md, check out the shift branch if needed, and continue
   with the next item." After `compact` this re-loads the skill text Claude lost.

### StopFailure (`asyncRewake`, timeout 1200 s)

A turn that ended on an API error (rate limit, overload) would otherwise leave the shift idle
until morning. If status is `active`: sleep `SLEEPLESS_RETRY_SECONDS` (default 900), check state
again, then exit 2 with "Resume the shift after an API error." Repeated failures repeat the cycle.
Not covered by the spike; `asyncRewake` on this event is assumed to behave as on Stop.

### PreToolUse (sync, matcher `Bash|mcp__.*`)

Active in every status while state exists. Touches heartbeat, then denies with
`permissionDecision: "deny"` and a reason:

| Rule | Detection |
|---|---|
| Force push | `git push` with `-f`, `--force`, `--force-with-lease`, `--force-if-includes`, or a refspec starting with `+` |
| Push to main/master | refspec destination `main`/`master` (`main`, `HEAD:main`, `x:refs/heads/master`), `--all`, `--mirror`, or a bare `git push` while the current branch is main/master |
| Remote branch deletion | `git push --delete` / `-d`, or refspec `:branch` |
| Deleting outside the repo | `rm`, `rmdir`, `unlink`, `find … -delete` with a path that resolves outside the repo root (relative to `cwd`), or that cannot be resolved (`$VAR`, `~user`, backticks, `$(…)`) |
| Sending messages | `gh pr comment`, `gh pr review`, `gh issue comment`, `gh issue create`; `mail`, `mailx`, `sendmail`, `mutt`; `curl`/`wget` to `hooks.slack.com` or `discord.com/api/webhooks`; MCP tools whose name contains `send`, `post`, `reply`, `message`, `comment`, `draft` or `email` |

Commands are split on `;`, `&&`, `||`, `|` and newlines, tokenised with `shlex`, and each part is
checked; `git -C <dir>` is honoured. This is a best-effort guard against mistakes, not a sandbox.

Allowed during a shift: pushing the shift branch, `gh pr create`/`gh pr edit`, deploys,
`PushNotification` (a built-in tool, not MCP).

## The skill (`SKILL.md`)

**Start check** – one `AskUserQuestion` round, at most 4 questions, detected options marked
"(detected)" and listed first:

1. End of shift: `stop` in chat / at a time / after N hours / when the list is done.
2. Task sources (multi-select): list in the prompt, `TODO.md`, GitHub issues (`gh issue list`),
   "propose tasks" (Claude derives tasks from the repo and writes them to the report first).

Then `shift.py start`, first report version, commit, push.

**Loop** – after every finished step: tests green, review by a subagent (fix or note findings),
commit (Conventional Commits), push, report update. Order: the chosen sources in the order above,
then quality work (failing or missing tests, stale docs, TODOs in code, lint). Independent tasks
may go to parallel subagents. The next item starts in the same turn.

**Decisions** – Claude decides alone and writes each decision with its reason to the report's
question list. A blocker goes on the list with what was tried; then the next item.

**Allowed without asking** – push the shift branch, open/update the PR, deploys as documented in the repo.

**Pause** – on the Stop hook's idle instruction: push, `PushNotification`, end the turn. "weiter"
resumes.

**Push notifications** – at idle pause, at shift end, and for important findings (e.g. a security
issue, broken main).

**End** – the wrap-up instruction above. Never merge.

**Red flags** table as in the template ("list is done" → quality work; "needs the user" → decide
and note; "good stopping point" → the report is the summary; a blocked stop is not an error).

## Report – `SLEEPLESS-REPORT.md`

Committed at the repo root of the shift branch and used as the PR body. Sections: Summary (label,
start/end, real duration including restarts), Done (item → commit hashes), Decisions and questions
(decision + reason, or open question), Blocked, Findings, Next. Stays in the repo after merge.

## Testing

- `tests/test_sleepless_state.py` – `shift.py` start/status/end/finish in a temp git repo: branch
  naming and suffix, exclude line written once, deadline maths, refusal cases.
- `tests/test_sleepless_hooks.py` – `hook.py` run as a subprocess with sample JSON per event:
  no-state no-op, Stop order (paused, background tasks, deadline, idle pause, normal block),
  prompt matching table, SessionStart heartbeat guard, every PreToolUse rule with allowed and
  denied examples.
- Manifest/JSON tests: both `hooks.json` parse and reference existing scripts; sleepless
  `plugin.json` valid; `SKILL.md` frontmatter present.
- Python 3.9 compatibility: `ast.parse(..., feature_version=(3, 9))` over all sleepless scripts.
- Manual, once: `claude plugin validate` on the repo and on `skills/sleepless`; a short shift in a
  scratch repo covering stop, idle pause, restart rewake. StopFailure is covered only by the unit
  test (with `SLEEPLESS_RETRY_SECONDS=0`), since an API error cannot be forced.
