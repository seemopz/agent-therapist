#!/usr/bin/env bash
# Builds a throwaway sandbox with copies of test repos. Never touches the originals.
#
# Usage: SANDBOX_REPO_MESSY=<path> SANDBOX_REPO_TIDY=<path> tests/sandbox.sh [TARGET]
#   SANDBOX_REPO_MESSY  repo with a cluttered setup, copied to repos/messy-repo (scenario 2)
#   SANDBOX_REPO_TIDY   repo whose setup is already good, copied to repos/tidy-repo (scenario 3)
# An unset variable skips that copy with a note on stderr.
#
# Safety model: allowlist, not denylist. The resolved target must land strictly inside a
# temp directory, and an already-existing target must carry our marker file — otherwise refuse.
set -euo pipefail

MARKER=".agent-therapist-sandbox"

TARGET="${1:-${TMPDIR:-/tmp}/agent-therapist-sandbox}"
TARGET="${TARGET%/}"

PARENT="$(dirname "$TARGET")"
if ! PARENT_RESOLVED="$(cd "$PARENT" 2>/dev/null && pwd -P)"; then
  echo "refusing: parent directory does not exist: $PARENT" >&2
  exit 1
fi
RESOLVED="$PARENT_RESOLVED/$(basename "$TARGET")"
RESOLVED_LC="$(printf '%s' "$RESOLVED" | tr '[:upper:]' '[:lower:]')"

allowed=0
for root in "${TMPDIR:-/tmp}" /tmp /private/tmp /private/var/folders; do
  root_resolved="$(cd "$root" 2>/dev/null && pwd -P)" || continue
  root_lc="$(printf '%s' "$root_resolved" | tr '[:upper:]' '[:lower:]')"
  case "$RESOLVED_LC" in
    "$root_lc"/*) allowed=1; break ;;
  esac
done
if [ "$allowed" -ne 1 ]; then
  echo "refusing: sandbox must be strictly inside \$TMPDIR, /tmp, /private/tmp or /private/var/folders (resolved target: $RESOLVED)" >&2
  exit 1
fi

if [ -e "$RESOLVED" ] && [ ! -f "$RESOLVED/$MARKER" ]; then
  echo "refusing: existing target is not an agent-therapist sandbox (missing $MARKER): $RESOLVED" >&2
  exit 1
fi

copies=()
for pair in "messy-repo:${SANDBOX_REPO_MESSY:-}" "tidy-repo:${SANDBOX_REPO_TIDY:-}"; do
  name="${pair%%:*}"
  src="${pair#*:}"
  if [ -z "$src" ]; then
    echo "note: skipping $name (SANDBOX_REPO_$(printf '%s' "${name%-repo}" | tr '[:lower:]' '[:upper:]') not set)" >&2
    continue
  fi
  if ! src_resolved="$(cd "$src" 2>/dev/null && pwd -P)"; then
    echo "refusing: source repo does not exist: $src" >&2
    exit 1
  fi
  copies+=("$name:$src_resolved")
done

rm -rf "$RESOLVED"
mkdir -p "$RESOLVED/home-claude" "$RESOLVED/repos"
touch "$RESOLVED/$MARKER"
echo '{}' > "$RESOLVED/home-claude/settings.json"

git init -q -b main "$RESOLVED/repos/empty"
git -C "$RESOLVED/repos/empty" -c user.name=test -c user.email=test@example.invalid commit -q --allow-empty -m "chore: init"

for copy in ${copies[@]+"${copies[@]}"}; do
  rsync -a \
    --exclude node_modules --exclude .build --exclude build --exclude DerivedData \
    --exclude .venv --exclude Pods --exclude .dart_tool --exclude dist \
    "${copy#*:}/" "$RESOLVED/repos/${copy%%:*}/"
done

echo "$RESOLVED"
