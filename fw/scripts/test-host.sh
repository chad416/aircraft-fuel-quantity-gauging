#!/usr/bin/env bash
# Build and run the host unit tests for lib/fq with GCC 14 coverage
# (statements, branches and MC/DC via -fcondition-coverage), then print the
# coverage summary. Usage: fw/scripts/test-host.sh [--no-cov]
# Output: fw/build/host/ (binary, .gcda/.gcno, gcov JSON).
set -euo pipefail
FW="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${FQ_HOST_BUILD:-$FW/build/host}"
CC="${CC:-gcc-14}"
GCOV="${GCOV:-gcov-14}"
PY="${PYTHON:-python3}"

rm -rf "$OUT"
mkdir -p "$OUT/obj"
WARN=(-std=c99 -Wall -Wextra -Wpedantic -Werror -Wconversion -Wshadow -Wcast-qual -Wstrict-prototypes -Wdouble-promotion)
COV=(--coverage -fcondition-coverage -fprofile-update=atomic)
[ "${1:-}" = "--no-cov" ] && COV=()

for f in "$FW"/lib/fq/src/*.c; do
	"$CC" "${WARN[@]}" "${COV[@]}" -O0 -g -I"$FW/lib/fq/include" \
		-c "$f" -o "$OUT/obj/$(basename "${f%.c}").o"
done
"$CC" -std=gnu11 -Wall -Wextra -Werror -O1 -g -I"$FW/lib/fq/include" \
	"$FW"/tests/unit/*.c "$OUT"/obj/*.o "${COV[@]}" -lm -o "$OUT/fq_tests"

"$OUT/fq_tests"

if [ ${#COV[@]} -gt 0 ]; then
	(cd "$OUT/obj" && "$GCOV" --conditions --branch-probabilities --json-format --stdout \
		./*.o > "$OUT/coverage.json" 2>/dev/null)
	"$PY" "$FW/tools/coverage.py" "$OUT/coverage.json" --src lib/fq/src ${FQ_COV_ARGS:-}
fi
