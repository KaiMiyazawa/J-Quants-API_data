#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="run/logs"
mkdir -p "$LOG_DIR"

FROM_DATE="${1:-2006-02-02}"
TO_DATE="${2:-2026-02-01}"
INCR_DATE="${3:-$(date +%F)}"

.venv/bin/python -u -m src.main backfill --from "$FROM_DATE" --to "$TO_DATE" | tee "$LOG_DIR/backfill.log"
.venv/bin/python -u -m src.main bulk-sync | tee "$LOG_DIR/bulk-sync.log"
.venv/bin/python -u -m src.main incremental --date "$INCR_DATE" | tee "$LOG_DIR/incremental-$INCR_DATE.log"
