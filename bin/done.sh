#!/usr/bin/env bash
# gist done — fuzzy-match an active node by title and mark it complete
# Usage: done.sh <search term>
# Exit 0 + prints "DONE: <title>" on success
# Exit 0 + prints "MATCHES:\n..." when ambiguous (Claude picks)
# Exit 1 + prints "NONE" when nothing found
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHONPATH="$ROOT_DIR" python3 -m digest.cli done "$@"
