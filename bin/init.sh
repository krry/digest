#!/usr/bin/env bash
# gist init — create local datastore files from committed examples
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

created=0
skipped=0
linked=0

init_file() {
  local name="$1"
  local example="$ROOT_DIR/$name.example"
  local target="$ROOT_DIR/$name"

  if [[ -f "$target" ]]; then
    echo "exists: $name"
    skipped=$((skipped + 1))
    return
  fi

  cp "$example" "$target"
  echo "created: $name"
  created=$((created + 1))
}

link_skill() {
  local name="$1"
  local source="$ROOT_DIR/skills/digest-gist/$name/SKILL.md"
  local target="$2"

  mkdir -p "$(dirname "$target")"

  if [[ -L "$target" ]] && [[ "$(readlink "$target")" == "$source" ]]; then
    echo "linked: $target"
    skipped=$((skipped + 1))
    return
  fi

  if [[ -e "$target" ]] && [[ ! -L "$target" ]]; then
    mv "$target" "$target.backup-$TIMESTAMP"
    echo "backup: $target.backup-$TIMESTAMP"
  elif [[ -L "$target" ]]; then
    rm "$target"
  fi

  ln -s "$source" "$target"
  echo "symlinked: $target"
  linked=$((linked + 1))
}

init_file "goals.json"
init_file "values.json"
init_file "checkins.json"

if [[ -f "$ROOT_DIR/digest.db" ]]; then
  echo "exists: digest.db"
  skipped=$((skipped + 1))
else
  PYTHONPATH="$ROOT_DIR" python3 -m digest.cli init >/dev/null
  echo "created: digest.db"
  created=$((created + 1))
fi

PYTHONPATH="$ROOT_DIR" python3 -m digest.cli export-json >/dev/null

for name in gist-show gist-add gist-done gist-checkin gist-onboard; do
  link_skill "$name" "$HOME/.codex/skills/digest-gist/$name/SKILL.md"
  link_skill "$name" "$HOME/.claude/skills/$name/SKILL.md"
done

echo ""
echo "Bootstrap complete."
echo "Created: $created  Linked: $linked  Skipped: $skipped"
echo "Next: ./bin/show.sh or ./bin/gist-tui"
