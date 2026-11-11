"""Sourced and assumed input data.

Every value carries its status and a reference key (DOSSIER.md §17, docs/sources.md):
V = read in the source, D = derived from V values by a stated method, A = assumption of
this study.  Units are SI unless the name says otherwise.
"""

from __future__ import annotations

import math

# ---- physical constants ---------------------------------------------------------------------
EPS0 = 8.8541878128e-12  # F/m, vacuum permittivity, CODATA 2018 [R10] (V)
G0 = 9.80665  # m/s^2, standard gravity [R10] (V)

# ---- pure hydrocarbons: static permittivity [R5] and density [R6] ---------------------------
# eps at t_eps (deg C), a = -d(eps)/dt in units of 1e-2 per deg C (NBS Circular 514, eq. (1));
# rho in g/cm^3 at t_rho.  Where the density is quoted at 25 C, eps is moved to 25 C with a.
# Class: P = paraffin, N1 = mono-cycloparaffin, N2 = di-cycloparaffin, A = alkylbenzene.
COMPOUNDS = {
    "n-decane": {"cls": "P", "eps": 1.991, "t_eps": 20.0, "a": 0.130, "rho": 0.730, "t_rho": 25.0},
    "n-dodecane": {"cls": "P", "eps": 2.014, "t_eps": 20.0, "a": 0.120, "rho": 0.7495, "t_rho": 20.0},
    # a for methylcyclohexane is illegible in the scan; the paraffin value 0.13 is used (A)
    "methylcyclohexane": {"cls": "N1", "eps": 2.020, "t_eps": 20.0, "a": 0.130, "rho": 0.770, "t_rho": 25.0},
    "cis-decalin": {"cls": "N2", "eps": 2.19, "t_eps": 20.0, "a": 0.11, "rho": 0.8965, "t_rho": 25.0},
    "trans-decalin": {"cls": "N2", "eps": 2.172, "t_eps": 20.0, "a": 0.11, "rho": 0.8659, "t_rho": 25.0},
    "toluene": {"cls": "A", "eps": 2.379, "t_eps": 25.0, "a": 0.243, "rho": 0.8623, "t_rho": 25.0},
}
# second temperature points in [R5], used to derive the thermal expansion through Clausius-Mossotti
EPS_T2 = {"n-decane": (2.050, -30.0), "n-dodecane": (2.047, -10.0)}

WATER_EPS = 78.5  # free water at 25 C [R5] section A (V)

# ---- jet fuel specification [R7] --------------------------------------------------------------
RHO15_MIN = 775.0  # kg/m^3 at 15 C, Jet A / Jet A-1 (V)
RHO15_MAX = 840.0  # (V)
AROM_MAX = 0.25  # volume fraction, aromatics maximum (V via [R7]; ASTM D1655 Table 1)
FUEL_T_MIN = -40.0  # C, operating fuel temperature range (A; Jet A-1 freezes at -47 C [R7])
FUEL_T_MAX = 50.0  # C (A)
# composition ranges of spec-compliant kerosene (mass fractions, A): aromatics 8-25 %,
# cycloparaffins 15-40 % of which 10-40 % bicyclic, rest paraffins (normal + iso)
COMP_AROM = (0.08, 0.25)
COMP_NAPH = (0.15, 0.40)
COMP_N2_SHARE = (0.10, 0.40)

# ---- tank and wing geometry (one integral wing tank, local frame) ---------------------------
# x aft from the front spar at the root (m), y outboard from the aircraft centreline (m), z up.
# A 19-seat twin-turboprop class high wing (all A; no particular aircraft).
WING = {
    "y_root": 1.20,  # inboard tank rib
    "y_tip": 4.20,  # outboard tank rib
    "chord_root": 2.50,  # wing chord at y_root
    "chord_tip": 1.90,
    "tc_root": 0.17,  # thickness/chord
    "tc_tip": 0.1475,
    "box_front": 0.15,  # front spar, fraction of chord
    "box_rear": 0.60,  # rear spar
    "sweep_le_deg": 1.0,  # leading-edge sweep
    "dihedral_deg": 1.5,
    "structure_frac": 0.03,  # volume taken by stringers, ribs, probes (A)
}
DEAD_ZONE = 0.008  # m, inactive length at each probe end (end caps, standoffs) (A)

# ---- probes (coaxial capacitors) ------------------------------------------------------------
PROBE_RI = 0.011  # m, inner electrode outer radius (A)
PROBE_RO = 0.014  # m, outer electrode inner radius (A)
PROBE_K = 2.0 * math.pi * EPS0 / math.log(PROBE_RO / PROBE_RI)  # F/m, coaxial capacitor (D)
PROBE_C_END = 3.0e-12  # F, end and stray capacitance included in C_dry (A)
COMP_LEN = 0.08  # m, compensator active length, always submerged above unusable fuel (A)

# ---- measurement errors (1 sigma, A) ---------------------------------------------------------
ERR = {
    "c_offset": 0.05e-12,  # F, front-end offset after calibration
    "c_gain": 0.001,  # relative gain (ratiometric against a reference capacitor)
    "c_dry_cal": 0.10e-12,  # F, residual of the stored dry capacitance
    "z_install": 0.001,  # m, probe vertical installation tolerance
    "strat_dT_max": 10.0,  # K, top-to-bottom temperature difference, uniform 0..max, warm on top
    "densitometer": 0.0015,  # relative, vibrating-element densitometer (A)
}

# ---- envelope of fuel-surface tilts the gauge must meet accuracy in (A, DOSSIER §2) ----------
# tilt_x = atan((a_fwd + g sin(theta)) / (g cos(theta))), nose-up / accelerating positive
# tilt_y = atan(n_y / n_z): sideslip or a wing-low parked attitude (zero in a coordinated turn)
TILT_X_DEG = (-5.0, 12.0)
TILT_Y_DEG = (-5.0, 5.0)

# ---- requirements numbers (DOSSIER §5) -------------------------------------------------------
REQ_ACC_FS = 0.02  # +/-2 % of full scale, all probes healthy, 95 % of states (A: usual accuracy class)
REQ_ACC_FS_1F = 0.03  # +/-3 % of full scale with one probe failed and excluded (A)
REQ_MISLEAD_FS = 0.05  # undetected error above this is "misleading" (A, FHA §10)
