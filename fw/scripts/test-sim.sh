#!/usr/bin/env bash
# Run the Robot Framework integration tests in Renode against the built firmware.
# Usage (inside WSL): scripts/test-sim.sh [robot file, default tests/robot/fq.robot] [extra renode-test args]
set -euo pipefail
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"

SUITE="${1:-tests/robot/fq.robot}"
shift || true
OUT="${FQ_ROBOT_OUT:-$WS/fqis-robot-out}"
mkdir -p "$OUT"
# renode-test writes its reports to the current directory, and mishandles a
# current directory that contains spaces.
cd "$OUT"
renode-test -r "$OUT" --variable "ELF:$BUILD/zephyr/zephyr.elf" --variable "OUT:$OUT" "$@" "$REPO/$SUITE"
