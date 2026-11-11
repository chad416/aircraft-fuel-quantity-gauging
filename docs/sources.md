# Sources: what every number rests on

This is the source register for DOSSIER.md and for `model/fqsim/data.py`. It was compiled on 10–11 Nov 2026. The reference keys match DOSSIER §17.

**Status labels**
- **V:** I read the number in the source myself, from PDF text extraction or the web page.
- **D:** I derived it from V values. The method is given, so the calculation can be repeated.
- **A:** an assumption of this study. It is given with the reason for its value.
- **S:** a standard textbook result. It is not tied to one page.

**Access notes**
- RTCA DO-178C, DO-160G, SAE ARP4754A, ARP4761, ARINC 429 and ASTM D1655 are paid documents and were **not** read. The repository uses them only for structure: the development assurance levels, the section numbers it names, and the ARINC 429 word layout as widely published. Every number from them is marked A.
- No manufacturer data for a particular aircraft or gauging system is used. The tank and probe geometry are this study's own (A).

---

## 1. Regulations and advisory material

| Quantity | Value | Source | Where | Status |
|---|---|---|---|---|
| Minimum spark ignition energy of hydrocarbon fuel vapour | 200 µJ | [R2] FAA AC 25.981-1D (2018) | §7.2.1, p. 8 (PDF p. 12) | V |
| Design energy that is technologically feasible / acceptable in normal operation / limit under failure | 20 µJ / 50 µJ / 200 µJ | [R2] | §7.2.2, p. 9 | V |
| Steady current into a tank / under failure / induced transient peak | 25 mA rms / 50 mA rms / 125 mA peak | [R2] | §7.3, p. 9 | V |
| Filament (steel-wool) ignition current | about 100 mA rms | [R2] | §7.3 | V |
| Class IV (commuter) allowable probability: Minor / Major / Hazardous / Catastrophic | < 10⁻³ / < 10⁻⁵ / < 10⁻⁷ / < 10⁻⁹ per flight hour | [R3] FAA AC 23.1309-1E (2011) | Fig. 2, p. 23 (PDF p. 25) | V |
| Class IV development assurance: Major P = C, S = D; Hazardous P = B, S = C; Catastrophic P = A, S = B | — | [R3] | Fig. 2 | V |
| "Display of fuel level indication": loss, loss of primary means, and misleading all rated Minor, for a Class I single-engine example, "pilot is required to calculate fuel range and endurance" | — | [R3] | App. 1 FHA table, p. 45 (PDF p. 47) | V |
| A fuel quantity indicator shall read zero in level flight when the fuel left equals the unusable fuel | — | [R1] CS 25.1337(b) / 14 CFR 25.1337(b) | paragraph (b)(1) | S. This is the well-known wording; the current text was not re-opened in this session. |

## 2. Permittivity and density of hydrocarbons

| Quantity | Value | Source | Where | Status |
|---|---|---|---|---|
| ε of n-decane at 20 °C; −dε/dt; ε at −30 °C | 1.991; 0.130 × 10⁻² /°C; 2.050 | [R5] NBS Circular 514 (Maryott & Smith 1951) | Table C, C10H22 | V |
| ε of n-dodecane at 20 °C; −dε/dt; ε at −10 °C | 2.014; 0.120 × 10⁻²; 2.047 | [R5] | Table C, C12H26 (PDF p. 44) | V |
| ε of methylcyclohexane at 20 °C | 2.020 | [R5] | Table C, C7H14 | V. The temperature coefficient cannot be read in the scan; the paraffin value 0.13 × 10⁻² is used (A). |
| ε of cis- and trans-decalin at 20 °C | 2.19; 2.172 (−dε/dt 0.11 × 10⁻²) | [R5] | Table C, C10H18 | V |
| ε of toluene at 25 °C; −dε/dt | 2.379; 0.243 × 10⁻² | [R5] | Table C, C7H8 (PDF p. 31) | V |
| ε of water at 25 °C | 78.5 | [R5] | section A, standard liquids | V |
| Accuracy of the four-figure values | 0.5 % or better | [R5] | §2.4 | V |
| Density: n-decane 0.730, n-dodecane 0.7495 (20 °C), methylcyclohexane 0.77, cis-decalin 0.8965, trans-decalin 0.8659, toluene 0.8623 (25 °C) | g/cm³ | [R6] compound data pages (Wikipedia infoboxes; the standard state is 25 °C where no temperature is given) | infobox | V (secondary) |
| Refractive index of n-dodecane | 1.421 | [R6] | infobox | V. Used only as an independent check: ε ≈ n² gives r within 1.5 % (`model/tests`). |
| Clausius–Mossotti (Lorentz–Lorenz): (ε − 1)/(ε + 2) = rρ; the specific polarisation r is additive by mass fraction | — | [R8] textbook | e.g. Böttcher, *Theory of Electric Polarization*; Jackson §4.5 | S |
| Specific polarisation per class: paraffin 3.378, monocycloparaffin 3.280, bicycloparaffin 3.195, alkylbenzene 3.652 (× 10⁻⁴ m³/kg) | — | [R5], [R6] | Clausius–Mossotti at 25 °C | D (S1) |
| Thermal expansion α from dε/dT at constant r | 8.6 × 10⁻⁴ /K (n-decane), 7.9 × 10⁻⁴ /K (n-dodecane), mean 8.3 × 10⁻⁴ /K | [R5] | Clausius–Mossotti | D (S1) |

## 3. Jet fuel

| Quantity | Value | Source | Where | Status |
|---|---|---|---|---|
| Density range, Jet A / Jet A-1 | 775–840 kg/m³ at 15 °C | [R7] jet fuel article (infobox), from the ASTM D1655 / DEF STAN 91-091 limits | infobox | V (secondary) |
| Jet A-1 freezing point | −47 °C | [R7] | properties table | V (secondary) |
| Aromatics maximum | 25 vol % | ASTM D1655 Table 1 (as cited by [R7]) | — | A (the standard was not opened) |
| Composition ranges used: aromatics 8–25 %, cycloparaffins 15–40 % (10–40 % of them bicyclic), rest paraffins | — | — | — | A |

## 4. Geometry, electromagnetics and constants

| Quantity | Value | Source | Status |
|---|---|---|---|
| ε0 | 8.8541878128 × 10⁻¹² F/m | [R10] CODATA 2018 | V |
| Coaxial capacitance per metre 2πε0 / ln(r_o/r_i) | 230.7 pF/m for r_i = 11 mm, r_o = 14 mm | [R11] textbook formula | S / D |
| NACA four-digit thickness distribution | y_t = 5t(0.2969√x − 0.1260x − 0.3516x² + 0.2843x³ − 0.1015x⁴) | [R9] NACA Report 824 (Abbott, von Doenhoff & Stivers, 1945) | S |
| Wing tank: y 1.20–4.20 m, chord 2.50→1.90 m, t/c 17→14.75 %, spars at 15 % and 60 % chord, dihedral 1.5° | — | — | A (19-seat twin-turboprop class) |
| Tank volume (one wing) / usable full scale at 800 kg/m³ / unusable fuel (20 mm sump) | 0.932 m³ / 743.9 kg / 1.7 L | `model/fqsim/tank.py` | D |

## 5. Measurement errors (all A; 1 σ)

| Quantity | Value | Reason |
|---|---|---|
| Front-end offset after calibration | 0.05 pF | ratiometric measurement against an on-board reference capacitor |
| Front-end gain | 0.1 % | same |
| Stored C_dry residual | 0.1 pF | per-probe calibration at manufacture |
| Probe installation height | 1 mm | rib-mounted brackets |
| Thermal stratification | 0–10 K, warm fuel on top (the stable case) | after ground soak or climb |
| Densitometer | 0.15 % | vibrating-element type |

## 6. Envelope

| Quantity | Value | Status |
|---|---|---|
| Fuel temperature | −40 to +50 °C | A |
| Longitudinal / lateral surface tilt in the accuracy envelope | −5 to +12° / ±5° | A |
| Take-off roll: 0.25 g falling to 0.13 g, rotation at 4°/s to 10° | — | A (S2) |
