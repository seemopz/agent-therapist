# Git

Read this for block 3 and when sorting git rules.

## Detection

Run in the project root. All read-only.

| Command | Signal | Means |
|---|---|---|
| `ls release-please-config.json .release-please-manifest.json; grep -rl release-please-action .github/workflows` | any hit | release-please |
| `ls .releaserc* release.config.*` | hit | semantic-release |
| `ls .changeset/config.json` | hit | changesets |
| `git branch -a --list '*develop'` | hit | git-flow possible |
| `gh api repos/{owner}/{repo}/branches/main/protection` and `gh api repos/{owner}/{repo}/rules/branches/main` | 200 with rules | branch + PR (403/404 = unknown, not "direct") |
| `gh pr list --state merged --limit 20` | merged PRs | branch + PR |
| `git shortlog -sn --since=1.year` | one author and no PRs | direct |
| `git log -50 --format=%s` | ≥ 80 % Conventional Commits | Conventional Commits |
| `git log -50 --format=%b \| grep -c Co-Authored-By` | 0 | user does not want the trailer |

`gh` missing or not logged in → skip the `gh` rows and say so.

## Fixed rules

Always part of `rules/git.md`, never asked:

- Never force-push.
- Never rewrite pushed history (no rebase/amend of pushed commits).
- Never use `--no-verify`.
- Never commit secrets (`.env`, keys, tokens).
- Ask before every push and every merge.

With release-please additionally:

- Conventional Commits are mandatory – release-please builds versions from them.
- Never touch `CHANGELOG.md`, version numbers or the release PR.

## Template: rules/git.md

```markdown
# Git
- Commits: `type(scope): what` (feat, fix, docs, refactor, test, chore). {no Co-Authored-By line.}
- {Direct: commit directly to main. | Branch + PR: work on a branch `type/topic`, merge via PR.} A repo may state an exception.
- Never force-push, never rewrite pushed history, never `--no-verify`, never commit secrets.
- Ask before push and merge.
{release-please:
- Default: versions come from release-please – Conventional Commits are mandatory; never edit CHANGELOG.md, versions or the release PR. A repo may state an exception.}
```

Replace `{…}` with the chosen variant and drop the braces. Keep it under 15 lines.

## Project deviations

Ask first whether to **Record exception** or **Align repo with the default** (SKILL.md step 4).
For an exception, write only what differs, explicitly, in the project CLAUDE.md, e.g.:

- "In this repo: commit directly to main (single-person repo)."
- "In this repo: no release-please; versions by hand in `pyproject.toml`."
