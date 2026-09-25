# preprompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/preprompt <idea>` skill that asks only the missing questions, outputs one finished Claude prompt in a code block, then offers to run it.

**Architecture:** Instructions only – `skills/preprompt/SKILL.md` holds the flow, `skills/preprompt/references/prompt-rules.md` holds the prompt skeleton, rules and checklist. A pytest file checks the files' structure; behaviour is checked by manual scenarios.

**Tech Stack:** Markdown skill files, pytest via `uv run pytest`.

**Spec:** `docs/superpowers/specs/2026-09-25-preprompt-design.md`

## Global Constraints

- All file content in English (no `äöüÄÖÜß` in skill files).
- Claude only; no `--for` flag, no saving to files, no clipboard, no scripts or hooks.
- Questions: 0–8, one batch, via `AskUserQuestion`, recommended default first.
- Output: exactly one code block with the prompt, no prose around it.
- After output: "Run it now?" with Yes / Adjust / No.
- Commits: Conventional Commits `type(scope): what`, no Co-Authored-By line. Never edit versions or `CHANGELOG.md`.
- Tests and examples use generic placeholders, never real private repo names.

---

### Task 1: Prompt rules reference

**Files:**
- Create: `skills/preprompt/references/prompt-rules.md`
- Create: `tests/test_preprompt_files.py`
- Modify: `tests/conftest.py` (add `PREPROMPT_DIR`)

**Interfaces:**
- Produces: `PREPROMPT_DIR` in `tests/conftest.py`; headings `## Skeleton`, `## Rules`, `## Checklist`, `## Sources` in `prompt-rules.md` (SKILL.md in Task 2 refers to them by name).

- [ ] **Step 1: Add the fixture path**

In `tests/conftest.py`, below `SLEEPLESS_DIR = ...`:

```python
PREPROMPT_DIR = ROOT / "skills" / "preprompt"
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_preprompt_files.py`:

```python
from __future__ import annotations

import re

from conftest import PREPROMPT_DIR

RULES = PREPROMPT_DIR / "references" / "prompt-rules.md"
SKELETON_TAGS = ("context", "task", "requirements", "constraints", "examples",
                 "output_format", "success_criteria")


def test_rules_has_all_sections():
    text = RULES.read_text()
    for heading in ("## Skeleton", "## Rules", "## Checklist", "## Sources"):
        assert heading in text, heading


def test_rules_skeleton_has_every_tag():
    text = RULES.read_text()
    for tag in SKELETON_TAGS:
        assert "<%s>" % tag in text and "</%s>" % tag in text, tag


def test_rules_cover_key_points_from_docs():
    text = RULES.read_text()
    for needle in ("reason", "positive", "all-caps", "15 years", "3–5", "last",
                   "explain its reasoning", "platform.claude.com"):
        assert needle in text, needle


def test_rules_are_english_only():
    assert not re.search(r"[äöüÄÖÜß]", RULES.read_text())
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_preprompt_files.py -v`
Expected: 4 FAIL with `FileNotFoundError` for `prompt-rules.md`.

- [ ] **Step 4: Write `skills/preprompt/references/prompt-rules.md`**

````markdown
# Prompt rules

How to build the prompt in step 4 of `SKILL.md`. Written for Claude as the target model.

## Skeleton

Use these sections in this order. Drop every section that would be empty or say nothing new –
a short prompt with three sections beats a long one with seven.

```
<context>
Who this is for, what it is for, what already exists, why it matters.
Long pasted material (code, documents, data) goes here, before the task.
</context>

<task>
The goal in 1–3 direct sentences, starting with a verb ("Build …", "Rewrite …").
</task>

<requirements>
- Concrete requirements, one per line.
</requirements>

<constraints>
- What must not happen, each with its reason ("No external packages – it runs on a server without internet").
</constraints>

<examples>
<example>
Only when style or format matters: 3–5 varied examples.
</example>
</examples>

<output_format>
What the result looks like: file, code block, prose, table, length.
</output_format>

<success_criteria>
How to tell the result is done and correct – checkable, not "good quality".
</success_criteria>
```

Write the prompt in the language of the user's idea. Tag names stay in English.

## Rules

1. **Clear and direct.** Write for a brilliant new colleague who has no context. Use imperative
   verbs ("Change the function …"); "Can you suggest …" gets suggestions instead of changes.
2. **Give the reason.** Every constraint carries a reason, so Claude can apply it to cases the
   prompt does not list.
3. **Say what to do, not what to avoid.** Prefer the positive form ("write in flowing prose")
   over a prohibition ("no bullet points").
4. **Role only with a purpose.** Add a role line ("You are a security reviewer …") only when it
   sets a real perspective or tone. Leave out seniority claims like "15 years of experience" –
   the docs give no evidence that they help.
5. **Calm wording.** No all-caps, no "CRITICAL" or "MUST". Newer models follow instructions
   closely and overreact to emphasis.
6. **Do not ask Claude to explain its reasoning in the answer.** It can trigger a refusal. When
   depth matters, "Think it through carefully before answering" is enough.
7. **Examples: 3–5, varied**, wrapped in `<example>` tags – only when style or format matters.
8. **Long material first, task last.** Pasted documents or code go into `<context>`; the task
   comes after them.
9. **Match the style of the wanted output.** A prompt with little markdown gets answers with
   little markdown.
10. **Say where to stop.** For large tasks: plan first, then implement. State whether Claude
    should "report the findings and stop" or "implement the changes".
11. **Short beats exhaustive.** One clear instruction beats a list of behaviours; no filler, no
    flattery.

## Checklist

Apply while writing – not as an extra pass:

- Is the goal unambiguous?
- Does every constraint have a reason?
- Is the success criterion checkable?
- Are there empty or duplicated sections?

## Sources

Checked on 2026-09-25:

- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5
````

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_preprompt_files.py -v`
Expected: 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/test_preprompt_files.py skills/preprompt/references/prompt-rules.md
git commit -m "feat(preprompt): add prompt rules reference"
```

---

### Task 2: SKILL.md flow

**Files:**
- Create: `skills/preprompt/SKILL.md`
- Modify: `tests/test_preprompt_files.py` (append tests)

**Interfaces:**
- Consumes: `PREPROMPT_DIR` (Task 1); headings `## Skeleton`, `## Rules`, `## Checklist` in `references/prompt-rules.md`.

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_preprompt_files.py`:

```python
SKILL = PREPROMPT_DIR / "SKILL.md"


def test_skill_frontmatter():
    text = SKILL.read_text()
    assert text.startswith("---\nname: preprompt\ndescription: Use when ")
    assert "\nargument-hint: <idea>\n" in text.split("\n---\n", 1)[0] + "\n"


def test_skill_flow_key_steps():
    text = SKILL.read_text()
    for needle in ("references/prompt-rules.md", "AskUserQuestion", "at most 8",
                   "one code block", "Run it now?", "Yes", "Adjust", "No",
                   "What is it about?"):
        assert needle in text, needle


def test_skill_is_english_only_and_short():
    text = SKILL.read_text()
    assert not re.search(r"[äöüÄÖÜß]", text)
    assert len(text.splitlines()) <= 90
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_preprompt_files.py -v`
Expected: the 3 new tests FAIL with `FileNotFoundError` for `SKILL.md`; the 4 from Task 1 PASS.

- [ ] **Step 3: Write `skills/preprompt/SKILL.md`**

````markdown
---
name: preprompt
description: Use when the user types /preprompt or asks Claude to write, build or improve a prompt for Claude ("write me a prompt for …", "turn this into a good prompt") – not for ordinary tasks that merely mention prompts.
argument-hint: <idea>
---

# preprompt

Turns a rough idea into one finished prompt for Claude. Ask only what is missing, build the
prompt from `references/prompt-rules.md`, show it, then offer to run it.

Talk to the user in their language. Keep messages short.

## 1. Get the idea

The idea is the text after `/preprompt`. If there is none, ask "What is it about?" in the
user's language and wait for the answer.

## 2. Check what is missing

Read `references/prompt-rules.md`. Compare the idea with the sections of the `## Skeleton`:
goal, context, requirements, constraints, examples, output format, success criteria.

Something is missing only if a good answer would change depending on it. Fill in obvious
details yourself; do not ask about them.

## 3. Ask – only if needed

Idea clear enough → skip to step 4.

Otherwise ask all questions in one `AskUserQuestion` call: at most 8 questions (split into two
calls of at most 4 if the tool limits a call to 4), each with 2–4 options, the recommended
option first and marked "(Recommended)". The user can always type their own answer.

Ask about substance (goal, audience, scope, constraints, format), not about prompt technique.

## 4. Build the prompt

Follow `## Skeleton`, `## Rules` and `## Checklist` in `references/prompt-rules.md`. Write the
prompt in the language of the idea. Drop sections that would be empty.

## 5. Show it

Output exactly one code block that contains the whole prompt – no heading, no explanation
before or after it. Use a fence longer than any fence inside the prompt (e.g. four backticks).

## 6. Offer to run it

Ask with `AskUserQuestion`: "Run it now?"

- **Yes** – work on the prompt in this session as if the user had just sent it.
- **Adjust** – ask what to change, rebuild the prompt (step 4), show it again (step 5), ask again.
- **No** – stop. Say nothing more.
````

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_preprompt_files.py -v`
Expected: 7 PASS.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/preprompt/SKILL.md tests/test_preprompt_files.py
git commit -m "feat(preprompt): add skill flow"
```

---

### Task 3: Docs, scenarios and install

**Files:**
- Modify: `README.md` (skill table, install, new `## preprompt` section, layout, roadmap)
- Modify: `CLAUDE.md` (symlink pitfall line)
- Modify: `tests/scenarios.md` (append preprompt scenarios)

**Interfaces:**
- Consumes: `skills/preprompt/SKILL.md` (Task 2).

- [ ] **Step 1: README – skill table**

Add a row after the sleepless row, and change "with two skills" to "with three skills":

```markdown
| [**preprompt**](#preprompt) | turns a rough idea into a finished prompt for Claude, asking only what is missing |
```

- [ ] **Step 2: README – install**

Add to the `ln -s` block:

```bash
ln -s ~/repos/agent-therapist/skills/preprompt ~/.claude/skills/preprompt
```

- [ ] **Step 3: README – new section before `## Layout`**

````markdown
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
````

- [ ] **Step 4: README – layout and roadmap**

In the `## Layout` code block, after the `skills/sleepless/` lines:

```
skills/preprompt/
  SKILL.md                       the flow (steps 1–6)
  references/prompt-rules.md     prompt skeleton, rules, checklist, sources
```

In `## Roadmap`, after item 2:

```markdown
3. ✅ preprompt: turn a rough idea into a finished prompt
```

and renumber the following items 4–6.

- [ ] **Step 5: CLAUDE.md – pitfall line**

Replace the symlink line with:

```markdown
- `~/.claude/skills/agent-therapist`, `~/.claude/skills/sleepless` and `~/.claude/skills/preprompt` are symlinks into `skills/` – every edit is live in real sessions, including the sleepless hooks.
```

- [ ] **Step 6: tests/scenarios.md – append**

```markdown
## 6. preprompt

Interactive only (`AskUserQuestion` needs a user). In any scratch repo, start
`claude --plugin-dir ~/repos/agent-therapist`, then:

1. `/preprompt Write a Python function that returns the n-th Fibonacci number iteratively, with type hints and a pytest test. Output only the code.`
   - [ ] no questions, one code block with the prompt, then "Run it now?"
2. `/preprompt do something with photos`
   - [ ] at least 3 questions in one batch, each with a recommended option
3. `/preprompt`
   - [ ] asks what it is about, nothing else
4. After any prompt is shown, choose **Adjust** and ask for "answer in German"
   - [ ] prompt rebuilt with that change, shown again, "Run it now?" again
```

- [ ] **Step 7: Verify and commit**

Run: `uv run pytest`
Expected: all PASS.

```bash
git add README.md CLAUDE.md tests/scenarios.md
git commit -m "docs(preprompt): document skill and add scenarios"
```

---

### Task 4: Install and try it (needs the user)

- [ ] **Step 1: Ask the user** before creating the symlink (outside the repo). After merge the
  symlink should point at the main checkout, not the worktree:

```bash
ln -s ~/repos/agent-therapist/skills/preprompt ~/.claude/skills/preprompt
```

  Until the branch is merged, the scenarios run from the worktree with
  `claude --plugin-dir <worktree path>`.

- [ ] **Step 2: Run scenarios 6.1–6.4** from `tests/scenarios.md` together with the user and
  tick the boxes in the PR description.

- [ ] **Step 3: Ask the user before push and PR.**
