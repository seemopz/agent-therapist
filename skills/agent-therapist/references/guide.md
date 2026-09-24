# CLAUDE.md – awesome guide

Compact reference: what goes where, how to write it, how to maintain it.
As of 24 September 2026, based on the Claude Code docs and our own measurements.

---

## Core principle

- CLAUDE.md = **advice**, not a rule → what must *always* happen belongs in a **hook**
- sent on **every model call** → every line costs tokens and attention
- long files → rules get lost, Claude ignores them
- test question per line: **"Would Claude make mistakes without this line?"** → no = cut it

---

## Levels

| File | Applies to | Loaded | Git |
|---|---|---|---|
| `~/.claude/CLAUDE.md` | all projects | always | no |
| `~/.claude/rules/*.md` | all projects | always | no |
| `./CLAUDE.md` / `./.claude/CLAUDE.md` | repo, team | always | yes |
| `./CLAUDE.local.md` | repo, me only | always | no |
| `./AGENTS.md` / `./.claude/AGENTS.md` | repo, all coding agents | always, **only if** no `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` in the working dir or above (default) | yes |
| `./.claude/rules/*.md` + `paths:` | specific files | when matching files are opened | yes |
| `subfolder/CLAUDE.md` | sub-area | when Claude reads there | yes |
| `subfolder/AGENTS.md` | sub-area | when Claude reads there and the folder has no CLAUDE file | yes |
| `.claude/skills/<name>/SKILL.md` | on demand | when invoked | yes |

- everything gets **merged**, nothing overwrites
- contradicting rules → Claude picks **arbitrarily**
- `@path/file.md` import → **still loads at startup**, saves no space; path relative to the importing file, max 4 hops deep
- monorepo: `claudeMdExcludes` in settings (glob on absolute paths) skips other teams' CLAUDE.md files

### AGENTS.md

- Claude Code reads `AGENTS.md` natively – no hook, no setting needed
- `~/.claude/CLAUDE.md` and `rules/` do **not** block it; `CLAUDE.local.md` does
- `/config` → **Project instructions** (user settings: `pluginConfigs."agents-md@builtin".options.instructionFiles`):
  `claude-md-or-agents-md` (default) · `claude-md-and-agents-md` · `claude-md` · `managed-only`
- repo with both files → `CLAUDE.md` starts with `@AGENTS.md`, below it only Claude-specific lines
- symlink `CLAUDE.md → AGENTS.md` is fine (not on Windows)
- outdated workarounds: `SessionStart` hook that prints `AGENTS.md` → remove (second copy);
  CLAUDE.md sentence "read AGENTS.md" → replace with `@AGENTS.md`

---

## What goes where

**Global (`~/.claude/CLAUDE.md`), how *I* work:**
- Language: "Reply in German"
- Answer style: short, result first
- Git habits: commit style, never push without asking
- Machine quirks: e.g. `python3` too old → `uv` / `.venv`
- Favourite tools: `uv`, `gh`, `pnpm` …

**Repo (`CLAUDE.md`), what *the project* needs:**
- Commands: build, test, run, lint, exact
- Conventions that deviate from the default, **with a reason**
- Architecture decisions not visible in the code
- Pitfalls, non-obvious behaviour
- Boundaries: "don't touch `legacy/`", "no new dependencies"
- Branch and PR conventions, required environment variables

**`CLAUDE.local.md`, me only, this repo only:**
- local paths, own test data, personal shortcuts

**Path rule (`.claude/rules/api.md` + `paths:`):**
- rules for only one area of the code: API, migrations, UI components

**Skill:**
- multi-step workflows: release, deployment, data migration
- rarely-needed, long knowledge: domain docs, API reference
- knowledge the model can't have: internal frameworks, new API versions

**Hook:**
- must **always** happen: tests before finishing, linter after edits
- must **never** happen: writing to `migrations/`, `.env`

**Nowhere:**
- what the model already knows or reads from the code

---

## In / Out

| ✅ in | ❌ out |
|---|---|
| commands you can't guess | anything visible in the code |
| style rules that deviate from the default | standard language conventions |
| test runner and how to test | full API docs → link it |
| repo conventions | information that changes often |
| project-specific architecture | tutorials, long explanations |
| environment quirks | file-by-file descriptions |
| pitfalls | "write clean code" |

---

## Writing

- **Length:** under 200 lines per file (docs) · ideal under 60 (practice)
- **Budget:** ~50 instructions global, ~100 in the project
- **Concrete:** "`npm test` before commit" instead of "test your changes"
- **Structured:** headings and bullet points, no prose
- **Why:** a short reason → Claude applies the rule sensibly to new cases
- **Positive:** say what to do, not only what not to
- **Emphasis:** at most one line with `IMPORTANT` · no CAPS shouting, no "MUST" everywhere
- **No magic words:** no role prompts ("You are an expert …"), no "double-check" (modern models already check themselves)
- **Links instead of content:** "Details on X: `docs/x.md`", so Claude only reads it when needed

---

## Maintaining

- **Add when:**
  - Claude makes the same mistake **twice**
  - I type the same correction again
  - a review finds something Claude should have known
  - a new team member would need the same info
- **Cut when:**
  - Claude gets it right even without the line
  - the info is outdated
  - Claude keeps ignoring a rule → the file is too long
- **Tools:**
  - `/context` → what's loaded
  - `/doctor` → suggests cuts
  - `/init` → starter scaffold, then cut it down hard
- treat it like code: version it, review it, clean it up regularly

---

## Template: global

```markdown
# Me
- Reply in German, briefly, result first.
- Ask before you push, force-push, or delete something.

# Machine
- macOS. `python3` is 3.9 → use `uv run` or `.venv/bin/python` for Python projects.
- GitHub via `gh`.

# Git
- Commit messages: `type(scope): what` (feat, fix, docs, refactor, test, chore).
```

## Template: repo

```markdown
# <Project>
One-liner: what it is.

## Commands
- Setup: `…`
- Tests: `…` (single test: `…`)
- Run: `…`

## Conventions
- <rule> – because <reason>.

## Pitfalls
- <non-obvious behaviour>

## Boundaries
- don't change `<path>/`: <reason>.

## More
- Architecture: `docs/architecture.md`
```

---

## Checklist

- [ ] global file under 30 lines, personal only
- [ ] repo file under 200 lines, better under 60
- [ ] every line passes the test question
- [ ] no contradictions between levels
- [ ] commands are correct and run
- [ ] must-rules as a hook, not as text
- [ ] workflows and long knowledge in skills or `docs/`
- [ ] at most one `IMPORTANT` line
- [ ] an `AGENTS.md` actually loads (no CLAUDE file blocking it without `@AGENTS.md`)

---

## Sources

- [Claude Code Docs: How Claude remembers your project](https://code.claude.com/docs/en/memory)
- [Claude Code Docs: Best practices](https://code.claude.com/docs/en/best-practices)
- [Claude Docs: Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- [HumanLayer: Writing a good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md)
- [alexop.dev: Stop Bloating Your CLAUDE.md](https://alexop.dev/posts/stop-bloating-your-claude-md-progressive-disclosure-ai-coding-tools/)
