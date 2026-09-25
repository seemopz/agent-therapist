---
name: sleepless
description: Use when the user starts a long autonomous work shift in a repo – overnight or while away ("sleepless", "work through the night", "keep going until I say stop", "Nachtschicht") – and whenever a sleepless hook message says a shift is active.
---

# sleepless

A shift is a long unattended work session on its own branch. It ends only the way the user chose
at the start: **stop** in chat, a time, a number of hours, or the task list being done. While
`.claude/sleepless/state.json` exists, this plugin's hooks enforce the mechanics: the Stop hook
keeps the turn going, "stop" and "weiter" in chat end or resume the shift, a new session after a
restart is woken automatically, and dangerous commands are blocked. This skill says what to do with
the time.

`$SHIFT` below stands for `python3 "${CLAUDE_SKILL_DIR}/scripts/shift.py"`, run inside the repo.

Talk to the user in their language. Everything written to files, commits and the PR is in English.

## Start (once)

1. `python3 "${CLAUDE_SKILL_DIR}/scripts/shift.py" status`. If a shift is active, you are resuming:
   go to **After a restart**.
2. Detect what is there: a task list in the user's prompt, `TODO.md`, open issues
   (`gh issue list --limit 20`, only if `gh` works), how tests run (CLAUDE.md, README, package
   files), how deploys run.
3. One `AskUserQuestion` round, at most 4 questions. Detected options first, marked "(detected)":
   - **End of shift**: "When I say stop" / "At a time" / "After N hours" / "When the list is done".
     The user types the time or hours via "Other"; if not, use a second question in the same round.
   - **Task sources** (multi-select): "List in my prompt" / "TODO.md" / "GitHub issues" /
     "Propose tasks" (you derive tasks from the repo and write them into the report's plan first).
   Never ask about cost – there is no cost limit. Never ask about keeping the machine awake – that
   is the user's job; never start `caffeinate` or anything similar.
4. `python3 "${CLAUDE_SKILL_DIR}/scripts/shift.py" start --label "<short topic>" --end <stop|time|hours|list> [--at HH:MM | --hours N] --sources <prompt,todo,issues,propose>`.
   It creates branch `sleepless/<date>`, the state, and `SLEEPLESS-REPORT.md`.
5. Write the plan (the task list in order) into the report, commit `docs(sleepless): start shift`,
   `git push -u origin <branch>`.
6. Tell the user in 2–3 lines: branch, end condition, first task. Start the first task in the same
   turn.

## The loop

For every item:

1. Do the work. Independent items may run in parallel subagents; give each a self-contained prompt
   and never let two touch the same files.
2. Run the tests. Red → fix. If you can't, revert or park the change and note it.
3. Review by a subagent: hand it the diff and the item. Fix real findings, note the rest under
   Findings.
4. Commit (`type(scope): what`), push.
5. Update `SLEEPLESS-REPORT.md` (Done: item → commit hashes; can go into the item's commit), push.
6. Take the next item **in the same turn**.

| Order | Source | Done means |
|---|---|---|
| 1 | the chosen sources: prompt list → `TODO.md` → issues → proposed tasks | every item done or on the question list |
| 2 | quality work | failing or missing tests, stale docs, TODO/FIXME in code, lint and type warnings, small refactors that make code clearer |

End condition "when the list is done": after row 1, run
`python3 "${CLAUDE_SKILL_DIR}/scripts/shift.py" end` and follow the wrap-up it prints. Every other end condition: quality work runs until the shift ends.

## Decisions and blockers

- Decide yourself. Write every decision with its reason under "Decisions and questions" in the
  report. When unsure, pick the option that is easiest to undo.
- Blocked: write the question and what you tried, switch to the next item, come back when
  something changes. Nothing waits for the user.

## Allowed without asking

Pushing the shift branch, opening or updating the shift PR, and deploys as the repo documents them
(CLAUDE.md, README, scripts). Session-hygiene rules ("suggest a new session") are waived during a
shift; compaction is expected and the report carries the state.

## Blocked by the hooks

Force push, push to main/master, deleting remote branches, merging, deleting outside the repo,
sending messages (PR/issue comments, new issues, mail, chat webhooks, MCP send tools). A denied
command is not an error: note it if it mattered and do something else. Never work around the guard.

## Stay inside the repo

- Create files, repos and remotes only inside the repo (scratch files may go to the system temp dir).
- No global installs, no changes to `~/.claude` or other global configuration, no new GitHub repos.
- Anything the user's standing rules say to ask about first goes on the question list instead of
  being done.
- "Propose tasks" means deriving work from the existing code. Never build a new project; an empty
  repo without code or tests means: run `$SHIFT end`.
- While a shift runs, other sessions in the same checkout are left alone by the hooks; tell the
  user to use a separate worktree for parallel work.

## Push notifications

Send `PushNotification` (load it with ToolSearch if it is deferred) only for: the idle pause, the
end of the shift (with the PR link), and important findings (security issue, broken main, risk of
data loss). The user is asleep.

## Pause

When the Stop hook says the shift pauses (no repo change across several stop attempts): push,
`PushNotification` with the reason, end the turn. The shift stays open (paused); the user resumes
it with "weiter" or "resume shift".

## End

On the wrap-up instruction (from "stop" in chat, a passed deadline, or `$SHIFT end`):

1. Finish or cleanly park the current step; tests; commit; push.
2. Final report: summary with real duration (including restarts and pauses), done, decisions and
   questions, blocked, findings, next. Commit, push.
3. `gh pr create --base <base> --head <branch> --title "sleepless: <label>" --body-file SLEEPLESS-REPORT.md`,
   or `gh pr edit <number> --body-file SLEEPLESS-REPORT.md` if the PR exists. Never merge.
4. `PushNotification` with the PR link.
5. `python3 "${CLAUDE_SKILL_DIR}/scripts/shift.py" finish`.
6. Closing message: what was done, the PR link, open questions.

## After a restart

A hook wakes the new session with "A sleepless shift is active". Then: `$SHIFT status`,
`git switch <branch>` if needed, read `SLEEPLESS-REPORT.md` and `git log --oneline <base>..HEAD`,
note the restart time in the report, continue with the next item.

## Red flags – all of these mean: take the next item

| Thought | Reality |
|---|---|
| "The list is done." | Quality work starts now (unless the end condition is "list done"). |
| "The next step needs the user." | Decide, note it with the reason, build. |
| "Good stopping point, I'll summarise." | The summary is the report. The turn goes on. |
| "The context is very long." | Compaction handles it; the report is the memory. |
| "I'm blocked." | Question list, next item. |
| The Stop hook blocked the stop | Not an error. Read its reason and continue. |

## Common mistakes

- Ending a message with "next step needs you" while the shift is active.
- Waiting on a background build instead of starting the next independent item.
- `sleep` loops to pass time: the idle guard pauses the shift; real work does not.
- Committing `.claude/sleepless/` – it is excluded via `.git/info/exclude`; never force-add it.
- Leaving long-lived background processes (dev servers, watchers) running: while they run, the Stop
  hook lets the turn end and nothing wakes the shift.
