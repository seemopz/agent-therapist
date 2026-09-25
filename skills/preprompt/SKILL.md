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
