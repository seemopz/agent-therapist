# Codex setup review

## Discover what actually applies

Resolve the Codex home from `CODEX_HOME`, otherwise the user's `.codex` directory, using the active shell's syntax. Inspect only files needed for the selected scope; never dump credentials or unrelated session history.

Trace instructions from the global directory and project root to the working directory. Per directory, the first nonempty candidate wins: `AGENTS.override.md`, `AGENTS.md`, then configured fallback names. Nested guidance takes precedence. Check for hidden overrides and configured byte limits (default 32 KiB). Plain links and Claude's `@file` syntax do not establish that another file was automatically loaded. Report actual sources and uncertain loading separately.

Inspect user `config.toml` and project `.codex/config.toml` layers. CLI overrides take precedence; project layers require trust. Profiles and managed requirements can affect the result. Do not infer effective settings from one file or weaken managed restrictions. Record the surface (desktop, CLI, or IDE), OS and shell: commands and supported features must fit that environment.

## Ask for useful choices

Inspect commands and conventions first. For Optimize, ask only unresolved questions, with a recommended option and a short reason. Propose configuration changes only for a demonstrated need; preserve existing choices and verify current model availability instead of prescribing a universal best model.

Detection is evidence, not consent to adopt a preference. Build new follows the complete plan below, even when instruction files already exist. Optimize keeps the outcome unchanged when the current setup already works.

## Build-new question plan

New setup is a guided interview, not a quick rewrite of detected files. For Global, cover G1-G13; for Project, cover P1-P12; for Both, complete Global first, then Project. Existing files do not change the requested mode to Optimize. Explain the upcoming blocks briefly, then start the first round.

- Ask 2-3 distinct questions per round using the available question tool; use a numbered text list if unavailable. Wait for the answers before the next round. Match the tool's supported option count; accept free text.
- Every question has a recommended answer with a short reason. For detected preferences, show the current value and recommend keeping it unless a concrete problem warrants changing it. Detected machine facts and commands are drafts for confirmation, not guesses the user must retype.
- A topic is complete only when explicitly answered in this conversation, confirmed with its detected value, or explicitly skipped by the user. Existing instruction text alone is not a confirmed answer for a rebuild. Reuse explicit answers without asking again.
- Combine closely related confirmations when helpful, but do not hide unrelated topics under one blanket "keep everything" question. A general autonomy answer does not answer language, Git strategy, quality criteria or project boundaries.
- Optional means offer the question with "none/skip" as an answer. Skip conditional topics only when they do not apply, with a reason. Do not require the user to invent extra rules.
- Record each topic as answered, confirmed, user-skipped, or not applicable. Before the file preview, give a short coverage summary and resolve outstanding topics. If the user explicitly requests fewer questions or an immediate draft, honor that choice and name the topics left unconfirmed; do not claim a complete interview.
- Clarify ambiguous authorization rather than silently broadening it. Autonomy preferences describe future work; they do not authorize commits, pushes or configuration changes during this setup.

### Global blocks

| ID | Topic to ask or confirm | Recommended starting point |
|---|---|---|
| G1 | Language of answers, code, commits and documentation | Confirm existing language rules; otherwise chat language for answers and English for authored files. |
| G2 | Answer length and explanation level | Brief, result first; confirm whether explanations should assume beginner, intermediate or professional experience. |
| G3 | Long chats and handoffs | Ask when to recommend a fresh chat: after substantial phases in long chats and substantial topic changes (recommended), topic changes only, or on request. Confirm whether to include a copyable handoff. Use the concrete guidance below for the selected policy; do not claim automatic context management. |
| G4 | Delegation | Ask whether independent subagents may be used autonomously, only on request, or after asking; only where supported. |
| G5 | Routine autonomy | Decide separately for edits, suitable checks and local commits within a requested task. |
| G6 | Actions requiring an explicit request | Confirm boundaries for push, publish, deploy, deletion and work outside the requested repository; do not treat a setup answer as immediate permission. |
| G7 | External documentation | Ask when current official documentation should be checked; retain mandatory accuracy requirements of the environment. |
| G8 | Machine, shell and preferred tools | Confirm detected OS, shell, tool choices and relevant quirks together. Do not record incidental version numbers. |
| G9 | Other working environments | Ask about other machines, VMs, servers or remote workflows; ask for relevant differences only on yes, never credentials. |
| G10 | Recurring agent mistakes | Offer examples from existing instructions or "none yet"; ask what should change the agent's decisions. |
| G11 | Commit conventions | Confirm detected style and any attribution preferences; a project's history is evidence, not a universal preference. |
| G12 | Branch and review strategy | Ask branch + PR, direct commits, or project-specific; distinguish local commits, push and merge. |
| G13 | Versions and releases | Confirm existing automation, manual versioning, none, or per project; do not install release tooling as part of the interview. |

### Project blocks

| ID | Topic to ask or confirm | Recommended starting point |
|---|---|---|
| P1 | Purpose and working scope | Confirm a one-sentence draft from README/code and any multi-repository boundaries. |
| P2 | Setup, build, test, lint and run commands | Present detected commands for confirmation. Separate commands verified here from ones needing hardware, privileges or unavailable services. |
| P3 | Definition of done | Ask which tests, manual/UI checks, security checks or real-device checks are required for which changes. A build alone need not certify runtime behavior. |
| P4 | Protected and generated paths | Confirm generated/vendor outputs, sensitive files and frozen areas; never show secret values. Explain instructions versus runtime enforcement. |
| P5 | Dependencies | Ask when adding or upgrading dependencies needs approval; use the current policy if known. |
| P6 | Project-specific exceptions | Ask which global Git, release, language or autonomy rules differ here and why; "none" is valid. |
| P7 | Recurring pitfalls and architecture constraints | Offer non-obvious findings for confirmation and ask about mistakes not visible in code; "none yet" is valid. |
| P8 | Knowledge and task tracking | Confirm existing task, architecture and handoff locations, or choose none. Do not create empty documentation merely to fill this category. |
| P9 | UI/design source of truth, only for a UI project | Confirm design system, components, language and accessibility requirements from detected guidance. |
| P10 | Formatting, only when a formatter exists | Confirm the command and when it should run; do not install hooks merely because a formatter exists. |
| P11 | Deployment/publication, only when present or requested | Confirm destinations, required approval, privilege boundaries, preservation/rollback and validation; perform no deployment. |
| P12 | Missing capabilities and remaining preferences | Ask whether the user needs configuration changes, missing tools or other rules; "keep current configuration" is a valid answer. Propose runtime settings only for a demonstrated need. |

An answer may cover several named topics, but report that coverage explicitly. The final instructions contain the confirmed decisions that matter, not the questionnaire or its coverage log. Keep Claude-only hooks, permission syntax, update stamps and arbitrary token budgets out of this Codex interview.

## Put each rule where it helps

- Global `AGENTS.md`: reusable user preferences.
- Project `AGENTS.md`: actionable commands, pitfalls and project exceptions.
- Nested instruction file: guidance specific to that directory.
- Skill: a repeatable workflow needed only for particular requests; suggest it rather than creating it as part of this setup review.
- Supporting documentation: long explanations, linked with a clear instruction about when to read them.
- Configuration or execution rules: runtime settings and enforceable permissions, using the current documented format after approval.

Keep only guidance that would change Codex's decisions. Avoid repeating built-in capabilities, repository facts readily discoverable from code, or the same rule at several levels. Do not impose arbitrary line counts. Count bytes for loading limits; any token count is an estimate. Instructions express intent and do not replace sandbox or permission enforcement.

For mixed Claude/Codex repositories, preserve `CLAUDE.md` and `.claude` settings. Shared `AGENTS.md` edits may affect both agents: call out that consequence in the preview and check for conflicting Claude instructions. Never add Claude-specific imports, hooks or settings as a Codex fix.

### Make session hygiene actionable

When the user chooses phase-based handoffs, propose concrete triggers instead of only "when a long chat warrants it". During Optimize, revisit vague handoff guidance when the user reports it was ignored. Preserve an explicit preference for fewer suggestions or no handoff prompts.

Suggested global instructions for the phase-based policy:

```markdown
- After completing a substantial phase in a long chat (audit, implementation, deployment, acceptance), recommend a fresh chat before the next substantial phase, even within the same repository. Also recommend one before a substantial topic change.
- Finish the current task and required checks first. Suggest the switch without stopping already authorized work or creating a chat automatically. Do not repeat the suggestion at every small follow-up; suggest again at the next substantial boundary if the user continues here.
- Include a concise, copyable handoff: objective, repository, branch and latest commit when applicable, completed work, verification and its limits, open issues and next step. Link existing documentation instead of repeating the conversation history. Verify current Git facts before quoting them; omit unavailable facts rather than inventing them.
```

These are user-selected working rules, not automatic enforcement. Do not add token-count thresholds, compaction claims or hooks to enforce them. A fresh-chat suggestion is not a reason to pause a task or request redundant authorization. A small fix and its checks belong together; a user explicitly saying "continue here" should be respected. Keep unverified tests, postponed acceptance and blockers visible in the handoff.

## Verify the result

Check paths and commands against this repository and shell. Parse TOML without rewriting unrelated keys or discarding comments. Syntax validation does not prove runtime support: confirm changed keys against current documentation. After approval and backup, show an instruction-source check the user can run in a fresh Codex session from the root and any affected subdirectory. Report observed results separately from checks still requiring a fresh session. Do not claim installation or activation merely because files exist in this repository.

## Official sources

Recheck these when using this workflow; the details above were reviewed on 2026-10-29.

- [Instruction discovery and overrides](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Configuration layers and trust](https://learn.chatgpt.com/docs/config-file/config-basic)
- [Skill design](https://learn.chatgpt.com/docs/build-skills)
- [Keeping skills and instructions focused](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)
