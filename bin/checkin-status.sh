#!/usr/bin/env bash
# gist checkin-status — check throttle and read context for check-in
# Prints: RECENT: <date>  OR  READY followed by values+goals JSON
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CHECKINS="$ROOT_DIR/checkins.json"
VALUES="$ROOT_DIR/values.json"
GOALS="$ROOT_DIR/goals.json"
FORCE="${1:-}"

if [[ -f "$CHECKINS" && -z "$FORCE" ]]; then
  last=$(jq -r '.checkins[-1].date // empty' "$CHECKINS")
  if [[ -n "$last" ]]; then
    today=$(date +%Y-%m-%d)
    days=$(python3 -c "from datetime import date; print((date.fromisoformat('$today') - date.fromisoformat('$last')).days)")
    if [[ "$days" -lt 20 ]]; then
      echo "RECENT: $last"
      exit 0
    fi
  fi
fi

echo "READY"

# emit context for Claude to reason over
echo "=== VALUES ==="
[[ -f "$VALUES" ]] && jq -r '.values[] | "• \(.phrase) — \(.pinnedMoment)"' "$VALUES" || echo "(none)"

echo "=== ACTIVE GOALS ==="
[[ -f "$GOALS" ]] && jq -r '.nodes[] | select(.status == "active") | "[\(.type)] \(.title)"' "$GOALS" || echo "(none)"
