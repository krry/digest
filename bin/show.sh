#!/usr/bin/env bash
# gist show — render the goal tree from goals.json
# Usage: show.sh [all]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GOALS="$ROOT_DIR/goals.json"
VALUES="$ROOT_DIR/values.json"
SHOW_ALL="${1:-}"

if [[ ! -f "$GOALS" ]]; then
  cp "$ROOT_DIR/goals.json.example" "$GOALS"
fi

node_count=$(jq '.nodes | length' "$GOALS")
if [[ "$node_count" -eq 0 ]]; then
  echo "Nothing here yet. Try /gist:add to create your first goal."
  exit 0
fi

# Build tree: print node + recurse into children
render_node() {
  local id="$1"
  local depth="$2"
  local indent=""
  for ((i=0; i<depth; i++)); do indent="   $indent"; done

  local node
  node=$(jq -r --arg id "$id" '.nodes[] | select(.id == $id)' "$GOALS")
  local type title status
  type=$(echo "$node" | jq -r '.type')
  title=$(echo "$node" | jq -r '.title')
  status=$(echo "$node" | jq -r '.status')

  [[ "$status" == "archived" && -z "$SHOW_ALL" ]] && return

  local badge
  case "$type" in
    goal) badge="G" ;;
    idea) badge="I" ;;
    step) badge="S" ;;
    task) badge="T" ;;
    *)    badge="·" ;;
  esac

  local suffix=""
  [[ "$status" == "completed" ]] && suffix=" ✓"

  echo "${indent}${badge}  ${title}${suffix}"

  # recurse into children
  while IFS= read -r child_id; do
    [[ -n "$child_id" ]] && render_node "$child_id" $((depth + 1))
  done < <(jq -r --arg pid "$id" '.nodes[] | select(.parentId == $pid) | .id' "$GOALS")
}

# render root nodes (parentId == null)
while IFS= read -r root_id; do
  render_node "$root_id" 0
done < <(jq -r '.nodes[] | select(.parentId == null) | .id' "$GOALS")

# values footer
if [[ -f "$VALUES" ]]; then
  phrases=$(jq -r '[.values[].phrase] | join(" · ")' "$VALUES")
  [[ -n "$phrases" ]] && echo "" && echo "Values: $phrases"
fi
