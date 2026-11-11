#!/usr/bin/env bash
# Run vm-test.sh for several distributions in parallel (as root).
#   sudo tests/run-all.sh yes|no laptop|desktop void arch debian
set -u
LOGS=/var/tmp/niruboot-logs
mkdir -p "$LOGS"
ENC=$1; FORM=$2; shift 2
cd "$(dirname "$0")/.." || exit 1
for d in "$@"; do
  ( timeout 4200 bash tests/vm-test.sh "$d" "$ENC" "$FORM" > "$LOGS/$d.log" 2>&1; echo "exit=$?" >> "$LOGS/$d.log" ) &
done
wait
for d in "$@"; do
  echo "=== $d"
  grep -E '^== |installed in|^PASS|^FAIL|INSTALL FAILED|exit=' "$LOGS/$d.log"
done
