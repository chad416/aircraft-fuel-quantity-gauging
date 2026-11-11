# MISRA C:2012 compliance (gauge library)

**Scope:** `fw/lib/fq/src` and `fw/lib/fq/include`. This is the code that the host tests and the firmware share, including the generated data file `fq_data.c`.

**Checker:** cppcheck 2.13 with its MISRA addon, run by `fw/scripts/misra.sh`.
- The script fails on any output at all, because cppcheck's exit code does not cover every addon finding.
- The Zephyr glue in `fw/app/src/main.c` is out of scope.

**Limits of the check:** this is a developer-level check, not a qualified MISRA compliance tool. Without the licensed rule texts, cppcheck reports rule numbers only.

## Result

No findings remain apart from deviations D1 and D2. These were fixed while setting up the check on 11 Nov 2026:

| Rule | Where | Fix |
|---|---|---|
| 10.3 (assignment to a narrower essential type) | `a429.c`, `1UL << i` into a `uint32_t` (64-bit `unsigned long` on the host) | Unsigned-int constants throughout. |
| 10.8 (composite expression cast to a different essential type) | `(float)(1UL << 18)` in `a429.c`; `(float)(n - 1U)` in `solve.c`; `(uint8_t)(excluded + 1)` in `frame.c` | Float constants `TWO18` and `DATA_MAX_F`; `(float)n - 1.0f`; an explicit non-negative branch. |
| 10.6 (composite expression assigned to a wider type) | ternary in `fq_no_data` | Rewritten as an `if`. |
| cppcheck knownConditionTrueFalse | leave-one-out search in `solve.c` | Moved into `best_subset()`, which returns a `found` flag. |
| cppcheck variableScope / unreadVariable | `solve.c`, `frame.c`, `fqc.c` | Declarations moved into their blocks. |

## Deviations

| ID | Rule | Category | Where | Reason |
|---|---|---|---|---|
| D1 | 2.5: a project should not contain unused macro definitions | Advisory | `fq.h` | `fq.h` is the public interface and the frame-protocol definition. Some of its macros are used only by the application, the tests and the Renode rig, which are all outside the analysed file set. Examples: the SSM code `FQ_SSM_FT`, and the status bits that the rig decodes. |
| D2 | 8.7: functions referenced in one translation unit should have internal linkage | Advisory | `solve.c` | `fq_rho_from_eps` and `fq_weight` are public API. The unit tests and the application call them, outside the analysed file set. |

## Design rules followed (not only checked)

- No dynamic memory.
- No recursion.
- No library calls; the core does not even use `<math.h>`.
- All state lives in caller-owned structs.
- Single-precision float with explicit `f` suffixes; `-Wdouble-promotion` and `-Wconversion` are on as errors.
- Explicit casts wherever a value is narrowed.
- `if`/`else if` chains end with `else`.
- Loops are bounded by `FQ_NP`, `FQ_NT` or table sizes. The only `while` loop is the 8-element insertion sort in the monitor lane.
