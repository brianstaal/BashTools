#!/usr/bin/env sh
set -eu

SCRIPT_PATH=$0
if command -v readlink >/dev/null 2>&1; then
  RESOLVED_PATH=$(readlink -f "$0" 2>/dev/null || true)
  if [ -n "$RESOLVED_PATH" ]; then
    SCRIPT_PATH=$RESOLVED_PATH
  fi
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd)
OUTPUT_DIR=${MEGARAID_OUTPUT_DIR:-"$SCRIPT_DIR/output"}
TIMESTAMP=$(date '+%Y%m%d-%H%M%S')
OUTPUT_FILE="$OUTPUT_DIR/megaraid-state-disk-$TIMESTAMP.txt"

mkdir -p "$OUTPUT_DIR"

export MEGARAID_STORCLI_LOG_DIR="$OUTPUT_DIR"
export MEGARAID_OUTPUT_DIR="$OUTPUT_DIR"
export MEGARAID_REPORT_TIMESTAMP="$TIMESTAMP"
OUTPUT=$(python3 "$SCRIPT_DIR/megaraid-state-disk.py" "$@")
printf '%s\n' "$OUTPUT"
printf '%s\n' "$OUTPUT" > "$OUTPUT_FILE"
if [ -f "$OUTPUT_DIR/storcli.log" ]; then
  cp "$OUTPUT_DIR/storcli.log" "$OUTPUT_DIR/storcli-debug-$TIMESTAMP.log"
fi
printf 'Saved output to: %s\n' "$OUTPUT_FILE" >&2
