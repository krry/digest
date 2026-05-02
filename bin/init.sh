#!/usr/bin/env bash
# gist init — create local datastore files from committed examples
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

created=0
skipped=0

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

init_file "goals.json"
init_file "values.json"
init_file "checkins.json"

echo ""
echo "Bootstrap complete."
echo "Created: $created  Skipped: $skipped"
echo "Next: ./bin/show.sh or ./bin/gist-tui"
