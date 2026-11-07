---
name: sleepless
description: Use when the user starts a long autonomous work shift in a repo – overnight or while away ("sleepless", "work through the night", "keep going until I say stop", "Nachtschicht") – and whenever a sleepless hook message says a shift is active.
---

# sleepless

A shift is a long unattended work session. Every task gets its own branch `type/topic` and its own
pull request against the shift's base branch; nothing is ever merged. It ends only the way the user
chose at the start: **stop** in chat, a time, a number of hours, or the task list being done. While
`.claude/sleepless/state.json` exists, this plugin's hooks enforce the mechanics: the Stop hook
keeps the turn going, "stop" and "weiter" in chat end or resume the shift, a new session after a
restart is woken automatically, and dangerous commands are blocked. This skill says what to do with
the time.

This session is the **coordinator**: it plans, starts one **worker** session per task, collects
results and keeps the report. `$SHIFT` below stands for
`python3 "${CLAUDE_SKILL_DIR}/scripts/shift.py"`, run inside the repo.

Talk to the user in their language. Everything written to files, commits and PRs is in English.

## Start (once)

1. `python3 "${CLAUDE_SKILL_DIR}/scripts/shift.py" status`. If a shift is active, you are resuming:
   go to **After a restart**.
2. Detect what is there: a task list in the user's prompt, `TODO.md`, open issues
   (`gh issue list --limit 20`, only if `gh` works), how tests run (CLAUDE.md, README, package
   files), how deploys run, and the worker mechanism: (a) the desktop tool `start_session` is listed
   or deferred, else (b) `claude --help` shows `--bg`, else (c) none.
3. One `AskUserQuestion` round, at most 4 questions. Detected options first, marked "(detected)":
   - **End of shift**: "When I say stop" / "At a time" / "After N hours" / "When the list is done".
     The user types the time or hours via "Other"; if not, use a second question in the same round.
   - **Task sources** (multi-select): "List in my prompt" / "TODO.md" / "GitHub issues" /
     "Propose tasks" (you derive tasks from the repo and write them into the report's plan first).
   - **Run each task in its own session?** "Yes – <detected mechanism>" (Recommended when a
     mechanism exists) / "No – work in this session". Yes is the user's consent for starting worker
     sessions during the shift.
   Never ask about cost – there is no cost limit. Never ask about keeping the machine awake – that
   is the user's job; never start `caffeinate` or anything similar.
4. `python3 "${CLAUDE_SKILL_DIR}/scripts/shift.py" start --label "<short topic>" --end <stop|time|hours|list> [--at HH:MM | --hours N] --sources <prompt,todo,issues,propose>`.
   It records the current branch as base and creates the state and the report; its JSON output
   names the report path (`report`, under `.claude/sleepless/reports/`). It does not switch
   branches. The report is never committed. Run it in the main checkout – it refuses in a linked
   worktree, where workers and hooks would not find the shift.
5. Write the plan (the task list in order, dependencies marked) into the report.
6. Tell the user in 2–3 lines: base, end condition, report path, first tasks. Start them in the
   same turn.

## The loop

1. Pick up to 3 independent tasks (no shared files). A task that depends on another waits until
   that one is done; it is cut from that task's branch and its PR targets that branch.
2. For each: `$SHIFT branch <type> <topic>` prints a free branch name. Fill in the **Worker brief**
   and start the worker:
   - (a) `start_session` (load with ToolSearch `select:mcp__ccd_session__start_session` if
     deferred): initiation `"user_asked"`, context `"fresh"`, use_worktree `true`, source_branch
     `<base>`, title `<branch>`, prompt `<brief>`, background: shift goal and rules (≥80 chars).
   - (b) `claude --bg --worktree <slug> --name <slug> --permission-mode <this session's mode> "<brief>"`
     with `<slug>` = branch with `/` → `--`; write the brief to a temp file and pass `"$(cat <file>)"`.
     `claude agents --json` lists the sessions.
   - (c) No mechanism, or the user said no: do the task yourself in this checkout –
     `git switch -c <branch> <base>`, work, tests, subagent review, commit, push, PR,
     `git switch <base>`. Independent tasks may go to subagents.
3. `$SHIFT wait` with `run_in_background`, then end the turn. The harness wakes you when a worker
   finishes, goes stale (no heartbeat for 20 min), the deadline passes, or after 50 min; the JSON
   `reason` says which (`status`, `stale`, `deadline`, `shift_inactive`, `timeout`, `none_running`).
4. On wake: `$SHIFT workers`. Update the report (Done: item → branch → PR; blocked items with the
   worker's note).
5. Blocked or stale worker: check its branch (`git log <base>..<branch>`) and session log. Restart
   it once with the brief plus what already exists, or finish it yourself; otherwise
   `$SHIFT done <branch> --status blocked --note "<why>"` and put it on the question list. A stale
   worker must be restarted or marked blocked before the next wait. Before a restart, stop the old
   worker session and remove its worktree (`git worktree remove <path>`), then restart it with the
   same branch – `join` switches to the existing branch.
6. Start the next tasks, back to 3.

| Order | Source | Done means |
|---|---|---|
| 1 | the chosen sources: prompt list → `TODO.md` → issues → proposed tasks | every item has a PR or is on the question list |
| 2 | quality work | failing or missing tests, stale docs, TODO/FIXME in code, lint and type warnings, small refactors that make code clearer |

End condition "when the list is done": after row 1 and all workers are finished, run
`python3 "${CLAUDE_SKILL_DIR}/scripts/shift.py" end` and follow the wrap-up it prints. Every other
end condition: quality work runs until the shift ends.

## Worker brief

The worker has no other context. Resolve `${CLAUDE_SKILL_DIR}` to an absolute path before sending.

```
You are a worker in a sleepless shift. Nobody answers questions; decide yourself.
Task: <task>. Done when: <done criteria>.
Branch: <branch>. Base: <base>. Shift script: <absolute path>/scripts/shift.py
Steps:
1. python3 <shift.py> join <branch>   (first; dependent task: add --from <dependency branch>)
2. Do the task in this worktree only. Run the tests; red → fix.
3. Have a subagent review the diff against the task; fix real findings.
4. Commit as type(scope): what. git push -u origin <branch>
5. gh pr create --base <base> --head <branch> --title "<type>(<scope>): <what>" --body "<what, why, tests, open questions>"
6. python3 <shift.py> done <branch> --status done --pr <url>
   (stuck: --status blocked --note "<what is missing, what you tried>")
Rules: never ask the user, never merge, no force push, no messages or comments, stay in this
worktree, end your turn after `done`.
```

## Decisions and blockers

- Decide yourself. Write every decision with its reason under "Decisions and questions" in the
  report. When unsure, pick the option that is easiest to undo.
- Blocked: write the question and what you tried, switch to the next item, come back when
  something changes. Nothing waits for the user.

## Allowed without asking

Pushing task branches, opening or updating their PRs, starting worker sessions (consented at the
start), and deploys as the repo documents them (CLAUDE.md, README, scripts). Session-hygiene rules
("suggest a new session") are waived during a shift; compaction is expected and the report carries
the state.

## Blocked by the hooks

Force push, push to main/master, deleting remote branches, merging, deleting outside the repo,
sending messages (PR/issue comments, new issues, mail, chat webhooks, MCP send tools). The guard
also protects worker sessions in linked worktrees, and the user's own sessions in other worktrees of
this repo while a shift runs. A denied command is not an error: note it if it mattered and do
something else. Never work around the guard.

## Stay inside the repo

- Create files, repos and remotes only inside the repo (scratch files may go to the system temp dir).
- No global installs, no changes to `~/.claude` or other global configuration, no new GitHub repos.
- Anything the user's standing rules say to ask about first goes on the question list instead of
  being done.
- "Propose tasks" means deriving work from the existing code. Never build a new project; an empty
  repo without code or tests means: run `$SHIFT end`.
- Other sessions in the main checkout are left alone by the hooks.

## Push notifications

Send `PushNotification` (load it with ToolSearch if it is deferred) only for: the idle pause, the
end of the shift (summary and PR links), and important findings (security issue, broken main, risk
of data loss). The user is asleep.

## Pause

When the Stop hook says the shift pauses (no repo change across several stop attempts): push any
unpushed task branch, `PushNotification` with the reason, end the turn. The shift stays open
(paused); the user resumes it with "weiter" or "resume shift".

## End

On the wrap-up instruction (from "stop" in chat, a passed deadline, or `$SHIFT end`):

1. Running workers: let them finish (`$SHIFT wait` in the background) unless the deadline passed;
   otherwise park them – check their branches, stop their sessions (desktop: stop the session;
   CLI: `claude stop <id>`), then `$SHIFT done <branch> --status blocked --note "parked at shift end"`.
   `finish` refuses while a worker is still marked running.
   Park your own current step too.
2. Every task branch is pushed and has its own PR (`gh pr list --head <branch>`); open missing ones.
   Never merge.
3. Final report at its path: summary with real duration (including restarts and pauses), done
   (item → branch → PR), decisions and questions, blocked, findings, next.
4. `PushNotification` with the summary and the PR links.
5. `python3 "${CLAUDE_SKILL_DIR}/scripts/shift.py" finish`. It keeps the reports and deletes the
   rest of `.claude/sleepless/`.
6. Closing message: what was done, the PR links, open questions, the report path.

## After a restart

A hook wakes the new session with "A sleepless shift is active". Then: `$SHIFT status` (base and
report path), read the report, `$SHIFT workers`, note the restart time in the report. Running
workers → `$SHIFT wait` in the background and end the turn; otherwise continue with the loop.

## Red flags – all of these mean: take the next item

| Thought | Reality |
|---|---|
| "The list is done." | Quality work starts now (unless the end condition is "list done"). |
| "The next step needs the user." | Decide, note it with the reason, build. |
| "Good stopping point, I'll summarise." | The summary is the report. The turn goes on. |
| "The context is very long." | Compaction handles it; the report is the memory. |
| "I'm blocked." | Question list, next item. |
| "The worker can ask me." | It can't. The brief must hold everything it needs. |
| The Stop hook blocked the stop | Not an error. Read its reason and continue. |

## Common mistakes

- Ending a message with "next step needs you" while the shift is active.
- Waiting for workers in the foreground: run `$SHIFT wait` with `run_in_background` and end the turn.
- Two workers touching the same files, or a brief that still contains `${CLAUDE_SKILL_DIR}`.
- `sleep` loops to pass time: the idle guard pauses the shift; real work does not.
- Committing `.claude/sleepless/` (reports included) – it is excluded via `.git/info/exclude`;
  never force-add it.
- Leaving long-lived background processes (dev servers, watchers) running: while they run, the Stop
  hook lets the turn end and nothing wakes the shift.
