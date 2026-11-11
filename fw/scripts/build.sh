#!/usr/bin/env bash
# Build the firmware for the MIMXRT1064-EVK (runs in Renode).
# Usage (inside WSL or Linux): scripts/build.sh [extra west build args]
#   FQ_IMAGE=test  (default) prj.conf + test.conf: the image the Renode tests
#                    run; it has the acoustic plant and fault-injection hooks
#   FQ_IMAGE=field prj.conf alone
set -euo pipefail
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"

case "${FQ_IMAGE:-test}" in
test) EXTRA=(-DEXTRA_CONF_FILE=test.conf) ;;
field) EXTRA=() ;;
*) echo "FQ_IMAGE must be test or field" >&2; exit 2 ;;
esac

cd "$WS"
west build -p auto -b mimxrt1064_evk -d "$BUILD" "$REPO/app" "$@" -- "${EXTRA[@]}"
