# TODO

- sleepless merge mode: verify in a real shift (`gh pr checks --watch`, retargeting a dependent PR
  after its parent merges, conflicts after a squash merge).
- sleepless guard: merges through `gh api` (`PUT …/pulls/<n>/merge`) are not detected.
- Codex sleepless: still never merges; decide whether it gets an opt-in merge mode too.
