"""Model tests: physics against closed forms and sources, the gauge against the truth model,
and the firmware constants against the model (the C library mirrors gauge.py)."""

from __future__ import annotations

import math
import os
import re

import numpy as np
import pytest

from fqsim import data, design, fuel, gauge, probe, tank

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---- fuel ------------------------------------------------------------------------------------
def test_clausius_mossotti_roundtrip():
    for e in (1.9, 2.1, 2.4):
        assert fuel.eps_from_cm(fuel.cm(e)) == pytest.approx(e, rel=1e-12)


def test_alkane_specific_polarisation_matches_refraction():
    # non-polar liquid: eps ~ n^2 (Maxwell); n-dodecane n_D = 1.421 [R6] gives r within 1.5 %
    r_n = fuel.cm(1.421**2) / 749.5
    assert fuel.compound_r()["n-dodecane"] == pytest.approx(r_n, rel=0.015)


def test_toluene_is_polar_outlier():
    r = fuel.compound_r()
    assert r["toluene"] > 1.07 * r["n-decane"]


def test_expansion_coefficient_plausible():
    # liquid kerosene-range hydrocarbons: about 8-10e-4 per K
    assert 7e-4 < fuel.ALPHA < 1e-3


def test_nominal_fuel_permittivity():
    e = float(fuel.NOMINAL.eps(15.0))
    assert 2.08 < e < 2.18
    assert fuel.rho_from_eps(e) == pytest.approx(fuel.NOMINAL.rho15, rel=1e-9)


# ---- tank -------------------------------------------------------------------------------------
def test_naca_thickness_max():
    xi = np.linspace(0, 1, 2001)
    y = fuel_free = tank.naca_half_thickness(xi, 0.12)
    assert 2 * y.max() == pytest.approx(0.12, rel=2e-3)
    assert xi[np.argmax(fuel_free)] == pytest.approx(0.30, abs=0.01)


def test_volume_column_integration_against_box():
    t = tank.Tank()
    # a flat plane through the tank: volume equals the sum of clipped column heights
    z = 0.0
    v = t.volume_below(z, 0.0, 0.0)
    manual = np.sum(np.clip(z - t.z_lo, 0, t.depth) * t.dA) * t.fill_frac
    assert v == pytest.approx(manual, rel=1e-12)
    assert t.volume_below(10.0, 0.1, 0.05) == pytest.approx(t.v_full, rel=1e-12)
    assert t.volume_below(-10.0, 0.1, 0.05) == 0.0


def test_volume_is_monotonic_and_invertible():
    t = tank.Tank()
    sx, sy = tank.slopes(6.0, -3.0)
    zs = np.linspace(t.z_empty(sx, sy), t.z_full(sx, sy), 50)
    v = t.volume_below(zs, sx, sy)
    assert np.all(np.diff(v) >= 0)
    z = t.z_for_volume(0.4 * t.v_full, sx, sy)
    assert t.volume_below(z, sx, sy) == pytest.approx(0.4 * t.v_full, rel=1e-6)


def test_tilt_from_specific_force():
    # steady climb at 8 deg: specific force (-g sin, 0, g cos) -> tilt 8 deg
    tx, ty = tank.tilts_from_specific_force(-math.sin(math.radians(8)), 0.0, math.cos(math.radians(8)))
    assert tx == pytest.approx(8.0)
    assert ty == pytest.approx(0.0)
    # coordinated turn: the specific force stays on z: no lateral tilt whatever the bank
    assert tank.tilts_from_specific_force(0.0, 0.0, 1.0 / math.cos(math.radians(30)))[1] == 0.0


# ---- probes and gauge ----------------------------------------------------------------------------
def test_coaxial_capacitance_per_metre():
    k = 2 * math.pi * data.EPS0 / math.log(data.PROBE_RO / data.PROBE_RI)
    assert data.PROBE_K == pytest.approx(k)
    assert 200e-12 < k < 260e-12


def test_gauge_exact_without_errors():
    t = design.the_tank()
    cfg = design.cfg_for()
    probes = design.chosen_probes()
    sx, sy = tank.slopes(4.0, 2.0)
    z = t.z_for_volume(0.5 * t.v_full, sx, sy)
    st = probe.TankState(z, sx, sy, fuel.NOMINAL, 15.0, 0.0)
    caps, cc = probe.measure(t, probes, st)
    r = gauge.solve(cfg, caps * 1e12, cc * 1e12, sf=gauge.sf_from_tilts(4.0, 2.0))
    assert r.status == gauge.ST_OK and r.verified
    v_true = t.volume_below(z, sx, sy)
    assert r.volume == pytest.approx(v_true, abs=0.002 * t.v_full)  # table interpolation
    assert r.rho == pytest.approx(float(fuel.NOMINAL.rho(15.0)), rel=1e-6)


def test_gauge_excludes_a_biased_probe():
    t = design.the_tank()
    cfg = design.cfg_for()
    probes = design.chosen_probes()
    z = t.z_for_volume(0.45 * t.v_full, 0.0, 0.0)
    st = probe.TankState(z, 0.0, 0.0, fuel.NOMINAL, 15.0, 0.0)
    caps, cc = probe.measure(t, probes, st)
    caps = caps * 1e12
    caps[4] += cfg.k_pf[4] * 1.13 * 0.05
    r = gauge.solve(cfg, caps, cc * 1e12, sf=(0.0, 0.0, 1.0))
    assert r.detected and r.excluded == 4


def test_monitor_agrees_with_com_when_healthy():
    t = design.the_tank()
    cfg = design.cfg_for()
    probes = design.chosen_probes()
    sx, sy = tank.slopes(3.0, -1.0)
    z = t.z_for_volume(0.6 * t.v_full, sx, sy)
    st = probe.TankState(z, sx, sy, fuel.NOMINAL, 15.0, 0.0)
    caps, cc = probe.measure(t, probes, st)
    sf = gauge.sf_from_tilts(3.0, -1.0)
    r = gauge.solve(cfg, caps * 1e12, cc * 1e12, sf=sf)
    mv = gauge.monitor(cfg, caps * 1e12, r.eps, sf)
    assert mv == pytest.approx(r.usable, abs=0.003 * t.v_full)


# ---- firmware consistency -------------------------------------------------------------------
def header_defines():
    txt = open(os.path.join(ROOT, "fw", "lib", "fq", "include", "fq", "fq.h"), encoding="utf-8").read()
    out = {}
    for m in re.finditer(r"#define (FQ_\w+)\s+\(?(-?[0-9.eE+-]+)f?U?\)?", txt):
        out[m.group(1)] = float(m.group(2).rstrip("fU"))
    return out


def test_firmware_constants_match_model():
    d = header_defines()
    pairs = {
        "FQ_EPS_MIN": gauge.EPS_MIN,
        "FQ_EPS_MAX": gauge.EPS_MAX,
        "FQ_EPS_DEFAULT": gauge.EPS_DEFAULT,
        "FQ_C_OPEN_PF": gauge.C_OPEN_PF,
        "FQ_C_SHORT_PF": gauge.C_SHORT_PF,
        "FQ_H_SAT": gauge.H_SAT,
        "FQ_SAT_REL": gauge.SAT_REL,
        "FQ_SIGMA_Z": gauge.SIGMA_Z,
        "FQ_KAPPA": gauge.KAPPA,
        "FQ_DET_MIN": gauge.DET_MIN,
        "FQ_SAT_TOL": gauge.SAT_TOL,
        "FQ_SX_MIN": gauge.SX_RANGE[0],
        "FQ_SX_MAX": gauge.SX_RANGE[1],
        "FQ_SY_MIN": gauge.SY_RANGE[0],
        "FQ_SY_MAX": gauge.SY_RANGE[1],
        "FQ_NSX": gauge.N_SX,
        "FQ_NSY": gauge.N_SY,
        "FQ_NU": gauge.N_U,
        "FQ_NP": len(design.CHOSEN),
    }
    for k, v in pairs.items():
        assert d[k] == pytest.approx(v, rel=1e-6), k


def test_generated_data_is_current():
    txt = open(os.path.join(ROOT, "fw", "lib", "fq", "src", "fq_data.c"), encoding="utf-8").read()
    m = re.search(r"fq_r_nom = ([0-9.e+-]+)f", txt)
    assert float(m.group(1)) == pytest.approx(fuel.R_NOM, rel=1e-6)
    p = design.chosen_probes()[0]
    assert ("%.9g" % p.x) in txt
