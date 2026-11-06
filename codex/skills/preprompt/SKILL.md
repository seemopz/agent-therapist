---
name: preprompt
description: Turn a rough idea into a reusable prompt for Codex when the user asks to write or improve a prompt.
---

# preprompt for Codex

Turn the user's idea into one clear prompt in the language of the request. Ask only about missing information that would materially change the result; suggest sensible defaults. For ordinary work requests, do the work instead of turning them into prompts unless the user asks for a prompt.

Include the goal, relevant context, concrete requirements, constraints and their reasons, desired output, and checkable success criteria where useful. Leave out empty sections and unnecessary roles or rigid formatting. State whether the requested result is analysis or implementation. Preserve the user's authorization and avoid adding unrequested side effects.

Show the finished prompt in a single code block. Then offer to run it, revise it, or stop; execute it only if the user asks.
