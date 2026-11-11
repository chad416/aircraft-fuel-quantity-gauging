# Open items

This file lists only what needs hardware, a fuel rig or a laboratory. Everything that software and models can close is closed in this repository.

| ID | Item | Why it is open | How it closes |
|---|---|---|---|
| H1 | Measurement front end: AC excitation, synchronous demodulation, reference-capacitor check | no hardware; the Renode test feeds capacitances through an acquisition frame | breadboard on an RT1064 EVK with an analogue front end; verify 0.05 pF offset and 0.1 % gain (docs/sources.md §5) |
| H2 | Intrinsic safety: energy and current into the tank, normal and failed | analysis only (DOSSIER §7.3) | measure against AC 25.981-1D §7.2–7.3 with the 1 kΩ series resistors in place |
| H3 | Tank calibration | the table comes from the geometry model | metered fuelling at several attitudes on a tank or wing rig |
| H4 | DO-160G qualification: Sections 4, 5, 9, 11, 16, 22 | needs a laboratory | test plan in DOSSIER §11 |
| H5 | Probe drift statistics | the failure rates in S7 are order-of-magnitude assumptions | service data or accelerated ageing in fuel |
| H6 | Slosh and dynamic surface | the 8 s filter is an assumption | a sloshing-tank test, or a CFD study of a tank bay |
