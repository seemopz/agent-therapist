# Checks for "Optimize"

Read this in step 3 for "Optimize". Run the checks in order. Every finding gets a proposal and a reason.
`$SKILL` is this skill's directory, `$G` the global directory, `$P` the project directory.

Every check carries a `<!-- check: id/revision -->` marker; "Update" (SKILL.md) runs only checks whose id
is new or whose revision went up since the last run. Maintainers: a new check gets a new id at revision 1;
raise the revision when a check changes so that already optimized setups would get different findings.

## Check 1 – Token cost per file
<!-- check: tokens/1 -->

Show the table: `python3 $SKILL/scripts/tokens.py --global $G $P`. Point out the largest always-loaded files.
The baseline JSON is saved in step 6; after saving (step 7): `python3 $SKILL/scripts/tokens.py --global $G --baseline $BACKUP/tokens-before.json $P`.

## Check 2 – Duplicate rules across repos → move to global
<!-- check: duplicates/1 -->

Read (never write) the top-level CLAUDE.md of every repo in `${AGENT_THERAPIST_REPOS:-$HOME/repos}`.
For every rule you consider moving, count the exact number of repos it appears in and name them with file:line,
e.g. "found in 2 repos: repo-a/CLAUDE.md:12, repo-b/CLAUDE.md:5". Never write a rounded
number or "3+" – always the exact count and the repo list.

- **3 or more repos:** propose moving it to the global file or `rules/`, reason "appears in N repos:
  <repo/file:line, …>".
- **Fewer than 3 repos:** propose moving it only if the rule is clearly personal (language, style,
  git habits, machine), reason "personal rule, belongs in global (found in N repo(s):
  <repo/file:line, …>)". Otherwise leave it where it is.

Either way, propose removing the rule from this project once it moves to global.
"Already in global" is a valid reason to delete a project section
only if the global version covers everything this one says. Compare them; if the project section has more (details, examples,
exceptions), name what would be lost and propose keeping those lines or moving them to `docs/`.

## Check 3 – Contradictions between levels
<!-- check: contradictions/1 -->

Compare global ↔ project ↔ subfolder files. Look especially for the same kind of value with different
content in several files: colours (`#RRGGBB`), versions, commands, branch rules, language.
For each: quote both lines with file:line, say which one is current (newest date, git log, or code),
propose one source of truth and a link from the others.

## Check 4 – Diary, counters, outdated entries → delete
<!-- check: diary/1 -->

`python3 $SKILL/scripts/scan.py --global $G $P` → findings with `check=diary`.
Dated headings, "State (…)", "superseded", test/commit counters are history, not instructions.
Also flag, even if scan.py does not: version numbers and counters in prose that someone updates by hand
(e.g. "schema v4", "49 tests", "v3 options") – check `git log -S` for commits that only corrected them.
Propose: replace with a pointer to the source of truth (e.g. "latest schema version: see `site/config-schema.js`").
Propose: delete; if the knowledge still matters, move it to `docs/HANDOFF.md` or `docs/` and keep a one-line link.

## Check 5 – Files too long (> 200 lines, target < 60)
<!-- check: length/1 -->

scan.py `check=length`. For each long file propose a split: what stays (commands, rules, pitfalls,
boundaries) and what moves to `docs/<topic>.md` with a one-line link ("Details on X: `docs/x.md`").
Moving is fine when the knowledge is correct but too long; deleting only with a reason.

## Check 6 – Passwords and secrets
<!-- check: secrets/1 -->

scan.py `check=secret`. Report file:line with the masked value only – never repeat the secret in chat,
the preview, or any new file. Propose: remove the line; store the secret in a password manager or `.env`
(not committed); if the file is in git history, tell the user the secret should be rotated.

## Check 7 – Checklist from `guide.md`
<!-- check: guide/1 -->

Go through `references/guide.md` → "Checklist": global under 30 lines · repo under 200, better under 60 ·
every line passes "Would Claude make mistakes without this line?" · no contradictions · commands exist
and run · must-rules as hooks · workflows and long knowledge in `docs/` · at most one `IMPORTANT` line
(scan.py `check=important`). Also flag: role prompts ("You are an expert…"), "double-check",
CAPS shouting, generic advice ("write clean code").

## Check 8 – AGENTS.md
<!-- check: agents/1 -->

Only if the project has an `AGENTS.md`. Facts: `references/guide.md` → "AGENTS.md". scan.py `check=agents`:
- **AGENTS.md is not loaded** (a CLAUDE.md, `.claude/CLAUDE.md` or `CLAUDE.local.md` takes precedence):
  propose `@AGENTS.md` as the first line of that CLAUDE.md, and removing lines there that duplicate AGENTS.md.
- **CLAUDE.md tells Claude in words to read AGENTS.md:** propose replacing the sentence with `@AGENTS.md`.
- **`SessionStart` hook prints AGENTS.md:** propose removing the hook – Claude reads it anyway, the hook adds a second copy.
An `@AGENTS.md` import or a `CLAUDE.md → AGENTS.md` symlink is fine – never flag it.

If `scan.py` finds little and the file already meets the `guide.md` checklist, keep the whole preview
short (roughly 5 findings or fewer): report the genuine ones, then say so explicitly ("looks good,
only this:") instead of adding marginal wording nitpicks to fill the preview.
