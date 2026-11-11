# Changelog

## Rev A, 11 Nov 2026
- Studies S1–S8. The fuel model uses Clausius–Mossotti with pure-compound data; there are also the tank and surface model, probe placement, the Monte Carlo budget, fault detection and exclusion, the AoA, and the fault tree with intrinsic safety.
- Gauge library in C99 (`fw/lib/fq`):
  - verified back to back against the model on 160 vectors;
  - 100 % MC/DC;
  - MISRA C:2012 with two advisory deviations.
- Zephyr application for the RT1064 and Renode tests IT01–IT07.
- Defects found and fixed:
  - BNR rounding into the sign bit;
  - a fallback status mismatch between the model and the firmware;
  - the FULL band and the plane-geometry threshold in the model.
