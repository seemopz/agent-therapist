# Permissions

Read this for question 27. Permissions live in `settings.json` under `permissions.allow` / `permissions.deny`.
Use the rule syntax already used in the file; if none, use `Bash(cmd:*)` for prefixes.
Merge: add entries, keep existing ones, never remove without asking. Validate afterwards with
`python3 -m json.tool settings.json > /dev/null`.

## Allow

Offer only what matches the project (detected in step 2):

- Read-only git: `Bash(git status:*)`, `Bash(git diff:*)`, `Bash(git log:*)`, `Bash(git show:*)`, `Bash(git branch:*)`
- Read-only gh: `Bash(gh pr view:*)`, `Bash(gh pr list:*)`, `Bash(gh issue view:*)`
- The project's confirmed test/lint/build commands from question 18, e.g. `Bash(npm test:*)`, `Bash(uv run pytest:*)`, `Bash(xcodebuild:*)`
- Harmless inspection: `Bash(ls:*)`, `Bash(which:*)`

## Deny

Suggest by default:

- `Read(./.env)`, `Read(./.env.*)`, `Read(./**/*.pem)`, `Read(./**/*.key)`
- `Bash(git push --force:*)`, `Bash(git push -f:*)`
- `Bash(rm -rf:*)`

## Never allow

Do not offer these as "allow without asking", even if the user asks – explain why and suggest asking each time:

- `Bash(git push:*)` – push is always asked (git rules)
- `Bash(curl:*)`, `Bash(wget:*)` – can send data anywhere
- `Bash(sudo:*)`
- `Bash(*)` or a bare `Bash` – allows everything
- `Bash(rm:*)`
