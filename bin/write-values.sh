#!/usr/bin/env bash
# gist write-values — write values into the canonical digest store from JSON on stdin
# Usage: echo '[{"phrase":"...","pinnedMoment":"..."}]' | write-values.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHONPATH="$ROOT_DIR" python3 -m digest.cli write-values
