#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
EXP_ID="$(basename "$SCRIPT_DIR")"

LOG_DIR="$SCRIPT_DIR/outputs/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/train_${TIMESTAMP}.log"

echo "[$EXP_ID] Starting at $(date)"
echo "[$EXP_ID] Log: $LOG_FILE"

cd "$PROJECT_ROOT"
uv run python -u experiments/"$EXP_ID"/train.py 2>&1 | tee "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$EXP_ID] Finished successfully at $(date)"
else
    echo "[$EXP_ID] Failed with exit code $EXIT_CODE at $(date)"
fi

exit $EXIT_CODE
