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
ZIP_FILE="$OUTPUT_DIR/$TIMESTAMP.zip"

mkdir -p "$OUTPUT_DIR"

export MEGARAID_STORCLI_LOG_DIR="$OUTPUT_DIR"
export MEGARAID_OUTPUT_DIR="$OUTPUT_DIR"
export MEGARAID_REPORT_TIMESTAMP="$TIMESTAMP"
OUTPUT=$(python3 "$SCRIPT_DIR/megaraid-state-disk.py" "$@")
case "$OUTPUT" in
  *"by WiseSoft ©2026"*) ;;
  *) OUTPUT=$(printf '%s\n\n%s' "by WiseSoft ©2026" "$OUTPUT") ;;
esac
printf '%s\n' "$OUTPUT" > "$OUTPUT_FILE"

if [ -t 1 ] && [ "${NO_COLOR:-}" = "" ] && [ "${MEGARAID_COLOR:-auto}" != "never" ]; then
  printf '%s\n' "$OUTPUT" | awk '
    BEGIN {
      reset = "\033[0m"
      bold = "\033[1m"
      dim = "\033[2m"
      red = "\033[31m"
      green = "\033[32m"
      yellow = "\033[33m"
      cyan = "\033[36m"
      magenta = "\033[35m"
    }
    /^by WiseSoft/ || /^Controller:/ || /^Action list:/ || /^Life source:/ || /^Raw smartctl files:/ {
      print bold cyan $0 reset
      next
    }
    /^  Status: OK/ || /^  Enclosure: OK/ || /^  Virtual drive .* Optl / {
      print green $0 reset
      next
    }
    /^Overall status: CRITICAL/ || /^  CRITICAL:/ || /^CRITICAL[[:space:]]/ {
      print bold red $0 reset
      next
    }
    /^Overall status: WARN/ || /^  WARN:/ || /^WARN[[:space:]]/ {
      print bold yellow $0 reset
      next
    }
    /^Overall status: OK/ || /^OK[[:space:]]/ {
      print bold green $0 reset
      next
    }
    /^Status[[:space:]]/ {
      print bold magenta $0 reset
      next
    }
    /^-+$/ {
      print dim $0 reset
      next
    }
    /^  DID / {
      print dim $0 reset
      next
    }
    {
      print
    }
  '
else
  printf '%s\n' "$OUTPUT"
fi

if [ -f "$OUTPUT_DIR/storcli.log" ]; then
  cp "$OUTPUT_DIR/storcli.log" "$OUTPUT_DIR/storcli-debug-$TIMESTAMP.log"
fi

python3 -c '
import os
import sys
import zipfile

output_dir, timestamp, zip_file = sys.argv[1], sys.argv[2], sys.argv[3]

def include(name):
    if name == f"megaraid-state-disk-{timestamp}.txt":
        return True
    if name == f"storcli-debug-{timestamp}.log":
        return True
    if name == "storcli.log":
        return True
    if name.startswith("smartctl-megaraid-") and name.endswith(f"-{timestamp}.txt"):
        return True
    if name.startswith("storcli-c") and name.endswith(f"-{timestamp}.txt"):
        return True
    return False

with zipfile.ZipFile(zip_file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for name in sorted(os.listdir(output_dir)):
        path = os.path.join(output_dir, name)
        if os.path.isfile(path) and include(name):
            archive.write(path, arcname=name)
' "$OUTPUT_DIR" "$TIMESTAMP" "$ZIP_FILE"

find "$OUTPUT_DIR" -maxdepth 1 -type f \( -name '*.txt' -o -name '*.log' \) -delete

if [ -t 2 ] && [ "${NO_COLOR:-}" = "" ] && [ "${MEGARAID_COLOR:-auto}" != "never" ]; then
  printf '\033[2mSaved zip to: %s\033[0m\n' "$ZIP_FILE" >&2
else
  printf 'Saved zip to: %s\n' "$ZIP_FILE" >&2
fi
