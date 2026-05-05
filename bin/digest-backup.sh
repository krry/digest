#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${DIGEST_BACKUP_DIR:-$HOME/backups/digest}"
mkdir -p "$DEST"
STAMP="$(date +%Y%m%d-%H%M%S)"
sqlite3 "$ROOT/digest.db" ".backup '$DEST/digest-$STAMP.db'"
echo "backed up to $DEST/digest-$STAMP.db"
