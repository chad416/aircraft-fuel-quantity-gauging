# Requirement-to-test traceability

Every FQ requirement in [../SRS.md](../SRS.md) maps to at least one kind of evidence:
- unit tests (`tests/unit/file.c:function`);
- Renode integration tests (`tests/robot/fq.robot`, IT01–IT07);
- other evidence (model studies).

`tools/trace.py` fails if a row is missing or names a test that does not exist. CI runs it.

| ID | Parent | Unit tests | Integration tests | Other evidence |
|---|---|---|---|---|
| FQ-01 | SYS-1 | test_vectors.c:test_vectors | IT01, IT02 | model/studies/s4_budget.py |
| FQ-02 | SYS-4 | test_solve.c:test_solve_exclusion | IT03 | model/studies/s5_fde.py |
| FQ-03 | SYS-2 | test_solve.c:test_solve_nominal | | model/fqsim/tank.py (unusable sump) |
| FQ-05 | SYS-6 | | IT07 | |
| FQ-10 | SYS-1 | test_solve.c:test_eps_density | | |
| FQ-11 | SYS-4 | test_solve.c:test_classify | IT03 | model/studies/s4_budget.py |
| FQ-12 | SYS-1 | test_solve.c:test_fit, test_solve.c:test_solve_nominal | IT02 | model/studies/s3_placement.py |
| FQ-13 | SYS-1 | test_solve.c:test_table, test_solve.c:test_solve_fallback | IT02 | |
| FQ-14 | SYS-3 | test_solve.c:test_solve_exclusion | IT03 | model/studies/s5_fde.py |
| FQ-15 | SYS-4 | test_solve.c:test_solve_exclusion, test_solve.c:test_solve_degenerate_subset | IT03 | |
| FQ-16 | SYS-3 | test_solve.c:test_solve_saturated | | |
| FQ-17 | SYS-4 | test_solve.c:test_solve_fallback | IT02 | model/studies/s2_attitude.py |
| FQ-18 | SYS-1 | test_solve.c:test_eps_density, test_solve.c:test_solve_nominal | | model/studies/s1_fuel.py |
| FQ-30 | SYS-3 | test_solve.c:test_monitor | | model/studies/s5_fde.py |
| FQ-40 | SYS-6 | | IT01 | |
| FQ-41 | SYS-3 | test_fqc.c:test_eps_selection | IT05 | |
| FQ-42 | SYS-4 | test_fqc.c:test_persistence | IT03 | |
| FQ-43 | SYS-4 | test_fqc.c:test_nominal | | |
| FQ-44 | SYS-1 | test_fqc.c:test_nominal, test_fqc.c:test_invalid | IT02 | |
| FQ-45 | SYS-3 | test_fqc.c:test_monitor_fail | | model/studies/s5_fde.py |
| FQ-46 | SYS-5 | test_fqc.c:test_monitor_fail, test_fqc.c:test_invalid | IT01 | |
| FQ-47 | SYS-5 | test_fqc.c:test_monitor_fail | | |
| FQ-48 | SYS-5 | test_fqc.c:test_no_data | IT05 | |
| FQ-50 | SYS-2 | test_fqc.c:test_low_fuel | IT04, IT06 | |
| FQ-51 | SYS-3 | test_fqc.c:test_low_fuel | IT06 | |
| FQ-52 | SYS-2 | | IT04 | |
| FQ-60 | SYS-5 | test_a429.c:test_layout, test_a429.c:test_bnr | IT01 | |
| FQ-61 | SYS-5 | test_a429.c:test_discrete | | |
| FQ-62 | SYS-5 | test_a429.c:test_bnr | | |
| FQ-70 | SYS-5 | test_frame.c:test_crc, test_frame.c:test_roundtrip | IT01 | |
| FQ-71 | SYS-4 | test_frame.c:test_parser_errors | | |
| FQ-72 | SYS-3 | test_frame.c:test_roundtrip | | |
| FQ-73 | SYS-5 | test_frame.c:test_out | IT01 | |
| FQ-80 | SYS-1 | test_vectors.c:test_vectors | | model/studies/s8_export.py |
