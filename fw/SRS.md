# Gauge-computer software requirements (SRS)

Rev A, 11 Nov 2026. These requirements derive from the system requirements in [DOSSIER.md §5](../DOSSIER.md) (SYS-n).
Each one is stated as subject, shall, outcome and condition, after Wasson 2016 ch. 22.

`fw/tools/trace.py` checks that every requirement below appears in [docs/traceability.md](docs/traceability.md)
and has at least one test that exists. The algorithm itself is specified by `model/fqsim/gauge.py`.

## 1. Performance

- **FQ-01 (SYS-1):** The gauge shall indicate the usable fuel mass of each tank, and the total, within ±2 % of full scale. This holds for 95 % of states in the gauging envelope with all probes healthy.
  - Rationale: S4 gives 0.65 % FS at the 95th percentile.
- **FQ-02 (SYS-4):** With one probe failed and excluded, the gauge shall indicate within ±3 % of full scale.
  - Rationale: S5 gives 0.61 % FS at the 95th percentile after exclusion.
- **FQ-03 (SYS-2):** The gauge shall indicate zero usable fuel when the quantity left equals the unusable fuel in level flight (CS 25.1337(b)).
- **FQ-05 (SYS-6):** The worst-case computation time of one cycle shall be below 10 ms, which is 10 % of the 100 ms cycle.

## 2. Single-cycle core

- **FQ-10 (SYS-1):** The gauge shall compute the permittivity from the compensator. It shall accept the value only inside [1.85, 2.45].
- **FQ-11 (SYS-4):** Each probe shall be classed by its capacitance:
  - OPEN: below C_dry − 2 pF.
  - SHORT or water: above the full-probe value at ε 2.45 + 2 pF.
  - DRY: wetted height ≤ 2 mm.
  - FULL: wetted height ≥ 97.5 % of the length − 2 mm. A full probe can read up to 2 % short (S4).
  - LIVE: anything else.
- **FQ-12 (SYS-1):** The fuel plane shall be fitted by weighted least squares through at least 3 LIVE probes.
  - The weights are 1/(σ0² + (κh)²), with σ0 = 1.2 mm and κ = 1.2 %.
  - The fit shall be rejected if the determinant of the weighted position covariance is below 3·10⁻³ m⁴.
- **FQ-13 (SYS-1):** The volume shall be interpolated trilinearly in the attitude table:
  - 25 × 17 × 65 points;
  - slopes −0.18 to 0.36 and ±0.14;
  - the normalised plane height.

  Slopes outside the table shall make the result invalid.
- **FQ-14 (SYS-3):** With at least 4 LIVE probes, the gauge shall compare the weighted residual with the chi-square threshold for n − 3 degrees of freedom (P_fa 10⁻⁵).
- **FQ-15 (SYS-4):** If the residual test fails:
  - With at least 5 LIVE probes, the gauge shall exclude the probe whose removal leaves the smallest residual, provided the rest then passes.
  - Otherwise the tank result shall be invalid.
- **FQ-16 (SYS-3):** DRY and FULL probes shall agree with the plane within 15 mm.
  - A disagreement with a verified plane (at least 4 LIVE probes, passed) marks the probe suspect.
  - A disagreement with an unverified plane drops that plane, and the gauge uses the fallback.
- **FQ-17 (SYS-4):** Without a usable plane, the gauge shall take the slopes from the specific force. If that is not valid, it shall use the slopes of the last verified plane. If neither exists, the result shall be invalid.
  - The height is the mean of the LIVE probes.
  - With no LIVE probe, the gauge reports the lowest plane that covers every FULL probe, or empty if all probes are DRY. The indication is then never above the true quantity.
- **FQ-18 (SYS-1):** The density shall be CM(ε)/r_nom (Clausius–Mossotti), or the densitometer value when that is valid.
- **FQ-30 (SYS-3):** The monitor lane (MON) shall compute the usable volume a different way: slopes from the specific force, height from the median of the LIVE probes.

## 3. Gauge computer

- **FQ-40 (SYS-6):** The computer shall run one cycle every 100 ms on the newest acquisition frame.
- **FQ-41 (SYS-3):** If both compensators are plausible but differ by more than 0.03, both tanks shall use the larger ε, which gives the lower mass. The XCOMP bit shall be set.
  - When the own compensator is implausible, the order is: the other tank's value, then the last good value, then the default 2.13.
- **FQ-42 (SYS-4):** A range fault, an exclusion or a DRY/FULL contradiction that persists for 3 cycles shall latch the probe as failed until power-down.
- **FQ-43 (SYS-4):** The slopes of every verified plane shall be kept for the fallback.
- **FQ-44 (SYS-1):** The indicated mass shall be filtered with a first-order filter, τ 8 s.
  - It is held while the result is invalid.
  - It is dropped after 3 s of invalid results.
- **FQ-45 (SYS-3):** If COM and MON differ by more than the monitor limit (1.0 % FS, from S5) for 3 s, the tank shall be in FQ FAIL. This is latched.
- **FQ-46 (SYS-5):** The sign/status of each tank shall be failure warning in FQ FAIL, no computed data when invalid, and normal otherwise.
- **FQ-47 (SYS-5):** The total shall be failure warning if either tank is. It shall be normal only if both tanks are. Otherwise it shall be no computed data.
- **FQ-48 (SYS-5):** After 0.5 s without an acquisition frame, both tanks shall be no computed data (a failure warning stays), and the NO DATA bit shall be set.
- **FQ-50 (SYS-2):** LOW FUEL shall be set per tank when either:
  - the independent low-level sensor has been dry for 20 s; or
  - the computed usable mass has been below 60 kg for 20 s.
- **FQ-51 (SYS-3):** FQ DISAGREE shall be set per tank when the sensor has been dry for 60 s while the computed mass is valid and above 100 kg.
- **FQ-52 (SYS-2):** The LOW FUEL lamp discrete shall be on while either tank is LOW FUEL.

## 4. Output words

- **FQ-60 (SYS-5):** The masses shall be sent as ARINC 429 BNR words:
  - labels 256 (left), 257 (right) and 247 (total);
  - 18 data bits, 4096 kg full range;
  - SSM, SDI 0 and odd parity.
- **FQ-61 (SYS-5):** The status bits shall be sent as a discrete word, label 270.
- **FQ-62 (SYS-5):** A BNR value shall be clamped to the data field. A small negative value shall never round into the sign bit (a defect found by the tests).

## 5. Acquisition and output frames

- **FQ-70 (SYS-5):** The acquisition frame shall be `A5 5A len type payload CRC16`. It holds 16 probe and 2 compensator capacitances (0.01 pF), the specific force (mg), two densities and the flags. CRC-16/CCITT-FALSE covers len, type and payload.
- **FQ-71 (SYS-4):** The computer shall reject and count frames with a CRC error, an unknown type or a wrong length. It shall resynchronise on the next sync pair.
- **FQ-72 (SYS-3):** The specific force shall be valid only when it is flagged valid and f_z > 0.1.
- **FQ-73 (SYS-5):** The computer shall send an output frame every cycle, carrying the masses, status, sign/status and the four ARINC 429 words.

## 6. Verification against the model

- **FQ-80 (SYS-1):** The C core shall reproduce the reference model `model/fqsim/gauge.py` on the 160 exported vectors.
  - Decisions must match exactly.
  - Plane within 0.2 mm, volume within 0.01 % FS, mass within 0.1 kg.

## Defects found by the tests

| Where | Defect | Fix |
|---|---|---|
| `a429.c` | Rounding a value just below zero (−0.001 kg) gave a data field of 2¹⁸. That overflowed into the sign bit and decoded as −4096 kg. | The value is clamped after the two's-complement offset. Test: `test_a429.c:test_bnr`. |
| `gauge.py` / `solve.c` | In a fallback the model reported status OK while the C code reported DEGRADED. The back-to-back test showed 37 mismatches. | Model fixed: a fallback is DEGRADED. |
| Model, S4 | A FULL probe read 2 % short through gain and stratification errors. It was taken as LIVE, which made a 48 mm residual. | FULL band made relative (`SAT_REL`); weighted residual (FQ-11, FQ-12). |
| Model, S3/S4 | A plane from a tight cluster of probes extrapolated badly across the span: 0.8 % of healthy states were invalid, up to 2.2 % FS error. | Geometry threshold raised to 3·10⁻³ m⁴, layout re-chosen, unverified planes fall back (FQ-12, FQ-16). |
