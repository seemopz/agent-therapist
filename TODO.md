# TODO

- sleepless merge mode: verify in a real shift (`gh pr checks --watch`, retargeting a dependent PR
  after its parent merges, conflicts after a squash merge).
- sleepless guard: merges through `gh api` (`PUT …/pulls/<n>/merge`) are not detected.
- Codex sleepless: still never merges; decide whether it gets an opt-in merge mode too.
- Codex sleepless: mention Codex's own long-running tools (`/goal`, Stop hooks with
  `decision: "block"`, app auto-resume) instead of only listing what the skill cannot do.
- agent-therapist memfiles: CLAUDE.md files in directories above the project root also load at
  launch; only the root's are treated as always-loaded today.
