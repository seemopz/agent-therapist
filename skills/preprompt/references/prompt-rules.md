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
- Limits, phrased positively where possible, each with its reason ("Use only the standard library – it runs on a server without internet").
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
6. **Do not ask Claude to explain its reasoning in the answer.** It can trigger a refusal. Leave
   thinking depth to the model's effort setting instead of adding "think carefully" lines.
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
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5
