#!/usr/bin/env bash
# Stamp out a new venture in this studio repo.
# Usage:  scaffold/new-project.sh <project-slug> "<Project Name>"
# Example: scaffold/new-project.sh plantpeers "plantpeers.com"
set -euo pipefail

SLUG="${1:?usage: new-project.sh <slug> \"<Project Name>\"}"
NAME="${2:-$SLUG}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/$SLUG"

if [ -e "$DEST" ]; then
  echo "refusing to overwrite existing $DEST" >&2
  exit 1
fi

mkdir -p "$DEST"
# Project skeleton (static app + data) with the name substituted in.
cp -r "$ROOT/scaffold/project-skeleton/." "$DEST/"
# CONTEXT.md from the template.
cp "$ROOT/scaffold/CONTEXT.template.md" "$DEST/CONTEXT.md"

# Substitute <PROJECT NAME> placeholders.
find "$DEST" -type f \( -name '*.html' -o -name '*.md' \) -print0 \
  | xargs -0 sed -i "s/<PROJECT NAME>/${NAME//\//\\/}/g"

cat <<EOF
Created $SLUG/:
$(cd "$ROOT" && find "$SLUG" -type f | sort | sed 's/^/  /')

Next:
  1. Fill in $SLUG/CONTEXT.md (product, mechanic, data model, constraints).
  2. Point the team at it — the five agents in .claude/agents/ ground themselves
     on that CONTEXT.md. Kick off with the Prototyper.
  3. Run it:  (cd $SLUG && python -m http.server 8000)  then open index.html
EOF
