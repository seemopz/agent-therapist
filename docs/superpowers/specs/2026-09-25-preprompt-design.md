# preprompt – design

A skill that turns a rough idea into a finished, well-structured prompt for Claude. The user types
`/preprompt <idea>`, answers a few click-to-choose questions if the idea has gaps, and gets one
prompt in a code block. Claude then offers to run it right away.

## Goals

- One ready-to-copy prompt per call, built from current Claude prompt-engineering guidance.
- Ask only what is missing: 0 questions for a clear idea, up to 8 for a vague one.
- Offer to run the prompt in the same session, or to revise it.

## Non-goals

- Prompts for other models (ChatGPT, Gemini, image models). Claude only; a `--for` flag can come later.
- Saving prompts to files or copying them to the clipboard.
- Scripts or hooks. The skill is instructions only.

## Layout

```
skills/preprompt/
├── SKILL.md                    # flow, ~60–80 lines
└── references/prompt-rules.md  # skeleton, rules, checklist
```

`~/.claude/skills/preprompt` is a symlink to `skills/preprompt/` (created after asking the user,
since it lives outside the repo).

### SKILL.md frontmatter

- `name: preprompt`
- `description:` triggers on `/preprompt` or on requests like "write me a prompt for …";
  must not trigger on ordinary tasks.
- `argument-hint: <idea>`

## Flow

1. **No idea given** → ask "What is it about?" and continue with the answer.
2. **Check the idea** against the skeleton: goal, context, constraints, output format, examples.
3. **Ask** – only if something important is missing: 1–8 questions in one batch via
   `AskUserQuestion`, each with a recommended default as the first option. Clear idea → skip.
4. **Build** the prompt from the skeleton, in the language of the idea. Drop sections that would
   be empty.
5. **Output** exactly one code block containing the prompt, with no prose around it.
6. **Offer** "Run it now?" via `AskUserQuestion`:
   - **Yes** → execute the prompt in this session as if the user had sent it.
   - **Adjust** → user names a change, go back to step 4.
   - **No** → stop.

## Prompt skeleton

Sections in XML tags, each optional:

| Tag | Content |
|---|---|
| `<context>` | Who, what for, what exists, why it matters |
| `<task>` | The goal in 1–3 direct sentences ("Build …", not "Could you …") |
| `<requirements>` | Concrete requirements as a list |
| `<constraints>` | What must not happen, each with its reason |
| `<examples>` | 1–3 examples, only when style or format matters |
| `<output_format>` | What the result looks like |
| `<success_criteria>` | How to tell it is done and correct |

## Rules

- Every constraint carries a reason, so Claude can generalise it.
- Phrase instructions positively ("write in prose") rather than as prohibitions.
- A role line ("You are …") only when it sets a real perspective (e.g. security reviewer).
  Seniority claims like "15 years of experience" are not used.
- No filler, no all-caps threats, no flattery.
- Large tasks get an instruction to plan first, then implement.

Before building, these rules are checked against Anthropic's current prompt-engineering docs and
extended where the docs say more. Sources are listed at the bottom of `prompt-rules.md`.

### Checklist (applied while writing, not as a separate pass)

- Is the goal unambiguous?
- Does every constraint have a reason?
- Is the success criterion checkable?
- Are there empty or duplicated sections?

## Testing

No code, so no pytest. Four scenarios in `tests/scenarios.md`:

1. Clear idea → no questions, prompt output directly.
2. Vague idea ("do something with photos") → at least 3 questions.
3. `/preprompt` with no idea → asks what it is about.
4. "Adjust" after output → prompt rebuilt with the change.

## Git

Branch `feat/preprompt` from `main`. Commits: `docs(preprompt): add design spec`, then
`feat(preprompt): add skill`.
