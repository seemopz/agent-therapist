# Question catalogue

Read this in step 3 (both modes – see "Question plan"). Ask in the user's language.

## How to ask

- Look first, ask second. Every question marked (auto) is answered from what step 2 found;
  show the finding and ask only for confirmation.
- Ask with the question tool (AskUserQuestion), up to 4 questions per call, 2–4 options each.
  Every question has a recommendation (SKILL.md Principle 6): one option first with "(Recommended)"
  and a one-line reason. The recommendations below are defaults – when the findings point elsewhere,
  recommend what fits them and name the finding. If the tool is unavailable (headless run),
  ask as a numbered text list. If the user's prompt already contains answers, use them.
- **Detected ≠ wanted.** For an (auto) answer, offer "Keep as is" preselected. Only put a change
  first when there is a concrete reason, and state the reason in the option description.
- Skip only what the Question plan marks as conditional and does not apply. Aim for at most 27 questions; combine (auto) confirmations to stay there.
- Optional means the user may skip the answer – still ask the question. (auto) means show the
  finding and let the user confirm – never apply it silently (e.g. question 14).

## Question plan

Fixed – follow it, do not improvise which questions to ask. (auto) questions may be combined into one
confirmation question (e.g. 10 + 11: "Found: macOS arm64, uv, gh … – keep?").

| Level + mode | Always ask | Only if |
|---|---|---|
| Global, Build new | 1–16 | – |
| Project, Build new | 17 (confirm), 18 (confirm), 19, 20, 21, 22, 24, 26, 27; one question per deviation from the global git rules | 23 UI found · 25 formatter found · 28 Branch + PR |
| Project, Optimize | one question per deviation from the global git rules; 24, 26, 27 if the project has no hooks/permissions yet | 25 formatter found · 28 Branch + PR |
| Global, Optimize | none – checks only | – |

After the last round, show one line: "Asked: 1–16, 24, 26, 27 · skipped: 23 (no UI), 25 (no formatter)".
Every question of the plan appears there as asked or skipped with a reason.

## Which blocks

| Scope | Blocks |
|---|---|
| Global | 0, 1, 2, 3 |
| Project | 3, 4, 5 |
| Both | 0–5 |

Block 3 in a project: ask only whether the project deviates from the global git rules.

## Block 0 – Token hygiene → `<global>/rules/token.md`

1. **When to suggest a new session:** on topic change (Recommended) / after every task / never
2. **Hand-off text:** include a ready-to-paste summary when suggesting a new session? yes (Recommended) / no
3. **Subagents:** hand big searches to subagents without asking? yes (Recommended) / ask first

## Block 1 – How you work → `<global>/CLAUDE.md`

4. **Answer language** (auto from the conversation): the language of this chat (Recommended) / other
5. **Language for code, commits, repo docs (not memory files – those are always English):** English (Recommended) / same as answers / per project
6. **Answer length:** short, result first (Recommended) / medium / detailed
7. **Expertise:** beginner / intermediate / professional – decides how much Claude explains. Recommended: the level the conversation and repos suggest – name the signal
8. **Always ask before:** push · delete files · install dependencies · anything outside the repo (multi-select, all four preselected = Recommended)
9. **Library docs:** look them up instead of answering from memory? yes (Recommended) / no

## Block 2 – Machine and tools → `<global>/CLAUDE.md`

10. **OS and quirks** (auto: `uname -a`, `python3 --version`, `which uv brew pnpm`). Example quirk: "`python3` is 3.9 → use `uv run`". Keep as found (Recommended).
11. **Favourite tools** (auto: `which uv gh pnpm bun docker`) – keep as found (Recommended) / remove / add
12. **Other machines:** "Do you also work on other machines, e.g. a server or a VM?" no (Recommended) / yes. If another repo mentions one, recommend yes instead and name the finding. Only on yes, ask as a follow-up: which host and how you connect (free text; host names only, never passwords or IP credentials).
13. **What Claude keeps getting wrong** (free text, optional). Recommended: a draft from corrections found in existing files, else "skip".

## Block 3 – Git → `<global>/rules/git.md`, in a project only deviations

14. **Commit style** (auto: ≥ 80 % of last 50 commits match `^(feat|fix|docs|refactor|test|chore|build|ci|perf|style)(\(.+\))?!?:`) incl. "no Co-Authored-By line?" Recommended: Conventional Commits, no Co-Authored-By line; keep as is if the repo already follows another consistent style.
15. **Way to main:** branch + PR (Recommended) / direct / other (auto, see `git.md` → Detection); keep as is recommended when detection finds a consistent other way. Offer git-flow only if a `develop` branch exists.
16. **Versions:** none / by hand / release-please (Recommended) (auto). Offer semantic-release or changesets only if found.

Fixed rules, never asked: see `git.md` → "Fixed rules".

## Block 4 – The project → `<project>/CLAUDE.md`

17. **Project in one sentence** – never asked directly. Take it from README, else `package.json`/`pyproject.toml` description, else infer from the code; show for confirmation, the draft sentence is the Recommended answer. Empty repo → ask. No README → offer a short one.
18. **Commands: build / test / run** (auto from `package.json` scripts, `pyproject.toml`, `Makefile`, `justfile`, `*.xcodeproj`/`project.yml`, `Cargo.toml`). Run the test command once if cheap; only confirmed-working commands go into CLAUDE.md. Recommended: the commands that ran.
19. **Rules that differ from the global ones, and why** (free text; phrase as "in this repo: …"). Recommended: drafts from deviations found, else "none".
20. **Pitfalls** – non-obvious behaviour (free text, optional). Recommended: drafts from README/code findings, else "skip".
21. **Boundaries:** off-limits paths · new dependencies allowed? · frozen parts. Recommended: generated/vendored paths off-limits, new dependencies only after asking.
22. **Knowledge files** (multi-select, existing ones first): `TODO.md` (preselected) · `docs/HANDOFF.md` (preselected) · `docs/architecture.md` (medium or larger projects) · `CHANGELOG.md` (only without version automation) · own. Preselected = Recommended. Each becomes one line in CLAUDE.md, e.g. "New TODOs → `TODO.md`".
23. **Design rules** (only if the project has a UI): colours, fonts, components – the single source of truth file. Recommended: the design/theme file found

## Block 5 – Automation and permissions → hook / permission

24. **When is something done:** tests pass / start it and look at it — check by hook? (template `done-check`). Recommended: tests pass + hook if the test run takes ≤ 10 s, else tests pass without hook
25. **Format automatically?** yes (Recommended) / no (only if a formatter was found; template `format-after-edit`)
26. **Protected files and sensitive data** (template `protect-files`; suggest `.env*`, keys, `migrations/` if present – all found ones preselected = Recommended)
27. **Permissions:** allow without asking / never allow (multi-select from `permissions.md`; its suggestions preselected = Recommended)
28. **Hook against commits on main?** yes (Recommended) / no (only with "branch + PR"; template `no-commit-on-main`)
