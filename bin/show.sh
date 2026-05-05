#!/usr/bin/env bash
# gist show — render the goal tree from the canonical digest store
# Usage: show.sh [all]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SHOW_ALL="${1:-}"
if [[ "$SHOW_ALL" == "all" ]]; then
  PYTHONPATH="$ROOT_DIR" python3 -m digest.cli show --all
else
  PYTHONPATH="$ROOT_DIR" python3 -m digest.cli show
fi
